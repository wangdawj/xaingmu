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
import CampusMap from '../components/CampusMap.vue'

const online = ref(false)
const range = ref('今日')
const rangeOpts = [{ label: '今日', value: '今日' }, { label: '本周', value: '本周' }, { label: '本月', value: '本月' }]
const rangeHours = { '今日': 24, '本周': 168, '本月': 720 }

const trendData = ref([])
const compareData = ref([])
const peakValley = ref({})
const heatmapData = ref([])
const alertStats = ref({})
const advices = ref([])
const buildings = ref([])

let es = null, timer = null
const nowStr = ref('')
const refreshCount = ref(0)
// 每 5 秒高频刷新，让答辩演示时数据变化肉眼可见
function updateTime() { const t = new Date(); nowStr.value = t.toLocaleTimeString('zh-CN', { hour12: false }) }
updateTime()
setInterval(updateTime, 1000)

// 统计卡片
const statCards = computed(() => {
  const total = trendData.value.reduce((s, d) => s + (d.value || 0), 0)
  const cnt = buildings.value.length
  const alerts = alertStats.value?.records?.length
    || Object.values(alertStats.value?.severity_count || {}).reduce((a, b) => a + b, 0) || 0
  const carbon = Math.round(total * 0.785)
  const fmt = (v) => v >= 10000 ? (v / 10000).toFixed(1) + '万' : v.toLocaleString('zh-CN')
  return [
    { key: 'energy', cls: 'blue', bg: 'rgba(24,144,255,.1)', icon: '⚡', label: (range.value === '今日' ? '24h ' : range.value === '本周' ? '7日 ' : '30日 ') + '总能耗', value: fmt(total), unit: 'kWh' },
    { key: 'bld', cls: 'green', bg: 'rgba(82,196,26,.1)', icon: '🏢', label: '运行建筑', value: cnt, unit: '栋' },
    { key: 'alert', cls: 'orange', bg: 'rgba(250,140,22,.1)', icon: '🔔', label: '告警数量', value: alerts, unit: '次' },
    { key: 'co2', cls: 'teal', bg: 'rgba(19,194,194,.1)', icon: '🌿', label: '碳减排', value: fmt(carbon), unit: 'kgCO₂' },
  ]
})

async function loadAll() {
  const h = rangeHours[range.value] || 24
  const [a, b, c, d, e, f, g] = await Promise.allSettled([
    api.get(`/energy/trend?hours=${h}`),
    api.get(`/energy/comparison?hours=${h}`),
    api.get(`/energy/peak-valley?hours=${h}`),
    api.get(`/energy/heatmap?hours=${h}`),
    api.get('/energy/alerts'),
    api.get('/energy/advice'),
    api.get('/energy/buildings/status'),
  ])
  if (a.status === 'fulfilled') trendData.value = a.value.data.data || []
  if (b.status === 'fulfilled') compareData.value = b.value.data.data || []
  if (c.status === 'fulfilled') peakValley.value = c.value.data.data || {}
  if (d.status === 'fulfilled') heatmapData.value = d.value.data.data || []
  if (e.status === 'fulfilled') alertStats.value = e.value.data.data || {}
  if (f.status === 'fulfilled') advices.value = f.value.data.data || []
  if (g.status === 'fulfilled') buildings.value = g.value.data.data || []
  refreshCount.value++
}

function goBuilding(id) { window.open('/building/' + id, '_blank') }

function connectSSE() {
  es = new EventSource('/api/energy/buildings/stream')
  es.onmessage = (e) => {
    try {
      const d = JSON.parse(e.data)
      if (d.code === 0 && d.data) { buildings.value = d.data; online.value = true }
    } catch {}
  }
  es.onerror = () => { online.value = false; es?.close(); setTimeout(connectSSE, 5000) }
}

onMounted(() => { loadAll(); connectSSE(); timer = setInterval(loadAll, 5000) })
onUnmounted(() => { es?.close(); clearInterval(timer) })
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
