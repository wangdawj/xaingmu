"""
能耗管理 API 路由模块
=================
提供校园能耗监测平台的核心 RESTful API：
- 建筑列表 / 详情 / 实时状态
- 能耗趋势 / 对比 / 峰谷 / 热力图
- 告警统计 / 节能建议 / 数据质量日志
- SSE 实时推送建筑状态
"""

import time
import json
from flask import Blueprint, jsonify, request, Response, stream_with_context, current_app
from models import Building, AlertRecord, EnergySavingAdvice, DataQualityLog
from services.influx_service import EnergyQueryService

# 创建能耗蓝图，所有路由以 /api/energy 为前缀
energy_bp = Blueprint("energy", __name__, url_prefix="/api/energy")


def _svc():
    """获取能耗数据查询服务实例"""
    return EnergyQueryService(current_app.config)


# ======================== 建筑信息接口 ========================

@energy_bp.route("/buildings", methods=["GET"])
def list_buildings():
    """获取所有启用状态的建筑列表"""
    buildings = Building.query.filter_by(status=1).all()
    return jsonify([{
        "building_id": b.building_id,
        "building_name": b.building_name,
        "building_type": b.building_type,
        "floor_count": b.floor_count,
        "build_area": float(b.build_area) if b.build_area else 0,
        "region_id": b.region_id,
    } for b in buildings])


@energy_bp.route("/building/<building_id>/detail", methods=["GET"])
def building_detail(building_id):
    """获取单个建筑的详细信息，包含 24h 能耗曲线和汇总统计"""
    building = Building.query.filter_by(building_id=building_id).first()
    if not building:
        return jsonify({"code": 1, "msg": "建筑不存在"}), 404

    with _svc() as svc:
        curve = svc.query_trend(hours=24, building_id=building_id)

    return jsonify({"code": 0, "data": {
        "building_id": building.building_id,
        "building_name": building.building_name,
        "building_type": building.building_type,
        "floor_count": building.floor_count,
        "build_area": float(building.build_area) if building.build_area else 0,
        "max_occupancy": building.max_occupancy,
        "open_time": building.open_time.isoformat() if building.open_time else None,
        "close_time": building.close_time.isoformat() if building.close_time else None,
        "curve": curve,
        "summary": {
            "total": round(sum(c.get("value", 0) for c in curve), 2),
            "peak": round(max((c.get("value", 0) for c in curve), default=0), 2),
            "avg": round(sum(c.get("value", 0) for c in curve) / len(curve) if curve else 0, 2),
            "record_count": len(curve),
        }
    }})


@energy_bp.route("/buildings/status", methods=["GET"])
def buildings_status():
    """校园拓扑图：获取所有建筑实时运行状态（含分类颜色标记）"""
    buildings = Building.query.filter_by(status=1).all()
    with _svc() as svc:
        result = []
        for b in buildings:
            # 取最近 1 小时数据，最新一条作为当前功率
            curve = svc.query_trend(hours=1, building_id=b.building_id)
            current = curve[-1]["value"] if curve else 0
            cat, color = EnergyQueryService.classify_building(b.building_type)
            result.append({
                "building_id": b.building_id,
                "building_name": b.building_name,
                "building_type": b.building_type,
                "category": cat,
                "color": color,
                "current_power": round(current, 2),
                # 功率阈值分级：<200 正常，<300 预警，>=300 告警
                "status": "normal" if current < 200 else ("warning" if current < 300 else "critical"),
            })
    return jsonify({"code": 0, "data": result})


# ======================== 能耗分析接口 ========================

@energy_bp.route("/trend", methods=["GET"])
def energy_trend():
    """能耗趋势数据：按小时聚合的能耗曲线"""
    hours = request.args.get("hours", 24, type=int)
    building_id = request.args.get("building_id")
    with _svc() as svc:
        data = svc.query_trend(hours=hours, building_id=building_id)
    return jsonify({"code": 0, "data": data})


