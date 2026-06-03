"""Generic alert sender. POSTs to a webhook URL stored in env var ALERT_WEBHOOK_URL.

Currently the webhook is ntfy.sh. The payload shape used here works for ntfy
and is mostly ignored by Discord-style endpoints, which would need a JSON body.
When we add a second provider, switch on `ALERT_PROVIDER`.
"""
from __future__ import annotations

import os

import requests
from tenacity import retry, stop_after_attempt, wait_exponential


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
)
def notify(title: str, body: str, tags: str = "warning") -> None:
    url = os.environ.get("ALERT_WEBHOOK_URL")
    if not url:
        raise RuntimeError("ALERT_WEBHOOK_URL is not set; cannot send alert")
    resp = requests.post(
        url,
        headers={"Title": title, "Tags": tags},
        data=body.encode("utf-8"),
        timeout=10,
    )
    resp.raise_for_status()
