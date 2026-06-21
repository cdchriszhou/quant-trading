<template>
  <el-card shadow="never">
    <template #header>
      <div style="display: flex; justify-content: space-between; align-items: center">
        <span style="font-weight: bold">订单查询</span>
        <el-radio-group v-model="filterStatus" @change="loadOrders">
          <el-radio-button value="">全部</el-radio-button>
          <el-radio-button value="pending">待成交</el-radio-button>
          <el-radio-button value="filled">已成交</el-radio-button>
          <el-radio-button value="cancelled">已取消</el-radio-button>
        </el-radio-group>
      </div>
    </template>
    <el-table :data="orders" stripe size="small">
      <el-table-column prop="created_at" label="时间" width="160" />
      <el-table-column prop="symbol" label="标的" width="90" />
      <el-table-column prop="side" label="方向" width="70">
        <template #default="{ row }">
          <el-tag :type="row.side === 'buy' ? 'danger' : 'success'" size="small">
            {{ row.side === 'buy' ? '买入' : '卖出' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="order_type" label="类型" width="70" />
      <el-table-column prop="price" label="价格" width="90" />
      <el-table-column prop="quantity" label="数量" width="80" />
      <el-table-column prop="filled_quantity" label="已成交" width="80" />
      <el-table-column prop="status" label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="statusType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="commission" label="手续费" width="80" />
      <el-table-column label="操作" width="100" v-if="filterStatus === 'pending'">
        <template #default="{ row }">
          <el-button text size="small" type="danger" @click="cancelOrder(row.id)" v-if="row.status === 'pending'">撤单</el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-card>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { tradingApi } from '@/api/trading'
import { ElMessage } from 'element-plus'

const orders = ref([])
const filterStatus = ref('')

function statusType(s) {
  return { pending: 'warning', submitted: 'primary', filled: 'success', cancelled: 'info', rejected: 'danger' }[s] || 'info'
}
function statusLabel(s) {
  return { pending: '待成交', submitted: '已提交', filled: '已成交', cancelled: '已取消', rejected: '已拒绝' }[s] || s
}

async function loadOrders() {
  try {
    const status = filterStatus.value || undefined
    const res = await tradingApi.listOrders(status)
    orders.value = res.data || []
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

onMounted(loadOrders)
</script>
