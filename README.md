# 基于能源大数据的校园综合能耗监测与节能管理决策平台

面向校园场景的多源能源数据采集、存储、分析、可视化与节能决策支持系统。

## 技术栈

| 层级 | 技术 |
|------|------|
| 采集 | Kafka（模拟传感器 → Topic → Consumer） |
| 存储 | MySQL 8.0（业务数据 + 时序能耗） |
| 处理 | Python Pandas（清洗） + Kafka Consumer（实时流转） |
docker exec campus-pipeline python /app/data-pipeline/cleaning/run_mysql_cleaning.py 2>&1
| 建模 | Scikit-learn（线性回归 + 随机森林预测） |
docker exec campus-backend python ml/prediction/energy_forecast.py
| 展示 | Vue 3 + ECharts + Element Plus |
| 部署 | Docker Compose（6 服务一键编排） |

## 项目结构

```
├── backend/                 # Flask API 服务
│   ├── routes/              # 路由：energy（能耗 API 蓝图）
│   ├── services/            # 能耗数据查询服务封装
│   ├── models/              # SQLAlchemy 数据模型
│   └── scripts/             # 种子数据生成脚本
├── frontend/                # Vue 3 可视化前端 (Vite 构建)
│   ├── src/views/           # Dashboard / BuildingDetail
│   └── src/components/      # ECharts 图表组件 + 校园拓扑图
├── data-pipeline/           # 数据管道（独立容器运行）
│   ├── run_all.py             # 统一启动器（Producer + Consumer + Alert）
│   ├── collector/             # Kafka Producer（模拟传感器）+ Consumer（写入 MySQL）
│   ├── cleaning/              # Pandas 数据清洗与异常检测
│   ├── alert/                 # 实时预警引擎（规则阈值 + 滑动窗口）
│   └── quality/               # 数据质量巡检（缺失/延迟/一致性校验）
├── database/mysql/          # MySQL 建表脚本与查询语句
├── ml/prediction/           # 能耗预测模型（线性回归 + 随机森林）
├── docker-compose.yml       # 6 服务编排文件
└── docs/architecture.md     # 系统架构说明书
```

## 快速启动

### 方式一：Docker 一键部署

```bash
# 1. 启动所有服务
docker compose up -d

# 2. 写入种子数据（可选，用于填充历史图表）
docker exec campus-backend python scripts/seed_mysql.py
```

访问 **http://localhost:8080**

### 方式二：查看运行状态

```bash
# 查看所有容器
docker compose ps

# 查看数据管道日志
docker logs -f campus-pipeline
```

## 核心数据流

```
传感器模拟器 ──每秒发数据──▶ Kafka ──消费──▶ MySQL energy_record
                                   │
                                   └──▶ 预警引擎 ──▶ MySQL alert_record

Flask API ◀── 查询 MySQL ──▶ Vue + ECharts 大屏展示
```

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/health | 健康检查 |
| GET | /api/energy/buildings | 建筑列表 |
| GET | /api/energy/building/{id}/detail | 建筑详情 + 24h 用电曲线 |
| GET | /api/energy/trend | 能耗趋势（按小时聚合） |
| GET | /api/energy/comparison | 楼宇能耗对比 |
| GET | /api/energy/peak-valley | 峰谷时段占比 |
| GET | /api/energy/heatmap | 区域 × 建筑能耗热力图 |
| GET | /api/energy/alerts | 预警记录与统计 |
| GET | /api/energy/advice | 节能建议列表 |
| GET | /api/energy/quality/logs | 数据质检日志 |

## 数据库核心表

| 表名 | 说明 |
|------|------|
| `building` | 建筑基础信息（名称、类型、面积、开放时间） |
| `meter` | 仪表设备（电表/水表/气表，关联建筑） |
| `energy_record` | 能耗时序数据（功率、电压、电流，按秒写入） |
| `energy_sub_record` | 分项能耗（照明/空调/插座） |
| `alert_rule` | 告警规则配置（阈值、级别） |
| `alert_record` | 告警记录（触发值、状态、时间） |
| `energy_saving_advice` | 节能决策建议 |
| `energy_daily_summary` | 日能耗汇总统计 |
| `data_quality_log` | 数据质量巡检日志 |

查询语句见 `database/mysql/queries.sql`。

## 可视化大屏

| 区域 | 内容 |
|------|------|
| 统计卡片 | 总能耗 / 运行建筑数 / 告警数 / 碳减排量 |
| 校园拓扑图 | SVG 地图，按建筑状态着色（绿色/橙色/红色） |
| 热力图 | 区域 × 建筑的能耗强度矩阵 |
| 峰谷图 | 峰时段（8-22 点）与谷时段用电占比环形图 |
| 预警统计 | 按严重级别（信息/警告/严重）的告警数量柱状图 |
| 楼宇对比 | 六栋建筑实时功率排行柱状图 |
| 节能建议 | 按优先级排序的节能措施列表 |

## 预警机制

采用双重策略进行异常检测：

1. **规则阈值**：管理员预设功率上限，超过则告警
2. **滑动窗口**：当前值与近 20 条历史均值比较，突增超过 2 倍则告警

告警按严重级别分为信息（info）、警告（warning）、严重（critical）三级。

## 扩展方向

- 对接真实 OPC UA / Modbus 工业协议电表
- 引入天气、课表数据提升预测精度
- 手机端告警推送（钉钉/微信）
- 升级至 Flink 实时流处理引擎
