/** Shared Chinese labels for enums shown in tables / details. */

export const STRATEGY_TYPE_LABELS = {
  ma: '均线策略',
  macd: 'MACD策略',
  bollinger: '布林带策略',
  grid: '网格交易',
  dca: '定投策略',
  dragon_pullback: '龙回头策略',
  trend_following: '趋势跟踪策略',
  right_side_entry: '右侧入场策略',
}

export const TRADE_MODE_LABELS = {
  paper: '模拟',
  live: '实盘',
}

export const ORDER_TYPE_LABELS = {
  market: '市价',
  limit: '限价',
}

export const ORDER_STATUS_LABELS = {
  pending: '待成交',
  submitted: '已提交',
  filled: '已成交',
  cancelled: '已取消',
  rejected: '已拒绝',
}

export const STRATEGY_STATUS_LABELS = {
  running: '运行中',
  stopped: '已停止',
  paused: '已暂停',
}

export const SIDE_LABELS = {
  buy: '买入',
  sell: '卖出',
}

export const TIME_FRAME_LABELS = {
  '1d': '日线',
  '1w': '周线',
  '60m': '60分钟',
  '30m': '30分钟',
  '15m': '15分钟',
  '5m': '5分钟',
}

export function strategyTypeLabel(t) {
  return STRATEGY_TYPE_LABELS[t] || t || '—'
}

export function tradeModeLabel(m) {
  return TRADE_MODE_LABELS[m] || m || '—'
}

export function orderTypeLabel(t) {
  return ORDER_TYPE_LABELS[t] || t || '—'
}

export function orderStatusLabel(s) {
  return ORDER_STATUS_LABELS[s] || s || '—'
}

export function strategyStatusLabel(s) {
  return STRATEGY_STATUS_LABELS[s] || s || '—'
}

export function sideLabel(s) {
  return SIDE_LABELS[s] || s || '—'
}

export function timeFrameLabel(t) {
  return TIME_FRAME_LABELS[t] || t || '—'
}
