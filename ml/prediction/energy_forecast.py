"""
=============================================================================
能耗预测独立脚本（Energy Forecast — Standalone Script）
=============================================================================
【功能说明】
  从 MySQL energy_record 表加载历史数据，训练 Scikit-learn 双模型
  （线性回归 + 随机森林），评估并输出预测结果。
  与 backend/routes/energy.py 中的 /api/energy/forecast 接口逻辑一致，
  区别：此脚本用于命令行手动运行和调试，接口用于前端调用。

【运行方式】
  python energy_forecast.py          → 预测 B001（默认）
  python energy_forecast.py B005     → 预测指定建筑

【输出内容】
  1. 数据加载统计（总条数、采样后条数、生成模拟数据条数）
  2. 模型评估指标（MAE、R²）
  3. 特征重要性排序
  4. 未来 24 小时预测表（逐小时）（用于答辩展示）

【依赖说明】
  需要先 pip install scikit-learn pandas numpy pymysql sqlalchemy
  或使用后端 Dockerfile 中已安装的依赖
=============================================================================
"""

import sys
import pandas as pd
import numpy as np

# Scikit-learn 模型
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, r2_score

# 数据库连接
from sqlalchemy import create_engine, text
from datetime import datetime, timedelta


def load_data_from_mysql(building_id: str = "B001", days: int = 60) -> pd.DataFrame:
    """从 MySQL 拉取指定建筑的历史能耗数据

    Args:
        building_id: 建筑编号（默认 B001）
        days:        拉取最近多少天的数据

    Returns:
        DataFrame with columns: [hour, weekday, value]
        如果无数据返回空 DataFrame
    """
    # SQLAlchemy 连接字符串
    # 容器内 service name 是 "mysql"，本地运行可改为 "localhost"
    engine = create_engine(
        "mysql+pymysql://energy:energy123@mysql:3306/campus_energy?charset=utf8mb4"
    )
    with engine.connect() as conn:
        rows = conn.execute(
            text("""
                SELECT HOUR(event_time) AS hour,
                       WEEKDAY(event_time) AS weekday,
                       value
                FROM energy_record
                WHERE building_id = :bid
                  AND event_time >= NOW() - INTERVAL :d DAY
                ORDER BY event_time
            """),
            {"bid": building_id, "d": days},
        ).fetchall()
    engine.dispose()
    if not rows:
        return pd.DataFrame(columns=["hour", "weekday", "value"])
    return pd.DataFrame(rows, columns=["hour", "weekday", "value"])


def generate_synthetic_data(days: int = 14, base_kw: float = 150) -> pd.DataFrame:
    """生成符合昼夜节律的模拟训练数据

    【生成逻辑 — 与 Kafka Producer 完全一致】
      - 基准功率：150kW（B001 的 base_kw）
      - 白天(8-21点)：功率 = 基准 × (0.7~1.3) × 周末系数 × 随机噪声
      - 夜间(22-7点)：功率 = 基准 × (0.2~0.5) × 周末系数 × 随机噪声
      - 周末系数：工作日 1.0，周六日 0.8

    Args:
        days:    模拟数据的天数（默认 14 天，覆盖 2 个完整周）
        base_kw: 基准功率（kW）

    Returns:
        DataFrame with columns: [hour, weekday, value]
    """
    records = []
    for day in range(days):
        for h in range(24):
            # weekday 按日历递增，从周六开始（确保覆盖周末）
            wd = (6 + day) % 7
            is_day = 8 <= h < 22
            # 昼夜系数：白天功率高，夜间功率低
            hour_factor = np.random.uniform(0.7, 1.3) if is_day else np.random.uniform(0.2, 0.5)
            # 周末人流量减少，额外降低 20%
            weekend_factor = 0.8 if wd >= 5 else 1.0
            # 最终功率 = 基准 × 昼夜系数 × 周末系数 × 随机噪声(±10%)
            value = round(base_kw * hour_factor * weekend_factor * np.random.uniform(0.9, 1.1), 2)
            records.append({"hour": h, "weekday": wd, "value": value})
    return pd.DataFrame(records)


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """构建机器学习特征

    输入 DataFrame 需包含列 [hour, weekday, value]
    输出在输入基础上新增特征列：

      is_daytime (int) : 是否白天(8-21点)，二进制 0/1
      is_weekend (int) : 是否周末(周六日)，二进制 0/1
      hour_sin (float) : 小时的循环正弦编码 sin(2π × hour / 24)
      hour_cos (float) : 小时的循环余弦编码 cos(2π × hour / 24)

    【为什么用 sin/cos 循环编码？】
      - 普通整数编码：23 点和 0 点差 23 个单位，但实际只差 1 小时
      - sin/cos 编码：把 24 小时映射到单位圆上，23 点和 0 点位置相邻
      - sin 和 cos 搭配使用：可以唯一确定圆上的任意位置
        （单独用 sin 或 cos 有对称歧义，如 sin(π/4)=sin(3π/4)）
    """
    df = df.copy()
    df["is_weekend"] = (df["weekday"] >= 5).astype(int)
    df["is_daytime"] = ((df["hour"] >= 8) & (df["hour"] < 22)).astype(int)
    df["hour_sin"] = np.sin(2 * np.pi * df["hour"] / 24)
    df["hour_cos"] = np.cos(2 * np.pi * df["hour"] / 24)
    return df


