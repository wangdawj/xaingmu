<template>
  <div class="dashboard">
    <!-- 顶栏 -->
    <header class="header">
      <h1 class="header-title">
        <svg viewBox="0 0 24 24" width="22" height="22" class="header-icon"><rect x="4" y="11" width="4" height="9" rx="1" fill="var(--primary)"/><rect x="10" y="7" width="4" height="13" rx="1" fill="var(--primary)"/><rect x="16" y="3" width="4" height="17" rx="1" fill="var(--primary)"/><circle cx="8" cy="10" r="1.5" fill="#ffd666"/><circle cx="14" cy="6" r="1.5" fill="#ffd666"/><circle cx="20" cy="2" r="1.5" fill="#ffd666"/></svg>
        校园综合能耗监测与节能管理决策平台
      </h1>
      <div class="user-info">
        <el-tag size="small" :type="streamConnected ? 'success' : 'info'" effect="plain">
          {{ streamConnected ? '实时在线' : '离线重连中' }}
        </el-tag>
        <span class="username">{{ username }}</span>
        <el-button link type="danger" @click="logout">退出</el-button>
      </div>
    </header>

    <!-- 时间范围选择器 -->
    <div class="time-range-bar">
      <el-segmented v-model="timeRange" :options="timeOptions" size="default" @change="onTimeChange" />
    </div>

    <!-- 统计卡片 -->
    <el-row :gutter="16" class="stat-row">
      <el-col :span="6">
        <div class="stat-card stat-card--blue">
          <div class="stat-card__inner">
            <div class="stat-card__icon">
              <svg viewBox="0 0 32 32" width="28" height="28"><path d="M13 4L5 14h6v14h4V14h6L13 4z" fill="var(--primary)"/></svg>
            </div>
            <div class="stat-card__info">
              <div class="stat-card__label">{{ timeLabel }}总能耗</div>
              <div class="stat-card__value">{{ fmtNum(stats.totalEnergy) }} <small>kWh</small></div>
            </div>
          </div>
        </div>
      </el-col>
      <el-col :span="6">
        <div class="stat-card stat-card--green">
          <div class="stat-card__inner">
            <div class="stat-card__icon">
              <svg viewBox="0 0 32 32" width="28" height="28"><rect x="4" y="10" width="7" height="16" rx="1" fill="var(--success)"/><rect x="13" y="6" width="7" height="20" rx="1" fill="var(--success)"/><rect x="22" y="13" width="7" height="13" rx="1" fill="var(--success)"/></svg>
            </div>
            <div class="stat-card__info">
              <div class="stat-card__label">运行建筑</div>
              <div class="stat-card__value">{{ stats.buildingCount }} <small>栋</small></div>
            </div>
          </div>
        </div>
      </el-col>
      <el-col :span="6">
        <div class="stat-card stat-card--orange">
          <div class="stat-card__inner">
            <div class="stat-card__icon">
              <svg viewBox="0 0 32 32" width="28" height="28"><circle cx="16" cy="16" r="12" fill="none" stroke="var(--warning)" stroke-width="2.5"/><line x1="16" y1="10" x2="16" y2="17" stroke="var(--warning)" stroke-width="2.5" stroke-linecap="round"/><circle cx="16" cy="21" r="1.2" fill="var(--warning)"/></svg>
            </div>
            <div class="stat-card__info">
              <div class="stat-card__label">告警数量</div>
              <div class="stat-card__value">{{ stats.alertCount }} <small>次</small></div>
            </div>
          </div>
        </div>
      </el-col>
      <el-col :span="6">
        <div class="stat-card stat-card--teal">
          <div class="stat-card__inner">
            <div class="stat-card__icon">
              <svg viewBox="0 0 32 32" width="28" height="28"><path d="M16 4C9.4 4 4 9.4 4 16s5.4 12 12 12 12-5.4 12-12S22.6 4 16 4z" fill="none" stroke="#13c2c2" stroke-width="2"/><path d="M11 18c0 0 3-4 5-4s5 4 5 4" fill="none" stroke="#13c2c2" stroke-width="2" stroke-linecap="round"/></svg>
            </div>
            <div class="stat-card__info">
              <div class="stat-card__label">碳减排</div>
              <div class="stat-card__value">{{ fmtNum(stats.carbonReduce) }} <small>kgCO₂</small></div>
            </div>
          </div>
        </div>
      </el-col>
    </el-row>

    <!-- 校园实况 -->
    <SectionTitle title="校园实况" subtitle="实时建筑运行状态" />
    <CampusMap :buildings="campusBuildings" @select="goBuilding" />

    <!-- 能耗分析 -->
    <SectionTitle title="能耗分析" subtitle="多维度数据对比" />
    <el-row :gutter="16" class="chart-row">
      <el-col :span="12">
        <el-card shadow="never"><EnergyTrendChart :data="trendData" /></el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="never"><BuildingCompareChart :data="compareData" @bar-click="goBuilding" /></el-card>
      </el-col>
    </el-row>
    <el-row :gutter="16" class="chart-row">
      <el-col :span="8">
        <el-card shadow="never"><HeatmapChart :data="heatmapData" /></el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="never"><PeakValleyChart :data="peakValleyData" /></el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="never"><AlertStatsChart :data="alertData" /></el-card>
      </el-col>
    </el-row>

    <!-- 决策建议 -->
    <SectionTitle title="决策建议" subtitle="基于数据分析的节能方案" />
    <el-card shadow="never" class="advice-card">
      <el-table :data="adviceList" stripe size="small">
        <el-table-column prop="building_type" label="楼宇类型" width="110" />
        <el-table-column prop="title" label="建议标题" min-width="180" />
        <el-table-column prop="content" label="建议内容" min-width="300" />
        <el-table-column prop="estimated_save" label="预估节能(%)" width="110" align="center">
          <template #default="{ row }">
            <span class="save-tag">{{ row.estimated_save }}%</span>
          </template>
        </el-table-column>
        <el-table-column prop="priority" label="优先级" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="row.priority === 'high' ? 'danger' : row.priority === 'medium' ? 'warning' : 'info'" size="small">
              {{ row.priority === 'high' ? '高' : row.priority === 'medium' ? '中' : '低' }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api'
import EnergyTrendChart from '../components/EnergyTrendChart.vue'
import BuildingCompareChart from '../components/BuildingCompareChart.vue'
import PeakValleyChart from '../components/PeakValleyChart.vue'
import HeatmapChart from '../components/HeatmapChart.vue'
import AlertStatsChart from '../components/AlertStatsChart.vue'
import CampusMap from '../components/CampusMap.vue'
import SectionTitle from '../components/SectionTitle.vue'

const router = useRouter()
const username = ref(localStorage.getItem('username') || '用户')
const trendData = ref([])
const compareData = ref([])
const peakValleyData = ref({})
const heatmapData = ref([])
const alertData = ref({})
const adviceList = ref([])
const campusBuildings = ref([])
const streamConnected = ref(false)
let eventSource = null
let refreshTimer = null

const timeRange = ref('今日')
const timeOptions = [
  { label: '今日', value: '今日' },
  { label: '本周', value: '本周' },
  { label: '本月', value: '本月' },
]
const timeRangeHours = { '今日': 24, '本周': 168, '本月': 720 }
const timeLabel = computed(() => timeRange.value === '今日' ? '24h ' : timeRange.value === '本周' ? '7日 ' : '30日 ')

function onTimeChange() {
  loadData()
}

async function loadData() {
  const hours = timeRangeHours[timeRange.value] || 24
  const [trend, compare, peakValley, heatmap, alerts, advice, status] = await Promise.allSettled([
    api.get(`/energy/trend?hours=${hours}`),
    api.get(`/energy/comparison?hours=${hours}`),
    api.get(`/energy/peak-valley?hours=${hours}`),
    api.get(`/energy/heatmap?hours=${hours}`),
    api.get('/energy/alerts'),
    api.get('/energy/advice'),
    api.get('/energy/buildings/status'),
  ])
  if (trend.status === 'fulfilled') trendData.value = trend.value.data.data || []
  if (compare.status === 'fulfilled') compareData.value = compare.value.data.data || []
  if (peakValley.status === 'fulfilled') peakValleyData.value = peakValley.value.data.data || {}
  if (heatmap.status === 'fulfilled') heatmapData.value = heatmap.value.data.data || []
  if (alerts.status === 'fulfilled') alertData.value = alerts.value.data.data || {}
  if (advice.status === 'fulfilled') adviceList.value = advice.value.data.data || []
  if (status.status === 'fulfilled') campusBuildings.value = status.value.data.data || []
}

function connectSSE() {
  const token = localStorage.getItem('token')
  eventSource = new EventSource(`/api/energy/buildings/stream?token=${token}`)
  eventSource.onmessage = (e) => {
    try {
      const res = JSON.parse(e.data)
      if (res.code === 0 && res.data) {
        campusBuildings.value = res.data
        streamConnected.value = true
      }
    } catch {}
  }
  eventSource.onerror = () => {
    streamConnected.value = false
    eventSource?.close()
    setTimeout(connectSSE, 5000)
  }
}

function logout() {
  localStorage.removeItem('token')
  localStorage.removeItem('username')
  eventSource?.close()
  clearInterval(refreshTimer)
  router.push('/login')
}

onMounted(() => {
  loadData()
  connectSSE()
  refreshTimer = setInterval(loadData, 30000)
})
onUnmounted(() => {
  eventSource?.close()
  clearInterval(refreshTimer)
})
</script>

<style scoped>
.dashboard {
  padding: 20px 24px;
  background: var(--bg);
  min-height: 100vh;
}

/* 顶栏 */
.header {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 20px; padding: 0 20px;
  height: 56px;
  background: var(--card-bg);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
}
.header-title {
  font-size: 17px; color: var(--text); margin: 0;
  display: flex; align-items: center; gap: 8px; font-weight: 600;
}
.header-icon { flex-shrink: 0; }
.user-info { display: flex; align-items: center; gap: 14px; font-size: 13px; color: var(--text-secondary); }
.username { font-weight: 500; color: var(--text); }

/* 时间范围 */
.time-range-bar {
  display: flex; justify-content: center; margin-bottom: 16px;
}

/* 统计卡片 */
.stat-row { margin-bottom: 8px; }
.stat-card {
  background: var(--card-bg);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  padding: 4px;
  position: relative;
  overflow: hidden;
  cursor: default;
  transition: box-shadow .25s, transform .25s;
}
.stat-card:hover { box-shadow: var(--shadow-hover); transform: translateY(-2px); }
.stat-card__inner {
  display: flex; align-items: center; gap: 14px; padding: 16px 18px;
}
.stat-card__icon {
  width: 50px; height: 50px; border-radius: 12px;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}
.stat-card--blue  .stat-card__icon { background: rgba(24,144,255,.1); }
.stat-card--green .stat-card__icon { background: rgba(82,196,26,.1); }
.stat-card--orange .stat-card__icon { background: rgba(250,140,22,.1); }
.stat-card--teal  .stat-card__icon { background: rgba(19,194,194,.1); }
.stat-card__label { font-size: 13px; color: var(--text-secondary); margin-bottom: 4px; }
.stat-card__value { font-size: 24px; font-weight: 700; color: var(--text); line-height: 1.1; }
.stat-card__value small { font-size: 13px; font-weight: 400; color: var(--text-secondary); }
.stat-card::after {
  content: ''; position: absolute; top: 0; right: 0; width: 60px; height: 60px;
  border-radius: 0 0 0 60px; opacity: .06;
}
.stat-card--blue::after  { background: var(--primary); }
.stat-card--green::after { background: var(--success); }
.stat-card--orange::after { background: var(--warning); }
.stat-card--teal::after  { background: #13c2c2; }

/* 图表行 */
.chart-row { margin-bottom: 16px; }

/* 建议卡片 */
.advice-card { margin-top: 4px; margin-bottom: 8px; }
.save-tag { color: var(--success); font-weight: 600; }
</style>
