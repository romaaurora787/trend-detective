"""Credentials from backend/.env (git-ignored), loaded into the environment at runtime.

The values are never printed, logged, cached or returned by the API.

AI-use note: drafted with Claude (Anthropic) during the hackathon.
"""

from __future__ import annotations

import os
from pathlib import Path

ENV = Path(__file__).resolve().parents[2] / ".env"


def _load() -> None:
    if not ENV.exists():
        return
    for line in ENV.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def earthdata_token() -> str | None:
    _load()
    return os.environ.get("EARTHDATA_TOKEN") or None


def earthdata_headers() -> dict:
    t = earthdata_token()
    return {"Authorization": f"Bearer {t}"} if t else {}
