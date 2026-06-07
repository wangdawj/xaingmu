#!/usr/bin/env python
"""向 InfluxDB 插入示例能耗数据"""
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
import random
from datetime import datetime, timedelta

client = InfluxDBClient(
    url="http://influxdb:8086",
    token="campus-energy-token",
    org="campus",
)
write_api = client.write_api(write_options=SYNCHRONOUS)

buildings = {
    "B001": "R001",
    "B002": "R001",
    "B003": "R001",
    "B004": "R002",
    "B005": "R001",
    "B006": "R001",
}

base_values = {
    "B001": 150,  # 教学楼
    "B002": 120,
    "B003": 80,   # 宿舍楼
    "B004": 70,
    "B005": 200,  # 图书馆
    "B006": 100,  # 食堂
}

now = datetime.utcnow()
points = []

for hour_offset in range(168):  # 7 天数据
    ts = now - timedelta(hours=hour_offset)
    hour = ts.hour
    for bid, rid in buildings.items():
        base = base_values[bid]
        # 模拟日间高用电、夜间低用电
        if 8 <= hour < 22:
            factor = random.uniform(0.7, 1.3)
        else:
            factor = random.uniform(0.2, 0.5)
        value = round(base * factor, 2)
        p = (
            Point("electricity_data")
            .tag("building_id", bid)
            .tag("region_id", rid)
            .field("value", value)
            .time(ts)
        )
        points.append(p)

# 分批写入
batch_size = 500
for i in range(0, len(points), batch_size):
    batch = points[i : i + batch_size]
    write_api.write(bucket="energy", record=batch)

print(f"已插入 {len(points)} 条示例数据")
client.close()
