-- Hourly OHLCV for one symbol on one day. Set the parameters at the top
-- of the SQL editor; defaults below produce a useful first result on the
-- most recently ingested batch.

WITH params AS (
    SELECT
        'BTCUSDT'                                                       AS symbol,
        (SELECT MAX(batch_date) FROM workspace.default.gold_ohlcv_daily) AS batch_date
)
SELECT
    h.symbol,
    h.batch_date,
    h.hour_bucket,
    h.open_price,
    h.high_price,
    h.low_price,
    h.close_price,
    h.volume,
    h.vwap,
    h.trade_count
FROM workspace.default.gold_ohlcv_hourly h
JOIN params p
    ON h.symbol     = p.symbol
   AND h.batch_date = p.batch_date
ORDER BY h.hour_bucket;
