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
