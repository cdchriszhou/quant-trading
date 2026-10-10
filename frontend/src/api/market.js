import client from './client'

export const marketApi = {
  getQuote(symbol) { return client.get('/market/quote', { params: { symbol } }) },
  getKline(symbol, period = '1d', count = 100) {
    return client.get('/market/kline', { params: { symbol, period, count } })
  },
  searchSymbols(query) { return client.get('/market/symbols', { params: { query } }) },
  getTopMovers(count = 10, market = 'all') { return client.get('/market/top-movers', { params: { count, market } }) },
  getSectors(count = 30) {
    return client.get('/market/sectors', { params: { count }, timeout: 60000 })
  },
  getSectorStocks(boardCode, count = 100) {
    return client.get('/market/sector-stocks', {
      params: { board_code: boardCode, count },
      timeout: 60000,
    })
  },
  getStockInsight(symbol) {
    return client.get('/market/stock-insight', {
      params: { symbol },
      timeout: 30000,
    })
  },
}
