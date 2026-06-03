-- Row counts and validity rates per symbol per batch_date.
-- Shows the DQ posture of Silver: how many rows landed, how many failed
-- the is_valid check, and what fraction were rejected.

SELECT
    symbol,
    batch_date,
    COUNT(*)                                                         AS rows_total,
    SUM(CAST(is_valid AS INT))                                       AS rows_valid,
    COUNT(*) - SUM(CAST(is_valid AS INT))                            AS rows_invalid,
    ROUND(
        100.0 * (COUNT(*) - SUM(CAST(is_valid AS INT))) / COUNT(*),
        2
    )                                                                AS pct_invalid
FROM workspace.default.silver_agg_trades
GROUP BY symbol, batch_date
ORDER BY symbol, batch_date DESC;
