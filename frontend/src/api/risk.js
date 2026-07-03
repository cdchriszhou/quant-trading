import client from './client'

export const riskApi = {
  listRules() { return client.get('/risk/rules') },
  createRule(data) { return client.post('/risk/rules', data) },
  updateRule(id, data) { return client.put(`/risk/rules/${id}`, data) },
  deleteRule(id) { return client.delete(`/risk/rules/${id}`) },
  check(data) { return client.post('/risk/check', data) },
}
