import client from './client'

export const notificationsApi = {
  /** Get paginated notifications list */
  list(params = {}) {
    return client.get('/notifications', { params })
  },
  /** Get unread count only */
  unreadCount() {
    return client.get('/notifications/unread-count')
  },
  /** Mark notifications as read (pass { ids: [...] } or {} to mark all) */
  markRead(data = {}) {
    return client.put('/notifications/read', data)
  },
}
