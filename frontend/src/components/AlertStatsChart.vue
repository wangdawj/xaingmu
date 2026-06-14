<!--
  告警统计图组件
  ============
  柱状图 — 按严重级别（信息/警告/严重）展示告警数量分布。
-->
<template>
  <div ref="chartRef" class="chart"></div>
</template>

<script setup>
import { watch } from 'vue'
import { useEChartsRaw } from '../composables/useECharts'

const props = defineProps({
  data: { type: Object, default: () => ({ severity_count: {} }) },
})

const getOption = () => {
  const sc = props.data.severity_count || {}
  return {
    title: { text: '异常预警统计', left: 'center', textStyle: { fontSize: 14 } },
    tooltip: { trigger: 'axis' },
    grid: { left: 50, right: 20, top: 50, bottom: 30 },
    xAxis: { type: 'category', data: ['信息', '警告', '严重'] },
    yAxis: { type: 'value', name: '次数' },
    series: [{
      type: 'bar',
      data: [
        { value: sc.info || 0, itemStyle: { color: '#909399' } },
        { value: sc.warning || 0, itemStyle: { color: '#E6A23C' } },
        { value: sc.critical || 0, itemStyle: { color: '#F56C6C' } },
      ],
    }],
  }
}

const { chartRef, render } = useEChartsRaw(getOption)
watch(() => props.data, render, { deep: true })
</script>

<style scoped>
.chart { width: 100%; height: 310px; }
</style>
