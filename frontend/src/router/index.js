import { createRouter, createWebHashHistory } from 'vue-router'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/user/Login.vue'),
    meta: { requiresAuth: false },
  },
  {
    path: '/',
    component: () => import('@/layouts/MainLayout.vue'),
    meta: { requiresAuth: true },
    redirect: '/dashboard',
    children: [
      { path: 'dashboard', name: 'Dashboard', component: () => import('@/views/dashboard/Index.vue') },
      { path: 'market', name: 'Market', component: () => import('@/views/market/Index.vue') },
      { path: 'strategies', name: 'Strategies', component: () => import('@/views/strategy/List.vue') },
      { path: 'strategies/create', name: 'CreateStrategy', component: () => import('@/views/strategy/Create.vue') },
      { path: 'strategies/:id', name: 'StrategyDetail', component: () => import('@/views/strategy/Detail.vue') },
      { path: 'trading', name: 'Trading', component: () => import('@/views/trading/Index.vue') },
      { path: 'trading/orders', name: 'Orders', component: () => import('@/views/trading/Orders.vue') },
      { path: 'trading/positions', name: 'Positions', component: () => import('@/views/trading/Positions.vue') },
      { path: 'backtest', name: 'Backtest', component: () => import('@/views/strategy/Backtest.vue') },
      { path: 'risk', name: 'RiskControl', component: () => import('@/views/risk/Index.vue') },
      { path: 'reports', name: 'Reports', component: () => import('@/views/reports/Index.vue') },
      { path: 'admin/users', name: 'AdminUsers', component: () => import('@/views/system/Users.vue'), meta: { role: 'admin' } },
      { path: 'admin/logs', name: 'AdminLogs', component: () => import('@/views/system/Logs.vue'), meta: { role: 'admin' } },
    ],
  },
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
})

router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('token')
  const user = JSON.parse(localStorage.getItem('user') || '{}')

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
