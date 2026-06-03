"""Download daily aggTrades from Binance Vision public archive.

Binance Vision publishes one zip file per symbol per day at:
    https://data.binance.vision/data/spot/daily/aggTrades/<SYMBOL>/<SYMBOL>-aggTrades-<YYYY-MM-DD>.zip

No auth, no rate limit, free forever. Files are usually available a few minutes
after UTC midnight for the previous day.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date as Date
from io import BytesIO

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

BASE_URL = "https://data.binance.vision/data/spot/daily/aggTrades"
USER_AGENT = "tickstream-lakehouse/0.1 (+https://github.com/Tharindi-W/tickstream-lakehouse)"


@dataclass(frozen=True)
class DailyFile:
    symbol: str
    date: Date

    @property
    def filename(self) -> str:
        return f"{self.symbol}-aggTrades-{self.date.isoformat()}.zip"

    @property
    def url(self) -> str:
        return f"{BASE_URL}/{self.symbol}/{self.filename}"


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=15),
    reraise=True,
)
def head_check(target: DailyFile) -> bool:
    """Return True if the file exists, False on 404, raises on other errors."""
    r = requests.head(
        target.url,
        timeout=15,
        allow_redirects=True,
        headers={"User-Agent": USER_AGENT},
    )
    if r.status_code == 200:
        return True
    if r.status_code == 404:
        return False
    r.raise_for_status()
    return False  # unreachable


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=4, max=30),
    reraise=True,
)
def download(target: DailyFile) -> tuple[bytes, str]:
    """Download the zip file fully into memory. Returns (bytes, sha256_hex)."""
    r = requests.get(
        target.url,
        timeout=300,
        stream=True,
        headers={"User-Agent": USER_AGENT},
    )
    r.raise_for_status()
    buf = BytesIO()
    h = hashlib.sha256()
    for chunk in r.iter_content(chunk_size=1 << 20):  # 1 MiB
        if not chunk:
            continue
        buf.write(chunk)
        h.update(chunk)
    return buf.getvalue(), h.hexdigest()
