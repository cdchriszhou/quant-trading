<template>
  <div>
    <el-alert
      type="warning"
      :closable="false"
      show-icon
      style="margin-bottom: 14px"
      title="重要说明：宁缺毋滥，不保证盈利"
      description="每只票均按真实日K结构筛选（趋势/回踩MA20/量能/低点抬高/盈亏比）。达不到结构门槛不会凑数推荐；止损止盈仅供风控参考。"
    />

    <el-card shadow="never" style="margin-bottom: 14px">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px">
          <span style="font-weight: 700">短期持仓推荐（匹配当前资金）</span>
          <el-button type="primary" :loading="loading" @click="() => load(true)">刷新推荐</el-button>
        </div>
      </template>

      <div style="font-size: 12px; color: #909399; margin: -4px 0 12px">
        调整仓位、持有天数或盈亏比后，需手动点击「刷新推荐」才会重新计算
      </div>
      <el-form label-position="top" class="rec-form" size="small">
        <el-row :gutter="16">
          <el-col :xs="24" :md="14">
            <el-form-item label="单票仓位上限">
              <div class="pos-controls">
                <el-radio-group v-model="sizingMode" size="small" @change="onSizingModeChange">
                  <el-radio-button label="pct">按比例</el-radio-button>
                  <el-radio-button label="amount">按金额</el-radio-button>
                  <el-radio-button label="full">全仓进场</el-radio-button>
                </el-radio-group>

                <div v-if="sizingMode === 'pct'" class="pos-row">
                  <el-button-group>
                    <el-button
                      v-for="p in pctPresets"
                      :key="p"
                      size="small"
                      :type="maxPosPct === p ? 'primary' : 'default'"
                      @click="maxPosPct = p"
                    >{{ p }}%</el-button>
                  </el-button-group>
                  <el-input-number
                    v-model="maxPosPct"
                    :min="5"
                    :max="100"
                    :step="5"
                    controls-position="right"
                    style="width: 120px"
                  />
                  <span class="hint">占可用资金</span>
                </div>

                <div v-else-if="sizingMode === 'amount'" class="pos-row">
                  <template v-if="amountMax > 0">
                    <el-button-group>
                      <el-button
                        v-for="a in visibleAmountPresets"
                        :key="a"
                        size="small"
                        :type="budgetAmount === a ? 'primary' : 'default'"
                        @click="setBudgetAmount(a)"
                      >{{ formatWan(a) }}</el-button>
                      <el-button
                        size="small"
                        :type="budgetAmount === amountMax ? 'primary' : 'default'"
                        @click="setBudgetAmount(amountMax)"
                      >全部资产</el-button>
                    </el-button-group>
                    <el-input-number
                      v-model="budgetAmount"
                      :min="amountMin"
                      :max="amountMax"
                      :step="1000"
                      :precision="0"
                      controls-position="right"
                      style="width: 160px"
                      @change="clampBudgetToEquity"
                    />
                    <span class="hint">元 · 上限 ¥{{ amountMax.toLocaleString() }}（总资产）</span>
                  </template>
                  <span v-else class="hint">正在读取总资产…</span>
                </div>

                <div v-else class="pos-row">
                  <span class="full-tip">按可用现金 100% 计算买入量（仍受一手与费用约束）</span>
                </div>
              </div>
            </el-form-item>
          </el-col>

          <el-col :xs="12" :md="5">
            <el-form-item label="计划持有">
              <el-input-number v-model="holdDays" :min="3" :max="20" style="width: 100%" />
              <span class="hint">交易日</span>
            </el-form-item>
          </el-col>

          <el-col :xs="12" :md="5">
            <el-form-item>
              <template #label>
                <span>最低盈亏比</span>
                <el-tooltip placement="top" :show-after="200">
                  <template #content>
                    <div style="max-width: 240px; line-height: 1.5">
                      盈亏比 = 潜在盈利 ÷ 潜在亏损。<br />
                      例如 2:1 表示：止盈空间至少是止损风险的 2 倍，才纳入推荐。
                    </div>
                  </template>
                  <span class="label-help">?</span>
                </el-tooltip>
              </template>
              <div class="rr-controls">
                <el-button-group>
                  <el-button
                    v-for="opt in rrPresets"
                    :key="opt.value"
                    size="small"
                    :type="minRr === opt.value ? 'primary' : 'default'"
                    @click="minRr = opt.value"
                  >{{ opt.label }}</el-button>
                </el-button-group>
                <div class="rr-custom">
                  <el-input-number
                    v-model="minRr"
                    :min="1"
                    :max="5"
                    :step="0.1"
                    :precision="1"
                    controls-position="right"
                    style="width: 110px"
                  />
                  <span class="rr-suffix">: 1</span>
                </div>
                <div class="rr-explain">{{ rrExplain }}</div>
              </div>
            </el-form-item>
          </el-col>

          <el-col :xs="24" :md="24">
            <el-form-item label="LLM 融合参考">
              <div class="llm-row">
                <el-checkbox v-model="useLlm" :disabled="!llmAnyConfigured">
                  多模型融合点评（不改变量化硬过滤）
                </el-checkbox>
                <el-checkbox-group
                  v-if="useLlm"
                  v-model="selectedLlmProviders"
                  class="llm-provider-group"
                >
                  <el-checkbox
                    v-for="p in llmProviders"
                    :key="p.id"
                    :label="p.id"
                    :disabled="!p.configured"
                  >{{ p.configured ? p.name : `${p.name}（未配置）` }}</el-checkbox>
                </el-checkbox-group>
                <span v-if="!llmAnyConfigured" class="hint">
                  管理员尚未配置 API Key（系统管理 → 大模型接入）
                </span>
                <span v-else-if="useLlm" class="hint">
                  并行调用勾选模型并投票共识；留空勾选则用全部已配置模型
                </span>
              </div>
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>

      <el-alert
        v-if="meta && meta.open_allowed === false"
        type="warning"
        :closable="false"
        show-icon
        style="margin-bottom: 12px"
        :title="meta.market_env?.message || '大盘环境不适合新开仓'"
        :description="meta.empty_reason || '已与策略执行器对齐：空头/震荡时锁定买入推荐。'"
      />
      <el-alert
        v-else-if="meta?.strategy_health?.strategies"
        type="info"
        :closable="false"
        show-icon
        style="margin-bottom: 12px"
        title="策略近期健康度（滚动信号，用于推荐加权）"
        :description="healthSummary"
      />

      <el-alert
        v-if="meta?.llm?.summary"
        type="success"
        :closable="false"
        show-icon
        style="margin-bottom: 12px"
        :title="`LLM 融合总评（${meta.llm.provider_name || meta.llm.provider}）`"
        :description="meta.llm.partial_error
          ? `${meta.llm.summary}\n（部分模型失败：${meta.llm.partial_error}）`
          : meta.llm.summary"
      />
      <el-alert
        v-else-if="meta?.llm?.error"
        type="warning"
        :closable="false"
        show-icon
        style="margin-bottom: 12px"
        :title="meta.llm.error"
      />
      <el-row :gutter="12" v-if="meta">
        <el-col :xs="12" :sm="6">
          <div class="meta-box">
            <div class="meta-label">总资产</div>
            <div class="meta-value">¥ {{ (meta.total_equity ?? meta.cash)?.toLocaleString() }}</div>
          </div>
        </el-col>
        <el-col :xs="12" :sm="6">
          <div class="meta-box">
            <div class="meta-label">可用资金</div>
            <div class="meta-value">¥ {{ meta.cash?.toLocaleString() }}</div>
          </div>
        </el-col>
        <el-col :xs="12" :sm="6">
          <div class="meta-box">
            <div class="meta-label">单票预算</div>
            <div class="meta-value">¥ {{ meta.budget_per_name?.toLocaleString() }}</div>
            <div class="meta-sub">{{ filterSummary }}</div>
          </div>
        </el-col>
        <el-col :xs="12" :sm="6">
          <div class="meta-box">
            <div class="meta-label">开仓 / 大盘</div>
            <div class="meta-value" :style="{ color: envColor }">
              {{ openPolicyText }} · {{ envText }}
              <span style="color: #6b7280; font-weight: 500; font-size: 13px">
                · {{ meta.scan_stats?.qualified || 0 }}/{{ meta.scan_stats?.scanned || 0 }}
              </span>
            </div>
          </div>
        </el-col>
      </el-row>
    </el-card>

    <el-card shadow="never">
      <div v-if="rows.length" style="overflow-x: auto">
        <el-table :data="rows" stripe size="small">
          <el-table-column prop="rank" label="#" width="50" />
          <el-table-column label="标的" width="150">
            <template #default="{ row }">
              <StockTicker :symbol="row.symbol" :name="row.name" :row="row" />
            </template>
          </el-table-column>
          <el-table-column label="结构/加权" width="90">
            <template #default="{ row }">
              <span style="font-weight: 700; color: #00B4B4">{{ row.adjusted_score ?? row.score }}</span>
              <div v-if="row.adjusted_score != null && row.adjusted_score !== row.score" style="font-size: 11px; color: #9ca3af">
                结构 {{ row.score }}
              </div>
            </template>
          </el-table-column>
          <el-table-column prop="price" label="现价" width="80" />
          <el-table-column label="建议买入" width="110">
            <template #default="{ row }">
              {{ row.suggested_quantity }} 股
              <div style="font-size: 11px; color: #9ca3af">{{ row.suggested_lots }} 手</div>
            </template>
          </el-table-column>
          <el-table-column label="预计花费" width="110">
            <template #default="{ row }">
              ¥{{ row.estimated_cost?.toLocaleString() }}
              <div style="font-size: 11px; color: #9ca3af">占资金 {{ row.cash_usage_pct }}%</div>
            </template>
          </el-table-column>
          <el-table-column label="止损 / 止盈" width="140">
            <template #default="{ row }">
              <div style="color: #10b981">{{ row.stop_loss }} ({{ row.stop_loss_pct }}%)</div>
              <div style="color: #ef4444">{{ row.take_profit }} (+{{ row.take_profit_pct }}%)</div>
            </template>
          </el-table-column>
          <el-table-column label="盈亏比" width="90">
            <template #default="{ row }">
              <span style="font-weight: 600">{{ Number(row.risk_reward).toFixed(1) }} : 1</span>
            </template>
          </el-table-column>
          <el-table-column label="近5日" width="80">
            <template #default="{ row }">
              <span :style="{ color: row.ret_5d_pct >= 0 ? '#ef4444' : '#10b981' }">
                {{ row.ret_5d_pct > 0 ? '+' : '' }}{{ row.ret_5d_pct }}%
              </span>
            </template>
          </el-table-column>
          <el-table-column label="匹配策略" width="150">
            <template #default="{ row }">
              <div style="font-weight: 600; color: #1a1a1a">{{ row.suggested_strategy?.name || '—' }}</div>
              <el-tag
                v-if="row.strategy_health_status"
                size="small"
                :type="healthTagType(row.strategy_health_status)"
                style="margin: 2px 0"
              >{{ healthLabel(row.strategy_health_status) }} ×{{ row.strategy_health_weight ?? '—' }}</el-tag>
              <div style="font-size: 11px; color: #9ca3af; line-height: 1.3">{{ row.suggested_strategy?.why }}</div>
            </template>
          </el-table-column>
          <el-table-column v-if="meta?.llm?.enabled" label="LLM 融合" min-width="200">
            <template #default="{ row }">
              <div style="display: flex; align-items: center; gap: 6px; margin-bottom: 4px; flex-wrap: wrap">
                <el-tag
                  v-if="row.llm_bias"
                  size="small"
                  :type="row.llm_bias === '偏多' ? 'danger' : row.llm_bias === '谨慎' ? 'warning' : 'info'"
                >{{ row.llm_bias }}</el-tag>
                <span v-if="row.llm_agree" style="font-size: 11px; color: #9ca3af">共识 {{ row.llm_agree }}</span>
              </div>
              <div style="font-size: 12px; color: #4b5563; line-height: 1.35">{{ row.llm_note || '—' }}</div>
            </template>
          </el-table-column>
          <el-table-column label="理由" min-width="180">
            <template #default="{ row }">
              <el-tag v-for="(r, i) in (row.reasons || []).slice(0, 4)" :key="i" size="small" style="margin: 2px" type="info">{{ r }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="220" fixed="right">
            <template #default="{ row }">
              <el-button text type="primary" size="small" @click="goTrade(row)">去下单</el-button>
              <el-button text type="success" size="small" @click="goStrategy(row)">用此策略</el-button>
              <el-button text size="small" @click="showPlan(row)">计划</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
      <el-empty v-else-if="!loading" :description="emptyHint" />
    </el-card>

    <el-dialog
      v-model="createDialogVisible"
      title="创建策略"
      width="640px"
      top="5vh"
      destroy-on-close
      append-to-body
      class="strategy-create-dialog"
    >
      <StrategyCreateForm
        v-if="createDialogVisible"
        :key="createPrefillKey"
        :prefill="createPrefill"
        variant="dialog"
        @cancel="createDialogVisible = false"
        @created="onStrategyCreated"
      />
    </el-dialog>

    <el-dialog
      v-model="tradeDialogVisible"
      :title="tradeDialogTitle"
      width="480px"
      top="8vh"
      destroy-on-close
      append-to-body
    >
      <TradeOrderForm
        v-if="tradeDialogVisible"
        :key="tradePrefillKey"
        :prefill="tradePrefill"
        variant="dialog"
        @cancel="tradeDialogVisible = false"
        @submitted="onOrderSubmitted"
      />
    </el-dialog>
  </div>
</template>

<script setup>
defineOptions({ name: 'Recommend' })
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { recommendApi } from '@/api/recommend'
import { tradingApi } from '@/api/trading'
import { useAccountStore } from '@/stores/account'
import { ElMessage, ElMessageBox } from 'element-plus'
import StrategyCreateForm from '@/views/strategy/StrategyCreateForm.vue'
import TradeOrderForm from '@/views/trading/TradeOrderForm.vue'

const router = useRouter()
const accountStore = useAccountStore()
const loading = ref(false)
const meta = ref(null)
const rows = ref([])
/** 是否已手动点过「刷新推荐」 */
const hasFetched = ref(false)
/** 独立缓存总资产，避免推荐接口未返回时误显示大额快捷项 */
const totalEquity = ref(0)

const createDialogVisible = ref(false)
const createPrefill = ref({})
const createPrefillKey = ref(0)

const tradeDialogVisible = ref(false)
const tradePrefill = ref({})
const tradePrefillKey = ref(0)
const tradeDialogTitle = computed(() => {
  const p = tradePrefill.value || {}
  const name = p.symbol_name || p.symbol || ''
  return name ? `下单 · ${name}` : '下单交易'
})

/** pct | amount | full */
const sizingMode = ref('pct')
const maxPosPct = ref(25)
const budgetAmount = ref(0)
const holdDays = ref(7)
/** 最低盈亏比：N 表示 N:1 */
const minRr = ref(1.5)
const useLlm = ref(false)
const selectedLlmProviders = ref([])
const llmProviders = ref([])
const llmAnyConfigured = ref(false)

const pctPresets = [25, 50, 75, 100]
const amountPresets = [10000, 30000, 50000, 100000, 200000]
const rrPresets = [
  { value: 1.5, label: '1.5:1' },
  { value: 2, label: '2:1' },
  { value: 3, label: '3:1' },
]

const amountMax = computed(() => {
  const eq = Number(meta.value?.total_equity || totalEquity.value || 0)
  if (eq > 0) return Math.floor(eq)
  const cash = Number(meta.value?.cash || 0)
  return cash > 0 ? Math.floor(cash) : 0
})

const amountMin = computed(() => {
  const max = amountMax.value
  if (!max) return 0
  return Math.min(1000, max)
})

const visibleAmountPresets = computed(() => {
  const max = amountMax.value
  if (!max) return []
  // 只展示不超过总资产的档位；总资产本身用「全部资产」按钮
  return amountPresets.filter((a) => a < max)
})

const rrExplain = computed(() => {
  const n = Number(minRr.value) || 1.5
  return `只推荐：止盈空间 ≥ 止损风险的 ${n.toFixed(1)} 倍`
})

const envText = computed(() => {
  const s = meta.value?.market_env?.env_state
  if (s === 'bull') return '多头'
  if (s === 'bear') return '空头'
  return '震荡'
})
const openPolicyText = computed(() => {
  if (meta.value?.open_allowed === false || meta.value?.open_policy === 'blocked') return '锁定开仓'
  return '允许开仓'
})
const envColor = computed(() => {
  const s = meta.value?.market_env?.env_state
  if (s === 'bull') return '#ef4444'
  if (s === 'bear') return '#10b981'
  return '#f59e0b'
})
const healthSummary = computed(() => {
  const strategies = meta.value?.strategy_health?.strategies || {}
  const parts = Object.values(strategies).map((s) => {
    const wr = s.win_rate != null ? `胜率${s.win_rate}%` : '样本少'
    const ar = s.avg_fwd_5d_pct != null ? `5日${s.avg_fwd_5d_pct > 0 ? '+' : ''}${s.avg_fwd_5d_pct}%` : ''
    return `${s.name}：${healthLabel(s.status)}（${wr}${ar ? ' / ' + ar : ''}，权重${s.weight}）`
  })
  return parts.join('；') || '暂无策略健康度'
})
const emptyHint = computed(() => {
  if (!hasFetched.value) {
    return '请先设置筛选条件，再点击右上角「刷新推荐」'
  }
  if (meta.value?.empty_reason) return meta.value.empty_reason
  if (meta.value?.open_allowed === false) {
    return '大盘环境与执行器一致，暂不给出新开仓推荐'
  }
  return '暂无匹配当前资金的候选，可调高单票仓位、降低盈亏比后再点「刷新推荐」'
})

function healthLabel(status) {
  const map = {
    healthy: '健康',
    ok: '尚可',
    weak: '偏弱',
    cold: '偏冷',
    scarce: '样本少',
    unknown: '未知',
  }
  return map[status] || status || '未知'
}
function healthTagType(status) {
  if (status === 'healthy') return 'success'
  if (status === 'ok') return ''
  if (status === 'weak' || status === 'scarce') return 'warning'
  if (status === 'cold') return 'danger'
  return 'info'
}

const filterSummary = computed(() => {
  const d = meta.value
  if (!d) return ''
  const rr = d.min_risk_reward != null ? `${Number(d.min_risk_reward).toFixed(1)}:1` : '-'
  const mode = d.sizing_mode === 'full' ? '全仓' : d.sizing_mode === 'amount' ? '金额' : `${Math.round((d.max_position_pct || 0) * 100)}%`
  const q = d.min_pattern_score != null ? `结构分≥${d.min_pattern_score}` : 'K线精选'
  return `${mode} · ${q} · 盈亏比≥${rr}`
})

function formatWan(n) {
  if (n >= 10000) return `${n / 10000}万`
  return `${n}`
}

function setBudgetAmount(n) {
  const max = amountMax.value
  if (!max) return
  budgetAmount.value = Math.max(amountMin.value, Math.min(Math.floor(n), max))
}

function clampBudgetToEquity() {
  const max = amountMax.value
  if (!max) {
    budgetAmount.value = 0
    return
  }
  if (!budgetAmount.value || budgetAmount.value < amountMin.value) {
    budgetAmount.value = Math.min(max, Math.max(amountMin.value, max))
    return
  }
  if (budgetAmount.value > max) {
    budgetAmount.value = max
  }
}

watch(amountMax, (max) => {
  if (max > 0) clampBudgetToEquity()
})

let _reqSeq = 0

function onSizingModeChange(mode) {
  // Element Plus 可能传 string，统一写入
  if (mode === 'pct' || mode === 'amount' || mode === 'full') {
    sizingMode.value = mode
  }
  if (sizingMode.value === 'full') {
    maxPosPct.value = 100
  } else if (sizingMode.value === 'pct' && maxPosPct.value >= 100) {
    maxPosPct.value = 25
  } else if (sizingMode.value === 'amount') {
    clampBudgetToEquity()
  }
}

function buildParams(forceRefresh = true) {
  const params = {
    max_results: 8,
    hold_days: holdDays.value,
    min_rr: Math.max(1, Number(minRr.value) || 1.5),
  }
  if (forceRefresh) params.refresh = true
  if (sizingMode.value === 'full') {
    params.max_position_pct = 1
  } else   if (sizingMode.value === 'amount') {
    clampBudgetToEquity()
    params.budget_amount = budgetAmount.value
    params.max_position_pct = 1
  } else {
    params.max_position_pct = Math.min(1, Math.max(0.05, maxPosPct.value / 100))
  }
  if (useLlm.value) {
    params.use_llm = true
    if (selectedLlmProviders.value.length) {
      params.llm_providers = selectedLlmProviders.value.join(',')
    }
  }
  return params
}

async function refreshEquity() {
  try {
    const res = await tradingApi.getAccount()
    const d = res.data || res
    totalEquity.value = Number(d.total_equity || 0)
    if (totalEquity.value > 0) clampBudgetToEquity()
  } catch (e) {
    console.error(e)
  }
}

async function load(forceRefresh = true) {
  const seq = ++_reqSeq
  loading.value = true
  try {
    if (!totalEquity.value) await refreshEquity()
    if (seq !== _reqSeq) return
    const res = await recommendApi.shortHold(buildParams(forceRefresh))
    if (seq !== _reqSeq) return
    const d = res.data || res
    meta.value = d
    hasFetched.value = true
    if (d.total_equity) totalEquity.value = Number(d.total_equity)
    rows.value = Array.isArray(d.recommendations) ? [...d.recommendations] : []
    clampBudgetToEquity()
    if (!rows.value.length) {
      ElMessage.info(d.empty_reason || '当前无符合 K 线结构门槛的推荐')
    } else {
      ElMessage.success(`按日K结构精选 ${rows.value.length} 只（宁缺毋滥）`)
    }
  } catch (e) {
    if (seq !== _reqSeq) return
    ElMessage.error(e?.response?.data?.detail || e?.message || '推荐生成失败')
  } finally {
    if (seq === _reqSeq) loading.value = false
  }
}

function goTrade(row) {
  tradePrefill.value = {
    symbol: row.symbol,
    symbol_name: row.name || '',
    quantity: row.suggested_quantity,
    side: 'buy',
    price: row.price,
    remark: `推荐买入 ${row.name || row.symbol}`,
  }
  tradePrefillKey.value += 1
  tradeDialogVisible.value = true
}

function onOrderSubmitted() {
  tradeDialogVisible.value = false
  refreshEquity()
}

function goStrategy(row) {
  const st = row.suggested_strategy || {}
  createPrefill.value = {
    strategy_type: st.type || 'right_side_entry',
    symbol: row.symbol,
    symbol_name: row.name || '',
    name: `${st.name || '短线策略'}-${row.name || row.symbol}`,
    capital: Math.max(10000, Math.ceil(row.estimated_cost || 10000)),
    description: st.why || '',
  }
  createPrefillKey.value += 1
  createDialogVisible.value = true
}

async function onStrategyCreated(created) {
  createDialogVisible.value = false
  const id = created?.id
  if (!id) {
    ElMessage.success('策略已创建')
    return
  }
  // 等创建弹窗完全关闭后再弹确认，避免遮罩/焦点把路由弄乱
  await nextTick()
  try {
    await ElMessageBox.confirm(
      '策略已创建。推荐结果会保留，从回测页返回后无需重新推荐。',
      '下一步',
      {
        confirmButtonText: '去回测',
        cancelButtonText: '留在本页',
        type: 'success',
        distinguishCancelAndClose: true,
      }
    )
    await router.push({
      name: 'Backtest',
      query: { strategy_id: String(id), from: 'recommend' },
    })
  } catch {
    // 留在推荐页
  }
}

function showPlan(row) {
  const st = row.suggested_strategy || {}
  const body = [
    row.action_plan || '',
    st.name ? `\n\n匹配策略：${st.name}` : '',
    st.why ? `\n匹配原因：${st.why}` : '',
    st.playbook ? `\n${st.playbook}` : '',
  ].join('')
  ElMessageBox.alert(body, `${row.name} 操作计划`, { confirmButtonText: '知道了' })
}

onMounted(async () => {
  await accountStore.refresh()
  await refreshEquity()
  try {
    const res = await recommendApi.llmOptions()
    const d = res.data || res
    llmProviders.value = d.providers || []
    llmAnyConfigured.value = !!d.any_configured
    // 默认勾选全部已配置模型，走融合
    selectedLlmProviders.value = (d.providers || [])
      .filter((p) => p.configured)
      .map((p) => p.id)
    if (!llmAnyConfigured.value) useLlm.value = false
  } catch {
    llmAnyConfigured.value = false
  }
  // 不自动拉推荐：仅在用户点击「刷新推荐」后执行
})
</script>

<style scoped>
.rec-form :deep(.el-form-item) {
  margin-bottom: 12px;
}
.pos-controls {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.pos-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}
.hint {
  margin-left: 4px;
  color: #6b7280;
  font-size: 12px;
}
.full-tip {
  font-size: 12px;
  color: #6b7280;
}
.llm-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
}
.llm-provider-group {
  display: inline-flex;
  flex-wrap: wrap;
  gap: 4px 12px;
}
.label-help {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 14px;
  height: 14px;
  margin-left: 4px;
  border-radius: 50%;
  background: #e5e7eb;
  color: #6b7280;
  font-size: 10px;
  cursor: help;
  vertical-align: middle;
}
.rr-controls {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.rr-custom {
  display: flex;
  align-items: center;
  gap: 4px;
}
.rr-suffix {
  color: #374151;
  font-weight: 600;
  font-size: 13px;
}
.rr-explain {
  font-size: 12px;
  color: #6b7280;
  line-height: 1.4;
}
.meta-box {
  background: #f9fafb;
  border-radius: 8px;
  padding: 10px 12px;
  margin-bottom: 10px;
}
.meta-label {
  font-size: 11px;
  color: #9ca3af;
}
.meta-value {
  font-size: 16px;
  font-weight: 700;
  margin-top: 4px;
  color: #111827;
}
.meta-sub {
  font-size: 11px;
  color: #9ca3af;
  margin-top: 2px;
}
</style>
