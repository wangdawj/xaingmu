<template>
  <div class="login-page">
    <!-- 背景动画 -->
    <div class="bg-shapes">
      <div class="shape shape-1"></div>
      <div class="shape shape-2"></div>
      <div class="shape shape-3"></div>
    </div>

    <div class="login-container">
      <div class="brand">
        <div class="logo-icon">
          <svg viewBox="0 0 48 48" width="48" height="48"><rect x="8" y="22" width="8" height="18" rx="1.5" fill="#fff" opacity=".9"/><rect x="20" y="14" width="8" height="26" rx="1.5" fill="#fff" opacity=".9"/><rect x="32" y="8" width="8" height="32" rx="1.5" fill="#fff" opacity=".9"/><circle cx="16" cy="20" r="3" fill="#ffd666"/><circle cx="28" cy="12" r="3" fill="#ffd666"/><circle cx="40" cy="5" r="3" fill="#ffd666"/></svg>
        </div>
        <h1>校园能耗监测平台</h1>
        <p>Campus Energy Monitoring System</p>
      </div>
      <el-card class="login-card" shadow="never">
        <el-form @submit.prevent="handleLogin" size="large">
          <el-form-item>
            <el-input
              v-model="form.username"
              placeholder="用户名"
              prefix-icon="User"
              clearable
            />
          </el-form-item>
          <el-form-item>
            <el-input
              v-model="form.password"
              type="password"
              placeholder="密码"
              prefix-icon="Lock"
              show-password
            />
          </el-form-item>
          <el-form-item>
            <el-button
              type="primary"
              native-type="submit"
              :loading="loading"
              round
              class="login-btn"
            >
              {{ loading ? '登录中...' : '登 录' }}
            </el-button>
          </el-form-item>
        </el-form>
        <div class="hint">默认账号 admin / admin123</div>
      </el-card>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '../api'

const router = useRouter()
const loading = ref(false)
const form = reactive({ username: 'admin', password: 'admin123' })

async function handleLogin() {
  loading.value = true
  try {
    const { data } = await api.post('/auth/login', form)
    if (data.code === 0) {
      localStorage.setItem('token', data.data.token)
      localStorage.setItem('username', data.data.username)
      ElMessage.success('登录成功')
      router.push('/')
    } else {
      ElMessage.error(data.message)
    }
  } catch {
    ElMessage.error('登录失败，请检查后端服务')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh; display: flex; align-items: center; justify-content: center;
  background: linear-gradient(135deg, #0c2646 0%, #134e7a 30%, #1a6e9f 60%, #1890ff 100%);
  position: relative; overflow: hidden;
}
/* 背景动画形状 */
.bg-shapes { position: absolute; inset: 0; }
.shape { position: absolute; border-radius: 50%; opacity: .06; background: #fff; }
.shape-1 { width: 600px; height: 600px; top: -200px; left: -100px; animation: float 20s ease-in-out infinite; }
.shape-2 { width: 400px; height: 400px; bottom: -100px; right: -50px; animation: float 15s ease-in-out infinite reverse; }
.shape-3 { width: 300px; height: 300px; top: 50%; left: 50%; animation: float 18s ease-in-out infinite .5s; }
@keyframes float {
  0%, 100% { transform: translate(0, 0) scale(1); }
  33% { transform: translate(30px, -30px) scale(1.05); }
  66% { transform: translate(-20px, 20px) scale(.95); }
}

.login-container { position: relative; z-index: 1; text-align: center; }
.brand { margin-bottom: 30px; }
.logo-icon {
  width: 72px; height: 72px; margin: 0 auto 16px;
  background: rgba(255,255,255,.15); border-radius: 18px;
  display: flex; align-items: center; justify-content: center;
  backdrop-filter: blur(10px);
}
.brand h1 { font-size: 26px; color: #fff; font-weight: 700; letter-spacing: 2px; margin-bottom: 6px; }
.brand p { font-size: 13px; color: rgba(255,255,255,.65); letter-spacing: 3px; text-transform: uppercase; }

.login-card {
  width: 400px; padding: 12px 24px 20px;
  background: rgba(255,255,255,.95) !important;
  backdrop-filter: blur(20px);
  border-radius: 16px !important;
}
.login-card :deep(.el-card__body) { padding: 20px 4px; }

.login-btn { width: 100%; height: 44px; font-size: 16px; letter-spacing: 4px; }

.hint { text-align: center; color: #bfbfbf; font-size: 12px; margin-top: 4px; }
</style>
