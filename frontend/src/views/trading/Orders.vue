<template>
  <el-card shadow="never">
    <template #header>
      <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px">
        <span style="font-weight: bold">订单查询</span>
        <el-radio-group v-model="filterStatus" @change="loadOrders" size="small">
          <el-radio-button value="">全部</el-radio-button>
          <el-radio-button value="pending">待成交</el-radio-button>
          <el-radio-button value="submitted">已提交</el-radio-button>
          <el-radio-button value="filled">已成交</el-radio-button>
          <el-radio-button value="cancelled">已取消</el-radio-button>
        </el-radio-group>
      </div>
    </template>
    <div style="overflow-x: auto; -webkit-overflow-scrolling: touch">
      <el-table :data="orders" stripe size="small">
      <el-table-column prop="created_at" label="时间" width="160" />
      <el-table-column label="标的" width="150">
        <template #default="{ row }">
          <StockTicker :symbol="row.symbol" :row="row" />
        </template>
      </el-table-column>
      <el-table-column prop="side" label="方向" width="70">
        <template #default="{ row }">
          <el-tag :type="row.side === 'buy' ? 'danger' : 'success'" size="small">
            {{ row.side === 'buy' ? '买入' : '卖出' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="order_type" label="类型" width="70">
        <template #default="{ row }">{{ orderTypeLabel(row.order_type) }}</template>
      </el-table-column>
      <el-table-column prop="price" label="价格" width="90" />
      <el-table-column prop="quantity" label="数量" width="100">
          <template #default="{ row }">
            {{ row.quantity }}
            <span v-if="row.filled_quantity !== row.quantity" style="color: #e6a23c; font-size: 11px">
              （已成交 {{ row.filled_quantity }}）
            </span>
          </template>
        </el-table-column>
      <el-table-column prop="status" label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="statusType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="commission" label="手续费" width="80" />
      <el-table-column label="操作" width="100" v-if="showCancelCol">
        <template #default="{ row }">
          <el-button
            text
            size="small"
            type="danger"
            @click="cancelOrder(row.id)"
            v-if="row.status === 'pending' || row.status === 'submitted'"
          >撤单</el-button>
        </template>
      </el-table-column>
    </el-table>
    </div>
  </el-card>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { tradingApi } from '@/api/trading'
import { ElMessage } from 'element-plus'
import { displayStockName, ensureStockNames } from '@/utils/stockNames'
import { orderTypeLabel, orderStatusLabel } from '@/utils/labels'

const orders = ref([])
const filterStatus = ref('')

const showCancelCol = computed(() =>
  !filterStatus.value || filterStatus.value === 'pending' || filterStatus.value === 'submitted'
)

function statusType(s) {
  return { pending: 'warning', submitted: 'primary', filled: 'success', cancelled: 'info', rejected: 'danger' }[s] || 'info'
}
function statusLabel(s) {
  return orderStatusLabel(s)
}

async function loadOrders() {
  try {
    const status = filterStatus.value || undefined
    const res = await tradingApi.listOrders(status)
    orders.value = res.data || []
    await ensureStockNames(orders.value.map((o) => o.symbol))
  } catch (e) { console.error(e) }
}

async function cancelOrder(id) {
  try {
    await tradingApi.cancelOrder(id)
    ElMessage.success('已撤单')
    await loadOrders()
  } catch (e) {
    ElMessage.error('撤单失败')
  }
}

onMounted(() => {
  loadOrders()
})
</script>
