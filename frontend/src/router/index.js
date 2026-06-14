/**
 * Vue Router 路由配置
 * /                     → 仪表盘总览
 * /building/:buildingId → 建筑详情
 */
import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/building/:buildingId',
      component: () => import('../views/BuildingDetail.vue'),
    },
    {
      path: '/',
      component: () => import('../views/Dashboard.vue'),
    },
  ],
})

export default router
