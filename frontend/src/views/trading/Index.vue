<template>
  <el-row :gutter="16">
    <el-col :xs="24" :md="8">
      <el-card shadow="never">
        <template #header>
          <div style="display: flex; justify-content: space-between; align-items: center">
            <span style="font-weight: bold">下单交易</span>
            <el-tag :type="accountStore.isLive ? 'danger' : 'info'" size="small" effect="plain">
              {{ accountStore.modeLabel }}
            </el-tag>
          </div>
        </template>
        <TradeOrderForm :prefill="prefill" variant="page" @account-refresh="loadAccount" />
      </el-card>
    </el-col>
    <el-col :xs="24" :md="16">
      <el-card shadow="never" style="margin-bottom: 14px">
        <template #header>
          <div style="display: flex; justify-content: space-between; align-items: center">
            <span style="font-weight: bold">账户概览</span>
            <span style="font-size: 12px; color: #6b7280">
              {{ account?.broker?.message || accountStore.dataPolicy }}
            </span>
          </div>
        </template>
        <el-row :gutter="12" v-if="account">
          <el-col :xs="12" :sm="8" v-for="(item, idx) in accountItems" :key="idx">
            <div style="text-align: center; padding: 8px; background: #f9f9f9; border-radius: 4px; margin-bottom: 8px">
              <div style="color: #909399; font-size: 12px">{{ item.label }}</div>
              <div style="font-size: 18px; font-weight: bold" :style="{ color: item.color || '#1a1a1a' }">{{ item.value }}</div>
            </div>
          </el-col>
        </el-row>
      </el-card>

      <el-card shadow="never" v-if="accountStore.isPaper">
        <template #header><span style="font-weight: bold">模拟资金设置</span></template>
        <div style="display: flex; gap: 12px; align-items: center; flex-wrap: wrap">
          <span style="font-size: 13px; color: #6b7280">初始模拟资金</span>
          <el-input-number v-model="simCash" :min="1000" :step="100000" />
          <el-button type="primary" plain @click="saveSimCash">保存</el-button>
        </div>
      </el-card>
    </el-col>
  </el-row>
</template>

<script setup>
<<<<<<< HEAD
import { ref, reactive, onMounted, computed, watch } from 'vue'
=======
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
>>>>>>> 4b5774d (feat: add stock recommend, insight popup, and trading UX upgrades)
import { tradingApi } from '@/api/trading'
import { useAccountStore } from '@/stores/account'
import { ElMessage } from 'element-plus'
import TradeOrderForm from './TradeOrderForm.vue'

const route = useRoute()
const accountStore = useAccountStore()
const account = ref(null)
const simCash = ref(1000000)

const prefill = computed(() => {
  const q = route.query || {}
  return {
    symbol: q.symbol ? String(q.symbol) : undefined,
    symbol_name: q.symbol_name ? String(q.symbol_name) : undefined,
    quantity: q.quantity != null ? Number(q.quantity) : undefined,
    side: q.side ? String(q.side) : undefined,
    price: q.price != null ? Number(q.price) : undefined,
  }
})

const accountItems = computed(() => {
  if (!account.value) return []
  const a = account.value
  const pnl = a.total_pnl || 0
  const retPct = a.total_return_pct || 0
  return [
    { label: '账户模式', value: a.account_mode === 'live' ? '真实' : '模拟' },
    { label: '总资产', value: `¥${(a.total_equity || 0).toLocaleString()}` },
    { label: '可用资金', value: `¥${(a.cash_balance || 0).toLocaleString()}` },
    { label: '持仓市值', value: `¥${(a.market_value || 0).toLocaleString()}` },
    { label: '累计盈亏', value: `¥${pnl.toLocaleString()}`, color: pnl > 0 ? '#ef4444' : pnl < 0 ? '#10b981' : undefined },
    { label: '收益率', value: `${retPct.toFixed(2)}%`, color: retPct > 0 ? '#ef4444' : retPct < 0 ? '#10b981' : undefined },
  ]
})

async function loadAccount() {
  try {
    const res = await tradingApi.getAccount()
    account.value = res.data
<<<<<<< HEAD
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
=======
    if (res.data?.initial_cash) simCash.value = res.data.initial_cash
  } catch (e) {
    console.error(e)
  }
}

async function saveSimCash() {
  try {
    await tradingApi.setSimulatedCash(simCash.value)
    ElMessage.success('模拟资金已更新')
    loadAccount()
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '保存失败')
  }
}

onMounted(async () => {
  await accountStore.refresh()
>>>>>>> 4b5774d (feat: add stock recommend, insight popup, and trading UX upgrades)
  loadAccount()
})

// Auto-update price when symbol changes
watch(() => form.symbol, (newSymbol) => {
  if (newSymbol) {
    marketApi.getQuote(newSymbol).then(r => { form.price = r.current_price }).catch(() => {})
  }
}, { immediate: true })
</script>
