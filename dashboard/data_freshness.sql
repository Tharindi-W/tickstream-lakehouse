-- How fresh is each symbol in Silver?
-- Answers: "as of right now, what is the most recent trade timestamp we
-- have for each symbol, and how many hours behind is it?"

SELECT
    symbol,
    MAX(transact_time)                                            AS latest_trade_at,
    COUNT(DISTINCT batch_date)                                    AS days_observed,
    DATEDIFF(HOUR, MAX(transact_time), CURRENT_TIMESTAMP())       AS hours_behind_now,
    MAX(_silver_at)                                               AS latest_silver_load_at
FROM workspace.default.silver_agg_trades
WHERE is_valid = TRUE
GROUP BY symbol
ORDER BY hours_behind_now ASC;
