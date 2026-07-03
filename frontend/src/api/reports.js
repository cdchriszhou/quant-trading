import client from './client'

export const reportsApi = {
  getDashboard() { return client.get('/reports/dashboard') },
  getTrades() { return client.get('/reports/trades') },
  getPerformance() { return client.get('/reports/performance') },
  exportTrades() { return client.get('/reports/trades/export') },
}
