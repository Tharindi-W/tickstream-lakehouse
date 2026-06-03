{{
    config(
        materialized = 'table',
        partition_by = ['symbol', 'batch_date']
    )
}}

-- Hourly OHLCV per symbol. Useful for intraday charts and short-window
-- volatility computation in downstream notebooks or dashboards.

with trades as (

    select
        symbol,
        batch_date,
        date_trunc('HOUR', transact_time) as hour_bucket,
        transact_time,
        price,
        quantity
    from {{ source('silver', 'silver_agg_trades') }}
    where is_valid = true

)

select
    symbol,
    batch_date,
    hour_bucket,
    min_by(price, transact_time)                                              as open_price,
    max(price)                                                                as high_price,
    min(price)                                                                as low_price,
    max_by(price, transact_time)                                              as close_price,
    sum(quantity)                                                             as volume,
    sum(cast(price as decimal(38, 8)) * cast(quantity as decimal(38, 8)))     as notional,
    case
        when sum(quantity) > 0
        then sum(cast(price as decimal(38, 8)) * cast(quantity as decimal(38, 8))) / sum(quantity)
    end                                                                       as vwap,
    count(*)                                                                  as trade_count,
    current_timestamp()                                                       as _gold_at
from trades
group by symbol, batch_date, hour_bucket
