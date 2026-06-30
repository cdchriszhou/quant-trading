<template>
  <div>
    <el-card shadow="never">
      <template #header><span style="font-weight: bold">创建策略</span></template>
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
          <el-input-number v-model="form.initial_capital" :min="10000" :step="10000" style="width: 200px" />
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
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { strategyApi } from '@/api/strategy'
import { marketApi } from '@/api/market'
import { ElMessage } from 'element-plus'
import { paramLabel } from '@/utils/paramLabel'

const router = useRouter()
const loading = ref(false)
const types = ref([])
const symbols = ref([])
const symbolLoading = ref(false)

// Remote search — calls backend API on each keystroke for live Tencent lookup
async function remoteSearchSymbols(query) {
  if (!query || query.trim().length < 2) {
    // Reload default list on clear
    try {
      const res = await marketApi.searchSymbols()
      symbols.value = res.data || []
    } catch {}
    return
  }
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
