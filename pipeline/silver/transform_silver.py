# Databricks notebook source
# MAGIC %md
# MAGIC # Silver: aggTrades transformation
# MAGIC
# MAGIC Reads parquet from the UC Volume that Bronze populated, type-casts strings
# MAGIC into proper Spark types, validates, deduplicates within
# MAGIC `(symbol, batch_date, agg_trade_id)`, and upserts into the Unity Catalog
# MAGIC managed Delta table `workspace.default.silver_agg_trades` via `MERGE`
# MAGIC for idempotency.
# MAGIC
# MAGIC No storage account key, no `fs.azure.*` config. Unity Catalog handles
# MAGIC authentication invisibly via the catalog's managed identity.

# COMMAND ----------
dbutils.widgets.text("batch_date",      "")
dbutils.widgets.text("silver_run_id",   "")
dbutils.widgets.text("source_volume",   "/Volumes/workspace/default/tickstream_bronze")
dbutils.widgets.text("target_table",    "workspace.default.silver_agg_trades")

batch_date     = dbutils.widgets.get("batch_date").strip()
silver_run_id  = dbutils.widgets.get("silver_run_id").strip()
source_volume  = dbutils.widgets.get("source_volume").strip()
target_table   = dbutils.widgets.get("target_table").strip()

assert silver_run_id, "missing silver_run_id widget"
assert source_volume, "missing source_volume widget"
assert target_table,  "missing target_table widget"

print(f"Source volume:  {source_volume}")
print(f"Target table:   {target_table}")
print(f"Batch date:     {batch_date or 'ALL'}")
print(f"Silver run id:  {silver_run_id}")

# COMMAND ----------
from pyspark.sql import functions as F
from pyspark.sql.types import BooleanType, DecimalType, LongType, TimestampType
from pyspark.sql.window import Window
from delta.tables import DeltaTable

# Spark's parquet partition discovery infers symbol and batch_date from the
# directory layout the Bronze ingester writes: symbol=X/batch_date=Y/file.parquet
bronze_df = spark.read.parquet(source_volume)
if batch_date:
    bronze_df = bronze_df.filter(F.col("batch_date") == batch_date)
bronze_count = bronze_df.count()
print(f"Bronze rows in scope: {bronze_count:,}")

# COMMAND ----------
# Cast Bronze (all strings, plus audit cols carried forward) into proper Silver types.
silver_df = (
    bronze_df
    .withColumn("agg_trade_id",     F.col("agg_trade_id").cast(LongType()))
    .withColumn("price",            F.col("price").cast(DecimalType(38, 8)))
    .withColumn("quantity",         F.col("quantity").cast(DecimalType(38, 8)))
    .withColumn("first_trade_id",   F.col("first_trade_id").cast(LongType()))
    .withColumn("last_trade_id",    F.col("last_trade_id").cast(LongType()))
    .withColumn("transact_time_ms", F.col("transact_time").cast(LongType()))
    .withColumn(
        "transact_time",
        F.from_unixtime(F.col("transact_time_ms") / 1000.0).cast(TimestampType()),
    )
    .withColumn("is_buyer_maker",   F.lower(F.col("is_buyer_maker")) == "true")
    .withColumn("is_best_match",    F.lower(F.col("is_best_match")) == "true")
    .drop("transact_time_ms")
)

# Validity flag. Records that fail this stay in Silver (Bronze fidelity) but
# downstream Gold filters on is_valid = true.
silver_df = silver_df.withColumn(
    "is_valid",
    F.col("agg_trade_id").isNotNull()
    & (F.col("price") > 0)
    & (F.col("quantity") > 0)
    & F.col("transact_time").isNotNull(),
)

# Silver audit columns. Bronze audit columns carry forward as-is.
silver_df = (
    silver_df
    .withColumn("_silver_run_id", F.lit(silver_run_id))
    .withColumn("_silver_at",     F.current_timestamp())
)

# Deduplicate within the natural key. Most recent _silver_at wins.
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
# Idempotent write into the UC managed Delta table.
# First write creates the table; subsequent writes upsert by natural key.
table_exists = spark.catalog.tableExists(target_table)

if table_exists:
    target = DeltaTable.forName(spark, target_table)
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
    print(f"MERGE into {target_table} completed.")
else:
    (
        silver_df.write
        .format("delta")
        .partitionBy("symbol", "batch_date")
        .mode("overwrite")
        .saveAsTable(target_table)
    )
    print(f"Created Silver table {target_table}.")

# COMMAND ----------
# Governance properties. These are queryable in the catalog and serve as a
# lightweight in-product data dictionary.
spark.sql(f"""
ALTER TABLE {target_table} SET TBLPROPERTIES (
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
summary = {
    "silver_run_id":         silver_run_id,
    "batch_date_filter":     batch_date or "ALL",
    "bronze_rows_in_scope":  bronze_count,
    "silver_rows_written":   silver_count,
    "duplicates_dropped":    duplicates_dropped,
    "target_table":          target_table,
}
print(summary)
dbutils.notebook.exit(str(summary))
