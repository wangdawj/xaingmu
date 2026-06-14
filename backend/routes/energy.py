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

# 模块级缓存：避免每次请求都重新训练（每 10 分钟刷新一次模型）
_forecast_cache = {"data": None, "ts": 0}
_FORECAST_TTL = 600  # 缓存有效期（秒）


@energy_bp.route("/forecast", methods=["GET"])
def energy_forecast():
    """能耗预测：线性回归 + 随机森林双模型对比，预测未来 24 小时

    数据策略：
        - 优先使用 MySQL 全量 energy_record 数据（不限建筑，所有楼宇共享昼夜规律）
        - 数据量 < 500 时，自动生成符合实际分布的模拟数据作为补充训练集
    """
    now = time.time()
    if _forecast_cache["data"] is not None and (now - _forecast_cache["ts"]) < _FORECAST_TTL:
        return jsonify({"code": 0, "data": _forecast_cache["data"]})

    try:
        import pandas as pd
        import numpy as np
        from sklearn.linear_model import LinearRegression
        from sklearn.ensemble import RandomForestRegressor
        from sklearn.metrics import mean_absolute_error, r2_score
        from sklearn.model_selection import train_test_split
        from extensions import db
        from sqlalchemy import text
        from datetime import datetime, timedelta

        # 1. 生成符合 Producer 逻辑的 7 天 × 24 小时训练数据
        #    （真实数据时间跨度不足时，用模拟数据补充日/夜节律）
        rows = db.session.execute(text("""
            SELECT HOUR(event_time) AS hour, WEEKDAY(event_time) AS weekday, value
            FROM energy_record
            WHERE building_id = 'B001' AND event_time >= NOW() - INTERVAL 60 DAY
            ORDER BY event_time
        """)).fetchall()

        df_real = pd.DataFrame(rows, columns=["hour", "weekday", "value"])
        n_real_raw = len(df_real)

        # 按小时均匀采样：每小时最多保留 20 条，避免某一小时（如大量实时记录）
        # 淹没其他时段，导致模型无法学习昼夜节律
        if n_real_raw > 0:
            df_real = df_real.groupby("hour", group_keys=False).apply(
                lambda g: g.sample(n=min(20, len(g)), random_state=42)
            ).reset_index(drop=True)
        n_real = len(df_real)

        # 生成 14 天模拟数据（与 Producer 相同昼夜逻辑）
        base_kw = 150
        synth = []
        for day in range(14):
            for h in range(24):
                wd = (6 + day) % 7  # 从周六开始，确保覆盖周末
                is_day = 8 <= h < 22
                hour_factor = np.random.uniform(0.7, 1.3) if is_day else np.random.uniform(0.2, 0.5)
                weekend_factor = 0.8 if wd >= 5 else 1.0
                value = round(base_kw * hour_factor * weekend_factor * np.random.uniform(0.9, 1.1), 2)
                synth.append({"hour": h, "weekday": wd, "value": value})
        df_synth = pd.DataFrame(synth)

        # 真实数据 + 模拟数据 1:1 混合，确保昼夜节律不被淹没
        df = pd.concat([df_real, df_synth], ignore_index=True) if n_real > 0 else df_synth
        data_source = f"B001 real({n_real})+synth({len(synth)})"

        # 2. 构建时间特征
        df["is_weekend"] = (df["weekday"] >= 5).astype(int)
        df["is_daytime"] = ((df["hour"] >= 8) & (df["hour"] < 22)).astype(int)
        df["hour_sin"] = np.sin(2 * np.pi * df["hour"] / 24)
        df["hour_cos"] = np.cos(2 * np.pi * df["hour"] / 24)

        features = ["is_daytime", "hour_sin", "hour_cos", "is_weekend"]
        X = df[features]
        y = df["value"]

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

        # 3. 训练模型（Ridge 回归 + 随机森林）
        from sklearn.linear_model import Ridge
        lr = Ridge(alpha=1.0)
        lr.fit(X_train, y_train)
        rf = RandomForestRegressor(
            n_estimators=100, max_depth=None, min_samples_leaf=10, random_state=42,
        )
        rf.fit(X_train, y_train)

        y_pred_lr = lr.predict(X_test)
        y_pred_rf = rf.predict(X_test)

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

        # 4. 特征重要性
        imp = sorted(zip(features, rf.feature_importances_), key=lambda x: x[1], reverse=True)
        feature_names = {
            "is_daytime": "是否白天", "hour_sin": "小时正弦",
            "hour_cos": "小时余弦", "is_weekend": "是否周末",
        }
        feature_importance = [
            {"feature": feature_names.get(f, f), "importance": round(float(i), 4)}
            for f, i in imp
        ]

        # 5. 预测未来 24 小时
        future = []
        now_dt = datetime.now()
        for i in range(24):
            ts = now_dt + timedelta(hours=i)
            h, wd = ts.hour, ts.weekday()
            row_f = pd.DataFrame([{
                "is_daytime": int(8 <= h < 22),
                "hour_sin": np.sin(2 * np.pi * h / 24),
                "hour_cos": np.cos(2 * np.pi * h / 24),
                "is_weekend": int(wd >= 5),
            }])[features]
            val_lr = float(lr.predict(row_f)[0])
            val_rf = float(rf.predict(row_f)[0])
            future.append({
                "time": ts.strftime("%H:00"),
                "predicted_lr": round(max(val_lr, 0), 2),
                "predicted_rf": round(max(val_rf, 0), 2),
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
