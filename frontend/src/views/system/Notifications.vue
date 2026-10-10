<template>
  <el-card shadow="never">
    <template #header>
      <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px">
        <span style="font-weight: 700">全部消息</span>
        <div style="display: flex; gap: 8px; align-items: center">
          <el-radio-group v-model="unreadOnly" size="small" @change="page = 1; load()">
            <el-radio-button :value="false">全部</el-radio-button>
            <el-radio-button :value="true">未读</el-radio-button>
          </el-radio-group>
          <el-button v-if="unreadCount > 0" size="small" @click="markAll">全部已读</el-button>
          <el-button text type="primary" size="small" :loading="loading" @click="load">刷新</el-button>
        </div>
      </div>
    </template>

    <el-alert
      v-if="loadError"
      type="error"
      :closable="false"
      show-icon
      style="margin-bottom: 12px"
      :title="loadError"
    />

    <div v-if="items.length" class="notif-list">
      <div
        v-for="n in items"
        :key="n.id"
        class="notif-row"
        :class="{ unread: !n.is_read }"
        @click="markOne(n)"
      >
        <div class="notif-time">{{ formatTime(n.created_at) }}</div>
        <div class="notif-body">
          <div class="notif-title">
            <span v-if="!n.is_read" class="dot" />
            {{ n.title }}
          </div>
          <div v-if="n.message" class="notif-msg">{{ n.message }}</div>
          <div v-if="n.symbol || n.strategy_name" class="notif-tags">
            <el-tag v-if="n.symbol" size="small" type="info">{{ n.symbol }}</el-tag>
            <el-tag v-if="n.price" size="small">{{ n.price }}</el-tag>
            <el-tag v-if="n.strategy_name" size="small" type="warning" effect="plain">{{ n.strategy_name }}</el-tag>
          </div>
        </div>
      </div>
    </div>
    <el-empty v-else-if="!loading" :description="emptyHint" />

    <div v-if="total > pageSize" style="display: flex; justify-content: flex-end; margin-top: 12px">
      <el-pagination
        v-model:current-page="page"
        :page-size="pageSize"
        :total="total"
        layout="prev, pager, next, total"
        small
        @current-change="load"
      />
    </div>
  </el-card>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { notificationsApi } from '@/api/notifications'

const items = ref([])
const total = ref(0)
const unreadCount = ref(0)
const page = ref(1)
const pageSize = 30
const unreadOnly = ref(false)
const loading = ref(false)
const loadError = ref('')

const emptyHint = computed(() => {
  if (loadError.value) return '消息列表加载失败'
  if (unreadOnly.value) return '没有未读消息'
  return '暂无消息'
})

function formatTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return String(iso)
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  const h = String(d.getHours()).padStart(2, '0')
  const min = String(d.getMinutes()).padStart(2, '0')
  const s = String(d.getSeconds()).padStart(2, '0')
  return `${y}-${m}-${day} ${h}:${min}:${s}`
}

async function load() {
  loading.value = true
  loadError.value = ''
  try {
    const res = await notificationsApi.list({
      page: page.value,
      page_size: pageSize,
      unread_only: unreadOnly.value,
    })
    items.value = res?.items ?? res?.data?.items ?? []
    total.value = res?.total ?? res?.data?.total ?? 0
    unreadCount.value = res?.unread_count ?? res?.data?.unread_count ?? 0
  } catch (e) {
    loadError.value = e?.response?.data?.detail || e?.message || '消息列表接口失败，请确认后端已重启'
    items.value = []
  } finally {
    loading.value = false
  }
}

async function markOne(n) {
  if (n.is_read) return
  try {
    await notificationsApi.markRead({ ids: [n.id] })
    n.is_read = true
    unreadCount.value = Math.max(0, unreadCount.value - 1)
  } catch (e) { /* ignore */ }
}

async function markAll() {
  try {
    await notificationsApi.markRead({})
    items.value.forEach((n) => { n.is_read = true })
    unreadCount.value = 0
    if (unreadOnly.value) await load()
  } catch (e) { /* ignore */ }
}

onMounted(load)
</script>

<style scoped>
.notif-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.notif-row {
  display: flex;
  gap: 14px;
  padding: 12px 10px;
  border-radius: 8px;
  cursor: pointer;
}
.notif-row.unread {
  background: rgba(0, 180, 180, 0.05);
}
.notif-row:hover {
  background: #f5f7fa;
}
.notif-time {
  width: 150px;
  flex-shrink: 0;
  font-size: 12px;
  color: #9ca3af;
  padding-top: 2px;
}
.notif-body {
  min-width: 0;
  flex: 1;
}
.notif-title {
  font-size: 14px;
  font-weight: 650;
  color: #111827;
}
.dot {
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #00B4B4;
  margin-right: 6px;
  vertical-align: middle;
}
.notif-msg {
  margin-top: 4px;
  font-size: 13px;
  color: #6b7280;
  line-height: 1.45;
  white-space: pre-wrap;
}
.notif-tags {
  margin-top: 6px;
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}
</style>
