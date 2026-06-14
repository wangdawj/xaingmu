"""
Kafka → MySQL 消费写入模块
=========================
消费 Kafka 中的原始能耗数据，写入 MySQL energy_record 和 energy_sub_record 表。
替代原 Kafka → InfluxDB 方案，数据全部直接存入 MySQL。

分项能耗拆分比例（按建筑类型）：
    教学楼：(照明 35%,  空调 45%,  插座 20%)
    宿舍楼：(照明 25%,  空调 50%,  插座 25%)
    图书馆：(照明 30%,  空调 55%,  插座 15%)
    食堂：  (照明 20%,  空调 30%,  插座 50%)
    其他：  (照明 33%,  空调 34%,  插座 33%)
"""

from datetime import datetime

from shared.connections import create_kafka_consumer, create_mysql_connection

# Kafka 消费配置
TOPIC = "energy.raw"

# 建筑类型 → 分项能耗占比 (lighting, ac, outlet)
SUB_RATIOS = {
    "教学楼": (0.35, 0.45, 0.20),
    "宿舍楼": (0.25, 0.50, 0.25),
    "图书馆": (0.30, 0.55, 0.15),
    "食堂":   (0.20, 0.30, 0.50),
    "行政楼": (0.35, 0.45, 0.20),
    "体育馆": (0.30, 0.40, 0.30),
}
DEFAULT_SUB_RATIO = (0.33, 0.34, 0.33)

# 建筑 ID → 建筑类型映射（用于分项拆分）
BUILDING_TYPES = {
    "B001": "教学楼", "B002": "教学楼",
    "B003": "宿舍楼", "B004": "宿舍楼",
    "B005": "图书馆", "B006": "食堂",
    "B007": "体育馆", "B008": "行政楼",
}


def main():
    """消费写入主循环：从 Kafka 消费 → 写入 MySQL energy_record + energy_sub_record"""
    consumer = create_kafka_consumer(topic=TOPIC, group_id="mysql-writer")
    conn = create_mysql_connection()
    print(f"[Consumer] 消费 Kafka [{TOPIC}] 并同步写入 MySQL...")
    count = 0
    try:
        for msg in consumer:
            record = msg.value
            try:
                # 解析时间戳
                event_time = datetime.fromisoformat(
                    record["event_time"].replace("Z", "+00:00")
                ).replace(tzinfo=None)

                value = float(record["value"])
                building_id = record["building_id"]
                region_id = record["region_id"]
                meter_id = record["meter_id"]

                # 写入总能耗记录
                with conn.cursor() as cur:
                    cur.execute(
                        """INSERT INTO energy_record
                           (building_id, region_id, meter_id, energy_type,
                            data_type, value, voltage, current_val, event_time)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                        (
                            building_id, region_id, meter_id,
                            record.get("energy_type", "electricity"),
                            record.get("data_type", "realtime"),
                            value,
                            float(record.get("voltage", 0)),
                            float(record.get("current", 0)),
                            event_time,
                        ),
                    )

                    # 写入分项能耗（照明/空调/插座拆分）
                    btype = BUILDING_TYPES.get(building_id, "")
                    light_r, ac_r, outlet_r = SUB_RATIOS.get(btype, DEFAULT_SUB_RATIO)
                    cur.executemany(
                        """INSERT INTO energy_sub_record
                           (building_id, sub_type, value, event_time)
                           VALUES (%s, %s, %s, %s)""",
                        [
                            (building_id, "lighting", round(value * light_r, 2), event_time),
                            (building_id, "ac", round(value * ac_r, 2), event_time),
                            (building_id, "outlet", round(value * outlet_r, 2), event_time),
                        ],
                    )

                conn.commit()
                count += 1
                if count % 500 == 0:
                    print(f"[Consumer] 已写入 {count} 条 (+分项 {count * 3} 条)")
            except Exception as e:
                print(f"[Consumer] 写入 MySQL 失败: {e}，跳过本条")
                conn.rollback()
    except KeyboardInterrupt:
        print(f"\n[Consumer] 停止消费，共写入 {count} 条")
    finally:
        conn.close()
        consumer.close()
        print("[Consumer] 已关闭")


if __name__ == "__main__":
    main()
