<template>
  <div class="sidebar-menu" :class="{ collapsed: isCollapse }">
    <div class="brand" @click="go('/dashboard')">
      <span class="brand-q">Q</span>
      <span v-show="!isCollapse" class="brand-text">QUANT</span>
    </div>

    <nav class="nav">
      <button
        type="button"
        class="nav-item"
        :class="{ active: isActive('/dashboard') }"
        title="仪表盘"
        @click.stop="go('/dashboard')"
      >
        <el-icon><Odometer /></el-icon>
        <span v-show="!isCollapse">仪表盘</span>
      </button>

      <button
        type="button"
        class="nav-item"
        :class="{ active: isActive('/market') }"
        title="实时行情"
        @click.stop="go('/market')"
      >
        <el-icon><DataLine /></el-icon>
        <span v-show="!isCollapse">实时行情</span>
      </button>

      <div
        v-for="g in primaryGroups"
        :key="g.key"
        class="nav-group"
        :data-key="g.key"
        @mouseenter="onGroupEnter(g.key, $event)"
        @mouseleave="onGroupLeave($event)"
      >
        <button
          type="button"
          class="nav-group-title"
          :title="g.title"
          :aria-expanded="isCollapse ? flyout === g.key : isOpen(g.key)"
          @click.stop="onGroupClick(g.key, $event)"
        >
          <el-icon><component :is="g.icon" /></el-icon>
          <span v-show="!isCollapse" class="group-label">{{ g.title }}</span>
          <el-icon v-show="!isCollapse" class="chevron" :class="{ open: isOpen(g.key) }">
            <ArrowRight />
          </el-icon>
        </button>

        <div v-if="!isCollapse && isOpen(g.key)" class="nav-children">
          <button
            v-for="item in g.items"
            :key="item.path"
            type="button"
            class="nav-item child"
            :class="{ active: isActive(item.path) }"
            @click.stop="go(item.path)"
          >
            {{ item.label }}
          </button>
        </div>
      </div>

      <button
        type="button"
        class="nav-item"
        :class="{ active: isActive('/risk') }"
        title="风险控制"
        @click.stop="go('/risk')"
      >
        <el-icon><WarningFilled /></el-icon>
        <span v-show="!isCollapse">风险控制</span>
      </button>

      <button
        type="button"
        class="nav-item"
        :class="{ active: isActive('/reports') }"
        title="数据报表"
        @click.stop="go('/reports')"
      >
        <el-icon><DataBoard /></el-icon>
        <span v-show="!isCollapse">数据报表</span>
      </button>

      <button
        type="button"
        class="nav-item"
        :class="{ active: isActive('/notifications') }"
        title="全部消息"
        @click.stop="go('/notifications')"
      >
        <el-icon><Bell /></el-icon>
        <span v-show="!isCollapse">全部消息</span>
      </button>

      <div
        v-if="adminGroup"
        class="nav-group"
        data-key="admin"
        @mouseenter="onGroupEnter('admin', $event)"
        @mouseleave="onGroupLeave($event)"
      >
        <button
          type="button"
          class="nav-group-title"
          title="系统管理"
          :aria-expanded="isCollapse ? flyout === 'admin' : isOpen('admin')"
          @click.stop="onGroupClick('admin', $event)"
        >
          <el-icon><UserFilled /></el-icon>
          <span v-show="!isCollapse" class="group-label">系统管理</span>
          <el-icon v-show="!isCollapse" class="chevron" :class="{ open: isOpen('admin') }">
            <ArrowRight />
          </el-icon>
        </button>
        <div v-if="!isCollapse && isOpen('admin')" class="nav-children">
          <button
            v-for="item in adminGroup.items"
            :key="item.path"
            type="button"
            class="nav-item child"
            :class="{ active: isActive(item.path) }"
            @click.stop="go(item.path)"
          >
            {{ item.label }}
          </button>
        </div>
      </div>
    </nav>

    <!-- Collapsed flyout: teleport so aside/nav overflow cannot clip it -->
    <teleport to="body">
      <div
        v-if="isCollapse && flyoutGroup"
        ref="flyoutEl"
        class="flyout-panel"
        :style="flyoutStyle"
        @mouseenter="cancelFlyoutClose"
        @mouseleave="onGroupLeave($event)"
      >
        <div class="flyout-title">{{ flyoutGroup.title }}</div>
        <button
          v-for="item in flyoutGroup.items"
          :key="item.path"
          type="button"
          class="flyout-item"
          :class="{ active: isActive(item.path) }"
          @click.stop="go(item.path)"
        >
          {{ item.label }}
        </button>
      </div>
    </teleport>
  </div>
