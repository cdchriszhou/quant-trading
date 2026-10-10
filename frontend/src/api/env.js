import client from './client'

/** Get current market environment status */
export function getEnvStatus() {
  return client.get('/env/status', { timeout: 60000 })
}
