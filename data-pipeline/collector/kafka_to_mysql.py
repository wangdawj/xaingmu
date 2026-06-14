"""
=============================================================================
Kafka → MySQL 消费写入模块（Consumer & Writer）
=============================================================================
【功能说明】
  消费 Kafka 主题 "energy.raw" 中的原始能耗数据，解析后写入 MySQL 两张表：
    1. energy_record     — 总能耗时序数据（功率、电压、电流）
    2. energy_sub_record — 分项能耗（照明/空调/插座，按建筑类型比例拆分）

【分项能耗拆分规则】
  不同建筑类型的用能结构不同，按经验比例将总功率拆分为三项：
    教学楼：(照明 35%,  空调 45%,  插座 20%)   → 空调占比最高
    宿舍楼：(照明 25%,  空调 50%,  插座 25%)   → 空调占比最高（住宿空间恒温需求）
    图书馆：(照明 30%,  空调 55%,  插座 15%)   → 空调占比最高（大空间温控）
    食堂：  (照明 20%,  空调 30%,  插座 50%)   → 插座占比最高（厨房设备）
    其他：  (照明 33%,  空调 34%,  插座 33%)   → 默认均分

【为什么不用 InfluxDB？】
  原方案 InfluxDB + MySQL 双库维护成本高、答辩部署复杂。
  改为 MySQL 单库方案后，所有数据统一存储，查询更简单。

【数据流向】
  Kafka Topic → Consumer 逐条消费 → 解析 JSON → INSERT MySQL → 提交事务
=============================================================================
"""

# ======================== 导入模块 ========================
from datetime import datetime   # 解析 ISO 格式时间戳

# 项目共享工具：create_kafka_consumer 创建消费者，create_mysql_connection 创建数据库连接
from shared.connections import create_kafka_consumer, create_mysql_connection

# ======================== 常量配置 ========================

# Kafka 消费配置：订阅哪个主题
TOPIC = "energy.raw"

# 建筑类型 → 分项能耗占比 (照明比例, 空调比例, 插座比例)
# 这是根据建筑用能特征设定的经验比例
SUB_RATIOS = {
    "教学楼": (0.35, 0.45, 0.20),   # 35% 照明 + 45% 空调 + 20% 插座
    "宿舍楼": (0.25, 0.50, 0.25),   # 25% 照明 + 50% 空调 + 25% 插座（空调是耗能大户）
    "图书馆": (0.30, 0.55, 0.15),   # 30% 照明 + 55% 空调 + 15% 插座（大挑高空间，空调耗能极高）
    "食堂":   (0.20, 0.30, 0.50),   # 20% 照明 + 30% 空调 + 50% 插座（蒸箱/保温台/油烟机等厨房设备）
    "行政楼": (0.35, 0.45, 0.20),   # 类比教学楼
    "体育馆": (0.30, 0.40, 0.30),   # 30% 照明 + 40% 空调 + 30% 插座
}
# 如果建筑类型不在上面列表中，使用以下默认比例
DEFAULT_SUB_RATIO = (0.33, 0.34, 0.33)   # 约各1/3

# 建筑 ID → 建筑类型映射表
# consumer 从 Kafka 读到 building_id（如 "B001"）后，查此表获取建筑类型
# 从而选择正确的分项能耗占比
BUILDING_TYPES = {
    "B001": "教学楼",   # 第一教学楼
    "B002": "教学楼",   # 第二教学楼
    "B003": "宿舍楼",   # 1号宿舍楼
    "B004": "宿舍楼",   # 2号宿舍楼
    "B005": "图书馆",   # 中心图书馆
    "B006": "食堂",     # 第一食堂
    "B007": "体育馆",   # （已废弃，仅兼容旧数据）
    "B008": "行政楼",   # （已废弃，仅兼容旧数据）
}


# ======================== 主函数 ========================

