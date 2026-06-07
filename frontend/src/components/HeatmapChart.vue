<template>
  <div ref="chartRef" class="chart"></div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue'
import * as echarts from 'echarts'

const props = defineProps({
  data: { type: Array, default: () => [] },
})

const chartRef = ref(null)
let chart = null

const BUILDING_NAMES = {
  B001: '第一教学楼', B002: '第二教学楼', B003: '1号宿舍楼',
  B004: '2号宿舍楼', B005: '中心图书馆', B006: '第一食堂',
}

function render() {
  if (!chartRef.value) return
  if (!chart) chart = echarts.init(chartRef.value)

  const regions = [...new Set(props.data.map(d => d.region_id))]
  const buildings = [...new Set(props.data.map(d => d.building_id))]
  const heatData = props.data.map(d => [
    regions.indexOf(d.region_id),
    buildings.indexOf(d.building_id),
    d.value,
  ])

  chart.setOption({
    title: { text: '校区能耗热力图', left: 'center', textStyle: { fontSize: 14 } },
    tooltip: {
      formatter: (p) => {
        const b = buildings[p.data[1]]
        return `${BUILDING_NAMES[b] || b}<br/>平均能耗: ${p.data[2]} kWh`
      },
    },
    grid: { left: 80, right: 40, top: 50, bottom: 40 },
    xAxis: { type: 'category', data: regions, name: '区域' },
    yAxis: {
      type: 'category',
      data: buildings.map(b => BUILDING_NAMES[b] || b),
    },
    visualMap: {
      min: 0,
      max: Math.max(...props.data.map(d => d.value), 100),
      calculable: true,
      orient: 'horizontal',
      left: 'center',
      bottom: 0,
      inRange: { color: ['#e0f3f8', '#abd9e9', '#74add1', '#4575b4', '#313695'] },
    },
    series: [{
      type: 'heatmap',
      data: heatData,
      label: { show: true, formatter: (p) => p.data[2] },
    }],
  })
}

watch(() => props.data, render, { deep: true })
onMounted(() => { render(); window.addEventListener('resize', () => chart?.resize()) })
onUnmounted(() => { chart?.dispose() })
</script>

<style scoped>
.chart { width: 100%; height: 310px; }
</style>
