# 系统架构说明书

## 1. 总体架构

```
┌─────────────┐    ┌──────────┐    ┌─────────────┐    ┌──────────────┐
│ OPC UA/传感器 │───▶│  Kafka   │───▶│ Flink/消费  │───▶│  InfluxDB    │
└─────────────┘    └──────────┘    └─────────────┘    └──────────────┘
                         │                                    │
                         ▼                                    ▼
                   ┌──────────┐                        ┌──────────────┐
                   │ HDFS/Hive│                        │ Flask API    │
                   └──────────┘                        └──────────────┘
                         │                                    │
                         ▼                                    ▼
                   ┌──────────┐                        ┌──────────────┐
                   │ Spark ML │                        │ Vue+ECharts  │
                   └──────────┘                        └──────────────┘
                              ┌──────────────┐
                              │    MySQL     │
                              └──────────────┘
```

## 2. 数据流

1. **采集**：OPC UA / 模拟器 → Kafka Topic `energy.raw`
2. **实时写入**：Consumer → InfluxDB `electricity_data`
3. **实时预警**：Alert Engine 消费 Kafka，超阈值写入 MySQL `alert_record`
4. **离线归档**：Flume/Spark → HDFS → Hive DWD 层
5. **展示**：Vue 前端调用 Flask API，Flux 查询 InfluxDB

## 3. 存储分工

| 存储 | 用途 | 数据类型 |
|------|------|----------|
| InfluxDB | 实时时序 | 电/水/气/环境 |
| MySQL | 业务元数据 | 楼宇、仪表、告警、用户 |
| Hive | 历史归档 | DWD/DWS 宽表 |

## 4. 模块说明

- **backend**：REST API，JWT 鉴权，InfluxDB Flux 查询封装
- **data-pipeline/collector**：Kafka 生产/消费
- **data-pipeline/cleaning**：Pandas 清洗 + 3σ 异常检测
- **data-pipeline/alert**：滑动窗口 + 规则引擎实时预警
- **data-pipeline/quality**：缺失/延迟/一致性巡检
- **ml/prediction**：LR + RF 能耗预测

## 5. 部署拓扑

Docker Compose 单机部署，适合学生实验环境。生产扩展可将 Kafka/Flink/Spark 拆至独立节点。
