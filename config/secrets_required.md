# Secrets Registry

Every secret the pipeline uses, where it lives, who can read it, and what would break if it leaks. This is the auditable source of truth for the project's secret hygiene.

**No actual secret values appear in this file or anywhere else in the repo.** Only names and metadata.

## Storage layers

| Layer | Lives in | Purpose |
|---|---|---|
| Bootstrap | GitHub Actions Secrets | Just enough to authenticate to Infisical at workflow start |
| Operational | Infisical project `tickstream-lakehouse`, env `dev` | Everything the pipeline actually uses |

## Bootstrap secrets (GitHub Actions Secrets)

Stored at https://github.com/Tharindi-W/tickstream-lakehouse/settings/secrets/actions

| Name | Source | What it does | Blast radius if leaked |
|---|---|---|---|
| `INFISICAL_CLIENT_ID` | Infisical → Machine Identity `github-actions-ingest` | Identifies the GitHub Actions runner to Infisical | Low alone, useless without the client secret |
| `INFISICAL_CLIENT_SECRET` | Infisical → Machine Identity `github-actions-ingest` | Authenticates GitHub Actions runner to Infisical | Medium. Anyone with both bootstrap secrets can fetch every operational secret. Revoke by rotating the client secret in Infisical. |
| `INFISICAL_PROJECT_ID` | Infisical project URL | Tells the Infisical CLI which project to read from | None (it is a public identifier) |

## Operational secrets (Infisical)

Stored at https://app.infisical.com/project/{INFISICAL_PROJECT_ID}/secrets

| Name | What it is | When it is fetched | Blast radius if leaked |
|---|---|---|---|
| `AZURE_STORAGE_ACCOUNT_NAME` | Name of the ADLS Gen2 storage account | Every pipeline run | Low (public-ish, but combined with the key gives full storage access) |
| `AZURE_STORAGE_ACCESS_KEY` | Account-level key for ADLS Gen2 | Every pipeline run | HIGH. Full read/write on every container in the account. Rotate via Azure portal → Access keys → Rotate. |
| `DATABRICKS_HOST` | URL of the Databricks workspace | Phase 3 onwards | Low (public-ish) |
| `DATABRICKS_TOKEN` | Personal access token for Databricks Jobs API | Phase 3 onwards | HIGH. Full workspace access. Rotate in Databricks → User Settings → Developer → Access tokens. |
| `ALERT_WEBHOOK_URL` | Webhook URL for the alerts destination (currently ntfy.sh topic) | Every pipeline run that needs to alert | LOW. Spam risk only. Rotate by picking a new ntfy topic and updating the secret. |

## Rotation policy

| Secret | Cadence | Trigger |
|---|---|---|
| `INFISICAL_CLIENT_SECRET` | Every 90 days, or immediately on team change | Calendar reminder or owner change |
| `AZURE_STORAGE_ACCESS_KEY` | Every 90 days | Calendar reminder |
| `DATABRICKS_TOKEN` | Every 90 days | Calendar reminder |
| `ALERT_WEBHOOK_URL` | Only on suspected abuse or topic guess | Spam from unknown senders |

## What is NOT in this registry, and why

- **No `.env` file anywhere.** A `.env.example` may appear later showing the variable NAMES only, never values.
- **No secrets in `config/pipeline.yml`.** That file holds only public tunables (thresholds, symbol list, cron schedules).
- **No secrets in commit messages or code comments.** `ruff` plus a pre-commit hook (added in a later phase) will scan for accidental leaks.

## How a workflow uses these

Conceptually:

1. GitHub Actions workflow starts.
2. Workflow uses `INFISICAL_CLIENT_ID` and `INFISICAL_CLIENT_SECRET` from GitHub Secrets to log in to Infisical.
3. Workflow fetches all required operational secrets by name from Infisical project `INFISICAL_PROJECT_ID`.
4. Operational secrets are exported as environment variables for the duration of the job only.
5. Job ends, environment is destroyed. Secrets do not persist on the runner.

The actual workflow YAML lives in `.github/workflows/` once we reach Phase 2.
