<template>
  <button
    type="button"
    class="stock-ticker"
    :title="titleText"
    @click.stop="onClick"
  >
    <span v-if="showCode" class="st-code">{{ codeText }}</span>
    <span v-if="showName && nameText" class="st-name" :class="{ 'st-name-alone': !showCode }">{{ nameText }}</span>
    <slot />
  </button>
</template>

<script setup>
import { computed } from 'vue'
import { displayStockName } from '@/utils/stockNames'
import { useStockInsightStore } from '@/stores/stockInsight'

const props = defineProps({
  symbol: { type: String, required: true },
  name: { type: String, default: '' },
  /** row object with symbol / symbol_name / name */
  row: { type: Object, default: null },
  showCode: { type: Boolean, default: true },
  showName: { type: Boolean, default: true },
  bareCode: { type: Boolean, default: true },
})

const store = useStockInsightStore()

const resolvedSymbol = computed(() => {
  return props.symbol || props.row?.symbol || ''
})

const codeText = computed(() => {
  const s = resolvedSymbol.value || ''
  if (!props.bareCode) return s
  return s.replace('.SZ', '').replace('.SH', '').replace('.BJ', '')
})

const nameText = computed(() => {
  if (props.name) return props.name
  if (props.row) return displayStockName(props.row) || props.row.name || ''
  return displayStockName(resolvedSymbol.value) || ''
})

const titleText = computed(() => {
  const parts = [resolvedSymbol.value, nameText.value].filter(Boolean)
  return `${parts.join(' · ')}（点击查看详情）`
})

function onClick() {
  store.open(resolvedSymbol.value, nameText.value)
}
</script>

<style scoped>
.stock-ticker {
  display: inline-flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 1px;
  padding: 0;
  margin: 0;
  border: none;
  background: transparent;
  cursor: pointer;
  text-align: left;
  line-height: 1.25;
  max-width: 100%;
}
.st-code {
  font-weight: 700;
  font-size: 12px;
  color: #1a1a1a;
}
.st-name {
  font-size: 11px;
  color: #9ca3af;
}
.st-name-alone {
  font-size: 12px;
  color: #1a1a1a;
  font-weight: 600;
}
.stock-ticker:hover .st-code,
.stock-ticker:hover .st-name-alone {
  color: var(--gp-cyan, #00B4B4);
  text-decoration: underline;
}
.stock-ticker:hover .st-name {
  color: #6b7280;
}
</style>
