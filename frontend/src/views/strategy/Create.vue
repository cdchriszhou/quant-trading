<template>
  <div>
    <el-card shadow="never">
      <template #header><span style="font-weight: bold">创建策略</span></template>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="120px" style="max-width: 600px">
        <el-form-item label="策略名称" prop="name">
          <el-input v-model="form.name" placeholder="输入策略名称" />
        </el-form-item>
        <el-form-item label="策略类型" prop="strategy_type">
          <el-select v-model="form.strategy_type" style="width: 100%" @change="onTypeChange">
            <el-option v-for="t in types" :key="t.type" :label="t.name" :value="t.type" />
          </el-select>
        </el-form-item>
        <el-form-item label="交易标的" prop="symbols">
          <el-select v-model="form.symbols" multiple filterable allow-create default-first-option style="width: 100%" placeholder="搜索或输入股票代码">
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
          <el-input-number v-model="form.initial_capital" :min="10000" :step="10000" style="width: 200px" />
        </el-form-item>
        <el-form-item label="交易模式">
          <el-radio-group v-model="form.mode">
            <el-radio value="paper">模拟交易</el-radio>
            <el-radio value="live" disabled>实盘交易(待对接)</el-radio>
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
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { strategyApi } from '@/api/strategy'
import { marketApi } from '@/api/market'
import { ElMessage } from 'element-plus'

const router = useRouter()
const loading = ref(false)
const types = ref([])
const symbols = ref([])

const form = reactive({
  name: '',
  strategy_type: 'ma',
  symbols: [],
  time_frame: '1d',
  initial_capital: 100000,
  mode: 'paper',
  description: '',
  parameters: {},
})

const rules = {
  name: [{ required: true, message: '请输入策略名称', trigger: 'blur' }],
  strategy_type: [{ required: true, message: '请选择策略类型', trigger: 'change' }],
  symbols: [{ required: true, message: '请选择交易标的', trigger: 'change' }],
}

function paramLabel(key) {
  const map = {
    fast_period: '快线周期', slow_period: '慢线周期', signal_period: '信号周期',
    period: '计算周期', std_dev: '标准差倍数', grid_levels: '网格层数',
    grid_spacing_pct: '网格间距(%)', interval_days: '定投间隔(天)',
    fixed_amount: '定投金额', base_price: '基准价格',
    signal_type: '信号类型',
  }
  return map[key] || key
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
    const [tRes, sRes] = await Promise.all([
      strategyApi.getTypes(),
      marketApi.searchSymbols(),
    ])
    types.value = tRes.data || []
    symbols.value = sRes.data || []
    if (types.value.length) {
      onTypeChange(form.strategy_type)
    }
  } catch (e) { console.error(e) }
})
</script>