def train_and_evaluate(X, y, random_state=42):
    """训练评估双模型（线性回归 + 随机森林）
    
    Args:
        X: 特征矩阵
        y: 目标值（功率 kW）
        random_state: 随机种子（保证可复现）
    
    Returns:
        tuple: (metrics_dict, feature_importance_list, trained_models_dict)
    """
    # 训练集/测试集拆分：80% 训练 / 20% 测试
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=random_state
    )

    # ------ 模型 1：岭回归（L2 正则化线性回归） ------
    # Ridge 对特征系数加 L2 惩罚 ∑α·w²，防止多共线性导致系数爆炸
    lr = Ridge(alpha=1.0)
    lr.fit(X_train, y_train)
    y_pred_lr = lr.predict(X_test)

    # ------ 模型 2：随机森林 ------
    # n_estimators=100: 100 棵决策树集成（越多越稳，但越慢）
    # max_depth=None:   不限制深度（依赖 min_samples_leaf 防过拟合）
    # min_samples_leaf=10: 每叶至少 10 个样本（控制模型复杂度）
    rf = RandomForestRegressor(
        n_estimators=100, max_depth=None, min_samples_leaf=10, random_state=random_state
    )
    rf.fit(X_train, y_train)
    y_pred_rf = rf.predict(X_test)

    # ------ 计算评估指标 ------
    # MAE：平均绝对误差，与 y 同单位，直观易理解
    # R²：决定系数 0~1，1 为完美预测，负值表示不如直接用均值预测
    lr_mae = mean_absolute_error(y_test, y_pred_lr)
    lr_r2 = r2_score(y_test, y_pred_lr)
    rf_mae = mean_absolute_error(y_test, y_pred_rf)
    rf_r2 = r2_score(y_test, y_pred_rf)

    metrics = {
        "ridge": {"mae": round(float(lr_mae), 2), "r2": round(float(lr_r2), 4)},
        "random_forest": {"mae": round(float(rf_mae), 2), "r2": round(float(rf_r2), 4)},
        "samples": f"{len(X_train)}/{len(X_test)} (train/test)",
    }

    # ------ 特征重要性（随机森林输出） ------
    # feature_importances_ 是每棵树分裂时该特征减少的不纯度总和
    # 数值越高 → 该特征对预测越重要（总和 = 1）
    feature_names = X.columns.tolist() if hasattr(X, 'columns') else []
    importance = sorted(
        zip(feature_names, rf.feature_importances_),
        key=lambda x: x[1], reverse=True
    )

    return metrics, importance, {"lr": lr, "rf": rf}


