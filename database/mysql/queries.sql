-- =============================================================================
-- 校园能耗监测平台 — 核心表查询语句
-- =============================================================================
-- 使用方法:
--   docker exec campus-mysql mysql -u energy -penergy123 campus_energy < queries.sql
--   或逐条复制到 MySQL 客户端执行
-- =============================================================================


-- ======================== 1. 建筑信息 ========================
SELECT building_id   AS '建筑编号',
       building_name AS '建筑名称',
       building_type AS '建筑类型',
       floor_count   AS '楼层数',
       build_area    AS '建筑面积(㎡)',
       open_time     AS '开放时间',
       close_time    AS '关闭时间',
       max_occupancy AS '最大容纳人数',
       status        AS '状态'
FROM building
ORDER BY building_id;


-- ======================== 2. 校区区域 ========================
SELECT region_id   AS '区域编号',
       region_name AS '区域名称',
       campus_name AS '所属校区'
FROM region;


-- ======================== 3. 仪表设备 ========================
SELECT m.meter_id    AS '仪表编号',
       m.meter_name  AS '仪表名称',
       m.meter_type  AS '仪表类型',
       b.building_name AS '所属建筑',
       m.protocol    AS '通信协议',
       m.status      AS '运行状态'
FROM meter m
LEFT JOIN building b ON m.building_id = b.building_id
ORDER BY m.meter_id
LIMIT 100;


-- ======================== 4. 能耗时序（核心表，数据量大） ========================
-- 查最后 100 条
SELECT er.id,
       er.building_id  AS '建筑',
       er.region_id    AS '区域',
       er.value        AS '功率(kWh)',
       er.voltage      AS '电压(V)',
       er.current_val  AS '电流(A)',
       er.event_time   AS '采集时间'
FROM energy_record er
ORDER BY er.id DESC
LIMIT 100;

-- 按建筑汇总最近 1 小时
SELECT building_id         AS '建筑',
       COUNT(*)            AS '记录数',
       ROUND(AVG(value),1) AS '平均功率(kWh)',
       ROUND(MAX(value),1) AS '最大功率(kWh)',
       ROUND(MIN(value),1) AS '最小功率(kWh)'
FROM energy_record
WHERE event_time >= NOW() - INTERVAL 1 HOUR
GROUP BY building_id
ORDER BY AVG(value) DESC;

-- 按小时聚合趋势（最近 24 小时）
SELECT DATE_FORMAT(event_time, '%Y-%m-%d %H:00') AS '时段',
       building_id    AS '建筑',
       ROUND(AVG(value),1) AS '平均功率(kWh)'
FROM energy_record
WHERE event_time >= NOW() - INTERVAL 24 HOUR
GROUP BY DATE_FORMAT(event_time, '%Y-%m-%d %H:00'), building_id
ORDER BY DATE_FORMAT(event_time, '%Y-%m-%d %H:00'), building_id;


-- ======================== 5. 分项能耗（数据量大） ========================
-- 查最后 100 条
SELECT esr.id,
       esr.building_id AS '建筑',
       esr.sub_type    AS '分项类型',
       esr.value       AS '功率(kWh)',
       esr.event_time  AS '采集时间'
FROM energy_sub_record esr
ORDER BY esr.id DESC
LIMIT 100;

-- 按分项汇总
SELECT sub_type                AS '分项类型',
       COUNT(*)                AS '记录数',
       ROUND(SUM(value),1)     AS '总功率(kWh)',
       ROUND(AVG(value),1)     AS '平均功率(kWh)'
FROM energy_sub_record
WHERE event_time >= NOW() - INTERVAL 1 HOUR
GROUP BY sub_type;


-- ======================== 6. 告警规则 ========================
SELECT ar.rule_id       AS '规则ID',
       ar.rule_name     AS '规则名称',
       ar.energy_type   AS '能源类型',
       COALESCE(b.building_name, '全局') AS '适用建筑',
       ar.threshold_min AS '阈值下限',
       ar.threshold_max AS '阈值上限',
       ar.severity      AS '严重级别',
       ar.enabled       AS '是否启用'
