"""Silver aggTrades data contract.

The shape Silver guarantees to downstream consumers (dbt Gold models,
ad-hoc analysts). This is a stricter contract than Bronze: types are
real, the validity flag is mandatory, and the natural key is enforced.
"""
from __future__ import annotations

from datetime import date as Date, datetime
from decimal import Decimal
from typing import Optional

try:
    from pydantic import BaseModel, Field
except ImportError:
    BaseModel = object  # type: ignore[assignment, misc]

    def Field(*args, **kwargs):  # type: ignore[no-redef]
        return None


class SilverAggTrade(BaseModel):
    """A single row as Silver writes it.

    Natural key: (symbol, batch_date, agg_trade_id).
    """

    # Core (typed)
    agg_trade_id: int
    price: Decimal
    quantity: Decimal
    first_trade_id: int
    last_trade_id: int
    transact_time: datetime
    is_buyer_maker: bool
    is_best_match: Optional[bool] = None

    # Partition / dimension
    symbol: str = Field(..., pattern=r"^[A-Z0-9]+$")
    batch_date: Date

    # Validation
    is_valid: bool

    # Carried-forward Bronze audit
    source_file_name: str = Field(..., alias="_source_file_name")
    source_file_sha256: str = Field(..., alias="_source_file_sha256")
    pipeline_run_id: str = Field(..., alias="_pipeline_run_id")
    ingested_at: datetime = Field(..., alias="_ingested_at")

    # Silver audit
    silver_at: datetime = Field(..., alias="_silver_at")
    silver_run_id: str = Field(..., alias="_silver_run_id")
