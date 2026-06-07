-- 校园综合能耗监测平台 - MySQL 业务库
SET NAMES utf8mb4;
CREATE DATABASE IF NOT EXISTS campus_energy DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE campus_energy;

-- 楼宇信息
CREATE TABLE IF NOT EXISTS building (
    building_id     VARCHAR(32)  PRIMARY KEY,
    building_name   VARCHAR(100) NOT NULL,
    building_type   ENUM('教学楼','宿舍楼','图书馆','食堂','体育馆','行政楼') NOT NULL,
    floor_count     INT          NOT NULL DEFAULT 1,
    build_area      DECIMAL(12,2) NOT NULL COMMENT '建筑面积(㎡)',
    open_time       TIME         NOT NULL DEFAULT '08:00:00',
    close_time      TIME         NOT NULL DEFAULT '22:00:00',
    max_occupancy   INT          NOT NULL DEFAULT 0,
    region_id       VARCHAR(32)  NOT NULL,
    status          TINYINT      NOT NULL DEFAULT 1 COMMENT '1启用 0停用',
    created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_region (region_id),
    INDEX idx_type (building_type)
) ENGINE=InnoDB COMMENT='楼宇基础信息';

-- 区域/校区
CREATE TABLE IF NOT EXISTS region (
    region_id   VARCHAR(32)  PRIMARY KEY,
    region_name VARCHAR(100) NOT NULL,
    campus_name VARCHAR(100) NOT NULL,
    longitude   DECIMAL(10,6),
    latitude    DECIMAL(10,6)
) ENGINE=InnoDB COMMENT='校区区域';

-- 仪表设备
CREATE TABLE IF NOT EXISTS meter (
    meter_id      VARCHAR(32)  PRIMARY KEY,
    meter_name    VARCHAR(100) NOT NULL,
    meter_type    ENUM('电表','水表','气表','环境传感器') NOT NULL,
    building_id   VARCHAR(32)  NOT NULL,
    region_id     VARCHAR(32)  NOT NULL,
    install_floor INT,
    protocol      VARCHAR(50)  DEFAULT 'OPC_UA',
    status        TINYINT      NOT NULL DEFAULT 1,
    created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (building_id) REFERENCES building(building_id),
    INDEX idx_building (building_id),
    INDEX idx_type (meter_type)
) ENGINE=InnoDB COMMENT='仪表设备信息';

-- 告警规则
CREATE TABLE IF NOT EXISTS alert_rule (
    rule_id       INT AUTO_INCREMENT PRIMARY KEY,
    rule_name     VARCHAR(100) NOT NULL,
    energy_type   ENUM('electricity','water','gas','environment') NOT NULL,
    building_id   VARCHAR(32),
    threshold_min DECIMAL(12,4),
    threshold_max DECIMAL(12,4),
    duration_sec  INT          NOT NULL DEFAULT 300 COMMENT '持续秒数触发告警',
    severity      ENUM('info','warning','critical') NOT NULL DEFAULT 'warning',
    enabled       TINYINT      NOT NULL DEFAULT 1,
    created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_building (building_id),
    INDEX idx_energy (energy_type)
) ENGINE=InnoDB COMMENT='异常预警规则';

-- 告警记录
CREATE TABLE IF NOT EXISTS alert_record (
    alert_id      BIGINT AUTO_INCREMENT PRIMARY KEY,
    rule_id       INT          NOT NULL,
    building_id   VARCHAR(32)  NOT NULL,
    meter_id      VARCHAR(32),
    energy_type   VARCHAR(32)  NOT NULL,
    alert_value   DECIMAL(12,4) NOT NULL,
    threshold     DECIMAL(12,4),
    severity      ENUM('info','warning','critical') NOT NULL,
    message       VARCHAR(500),
    status        ENUM('open','acknowledged','resolved') NOT NULL DEFAULT 'open',
    triggered_at  DATETIME     NOT NULL,
    resolved_at   DATETIME,
    INDEX idx_status (status),
    INDEX idx_triggered (triggered_at),
    FOREIGN KEY (rule_id) REFERENCES alert_rule(rule_id)
) ENGINE=InnoDB COMMENT='告警记录';

-- 日统计汇总
CREATE TABLE IF NOT EXISTS energy_daily_summary (
    id            BIGINT AUTO_INCREMENT PRIMARY KEY,
    stat_date     DATE         NOT NULL,
    building_id   VARCHAR(32)  NOT NULL,
    energy_type   ENUM('electricity','water','gas') NOT NULL,
    total_value   DECIMAL(14,4) NOT NULL,
    peak_value    DECIMAL(12,4),
    valley_value  DECIMAL(12,4),
    avg_value     DECIMAL(12,4),
    unit          VARCHAR(20)  NOT NULL DEFAULT 'kWh',
    created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_date_building_type (stat_date, building_id, energy_type),
    INDEX idx_date (stat_date)
) ENGINE=InnoDB COMMENT='日能耗汇总';

