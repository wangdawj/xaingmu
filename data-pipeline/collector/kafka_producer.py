"""
=============================================================================
Kafka 数据采集模拟器（ISimulated Sensor Data Producer）
=============================================================================
【功能说明】
  模拟 OPC UA / 传感器设备，按固定间隔向 Kafka 发送模拟的能耗采集数据。
  生产环境中可替换为真实的 OPC UA / Modbus / MQTT 采集器。

【数据特征】
  - 功率值（kW）与当前时间强相关：
    * 白天(8:00-21:59)：系数 0.7~1.3   →  功率较高（教学楼/图书馆/食堂在用）
    * 夜间(22:00-次日7:59)：系数 0.2~0.5   →  功率较低（仅基础照明/待机）
  - 周末(周六/周日)：额外降低约 20%（人流量减少）
  - 覆盖全部 6 栋建筑，各有不同的基准功率（base_kw）

【数据流向】
  Python 模拟传感器 → Kafka Topic "energy.raw" → Consumer → MySQL energy_record 表
=============================================================================
"""

# ======================== 导入模块 ========================
import random                            # 用于生成随机功率波动和电压变化
import time                              # 控制发送间隔
from datetime import datetime, timezone  # 获取当前时间戳

# 项目共享工具：封装 Kafka Producer 的创建逻辑（连接地址、序列化等）
from shared.connections import create_kafka_producer

# ======================== 常量配置 ========================

# Kafka 主题名：所有采集数据都发布到这个主题
# Consumer 端（kafka_to_mysql.py / realtime_alert.py）通过订阅同一主题消费数据
TOPIC = "energy.raw"

# 校园建筑清单
# 每个元素是一个字典，包含建筑的全部标识信息：
#   building_id : 建筑编号（与数据库 building 表主键一致）
#   region_id   : 所属校区区域编号
#   meter_id    : 总电表编号
#   base_kw     : 基准功率（kW）— 不同建筑类型的用电基线不同：
#                 教学楼 150/120、宿舍 80/70、图书馆 200（面积大）、食堂 100
# 注意：必须与数据库 building 表保持一致（B001~B006），否则 FK 约束会拒绝写入
BUILDINGS = [
    {"building_id": "B001", "region_id": "R001", "meter_id": "M001", "base_kw": 150},   # 第一教学楼
    {"building_id": "B002", "region_id": "R001", "meter_id": "M002", "base_kw": 120},   # 第二教学楼
    {"building_id": "B003", "region_id": "R001", "meter_id": "M003", "base_kw": 80},    # 1号宿舍楼
    {"building_id": "B004", "region_id": "R002", "meter_id": "M005", "base_kw": 70},    # 2号宿舍楼（西校区）
    {"building_id": "B005", "region_id": "R001", "meter_id": "M004", "base_kw": 200},   # 中心图书馆
    {"building_id": "B006", "region_id": "R001", "meter_id": "M006", "base_kw": 100},   # 第一食堂
]


# ======================== 核心函数 ========================

