<template>
  <el-card shadow="never">
    <template #header><span style="font-weight: bold">用户管理</span></template>
    <div style="overflow-x: auto; -webkit-overflow-scrolling: touch">
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
          <el-switch v-model="row.is_active" @change="toggleActive(row)" />
        </template>
      </el-table-column>
      <el-table-column prop="initial_cash" label="初始资金" width="160">
        <template #default="{ row }">
          <template v-if="editingId === row.id">
            <el-input-number
              v-model="row.initial_cash"
              :min="0"
              :step="10000"
              size="small"
              style="width: 130px"
              @blur="saveInlineCash(row)"
              @keyup.enter="saveInlineCash(row)"
              ref="el => cashInputs[row.id] = el"
            />
          </template>
          <template v-else>
            <span
              style="cursor: pointer; border-bottom: 1px dashed #c0c4cc; padding-bottom: 2px"
              @click="startEditCash(row)"
              title="点击修改初始资金"
            >
              ¥{{ (row.initial_cash || 0).toLocaleString() }}
            </span>
          </template>
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="注册时间" width="160" />
      <el-table-column label="操作" width="180" fixed="right">
        <template #default="{ row }">
          <el-button text size="small" @click="openEdit(row)">编辑</el-button>
          <el-button text size="small" :type="row.role === 'admin' ? '' : 'warning'" @click="toggleRole(row)">
            设为{{ row.role === 'admin' ? '用户' : '管理员' }}
          </el-button>
        </template>
      </el-table-column>
    </el-table>
    </div>

    <!-- 编辑用户对话框 -->
    <el-dialog v-model="dialogVisible" title="编辑用户" width="460px" :close-on-click-modal="false">
      <el-form ref="formRef" :model="editForm" :rules="editRules" label-width="90px" class="responsive-form">
        <el-form-item label="用户名">
          <el-input :model-value="editForm.username" disabled />
        </el-form-item>
        <el-form-item label="显示名" prop="display_name">
          <el-input v-model="editForm.display_name" placeholder="请输入显示名" />
        </el-form-item>
        <el-form-item label="邮箱" prop="email">
          <el-input v-model="editForm.email" placeholder="请输入邮箱" />
        </el-form-item>
        <el-form-item label="初始资金" prop="initial_cash">
          <el-input-number v-model="editForm.initial_cash" :min="0" :step="10000" style="width: 100%" />
        </el-form-item>
        <el-form-item label="角色">
          <el-radio-group v-model="editForm.role">
            <el-radio value="user">普通用户</el-radio>
            <el-radio value="admin">管理员</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="状态">
          <el-switch v-model="editForm.is_active" active-text="启用" inactive-text="禁用" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { adminApi } from '@/api/admin'
import { ElMessage } from 'element-plus'

const users = ref([])
const dialogVisible = ref(false)
const saving = ref(false)
const formRef = ref(null)
const editingId = ref(null)
const cashInputs = ref({})

function startEditCash(user) {
  editingId.value = user.id
  // 等 DOM 更新后自动聚焦输入框
  setTimeout(() => {
    const input = cashInputs.value[user.id]
    if (input) input.focus()
  }, 50)
}

async function saveInlineCash(user) {
  try {
    await adminApi.updateUser(user.id, { initial_cash: user.initial_cash })
    ElMessage.success(`初始资金已更新为 ¥${(user.initial_cash || 0).toLocaleString()}`)
  } catch (e) {
    ElMessage.error('更新失败')
  } finally {
    editingId.value = null
  }
}

const editForm = reactive({
  id: null,
  username: '',
  display_name: '',
  email: '',
  initial_cash: 0,
  role: 'user',
  is_active: true,
})

const editRules = {
  display_name: [{ required: true, message: '请输入显示名', trigger: 'blur' }],
  email: [{ type: 'email', message: '请输入有效的邮箱地址', trigger: 'blur' }],
  initial_cash: [{ required: true, message: '请输入初始资金', trigger: 'blur' }],
}

async function load() {
  try {
    const res = await adminApi.listUsers()
    users.value = res.data || []
  } catch (e) { console.error(e) }
}

async function toggleActive(user) {
  try {
    await adminApi.updateUser(user.id, { is_active: user.is_active })
    ElMessage.success('状态已更新')
  } catch (e) {
    user.is_active = !user.is_active
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

function openEdit(user) {
  editForm.id = user.id
  editForm.username = user.username
  editForm.display_name = user.display_name || ''
  editForm.email = user.email || ''
  editForm.initial_cash = user.initial_cash || 0
  editForm.role = user.role || 'user'
  editForm.is_active = user.is_active !== false
  dialogVisible.value = true
}

async function handleSave() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  saving.value = true
  try {
    await adminApi.updateUser(editForm.id, {
      display_name: editForm.display_name,
      email: editForm.email,
      initial_cash: editForm.initial_cash,
      role: editForm.role,
      is_active: editForm.is_active,
    })
    ElMessage.success('用户信息已更新')
    dialogVisible.value = false
    await load()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '更新失败')
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>
