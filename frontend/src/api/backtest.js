import client from './client'

export const backtestApi = {
  run(data, config) { return client.post('/backtest/run', data, config) },
  list() { return client.get('/backtest/history') },
}
