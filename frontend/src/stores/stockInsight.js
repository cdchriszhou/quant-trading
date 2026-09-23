import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useStockInsightStore = defineStore('stockInsight', () => {
  const visible = ref(false)
  const symbol = ref('')
  const nameHint = ref('')

  function open(sym, name = '') {
    const s = String(sym || '').trim().toUpperCase()
    if (!s) return
    symbol.value = s
    nameHint.value = name || ''
    visible.value = true
  }

  function close() {
    visible.value = false
  }

  return { visible, symbol, nameHint, open, close }
})
