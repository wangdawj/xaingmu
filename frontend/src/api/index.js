/**
 * Axios HTTP 客户端
 * =================
 * 统一的 API 请求实例，所有请求以 /api 为基础路径。
 */

import axios from 'axios'

const api = axios.create({
  baseURL: '/api',      // 所有请求自动拼接 /api 前缀
  timeout: 15000,       // 15 秒超时
})

export default api
