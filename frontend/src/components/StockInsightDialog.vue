<template>
  <el-dialog
    :model-value="store.visible"
    :title="dialogTitle"
    :width="fullscreen ? '100%' : `${dlgWidth}px`"
    :fullscreen="fullscreen"
    :top="fullscreen ? '0' : '4vh'"
    draggable
    overflow
    destroy-on-close
    append-to-body
    align-center
    class="stock-insight-dialog"
    @close="onClose"
    @opened="onOpened"
  >
    <template #header="{ titleId, titleClass }">
      <div class="dlg-header">
        <span :id="titleId" :class="titleClass" class="dlg-title">{{ dialogTitle }}</span>
        <el-button
          class="dlg-fs-btn"
          text
          size="small"
          :title="fullscreen ? '退出全屏' : '全屏'"
          @click.stop="toggleFullscreen"
        >
          <el-icon :size="16"><FullScreen /></el-icon>
        </el-button>
      </div>
    </template>

    <div v-loading="loading" class="insight-body">
      <el-alert
        v-if="error"
        type="warning"
        :closable="false"
        show-icon
        :title="error"
        style="margin-bottom: 12px"
      />

      <template v-if="data">
        <el-tabs v-model="tab" class="insight-tabs">
          <el-tab-pane label="行情" name="market">
            <div class="quote-head">
              <div>
                <div class="qh-name">{{ data.name || store.nameHint || data.symbol }}</div>
                <div class="qh-code">{{ data.symbol }}</div>
              </div>
              <div class="qh-price" :style="{ color: changeColor }">
                <div class="qh-px">{{ fmtPrice(market.current_price) }}</div>
                <div class="qh-chg">
                  {{ fmtSigned(market.change) }}
                  （{{ fmtSigned(market.change_pct) }}%）
                </div>
              </div>
            </div>
            <el-row :gutter="10" class="metric-grid">
              <el-col :xs="12" :sm="8" v-for="item in marketItems" :key="item.label">
                <div class="metric">
                  <div class="m-label">{{ item.label }}</div>
                  <div class="m-value">{{ item.value }}</div>
                </div>
              </el-col>
            </el-row>
          </el-tab-pane>

          <el-tab-pane label="公司信息" name="company">
            <el-descriptions :column="2" border size="small" class="responsive-descriptions">
              <el-descriptions-item label="公司简称">{{ company.name || '—' }}</el-descriptions-item>
              <el-descriptions-item label="所属行业">{{ company.industry || '—' }}</el-descriptions-item>
              <el-descriptions-item label="所属地区">{{ company.region || '—' }}</el-descriptions-item>
              <el-descriptions-item label="上市日期">{{ company.list_date || '—' }}</el-descriptions-item>
              <el-descriptions-item label="成立日期">{{ company.found_date || '—' }}</el-descriptions-item>
              <el-descriptions-item label="员工人数">{{ company.employees || '—' }}</el-descriptions-item>
              <el-descriptions-item label="法人代表">{{ company.chairman || '—' }}</el-descriptions-item>
              <el-descriptions-item label="董秘">{{ company.secretary || '—' }}</el-descriptions-item>
              <el-descriptions-item label="官网" :span="2">
                <a v-if="company.website" :href="normalizeUrl(company.website)" target="_blank" rel="noopener">{{ company.website }}</a>
                <span v-else>—</span>
              </el-descriptions-item>
              <el-descriptions-item label="办公地址" :span="2">{{ company.office || '—' }}</el-descriptions-item>
              <el-descriptions-item label="主营业务" :span="2">{{ company.main_business || '—' }}</el-descriptions-item>
              <el-descriptions-item label="公司简介" :span="2">
                <div class="intro">{{ company.intro || '暂无简介' }}</div>
              </el-descriptions-item>
            </el-descriptions>
          </el-tab-pane>

          <el-tab-pane label="新闻公告" name="news">
            <el-empty v-if="!news.length" description="暂无相关新闻/公告" :image-size="64" />
            <div v-else class="news-list">
              <a
                v-for="(n, i) in news"
                :key="i"
                class="news-item"
                :href="n.url || undefined"
                :target="n.url ? '_blank' : undefined"
                :rel="n.url ? 'noopener' : undefined"
                @click="onNewsClick($event, n)"
              >
                <div class="news-title">
                  <el-tag v-if="n.type === 'announcement'" size="small" type="warning" effect="plain">公告</el-tag>
                  <el-tag v-else size="small" type="info" effect="plain">新闻</el-tag>
                  <span>{{ n.title }}</span>
                </div>
                <div class="news-meta">
                  <span>{{ n.source || '—' }}</span>
                  <span>{{ n.time || '' }}</span>
                </div>
              </a>
            </div>
          </el-tab-pane>

          <el-tab-pane label="K线图" name="kline" lazy>
            <div class="kline-toolbar">
              <el-radio-group v-model="klinePeriod" size="small" @change="loadKline">
                <el-radio-button value="1d">日K</el-radio-button>
                <el-radio-button value="1w">周K</el-radio-button>
                <el-radio-button value="1h">60分</el-radio-button>
                <el-radio-button value="15m">15分</el-radio-button>
              </el-radio-group>
              <el-button text size="small" :loading="klineLoading" @click="loadKline">刷新</el-button>
            </div>
            <div v-loading="klineLoading" class="kline-wrap">
              <div v-if="klineError" class="kline-empty">
                <p>{{ klineError }}</p>
                <el-button size="small" type="primary" plain @click="loadKline">重试</el-button>
              </div>
              <div v-else ref="klineChartRef" class="kline-chart"></div>
            </div>
          </el-tab-pane>
        </el-tabs>
      </template>
    </div>

    <div
      v-if="!fullscreen"
      class="resize-handle"
      title="拖动缩放"
      @mousedown.prevent="startResize"
    />
  </el-dialog>