</template>

<script setup>
import { reactive, ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import {
  Odometer, DataLine, Setting, Money, WarningFilled, DataBoard, UserFilled, ArrowRight, Bell,
} from '@element-plus/icons-vue'

const props = defineProps({
  isCollapse: { type: Boolean, default: false },
})

const emit = defineEmits(['nav'])

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const open = reactive({
  strategy: true,
  trading: true,
  admin: true,
})

const flyout = ref('')
const flyoutStyle = ref({})
const flyoutEl = ref(null)
/** Click-opened flyout stays until outside click / nav (touch-safe). Hover-only may auto-close. */
const flyoutSticky = ref(false)
let flyoutTimer = null

const primaryGroups = [
  {
    key: 'strategy',
    title: '量化策略',
    icon: Setting,
    items: [
      { path: '/strategies', label: '策略管理' },
      { path: '/strategies/create', label: '创建策略' },
      { path: '/backtest', label: '策略回测' },
    ],
  },
  {
    key: 'trading',
    title: '交易管理',
    icon: Money,
    items: [
      { path: '/trading', label: '快速交易' },
      { path: '/recommend', label: '资金匹配推荐' },
      { path: '/trading/orders', label: '订单查询' },
      { path: '/trading/positions', label: '持仓查询' },
    ],
  },
]

const adminGroup = computed(() => {
  if (!userStore.isAdmin) return null
  return {
    key: 'admin',
    title: '系统管理',
    icon: UserFilled,
    items: [
      { path: '/admin/users', label: '用户管理' },
      { path: '/admin/broker', label: '实盘接入' },
      { path: '/admin/llm', label: '大模型接入' },
      { path: '/admin/logs', label: '操作日志' },
    ],
  }
})

const flyoutGroup = computed(() => {
  if (!flyout.value) return null
  if (flyout.value === 'admin') return adminGroup.value
  return primaryGroups.find((g) => g.key === flyout.value) || null
})

watch(
  () => props.isCollapse,
  () => {
    closeFlyout()
  },
)

function isOpen(key) {
  return !!open[key]
}

function isActive(path) {
  if (path === '/strategies') {
    return route.path === '/strategies' || /^\/strategies\/\d+$/.test(route.path)
  }
  return route.path === path
}

function onGroupClick(key, evt) {
  if (props.isCollapse) {
    const anchor = evt?.currentTarget?.closest?.('.nav-group') || evt?.currentTarget
    // Toggle sticky flyout on click (works for mouse + touch)
    if (flyout.value === key && flyoutSticky.value) {
      closeFlyout()
      return
    }
    openFlyout(key, anchor, { sticky: true })
    return
  }
  open[key] = !open[key]
}

function onGroupEnter(key, evt) {
  if (!props.isCollapse) return
  // Don't steal a sticky click-opened panel for another group via hover
  if (flyoutSticky.value && flyout.value && flyout.value !== key) return
  if (flyoutSticky.value && flyout.value === key) {
    cancelFlyoutClose()
    return
  }
  const anchor = evt?.currentTarget
  openFlyout(key, anchor, { sticky: false })
}

function openFlyout(key, el, { sticky = false } = {}) {
  cancelFlyoutClose()
  flyoutSticky.value = sticky
  flyout.value = key
  nextTick(() => {
    const anchor = el || document.querySelector(`.nav-group[data-key="${key}"]`)
    const rect = anchor && typeof anchor.getBoundingClientRect === 'function'
      ? anchor.getBoundingClientRect()
      : null
    if (!rect) {
      flyoutStyle.value = { left: '68px', top: '80px' }
      return
    }
    const panelH = flyoutEl.value?.offsetHeight || 220
    const top = Math.min(rect.top, Math.max(8, window.innerHeight - panelH - 8))
    flyoutStyle.value = {
      left: `${Math.round(rect.right + 6)}px`,
      top: `${Math.round(Math.max(8, top))}px`,
    }
  })
}

function cancelFlyoutClose() {
  if (flyoutTimer) {
    clearTimeout(flyoutTimer)
    flyoutTimer = null
  }
}

function closeFlyout() {
  cancelFlyoutClose()
  flyout.value = ''
  flyoutSticky.value = false
}

function onGroupLeave(evt) {
  if (!props.isCollapse) return
  if (flyoutSticky.value) return
  const next = evt?.relatedTarget
  if (next && (flyoutEl.value?.contains(next) || next.closest?.('.nav-group'))) {
    return
  }
  cancelFlyoutClose()
  flyoutTimer = setTimeout(() => {
    if (!flyoutSticky.value) {
      flyout.value = ''
      flyoutTimer = null
    }
  }, 220)
}

function onDocPointerDown(evt) {
  if (!props.isCollapse || !flyout.value) return
  const t = evt.target
  if (flyoutEl.value?.contains(t)) return
  if (t?.closest?.('.nav-group')) return
  closeFlyout()
}

function onKeydown(evt) {
  if (evt.key === 'Escape') closeFlyout()
}

async function go(path) {
  if (!path || typeof path !== 'string') return
  const target = path.startsWith('/') ? path : `/${path}`
  emit('nav')
  closeFlyout()
  if (route.path === target) return
  try {
    await router.push(target)
  } catch (err) {
    // Ignore duplicate-nav; otherwise force hash update for prod chunk failures
    const msg = String(err?.message || err || '')
    if (/Avoided redundant navigation|NavigationDuplicated/i.test(msg)) return
    const want = `#${target}`
    if (window.location.hash !== want) {
      window.location.hash = want
    }
    console.warn('[Sidebar] navigation fallback', target, err)
  }
}

onMounted(() => {
  document.addEventListener('pointerdown', onDocPointerDown, true)
  document.addEventListener('keydown', onKeydown)
})

onUnmounted(() => {
  document.removeEventListener('pointerdown', onDocPointerDown, true)
  document.removeEventListener('keydown', onKeydown)
  cancelFlyoutClose()
})
</script>

<style scoped>
.sidebar-menu {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #fff;
  position: relative;
  overflow: visible;
  z-index: 20;
}
.brand {
  height: 56px;
  display: flex;
  align-items: center;
  padding: 0 18px;
  gap: 10px;
  border-bottom: 1px solid #e5e7eb;
  cursor: pointer;
  flex-shrink: 0;
}
.brand-q {
  font-size: 22px;
  font-weight: 800;
  color: var(--gp-cyan, #00B4B4);
  letter-spacing: -1px;
  flex-shrink: 0;
}
.brand-text {
  font-size: 15px;
  font-weight: 700;
  letter-spacing: 2px;
  color: #1a1a1a;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.nav {
  padding: 8px 0 16px;
  overflow-y: auto;
  overflow-x: hidden;
  flex: 1;
  min-height: 0;
}
.sidebar-menu.collapsed .nav {
  overflow: visible;
}
.nav-group {
  position: relative;
  z-index: 2;
}
.nav-item,
.nav-group-title {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  min-height: 44px;
  padding: 0 18px;
  border: 0;
  background: transparent;
  color: #6b7280;
  font-size: 14px;
  text-align: left;
  cursor: pointer;
  box-sizing: border-box;
  pointer-events: auto;
  position: relative;
  z-index: 1;
  white-space: nowrap;
}
.nav-item:hover,
.nav-group-title:hover {
  background: #f3f4f6;
  color: #111827;
}
.nav-item.active {
  color: #00B4B4;
  font-weight: 600;
  background: rgba(0, 180, 180, 0.08);
}
.nav-children {
  display: block;
  position: relative;
  z-index: 3;
}
.nav-item.child {
  padding-left: 48px;
  min-height: 40px;
  font-size: 13px;
}
.group-label {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
}
.chevron {
  transition: transform 0.15s ease;
  font-size: 12px;
}
.chevron.open {
  transform: rotate(90deg);
}
.sidebar-menu.collapsed .nav-item,
.sidebar-menu.collapsed .nav-group-title {
  justify-content: center;
  padding: 0;
}
</style>

<style>
/* unscoped: teleported flyout + el-aside overflow (prod CSS chunk must keep these) */
.flyout-panel {
  position: fixed;
  min-width: 168px;
  padding: 6px 0;
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12);
  z-index: 5000;
  pointer-events: auto;
}
.flyout-panel .flyout-title {
  padding: 6px 14px 8px;
  font-size: 12px;
  font-weight: 600;
  color: #9ca3af;
}
.flyout-panel .flyout-item {
  display: flex;
  align-items: center;
  width: 100%;
  min-height: 40px;
  padding: 0 14px;
  border: 0;
  background: transparent;
  color: #6b7280;
  font-size: 13px;
  text-align: left;
  cursor: pointer;
  box-sizing: border-box;
  white-space: nowrap;
}
.flyout-panel .flyout-item:hover {
  background: #f3f4f6;
  color: #111827;
}
.flyout-panel .flyout-item.active {
  color: #00B4B4;
  font-weight: 600;
  background: rgba(0, 180, 180, 0.08);
}
.el-aside.app-aside {
  overflow: visible !important;
  position: relative;
  z-index: 30;
}
</style>
