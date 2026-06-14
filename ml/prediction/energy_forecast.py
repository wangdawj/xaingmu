"""
能耗预测模型（MySQL 版）
========================
基于 Scikit-learn 的短期能耗预测：
- 线性回归 + 随机森林双模型对比
- 从 MySQL energy_record 表加载真实历史数据训练
- 特征：小时循环编码、星期、月份、是否周末
- 输出：未来 24 小时预测 + 模型评估指标

用法:
    python energy_forecast.py                    # 命令行运行，输出到 JSON
    或导入: from ml.prediction.energy_forecast import load_data, train_and_predict
"""

import json
import os
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split, GridSearchCV


def load_data(building_id: str = "B001", days: int = 60,
              host: str = "mysql", port: int = 3306,
              user: str = "energy", password: str = "energy123",
              database: str = "campus_energy") -> pd.DataFrame:
    """从 MySQL energy_record 表加载真实历史能耗数据

    Args:
        building_id: 目标建筑编号
        days: 加载最近 N 天的数据
        host: MySQL 主机地址（Docker 内用 "mysql"，宿主机用 "localhost"）

    Returns:
        包含 hour, weekday, month, is_weekend, hour_sin, hour_cos, value 的 DataFrame
    """
    try:
        import pymysql
    except ImportError:
        print("pymysql 未安装，回退到模拟数据。pip install pymysql")
        return _generate_fallback_data(building_id, days)

    try:
        conn = pymysql.connect(
            host=host, port=port, user=user, password=password,
            database=database, charset="utf8mb4",
        )
        sql = """
            SELECT
                HOUR(event_time) AS hour,
                WEEKDAY(event_time) AS weekday,
                MONTH(event_time) AS month,
                value
            FROM energy_record
            WHERE building_id = %s
              AND event_time >= NOW() - INTERVAL %s DAY
            ORDER BY event_time
        """
        df = pd.read_sql(sql, conn, params=(building_id, days))
        conn.close()

        if len(df) < 50:
            print(f"MySQL 数据量不足 ({len(df)} 条)，回退到模拟数据")
            return _generate_fallback_data(building_id, days)

        print(f"从 MySQL 加载 {len(df)} 条训练数据 (building={building_id}, days={days})")
    except Exception as e:
        print(f"MySQL 连接失败: {e}，回退到模拟数据")
        return _generate_fallback_data(building_id, days)

    # 添加衍生特征
    df["is_weekend"] = (df["weekday"] >= 5).astype(int)
    # 循环时间编码：避免 23→0 的数值断层
    df["hour_sin"] = np.sin(2 * np.pi * df["hour"] / 24)
    df["hour_cos"] = np.cos(2 * np.pi * df["hour"] / 24)
    df["building_id"] = building_id
    return df


def _generate_fallback_data(building_id: str = "B001", days: int = 30) -> pd.DataFrame:
    """回退方案：生成模拟数据（当 MySQL 不可用时）"""
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
                "building_id": building_id,
                "value": max(value, 0),
            })
    df = pd.DataFrame(records)
    df["hour_sin"] = np.sin(2 * np.pi * df["hour"] / 24)
    df["hour_cos"] = np.cos(2 * np.pi * df["hour"] / 24)
    return df


def train_and_predict(df: pd.DataFrame, building_id: str = "B001",
                      tune_hyperparams: bool = False):
    """训练预测模型并生成未来 24 小时预测

    Args:
        df: 训练数据（包含 features 和 target）
        building_id: 要预测的建筑编号
        tune_hyperparams: 是否启用 GridSearchCV 超参数调优（耗时）

    Returns:
        {"metrics": {...}, "forecast": [...], "feature_importance": [...]}
    """
    # 特征列（使用循环编码替代原始 hour）
    features = ["hour_sin", "hour_cos", "weekday", "month", "is_weekend"]

    # 筛选目标建筑的数据
    sub = df[df["building_id"] == building_id] if "building_id" in df.columns else df
    X = sub[features]
    y = sub["value"]

    if len(X) < 10:
        raise ValueError(f"训练数据不足 ({len(X)} 条)，至少需要 10 条")

    # 训练集/测试集划分（80% / 20%）
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    # 模型 1：线性回归（快速基线）
    lr = LinearRegression()
    lr.fit(X_train, y_train)

    # 模型 2：随机森林
    if tune_hyperparams:
        # 网格搜索调优
        rf_grid = GridSearchCV(
            RandomForestRegressor(random_state=42),
            {"n_estimators": [50, 100, 200],
             "max_depth": [None, 10, 20],
             "min_samples_split": [2, 5]},
            cv=3, scoring="neg_mean_absolute_error", n_jobs=-1,
        )
        rf_grid.fit(X_train, y_train)
        rf = rf_grid.best_estimator_
        print(f"随机森林最优参数: {rf_grid.best_params_}")
    else:
        rf = RandomForestRegressor(n_estimators=100, max_depth=15, random_state=42)
        rf.fit(X_train, y_train)

    # 测试集评估
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
        "train_samples": len(X_train),
        "test_samples": len(X_test),
    }

    # 特征重要性（仅随机森林）
    feat_imp = sorted(
        zip(features, rf.feature_importances_),
        key=lambda x: x[1], reverse=True,
    )

    # 预测未来 24 小时
    future = []
    now = datetime.now()
    for i in range(24):
        ts = now + timedelta(hours=i)
        hour = ts.hour
        weekday = ts.weekday()
        feat = pd.DataFrame([{
            "hour_sin": np.sin(2 * np.pi * hour / 24),
            "hour_cos": np.cos(2 * np.pi * hour / 24),
            "weekday": weekday,
            "month": ts.month,
            "is_weekend": int(weekday >= 5),
        }])
        future.append({
            "time": ts.strftime("%Y-%m-%d %H:00"),
            "predicted_lr": round(float(lr.predict(feat)[0]), 2),
            "predicted_rf": round(float(rf.predict(feat)[0]), 2),
        })

    return {
        "building_id": building_id,
        "metrics": metrics,
        "feature_importance": [{"feature": f, "importance": round(i, 4)} for f, i in feat_imp],
        "forecast": future,
    }


def main():
    """训练入口：加载真实数据 → 训练模型 → 保存结果"""
    # 从 MySQL 加载（Docker 内），失败时自动回退到模拟数据
    building_id = "B001"
    df = load_data(building_id, days=60)
    result = train_and_predict(df, building_id, tune_hyperparams=False)

    output_path = os.path.join(os.path.dirname(__file__), "forecast_result.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"模型训练完成 → {output_path}")
    print(json.dumps(result["metrics"], ensure_ascii=False, indent=2))
    print(f"特征重要性: {result['feature_importance']}")


if __name__ == "__main__":
    main()
