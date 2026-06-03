# Dashboard queries

Hand-written SQL queries for the Databricks SQL editor. They cover pipeline health, data freshness, and per-symbol analytics on the Gold tables.

These can be:
- Pasted directly into the Databricks SQL editor for one-off inspection.
- Saved as Lakeview Dashboard widgets (Databricks Free Edition supports Lakeview).
- Pointed at by Evidence.dev or Streamlit if you later want a static or web dashboard published from this repo.

The queries are intentionally plain SQL, no dbt macros, so they work even if you do not have the dbt project running.

## What each query is for

| File | Question it answers |
|---|---|
| `data_freshness.sql` | When was the most recent pipeline run, per symbol? Are we behind? |
| `symbol_overview.sql` | High-level rollup per symbol (volume, days observed, VWAP) |
| `daily_volume_trend.sql` | Day-over-day total volume per symbol |
| `intraday_price_path.sql` | Hourly OHLCV for one symbol on one day |
| `dq_summary.sql` | Row counts and validity rates across Silver |

## To build a dashboard from these

1. Open Databricks workspace → SQL → Dashboards (Lakeview).
2. Create a new dashboard.
3. For each `.sql` file in this folder, paste it as a dataset, give it a name, then drop chart widgets on top of it.
4. Save and share.

Dashboards built this way are queryable, governed by Unity Catalog, and free on Free Edition.
