# 基于能源大数据的校园综合能耗监测与节能管理决策平台

面向校园场景的多源能源数据采集、存储、分析、可视化与节能决策支持系统。

## 技术栈

| 层级 | 技术 |
|------|------|
| 采集 | Kafka + Flume + OPC UA |
| 存储 | InfluxDB（时序）+ MySQL（业务）+ HDFS/Hive（离线） |
| 处理 | Spark + Flink + Python Pandas |
| 建模 | Scikit-learn / TensorFlow |
| 展示 | Vue 3 + ECharts |
| 部署 | Docker Compose |

## 项目结构

```
├── backend/                 # Flask API 服务
├── frontend/                # Vue 3 可视化前端
├── data-pipeline/           # 数据采集、清洗、预警、质检
│   ├── collector/           # Kafka 采集与 InfluxDB 写入
│   ├── cleaning/            # Pandas 数据清洗与异常检测
│   ├── alert/               # 实时预警引擎
│   └── quality/             # 数据质量巡检
├── database/                # 建表脚本
│   ├── mysql/
│   ├── influxdb/
│   └── hive/
├── ml/prediction/           # 能耗预测模型
└── docker-compose.yml
```

## 快速启动

### 1. 启动基础设施

```bash
docker compose up -d mysql influxdb kafka zookeeper
```

### 2. 初始化 InfluxDB 示例数据

```bash
pip install influxdb-client
python database/influxdb/setup.py
```

### 3. 启动后端

```bash
cd backend
pip install -r requirements.txt
python app.py
```

### 4. 启动前端

```bash
cd frontend
npm install
npm run dev
```

访问 http://localhost:5173 ，默认账号 `admin` / `admin123`

### 5. 启动数据管道（可选）

```bash
# 终端1: 模拟数据采集
python data-pipeline/collector/kafka_producer.py

# 终端2: Kafka -> InfluxDB
python data-pipeline/collector/kafka_to_influx.py

# 终端3: 实时预警
python data-pipeline/alert/realtime_alert.py

# 数据质量巡检
python data-pipeline/quality/quality_inspector.py
```

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/auth/login | 用户登录 |
| GET | /api/energy/trend | 能耗趋势 |
| GET | /api/energy/comparison | 楼宇对比 |
| GET | /api/energy/peak-valley | 峰谷占比 |
| GET | /api/energy/heatmap | 热力图 |
| GET | /api/energy/alerts | 预警统计 |
| GET | /api/energy/advice | 节能建议 |
| GET | /api/energy/quality/logs | 质检日志 |

## 已完成模块

- MySQL / InfluxDB / Hive 建表与初始化数据
- 5 类 ECharts 可视化图表
- Flask REST API + JWT 用户权限
- Kafka 数据采集 → InfluxDB 写入链路
- Pandas 数据清洗与异常检测
- 实时预警引擎（Kafka 消费 + MySQL 告警入库）
- 数据质量巡检（缺失/延迟/一致性）
- Scikit-learn 能耗预测模型

## 扩展说明

- 新增楼宇：在 `building` 表插入记录并配置对应 `meter`
- 新增告警规则：在 `alert_rule` 表配置阈值
- Hive 离线分析：将 Kafka 数据归档至 HDFS 后执行 Hive SQL
