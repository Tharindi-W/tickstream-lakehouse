# Archival policy

How data ages through the lakehouse, where it ends up, and why. This is the cost-control and compliance contract for the project.

## Tiering, in plain English

Data has a half-life. Yesterday's batch will be queried by analysts a thousand times this week. Last quarter's batch will be queried once a month. A five-year-old batch will be queried once a year, if at all. We let the storage layer reflect that reality.

| Tier | Age | Where | Read speed | Write cost | Storage cost (Australia East) |
|---|---|---|---|---|---|
| Hot | 0 to 2 years | ADLS Gen2 Hot tier | Milliseconds | Standard | Standard |
| Cool | 2 to 5 years | ADLS Gen2 Cool tier | Tens of ms | Lower | ~50% of Hot |
| Archive | 5+ years | ADLS Gen2 Archive tier | Up to 15 hours | Lowest | ~10% of Hot |

## What lives at each tier

- **Hot.** Everything we processed in the last 2 years. Bronze raw zips, Bronze Delta, Silver Delta, Gold tables.
- **Cool.** Bronze raw zips and Bronze Delta from 2 to 5 years ago. Silver and Gold stay in Hot because they are query targets.
- **Archive.** Bronze raw zips older than 5 years. Effectively a write-only backup tier; reads are rare and slow.
- **Delete after 90 days.** `bad-records/` content. Bad rows are diagnostic, not source of truth. After 90 days they have either been fixed in code or accepted as historical noise.

## How the tiering is enforced

The lifecycle rules live in `maintenance/adls_lifecycle_policy.json`. They are applied to the storage account via the Azure portal or the CLI:

```bash
# Apply the policy (one-off, with az CLI)
az storage account management-policy create \
  --account-name <storage-account-name> \
  --resource-group tickstream-rg \
  --policy @maintenance/adls_lifecycle_policy.json
```

Azure evaluates the rules every 24 hours and moves blobs that match the age conditions. There is no cron we run; the platform does this for us.

## What stays in Delta versus what does NOT

Delta Lake on ADLS does NOT have first-class lifecycle awareness. If a Delta data file gets tiered to Archive, a query against that table will rehydrate it on read, which is slow and costs a Cool/Archive read.

This means:
- **Active Silver and Gold tables stay 100% in Hot**, no matter the age. We rely on `VACUUM` and partition design to keep their footprint small.
- **Bronze Delta can tier to Cool** because we rarely query it after Silver has been built. Reads are auditing-only.
- **Bronze raw zips can tier to Archive** because they are write-only after the first Silver build.

## Delta time travel and VACUUM

Delta keeps every historical version of a table by default. We set `VACUUM ... RETAIN 720 HOURS` (30 days) weekly so older versions stop costing storage after a month. The `maintenance-weekly.yml` workflow runs this.

If you ever need to extend the time-travel window for debugging, run:

```sql
VACUUM workspace.default.<table> RETAIN 4320 HOURS;   -- 180 days
```

But know that this raises storage cost roughly proportionally.

## Restoring from a cold tier (operational runbook)

If you ever need to query a Bronze raw zip from the Archive tier:

1. In Azure portal, navigate to the blob.
2. Right-click → Rehydrate to Hot. Choose Standard priority unless you need it in under an hour.
3. Wait. Standard rehydrate is up to 15 hours. High priority (more expensive) is under one hour.
4. Once the blob shows Hot, query as normal.
5. After you finish, either delete the rehydrated copy or move it back to Archive to control cost.

There is no automated rehydrate-on-read for Archive tier. This is intentional. Archive is a deliberate access pattern, not a transparent cache.

## Cost expectations at our scale

At the current rate (50 MiB per day of Bronze parquet, similar for raw zips), one year of storage:

| Layer | One year Hot | One year Cool | One year Archive |
|---|---|---|---|
| Bronze raw zips    | ~18 GB | ~9 GB | ~2 GB |
| Bronze Delta       | ~25 GB | ~12 GB | ~3 GB |
| Silver Delta       | ~30 GB | N/A | N/A |
| Gold tables        | ~5 GB | N/A | N/A |

In Australian dollars on the Australia East region, one year of Hot ADLS at ~80 GB is well under AU$3 per month. After ten years of unmanaged growth and natural tiering, we expect under AU$10 per month.

The 12-month Azure free tier covers the first year entirely.
