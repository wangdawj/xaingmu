"""
=============================================================================
MySQL → Pandas 离线清洗管道（Offline Data Cleaning Pipeline）
=============================================================================
【功能说明】
  从 MySQL energy_record 表拉取最近 N 小时数据 → Pandas 清洗 → 异常检测 → 写回质检日志。
  定时执行，与实时 Kafka Consumer 互补。

【为什么需要离线清洗？】
  1. 实时 Consumer 只负责写入，不做数据质量校验
  2. Kafka Producer 模拟数据无真正的脏数据，但真实场景中传感器会产生：
     - 重复上报（同一时间戳多条相同记录）
     - 空值/缺失（传感器断连）
     - 异常值（传感器故障导致读数飙升或归零）

【清洗管道步骤】
  步骤 1：拉取数据    → pd.read_sql 从 MySQL 读取最近 N 小时数据
  步骤 2：去重       → drop_duplicates 按 (building_id, event_time) 删除重复行
  步骤 3：插值       → interpolate 填充缺失值（线性插值补全空值点）
  步骤 4：3σ 过滤    → 剔除偏离均值 3 倍标准差的极端异常点
  步骤 5：滚动窗口检测 → 检测滑动窗口均值 × 2 倍突增点（区分于持续性故障）
  步骤 6：写回质检日志 → 记录本次清洗的影响范围到 data_quality_log 表

【运行方式】
  - 手动运行：python run_mysql_cleaning.py
  - 定时运行：由 data-pipeline/run_all.py 的 CleaningLoop 线程调度（每 10 分钟一次）
=============================================================================
"""

# ======================== 导入模块 ========================
import sys
import os
# 添加父目录到 sys.path，确保可以导入 cleaning 包中的清洗函数
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd              # 数据处理核心库
import pymysql                   # MySQL 原生驱动（用于直接写质检日志）
import json                      # 序列化质检详情
from datetime import datetime    # 记录质检时间
from sqlalchemy import create_engine  # SQLAlchemy 引擎（pandas.read_sql 推荐使用）

# 清洗与异常检测工具（来自 data_cleaner.py）
from data_cleaner import clean_energy_data, detect_anomalies


# ======================== 主函数 ========================

def run_mysql_cleaning(hours: int = 2):
    """从 MySQL 拉取最近 N 小时数据，执行完整清洗管线

    【数据加载方式选择】
      使用 SQLAlchemy 引擎而非原生 pymysql 连接调用 pd.read_sql，
      原因是：pandas 2.0+ 对 pymysql 直连会触发 UserWarning：
      "pandas only supports SQLAlchemy connectable"
      SQLAlchemy 引擎是官方推荐的方式，兼容性更好。

    Args:
        hours: 拉取最近多少小时的数据（默认 2 小时），
               定时任务传 2，首次运行传 24 可以获得更多数据

    Returns:
        dict: {"cleaned": N, "anomalies": N, "removed": N}
              或者 {"error": "..."} 发生异常时
    """
    # ---- 步骤 1：建立 SQLAlchemy 数据库连接 ----
    # 连接字符串格式：mysql+pymysql://用户名:密码@主机:端口/数据库?参数
    # 容器内服务名是 "mysql"（不是 localhost）
    engine = create_engine(
        "mysql+pymysql://energy:energy123@mysql:3306/campus_energy?charset=utf8mb4"
    )
    conn = engine.connect()
    try:
        # ---- 步骤 2：从 MySQL 拉取原始数据 ----
        # pd.read_sql 自动将查询结果转换为 DataFrame
        sql = """
            SELECT id, building_id, region_id, meter_id, value, voltage,
                   current_val, event_time
            FROM energy_record
            WHERE event_time >= NOW() - INTERVAL %s HOUR   -- 最近 N 小时
            ORDER BY event_time
        """
        df = pd.read_sql(sql, conn, params=(hours,))

        # 如果没有数据则跳过
        if df.empty:
            print(f"[清洗] 近 {hours} 小时无数据，跳过")
            return {"cleaned": 0, "anomalies": 0, "removed": 0}

        raw_count = len(df)
        print(f"[清洗] 拉取 {raw_count} 条数据 (近{hours}h)")

        # ---- 步骤 3：执行数据清洗 ----
        # clean_energy_data 内部包含三步操作：
        #   ① drop_duplicates：按 (building_id, event_time) 去重
        #   ② interpolate：线性插值填充缺失值
        #   ③ 3σ 过滤：剔除 value 偏离均值 3 倍标准差以上的记录
        cleaned = clean_energy_data(df)
        removed = raw_count - len(cleaned)
        print(f"[清洗] 清洗后 {len(cleaned)} 条, 剔除 {removed} 条 (去重/空值/3σ异常)")

        # ---- 步骤 4：滑动窗口异常检测 ----
        # 清洗后的干净数据再进行异常点检测（与告警引擎策略一致）
        anomalies = detect_anomalies(cleaned)
        anomaly_count = len(anomalies)
        print(f"[异常检测] 滚动窗口发现 {anomaly_count} 个异常点")

        # ---- 步骤 5：写质检日志 ----
        # 使用独立的 pymysql 连接写入（与读取引擎分离，避免事务冲突）
        write_conn = pymysql.connect(
            host="mysql", port=3306, user="energy",
            password="energy123", database="campus_energy", charset="utf8mb4"
        )
        try:
            with write_conn.cursor() as cur:
                # 组装质检详情 JSON
                detail = {
                    "raw_count": raw_count,            # 原始数据量
                    "cleaned_count": len(cleaned),     # 清洗后数据量
                    "removed": removed,                # 剔除数据量
                    "anomaly_detected": anomaly_count, # 滚动窗口异常点数
                    "window_hours": hours,             # 查询时间窗口
                }
                # 插入 data_quality_log 表
                cur.execute(
                    """INSERT INTO data_quality_log
                       (check_time, data_source, check_type, target_table,
                        issue_count, detail, status)
                       VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                    (
                        datetime.now(),                           # 质检时间
                        "mysql",                                  # 数据来源
                        "cleaning_pipeline",                      # 质检类型
                        "energy_record",                          # 目标表
                        removed + anomaly_count,                  # 问题总数
                        json.dumps(detail, ensure_ascii=False),   # 详情 JSON
                        "warn" if (removed + anomaly_count) > 0 else "pass",  # 状态
                    ),
                )
            write_conn.commit()
        finally:
            write_conn.close()

        # ---- 步骤 6：返回汇总结果 ----
        result = {"cleaned": len(cleaned), "anomalies": anomaly_count, "removed": removed}
        print(f"[清洗] 完成 -> {json.dumps(result, ensure_ascii=False)}")
        return result

    except Exception as e:
        # 异常处理：打印错误并返回错误信息（不抛出，避免定时任务中断）
        print(f"[清洗] 失败: {e}")
        return {"error": str(e)}
    finally:
        # 释放连接资源
        conn.close()
        engine.dispose()


# ======================== 入口 ========================
if __name__ == "__main__":
    run_mysql_cleaning(hours=2)
