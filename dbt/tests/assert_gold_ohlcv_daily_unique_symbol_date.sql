-- Singular dbt test: each (symbol, batch_date) must appear at most once.
-- Returning any rows means the test fails. dbt-utils.unique_combination_of_columns
-- would do this more elegantly but I want to keep dependencies to zero
-- in the first dbt iteration.

select
    symbol,
    batch_date,
    count(*) as n
from {{ ref('gold_ohlcv_daily') }}
group by symbol, batch_date
having count(*) > 1
