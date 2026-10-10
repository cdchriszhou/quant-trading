import client from './client'

export const adminApi = {
  listUsers() { return client.get('/admin/users') },
  updateUser(id, data) { return client.put(`/admin/users/${id}`, data) },
  resetUserTrading(id) { return client.post(`/admin/users/${id}/reset-trading`) },
  reset() { return client.post('/admin/reset') },
  getLogs() { return client.get('/admin/logs') },
  getBrokerConfig() { return client.get('/admin/broker-config') },
  updateBrokerConfig(data) { return client.put('/admin/broker-config', data) },
  testBrokerConnection() { return client.post('/admin/broker-config/test') },
  getLlmConfig() { return client.get('/admin/llm-config') },
  updateLlmConfig(data) { return client.put('/admin/llm-config', data) },
  testLlmConnection(data) { return client.post('/admin/llm-config/test', data) },
}
