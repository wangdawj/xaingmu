"""Flink 风格实时预警模块（独立 Python 实现，可迁移至 PyFlink）"""
import json
import os
import time
from collections import defaultdict, deque
from datetime import datetime

import pymysql
from kafka import KafkaConsumer

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "localhost:9092")
TOPIC = "energy.raw"

MYSQL_CONFIG = {
    "host": os.getenv("MYSQL_HOST", "localhost"),
    "port": int(os.getenv("MYSQL_PORT", 3306)),
    "user": os.getenv("MYSQL_USER", "energy"),
    "password": os.getenv("MYSQL_PASSWORD", "energy123"),
    "database": os.getenv("MYSQL_DATABASE", "campus_energy"),
    "charset": "utf8mb4",
}

# 滑动窗口：每 building 保留最近 N 条
WINDOW_SIZE = 20
THRESHOLD_MULTIPLIER = 2.0


class AlertEngine:
    def __init__(self):
        self.windows: dict[str, deque] = defaultdict(lambda: deque(maxlen=WINDOW_SIZE))
        self.rules = self._load_rules()

    def _load_rules(self) -> dict:
        conn = pymysql.connect(**MYSQL_CONFIG)
        try:
            with conn.cursor(pymysql.cursors.DictCursor) as cur:
                cur.execute(
                    "SELECT rule_id, building_id, threshold_max, severity "
                    "FROM alert_rule WHERE enabled = 1"
                )
                rules = {}
                for row in cur.fetchall():
                    rules[row["building_id"]] = row
                return rules
        finally:
            conn.close()

    def _save_alert(self, record: dict, rule: dict, threshold: float):
        conn = pymysql.connect(**MYSQL_CONFIG)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO alert_record
                       (rule_id, building_id, meter_id, energy_type, alert_value,
                        threshold, severity, message, triggered_at)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (
                        rule["rule_id"],
                        record["building_id"],
                        record.get("meter_id"),
                        record.get("energy_type", "electricity"),
                        record["value"],
                        threshold,
                        rule["severity"],
                        f"楼宇 {record['building_id']} 能耗 {record['value']} 超过阈值 {threshold:.2f}",
                        datetime.now(),
                    ),
                )
            conn.commit()
            print(f"[ALERT] {record['building_id']} value={record['value']} threshold={threshold:.2f}")
        finally:
            conn.close()

    def process(self, record: dict):
        building_id = record["building_id"]
        value = float(record["value"])
        window = self.windows[building_id]
        window.append(value)

        rule = self.rules.get(building_id)
        if rule and rule.get("threshold_max") and value > float(rule["threshold_max"]):
            self._save_alert(record, rule, float(rule["threshold_max"]))
            return

        if len(window) >= 5:
            mean = sum(window) / len(window)
            if mean > 0 and value > mean * THRESHOLD_MULTIPLIER:
                fallback_rule = rule or {"rule_id": 0, "severity": "warning"}
                self._save_alert(record, fallback_rule, mean * THRESHOLD_MULTIPLIER)


def main():
    engine = AlertEngine()
    consumer = KafkaConsumer(
        TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP,
        value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        auto_offset_reset="latest",
        group_id="alert-engine",
    )
    print("实时预警引擎已启动...")
    try:
        for msg in consumer:
            engine.process(msg.value)
    except KeyboardInterrupt:
        print("预警引擎已停止")
    finally:
        consumer.close()


if __name__ == "__main__":
    main()
