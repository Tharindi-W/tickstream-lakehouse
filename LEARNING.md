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

### Phase 1 — External accounts and vault wiring (2026-06-03)

**What we are doing.** We set up four external services that the pipeline will use, and put the smallest possible bootstrap secret into GitHub. Everything else lives in a real vault (Infisical) and is fetched at workflow runtime.

**Why this matters.** A common portfolio mistake is dropping every secret into GitHub Actions Secrets and calling it "secrets management". That works but is not how enterprises actually do it. Real teams use a vault (HashiCorp Vault, AWS Secrets Manager, Azure Key Vault, Infisical) and bootstrap only one identity token into the CI system. This phase teaches you that pattern with the free tier of Infisical.

**The four accounts at a glance.**

| Account | What it stores | Why this one |
|---|---|---|
| Azure ADLS Gen2 | Bronze raw zips, Silver and Gold Delta tables | The lakehouse storage layer. Free for 12 months. |
| Infisical | All operational secrets (Azure key, Databricks token, Discord URL) | A real vault, not just env vars. Free tier covers this project. |
| GitHub Secrets | ONE secret only: the Infisical bootstrap credentials | Used at workflow start to fetch everything else from Infisical. |
| Discord webhook | The endpoint we POST alerts to | Free, durable, easy to filter by channel. |

Databricks Free Edition is **deferred to Phase 3** since we do not need it until Silver transforms start.

---

#### Step 1 — Azure ADLS Gen2 storage account

If you do not already have an Azure account, go to https://azure.microsoft.com/free and sign up with your normal email. You get $200 credit and 12 months free tier. No charges if you stay within free tier limits.

Inside the Azure portal:

1. Search bar at the top: type **Storage accounts**, click the service.
2. Click **+ Create**.
3. **Subscription**: your default. **Resource group**: click **Create new**, name it `tickstream-rg`.
4. **Storage account name**: must be globally unique, 3 to 24 lowercase letters and numbers. Suggested: `tickstreamlake01`. If taken, add digits.
5. **Region**: Australia East (lowest latency for you).
6. **Performance**: Standard.
7. **Redundancy**: LRS (locally redundant, cheapest).
8. Click **Next: Advanced**.
9. CRITICAL: Tick **Enable hierarchical namespace**. This is what turns plain Blob storage into ADLS Gen2. Without it, the Delta Lake parts later will be painful.
10. Click **Review + create**, then **Create**.

Wait about 30 seconds for the deployment to finish, then **Go to resource**.

Get the access key:

11. Left menu: **Security + networking → Access keys**.
12. Click **Show** next to key1. Copy the **Storage account name** and the **Key** value into a notepad.

Create the five containers:

13. Left menu: **Data storage → Containers**.
14. Click **+ Container** five times. Names exactly: `bronze`, `silver`, `gold`, `bad-records`, `archive`.

Done with Azure.

---

#### Step 2 — Infisical vault

1. Go to https://infisical.com, click **Sign Up**, use the same email.
2. Verify your email, log in.
3. **Create Project**, name it `tickstream-lakehouse`. The default environment is `dev`, leave that as is.
4. Left sidebar: **Secrets**. You see an empty secret list.
5. Click **+ Add Secret** and add the first two now. Names exactly:

| Secret name | Value |
|---|---|
| `AZURE_STORAGE_ACCOUNT_NAME` | The storage account name from Step 1 |
| `AZURE_STORAGE_ACCESS_KEY` | The key1 value from Step 1 |

Leave the rest of the registry in `config/secrets_required.md` blank for now. We fill them when we need them.

Create a machine identity for GitHub Actions:

