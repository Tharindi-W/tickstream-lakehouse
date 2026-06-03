-- Per-symbol daily volume time series, ready to plot as a line chart
-- with batch_date on the x axis, volume on the y axis, and symbol as
-- the series breakdown.

SELECT
    symbol,
    batch_date,
    volume,
    notional,
    vwap,
    trade_count
FROM workspace.default.gold_ohlcv_daily
ORDER BY symbol, batch_date;
