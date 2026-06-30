<template>
  <div style="min-height: 100vh; display: flex; align-items: center; justify-content: center; background: linear-gradient(135deg, #f0f5f5 0%, #e8f0f0 50%, #f5f6f8 100%)">
    <el-card style="width: 100%; max-width: 400px; margin: 0 16px; border-radius: 12px; border: 1px solid #e5e7eb">
      <div style="text-align: center; margin-bottom: 28px">
        <div style="font-size: 32px; font-weight: 900; color: #00B4B4; letter-spacing: 4px; margin-bottom: 4px">QUANT</div>
        <div style="font-size: 13px; color: #9ca3af; letter-spacing: 2px">量化交易系统</div>
      </div>
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top" @keyup.enter="handleLogin">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" placeholder="请输入用户名" :prefix-icon="User" size="large" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input v-model="form.password" type="password" show-password placeholder="请输入密码" :prefix-icon="Lock" size="large" />
        </el-form-item>
        <el-form-item style="margin-top: 8px">
          <el-button type="primary" style="width: 100%; height: 42px; font-weight: 700; font-size: 15px; letter-spacing: 2px" :loading="loading" @click="handleLogin">登 录</el-button>
        </el-form-item>
        <div style="text-align: center">
          <el-button text type="primary" @click="handleRegister">还没有账号？立即注册</el-button>
        </div>
      </el-form>
    </el-card>

    <el-dialog v-model="showRegister" title="注册账号" width="400px" :close-on-click-modal="false">
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

const form = reactive({ username: '', password: '' })
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

function handleRegister() { showRegister.value = true }

async function handleRegisterSubmit() {
  regLoading.value = true
  try {
    await authApi.register({ username: regForm.username, password: regForm.password })
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
