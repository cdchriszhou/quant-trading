<template>
  <div>
    <el-card shadow="never" style="margin-bottom: 16px">
      <div style="display: flex; gap: 12px; align-items: center; flex-wrap: wrap">
        <el-select v-model="selectedSymbol" filterable placeholder="选择标的" style="width: 200px" @change="loadData">
          <el-option v-for="s in symbols" :key="s.code" :label="`${s.code} - ${s.name}`" :value="s.code" />
        </el-select>
        <el-radio-group v-model="selectedPeriod" @change="loadData">
          <el-radio-button value="1d">日K</el-radio-button>
          <el-radio-button value="1w">周K</el-radio-button>
          <el-radio-button value="30m">30分</el-radio-button>
        </el-radio-group>
        <span v-if="symbolsLoadError" style="color: #f59e0b; font-size: 12px">标的列表加载失败，使用备用列表</span>
      </div>
    </el-card>

    <el-row :gutter="16">
      <el-col :xs="24" :md="16">
        <el-card shadow="never" style="margin-bottom: 16px">
          <template #header>
            <div style="display: flex; justify-content: space-between; align-items: center">
              <span style="font-weight: bold">K线图</span>
              <span v-if="klineError" style="color: #f59e0b; font-size: 12px">数据加载失败，请检查网络</span>
            </div>
          </template>
          <div v-if="klineError" style="height: 350px; display: flex; align-items: center; justify-content: center; color: #909399">
            <div style="text-align: center">
              <el-icon :size="40" style="color: #e5e7eb"><WarningFilled /></el-icon>
              <p style="margin-top: 12px">K线数据暂不可用</p>
              <p style="font-size: 12px; color: #c0c4cc">请确认后端服务及外部行情API连通性</p>
            </div>
          </div>
          <div v-else ref="klineChartRef" style="height: 350px; width: 100%"></div>
        </el-card>
      </el-col>
      <el-col :xs="24" :md="8">
        <el-card shadow="never" style="margin-bottom: 16px">
          <template #header>
            <div style="display: flex; justify-content: space-between; align-items: center">
              <span style="font-weight: bold">实时行情</span>
              <span v-if="quoteError" style="font-size: 10px; color: #f59e0b">数据异常</span>
            </div>
          </template>
          <div v-if="quoteError" style="text-align: center; padding: 20px; color: #909399">
            <el-icon :size="32" style="color: #e5e7eb"><WarningFilled /></el-icon>
            <p style="margin-top: 8px">行情数据获取失败</p>
          </div>
          <div v-else-if="quote" style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px">
            <div><span style="color: #909399">最新价</span><br><span style="font-size: 24px; font-weight: bold">{{ quote.current_price }}</span></div>
            <div><span style="color: #909399">涨跌幅</span><br><span :style="{ fontSize: '24px', fontWeight: 'bold', color: (quote.change_pct || 0) > 0 ? '#ef4444' : '#10b981' }">{{ quote.change_pct }}%</span></div>
            <div><span style="color: #909399">最高</span><br><span>{{ quote.high }}</span></div>
            <div><span style="color: #909399">最低</span><br><span>{{ quote.low }}</span></div>
            <div><span style="color: #909399">开盘</span><br><span>{{ quote.open }}</span></div>
            <div><span style="color: #909399">昨收</span><br><span>{{ quote.pre_close }}</span></div>
            <div><span style="color: #909399">成交量</span><br><span>{{ (quote.volume / 10000).toFixed(0) }}万</span></div>
            <div><span style="color: #909399">成交额</span><br><span>{{ quote.amount }}亿</span></div>
          </div>
          <div v-else style="text-align: center; padding: 20px; color: #909399">加载中...</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 主流板块 -->
    <el-card shadow="never">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center">
          <span style="font-weight: bold">主流板块</span>
          <span style="font-size: 12px; color: #909399">行业板块 · 实时行情</span>
        </div>
      </template>
      <div v-if="sectorsError" style="text-align: center; padding: 20px; color: #909399">
        <el-icon :size="32" style="color: #e5e7eb"><WarningFilled /></el-icon>
        <p style="margin-top: 8px">板块数据加载失败</p>
      </div>
      <div v-else-if="sectors.length" style="display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 8px">
        <div
          v-for="s in sectors"
          :key="s.code"
          style="display: flex; justify-content: space-between; align-items: center; padding: 10px 14px; border: 1px solid #ebeef5; border-radius: 6px; cursor: pointer; transition: background 0.2s, border-color 0.2s"
          @mouseenter="hoverBg"
          @mouseleave="hoverBgReset"
          @click="handleSectorClick(s)"
        >
          <div style="flex: 1; min-width: 0; margin-right: 8px">
            <div style="font-size: 14px; font-weight: 500">{{ s.name }}</div>
            <div style="font-size: 11px; color: #909399; margin-top: 2px">
              领涨: {{ s.leading_stock || '-' }}
              <span :style="{ color: (s.leading_stock_change_pct || 0) >= 0 ? '#ef4444' : '#10b981' }">
                {{ s.leading_stock_change_pct ? (s.leading_stock_change_pct > 0 ? '+' : '') + s.leading_stock_change_pct + '%' : '' }}
              </span>
            </div>
            <div v-if="s.total_count" style="font-size: 10px; color: #c0c4cc; margin-top: 1px">
              涨 {{ s.up_count }}/{{ s.total_count }}
            </div>
          </div>
          <div :style="{
            fontSize: '15px',
            fontWeight: 'bold',
            color: (s.change_pct || 0) > 0 ? '#ef4444' : (s.change_pct || 0) < 0 ? '#10b981' : '#909399',
            whiteSpace: 'nowrap'
          }">
            {{ s.change_pct > 0 ? '+' : '' }}{{ s.change_pct }}%
          </div>
        </div>
      </div>
      <div v-else style="text-align: center; padding: 20px; color: #909399">加载中...</div>
    </el-card>

    <!-- 板块成分股弹窗 -->
    <el-dialog
      v-model="sectorDialogVisible"
      :title="selectedSector ? `${selectedSector.name} - 成分股` : '板块成分股'"
      width="800px"
      :close-on-click-modal="false"
      @close="handleDialogClose"
    >
      <div v-if="sectorStocksLoading" style="text-align: center; padding: 40px; color: #909399">
        <el-icon class="is-loading" :size="32"><Loading /></el-icon>
        <p style="margin-top: 12px">加载成分股数据...</p>
      </div>
      <div v-else-if="sectorStocksError" style="text-align: center; padding: 40px; color: #909399">
        <el-icon :size="32" style="color: #e5e7eb"><WarningFilled /></el-icon>
        <p style="margin-top: 12px">成分股数据加载失败</p>
        <el-button type="primary" size="small" style="margin-top: 12px" @click="retryLoadSectorStocks">重试</el-button>
      </div>
      <div v-else-if="!sectorStocks.length" style="text-align: center; padding: 40px; color: #909399">
        <p>暂无成分股数据</p>
      </div>
      <el-table v-else :data="sectorStocks" stripe max-height="500" style="width: 100%">
        <el-table-column prop="code" label="代码" width="110" />
        <el-table-column prop="name" label="名称" width="120" />
        <el-table-column label="最新价" width="100" align="right">
          <template #default="{ row }">
            <span :style="{ fontWeight: 'bold' }">{{ row.price || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="涨跌幅" width="100" align="right">
          <template #default="{ row }">
            <span :style="{
              color: (row.change_pct || 0) > 0 ? '#ef4444' : (row.change_pct || 0) < 0 ? '#10b981' : '#909399',
              fontWeight: 'bold'
            }">
              {{ (row.change_pct || 0) > 0 ? '+' : '' }}{{ row.change_pct }}%
            </span>
          </template>
        </el-table-column>
        <el-table-column label="最高" width="100" align="right">
          <template #default="{ row }">{{ row.high || '-' }}</template>
        </el-table-column>
        <el-table-column label="最低" width="100" align="right">
          <template #default="{ row }">{{ row.low || '-' }}</template>
        </el-table-column>
        <el-table-column label="昨收" width="100" align="right">
          <template #default="{ row }">{{ row.pre_close || '-' }}</template>
        </el-table-column>
        <el-table-column label="成交量(万)" min-width="120" align="right">
          <template #default="{ row }">{{ row.volume ? (row.volume / 10000).toFixed(0) : '-' }}</template>
        </el-table-column>
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { marketApi } from '@/api/market'
import * as echarts from 'echarts'

const selectedSymbol = ref('000001.SZ')
const selectedPeriod = ref('1d')
const symbols = ref([])
const symbolsLoadError = ref(false)
const quote = ref(null)
const quoteError = ref(false)
const klineError = ref(false)
const sectors = ref([])
const sectorsError = ref(false)
const sectorDialogVisible = ref(false)
const selectedSector = ref(null)
const sectorStocks = ref([])
const sectorStocksLoading = ref(false)
const sectorStocksError = ref(false)
const klineChartRef = ref(null)
let klineChart = null
let quoteInterval = null
let sectorsInterval = null

async function loadSymbols() {
  symbolsLoadError.value = false
  try {
    const res = await marketApi.searchSymbols()
    symbols.value = res.data || []
    if (!symbols.value.length) {
      symbolsLoadError.value = true
    }
  } catch (e) {
    console.error('loadSymbols error:', e)
    symbolsLoadError.value = true
  }
}

async function loadData() {
  quoteError.value = false
  try {
    const res = await marketApi.getQuote(selectedSymbol.value)
    quote.value = res
  } catch (e) {
    console.error('getQuote error:', e)
    quoteError.value = true
    quote.value = null
  }

  klineError.value = false
  try {
    const res = await marketApi.getKline(selectedSymbol.value, selectedPeriod.value, 120)
    const kdata = res.data || []
    await nextTick()
    if (!kdata.length) {
      klineError.value = true
    } else {
      renderKline(kdata)
    }
  } catch (e) {
    console.error('getKline error:', e)
    klineError.value = true
  }
}

async function loadSectors() {
  sectorsError.value = false
  try {
    const res = await marketApi.getSectors(30)
    sectors.value = (res.data || []).sort((a, b) => b.change_pct - a.change_pct)
    if (!sectors.value.length) {
      sectorsError.value = true
    }
  } catch (e) {
    console.error('loadSectors error:', e)
    sectorsError.value = true
  }
}

function hoverBg(e) { e.currentTarget.style.background = '#f5f7fa' }
function hoverBgReset(e) { e.currentTarget.style.background = '' }

async function handleSectorClick(sector) {
  selectedSector.value = sector
  sectorStocks.value = []
  sectorStocksLoading.value = true
  sectorStocksError.value = false
  sectorDialogVisible.value = true
  try {
    const res = await marketApi.getSectorStocks(sector.code)
    sectorStocks.value = res.data || []
    if (!sectorStocks.value.length) {
      sectorStocksError.value = true
    }
  } catch (e) {
    console.error('getSectorStocks error:', e)
    sectorStocksError.value = true
  } finally {
    sectorStocksLoading.value = false
  }
}

function handleDialogClose() {
  selectedSector.value = null
  sectorStocks.value = []
  sectorStocksLoading.value = false
  sectorStocksError.value = false
}

async function retryLoadSectorStocks() {
  if (!selectedSector.value) return
  sectorStocksLoading.value = true
  sectorStocksError.value = false
  try {
    const res = await marketApi.getSectorStocks(selectedSector.value.code)
    sectorStocks.value = res.data || []
    if (!sectorStocks.value.length) {
      sectorStocksError.value = true
    }
  } catch (e) {
    console.error('retryLoadSectorStocks error:', e)
    sectorStocksError.value = true
  } finally {
    sectorStocksLoading.value = false
  }
}

function renderKline(data) {
  if (klineChart) klineChart.dispose()
  if (!data.length) return

  klineChart = echarts.init(klineChartRef.value)
  const dates = data.map(d => d.date)
  const vols = data.map(d => d.volume)
  const values = data.map(d => [d.open, d.close, d.low, d.high])

  klineChart.setOption({
    tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
    grid: [{ left: '10%', right: '8%', top: '10%', height: '60%' }, { left: '10%', right: '8%', top: '78%', height: '15%' }],
    xAxis: [{ type: 'category', data: dates, gridIndex: 0, axisLabel: { rotate: 45 } }, { type: 'category', data: dates, gridIndex: 1, show: false }],
    yAxis: [{ type: 'value', gridIndex: 0, scale: true }, { type: 'value', gridIndex: 1, scale: true }],
    series: [
      {
        type: 'candlestick', data: values,
        itemStyle: { color: '#f56c6c', color0: '#67c23a', borderColor: '#f56c6c', borderColor0: '#67c23a' },
      },
      {
        type: 'bar', data: vols, xAxisIndex: 1, yAxisIndex: 1,
        itemStyle: { color: 'rgba(64,158,255,0.3)' },
      },
    ],
  })
}

onMounted(() => {
  loadSymbols()
  loadData()
  loadSectors()
  quoteInterval = setInterval(() => {
    marketApi.getQuote(selectedSymbol.value).then(r => {
      quote.value = r
      quoteError.value = false
    }).catch(() => {
      quoteError.value = true
    })
  }, 5000)
  sectorsInterval = setInterval(() => {
    loadSectors()
  }, 30000)
})

onUnmounted(() => {
  if (klineChart) klineChart.dispose()
  if (quoteInterval) clearInterval(quoteInterval)
  if (sectorsInterval) clearInterval(sectorsInterval)
})
</script>
