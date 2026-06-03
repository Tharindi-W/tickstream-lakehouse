"""Read and write state/last_seen_hashes.json.

State shape:
{
  "BTCUSDT": {"date": "2026-06-02", "sha256": "...", "ingested_at": "..."},
  "ETHUSDT": {...},
  ...
}

Used by Bronze ingestion to skip files whose content is unchanged since the
last successful ingestion. The file is committed back to the repo by the
GitHub Actions workflow so the next hourly run sees the latest state.
"""
from __future__ import annotations

import json
from pathlib import Path

from pipeline.common.config import REPO_ROOT

STATE_PATH = REPO_ROOT / "state" / "last_seen_hashes.json"


def load_state() -> dict[str, dict]:
    if not STATE_PATH.exists():
        return {}
    with STATE_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_state(state: dict[str, dict]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with STATE_PATH.open("w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, sort_keys=True)
        f.write("\n")
