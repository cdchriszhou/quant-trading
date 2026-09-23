<template>
  <div>
    <!-- 我的持仓实时行情（优先展示已买入标的） -->
    <el-card shadow="never" style="margin-bottom: 16px">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px">
          <span style="font-weight: bold">我的持仓行情</span>
          <span style="font-size: 12px; color: #909399">
            {{ holdingsLoading ? '加载持仓中…' : (holdings.length ? `共 ${holdings.length} 只 · 约15秒刷新` : '暂无持仓') }}
          </span>
        </div>
      </template>
      <div v-if="holdingsLoading" style="padding: 12px; color: #909399; font-size: 13px">正在读取当前账户持仓…</div>
      <el-empty v-else-if="!holdings.length" description="当前账户暂无持仓，可在下方搜索任意股票查看行情" :image-size="64" />
      <div v-else class="holding-grid">
        <button
          v-for="h in holdings"
          :key="h.symbol"
          type="button"
          class="holding-card"
          :class="{ active: selectedSymbol === h.symbol }"
          @click="selectSymbol(h.symbol)"
        >
          <div class="holding-top">
            <div style="min-width: 0">
              <StockTicker :symbol="h.symbol" :row="h" />
              <div class="holding-code">持仓 {{ h.quantity }}</div>
            </div>
            <div class="holding-px" :style="{ color: pctColor(holdingQuote(h.symbol)?.change_pct ?? h.unrealized_pnl_pct) }">
              {{ formatPrice(holdingQuote(h.symbol)?.current_price ?? h.current_price) }}
            </div>
          </div>
          <div class="holding-bottom">
            <span :style="{ color: pctColor(holdingQuote(h.symbol)?.change_pct) }">
              {{ formatPct(holdingQuote(h.symbol)?.change_pct) }}
            </span>
            <span :style="{ color: pctColor(h.unrealized_pnl) }">
              盈亏 {{ formatSignedMoney(h.unrealized_pnl) }}
            </span>
          </div>
        </button>
      </div>
    </el-card>

    <el-card shadow="never" style="margin-bottom: 16px">
      <div style="display: flex; gap: 12px; align-items: center; flex-wrap: wrap">
        <span style="font-size: 13px; color: #6b7280; white-space: nowrap">查看其他股票</span>
        <el-select
          v-model="selectedSymbol"
          filterable
          remote
          clearable
          :remote-method="remoteSearch"
          :loading="symLoading"
          placeholder="输入代码或名称搜索"
          style="width: 260px"
          @change="onSearchChange"
        >
          <el-option v-for="s in symbols" :key="s.code" :label="`${s.code} - ${s.name}`" :value="s.code" />
        </el-select>
        <el-radio-group v-model="selectedPeriod" :disabled="!selectedSymbol" @change="loadData">
          <el-radio-button value="1d">日K</el-radio-button>
          <el-radio-button value="1w">周K</el-radio-button>
          <el-radio-button value="30m">30分</el-radio-button>
        </el-radio-group>
        <span v-if="symbolsLoadError" style="color: #f59e0b; font-size: 12px">真实标的列表加载失败，请检查网络后刷新</span>
      </div>
    </el-card>

    <el-row v-if="selectedSymbol" :gutter="16">
      <el-col :xs="24" :md="16">
        <el-card shadow="never" style="margin-bottom: 16px">
          <template #header>
            <div style="display: flex; justify-content: space-between; align-items: center; gap: 8px">
              <span style="font-weight: bold">K线图 · {{ displayName }}</span>
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
            <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 8px">
              <div style="min-width: 0">
                <div style="font-weight: 700; font-size: 16px; line-height: 1.3; overflow: hidden; text-overflow: ellipsis; white-space: nowrap">
                  {{ displayName }}
                </div>
                <div style="font-size: 12px; color: #909399; margin-top: 2px">
                  {{ selectedSymbol }}
                  <template v-if="isHoldingSelected"> · 持仓股分时报价</template>
                  <template v-else> · 自选查看</template>
                </div>
              </div>
              <span v-if="quoteError" style="font-size: 10px; color: #f59e0b; flex-shrink: 0">数据异常</span>
            </div>
          </template>
          <div v-if="quoteError" style="text-align: center; padding: 20px; color: #909399">
            <el-icon :size="32" style="color: #e5e7eb"><WarningFilled /></el-icon>
            <p style="margin-top: 8px">行情数据获取失败</p>
          </div>
          <div v-else-if="quote">
            <div style="display: flex; align-items: baseline; gap: 12px; margin-bottom: 14px; flex-wrap: wrap">
              <span :style="{ fontSize: '28px', fontWeight: 800, color: quoteColor, fontVariantNumeric: 'tabular-nums' }">
                {{ formatPrice(quote.current_price) }}
              </span>
              <span :style="{ fontSize: '16px', fontWeight: 700, color: quoteColor }">
                {{ formatSigned(quote.change) }}
              </span>
              <span :style="{ fontSize: '16px', fontWeight: 700, color: quoteColor }">
                {{ formatPct(quote.change_pct) }}
              </span>
            </div>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px 16px; font-size: 13px">
              <div class="q-row"><span class="q-label">今开</span><span class="q-val">{{ formatPrice(quote.open) }}</span></div>
              <div class="q-row"><span class="q-label">昨收</span><span class="q-val">{{ formatPrice(quote.pre_close) }}</span></div>
              <div class="q-row"><span class="q-label">最高</span><span class="q-val">{{ formatPrice(quote.high) }}</span></div>
              <div class="q-row"><span class="q-label">最低</span><span class="q-val">{{ formatPrice(quote.low) }}</span></div>
              <div class="q-row"><span class="q-label">成交量</span><span class="q-val">{{ formatVolume(quote.volume) }}</span></div>
              <div class="q-row"><span class="q-label">成交额</span><span class="q-val">{{ formatAmount(quote.amount) }}</span></div>
            </div>
            <div v-if="selectedHolding" style="margin-top: 12px; padding-top: 12px; border-top: 1px solid #f0f0f0; font-size: 12px; color: #6b7280; display: grid; grid-template-columns: 1fr 1fr; gap: 8px">
              <div>成本均价 <b style="color:#1f2937">{{ formatPrice(selectedHolding.avg_cost) }}</b></div>
              <div>持仓市值 <b style="color:#1f2937">{{ formatSignedMoney(selectedHolding.market_value, false) }}</b></div>
              <div>浮动盈亏 <b :style="{ color: pctColor(selectedHolding.unrealized_pnl) }">{{ formatSignedMoney(selectedHolding.unrealized_pnl) }}</b></div>
              <div>盈亏比例 <b :style="{ color: pctColor(selectedHolding.unrealized_pnl_pct) }">{{ formatPct(selectedHolding.unrealized_pnl_pct) }}</b></div>
            </div>
          </div>
          <div v-else style="text-align: center; padding: 20px; color: #909399">加载中...</div>
        </el-card>
      </el-col>
    </el-row>
    <el-card v-else shadow="never" style="margin-bottom: 16px">
      <el-empty description="请先买入股票，或在上方搜索标的查看行情" :image-size="72" />
    </el-card>

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
        <el-button type="primary" size="small" style="margin-top: 10px" :loading="sectorsLoading" @click="loadSectors">重试</el-button>
      </div>
      <div v-else-if="sectorsLoading && !sectors.length" style="text-align: center; padding: 20px; color: #909399">加载中...</div>
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
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { marketApi } from '@/api/market'
import { tradingApi } from '@/api/trading'
import { displayStockName, ensureStockNames } from '@/utils/stockNames'
import * as echarts from 'echarts'

