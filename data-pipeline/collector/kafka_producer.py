"""Kafka 数据采集模拟器 - 模拟 OPC UA / 传感器实时数据"""
import json
import os
import random
import time
from datetime import datetime, timezone

from kafka import KafkaProducer

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "localhost:9092")
TOPIC = "energy.raw"

BUILDINGS = [
    {"building_id": "B001", "region_id": "R001", "meter_id": "M001"},
    {"building_id": "B002", "region_id": "R001", "meter_id": "M002"},
    {"building_id": "B003", "region_id": "R001", "meter_id": "M003"},
    {"building_id": "B005", "region_id": "R001", "meter_id": "M004"},
    {"building_id": "B006", "region_id": "R001", "meter_id": "M005"},
]


def generate_record():
    b = random.choice(BUILDINGS)
    value = round(random.uniform(30, 450), 2)
    voltage = round(random.uniform(218, 242), 1)
    return {
        "event_time": datetime.now(timezone.utc).isoformat(),
        "building_id": b["building_id"],
        "region_id": b["region_id"],
        "meter_id": b["meter_id"],
        "energy_type": "electricity",
        "data_type": "realtime",
        "value": value,
        "unit": "kWh",
        "voltage": voltage,
        "current": round(value / voltage, 2),
    }


def main(interval_sec: float = 1.0, batch_size: int = 10):
    producer = KafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )
    print(f"开始向 Kafka topic [{TOPIC}] 发送模拟数据...")
    count = 0
    try:
        while True:
            for _ in range(batch_size):
                record = generate_record()
                producer.send(TOPIC, record)
                count += 1
            producer.flush()
            if count % 100 == 0:
                print(f"已发送 {count} 条")
            time.sleep(interval_sec)
    except KeyboardInterrupt:
        print(f"\n停止采集，共发送 {count} 条")
    finally:
        producer.close()


if __name__ == "__main__":
    main()