@energy_bp.route("/comparison", methods=["GET"])
def building_comparison():
    """楼宇能耗对比：各建筑在指定时间窗内的总能耗排名"""
    hours = request.args.get("hours", 24, type=int)
    building_map = {b.building_id: b.building_name for b in Building.query.all()}
    with _svc() as svc:
        data = svc.query_building_comparison(hours=hours)
    # 补充建筑中文名称
    for item in data:
        item["building_name"] = building_map.get(item["building_id"], item["building_id"])
    return jsonify({"code": 0, "data": data})


@energy_bp.route("/peak-valley", methods=["GET"])
def peak_valley():
    """峰谷用电分析：峰时段(8-22点) vs 谷时段(22-次日8点)"""
    hours = request.args.get("hours", 24, type=int)
    with _svc() as svc:
        data = svc.query_peak_valley(hours=hours)
    return jsonify({"code": 0, "data": data})


@energy_bp.route("/heatmap", methods=["GET"])
def heatmap():
    """校区能耗热力图：按区域和建筑维度的能耗分布矩阵"""
    hours = request.args.get("hours", 24, type=int)
    with _svc() as svc:
        data = svc.query_heatmap(hours=hours)
    return jsonify({"code": 0, "data": data})


# ======================== 建筑子项分析接口 ========================

@energy_bp.route("/building/<building_id>/sub-items", methods=["GET"])
def building_sub_items(building_id):
    """分项能耗：按照明/空调/插座拆分建筑用能结构"""
    hours = request.args.get("hours", 24, type=int)
    with _svc() as svc:
        sub_items = svc.query_sub_items(building_id=building_id, hours=hours)
    item_labels = {"lighting": "照明", "ac": "空调", "outlet": "插座"}
    data = [{"type": k, "label": item_labels.get(k, k), "value": v} for k, v in sub_items.items()]
    return jsonify({"code": 0, "data": data})


@energy_bp.route("/building/<building_id>/comparison", methods=["GET"])
def building_historical_comparison(building_id):
    """历史环比：今日 vs 昨日、本周 vs 上周的能耗变化率"""
    with _svc() as svc:
        comp = svc.query_historical_comparison(building_id=building_id)

    def pct(a, b):
        """计算百分比变化，b 为 0 时返回 None"""
        if not b:
            return None
        return round((a - b) / b * 100, 1)

    comp["day_change"] = pct(comp["today"], comp["yesterday"])
    comp["week_change"] = pct(comp["this_week"], comp["last_week"])
    return jsonify({"code": 0, "data": comp})


# ======================== 告警 & 建议接口 ========================

@energy_bp.route("/alerts", methods=["GET"])
def alert_stats():
    """告警统计：最近告警记录及按严重级别的数量分布"""
    status = request.args.get("status")
    query = AlertRecord.query
    if status:
        query = query.filter_by(status=status)
    total_count = query.count()

    # 全量统计各级别告警数量（不受 limit 影响）
    from sqlalchemy import func
    severity_rows = query.with_entities(
        AlertRecord.severity, func.count(AlertRecord.alert_id)
    ).group_by(AlertRecord.severity).all()
    severity_count = {"info": 0, "warning": 0, "critical": 0}
    for sev, cnt in severity_rows:
        if sev in severity_count:
            severity_count[sev] = cnt

    records = query.order_by(AlertRecord.triggered_at.desc()).limit(100).all()

    return jsonify({
        "code": 0,
        "data": {
            "total_count": total_count,
            "severity_count": severity_count,
            "records": [{
                "alert_id": r.alert_id,
                "building_id": r.building_id,
                "severity": r.severity,
                "message": r.message,
                "alert_value": float(r.alert_value) if r.alert_value else 0,
                "status": r.status,
                "triggered_at": r.triggered_at.isoformat() if r.triggered_at else None,
            } for r in records],
        },
    })


