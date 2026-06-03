"""Delete pipeline run logs older than the retention window.

Retention is read from config/pipeline.yml -> retention.pipeline_log_days.
Default is 50 days. Files in logs/runs/ whose filename starts with a date
older than the cutoff are deleted.

Filename convention is YYYYMMDD_HHMMSS_<id>.log (set by RunLogger). We parse
the YYYYMMDD prefix to make the date decision so we do not depend on the
file's mtime, which is unreliable across git commits.
"""
from __future__ import annotations

import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from pipeline.common.config import REPO_ROOT, load_config

LOGS_DIR = REPO_ROOT / "logs" / "runs"
DATE_RX = re.compile(r"^(\d{8})_")  # captures the YYYYMMDD prefix of the filename


def main() -> int:
    cfg = load_config()
    retention_days = int(cfg["retention"]["pipeline_log_days"])
    cutoff = (datetime.now(timezone.utc) - timedelta(days=retention_days)).date()

    if not LOGS_DIR.exists():
        print(f"logs dir does not exist: {LOGS_DIR}")
        return 0

    deleted = 0
    kept = 0
    skipped = 0
    for p in sorted(LOGS_DIR.glob("*.log")):
        m = DATE_RX.match(p.name)
        if not m:
            skipped += 1
            continue
        file_date_str = m.group(1)
        try:
            file_date = datetime.strptime(file_date_str, "%Y%m%d").date()
        except ValueError:
            skipped += 1
            continue
        if file_date < cutoff:
            p.unlink()
            deleted += 1
        else:
            kept += 1

    print(f"Retention: {retention_days} days (cutoff date {cutoff.isoformat()})")
    print(f"Deleted:   {deleted}")
    print(f"Kept:      {kept}")
    print(f"Skipped:   {skipped} (filenames not matching YYYYMMDD_ pattern)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
