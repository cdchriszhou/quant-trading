<template>
  <div>
    <!-- Header: sector ranking filter -->
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; flex-wrap: wrap; gap: 8px">
      <div>
        <span style="font-weight: 700; font-size: 16px">📊 行业板块轮动</span>
        <span style="font-size: 11px; color: #9ca3af; margin-left: 8px">Core 2: 主线优先</span>
      </div>
      <div style="display: flex; gap: 8px; align-items: center">
        <span style="font-size: 11px; color: #6b7280">显示前</span>
        <el-input-number v-model="topN" :min="5" :max="30" size="small" style="width: 80px" />
        <span style="font-size: 11px; color: #6b7280">名</span>
        <el-button size="small" @click="loadRanking(true)" :icon="RefreshRight">刷新</el-button>
      </div>
    </div>

    <!-- Benchmark info -->
    <el-alert v-if="avgPriceChange !== null" type="info" :closable="false" style="margin-bottom: 12px">
      <template #title>
        近20日平均股价涨跌: <strong :style="{ color: avgPriceChange >= 0 ? '#ef4444' : '#10b981' }">
          {{ avgPriceChange >= 0 ? '+' : '' }}{{ avgPriceChange }}%
        </strong>
        | 板块跑赢此基准即为强势
      </template>
    </el-alert>

    <!-- Sector ranking table -->
    <el-card shadow="never">
      <template #header>
        <span style="font-weight: 700; font-size: 14px">🏆 行业板块强度排名</span>
      </template>

      <div v-if="loading" style="text-align: center; padding: 32px">
        <el-icon class="is-loading" :size="32"><Loading /></el-icon>
        <div style="margin-top: 8px; color: #9ca3af; font-size: 12px">正在分析板块趋势...</div>
      </div>

      <div v-else-if="ranking.length" style="overflow-x: auto; -webkit-overflow-scrolling: touch">
        <el-table :data="ranking" stripe size="small" highlight-current-row
          @row-click="showSectorDetail">
          <el-table-column label="排名" width="55" align="center">
            <template #default="{ row }">
              <span :style="{ fontWeight: 700, color: row.rank <= 3 ? '#f59e0b' : '#6b7280' }">
                {{ row.rank }}
              </span>
            </template>
          </el-table-column>
          <el-table-column label="板块名称" min-width="110">
            <template #default="{ row }">
              <div style="font-weight: 600; font-size: 13px">{{ row.sector_name }}</div>
              <div style="font-size: 11px; color: #9ca3af">{{ row.sector_code }}</div>
            </template>
          </el-table-column>
          <el-table-column label="综合评分" width="90" align="right" sortable prop="strength_score">
            <template #default="{ row }">
              <span :style="{ fontWeight: 700, fontSize: 14, color: row.strength_score >= 60 ? '#ef4444' : row.strength_score >= 40 ? '#f59e0b' : '#9ca3af' }">
                {{ row.strength_score }}
              </span>
            </template>
          </el-table-column>
          <el-table-column label="均线形态" width="80" align="center">
            <template #default="{ row }">
              <el-tag :type="maAlignType(row.ma_alignment)" size="small" effect="plain">
                {{ maAlignLabel(row.ma_alignment) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="20日涨幅" width="85" align="right">
            <template #default="{ row }">
              <span :style="{ fontWeight: 600, color: row.change_20d >= 0 ? '#ef4444' : '#10b981' }">
                {{ row.change_20d >= 0 ? '+' : '' }}{{ row.change_20d }}%
              </span>
            </template>
          </el-table-column>
          <el-table-column label="涨停家数" width="75" align="center" prop="limit_up_count" />
          <el-table-column label="龙头股" width="100">
            <template #default="{ row }">
              <span style="font-size: 12px">{{ row.leading_stock || '-' }}</span>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="70" align="center">
            <template #default="{ row }">
              <el-tag :type="row.is_blacklisted ? 'danger' : 'success'" size="small" effect="dark">
                {{ row.is_blacklisted ? '已拉黑' : '可用' }}
              </el-tag>
            </template>
          </el-table-column>
        </el-table>
      </div>
      <el-empty v-else description="板块数据加载失败" />
    </el-card>

    <!-- Sector detail drawer -->
    <el-drawer v-model="drawerVisible" :title="selectedSector?.sector_name" size="480px">
      <template v-if="selectedSector">
        <el-descriptions :column="1" border size="small">
          <el-descriptions-item label="板块代码">{{ selectedSector.sector_code }}</el-descriptions-item>
          <el-descriptions-item label="综合评分">{{ selectedSector.strength_score }}</el-descriptions-item>
          <el-descriptions-item label="排名">{{ selectedSector.rank }}</el-descriptions-item>
          <el-descriptions-item label="均线形态">
            <el-tag :type="maAlignType(selectedSector.ma_alignment)" size="small">{{ maAlignLabel(selectedSector.ma_alignment) }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="MA5">{{ selectedSector.ma5 || '-' }}</el-descriptions-item>
          <el-descriptions-item label="MA10">{{ selectedSector.ma10 || '-' }}</el-descriptions-item>
          <el-descriptions-item label="MA20">{{ selectedSector.ma20 || '-' }}</el-descriptions-item>
          <el-descriptions-item label="MA60">{{ selectedSector.ma60 || '-' }}</el-descriptions-item>
          <el-descriptions-item label="20日涨跌幅">{{ selectedSector.change_20d }}%</el-descriptions-item>
          <el-descriptions-item label="涨停家数">{{ selectedSector.limit_up_count }}</el-descriptions-item>
          <el-descriptions-item label="龙头股">{{ selectedSector.leading_stock }}</el-descriptions-item>
        </el-descriptions>

        <el-divider />

        <!-- Stocks within this sector -->
        <h4 style="font-size: 13px; margin-bottom: 8px">板块成分股（已筛选）</h4>
        <el-button size="small" @click="loadSectorStocks(selectedSector.sector_code)" :loading="stocksLoading" style="margin-bottom: 8px">
          加载成分股
        </el-button>
        <div v-if="sectorStocks.length" style="max-height: 400px; overflow-y: auto">
          <div v-for="s in sectorStocks" :key="s.symbol"
            style="display: flex; justify-content: space-between; align-items: center; padding: 6px 0; border-bottom: 1px solid #f3f4f6; font-size: 12px">
            <div>
              <span style="font-weight: 600">{{ s.symbol?.replace('.SZ','').replace('.SH','') }}</span>
              <span style="color: #6b7280; margin-left: 4px">{{ s.name }}</span>
            </div>
            <div style="display: flex; gap: 8px; align-items: center">
              <span v-if="s.criteria_met !== undefined">
                <el-tag :type="s.criteria_met ? 'success' : 'info'" size="small" effect="plain">
                  {{ s.criteria_met ? '合格' : '未达标' }}
                </el-tag>
              </span>
              <span v-if="s.buy_signal" style="color: #ef4444; font-weight: 600">买入信号</span>
            </div>
          </div>
        </div>
      </template>
    </el-drawer>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { RefreshRight, Loading } from '@element-plus/icons-vue'
import { getSectorRanking, getSectorStocks } from '@/api/sector'
import { ElMessage } from 'element-plus'

const topN = ref(10)
const loading = ref(false)
const ranking = ref([])
const avgPriceChange = ref(null)
const drawerVisible = ref(false)
const selectedSector = ref(null)
const sectorStocks = ref([])
const stocksLoading = ref(false)

function maAlignType(align) {
  const map = { bullish: 'danger', mixed: 'warning', bearish: 'info', unknown: '' }
  return map[align] || ''
}

function maAlignLabel(align) {
  const map = { bullish: '多头排列', mixed: '混合', bearish: '空头排列', unknown: '数据不足' }
  return map[align] || align
}

async function loadRanking(forceRefresh = false) {
  loading.value = true
  try {
    const res = await getSectorRanking(forceRefresh, topN.value)
    const data = res.data
    ranking.value = data.top_sectors || []
    avgPriceChange.value = data.avg_stock_price_change_20d ?? null
  } catch (e) {
    ElMessage.error('板块排名加载失败')
    console.error(e)
  } finally {
    loading.value = false
  }
}

function showSectorDetail(row) {
  selectedSector.value = row
  sectorStocks.value = []
  drawerVisible.value = true
}

async function loadSectorStocks(sectorCode) {
  if (!sectorCode) return
  stocksLoading.value = true
  try {
    const res = await getSectorStocks(sectorCode, true, 30)
    sectorStocks.value = res.data || []
  } catch (e) {
    ElMessage.error('成分股加载失败')
  } finally {
    stocksLoading.value = false
  }
}

onMounted(() => {
  loadRanking()
})
</script>
