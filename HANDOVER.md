# Project Handover Log

This document is the operational and architectural log of the project. It is written in plain English so any future maintainer (human or AI agent) can take over from this document alone, with no tribal knowledge required.

## Current owner

**Tharindi-W** (https://github.com/Tharindi-W)

## Scope statement

This is a portfolio project demonstrating enterprise-grade data engineering on a $0 stack. Free tier services are used throughout. Where a paid enterprise tool would normally be used (Databricks Premium with Unity Catalog, Microsoft Fabric, Snowflake), the open source or free equivalent is used and the mapping to its paid counterpart is documented in this file.

The data is real, public, and free: crypto tick data from `data.binance.vision`. There is no synthetic data, no toy data, no paywall, no rate-limited API.

## Design philosophy

1. **Everything in GitHub.** Code, configuration, workflow definitions, dashboards-as-code, governance records, handover log. The repository is the system.
2. **Plain English everywhere.** Logs, this file, decision records, alert messages. The next person picking this up should not need to read a single Spark stack trace to understand what is happening.
3. **No misapplied security theatre.** Encryption and hashing are used where they add real value (file integrity, secret storage). They are not sprinkled on public data fields just to look professional. The AES utility lives in `encryption/` as a labelled demo on a synthetic PII column, so the skill is on display without the misapplication.
4. **Honest framing.** Where a free tier choice forces a compromise, the compromise is documented here, not hidden.
5. **Idempotency by default.** Every stage can be re-run safely. Delta `MERGE` is the primary tool for this.
6. **Plan to hand it off from Day 1.** This document is updated as decisions are made, not at the end.

## Decision log

### 2026-06-03 — Project initialised

- Repository created with empty scaffold: README, HANDOVER, LEARNING, gitignore, config stub
- Owner: Tharindi-W
- Stack selected: GitHub Actions, Databricks Free Edition, Azure ADLS Gen2, Infisical vault, Soda Core, dbt-spark, Evidence.dev, Grafana Cloud, Discord webhooks
- Data source chosen: Binance Vision (`data.binance.vision`), no auth required, free forever, multi-GB per day across the symbols below
- Symbols for initial scope: BTCUSDT, ETHUSDT, SOLUSDT
- Data type: daily `aggTrades` files (aggregated trade ticks)
- Schedule: hourly during Week 1, daily thereafter (driven by GitHub Actions cron)
- Compute decision: Databricks Free Edition over the retired Community Edition. Free Edition has a working Jobs API which the orchestration depends on.
- Storage decision: Azure ADLS Gen2 over Cloudflare R2. Reason: Azure on the resume matches the owner's stated career direction. Trade-off: free tier is 12 months only. Mitigation: keep stored data small (raw zips are deleted after Bronze land; only Delta tables persist), and document the migration path to R2 if cost ever becomes an issue.
- Vault decision: Infisical (open source) over GitHub Secrets only. Reason: real vault semantics for the project narrative. GitHub Secrets is still used to hold a single Infisical machine token, which fetches all other secrets at workflow runtime.
- Alert channel: Discord webhook (simpler than Slack for personal use, durable, free).
- Encryption: applied only to file integrity (SHA-256). The AES utility is included as a labelled PII demo, not used on tick data fields. Rationale: Binance tick data is fully public; encrypting it would be theatre and would break joins.

## Mapping of original requirements to current implementation

| Requirement | Implementation |
|---|---|
| 1. Everything in GitHub | Repo holds code, configs, YAML, dashboards-as-code, governance docs, logs |
| 2. Hourly ingestion, no bulk push | GitHub Actions cron `0 * * * *` plus `workflow_dispatch` |
| 3. Secrets in a vault | Infisical, fetched at workflow runtime via a single GitHub Secret bootstrap token |
| 4. Plain-English handover | This file |
| 5. Per-run log with 50-day rotation | `logs/runs/*.log` plus `delta.pipeline_run_log` table; rotation script in `maintenance/` |
| 6. DQ threshold alert | Soda Core suite, alert if rejection rate above 5% (configurable) |
| 7. Fault tolerance | Retry decorator with backoff, PySpark `badRecordsPath`, Delta `MERGE`, partial-success status |
| 8. Audit columns | Each layer adds its own `_at`, `_run_id`, `_source_hash`, `_batch_window` |
| 9. Missing source file alert | Separate Stage 0 alert, fires before any data processing |
| 10. Encryption and hashing | SHA-256 file fingerprints used. AES is a labelled demo only. |
| 11. RBAC and dashboard | Role matrix in `governance/`, TBLPROPERTIES per table, Evidence.dev for data, Grafana Cloud for ops |
| 12. Time-intelligent archival | ADLS Gen2 lifecycle policy: Hot 0-2y, Cool 2-5y, Archive 5y+ |
| 13. Other enterprise concerns | dbt tests, OpenLineage to Marquez, data contracts as Pydantic models, PR-gated CI, pre-commit, backfill runbook, SLO, schema evolution policy, DR note, incident runbook |

### 2026-06-03 — Phase 4 done (Gold dbt)

Three Gold models materialised in Databricks UC, all dbt tests pass.

- `workspace.default.gold_ohlcv_daily` (Delta table, partitioned by `symbol`): daily OHLCV per `(symbol, batch_date)` with VWAP, total volume, total notional, trade count, session open/close timestamps. Uses `min_by(price, transact_time)` and `max_by(price, transact_time)` to capture true open and close prices.
- `workspace.default.gold_ohlcv_hourly` (Delta table, partitioned by `(symbol, batch_date)`): hourly OHLCV bucketed by `date_trunc('HOUR', transact_time)`.
- `workspace.default.gold_symbol_summary` (Delta view over the daily table): per-symbol rollup of days observed, total volume, total notional, overall VWAP, average daily VWAP, first and last seen trade timestamps.

dbt build summary: 2 table models, 25 data tests, 1 view model, 39.02 seconds wall clock. PASS=28 ERROR=0.

Tests in place:
- Source tests on `silver_agg_trades`: `not_null` on `symbol`, `agg_trade_id`, `batch_date`, `is_valid`. `accepted_values` on `symbol`.
- Schema tests on each Gold model: `not_null` on every analytical column (open/high/low/close/volume/notional/trade_count). `accepted_values` on `symbol`. `unique` on `symbol` in the summary view.
- Singular test: each `(symbol, batch_date)` must appear at most once in `gold_ohlcv_daily`.

Orchestration:
- `.github/workflows/gold-dbt.yml` discovers a SQL warehouse via `/api/2.0/sql/warehouses`, starts it if STOPPED, polls until RUNNING, then runs `dbt debug` followed by `dbt build`. Reports per-model `rows_affected` via ntfy on success.
- dbt profile reads `DATABRICKS_HOST_BARE`, `DATABRICKS_HTTP_PATH`, `DATABRICKS_TOKEN` from env. All three are populated at runtime by the same Infisical bootstrap chain that Bronze and Silver use.

Known deprecation warnings:
- `MissingArgumentsPropertyInGenericTestDeprecation: 3 occurrences` in dbt 1.10+ for the way we declare `accepted_values` tests. Cosmetic only, runs pass clean. Tracked for a follow-up commit to migrate the test syntax.

### 2026-06-03 — Phase 3 done (Path B)

End-to-end Silver pipeline works. Concrete state after this phase:

- **UC Volume**: `workspace.default.tickstream_bronze`, MANAGED, populated with three parquet files per batch (one per symbol) at `symbol=X/batch_date=YYYY-MM-DD/agg_trades.parquet`. Spark partition discovery picks up the partition columns from the directory layout.
- **UC managed Delta table**: `workspace.default.silver_agg_trades`, partitioned by `(symbol, batch_date)`, written via Delta `MERGE` on natural key for idempotency.
- **First successful Silver run**: 3,277,567 Bronze rows in scope, 3,277,567 Silver rows written, 0 duplicates dropped (clean first-time MERGE). 40 seconds of Databricks Free Edition Serverless Spark time.
- **Governance TBLPROPERTIES**: `domain`, `data_source`, `contains_pii`, `regulatory_basis`, `refresh_cadence`, `last_silver_run` all set on the Silver table. `owner` is auto-managed by UC.
- **No storage credentials in Databricks**: Silver does not touch ADLS at all. Reads from UC Volume, writes to UC managed Delta. The shared key for ADLS lives only in Infisical and is used only by the GitHub Actions runner during Bronze ingestion.

Vault chain end-to-end:
GitHub Actions cron → GitHub Secrets (3 bootstrap secrets) → Infisical (5 operational secrets) → ADLS (via shared key in Python) AND Databricks Files API (via PAT) → UC Volume → Databricks Serverless Spark → UC managed Silver Delta table.

The complete dependency tree is described in `LEARNING.md` Phase 3 section.

### 2026-06-03 — Path C dead end documented, Path B chosen

We attempted Phase 3 Path C (Unity Catalog External Location backed by an Azure Managed Identity) and discovered it is architecturally impossible on Databricks Free Edition.

**The fact.** Free Edition workspaces are hosted by Databricks themselves under their own Azure account (account id `c3c1bd8f-49c3-408d-8f3e-a226329652d4`, observed in the API error). Our Azure Access Connector and its managed identity live in our own Azure subscription. Azure managed identities cannot cross Azure AD tenants. Therefore Databricks compute cannot resolve a managed identity that we own.

**Symptom.** `BAD_REQUEST: Azure Managed Identity Credential with Access Connector Id ... could not be found.` on `POST /api/2.1/unity-catalog/storage-credentials`.

**What we built before discovering it (kept for posterity, no cost):**
- Azure Access Connector `tickstream-access-connector` in `tickstream-rg`, system-assigned managed identity, principal id `1cbc4ba9-d6dc-43e2-b3a2-df99b667436d`.
- Storage Blob Data Contributor role assigned to that principal on `tickstreamlakecbe5`.
- These resources are free and will become useful the day this project ever migrates to paid Azure Databricks (where the workspace lives in the same tenant as the connector).

**Workflow kept as evidence.** `.github/workflows/setup-uc-external-locations.yml` is left in place. It is the actual API call shape needed for Path C. Anyone reproducing this on paid Azure Databricks should be able to run it and have it succeed.

**Decision: Path B (UC Volume copy).** Bronze stays in ADLS exactly as it is, AND uploads a parquet copy of each batch to a UC managed Volume (`workspace.default.tickstream_bronze`) via Databricks Files API. Volumes live in Databricks-managed storage, no cross-tenant identity needed. Silver runs on Free Edition Serverless, reads from the Volume, writes to a UC managed Delta table `workspace.default.silver_agg_trades`. ADLS remains the source of record. The Volume is the Spark-readable copy.

### 2026-06-03 — Phase 3 planned

Silver transform on Databricks Free Edition. Decisions locked here:

- **Compute**: Databricks Free Edition (replaced Community Edition; has working Jobs REST API).
- **Auth from GitHub Actions to Databricks**: bearer token (`DATABRICKS_TOKEN`) sourced from Infisical, never on a command line.
- **Auth from Databricks to ADLS**: storage account key passed as a Databricks Job parameter for first iteration. Trade-off documented: visible in Job run history. Follow-up will replace with Databricks Secret Scope or Azure AD service principal.
- **Transform language**: PySpark notebook source held in `pipeline/silver/transform_silver.py` in git, deployed to Databricks workspace via Workspace API on each push. The source of truth is git, never the workspace.
- **Idempotency**: Delta `MERGE` keyed on `(symbol, batch_date, agg_trade_id)`. Re-runs do not duplicate rows. Replaces the Bronze partition-append pattern which only works because the hash check prevents re-ingest.
- **Schema**: enforced StructType at read, explicit type casts in transform, schema-on-write enforcement at the target Delta table.
- **DQ**: Soda Core declarative checks at `dq/soda_silver.yml`, run from a follow-up GitHub Actions step after the Databricks job succeeds. Reads Silver via deltalake-py (not Spark) since the runner is small. Alert fires if rejection rate above 5%.
- **Bad records**: `badRecordsPath` set to `az://bad-records/silver/{run_id}/`. Single malformed rows do not kill the job.
- **Orchestration**: `.github/workflows/ingest-silver-after-bronze.yml`. Triggered by `workflow_run` event when `ingest-bronze-hourly` completes successfully. Calls Databricks Jobs API `run-now` with `batch_date` and storage credential parameters.
- **Governance**: Silver Delta gets TBLPROPERTIES (owner=Tharindi-W, domain=crypto_markets, data_source=binance_vision, contains_pii=false, regulatory_basis=public_market_data, refresh_cadence=hourly_dev_then_daily).

### 2026-06-03 — Phase 2 done

Second Bronze run (after parser fix + key rotation + Infisical update) ingested all three symbols cleanly in 46 seconds of Python time (1m21s total wall clock including CLI install and dependency setup).

Concrete state:

- `az://bronze/raw/symbol=BTCUSDT/batch_date=2026-06-02/...zip` plus same for ETH and SOL.
- `az://bronze/delta/bronze_agg_trades/` Delta table partitioned by `(symbol, batch_date)`, with 8 canonical aggTrades columns plus six audit columns.
- Row counts on this batch: BTCUSDT 1,677,042, ETHUSDT 1,380,545, SOLUSDT 219,980. Total ~3.28M rows for one trading day.
- `state/last_seen_hashes.json` has all three symbols' SHA-256 fingerprints. Next hourly run will skip all three with a "Hash unchanged" log entry until tomorrow's file is published.
- `logs/runs/` has two files: the failed first run (`20260603_064326_367740a3.log`, status SUCCESS at workflow level but PARTIAL at app level since 2 of 3 symbols errored) and the corrected run (`20260603_074336_e000322e.log`, full SUCCESS).
- Hourly cron is live. Manual `workflow_dispatch` always available.

What this proves end to end:

1. GitHub Actions cron triggers Python ingestion.
2. Bootstrap secrets (3 in GitHub) authenticate to Infisical.
3. Infisical hands back the operational secrets (Azure key, ntfy URL) for the duration of the job only.
4. Python downloads from a public source, hashes, dedups against committed state, uploads raw to ADLS, parses CSV, writes Delta with audit columns.
5. Plain-English run log auto-commits back to the repo so the audit trail lives next to the code.
6. ntfy alerts fire on missing source files or transient errors (not exercised this run because everything worked, but the code paths are in place).

### 2026-06-03 — Phase 2 first run + security incident + parser fix

**What we tried.** First Bronze ingestion run with the three configured symbols. The workflow itself returned green at the GitHub Actions level because BTCUSDT succeeded. ETHUSDT and SOLUSDT failed with `deltalake.SchemaMismatchError: Field <numeric_id> not found in schema`.

**Root cause of the data error.** Binance Vision is inconsistent across symbols. BTCUSDT's daily aggTrades CSV ships with a header row (`agg_trade_id,price,...`), but ETHUSDT and SOLUSDT do not. pandas with default `header=0` inferred the first numeric data row as column names for those two, producing schemas like `1999085122,...` that did not match the Delta table created by BTCUSDT. Fixed in `pipeline/bronze/land_to_bronze.py::_parse_csv_from_zip`: detect header by checking if the first cell parses as an integer, always normalise to canonical 8-column schema regardless of source format.

**Security incident — Azure storage key leaked twice during cleanup.**

1. First leak: while trying to wipe the half-written bronze container with `az storage blob delete-batch ... --account-key <value>`, a subsequent `az storage blob list --query "length(@)" -o tsv` triggered an internal az exception that dumped `sys.argv` (including the `--account-key=<value>` argument) to its stdout. The captured stdout was then `Write-Output`-ed by the wrapping PowerShell command, putting the live key into the conversation transcript.
2. Second leak: same mechanism after the first rotation, because I re-used the same `--query length(@)` pattern with the newly-rotated key.

Both leaks were responded to within seconds:

- Rotated the storage account keys via `az storage account keys renew` (management plane operation, AAD-authenticated, no `--account-key` argument so no leak path).
- Bronze container wiped fresh with the third-generation key, this time using `azure-storage-file-datalake` Python SDK because ADLS Gen2's hierarchical namespace rejects non-recursive blob deletes on directories.

**Permanent fix to prevent recurrence.**

- Never pass `--account-key` as a CLI argument again. Use the `AZURE_STORAGE_KEY` environment variable so the key is never on a command line and so never appears in any `sys.argv` dump from a CLI subcommand.
- For local admin tasks, prefer the Python SDK over `az` CLI on Windows because PowerShell 5.1 wraps native command stderr and can echo it to host output even when redirected.
- Container is hierarchical-namespace enabled, so any "wipe" needs `DataLakeServiceClient`, not `BlobServiceClient`.

**Operational state after incident.**

- Storage account keys rotated three times. Current valid key is in Infisical only after the owner re-pastes it from the local file `.tickstream-rotated-key.txt`.
- Bronze container empty.
- `state/last_seen_hashes.json` still `{}` so next run will re-ingest all three symbols cleanly.
- No data lost (no Silver or Gold yet, Bronze was the first writer).
- Parser fix committed.

### 2026-06-03 — Phase 1 done

Phase 1 executed today. Concrete state of the environment after this phase:

- **Azure resource group**: `tickstream-rg` in `australiaeast`.
- **Azure storage account**: name held in Infisical as `AZURE_STORAGE_ACCOUNT_NAME`, hierarchical namespace enabled, Standard LRS, public blob access disabled, minimum TLS 1.2.
- **Containers**: `bronze`, `silver`, `gold`, `bad-records`, `archive` (all empty).
- **Storage access key**: held in Infisical as `AZURE_STORAGE_ACCESS_KEY`. Never appeared in chat, never committed to git.
- **Infisical project**: `tickstream-lakehouse`, env `dev`. Five secrets registered: `AZURE_STORAGE_ACCOUNT_NAME`, `AZURE_STORAGE_ACCESS_KEY`, `ALERT_WEBHOOK_URL`, plus `DATABRICKS_HOST` and `DATABRICKS_TOKEN` placeholders (added in Phase 3).
- **Infisical machine identity**: `github-actions-ingest`, Universal Auth, Viewer role on the project.
- **Alerts**: ntfy.sh public topic substituted for Discord because the owner did not want yet another desktop app to install. Documented trade-off: ntfy public topics are obscurity-secured; for real production, self-host ntfy or use a properly authenticated webhook. Secret renamed `DISCORD_WEBHOOK_URL` → `ALERT_WEBHOOK_URL` to keep the variable name provider-agnostic. `config/pipeline.yml` and `config/secrets_required.md` updated accordingly.
- **GitHub Actions Secrets** (bootstrap only): `INFISICAL_CLIENT_ID`, `INFISICAL_CLIENT_SECRET`, `INFISICAL_PROJECT_ID`. Pushed via `gh secret set` without values ever appearing in chat. Verified via `gh secret list`.
- **Smoke test**: `.github/workflows/phase-1-smoke-test.yml` runs on manual dispatch. Installs Infisical CLI, logs in via Universal Auth, fetches all dev secrets, prints proof of chain without leaking values (lengths and prefixes only), and posts a real test alert to ntfy.

### 2026-06-03 — Phase 1 planned (original entry, kept for reference)

Four external accounts will be wired up before any pipeline code is written. Click-by-click guide lives in `LEARNING.md`. Decisions locked in here:

- **Azure ADLS Gen2**
  - Resource group: `tickstream-rg`
  - Region: Australia East (lowest latency for owner)
  - Storage account: globally unique name, lowercase, hierarchical namespace enabled
  - Containers: `bronze`, `silver`, `gold`, `bad-records`, `archive`
  - Performance: Standard. Redundancy: LRS. Trade-off: no geo-redundancy, but cheapest. Cost matters more than DR for a portfolio project.
- **Infisical**
  - Project: `tickstream-lakehouse`
  - Environment: `dev` only for now. Could add `prod` later if a separate prod path is ever built.
  - Machine identity: `github-actions-ingest`, Universal Auth, Viewer role on `dev`.
- **Discord**
  - Server: `tickstream-alerts`
  - Channel: `#pipeline-alerts`
  - Webhook stored in Infisical as `DISCORD_WEBHOOK_URL`.
- **GitHub Secrets** (bootstrap only)
  - `INFISICAL_CLIENT_ID`
  - `INFISICAL_CLIENT_SECRET`
  - `INFISICAL_PROJECT_ID`
  - Rationale: smallest possible blast radius. If GitHub is compromised, only Infisical access leaks, not Azure or Databricks credentials. Infisical can revoke the identity to cut the chain.
- **Databricks Free Edition**: deferred to Phase 3. Not needed until Silver transforms begin.

## Next phase

**Phase 2: Bronze ingestion.** Starts after Phase 1 accounts are confirmed live. Output: a working hourly GitHub Actions workflow that downloads Binance Vision aggTrades for the three symbols, lands the raw file in ADLS `bronze/`, computes SHA-256, writes a plain-English run log to `logs/runs/`, and fires the missing-source-file Discord alert if the source is unreachable.