6. Left sidebar: **Access Control → Machine Identities**.
7. Click **+ Create Identity**, name it `github-actions-ingest`.
8. Auth method: **Universal Auth**. Click create.
9. Click into the new identity. Under **Authentication → Universal Auth → Client Secrets**, click **+ Create Client Secret**. Copy both the **Client ID** (top of the page) and the new **Client Secret** value into your notepad. The Client Secret is shown ONCE so do not close the modal until it is copied.
10. Back in the project (left sidebar **Access Control → Identities** or the project's Identities tab), click **+ Add Identity**, choose `github-actions-ingest`, give it the **Viewer** role on the `dev` environment.

You will also need the **Project ID**. Find it in the project URL `https://app.infisical.com/project/<PROJECT_ID>/...` or in the project settings page. Copy that too.

---

#### Step 3 — Discord webhook

1. Open Discord. If you do not already have a server, click the **+** on the left, **Create My Own → For me and my friends**, name it `tickstream-alerts`.
2. Inside the server, hover the channel list, click **+** to create a channel called `pipeline-alerts`. Make it a text channel.
3. Right-click the channel, **Edit Channel → Integrations → Webhooks → New Webhook**.
4. Name it `TickStream Alerts`. Click **Copy Webhook URL**.
5. Go back to Infisical, click **+ Add Secret**, name `DISCORD_WEBHOOK_URL`, paste the URL as the value.

---

#### Step 4 — Wire the bootstrap secrets into GitHub

This is the one and only place a secret is stored in GitHub Actions Secrets. Everything else flows from Infisical.

1. Go to https://github.com/Tharindi-W/tickstream-lakehouse/settings/secrets/actions
2. Click **New repository secret** and add these three, one at a time:

| Name | Value |
|---|---|
| `INFISICAL_CLIENT_ID` | The Client ID from Step 2.9 |
| `INFISICAL_CLIENT_SECRET` | The Client Secret from Step 2.9 |
| `INFISICAL_PROJECT_ID` | The Project ID from the Infisical URL |

---

**Verify.** When you tell me Phase 1 is done, I will write a tiny GitHub Actions workflow that runs the Infisical CLI, fetches `AZURE_STORAGE_ACCOUNT_NAME`, and prints just the first three characters of it (so we prove the vault chain works without leaking the secret). That is our smoke test for Phase 1.

**Key idea.** Every secret has exactly one home. Infisical for operational secrets, GitHub for the bootstrap. No copy-pasting between systems, no `.env` files in chat, no Slack DMs of credentials. This is the property an auditor checks for.

#### Phase 1 — what actually happened (2026-06-03)

The plan above is the clean version. Reality had small variations worth recording.

- **Infisical UI changed.** The guide said "Create Project". The current UI shows an Org Overview with tiles. The path is **Org Overview → Secrets Management tile → Create Project**. Updated mental model: Infisical the company has expanded into KMS, Certificate Manager, PAM. Secrets Management is now one product among several.
- **Discord replaced with ntfy.sh.** The owner did not want yet another desktop app. Switched to ntfy.sh: zero account, zero install, just pick a hard-to-guess topic and POST to it. The secret name in Infisical was renamed `DISCORD_WEBHOOK_URL` → `ALERT_WEBHOOK_URL` so future swaps to Slack or self-hosted webhooks do not need code changes. Trade-off documented in `HANDOVER.md`: ntfy public topics are obscurity-secured.
- **Azure resource provider registration.** First storage account creation attempt failed with `SubscriptionNotFound`. Real cause: `Microsoft.Storage` was `NotRegistered` on the fresh subscription. Fix: `az provider register --namespace Microsoft.Storage` then poll until state is `Registered` (about 30 seconds). This is a common gotcha on new Azure subscriptions and the error message is misleading.
- **Project-level Machine Identity creation.** Infisical now offers a combined "Create New / Assign Existing" dialog at the project level which creates the identity AND assigns it to the project with a role in one shot. Faster than the org-level path.

#### The pattern you just learned

Real teams do not put every secret in CI Secrets. They put exactly one bootstrap identity in CI and a real vault holds everything else. If CI is compromised, the blast radius is "attacker can pretend to be the CI runner against the vault" rather than "attacker has Azure storage keys outright". The vault can then revoke that one identity to cut the chain.

#### The smoke test

`.github/workflows/phase-1-smoke-test.yml` runs on manual dispatch. It installs the Infisical CLI, logs in with the machine identity, fetches the dev secrets, masks them in logs via the `::add-mask::` directive, prints proof of the chain (lengths and host prefixes only), and POSTs a real notification to your ntfy topic. If both the workflow shows green and the ntfy notification arrives, the entire Phase 1 plumbing is verified.

### Phase 2 — first run, two leaks, real lessons (2026-06-03)

The first Bronze run did its job at the GitHub Actions level (green tick in 1m25s) but Python inside ran into two distinct kinds of failure worth recording here in plain English, because both are the kind of thing that bites real teams in real projects.

**Lesson 1 — public data is messy.**

Binance Vision is FREE and PUBLIC, which means there is no SLA on its CSV format. We assumed every symbol's daily aggTrades file would have a header row. BTCUSDT does. ETHUSDT and SOLUSDT do not. Our parser used `pd.read_csv` with default `header=0`, so for ETHUSDT the first row of actual trade data became the "column names". Delta's schema check (correctly) refused to append rows whose columns were `1999085122, 0.0234, ...` to a table whose columns were `agg_trade_id, price, ...`.

The fix in `pipeline/bronze/land_to_bronze.py` is the kind of thing you see in real production: peek at the first cell, if it parses as an integer treat the file as headerless and apply a canonical schema; otherwise skip the header row and apply the same canonical schema. Either way the DataFrame leaves the parser with the same 8 columns in the same order. The Delta table sees a stable schema regardless of which symbol it came from.

The take-away: when you ingest someone else's data, never let pandas guess your schema. Always assert it.

**Lesson 2 — your shell can leak your secrets.**

While cleaning up the half-written Bronze data, the Azure CLI's `--account-key=<value>` argument got dumped into the conversation transcript twice in a row.

Mechanism: when az has an internal exception (here, parsing the JMESPath query `length(@)`), it dumps a Python traceback to stdout. The traceback includes `sys.argv`. `sys.argv` includes every argument passed to az, which includes `--account-key=<base64-value>`. PowerShell 5.1 then takes the captured stdout, treats it as a NativeCommandError, and echoes it to host output regardless of `2>$null` or `Out-Null` because it does the wrapping at a higher level than the redirect.

The fix:

- For data plane operations, use the `AZURE_STORAGE_KEY` env var instead of `--account-key`. Environment variables are not in `sys.argv` and so cannot leak through a traceback.
- On Windows specifically, prefer the Python SDK for any operation that handles a secret. `azure-storage-file-datalake` accepts the key as a constructor argument; nothing inside the Python process will ever serialise it.
- If you must use the CLI for a sensitive operation, use `--auth-mode login` with an AAD identity that has the right RBAC. Then there is no key on the command line at all.

The fact that this caused two leaks and three key rotations in the space of a few minutes is exactly how it goes in the real world. The lesson is not "be more careful" — humans cannot be relied upon to remember stderr-wrapping quirks under pressure. The lesson is to remove the surface area: use env vars and SDKs, never pass secrets as CLI flags.

**Lesson 3 — ADLS Gen2 hierarchical namespace is not Blob storage.**

When we tried to wipe Bronze with the standard `azure-storage-blob` SDK, it failed on the first non-empty "directory" with `DirectoryIsNotEmpty`. ADLS Gen2 with HNS enabled treats prefixes as real directories with metadata of their own. The right SDK is `azure-storage-file-datalake`, which has `delete_directory(recursive=True)` semantics that mirror a real filesystem.

Real-world implication: any tooling you pick for working with ADLS Gen2 needs to know about HNS. Some packages (older `deltalake` builds for example) assume flat blob layout and will surprise you.

**Operational outcome.**

- Storage keys rotated. New key is on the owner's desktop in `.tickstream-rotated-key.txt`.
- Bronze container is empty and ready for the corrected ingester.
- Parser is fixed.
- The hourly schedule was paused (workflow_dispatch only triggers it) so no automatic re-run lands until the owner updates Infisical with the new key and we manually re-trigger.

### Phase 2 done — what landed (2026-06-03)

Second run ingested all three symbols in 46 seconds of Python time. ~3.28M rows of real Binance trade data are now in Bronze Delta, partitioned by `(symbol, batch_date)`, with audit columns attached. The two log files in `logs/runs/` together tell the story of a failed run followed by a corrected run — exactly the kind of audit trail an enterprise auditor wants to see.

**What you have proven you can build, end to end.**

You now have a small but real lakehouse foundation: a vault, a cron-scheduled ingestion job, idempotent state, audit-columned Delta tables, plain-English logging, missing-source alerting, retry-with-backoff fault tolerance, and a real public data source feeding it. Every component is open source or free tier. Nothing relies on a paid Databricks or paid orchestrator.

**Numbers from this batch (2026-06-02 daily aggTrades):**

| Symbol | Compressed download | Parsed rows |
|---|---|---|
| BTCUSDT | 23.3 MiB | 1,677,042 |
| ETHUSDT | 20.0 MiB | 1,380,545 |
| SOLUSDT | 3.7 MiB | 219,980 |

This is enough to start meaningfully exercising PySpark when we get to Silver. Three-and-a-quarter million rows is small for Spark in absolute terms but already large enough that a Pandas-only Silver would struggle as we add more days and more symbols.

### Phase 3 — Silver transformation on Databricks Free Edition

**What you set up here.** A real Spark workspace running real PySpark on real Bronze data, orchestrated from GitHub Actions over the Databricks Jobs API. After Phase 3 you can credibly say "I have used Databricks in production-shape work."

**The four account steps.**

#### Step 1 — Databricks Free Edition signup (5 min)

1. Open https://www.databricks.com/learn/free-edition in your browser.
2. Click **Get Started** (or **Try Databricks Free**).
3. Sign up with the same email you used for Infisical and Azure. No credit card required.
4. Verify the email if prompted.
5. When asked to pick a cloud provider for the trial, choose anything (we won't use the cloud integration, just the compute and notebooks Free Edition gives us directly).
6. Region: pick the one closest to Australia (Sydney/East Asia/US West are usual options).
7. Wait for your workspace to provision. The URL will look like `https://dbc-XXXXXXXX-XXXX.cloud.databricks.com`. Copy it.

#### Step 2 — Verify you can launch compute (2 min)

1. Inside the workspace, left sidebar: **Compute → All-purpose compute**.
2. If you see no clusters, click **Create compute** to confirm the option is there (do not actually create one yet, Free Edition's Serverless is what we use). Free Edition typically gives you a default Serverless cluster.
3. Left sidebar: **Workspace → Users → your-email**. You should see a Home folder.

If anything here looks different from what I described, screenshot it. Databricks UIs vary by tenant.

#### Step 3 — Generate a Personal Access Token (3 min)

1. Top right: click your **profile circle → Settings**.
2. Left sidebar inside Settings: **Developer**.
3. Find **Access tokens → Manage**.
4. Click **Generate new token**.
5. Comment: `github-actions-silver`. Lifetime: leave default 90 days.
6. Click Generate. A modal shows the token value ONCE. Copy it immediately. If you close the modal without copying, you have to make a new one.

#### Step 4 — Put the workspace URL and token into Infisical (2 min)

1. Open Infisical → `tickstream-lakehouse` project → Dev env.
2. Find the secret named `DATABRICKS_HOST` (it should already exist as a placeholder from Phase 1). Click it, paste the workspace URL (full URL with `https://`), save.
3. Find `DATABRICKS_TOKEN`. Paste the token from step 3.6, save.
4. Confirm Infisical now shows 5 secrets with real values: `AZURE_STORAGE_ACCOUNT_NAME`, `AZURE_STORAGE_ACCESS_KEY`, `ALERT_WEBHOOK_URL`, `DATABRICKS_HOST`, `DATABRICKS_TOKEN`.

That is it for your side. Tell me when done and I will run the Phase 3 vault chain smoke test (same idea as Phase 1, this time also calling the Databricks REST API to prove the token works) before any Silver code lands.

---

**Plan for what I build after your accounts are ready.**

| Step | Output |
|---|---|
| 3a | `pipeline/silver/transform_silver.py` PySpark notebook source (committed in repo for review; Databricks gets a copy via Workspace API) |
| 3b | `pipeline/silver/job_spec.json` Databricks Job spec describing tasks, parameters, retries |
| 3c | Helper script `pipeline/silver/deploy.py` that uploads the notebook and creates/updates the job via Databricks API |
| 3d | `.github/workflows/ingest-silver-after-bronze.yml` chained workflow triggered by successful Bronze runs, calls Jobs API run-now with batch parameters |
| 3e | `dq/soda_silver.yml` Soda Core checks that read Silver via deltalake-py and fail loud on threshold breach |
| 3f | Phase 3 smoke test workflow proving the full Bronze → Silver chain end to end |

**Silver transformation logic at a glance.**

- Read Bronze Delta filtered to the target batch_date.
- Cast strings into proper types: `agg_trade_id` Long, `price`/`quantity` Decimal(38,8), `transact_time` from epoch-ms Long to Timestamp, `is_buyer_maker`/`is_best_match` Bool.
- Compute `is_valid` boolean from null and range checks.
- Deduplicate within `(symbol, batch_date, agg_trade_id)`.
- Attach Silver audit columns: `_silver_at`, `_silver_run_id`.
- Write Silver Delta via Delta `MERGE` keyed on `(symbol, batch_date, agg_trade_id)` so re-runs are idempotent (no duplicates, no double-counting).
- Set `badRecordsPath` to `az://bad-records/silver/<run_id>/` so single malformed rows do not kill the job.
- Apply Delta TBLPROPERTIES for governance (owner, domain, contains_pii=false, regulatory_basis=public_market_data).

**Honest scoping note.** The first Silver iteration passes the storage account key as a Databricks Job parameter, which means the value is visible in Job run history. That is acceptable for a portfolio project and is documented as a known trade-off. A follow-up commit will replace this with either a Databricks Secret Scope synced from Infisical or an Azure AD service principal mounted on the workspace.

### Phase 3 done — what landed (2026-06-03)

Silver Delta table created at `workspace.default.silver_agg_trades` via real Databricks Free Edition Serverless Spark. 3.28M rows from the 2026-06-02 batch, type-cast into proper Decimal/Timestamp/Bool, deduplicated, written via `MERGE`. Governance TBLPROPERTIES applied. 40 seconds of Spark wall clock.

#### The two architectural lessons of Phase 3

1. **Databricks Free Edition Serverless deliberately blocks `fs.azure.*` Spark configs.** Spark Connect (the protocol Free Edition uses) has a denylist of server-side configs that user code cannot set. The intent is to force all storage access through Unity Catalog so the catalog stays the audit point. We learned this by hitting `[CONFIG_NOT_AVAILABLE]` when the first Silver iteration tried `spark.conf.set("fs.azure.account.auth.type.<account>", "SharedKey")`.

2. **Free Edition workspaces live in Databricks' own Azure tenant, not yours.** This kills the "UC External Location backed by your Azure Managed Identity" pattern because the managed identity cannot cross Azure AD tenants. The error we hit was `Azure Managed Identity Credential ... could not be found` with Databricks' own account id showing up in the error. The Access Connector and role we created in Azure are valid resources, they will work the day you stand up paid Azure Databricks inside your own subscription. For Free Edition we pivoted to UC Volumes.

#### Path B in plain English

- ADLS stays as the source of record. Raw zips, Bronze Delta, all there.
- Bronze ingester writes a parquet copy of each batch to a UC Volume at `/Volumes/workspace/default/tickstream_bronze/symbol=X/batch_date=Y/agg_trades.parquet`. The Volume lives in Databricks-managed storage, so Spark on Free Edition is allowed to read it.
- Silver notebook reads from the Volume, transforms, writes to a UC managed Delta table at `workspace.default.silver_agg_trades`. No storage account key passes through Spark at any point.
- Cost of this pattern: data is stored twice. At our 50 MiB per day it is irrelevant. At hundreds of GB per day you would want to revisit the architecture.

#### Why this is still a real Databricks story for a portfolio

- The notebook is real PySpark.
- The job is a real Databricks Job on real Serverless compute.
- The MERGE is a real Delta MERGE that demonstrates idempotency.
- The target is a real Unity Catalog managed table that you can query from Databricks SQL.
- The orchestration is real cross-system: GitHub Actions runs the bash, calls the Databricks Jobs API, polls, alerts.

What is NOT real: Spark is not reading from your enterprise data lake directly. It is reading a copy in Databricks-managed storage. For paid Databricks this layer would not be necessary.

#### Phase 3 incident log

Before this passed clean, we hit and resolved five distinct issues. They are recorded here because each one is exactly the kind of surprise a real DE faces.

| # | Symptom | Real cause | Fix |
|---|---|---|---|
| 1 | `Workspace doesn't support Client-1 channel for REPL` | Free Edition Serverless requires `client: "2"` in the Jobs API environment spec | Bumped the client version in `silver-transform.yml` |
| 2 | `Workload failed, see run output for details` with empty `notebook_output.result` | `runs/get-output` requires the TASK run_id, not the parent run_id | Walked `tasks[0].run_id` from the parent run and called get-output with that |
| 3 | `[CONFIG_NOT_AVAILABLE] fs.azure.account.auth.type.*** is not available` | Spark Connect denylist of configs on Free Edition | Pivoted from raw shared-key ADLS access to UC, ultimately to Path B |
| 4 | `Azure Managed Identity Credential ... could not be found` on creating Storage Credential | Free Edition runs in Databricks' Azure tenant, not yours; managed identities cannot cross tenants | Documented as the Path C dead end; pivoted to Path B (UC Volume copy) |
| 5 | `[UNSUPPORTED_FEATURE.SET_TABLE_PROPERTY] owner is a reserved table property` | UC auto-manages `owner` on every table; you cannot set it via `TBLPROPERTIES` | Removed `owner` from the Silver notebook's SET TBLPROPERTIES, kept the other custom keys |

The detail above is in the repo's commit history with full timestamps and error traces. Anyone inheriting this project can search the relevant commit messages and reproduce the reasoning.

### Phase 4 — coming next

Gold modelling with dbt-spark. Reads the Silver Delta table, builds OHLCV resamples (1-minute, 1-hour, 1-day), VWAP per symbol-day, and a daily volatility metric. Tests live next to the models in dbt format. Output: three or four Gold tables under `workspace.default.gold_*`.
