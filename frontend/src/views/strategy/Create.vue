<template>
  <div>
    <el-card shadow="never">
      <template #header><span style="font-weight: bold">创建策略</span></template>
      <StrategyCreateForm :prefill="prefill" variant="page" @cancel="router.back()" />
    </el-card>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import StrategyCreateForm from './StrategyCreateForm.vue'

const router = useRouter()
const route = useRoute()

const prefill = computed(() => {
  const q = route.query || {}
  return {
    strategy_type: q.strategy_type ? String(q.strategy_type) : undefined,
    symbol: q.symbol ? String(q.symbol) : undefined,
    symbol_name: q.symbol_name ? String(q.symbol_name) : undefined,
    name: q.name ? String(q.name) : undefined,
    description: q.description != null ? String(q.description) : undefined,
    capital: q.capital != null ? Number(q.capital) : undefined,
  }
})
</script>
