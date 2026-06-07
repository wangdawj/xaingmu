"""能耗预测模型 - Scikit-learn 线性回归 + 随机森林"""
import json
import os
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split


def generate_training_data(days: int = 30) -> pd.DataFrame:
    """生成/加载训练数据（实际项目从 Hive/MySQL 读取）"""
    records = []
    base = datetime.now() - timedelta(days=days)
    for d in range(days):
        for h in range(24):
            ts = base + timedelta(days=d, hours=h)
            hour_factor = 1.5 if 8 <= h < 22 else 0.6
            weekday_factor = 1.2 if ts.weekday() < 5 else 0.8
            value = 200 * hour_factor * weekday_factor + np.random.normal(0, 15)
            records.append({
                "hour": h,
                "weekday": ts.weekday(),
                "month": ts.month,
                "is_weekend": int(ts.weekday() >= 5),
                "building_id": "B001",
                "value": max(value, 0),
            })
    return pd.DataFrame(records)


def train_and_predict(df: pd.DataFrame, building_id: str = "B001"):
    features = ["hour", "weekday", "month", "is_weekend"]
    sub = df[df["building_id"] == building_id] if "building_id" in df.columns else df
    X = sub[features]
    y = sub["value"]

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    lr = LinearRegression()
    lr.fit(X_train, y_train)
    rf = RandomForestRegressor(n_estimators=100, random_state=42)
    rf.fit(X_train, y_train)

    y_pred_lr = lr.predict(X_test)
    y_pred_rf = rf.predict(X_test)

    metrics = {
        "linear_regression": {
            "mae": round(mean_absolute_error(y_test, y_pred_lr), 2),
            "r2": round(r2_score(y_test, y_pred_lr), 4),
        },
        "random_forest": {
            "mae": round(mean_absolute_error(y_test, y_pred_rf), 2),
            "r2": round(r2_score(y_test, y_pred_rf), 4),
        },
    }

    # 预测未来 24 小时
    future = []
    now = datetime.now()
    for i in range(24):
        ts = now + timedelta(hours=i)
        feat = pd.DataFrame([{
            "hour": ts.hour,
            "weekday": ts.weekday(),
            "month": ts.month,
            "is_weekend": int(ts.weekday() >= 5),
        }])
        future.append({
            "time": ts.isoformat(),
            "predicted_lr": round(float(lr.predict(feat)[0]), 2),
            "predicted_rf": round(float(rf.predict(feat)[0]), 2),
        })

    return {"metrics": metrics, "forecast": future}


def main():
    df = generate_training_data(60)
    result = train_and_predict(df)
    output_path = os.path.join(os.path.dirname(__file__), "forecast_result.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"模型训练完成，结果已保存至 {output_path}")
    print(json.dumps(result["metrics"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
