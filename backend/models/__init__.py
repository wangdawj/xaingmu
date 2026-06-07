from datetime import datetime
from extensions import db


class Building(db.Model):
    __tablename__ = "building"
    building_id = db.Column(db.String(32), primary_key=True)
    building_name = db.Column(db.String(100), nullable=False)
    building_type = db.Column(db.String(20), nullable=False)
    floor_count = db.Column(db.Integer, default=1)
    build_area = db.Column(db.Numeric(12, 2))
    open_time = db.Column(db.Time)
    close_time = db.Column(db.Time)
    max_occupancy = db.Column(db.Integer, default=0)
    region_id = db.Column(db.String(32))
    status = db.Column(db.Integer, default=1)


class AlertRecord(db.Model):
    __tablename__ = "alert_record"
    alert_id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    rule_id = db.Column(db.Integer)
    building_id = db.Column(db.String(32))
    meter_id = db.Column(db.String(32))
    energy_type = db.Column(db.String(32))
    alert_value = db.Column(db.Numeric(12, 4))
    threshold = db.Column(db.Numeric(12, 4))
    severity = db.Column(db.String(20))
    message = db.Column(db.String(500))
    status = db.Column(db.String(20), default="open")
    triggered_at = db.Column(db.DateTime, default=datetime.utcnow)
    resolved_at = db.Column(db.DateTime)


class EnergySavingAdvice(db.Model):
    __tablename__ = "energy_saving_advice"
    advice_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    building_id = db.Column(db.String(32))
    building_type = db.Column(db.String(50))
    title = db.Column(db.String(200))
    content = db.Column(db.Text)
    priority = db.Column(db.String(20))
    estimated_save = db.Column(db.Numeric(8, 2))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class SysUser(db.Model):
    __tablename__ = "sys_user"
    user_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    real_name = db.Column(db.String(50))
    role = db.Column(db.String(20), default="viewer")
    status = db.Column(db.Integer, default=1)


class DataQualityLog(db.Model):
    __tablename__ = "data_quality_log"
    log_id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    check_time = db.Column(db.DateTime, default=datetime.utcnow)
    data_source = db.Column(db.String(50))
    check_type = db.Column(db.String(50))
    target_table = db.Column(db.String(100))
    issue_count = db.Column(db.Integer, default=0)
    detail = db.Column(db.JSON)
    status = db.Column(db.String(20), default="pass")