def main():
    """消费写入主循环

    【工作流程】
      1. 创建 Kafka Consumer，订阅 "energy.raw" 主题
      2. 创建 MySQL 连接（持久连接，复用直到程序退出）
      3. 循环消费消息：
         a. 解析时间戳（ISO 8601 → datetime 对象）
         b. 写入 energy_record 总能耗表（一条 INSERT）
         c. 查建筑类型 → 计算分项能耗 → 写入 energy_sub_record 表（三条 INSERT）
         d. 提交事务（commit）
      4. 捕获 Ctrl+C 信号优雅退出

    【容错处理】
      - 单条写入失败：打印错误日志 + rollback 当前事务，跳过本条继续处理下一条
      - MySQL 连接断开：由 shared.connections 中的连接池自动重连
    """
    # 创建 Kafka 消费者
    # group_id="mysql-writer" 标识消费者组
    # 同一个消费者组内的实例共享 offset，不会重复消费
    consumer = create_kafka_consumer(topic=TOPIC, group_id="mysql-writer")

    # 创建 MySQL 持久连接（复用整个生命周期）
    conn = create_mysql_connection()

    print(f"[Consumer] 消费 Kafka [{TOPIC}] 并同步写入 MySQL...")
    count = 0  # 已写入记录计数器

    try:
        # consumer 是一个可迭代对象，每次迭代返回一条 Kafka 消息
        # 内部会自动提交 offset（自动确认消费进度）
        for msg in consumer:

            # msg.value 是反序列化后的 Python 字典（JSON → dict）
            record = msg.value

            try:
                # ---- 步骤 1：解析时间戳 ----
                # Kafka Producer 发送的是 ISO 8601 格式（如 "2026-06-14T11:07:23Z"）
                # .replace("Z", "+00:00") 将 UTC 标识转为 Python 可识别的时区格式
                # .replace(tzinfo=None) 去除时区信息（MySQL DATETIME 类型不接受时区）
                event_time = datetime.fromisoformat(
                    record["event_time"].replace("Z", "+00:00")
                ).replace(tzinfo=None)

                # ---- 步骤 2：提取关键字段 ----
                value = float(record["value"])           # 功率值
                building_id = record["building_id"]      # 建筑编号
                region_id = record["region_id"]          # 区域编号
                meter_id = record["meter_id"]            # 仪表编号

                # ---- 步骤 3：写入数据库（在一个事务中完成） ----
                with conn.cursor() as cur:
                    # 3a. 插入总能耗记录到 energy_record 表
                    cur.execute(
                        """INSERT INTO energy_record
                           (building_id, region_id, meter_id, energy_type,
                            data_type, value, voltage, current_val, event_time)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                        (
                            building_id,
                            region_id,
                            meter_id,
                            record.get("energy_type", "electricity"),    # 默认 "electricity"
                            record.get("data_type", "realtime"),         # 默认 "realtime"
                            value,
                            float(record.get("voltage", 0)),             # 电压，缺失填 0
                            float(record.get("current", 0)),             # 电流，缺失填 0
                            event_time,
                        ),
                    )

                    # 3b. 计算并插入分项能耗
                    # 根据建筑 ID 查建筑类型 → 获取照明/空调/插座比例
                    btype = BUILDING_TYPES.get(building_id, "")
                    light_r, ac_r, outlet_r = SUB_RATIOS.get(btype, DEFAULT_SUB_RATIO)

                    # executemany：用同一 SQL 模板批量插入多条记录
                    # 一条总功率记录拆分为 3 条分项记录
                    cur.executemany(
                        """INSERT INTO energy_sub_record
                           (building_id, sub_type, value, event_time)
                           VALUES (%s, %s, %s, %s)""",
                        [
                            # 照明 = 总功率 × 照明比例
                            (building_id, "lighting", round(value * light_r, 2), event_time),
                            # 空调 = 总功率 × 空调比例
                            (building_id, "ac", round(value * ac_r, 2), event_time),
                            # 插座 = 总功率 × 插座比例
                            (building_id, "outlet", round(value * outlet_r, 2), event_time),
                        ],
                    )

                # 提交事务：把上面 4 条 INSERT（1条总+3条分项）一起提交
                # 事务保证要么全部成功，要么全部失败
                conn.commit()
                count += 1

                # 每 500 条打印一次进度
                # 总记录数 × 3 = 分项记录数
                if count % 500 == 0:
                    print(f"[Consumer] 已写入 {count} 条 (+分项 {count * 3} 条)")

            except Exception as e:
                # 单条写入失败的回滚处理
                # 不会让整个程序崩溃，只是跳过这条有问题的记录
                print(f"[Consumer] 写入 MySQL 失败: {e}，跳过本条")
                conn.rollback()   # 回滚当前事务，恢复到写入前的状态

    except KeyboardInterrupt:
        # 用户按 Ctrl+C 时优雅退出
        print(f"\n[Consumer] 停止消费，共写入 {count} 条")

    finally:
        # 释放资源：关闭数据库连接和 Kafka 消费者
        conn.close()
        consumer.close()
        print("[Consumer] 已关闭")


# ======================== 入口 ========================
if __name__ == "__main__":
    main()
