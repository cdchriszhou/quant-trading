const PARAM_LABELS = {
  // 均线/MACD/布林带
  fast_period: '快线周期', slow_period: '慢线周期', signal_period: '信号周期',
  period: '计算周期', std_dev: '标准差倍数',
  // 网格
  grid_levels: '网格层数', grid_spacing_pct: '网格间距(%)', base_price: '基准价格',
  // 定投
  interval_days: '定投间隔(天)', fixed_amount: '定投金额',
  signal_type: '信号类型',
  oversold_threshold: '超卖阈值', overbought_threshold: '超买阈值',
  target_symbols: '目标标的',
  // 龙回头策略
  strong_lookback: '强势回溯天数', limit_up_threshold: '涨停阈值(%)',
  min_limit_ups: '最少涨停次数', breakout_gain_pct: '突破涨幅(%)',
  breakout_high_period: '创新高回溯天数', breakout_vol_ratio: '突破量比',
  ma_short: '短期均线', ma_medium: '中期均线', ma_long: '长期均线', ma_trend: '趋势均线',
  min_pullback_days: '最小回调天数', max_pullback_days: '最大回调天数',
  fib_ratio_strong: '极强股斐波那契位', fib_ratio_normal: '强势股斐波那契位',
  vol_contraction_ratio: '缩量比', max_bearish_body_pct: '最大阴线幅度(%)',
  max_single_drop_pct: '最大单日跌幅(%)', entry_near_ma: '均线支撑买入',
  entry_near_fib: '斐波那契买入', entry_tolerance_pct: '入场容忍度(%)',
  stop_loss_pct: '空间止损(%)', ma_stop_buffer_pct: '均线止损缓冲(%)',
  max_capital_loss_pct: '单笔最大亏损(%)', time_stop_days_1: '时间止损1(天)',
  time_stop_profit_1: '时间止损1盈利(%)', time_stop_days_2: '时间止损2(天)',
  trail_profit_level_1: '移动止盈1(%)', trail_profit_level_2: '移动止盈2(%)',
  top_vol_surge_ratio: '天量标准', top_gain_stall_pct: '放量滞涨阈值(%)',
  top_turnover_rate: '换手率警戒(%)', top_big_drop_pct: '长阴破位跌幅(%)',
  top_deviation_pct: '乖离率警戒(%)',
  // 趋势跟踪
  adx_period: 'ADX周期', adx_threshold: 'ADX阈值',
  atr_period: 'ATR周期', atr_multiplier: 'ATR倍数',
  trailing_stop_pct: '移动止损(%)', volume_confirm_ratio: '成交量确认比',
  // 右侧入场策略
  pullback_near_ma_pct: '回调靠近均线幅度(%)',
  vol_expansion_ratio: '放量比',
  stop_loss_ma_break_pct: '均线止损破位幅度(%)',
  hard_stop_pct: '硬止损(%)',
  ma_slope_flat_threshold: '均线斜率平坦阈值',
  min_daily_amount: '最小日均成交额',
}

export function paramLabel(key) {
  return PARAM_LABELS[key] || key
}
