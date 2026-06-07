<template>
  <div ref="chartRef" class="chart"></div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue'
import * as echarts from 'echarts'

const props = defineProps({
  data: { type: Array, default: () => [] },
  title: { type: String, default: '全校能耗趋势' },
})

const chartRef = ref(null)
let chart = null

function render() {
  if (!chartRef.value) return
  if (!chart) chart = echarts.init(chartRef.value)

  const times = props.data.map(d => d.time?.slice(11, 16) || d.time)
  const values = props.data.map(d => d.value)

  chart.setOption({
    title: { text: props.title, left: 'center', textStyle: { fontSize: 14 } },
    tooltip: { trigger: 'axis' },
    grid: { left: 50, right: 20, top: 50, bottom: 30 },
    xAxis: { type: 'category', data: times, boundaryGap: false },
    yAxis: { type: 'value', name: 'kWh' },
    series: [{
      name: '能耗',
      type: 'line',
      smooth: true,
      areaStyle: { opacity: 0.15 },
      data: values,
      itemStyle: { color: '#409EFF' },
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
