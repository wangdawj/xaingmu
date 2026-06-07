"""InfluxDB 初始化：创建 Bucket 与示例写入验证"""
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
import os
import time
import random

INFLUX_URL = os.getenv("INFLUXDB_URL", "http://localhost:8086")
INFLUX_TOKEN = os.getenv("INFLUXDB_TOKEN", "campus-energy-token")
INFLUX_ORG = os.getenv("INFLUXDB_ORG", "campus")
INFLUX_BUCKET = os.getenv("INFLUXDB_BUCKET", "energy")

BUILDINGS = ["B001", "B002", "B003", "B004", "B005", "B006"]
METERS = {
    "B001": "M001", "B002": "M002", "B003": "M003",
    "B005": "M004", "B006": "M005",
}


def write_sample_data(count: int = 100):
    client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
    write_api = client.write_api(write_options=SYNCHRONOUS)

    points = []
    now = int(time.time())
    for i in range(count):
        building_id = random.choice(BUILDINGS)
        meter_id = METERS.get(building_id, "M001")
        value = round(random.uniform(50, 400), 2)
        point = (
            Point("electricity_data")
            .tag("building_id", building_id)
            .tag("region_id", "R001")
            .tag("meter_id", meter_id)
            .tag("data_type", "realtime")
            .field("value", value)
            .field("voltage", round(random.uniform(220, 240), 1))
            .field("current", round(value / 220, 2))
            .time(now - (count - i) * 60, WritePrecision.S)
        )
        points.append(point)

    write_api.write(bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=points)
    print(f"已写入 {count} 条 electricity_data 到 InfluxDB")
    client.close()


if __name__ == "__main__":
    write_sample_data(500)
