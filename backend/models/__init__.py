"""
数据模型模块
=========
SQLAlchemy ORM 模型定义，映射校园能耗管理系统的 MySQL 数据表。
包含：建筑信息、区域信息、仪表设备、告警规则、告警记录、
      能耗时序数据、分项能耗、日汇总、节能建议、系统用户、数据质量日志。
"""

from datetime import datetime
from extensions import db


# ======================== 基础信息表 ========================

class Region(db.Model):
    """校区区域表"""
    __tablename__ = "region"

    region_id = db.Column(db.String(32), primary_key=True)       # 区域编号（如 R001）
    region_name = db.Column(db.String(100), nullable=False)      # 区域名称
    campus_name = db.Column(db.String(100), nullable=False)      # 所属校区名称
    longitude = db.Column(db.Numeric(10, 6))                     # 经度
    latitude = db.Column(db.Numeric(10, 6))                      # 纬度


class Building(db.Model):
    """建筑信息表 - 存储校园各建筑的基本属性和运营参数"""
    __tablename__ = "building"

    building_id = db.Column(db.String(32), primary_key=True)          # 建筑编号（如 B001）
    building_name = db.Column(db.String(100), nullable=False)         # 建筑名称
    building_type = db.Column(db.String(20), nullable=False)          # 建筑类型（教学/办公/宿舍/食堂/图书馆等）
    floor_count = db.Column(db.Integer, default=1)                    # 楼层数
    build_area = db.Column(db.Numeric(12, 2))                         # 建筑面积（m²）
    open_time = db.Column(db.Time)                                    # 开放时间
    close_time = db.Column(db.Time)                                   # 关闭时间
    max_occupancy = db.Column(db.Integer, default=0)                  # 最大容纳人数
    region_id = db.Column(db.String(32))                              # 所属区域编号
    status = db.Column(db.Integer, default=1)                         # 状态：1=启用，0=停用


class Meter(db.Model):
    """仪表设备信息表"""
    __tablename__ = "meter"

    meter_id = db.Column(db.String(32), primary_key=True)             # 仪表编号
    meter_name = db.Column(db.String(100), nullable=False)            # 仪表名称
    meter_type = db.Column(db.String(20), nullable=False)             # 仪表类型（电表/水表/气表/环境传感器）
    building_id = db.Column(db.String(32), nullable=False)            # 所属建筑编号
    region_id = db.Column(db.String(32), nullable=False)              # 所属区域编号
    install_floor = db.Column(db.Integer)                             # 安装楼层
    protocol = db.Column(db.String(50), default="OPC_UA")             # 通信协议
    status = db.Column(db.Integer, default=1)                         # 状态


# ======================== 告警相关表 ========================

class AlertRule(db.Model):
    """告警规则配置表"""
    __tablename__ = "alert_rule"

    rule_id = db.Column(db.Integer, primary_key=True, autoincrement=True)    # 规则 ID
    rule_name = db.Column(db.String(100), nullable=False)                    # 规则名称
    energy_type = db.Column(db.String(20), nullable=False)                   # 能源类型
    building_id = db.Column(db.String(32))                                   # 目标建筑
    threshold_min = db.Column(db.Numeric(12, 4))                             # 阈值下限
    threshold_max = db.Column(db.Numeric(12, 4))                             # 阈值上限
    duration_sec = db.Column(db.Integer, default=300)                        # 持续秒数触发
    severity = db.Column(db.String(20), default="warning")                   # 严重级别
    enabled = db.Column(db.Integer, default=1)                               # 是否启用


class AlertRecord(db.Model):
    """告警记录表 - 存储能耗异常告警的详细信息"""
    __tablename__ = "alert_record"

    alert_id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)  # 告警 ID
    rule_id = db.Column(db.Integer)                                            # 关联的告警规则 ID
    building_id = db.Column(db.String(32))                                     # 建筑编号
    meter_id = db.Column(db.String(32))                                        # 仪表编号
    energy_type = db.Column(db.String(32))                                     # 能源类型（electricity/water/gas）
    alert_value = db.Column(db.Numeric(12, 4))                                 # 触发告警时的实际值
    threshold = db.Column(db.Numeric(12, 4))                                   # 告警阈值
    severity = db.Column(db.String(20))                                        # 严重级别（info/warning/critical）
    message = db.Column(db.String(500))                                        # 告警描述信息
    status = db.Column(db.String(20), default="open")                          # 处理状态（open/resolved）
    triggered_at = db.Column(db.DateTime, default=datetime.utcnow)             # 触发时间
    resolved_at = db.Column(db.DateTime)                                       # 解决时间


