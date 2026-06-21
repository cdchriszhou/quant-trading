<template>
  <div>
    <el-row :gutter="16">
      <el-col :span="12">
        <el-card shadow="never" style="margin-bottom: 16px">
          <template #header><span style="font-weight: bold">交易绩效</span></template>
          <div v-if="performance" style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px">
            <div v-for="(item, idx) in perfItems" :key="idx" style="text-align: center; padding: 12px; background: #f9f9f9; border-radius: 4px">
              <div style="color: #909399; font-size: 12px">{{ item.label }}</div>
              <div style="font-size: 20px; font-weight: bold">{{ item.value }}</div>
            </div>
          </div>
          <el-empty v-else description="暂无交易数据" />
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="never" style="margin-bottom: 16px">
          <template #header><span style="font-weight: bold">账户概览</span></template>
          <div v-if="account" style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px">
            <div v-for="(item, idx) in accountItems" :key="idx" style="text-align: center; padding: 12px; background: #f9f9f9; border-radius: 4px">
              <div style="color: #909399; font-size: 12px">{{ item.label }}</div>
              <div style="font-size: 20px; font-weight: bold">{{ item.value }}</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="never">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center">
          <span style="font-weight: bold">交易记录</span>
          <el-button size="small" @click="exportTrades">导出全部</el-button>
        </div>
      </template>
      <el-table :data="trades" stripe size="small" v-if="trades.length" max-height="400">
        <el-table-column prop="trade_time" label="时间" width="160" />
        <el-table-column prop="symbol" label="标的" width="80" />
        <el-table-column prop="side" label="方向" width="60">
          <template #default="{ row }">
            <el-tag :type="row.side === 'buy' ? 'danger' : 'success'" size="small">{{ row.side === 'buy' ? '买入' : '卖出' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="price" label="价格" width="80" />
        <el-table-column prop="quantity" label="数量" width="80" />
        <el-table-column prop="amount" label="金额" width="100" />
        <el-table-column prop="commission" label="手续费" width="80" />
        <el-table-column prop="pnl" label="盈亏" width="90">
          <template #default="{ row }">
            <span :style="{ color: row.pnl > 0 ? '#67c23a' : row.pnl < 0 ? '#f56c6c' : '', fontWeight: 'bold' }">
              {{ row.pnl || '-' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="trade_mode" label="模式" width="60" />
      </el-table>
      <el-empty v-else description="暂无交易记录" />
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { reportsApi } from '@/api/reports'
import { tradingApi } from '@/api/trading'
import { ElMessage } from 'element-plus'

const trades = ref([])
const performance = ref(null)
const account = ref(null)

const perfItems = computed(() => {
  if (!performance.value) return []
  const p = performance.value
  const a = account.value || {}
  return [
    { label: '总交易次数', value: p.total_trades },
    { label: '买入次数', value: p.buy_trades },
    { label: '卖出次数', value: p.sell_trades },
    { label: '胜率', value: `${p.win_rate}%` },
    { label: '总手续费', value: `¥${p.total_commission?.toFixed(2)}` },
    { label: '总盈亏', value: `¥${p.total_pnl?.toFixed(2)}` },
  ]
})

const accountItems = computed(() => {
  if (!account.value) return []
  const a = account.value
  return [
    { label: '总资产', value: `¥${(a.total_equity || 0).toLocaleString()}` },
    { label: '可用资金', value: `¥${(a.cash_balance || 0).toLocaleString()}` },
    { label: '持仓市值', value: `¥${(a.market_value || 0).toLocaleString()}` },
    { label: '收益率', value: `${(a.total_return_pct || 0).toFixed(2)}%` },
  ]
})

async function load() {
  try {
    const [tRes, pRes, aRes] = await Promise.all([
      reportsApi.getTrades(),
      reportsApi.getPerformance(),
      tradingApi.getAccount(),
    ])
    trades.value = tRes.data || []
    performance.value = pRes.data
    account.value = aRes.data
  } catch (e) { console.error(e) }
}

function exportTrades() {
  const csv = [
    ['时间', '标的', '方向', '价格', '数量', '金额', '手续费', '盈亏', '模式'].join(','),
    ...trades.value.map(t =>
      [t.trade_time, t.symbol, t.side, t.price, t.quantity, t.amount, t.commission, t.pnl || '', t.trade_mode].join(',')
    ),
  ].join('\n')
  const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `交易记录_${new Date().toISOString().slice(0, 10)}.csv`
  a.click()
  URL.revokeObjectURL(url)
  ElMessage.success('导出成功')
}

onMounted(load)
</script>
