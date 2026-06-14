"""
Flink 风格实时预警引擎
===================
独立的 Python 实现（可迁移至 PyFlink），消费 Kafka 能耗数据，
基于规则阈值 + 滑动窗口异常检测，实时触发告警并写入 MySQL。

告警策略：
    1. 规则阈值告警：当前值 > 预设的 threshold_max
    2. 滑动窗口告警：当前值 > 窗口均值 × 2.0（突增检测）
"""

import time
from collections import defaultdict, deque
from datetime import datetime

import pymysql
from shared.connections import create_kafka_consumer, create_mysql_connection

# Kafka 消费主题
TOPIC = "energy.raw"

# 滑动窗口参数：每个建筑保留最近 20 条数据
WINDOW_SIZE = 20

# 突增倍数阈值：当前值超过窗口均值 2 倍时告警
THRESHOLD_MULTIPLIER = 2.0


class AlertEngine:
    """实时预警引擎 — 消费 Kafka 消息，检测异常并触发告警"""

    def __init__(self):
        # 每个建筑的滑动窗口（定长双端队列）
        self.windows: dict[str, deque] = defaultdict(lambda: deque(maxlen=WINDOW_SIZE))
        # 从 MySQL 加载告警规则（启动时加载，运行中不变）
        self.rules = self._load_rules()

    def _load_rules(self) -> dict:
        """从 MySQL 加载启用的告警规则，以 building_id 为键索引"""
        conn = create_mysql_connection()
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
        """将告警记录持久化到 MySQL alert_record 表"""
        try:
            conn = create_mysql_connection()
        except Exception as e:
            print(f"[Alert] MySQL 连接失败: {e}，告警未入库")
            return
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
        except Exception as e:
            print(f"[Alert] 写入告警失败: {e}")
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def process(self, record: dict):
        """处理单条能耗记录

        检测逻辑：
            1. 规则阈值检查（优先级最高）
            2. 滑动窗口突增检查（窗口 >= 5 条时生效）
        """
        building_id = record["building_id"]
        value = float(record["value"])
        window = self.windows[building_id]
        window.append(value)

        # 规则阈值告警：当前值超过预设上限
        rule = self.rules.get(building_id)
        if rule and rule.get("threshold_max") and value > float(rule["threshold_max"]):
            self._save_alert(record, rule, float(rule["threshold_max"]))
            return

        # 滑动窗口异常：当前值远超窗口均值（突增检测）
        if len(window) >= 5:
            mean = sum(window) / len(window)
            if mean > 0 and value > mean * THRESHOLD_MULTIPLIER:
                if rule and rule.get("rule_id"):
                    self._save_alert(record, rule, mean * THRESHOLD_MULTIPLIER)
                else:
                    print(f"[Alert] {record['building_id']} value={record['value']} "
                          f"超过滑动窗口阈值 {mean * THRESHOLD_MULTIPLIER:.2f}，无匹配规则，跳过入库")


def main():
    """预警引擎入口：创建消费者和引擎实例，循环处理消息"""
    engine = AlertEngine()
    consumer = create_kafka_consumer(topic=TOPIC, group_id="alert-engine")
    print("[Alert] 实时预警引擎已启动...")
    try:
        for msg in consumer:
            try:
                engine.process(msg.value)
            except Exception as e:
                print(f"[Alert] 处理消息异常: {e}")
    except KeyboardInterrupt:
        print("[Alert] 预警引擎已停止")
    finally:
        consumer.close()
        print("[Alert] 已关闭")


if __name__ == "__main__":
    main()
