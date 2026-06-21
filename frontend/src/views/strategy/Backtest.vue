<template>
  <div>
    <el-row :gutter="16">
      <el-col :span="8">
        <el-card shadow="never">
          <template #header><span style="font-weight: bold">回测配置</span></template>
          <el-form label-width="100px" size="small">
            <el-form-item label="策略类型">
              <el-select v-model="form.strategy_type" style="width: 100%">
                <el-option v-for="t in types" :key="t.type" :label="t.name" :value="t.type" />
              </el-select>
            </el-form-item>
            <el-form-item label="交易标的">
              <el-select v-model="form.symbols" filterable allow-create style="width: 100%">
                <el-option v-for="s in symbols" :key="s.code" :label="`${s.code} - ${s.name}`" :value="s.code" />
              </el-select>
            </el-form-item>
            <el-form-item label="开始日期">
              <el-date-picker v-model="form.start_date" type="date" style="width: 100%" value-format="YYYY-MM-DD" />
            </el-form-item>
            <el-form-item label="结束日期">
              <el-date-picker v-model="form.end_date" type="date" style="width: 100%" value-format="YYYY-MM-DD" />
            </el-form-item>
            <el-form-item label="初始资金">
              <el-input-number v-model="form.initial_capital" :min="10000" :step="10000" style="width: 180px" />
            </el-form-item>
            <el-divider />
            <el-form-item v-for="(val, key) in form.parameters" :key="key" :label="key">
              <el-input-number v-model="form.parameters[key]" :min="1" :step="1" style="width: 180px" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="runBacktest" :loading="running" style="width: 100%">开始回测</el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>
      <el-col :span="16">
        <el-card shadow="never" v-if="result" style="margin-bottom: 16px">
          <template #header><span style="font-weight: bold">回测结果</span></template>
          <el-row :gutter="12">
            <el-col :span="8" v-for="(item, idx) in metrics" :key="idx">
              <div style="text-align: center; padding: 8px; background: #f9f9f9; border-radius: 4px; margin-bottom: 8px">
                <div style="color: #909399; font-size: 12px">{{ item.label }}</div>
                <div :style="{ fontSize: '18px', fontWeight: 'bold', color: item.color || '#303133' }">{{ item.value }}</div>
              </div>
            </el-col>
          </el-row>
          <div ref="chartRef" style="height: 250px; margin-top: 16px"></div>
        </el-card>

        <el-card shadow="never" v-if="backtests.length">
          <template #header><span style="font-weight: bold">历史回测</span></template>
          <el-table :data="backtests" stripe size="small">
            <el-table-column prop="strategy_name" label="策略类型" width="100" />
            <el-table-column prop="start_date" label="开始" width="100" />
            <el-table-column prop="end_date" label="结束" width="100" />
            <el-table-column prop="total_return_pct" label="收益率" width="90">
              <template #default="{ row }">
                <span :style="{ color: row.total_return_pct >= 0 ? '#67c23a' : '#f56c6c' }">{{ row.total_return_pct?.toFixed(2) }}%</span>
              </template>
            </el-table-column>
            <el-table-column prop="sharpe_ratio" label="夏普比" width="80" />
            <el-table-column prop="max_drawdown_pct" label="最大回撤" width="90" />
            <el-table-column prop="total_trades" label="交易" width="60" />
            <el-table-column prop="win_rate" label="胜率" width="70">
              <template #default="{ row }">{{ row.win_rate?.toFixed(1) }}%</template>
            </el-table-column>
            <el-table-column label="操作" width="80">
              <template #default="{ row }">
                <el-button text size="small" @click="viewBacktest(row)">查看</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, nextTick } from 'vue'
import { strategyApi } from '@/api/strategy'
import { backtestApi } from '@/api/backtest'
import { marketApi } from '@/api/market'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'

const types = ref([])
const symbols = ref([])
const result = ref(null)
const backtests = ref([])
const running = ref(false)
const chartRef = ref(null)
let chart = null

const form = reactive({
  strategy_type: 'ma',
  symbols: ['000001.SZ'],
  start_date: '2023-01-01',
  end_date: '2024-12-31',
  initial_capital: 100000,
  parameters: { fast_period: 5, slow_period: 20 },
})

const metrics = ref([])

async function runBacktest() {
  running.value = true
  try {
    const res = await backtestApi.run({ ...form })
    result.value = res.data
    ElMessage.success('回测完成')

    const d = res.data
    metrics.value = [
      { label: '累计收益率', value: `${d.total_return_pct?.toFixed(2)}%`, color: d.total_return_pct >= 0 ? '#67c23a' : '#f56c6c' },
      { label: '年化收益', value: `${d.annual_return?.toFixed(2)}%`, color: '#409EFF' },
      { label: '最大回撤', value: `${d.max_drawdown_pct?.toFixed(2)}%`, color: '#e6a23c' },
      { label: '夏普比率', value: d.sharpe_ratio?.toFixed(2) },
      { label: '胜率', value: `${d.win_rate?.toFixed(1)}%` },
      { label: '交易次数', value: d.total_trades },
      { label: '盈利因子', value: d.profit_factor?.toFixed(2) },
    ]

    await nextTick()
    renderChart(d.equity_curve || [])
  } catch (e) {
    ElMessage.error('回测失败')
  } finally {
    running.value = false
  }
}

function renderChart(equityCurve) {
  if (chart) chart.dispose()
  chart = echarts.init(chartRef.value)
  chart.setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: { type: 'category', data: equityCurve.map(e => e.date || e) },
    yAxis: { type: 'value' },
    series: [{
      type: 'line', data: equityCurve.map(e => e.equity || e),
      smooth: true, lineStyle: { color: '#409EFF' },
      areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: 'rgba(64,158,255,0.3)' }, { offset: 1, color: 'rgba(64,158,255,0.02)' }] } },
    }],
  })
}

function viewBacktest(row) {
  result.value = row
  metrics.value = [
    { label: '累计收益率', value: `${row.total_return_pct?.toFixed(2)}%`, color: row.total_return_pct >= 0 ? '#67c23a' : '#f56c6c' },
    { label: '年化收益', value: `${row.annual_return?.toFixed(2)}%`, color: '#409EFF' },
    { label: '最大回撤', value: `${row.max_drawdown_pct?.toFixed(2)}%`, color: '#e6a23c' },
    { label: '夏普比率', value: row.sharpe_ratio?.toFixed(2) },
    { label: '胜率', value: `${row.win_rate?.toFixed(1)}%` },
    { label: '交易次数', value: row.total_trades },
  ]
  nextTick(() => renderChart(row.equity_curve || []))
}

onMounted(async () => {
  try {
    const [tRes, sRes, bRes] = await Promise.all([
      strategyApi.getTypes(),
      marketApi.searchSymbols(),
      backtestApi.list(),
    ])
    types.value = tRes.data || []
    symbols.value = sRes.data || []
    backtests.value = bRes.data || []
  } catch (e) { console.error(e) }
})
</script>
