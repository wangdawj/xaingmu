import time
import json
from flask import Blueprint, jsonify, request, Response, stream_with_context
from models import Building, AlertRecord, EnergySavingAdvice, DataQualityLog
from services.influx_service import InfluxService

energy_bp = Blueprint("energy", __name__, url_prefix="/api/energy")


@energy_bp.route("/buildings", methods=["GET"])
def list_buildings():
    buildings = Building.query.filter_by(status=1).all()
    return jsonify([{
        "building_id": b.building_id,
        "building_name": b.building_name,
        "building_type": b.building_type,
        "floor_count": b.floor_count,
        "build_area": float(b.build_area) if b.build_area else 0,
        "region_id": b.region_id,
    } for b in buildings])


@energy_bp.route("/trend", methods=["GET"])
def energy_trend():
    hours = request.args.get("hours", 24, type=int)
    building_id = request.args.get("building_id")
    svc = InfluxService()
    try:
        data = svc.query_trend(hours=hours, building_id=building_id)
        return jsonify({"code": 0, "data": data})
    finally:
        svc.close()


@energy_bp.route("/comparison", methods=["GET"])
def building_comparison():
    hours = request.args.get("hours", 24, type=int)
    svc = InfluxService()
    try:
        data = svc.query_building_comparison(hours=hours)
        building_map = {b.building_id: b.building_name for b in Building.query.all()}
        for item in data:
            item["building_name"] = building_map.get(item["building_id"], item["building_id"])
        return jsonify({"code": 0, "data": data})
    finally:
        svc.close()


@energy_bp.route("/peak-valley", methods=["GET"])
def peak_valley():
    hours = request.args.get("hours", 24, type=int)
    svc = InfluxService()
    try:
        return jsonify({"code": 0, "data": svc.query_peak_valley(hours=hours)})
    finally:
        svc.close()


@energy_bp.route("/heatmap", methods=["GET"])
def heatmap():
    hours = request.args.get("hours", 24, type=int)
    svc = InfluxService()
    try:
        return jsonify({"code": 0, "data": svc.query_heatmap(hours=hours)})
    finally:
        svc.close()


@energy_bp.route("/alerts", methods=["GET"])
def alert_stats():
    status = request.args.get("status")
    query = AlertRecord.query
    if status:
        query = query.filter_by(status=status)
    records = query.order_by(AlertRecord.triggered_at.desc()).limit(100).all()
    severity_count = {"info": 0, "warning": 0, "critical": 0}
    for r in records:
        if r.severity in severity_count:
            severity_count[r.severity] += 1
    return jsonify({
        "code": 0,
        "data": {
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


@energy_bp.route("/quality/logs", methods=["GET"])
def quality_logs():
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


@energy_bp.route("/building/<building_id>/detail", methods=["GET"])
def building_detail(building_id):
    """建筑详情：基本信息 + 24h 用电曲线"""
    building = Building.query.filter_by(building_id=building_id).first()
    if not building:
        return jsonify({"code": 1, "msg": "建筑不存在"}), 404

    svc = InfluxService()
    try:
        curve = svc.query_trend(hours=24, building_id=building_id)
    finally:
        svc.close()

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
    """校园拓扑图：所有建筑实时状态"""
    buildings = Building.query.filter_by(status=1).all()
    svc = InfluxService()
    try:
        result = []
        for b in buildings:
            curve = svc.query_trend(hours=1, building_id=b.building_id)
            current = curve[-1]["value"] if curve else 0
            building_map = {
                "教学": ("academic", "#1890ff"),
                "办公": ("office", "#52c41a"),
                "宿舍": ("dormitory", "#fa8c16"),
                "食堂": ("canteen", "#f5222d"),
                "图书馆": ("library", "#722ed1"),
            }
            btype_bg = b.building_type[:2] if len(b.building_type) >= 2 else b.building_type
            cat, color = "default", "#909399"
            for key, val in building_map.items():
                if key in b.building_type:
                    cat, color = val
                    break
            result.append({
                "building_id": b.building_id,
                "building_name": b.building_name,
                "building_type": b.building_type,
                "category": cat,
                "color": color,
                "current_power": round(current, 2),
                "status": "normal" if current < 200 else ("warning" if current < 300 else "critical"),
            })
        return jsonify({"code": 0, "data": result})
    finally:
        svc.close()


@energy_bp.route("/building/<building_id>/sub-items", methods=["GET"])
def building_sub_items(building_id):
    """建筑分项能耗（照明/空调/插座）"""
    hours = request.args.get("hours", 24, type=int)
    svc = InfluxService()
    try:
        sub_items = svc.query_sub_items(building_id=building_id, hours=hours)
        item_labels = {"lighting": "照明", "ac": "空调", "outlet": "插座"}
        data = [{"type": k, "label": item_labels.get(k, k), "value": v} for k, v in sub_items.items()]
        return jsonify({"code": 0, "data": data})
    finally:
        svc.close()


@energy_bp.route("/building/<building_id>/comparison", methods=["GET"])
def building_historical_comparison(building_id):
    """建筑历史环比（今日/昨日/本周/上周）"""
    svc = InfluxService()
    try:
        comp = svc.query_historical_comparison(building_id=building_id)
        # 计算环比变化百分比
        def pct(a, b):
            if not b:
                return None
            return round((a - b) / b * 100, 1)

        comp["day_change"] = pct(comp["today"], comp["yesterday"])
        comp["week_change"] = pct(comp["this_week"], comp["last_week"])
        return jsonify({"code": 0, "data": comp})
    finally:
        svc.close()


@energy_bp.route("/trend/range", methods=["GET"])
def energy_trend_range():
    """支持时间范围参数的趋势查询"""
    hours = request.args.get("hours", 24, type=int)
    building_id = request.args.get("building_id")
    svc = InfluxService()
    try:
        data = svc.query_trend(hours=hours, building_id=building_id)
        return jsonify({"code": 0, "data": data})
    finally:
        svc.close()


@energy_bp.route("/dashboard-stats", methods=["GET"])
def dashboard_stats():
    """仪表盘统计（支持时间范围）"""
    hours = request.args.get("hours", 24, type=int)
    svc = InfluxService()
    try:
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
            "carbon_reduce": round(total_energy * 0.72, 2),
            "comparison": comparison,
        }})
    finally:
        svc.close()


@energy_bp.route("/buildings/stream", methods=["GET"])
def buildings_stream():
    """SSE 实时推送建筑状态"""
    def event_stream():
        while True:
            buildings = Building.query.filter_by(status=1).all()
            svc = InfluxService()
            try:
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
            finally:
                svc.close()
            yield f"data: {json.dumps({'code':0,'data':data}, ensure_ascii=False)}\n\n"
            time.sleep(5)

    return Response(
        stream_with_context(event_stream()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        }
    )
