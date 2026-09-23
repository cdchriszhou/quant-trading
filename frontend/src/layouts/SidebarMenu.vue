<template>
  <div class="sidebar-menu">
    <div class="brand" @click="go('/dashboard')">
      <span class="brand-q">Q</span>
      <span v-show="!isCollapse" class="brand-text">QUANT</span>
    </div>

    <!--
      生产注意：
      1) 不要用 el-menu 的 router（布尔属性会编成 ""，且嵌套项 indexPath 易抛错）
      2) 不要依赖绝对定位 nav-mask（生产 CSS/折叠弹出层下常盖不住）
      3) 在子节点 @click.stop.prevent 里直接 router.push，并保留 hash 兜底
    -->
    <el-menu
      :default-active="activeMenu"
      :collapse="isCollapse"
      background-color="#ffffff"
      text-color="#6b7280"
      active-text-color="#00B4B4"
<<<<<<< HEAD
      :default-openeds="['market-group', 'strategy', 'trading']"
      style="border-right: none; margin-top: 8px"
      @select="onMenuSelect"
=======
      :default-openeds="['strategy', 'trading', 'admin']"
      :router="false"
      class="side-el-menu"
>>>>>>> 4b5774d (feat: add stock recommend, insight popup, and trading UX upgrades)
    >
      <el-menu-item index="/dashboard">
        <div class="nav-hit" role="link" @click.stop.prevent="go('/dashboard')">
          <el-icon><Odometer /></el-icon>
          <span>仪表盘</span>
        </div>
      </el-menu-item>

      <el-menu-item index="/market">
        <div class="nav-hit" role="link" @click.stop.prevent="go('/market')">
          <el-icon><DataLine /></el-icon>
          <span>实时行情</span>
        </div>
      </el-menu-item>

      <el-sub-menu index="strategy">
        <template #title>
          <el-icon><Setting /></el-icon>
          <span>量化策略</span>
        </template>
        <el-menu-item index="/strategies">
          <div class="nav-hit" role="link" @click.stop.prevent="go('/strategies')">
            <span>策略管理</span>
          </div>
        </el-menu-item>
        <el-menu-item index="/strategies/create">
          <div class="nav-hit" role="link" @click.stop.prevent="go('/strategies/create')">
            <span>创建策略</span>
          </div>
        </el-menu-item>
        <el-menu-item index="/backtest">
          <div class="nav-hit" role="link" @click.stop.prevent="go('/backtest')">
            <span>策略回测</span>
          </div>
        </el-menu-item>
      </el-sub-menu>

      <el-sub-menu index="trading">
        <template #title>
          <el-icon><Money /></el-icon>
          <span>交易管理</span>
        </template>
        <el-menu-item index="/trading">
          <div class="nav-hit" role="link" @click.stop.prevent="go('/trading')">
            <span>快速交易</span>
          </div>
        </el-menu-item>
        <el-menu-item index="/recommend">
          <div class="nav-hit" role="link" @click.stop.prevent="go('/recommend')">
            <span>资金匹配推荐</span>
          </div>
        </el-menu-item>
        <el-menu-item index="/trading/orders">
          <div class="nav-hit" role="link" @click.stop.prevent="go('/trading/orders')">
            <span>订单查询</span>
          </div>
        </el-menu-item>
        <el-menu-item index="/trading/positions">
          <div class="nav-hit" role="link" @click.stop.prevent="go('/trading/positions')">
            <span>持仓查询</span>
          </div>
        </el-menu-item>
      </el-sub-menu>

      <el-menu-item index="/risk">
        <div class="nav-hit" role="link" @click.stop.prevent="go('/risk')">
          <el-icon><WarningFilled /></el-icon>
          <span>风险控制</span>
        </div>
      </el-menu-item>
      <el-menu-item index="/reports">
        <div class="nav-hit" role="link" @click.stop.prevent="go('/reports')">
          <el-icon><DataBoard /></el-icon>
          <span>数据报表</span>
        </div>
      </el-menu-item>

      <el-sub-menu v-if="userStore.isAdmin" index="admin">
        <template #title>
          <el-icon><UserFilled /></el-icon>
          <span>系统管理</span>
        </template>
        <el-menu-item index="/admin/users">
          <div class="nav-hit" role="link" @click.stop.prevent="go('/admin/users')">
            <span>用户管理</span>
          </div>
        </el-menu-item>
        <el-menu-item index="/admin/broker">
          <div class="nav-hit" role="link" @click.stop.prevent="go('/admin/broker')">
            <span>实盘接入</span>
          </div>
        </el-menu-item>
        <el-menu-item index="/admin/llm">
          <div class="nav-hit" role="link" @click.stop.prevent="go('/admin/llm')">
            <span>大模型接入</span>
          </div>
        </el-menu-item>
        <el-menu-item index="/admin/logs">
          <div class="nav-hit" role="link" @click.stop.prevent="go('/admin/logs')">
            <span>操作日志</span>
          </div>
        </el-menu-item>
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

<<<<<<< HEAD
function handleLogoClick() {
  router.push('/dashboard')
  emit('nav')
}

function onMenuSelect(index) {
  // Only navigate if index looks like a route path (starts with '/')
  // Sub-menu group indices like "market-group" should only toggle expansion
  if (index && typeof index === 'string' && index.startsWith('/')) {
    router.push(index).catch(() => {})
  }
=======
function go(path) {
  if (!path || typeof path !== 'string') return
  const target = path.startsWith('/') ? path : `/${path}`
>>>>>>> 4b5774d (feat: add stock recommend, insight popup, and trading UX upgrades)
  emit('nav')
  // Hash 模式：push 失败时仍可改 location.hash
  router.push(target).catch(() => {
    if (window.location.hash !== `#${target}`) {
      window.location.hash = `#${target}`
    }
  })
}
</script>

<style scoped>
.brand {
  height: 56px;
  display: flex;
  align-items: center;
  padding: 0 18px;
  gap: 10px;
  border-bottom: 1px solid #e5e7eb;
  cursor: pointer;
}
.brand-q {
  font-size: 22px;
  font-weight: 800;
  color: var(--gp-cyan);
  letter-spacing: -1px;
  flex-shrink: 0;
}
.brand-text {
  font-size: 15px;
  font-weight: 700;
  letter-spacing: 2px;
  color: #1a1a1a;
  white-space: nowrap;
}
.side-el-menu {
  border-right: none;
  margin-top: 8px;
}
/* 占满菜单项可点区域，拦截点击，避免冒泡进 Element Plus 的 indexPath 逻辑 */
.nav-hit {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  min-height: 100%;
  margin: 0 -20px;
  padding: 0 20px;
  box-sizing: border-box;
  cursor: pointer;
  color: inherit;
  text-decoration: none;
  user-select: none;
}
:deep(.el-menu-item) {
  padding: 0 !important;
}
:deep(.el-menu-item.is-active) .nav-hit {
  color: #00B4B4;
  font-weight: 600;
}
:deep(.el-sub-menu .el-menu-item) {
  padding: 0 !important;
}
:deep(.el-sub-menu .el-menu-item .nav-hit) {
  padding-left: 48px;
}
</style>
