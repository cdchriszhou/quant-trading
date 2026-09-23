<template>
  <el-form ref="formRef" :model="form" :rules="rules" label-width="100px" style="max-width: 600px" class="responsive-form">
    <el-form-item label="策略名称" prop="name">
      <el-input v-model="form.name" placeholder="输入策略名称" />
    </el-form-item>
    <el-form-item label="策略类型" prop="strategy_type">
      <el-select v-model="form.strategy_type" style="width: 100%" @change="onTypeChange">
        <el-option v-for="t in types" :key="t.type" :label="t.name" :value="t.type" />
      </el-select>
    </el-form-item>
    <el-form-item label="交易标的" prop="symbols">
      <el-select
        v-model="form.symbols"
        multiple
        filterable
        remote
        :remote-method="remoteSearchSymbols"
        :loading="symbolLoading"
        style="width: 100%"
        placeholder="输入代码搜索，如 000001"
      >
        <el-option
          v-for="s in symbols"
          :key="s.code"
          :label="`${s.code} - ${s.name || s.code}`"
          :value="s.code"
        />
      </el-select>
    </el-form-item>
    <el-form-item label="时间周期" prop="time_frame">
      <el-select v-model="form.time_frame" style="width: 100%">
        <el-option label="日线" value="1d" />
        <el-option label="周线" value="1w" />
        <el-option label="60分钟" value="60m" />
        <el-option label="30分钟" value="30m" />
      </el-select>
    </el-form-item>
    <el-form-item label="初始资金" prop="initial_capital">
      <el-input-number v-model="form.initial_capital" :min="10000" :step="10000" style="width: 200px" />
      <div style="font-size: 12px; color: #909399; margin-top: 4px">
        默认取自当前账户初始资金（¥{{ accountStore.defaultCapital.toLocaleString() }}）
      </div>
    </el-form-item>
    <el-form-item label="交易模式">
      <el-radio-group v-model="form.mode">
        <el-radio value="paper">模拟交易</el-radio>
        <el-radio value="live" :disabled="!accountStore.allowLive">实盘交易</el-radio>
      </el-radio-group>
      <div style="font-size: 12px; color: #909399; margin-top: 4px">
        <template v-if="accountStore.allowLive">
          实盘需 MiniQMT 已连接；下单走真实券商账户，请谨慎启用
        </template>
        <template v-else>
          实盘未启用：请管理员在「系统管理 → 实盘接入」配置并开启
        </template>
      </div>
    </el-form-item>
    <el-form-item label="策略描述">
      <el-input v-model="form.description" type="textarea" :rows="3" />
    </el-form-item>

    <el-divider content-position="left">策略参数</el-divider>
    <el-form-item v-for="(val, key) in form.parameters" :key="key" :label="paramLabel(key)">
      <el-select v-if="key === 'signal_type'" v-model="form.parameters[key]" style="width: 200px">
        <el-option label="金叉死叉" value="cross" />
      </el-select>
      <el-input v-else-if="typeof val === 'string'" v-model="form.parameters[key]" style="width: 200px" />
      <el-input-number
        v-else-if="['fast_period','slow_period','signal_period','period','grid_levels','interval_days'].includes(key)"
        v-model="form.parameters[key]"
        :min="1"
        :step="1"
        style="width: 200px"
      />
      <template v-else-if="key === 'min_daily_amount'">
        <el-input-number v-model="form.parameters[key]" :min="0" :step="1000000" :precision="0" style="width: 220px" />
        <div style="font-size: 12px; color: #909399; margin-top: 4px">
          单位：元。默认 1000 万（10000000）；5000 万=50000000。过严会筛掉多数中小盘。
        </div>
      </template>
      <el-input-number v-else v-model="form.parameters[key]" :min="0" :step="0.1" style="width: 200px" />
    </el-form-item>

    <el-form-item>
      <el-button type="primary" @click="handleCreate" :loading="loading">创建策略</el-button>
      <el-button @click="emit('cancel')">取消</el-button>
    </el-form-item>
  </el-form>
</template>