-- 节能建议
CREATE TABLE IF NOT EXISTS energy_saving_advice (
    advice_id     INT AUTO_INCREMENT PRIMARY KEY,
    building_id   VARCHAR(32)  NOT NULL,
    building_type VARCHAR(50)  NOT NULL,
    title         VARCHAR(200) NOT NULL,
    content       TEXT         NOT NULL,
    priority      ENUM('low','medium','high') NOT NULL DEFAULT 'medium',
    estimated_save DECIMAL(8,2) COMMENT '预估节能百分比',
    created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_building (building_id)
) ENGINE=InnoDB COMMENT='节能决策建议';

-- 用户权限
CREATE TABLE IF NOT EXISTS sys_user (
    user_id       INT AUTO_INCREMENT PRIMARY KEY,
    username      VARCHAR(50)  NOT NULL UNIQUE,
    password_hash VARCHAR(256) NOT NULL,
    real_name     VARCHAR(50),
    role          ENUM('admin','operator','viewer') NOT NULL DEFAULT 'viewer',
    status        TINYINT      NOT NULL DEFAULT 1,
    created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB COMMENT='系统用户';

-- 数据质量巡检记录
CREATE TABLE IF NOT EXISTS data_quality_log (
    log_id        BIGINT AUTO_INCREMENT PRIMARY KEY,
    check_time    DATETIME     NOT NULL,
    data_source   VARCHAR(50)  NOT NULL COMMENT 'influxdb/mysql/hive',
    check_type    VARCHAR(50)  NOT NULL COMMENT 'missing/outlier/delay/consistency',
    target_table  VARCHAR(100),
    issue_count   INT          NOT NULL DEFAULT 0,
    detail        JSON,
    status        ENUM('pass','warn','fail') NOT NULL DEFAULT 'pass',
    INDEX idx_check_time (check_time),
    INDEX idx_status (status)
) ENGINE=InnoDB COMMENT='数据质量巡检日志';

-- 初始化数据
INSERT INTO region (region_id, region_name, campus_name, longitude, latitude) VALUES
('R001', '东校区', '主校区', 116.397128, 39.916527),
('R002', '西校区', '主校区', 116.387128, 39.906527);

INSERT INTO building (building_id, building_name, building_type, floor_count, build_area, open_time, close_time, max_occupancy, region_id) VALUES
('B001', '第一教学楼', '教学楼', 6, 12000.00, '07:30:00', '22:00:00', 2000, 'R001'),
('B002', '第二教学楼', '教学楼', 5, 9800.00, '07:30:00', '22:00:00', 1800, 'R001'),
('B003', '1号宿舍楼', '宿舍楼', 12, 8500.00, '00:00:00', '23:59:59', 1200, 'R001'),
('B004', '2号宿舍楼', '宿舍楼', 12, 8500.00, '00:00:00', '23:59:59', 1200, 'R002'),
('B005', '中心图书馆', '图书馆', 4, 15000.00, '08:00:00', '22:00:00', 800, 'R001'),
('B006', '第一食堂', '食堂', 2, 5000.00, '06:30:00', '21:00:00', 1500, 'R001');

INSERT INTO meter (meter_id, meter_name, meter_type, building_id, region_id, install_floor) VALUES
('M001', '教学楼1总电表', '电表', 'B001', 'R001', 1),
('M002', '教学楼2总电表', '电表', 'B002', 'R001', 1),
('M003', '1号宿舍总电表', '电表', 'B003', 'R001', 1),
('M004', '图书馆总电表', '电表', 'B005', 'R001', 1),
('M005', '食堂总电表', '电表', 'B006', 'R001', 1),
('M006', '1号宿舍总水表', '水表', 'B003', 'R001', 1);

INSERT INTO alert_rule (rule_name, energy_type, building_id, threshold_max, duration_sec, severity) VALUES
('教学楼用电峰值告警', 'electricity', 'B001', 500.0000, 300, 'warning'),
('宿舍楼夜间用电异常', 'electricity', 'B003', 200.0000, 600, 'critical'),
('食堂用水异常', 'water', 'B006', 50.0000, 300, 'warning');

INSERT INTO energy_saving_advice (building_id, building_type, title, content, priority, estimated_save) VALUES
('B001', '教学楼', '非教学时段空调管控', '建议在18:00后关闭无人教室空调，周末仅开放预约教室。', 'high', 15.00),
('B003', '宿舍楼', '峰谷电价引导', '建议推送22:00-06:00低谷时段洗衣、充电提醒，降低高峰负荷。', 'medium', 8.50),
('B006', '食堂', '备餐时段设备优化', '建议备餐前30分钟预热，打烊后及时关闭蒸箱、保温台。', 'high', 12.00);

INSERT INTO sys_user (username, password_hash, real_name, role) VALUES
('admin', 'scrypt:32768:8:1$placeholder$placeholder', '系统管理员', 'admin');
