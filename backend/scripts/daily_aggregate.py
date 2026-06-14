#!/usr/bin/env python
"""
日能耗汇总定时脚本
=================
每天凌晨执行，从 energy_record 表聚合前一天的能耗数据，
写入 energy_daily_summary 表。

用法（手动执行）:
    docker exec campus-backend python scripts/daily_aggregate.py

用法（crontab 每日凌晨 1 点）:
    0 1 * * * docker exec campus-backend python scripts/daily_aggregate.py
"""

import pymysql
from datetime import datetime, timedelta


def aggregate_yesterday(conn):
    """聚合前一天的数据写入 energy_daily_summary

    每个建筑每天产生一条汇总记录：
        - total_value: 当日总能耗
        - peak_value:  当日最大小时值
        - valley_value: 当日最小小时值
        - avg_value:   当日小时均值
    """
    sql = """
        INSERT INTO energy_daily_summary
            (stat_date, building_id, energy_type,
             total_value, peak_value, valley_value, avg_value)
        SELECT
            DATE(?)                            AS stat_date,
            building_id,
            'electricity'                      AS energy_type,
            SUM(value)                         AS total_value,
            COALESCE(MAX(hourly), 0)           AS peak_value,
            COALESCE(MIN(hourly), 0)           AS valley_value,
            ROUND(AVG(hourly), 2)             AS avg_value
        FROM (
            SELECT
                building_id,
                DATE_FORMAT(event_time, '%Y-%m-%d %H:00') AS h,
                SUM(value) AS hourly
            FROM energy_record
            WHERE event_time >= ? AND event_time < ?
            GROUP BY building_id, h
        ) t
        GROUP BY building_id
        ON DUPLICATE KEY UPDATE
            total_value  = VALUES(total_value),
            peak_value   = VALUES(peak_value),
            valley_value = VALUES(valley_value),
            avg_value    = VALUES(avg_value)
    """
    yesterday = datetime.now().date() - timedelta(days=1)
    day_start = yesterday.strftime("%Y-%m-%d 00:00:00")
    day_end = yesterday.strftime("%Y-%m-%d 23:59:59")

    cur = conn.cursor()
    cur.execute(sql, (yesterday, day_start, day_end))
    conn.commit()
    rowcount = cur.rowcount
    cur.close()
    print(f"日汇总完成: {yesterday} → {rowcount} 栋建筑")


def main():
    conn = pymysql.connect(
        host="mysql",
        port=3306,
        user="energy",
        password="energy123",
        database="campus_energy",
        charset="utf8mb4",
    )
    try:
        aggregate_yesterday(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
