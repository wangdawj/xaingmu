<template>
  <div class="building-detail">
    <!-- 顶栏 -->
    <header class="header">
      <el-button link type="primary" @click="$router.push('/')" class="back-btn">
        <el-icon><ArrowLeft /></el-icon> 返回总览
      </el-button>
      <h1 class="header-title">{{ info.building_name || '加载中...' }}</h1>
      <el-tag size="small" :type="statusType" effect="plain">{{ statusLabel }}</el-tag>
    </header>

    <!-- 基本信息 -->
    <el-row :gutter="16" class="info-row">
      <el-col :span="6">
        <div class="info-card">
          <div class="info-card__label">建筑类型</div>
          <div class="info-card__value">{{ info.building_type || '-' }}</div>
        </div>
      </el-col>
      <el-col :span="6">
        <div class="info-card">
          <div class="info-card__label">建筑面积</div>
          <div class="info-card__value">{{ info.build_area || 0 }} <small>m²</small></div>
        </div>
      </el-col>
      <el-col :span="6">
        <div class="info-card">
          <div class="info-card__label">楼层数</div>
          <div class="info-card__value">{{ info.floor_count || 0 }} <small>层</small></div>
        </div>
      </el-col>
      <el-col :span="6">
        <div class="info-card">
          <div class="info-card__label">容纳人数</div>
          <div class="info-card__value">{{ info.max_occupancy || '-' }} <small>人</small></div>
        </div>
      </el-col>
    </el-row>

    <!-- 能耗摘要 -->
    <el-row :gutter="16" class="summary-row">
      <el-col :span="8">
        <div class="summary-card summary-card--blue">
          <svg viewBox="0 0 32 32" width="24" height="24" class="summary-card__icon"><path d="M13 4L5 14h6v14h4V14h6L13 4z" fill="var(--primary)"/></svg>
          <div class="summary-card__info">
            <div class="summary-card__label">24h 总用电量</div>
            <div class="summary-card__value">{{ fmtNum(summary.total) }} <small>kWh</small></div>
          </div>
        </div>
      </el-col>
      <el-col :span="8">
        <div class="summary-card summary-card--orange">
          <svg viewBox="0 0 32 32" width="24" height="24"><polyline points="4,26 10,18 16,22 22,10 28,6" fill="none" stroke="var(--warning)" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/><circle cx="10" cy="18" r="2" fill="var(--warning)"/><circle cx="22" cy="10" r="2" fill="var(--warning)"/></svg>
          <div class="summary-card__info">
            <div class="summary-card__label">峰值功率</div>
            <div class="summary-card__value">{{ fmtNum(summary.peak) }} <small>kW</small></div>
          </div>
        </div>
      </el-col>
      <el-col :span="8">
        <div class="summary-card summary-card--green">
          <svg viewBox="0 0 32 32" width="24" height="24"><rect x="4" y="6" width="24" height="20" rx="2" fill="none" stroke="var(--success)" stroke-width="2"/><line x1="12" y1="14" x2="12" y2="14" stroke="var(--success)" stroke-width="8" stroke-linecap="round"/><line x1="17" y1="18" x2="17" y2="18" stroke="var(--success)" stroke-width="8" stroke-linecap="round"/><line x1="22" y1="11" x2="22" y2="11" stroke="var(--success)" stroke-width="8" stroke-linecap="round"/></svg>
          <div class="summary-card__info">
            <div class="summary-card__label">平均功率</div>
            <div class="summary-card__value">{{ fmtNum(summary.avg) }} <small>kW</small></div>
          </div>
        </div>
      </el-col>
    </el-row>

    <!-- 24h 曲线 + 分项能耗 -->
    <el-row :gutter="16" class="chart-row">
      <el-col :span="16">
        <el-card shadow="never" class="chart-card">
          <template #header>
            <div class="card-header">
              <span class="card-header__title">24 小时用电曲线</span>
              <el-tag size="small" type="info">数据粒度为小时</el-tag>
            </div>
          </template>
          <div ref="curveChartRef" class="chart-container"></div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="never" class="chart-card">
          <template #header><span class="card-header__title">分项能耗占比</span></template>
          <div ref="subChartRef" class="sub-chart-container"></div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 历史环比 -->
    <el-card shadow="never" class="comparison-card" v-if="comparison.today != null">
      <template #header><span>历史环比</span></template>
      <el-row :gutter="16">
        <el-col :span="6">
          <div class="comp-item">
            <div class="comp-item__label">今日用电</div>
            <div class="comp-item__value">{{ fmtNum(comparison.today) }} kWh</div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="comp-item">
            <div class="comp-item__label">昨日用电</div>
            <div class="comp-item__value">{{ fmtNum(comparison.yesterday) }} kWh</div>
            <div class="comp-item__change" :class="comparison.day_change > 0 ? 'up' : 'down'" v-if="comparison.day_change != null">
              {{ comparison.day_change > 0 ? '+' : '' }}{{ comparison.day_change }}%
            </div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="comp-item">
            <div class="comp-item__label">本周累计</div>
            <div class="comp-item__value">{{ fmtNum(comparison.this_week) }} kWh</div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="comp-item">
            <div class="comp-item__label">上周累计</div>
            <div class="comp-item__value">{{ fmtNum(comparison.last_week) }} kWh</div>
            <div class="comp-item__change" :class="comparison.week_change > 0 ? 'up' : 'down'" v-if="comparison.week_change != null">
              {{ comparison.week_change > 0 ? '+' : '' }}{{ comparison.week_change }}%
            </div>
          </div>
        </el-col>
      </el-row>
    </el-card>

    <!-- 节能建议 -->
    <el-card shadow="never" class="advice-card" v-if="adviceList.length > 0">
      <template #header><span>节能建议</span></template>
      <el-table :data="adviceList" stripe size="small">
        <el-table-column prop="title" label="建议" min-width="180" />
        <el-table-column prop="content" label="具体内容" min-width="300" />
        <el-table-column prop="estimated_save" label="预估节能" width="100" align="center">
          <template #default="{ row }">
            <span class="save-tag">{{ row.estimated_save }}%</span>
          </template>
        </el-table-column>
        <el-table-column prop="priority" label="优先级" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="row.priority === 'high' ? 'danger' : 'warning'" size="small">
              {{ row.priority === 'high' ? '高' : '中' }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import * as echarts from 'echarts'
import api from '../api'

const route = useRoute()
const curveChartRef = ref(null)
const subChartRef = ref(null)
let curveChart = null
let subChart = null

const info = ref({})
const summary = ref({ total: 0, peak: 0, avg: 0 })
const adviceList = ref([])
const comparison = ref({ today: null, yesterday: 0, this_week: 0, last_week: 0, day_change: null, week_change: null })

const statusType = computed(() => {
  if (summary.value.peak > 200) return 'danger'
  if (summary.value.peak > 100) return 'warning'
  return 'success'
})
const statusLabel = computed(() => {
  if (summary.value.peak > 200) return '高负荷'
  if (summary.value.peak > 100) return '中等'
  return '正常'
})

function fmtNum(v) {
  if (v == null) return '0'
  return Number(v).toLocaleString('zh-CN', { maximumFractionDigits: 1 })
}

async function loadData() {
  const buildingId = route.params.buildingId
  const [detail, advice, subRes, compRes] = await Promise.allSettled([
    api.get(`/energy/building/${buildingId}/detail`),
    api.get(`/energy/advice?building_id=${buildingId}`),
    api.get(`/energy/building/${buildingId}/sub-items`),
    api.get(`/energy/building/${buildingId}/comparison`),
  ])

  if (detail.status === 'fulfilled' && detail.value.data.code === 0) {
    const d = detail.value.data.data
    info.value = d
    summary.value = d.summary
    renderCurveChart(d.curve)
  }
  if (advice.status === 'fulfilled') {
    adviceList.value = advice.value.data.data || []
  }
  if (subRes.status === 'fulfilled' && subRes.value.data.code === 0) {
    renderSubChart(subRes.value.data.data || [])
  }
  if (compRes.status === 'fulfilled' && compRes.value.data.code === 0) {
    comparison.value = compRes.value.data.data
  }
}

function renderCurveChart(curve) {
  if (!curveChartRef.value) return
  if (!curveChart) {
    curveChart = echarts.init(curveChartRef.value)
  }
  const times = curve.map(c => c.time)
  const values = curve.map(c => c.value)
  curveChart.setOption({
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: times, axisLabel: { rotate: 45, fontSize: 10 } },
    yAxis: { type: 'value', name: 'kW' },
    dataZoom: [{ type: 'inside' }, { type: 'slider', height: 20, bottom: 6 }],
    series: [{
      type: 'line',
      data: values,
      smooth: true,
      areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
        { offset: 0, color: 'rgba(24,144,255,.35)' }, { offset: 1, color: 'rgba(24,144,255,.02)' }
      ])},
      lineStyle: { color: '#1890ff', width: 2 },
      itemStyle: { color: '#1890ff' },
      markLine: {
        silent: true,
        data: [{ type: 'average', name: '均值', label: { formatter: '均值 {c} kW' } }],
        lineStyle: { color: '#faad14', type: 'dashed' }
      }
    }],
    grid: { left: 50, right: 20, top: 30, bottom: 50 },
  })
}

