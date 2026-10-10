<template>
  <div>
    <el-card shadow="never" style="margin-bottom: 16px">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px">
          <span style="font-weight: bold">持仓查询</span>
          <el-button text type="primary" size="small" :loading="loading" @click="load">刷新</el-button>
        </div>
      </template>
      <div v-if="positions.length" class="pos-table-wrap">
        <el-table :data="positions" stripe size="small" table-layout="auto" style="width: 100%">
          <el-table-column label="标的" width="120">
            <template #default="{ row }">
              <StockTicker :symbol="row.symbol" :row="row" />
            </template>
          </el-table-column>

          <el-table-column prop="quantity" label="持仓数量" width="88" align="right" />
          <el-table-column prop="available_quantity" label="可用数量" width="88" align="right" />

          <el-table-column label="购入均价" width="96" align="right">
            <template #default="{ row }">
              {{ fmtPrice(costPrice(row)) }}
            </template>
          </el-table-column>
          <el-table-column label="购入总资金" width="112" align="right">
            <template #default="{ row }">
              ¥{{ fmtMoney(costTotal(row)) }}
            </template>
          </el-table-column>
          <el-table-column label="现价" width="88" align="right">
            <template #default="{ row }">
              {{ fmtPrice(row.current_price) }}
            </template>
          </el-table-column>
          <el-table-column label="当前市值" width="108" align="right">
            <template #default="{ row }">
              ¥{{ fmtMoney(marketValue(row)) }}
            </template>
          </el-table-column>

          <el-table-column label="浮动盈亏" width="100" align="right">
            <template #default="{ row }">
              <span :style="{ color: pnlColor(row.unrealized_pnl), fontWeight: 'bold' }">
                {{ fmtSigned(row.unrealized_pnl) }}
              </span>
            </template>
          </el-table-column>
          <el-table-column label="盈亏比例" width="92" align="right">
            <template #default="{ row }">
              <span :style="{ color: pnlColor(row.unrealized_pnl_pct) }">
                {{ fmtSigned(row.unrealized_pnl_pct) }}%
              </span>
            </template>
          </el-table-column>
          <el-table-column label="当日盈亏" width="100" align="right">
            <template #header>
              <el-tooltip content="相对昨收：(现价−昨收)×持仓数量" placement="top">
                <span>当日盈亏</span>
              </el-tooltip>
            </template>
            <template #default="{ row }">
              <span :style="{ color: pnlColor(row.day_pnl), fontWeight: 'bold' }">
                {{ fmtSigned(row.day_pnl) }}
              </span>
            </template>
          </el-table-column>
          <el-table-column label="卖出盈亏" width="100" align="right">
            <template #header>
              <el-tooltip content="本标的历史卖出已锁定盈亏；从未卖出则为 0（不是浮动盈亏）" placement="top">
                <span>卖出盈亏</span>
              </el-tooltip>
            </template>
            <template #default="{ row }">
              <span :style="{ color: pnlColor(row.realized_pnl) }">
                {{ fmtSigned(row.realized_pnl) }}
              </span>
            </template>
          </el-table-column>

          <el-table-column label="操作" width="120" fixed="right" align="center">
            <template #default="{ row }">
              <el-button text type="danger" size="small" @click="openTrade(row, 'buy')">买入</el-button>
              <el-button
                text
                type="success"
                size="small"
                :disabled="sellQty(row) < 100"
                @click="openTrade(row, 'sell')"
              >卖出</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
      <el-empty v-else description="暂无持仓" />
    </el-card>

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
import { ref, computed, onMounted } from 'vue'
import { tradingApi } from '@/api/trading'
import { displayStockName, ensureStockNames } from '@/utils/stockNames'
import TradeOrderForm from './TradeOrderForm.vue'

const positions = ref([])
const loading = ref(false)

const tradeDialogVisible = ref(false)
const tradePrefill = ref({})
const tradePrefillKey = ref(0)

const tradeDialogTitle = computed(() => {
  const p = tradePrefill.value || {}
  const side = p.side === 'sell' ? '卖出' : '买入'
  const name = p.symbol_name || p.symbol || ''
  return name ? `${side} · ${name}` : side
})

function costPrice(row) {
  const v = Number(row?.avg_cost)
  return Number.isFinite(v) ? v : 0
}

function costTotal(row) {
  if (row?.cost_total != null && Number.isFinite(Number(row.cost_total))) {
    return Number(row.cost_total)
  }
  return costPrice(row) * Number(row?.quantity || 0)
}

function marketValue(row) {
  const mv = Number(row?.market_value)
  if (Number.isFinite(mv) && mv > 0) return mv
  return Number(row?.current_price || 0) * Number(row?.quantity || 0)
}

function fmtPrice(v) {
  const n = Number(v)
  if (!Number.isFinite(n) || n <= 0) return '—'
  return n >= 100 ? n.toFixed(2) : n.toFixed(3)
}

function fmtMoney(v) {
  const n = Number(v)
  if (!Number.isFinite(n)) return '—'
  return n.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function fmtSigned(v) {
  const n = Number(v)
  if (!Number.isFinite(n)) return '—'
  const s = n >= 0 ? '+' : ''
  return `${s}${n.toFixed(2)}`
}

function pnlColor(v) {
  const n = Number(v)
  if (!Number.isFinite(n) || n === 0) return undefined
  return n > 0 ? '#ef4444' : '#10b981'
}

function sellQty(row) {
  const avail = Number(row.available_quantity ?? row.quantity ?? 0)
  return Math.floor(avail / 100) * 100
}

function openTrade(row, side) {
  const name = displayStockName(row) || ''
  const qty = side === 'sell' ? Math.max(100, sellQty(row)) : 100
  tradePrefill.value = {
    symbol: row.symbol,
    symbol_name: name,
    quantity: qty,
    side,
    price: row.current_price,
    remark: side === 'sell' ? `持仓卖出 ${name || row.symbol}` : `加仓 ${name || row.symbol}`,
  }
  tradePrefillKey.value += 1
  tradeDialogVisible.value = true
}

async function onOrderSubmitted() {
  tradeDialogVisible.value = false
  await load()
}

async function load() {
  loading.value = true
  try {
    const res = await tradingApi.getPositions()
    positions.value = res.data || []
    await ensureStockNames(positions.value.map((p) => p.symbol))
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.pos-table-wrap {
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}
.pos-table-wrap :deep(.el-table .cell) {
  padding-left: 8px;
  padding-right: 8px;
}
.pos-table-wrap :deep(.el-button + .el-button) {
  margin-left: 4px;
}
</style>
