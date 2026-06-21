import client from './client'

export const marketApi = {
  getOverview() { return client.get('/market/overview') },
  getQuote(symbol) { return client.get('/market/quote', { params: { symbol } }) },
  getKline(symbol, period = '1d', count = 100) {
    return client.get('/market/kline', { params: { symbol, period, count } })
  },
  searchSymbols(query) { return client.get('/market/symbols', { params: { query } }) },
}
