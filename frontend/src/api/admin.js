import client from './client'

export const adminApi = {
  listUsers() { return client.get('/admin/users') },
  updateUser(id, data) { return client.put(`/admin/users/${id}`, data) },
  getLogs() { return client.get('/admin/logs') },
}
