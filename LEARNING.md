# Learning Walk-through

This document is the educational companion to the project. It explains what each part teaches you, in plain English, and where to look in the codebase for the concept in action.

`HANDOVER.md` is for operators. `LEARNING.md` is for the curious. Read both, in that order, if you want the full picture.

## Skills this project covers

| Skill area | Where you see it |
|---|---|
| Cloud storage | Azure ADLS Gen2, hot / cool / archive tiers |
| Distributed compute | PySpark on Databricks Free Edition |
| Delta Lake | ACID writes, MERGE, time travel, OPTIMIZE, ZORDER, VACUUM |
| Medallion architecture | Bronze raw, Silver cleaned, Gold business-ready |
| dbt | dbt-spark project for Silver to Gold transforms with tests |
| Orchestration | GitHub Actions cron, manual triggers, retries, schedule reset |
| Secrets management | Infisical vault, machine tokens, GitHub Actions integration |
| Data quality | Soda Core declarative checks plus dbt tests |
| Observability | Evidence.dev data dashboard, Grafana Cloud ops dashboard |
| Data lineage | OpenLineage events emitted to Marquez |
| Governance | Role access matrix, TBLPROPERTIES catalog, column sensitivity tags |
| Encryption and hashing | SHA-256 file fingerprints, AES utility (labelled demo) |
| Fault tolerance | Retry with backoff, badRecordsPath, idempotent MERGE |
| CI / DevEx | ruff, mypy, pytest, pre-commit, PR gating |
| Documentation discipline | Mermaid diagrams in version control, plain-English handover, decision log |

## Phase roadmap

| Phase | What gets built | Skills you pick up |
|---|---|---|
| 0 | Repo scaffold and architecture diagram | Repo hygiene, Mermaid, project planning |
| 1 | External accounts and vault wiring | Azure portal, Infisical, GitHub Secrets, Discord webhooks |
| 2 | Bronze ingestion | GitHub Actions, Python requests, SHA-256, audit columns, Delta writes |
| 3 | Silver transformation | PySpark dedup, schema enforcement, Soda Core, retry decorators |
| 4 | Gold modelling | dbt-spark, dbt tests, dbt docs |
| 5 | Observability | Evidence.dev, Grafana Cloud, OpenLineage, log rotation |
| 6 | Governance | TBLPROPERTIES, role matrix, data dictionary, data contracts |
| 7 | Archival | ADLS lifecycle policies, Delta VACUUM |
| 8 | Polish and demo | README polish, recorded demo, schedule reset from hourly to daily |

## Learning journal

The journal grows as we build. Each phase gets a section.

### Phase 0 — Repo scaffolding (2026-06-03)

**What we did.** Created an empty public GitHub repo named `tickstream-lakehouse`. Scaffolded a folder structure that mirrors the medallion architecture. Wrote three documents at the root: this file (`LEARNING.md`), the operational decision log (`HANDOVER.md`), and the project overview (`README.md`). Added a Mermaid architecture diagram that renders directly in the GitHub UI.

**Why it matters.** Most real data engineering projects fail not because the code is wrong but because no-one can pick them up six months later. Writing the handover document and the architecture diagram on Day 1 is unusual. It pays off every week after.

**What to look for.**

- The folder list in the README mirrors the medallion stages: `pipeline/bronze`, `pipeline/silver`, `pipeline/gold`. Every layer is going to have its own ingestion or transformation logic with audit columns added at write time.
- The `dbt/` folder is reserved for Silver-to-Gold modelling, because dbt is the industry standard for analytical transformations and shows up in nearly every data engineering job ad.
- `config/pipeline.yml` holds every non-secret tunable knob. Thresholds, retention windows, symbol list, schedule cron. Secrets are NOT here. Secrets go in Infisical.

**Key idea.** A folder structure is a contract. If a future maintainer sees `pipeline/silver/transform_silver.py`, they should be able to guess what that file does before opening it. Naming is governance.

**The Mermaid diagram trick.** GitHub renders Mermaid blocks inside markdown automatically. You write a fenced block with the language `mermaid` and GitHub shows the diagram. This means the architecture diagram lives next to the code, in version control, and updates with every PR. No more "the diagram is in someone's Lucidchart that they have not opened since 2023".

### Phase 1 — coming next

External accounts. Click-by-click guide goes here once we start Phase 1.
