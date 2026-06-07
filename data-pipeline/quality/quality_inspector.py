"""数据质量巡检模块"""
import json
import os
from datetime import datetime, timedelta

import pymysql
from influxdb_client import InfluxDBClient

MYSQL_CONFIG = {
    "host": os.getenv("MYSQL_HOST", "localhost"),
    "port": int(os.getenv("MYSQL_PORT", 3306)),
    "user": os.getenv("MYSQL_USER", "energy"),
    "password": os.getenv("MYSQL_PASSWORD", "energy123"),
    "database": os.getenv("MYSQL_DATABASE", "campus_energy"),
    "charset": "utf8mb4",
}

INFLUX_URL = os.getenv("INFLUXDB_URL", "http://localhost:8086")
INFLUX_TOKEN = os.getenv("INFLUXDB_TOKEN", "campus-energy-token")
INFLUX_ORG = os.getenv("INFLUXDB_ORG", "campus")
INFLUX_BUCKET = os.getenv("INFLUXDB_BUCKET", "energy")


def save_log(data_source, check_type, target_table, issue_count, detail, status):
    conn = pymysql.connect(**MYSQL_CONFIG)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO data_quality_log
                   (check_time, data_source, check_type, target_table, issue_count, detail, status)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (datetime.now(), data_source, check_type, target_table,
                 issue_count, json.dumps(detail, ensure_ascii=False), status),
            )
        conn.commit()
    finally:
        conn.close()


def check_influx_missing():
    """检查 InfluxDB 近1小时是否有数据"""
    client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
    flux = f'''
    from(bucket: "{INFLUX_BUCKET}")
      |> range(start: -1h)
      |> filter(fn: (r) => r["_measurement"] == "electricity_data")
      |> count()
    '''
    tables = client.query_api().query(flux, org=INFLUX_ORG)
    count = sum(int(r.get_value()) for t in tables for r in t.records)
    client.close()
    status = "pass" if count > 0 else "fail"
    save_log("influxdb", "missing", "electricity_data", 0 if count > 0 else 1,
             {"record_count": count, "window": "1h"}, status)
    return status, count


def check_mysql_consistency():
    """MySQL 楼宇与仪表关联一致性"""
    conn = pymysql.connect(**MYSQL_CONFIG)
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT COUNT(*) FROM meter m
                LEFT JOIN building b ON m.building_id = b.building_id
                WHERE b.building_id IS NULL
            """)
            orphan = cur.fetchone()[0]
        status = "pass" if orphan == 0 else "warn"
        save_log("mysql", "consistency", "meter/building", orphan,
                 {"orphan_meters": orphan}, status)
        return status, orphan
    finally:
        conn.close()


def check_data_delay():
    """检查 InfluxDB 最新数据延迟"""
    client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
    flux = f'''
    from(bucket: "{INFLUX_BUCKET}")
      |> range(start: -24h)
      |> filter(fn: (r) => r["_measurement"] == "electricity_data")
      |> last()
    '''
    tables = client.query_api().query(flux, org=INFLUX_ORG)
    latest = None
    for t in tables:
        for r in t.records:
            latest = r.get_time()
    client.close()
    if not latest:
        save_log("influxdb", "delay", "electricity_data", 1,
                 {"message": "无最新数据"}, "fail")
        return "fail", None
    delay_sec = (datetime.utcnow().replace(tzinfo=latest.tzinfo) - latest).total_seconds()
    status = "pass" if delay_sec < 300 else "warn"
    save_log("influxdb", "delay", "electricity_data", 1 if delay_sec >= 300 else 0,
             {"delay_seconds": delay_sec}, status)
    return status, delay_sec


def run_all_checks():
    print("=== 数据质量巡检开始 ===")
    results = {
        "missing": check_influx_missing(),
        "consistency": check_mysql_consistency(),
        "delay": check_data_delay(),
    }
    print(json.dumps(results, ensure_ascii=False, default=str))
    print("=== 巡检完成 ===")
    return results


if __name__ == "__main__":
    run_all_checks()
