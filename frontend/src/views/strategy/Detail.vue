<template>
  <div v-if="strategy">
    <el-card shadow="never" style="margin-bottom: 16px">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px">
          <span style="font-weight: bold">{{ strategy.name }}</span>
          <div style="display: flex; flex-wrap: wrap; gap: 8px">
            <el-button type="primary" plain @click="goBacktest">回测此策略</el-button>
            <el-button @click="openEdit">编辑参数</el-button>
            <el-button :type="strategy.status === 'running' ? 'warning' : 'success'" @click="toggleStatus">
              {{ strategy.status === 'running' ? '停止策略' : '启动策略' }}
            </el-button>
            <el-button @click="$router.push('/strategies')">返回</el-button>
          </div>
        </div>
      </template>
      <el-descriptions :column="3" border size="small" class="responsive-descriptions">
        <el-descriptions-item label="策略类型">{{ strategyTypeLabel(strategy.strategy_type) }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="strategy.status === 'running' ? 'success' : 'info'" size="small">
            {{ strategyStatusLabel(strategy.status) }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="交易模式">
          <el-tag :type="strategy.mode === 'live' ? 'danger' : 'info'" size="small" effect="plain">
            {{ tradeModeLabel(strategy.mode) }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="交易标的">
          <span v-if="!(strategy.symbols || []).length">—</span>
          <span v-for="(sym, i) in (strategy.symbols || [])" :key="sym" style="margin-right: 8px">
            <StockTicker :symbol="sym" :show-name="true" style="display: inline-flex" />
            <span v-if="i < strategy.symbols.length - 1">、</span>
          </span>
        </el-descriptions-item>
        <el-descriptions-item label="时间周期">{{ timeFrameLabel(strategy.time_frame) }}</el-descriptions-item>
        <el-descriptions-item label="初始资金">¥ {{ strategy.initial_capital?.toLocaleString() }}</el-descriptions-item>
        <el-descriptions-item label="总交易次数">{{ strategy.total_trades ?? 0 }}</el-descriptions-item>
        <el-descriptions-item label="总收益">
          <span :style="{ color: (strategy.total_return ?? 0) >= 0 ? '#ef4444' : '#10b981', fontWeight: 600 }">
            {{ formatPct(strategy.total_return) }}
          </span>
        </el-descriptions-item>
        <el-descriptions-item label="胜率">{{ formatPct(strategy.win_rate) }}</el-descriptions-item>
        <el-descriptions-item label="最大回撤">{{ formatPct(strategy.max_drawdown) }}</el-descriptions-item>
      </el-descriptions>
    </el-card>

    <el-row :gutter="14">
      <el-col :xs="24" :md="14">
        <el-card shadow="never" style="margin-bottom: 14px">
          <template #header>
            <div style="display: flex; justify-content: space-between; align-items: center">
              <span style="font-weight: bold">策略参数</span>
              <el-button text type="primary" size="small" @click="openEdit">编辑</el-button>
            </div>
          </template>
          <div v-if="strategy.parameters && Object.keys(strategy.parameters).length">
            <el-descriptions :column="2" border size="small" class="responsive-descriptions">
              <el-descriptions-item v-for="(val, key) in strategy.parameters" :key="key" :label="paramLabel(key)">
                <template v-if="key === 'min_daily_amount'">
                  {{ Number(val).toLocaleString() }} 元（约 {{ (Number(val) / 1e4).toFixed(0) }} 万）
                </template>
                <template v-else>{{ val }}</template>
              </el-descriptions-item>
            </el-descriptions>
          </div>
          <el-empty v-else description="无参数配置" :image-size="64" />
        </el-card>
      </el-col>
      <el-col :xs="24" :md="10">
        <el-card shadow="never" style="margin-bottom: 14px">
          <template #header><span style="font-weight: bold">近期成交</span></template>
          <div v-if="trades.length" style="overflow-x: auto">
            <el-table :data="trades" stripe size="small" max-height="320">
              <el-table-column prop="trade_time" label="时间" width="140" />
              <el-table-column label="标的" width="130">
                <template #default="{ row }">
                  <StockTicker :symbol="row.symbol" :row="row" />
                </template>
              </el-table-column>
              <el-table-column prop="side" label="方向" width="60">
                <template #default="{ row }">
                  <el-tag :type="row.side === 'buy' ? 'danger' : 'success'" size="small" effect="plain">
                    {{ row.side === 'buy' ? '买' : '卖' }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="price" label="价格" width="80" />
              <el-table-column prop="quantity" label="数量" width="70" />
              <el-table-column prop="pnl" label="盈亏" width="80">
                <template #default="{ row }">
                  <span :style="{ color: row.pnl > 0 ? '#ef4444' : row.pnl < 0 ? '#10b981' : undefined }">
                    {{ row.pnl != null ? Number(row.pnl).toFixed(2) : '-' }}
                  </span>
                </template>
              </el-table-column>
            </el-table>
          </div>
          <el-empty v-else description="暂无成交，建议先回测再启动" :image-size="64" />
        </el-card>
      </el-col>
    </el-row>

    <el-dialog v-model="editVisible" title="编辑策略参数" width="560px" destroy-on-close>
      <el-form label-width="120px" size="small">
        <el-form-item label="策略名称">
          <el-input v-model="editForm.name" />
        </el-form-item>
        <el-form-item label="初始资金">
          <el-input-number v-model="editForm.initial_capital" :min="10000" :step="10000" style="width: 200px" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="editForm.description" type="textarea" :rows="2" />
        </el-form-item>
        <el-divider content-position="left">参数</el-divider>
        <el-form-item v-for="(val, key) in editForm.parameters" :key="key" :label="paramLabel(key)">
          <el-input v-if="typeof val === 'string'" v-model="editForm.parameters[key]" style="width: 200px" />
          <el-input-number v-else-if="key === 'min_daily_amount'" v-model="editForm.parameters[key]" :min="0" :step="1000000" :precision="0" style="width: 220px" />
          <el-input-number v-else v-model="editForm.parameters[key]" :step="0.1" style="width: 200px" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveEdit">保存</el-button>
      </template>
    </el-dialog>
  </div>
  <div v-else style="text-align: center; padding: 40px; color: #909399">加载中...</div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { strategyApi } from '@/api/strategy'
import { reportsApi } from '@/api/reports'
import { ElMessage, ElMessageBox } from 'element-plus'
import { paramLabel } from '@/utils/paramLabel'
import { displayStockName, ensureStockNames } from '@/utils/stockNames'
import { strategyTypeLabel, strategyStatusLabel, tradeModeLabel, timeFrameLabel } from '@/utils/labels'

const route = useRoute()
const router = useRouter()
const strategy = ref(null)
const trades = ref([])
const editVisible = ref(false)
const saving = ref(false)
const editForm = reactive({
  name: '',
  description: '',
  initial_capital: 1000000,
  parameters: {},
})

function formatPct(v) {
  if (v == null || Number.isNaN(Number(v))) return '—'
  const n = Number(v)
  return `${n >= 0 ? '+' : ''}${n.toFixed(2)}%`
}

async function load() {
  try {
    const res = await strategyApi.get(route.params.id)
    strategy.value = res.data
    await loadTrades()
  } catch (e) {
    ElMessage.error('策略不存在')
    router.push('/strategies')
  }
}

async function loadTrades() {
  try {
    const res = await reportsApi.getTrades()
    const all = res.data || []
    const sid = Number(route.params.id)
    trades.value = all
      .filter((t) => t.strategy_id === sid)
      .slice(0, 20)
    await ensureStockNames(trades.value.map((t) => t.symbol))
  } catch {
    trades.value = []
  }
}

function goBacktest() {
  router.push({ path: '/backtest', query: { strategy_id: strategy.value.id } })
}

function openEdit() {
  editForm.name = strategy.value.name || ''
  editForm.description = strategy.value.description || ''
  editForm.initial_capital = strategy.value.initial_capital || 1000000
  editForm.parameters = { ...(strategy.value.parameters || {}) }
  editVisible.value = true
}

async function saveEdit() {
  saving.value = true
  try {
    await strategyApi.update(strategy.value.id, {
      name: editForm.name,
      description: editForm.description,
      initial_capital: editForm.initial_capital,
      parameters: editForm.parameters,
    })
    ElMessage.success('已保存')
    editVisible.value = false
    await load()
  } catch (e) {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

async function toggleStatus() {
  try {
    if (strategy.value.status === 'running') {
      await strategyApi.stop(strategy.value.id)
      ElMessage.success('策略已停止')
    } else {
      await ElMessageBox.confirm(
        '建议先完成回测再启动。当前为模拟交易模式，确认启动？',
        '启动策略',
        { type: 'warning', confirmButtonText: '启动', cancelButtonText: '取消' }
      )
      await strategyApi.start(strategy.value.id)
      ElMessage.success('策略已启动')
    }
    await load()
  } catch (e) {
    if (e !== 'cancel' && e?.toString?.() !== 'cancel') {
      ElMessage.error(e?.response?.data?.detail || '操作失败')
    }
  }
}

onMounted(load)
</script>
