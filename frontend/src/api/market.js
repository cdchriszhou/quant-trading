import client from './client'

export const marketApi = {
  getOverview() { return client.get('/market/overview') },
  getQuote(symbol) { return client.get('/market/quote', { params: { symbol } }) },
  getKline(symbol, period = '1d', count = 100) {
    return client.get('/market/kline', { params: { symbol, period, count } })
  },
  searchSymbols(query) { return client.get('/market/symbols', { params: { query } }) },
  getTopMovers(count = 10, market = 'all') { return client.get('/market/top-movers', { params: { count, market } }) },
  getSectors(count = 30) { return client.get('/market/sectors', { params: { count } }) },
  getSectorStocks(boardCode, count = 100) { return client.get('/market/sector-stocks', { params: { board_code: boardCode, count } }) },
}
