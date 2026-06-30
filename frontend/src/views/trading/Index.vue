<template>
  <el-row :gutter="16">
    <el-col :xs="24" :md="8">
      <el-card shadow="never">
        <template #header><span style="font-weight: bold">下单交易</span></template>
        <el-form label-width="80px" size="small">
          <el-form-item label="标的">
            <el-select v-model="form.symbol" filterable remote :remote-method="remoteSearch" :loading="symLoading" style="width: 100%" placeholder="输入代码搜索，如 000001">
              <el-option v-for="s in symbols" :key="s.code" :label="`${s.code} - ${s.name}`" :value="s.code" />
            </el-select>
          </el-form-item>
          <el-form-item label="方向">
            <el-radio-group v-model="form.side">
              <el-radio-button value="buy" style="color: #f56c6c">买入</el-radio-button>
              <el-radio-button value="sell" style="color: #67c23a">卖出</el-radio-button>
            </el-radio-group>
          </el-form-item>
          <el-form-item label="价格">
            <el-input-number v-model="form.price" :min="0.01" :step="0.01" style="width: 200px" />
          </el-form-item>
          <el-form-item label="数量">
            <el-input-number v-model="form.quantity" :min="100" :step="100" style="width: 200px" />
          </el-form-item>
          <el-form-item label="备注">
            <el-input v-model="form.remark" placeholder="可选" />
          </el-form-item>
          <el-form-item label="模式">
            <el-radio-group v-model="form.mode">
              <el-radio value="paper">模拟交易</el-radio>
              <el-radio value="live">实盘交易</el-radio>
            </el-radio-group>
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="placeOrder" :loading="loading" style="width: 100%">
              提交{{ form.side === 'buy' ? '买入' : '卖出' }}订单
            </el-button>
          </el-form-item>
        </el-form>

        <el-alert v-if="riskWarnings.length" :title="riskWarnings[0].rule_name" type="warning" show-icon :closable="false" style="margin-top: 12px">
          <template #default>
            <div v-for="w in riskWarnings" :key="w.rule_id">{{ w.rule_name }}: 当前值 {{ w.current_value }}, 阈值 {{ w.threshold }}</div>
          </template>
        </el-alert>
      </el-card>
    </el-col>
    <el-col :xs="24" :md="16">
      <el-card shadow="never">
        <template #header><span style="font-weight: bold">账户概览</span></template>
        <el-row :gutter="12" v-if="account">
          <el-col :xs="12" :sm="8" v-for="(item, idx) in accountItems" :key="idx">
            <div style="text-align: center; padding: 8px; background: #f9f9f9; border-radius: 4px; margin-bottom: 8px">
              <div style="color: #909399; font-size: 12px">{{ item.label }}</div>
              <div style="font-size: 18px; font-weight: bold" :style="{ color: item.color || '#1a1a1a' }">{{ item.value }}</div>
            </div>
          </el-col>
        </el-row>
      </el-card>
    </el-col>
  </el-row>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { tradingApi } from '@/api/trading'
import { marketApi } from '@/api/market'
import { riskApi } from '@/api/risk'
import { ElMessage } from 'element-plus'

const symbols = ref([])
const symLoading = ref(false)
const account = ref(null)
const loading = ref(false)

async function remoteSearch(query) {
  if (!query || query.trim().length < 2) {
    try { const r = await marketApi.searchSymbols(); symbols.value = r.data || [] } catch {}
    return
  }
  symLoading.value = true
  try { const r = await marketApi.searchSymbols(query.trim()); symbols.value = r.data || [] } catch {}
  finally { symLoading.value = false }
}
const riskWarnings = ref([])

const form = reactive({
  symbol: '000001.SZ',
  side: 'buy',
  price: 10,
  quantity: 100,
  remark: '',
  mode: 'paper',
})

const accountItems = computed(() => {
  if (!account.value) return []
  const a = account.value
  const pnl = a.total_pnl || 0
  const retPct = a.total_return_pct || 0
  return [
    { label: '总资产', value: `¥${(a.total_equity || 0).toLocaleString()}`, color: undefined },
    { label: '可用资金', value: `¥${(a.cash_balance || 0).toLocaleString()}`, color: undefined },
    { label: '持仓市值', value: `¥${(a.market_value || 0).toLocaleString()}`, color: undefined },
    { label: '累计盈亏', value: `¥${pnl.toLocaleString()}`, color: pnl > 0 ? '#ef4444' : pnl < 0 ? '#10b981' : undefined },
    { label: '持仓数量', value: `${a.position_count || 0}`, color: undefined },
    { label: '收益率', value: `${retPct.toFixed(2)}%`, color: retPct > 0 ? '#ef4444' : retPct < 0 ? '#10b981' : undefined },
  ]
})

async function placeOrder() {
  loading.value = true
  riskWarnings.value = []
  try {
    const res = await tradingApi.placeOrder(form)
    if (res.status === 'rejected') {
      riskWarnings.value = res.violations || []
      ElMessage.warning('订单被风控拦截')
    } else {
      ElMessage.success('订单已提交')
      loadAccount()
    }
  } catch (e) {
    ElMessage.error('下单失败')
  } finally {
    loading.value = false
  }
}

async function loadAccount() {
  try {
    const res = await tradingApi.getAccount()
    account.value = res.data
  } catch (e) { console.error(e) }
}

async function loadSymbols() {
  try {
    const res = await marketApi.searchSymbols()
    symbols.value = res.data || []
  } catch (e) { console.error(e) }
}

onMounted(() => {
  loadSymbols()
  loadAccount()
  // Update quote price
  if (form.symbol) {
    marketApi.getQuote(form.symbol).then(r => { form.price = r.current_price }).catch(() => {})
  }
})
</script>