function renderSubChart(subItems) {
  if (!subChartRef.value) return
  if (!subChart) {
    subChart = echarts.init(subChartRef.value)
  }
  const pieData = subItems.map(s => ({ name: s.label, value: s.value }))
  subChart.setOption({
    tooltip: { trigger: 'item', formatter: '{b}: {c} kWh ({d}%)' },
    legend: { bottom: 0, textStyle: { fontSize: 11 } },
    series: [{
      type: 'pie',
      radius: ['45%', '72%'],
      center: ['50%', '45%'],
      data: pieData,
      label: { formatter: '{b}\n{d}%', fontSize: 11 },
      itemStyle: {
        color: (p) => ['#1890ff', '#fa8c16', '#52c41a'][p.dataIndex % 3],
      },
      emphasis: {
        itemStyle: { shadowBlur: 10, shadowOffsetX: 0, shadowColor: 'rgba(0,0,0,.3)' }
      }
    }],
  })
}

function handleResize() {
  curveChart?.resize()
  subChart?.resize()
}

onMounted(() => {
  loadData()
  window.addEventListener('resize', handleResize)
})
onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  curveChart?.dispose()
  subChart?.dispose()
})
</script>

<style scoped>
.building-detail { padding: 20px 24px; background: var(--bg); min-height: 100vh; }

