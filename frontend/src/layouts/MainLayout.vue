<template>
  <el-container style="height: 100vh">
    <el-aside :width="isCollapse ? '64px' : '220px'" style="background: #1f2d3d; transition: width 0.3s">
      <div class="logo-container" style="height: 60px; display: flex; align-items: center; justify-content: center; color: #fff; font-size: 18px; font-weight: bold; border-bottom: 1px solid rgba(255,255,255,0.1)">
        <el-icon :size="24" style="margin-right: 8px"><TrendCharts /></el-icon>
        <span v-show="!isCollapse">量化交易系统</span>
      </div>
      <el-menu
        :default-active="activeMenu"
        :collapse="isCollapse"
        background-color="#1f2d3d"
        text-color="rgba(255,255,255,0.7)"
        active-text-color="#409EFF"
        router
        style="border-right: none"
      >
        <el-menu-item index="/dashboard">
          <el-icon><Odometer /></el-icon>
          <span>仪表盘</span>
        </el-menu-item>
        <el-menu-item index="/market">
          <el-icon><DataLine /></el-icon>
          <span>行情数据</span>
        </el-menu-item>
        <el-sub-menu index="strategy">
          <template #title>
            <el-icon><Setting /></el-icon>
            <span>量化策略</span>
          </template>
          <el-menu-item index="/strategies">策略管理</el-menu-item>
          <el-menu-item index="/strategies/create">创建策略</el-menu-item>
          <el-menu-item index="/backtest">策略回测</el-menu-item>
        </el-sub-menu>
        <el-sub-menu index="trading">
          <template #title>
            <el-icon><Money /></el-icon>
            <span>交易管理</span>
          </template>
          <el-menu-item index="/trading">快速交易</el-menu-item>
          <el-menu-item index="/trading/orders">订单查询</el-menu-item>
          <el-menu-item index="/trading/positions">持仓查询</el-menu-item>
        </el-sub-menu>
        <el-menu-item index="/risk">
          <el-icon><WarningFilled /></el-icon>
          <span>风险控制</span>
        </el-menu-item>
        <el-menu-item index="/reports">
          <el-icon><DataBoard /></el-icon>
          <span>数据报表</span>
        </el-menu-item>
        <el-sub-menu v-if="userStore.isAdmin" index="admin">
          <template #title>
            <el-icon><UserFilled /></el-icon>
            <span>系统管理</span>
          </template>
          <el-menu-item index="/admin/users">用户管理</el-menu-item>
          <el-menu-item index="/admin/logs">操作日志</el-menu-item>
        </el-sub-menu>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header style="height: 50px; background: #fff; border-bottom: 1px solid #e6e6e6; display: flex; align-items: center; justify-content: space-between; padding: 0 20px">
        <div style="display: flex; align-items: center">
          <el-icon style="cursor: pointer; font-size: 20px" @click="isCollapse = !isCollapse">
            <Fold v-if="!isCollapse" /><Expand v-else />
          </el-icon>
          <el-breadcrumb separator="/" style="margin-left: 20px">
            <el-breadcrumb-item :to="{ path: '/dashboard' }">首页</el-breadcrumb-item>
            <el-breadcrumb-item v-if="route.name">{{ route.meta?.title || route.name }}</el-breadcrumb-item>
          </el-breadcrumb>
        </div>
        <div style="display: flex; align-items: center; gap: 16px">
          <el-tag v-if="wsConnected" type="success" size="small">行情连接</el-tag>
          <el-tag v-else type="danger" size="small">未连接</el-tag>
          <el-dropdown @command="handleCommand">
            <span style="cursor: pointer; display: flex; align-items: center">
              <el-icon><User /></el-icon>
              <span style="margin-left: 4px">{{ userStore.displayName }}</span>
              <el-icon><ArrowDown /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="profile">个人信息</el-dropdown-item>
                <el-dropdown-item command="logout" divided>退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>
      <el-main style="background: #f0f2f5; padding: 16px; overflow-y: auto">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const isCollapse = ref(false)
const wsConnected = ref(false)
let ws = null

const activeMenu = computed(() => route.path)

function handleCommand(command) {
  if (command === 'logout') {
    userStore.logout()
    if (ws) ws.close()
    router.push('/login')
  } else if (command === 'profile') {
    // Profile dialog could go here
  }
}

function connectWebSocket() {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = window.location.host
  ws = new WebSocket(`${protocol}//${host}/ws/market`)

  ws.onopen = () => { wsConnected.value = true }
  ws.onclose = () => { wsConnected.value = false }
  ws.onerror = () => { wsConnected.value = false }
  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      // Could dispatch to a store for real-time updates
    } catch (e) {}
  }
}

onMounted(() => {
  connectWebSocket()
})

onUnmounted(() => {
  if (ws) ws.close()
})
</script>
