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

## Next phase

**Phase 1: external accounts.** Step-by-step click guide will appear in `LEARNING.md` Phase 1 section. Accounts to set up: Azure ADLS Gen2 storage account, Infisical workspace, Discord webhook, Databricks Free Edition workspace. No code in this phase. Output is a populated vault with named secrets that Phase 2 will reference.
