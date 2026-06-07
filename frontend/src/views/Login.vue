<template>
  <div class="login-page">
    <el-card class="login-card">
      <h2>校园能耗监测平台</h2>
      <el-form @submit.prevent="handleLogin">
        <el-form-item>
          <el-input v-model="form.username" placeholder="用户名" prefix-icon="User" />
        </el-form-item>
        <el-form-item>
          <el-input v-model="form.password" type="password" placeholder="密码" show-password />
        </el-form-item>
        <el-button type="primary" native-type="submit" :loading="loading" style="width:100%">
          登录
        </el-button>
      </el-form>
      <p class="hint">默认账号: admin / admin123</p>
    </el-card>
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
  } catch (e) {
    ElMessage.error('登录失败，请检查后端服务')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #1a5276 0%, #2ecc71 100%);
}
.login-card {
  width: 380px;
  padding: 20px;
}
.login-card h2 {
  text-align: center;
  margin-bottom: 24px;
  color: #303133;
}
.hint {
  text-align: center;
  color: #909399;
  font-size: 12px;
  margin-top: 16px;
}
</style>
