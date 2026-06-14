<!--
=============================================================================
能耗预测图组件（ForecastChart.vue）
=============================================================================
【组件职责】
  展示后端 /api/energy/forecast 接口的返回结果：
    1. 折线图：未来 24 小时能耗预测（岭回归 vs 随机森林 双曲线对比）
    2. 指标卡片：两个模型的 MAE（平均绝对误差）和 R²（决定系数）
    3. 特征重要性：随机森林输出的各特征对预测的贡献度（进度条展示）

【数据来源】
  Dashboard.vue 每 5 秒轮询 /api/energy/forecast，将返回的 data 对象传进来。

【双模型对比的意义】
  - 岭回归（蓝色线）：线性模型，容易解释，但无法捕捉非线性关系
  - 随机森林（绿色线）：非线性模型，拟合能力更强，但解释性弱
  - 两条线重合度高 → 结果可信；偏差大 → 需检查数据或特征
=============================================================================
-->

<template>
  <div class="forecast-wrap">
    <!-- ECharts 图表容器：绑定 chartRef 用于初始化 -->
    <div ref="chartRef" class="chart"></div>

    <!-- 模型评估指标：5 个卡片横向排列 -->
    <div class="metrics-row">
      <!-- 岭回归 MAE：平均绝对误差，越小越好 -->
      <div class="metric-item">
        <span class="metric-label">岭回归 MAE</span>
        <span class="metric-val">{{ metrics.lr_mae }}</span>
      </div>
      <!-- 岭回归 R²：决定系数 0~1，越接近 1 拟合越好 -->
      <div class="metric-item">
        <span class="metric-label">岭回归 R²</span>
        <span class="metric-val">{{ metrics.lr_r2 }}</span>
      </div>
      <!-- 随机森林 MAE -->
      <div class="metric-item">
        <span class="metric-label">随机森林 MAE</span>
        <span class="metric-val">{{ metrics.rf_mae }}</span>
      </div>
      <!-- 随机森林 R² -->
      <div class="metric-item">
        <span class="metric-label">随机森林 R²</span>
        <span class="metric-val">{{ metrics.rf_r2 }}</span>
      </div>
      <!-- 训练/测试样本数 -->
      <div class="metric-item">
        <span class="metric-label">训练样本</span>
        <span class="metric-val">{{ metrics.samples }}</span>
      </div>
      <!-- 数据来源标签 -->
      <div class="metric-item">
        <span class="metric-label">数据来源</span>
        <span class="metric-val" style="font-size:11px">{{ metrics.source }}</span>
      </div>
    </div>

    <!-- 特征重要性：仅当有数据时显示 -->
    <div class="feat-row" v-if="features.length">
      <span class="feat-title">特征重要性：</span>
      <!-- v-for 循环渲染每个特征的标签 + 进度条 -->
      <span v-for="(f, i) in features" :key="f.feature" class="feat-tag">
        {{ f.feature }}
        <!-- el-progress 显示重要性百分比，importance 是 0~1 的小数需 ×100 -->
        <el-progress
          :percentage="Math.round(f.importance * 100)"
          :stroke-width="6"
          style="width:60px;display:inline-flex;vertical-align:middle"
        />
      </span>
    </div>
  </div>
</template>

<!-- ======================== 组件逻辑 ======================== -->
<script setup>
import { computed, watch } from 'vue'
// 使用通用图表 composable（非标准 X/Y 轴图表版本）
import { useEChartsRaw } from '../composables/useECharts'

// 接收父组件传入的预测数据
const props = defineProps({
  data: { type: Object, default: () => ({}) },
})

// ======================== 计算属性 ========================

/**
 * 从 API 返回的 data.metrics 中提取模型指标
 *
 * 数据结构示例：
 *   {
 *     "ridge_regression": { "mae": 16.31, "r2": 0.8322 },
 *     "random_forest":     { "mae": 16.24, "r2": 0.8273 },
 *     "train_samples": 424, "test_samples": 106,
 *     "data_source": "B001 real(194)+synth(336)"
 *   }
 *
 * 使用 ?. 可选链 + ?? 空值合并：数据不存在时显示 "-" 而非报错
 */
