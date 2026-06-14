/**
 * ECharts 组合式函数（Composables）
 * =================================
 * 封装 ECharts 图表的初始化、渲染、自适应大小和销毁生命周期。
 *
 * 提供两个版本：
 * - useECharts:      适用于标准 X/Y 轴图表（折线图等）
 * - useEChartsRaw:   适用于非标准图表（柱状图、饼图、热力图等）
 */

import { ref, watch, onMounted, onUnmounted } from 'vue'
import * as echarts from 'echarts'

/**
 * 适用于标准 X/Y 轴图表的封装
 *
 * @param {Object} props - 组件 props（需包含 data）
 * @param {Function} getDataFn - (props) => ({ xAxis, series }) 数据提取函数
 * @returns {{ chartRef }} 模板引用对象
 */
export function useECharts(props, getDataFn) {
  const chartRef = ref(null)
  let chart = null

  /** 渲染图表：初始化 ECharts 实例并设置 option */
  function render() {
    if (!chartRef.value) return
    if (!chart) chart = echarts.init(chartRef.value)

    const { xAxis, series } = getDataFn(props)
    chart.setOption({
      tooltip: { trigger: 'axis' },
      grid: { left: 50, right: 20, top: 50, bottom: 60 },
      dataZoom: [
        { type: 'inside', start: 0, end: 100 },              // 鼠标滚轮缩放
        { type: 'slider', start: 0, end: 100, height: 20, bottom: 6 },  // 底部滑块
      ],
      xAxis: { type: 'category', data: xAxis, boundaryGap: false },
      yAxis: { type: 'value', name: 'kWh' },
      series,
    }, { replaceMerge: ['series'] })  // 仅替换 series，保留其他配置
  }

  /** 图表自适应大小 */
  function resize() {
    chart?.resize()
  }

  // 监听 data 变化自动重新渲染
  watch(() => props.data, render, { deep: true })

  // 挂载时初始化 + 注册 resize 监听
  onMounted(() => {
    render()
    window.addEventListener('resize', resize)
  })

  // 卸载时清理
  onUnmounted(() => {
    window.removeEventListener('resize', resize)
    chart?.dispose()
  })

  return { chartRef }
}

/**
 * 适用于非标准（非 xy 轴）图表的通用封装
 *
 * @param {Function} getOptionFn - () => ECharts option 对象
 * @param {Object} events - { eventName: handler } 可选事件绑定（如 click）
 * @returns {{ chartRef, render }} 模板引用对象 + 手动渲染函数
 */
export function useEChartsRaw(getOptionFn, events = {}, watchSource = null) {
  const chartRef = ref(null)
  let chart = null

  /** 渲染图表：初始化 ECharts 实例并绑定事件 */
  function render() {
    if (!chartRef.value) return
    if (!chart) {
      chart = echarts.init(chartRef.value)
      // 绑定自定义事件（如 click 回调）
      Object.entries(events).forEach(([name, handler]) => {
        chart.on(name, handler)
      })
    }
    const opt = getOptionFn()
    if (opt) chart.setOption(opt, { replaceMerge: ['series'] })
  }

  /** 图表自适应大小 */
  function resize() {
    chart?.resize()
  }

  // 监听数据源变化，自动重新渲染
  if (watchSource) {
    watch(watchSource, () => {
      render()
    }, { deep: true })
  }

  onMounted(() => {
    render()
    window.addEventListener('resize', resize)
  })

  onUnmounted(() => {
    window.removeEventListener('resize', resize)
    chart?.dispose()
  })

  return { chartRef, render }
}
