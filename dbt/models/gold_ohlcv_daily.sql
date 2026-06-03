{{
    config(
        materialized = 'table',
        partition_by = ['symbol']
    )
}}

-- Daily OHLCV with VWAP, total volume, total notional, and trade count
-- per (symbol, batch_date). The session_open_at / session_close_at columns
-- preserve the actual first/last trade timestamps in the UTC day so an
-- analyst can see whether the session was incomplete.

with trades as (

    select *
    from {{ source('silver', 'silver_agg_trades') }}
    where is_valid = true

),

aggregated as (

    select
        symbol,
        batch_date,
        min(transact_time)                                                       as session_open_at,
        max(transact_time)                                                       as session_close_at,
        min_by(price, transact_time)                                             as open_price,
        max(price)                                                               as high_price,
        min(price)                                                               as low_price,
        max_by(price, transact_time)                                             as close_price,
        sum(quantity)                                                            as volume,
        sum(cast(price as decimal(38, 8)) * cast(quantity as decimal(38, 8)))    as notional,
        count(*)                                                                 as trade_count
    from trades
    group by symbol, batch_date

)

select
    symbol,
    batch_date,
    session_open_at,
    session_close_at,
    open_price,
    high_price,
    low_price,
    close_price,
    volume,
    notional,
    case when volume > 0 then notional / volume end as vwap,
    trade_count,
    current_timestamp()       as _gold_at,
    '{{ invocation_id }}'      as _gold_run_id
from aggregated
