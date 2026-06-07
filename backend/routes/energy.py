from flask import Blueprint, jsonify, request
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
