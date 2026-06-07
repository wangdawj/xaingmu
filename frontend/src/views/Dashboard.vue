<template>
  <div class="dashboard">
    <header class="header">
      <h1>校园综合能耗监测与节能管理决策平台</h1>
      <div class="user-info">
        <span>{{ username }}</span>
        <el-button link type="primary" @click="logout">退出</el-button>
      </div>
    </header>

    <el-row :gutter="16" class="chart-row">
      <el-col :span="12"><EnergyTrendChart :data="trendData" /></el-col>
      <el-col :span="12"><BuildingCompareChart :data="compareData" /></el-col>
    </el-row>

    <el-row :gutter="16" class="chart-row">
      <el-col :span="8"><HeatmapChart :data="heatmapData" /></el-col>
      <el-col :span="8"><PeakValleyChart :data="peakValleyData" /></el-col>
      <el-col :span="8"><AlertStatsChart :data="alertData" /></el-col>
    </el-row>

    <el-card class="advice-card">
      <template #header><span>节能决策建议</span></template>
      <el-table :data="adviceList" stripe size="small">
        <el-table-column prop="building_type" label="楼宇类型" width="100" />
        <el-table-column prop="title" label="建议标题" width="200" />
        <el-table-column prop="content" label="建议内容" />
        <el-table-column prop="estimated_save" label="预估节能(%)" width="120" />
        <el-table-column prop="priority" label="优先级" width="80">
          <template #default="{ row }">
            <el-tag :type="row.priority === 'high' ? 'danger' : row.priority === 'medium' ? 'warning' : 'info'" size="small">
              {{ row.priority }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api'
import EnergyTrendChart from '../components/EnergyTrendChart.vue'
import BuildingCompareChart from '../components/BuildingCompareChart.vue'
import PeakValleyChart from '../components/PeakValleyChart.vue'
import HeatmapChart from '../components/HeatmapChart.vue'
import AlertStatsChart from '../components/AlertStatsChart.vue'

const router = useRouter()
const username = ref(localStorage.getItem('username') || '用户')
const trendData = ref([])
const compareData = ref([])
const peakValleyData = ref({})
const heatmapData = ref([])
const alertData = ref({})
const adviceList = ref([])

async function loadData() {
  const [trend, compare, peakValley, heatmap, alerts, advice] = await Promise.allSettled([
    api.get('/energy/trend?hours=24'),
    api.get('/energy/comparison?hours=24'),
    api.get('/energy/peak-valley?hours=24'),
    api.get('/energy/heatmap?hours=24'),
    api.get('/energy/alerts'),
    api.get('/energy/advice'),
  ])
  if (trend.status === 'fulfilled') trendData.value = trend.value.data.data || []
  if (compare.status === 'fulfilled') compareData.value = compare.value.data.data || []
  if (peakValley.status === 'fulfilled') peakValleyData.value = peakValley.value.data.data || {}
  if (heatmap.status === 'fulfilled') heatmapData.value = heatmap.value.data.data || []
  if (alerts.status === 'fulfilled') alertData.value = alerts.value.data.data || {}
  if (advice.status === 'fulfilled') adviceList.value = advice.value.data.data || []
}

function logout() {
  localStorage.removeItem('token')
  localStorage.removeItem('username')
  router.push('/login')
}

onMounted(loadData)
</script>

<style scoped>
.dashboard { padding: 16px 24px; background: #f5f7fa; min-height: 100vh; }
.header {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 20px; padding: 12px 20px;
  background: #fff; border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,.08);
}
.header h1 { font-size: 18px; color: #303133; margin: 0; }
.user-info { display: flex; align-items: center; gap: 12px; color: #606266; }
.chart-row { margin-bottom: 16px; }
.chart-row .el-col > div, .chart-row .el-col > *:first-child {
  background: #fff; border-radius: 8px; padding: 12px;
  box-shadow: 0 1px 4px rgba(0,0,0,.08);
}
.advice-card { margin-top: 8px; }
</style>
