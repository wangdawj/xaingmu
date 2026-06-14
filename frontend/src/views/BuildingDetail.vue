<!--
  建筑详情页
  =========
  展示单体建筑完整信息：基本信息 / 24h 曲线 / 分项能耗 / 历史环比
-->
<template>
  <div class="detail" v-loading="loading">
    <!-- 顶栏 -->
    <header class="top-bar">
      <el-button link @click="$router.push('/')">← 返回总览</el-button>
      <h1>{{ info.building_name || '加载中...' }}</h1>
      <el-tag size="small" :type="stType">{{ stLabel }}</el-tag>
    </header>

    <!-- 基本信息 -->
    <el-row :gutter="12" class="info-row">
      <el-col :span="6"><div class="info-card"><div class="info-label">建筑类型</div><div class="info-val">{{ info.building_type || '-' }}</div></div></el-col>
      <el-col :span="6"><div class="info-card"><div class="info-label">建筑面积</div><div class="info-val">{{ info.build_area || 0 }} <small>m²</small></div></div></el-col>
      <el-col :span="6"><div class="info-card"><div class="info-label">楼层数</div><div class="info-val">{{ info.floor_count || 0 }} <small>层</small></div></div></el-col>
      <el-col :span="6"><div class="info-card"><div class="info-label">容纳人数</div><div class="info-val">{{ info.max_occupancy || '-' }} <small>人</small></div></div></el-col>
    </el-row>

    <!-- 能耗摘要 -->
    <el-row :gutter="12" class="sum-row">
      <el-col :span="8">
        <div class="sum-card blue"><span class="sum-icon">⚡</span><div><div class="sum-label">24h 总用电</div><div class="sum-val">{{ fmt(summary.total) }} <small>kWh</small></div></div></div>
      </el-col>
      <el-col :span="8">
        <div class="sum-card orange"><span class="sum-icon">📈</span><div><div class="sum-label">峰值功率</div><div class="sum-val">{{ fmt(summary.peak) }} <small>kW</small></div></div></div>
      </el-col>
      <el-col :span="8">
        <div class="sum-card green"><span class="sum-icon">📊</span><div><div class="sum-label">平均功率</div><div class="sum-val">{{ fmt(summary.avg) }} <small>kW</small></div></div></div>
      </el-col>
    </el-row>

    <!-- 图表行1：24h曲线 + 分项能耗 -->
    <el-row :gutter="12" class="chart-row">
      <el-col :span="16">
        <el-card shadow="never">
          <template #header>24 小时用电曲线</template>
          <div ref="crv" class="chart-box"></div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="never">
          <template #header>分项能耗占比</template>
          <div ref="sub" class="chart-box" style="height:340px"></div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 历史环比（仅数据存在时显示） -->
    <el-card shadow="never" class="comp-card" v-if="comp.today != null">
      <template #header>历史环比</template>
      <el-row :gutter="12">
        <el-col :span="6"><div class="comp-item"><div class="comp-label">今日用电</div><div class="comp-val">{{ fmt(comp.today) }} kWh</div></div></el-col>
        <el-col :span="6"><div class="comp-item"><div class="comp-label">昨日用电</div><div class="comp-val">{{ fmt(comp.yesterday) }} kWh</div><div class="comp-chg" :class="comp.day_change>0?'up':'down'" v-if="comp.day_change!=null">{{ comp.day_change>0?'+':'' }}{{ comp.day_change }}%</div></div></el-col>
        <el-col :span="6"><div class="comp-item"><div class="comp-label">本周累计</div><div class="comp-val">{{ fmt(comp.this_week) }} kWh</div></div></el-col>
        <el-col :span="6"><div class="comp-item"><div class="comp-label">上周累计</div><div class="comp-val">{{ fmt(comp.last_week) }} kWh</div><div class="comp-chg" :class="comp.week_change>0?'up':'down'" v-if="comp.week_change!=null">{{ comp.week_change>0?'+':'' }}{{ comp.week_change }}%</div></div></el-col>
      </el-row>
    </el-card>

    <!-- 节能建议 -->
    <el-card shadow="never" v-if="adviceList.length" class="advice-card">
      <template #header>节能建议</template>
      <el-table :data="adviceList" stripe size="small">
        <el-table-column prop="title" label="建议" min-width="160" />
        <el-table-column prop="content" label="具体内容" min-width="260" show-overflow-tooltip />
        <el-table-column prop="estimated_save" label="预估节能" width="100" align="center">
          <template #default="{row}"><span class="save-pct">{{ row.estimated_save }}%</span></template>
        </el-table-column>
        <el-table-column prop="priority" label="优先级" width="80" align="center">
          <template #default="{row}">
            <el-tag :type="row.priority==='high'?'danger':'warning'" size="small">{{ row.priority==='high'?'高':'中' }}</el-tag>
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
const crv = ref(null)
const sub = ref(null)
let c1 = null, c2 = null

const loading = ref(false)
const info = ref({})
const summary = ref({ total: 0, peak: 0, avg: 0 })
const adviceList = ref([])
const comp = ref({ today: null, yesterday: 0, this_week: 0, last_week: 0, day_change: null, week_change: null })

const stType = computed(() => summary.value.peak > 200 ? 'danger' : summary.value.peak > 100 ? 'warning' : 'success')
const stLabel = computed(() => summary.value.peak > 200 ? '高负荷' : summary.value.peak > 100 ? '中等' : '正常')