def generate_record(b=None):
    """生成一条模拟的能耗采集记录（模拟传感器单次上报）

    【功率模拟策略（4 层叠加）】
      第 1 层 — 基准功率(base_kw)：每种建筑类型的基础用电水平（教学楼=150, 宿舍=80, 等等）
      第 2 层 — 昼夜因子(hour_factor)：
              白天(8:00-21:59) → 系数 0.7~1.3  （上课/办公/就餐高峰）
              夜间(22:00-7:59) → 系数 0.2~0.5  （仅基础照明/待机负荷）
      第 3 层 — 周末因子(weekend_factor)：
              工作日(周一~周五) → 系数 1.0
              周末(周六/周日)   → 系数 0.8（人流量减少约 20%）
      第 4 层 — 随机噪声：±10% 随机波动（模拟真实传感器的测量误差和用电随机性）

    【电压与电流】
      电压: 220V 市电 ±10% 波动（218V~242V）
      电流: 根据 I = P/U 计算（电流 = 功率 / 电压）

    Args:
        b: 建筑字典（可选）。传入时直接使用该建筑，不传则随机选一栋

    Returns:
        dict: 包含 event_time, building_id, value, voltage, current 等字段的记录
    """
    # 如果没有指定建筑，随机选择一栋（每轮循环中不会走这里，因为 main() 中传了参数）
    if b is None:
        b = random.choice(BUILDINGS)

    # 获取当前 UTC 时间（容器内时区统一）
    now = datetime.now(timezone.utc)
    hour = now.hour      # 当前小时(0-23)
    weekday = now.weekday()  # 星期几(0=周一,5=周六,6=周日)

    # ---- 第 2 层：昼夜因子 ----
    # random.uniform(a, b) 生成 [a, b) 范围内的随机浮点数
    # 白天系数 0.7~1.3：实际功率在基准的 70%~130% 之间波动
    # 夜间系数 0.2~0.5：实际功率骤降至基准的 20%~50%
    if 8 <= hour < 22:
        hour_factor = random.uniform(0.7, 1.3)   # 峰时段（14 小时）
    else:
        hour_factor = random.uniform(0.2, 0.5)   # 谷时段（10 小时）

    # ---- 第 3 层：周末因子 ----
    # weekday() 返回 0-6，>=5 表示周六(5)或周日(6)
    weekend_factor = 0.8 if weekday >= 5 else 1.0

    # ---- 计算最终功率值 ----
    # 公式：基准功率 × 昼夜系数 × 周末系数 × 随机噪声
    # round(value, 2) 保留 2 位小数，避免浮点精度问题
    value = round(b["base_kw"] * hour_factor * weekend_factor * random.uniform(0.9, 1.1), 2)

    # 模拟电压测量值
    # 市电标准 220V，允许 ±10% 波动（218V~242V）
    voltage = round(random.uniform(218, 242), 1)

    # ---- 返回完整的传感器记录 ----
    return {
        "event_time": now.isoformat(),            # ISO 8601 格式时间戳
        "building_id": b["building_id"],          # 建筑编号
        "region_id": b["region_id"],              # 区域编号
        "meter_id": b["meter_id"],                # 仪表编号
        "energy_type": "electricity",             # 能源类型（本项目仅用电）
        "data_type": "realtime",                  # 数据类型（实时采集）
        "value": value,                           # 功率值（kW）
        "unit": "kWh",                            # 单位
        "voltage": voltage,                       # 电压（V）
        "current": round(value / voltage, 2),     # 电流（A）= 功率 / 电压
    }


# ======================== 主循环 ========================

def main(interval_sec: float = 1.0):
    """采集器主循环：每轮给全部 6 栋建筑各发一条数据到 Kafka

    【为什么每轮给全部建筑发？】
      旧版本用 random.choice 随机选楼，导致数据分布严重不均（某些建筑长期无数据）。
      改为每轮遍历全部 6 栋建筑，确保数据均匀分布，前端每个建筑都能看到完整的 24h 曲线。

    【发送频率】
      每 1 秒完成一轮（6 条 × 1秒 = 360 条/分钟），持续运行直到 Ctrl+C 中断。

    Args:
        interval_sec: 每轮发送后的等待间隔（秒），默认 1 秒
    """
    # 创建 Kafka 生产者（连接 kafka:29092）
    producer = create_kafka_producer()
    print(f"[Producer] 开始向 topic [{TOPIC}] 发送 {len(BUILDINGS)} 栋建筑的模拟数据...")
    count = 0  # 总发送条数计数器

    try:
        # 无限循环，持续产生数据
        while True:
            # 遍历全部 6 栋建筑，每栋生成一条记录并发送
            for b in BUILDINGS:
                record = generate_record(b)   # 生成模拟记录
                try:
                    # producer.send(topic, record) 是异步操作：
                    # 把记录放入内部缓冲区，不会立即发送到 Kafka 服务器
                    # 累积一定量后批量发送，提高吞吐量
                    producer.send(TOPIC, record)
                    count += 1
                except Exception as e:
                    # 发送失败时的容错处理：
                    # 1. 关闭旧连接（释放资源）
                    # 2. 等待 3 秒（可能 Kafka 正在重启）
                    # 3. 重新创建生产者（重新连接）
                    print(f"[Producer] 发送失败，尝试重连: {e}")
                    producer.close()
                    time.sleep(3)
                    producer = create_kafka_producer()

            # flush() 强制将缓冲区中所有待发送的消息推送到 Kafka 服务器
            # 确保数据不会在内存中积压过久
            producer.flush()

            # 每 10 轮（60 条）打印一次进度
            if count % 60 == 0:
                print(f"[Producer] 已发送 {count} 条 ({count // 6} 轮)")

            # 等待指定间隔后再进行下一轮发送
            time.sleep(interval_sec)

    except KeyboardInterrupt:
        # 用户按 Ctrl+C 时优雅退出
        print(f"\n[Producer] 停止采集，共发送 {count} 条")
    finally:
        # 无论正常还是异常退出，都要关闭生产者连接
        producer.close()
        print("[Producer] 已关闭")


# ======================== 入口 ========================
if __name__ == "__main__":
    main()
