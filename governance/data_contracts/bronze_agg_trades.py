"""Bronze aggTrades data contract.

The shape Bronze is supposed to write before Silver consumes it. Lives here
in version control so a PR that changes Bronze's output schema has to also
change this contract, making the change explicit and reviewable.

To use in tests:

    from governance.data_contracts.bronze_agg_trades import BronzeAggTrade
    import json
    sample = json.loads(open("tests/fixtures/sample_bronze_row.json").read())
    BronzeAggTrade(**sample)   # raises if shape drifted

In a future polish phase the Bronze ingester will call this on a sample
row at write time and fail the run if the contract is violated.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

try:
    from pydantic import BaseModel, Field, field_validator
except ImportError:
    # Pydantic is not a runtime dependency of the pipeline; the contract is
    # for use in tests and PR reviews. Fall back gracefully if pydantic
    # is not installed.
    BaseModel = object  # type: ignore[assignment, misc]

    def Field(*args, **kwargs):  # type: ignore[no-redef]
        return None

    def field_validator(*args, **kwargs):  # type: ignore[no-redef]
        def deco(f):
            return f
        return deco


class BronzeAggTrade(BaseModel):
    """A single row as Bronze writes it.

    Bronze keeps everything as string to preserve source fidelity. The
    audit columns are mandatory and prefixed with underscore.
    """

    # Source columns (all string in Bronze)
    agg_trade_id: str = Field(..., min_length=1)
    price: str = Field(..., min_length=1)
    quantity: str = Field(..., min_length=1)
    first_trade_id: str = Field(..., min_length=1)
    last_trade_id: str = Field(..., min_length=1)
    transact_time: str = Field(..., min_length=1)
    is_buyer_maker: str
    is_best_match: Optional[str] = None

    # Hive partition columns
    symbol: str = Field(..., pattern=r"^[A-Z0-9]+$")
    batch_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")

    # Audit
    source_file_name: str = Field(..., alias="_source_file_name", min_length=1)
    source_file_sha256: str = Field(..., alias="_source_file_sha256", min_length=64, max_length=64)
    pipeline_run_id: str = Field(..., alias="_pipeline_run_id", min_length=1)
    ingested_at: str = Field(..., alias="_ingested_at", min_length=1)

    @field_validator("ingested_at")
    @classmethod
    def _ingested_at_is_iso(cls, v: str) -> str:
        # Will raise ValueError if not parseable
        datetime.fromisoformat(v.replace("Z", "+00:00"))
        return v
