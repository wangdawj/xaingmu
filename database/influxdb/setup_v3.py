"""InfluxDB 3 初始化：创建数据库并写入示例电表数据"""
import os
import random
import time
from datetime import datetime, timezone

try:
    from influxdb_client_3 import InfluxDBClient3, Point
except ImportError:
    raise SystemExit("请先安装: pip install influxdb3-python")

INFLUX_HOST = os.getenv("INFLUXDB_HOST", "http://127.0.0.1:8181")
INFLUX_TOKEN = os.getenv(
    "INFLUXDB_TOKEN",
    "apiv3_JSkr8fQ2mVGOwO26xvhJDOG6GX4wfSmUqE_wss8hSw4hHKMdM1oexNA6d0Lq-YEu1RQpLpTKRboQSBmfzAbhYg",
)
INFLUX_DATABASE = os.getenv("INFLUXDB_BUCKET", "energy")

BUILDINGS = [
    ("B001", "R001", "M001"),
    ("B002", "R001", "M002"),
    ("B003", "R001", "M003"),
    ("B005", "R001", "M004"),
    ("B006", "R001", "M005"),
]


def write_sample_data(count: int = 500):
    client = InfluxDBClient3(
        host=INFLUX_HOST,
        token=INFLUX_TOKEN,
        database=INFLUX_DATABASE,
        auth_scheme="Bearer",
    )

    now = datetime.now(timezone.utc)
    points = []
    for i in range(count):
        building_id, region_id, meter_id = random.choice(BUILDINGS)
        value = round(random.uniform(50, 400), 2)
        ts = now.timestamp() - (count - i) * 360
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        point = (
            Point("electricity_data")
            .tag("building_id", building_id)
            .tag("region_id", region_id)
            .tag("meter_id", meter_id)
            .tag("data_type", "realtime")
            .field("value", value)
            .field("voltage", round(random.uniform(220, 240), 1))
            .field("current", round(value / 220, 2))
            .time(dt)
        )
        points.append(point)

    client.write(record=points)
    print(f"已写入 {count} 条 electricity_data 到 InfluxDB 3 数据库 [{INFLUX_DATABASE}]")
    client.close()


if __name__ == "__main__":
    write_sample_data(500)
