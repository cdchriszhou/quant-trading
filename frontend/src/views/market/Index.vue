<template>
  <div>
    <el-card shadow="never" style="margin-bottom: 16px">
      <div style="display: flex; gap: 12px; align-items: center">
        <el-select v-model="selectedSymbol" filterable placeholder="选择标的" style="width: 200px" @change="loadData">
          <el-option v-for="s in symbols" :key="s.code" :label="`${s.code} - ${s.name}`" :value="s.code" />
        </el-select>
        <el-radio-group v-model="selectedPeriod" @change="loadData">
          <el-radio-button value="1d">日K</el-radio-button>
          <el-radio-button value="1w">周K</el-radio-button>
          <el-radio-button value="30m">30分</el-radio-button>
        </el-radio-group>
      </div>
    </el-card>

    <el-row :gutter="16">
      <el-col :span="16">
        <el-card shadow="never" style="margin-bottom: 16px">
          <div ref="klineChartRef" style="height: 450px; width: 100%"></div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="never" style="margin-bottom: 16px">
          <template #header><span style="font-weight: bold">实时行情</span></template>
          <div v-if="quote" style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px">
            <div><span style="color: #909399">最新价</span><br><span style="font-size: 24px; font-weight: bold">{{ quote.current_price }}</span></div>
            <div><span style="color: #909399">涨跌幅</span><br><span :style="{ fontSize: '24px', fontWeight: 'bold', color: (quote.change_pct || 0) > 0 ? '#f56c6c' : '#67c23a' }">{{ quote.change_pct }}%</span></div>
            <div><span style="color: #909399">最高</span><br><span>{{ quote.high }}</span></div>
            <div><span style="color: #909399">最低</span><br><span>{{ quote.low }}</span></div>
            <div><span style="color: #909399">开盘</span><br><span>{{ quote.open }}</span></div>
            <div><span style="color: #909399">昨收</span><br><span>{{ quote.pre_close }}</span></div>
            <div><span style="color: #909399">成交量</span><br><span>{{ (quote.volume / 10000).toFixed(0) }}万</span></div>
            <div><span style="color: #909399">成交额</span><br><span>{{ quote.amount }}亿</span></div>
          </div>
          <div v-else style="text-align: center; padding: 20px; color: #909399">加载中...</div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { marketApi } from '@/api/market'
import * as echarts from 'echarts'

const selectedSymbol = ref('000001.SZ')
const selectedPeriod = ref('1d')
const symbols = ref([])
const quote = ref(null)
const klineChartRef = ref(null)
let klineChart = null
let quoteInterval = null

async function loadSymbols() {
  try {
    const res = await marketApi.searchSymbols()
    symbols.value = res.data || []
  } catch (e) { console.error(e) }
}

async function loadData() {
  try {
    const res = await marketApi.getQuote(selectedSymbol.value)
    quote.value = res
  } catch (e) { console.error(e) }

  try {
    const res = await marketApi.getKline(selectedSymbol.value, selectedPeriod.value, 120)
    const kdata = res.data || []
    await nextTick()
    renderKline(kdata)
  } catch (e) { console.error(e) }
}

function renderKline(data) {
  if (klineChart) klineChart.dispose()
  if (!data.length) return

  klineChart = echarts.init(klineChartRef.value)
  const dates = data.map(d => d.date)
  const vols = data.map(d => d.volume)
  const values = data.map(d => [d.open, d.close, d.low, d.high])

  klineChart.setOption({
    tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
    grid: [{ left: '10%', right: '8%', top: '10%', height: '60%' }, { left: '10%', right: '8%', top: '78%', height: '15%' }],
    xAxis: [{ type: 'category', data: dates, gridIndex: 0, axisLabel: { rotate: 45 } }, { type: 'category', data: dates, gridIndex: 1, show: false }],
    yAxis: [{ type: 'value', gridIndex: 0, scale: true }, { type: 'value', gridIndex: 1, scale: true }],
    series: [
      {
        type: 'candlestick', data: values,
        itemStyle: { color: '#f56c6c', color0: '#67c23a', borderColor: '#f56c6c', borderColor0: '#67c23a' },
      },
      {
        type: 'bar', data: vols, xAxisIndex: 1, yAxisIndex: 1,
        itemStyle: { color: 'rgba(64,158,255,0.3)' },
      },
    ],
  })
}

onMounted(() => {
  loadSymbols()
  loadData()
  quoteInterval = setInterval(() => {
    marketApi.getQuote(selectedSymbol.value).then(r => { quote.value = r }).catch(() => {})
  }, 5000)
})

onUnmounted(() => {
  if (klineChart) klineChart.dispose()
  if (quoteInterval) clearInterval(quoteInterval)
})
</script>
