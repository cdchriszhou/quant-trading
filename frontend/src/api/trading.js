import client from './client'

export const tradingApi = {
  placeOrder(data) { return client.post('/trading/orders', data) },
  listOrders(status, limit = 50) {
    return client.get('/trading/orders', { params: { status, limit } })
  },
  cancelOrder(id) { return client.post(`/trading/orders/${id}/cancel`) },
  getPositions() { return client.get('/trading/positions') },
  getAccount() { return client.get('/trading/account') },
  getEquityCurve() { return client.get('/trading/equity-curve') },
  getAccountMode() { return client.get('/trading/account-mode') },
  setAccountMode(mode) { return client.put('/trading/account-mode', { mode }) },
  setSimulatedCash(initial_cash) { return client.put('/trading/simulated-cash', { initial_cash }) },
  feePreview(side, price, quantity) {
    return client.get('/trading/fee-preview', { params: { side, price, quantity } })
  },
}
