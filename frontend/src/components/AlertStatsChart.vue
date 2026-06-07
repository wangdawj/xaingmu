<template>
  <div ref="chartRef" class="chart"></div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue'
import * as echarts from 'echarts'

const props = defineProps({
  data: { type: Object, default: () => ({ severity_count: {} }) },
})

const chartRef = ref(null)
let chart = null

function render() {
  if (!chartRef.value) return
  if (!chart) chart = echarts.init(chartRef.value)

  const sc = props.data.severity_count || {}
  chart.setOption({
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
  })
}

watch(() => props.data, render, { deep: true })
onMounted(() => { render(); window.addEventListener('resize', () => chart?.resize()) })
onUnmounted(() => { chart?.dispose() })
</script>

<style scoped>
.chart { width: 100%; height: 320px; }
</style>