@energy_bp.route("/advice", methods=["GET"])
def saving_advice():
    """节能建议列表：支持按建筑ID过滤，按优先级降序排列"""
    building_id = request.args.get("building_id")
    query = EnergySavingAdvice.query
    if building_id:
        query = query.filter_by(building_id=building_id)
    advice_list = query.order_by(EnergySavingAdvice.priority.desc()).all()
    return jsonify({"code": 0, "data": [{
        "advice_id": a.advice_id,
        "building_id": a.building_id,
        "building_type": a.building_type,
        "title": a.title,
        "content": a.content,
        "priority": a.priority,
        "estimated_save": float(a.estimated_save) if a.estimated_save else 0,
    } for a in advice_list]})


# ======================== 数据质量接口 ========================

@energy_bp.route("/quality/logs", methods=["GET"])
def quality_logs():
    """数据质量巡检日志：最近 50 条质量检查记录"""
    logs = DataQualityLog.query.order_by(DataQualityLog.check_time.desc()).limit(50).all()
    return jsonify({"code": 0, "data": [{
        "log_id": l.log_id,
        "check_time": l.check_time.isoformat() if l.check_time else None,
        "data_source": l.data_source,
        "check_type": l.check_type,
        "issue_count": l.issue_count,
        "status": l.status,
        "detail": l.detail,
    } for l in logs]})


# ======================== 仪表盘聚合接口 ========================

@energy_bp.route("/dashboard-stats", methods=["GET"])
def dashboard_stats():
    """仪表盘首页统计卡片：总能耗、运行建筑数、告警数、碳减排"""
    hours = request.args.get("hours", 24, type=int)
    with _svc() as svc:
        comparison = svc.query_building_comparison(hours=hours)
    buildings = Building.query.filter_by(status=1).all()
    alerts = AlertRecord.query.filter_by(status="open").all()

    severity_count = {"info": 0, "warning": 0, "critical": 0}
    for r in alerts:
        if r.severity in severity_count:
            severity_count[r.severity] += 1

    total_energy = sum(c["total"] for c in comparison)
    alert_count = sum(severity_count.values())
    return jsonify({"code": 0, "data": {
        "total_energy": round(total_energy, 2),
        "building_count": len(buildings),
        "alert_count": alert_count,
        # 碳减排估算系数：1 kWh ≈ 0.72 kgCO₂（中国电网平均排放因子）
        "carbon_reduce": round(total_energy * 0.72, 2),
        "comparison": comparison,
    }})


# ======================== SSE 实时推送 ========================

@energy_bp.route("/buildings/stream", methods=["GET"])
def buildings_stream():
    """SSE (Server-Sent Events) 实时推送建筑状态，每 5 秒刷新一次"""
    def event_stream():
        while True:
            buildings = Building.query.filter_by(status=1).all()
            with _svc() as svc:
                data = []
                for b in buildings:
                    curve = svc.query_trend(hours=1, building_id=b.building_id)
                    current = curve[-1]["value"] if curve else 0
                    data.append({
                        "building_id": b.building_id,
                        "building_name": b.building_name,
                        "building_type": b.building_type,
                        "current_power": round(current, 2),
                        "status": "normal" if current < 200 else ("warning" if current < 300 else "critical"),
                    })
            yield f"data: {json.dumps({'code':0,'data':data}, ensure_ascii=False)}\n\n"
            time.sleep(5)

    return Response(
        stream_with_context(event_stream()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",       # 禁用 Nginx 缓冲，确保实时推送
            "Connection": "keep-alive",
        }
    )


