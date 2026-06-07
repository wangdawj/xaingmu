#!/usr/bin/env python
"""向 InfluxDB 插入示例能耗数据（含分项能耗）"""
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
    "B001": "R001",  # 第一教学楼
    "B002": "R001",  # 第二教学楼
    "B003": "R001",  # 1号宿舍楼
    "B004": "R002",  # 2号宿舍楼
    "B005": "R001",  # 中心图书馆
    "B006": "R001",  # 第一食堂
    "B007": "R002",  # 体育馆
    "B008": "R002",  # 行政楼
}

base_values = {
    "B001": 150,
    "B002": 120,
    "B003": 80,
    "B004": 70,
    "B005": 200,
    "B006": 100,
    "B007": 180,
    "B008": 90,
}

# 分项能耗占比（照明/空调/插座）
sub_ratios = {
    "教学楼":   (0.35, 0.45, 0.20),
    "宿舍楼":   (0.25, 0.50, 0.25),
    "图书馆":   (0.30, 0.55, 0.15),
    "食堂":     (0.20, 0.30, 0.50),
    "体育馆":   (0.30, 0.40, 0.30),
    "行政楼":   (0.35, 0.45, 0.20),
}

building_types = {
    "B001": "教学楼",
    "B002": "教学楼",
    "B003": "宿舍楼",
    "B004": "宿舍楼",
    "B005": "图书馆",
    "B006": "食堂",
    "B007": "体育馆",
    "B008": "行政楼",
}

now = datetime.utcnow()
points = []
sub_points = []

for hour_offset in range(168):  # 7 天数据
    ts = now - timedelta(hours=hour_offset)
    hour = ts.hour
    for bid, rid in buildings.items():
        base = base_values[bid]
        if 8 <= hour < 22:
            factor = random.uniform(0.7, 1.3)
        else:
            factor = random.uniform(0.2, 0.5)
        value = round(base * factor, 2)
        # 总用电量
        p = (
            Point("electricity_data")
            .tag("building_id", bid)
            .tag("region_id", rid)
            .field("value", value)
            .time(ts)
        )
        points.append(p)

        # 分项能耗（照明/空调/插座）
        btype = building_types[bid]
        light_r, ac_r, outlet_r = sub_ratios[btype]
        sub_points.append(
            Point("electricity_sub")
            .tag("building_id", bid)
            .tag("region_id", rid)
            .tag("sub_type", "lighting")
            .field("value", round(value * light_r, 2))
            .time(ts)
        )
        sub_points.append(
            Point("electricity_sub")
            .tag("building_id", bid)
            .tag("region_id", rid)
            .tag("sub_type", "ac")
            .field("value", round(value * ac_r, 2))
            .time(ts)
        )
        sub_points.append(
            Point("electricity_sub")
            .tag("building_id", bid)
            .tag("region_id", rid)
            .tag("sub_type", "outlet")
            .field("value", round(value * outlet_r, 2))
            .time(ts)
        )

# 分批写入
batch_size = 500
for i in range(0, len(points), batch_size):
    write_api.write(bucket="energy", record=points[i:i + batch_size])
for i in range(0, len(sub_points), batch_size):
    write_api.write(bucket="energy", record=sub_points[i:i + batch_size])

total = len(points) + len(sub_points)
print(f"已插入 {len(points)} 条总用电数据 + {len(sub_points)} 条分项数据，共 {total} 条")
client.close()
