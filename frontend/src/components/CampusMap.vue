<template>
  <el-card class="campus-map-card" shadow="hover">
    <div class="campus-map">
      <svg viewBox="0 0 800 500" class="topo-svg">
        <!-- 道路/草地背景 -->
        <rect x="0" y="0" width="800" height="500" fill="#e8f5e9" rx="8" />
        <!-- 主干道 -->
        <line x1="0" y1="300" x2="800" y2="300" stroke="#bdbdbd" stroke-width="12" />
        <line x1="400" y1="0" x2="400" y2="500" stroke="#bdbdbd" stroke-width="10" />
        <!-- 操场 -->
        <ellipse cx="650" cy="120" rx="100" ry="55" fill="#a5d6a7" stroke="#66bb6a" stroke-width="2" />
        <text x="650" y="125" text-anchor="middle" font-size="10" fill="#388e3c">运动场</text>

        <!-- 动态渲染建筑 -->
        <g v-for="(b, idx) in buildings" :key="b.building_id" @click="$emit('select', b.building_id)">
          <rect
            :x="getPos(idx).x"
            :y="getPos(idx).y"
            width="90"
            height="55"
            rx="6"
            :fill="getFillColor(b.status)"
            :stroke="b.status === 'critical' ? '#ff4d4f' : b.status === 'warning' ? '#fa8c16' : '#52c41a'"
            stroke-width="2"
            class="building-rect"
          >
            <animate
              v-if="b.status === 'critical'"
              attributeName="stroke-opacity"
              values="0.4;1;0.4" dur="1.5s" repeatCount="indefinite"
            />
          </rect>
          <text
            :x="getPos(idx).x + 45"
            :y="getPos(idx).y + 22"
            text-anchor="middle" font-size="11" font-weight="bold"
            fill="#fff"
          >{{ b.building_name }}</text>
          <text
            :x="getPos(idx).x + 45"
            :y="getPos(idx).y + 42"
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
import { ref, onMounted, onUnmounted } from 'vue'
import api from '../api'

const props = defineProps({ buildings: { type: Array, default: () => [] } })
const emit = defineEmits(['select'])

// 8 个预定义建筑位置
const layout = [
  { x: 50,  y: 60  },   // B001
  { x: 170, y: 60  },   // B002
  { x: 290, y: 60  },   // B003
  { x: 50,  y: 180 },   // B004
  { x: 170, y: 180 },   // B005
  { x: 290, y: 180 },   // B006
  { x: 50,  y: 340 },   // B007
  { x: 170, y: 340 },   // B008
]

function getPos(idx) { return layout[idx] || { x: 50 + (idx % 3) * 120, y: 60 + Math.floor(idx / 3) * 130 } }
function getFillColor(status) {
  if (status === 'critical') return 'rgba(255,77,79,.85)'
  if (status === 'warning') return 'rgba(250,140,22,.85)'
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
