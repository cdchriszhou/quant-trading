import client from './client'

export const strategyApi = {
  getTypes() { return client.get('/strategies/types') },
  getDefaultParams(type) { return client.get(`/strategies/default-params/${type}`) },
  list(status) { return client.get('/strategies', { params: { status } }) },
  get(id) { return client.get(`/strategies/${id}`) },
  create(data) { return client.post('/strategies', data) },
  update(id, data) { return client.put(`/strategies/${id}`, data) },
  delete(id) { return client.delete(`/strategies/${id}`) },
  start(id) { return client.post(`/strategies/${id}/start`) },
  stop(id) { return client.post(`/strategies/${id}/stop`) },
}
