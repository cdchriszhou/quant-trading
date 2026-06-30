<template>
  <div>
    <el-row :gutter="16">
      <el-col :xs="24" :md="8">
        <el-card shadow="never">
          <template #header><span style="font-weight: bold">回测配置</span></template>
          <el-form label-width="100px" size="small">
            <el-form-item label="策略类型">
              <el-select v-model="form.strategy_type" style="width: 100%">
                <el-option v-for="t in types" :key="t.type" :label="t.name" :value="t.type" />
              </el-select>
            </el-form-item>
            <el-form-item label="交易标的">
              <el-select v-model="form.symbol" filterable remote :remote-method="remoteSearch" :loading="symLoading" style="width: 100%" placeholder="输入代码搜索">
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
            <el-divider content-position="left">筛选条件</el-divider>
            <el-form-item label="大盘环境过滤">
              <el-switch v-model="form.enable_env_filter" />
              <span style="margin-left: 8px; font-size: 11px; color: #909399">只在大盘多头时交易</span>
            </el-form-item>
            <el-form-item label="板块筛选">
              <el-switch v-model="form.enable_sector_filter" />
              <span style="margin-left: 8px; font-size: 11px; color: #909399">只交易Top10板块内标的</span>
            </el-form-item>
            <el-form-item label="对比模式">
              <el-switch v-model="form.comparison_mode" />
              <span style="margin-left: 8px; font-size: 11px; color: #909399">同时运行有/无筛选回测</span>
            </el-form-item>
            <el-divider />
            <el-form-item v-for="(val, key) in form.parameters" :key="key" :label="paramLabel(key)">
              <el-input-number v-model="form.parameters[key]" :min="0.1" :step="getParamStep(key)" :precision="getParamPrecision(key)" style="width: 180px" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="runBacktest" :loading="running" style="width: 100%">开始回测</el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>
      <el-col :xs="24" :md="16">
        <el-card shadow="never" v-if="result" style="margin-bottom: 16px">
          <template #header><span style="font-weight: bold">回测结果</span></template>
          <el-row :gutter="12">
            <el-col :xs="12" :sm="8" v-for="(item, idx) in metrics" :key="idx">
              <div style="text-align: center; padding: 8px; background: #f9f9f9; border-radius: 4px; margin-bottom: 8px">
                <div style="color: #909399; font-size: 12px">{{ item.label }}</div>
                <div :style="{ fontSize: '18px', fontWeight: 'bold', color: item.color || '#303133' }">{{ item.value }}</div>
              </div>
            </el-col>
          </el-row>
          <div ref="chartRef" style="height: 250px; margin-top: 16px"></div>
        </el-card>

        <!-- Comparison Results (Core 4) -->
        <el-card shadow="never" v-if="comparisonResult" style="margin-bottom: 16px">
          <template #header>
            <span style="font-weight: bold">📊 筛选效果对比</span>
          </template>
          <el-alert type="info" :closable="false" style="margin-bottom: 12px">
            {{ comparisonResult.summary }}
          </el-alert>
          <el-row :gutter="12">
            <el-col :xs="12" :sm="8" :md="6">
              <div style="text-align: center; padding: 8px; background: #f0fdf4; border-radius: 4px; margin-bottom: 8px">
                <div style="font-size: 11px; color: #6b7280">收益改善</div>
                <div style="font-size: 16px; font-weight: 700" :style="{ color: comparisonResult.return_improvement_pct >= 0 ? '#16a34a' : '#dc2626' }">
                  {{ comparisonResult.return_improvement_pct >= 0 ? '+' : '' }}{{ comparisonResult.return_improvement_pct }}%
                </div>
              </div>
            </el-col>
            <el-col :xs="12" :sm="8" :md="6">
              <div style="text-align: center; padding: 8px; background: #fef2f2; border-radius: 4px; margin-bottom: 8px">
                <div style="font-size: 11px; color: #6b7280">回撤减少</div>
                <div style="font-size: 16px; font-weight: 700" :style="{ color: comparisonResult.drawdown_reduction_pct >= 0 ? '#16a34a' : '#dc2626' }">
                  {{ comparisonResult.drawdown_reduction_pct >= 0 ? '+' : '' }}{{ comparisonResult.drawdown_reduction_pct }}%
                </div>
              </div>
            </el-col>
            <el-col :xs="12" :sm="8" :md="6">
              <div style="text-align: center; padding: 8px; background: #eff6ff; border-radius: 4px; margin-bottom: 8px">
                <div style="font-size: 11px; color: #6b7280">胜率改善</div>
                <div style="font-size: 16px; font-weight: 700" :style="{ color: comparisonResult.win_rate_improvement_pct >= 0 ? '#16a34a' : '#dc2626' }">
                  {{ comparisonResult.win_rate_improvement_pct >= 0 ? '+' : '' }}{{ comparisonResult.win_rate_improvement_pct }}%
                </div>
              </div>
            </el-col>
            <el-col :xs="12" :sm="8" :md="6">
              <div style="text-align: center; padding: 8px; background: #fefce8; border-radius: 4px; margin-bottom: 8px">
                <div style="font-size: 11px; color: #6b7280">连续亏损(筛选/全市场)</div>
                <div style="font-size: 16px; font-weight: 700; color: #e6a23c">
                  {{ comparisonResult.consecutive_losses_filtered }} / {{ comparisonResult.consecutive_losses_unfiltered }}
                </div>
              </div>
            </el-col>
          </el-row>
        </el-card>

        <el-card shadow="never" v-if="backtests.length">
          <template #header><span style="font-weight: bold">历史回测</span></template>
          <div style="overflow-x: auto; -webkit-overflow-scrolling: touch">
            <el-table :data="backtests" stripe size="small">
            <el-table-column label="策略类型" width="80">
              <template #default="{ row }">
                <el-tag size="small" type="info">{{ typeLabel(row.strategy_type) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="标的" width="110">
              <template #default="{ row }">
                <template v-if="row.symbols && row.symbols.length">
                  <div v-for="s in row.symbols" :key="s" style="font-size: 11px">
                    {{ s.replace('.SZ','').replace('.SH','') }}
                    <span style="color: #9ca3af; font-size: 10px">{{ getStockName(s) }}</span>
                  </div>
                </template>
                <span v-else style="color: #9ca3af">--</span>
              </template>
            </el-table-column>
            <el-table-column prop="start_date" label="开始" width="95" />
            <el-table-column prop="end_date" label="结束" width="100" />
            <el-table-column prop="total_return_pct" label="收益率" width="90">
              <template #default="{ row }">
                <span :style="{ color: row.total_return_pct > 0 ? '#ef4444' : row.total_return_pct < 0 ? '#10b981' : '#1a1a1a' }">{{ row.total_return_pct > 0 ? '+' : '' }}{{ row.total_return_pct?.toFixed(2) }}%</span>
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
          </div>
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
import { paramLabel } from '@/utils/paramLabel'
import { getStockName } from '@/utils/stockNames'
import * as echarts from 'echarts'

const typeMap = { ma: '均线', macd: 'MACD', bollinger: '布林带', grid: '网格', dca: '定投', dragon_pullback: '龙回头', trend_following: '趋势跟踪', right_side_entry: '右侧入场' }
function typeLabel(t) { return typeMap[t] || t }

const types = ref([])
const symbols = ref([])
const symLoading = ref(false)

async function remoteSearch(query) {
  if (!query || query.trim().length < 2) {
    try { const r = await marketApi.searchSymbols(); symbols.value = r.data || [] } catch {}
    return
  }
  symLoading.value = true
  try { const r = await marketApi.searchSymbols(query.trim()); symbols.value = r.data || [] } catch {}
  finally { symLoading.value = false }
}

const result = ref(null)
const backtests = ref([])
const running = ref(false)
const chartRef = ref(null)
let chart = null

function defaultStartDate() {
  const d = new Date()
  d.setFullYear(d.getFullYear() - 1)
  return d.toISOString().slice(0, 10)
}
function defaultEndDate() {
  return new Date().toISOString().slice(0, 10)
}

const form = reactive({
  strategy_type: 'right_side_entry',
  symbol: '000001.SZ',
  start_date: defaultStartDate(),
  end_date: defaultEndDate(),
  initial_capital: 100000,
  parameters: { ma_short: 5, ma_medium: 20, ma_long: 60, pullback_near_ma_pct: 2.0, vol_contraction_ratio: 0.5, vol_expansion_ratio: 1.5, stop_loss_ma_break_pct: 2.0, hard_stop_pct: 7.0 },
  enable_env_filter: true,
  enable_sector_filter: true,
  comparison_mode: true,
})

const metrics = ref([])

const comparisonResult = ref(null)

async function runBacktest() {
  running.value = true
  try {
    const payload = {
      strategy_type: form.strategy_type,
      parameters: form.parameters,
      symbols: [form.symbol],
      start_date: form.start_date,
      end_date: form.end_date,
      initial_capital: form.initial_capital,
      enable_env_filter: form.enable_env_filter,
      enable_sector_filter: form.enable_sector_filter,
      comparison_mode: form.comparison_mode,
    }
    const res = await backtestApi.run(payload)
    // Server envelope: { data: { filtered_result, comparison, unfiltered_result } }
    // Axios interceptor unwraps response.data → res is { data: { ... } }
    const body = res.data || res
    const filtered = body.filtered_result || body
    result.value = filtered
    comparisonResult.value = body.comparison || null

    const d = filtered
    metrics.value = [
      { label: '累计收益率', value: `${d.total_return_pct?.toFixed(2)}%`, color: d.total_return_pct >= 0 ? '#67c23a' : '#f56c6c' },
      { label: '年化收益', value: `${d.annual_return?.toFixed(2)}%`, color: '#409EFF' },
      { label: '最大回撤', value: `${d.max_drawdown_pct?.toFixed(2)}%`, color: '#e6a23c' },
      { label: '夏普比率', value: d.sharpe_ratio?.toFixed(2) },
      { label: '胜率', value: `${d.win_rate?.toFixed(1)}%` },
      { label: '交易次数', value: d.total_trades },
      { label: '盈利因子', value: d.profit_factor?.toFixed(2) },
      { label: '连续亏损', value: d.consecutive_losses || 0, color: '#f56c6c' },
    ]

    ElMessage.success(res.comparison ? '回测完成 — 查看筛选对比效果' : '回测完成')

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

function getParamStep(key) {
  const floatKeys = ['pullback_near_ma_pct', 'vol_contraction_ratio', 'vol_expansion_ratio', 'stop_loss_ma_break_pct', 'hard_stop_pct', 'ma_slope_flat_threshold']
  return floatKeys.includes(key) ? 0.1 : 1
}

function getParamPrecision(key) {
  const floatKeys = ['pullback_near_ma_pct', 'vol_contraction_ratio', 'vol_expansion_ratio', 'stop_loss_ma_break_pct', 'hard_stop_pct', 'ma_slope_flat_threshold']
  return floatKeys.includes(key) ? 2 : 0
}

function viewBacktest(row) {
  result.value = row
  comparisonResult.value = null
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
