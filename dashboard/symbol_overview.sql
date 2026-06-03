-- One row per symbol with the headline numbers an analyst would ask for.
-- Backed by gold_symbol_summary (a view) so it stays fresh against
-- gold_ohlcv_daily on every read.

SELECT
    symbol,
    days_observed,
    total_volume,
    total_notional,
    overall_vwap,
    avg_daily_vwap,
    first_trade_at,
    last_trade_at
FROM workspace.default.gold_symbol_summary
ORDER BY total_notional DESC;