<script setup>
import { ref, reactive, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { strategyApi } from '@/api/strategy'
import { marketApi } from '@/api/market'
import { useAccountStore } from '@/stores/account'
import { ElMessage, ElMessageBox } from 'element-plus'
import { paramLabel } from '@/utils/paramLabel'

const props = defineProps({
  /** Prefill from recommend / deep-link */
  prefill: {
    type: Object,
    default: () => ({}),
  },
  /** page: after create navigate; dialog: emit only */
  variant: {
    type: String,
    default: 'page', // 'page' | 'dialog'
  },
})

const emit = defineEmits(['created', 'cancel'])

const router = useRouter()
const accountStore = useAccountStore()
const formRef = ref(null)
const loading = ref(false)
const types = ref([])
const symbols = ref([])
const symbolLoading = ref(false)

const form = reactive({
  name: '',
  strategy_type: 'ma',
  symbols: [],
  time_frame: '1d',
  initial_capital: 1000000,
  mode: 'paper',
  description: '',
  parameters: {},
})

const rules = {
  name: [{ required: true, message: '请输入策略名称', trigger: 'blur' }],
  strategy_type: [{ required: true, message: '请选择策略类型', trigger: 'change' }],
  symbols: [{ type: 'array', required: true, min: 1, message: '请选择交易标的', trigger: 'change' }],
}

function upsertSymbolOption(code, name) {
  if (!code) return
  const cn = (name && name !== code) ? name : ''
  const idx = symbols.value.findIndex((s) => s.code === code)
  if (idx >= 0) {
    const cur = symbols.value[idx]
    if (cn && (!cur.name || cur.name === code)) {
      symbols.value[idx] = { ...cur, name: cn }
    }
  } else {
    symbols.value = [{ code, name: cn || code }, ...symbols.value]
  }
}

async function resolveSymbolName(code, hintName = '') {
  if (hintName && hintName !== code) return hintName
  const hit = symbols.value.find((s) => s.code === code)
  if (hit?.name && hit.name !== code) return hit.name
  try {
    const digits = String(code).replace(/\D/g, '').slice(0, 6)
    const res = await marketApi.searchSymbols(digits || code)
    const list = res.data || []
    const found = list.find((s) => s.code === code) || list[0]
    if (found?.name && found.name !== found.code) return found.name
  } catch {}
  return hintName || code
}

async function remoteSearchSymbols(query) {
  if (!query || query.trim().length < 2) {
    try {
      const res = await marketApi.searchSymbols()
      symbols.value = res.data || []
    } catch {}
    return
  }
  symbolLoading.value = true
  try {
    const res = await marketApi.searchSymbols(query.trim())
    symbols.value = res.data || []
  } catch {
    symbols.value = []
  } finally {
    symbolLoading.value = false
  }
}

async function onTypeChange(type) {
  try {
    const res = await strategyApi.getDefaultParams(type)
    form.parameters = res.params || {}
  } catch {
    form.parameters = {}
  }
}

async function applyPrefill(p) {
  if (!p || typeof p !== 'object') return
  if (p.strategy_type) form.strategy_type = String(p.strategy_type)
  if (p.name) form.name = String(p.name)
  if (p.description != null) form.description = String(p.description)
  if (p.capital != null) {
    const cap = Number(p.capital)
    if (cap >= 10000) form.initial_capital = Math.round(cap)
  }
  if (p.symbol) {
    const sym = String(p.symbol)
    const cn = await resolveSymbolName(sym, p.symbol_name || p.stock_name || '')
    upsertSymbolOption(sym, cn)
    form.symbols = [sym]
  }
}

async function handleCreate() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  if (form.mode === 'live' && !accountStore.allowLive) {
    ElMessage.warning('实盘未启用，请先配置 ALLOW_LIVE_TRADING 与 MiniQMT')
    return
  }

  loading.value = true
  try {
    const payload = { ...form, status: 'stopped' }
    const res = await strategyApi.create(payload)
    const created = res.data || res
    ElMessage.success('策略创建成功')
    emit('created', created)

    if (props.variant === 'dialog') return

    try {
      const tip = form.mode === 'live'
        ? '实盘策略建议先回测验证参数再启动。是否立即回测？'
        : '建议先回测验证参数，再启动模拟运行。是否立即回测？'
      await ElMessageBox.confirm(
        tip,
        '下一步',
        { confirmButtonText: '去回测', cancelButtonText: '查看详情', type: 'info', distinguishCancelAndClose: true }
      )
      router.push({ path: '/backtest', query: { strategy_id: created.id } })
    } catch (action) {
      if (action === 'cancel') {
        router.push(`/strategies/${created.id}`)
      } else {
        router.push('/strategies')
      }
    }
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '创建失败')
  } finally {
    loading.value = false
  }
}

watch(
  () => props.prefill,
  (p) => { applyPrefill(p) },
  { deep: true }
)

onMounted(async () => {
  try {
    const [, tRes, sRes] = await Promise.all([
      accountStore.refresh(),
      strategyApi.getTypes(),
      marketApi.searchSymbols(),
    ])
    types.value = tRes.data || []
    symbols.value = sRes.data || []
    form.mode = accountStore.mode || 'paper'
    if (!accountStore.allowLive && form.mode === 'live') {
      form.mode = 'paper'
    }
    form.initial_capital = accountStore.defaultCapital
    await applyPrefill(props.prefill)
    if (types.value.length) {
      await onTypeChange(form.strategy_type)
    }
  } catch (e) {
    console.error(e)
  }
})
</script>
