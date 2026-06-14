<!--
  楼宇能耗对比图组件
  柱状图 — 各建筑总能耗对比，点击柱子可跳转到建筑详情页。
-->
<template>
  <div ref="chartRef" class="chart"></div>
</template>

<script setup>
import { watch } from 'vue'
import { useEChartsRaw } from '../composables/useECharts'

const props = defineProps({
  data: { type: Array, default: () => [] },
})

const emit = defineEmits(['bar-click'])

const getOption = () => ({
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

// 使用通用图表封装：自定义 option + click 事件 + 响应式数据监听
useEChartsRaw(getOption, {
  click: (p) => {
    if (p.dataIndex != null && props.data[p.dataIndex]) {
      emit('bar-click', props.data[p.dataIndex].building_id)
    }
  },
}, () => props.data)
</script>

<style scoped>
.chart { width: 100%; height: 310px; }
</style>
