-- Weekly maintenance for the UC-managed Delta tables.
-- Runs OPTIMIZE (with ZORDER on the most queried columns) then VACUUM
-- with the project's retention window.
--
-- Executed by .github/workflows/maintenance-weekly.yml against the
-- workspace's SQL warehouse.

-- Silver: ZORDER on the natural-key columns analysts filter by.
OPTIMIZE workspace.default.silver_agg_trades
ZORDER BY (transact_time, agg_trade_id);

-- Gold daily: small table, OPTIMIZE compacts the partition files.
OPTIMIZE workspace.default.gold_ohlcv_daily;

-- Gold hourly: ZORDER on hour_bucket so chart queries are fast.
OPTIMIZE workspace.default.gold_ohlcv_hourly
ZORDER BY (hour_bucket);

-- VACUUM with 30-day retention (the time travel window).
-- Below 168 hours (7 days) you would need to disable a safety flag;
-- 30 days is well above that floor.
VACUUM workspace.default.silver_agg_trades  RETAIN 720 HOURS;
VACUUM workspace.default.gold_ohlcv_daily   RETAIN 720 HOURS;
VACUUM workspace.default.gold_ohlcv_hourly  RETAIN 720 HOURS;
