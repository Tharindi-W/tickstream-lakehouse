# Role access matrix

Who can do what across the lakehouse. This matrix is the source of truth for access decisions and is enforced by a combination of Unity Catalog grants in Databricks and IAM role assignments in Azure.

This document is part of the governance handover. If you join this project as a maintainer, read this first.

## Roles

| Role | Description |
|---|---|
| **Pipeline Service Account** | The Infisical machine identity `github-actions-ingest` whose credentials are bootstrapped from GitHub Secrets. All scheduled pipeline writes flow through this identity. |
| **Data Engineer (Owner)** | The human owning the project. Today: Tharindi-W. Has admin on the Databricks workspace, Owner on the Azure subscription, and admin on the Infisical project. |
| **Data Analyst** | A read-only persona for downstream consumers (BI, ad hoc SQL, dbt model authors). Not assigned to anyone today, but the SQL grants below describe the intended posture. |
| **External / Public** | The wider internet. No path to any data in this project. |

## Access matrix

| Resource | Pipeline Service Account | Data Engineer | Data Analyst | External |
|---|---|---|---|---|
| ADLS `bronze/raw/`           | Write          | Read + Write    | None           | None |
| ADLS `bronze/delta/`         | Write          | Read + Write    | None           | None |
| ADLS `silver/` (UC managed)  | Write via Spark | Read + Write   | None           | None |
| ADLS `gold/` (UC managed)    | Write via dbt  | Read + Write    | None           | None |
| UC Volume `tickstream_bronze` | Write         | Read + Write    | Read           | None |
| `workspace.default.silver_agg_trades` | Write via Spark | Read + Write | SELECT  | None |
| `workspace.default.gold_*`   | Write via dbt  | Read + Write    | SELECT         | None |
| `dashboard/*.sql`            | -              | Read + Write    | Read           | Read on GitHub |
| `logs/runs/*.log`            | Write (commit) | Read + Write    | Read           | Read on GitHub |
| `state/last_seen_hashes.json` | Write (commit) | Read + Write   | Read           | Read on GitHub |
| Infisical secrets            | Read           | Read + Write    | None           | None |
| GitHub Actions Secrets       | -              | Read + Write    | None           | None |

## Enforcement points

| Layer | How access is enforced |
|---|---|
| Azure (ADLS) | RBAC role assignments on the storage account. Pipeline Service Account uses a Shared Key fetched from Infisical (a follow-up will switch to OAuth via managed identity once we move to paid Databricks). |
| Databricks (Unity Catalog) | UC grants on catalogs, schemas, tables, and volumes. Workspace admin (the Data Engineer) controls these. |
| Infisical (Vault) | Machine identity has `Viewer` role on the `dev` environment. Human owner has admin. |
| GitHub Actions Secrets | Only the bootstrap Infisical credentials live here. Repo admin (the Data Engineer) controls. |

## Privileged operations

These operations require the **Data Engineer (Owner)** role and are not automated:

- Rotating the Infisical machine identity client secret.
- Rotating Azure storage account access keys.
- Rotating the Databricks personal access token.
- Granting access to new humans or service principals on any of the above.
- Modifying GitHub repo collaborators.
- Approving destructive UC operations (DROP TABLE, REVOKE).

## In a paid Databricks environment

This role matrix maps directly to Unity Catalog GRANT statements. Example for paid Azure Databricks:

```sql
-- Data Analyst role
CREATE ROLE data_analyst;
GRANT SELECT ON SCHEMA workspace.default TO ROLE data_analyst;
GRANT USAGE ON CATALOG workspace TO ROLE data_analyst;
GRANT USAGE ON VOLUME workspace.default.tickstream_bronze TO ROLE data_analyst;

-- Pipeline Service Account
GRANT MODIFY, USAGE ON SCHEMA workspace.default TO `<service-principal>`;
```

Free Edition does not have full UC role-based grants; the matrix here is a contract that becomes executable the day this migrates to paid.
