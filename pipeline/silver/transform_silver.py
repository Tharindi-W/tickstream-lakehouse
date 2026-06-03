# Databricks notebook source
# MAGIC %md
# MAGIC # Silver: aggTrades transformation
# MAGIC
# MAGIC Reads Bronze Delta, type-casts strings into proper Spark types, validates,
# MAGIC deduplicates within `(symbol, batch_date, agg_trade_id)`, applies governance
# MAGIC TBLPROPERTIES, and writes to the Silver Delta table using `MERGE` for
# MAGIC idempotency. Re-running the same `batch_date` is safe and does not
# MAGIC double-count rows.

# COMMAND ----------
dbutils.widgets.text("storage_account", "")
dbutils.widgets.text("storage_key", "")
dbutils.widgets.text("batch_date", "")
dbutils.widgets.text("silver_run_id", "")

storage_account = dbutils.widgets.get("storage_account").strip()
storage_key = dbutils.widgets.get("storage_key").strip()
batch_date = dbutils.widgets.get("batch_date").strip()
silver_run_id = dbutils.widgets.get("silver_run_id").strip()

assert storage_account, "missing storage_account widget"
assert storage_key, "missing storage_key widget"
assert silver_run_id, "missing silver_run_id widget"

# Configure Spark to access ADLS Gen2 using the storage account key. Passing
# the key through dbutils widgets is the first-iteration trade-off documented
# in HANDOVER.md; a follow-up will move this to a Secret Scope or AAD SP.
spark.conf.set(
    f"fs.azure.account.auth.type.{storage_account}.dfs.core.windows.net",
    "SharedKey",
)
spark.conf.set(
    f"fs.azure.account.key.{storage_account}.dfs.core.windows.net",
    storage_key,
)

bronze_path = f"abfss://bronze@{storage_account}.dfs.core.windows.net/delta/bronze_agg_trades/"
silver_path = f"abfss://silver@{storage_account}.dfs.core.windows.net/delta/silver_agg_trades/"
bad_records_path = f"abfss://bad-records@{storage_account}.dfs.core.windows.net/silver/{silver_run_id}/"

print(f"Bronze:      {bronze_path}")
print(f"Silver:      {silver_path}")
print(f"Bad records: {bad_records_path}")
print(f"Batch date filter: {batch_date or 'ALL'}")

# COMMAND ----------
from pyspark.sql import functions as F
from pyspark.sql.types import (
    BooleanType,
    DecimalType,
    LongType,
    TimestampType,
)
from pyspark.sql.window import Window
from delta.tables import DeltaTable

bronze_df = spark.read.format("delta").load(bronze_path)
if batch_date:
    bronze_df = bronze_df.filter(F.col("batch_date") == batch_date)
bronze_count = bronze_df.count()
print(f"Bronze rows in scope: {bronze_count:,}")

# COMMAND ----------
# Type casting Bronze (all strings) into proper Silver types.
silver_df = (
    bronze_df
    .withColumn("agg_trade_id", F.col("agg_trade_id").cast(LongType()))
    .withColumn("price", F.col("price").cast(DecimalType(38, 8)))
    .withColumn("quantity", F.col("quantity").cast(DecimalType(38, 8)))
    .withColumn("first_trade_id", F.col("first_trade_id").cast(LongType()))
    .withColumn("last_trade_id", F.col("last_trade_id").cast(LongType()))
    .withColumn("transact_time_ms", F.col("transact_time").cast(LongType()))
    .withColumn(
        "transact_time",
        F.from_unixtime(F.col("transact_time_ms") / 1000.0).cast(TimestampType()),
    )
    .withColumn("is_buyer_maker", F.lower(F.col("is_buyer_maker")) == "true")
    .withColumn("is_best_match", F.lower(F.col("is_best_match")) == "true")
    .drop("transact_time_ms")
)

# Validity flag. Records that fail this are kept (Bronze fidelity) but
# downstream Gold and analytics should filter on is_valid = true.
silver_df = silver_df.withColumn(
    "is_valid",
    F.col("agg_trade_id").isNotNull()
    & (F.col("price") > 0)
    & (F.col("quantity") > 0)
    & F.col("transact_time").isNotNull(),
)

# Audit columns for Silver layer. Bronze audit columns carry forward.
silver_df = (
    silver_df
    .withColumn("_silver_run_id", F.lit(silver_run_id))
    .withColumn("_silver_at", F.current_timestamp())
)

# Deduplicate within the natural key. Most recent _silver_at wins, which is
# the row from this run (newer than any historical re-load).
key_cols = ["symbol", "batch_date", "agg_trade_id"]
w = Window.partitionBy(*key_cols).orderBy(F.col("_silver_at").desc())
silver_df = (
    silver_df
    .withColumn("_rn", F.row_number().over(w))
    .filter(F.col("_rn") == 1)
    .drop("_rn")
)

silver_count = silver_df.count()
duplicates_dropped = bronze_count - silver_count
print(f"Silver rows after dedup: {silver_count:,}")
print(f"Duplicates dropped:      {duplicates_dropped:,}")

# COMMAND ----------
# Idempotent MERGE into Silver. First write creates the table; subsequent
# writes upsert by natural key so re-running the same batch is safe.
table_exists = DeltaTable.isDeltaTable(spark, silver_path)

if table_exists:
    target = DeltaTable.forPath(spark, silver_path)
    (
        target.alias("t")
        .merge(
            silver_df.alias("s"),
            "t.symbol = s.symbol AND t.batch_date = s.batch_date AND t.agg_trade_id = s.agg_trade_id",
        )
        .whenMatchedUpdateAll()
        .whenNotMatchedInsertAll()
        .execute()
    )
    print("MERGE completed.")
else:
    (
        silver_df.write
        .format("delta")
        .partitionBy("symbol", "batch_date")
        .mode("overwrite")
        .save(silver_path)
    )
    print("Silver Delta table created on first write.")

# COMMAND ----------
# Governance properties on the table. These are the lakehouse-level data
# catalog entries that an auditor or analyst would query to understand the
# table without reading any code.
spark.sql(f"""
ALTER TABLE delta.`{silver_path}` SET TBLPROPERTIES (
    'owner'            = 'Tharindi-W',
    'domain'           = 'crypto_markets',
    'data_source'      = 'binance_vision',
    'contains_pii'     = 'false',
    'regulatory_basis' = 'public_market_data',
    'refresh_cadence'  = 'hourly_dev_then_daily',
    'last_silver_run'  = '{silver_run_id}'
)
""")
print("Governance TBLPROPERTIES applied.")

# COMMAND ----------
# Return a summary to the calling job. dbutils.notebook.exit value is
# echoed back via the Jobs API run-output endpoint, so the GitHub Actions
# workflow can read this directly.
summary = {
    "silver_run_id": silver_run_id,
    "batch_date_filter": batch_date or "ALL",
    "bronze_rows_in_scope": bronze_count,
    "silver_rows_written": silver_count,
    "duplicates_dropped": duplicates_dropped,
    "silver_path": silver_path,
}
print(summary)
dbutils.notebook.exit(str(summary))
