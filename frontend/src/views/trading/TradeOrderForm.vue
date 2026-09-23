<template>
  <div>
    <el-alert
      type="info"
      :closable="false"
      show-icon
      style="margin-bottom: 12px"
      title="行情真实 · 费率真实 · 资金可切换"
      description="模拟资金仅替换账户余额；报价/成交价/印花税/佣金/过户费均按 A 股真实规则。"
    />
    <el-form label-width="80px" size="small" @submit.prevent>
      <el-form-item label="标的">
        <el-select
          v-model="form.symbol"
          filterable
          remote
          :remote-method="remoteSearch"
          :loading="symLoading"
          style="width: 100%"
          placeholder="输入代码搜索"
          @change="onSymbolChange"
        >
          <el-option
            v-for="s in symbols"
            :key="s.code"
            :label="`${s.code} - ${s.name || s.code}`"
            :value="s.code"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="方向">
        <el-radio-group v-model="form.side" @change="refreshFee">
          <el-radio-button value="buy">买入</el-radio-button>
          <el-radio-button value="sell">卖出</el-radio-button>
        </el-radio-group>
      </el-form-item>
      <el-form-item label="价格">
        <el-input-number v-model="form.price" :min="0.01" :step="0.01" style="width: 200px" @change="refreshFee" />
        <el-button text size="small" style="margin-left: 8px" @click="onSymbolChange(form.symbol)">刷新报价</el-button>
      </el-form-item>
      <el-form-item label="数量">
        <el-input-number v-model="form.quantity" :min="100" :step="100" style="width: 200px" @change="refreshFee" />
      </el-form-item>
      <el-form-item label="备注">
        <el-input v-model="form.remark" placeholder="可选" />
      </el-form-item>
      <el-form-item v-if="fee" label="费用预估">
        <div style="font-size: 12px; line-height: 1.7; color: #4b5563">
          <div>成交额 ¥{{ fee.amount?.toFixed(2) }}</div>
          <div>佣金 ¥{{ fee.commission?.toFixed(2) }}（万{{ ((fee.rates?.commission_rate || 0) * 10000).toFixed(1) }}，最低{{ fee.rates?.min_commission }}）</div>
          <div>印花税 ¥{{ fee.stamp_duty?.toFixed(2) }}（卖出 {{ ((fee.rates?.stamp_duty_rate || 0) * 100).toFixed(2) }}%）</div>
          <div>过户费 ¥{{ fee.transfer_fee?.toFixed(2) }}</div>
          <div style="font-weight: 700; color: #1a1a1a">合计费用 ¥{{ fee.total?.toFixed(2) }}</div>
        </div>
      </el-form-item>
      <el-form-item>
        <el-button
          :type="form.side === 'buy' ? 'danger' : 'success'"
          native-type="button"
          :loading="loading"
          style="width: 100%"
          @click="placeOrder"
        >
          {{ accountStore.isLive ? '实盘' : '模拟' }}{{ form.side === 'buy' ? '买入' : '卖出' }}
        </el-button>
        <el-button v-if="variant === 'dialog'" style="width: 100%; margin-left: 0; margin-top: 8px" @click="emit('cancel')">
          取消
        </el-button>
      </el-form-item>
    </el-form>

    <el-alert
      v-if="riskWarnings.length"
      :title="riskWarnings[0].rule_name"
      type="warning"
      show-icon
      :closable="false"
      style="margin-top: 12px"
    >
      <template #default>
        <div v-for="w in riskWarnings" :key="w.rule_id">{{ w.rule_name }}: 当前值 {{ w.current_value }}, 阈值 {{ w.threshold }}</div>
      </template>
    </el-alert>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, watch } from 'vue'
import { tradingApi } from '@/api/trading'
import { marketApi } from '@/api/market'
import { useAccountStore } from '@/stores/account'
import { ElMessage, ElMessageBox } from 'element-plus'

const props = defineProps({
  prefill: {
    type: Object,
    default: () => ({}),
  },
  variant: {
    type: String,
    default: 'page', // 'page' | 'dialog'
  },
})

const emit = defineEmits(['submitted', 'cancel', 'account-refresh'])

const accountStore = useAccountStore()
const symbols = ref([])
const symLoading = ref(false)
const loading = ref(false)
const fee = ref(null)
const riskWarnings = ref([])

const form = reactive({
  symbol: '000001.SZ',
  side: 'buy',
  price: null,
  quantity: 100,
  remark: '',
  mode: accountStore.mode,
})

watch(() => accountStore.mode, (m) => {
  form.mode = m
})

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

async function remoteSearch(query) {
  if (!query || query.trim().length < 2) {
    try {
      const r = await marketApi.searchSymbols()
      symbols.value = r.data || []
    } catch {}
    return
  }
  symLoading.value = true
  try {
    const r = await marketApi.searchSymbols(query.trim())
    symbols.value = r.data || []
  } catch {
    symbols.value = []
  } finally {
    symLoading.value = false
  }
}

async function refreshFee() {
  if (!form.price || !form.quantity) return
  try {
    const res = await tradingApi.feePreview(form.side, form.price, form.quantity)
    fee.value = res.data
  } catch {
    fee.value = null
  }
}

async function onSymbolChange(symbol) {
  if (!symbol) return
  try {
    const r = await marketApi.getQuote(symbol)
    if (r?._fallback || r?.data_source === 'simulated') {
      ElMessage.error('未拿到真实行情，请稍后重试')
      return
    }
    form.price = r.current_price
    await refreshFee()
  } catch {
    ElMessage.error('真实行情获取失败')
  }
}

async function applyPrefill(p) {
  if (!p || typeof p !== 'object') return
  if (p.symbol) {
    const sym = String(p.symbol)
    upsertSymbolOption(sym, p.symbol_name || p.name || '')
    form.symbol = sym
  }
  if (p.quantity != null) {
    const q = Number(p.quantity)
    if (q >= 100) form.quantity = Math.floor(q / 100) * 100
  }
  if (p.side) form.side = String(p.side)
  if (p.remark) form.remark = String(p.remark)
  // 始终拉最新报价；推荐里的 price 仅作兜底展示
  if (form.symbol) {
    await onSymbolChange(form.symbol)
    if ((!form.price || form.price <= 0) && p.price != null && Number(p.price) > 0) {
      form.price = Number(p.price)
      await refreshFee()
    }
  }
}

async function placeOrder() {
  if (!form.price || form.price <= 0) {
    ElMessage.error('请先获取真实行情价格后再下单')
    return
  }
  if (accountStore.isLive) {
    try {
      await ElMessageBox.confirm('确认向真实券商账户提交订单？', '实盘确认', { type: 'warning' })
    } catch {
      return
    }
  }
  loading.value = true
  riskWarnings.value = []
  form.mode = accountStore.mode
  try {
    const res = await tradingApi.placeOrder({ ...form })
    if (res.status === 'rejected') {
      riskWarnings.value = res.violations || []
      ElMessage.warning(res.message || '订单被拒绝')
      if (res.fee_preview) fee.value = res.fee_preview
    } else {
      ElMessage.success('订单已提交')
      if (res.fee_preview) fee.value = res.fee_preview
      emit('submitted', res)
      emit('account-refresh')
    }
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '下单失败')
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
  await accountStore.refresh()
  form.mode = accountStore.mode
  try {
    const res = await marketApi.searchSymbols()
    symbols.value = res.data || []
  } catch {}
  await applyPrefill(props.prefill)
  if (!props.prefill?.symbol) {
    await onSymbolChange(form.symbol)
  }
})
</script>
