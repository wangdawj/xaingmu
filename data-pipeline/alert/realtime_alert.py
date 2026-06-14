"""
=============================================================================
Flink 风格实时预警引擎（Real-time Alert Engine）
=============================================================================
【功能说明】
  独立的 Python 进程，消费 Kafka 能耗数据，实时检测异常并写入告警记录到 MySQL。
  架构灵感来自 Apache Flink 流处理，使用纯 Python 实现（可迁移至 PyFlink）。

【告警策略（双轨制）】
  策略 1 — 规则阈值告警（Rule-based Threshold）：
    从 MySQL alert_rule 表加载每个建筑的 threshold_max，当前值超过上限时立即告警。
    适用场景：已知安全上限（如食堂功率不超过 100kW），超过即异常。

  策略 2 — 滑动窗口异常检测（Sliding Window Anomaly Detection）：
    每个建筑维护最近 20 条数据的滑动窗口，当前值超过窗口均值 × 2.0 时告警。
    适用场景：功率突然飙升（如深夜实验室设备意外全开），阈值规则可能没能覆盖。

【数据流向】
  Kafka Topic → AlertEngine.process() → 双策略检测 → MySQL alert_record 表
=============================================================================
"""

# ======================== 导入模块 ========================
import time                                  # 用于调试/延迟
from collections import defaultdict, deque   # defaultdict: 自动创建滑动窗口, deque: 定长双端队列
from datetime import datetime                # 记录告警触发时间

import pymysql                               # MySQL 连接

# 共享工具：Kafka Consumer 和 MySQL 连接工厂
from shared.connections import create_kafka_consumer, create_mysql_connection

# ======================== 常量配置 ========================

# Kafka 主题（与 Producer 保持一致）
TOPIC = "energy.raw"

# 滑动窗口大小：每个建筑保留最近 20 条功率数据
# 窗口越大 → 检测越稳定但响应越慢
# 窗口越小 → 检测越灵敏但容易误报
WINDOW_SIZE = 20

# 突增倍数阈值：当前值 > (窗口均值 × 2.0) 时触发告警
# 2.0 表示当前值是过去平均水平的 2 倍以上
# 这个值不宜设太小（容易误报），也不宜太大（漏报）
THRESHOLD_MULTIPLIER = 2.0


# ======================== 告警引擎类 ========================

