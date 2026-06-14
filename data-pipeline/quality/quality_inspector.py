"""
数据质量巡检模块（MySQL 版）
=======================
定期检查数据管道各环节的数据质量，包括：
- energy_record 数据缺失检测
- MySQL 关联一致性校验
- 数据延迟监控
检测结果写入 data_quality_log 表供前端展示。
"""

import json
from datetime import datetime

from shared.connections import create_mysql_connection


def save_log(data_source, check_type, target_table, issue_count, detail, status):
    """将质量检查结果写入 MySQL data_quality_log 表"""
    conn = create_mysql_connection()
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


def check_energy_record_missing():
    """检查 energy_record 表近 1 小时是否有新数据写入

    Returns:
        (status, count) — status 为 "pass"/"fail"，count 为记录数
    """
    conn = create_mysql_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM energy_record "
                "WHERE event_time >= NOW() - INTERVAL 1 HOUR"
            )
            count = cur.fetchone()[0]
    finally:
        conn.close()

    status = "pass" if count > 0 else "fail"
    save_log("mysql", "missing", "energy_record", 0 if count > 0 else 1,
             {"record_count": count, "window": "1h"}, status)
    return status, count


def check_mysql_consistency():
    """MySQL 数据一致性检查：仪表表与建筑表的关联完整性

    Returns:
        (status, orphan_count)
    """
    conn = create_mysql_connection()
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
    """检查 energy_record 最新数据的时间延迟

    Returns:
        (status, delay_seconds) — delay >= 300s 为 "warn"，无数据为 "fail"
    """
    conn = create_mysql_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT MAX(event_time) FROM energy_record"
            )
            row = cur.fetchone()
            latest = row[0] if row else None
    finally:
        conn.close()

    if not latest:
        save_log("mysql", "delay", "energy_record", 1,
                 {"message": "无最新数据"}, "fail")
        return "fail", None

    delay_sec = (datetime.now() - latest).total_seconds()
    status = "pass" if delay_sec < 300 else "warn"
    save_log("mysql", "delay", "energy_record", 1 if delay_sec >= 300 else 0,
             {"delay_seconds": delay_sec}, status)
    return status, delay_sec


def run_all_checks():
    """执行全部质量检查项，返回汇总结果"""
    print("=== 数据质量巡检开始 ===")
    results = {
        "missing": check_energy_record_missing(),
        "consistency": check_mysql_consistency(),
        "delay": check_data_delay(),
    }
    print(json.dumps(results, ensure_ascii=False, default=str))
    print("=== 巡检完成 ===")
    return results


if __name__ == "__main__":
    run_all_checks()