const metrics = computed(() => {
  const d = props.data
  if (!d.metrics) return { lr_mae: '-', lr_r2: '-', rf_mae: '-', rf_r2: '-', samples: '-' }
  const m = d.metrics
  return {
    lr_mae: m.ridge_regression?.mae ?? '-',    // 岭回归 MAE
    lr_r2: m.ridge_regression?.r2 ?? '-',       // 岭回归 R²
    rf_mae: m.random_forest?.mae ?? '-',        // 随机森林 MAE
    rf_r2: m.random_forest?.r2 ?? '-',          // 随机森林 R²
    samples: m.train_samples ? m.train_samples + '/' + m.test_samples : '-',  // "训练数/测试数"
    source: m.data_source ?? '-',               // 数据来源标签
  }
})

/** 特征重要性数组，如 [{feature:"是否白天", importance:0.89}, ...] */
const features = computed(() => props.data.feature_importance || [])

// ======================== ECharts 配置 ========================

/**
 * 构建 ECharts 配置对象
 *
 * 图表结构：
 *   - 横轴：未来 24 小时的时间标签（如 "12:00", "13:00", ...）
 *   - 纵轴：预测功率值（kWh）
 *   - 两条折线：
 *     蓝色(lineStyle: '#1890ff') → 岭回归预测值
 *     绿色(lineStyle: '#52c41a') → 随机森林预测值
 *
 * Y 轴最小值动态计算：确保不会出现负值（min: val => Math.max(0, ...)）
 */
const getOption = () => {
  const fc = props.data.forecast || []   // 预测数组 [{time, predicted_lr, predicted_rf}, ...]
  if (!fc.length) return null            // 无数据时返回 null，不渲染

  return {
    // 标题：居中，字体大小 14px
    title: { text: '能耗预测 · 未来 24 小时', left: 'center', textStyle: { fontSize: 14 } },
    tooltip: { trigger: 'axis' },         // 鼠标悬停：显示同时间两条线的数值
    legend: { data: ['岭回归', '随机森林'], bottom: 0 },  // 图例放底部
    grid: { left: 50, right: 20, top: 50, bottom: 40 },  // 图表边距
    xAxis: {
      type: 'category',
      data: fc.map(f => f.time),          // 横轴：["12:00", "13:00", ...]
      boundaryGap: false,                 // 折线从轴线起点开始（不留空隙）
    },
    yAxis: {
      type: 'value',
      name: 'kWh',
      // 动态计算 Y 轴最小值：确保底部 > 0（防止负值影响显示）
      min: val => Math.max(0, Math.floor((val.min - 20) / 50) * 50),
    },
    series: [
      {
        name: '岭回归',                   // 图例名称
        type: 'line',                     // 折线图
        smooth: true,                     // 平滑曲线（贝塞尔插值）
        data: fc.map(f => f.predicted_lr),// 数据：[119.56, 121.67, ...]
        lineStyle: { color: '#1890ff', width: 2 },  // 蓝色线
        itemStyle: { color: '#1890ff' },
      },
      {
        name: '随机森林',
        type: 'line',
        smooth: true,
        data: fc.map(f => f.predicted_rf),
        lineStyle: { color: '#52c41a', width: 2 },  // 绿色线
        itemStyle: { color: '#52c41a' },
      },
    ],
  }
}

// ======================== ECharts 初始化 ========================

// 使用通用 composable：传入 getOption 函数，返回 chartRef 和 render
const { chartRef, render } = useEChartsRaw(getOption)

// 监听 props.data 变化 → 自动重新渲染图表（deep: true 确保深层字段变化也触发）
watch(() => props.data, render, { deep: true })
</script>

<!-- ======================== 样式 ======================== -->
<style scoped>
.forecast-wrap { width: 100%; }
.chart { width: 100%; height: 280px; }  /* 图表区高度固定 280px */

/* 指标卡片行：flex 布局 + 居中对齐 + 换行 */
.metrics-row {
  display: flex; gap: 16px; justify-content: center; flex-wrap: wrap;
  padding: 8px 0 4px;
}
/* 单个指标卡片 */
.metric-item {
  text-align: center; padding: 6px 14px;
  background: #f5f7fa; border-radius: 8px;
}
.metric-label { font-size: 11px; color: #909399; display: block; }  /* 标签 */
.metric-val { font-size: 16px; font-weight: 700; color: #303133; }  /* 数值 */

/* 特征重要性行 */
.feat-row {
  display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
  padding: 4px 0 0; justify-content: center;
}
.feat-title { font-size: 12px; color: #909399; }
.feat-tag {
  font-size: 11px; color: #606266; display: inline-flex; align-items: center; gap: 4px;
  background: #f0f2f5; padding: 2px 8px; border-radius: 4px;
}
</style>
