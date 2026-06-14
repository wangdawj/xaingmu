<!--
  能耗预测图组件
  ============
  展示未来 24 小时能耗预测（线性回归 vs 随机森林）
  + 模型评估指标（MAE / R²）+ 特征重要性。
-->
<template>
  <div class="forecast-wrap">
    <div ref="chartRef" class="chart"></div>
    <div class="metrics-row">
      <div class="metric-item">
        <span class="metric-label">岭回归 MAE</span>
        <span class="metric-val">{{ metrics.lr_mae }}</span>
      </div>
      <div class="metric-item">
        <span class="metric-label">岭回归 R²</span>
        <span class="metric-val">{{ metrics.lr_r2 }}</span>
      </div>
      <div class="metric-item">
        <span class="metric-label">随机森林 MAE</span>
        <span class="metric-val">{{ metrics.rf_mae }}</span>
      </div>
      <div class="metric-item">
        <span class="metric-label">随机森林 R²</span>
        <span class="metric-val">{{ metrics.rf_r2 }}</span>
      </div>
      <div class="metric-item">
        <span class="metric-label">训练样本</span>
        <span class="metric-val">{{ metrics.samples }}</span>
      </div>
      <div class="metric-item">
        <span class="metric-label">数据来源</span>
        <span class="metric-val" style="font-size:11px">{{ metrics.source }}</span>
      </div>
    </div>
    <div class="feat-row" v-if="features.length">
      <span class="feat-title">特征重要性：</span>
      <span v-for="(f, i) in features" :key="f.feature" class="feat-tag">
        {{ f.feature }}
        <el-progress :percentage="Math.round(f.importance * 100)" :stroke-width="6"
          style="width:60px;display:inline-flex;vertical-align:middle" />
      </span>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { useEChartsRaw } from '../composables/useECharts'

const props = defineProps({
  data: { type: Object, default: () => ({}) },
})

// 提取模型指标
const metrics = computed(() => {
  const d = props.data
  if (!d.metrics) return { lr_mae: '-', lr_r2: '-', rf_mae: '-', rf_r2: '-', samples: '-' }
  const m = d.metrics
  return {
    lr_mae: m.ridge_regression?.mae ?? '-',
    lr_r2: m.ridge_regression?.r2 ?? '-',
    rf_mae: m.random_forest?.mae ?? '-',
    rf_r2: m.random_forest?.r2 ?? '-',
    samples: m.train_samples ? m.train_samples + '/' + m.test_samples : '-',
    source: m.data_source ?? '-',
  }
})

const features = computed(() => props.data.feature_importance || [])

const getOption = () => {
  const fc = props.data.forecast || []
  if (!fc.length) return null
  return {
    title: { text: '能耗预测 · 未来 24 小时', left: 'center', textStyle: { fontSize: 14 } },
    tooltip: { trigger: 'axis' },
    legend: { data: ['岭回归', '随机森林'], bottom: 0 },
    grid: { left: 50, right: 20, top: 50, bottom: 40 },
    xAxis: { type: 'category', data: fc.map(f => f.time), boundaryGap: false },
    yAxis: { type: 'value', name: 'kWh', min: val => Math.max(0, Math.floor((val.min - 20) / 50) * 50) },
    series: [
      {
        name: '岭回归', type: 'line', smooth: true,
        data: fc.map(f => f.predicted_lr),
        lineStyle: { color: '#1890ff', width: 2 },
        itemStyle: { color: '#1890ff' },
      },
      {
        name: '随机森林', type: 'line', smooth: true,
        data: fc.map(f => f.predicted_rf),
        lineStyle: { color: '#52c41a', width: 2 },
        itemStyle: { color: '#52c41a' },
      },
    ],
  }
}

const { chartRef, render } = useEChartsRaw(getOption)
watch(() => props.data, render, { deep: true })
</script>

<style scoped>
.forecast-wrap { width: 100%; }
.chart { width: 100%; height: 280px; }
.metrics-row {
  display: flex; gap: 16px; justify-content: center; flex-wrap: wrap;
  padding: 8px 0 4px;
}
.metric-item {
  text-align: center; padding: 6px 14px;
  background: #f5f7fa; border-radius: 8px;
}
.metric-label { font-size: 11px; color: #909399; display: block; }
.metric-val { font-size: 16px; font-weight: 700; color: #303133; }
.feat-row {
  display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
  padding: 4px 0 0; justify-content: center;
}
.feat-title { font-size: 12px; color: #909399; }
.feat-tag {
  font-size: 11px; color: #606266; display: inline-flex; align-items: center; gap: 4px;
  background: #f0f2f5; padding: 2px 8px; border-radius: 4px;
}
</style>
