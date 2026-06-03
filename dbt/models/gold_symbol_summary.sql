{{
    config(materialized = 'view')
}}

-- Per-symbol headline metrics rolled up across every day we have processed.
-- Materialised as a view so it is always fresh against the underlying daily
-- table and costs zero storage.

select
    symbol,
    count(distinct batch_date)                                  as days_observed,
    sum(volume)                                                 as total_volume,
    sum(notional)                                               as total_notional,
    case when sum(volume) > 0 then sum(notional) / sum(volume) end as overall_vwap,
    avg(case when volume > 0 then notional / volume end)        as avg_daily_vwap,
    min(session_open_at)                                        as first_trade_at,
    max(session_close_at)                                       as last_trade_at
from {{ ref('gold_ohlcv_daily') }}
group by symbol