const selectedSymbol = ref('')
const selectedPeriod = ref('1d')
const symbols = ref([])
const symbolsLoadError = ref(false)
const symLoading = ref(false)
const quote = ref(null)
const quoteError = ref(false)
const klineError = ref(false)
const sectors = ref([])
const sectorsError = ref(false)
const sectorsLoading = ref(false)
const sectorDialogVisible = ref(false)
const selectedSector = ref(null)
const sectorStocks = ref([])
const sectorStocksLoading = ref(false)
const sectorStocksError = ref(false)
const holdings = ref([])
const holdingsLoading = ref(true)
const holdingQuotes = ref({})
const klineChartRef = ref(null)
let klineChart = null
let quoteInterval = null
let holdingsInterval = null
let sectorsInterval = null

const isHoldingSelected = computed(() =>
  holdings.value.some((h) => h.symbol === selectedSymbol.value)
)

const selectedHolding = computed(() =>
  holdings.value.find((h) => h.symbol === selectedSymbol.value) || null
)

const displayName = computed(() => {
  const fromQuote = (quote.value && quote.value.name) || ''
  if (fromQuote && fromQuote !== selectedSymbol.value) return fromQuote
  const hold = selectedHolding.value
  if (hold) {
    const n = displayStockName(hold) || hold.name
    if (n) return n
  }
  const hit = symbols.value.find((s) => s.code === selectedSymbol.value)
  if (hit && hit.name && hit.name !== hit.code) return hit.name
  return fromQuote || selectedSymbol.value || '—'
})

