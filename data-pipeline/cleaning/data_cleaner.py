"""数据清洗与异常检测 - Pandas 批处理"""
import json
from datetime import datetime

import numpy as np
import pandas as pd


def clean_energy_data(df: pd.DataFrame) -> pd.DataFrame:
    """缺失值填充、异常值剔除、重复去重"""
    df = df.copy()
    df["event_time"] = pd.to_datetime(df["event_time"])
    df = df.drop_duplicates(subset=["meter_id", "event_time"])

    # 缺失值：同仪表前后均值填充
    df["value"] = df.groupby("meter_id")["value"].transform(
        lambda s: s.interpolate(method="linear").fillna(s.mean())
    )

    # 3σ 异常值剔除
    def remove_outliers(group):
        mean, std = group["value"].mean(), group["value"].std()
        if std == 0:
            return group
        return group[(group["value"] >= mean - 3 * std) & (group["value"] <= mean + 3 * std)]

    df = df.groupby("meter_id", group_keys=False).apply(remove_outliers)
    df["etl_time"] = datetime.utcnow()
    return df.reset_index(drop=True)


def detect_anomalies(df: pd.DataFrame, threshold_multiplier: float = 2.5) -> pd.DataFrame:
    """基于滑动窗口的实时异常检测"""
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
    df = pd.read_json(input_path)
    cleaned = clean_energy_data(df)
    anomalies = detect_anomalies(cleaned)
    cleaned.to_json(output_path, orient="records", date_format="iso")
    anomaly_path = output_path.replace(".json", "_anomalies.json")
    anomalies.to_json(anomaly_path, orient="records", date_format="iso")
    print(f"清洗完成: {len(cleaned)} 条, 异常: {len(anomalies)} 条")
    return cleaned, anomalies


if __name__ == "__main__":
    # 生成示例数据并运行
    sample = []
    for i in range(200):
        sample.append({
            "event_time": pd.Timestamp.now() - pd.Timedelta(minutes=i),
            "building_id": "B001",
            "meter_id": "M001",
            "value": float(np.random.uniform(100, 300)) if i != 50 else 999.0,
        })
    pd.DataFrame(sample).to_json("sample_raw.json", orient="records", date_format="iso")
    run_pipeline("sample_raw.json", "sample_cleaned.json")
