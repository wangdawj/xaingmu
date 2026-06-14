<!--
  校区能耗热力图组件
  ================
  ECharts 热力图 — 以区域(Rows) × 建筑(Cols) 矩阵展示能耗分布密度。
  颜色越深表示平均能耗越高。
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

// 建筑名称中文映射表
const BUILDING_NAMES = {
  B001: '教学楼A', B002: '行政楼', B003: '学生宿舍1号楼',
  B005: '食堂', B006: '图书馆',
}

const getOption = () => {
  if (!props.data.length) return null
  // 去重后的区域和建筑列表
  const regions = [...new Set(props.data.map(d => d.region_id))]
  const buildings = [...new Set(props.data.map(d => d.building_id))]

  // 转换为 [regionIndex, buildingIndex, value] 格式
  const heatData = props.data.map(d => [
    regions.indexOf(d.region_id),
    buildings.indexOf(d.building_id),
    d.value,
  ])

  return {
    title: { text: '校区能耗热力图', left: 'center', textStyle: { fontSize: 14 } },
    tooltip: {
      formatter: (p) => {
        const b = buildings[p.data[1]]
        return `${BUILDING_NAMES[b] || b}<br/>平均能耗: ${p.data[2]} kWh`
      },
    },
    grid: { left: 80, right: 40, top: 50, bottom: 40 },
    xAxis: { type: 'category', data: regions, name: '区域' },
    yAxis: { type: 'category', data: buildings.map(b => BUILDING_NAMES[b] || b) },
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
  }
}

const { chartRef, render } = useEChartsRaw(getOption)
watch(() => props.data, render, { deep: true })
</script>

<style scoped>
.chart { width: 100%; height: 310px; }
</style>
