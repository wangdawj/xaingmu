<!--
  校园拓扑图组件
  ============
  使用 SVG 绘制校园建筑平面布局，实时展示各建筑运行状态。
  - 绿色边框：正常 | 橙色边框：预警 | 红色边框（闪烁）：告警
  - 点击建筑可跳转到建筑详情页
-->
<template>
  <el-card class="campus-map-card" shadow="hover">
    <div class="campus-map">
      <svg viewBox="0 0 800 500" class="topo-svg">
        <!-- 草地背景 -->
        <rect x="0" y="0" width="800" height="500" fill="#e8f5e9" rx="8" />

        <!-- 主干道（十字交叉） -->
        <line x1="0" y1="300" x2="800" y2="300" stroke="#bdbdbd" stroke-width="12" />
        <line x1="400" y1="0" x2="400" y2="500" stroke="#bdbdbd" stroke-width="10" />

        <!-- 运动场 -->
        <ellipse cx="650" cy="120" rx="100" ry="55" fill="#a5d6a7" stroke="#66bb6a" stroke-width="2" />
        <text x="650" y="125" text-anchor="middle" font-size="10" fill="#388e3c">运动场</text>

        <!-- 动态渲染建筑（绑定 campusLayout 位置 + API 实时状态） -->
        <g v-for="b in visibleBuildings" :key="b.building_id" @click="$emit('select', b.building_id)">
          <!-- 建筑矩形 -->
          <rect
            :x="b.layout.x"
            :y="b.layout.y"
            :width="b.layout.width"
            :height="b.layout.height"
            rx="6"
            :fill="getFillColor(b)"
            :stroke="b.status === 'critical' ? '#ff4d4f' : b.status === 'warning' ? '#fa8c16' : '#52c41a'"
            stroke-width="2"
            class="building-rect"
          >
            <!-- critical 状态时边框闪烁动画 -->
            <animate
              v-if="b.status === 'critical'"
              attributeName="stroke-opacity"
              values="0.4;1;0.4" dur="1.5s" repeatCount="indefinite"
            />
          </rect>
          <!-- 建筑名称 -->
          <text
            :x="b.layout.x + b.layout.width / 2"
            :y="b.layout.y + 22"
            text-anchor="middle" font-size="11" font-weight="bold"
            fill="#fff"
          >{{ b.building_name }}</text>
          <!-- 当前功率 -->
          <text
            :x="b.layout.x + b.layout.width / 2"
            :y="b.layout.y + 42"
            text-anchor="middle" font-size="10"
            :fill="b.status === 'critical' ? '#fff' : '#e8f5e9'"
          >{{ b.current_power }} kW</text>
        </g>

        <!-- 图例 -->
        <g transform="translate(600, 430)">
          <rect x="0" y="0" width="14" height="14" rx="2" fill="#52c41a" />
          <text x="18" y="12" font-size="11" fill="#333">正常</text>
          <rect x="60" y="0" width="14" height="14" rx="2" fill="#fa8c16" />
          <text x="78" y="12" font-size="11" fill="#333">预警</text>
          <rect x="120" y="0" width="14" height="14" rx="2" fill="#ff4d4f">
            <animate attributeName="opacity" values="0.6;1;0.6" dur="1s" repeatCount="indefinite" />
          </rect>
          <text x="138" y="12" font-size="11" fill="#333">告警</text>
        </g>
      </svg>
    </div>
  </el-card>
</template>

<script setup>
import { computed } from 'vue'
import { campusLayout } from '../config/campusLayout'

const props = defineProps({ buildings: { type: Array, default: () => [] } })
defineEmits(['select'])

/**
 * 将 API 返回的建筑数据与 campusLayout 布局信息合并
 * 未配置布局的建筑使用默认位置
 */
const visibleBuildings = computed(() => {
  return props.buildings.map(b => {
    const layout = campusLayout.find(l => l.building_id === b.building_id) || {
      x: 50, y: 60, width: 90, height: 55,
    }
    return { ...b, layout }
  })
})

/**
 * 根据建筑状态返回填充色
 * critical(告警) → 红色 | warning(预警) → 橙色 | normal → 蓝色
 */
function getFillColor(b) {
  if (b.status === 'critical') return 'rgba(255,77,79,.85)'
  if (b.status === 'warning') return 'rgba(250,140,22,.85)'
  return 'rgba(24,144,255,.75)'
}
</script>

<style scoped>
.campus-map-card { cursor: default; }
.campus-map { display: flex; justify-content: center; }
.topo-svg { width: 100%; max-width: 800px; height: auto; }
.building-rect { cursor: pointer; transition: opacity .2s; }
.building-rect:hover { opacity: .65; }
</style>
