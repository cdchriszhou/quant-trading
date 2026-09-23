import client from './client'

export const backtestApi = {
  run(data, config) { return client.post('/backtest/run', data, config) },
  optimize(data, config) { return client.post('/backtest/optimize', data, config) },
  list() { return client.get('/backtest/history') },
  get(id) { return client.get(`/backtest/${id}`) },
}
