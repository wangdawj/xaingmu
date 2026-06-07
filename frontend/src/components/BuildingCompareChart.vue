<template>
  <div ref="chartRef" class="chart"></div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue'
import * as echarts from 'echarts'

const props = defineProps({
  data: { type: Array, default: () => [] },
})
const emit = defineEmits(['bar-click'])

const chartRef = ref(null)
let chart = null

function render() {
  if (!chartRef.value) return
  if (!chart) chart = echarts.init(chartRef.value)

  chart.setOption({
    title: { text: '楼宇能耗对比', left: 'center', textStyle: { fontSize: 14 } },
    tooltip: { trigger: 'axis' },
    grid: { left: 60, right: 20, top: 50, bottom: 60 },
    xAxis: {
      type: 'category',
      data: props.data.map(d => d.building_name || d.building_id),
      axisLabel: { rotate: 30 },
    },
    yAxis: { type: 'value', name: 'kWh' },
    series: [{
      type: 'bar',
      data: props.data.map(d => d.total),
      itemStyle: {
        color: (p) => ['#5470c6', '#91cc75', '#fac858', '#ee6666', '#73c0de'][p.dataIndex % 5],
      },
    }],
  })
}

watch(() => props.data, render, { deep: true })
onMounted(() => {
  render()
  window.addEventListener('resize', () => chart?.resize())
  setTimeout(() => {
    if (chart) {
      chart.off('click')
      chart.on('click', (p) => {
        if (p.dataIndex != null && props.data[p.dataIndex]) {
          emit('bar-click', props.data[p.dataIndex].building_id)
        }
      })
    }
  }, 300)
})
onUnmounted(() => { chart?.dispose() })
</script>

<style scoped>
.chart { width: 100%; height: 310px; }
</style>
