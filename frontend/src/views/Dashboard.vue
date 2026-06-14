<!--
  仪表盘总览
  =========
  校园综合能耗监测平台主页面。展示：
  统计卡片 / 校园拓扑图 / 趋势曲线 / 楼宇对比 / 热力图 / 峰谷占比 / 告警统计 / 节能建议
  数据：SSE 实时推送 + 30s 轮询
-->
<template>
  <div class="dashboard">
    <!-- 顶栏 -->
    <header class="top-bar">
      <h1>校园综合能耗监测与节能管理决策平台</h1>
      <span style="display:flex;align-items:center;gap:8px;">
        <el-tag size="small" :type="online ? 'success' : 'info'">{{ online ? '实时在线' : '离线' }}</el-tag>
        <span style="font-size:12px;color:var(--text-secondary);">数据刷新 {{ nowStr }} <span style="color:#1890ff;font-weight:600;">·{{ refreshCount }}</span></span>
      </span>
    </header>

    <!-- 时间范围 -->
    <div class="time-bar">
      <el-segmented v-model="range" :options="rangeOpts" @change="loadAll" />
    </div>

    <!-- 统计卡片 -->
    <el-row :gutter="14" class="stat-row">
      <el-col :span="6" v-for="card in statCards" :key="card.key">
        <div class="stat-card" :class="card.cls">
          <div class="stat-icon" :style="{background:card.bg}">{{ card.icon }}</div>
          <div class="stat-body">
            <div class="stat-label">{{ card.label }}</div>
            <div class="stat-val">{{ card.value }} <small>{{ card.unit }}</small></div>
          </div>
        </div>
      </el-col>
    </el-row>

    <!-- 校园实况 -->
    <el-card shadow="never" class="section">
      <template #header>校园实况 · 实时建筑运行状态</template>
      <CampusMap :buildings="buildings" @select="goBuilding" />
    </el-card>

    <!-- 图表行1：能耗趋势 + 楼宇对比 -->
    <el-row :gutter="14" class="chart-row">
      <el-col :span="12">
        <el-card shadow="never"><EnergyTrendChart :data="trendData" /></el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="never"><BuildingCompareChart :data="compareData" @bar-click="goBuilding" /></el-card>
      </el-col>
    </el-row>

    <!-- 图表行2：热力图 + 峰谷占比 + 告警统计 -->
    <el-row :gutter="14" class="chart-row">
      <el-col :span="8">
        <el-card shadow="never"><HeatmapChart :data="heatmapData" /></el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="never"><PeakValleyChart :data="peakValley" /></el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="never"><AlertStatsChart :data="alertStats" /></el-card>
      </el-col>
    </el-row>

    <!-- 图表行3：能耗预测 -->
    <el-row :gutter="14" class="chart-row">
      <el-col :span="24">
        <el-card shadow="never"><ForecastChart :data="forecastData" /></el-card>
      </el-col>
    </el-row>

    <!-- 节能建议表格 -->
    <el-card shadow="never" class="section">
      <template #header>决策建议 · 基于数据分析的节能方案</template>
      <el-table :data="advices" stripe size="small">
        <el-table-column prop="building_type" label="楼宇类型" width="100" />
        <el-table-column prop="title" label="建议标题" min-width="160" />
        <el-table-column prop="content" label="建议内容" min-width="280" show-overflow-tooltip />
        <el-table-column prop="estimated_save" label="预估节能" width="100" align="center">
          <template #default="{row}"><span class="save-pct">{{ row.estimated_save }}%</span></template>
        </el-table-column>
        <el-table-column prop="priority" label="优先级" width="90" align="center">
          <template #default="{row}">
            <el-tag :type="row.priority==='high'?'danger':row.priority==='medium'?'warning':'info'" size="small">
              {{ row.priority==='high'?'高':row.priority==='medium'?'中':'低' }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import api from '../api'
import EnergyTrendChart from '../components/EnergyTrendChart.vue'
import BuildingCompareChart from '../components/BuildingCompareChart.vue'
import PeakValleyChart from '../components/PeakValleyChart.vue'
import HeatmapChart from '../components/HeatmapChart.vue'
import AlertStatsChart from '../components/AlertStatsChart.vue'
import ForecastChart from '../components/ForecastChart.vue'
import CampusMap from '../components/CampusMap.vue'

const online = ref(false)
// ======================== 时间范围与数据状态 ========================

// 时间范围选择器：今日(24h) / 本周(168h) / 本月(720h)
const range = ref('今日')
const rangeOpts = [
  { label: '今日', value: '今日' },
  { label: '本周', value: '本周' },
  { label: '本月', value: '本月' },
]
// 范围 → 查询小时数 映射表（传给后端 API 的 hours 参数）
const rangeHours = { '今日': 24, '本周': 168, '本月': 720 }

// 各图表的数据响应式引用
const trendData = ref([])       // 24h 趋势曲线
const compareData = ref([])     // 建筑对比柱状图
const peakValley = ref({})      // 峰谷环形图
const heatmapData = ref([])     // 热力图
const alertStats = ref({})      // 告警统计（total_count + severity_count）
const forecastData = ref({})    // 预测图表（metrics + feature_importance + forecast）
const advices = ref([])         // 节能建议表格
const buildings = ref([])       // 建筑状态列表

// SSE 和定时器引用
let es = null, timer = null

// 实时时钟显示（每秒更新）
const nowStr = ref('')
const refreshCount = ref(0)     // 已刷新次数（用于调试/演示：验证 5 秒轮询是否生效）

/** 更新当前时间字符串格式：HH:MM:SS（24 小时制） */
function updateTime() {
  const t = new Date()
  nowStr.value = t.toLocaleTimeString('zh-CN', { hour12: false })
}
updateTime()                           // 立即显示当前时间
setInterval(updateTime, 1000)           // 每秒刷新一次

// ======================== 统计卡片计算属性 ========================

/**
 * 顶部 4 个统计卡片的数据
 * 卡片内容：
 *   [0] 总能耗     → 所有建筑 24h 趋势数据的 value 求和
 *   [1] 运行建筑   → buildings 数组长度（online 的建筑数）
 *   [2] 告警数量   → alertStats.total_count（后端从全量数据 GROUP BY 统计）
 *   [3] 碳减排     → 总能耗 × 0.785 kgCO₂/kWh（电网排放因子）
 *
 * 修复前告警数量用 alertStats.records.length，但 records 被 LIMIT 100 截断
 * 修复后改用 total_count（后端 query.count() 全量统计）
 */
const statCards = computed(() => {
  // 总能耗：趋势数据各点求和
  const total = trendData.value.reduce((s, d) => s + (d.value || 0), 0)
  // 运行建筑数
  const cnt = buildings.value.length
  // 告警总数：优先 total_count（全量），降级 severity_count 求和（兼容旧版 API）
  const alerts = alertStats.value?.total_count
    || Object.values(alertStats.value?.severity_count || {}).reduce((a, b) => a + b, 0) || 0
  // 碳排放：每 kWh 电力约排放 0.785 kg CO₂（2023 年中国电网平均排放因子）
  const carbon = Math.round(total * 0.785)

  /** 数字格式化：>= 10000 显示为 "1.2万"，否则千分位分隔 */
  const fmt = (v) => v >= 10000 ? (v / 10000).toFixed(1) + '万' : v.toLocaleString('zh-CN')

  return [
    { key: 'energy', cls: 'blue', bg: 'rgba(24,144,255,.1)', icon: '⚡',
      label: (range.value === '今日' ? '24h ' : range.value === '本周' ? '7日 ' : '30日 ') + '总能耗',
      value: fmt(total), unit: 'kWh' },
    { key: 'bld', cls: 'green', bg: 'rgba(82,196,26,.1)', icon: '🏢',
      label: '运行建筑', value: cnt, unit: '栋' },
    { key: 'alert', cls: 'orange', bg: 'rgba(250,140,22,.1)', icon: '🔔',
      label: '告警数量', value: alerts, unit: '次' },
    { key: 'co2', cls: 'teal', bg: 'rgba(19,194,194,.1)', icon: '🌿',
      label: '碳减排', value: fmt(carbon), unit: 'kgCO₂' },
  ]
})

// ======================== 数据加载 ========================

/**
 * 并发请求 8 个 API 接口，加载仪表盘全部数据
 *
 * 【技术要点】
 *   1. Promise.allSettled：8 个请求并发发出，互不阻塞
 *      - 对比 Promise.all：一个失败全部失败 → 页面白屏
 *      - allSettled：每个请求独立返回 { status: 'fulfilled'|'rejected', value }
 *        某个 API 失败时其他图表仍然能正常显示
 *   2. 每小时调用一次，由定时器驱动：
 *      - timer = setInterval(loadAll, 5000) → 每 5 秒全量刷新
 *      - 为什么 5 秒？答辩演示时需要频繁看到数据变化，
 *        生产环境建议 30-60 秒减少后端压力
 *   3. refreshCount++ 用于验证轮询是否正常工作（UI 上可见计数器）
 */
async function loadAll() {
  const h = rangeHours[range.value] || 24

  // Promise.allSettled：并发 8 个请求，互不阻塞
  // 解构顺序与传入顺序一致：[a=趋势, b=对比, c=峰谷, d=热力图, e=告警, f=建议, g=建筑, fc=预测]
  const [a, b, c, d, e, f, g, fc] = await Promise.allSettled([
    api.get(`/energy/trend?hours=${h}`),        // a: 24h 趋势数据
    api.get(`/energy/comparison?hours=${h}`),   // b: 建筑对比
    api.get(`/energy/peak-valley?hours=${h}`),  // c: 峰谷占比
    api.get(`/energy/heatmap?hours=${h}`),      // d: 热力图
    api.get('/energy/alerts'),                  // e: 告警统计（不受 hours 影响）
    api.get('/energy/advice'),                  // f: 节能建议（静态数据）
    api.get('/energy/buildings/status'),        // g: 建筑实时状态
    api.get('/energy/forecast'),                // fc: 能耗预测（缓存 10 分钟）
  ])

  // 逐个检查状态，成功的才赋值
  // 数据结构：axios 响应 .data = { code: 0, data: [...actual data...] }
  if (a.status === 'fulfilled') trendData.value = a.value.data.data || []
  if (b.status === 'fulfilled') compareData.value = b.value.data.data || []
  if (c.status === 'fulfilled') peakValley.value = c.value.data.data || {}
  if (d.status === 'fulfilled') heatmapData.value = d.value.data.data || []
  if (e.status === 'fulfilled') alertStats.value = e.value.data.data || {}
  if (f.status === 'fulfilled') advices.value = f.value.data.data || []
  if (g.status === 'fulfilled') buildings.value = g.value.data.data || []
  if (fc.status === 'fulfilled') forecastData.value = fc.value.data.data || {}

  // 刷新计数器 +1（UI 上显示 "已更新 X 次" 验证轮询）
  refreshCount.value++
}

// ======================== 建筑详情页跳转 ========================

function goBuilding(id) { window.open('/building/' + id, '_blank') }

// ======================== SSE 实时连接 ========================

/**
 * 通过 Server-Sent Events 建立实时推送连接
 * 后端 /api/energy/buildings/stream 每秒推送一次全量建筑状态
 * 
 * 【容错机制】
 *   onerror → 关闭当前连接 → 5 秒后自动重连
 *   确保后端重启或网络波动后能自动恢复
 */
function connectSSE() {
  // 创建 EventSource 连接（GET /api/energy/buildings/stream）
  es = new EventSource('/api/energy/buildings/stream')

  // 收到消息时更新建筑状态
  es.onmessage = (e) => {
    try {
      const d = JSON.parse(e.data)
      if (d.code === 0 && d.data) {
        buildings.value = d.data       // 更新建筑列表
        online.value = true            // 标记在线
      }
    } catch { /* JSON 解析失败则忽略 */ }
  }

  // 连接断开/错误时的处理
  es.onerror = () => {
    online.value = false               // 标记离线
    es?.close()                        // 释放旧连接
    setTimeout(connectSSE, 5000)       // 5 秒后重连（避免频繁重试）
  }
}

// ======================== 生命周期 ========================

onMounted(() => {
  loadAll()                          // 首页加载：发起 8 个 API 请求
  connectSSE()                       // 启动 SSE 推送
  timer = setInterval(loadAll, 5000) // 每 5 秒轮询刷新全部数据
})

onUnmounted(() => {
  es?.close()                        // 关闭 SSE 连接
  clearInterval(timer)               // 清除定时器
})
</script>

<style scoped>
.dashboard { padding: 16px 20px; background: var(--bg); min-height: 100vh; }

.top-bar {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 14px; padding: 0 16px; height: 50px;
  background: var(--card-bg); border-radius: var(--radius); box-shadow: var(--shadow);
}
.top-bar h1 { font-size: 16px; color: var(--text); margin: 0; font-weight: 600; }

.time-bar { display: flex; justify-content: center; margin-bottom: 14px; }

.stat-row { margin-bottom: 10px; }
.stat-card {
  display: flex; align-items: center; gap: 12px;
  padding: 14px 16px; border-radius: var(--radius);
  background: var(--card-bg); box-shadow: var(--shadow);
  transition: transform .2s, box-shadow .2s;
}
.stat-card:hover { transform: translateY(-2px); box-shadow: var(--shadow-hover); }
.stat-icon { width: 44px; height: 44px; border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 20px; flex-shrink: 0; }
.stat-label { font-size: 12px; color: var(--text-secondary); margin-bottom: 2px; }
.stat-val { font-size: 22px; font-weight: 700; color: var(--text); line-height: 1.1; }
.stat-val small { font-size: 12px; font-weight: 400; color: var(--text-secondary); }

.section { margin-bottom: 12px; }
.chart-row { margin-bottom: 12px; }
.save-pct { color: var(--success); font-weight: 600; }
</style>
