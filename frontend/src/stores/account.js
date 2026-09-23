import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { tradingApi } from '@/api/trading'
import { ElMessage } from 'element-plus'

export const useAccountStore = defineStore('account', () => {
  const mode = ref(localStorage.getItem('account_mode') || 'paper')
  const allowLive = ref(false)
  const broker = ref(null)
  const feeRates = ref(null)
  const dataPolicy = ref('')
  const loading = ref(false)

  // Account capital snapshot (from /trading/account)
  const initialCash = ref(0)
  const cashBalance = ref(0)
  const totalEquity = ref(0)

  const isPaper = computed(() => mode.value === 'paper')
  const isLive = computed(() => mode.value === 'live')
  const modeLabel = computed(() => (mode.value === 'live' ? '真实账户' : '模拟资金'))

  /** Preferred default capital for forms: account initial cash, else equity/cash. */
  const defaultCapital = computed(() => {
    const n = Number(initialCash.value || totalEquity.value || cashBalance.value || 0)
    return n > 0 ? Math.round(n) : 1000000
  })

  async function refreshSummary() {
    try {
      const res = await tradingApi.getAccount()
      const d = res.data || res
      initialCash.value = Number(d.initial_cash || 0)
      cashBalance.value = Number(d.cash_balance || 0)
      totalEquity.value = Number(d.total_equity || 0)
      if (d.account_mode) {
        mode.value = d.account_mode
        localStorage.setItem('account_mode', mode.value)
      }
      if (d.fee_rates) feeRates.value = d.fee_rates
      if (d.broker) broker.value = d.broker
      if (d.data_policy) dataPolicy.value = d.data_policy
    } catch (e) {
      console.error(e)
    }
  }

  async function refresh() {
    loading.value = true
    try {
      const res = await tradingApi.getAccountMode()
      const d = res.data || res
      mode.value = d.mode || 'paper'
      allowLive.value = !!d.allow_live
      broker.value = d.broker || null
      feeRates.value = d.fee_rates || null
      dataPolicy.value = d.data_policy || ''
      localStorage.setItem('account_mode', mode.value)
      await refreshSummary()
    } catch (e) {
      console.error(e)
    } finally {
      loading.value = false
    }
  }

  async function switchMode(next) {
    if (next === mode.value) return
    loading.value = true
    try {
      const res = await tradingApi.setAccountMode(next)
      const d = res.data || res
      mode.value = d.mode
      broker.value = d.broker || null
      localStorage.setItem('account_mode', mode.value)
      await refreshSummary()
      ElMessage.success(res.message || (next === 'paper' ? '已切换模拟资金' : '已切换真实账户'))
    } catch (e) {
      ElMessage.error(e?.response?.data?.detail || '切换失败')
      throw e
    } finally {
      loading.value = false
    }
  }

  return {
    mode, allowLive, broker, feeRates, dataPolicy, loading,
    initialCash, cashBalance, totalEquity, defaultCapital,
    isPaper, isLive, modeLabel, refresh, refreshSummary, switchMode,
  }
})
