import client from './client'

/** Get current market environment status */
export function getEnvStatus() {
  return client.get('/env/status', { timeout: 60000 })
}

/** Get historical env records */
export function getEnvHistory(limit = 60) {
  return client.get('/env/history', { params: { limit }, timeout: 30000 })
}

/** Get avg stock price K-line data */
export function getAvgPriceKline(count = 120) {
  return client.get('/env/avg-price-kline', { params: { count }, timeout: 90000 })
}

/** Get quick avg price snapshot */
export function getAvgPriceSnapshot() {
  return client.get('/env/avg-price-snapshot', { timeout: 60000 })
}
