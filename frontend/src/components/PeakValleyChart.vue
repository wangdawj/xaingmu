<!--
  峰谷用电占比图组件
  ================
  环形饼图 — 展示峰时段(8-22点)和谷时段(22-次日8点)的用电占比。
-->
<template>
  <div ref="chartRef" class="chart"></div>
</template>

<script setup>
import { watch } from 'vue'
import { useEChartsRaw } from '../composables/useECharts'

const props = defineProps({
  data: { type: Object, default: () => ({ peak: 0, valley: 0 }) },
})

const getOption = () => ({
  title: { text: '用电峰谷占比', left: 'center', textStyle: { fontSize: 14 } },
  tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
  legend: { bottom: 0 },
  series: [{
    type: 'pie',
    radius: ['40%', '65%'],
    data: [
      { name: '峰时段', value: props.data.peak || 0 },
      { name: '谷时段', value: props.data.valley || 0 },
    ],
    label: { formatter: '{b}\n{d}%' },
  }],
})

const { chartRef, render } = useEChartsRaw(getOption)
watch(() => props.data, render, { deep: true })
</script>

<style scoped>
.chart { width: 100%; height: 310px; }
</style>