const quoteColor = computed(() => pctColor(quote.value?.change_pct))

function formatCode(symbol) {
  return (symbol || '').replace('.SZ', '').replace('.SH', '').replace('.BJ', '')
}

function holdingName(h) {
  return displayStockName(h) || h.name || formatCode(h.symbol)
}

function holdingQuote(symbol) {
  return holdingQuotes.value[symbol] || null
}

function pctColor(v) {
  const n = Number(v)
  if (!Number.isFinite(n) || n === 0) return '#374151'
  return n > 0 ? '#ef4444' : '#10b981'
}

function formatPrice(v) {
  const n = Number(v)
  if (!Number.isFinite(n)) return '-'
  return n.toFixed(2)
}

function formatSigned(v) {
  const n = Number(v)
  if (!Number.isFinite(n)) return '-'
  const s = n.toFixed(2)
  return n > 0 ? `+${s}` : s
}

function formatSignedMoney(v, withSign = true) {
  const n = Number(v)
  if (!Number.isFinite(n)) return '-'
  const s = Math.abs(n).toFixed(2)
  if (!withSign) return s
  return n > 0 ? `+${s}` : n < 0 ? `-${s}` : s
}

function formatPct(v) {
  const n = Number(v)
  if (!Number.isFinite(n)) return '-'
  const s = n.toFixed(2)
  return n > 0 ? `+${s}%` : `${s}%`
}

function formatVolume(v) {
  const n = Number(v)
  if (!Number.isFinite(n) || n <= 0) return '-'
  if (n >= 10000) return `${(n / 10000).toFixed(0)} 万股`
  return `${n} 股`
}

function formatAmount(v) {
  const n = Number(v)
  if (!Number.isFinite(n) || n <= 0) return '-'
  if (n >= 1) return `${n.toFixed(2)} 亿元`
  if (n >= 0.01) return `${(n * 10000).toFixed(0)} 万元`
  return `${(n * 1e8).toFixed(0)} 元`
}

function selectSymbol(symbol) {
  if (!symbol || selectedSymbol.value === symbol) {
    if (symbol) loadData()
    return
  }
  selectedSymbol.value = symbol
  loadData()
}

function onSearchChange(val) {
  if (!val) {
    quote.value = null
    if (klineChart) {
      klineChart.dispose()
      klineChart = null
    }
    return
  }
  loadData()
}