</template>

<script setup>
import { ref, computed, watch, nextTick, onBeforeUnmount } from 'vue'
import * as echarts from 'echarts'
import { FullScreen } from '@element-plus/icons-vue'
import { marketApi } from '@/api/market'
import { useStockInsightStore } from '@/stores/stockInsight'
import { ElMessage } from 'element-plus'

const MIN_W = 520
const MIN_H = 420
const DEFAULT_W = 780
const DEFAULT_H = 640

const store = useStockInsightStore()
const loading = ref(false)
const error = ref('')
const data = ref(null)
const tab = ref('market')

const dlgWidth = ref(DEFAULT_W)
const dlgHeight = ref(DEFAULT_H)
const fullscreen = ref(false)
let resizing = false

const klinePeriod = ref('1d')
const klineLoading = ref(false)
const klineError = ref('')
const klineChartRef = ref(null)
let klineChart = null
let klineLoadedFor = ''

const market = computed(() => data.value?.market || {})
const company = computed(() => data.value?.company || {})
const news = computed(() => data.value?.news || [])

const dialogTitle = computed(() => {
  const name = data.value?.name || store.nameHint
  const sym = store.symbol
  return name ? `${name}（${sym}）` : (sym || '股票详情')
})

function getDialogEl() {
  return document.querySelector('.el-dialog.stock-insight-dialog')
}

function applyDlgSize() {
  const el = getDialogEl()
  if (!el) return
  if (fullscreen.value) {
    el.style.height = ''
    el.style.maxHeight = ''
    return
  }
  el.style.height = `${dlgHeight.value}px`
  el.style.maxHeight = '92vh'
  el.style.display = 'flex'
  el.style.flexDirection = 'column'
}

const changeColor = computed(() => {
  const n = Number(market.value.change_pct)
  if (!Number.isFinite(n) || n === 0) return '#1a1a1a'
  return n > 0 ? '#ef4444' : '#10b981'
})

