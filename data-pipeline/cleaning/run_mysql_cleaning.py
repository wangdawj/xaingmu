"""
MySQL → Pandas 离线清洗管道
=========================
从 MySQL energy_record 拉取数据 → Pandas 清洗 → 写回质检日志
定时执行，与实时 Consumer 互补。
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import pymysql
import json
from datetime import datetime
from sqlalchemy import create_engine

from data_cleaner import clean_energy_data, detect_anomalies


def run_mysql_cleaning(hours: int = 2):
    """从 MySQL 拉取最近 N 小时数据，执行清洗 + 异常检测

    Args:
        hours: 拉取最近多少小时的数据
    """
    engine = create_engine(
        "mysql+pymysql://energy:energy123@mysql:3306/campus_energy?charset=utf8mb4"
    )
    conn = engine.connect()
    try:
        # 从 MySQL 拉取原始数据
        sql = """
            SELECT id, building_id, region_id, meter_id, value, voltage,
                   current_val, event_time
            FROM energy_record
            WHERE event_time >= NOW() - INTERVAL %s HOUR
            ORDER BY event_time
        """
        df = pd.read_sql(sql, conn, params=(hours,))

        if df.empty:
            print(f"[清洗] 近 {hours} 小时无数据，跳过")
            return {"cleaned": 0, "anomalies": 0, "removed": 0}

        raw_count = len(df)
        print(f"[清洗] 拉取 {raw_count} 条数据 (近{hours}h)")

        # 执行清洗
        cleaned = clean_energy_data(df)
        removed = raw_count - len(cleaned)
        print(f"[清洗] 清洗后 {len(cleaned)} 条, 剔除 {removed} 条 (去重/空值/3σ异常)")

        # 异常检测
        anomalies = detect_anomalies(cleaned)
        anomaly_count = len(anomalies)
        print(f"[异常检测] 滚动窗口发现 {anomaly_count} 个异常点")

        # 写入质检日志（用 pymysql 连接直接写）
        write_conn = pymysql.connect(
            host="mysql", port=3306, user="energy",
            password="energy123", database="campus_energy", charset="utf8mb4"
        )
        try:
            with write_conn.cursor() as cur:
                detail = {
                    "raw_count": raw_count,
                    "cleaned_count": len(cleaned),
                    "removed": removed,
                    "anomaly_detected": anomaly_count,
                    "window_hours": hours,
                }
                cur.execute(
                    """INSERT INTO data_quality_log
                       (check_time, data_source, check_type, target_table,
                        issue_count, detail, status)
                       VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                    (
                        datetime.now(),
                        "mysql",
                        "cleaning_pipeline",
                        "energy_record",
                        removed + anomaly_count,
                        json.dumps(detail, ensure_ascii=False),
                        "warn" if (removed + anomaly_count) > 0 else "pass",
                    ),
                )
            write_conn.commit()
        finally:
            write_conn.close()

        result = {"cleaned": len(cleaned), "anomalies": anomaly_count, "removed": removed}
        print(f"[清洗] 完成 -> {json.dumps(result, ensure_ascii=False)}")
        return result

    except Exception as e:
        print(f"[清洗] 失败: {e}")
        return {"error": str(e)}
    finally:
        conn.close()
        engine.dispose()


if __name__ == "__main__":
    run_mysql_cleaning(hours=2)