/* 顶栏 */
.header {
  display: flex; justify-content: space-between; align-items: center;
  height: 56px; padding: 0 20px; margin-bottom: 20px;
  background: var(--card-bg); border-radius: var(--radius); box-shadow: var(--shadow);
}
.back-btn { font-size: 13px; }
.header-title { font-size: 17px; font-weight: 600; color: var(--text); margin: 0; flex: 1; text-align: center; }

/* 基本信息卡片 */
.info-row { margin-bottom: 16px; }
.info-card {
  background: var(--card-bg); border-radius: var(--radius);
  box-shadow: var(--shadow); padding: 16px 20px;
  transition: box-shadow .25s;
}
.info-card:hover { box-shadow: var(--shadow-hover); }
.info-card__label { font-size: 12px; color: var(--text-secondary); margin-bottom: 6px; }
.info-card__value { font-size: 22px; font-weight: 700; color: var(--text); line-height: 1.2; }
.info-card__value small { font-size: 13px; font-weight: 400; color: var(--text-secondary); }

/* 能耗摘要卡片 */
.summary-row { margin-bottom: 16px; }
.summary-card {
  display: flex; align-items: center; gap: 14px;
  padding: 18px 20px; border-radius: var(--radius);
  background: var(--card-bg); box-shadow: var(--shadow);
  transition: box-shadow .25s, transform .25s;
}
.summary-card:hover { box-shadow: var(--shadow-hover); transform: translateY(-2px); }
.summary-card__icon { flex-shrink: 0; }
.summary-card__label { font-size: 12px; color: var(--text-secondary); margin-bottom: 4px; }
.summary-card__value { font-size: 26px; font-weight: 700; color: var(--text); line-height: 1.1; }
.summary-card__value small { font-size: 13px; font-weight: 400; color: var(--text-secondary); }

/* 图表行 */
.chart-row { margin-bottom: 16px; }
.chart-card { height: 100%; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.card-header__title { font-weight: 600; }
.chart-container { width: 100%; height: 400px; }
.sub-chart-container { width: 100%; height: 360px; }

/* 历史环比 */
.comparison-card { margin-bottom: 16px; }
.comp-item { text-align: center; padding: 12px 0; }
.comp-item__label { font-size: 12px; color: var(--text-secondary); margin-bottom: 6px; }
.comp-item__value { font-size: 22px; font-weight: 700; color: var(--text); line-height: 1.2; }
.comp-item__change { font-size: 13px; margin-top: 4px; font-weight: 600; }
.comp-item__change.up { color: var(--danger); }
.comp-item__change.down { color: var(--success); }

.advice-card { margin-bottom: 16px; }
.save-tag { color: var(--success); font-weight: 600; }
</style>