# ======================== 能耗数据表 ========================

class EnergyRecord(db.Model):
    """能耗时序数据表（替代原 InfluxDB electricity_data）"""
    __tablename__ = "energy_record"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    building_id = db.Column(db.String(32), nullable=False)
    region_id = db.Column(db.String(32), nullable=False)
    meter_id = db.Column(db.String(32), nullable=False)
    energy_type = db.Column(db.String(20), default="electricity")
    data_type = db.Column(db.String(20), default="realtime")
    value = db.Column(db.Numeric(12, 2), nullable=False)
    voltage = db.Column(db.Numeric(6, 1), default=0)
    current_val = db.Column(db.Numeric(6, 2), default=0)
    event_time = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class EnergySubRecord(db.Model):
    """分项能耗记录表（照明/空调/插座）"""
    __tablename__ = "energy_sub_record"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    building_id = db.Column(db.String(32), nullable=False)
    sub_type = db.Column(db.String(20), nullable=False)            # lighting/ac/outlet
    value = db.Column(db.Numeric(12, 2), nullable=False)
    event_time = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class EnergyDailySummary(db.Model):
    """日能耗汇总表"""
    __tablename__ = "energy_daily_summary"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    stat_date = db.Column(db.Date, nullable=False)
    building_id = db.Column(db.String(32), nullable=False)
    energy_type = db.Column(db.String(20), nullable=False)
    total_value = db.Column(db.Numeric(14, 4), nullable=False)
    peak_value = db.Column(db.Numeric(12, 4))
    valley_value = db.Column(db.Numeric(12, 4))
    avg_value = db.Column(db.Numeric(12, 4))
    unit = db.Column(db.String(20), default="kWh")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ======================== 业务功能表 ========================

class EnergySavingAdvice(db.Model):
    """节能建议表 - 基于数据分析生成的节能优化建议"""
    __tablename__ = "energy_saving_advice"

    advice_id = db.Column(db.Integer, primary_key=True, autoincrement=True)    # 建议 ID
    building_id = db.Column(db.String(32))                                     # 目标建筑编号
    building_type = db.Column(db.String(50))                                   # 建筑类型
    title = db.Column(db.String(200))                                          # 建议标题
    content = db.Column(db.Text)                                               # 建议详细内容
    priority = db.Column(db.String(20))                                        # 优先级（high/medium/low）
    estimated_save = db.Column(db.Numeric(8, 2))                               # 预估节能比例（%）
    created_at = db.Column(db.DateTime, default=datetime.utcnow)               # 创建时间


class SysUser(db.Model):
    """系统用户表 - 平台用户认证与权限管理"""
    __tablename__ = "sys_user"

    user_id = db.Column(db.Integer, primary_key=True, autoincrement=True)      # 用户 ID
    username = db.Column(db.String(50), unique=True, nullable=False)           # 用户名（唯一）
    password_hash = db.Column(db.String(256), nullable=False)                  # 密码哈希值
    real_name = db.Column(db.String(50))                                       # 真实姓名
    role = db.Column(db.String(20), default="viewer")                          # 角色（admin/operator/viewer）
    status = db.Column(db.Integer, default=1)                                  # 状态：1=正常，0=禁用


class DataQualityLog(db.Model):
    """数据质量日志表 - 记录数据质量巡检结果"""
    __tablename__ = "data_quality_log"

    log_id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)    # 日志 ID
    check_time = db.Column(db.DateTime, default=datetime.utcnow)               # 检查时间
    data_source = db.Column(db.String(50))                                     # 数据源（mysql/kafka）
    check_type = db.Column(db.String(50))                                      # 检查类型（missing/consistency/delay）
    target_table = db.Column(db.String(100))                                   # 目标表/测量
    issue_count = db.Column(db.Integer, default=0)                             # 发现的问题数量
    detail = db.Column(db.JSON)                                                # 检查详情（JSON 格式）
    status = db.Column(db.String(20), default="pass")                          # 检查结果（pass/warn/fail）
