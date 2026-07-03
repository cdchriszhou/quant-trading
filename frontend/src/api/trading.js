import client from './client'

export const tradingApi = {
  placeOrder(data) { return client.post('/trading/orders', data) },
  listOrders(status, limit = 50) {
    return client.get('/trading/orders', { params: { status, limit } })
  },
  cancelOrder(id) { return client.post(`/trading/orders/${id}/cancel`) },
  getPositions() { return client.get('/trading/positions') },
  getAccount() { return client.get('/trading/account') },
}
