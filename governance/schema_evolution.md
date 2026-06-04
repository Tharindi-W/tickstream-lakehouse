# Schema evolution policy

How this project handles changes to source schemas, intermediate schemas, and target schemas. Written so a future maintainer can make a schema change without breaking the pipeline.

## Source schema changes (Binance Vision)

Binance has historically made the following changes:

- Removed the `is_best_match` column on some symbols.
- Started shipping a header row on some symbols and not others.
- Added a `b` flag column (planned, not observed yet).

### Detection

The Bronze parser in `pipeline/bronze/land_to_bronze.py::_parse_csv_from_zip` peeks at the first non-empty CSV line and counts columns. If the count differs from the expected canonical schema (8 columns), it pads missing columns with NULL or drops extras silently.

This is intentional: Bronze is the place to absorb source variation. Silver enforces the strict schema.

### Action when Binance adds a new column

1. Update `COLUMNS_FULL` in `pipeline/bronze/land_to_bronze.py` to include the new column name.
2. Add a cast for the new column in `pipeline/silver/transform_silver.py`.
3. Add the column to the Silver section of `governance/data_dictionary.md`.
4. Add a schema test in `dq/` (when the DQ layer lands) or in `dbt/models/sources.yml` if it should be enforced as not_null.
5. If the column is sensitive, add it to the sensitivity classification table.
6. Bronze re-runs will start populating the new column; Silver `MERGE` will leave existing rows null for the new column. That is intentional, not a bug.

### Action when Binance removes a column

1. The Bronze parser pads with NULL so this does not break immediately.
2. Decide whether to drop the column from Silver or keep it as a nullable historical field. Default: keep it nullable.
3. Update the data dictionary to note when the column was deprecated.
4. Do NOT delete historical data; the column remains valid for old batches.

## Silver schema changes

Silver is governed by the type casts and audit-column attachment in `pipeline/silver/transform_silver.py`.

### Adding a column

1. Add the cast or computation in the notebook.
2. Add the column to `governance/data_dictionary.md`.
3. Add tests in `dbt/models/sources.yml` if Gold will rely on it.
4. Silver Delta does NOT have schema enforcement on append today. A Silver write with a new column will succeed and the table will gain it.
5. For a removed column: do NOT remove from the table directly. Add a deprecation note in the data dictionary, and a follow-up commit can drop after a quarter.

### Backfill

If Silver's transformation logic changes (e.g., new validity rule), re-running the Silver notebook with `batch_date=""` (no filter) re-processes every batch currently in the Volume. Delta `MERGE` makes this idempotent: existing rows get updated with the new logic, no duplicates.

## Gold schema changes

Gold is governed by the dbt models under `dbt/models/`.

### Adding a column to a Gold table

1. Add the column to the model's SQL.
2. Add a corresponding entry in `dbt/models/schema.yml` with appropriate tests.
3. Update `governance/data_dictionary.md`.
4. `dbt build` will FAIL the next run with a "schema mismatch" error if the model is materialised as `table`. Resolution: run `dbt run --full-refresh -s <model_name>` once to rebuild the table with the new schema, then revert to normal `dbt build`.

### Adding a new Gold model

1. Create the SQL file in `dbt/models/`.
2. Add a corresponding block in `dbt/models/schema.yml` with column tests.
3. Add a section to `governance/data_dictionary.md`.
4. Add a dashboard query in `dashboard/` that exercises the new model.

## What this project does NOT do (yet)

- **Strict schema-on-write enforcement** on Silver. The Silver MERGE accepts new columns. A follow-up commit will enforce an asserted `StructType` on read to fail loud.
- **Backwards-incompatible change gating**. Right now any contributor can push a column rename or drop. A follow-up will add a CI step that compares the proposed schema to the latest known schema and requires an explicit decision label on the PR.
- **Schema registry**. We do not currently maintain a versioned schema registry (e.g., via `confluent-schema-registry` or `dataclass-version-decorator`). The data dictionary is the closest thing.

These are tracked as Phase 9 polish items in HANDOVER.