const marketItems = computed(() => {
  const m = market.value
  return [
    { label: '今开', value: fmtPrice(m.open) },
    { label: '最高', value: fmtPrice(m.high) },
    { label: '最低', value: fmtPrice(m.low) },
    { label: '昨收', value: fmtPrice(m.pre_close) },
    { label: '成交量', value: fmtVol(m.volume) },
    { label: '成交额', value: fmtAmount(m.amount) },
    { label: '换手率', value: fmtPct(m.turnover_rate) },
    { label: '振幅', value: fmtPct(m.amplitude) },
    { label: '量比', value: fmtNum(m.volume_ratio) },
    { label: '市盈率', value: fmtNum(m.pe) },
    { label: '市净率', value: fmtNum(m.pb) },
    { label: '总市值', value: fmtYi(m.total_market_cap) },
    { label: '流通市值', value: fmtYi(m.circ_market_cap) },
    { label: '涨停', value: fmtPrice(m.limit_up) },
    { label: '跌停', value: fmtPrice(m.limit_down) },
  ]
})

function fmtPrice(v) {
  const n = Number(v)
  if (!Number.isFinite(n) || n <= 0) return '—'
  return n >= 100 ? n.toFixed(2) : n.toFixed(3)
}
function fmtSigned(v) {
  const n = Number(v)
  if (!Number.isFinite(n)) return '—'
  return `${n >= 0 ? '+' : ''}${n.toFixed(2)}`
}
function fmtNum(v) {
  const n = Number(v)
  if (!Number.isFinite(n) || n === 0) return '—'
  return n.toFixed(2)
}
function fmtPct(v) {
  const n = Number(v)
  if (!Number.isFinite(n) || n === 0) return '—'
  return `${n.toFixed(2)}%`
}
function fmtVol(v) {
  const n = Number(v)
  if (!Number.isFinite(n) || n <= 0) return '—'
  if (n >= 1e8) return `${(n / 1e8).toFixed(2)}亿手`
  if (n >= 1e4) return `${(n / 1e4).toFixed(2)}万手`
  return `${n}`
}
function fmtAmount(v) {
  const n = Number(v)
  if (!Number.isFinite(n) || n <= 0) return '—'
  if (n < 1000) return `${n.toFixed(2)}亿`
  if (n >= 1e8) return `${(n / 1e8).toFixed(2)}亿`
  return n.toLocaleString()
}
function fmtYi(v) {
  const n = Number(v)
  if (!Number.isFinite(n) || n <= 0) return '—'
  return `${n.toFixed(2)}亿`
}
function normalizeUrl(u) {
  if (!u) return '#'
  if (/^https?:\/\//i.test(u)) return u
  return `https://${u}`
}
function onNewsClick(e, n) {
  if (!n?.url) {
    e.preventDefault()
    ElMessage.info('暂无原文链接')
  }
}

function clamp(n, min, max) {
  return Math.min(max, Math.max(min, n))
}

function resizeKlineChart() {
  nextTick(() => klineChart?.resize())
}

function toggleFullscreen() {
  fullscreen.value = !fullscreen.value
  nextTick(() => {
    applyDlgSize()
    resizeKlineChart()
  })
}

function startResize(e) {
  if (fullscreen.value) return
  resizing = true
  const startX = e.clientX
  const startY = e.clientY
  const startW = dlgWidth.value
  const startH = dlgHeight.value
  const maxW = Math.floor(window.innerWidth * 0.96)
  const maxH = Math.floor(window.innerHeight * 0.92)

  const onMove = (ev) => {
    if (!resizing) return
    dlgWidth.value = clamp(startW + (ev.clientX - startX), MIN_W, maxW)
    dlgHeight.value = clamp(startH + (ev.clientY - startY), MIN_H, maxH)
    applyDlgSize()
    resizeKlineChart()
  }
  const onUp = () => {
    resizing = false
    document.removeEventListener('mousemove', onMove)
    document.removeEventListener('mouseup', onUp)
    document.body.style.cursor = ''
    document.body.style.userSelect = ''
    applyDlgSize()
    resizeKlineChart()
  }
  document.body.style.cursor = 'nwse-resize'
  document.body.style.userSelect = 'none'
  document.addEventListener('mousemove', onMove)
  document.addEventListener('mouseup', onUp)
}

function onOpened() {
  applyDlgSize()
  resizeKlineChart()
}

function onClose() {
  disposeKline()
  store.close()
}

function disposeKline() {
  if (klineChart) {
    klineChart.dispose()
    klineChart = null
  }
  klineLoadedFor = ''
}

function renderKline(rows) {
  if (!klineChartRef.value) return
  if (!klineChart) {
    klineChart = echarts.init(klineChartRef.value)
  }
  const dates = rows.map((d) => d.date || d.time || '')
  const values = rows.map((d) => [d.open, d.close, d.low, d.high])
  const vols = rows.map((d) => d.volume || 0)
  klineChart.setOption({
    animation: false,
    tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
    axisPointer: { link: [{ xAxisIndex: 'all' }] },
    grid: [
      { left: 48, right: 16, top: 24, height: '58%' },
      { left: 48, right: 16, top: '78%', height: '14%' },
    ],
    xAxis: [
      { type: 'category', data: dates, gridIndex: 0, boundaryGap: true, axisLabel: { show: false }, axisTick: { show: false } },
      { type: 'category', data: dates, gridIndex: 1, boundaryGap: true, axisLabel: { rotate: 0, fontSize: 10, color: '#9ca3af' } },
    ],
    yAxis: [
      { type: 'value', gridIndex: 0, scale: true, splitLine: { lineStyle: { color: '#f3f4f6' } }, axisLabel: { fontSize: 10 } },
      { type: 'value', gridIndex: 1, scale: true, splitNumber: 2, axisLabel: { show: false }, splitLine: { show: false } },
    ],
    dataZoom: [
      { type: 'inside', xAxisIndex: [0, 1], start: 40, end: 100 },
    ],
    series: [
      {
        type: 'candlestick',
        data: values,
        xAxisIndex: 0,
        yAxisIndex: 0,
        itemStyle: {
          color: '#ef4444',
          color0: '#10b981',
          borderColor: '#ef4444',
          borderColor0: '#10b981',
        },
      },
      {
        type: 'bar',
        data: vols,
        xAxisIndex: 1,
        yAxisIndex: 1,
        itemStyle: {
          color: (p) => {
            const row = rows[p.dataIndex]
            if (!row) return 'rgba(156,163,175,0.45)'
            return Number(row.close) >= Number(row.open)
              ? 'rgba(239,68,68,0.35)'
              : 'rgba(16,185,129,0.35)'
          },
        },
      },
    ],
  }, true)
  nextTick(() => klineChart?.resize())
}

async function loadKline() {
  const symbol = store.symbol || data.value?.symbol
  if (!symbol) return
  klineLoading.value = true
  klineError.value = ''
  try {
    const res = await marketApi.getKline(symbol, klinePeriod.value, 120)
    const rows = res.data || res || []
    if (!Array.isArray(rows) || !rows.length) {
      klineError.value = '暂无K线数据'
      disposeKline()
      return
    }
    klineLoadedFor = `${symbol}:${klinePeriod.value}`
    await nextTick()
    renderKline(rows)
  } catch (e) {
    klineError.value = e?.response?.data?.detail || e?.message || 'K线加载失败'
    disposeKline()
  } finally {
    klineLoading.value = false
  }
}

async function load() {
  if (!store.symbol) return
  loading.value = true
  error.value = ''
  data.value = null
  tab.value = 'market'
  disposeKline()
  klineError.value = ''
  klinePeriod.value = '1d'
  fullscreen.value = false
  dlgWidth.value = DEFAULT_W
  dlgHeight.value = DEFAULT_H
  try {
    const res = await marketApi.getStockInsight(store.symbol)
    data.value = res.data || res
  } catch (e) {
    error.value = e?.response?.data?.detail || e?.message || '加载失败'
  } finally {
    loading.value = false
  }
}

watch(
  () => [store.visible, store.symbol],
  ([vis]) => {
    if (vis && store.symbol) load()
    if (!vis) disposeKline()
  }
)

watch(tab, async (name) => {
  if (name !== 'kline') return
  const key = `${store.symbol}:${klinePeriod.value}`
  await nextTick()
  if (klineLoadedFor !== key || !klineChart) {
    await loadKline()
  } else {
    klineChart?.resize()
  }
})

watch(fullscreen, () => nextTick(() => {
  applyDlgSize()
  resizeKlineChart()
}))

onBeforeUnmount(() => disposeKline())
</script>

<style scoped>
.dlg-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding-right: 28px;
  width: 100%;
}
.dlg-title {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 16px;
  font-weight: 600;
}
.dlg-fs-btn {
  flex-shrink: 0;
  margin-right: 4px;
}
.insight-body {
  flex: 1;
  min-height: 0;
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.insight-tabs {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}
.insight-tabs :deep(.el-tabs__content) {
  flex: 1;
  min-height: 0;
  overflow: auto;
}
.insight-tabs :deep(.el-tab-pane) {
  height: 100%;
}
.quote-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 14px;
}
.qh-name {
  font-size: 18px;
  font-weight: 700;
  color: #1a1a1a;
}
.qh-code {
  font-size: 12px;
  color: #9ca3af;
  margin-top: 2px;
}
.qh-price {
  text-align: right;
}
.qh-px {
  font-size: 24px;
  font-weight: 800;
  font-variant-numeric: tabular-nums;
}
.qh-chg {
  font-size: 13px;
  margin-top: 2px;
}
.metric {
  background: #f9fafb;
  border-radius: 6px;
  padding: 8px 10px;
  margin-bottom: 8px;
}
.m-label {
  font-size: 11px;
  color: #9ca3af;
}
.m-value {
  font-size: 14px;
  font-weight: 600;
  color: #1a1a1a;
  margin-top: 2px;
  font-variant-numeric: tabular-nums;
}
.intro {
  white-space: pre-wrap;
  line-height: 1.55;
  color: #374151;
  max-height: 280px;
  overflow-y: auto;
}
.news-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: none;
  height: 100%;
  overflow-y: auto;
}
.news-item {
  display: block;
  padding: 10px 12px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  text-decoration: none;
  color: inherit;
  transition: border-color 0.15s, background 0.15s;
}
.news-item:hover {
  border-color: #00B4B4;
  background: rgba(0, 180, 180, 0.04);
}
.news-title {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  font-size: 13px;
  font-weight: 600;
  color: #1a1a1a;
  line-height: 1.4;
}
.news-meta {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  margin-top: 6px;
  font-size: 11px;
  color: #9ca3af;
}
.kline-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
  flex-wrap: wrap;
}
.kline-wrap {
  flex: 1;
  min-height: 280px;
  height: calc(100% - 40px);
  position: relative;
}
.kline-chart {
  width: 100%;
  height: 100%;
  min-height: 280px;
}
.kline-empty {
  height: 100%;
  min-height: 280px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  color: #9ca3af;
  font-size: 13px;
}
.resize-handle {
  position: absolute;
  right: 2px;
  bottom: 2px;
  width: 16px;
  height: 16px;
  cursor: nwse-resize;
  z-index: 10;
  background:
    linear-gradient(135deg, transparent 0 45%, #c0c4cc 45% 55%, transparent 55% 70%, #c0c4cc 70% 80%, transparent 80%);
  border-radius: 0 0 4px 0;
}
.resize-handle:hover {
  background:
    linear-gradient(135deg, transparent 0 45%, #00B4B4 45% 55%, transparent 55% 70%, #00B4B4 70% 80%, transparent 80%);
}
</style>

<style>
/* teleported dialog — unscoped flex layout */
.stock-insight-dialog.el-dialog {
  display: flex;
  flex-direction: column;
  max-width: 96vw;
  position: relative;
  overflow: hidden;
}
.stock-insight-dialog .el-dialog__header {
  flex-shrink: 0;
  margin-right: 0;
  padding-right: 16px;
}
.stock-insight-dialog .el-dialog__body {
  flex: 1;
  min-height: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  padding-bottom: 20px;
  position: relative;
}
.stock-insight-dialog.is-fullscreen {
  margin: 0 !important;
  height: 100vh !important;
  max-height: 100vh !important;
}
</style>
