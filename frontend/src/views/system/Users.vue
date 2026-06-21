<template>
  <el-card shadow="never">
    <template #header><span style="font-weight: bold">用户管理</span></template>
    <el-table :data="users" stripe size="small">
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="username" label="用户名" width="120" />
      <el-table-column prop="display_name" label="显示名" width="120" />
      <el-table-column prop="email" label="邮箱" width="180" />
      <el-table-column prop="role" label="角色" width="80">
        <template #default="{ row }">
          <el-tag :type="row.role === 'admin' ? 'danger' : 'primary'" size="small">{{ row.role === 'admin' ? '管理员' : '用户' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="80">
        <template #default="{ row }">
          <el-switch v-model="row.is_active" @change="updateUser(row)" />
        </template>
      </el-table-column>
      <el-table-column prop="initial_cash" label="初始资金" width="120" />
      <el-table-column prop="created_at" label="注册时间" width="160" />
      <el-table-column label="操作" width="150">
        <template #default="{ row }">
          <el-button text size="small" @click="editUser(row)">编辑</el-button>
          <el-button text size="small" :type="row.role === 'admin' ? '' : 'warning'" @click="toggleRole(row)">
            设为{{ row.role === 'admin' ? '用户' : '管理员' }}
          </el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-card>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { adminApi } from '@/api/admin'
import { ElMessage } from 'element-plus'

const users = ref([])

async function load() {
  try {
    const res = await adminApi.listUsers()
    users.value = res.data || []
  } catch (e) { console.error(e) }
}

async function updateUser(user) {
  try {
    await adminApi.updateUser(user.id, { is_active: user.is_active })
    ElMessage.success('更新成功')
  } catch (e) {
    ElMessage.error('更新失败')
  }
}

async function toggleRole(user) {
  const newRole = user.role === 'admin' ? 'user' : 'admin'
  try {
    await adminApi.updateUser(user.id, { role: newRole })
    ElMessage.success('角色已更新')
    await load()
  } catch (e) {
    ElMessage.error('更新失败')
  }
}

async function editUser(user) {
  // Simplified inline editing
  ElMessage.info('编辑功能')
}

onMounted(load)
</script>
