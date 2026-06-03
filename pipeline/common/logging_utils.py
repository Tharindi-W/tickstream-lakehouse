"""Plain-English per-run logger.

One log file per pipeline run is written under logs/runs/. The file name encodes
the run timestamp and a short unique id so it is sortable and grep-able. The
content is written in human-readable Markdown so an operator (or future agent)
can read it cold and understand what happened, in what order, and why.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

from pipeline.common.config import REPO_ROOT

LOGS_DIR = REPO_ROOT / "logs" / "runs"


class RunLogger:
    def __init__(self) -> None:
        now = datetime.now(timezone.utc)
        self.run_id = f"{now:%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:8]}"
        self.started_at = now
        self.lines: list[str] = []
        self.status = "RUNNING"
        self._write_header()

    def _write_header(self) -> None:
        self.lines.append(f"# Pipeline run {self.run_id}")
        self.lines.append("")
        self.lines.append(f"Started at (UTC): {self.started_at.isoformat()}")
        self.lines.append("")

    def section(self, title: str) -> None:
        self.lines.append("")
        self.lines.append(f"## {title}")
        self.lines.append("")
        print(f"\n## {title}\n", flush=True)

    def info(self, msg: str) -> None:
        ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
        line = f"[{ts}] {msg}"
        print(line, flush=True)
        self.lines.append(line)

    def finalise(self, status: str, summary: str = "") -> Path:
        self.status = status
        ended = datetime.now(timezone.utc)
        duration_s = (ended - self.started_at).total_seconds()
        self.lines.append("")
        self.lines.append("## Result")
        self.lines.append("")
        self.lines.append(f"- Status: **{status}**")
        if summary:
            self.lines.append(f"- Summary: {summary}")
        self.lines.append(f"- Ended at (UTC): {ended.isoformat()}")
        self.lines.append(f"- Duration: {duration_s:.1f} seconds")
        self.lines.append("")
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        path = LOGS_DIR / f"{self.run_id}.log"
        path.write_text("\n".join(self.lines), encoding="utf-8")
        return path
