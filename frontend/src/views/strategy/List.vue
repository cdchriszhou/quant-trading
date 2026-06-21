<template>
  <div>
    <div style="display: flex; justify-content: space-between; margin-bottom: 16px">
      <h3 style="margin: 0">策略管理</h3>
      <el-button type="primary" @click="$router.push('/strategies/create')">创建策略</el-button>
    </div>

    <el-card shadow="never">
      <el-table :data="strategies" stripe size="small" v-if="strategies.length">
        <el-table-column prop="name" label="策略名称" min-width="140" />
        <el-table-column prop="strategy_type" label="策略类型" width="100">
          <template #default="{ row }">
            <el-tag>{{ typeLabel(row.strategy_type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="symbols" label="交易标的" width="140">
          <template #default="{ row }">
            {{ (row.symbols || []).join(', ') }}
          </template>
        </el-table-column>
        <el-table-column prop="mode" label="模式" width="70" />
        <el-table-column prop="status" label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.status === 'running' ? 'success' : 'info'" size="small">
              {{ row.status === 'running' ? '运行中' : '已停止' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="total_return" label="总收益" width="100">
          <template #default="{ row }">
            <span :style="{ color: row.total_return >= 0 ? '#67c23a' : '#f56c6c' }">
              {{ row.total_return >= 0 ? '+' : '' }}{{ row.total_return?.toFixed(2) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="total_trades" label="交易次数" width="80" />
        <el-table-column prop="created_at" label="创建时间" width="160" />
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button text size="small" @click="$router.push(`/strategies/${row.id}`)">详情</el-button>
            <el-button
              text size="small"
              :type="row.status === 'running' ? 'warning' : 'success'"
              @click="toggleStrategy(row)"
            >
              {{ row.status === 'running' ? '停止' : '启动' }}
            </el-button>
            <el-button text size="small" type="danger" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-else description="暂无策略，点击上方按钮创建" />
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { strategyApi } from '@/api/strategy'
import { ElMessage, ElMessageBox } from 'element-plus'

const strategies = ref([])

const typeMap = { ma: '均线', macd: 'MACD', bollinger: '布林带', grid: '网格', dca: '定投' }
function typeLabel(t) { return typeMap[t] || t }

async function loadStrategies() {
  try {
    const res = await strategyApi.list()
    strategies.value = res.data || []
  } catch (e) { console.error(e) }
}

async function toggleStrategy(row) {
  try {
    if (row.status === 'running') {
      await strategyApi.stop(row.id)
      ElMessage.success('策略已停止')
    } else {
      await strategyApi.start(row.id)
      ElMessage.success('策略已启动')
    }
    await loadStrategies()
  } catch (e) {
    ElMessage.error('操作失败')
  }
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm(`确定删除策略"${row.name}"？`, '确认', { type: 'warning' })
    await strategyApi.delete(row.id)
    ElMessage.success('已删除')
    await loadStrategies()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('删除失败')
  }
}

onMounted(loadStrategies)
</script>
