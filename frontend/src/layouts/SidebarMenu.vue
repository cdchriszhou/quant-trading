<template>
  <div>
    <div
      style="height: 56px; display: flex; align-items: center; padding: 0 18px; gap: 10px; border-bottom: 1px solid #e5e7eb; cursor: pointer"
      @click="handleLogoClick"
    >
      <span style="font-size: 22px; font-weight: 800; color: var(--gp-cyan); letter-spacing: -1px; flex-shrink: 0">Q</span>
      <span v-show="!isCollapse" style="font-size: 15px; font-weight: 700; letter-spacing: 2px; color: #1a1a1a; white-space: nowrap">QUANT</span>
    </div>

    <el-menu
      :default-active="activeMenu"
      :collapse="isCollapse"
      background-color="#ffffff"
      text-color="#6b7280"
      active-text-color="#00B4B4"
      :default-openeds="['market-group', 'strategy', 'trading']"
      router
      style="border-right: none; margin-top: 8px"
      @select="onMenuSelect"
    >
      <el-menu-item index="/dashboard">
        <el-icon><Odometer /></el-icon>
        <span>仪表盘</span>
      </el-menu-item>
      <el-sub-menu index="market-group">
        <template #title>
          <el-icon><DataLine /></el-icon>
          <span>行情分析</span>
        </template>
        <el-menu-item index="/market">实时行情</el-menu-item>
        <el-menu-item index="/market/sectors">板块轮动</el-menu-item>
      </el-sub-menu>
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
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'

defineProps({
  isCollapse: { type: Boolean, default: false },
})

const emit = defineEmits(['nav'])

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const activeMenu = computed(() => route.path)

function handleLogoClick() {
  router.push('/dashboard')
  emit('nav')
}

function onMenuSelect() {
  emit('nav')
}
</script>
