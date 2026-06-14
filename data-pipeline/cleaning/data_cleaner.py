"""
数据清洗与异常检测模块
==================
基于 Pandas 的离线批处理管道：
- clean_energy_data(): 缺失值填充、3σ 异常值剔除、重复去重
- detect_anomalies(): 滑动窗口异常检测
- run_pipeline(): 串联清洗+检测的完整管道
"""

from datetime import datetime

import numpy as np
import pandas as pd


def clean_energy_data(df: pd.DataFrame) -> pd.DataFrame:
    """数据清洗管道：缺失值填充 → 异常值剔除 → 重复去重

    处理步骤：
        1. 去重：按 (meter_id, event_time) 组合去除重复记录
        2. 缺失值：同一仪表前后均值线性插值填充
        3. 异常值：3σ 法则 — 超出均值 ± 3 倍标准差的值被剔除

    Args:
        df: 原始数据 DataFrame，需包含 meter_id、event_time、value 列

    Returns:
        清洗后的 DataFrame，新增 etl_time 列标记处理时间
    """
    df = df.copy()
    df["event_time"] = pd.to_datetime(df["event_time"])
    # 1. 去重
    df = df.drop_duplicates(subset=["meter_id", "event_time"])

    # 2. 缺失值：同仪表前后均值填充（线性插值 → 均值回退）
    df["value"] = df.groupby("meter_id")["value"].transform(
        lambda s: s.interpolate(method="linear").fillna(s.mean())
    )

    # 3. 3σ 异常值剔除（按仪表分组）
    def remove_outliers(group):
        mean, std = group["value"].mean(), group["value"].std()
        if std == 0:
            return group
        return group[(group["value"] >= mean - 3 * std) & (group["value"] <= mean + 3 * std)]

    df = df.groupby("meter_id", group_keys=False).apply(remove_outliers)
    df["etl_time"] = datetime.utcnow()
    return df.reset_index(drop=True)


def detect_anomalies(df: pd.DataFrame, threshold_multiplier: float = 2.5) -> pd.DataFrame:
    """基于滚动窗口的异常检测

    对每个仪表按时间排序后，计算 12 点滚动均值和标准差，
    当前值超过 均值 + threshold_multiplier × 标准差 时标记为异常。

    Args:
        df: 清洗后的 DataFrame
        threshold_multiplier: 异常阈值倍数，默认 2.5

    Returns:
        异常记录 DataFrame，包含 meter_id、building_id、event_time、value、threshold、severity
    """
    alerts = []
    for meter_id, group in df.groupby("meter_id"):
        group = group.sort_values("event_time")
        rolling_mean = group["value"].rolling(window=12, min_periods=3).mean()
        rolling_std = group["value"].rolling(window=12, min_periods=3).std()
        upper = rolling_mean + threshold_multiplier * rolling_std
        mask = group["value"] > upper
        for idx in group[mask].index:
            row = group.loc[idx]
            alerts.append({
                "meter_id": meter_id,
                "building_id": row.get("building_id"),
                "event_time": row["event_time"].isoformat(),
                "value": float(row["value"]),
                "threshold": float(upper.loc[idx]) if pd.notna(upper.loc[idx]) else None,
                "severity": "warning",
            })
    return pd.DataFrame(alerts)


def run_pipeline(input_path: str, output_path: str):
    """完整的清洗 + 异常检测管道

    Args:
        input_path: 原始 JSON 文件路径
        output_path: 清洗后 JSON 输出路径（异常文件在同目录下生成 _anomalies 后缀文件）
    """
    df = pd.read_json(input_path)
    cleaned = clean_energy_data(df)
    anomalies = detect_anomalies(cleaned)
    cleaned.to_json(output_path, orient="records", date_format="iso")
    anomaly_path = output_path.replace(".json", "_anomalies.json")
    anomalies.to_json(anomaly_path, orient="records", date_format="iso")
    print(f"清洗完成: {len(cleaned)} 条, 异常: {len(anomalies)} 条")
    return cleaned, anomalies


if __name__ == "__main__":
    # 生成示例数据并运行管道演示
    sample = []
    for i in range(200):
        sample.append({
            "event_time": pd.Timestamp.now() - pd.Timedelta(minutes=i),
            "building_id": "B001",
            "meter_id": "M001",
            "value": float(np.random.uniform(100, 300)) if i != 50 else 999.0,  # 第 50 条注入一个异常值
        })
    pd.DataFrame(sample).to_json("sample_raw.json", orient="records", date_format="iso")
    run_pipeline("sample_raw.json", "sample_cleaned.json")
