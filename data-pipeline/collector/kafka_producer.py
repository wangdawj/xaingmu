"""
Kafka 数据采集模拟器
=================
模拟 OPC UA / 传感器实时数据采集，向 Kafka 发送模拟的能耗数据。
生产环境中可替换为真实的 OPC UA / Modbus / MQTT 采集器。

数据特征：
- 功率值与当前时间相关：白天高(8-22点) / 夜间低(22-次日8点)
- 工作日 vs 周末有约 20% 差异
- 覆盖全部 8 栋建筑，各有不同的基准功率
"""

import random
import time
from datetime import datetime, timezone

from shared.connections import create_kafka_producer

# Kafka 主题
TOPIC = "energy.raw"

# 全部建筑列表（building_id, region_id, meter_id, 基准功率 kW）
# 与数据库 building 表保持一致（B001~B006）
BUILDINGS = [
    {"building_id": "B001", "region_id": "R001", "meter_id": "M001", "base_kw": 150},
    {"building_id": "B002", "region_id": "R001", "meter_id": "M002", "base_kw": 120},
    {"building_id": "B003", "region_id": "R001", "meter_id": "M003", "base_kw": 80},
    {"building_id": "B004", "region_id": "R002", "meter_id": "M005", "base_kw": 70},
    {"building_id": "B005", "region_id": "R001", "meter_id": "M004", "base_kw": 200},
    {"building_id": "B006", "region_id": "R001", "meter_id": "M006", "base_kw": 100},
]


def generate_record(b=None):
    """生成一条模拟的能耗采集记录

    功率模拟策略：
        1. 以建筑基准功率为基数
        2. 白天(8-22点) × 0.7~1.3，夜间(22-8点) × 0.2~0.5
        3. 周末(周六/周日) 额外降低约 20%
        4. 添加 ±10% 随机噪声
        5. 电压 218~242V，电流 = 功率 / 电压
    """
    if b is None:
        b = random.choice(BUILDINGS)
    now = datetime.now(timezone.utc)
    hour = now.hour
    weekday = now.weekday()

    # 峰谷因子
    if 8 <= hour < 22:
        hour_factor = random.uniform(0.7, 1.3)
    else:
        hour_factor = random.uniform(0.2, 0.5)

    # 周末因子
    weekend_factor = 0.8 if weekday >= 5 else 1.0

    # 计算功率值
    value = round(b["base_kw"] * hour_factor * weekend_factor * random.uniform(0.9, 1.1), 2)
    voltage = round(random.uniform(218, 242), 1)

    return {
        "event_time": now.isoformat(),
        "building_id": b["building_id"],
        "region_id": b["region_id"],
        "meter_id": b["meter_id"],
        "energy_type": "electricity",
        "data_type": "realtime",
        "value": value,
        "unit": "kWh",
        "voltage": voltage,
        "current": round(value / voltage, 2),  # I = P / U
    }


def main(interval_sec: float = 1.0):
    """采集器主循环：每轮给全部建筑各发一条数据到 Kafka

    Args:
        interval_sec: 发送间隔（秒），默认 1 秒
    """
    producer = create_kafka_producer()
    print(f"[Producer] 开始向 topic [{TOPIC}] 发送 {len(BUILDINGS)} 栋建筑的模拟数据...")
    count = 0
    try:
        while True:
            for b in BUILDINGS:
                record = generate_record(b)
                try:
                    producer.send(TOPIC, record)
                    count += 1
                except Exception as e:
                    print(f"[Producer] 发送失败，尝试重连: {e}")
                    producer.close()
                    time.sleep(3)
                    producer = create_kafka_producer()
            producer.flush()
            if count % 60 == 0:
                print(f"[Producer] 已发送 {count} 条 ({count // 6} 轮)")
            time.sleep(interval_sec)
    except KeyboardInterrupt:
        print(f"\n[Producer] 停止采集，共发送 {count} 条")
    finally:
        producer.close()
        print("[Producer] 已关闭")


if __name__ == "__main__":
    main()
