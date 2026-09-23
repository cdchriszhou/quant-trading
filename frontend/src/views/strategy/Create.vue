<template>
  <div>
    <el-card shadow="never">
      <template #header><span style="font-weight: bold">创建策略</span></template>
<<<<<<< HEAD
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px" style="max-width: 600px" class="responsive-form">
        <el-form-item label="策略名称" prop="name">
          <el-input v-model="form.name" placeholder="输入策略名称" />
        </el-form-item>
        <el-form-item label="策略类型" prop="strategy_type">
          <el-select v-model="form.strategy_type" style="width: 100%" @change="onTypeChange">
            <el-option v-for="t in types" :key="t.type" :label="t.name" :value="t.type" />
          </el-select>
        </el-form-item>
        <el-form-item label="交易标的" prop="symbols">
          <el-select v-model="form.symbols" multiple filterable remote
            :remote-method="remoteSearchSymbols"
            :loading="symbolLoading"
            style="width: 100%" placeholder="输入代码搜索，如 000001">
            <el-option v-for="s in symbols" :key="s.code" :label="`${s.code} - ${s.name}`" :value="s.code" />
          </el-select>
        </el-form-item>
        <el-form-item label="时间周期" prop="time_frame">
          <el-select v-model="form.time_frame" style="width: 100%">
            <el-option label="日线" value="1d" />
            <el-option label="周线" value="1w" />
            <el-option label="60分钟" value="60m" />
            <el-option label="30分钟" value="30m" />
          </el-select>
        </el-form-item>
        <el-form-item label="初始资金" prop="initial_capital">
          <el-input-number v-model="form.initial_capital" :min="0" :step="10000" style="width: 200px"
            :placeholder="`¥${remainingCash.toLocaleString()}`" />
          <span v-if="form.initial_capital <= 0" style="margin-left: 10px; color: #67c23a; font-size: 13px">
            ✓ 使用账户余额 ¥{{ remainingCash.toLocaleString() }}
          </span>
          <span v-else style="margin-left: 10px; color: #e6a23c; font-size: 13px">
            ⚠ 自定义金额（账户余额: ¥{{ remainingCash.toLocaleString() }}）
          </span>
        </el-form-item>
        <el-form-item label="交易模式">
          <el-radio-group v-model="form.mode">
            <el-radio value="paper">模拟交易</el-radio>
            <el-radio value="live">实盘交易</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="策略描述">
          <el-input v-model="form.description" type="textarea" :rows="3" />
        </el-form-item>

        <el-divider content-position="left">策略参数</el-divider>
        <el-form-item v-for="(val, key) in form.parameters" :key="key" :label="paramLabel(key)">
          <el-select v-if="key === 'signal_type'" v-model="form.parameters[key]" style="width: 200px">
            <el-option label="金叉死叉" value="cross" />
          </el-select>
          <el-input v-else-if="typeof val === 'string'" v-model="form.parameters[key]" style="width: 200px" />
          <el-input-number v-else-if="['fast_period','slow_period','signal_period','period','grid_levels','interval_days'].includes(key)"
            v-model="form.parameters[key]" :min="1" :step="1" style="width: 200px" />
          <el-input-number v-else v-model="form.parameters[key]" :min="0" :step="0.1" style="width: 200px" />
        </el-form-item>

        <el-form-item>
          <el-button type="primary" @click="handleCreate" :loading="loading">创建策略</el-button>
          <el-button @click="$router.back()">取消</el-button>
        </el-form-item>
      </el-form>
=======
      <StrategyCreateForm :prefill="prefill" variant="page" @cancel="router.back()" />
>>>>>>> 4b5774d (feat: add stock recommend, insight popup, and trading UX upgrades)
    </el-card>
  </div>
</template>

<script setup>
<<<<<<< HEAD
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { strategyApi } from '@/api/strategy'
import { marketApi } from '@/api/market'
import { tradingApi } from '@/api/trading'
import { ElMessage } from 'element-plus'
import { paramLabel } from '@/utils/paramLabel'

const router = useRouter()
const loading = ref(false)
const types = ref([])
const symbols = ref([])
const symbolLoading = ref(false)
const remainingCash = ref(100000)
=======
import { computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import StrategyCreateForm from './StrategyCreateForm.vue'

const router = useRouter()
const route = useRoute()
>>>>>>> 4b5774d (feat: add stock recommend, insight popup, and trading UX upgrades)

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
<<<<<<< HEAD
  symbolLoading.value = true
  try {
    const res = await marketApi.searchSymbols(query.trim())
    symbols.value = res.data || []
  } catch {
    symbols.value = []
  } finally {
    symbolLoading.value = false
  }
}

const form = reactive({
  name: '',
  strategy_type: 'ma',
  symbols: [],
  time_frame: '1d',
  initial_capital: 0,  // 0 = 自动使用账户剩余资金
  mode: 'paper',
  description: '',
  parameters: {},
})

const rules = {
  name: [{ required: true, message: '请输入策略名称', trigger: 'blur' }],
  strategy_type: [{ required: true, message: '请选择策略类型', trigger: 'change' }],
  symbols: [{ required: true, message: '请选择交易标的', trigger: 'change' }],
}

async function onTypeChange(type) {
  try {
    const res = await strategyApi.getDefaultParams(type)
    form.parameters = res.params || {}
  } catch (e) {
    form.parameters = {}
  }
}

async function handleCreate() {
  loading.value = true
  try {
    const payload = { ...form, status: 'stopped' }
    await strategyApi.create(payload)
    ElMessage.success('策略创建成功')
    router.push('/strategies')
  } catch (e) {
    ElMessage.error('创建失败')
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  try {
    const [tRes, sRes, acctRes] = await Promise.all([
      strategyApi.getTypes(),
      marketApi.searchSymbols(),
      tradingApi.getAccount(),
    ])
    types.value = tRes.data || []
    symbols.value = sRes.data || []
    if (types.value.length) {
      onTypeChange(form.strategy_type)
    }
    // 获取账户剩余资金作为参考，初始资金保持 0 由后端自动计算
    const cash = acctRes.data?.cash_balance
    if (cash !== undefined && cash > 0) {
      remainingCash.value = cash
    }
  } catch (e) { console.error(e) }
=======
>>>>>>> 4b5774d (feat: add stock recommend, insight popup, and trading UX upgrades)
})
</script>
