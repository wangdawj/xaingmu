<!--
  能耗趋势图组件
  ============
  基于 ECharts 的平滑折线图，展示能耗随时间的变化趋势。
  使用 useECharts 组合式函数，自动响应 data 变化。
-->
<template>
  <div ref="chartRef" class="chart"></div>
</template>

<script setup>
import { useECharts } from '../composables/useECharts'

const props = defineProps({
  data: { type: Array, default: () => [] },
})

// 使用标准图表封装：提取时间轴和数据轴
const { chartRef } = useECharts(props, (p) => ({
  xAxis: p.data.map(d => d.time?.slice(11, 16) || d.time),  // 取 HH:mm 作为 X 轴标签
  series: [{
    name: '能耗',
    type: 'line',
    smooth: true,           // 平滑曲线
    areaStyle: { opacity: 0.15 },  // 半透明面积填充
    data: p.data.map(d => d.value),
    itemStyle: { color: '#409EFF' },
  }],
}))
</script>

<style scoped>
.chart { width: 100%; height: 310px; }
</style>
