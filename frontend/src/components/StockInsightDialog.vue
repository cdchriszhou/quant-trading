<template>
  <el-dialog
    :model-value="store.visible"
    :title="dialogTitle"
    width="720px"
    top="6vh"
    destroy-on-close
    append-to-body
    class="stock-insight-dialog"
    @close="store.close()"
  >
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
        <el-tabs v-model="tab">
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
        </el-tabs>
      </template>
    </div>
  </el-dialog>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { marketApi } from '@/api/market'
import { useStockInsightStore } from '@/stores/stockInsight'
import { ElMessage } from 'element-plus'

const store = useStockInsightStore()
const loading = ref(false)
const error = ref('')
const data = ref(null)
const tab = ref('market')

const market = computed(() => data.value?.market || {})
const company = computed(() => data.value?.company || {})
const news = computed(() => data.value?.news || [])

const dialogTitle = computed(() => {
  const name = data.value?.name || store.nameHint
  const sym = store.symbol
  return name ? `${name}（${sym}）` : (sym || '股票详情')
})

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
  // quote.amount is often already in 亿元
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

async function load() {
  if (!store.symbol) return
  loading.value = true
  error.value = ''
  data.value = null
  tab.value = 'market'
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
  }
)
</script>

<style scoped>
.insight-body {
  min-height: 220px;
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
  max-height: 220px;
  overflow-y: auto;
}
.news-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 420px;
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
</style>