class AlertEngine:
    """实时预警引擎

    【核心数据结构】
      self.windows: dict[str, deque]
        键 = building_id（如 "B001"）
        值 = deque（定长 20 的双端队列）
        每次新数据到达时 append，队列满时自动丢弃最旧的数据

      self.rules: dict[str, dict]
        键 = building_id
        值 = {rule_id, building_id, threshold_max, severity}
        从 MySQL alert_rule 表加载，进程启动时读取一次，运行中不变
    """

    def __init__(self):
        # 初始化滑动窗口字典
        # defaultdict(deque) 确保首次访问不存在的 building_id 时自动创建一个空 deque
        # deque(maxlen=20) 确保队列最多保留 20 条数据，超出时自动弹出最旧的
        self.windows: dict[str, deque] = defaultdict(lambda: deque(maxlen=WINDOW_SIZE))

        # 启动时从 MySQL 加载告警规则
        self.rules = self._load_rules()

    # ---------- 规则加载 ----------

    def _load_rules(self) -> dict:
        """从 MySQL alert_rule 表加载所有启用的告警规则

        返回以 building_id 为键的字典，便于 O(1) 查找：
          {"B001": {"rule_id": 1, "threshold_max": 130, "severity": "warning"}, ...}

        为什么启动时加载一次而不每次查数据库？
          1. 性能：避免每条数据处理都查一次 MySQL
          2. 简单：规则不频繁变动，按需重启 pipeline 即可刷新
        """
        conn = create_mysql_connection()
        try:
            # DictCursor：查询结果返回为字典列表而非元组列表，可以用列名访问字段
            with conn.cursor(pymysql.cursors.DictCursor) as cur:
                cur.execute(
                    "SELECT rule_id, building_id, threshold_max, severity "
                    "FROM alert_rule WHERE enabled = 1"  # enabled=1 表示启用
                )
                rules = {}
                for row in cur.fetchall():
                    rules[row["building_id"]] = row
                print(f"[Alert] 已加载 {len(rules)} 条告警规则")
                return rules
        finally:
            conn.close()

    # ---------- 告警持久化 ----------

    def _save_alert(self, record: dict, rule: dict, threshold: float):
        """将告警记录持久化到 MySQL alert_record 表

        Args:
            record: Kafka 消息中的原始能耗记录
            rule:    触发的告警规则（包含 rule_id, severity 等）
            threshold: 触发告警的阈值（用于记录在告警表中）
        """
        try:
            # 每次告警创建新的数据库连接（避免长连接超时问题）
            conn = create_mysql_connection()
        except Exception as e:
            print(f"[Alert] MySQL 连接失败: {e}，告警未入库")
            return
        try:
            with conn.cursor() as cur:
                # 插入告警记录
                cur.execute(
                    """INSERT INTO alert_record
                       (rule_id, building_id, meter_id, energy_type, alert_value,
                        threshold, severity, message, triggered_at)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (
                        rule["rule_id"],                         # 关联的规则 ID
                        record["building_id"],                   # 建筑编号
                        record.get("meter_id"),                  # 仪表编号（可选）
                        record.get("energy_type", "electricity"),# 能源类型
                        record["value"],                         # 触发时的实际功率值
                        threshold,                               # 触发阈值
                        rule["severity"],                        # 严重级别: info/warning/critical
                        # 告警消息：拼接可读的描述文本
                        f"楼宇 {record['building_id']} 能耗 {record['value']} 超过阈值 {threshold:.2f}",
                        datetime.now(),                          # 触发时间
                    ),
                )
            conn.commit()   # 提交事务
            print(f"[ALERT] {record['building_id']} value={record['value']} threshold={threshold:.2f}")
        except Exception as e:
            print(f"[Alert] 写入告警失败: {e}")
        finally:
            try:
                conn.close()
            except Exception:
                pass

    # ---------- 核心检测逻辑 ----------

    def process(self, record: dict):
        """处理单条能耗记录 — 告警引擎的核心方法

        对每条到达的能耗数据依次执行两种检测策略：

        【策略 1】规则阈值检查（优先执行）
          从 self.rules 查找该建筑的 threshold_max
          如果当前功率值 > threshold_max → 立即触发告警
          这是静态阈值，适合已知安全范围的场景

        【策略 2】滑动窗口异常检测
          将当前值加入该建筑的滑动窗口（deque，最多 20 条）
          计算窗口均值
          如果 当前值 > 均值 × 2.0 → 触发突增告警
          要求窗口至少积累 5 条数据后才生效（避免冷启动误报）

        Args:
            record: Kafka 消息的 value 部分，包含 building_id, value 等字段
        """
        building_id = record["building_id"]
        value = float(record["value"])

        # ---- 将当前值加入滑动窗口 ----
        # deque.append 时如果队列已满(20条)，会自动丢弃最旧的一条
        window = self.windows[building_id]
        window.append(value)

        # ---- 策略 1：规则阈值告警 ----
        # 从规则表中查找该建筑有没有配阈值
        rule = self.rules.get(building_id)
        if rule and rule.get("threshold_max") and value > float(rule["threshold_max"]):
            # 当前功率超过阈值上限 → 立即告警
            self._save_alert(record, rule, float(rule["threshold_max"]))
            return  # 已触发阈值告警，不再检查滑动窗口

        # ---- 策略 2：滑动窗口异常检测 ----
        # 要求窗口至少有 5 条数据（冷启动保护：刚开始运行时数据不足，不可靠）
        if len(window) >= 5:
            mean = sum(window) / len(window)  # 窗口均值
            # 检查是否突增：当前值 > 窗口均值 × 2.0
            if mean > 0 and value > mean * THRESHOLD_MULTIPLIER:
                if rule and rule.get("rule_id"):
                    # 有匹配规则 → 使用规则的 rule_id 和 severity 入库
                    self._save_alert(record, rule, mean * THRESHOLD_MULTIPLIER)
                else:
                    # 没有匹配规则 → 只打印日志，不写数据库（无法确定 severity）
                    print(f"[Alert] {record['building_id']} value={record['value']} "
                          f"超过滑动窗口阈值 {mean * THRESHOLD_MULTIPLIER:.2f}，无匹配规则，跳过入库")


# ======================== 主函数 ========================

def main():
    """预警引擎入口

    【运行方式】
      由 data-pipeline/run_all.py 作为独立线程启动
      也可以单独运行: python realtime_alert.py

    【工作流程】
      1. 创建 AlertEngine 实例（加载规则 + 初始化滑动窗口）
      2. 创建 Kafka Consumer，订阅 energy.raw 主题
      3. 循环消费消息，每条消息交给 engine.process() 处理
      4. 捕获 Ctrl+C 信号优雅退出
    """
    # 创建告警引擎实例（内部会从 MySQL 加载规则）
    engine = AlertEngine()

    # 创建 Kafka 消费者
    # group_id="alert-engine" 确保告警引擎独立消费，不与其他 Consumer 冲突
    consumer = create_kafka_consumer(topic=TOPIC, group_id="alert-engine")
    print("[Alert] 实时预警引擎已启动...")

    try:
        # 逐个消费 Kafka 消息
        for msg in consumer:
            try:
                # msg.value 是 JSON 反序列化后的字典
                engine.process(msg.value)
            except Exception as e:
                # 单条消息处理异常不会导致整个引擎崩溃
                print(f"[Alert] 处理消息异常: {e}")

    except KeyboardInterrupt:
        print("[Alert] 预警引擎已停止")
    finally:
        consumer.close()
        print("[Alert] 已关闭")


# ======================== 入口 ========================
if __name__ == "__main__":
    main()
