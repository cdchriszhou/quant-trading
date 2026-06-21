<template>
  <div style="min-height: 100vh; display: flex; align-items: center; justify-content: center; background: linear-gradient(135deg, #1f2d3d 0%, #324057 100%)">
    <el-card style="width: 420px; padding: 20px">
      <div style="text-align: center; margin-bottom: 30px">
        <el-icon :size="48" color="#409EFF"><TrendCharts /></el-icon>
        <h2 style="margin-top: 12px; color: #303133">量化交易系统</h2>
        <p style="color: #909399; font-size: 14px">基于Vue+Python的全流程量化交易平台</p>
      </div>
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top" @keyup.enter="handleLogin">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" placeholder="请输入用户名" :prefix-icon="User" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input v-model="form.password" type="password" show-password placeholder="请输入密码" :prefix-icon="Lock" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" style="width: 100%" :loading="loading" @click="handleLogin">登 录</el-button>
        </el-form-item>
        <div style="text-align: center">
          <el-button text type="primary" @click="handleRegister">还没有账号？立即注册</el-button>
        </div>
        <div style="margin-top: 12px; text-align: center; color: #909399; font-size: 12px">
          演示账号: admin / admin123
        </div>
      </el-form>
    </el-card>

    <el-dialog v-model="showRegister" title="注册账号" width="400px">
      <el-form ref="regFormRef" :model="regForm" :rules="regRules" label-position="top">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="regForm.username" placeholder="请输入用户名" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input v-model="regForm.password" type="password" show-password placeholder="请输入密码" />
        </el-form-item>
        <el-form-item label="确认密码" prop="confirmPassword">
          <el-input v-model="regForm.confirmPassword" type="password" show-password placeholder="请确认密码" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showRegister = false">取消</el-button>
        <el-button type="primary" :loading="regLoading" @click="handleRegisterSubmit">注册</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { User, Lock } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'
import { authApi } from '@/api/auth'
import { ElMessage } from 'element-plus'

const router = useRouter()
const userStore = useUserStore()
const loading = ref(false)
const regLoading = ref(false)
const showRegister = ref(false)

const form = reactive({ username: 'admin', password: 'admin123' })
const regForm = reactive({ username: '', password: '', confirmPassword: '' })

const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}
const regRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, min: 6, message: '密码至少6位', trigger: 'blur' }],
  confirmPassword: [
    { required: true, message: '请确认密码', trigger: 'blur' },
    { validator: (rule, value, callback) => {
      if (value !== regForm.password) callback(new Error('两次密码不一致'))
      else callback()
    }, trigger: 'blur' },
  ],
}

async function handleLogin() {
  loading.value = true
  try {
    const res = await authApi.login(form)
    userStore.setUser(res.user, res.access_token)
    ElMessage.success('登录成功')
    router.push('/dashboard')
  } catch (err) {
    ElMessage.error(err.response?.data?.detail || '登录失败')
  } finally {
    loading.value = false
  }
}

function handleRegister() {
  showRegister.value = true
}

async function handleRegisterSubmit() {
  regLoading.value = true
  try {
    await authApi.register({
      username: regForm.username,
      password: regForm.password,
    })
    ElMessage.success('注册成功，请登录')
    showRegister.value = false
    form.username = regForm.username
  } catch (err) {
    ElMessage.error(err.response?.data?.detail || '注册失败')
  } finally {
    regLoading.value = false
  }
}
</script>