async function loadHoldings({ preferKeepSelection = false } = {}) {
  holdingsLoading.value = true
  try {
    const res = await tradingApi.getPositions()
    const rows = (res.data || []).filter((p) => Number(p.quantity) > 0)
    // 同一标的可能多策略拆行：按 symbol 合并展示
    const merged = new Map()
    for (const p of rows) {
      const key = p.symbol
      if (!key) continue
      if (!merged.has(key)) {
        merged.set(key, { ...p })
      } else {
        const cur = merged.get(key)
        const q1 = Number(cur.quantity) || 0
        const q2 = Number(p.quantity) || 0
        const mv1 = Number(cur.market_value) || 0
        const mv2 = Number(p.market_value) || 0
        const pnl1 = Number(cur.unrealized_pnl) || 0
        const pnl2 = Number(p.unrealized_pnl) || 0
        cur.quantity = q1 + q2
        cur.available_quantity = (Number(cur.available_quantity) || 0) + (Number(p.available_quantity) || 0)
        cur.market_value = mv1 + mv2
        cur.unrealized_pnl = pnl1 + pnl2
        const costNotional = (Number(cur.avg_cost) || 0) * q1 + (Number(p.avg_cost) || 0) * q2
        cur.avg_cost = cur.quantity > 0 ? costNotional / cur.quantity : 0
        cur.unrealized_pnl_pct = cur.market_value - cur.unrealized_pnl > 0
          ? (cur.unrealized_pnl / (cur.market_value - cur.unrealized_pnl)) * 100
          : 0
      }
    }
    holdings.value = Array.from(merged.values())
    await ensureStockNames(holdings.value.map((p) => p.symbol))
    await refreshHoldingQuotes()

    const stillSelected = holdings.value.some((h) => h.symbol === selectedSymbol.value)
    if (!preferKeepSelection || !stillSelected) {
      if (holdings.value.length && !stillSelected) {
        selectedSymbol.value = holdings.value[0].symbol
      }
    }
  } catch (e) {
    console.error('loadHoldings error:', e)
    holdings.value = []
  } finally {
    holdingsLoading.value = false
  }
}

async function refreshHoldingQuotes() {
  const list = holdings.value
  if (!list.length) {
    holdingQuotes.value = {}
    return
  }
  const next = { ...holdingQuotes.value }
  await Promise.all(
    list.map(async (h) => {
      try {
        const q = await marketApi.getQuote(h.symbol)
        next[h.symbol] = q
        // 同步持仓现价展示
        if (q && Number(q.current_price) > 0) {
          h.current_price = q.current_price
        }
      } catch {
        /* keep previous */
      }
    })
  )
  holdingQuotes.value = next
  // 若当前选中是持仓股，顺带刷新右侧详情报价
  if (selectedSymbol.value && next[selectedSymbol.value]) {
    quote.value = next[selectedSymbol.value]
    quoteError.value = false
  }
}

async function loadSymbols(query = '') {
  symbolsLoadError.value = false
  try {
    const res = await marketApi.searchSymbols(query)
    const list = res.data || []
    const cur = selectedSymbol.value
    if (cur && !list.some((s) => s.code === cur)) {
      const hold = holdings.value.find((h) => h.symbol === cur)
      list.unshift({ code: cur, name: hold ? holdingName(hold) : cur })
    }
    symbols.value = list
    if (!query && !symbols.value.length) symbolsLoadError.value = true
  } catch (e) {
    console.error('loadSymbols error:', e)
    if (!query) symbolsLoadError.value = true
  }
}

async function remoteSearch(query) {
  const q = (query || '').trim()
  if (!q) {
    await loadSymbols()
    return
  }
  symLoading.value = true
  try {
    await loadSymbols(q)
  } finally {
    symLoading.value = false
  }
}

