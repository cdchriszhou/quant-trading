import client from './client'

export const authApi = {
  login(data) { return client.post('/auth/login', data) },
  register(data) { return client.post('/auth/register', data) },
  getProfile() { return client.get('/auth/profile') },
  updateProfile(data) { return client.put('/auth/profile', data) },
}
