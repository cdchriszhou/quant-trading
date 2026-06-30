<template>
  <div>
    <el-card shadow="never" style="margin-bottom: 16px">
      <template #header><span style="font-weight: bold">持仓查询</span></template>
      <div v-if="positions.length" style="overflow-x: auto; -webkit-overflow-scrolling: touch">
        <el-table :data="positions" stripe size="small">
        <el-table-column prop="symbol" label="标的" width="100" />
        <el-table-column prop="quantity" label="持仓数量" width="100" />
        <el-table-column prop="available_quantity" label="可用数量" width="100" />
        <el-table-column prop="avg_cost" label="均价" width="90" />
        <el-table-column prop="current_price" label="现价" width="90" />
        <el-table-column prop="market_value" label="市值" width="100" />
        <el-table-column prop="unrealized_pnl" label="浮动盈亏" width="110">
          <template #default="{ row }">
            <span :style="{ color: row.unrealized_pnl >= 0 ? '#ef4444' : '#10b981', fontWeight: 'bold' }">
              {{ row.unrealized_pnl >= 0 ? '+' : '' }}{{ row.unrealized_pnl?.toFixed(2) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="unrealized_pnl_pct" label="盈亏比例" width="100">
          <template #default="{ row }">
            <span :style="{ color: row.unrealized_pnl_pct >= 0 ? '#ef4444' : '#10b981' }">
              {{ row.unrealized_pnl_pct >= 0 ? '+' : '' }}{{ row.unrealized_pnl_pct?.toFixed(2) }}%
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="realized_pnl" label="已实现盈亏" width="110">
          <template #default="{ row }">
            <span :style="{ color: row.realized_pnl >= 0 ? '#ef4444' : '#10b981' }">
              {{ row.realized_pnl >= 0 ? '+' : '' }}{{ row.realized_pnl?.toFixed(2) }}
            </span>
          </template>
        </el-table-column>
      </el-table>
      </div>
      <el-empty v-else description="暂无持仓" />
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { tradingApi } from '@/api/trading'

const positions = ref([])

async function load() {
  try {
    const res = await tradingApi.getPositions()
    positions.value = res.data || []
  } catch (e) { console.error(e) }
}

onMounted(load)
</script>