def predict_future(models, features, hours=24):
    """使用训练好的模型预测未来 N 小时能耗

    Args:
        models:   训练好的模型字典 {"lr": Ridge, "rf": RandomForest}
        features: 特征列名列表
        hours:    预测未来多少小时

    Returns:
        list[dict]: [{"time": "12:00", "lr": 119.5, "rf": 121.3}, ...]
    """
    now = datetime.now()
    predictions = []
    for i in range(hours):
        ts = now + timedelta(hours=i)
        h, wd = ts.hour, ts.weekday()
        # 构建与训练集完全相同的特征向量
        row = pd.DataFrame([{
            "is_daytime": int(8 <= h < 22),
            "is_weekend": int(wd >= 5),
            "hour_sin": np.sin(2 * np.pi * h / 24),
            "hour_cos": np.cos(2 * np.pi * h / 24),
        }])[features]
        pred_lr = float(models["lr"].predict(row)[0])
        pred_rf = float(models["rf"].predict(row)[0])
        predictions.append({
            "time": ts.strftime("%H:00"),
            "lr": round(max(pred_lr, 0), 2),   # 截断负值
            "rf": round(max(pred_rf, 0), 2),
        })
    return predictions


# ======================== 主函数 ========================
if __name__ == "__main__":
    # 命令行参数：python energy_forecast.py [building_id]
    building = sys.argv[1] if len(sys.argv) > 1 else "B001"
    base_power = 150  # B001 基准功率

    print(f"\n{'='*60}")
    print(f"  校园能耗预测模型 — 建筑 {building}")
    print(f"{'='*60}")

    # ---- 1. 加载数据 ----
    print(f"\n[1/5] 加载 MySQL 数据 (最近 60 天)...")
    df = load_data_from_mysql(building)
    print(f"      MySQL 返回 {len(df)} 条原始数据")

    # ---- 2. 数据预处理（均匀采样） ----
    if len(df) > 0:
        before = len(df)
        # 按小时均匀采样：每小时最多 20 条
        df = df.groupby("hour", group_keys=False).apply(
            lambda g: g.sample(n=min(20, len(g)), random_state=42)
        ).reset_index(drop=True)
        print(f"      均匀采样 {len(df)} 条 (原始 {before} 条)")

    # 生成模拟数据并合并
    print(f"      生成 14 天模拟数据...")
    df_synth = generate_synthetic_data(days=14, base_kw=base_power)
    df = pd.concat([df, df_synth], ignore_index=True) if len(df) > 0 else df_synth
    print(f"      合并后共 {len(df)} 条 (真实 + 模拟)")

    # ---- 3. 构建特征 ----
    print(f"\n[2/5] 构建特征 (is_daytime, hour_sin/cos, is_weekend)...")
    df = build_features(df)
    features = ["is_daytime", "hour_sin", "hour_cos", "is_weekend"]
    X = df[features]
    y = df["value"]
    print(f"      特征矩阵: {X.shape}")

    # ---- 4. 训练评估 ----
    print(f"\n[3/5] 训练双模型...")
    metrics, importance, models = train_and_evaluate(X, y)

    print(f"\n{'─'*40}")
    print(f"  RIDGE 回归 ")
    print(f"    MAE  = {metrics['ridge']['mae']} kW")
    print(f"    R²   = {metrics['ridge']['r2']}")
    print(f"  RANDOM FOREST")
    print(f"    MAE  = {metrics['random_forest']['mae']} kW")
    print(f"    R²   = {metrics['random_forest']['r2']}")
    print(f"  样本   = {metrics['samples']}")

    # ---- 5. 特征重要性 ----
    print(f"\n[4/5] 特征重要性（随机森林输出）:")
    feature_names_cn = {
        "is_daytime": "是否白天", "hour_sin": "小时正弦",
        "hour_cos": "小时余弦", "is_weekend": "是否周末",
    }
    for name, imp in importance:
        bar = "█" * int(imp * 50)
        print(f"  {feature_names_cn.get(name, name):<8}  {imp:.2%}  {bar}")

    # ---- 6. 预测未来 24 小时 ----
    print(f"\n[5/5] 预测未来 24 小时能耗:")
    fc = predict_future(models, features, hours=24)
    print(f"  {'时间':<8} {'岭回归':>8} {'随机森林':>8}")
    print(f"  {'─'*28}")
    for p in fc:
        print(f"  {p['time']:<8} {p['lr']:>8.1f} {p['rf']:>8.1f}")
    print(f"\n{'='*60}\n")
