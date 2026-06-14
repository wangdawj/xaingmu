"""
共享连接工厂模块
=============
统一管理 Kafka / MySQL 客户端创建与重试逻辑。
所有数据管道组件通过此模块获取连接，确保配置一致性。
"""

import json
import os
import time

from kafka import KafkaProducer, KafkaConsumer
from kafka.errors import NoBrokersAvailable
import pymysql


def _env(name, default):
    """读取环境变量，不存在时返回默认值"""
    return os.getenv(name, default)


# ======================== Kafka 连接 ========================

def create_kafka_producer(bootstrap=None, max_retries=10):
    """创建 Kafka Producer 实例，支持自动重试

    Args:
        bootstrap: Kafka 集群地址，默认从 KAFKA_BOOTSTRAP 环境变量读取
        max_retries: 最大重试次数，每次间隔 5 秒

    Returns:
        KafkaProducer 实例

    Raises:
        RuntimeError: 重试耗尽仍无法连接
    """
    bootstrap = bootstrap or _env("KAFKA_BOOTSTRAP", "kafka:29092")
    for attempt in range(1, max_retries + 1):
        try:
            producer = KafkaProducer(
                bootstrap_servers=bootstrap,
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),  # 消息体 → JSON bytes
                max_block_ms=10000,
            )
            print(f"[Kafka] Producer 已连接 ({bootstrap})")
            return producer
        except Exception as e:
            print(f"[Kafka] Producer 连接失败 ({attempt}/{max_retries}): {e}")
            if attempt < max_retries:
                time.sleep(5)
    raise RuntimeError(f"[Kafka] Producer 无法连接 {bootstrap}")


def create_kafka_consumer(bootstrap=None, topic="energy.raw", group_id="default", max_retries=10):
    """创建 Kafka Consumer 实例，支持自动重试

    Args:
        bootstrap: Kafka 集群地址
        topic: 消费主题名称
        group_id: 消费者组 ID
        max_retries: 最大重试次数
    """
    bootstrap = bootstrap or _env("KAFKA_BOOTSTRAP", "kafka:29092")
    for attempt in range(1, max_retries + 1):
        try:
            consumer = KafkaConsumer(
                topic,
                bootstrap_servers=bootstrap,
                value_deserializer=lambda m: json.loads(m.decode("utf-8")),  # JSON bytes → 字典
                auto_offset_reset="latest",        # 从最新消息开始消费
                group_id=group_id,
                consumer_timeout_ms=10000,
            )
            print(f"[Kafka] Consumer 已连接 ({bootstrap}), topic={topic}, group={group_id}")
            return consumer
        except Exception as e:
            print(f"[Kafka] Consumer 连接失败 ({attempt}/{max_retries}): {e}")
            if attempt < max_retries:
                time.sleep(5)
    raise RuntimeError(f"[Kafka] Consumer 无法连接 {bootstrap}")


def wait_for_kafka(bootstrap=None, timeout=120):
    """阻塞等待 Kafka 集群就绪（用于启动时的依赖等待）

    Args:
        bootstrap: Kafka 集群地址
        timeout: 最大等待时间（秒）

    Returns:
        True 表示 Kafka 就绪，False 表示超时
    """
    bootstrap = bootstrap or _env("KAFKA_BOOTSTRAP", "kafka:29092")
    deadline = time.time() + timeout
    print(f"[Kafka] 等待就绪 ({bootstrap})...")
    while time.time() < deadline:
        try:
            consumer = KafkaConsumer(
                bootstrap_servers=bootstrap,
                request_timeout_ms=5000,
                api_version_auto_timeout_ms=5000,
            )
            topics = consumer.topics()
            consumer.close()
            print(f"[Kafka] 已就绪, topics: {topics}")
            return True
        except Exception:
            remaining = int(deadline - time.time())
            if remaining > 0:
                time.sleep(3)
    print("[Kafka] 等待超时！")
    return False


# ======================== MySQL 连接 ========================

def create_mysql_connection():
    """创建 MySQL 连接（pymysql）

    用于告警记录写入、数据质量日志存储等场景。
    """
    config = {
        "host": _env("MYSQL_HOST", "localhost"),
        "port": int(_env("MYSQL_PORT", "3306")),
        "user": _env("MYSQL_USER", "energy"),
        "password": _env("MYSQL_PASSWORD", "energy123"),
        "database": _env("MYSQL_DATABASE", "campus_energy"),
        "charset": "utf8mb4",
    }
    return pymysql.connect(**config)