FROM alert_rule ar
LEFT JOIN building b ON ar.building_id = b.building_id
ORDER BY ar.rule_id;


-- ======================== 7. 告警记录（数据量可能大） ========================
-- 查最后 100 条
SELECT ar.alert_id     AS '告警ID',
       ar.building_id  AS '建筑',
       ar.alert_value  AS '告警值',
       ar.threshold    AS '阈值',
       ar.severity     AS '严重级别',
       ar.status       AS '处理状态',
       ar.triggered_at AS '触发时间'
FROM alert_record ar
ORDER BY ar.alert_id DESC
LIMIT 100;

-- 按严重级别统计（最近 24h）
SELECT severity              AS '严重级别',
       COUNT(*)              AS '数量',
       DATE_FORMAT(MAX(triggered_at),'%H:%i') AS '最近一次触发'
FROM alert_record
WHERE triggered_at >= NOW() - INTERVAL 24 HOUR
GROUP BY severity
ORDER BY COUNT(*) DESC;

-- 按建筑统计告警排行
SELECT building_id           AS '建筑',
       COUNT(*)              AS '告警次数',
       COUNT(CASE WHEN status='open' THEN 1 END) AS '未处理'
FROM alert_record
WHERE triggered_at >= NOW() - INTERVAL 7 DAY
GROUP BY building_id
ORDER BY COUNT(*) DESC;


-- ======================== 8. 日能耗汇总 ========================
-- 最近 7 天
SELECT stat_date     AS '日期',
       building_id   AS '建筑',
       energy_type   AS '能源类型',
       total_value   AS '总能耗',
       peak_value    AS '峰值',
       valley_value  AS '谷值'
FROM energy_daily_summary
WHERE stat_date >= CURRENT_DATE - INTERVAL 7 DAY
ORDER BY stat_date DESC, building_id;


-- ======================== 9. 节能建议 ========================
SELECT adv.advice_id      AS '建议ID',
       adv.building_id    AS '建筑',
       adv.building_type  AS '建筑类型',
       adv.title          AS '建议标题',
       adv.priority       AS '优先级',
       adv.estimated_save AS '预估节能(%)',
       adv.created_at     AS '创建时间'
FROM energy_saving_advice adv
ORDER BY FIELD(adv.priority, 'high','medium','low'), adv.advice_id;


-- ======================== 10. 数据质量巡检日志（查最后 100 条） ========================
SELECT log_id       AS '日志ID',
       check_time   AS '检查时间',
       data_source  AS '数据源',
       check_type   AS '检查类型',
       target_table AS '目标表',
       issue_count  AS '异常数',
       status       AS '结果'
FROM data_quality_log
ORDER BY log_id DESC
LIMIT 100;


-- ======================== 11. 综合总览（一次性看全部概况） ========================
SELECT '建筑总数'      AS '指标', COUNT(*)          AS '数值' FROM building
UNION ALL
SELECT '仪表总数',      COUNT(*)                   FROM meter
UNION ALL
SELECT '能耗记录总数',   FORMAT(COUNT(*), 0)         FROM energy_record
UNION ALL
SELECT '最近24h记录数',  FORMAT(COUNT(*), 0)         FROM energy_record WHERE event_time >= NOW() - INTERVAL 24 HOUR
UNION ALL
SELECT '最近24h告警数',  FORMAT(COUNT(*), 0)         FROM alert_record  WHERE triggered_at >= NOW() - INTERVAL 24 HOUR
UNION ALL
SELECT '活跃告警(open)', FORMAT(COUNT(*), 0)         FROM alert_record  WHERE status = 'open'
UNION ALL
SELECT '数据异常日志',  FORMAT(COUNT(*), 0)          FROM data_quality_log WHERE status IN ('warn','fail') AND check_time >= NOW() - INTERVAL 24 HOUR
UNION ALL
SELECT '节能建议数',    COUNT(*)                    FROM energy_saving_advice
UNION ALL
SELECT '质检日志总数',  COUNT(*)                    FROM data_quality_log;
