"""
统一数据管道启动器
===============
管理 Producer / Consumer / Alert / Cleaning 四个组件的生命周期：
- 多线程并发运行
- 异常自动重试
- 优雅退出（SIGINT / SIGTERM 信号处理）
"""

import signal
import sys
import threading
import time
import traceback

from shared.connections import wait_for_kafka


# 全局退出标志（线程安全）
shutdown_event = threading.Event()


def run_with_retry(name: str, target, *args, **kwargs):
    """在线程中运行目标函数，异常退出时自动重试

    Args:
        name: 组件名称（用于日志）
        target: 目标函数
        *args, **kwargs: 传递给目标函数的参数
    """
    retry_delay = 5  # 重试间隔（秒）
    while not shutdown_event.is_set():
        try:
            print(f"[启动器] 启动组件: {name}")
            target(*args, **kwargs)
        except KeyboardInterrupt:
            break
        except Exception:
            if not shutdown_event.is_set():
                print(f"[启动器] {name} 异常退出，{retry_delay}s 后重试:")
                traceback.print_exc()
                shutdown_event.wait(retry_delay)
    print(f"[启动器] 组件已停止: {name}")


def run_cleaning_loop():
    """离线清洗定时器：首次等 30s 让数据积累，之后每 10 分钟执行一次

    从 MySQL energy_record 拉取数据 → Pandas 清洗/异常检测 → 结果写入 data_quality_log
    """
    first_run = True
    while not shutdown_event.is_set():
        wait = 30 if first_run else 600  # 首次等 30 秒积累数据，之后每 10 分钟
        if shutdown_event.wait(wait):
            break
        try:
            from cleaning.run_mysql_cleaning import run_mysql_cleaning
            print("[启动器] 触发离线清洗...")
            run_mysql_cleaning(hours=2)
        except Exception:
            print("[启动器] 离线清洗异常:")
            traceback.print_exc()
        first_run = False


def main():
    """启动器入口：等待 Kafka 就绪 → 启动四个工作线程 → 监听退出信号"""
    # 先确保 Kafka 可用
    if not wait_for_kafka():
        print("[启动器] Kafka 不可用，退出")
        sys.exit(1)

    # 延迟导入各组件入口函数，避免启动阶段因依赖缺失而崩溃
    from collector.kafka_producer import main as run_producer
    from collector.kafka_to_mysql import main as run_consumer
    from alert.realtime_alert import main as run_alert

    threads = [
        threading.Thread(target=run_with_retry, args=("Producer", run_producer), daemon=True),
        threading.Thread(target=run_with_retry, args=("Consumer→MySQL", run_consumer), daemon=True),
        threading.Thread(target=run_with_retry, args=("AlertEngine", run_alert), daemon=True),
        threading.Thread(target=run_cleaning_loop, daemon=True, name="CleaningLoop"),
    ]

    for t in threads:
        t.start()

    print("[启动器] 所有组件已启动 (Producer + Consumer + Alert + Cleaning)")

    def _shutdown(sig, frame):
        """信号处理器：设置退出标志，通知所有线程停止"""
        print(f"\n[启动器] 收到信号 {sig}，正在优雅退出...")
        shutdown_event.set()

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    # 主线程等待退出信号
    while not shutdown_event.is_set():
        shutdown_event.wait(1)

    print("[启动器] 等待组件停止...")
    for t in threads:
        t.join(timeout=10)
    print("[启动器] 数据管道已停止")


if __name__ == "__main__":
    main()
