<template>
  <div>
    <!-- Market Environment Indicator (Core 1) -->
    <div style="margin-bottom: 14px; padding: 12px 16px; border-radius: 10px; display: flex; align-items: center; gap: 12px;"
         :style="{ background: envBgColor, border: `1px solid ${envBorderColor}` }">
      <div style="width: 40px; height: 40px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 22px; flex-shrink: 0"
           :style="{ background: envIconBg }">
        {{ envIcon }}
      </div>
      <div style="flex: 1; min-width: 0">
        <div style="font-weight: 700; font-size: 14px" :style="{ color: envTextColor }">{{ envStatusText }}</div>
        <div style="font-size: 11px; color: #6b7280; margin-top: 2px">
          平均股价: {{ envAvgPrice }} | MA20: {{ envMa20 }}
          <span v-if="envSignals.length" style="margin-left: 8px">|</span>
        </div>
        <div v-if="envWarnings.length" style="font-size: 11px; color: #ef4444; margin-top: 2px">
          ⚠ {{ envWarnings[0] }}
        </div>
      </div>
      <div style="text-align: right; flex-shrink: 0">
        <el-tag :type="envTagType" size="small" effect="dark">{{ envCanTrade ? '允许开仓' : '暂停开仓' }}</el-tag>
      </div>
    </div>

    <!-- Metric cards -->
    <el-row :gutter="14" style="margin-bottom: 14px">
      <el-col :xs="12" :sm="12" :md="6" v-for="card in cards" :key="card.label">
        <el-card shadow="never" style="border-radius: 10px">
          <div style="display: flex; justify-content: space-between; align-items: flex-start">
            <div>
              <div style="color: #6b7280; font-size: 12px; font-weight: 500; letter-spacing: 0.5px; text-transform: uppercase">{{ card.label }}</div>
              <div style="font-size: 26px; font-weight: 700; margin-top: 6px; letter-spacing: -0.5px"
                   :style="{ color: card.pnlColor || '#1a1a1a' }">{{ card.value }}</div>
              <div v-if="card.change !== undefined" style="font-size: 12px; margin-top: 4px; font-weight: 600"
                   :style="{ color: card.change > 0 ? '#ef4444' : '#10b981' }">
                {{ card.change > 0 ? '+' : '' }}{{ card.change }}%
              </div>
            </div>
            <el-icon :size="34" :color="card.color"><component :is="card.icon" /></el-icon>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="14">
      <!-- Equity chart -->
      <el-col :xs="24" :sm="24" :md="16">
        <el-card shadow="never" style="margin-bottom: 14px; border-radius: 10px">
          <template #header>
            <div style="display: flex; justify-content: space-between; align-items: center">
              <span style="font-weight: 700; font-size: 14px">盈亏曲线</span>
              <span style="font-size: 10px; color: #9ca3af; letter-spacing: 1px">PORTFOLIO</span>
            </div>
          </template>
          <div ref="equityChartRef" style="height: 300px"></div>
        </el-card>

        <el-card shadow="never" style="border-radius: 10px">
          <template #header>
            <div style="display: flex; justify-content: space-between; align-items: center">
              <span style="font-weight: 700; font-size: 14px">最近交易</span>
              <span style="font-size: 10px; color: #9ca3af; letter-spacing: 1px">RECENT</span>
            </div>
          </template>
          <div v-if="recentTrades.length" style="overflow-x: auto; -webkit-overflow-scrolling: touch">
            <el-table :data="recentTrades" stripe size="small">
            <el-table-column prop="trade_time" label="时间" width="160" />
            <el-table-column label="标的" width="140">
              <template #default="{ row }">
                <div style="font-weight: 600; font-size: 12px">{{ row.symbol?.replace('.SZ','').replace('.SH','') }}</div>
                <div style="color: #9ca3af; font-size: 11px">{{ getStockName(row.symbol) }}</div>
              </template>
            </el-table-column>
            <el-table-column prop="side" label="方向" width="70">
              <template #default="{ row }">
                <el-tag :type="row.side === 'buy' ? 'danger' : 'success'" size="small" effect="plain">
                  {{ row.side === 'buy' ? '买入' : '卖出' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="price" label="价格" width="80" />
            <el-table-column prop="quantity" label="数量" width="80" />
            <el-table-column prop="pnl" label="盈亏" width="90">
              <template #default="{ row }">
                <span :style="{ color: row.pnl > 0 ? '#ef4444' : '#10b981', fontWeight: 600 }">
                  {{ row.pnl ? row.pnl.toFixed(2) : '-' }}
                </span>
              </template>
            </el-table-column>
          </el-table>
          </div>
          <el-empty v-else description="暂无交易记录" />
        </el-card>
      </el-col>

      <!-- Market indices + Strategy overview -->
      <el-col :xs="24" :sm="24" :md="8">
        <el-card shadow="never" style="margin-bottom: 14px; border-radius: 10px">
          <template #header>
            <div style="display: flex; justify-content: space-between; align-items: center">
              <span style="font-weight: 700; font-size: 14px">大盘指数</span>
              <span style="font-size: 10px; font-weight: 600; letter-spacing: 1px; padding: 1px 8px; border-radius: 3px"
                    :style="dataSource === 'realtime' ? 'color:#00B4B4;background:rgba(0,180,180,0.1)' : 'color:#f59e0b;background:rgba(245,158,11,0.1)'">
                {{ dataSource === 'realtime' ? 'LIVE' : 'SIM' }}
              </span>
            </div>
          </template>
          <div v-if="marketIndices.length === 0" style="text-align: center; padding: 16px; color: #9ca3af; font-size: 12px">
            指数数据暂不可用
          </div>
          <div v-for="idx in marketIndices" :key="idx.code"
               style="display: flex; justify-content: space-between; align-items: center; padding: 10px 0; border-bottom: 1px solid #f3f4f6">
            <span style="font-size: 13px; color: #6b7280">{{ idx.name }}</span>
            <span style="font-size: 13px; font-weight: 600">{{ idx.price }}</span>
            <span style="font-size: 13px; font-weight: 600" :style="{ color: idx.change_pct >= 0 ? '#ef4444' : '#10b981' }">
              {{ idx.change_pct >= 0 ? '+' : '' }}{{ idx.change_pct }}%
            </span>
          </div>
        </el-card>

        <el-card shadow="never" style="border-radius: 10px; margin-bottom: 14px">
          <template #header>
            <div style="display: flex; justify-content: space-between; align-items: center">
              <span style="font-weight: 700; font-size: 14px">策略概览</span>
              <span style="font-size: 10px; color: #9ca3af; letter-spacing: 1px">STRATEGIES</span>
            </div>
          </template>
          <div style="text-align: center; padding: 10px 0">
            <div style="display: flex; justify-content: space-around">
              <div>
                <div style="font-size: 32px; font-weight: 800; color: #1a1a1a; letter-spacing: -1px">{{ stats.total_strategies }}</div>
                <div style="color: #6b7280; font-size: 12px; margin-top: 2px">策略总数</div>
              </div>
              <div>
                <div style="font-size: 32px; font-weight: 800; color: #00B4B4; letter-spacing: -1px">{{ stats.running_strategies }}</div>
                <div style="color: #6b7280; font-size: 12px; margin-top: 2px">运行中</div>
              </div>
            </div>
          </div>
        </el-card>

        <!-- Top Gainers -->
        <el-card shadow="never" style="border-radius: 10px; margin-bottom: 14px">
          <template #header>
            <div style="display: flex; justify-content: space-between; align-items: center">
              <span style="font-weight: 700; font-size: 14px">📈 涨幅 Top10</span>
              <div style="display: flex; gap: 2px">
                <el-button v-for="t in moverTabs" :key="t.key" size="small"
                  :type="moverMarket === t.key ? 'primary' : ''"
                  :text="moverMarket !== t.key"
                  style="padding: 3px 8px; font-size: 11px"
                  @click="switchMoverMarket(t.key)">{{ t.label }}</el-button>
              </div>
            </div>
          </template>
          <div v-if="topGainers.length">
            <div v-for="(s, i) in topGainers" :key="s.code"
                 style="display: flex; align-items: center; padding: 5px 0; border-bottom: 1px solid #f3f4f6; gap: 6px">
              <span style="font-size: 11px; color: #9ca3af; width: 16px; text-align: center; flex-shrink: 0">{{ i + 1 }}</span>
              <span style="flex: 1; min-width: 0; font-size: 12px; font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap">{{ s.name }}</span>
              <span style="font-size: 10px; color: #9ca3af; flex-shrink: 0">{{ s.code.replace('.SZ','').replace('.SH','') }}</span>
              <span style="font-size: 11px; color: #6b7280; flex-shrink: 0; text-align: right; width: 48px">{{ s.price.toFixed(2) }}</span>
              <span style="font-size: 12px; font-weight: 700; flex-shrink: 0; text-align: right; width: 56px"
                    :style="{ color: s.change_pct >= 0 ? '#ef4444' : '#10b981' }">
                {{ s.change_pct >= 0 ? '+' : '' }}{{ s.change_pct }}%
              </span>
            </div>
          </div>
          <div v-else style="text-align: center; padding: 16px; color: #9ca3af; font-size: 12px">加载中...</div>
        </el-card>

        <!-- Top Losers -->
        <el-card shadow="never" style="border-radius: 10px">
          <template #header>
            <div style="display: flex; justify-content: space-between; align-items: center">
              <span style="font-weight: 700; font-size: 14px">📉 跌幅 Top10</span>
              <div style="display: flex; gap: 2px">
                <el-button v-for="t in moverTabs" :key="t.key" size="small"
                  :type="moverMarket === t.key ? 'primary' : ''"
                  :text="moverMarket !== t.key"
                  style="padding: 3px 8px; font-size: 11px"
                  @click="switchMoverMarket(t.key)">{{ t.label }}</el-button>
              </div>
            </div>
          </template>
          <div v-if="topLosers.length">
            <div v-for="(s, i) in topLosers" :key="s.code"
                 style="display: flex; align-items: center; padding: 5px 0; border-bottom: 1px solid #f3f4f6; gap: 6px">
              <span style="font-size: 11px; color: #9ca3af; width: 16px; text-align: center; flex-shrink: 0">{{ i + 1 }}</span>
              <span style="flex: 1; min-width: 0; font-size: 12px; font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap">{{ s.name }}</span>
              <span style="font-size: 10px; color: #9ca3af; flex-shrink: 0">{{ s.code.replace('.SZ','').replace('.SH','') }}</span>
              <span style="font-size: 11px; color: #6b7280; flex-shrink: 0; text-align: right; width: 48px">{{ s.price.toFixed(2) }}</span>
              <span style="font-size: 12px; font-weight: 700; flex-shrink: 0; text-align: right; width: 56px"
                    :style="{ color: s.change_pct >= 0 ? '#ef4444' : '#10b981' }">
                {{ s.change_pct >= 0 ? '+' : '' }}{{ s.change_pct }}%
              </span>
            </div>
          </div>
          <div v-else style="text-align: center; padding: 16px; color: #9ca3af; font-size: 12px">加载中...</div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { reportsApi } from '@/api/reports'
import { marketApi } from '@/api/market'
import { getEnvStatus } from '@/api/env'
import { getStockName } from '@/utils/stockNames'
import * as echarts from 'echarts'

const cards = ref([
  { label: '总资产', value: '¥ --', icon: 'Money', color: '#00B4B4', pnlColor: undefined },
  { label: '持仓市值', value: '¥ --', icon: 'Coin', color: '#1A6FF5', pnlColor: undefined },
  { label: '今日盈亏', value: '¥ --', icon: 'TrendCharts', color: '#f59e0b', pnlColor: undefined },
  { label: '累计收益', value: '--%', icon: 'DataBoard', color: '#8b5cf6', pnlColor: undefined },
])

const recentTrades = ref([])
const marketIndices = ref([])
const dataSource = ref('simulated')
const stats = ref({ total_strategies: 0, running_strategies: 0 })
const moverTabs = [
  { key: 'all', label: '全部' },
  { key: 'main', label: '主板' },
  { key: 'star', label: '科创板' },
  { key: 'chinext', label: '创业板' },
  { key: 'bse', label: '北交所' },
]
const topGainers = ref([])
const topLosers = ref([])
const moverMarket = ref('all')
const equityChartRef = ref(null)
let equityChart = null
let intervalId = null
let moversIntervalId = null

// ── Market Environment State ──
const envStatusText = ref('加载中...')
const envAvgPrice = ref('--')
const envMa20 = ref('--')
const envCanTrade = ref(false)
const envSignals = ref([])
const envWarnings = ref([])

// Store raw env_state for computed properties
const envState = ref('neutral')

const envIcon = computed(() => {
  if (envState.value === 'bull') return '🐂'
  if (envState.value === 'bear') return '🐻'
  return '⏸'
})
const envBgColor = computed(() => {
  if (envState.value === 'bull') return 'rgba(239,68,68,0.06)'
  if (envState.value === 'bear') return 'rgba(16,185,129,0.06)'
  return 'rgba(245,158,11,0.06)'
})
const envBorderColor = computed(() => {
  if (envState.value === 'bull') return 'rgba(239,68,68,0.3)'
  if (envState.value === 'bear') return 'rgba(16,185,129,0.3)'
  return 'rgba(245,158,11,0.3)'
})
const envIconBg = computed(() => {
  if (envState.value === 'bull') return 'rgba(239,68,68,0.15)'
  if (envState.value === 'bear') return 'rgba(16,185,129,0.15)'
  return 'rgba(245,158,11,0.15)'
})
const envTextColor = computed(() => {
  if (envState.value === 'bull') return '#ef4444'
  if (envState.value === 'bear') return '#10b981'
  return '#f59e0b'
})
const envTagType = computed(() => {
  if (envState.value === 'bull') return 'danger'
  if (envState.value === 'bear') return 'success'
  return 'warning'
})

async function loadEnvStatus() {
  try {
    const res = await getEnvStatus()
    const d = res.data
    envState.value = d.env_state || 'neutral'
    envCanTrade.value = d.can_trade || false
    if (envCanTrade.value) {
      envStatusText.value = '🐂 多头市场'
    } else if (d.env_state === 'bear') {
      envStatusText.value = '🐻 空头市场'
    } else {
      envStatusText.value = '⏸ 震荡市场'
    }
    envAvgPrice.value = d.avg_price ? d.avg_price.toFixed(2) : '--'
    envMa20.value = d.ma20 ? d.ma20.toFixed(2) : '--'
    envSignals.value = d.signals || []
    envWarnings.value = d.warnings || []
  } catch (e) {
    console.error('Env status error:', e)
    envStatusText.value = '数据获取失败'
  }
}

async function loadMovers() {
  try {
    const res = await marketApi.getTopMovers(10, moverMarket.value)
    topGainers.value = res.gainers || []
    topLosers.value = res.losers || []
  } catch (e) {
    console.error('Top movers error:', e)
  }
}

function switchMoverMarket(market) {
  moverMarket.value = market
  loadMovers()
}

async function loadDashboard() {
  try {
    const res = await reportsApi.getDashboard()
    const data = res.data
    const account = data.account || {}
    const totalPnl = account.total_pnl || 0
    const totalReturnPct = account.total_return_pct || 0

    cards.value = [
      { label: '总资产', value: `¥ ${(account.total_equity || 0).toLocaleString()}`, icon: 'Money', color: '#00B4B4', pnlColor: undefined },
      { label: '持仓市值', value: `¥ ${(account.market_value || 0).toLocaleString()}`, icon: 'Coin', color: '#1A6FF5', pnlColor: undefined },
      { label: '今日盈亏', value: `¥ ${totalPnl.toLocaleString()}`, icon: 'TrendCharts', color: '#f59e0b', pnlColor: totalPnl > 0 ? '#ef4444' : totalPnl < 0 ? '#10b981' : undefined },
      { label: '累计收益', value: `${totalReturnPct.toFixed(2)}%`, icon: 'DataBoard', color: '#8b5cf6', pnlColor: totalReturnPct > 0 ? '#ef4444' : totalReturnPct < 0 ? '#10b981' : undefined },
    ]

    recentTrades.value = data.recent_trades || []
    marketIndices.value = data.market?.indices || []
    dataSource.value = data.market?.data_source || 'simulated'
    stats.value = { total_strategies: data.total_strategies || 0, running_strategies: data.running_strategies || 0 }

    if (equityChartRef.value) {
      await nextTick()
      renderChart()
    }
  } catch (err) {
    console.error('Dashboard error:', err)
  }
}

function renderChart() {
  if (equityChart) equityChart.dispose()
  equityChart = echarts.init(equityChartRef.value)

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
    grid: { left: '0', right: '10', top: '10', bottom: '0', containLabel: true },
    xAxis: { type: 'category', data: dates, show: false },
    yAxis: {
      type: 'value',
      splitLine: { lineStyle: { color: '#f3f4f6' } },
      axisLabel: { color: '#9ca3af', formatter: (v) => (v / 10000).toFixed(0) + 'w' },
    },
    series: [{
      type: 'line', data: values, smooth: true, symbol: 'none',
      lineStyle: { color: '#00B4B4', width: 2 },
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(0, 180, 180, 0.2)' },
          { offset: 1, color: 'rgba(0, 180, 180, 0.0)' },
        ]),
      },
    }],
  })
}

onMounted(() => {
  loadEnvStatus()
  loadDashboard()
  loadMovers()
  intervalId = setInterval(loadDashboard, 60000)
  moversIntervalId = setInterval(loadMovers, 30000)
})
onUnmounted(() => {
  if (intervalId) clearInterval(intervalId)
  if (moversIntervalId) clearInterval(moversIntervalId)
  if (equityChart) equityChart.dispose()
})
</script>
