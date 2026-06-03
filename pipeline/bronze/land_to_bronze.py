"""Bronze ingestion orchestrator.

For each configured symbol in config/pipeline.yml, this script:
  1. Picks the target batch date as yesterday in UTC (daily files are only
     final after UTC midnight).
  2. HEAD-checks the Binance Vision endpoint. If 404, fires a missing-source
     alert and moves on (does NOT abort the whole run).
  3. Downloads the zip into memory, computing SHA-256 as it streams.
  4. Compares the hash to state/last_seen_hashes.json. If unchanged, logs
     "skipped" and moves on. This is what makes the hourly schedule cheap.
  5. Uploads the raw zip to ADLS `bronze/raw/symbol=X/batch_date=YYYY-MM-DD/`.
  6. Unzips, parses the CSV, attaches audit columns, and appends to the Bronze
     Delta table at `bronze/delta/bronze_agg_trades/` partitioned by
     (symbol, batch_date).
  7. Updates state/last_seen_hashes.json so the next run sees the new hash.

End of run:
  - Writes a Markdown run log to logs/runs/{run_id}.log.
  - Returns exit code 0 (SUCCESS or PARTIAL) or 1 (FAILED with no symbols done).

Idempotency note:
  This first cut uses Delta `append`. If the same date is re-ingested (e.g.
  state file lost), this would create duplicates in the Bronze Delta. A
  follow-up commit will switch to a partition-overwrite or MERGE strategy.
  Document this in HANDOVER so the trade-off is visible.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from io import BytesIO
from zipfile import ZipFile

import pandas as pd
import requests

from alerts.notifier import notify
from ingestion.binance_vision import DailyFile, download, head_check
from pipeline.common.config import load_config
from pipeline.common.logging_utils import RunLogger
from pipeline.common.state import load_state, save_state


def _upload_raw_zip(
    storage_account: str,
    storage_key: str,
    container: str,
    blob_path: str,
    data: bytes,
) -> None:
    """Upload raw zip bytes to ADLS Gen2 (HNS-enabled blob endpoint)."""
    from azure.storage.blob import BlobServiceClient, ContentSettings

    url = f"https://{storage_account}.blob.core.windows.net"
    client = BlobServiceClient(account_url=url, credential=storage_key)
    container_client = client.get_container_client(container)
    blob = container_client.get_blob_client(blob_path)
    blob.upload_blob(
        data,
        overwrite=True,
        content_settings=ContentSettings(content_type="application/zip"),
    )


def _upload_to_volume(host: str, token: str, volume_path: str, data: bytes) -> None:
    """Upload bytes to a Databricks UC Volume path via the Files API.

    Used on Free Edition where Spark cannot directly access our ADLS Gen2
    via shared key. A copy of the Bronze parquet lives in the Volume so
    Silver (PySpark on Free Edition Serverless) has something it is allowed
    to read.
    """
    url = f"{host.rstrip('/')}/api/2.0/fs/files{volume_path}?overwrite=true"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/octet-stream",
    }
    r = requests.put(url, headers=headers, data=data, timeout=600)
    r.raise_for_status()


def _write_bronze_delta(
    storage_account: str,
    storage_key: str,
    container: str,
    delta_path: str,
    df: pd.DataFrame,
) -> None:
    """Append a partition of rows to the Bronze Delta table.

    Uses the delta-rs Rust core via the deltalake Python package, which means
    we do NOT need Spark at this layer. Spark comes in at Silver.
    """
    from deltalake import write_deltalake

    table_uri = f"az://{container}/{delta_path}"
    storage_options = {
        "AZURE_STORAGE_ACCOUNT_NAME": storage_account,
        "AZURE_STORAGE_ACCESS_KEY": storage_key,
    }
    write_deltalake(
        table_uri,
        df,
        storage_options=storage_options,
        mode="append",
        partition_by=["symbol", "batch_date"],
    )


# Canonical 8-column schema for Binance aggTrades. Older files may have 7
# columns (no is_best_match). We always normalise the parsed DataFrame to
# this full set so the Bronze Delta schema is stable across symbols and dates.
COLUMNS_FULL = [
    "agg_trade_id",
    "price",
    "quantity",
    "first_trade_id",
    "last_trade_id",
    "transact_time",
    "is_buyer_maker",
    "is_best_match",
]


def _parse_csv_from_zip(zip_bytes: bytes) -> pd.DataFrame:
    """Extract the single CSV inside a Binance daily aggTrades zip.

    Binance Vision is inconsistent: BTCUSDT files ship with a header row, but
    several other symbols do not. If we let pandas guess a header, the first
    data row becomes the column names and every symbol ends up with a different
    schema. We detect header presence by looking at the first cell and always
    return a DataFrame with the same canonical 8-column schema.

    Everything is read as string. Silver does the type casting.
    """
    with ZipFile(BytesIO(zip_bytes)) as zf:
        csv_names = [n for n in zf.namelist() if n.endswith(".csv")]
        if not csv_names:
            raise ValueError("zip contains no .csv file")
        with zf.open(csv_names[0]) as f:
            data = f.read()

    # First non-empty line tells us column count and whether there's a header.
    first_line = b""
    for line in data.split(b"\n"):
        line = line.strip()
        if line:
            first_line = line
            break
    cells = first_line.decode("utf-8", errors="replace").split(",")
    n_cols = len(cells)
    first_cell = cells[0].strip().strip('"')

    try:
        int(first_cell)
        has_header = False
    except ValueError:
        has_header = True

    columns = COLUMNS_FULL[:n_cols]
    df = pd.read_csv(
        BytesIO(data),
        dtype=str,
        header=None,
        names=columns,
        skiprows=1 if has_header else 0,
    )

    # Pad any missing canonical columns so the Bronze Delta schema is stable.
    for col in COLUMNS_FULL:
        if col not in df.columns:
            df[col] = pd.NA
    return df[COLUMNS_FULL]


def main() -> int:
    cfg = load_config()
    log = RunLogger()

    try:
        storage_account = os.environ["AZURE_STORAGE_ACCOUNT_NAME"]
        storage_key = os.environ["AZURE_STORAGE_ACCESS_KEY"]
    except KeyError as e:
        log.info(f"FATAL: required env var missing: {e}")
        log.finalise("FAILED", f"missing env: {e}")
        return 1

    container = cfg["storage"]["container_bronze"]
    symbols: list[str] = cfg["source"]["symbols"]
    target_date = (datetime.now(timezone.utc) - timedelta(days=1)).date()

    log.info(f"Run id: {log.run_id}")
    log.info(f"Symbols: {', '.join(symbols)}")
    log.info(f"Batch date (T-1 UTC): {target_date.isoformat()}")
    log.info(f"Bronze container: {container}")

    state = load_state()
    summary = {"processed": 0, "skipped_unchanged": 0, "missing_source": 0, "errors": 0}

    for symbol in symbols:
        log.section(f"Symbol: {symbol}")
        target = DailyFile(symbol=symbol, date=target_date)
        try:
            log.info(f"Checking source: {target.url}")
            exists = head_check(target)
            if not exists:
                log.info(f"Source not yet available for {symbol} on {target_date}.")
                summary["missing_source"] += 1
                try:
                    notify(
                        title="TickStream missing source",
                        body=(
                            f"Binance Vision file not yet available for "
                            f"{symbol} on {target_date.isoformat()}. "
                            f"Run id: {log.run_id}."
                        ),
                        tags="warning",
                    )
                except Exception as ne:
                    log.info(f"Alert send failed for missing-source: {ne}")
                continue

            log.info("Downloading and hashing in memory...")
            data, sha256 = download(target)
            mib = len(data) / (1024 * 1024)
            log.info(f"Downloaded {mib:.1f} MiB. sha256 prefix: {sha256[:12]}")

            prior = state.get(symbol, {})
            if prior.get("sha256") == sha256:
                log.info(
                    f"Hash unchanged since {prior.get('date')} "
                    f"(prior ingest at {prior.get('ingested_at')}). Skipping."
                )
                summary["skipped_unchanged"] += 1
                continue

            blob_path = (
                f"raw/symbol={symbol}/batch_date={target_date.isoformat()}/"
                f"{target.filename}"
            )
            log.info(f"Uploading raw zip to az://{container}/{blob_path}")
            _upload_raw_zip(storage_account, storage_key, container, blob_path, data)

            log.info("Parsing CSV from zip...")
            df = _parse_csv_from_zip(data)
            n_rows = len(df)
            n_cols = len(df.columns)
            log.info(f"Parsed {n_rows:,} rows, {n_cols} columns")

            now_iso = datetime.now(timezone.utc).isoformat()
            df["symbol"] = symbol
            df["batch_date"] = target_date.isoformat()
            df["_source_file_name"] = target.filename
            df["_source_file_sha256"] = sha256
            df["_pipeline_run_id"] = log.run_id
            df["_ingested_at"] = now_iso

            # Upload a parquet copy of the parsed Bronze data to the UC Volume.
            # This is what Silver on Free Edition Serverless reads, since that
            # tier cannot directly access our ADLS Gen2 via shared key (the
            # fs.azure.* spark configs are denylisted on Spark Connect).
            databricks_host = os.environ.get("DATABRICKS_HOST", "").rstrip("/")
            databricks_token = os.environ.get("DATABRICKS_TOKEN", "")
            if databricks_host and databricks_token:
                volume_path = (
                    f"/Volumes/workspace/default/tickstream_bronze"
                    f"/symbol={symbol}/batch_date={target_date.isoformat()}"
                    f"/agg_trades.parquet"
                )
                log.info(f"Uploading parquet copy to UC Volume {volume_path}")
                # Drop the hive-partition columns since they live in the path,
                # so Spark partition discovery on read does not clash.
                parquet_df = df.drop(columns=["symbol", "batch_date"])
                parquet_buf = BytesIO()
                parquet_df.to_parquet(parquet_buf, index=False, compression="snappy")
                _upload_to_volume(databricks_host, databricks_token, volume_path, parquet_buf.getvalue())
                log.info(f"Volume upload done ({len(parquet_buf.getvalue()) / (1024 * 1024):.1f} MiB)")
            else:
                log.info("DATABRICKS_HOST/TOKEN not set, skipping UC Volume upload")

            delta_path = "delta/bronze_agg_trades"
            log.info(
                f"Writing Bronze Delta to az://{container}/{delta_path} "
                f"(append, partitioned by symbol+batch_date)"
            )
            _write_bronze_delta(storage_account, storage_key, container, delta_path, df)

            state[symbol] = {
                "date": target_date.isoformat(),
                "sha256": sha256,
                "ingested_at": now_iso,
            }
            summary["processed"] += 1
            log.info(f"{symbol} done.")
        except Exception as e:
            summary["errors"] += 1
            log.info(f"ERROR processing {symbol}: {type(e).__name__}: {e}")
            try:
                notify(
                    title="TickStream Bronze error",
                    body=(
                        f"Symbol {symbol} on {target_date.isoformat()} failed: "
                        f"{type(e).__name__}: {e}. Run id: {log.run_id}."
                    ),
                    tags="rotating_light",
                )
            except Exception as ne:
                log.info(f"Alert send failed for error: {ne}")

    # Persist state regardless of outcome so partial progress is captured.
    save_state(state)

    summary_text = (
        f"processed={summary['processed']}, "
        f"skipped_unchanged={summary['skipped_unchanged']}, "
        f"missing_source={summary['missing_source']}, "
        f"errors={summary['errors']}"
    )

    if summary["errors"] > 0 and summary["processed"] == 0 and summary["skipped_unchanged"] == 0:
        status = "FAILED"
    elif summary["errors"] > 0:
        status = "PARTIAL"
    elif summary["processed"] == 0 and summary["missing_source"] == len(symbols):
        status = "WAITING_SOURCE"
    elif summary["processed"] == 0:
        status = "SKIPPED"
    else:
        status = "SUCCESS"

    log_path = log.finalise(status, summary_text)
    print(f"\nRun log written to {log_path}")
    return 0 if status != "FAILED" else 1


if __name__ == "__main__":
    sys.exit(main())
