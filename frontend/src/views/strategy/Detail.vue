<template>
  <div v-if="strategy">
    <el-card shadow="never" style="margin-bottom: 16px">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center">
          <span style="font-weight: bold">{{ strategy.name }}</span>
          <div>
            <el-button :type="strategy.status === 'running' ? 'warning' : 'success'" @click="toggleStatus">
              {{ strategy.status === 'running' ? '停止策略' : '启动策略' }}
            </el-button>
            <el-button @click="$router.push('/strategies')">返回</el-button>
          </div>
        </div>
      </template>
      <el-descriptions :column="3" border size="small">
        <el-descriptions-item label="策略类型">{{ typeLabel(strategy.strategy_type) }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="strategy.status === 'running' ? 'success' : 'info'" size="small">
            {{ strategy.status === 'running' ? '运行中' : '已停止' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="交易模式">{{ strategy.mode === 'paper' ? '模拟' : '实盘' }}</el-descriptions-item>
        <el-descriptions-item label="交易标的">{{ (strategy.symbols || []).join(', ') }}</el-descriptions-item>
        <el-descriptions-item label="时间周期">{{ strategy.time_frame }}</el-descriptions-item>
        <el-descriptions-item label="初始资金">{{ strategy.initial_capital?.toLocaleString() }}</el-descriptions-item>
        <el-descriptions-item label="总交易次数">{{ strategy.total_trades }}</el-descriptions-item>
        <el-descriptions-item label="总收益">
          <span :style="{ color: strategy.total_return >= 0 ? '#67c23a' : '#f56c6c' }">
            {{ strategy.total_return?.toFixed(2) }}
          </span>
        </el-descriptions-item>
        <el-descriptions-item label="胜率">{{ strategy.win_rate?.toFixed(2) }}%</el-descriptions-item>
        <el-descriptions-item label="最大回撤">{{ strategy.max_drawdown?.toFixed(2) }}%</el-descriptions-item>
      </el-descriptions>
    </el-card>

    <el-card shadow="never">
      <template #header><span style="font-weight: bold">策略参数</span></template>
      <div v-if="strategy.parameters && Object.keys(strategy.parameters).length">
        <el-descriptions :column="3" border size="small">
          <el-descriptions-item v-for="(val, key) in strategy.parameters" :key="key" :label="key">
            {{ val }}
          </el-descriptions-item>
        </el-descriptions>
      </div>
      <div v-else style="color: #909399">无参数配置</div>
    </el-card>
  </div>
  <div v-else style="text-align: center; padding: 40px; color: #909399">加载中...</div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { strategyApi } from '@/api/strategy'
import { ElMessage } from 'element-plus'

const route = useRoute()
const router = useRouter()
const strategy = ref(null)
const typeMap = { ma: '均线', macd: 'MACD', bollinger: '布林带', grid: '网格', dca: '定投' }
function typeLabel(t) { return typeMap[t] || t }

async function load() {
  try {
    const res = await strategyApi.get(route.params.id)
    strategy.value = res.data
  } catch (e) {
    ElMessage.error('策略不存在')
    router.push('/strategies')
  }
}

async function toggleStatus() {
  try {
    if (strategy.value.status === 'running') {
      await strategyApi.stop(strategy.value.id)
      ElMessage.success('策略已停止')
    } else {
      await strategyApi.start(strategy.value.id)
      ElMessage.success('策略已启动')
    }
    await load()
  } catch (e) {
    ElMessage.error('操作失败')
  }
}

onMounted(load)
</script>
