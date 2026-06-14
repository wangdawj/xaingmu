#!/usr/bin/env python
"""
MySQL 种子数据生成器
==================
向 MySQL energy_record 表插入 7 天模拟能耗数据（含分项能耗：照明/空调/插座）。
用于开发环境快速填充测试数据。

用法:
    docker exec campus-backend python scripts/seed_mysql.py
"""

import pymysql
import random
from datetime import datetime, timedelta

# MySQL 连接参数
CONN_PARAMS = dict(host="mysql", port=3306, user="energy", password="energy123",
                   database="campus_energy", charset="utf8mb4")

# 模拟建筑列表（building_id, region_id, meter_id）
BUILDINGS = [
    ("B001", "R001", "M001"),
    ("B002", "R001", "M002"),
    ("B003", "R001", "M003"),
    ("B005", "R001", "M004"),
    ("B006", "R001", "M005"),
]


def seed_energy_records(conn, days=7, interval_min=6):
    """插入指定天数的模拟能耗数据

    Args:
        conn: MySQL 连接
        days: 模拟天数
        interval_min: 数据间隔（分钟）
    """
    now = datetime.now()
    start = now - timedelta(days=days)
    records_per_day = 24 * 60 // interval_min

    cur = conn.cursor()
    count = 0
    for day_offset in range(days):
        for i in range(records_per_day):
            ts = start + timedelta(days=day_offset, minutes=i * interval_min)
            building_id, region_id, meter_id = random.choice(BUILDINGS)

            # 模拟用电规律：白天多，夜间少
            hour = ts.hour
            base = 200 if 8 <= hour < 22 else 80
            value = round(random.uniform(base * 0.6, base * 1.4), 2)
            voltage = round(random.uniform(218, 242), 1)
            current = round(value / voltage, 2)

            cur.execute(
                """INSERT INTO energy_record
                   (building_id, region_id, meter_id, energy_type, data_type,
                    value, voltage, current_val, event_time)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (building_id, region_id, meter_id, "electricity", "realtime",
                 value, voltage, current, ts),
            )
            count += 1
    conn.commit()
    cur.close()
    print(f"energy_record 写入完成，共 {count} 条")


def seed_sub_records(conn, days=7):
    """插入分项能耗数据（照明/空调/插座）"""
    sub_types = {"lighting": (30, 80), "ac": (50, 150), "outlet": (20, 60)}
    now = datetime.now()
    start = now - timedelta(days=days)

    cur = conn.cursor()
    count = 0
    for building_id, _, _ in BUILDINGS:
        for hour_offset in range(days * 24):
            ts = start + timedelta(hours=hour_offset)
            for sub_type, (lo, hi) in sub_types.items():
                value = round(random.uniform(lo, hi), 2)
                cur.execute(
                    """INSERT INTO energy_sub_record
                       (building_id, sub_type, value, event_time)
                       VALUES (%s,%s,%s,%s)""",
                    (building_id, sub_type, value, ts),
                )
                count += 1
    conn.commit()
    cur.close()
    print(f"energy_sub_record 写入完成，共 {count} 条")


def main():
    conn = pymysql.connect(**CONN_PARAMS)
    try:
        seed_energy_records(conn)
        seed_sub_records(conn)
        print("种子数据写入完成！")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
