/**
 * 应用入口文件
 * ==========
 * 创建 Vue 3 应用实例，挂载 Element Plus UI 库和 Vue Router。
 */

import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import App from './App.vue'
import router from './router'

// 创建 Vue 应用 → 注册 Element Plus → 注册路由 → 挂载到 #app
createApp(App).use(ElementPlus).use(router).mount('#app')
