import client from './client'

export const authApi = {
  login(data) { return client.post('/auth/login', data) },
  register(data) { return client.post('/auth/register', data) },
}
