import { createRouter, createWebHashHistory } from 'vue-router'

/** Eager menu routes avoid blank pages when a lazy chunk fails to load in prod CDN/cache skew. */
import MainLayout from '@/layouts/MainLayout.vue'
import Dashboard from '@/views/dashboard/Index.vue'
import Market from '@/views/market/Index.vue'
import StrategyList from '@/views/strategy/List.vue'
import StrategyCreate from '@/views/strategy/Create.vue'
import TradingIndex from '@/views/trading/Index.vue'
import Recommend from '@/views/recommend/Index.vue'
import Orders from '@/views/trading/Orders.vue'
import Positions from '@/views/trading/Positions.vue'
import Backtest from '@/views/strategy/Backtest.vue'
import RiskControl from '@/views/risk/Index.vue'
import Reports from '@/views/reports/Index.vue'
import Notifications from '@/views/system/Notifications.vue'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/user/Login.vue'),
    meta: { requiresAuth: false, title: '登录' },
  },
  {
    path: '/',
    component: MainLayout,
    meta: { requiresAuth: true },
    redirect: '/dashboard',
    children: [
      { path: 'dashboard', name: 'Dashboard', component: Dashboard, meta: { title: '仪表盘' } },
      { path: 'market', name: 'Market', component: Market, meta: { title: '实时行情', parent: '行情分析' } },
      { path: 'strategies', name: 'Strategies', component: StrategyList, meta: { title: '策略管理', parent: '量化策略' } },
      { path: 'strategies/create', name: 'CreateStrategy', component: StrategyCreate, meta: { title: '创建策略', parent: '量化策略' } },
      { path: 'strategies/:id', name: 'StrategyDetail', component: () => import('@/views/strategy/Detail.vue'), meta: { title: '策略详情', parent: '量化策略' } },
      { path: 'trading', name: 'Trading', component: TradingIndex, meta: { title: '快速交易', parent: '交易管理' } },
      { path: 'recommend', name: 'Recommend', component: Recommend, meta: { title: '资金匹配推荐', parent: '交易管理' } },
      { path: 'trading/orders', name: 'Orders', component: Orders, meta: { title: '订单查询', parent: '交易管理' } },
      { path: 'trading/positions', name: 'Positions', component: Positions, meta: { title: '持仓查询', parent: '交易管理' } },
      { path: 'backtest', name: 'Backtest', component: Backtest, meta: { title: '策略回测', parent: '量化策略' } },
      { path: 'risk', name: 'RiskControl', component: RiskControl, meta: { title: '风险控制' } },
      { path: 'reports', name: 'Reports', component: Reports, meta: { title: '数据报表' } },
      { path: 'notifications', name: 'Notifications', component: Notifications, meta: { title: '全部消息' } },
      { path: 'admin/users', name: 'AdminUsers', component: () => import('@/views/system/Users.vue'), meta: { title: '用户管理', parent: '系统管理', role: 'admin' } },
      { path: 'admin/broker', name: 'AdminBroker', component: () => import('@/views/system/Broker.vue'), meta: { title: '实盘接入', parent: '系统管理', role: 'admin' } },
      { path: 'admin/llm', name: 'AdminLlm', component: () => import('@/views/system/Llm.vue'), meta: { title: '大模型接入', parent: '系统管理', role: 'admin' } },
      { path: 'admin/logs', name: 'AdminLogs', component: () => import('@/views/system/Logs.vue'), meta: { title: '操作日志', parent: '系统管理', role: 'admin' } },
    ],
  },
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
})

router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('token')
  let user = {}
  try { user = JSON.parse(localStorage.getItem('user') || '{}') } catch { user = {} }

  if (to.meta.requiresAuth && !token) {
    next('/login')
  } else if (to.path === '/login' && token) {
    next('/dashboard')
  } else if (to.meta.role && user.role !== to.meta.role) {
    next('/dashboard')
  } else {
    next()
  }
})

export default router
