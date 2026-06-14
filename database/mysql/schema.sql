-- =============================================================================
-- 校园能耗监测平台 — 数据库建表脚本
-- =============================================================================
-- 数据库：campus_energy
-- 引擎：MySQL 8.0（Docker Compose 首次启动时自动执行）
--
-- 【表清单】
--   1. building          — 建筑信息表（6 栋校园建筑）
--   2. region            — 校区区域表
--   3. meter             — 计量仪表表
--   4. energy_record     — 能耗实时数据表（核心，数据量最大的表）
--   5. energy_sub_record — 分项能耗表（照明/空调/插座拆分）
--   6. alert_rule        — 告警规则配置表
--   7. alert_record      — 告警记录表
--   8. data_quality_log  — 数据质量日志表
--   9. energy_advice     — 节能建议表
--   10. campus_map        — 校园地图坐标表
-- =============================================================================

-- 创建数据库（如果由 docker-entrypoint-initdb 创建则不需要，此处作为备选）
-- CREATE DATABASE IF NOT EXISTS campus_energy DEFAULT CHARACTER SET utf8mb4;
-- USE campus_energy;


-- ============================ 1. 校区区域表 ============================
-- 记录校园的不同区域（如东校区、西校区）
-- 用途：建筑按区域分组统计、区域级能耗对比分析
CREATE TABLE IF NOT EXISTS `region` (
    `id`          INT AUTO_INCREMENT PRIMARY KEY COMMENT '自增主键',
    `region_id`   VARCHAR(32)  NOT NULL UNIQUE COMMENT '区域编号（如 R001=东校区, R002=西校区）',
    `region_name` VARCHAR(128) NOT NULL COMMENT '区域名称（如 东校区）',
    `created_at`  DATETIME     DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='校区区域表';


-- ============================ 2. 建筑信息表 ============================
-- 记录校园内各栋建筑的基本信息
-- 用途：大屏建筑卡片、建筑详情页、分组聚合查询
CREATE TABLE IF NOT EXISTS `building` (
    `id`            INT AUTO_INCREMENT PRIMARY KEY COMMENT '自增主键',
    `building_id`   VARCHAR(32)  NOT NULL UNIQUE COMMENT '建筑编号（B001~B006，如 B001=第一教学楼）',
    `building_name` VARCHAR(128) NOT NULL COMMENT '建筑名称（如 第一教学楼）',
    `building_type` VARCHAR(64)  COMMENT '建筑类型（教学楼/宿舍楼/图书馆/食堂/体育馆/行政楼）',
    `region_id`     VARCHAR(32)  COMMENT '所属区域编号（关联 region 表）',
    `base_kw`       FLOAT        COMMENT '基准功率 kW（用于模拟数据生成和告警基线）',
    `status`        VARCHAR(32)  DEFAULT 'active' COMMENT '状态（active=正常, alarm=告警中, offline=离线）',
    `created_at`    DATETIME     DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',

    INDEX `idx_region` (`region_id`),
    FOREIGN KEY (`region_id`) REFERENCES `region`(`region_id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='建筑信息表';


-- ============================ 3. 计量仪表表 ============================
-- 记录各建筑的计量仪表信息（电表）
-- 用途：一个建筑可能有多块表（如总表 + 分表），用于精确计量
CREATE TABLE IF NOT EXISTS `meter` (
    `id`          INT AUTO_INCREMENT PRIMARY KEY COMMENT '自增主键',
    `meter_id`    VARCHAR(32)  NOT NULL UNIQUE COMMENT '仪表编号（如 M001）',
    `building_id` VARCHAR(32)  NOT NULL COMMENT '所属建筑编号',
    `meter_type`  VARCHAR(64)  DEFAULT 'electricity' COMMENT '仪表类型（electricity=电表）',
    `status`      VARCHAR(32)  DEFAULT 'active' COMMENT '状态（active=正常, offline=离线）',
    `created_at`  DATETIME     DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',

    INDEX `idx_building` (`building_id`),
    FOREIGN KEY (`building_id`) REFERENCES `building`(`building_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='计量仪表表';


-- ============================ 4. 能耗实时数据表（核心表）============================
-- 存储每条传感器上报的原始能耗数据
-- 数据流向：Kafka Producer → Kafka Topic → Consumer → 此表
-- 特点：数据量大（首批 1008 条 + 每秒 6 条持续增长），需加索引优化查询
CREATE TABLE IF NOT EXISTS `energy_record` (
    `id`          INT AUTO_INCREMENT PRIMARY KEY COMMENT '自增主键',
    `building_id` VARCHAR(32)  NOT NULL COMMENT '建筑编号（关联 building 表）',
    `region_id`   VARCHAR(32)  COMMENT '区域编号（冗余，加快区域级查询）',
    `meter_id`    VARCHAR(32)  COMMENT '仪表编号（关联 meter 表）',
    `energy_type` VARCHAR(64)  DEFAULT 'electricity' COMMENT '能源类型（electricity=电能）',
    `data_type`   VARCHAR(64)  DEFAULT 'realtime' COMMENT '数据类型（realtime=实时数据）',
    `value`       FLOAT        NOT NULL COMMENT '功率值（kW）',
    `voltage`     FLOAT        COMMENT '电压值（V）',
    `current_val` FLOAT        COMMENT '电流值（A）',
    `event_time`  DATETIME     NOT NULL COMMENT '采集时间戳',

    -- 复合索引：最频繁的查询是 "某建筑最近 N 小时的数据"
    INDEX `idx_building_time` (`building_id`, `event_time`),
    INDEX `idx_event_time` (`event_time`),
    FOREIGN KEY (`building_id`) REFERENCES `building`(`building_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='总能耗时序数据表（核心表）';


-- ============================ 5. 分项能耗表 ============================
-- 将总功率按建筑类型拆分为照明/空调/插座三部分
-- 拆分规则见 kafka_to_mysql.py 中 SUB_RATIOS 配置
-- 用途：前端分项能耗分析、节能潜力评估
CREATE TABLE IF NOT EXISTS `energy_sub_record` (
    `id`          INT AUTO_INCREMENT PRIMARY KEY COMMENT '自增主键',
    `building_id` VARCHAR(32)  NOT NULL COMMENT '建筑编号',
    `sub_type`    VARCHAR(32)  NOT NULL COMMENT '分项类型（lighting=照明, ac=空调, outlet=插座）',
    `value`       FLOAT        NOT NULL COMMENT '该分项功率值（kW）',
    `event_time`  DATETIME     NOT NULL COMMENT '采集时间戳',

    INDEX `idx_sub_building_time` (`building_id`, `event_time`),
    FOREIGN KEY (`building_id`) REFERENCES `building`(`building_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='分项能耗表（照明/空调/插座）';


-- ============================ 6. 告警规则配置表 ============================
-- 存储每个建筑的告警阈值规则
-- 用途：告警引擎启动时加载到内存，实时检测新数据是否超限
CREATE TABLE IF NOT EXISTS `alert_rule` (
    `rule_id`       INT AUTO_INCREMENT PRIMARY KEY COMMENT '自增主键',
    `rule_name`     VARCHAR(128) NOT NULL COMMENT '规则名称（如 第一教学楼能耗上限）',
    `energy_type`   VARCHAR(64)  DEFAULT 'electricity' COMMENT '能源类型',
    `building_id`   VARCHAR(32)  COMMENT '建筑编号（NULL 表示全局规则）',
    `threshold_max` FLOAT        COMMENT '阈值上限（kW），当前值 > 此值触发告警',
    `severity`      VARCHAR(32)  DEFAULT 'warning' COMMENT '严重级别（info=信息, warning=警告, critical=严重）',
    `enabled`       TINYINT(1)   DEFAULT 1 COMMENT '是否启用（1=启用, 0=禁用）',
    `created_at`    DATETIME     DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',

    INDEX `idx_building` (`building_id`),
    FOREIGN KEY (`building_id`) REFERENCES `building`(`building_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='告警规则配置表';


-- ============================ 7. 告警记录表 ============================
-- 存储每次触发的告警记录
-- 用途：前端告警统计图表、告警列表查询
CREATE TABLE IF NOT EXISTS `alert_record` (
    `alert_id`     INT AUTO_INCREMENT PRIMARY KEY COMMENT '自增主键',
    `rule_id`      INT          COMMENT '触发的规则 ID（关联 alert_rule 表）',
    `building_id`  VARCHAR(32)  NOT NULL COMMENT '建筑编号',
    `meter_id`     VARCHAR(32)  COMMENT '仪表编号',
    `energy_type`  VARCHAR(64)  DEFAULT 'electricity' COMMENT '能源类型',
    `alert_value`  FLOAT        NOT NULL COMMENT '触发告警时的实际功率值（kW）',
    `threshold`    FLOAT        COMMENT '触发阈值（kW）',
    `severity`     VARCHAR(32)  NOT NULL COMMENT '严重级别（info/warning/critical）',
    `message`      TEXT         COMMENT '告警描述文本',
    `triggered_at` DATETIME     NOT NULL COMMENT '触发时间',
    `created_at`   DATETIME     DEFAULT CURRENT_TIMESTAMP COMMENT '记录创建时间',

    INDEX `idx_alert_building` (`building_id`),
    INDEX `idx_alert_time` (`triggered_at`),
    INDEX `idx_alert_severity` (`severity`),
    FOREIGN KEY (`rule_id`) REFERENCES `alert_rule`(`rule_id`) ON DELETE SET NULL,
    FOREIGN KEY (`building_id`) REFERENCES `building`(`building_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='告警记录表';


-- ============================ 8. 数据质量日志表 ============================
-- 记录每次离线清洗的执行结果
-- 用途：追踪数据质量趋势、定位清洗异常
CREATE TABLE IF NOT EXISTS `data_quality_log` (
    `id`          INT AUTO_INCREMENT PRIMARY KEY COMMENT '自增主键',
    `check_time`  DATETIME     NOT NULL COMMENT '质检执行时间',
    `data_source` VARCHAR(64)  DEFAULT 'mysql' COMMENT '数据来源（mysql/kafka）',
    `check_type`  VARCHAR(64)  NOT NULL COMMENT '质检类型（cleaning_pipeline=清洗检查）',
    `target_table` VARCHAR(128) NOT NULL COMMENT '目标表名（如 energy_record）',
    `issue_count` INT          DEFAULT 0 COMMENT '发现的问题数量',
    `detail`      JSON         COMMENT '质检详情（JSON 格式：raw_count, cleaned_count, removed等）',
    `status`      VARCHAR(32)  DEFAULT 'pass' COMMENT '质检状态（pass=通过, warn=有问题）',
    `created_at`  DATETIME     DEFAULT CURRENT_TIMESTAMP COMMENT '记录创建时间',

    INDEX `idx_quality_time` (`check_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='数据质量日志表';


-- ============================ 9. 节能建议表 ============================
-- 存储基于数据分析生成的节能建议
-- 用途：前端决策建议表格、Dashboard 建议卡片
CREATE TABLE IF NOT EXISTS `energy_advice` (
    `id`            INT AUTO_INCREMENT PRIMARY KEY COMMENT '自增主键',
    `advice_type`   VARCHAR(64)  NOT NULL COMMENT '建议类型（peak_shaving=削峰填谷, efficiency=效率提升, maintenance=设备维护）',
    `building_id`   VARCHAR(32)  COMMENT '针对的建筑编号（NULL 表示全校建议）',
    `title`         VARCHAR(256) NOT NULL COMMENT '建议标题',
    `content`       TEXT         COMMENT '建议详细内容',
    `priority`      VARCHAR(32)  DEFAULT 'medium' COMMENT '优先级（low/medium/high）',
    `potential_kwh` FLOAT        COMMENT '预计可节约能耗（kWh）',
    `created_at`    DATETIME     DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',

    INDEX `idx_advice_building` (`building_id`),
    FOREIGN KEY (`building_id`) REFERENCES `building`(`building_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='节能建议表';


-- ============================ 10. 校园地图坐标表 ============================
-- 存储建筑在校园地图上的位置坐标
-- 用途：前端 CampusMap 组件 SVG 标注
CREATE TABLE IF NOT EXISTS `campus_map` (
    `id`          INT AUTO_INCREMENT PRIMARY KEY COMMENT '自增主键',
    `building_id` VARCHAR(32)  NOT NULL UNIQUE COMMENT '建筑编号',
    `map_x`       FLOAT        NOT NULL COMMENT '地图 X 坐标',
    `map_y`       FLOAT        NOT NULL COMMENT '地图 Y 坐标',
    `created_at`  DATETIME     DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',

    FOREIGN KEY (`building_id`) REFERENCES `building`(`building_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='校园地图坐标表';


-- ============================ 初始数据插入 ============================

-- 1. 区域数据
INSERT INTO `region` (`region_id`, `region_name`) VALUES
('R001', '东部校区'),
('R002', '西部校区');

-- 2. 建筑数据（6 栋）
INSERT INTO `building` (`building_id`, `building_name`, `building_type`, `region_id`, `base_kw`, `status`) VALUES
('B001', '第一教学楼',   '教学楼', 'R001', 150, 'active'),
('B002', '第二教学楼',   '教学楼', 'R001', 120, 'active'),
('B003', '1号宿舍楼',    '宿舍楼', 'R001',  80, 'active'),
('B004', '2号宿舍楼',    '宿舍楼', 'R002',  70, 'active'),
('B005', '中心图书馆',   '图书馆', 'R001', 200, 'active'),
('B006', '第一食堂',     '食堂',   'R001', 100, 'active');

-- 3. 仪表数据
INSERT INTO `meter` (`meter_id`, `building_id`, `meter_type`, `status`) VALUES
('M001', 'B001', 'electricity', 'active'),
('M002', 'B002', 'electricity', 'active'),
('M003', 'B003', 'electricity', 'active'),
('M004', 'B005', 'electricity', 'active'),
('M005', 'B004', 'electricity', 'active'),
('M006', 'B006', 'electricity', 'active');

-- 4. 告警规则（覆盖全部 6 栋建筑）
-- 阈值设置逻辑：基准功率 × 1.0~1.2（留 20% 余量，但用于触发模拟告警则设低一些）
INSERT INTO `alert_rule` (`rule_name`, `energy_type`, `building_id`, `threshold_max`, `severity`, `enabled`) VALUES
('第一教学楼能耗上限',   'electricity', 'B001', 130, 'warning', 1),
('第二教学楼能耗上限',   'electricity', 'B002', 95,  'warning', 1),
('1号宿舍楼能耗上限',    'electricity', 'B003', 60,  'warning', 1),
('2号宿舍楼能耗上限',    'electricity', 'B004', 55,  'warning', 1),
('中心图书馆能耗上限',   'electricity', 'B005', 170, 'warning', 1),
('第一食堂能耗上限',     'electricity', 'B006', 75,  'warning', 1);

-- 5. 节能建议（初始数据）
INSERT INTO `energy_advice` (`advice_type`, `title`, `content`, `priority`, `potential_kwh`) VALUES
('peak_shaving', '错峰用电：调整高耗能设备运行时间',
 '将部分非必要设备（如电热水器、空调预冷）安排在夜间谷时段（22:00-08:00）运行，利用峰谷电价差降低用电成本。', 'high', 1200),
('efficiency',   '照明系统节能改造',
 '教学楼和图书馆更换 LED 灯具，加装人体感应开关，预计可减少照明能耗 30%-40%。', 'medium', 800),
('maintenance',  '空调系统定期维护',
 '定期清洗空调滤网和冷凝器，提高换热效率，可降低空调能耗 10%-15%。', 'medium', 600);

-- 6. 校园地图坐标
INSERT INTO `campus_map` (`building_id`, `map_x`, `map_y`) VALUES
('B001', 150, 120),
('B002', 320, 130),
('B003', 180, 280),
('B004', 480, 290),
('B005', 300, 200),
('B006', 420, 210);
