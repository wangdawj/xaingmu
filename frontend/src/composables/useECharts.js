/**
 * =========================================================================
 * useECharts — ECharts 组合式函数（Vue Composables）
 * =========================================================================
 * 【为什么抽离成 Composable？】
 *   ECharts 图表的生命周期管理（init → setOption → watch data → resize → dispose）
 *   在每个组件中重复，抽离后只需一行 useECharts(props, getDataFn) 即可。
 *
 * 【提供两个版本】
 *   1. useECharts    — 适用于标准 X/Y 轴图表（折线图、趋势图）
 *   2. useEChartsRaw — 适用于非标准图表（饼图、柱状图、热力图）
 *
 * 【两个版本的区别】
 *
 *   useECharts(props, getDataFn):
 *     - 入参是 props 和 getDataFn 函数
 *     - 内部预设了 tooltip、grid、dataZoom、xAxis、yAxis 等通用配置
 *     - 组件只需提供 xAxis.data 和 series 数据即可
 *     - 自动 watch props.data → 重新渲染
 *
 *   useEChartsRaw(getOptionFn, events, watchSource):
 *     - 入参是 getOptionFn 函数（返回完整 ECharts option）
 *     - 不预设任何配置，完全由组件自行定义 option
 *     - 支持绑定自定义事件（如 click）
 *     - 需要手动传入 watchSource 来监听数据变化
 */
import { ref, watch, onMounted, onUnmounted } from 'vue'
import * as echarts from 'echarts'

/**
 * =========================================================================
 * useECharts — 标准 X/Y 轴图表封装
 * =========================================================================
 * 自动处理：初始化、数据更新渲染、dataZoom 缩放、窗口 resize 自适应、销毁清理。
 *
 * 使用示例：
 *   const props = defineProps({ data: Array })
 *   const getData = (p) => ({
 *     xAxis: p.data.map(d => d.time),        // 横轴时间标签
 *     series: [{ type: 'line', data: ... }],  // 系列数据
 *   })
 *   const { chartRef } = useECharts(props, getData)
 *
 * @param {Object}   props     - 组件 props（需包含 data 字段）
 * @param {Function} getDataFn - (props) => ({ xAxis: Array, series: Array }) 数据提取函数
 * @returns {{ chartRef }}     - 模板 ref 对象，在模板中绑定 <div ref="chartRef">
 */
export function useECharts(props, getDataFn) {
  const chartRef = ref(null)   // 模板引用（绑定到 DOM 元素）
  let chart = null             // ECharts 实例（init 后赋值）

  /** 渲染图表 */
  function render() {
    if (!chartRef.value) return
    // 首次渲染时初始化 ECharts 实例，后续复用
    if (!chart) chart = echarts.init(chartRef.value)

    // 从 getDataFn 提取数据
    const { xAxis, series } = getDataFn(props)

    // setOption 设置图表配置
    chart.setOption(
      {
        tooltip: { trigger: 'axis' },                         // 鼠标悬停提示（轴线触发）
        grid: { left: 50, right: 20, top: 50, bottom: 60 },   // 图表边距
        dataZoom: [
          { type: 'inside', start: 0, end: 100 },             // 鼠标滚轮缩放（内部缩放）
          { type: 'slider', start: 0, end: 100, height: 20, bottom: 6 }, // 底部滑块缩放条
        ],
        xAxis: { type: 'category', data: xAxis, boundaryGap: false }, // 类目轴（时间标签）
        yAxis: { type: 'value', name: 'kWh' },                // 数值轴（功率单位 kWh）
        series,                                                // 系列数据（折线/柱状）
      },
      { replaceMerge: ['series'] }  // 数据更新时只替换 series，不重建 dataZoom 等其他配置
    )
  }

  /** 响应窗口 resize 事件，图表自适应宽度 */
  function resize() {
    chart?.resize()   // ECharts 内置的 resize 方法
  }

  // ---- 生命周期管理 ----

  // 深度监听 props.data：数据变化时自动重新渲染
  // deep: true 保证了数组/对象内部字段变化也能触发
  watch(() => props.data, render, { deep: true })

  // 组件挂载时：首次渲染 + 注册 resize 监听
  onMounted(() => {
    render()
    window.addEventListener('resize', resize)
  })

  // 组件卸载时：移除监听 + 销毁图表实例（释放内存）
  onUnmounted(() => {
    window.removeEventListener('resize', resize)
    chart?.dispose()   // dispose 释放 ECharts 分配的 DOM 和事件资源
  })

  return { chartRef }
}

/**
 * =========================================================================
 * useEChartsRaw — 通用图表封装（饼图/柱状图/热力图等）
 * =========================================================================
 * 与 useECharts 的区别：
 *   - 不预设 tooltip/grid/xAxis/yAxis 等配置，完全由 getOptionFn 自定义
 *   - 支持绑定 ECharts 事件（如 chart.on('click', handler)）
 *   - 使用 watchSource 参数指定要监听的数据源
 *
 * 使用示例（饼图）：
 *   const getOption = () => ({
 *     series: [{ type: 'pie', data: [{ name: '峰', value: 100 }, ...] }]
 *   })
 *   const { chartRef, render } = useEChartsRaw(getOption)
 *   // 手动触发：watch(() => props.data, render, { deep: true })
 *
 * @param {Function} getOptionFn - () => ECharts option 对象（每次调用返回最新配置）
 * @param {Object}   events      - { eventName: handler } 事件绑定（可选）
 * @param {*}        watchSource - 要 watch 的数据源（可选，传了自动监听）
 * @returns {{ chartRef, render }} - 模板 ref + 手动渲染函数
 */
export function useEChartsRaw(getOptionFn, events = {}, watchSource = null) {
  const chartRef = ref(null)
  let chart = null

  /** 渲染图表 */
  function render() {
    if (!chartRef.value) return
    // 首次渲染时初始化实例 + 绑定事件
    if (!chart) {
      chart = echarts.init(chartRef.value)
      // 绑定自定义事件（如 click、legendselectchanged 等）
      Object.entries(events).forEach(([name, handler]) => {
        chart.on(name, handler)
      })
    }
    // 调用 getOptionFn 获取最新 option（支持 computed 等响应式数据）
    const opt = getOptionFn()
    // 如果返回 null 则跳过渲染（数据为空时的保护）
    if (opt) chart.setOption(opt, { replaceMerge: ['series'] })
  }

  /** 响应窗口 resize */
  function resize() {
    chart?.resize()
  }

  // 如果传了 watchSource，自动监听数据变化重新渲染
  // 适用场景：父组件传入的 props 变化时需要 chart 自动更新
  if (watchSource) {
    watch(watchSource, () => {
      render()
    }, { deep: true })
  }

  // ---- 生命周期管理 ----
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
