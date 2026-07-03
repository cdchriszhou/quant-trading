import client from './client'

export const backtestApi = {
  run(data) { return client.post('/backtest/run', data) },
  optimize(data) { return client.post('/backtest/optimize', data) },
  list() { return client.get('/backtest/history') },
  get(id) { return client.get(`/backtest/${id}`) },
}
