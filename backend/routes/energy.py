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
    records = query.order_by(AlertRecord.triggered_at.desc()).limit(100).all()

    # 统计各级别告警数量
    severity_count = {"info": 0, "warning": 0, "critical": 0}
    for r in records:
        if r.severity in severity_count:
            severity_count[r.severity] += 1

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
