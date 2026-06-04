# Data dictionary

Column-level documentation for every table in the lakehouse. Read this before writing a query against the Gold tables, or before adding a new column anywhere.

## Sources

| Table | Owner | Source of record | Schema enforced where |
|---|---|---|---|
| Binance Vision daily aggTrades | Binance (external) | `data.binance.vision` HTTPS endpoint | Bronze parser, then Silver type cast |

## Bronze layer

### `bronze/raw/symbol=X/batch_date=Y/*.zip` (ADLS)
Raw zip files as downloaded from Binance Vision. No transformation. Source of record for audit and any future re-processing.

### Bronze Delta table (ADLS) and UC Volume (parquet)
Both layouts hold the same data: the parsed CSV converted to typed columns with audit columns attached.

| Column | Type | Source | Notes |
|---|---|---|---|
| `agg_trade_id` | string | Binance CSV col 1 | Long integer; kept as string in Bronze for fidelity, cast in Silver |
| `price` | string | Binance CSV col 2 | Decimal as text; cast to Decimal(38,8) in Silver |
| `quantity` | string | Binance CSV col 3 | Decimal as text |
| `first_trade_id` | string | Binance CSV col 4 | First underlying trade in the aggregation |
| `last_trade_id` | string | Binance CSV col 5 | Last underlying trade in the aggregation |
| `transact_time` | string | Binance CSV col 6 | Epoch milliseconds as text |
| `is_buyer_maker` | string | Binance CSV col 7 | `"true"` or `"false"` |
| `is_best_match` | string | Binance CSV col 8 | Deprecated by Binance; may be absent in some files |
| `symbol` | string | derived from filename | Hive partition column |
| `batch_date` | string | derived from filename | Hive partition column, ISO yyyy-mm-dd |
| `_source_file_name` | string | audit | Filename as downloaded |
| `_source_file_sha256` | string | audit | SHA-256 hex digest of the zip |
| `_pipeline_run_id` | string | audit | Run id of the Bronze ingester |
| `_ingested_at` | string | audit | UTC ISO timestamp |

## Silver layer

### `workspace.default.silver_agg_trades` (UC managed Delta)
Type-cast, validated, deduplicated.

| Column | Type | Description |
|---|---|---|
| `agg_trade_id` | bigint | Unique within (symbol, batch_date) |
| `price` | decimal(38,8) | Trade price |
| `quantity` | decimal(38,8) | Trade base-asset quantity |
| `first_trade_id` | bigint | First underlying trade |
| `last_trade_id` | bigint | Last underlying trade |
| `transact_time` | timestamp | Trade execution time, UTC |
| `is_buyer_maker` | boolean | true if buyer was the maker side |
| `is_best_match` | boolean | Deprecated; preserved if present |
| `symbol` | string | BTCUSDT \| ETHUSDT \| SOLUSDT |
| `batch_date` | string (yyyy-mm-dd) | UTC date of the source file |
| `is_valid` | boolean | true if `price > 0 AND quantity > 0 AND transact_time IS NOT NULL` |
| `_source_file_name` | string | Carried from Bronze |
| `_source_file_sha256` | string | Carried from Bronze |
| `_pipeline_run_id` | string | Carried from Bronze |
| `_ingested_at` | string | Carried from Bronze |
| `_silver_at` | timestamp | When this row was written to Silver |
| `_silver_run_id` | string | Silver run id |

Natural key for MERGE: `(symbol, batch_date, agg_trade_id)`.

## Gold layer

### `workspace.default.gold_ohlcv_daily` (UC managed Delta, partitioned by symbol)
Daily OHLCV per symbol per UTC trading day.

| Column | Type | Description |
|---|---|---|
| `symbol` | string | |
| `batch_date` | string | UTC date |
| `session_open_at` | timestamp | First trade of the day |
| `session_close_at` | timestamp | Last trade of the day |
| `open_price` | decimal(38,8) | Price of first trade |
| `high_price` | decimal(38,8) | Max price in the day |
| `low_price` | decimal(38,8) | Min price in the day |
| `close_price` | decimal(38,8) | Price of last trade |
| `volume` | decimal(38,8) | Sum of `quantity` |
| `notional` | decimal(38,8) | Sum of `price * quantity` |
| `vwap` | decimal | `notional / volume` (null if volume is zero) |
| `trade_count` | bigint | Number of aggregated trades in the day |
| `_gold_at` | timestamp | When this row was written to Gold |
| `_gold_run_id` | string | dbt `invocation_id` |

Natural key: `(symbol, batch_date)`. Enforced by a singular dbt test.

### `workspace.default.gold_ohlcv_hourly` (UC managed Delta)
Same shape as daily but at hour granularity. Adds `hour_bucket` (timestamp truncated to the hour).

### `workspace.default.gold_symbol_summary` (UC managed Delta view)
Per-symbol rollup over all observed days. Materialised as a view so it is always fresh.

| Column | Type | Description |
|---|---|---|
| `symbol` | string | |
| `days_observed` | bigint | Distinct count of batch_date |
| `total_volume` | decimal(38,8) | |
| `total_notional` | decimal(38,8) | |
| `overall_vwap` | decimal | `total_notional / total_volume` |
| `avg_daily_vwap` | decimal | Mean of per-day VWAP |
| `first_trade_at` | timestamp | Earliest session_open_at across all days |
| `last_trade_at` | timestamp | Latest session_close_at across all days |

## Sensitivity classification

| Column or field | Class | Notes |
|---|---|---|
| All Binance trade fields (price, quantity, ids, timestamps) | PUBLIC | Mandatory public disclosure under Binance Vision |
| `symbol` | PUBLIC | Public ticker |
| Audit columns | INTERNAL | Identifies our pipeline; not PII |
| `_pipeline_run_id`, `_silver_run_id`, `_gold_run_id` | INTERNAL | Run identifiers, no PII |

No column in this lakehouse is classified PII or SENSITIVE. The dataset is public market data by design. The AES encryption utility under `encryption/` is a labelled demonstration only and is never applied to live columns.