async function loadData() {
  if (!selectedSymbol.value) {
    quote.value = null
    return
  }
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
  sectorsLoading.value = true
  try {
    const res = await marketApi.getSectors(30)
    sectors.value = (res.data || []).sort((a, b) => b.change_pct - a.change_pct)
    if (!sectors.value.length) {
      sectorsError.value = true
    }
  } catch (e) {
    console.error('loadSectors error:', e)
    sectorsError.value = true
  } finally {
    sectorsLoading.value = false
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
<<<<<<< HEAD
  if (!data.length) return
=======
  if (klineChart) klineChart.dispose()
  if (!data.length || !klineChartRef.value) return
>>>>>>> 4b5774d (feat: add stock recommend, insight popup, and trading UX upgrades)

  // Reuse chart instance: only create once, update data with setOption
  if (!klineChart) {
    klineChart = echarts.init(klineChartRef.value)
  }

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

onMounted(async () => {
  await loadHoldings()
  await loadSymbols()
  if (selectedSymbol.value) {
    await loadData()
  }
  loadSectors()
  quoteInterval = setInterval(() => {
    if (!selectedSymbol.value) return
    // 持仓行情统一走 refreshHoldingQuotes，避免重复请求
    if (isHoldingSelected.value) return
    marketApi.getQuote(selectedSymbol.value).then(r => {
      quote.value = r
      quoteError.value = false
    }).catch(() => {
      quoteError.value = true
    })
  }, 8000)
  holdingsInterval = setInterval(() => {
    refreshHoldingQuotes()
    // 轻量刷新持仓盈亏字段（批量行情后服务端仍有开销，降频到15s）
    tradingApi.getPositions().then((res) => {
      const rows = (res.data || []).filter((p) => Number(p.quantity) > 0)
      if (!rows.length) return
      // 仅更新盈亏数字，不打断当前选中
      const bySym = new Map()
      for (const p of rows) {
        if (!bySym.has(p.symbol)) bySym.set(p.symbol, { ...p })
        else {
          const cur = bySym.get(p.symbol)
          cur.quantity = (Number(cur.quantity) || 0) + (Number(p.quantity) || 0)
          cur.market_value = (Number(cur.market_value) || 0) + (Number(p.market_value) || 0)
          cur.unrealized_pnl = (Number(cur.unrealized_pnl) || 0) + (Number(p.unrealized_pnl) || 0)
        }
      }
      holdings.value = holdings.value.map((h) => {
        const u = bySym.get(h.symbol)
        return u ? { ...h, ...u, name: h.name } : h
      })
    }).catch(() => {})
  }, 15000)
  sectorsInterval = setInterval(() => {
    loadSectors()
  }, 30000)
})

onUnmounted(() => {
  if (klineChart) klineChart.dispose()
  if (quoteInterval) clearInterval(quoteInterval)
  if (holdingsInterval) clearInterval(holdingsInterval)
  if (sectorsInterval) clearInterval(sectorsInterval)
})
</script>

<style scoped>
.q-row {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 8px;
}
.q-label {
  color: #909399;
  flex-shrink: 0;
}
.q-val {
  font-weight: 600;
  color: #1f2937;
  font-variant-numeric: tabular-nums;
  text-align: right;
}
.holding-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 10px;
}
.holding-card {
  text-align: left;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #fff;
  padding: 12px 14px;
  cursor: pointer;
  transition: border-color 0.15s, box-shadow 0.15s;
}
.holding-card:hover {
  border-color: #99e6e6;
}
.holding-card.active {
  border-color: #00B4B4;
  box-shadow: 0 0 0 1px #00B4B4 inset;
  background: #f0fbfb;
}
.holding-top {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 8px;
}
.holding-name {
  font-size: 14px;
  font-weight: 700;
  color: #111827;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.holding-code {
  font-size: 11px;
  color: #9ca3af;
  margin-top: 2px;
}
.holding-px {
  font-size: 18px;
  font-weight: 800;
  font-variant-numeric: tabular-nums;
  flex-shrink: 0;
}
.holding-bottom {
  margin-top: 8px;
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  font-weight: 600;
}
</style>