# ======================== 能耗预测接口 ========================
#
# 【接口设计说明】
#   GET /api/energy/forecast
#   返回 JSON: { code, data: { metrics, feature_importance, forecast } }
#
# 【模型架构】
#   双模型对比方案：
#     1. Ridge 回归（L2 正则化线性回归，alpha=1.0）
#        - 优点：训练快、可解释性强，L2 正则化解决多共线性
#        - 对比普通线性回归：系数不会爆炸（如遇到高度相关特征时）
#     2. 随机森林（100 棵树，不限深度，每叶至少 10 样本）
#        - 优点：捕捉非线性关系，输出特征重要性
#        - max_depth=None 不限制深度（依赖 min_samples_leaf 防过拟合）
#
# 【特征工程】
#   is_daytime: 是否白天(8-21点)，布尔值 → 最关键特征（importance ~89%）
#   hour_sin/hou_cos: 小时的正弦/余弦循环编码
#      - 为什么用 sin/cos 而不用原始 0-23？
#        避免数值断层：23 点和 0 点在数字上差 23，实际上只差 1 小时
#        sin/cos 把小时映射回单位圆，23点和0点在圆上是连续的
#   is_weekend: 是否周末
#
# 【数据策略】
#   1. 从 MySQL 拉取 B001 最近 60 天数据
#   2. groupby("hour").sample(n=20)：每小时均匀采样，防止某一小时垄断训练集
#   3. 生成 14 天模拟数据（与 Producer 同逻辑），1:1 混合
#   4. train_test_split(test_size=0.2)：80% 训练，20% 评估
#
# 【缓存机制】
#   _forecast_cache: { data, ts }
#   TTL = 600 秒（10 分钟）
#   避免每次请求都重新训练模型（训练一次约需 1-2 秒）

# 模块级缓存：避免每次请求都重新训练（每 10 分钟刷新一次模型）
_forecast_cache = {"data": None, "ts": 0}
_FORECAST_TTL = 600  # 缓存有效期（秒）


