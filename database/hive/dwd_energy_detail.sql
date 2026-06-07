-- Hive DWD 层 - 能耗明细宽表
CREATE DATABASE IF NOT EXISTS campus_energy_dw;
USE campus_energy_dw;

CREATE EXTERNAL TABLE IF NOT EXISTS dwd_energy_detail (
    event_time   TIMESTAMP   COMMENT '事件时间',
    building_id  STRING      COMMENT '楼宇ID',
    region_id    STRING      COMMENT '区域ID',
    meter_id     STRING      COMMENT '仪表ID',
    energy_type  STRING      COMMENT '能源类型 electricity/water/gas/environment',
    data_type    STRING      COMMENT '数据类型',
    value        DOUBLE      COMMENT '数值',
    unit         STRING      COMMENT '单位',
    voltage      DOUBLE      COMMENT '电压(电)',
    current_val  DOUBLE      COMMENT '电流(电)',
    etl_time     TIMESTAMP   COMMENT 'ETL入库时间'
)
PARTITIONED BY (dt STRING COMMENT '日期分区 yyyy-MM-dd')
STORED AS PARQUET
LOCATION '/warehouse/campus_energy/dwd/dwd_energy_detail'
TBLPROPERTIES ('parquet.compress'='SNAPPY');

-- ODS 原始层（Kafka 落地）
CREATE EXTERNAL TABLE IF NOT EXISTS ods_energy_raw (
    raw_json STRING COMMENT '原始JSON'
)
PARTITIONED BY (dt STRING, hour STRING)
ROW FORMAT SERDE 'org.apache.hadoop.hive.serde2.JsonSerDe'
STORED AS TEXTFILE
LOCATION '/warehouse/campus_energy/ods/ods_energy_raw';

-- DWS 日汇总层
CREATE TABLE IF NOT EXISTS dws_energy_daily (
    stat_date    STRING,
    building_id  STRING,
    region_id    STRING,
    energy_type  STRING,
    total_value  DOUBLE,
    peak_value   DOUBLE,
    valley_value DOUBLE,
    avg_value    DOUBLE,
    record_count BIGINT
)
PARTITIONED BY (dt STRING)
STORED AS PARQUET
LOCATION '/warehouse/campus_energy/dws/dws_energy_daily';
