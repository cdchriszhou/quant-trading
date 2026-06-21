<template>
  <el-card shadow="never">
    <template #header><span style="font-weight: bold">操作日志</span></template>
    <el-table :data="logs" stripe size="small" v-if="logs.length">
      <el-table-column prop="created_at" label="时间" width="160" />
      <el-table-column prop="username" label="用户" width="100" />
      <el-table-column prop="action" label="操作" width="140" />
      <el-table-column prop="resource" label="资源" width="120" />
      <el-table-column prop="detail" label="详情" min-width="200" show-overflow-tooltip />
      <el-table-column prop="status" label="状态" width="70">
        <template #default="{ row }">
          <el-tag :type="row.status === 'success' ? 'success' : 'danger'" size="small">{{ row.status }}</el-tag>
        </template>
      </el-table-column>
    </el-table>
    <el-empty v-else description="暂无日志" />
  </el-card>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { adminApi } from '@/api/admin'

const logs = ref([])

async function load() {
  try {
    const res = await adminApi.getLogs()
    logs.value = res.data || []
  } catch (e) { console.error(e) }
}

onMounted(load)
</script>
