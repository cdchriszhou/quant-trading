<template>
  <el-container style="height: 100vh">
    <!-- Desktop Sidebar -->
    <el-aside
      v-if="!isMobile"
      :width="isCollapse ? '64px' : '220px'"
      style="background: #fff; border-right: 1px solid #e5e7eb; transition: width 0.3s; flex-shrink: 0"
    >
      <SidebarMenu :is-collapse="isCollapse" />
    </el-aside>

    <!-- Mobile Drawer Overlay -->
    <teleport to="body">
      <div
        v-if="isMobile && drawerOpen"
        style="position: fixed; inset: 0; z-index: 2000; display: flex"
        @click.self="drawerOpen = false"
      >
        <!-- Backdrop -->
        <div
          style="position: absolute; inset: 0; background: rgba(0,0,0,0.4)"
          @click="drawerOpen = false"
        />
        <!-- Drawer -->
        <div style="position: relative; width: 240px; height: 100%; background: #fff; overflow-y: auto; box-shadow: 2px 0 12px rgba(0,0,0,0.15)">
          <SidebarMenu :is-collapse="false" @nav="drawerOpen = false" />
        </div>
      </div>
    </teleport>

    <el-container>
      <el-header style="height: 48px; min-height: 48px; background: #fff; border-bottom: 1px solid #e5e7eb; display: flex; align-items: center; justify-content: space-between; padding: 0 12px; flex-shrink: 0">
        <div style="display: flex; align-items: center; gap: 8px">
          <!-- Mobile hamburger -->
          <el-icon v-if="isMobile" style="cursor: pointer; font-size: 22px; color: #374151" @click="drawerOpen = true">
            <Menu />
          </el-icon>
          <!-- Desktop collapse toggle -->
          <el-icon v-else style="cursor: pointer; font-size: 20px; color: #6b7280" @click="isCollapse = !isCollapse">
            <Fold v-if="!isCollapse" /><Expand v-else />
          </el-icon>
          <el-breadcrumb separator="/" style="font-size: 13px">
            <el-breadcrumb-item :to="{ path: '/dashboard' }">首页</el-breadcrumb-item>
            <el-breadcrumb-item v-if="route.name && route.path !== '/dashboard'">
              <span style="max-width: 120px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; display: inline-block; vertical-align: middle">
                {{ route.meta?.title || route.name }}
              </span>
            </el-breadcrumb-item>
          </el-breadcrumb>
        </div>
        <div style="display: flex; align-items: center; gap: 10px">
          <!-- Notification bell -->
          <el-popover
            placement="bottom-end"
            :width="380"
            trigger="click"
            :visible="notifPopVisible"
            @show="onNotifOpen"
            @hide="notifPopVisible = false"
          >
            <template #reference>
              <el-badge :value="unreadCount" :hidden="unreadCount === 0" :max="99" style="cursor: pointer" @click="notifPopVisible = !notifPopVisible">
                <el-icon :size="20" style="color: #6b7280">
                  <Bell />
                </el-icon>
              </el-badge>
            </template>
            <div style="max-height: 420px; display: flex; flex-direction: column">
              <div style="display: flex; justify-content: space-between; align-items: center; padding-bottom: 10px; border-bottom: 1px solid #e5e7eb; margin-bottom: 6px">
                <span style="font-weight: 700; font-size: 14px">消息通知</span>
                <el-button v-if="unreadCount > 0" text size="small" @click="markAllRead">全部已读</el-button>
              </div>
              <div style="overflow-y: auto; flex: 1; min-height: 0">
                <div v-if="notifications.length === 0" style="text-align: center; padding: 28px 0; color: #9ca3af">暂无通知</div>
                <div
                  v-for="n in notifications"
                  :key="n.id"
                  style="padding: 10px 8px; border-radius: 6px; cursor: pointer; margin-bottom: 2px; transition: background 0.15s"
                  :style="{ background: n.is_read ? 'transparent' : 'rgba(0,180,180,0.04)' }"
                  @click="markOneRead(n)"
                >
                  <div style="display: flex; align-items: flex-start; gap: 8px">
                    <span style="font-size: 12px; color: #9ca3af; white-space: nowrap; padding-top: 1px">{{ formatTime(n.created_at) }}</span>
                    <div style="flex: 1; min-width: 0">
                      <div style="font-size: 13px; font-weight: 600; color: #1a1a1a; margin-bottom: 2px">
                        <span v-if="!n.is_read" style="display: inline-block; width: 6px; height: 6px; border-radius: 50%; background: #00B4B4; margin-right: 6px; vertical-align: middle"></span>
                        {{ n.title }}
                      </div>
                      <div v-if="n.message" style="font-size: 12px; color: #6b7280; line-height: 1.4; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden">{{ n.message }}</div>
                      <div v-if="n.symbol" style="margin-top: 3px">
                        <el-tag size="small" type="info">{{ n.symbol }}</el-tag>
                        <el-tag v-if="n.price" size="small" style="margin-left: 4px">{{ n.price }}</el-tag>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
              <div style="text-align: center; padding-top: 8px; border-top: 1px solid #e5e7eb; margin-top: 6px">
                <el-button text size="small" @click="viewAllNotifications">查看全部</el-button>
              </div>
            </div>
          </el-popover>

          <!-- Live clock -->
          <span style="font-size: 12px; font-weight: 600; color: #374151; white-space: nowrap; font-variant-numeric: tabular-nums; user-select: none">
            {{ nowStr }}
          </span>

          <span style="font-size: 10px; font-weight: 600; letter-spacing: 1px; padding: 2px 6px; border-radius: 3px; white-space: nowrap"
                :style="wsConnected ? 'color:#00B4B4;background:rgba(0,180,180,0.1)' : 'color:#ef4444;background:rgba(239,68,68,0.08)'">
            {{ wsConnected ? 'LIVE' : 'OFFLINE' }}
          </span>
          <el-dropdown @command="handleCommand">
            <span style="cursor: pointer; display: flex; align-items: center; gap: 4px; font-size: 13px; color: #374151; white-space: nowrap">
              <el-icon><User /></el-icon>
              <span style="max-width: 80px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap">{{ userStore.displayName }}</span>
              <el-icon><ArrowDown /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="logout" divided>退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>
      <el-main style="background: #f5f6f8; padding: 12px; overflow-y: auto; overflow-x: hidden">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { notificationsApi } from '@/api/notifications'
