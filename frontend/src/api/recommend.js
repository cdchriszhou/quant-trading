import client from './client'

export const recommendApi = {
  shortHold(params = {}) {
    return client.get('/recommend/short-hold', {
      params,
      // 扫描多标的 + 可选大模型，默认 15s 不够
      timeout: 120000,
    })
  },
  llmOptions() {
    return client.get('/recommend/llm-options')
  },
}