@energy_bp.route("/forecast", methods=["GET"])
def energy_forecast():
    """能耗预测接口：训练 Ridge + 随机森林双模型，预测未来 24 小时"""
    now = time.time()
    # 缓存命中：直接返回上次训练结果
    if _forecast_cache["data"] is not None and (now - _forecast_cache["ts"]) < _FORECAST_TTL:
        return jsonify({"code": 0, "data": _forecast_cache["data"]})

    try:
        import pandas as pd
        import numpy as np
        from sklearn.linear_model import Ridge  # L2 正则化线性回归
        from sklearn.ensemble import RandomForestRegressor
        from sklearn.metrics import mean_absolute_error, r2_score
        from sklearn.model_selection import train_test_split
        from extensions import db
        from sqlalchemy import text
        from datetime import datetime, timedelta

        # ================================================================
        # 步骤 1：加载真实数据（B001 最近 60 天）
        # ================================================================
        # 只取 B001 而非全建筑：跨建筑功率差异大（70~200kW），混合后
        # 方差淹没昼夜规律，模型学不到有效模式
        rows = db.session.execute(text("""
            SELECT
                HOUR(event_time) AS hour,       -- 采样小时(0-23)
                WEEKDAY(event_time) AS weekday, -- 星期几(0=周一)
                value                           -- 功率值(kW)
            FROM energy_record
            WHERE building_id = 'B001'           -- 单建筑训练
              AND event_time >= NOW() - INTERVAL 60 DAY
            ORDER BY event_time
        """)).fetchall()

        df_real = pd.DataFrame(rows, columns=["hour", "weekday", "value"])
        n_real_raw = len(df_real)

        # ---- 关键：按小时均匀采样 ----
        # 问题：Producer 刚启动时，所有数据集中在当前小时（如 11 点）
        #      假设 3500 条数据中 99% 是 hour=11，模型只能学会"全是一个值"
        # 解决：groupby("hour") → 每小时最多保留 20 条
        #      这样即使 11 点有 3000 条，也只保留 20 条与其他小时均衡
        if n_real_raw > 0:
            df_real = df_real.groupby("hour", group_keys=False).apply(
                lambda g: g.sample(n=min(20, len(g)), random_state=42)
            ).reset_index(drop=True)
        n_real = len(df_real)

        # ================================================================
        # 步骤 2：生成 14 天模拟数据（补齐昼夜节律）
        # ================================================================
        # 为什么需要模拟数据？
        #   真实数据时间跨度不足（可能只有几个小时的覆盖度）
        #   模拟数据确保 24 小时 × 14 天 的完备昼夜样本
        #
        # 生成逻辑与 Kafka Producer 完全一致：
        #   - 基准功率 150kW（B001 的 base_kw）
        #   - 白天 0.7~1.3 倍，夜间 0.2~0.5 倍
        #   - 周末降低 20%
        #   - ±10% 随机噪声
        base_kw = 150  # B001 基准功率
        synth = []
        for day in range(14):                          # 覆盖 14 天（2 个完整周）
            for h in range(24):                        # 每天 24 个整点
                wd = (6 + day) % 7                     # 从周六开始，确保覆盖周末
                is_day = 8 <= h < 22                   # 是否白天
                # 昼夜系数：白天 0.7~1.3，夜间 0.2~0.5
                hour_factor = np.random.uniform(0.7, 1.3) if is_day else np.random.uniform(0.2, 0.5)
                weekend_factor = 0.8 if wd >= 5 else 1.0  # 周末降 20%
                # 最终功率 = 基准 × 昼夜 × 周末 × 噪声
                value = round(base_kw * hour_factor * weekend_factor * np.random.uniform(0.9, 1.1), 2)
                synth.append({"hour": h, "weekday": wd, "value": value})
        df_synth = pd.DataFrame(synth)

        # 1:1 混合真实数据和模拟数据
        # 不放大真实数据权重（之前 ×3 导致真实数据淹没模拟数据）
        df = pd.concat([df_real, df_synth], ignore_index=True) if n_real > 0 else df_synth
        data_source = f"B001 real({n_real})+synth({len(synth)})"

        # ================================================================
        # 步骤 3：构建特征
        # ================================================================
        # is_weekend: 布尔值，(weekday >= 5) → 周六日
        df["is_weekend"] = (df["weekday"] >= 5).astype(int)
        # is_daytime: 布尔值，(8 <= hour < 22) → 白天
        df["is_daytime"] = ((df["hour"] >= 8) & (df["hour"] < 22)).astype(int)
        # hour_sin / hour_cos: 循环时间编码
        # 为什么不用 hour 原始值？因为 23 点和 0 点数值差 23，
        # 但实际上只差 1 小时。sin/cos 把小时映射到单位圆上做连续编码
        # 24 小时 = 360° = 2π，h / 24 归一化后 × 2π
        df["hour_sin"] = np.sin(2 * np.pi * df["hour"] / 24)
        df["hour_cos"] = np.cos(2 * np.pi * df["hour"] / 24)

        # 特征列：只用 4 个时间特征
        # 不用 building_id（单建筑训练，且 one-hot 会吞掉时间特征重要性）
        features = ["is_daytime", "hour_sin", "hour_cos", "is_weekend"]
        X = df[features]
        y = df["value"]

        # 80% 训练集 / 20% 测试集
        # random_state=42 保证每次切分一致（可复现）
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )

        # ================================================================
        # 步骤 4：训练模型
        # ================================================================
        # Ridge(L2 正则化)：对特征权重加惩罚，避免多共线性导致系数爆炸
        # alpha=1.0 是正则化强度，越大 → 系数越趋于 0 → 模型越稳但可能欠拟合
        lr = Ridge(alpha=1.0)
        lr.fit(X_train, y_train)

        # 随机森林：100 棵树集成
        # max_depth=None：不限制树深度（让每棵树充分生长）
        # min_samples_leaf=10：每片叶子至少 10 个样本 → 防止过拟合
        # random_state=42：固定随机种子，保证可复现
        rf = RandomForestRegressor(
            n_estimators=100, max_depth=None, min_samples_leaf=10, random_state=42,
        )
        rf.fit(X_train, y_train)

        # ---- 测试集预测 & 评估 ----
        y_pred_lr = lr.predict(X_test)
        y_pred_rf = rf.predict(X_test)

        # MAE (Mean Absolute Error)：平均绝对误差，单位与 y 一致(kW)，越小越好
        # R² (R-squared)：决定系数 0~1，越接近 1 拟合越好
        metrics = {
            "ridge_regression": {
                "mae": round(float(mean_absolute_error(y_test, y_pred_lr)), 2),
                "r2": round(float(r2_score(y_test, y_pred_lr)), 4),
            },
            "random_forest": {
                "mae": round(float(mean_absolute_error(y_test, y_pred_rf)), 2),
                "r2": round(float(r2_score(y_test, y_pred_rf)), 4),
            },
            "train_samples": len(X_train),
            "test_samples": len(X_test),
            "data_source": data_source,
        }

        # ================================================================
        # 步骤 5：特征重要性（随机森林输出）
        # ================================================================
        # rf.feature_importances_ 返回每个特征对预测的贡献度（总和 = 1）
        # 按重要性降序排列
        imp = sorted(
            zip(features, rf.feature_importances_), key=lambda x: x[1], reverse=True
        )
        # 特征名中文化映射
        feature_names = {
            "is_daytime": "是否白天", "hour_sin": "小时正弦",
            "hour_cos": "小时余弦", "is_weekend": "是否周末",
        }
        feature_importance = [
            {"feature": feature_names.get(f, f), "importance": round(float(i), 4)}
            for f, i in imp
        ]

        # ================================================================
        # 步骤 6：预测未来 24 小时
        # ================================================================
        # 从当前时间起，逐小时预测未来 24 个点的能耗值
        future = []
        now_dt = datetime.now()
        for i in range(24):
            ts = now_dt + timedelta(hours=i)  # 未来第 i 小时的时间
            h, wd = ts.hour, ts.weekday()     # 该时间的小时和星期几
            # 构建与训练集相同的特征向量
            row_f = pd.DataFrame([{
                "is_daytime": int(8 <= h < 22),               # 是否白天
                "hour_sin": np.sin(2 * np.pi * h / 24),        # 小时正弦编码
                "hour_cos": np.cos(2 * np.pi * h / 24),        # 小时余弦编码
                "is_weekend": int(wd >= 5),                    # 是否周末
            }])[features]
            # 两个模型分别预测
            val_lr = float(lr.predict(row_f)[0])
            val_rf = float(rf.predict(row_f)[0])
            # 截断负值：线性回归可能在夜间外推到负数（max 保证 ≥ 0）
            future.append({
                "time": ts.strftime("%H:00"),          # 时间标签：如 "12:00"
                "predicted_lr": round(max(val_lr, 0), 2),  # 岭回归预测
                "predicted_rf": round(max(val_rf, 0), 2),  # 随机森林预测
            })

        result = {
            "metrics": metrics,
            "feature_importance": feature_importance,
            "forecast": future,
        }
        _forecast_cache["data"] = result
        _forecast_cache["ts"] = now
        return jsonify({"code": 0, "data": result})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"code": -1, "message": f"模型预测失败: {str(e)}"}), 500


# ======================== 告警 SSE 实时推送 ========================

@energy_bp.route("/alerts/stream", methods=["GET"])
def alerts_stream():
    """SSE 实时推送最新告警，每 2 秒检查一次新告警"""
    last_alert_id = 0  # 记录上次推送的最大 alert_id

    def event_stream():
        nonlocal last_alert_id
        while True:
            new_alerts = AlertRecord.query \
                .filter(AlertRecord.alert_id > last_alert_id) \
                .order_by(AlertRecord.alert_id.asc()).all()
            if new_alerts:
                last_alert_id = new_alerts[-1].alert_id
                data = [{
                    "alert_id": r.alert_id,
                    "building_id": r.building_id,
                    "severity": r.severity,
                    "message": r.message,
                    "alert_value": float(r.alert_value) if r.alert_value else 0,
                    "status": r.status,
                    "triggered_at": r.triggered_at.isoformat() if r.triggered_at else None,
                } for r in new_alerts]
                yield f"data: {json.dumps({'code':0,'data':data}, ensure_ascii=False)}\n\n"
            time.sleep(2)

    return Response(
        stream_with_context(event_stream()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        }
    )
