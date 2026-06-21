<template>
  <div>
    <el-row :gutter="16">
      <el-col :span="6" v-for="card in cards" :key="card.label">
        <el-card shadow="never" style="margin-bottom: 16px">
          <div style="display: flex; justify-content: space-between; align-items: center">
            <div>
              <div style="color: #909399; font-size: 13px">{{ card.label }}</div>
              <div style="font-size: 24px; font-weight: bold; margin-top: 4px">{{ card.value }}</div>
              <div style="color: #67c23a; font-size: 12px; margin-top: 4px" v-if="card.change !== undefined">
                {{ card.change > 0 ? '+' : '' }}{{ card.change }}%
              </div>
            </div>
            <el-icon :size="36" :color="card.color"><component :is="card.icon" /></el-icon>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16">
      <el-col :span="16">
        <el-card shadow="never" style="margin-bottom: 16px">
          <template #header>
            <span style="font-weight: bold">盈亏曲线</span>
          </template>
          <div ref="equityChartRef" style="height: 300px"></div>
        </el-card>
        <el-card shadow="never">
          <template #header>
            <span style="font-weight: bold">最近交易</span>
          </template>
          <el-table :data="recentTrades" stripe size="small" v-if="recentTrades.length">
            <el-table-column prop="trade_time" label="时间" width="160" />
            <el-table-column prop="symbol" label="标的" width="100" />
            <el-table-column prop="side" label="方向" width="70">
              <template #default="{ row }">
                <el-tag :type="row.side === 'buy' ? 'danger' : 'success'" size="small">
                  {{ row.side === 'buy' ? '买入' : '卖出' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="price" label="价格" width="90" />
            <el-table-column prop="quantity" label="数量" width="90" />
            <el-table-column prop="pnl" label="盈亏" width="90">
              <template #default="{ row }">
                <span :style="{ color: row.pnl > 0 ? '#67c23a' : '#f56c6c' }">
                  {{ row.pnl ? row.pnl.toFixed(2) : '-' }}
                </span>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-else description="暂无交易记录" />
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="never" style="margin-bottom: 16px">
          <template #header>
            <span style="font-weight: bold">大盘指数</span>
          </template>
          <div v-for="idx in marketIndices" :key="idx.code" style="display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #f0f0f0">
            <span>{{ idx.name }}</span>
            <span>{{ idx.price }}</span>
            <span :style="{ color: idx.change_pct > 0 ? '#f56c6c' : '#67c23a' }">
              {{ idx.change_pct > 0 ? '+' : '' }}{{ idx.change_pct }}%
            </span>
          </div>
        </el-card>
        <el-card shadow="never">
          <template #header>
            <span style="font-weight: bold">策略概览</span>
          </template>
          <div style="text-align: center; padding: 10px 0">
            <div style="display: flex; justify-content: space-around">
              <div>
                <div style="font-size: 28px; font-weight: bold; color: #409EFF">{{ stats.total_strategies }}</div>
                <div style="color: #909399; font-size: 13px">策略总数</div>
              </div>
              <div>
                <div style="font-size: 28px; font-weight: bold; color: #67c23a">{{ stats.running_strategies }}</div>
                <div style="color: #909399; font-size: 13px">运行中</div>
              </div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { reportsApi } from '@/api/reports'
import { marketApi } from '@/api/market'
import * as echarts from 'echarts'

const cards = ref([
  { label: '总资产', value: '¥ --', icon: 'Money', color: '#409EFF' },
  { label: '持仓市值', value: '¥ --', icon: 'Coin', color: '#67c23a' },
  { label: '今日盈亏', value: '¥ --', icon: 'TrendCharts', color: '#e6a23c' },
  { label: '累计收益', value: '--%', icon: 'DataBoard', color: '#f56c6c' },
])

const recentTrades = ref([])
const marketIndices = ref([])
const stats = ref({ total_strategies: 0, running_strategies: 0 })
const equityChartRef = ref(null)
let equityChart = null

let intervalId = null

async function loadDashboard() {
  try {
    const res = await reportsApi.getDashboard()
    const data = res.data
    const account = data.account || {}

    cards.value = [
      { label: '总资产', value: `¥ ${(account.total_equity || 0).toLocaleString()}`, icon: 'Money', color: '#409EFF' },
      { label: '持仓市值', value: `¥ ${(account.market_value || 0).toLocaleString()}`, icon: 'Coin', color: '#67c23a' },
      { label: '今日盈亏', value: `¥ ${(account.total_pnl || 0).toLocaleString()}`, icon: 'TrendCharts', color: '#e6a23c' },
      { label: '累计收益', value: `${(account.total_return_pct || 0).toFixed(2)}%`, icon: 'DataBoard', color: '#f56c6c' },
    ]

    recentTrades.value = data.recent_trades || []
    marketIndices.value = data.market?.indices || []
    stats.value = { total_strategies: data.total_strategies || 0, running_strategies: data.running_strategies || 0 }

    if (equityChartRef.value) {
      await nextTick()
      renderChart()
    }
  } catch (err) {
    console.error('Dashboard load error:', err)
  }
}

function renderChart() {
  if (equityChart) equityChart.dispose()
  equityChart = echarts.init(equityChartRef.value)

  // Generate sample equity curve data
  const dates = []
  const values = []
  let eq = 1000000
  for (let i = 365; i >= 0; i--) {
    const d = new Date()
    d.setDate(d.getDate() - i)
    dates.push(d.toLocaleDateString('zh-CN'))
    eq = eq * (1 + (Math.random() - 0.48) * 0.008)
    values.push(Math.round(eq))
  }

  equityChart.setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: { type: 'category', data: dates, show: false },
    yAxis: { type: 'value', axisLabel: { formatter: (v) => '¥' + (v / 10000).toFixed(0) + 'w' } },
    series: [{
      type: 'line',
      data: values,
      smooth: true,
      lineStyle: { color: '#409EFF', width: 2 },
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(64,158,255,0.3)' },
          { offset: 1, color: 'rgba(64,158,255,0.02)' },
        ]),
      },
    }],
  })
}

onMounted(() => {
  loadDashboard()
  intervalId = setInterval(loadDashboard, 60000)
})

onUnmounted(() => {
  if (intervalId) clearInterval(intervalId)
  if (equityChart) equityChart.dispose()
})
</script>