function fmt(v) {
  if (v == null || isNaN(v)) return '0'
  return Number(v).toLocaleString('zh-CN', { maximumFractionDigits: 1 })
}

async function load() {
  loading.value = true
  const bid = route.params.buildingId
  const [d, a, s, c] = await Promise.allSettled([
    api.get(`/energy/building/${bid}/detail`),
    api.get(`/energy/advice?building_id=${bid}`),
    api.get(`/energy/building/${bid}/sub-items`),
    api.get(`/energy/building/${bid}/comparison`),
  ])
  if (d.status === 'fulfilled' && d.value.data.code === 0) {
    const dt = d.value.data.data
    info.value = dt; summary.value = dt.summary
    renderCurve(dt.curve)
  }
  if (a.status === 'fulfilled') adviceList.value = a.value.data.data || []
  if (s.status === 'fulfilled' && s.value.data.code === 0) renderSub(s.value.data.data || [])
  if (c.status === 'fulfilled' && c.value.data.code === 0) comp.value = c.value.data.data
  loading.value = false
}

function renderCurve(curve) {
  if (!crv.value) return
  if (!c1) c1 = echarts.init(crv.value)
  const times = curve.map(d => d.time)
  const vals = curve.map(d => d.value)
  c1.setOption({
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: times, axisLabel: { rotate: 45, fontSize: 10 } },
    yAxis: { type: 'value', name: 'kW' },
    dataZoom: [{ type: 'inside' }, { type: 'slider', height: 20, bottom: 6 }],
    series: [{
      type: 'line', data: vals, smooth: true,
      areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
        { offset: 0, color: 'rgba(24,144,255,.35)' }, { offset: 1, color: 'rgba(24,144,255,.02)' }
      ])},
      lineStyle: { color: '#1890ff', width: 2 },
      itemStyle: { color: '#1890ff' },
      markLine: { silent: true, data: [{ type: 'average', name: '均值', label: { formatter: '均值 {c} kW' } }], lineStyle: { color: '#faad14', type: 'dashed' } },
    }],
    grid: { left: 50, right: 20, top: 30, bottom: 50 },
  })
}

function renderSub(items) {
  if (!sub.value) return
  if (!c2) c2 = echarts.init(sub.value)
  c2.setOption({
    tooltip: { trigger: 'item', formatter: '{b}: {c} kWh ({d}%)' },
    legend: { bottom: 0, textStyle: { fontSize: 11 } },
    series: [{
      type: 'pie', radius: ['45%', '72%'], center: ['50%', '45%'],
      data: items.map(s => ({ name: s.label, value: s.value })),
      label: { formatter: '{b}\n{d}%', fontSize: 11 },
      itemStyle: { color: (p) => ['#1890ff', '#fa8c16', '#52c41a'][p.dataIndex % 3] },
      emphasis: { itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0,0,0,.3)' } },
    }],
  })
}

function handleResize() { c1?.resize(); c2?.resize() }

onMounted(() => { load(); window.addEventListener('resize', handleResize) })
onUnmounted(() => { window.removeEventListener('resize', handleResize); c1?.dispose(); c2?.dispose() })
</script>

<style scoped>
.detail { padding: 16px 20px; background: var(--bg); min-height: 100vh; }
.top-bar {
  display: flex; justify-content: space-between; align-items: center;
  height: 50px; padding: 0 16px; margin-bottom: 14px;
  background: var(--card-bg); border-radius: var(--radius); box-shadow: var(--shadow);
}
.top-bar h1 { font-size: 16px; font-weight: 600; margin: 0; color: var(--text); }
.info-row { margin-bottom: 10px; }
.info-card {
  background: var(--card-bg); border-radius: var(--radius);
  box-shadow: var(--shadow); padding: 14px 16px;
  transition: box-shadow .2s;
}
.info-card:hover { box-shadow: var(--shadow-hover); }
.info-label { font-size: 11px; color: var(--text-secondary); margin-bottom: 4px; }
.info-val { font-size: 20px; font-weight: 700; color: var(--text); line-height: 1.2; }
.info-val small { font-size: 12px; font-weight: 400; color: var(--text-secondary); }

.sum-row { margin-bottom: 10px; }
.sum-card {
  display: flex; align-items: center; gap: 12px;
  padding: 14px 16px; border-radius: var(--radius);
  background: var(--card-bg); box-shadow: var(--shadow);
  transition: transform .2s, box-shadow .2s;
}
.sum-card:hover { transform: translateY(-2px); box-shadow: var(--shadow-hover); }
.sum-icon { font-size: 22px; flex-shrink: 0; }
.sum-label { font-size: 11px; color: var(--text-secondary); margin-bottom: 2px; }
.sum-val { font-size: 22px; font-weight: 700; color: var(--text); line-height: 1.1; }
.sum-val small { font-size: 12px; font-weight: 400; color: var(--text-secondary); }

.chart-row { margin-bottom: 10px; }
.chart-box { width: 100%; height: 360px; }

.comp-card { margin-bottom: 10px; }
.comp-item { text-align: center; padding: 8px 0; }
.comp-label { font-size: 11px; color: var(--text-secondary); margin-bottom: 4px; }
.comp-val { font-size: 20px; font-weight: 700; color: var(--text); line-height: 1.2; }
.comp-chg { font-size: 12px; margin-top: 2px; font-weight: 600; }
.comp-chg.up { color: var(--danger); }
.comp-chg.down { color: var(--success); }

.advice-card { margin-bottom: 10px; }
.save-pct { color: var(--success); font-weight: 600; }
</style>