import SidebarMenu from './SidebarMenu.vue'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const isCollapse = ref(false)
const drawerOpen = ref(false)
const isMobile = ref(false)
const wsConnected = ref(false)
let ws = null

// ── Live clock ──
const nowStr = ref('')
let clockTimer = null

function updateClock() {
  const d = new Date()
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  const h = String(d.getHours()).padStart(2, '0')
  const min = String(d.getMinutes()).padStart(2, '0')
  const s = String(d.getSeconds()).padStart(2, '0')
  const week = ['日', '一', '二', '三', '四', '五', '六'][d.getDay()]
  nowStr.value = `${y}-${m}-${day} 周${week} ${h}:${min}:${s}`
}

// ── Notification state ──
const notifications = ref([])
const unreadCount = ref(0)
const notifPopVisible = ref(false)
let notifWs = null

// ── Notification methods ──
function formatTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  const now = new Date()
  const diff = now - d
  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return `${Math.floor(diff / 60000)}分钟前`
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}小时前`
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${m}-${day} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

async function fetchNotifications() {
  try {
    const res = await notificationsApi.list({ page: 1, page_size: 20 })
    notifications.value = res.items || []
    unreadCount.value = res.unread_count || 0
  } catch (e) { /* silent */ }
}

async function fetchUnreadCount() {
  try {
    const res = await notificationsApi.unreadCount()
    unreadCount.value = res.unread_count || 0
  } catch (e) { /* silent */ }
}

function onNotifOpen() {
  notifPopVisible.value = true
  fetchNotifications()
}

async function markOneRead(n) {
  if (!n.is_read) {
    try {
      await notificationsApi.markRead({ ids: [n.id] })
      n.is_read = true
      unreadCount.value = Math.max(0, unreadCount.value - 1)
    } catch (e) { /* silent */ }
  }
}

async function markAllRead() {
  try {
    await notificationsApi.markRead({})
    notifications.value.forEach(n => { n.is_read = true })
    unreadCount.value = 0
  } catch (e) { /* silent */ }
}

function viewAllNotifications() {
  notifPopVisible.value = false
  // Could navigate to a dedicated page; for now just re-open
}

function connectNotifWebSocket() {
  const token = localStorage.getItem('token')
  if (!token) return
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = window.location.host
  try {
    notifWs = new WebSocket(`${protocol}//${host}/ws/notifications?token=${token}`)
    notifWs.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data)
        if (msg.type === 'notification') {
          // Prepend new notification to list
          notifications.value.unshift(msg.data)
          unreadCount.value++
          // Trim to max 50 in memory
          if (notifications.value.length > 50) {
            notifications.value = notifications.value.slice(0, 50)
          }
        }
      } catch (e) { /* ignore malformed */ }
    }
    notifWs.onclose = () => {
      // Reconnect after 30s
      setTimeout(() => { if (userStore.isLoggedIn) connectNotifWebSocket() }, 30000)
    }
    notifWs.onerror = () => { /* silent */ }
  } catch (e) { /* WebSocket not supported */ }
}

// ── Lifecycle ──
function checkMobile() {
  isMobile.value = window.innerWidth < 768
  if (isMobile.value) {
    isCollapse.value = true
    drawerOpen.value = false
  }
}

const activeMenu = computed(() => route.path)

function handleCommand(command) {
  if (command === 'logout') {
    userStore.logout()
    if (ws) ws.close()
    if (notifWs) notifWs.close()
    router.push('/login')
  }
}

function connectWebSocket() {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = window.location.host
  ws = new WebSocket(`${protocol}//${host}/ws/market`)
  ws.onopen = () => { wsConnected.value = true }
  ws.onclose = () => { wsConnected.value = false }
  ws.onerror = () => { wsConnected.value = false }
}

onMounted(() => {
  checkMobile()
  window.addEventListener('resize', checkMobile)
  connectWebSocket()
  connectNotifWebSocket()
  fetchUnreadCount()
  updateClock()
  clockTimer = setInterval(updateClock, 1000)
})

onUnmounted(() => {
  window.removeEventListener('resize', checkMobile)
  if (ws) ws.close()
  if (notifWs) notifWs.close()
  if (clockTimer) clearInterval(clockTimer)
})
</script>
