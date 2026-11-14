"""NASA EONET (Earth Observatory Natural Event Tracker): natural events near a
place, as context for unusual years (wildfire smoke, storms, floods).
EONET's archive is sparse before about 2016, so absence proves nothing.

AI-use note: drafted with Claude (Anthropic) during the hackathon.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import httpx

CACHE = Path(__file__).resolve().parents[2] / "data" / "cache"
URL = "https://eonet.gsfc.nasa.gov/api/v3/events"


def nearby(box: list[float], pad: float = 3.0) -> dict:
    la0, la1 = max(box[0] - pad, -90), min(box[1] + pad, 90)
    lo0, lo1 = max(box[2] - pad, -180), min(box[3] + pad, 180)
    f = CACHE / f"eonet_{la0:.1f}_{la1:.1f}_{lo0:.1f}_{lo1:.1f}.json"
    if f.exists():
        d = json.loads(f.read_text())
    else:
        r = httpx.get(URL, params={"bbox": f"{lo0},{la1},{lo1},{la0}", "status": "all",
                                   "start": "1981-01-01", "end": "2025-12-31", "limit": 1000}, timeout=60)
        r.raise_for_status()
        d = r.json()
        f.write_text(json.dumps(d))
    ev = []
    for e in d.get("events", []):
        g = e.get("geometry") or [{}]
        ev.append({"title": e.get("title"), "category": (e.get("categories") or [{}])[0].get("title"),
                   "date": (g[0].get("date") or "")[:10], "link": e.get("link")})
    ev.sort(key=lambda x: x["date"], reverse=True)
    by = Counter((x["category"], x["date"][:4]) for x in ev)
    summary = [{"category": c, "year": int(y), "count": n} for (c, y), n in sorted(by.items(), key=lambda k: (k[0][1], k[0][0]))]
    head = (f"{len(ev)} natural events logged by NASA EONET within about {int(pad * 111)} km "
            f"(mostly since 2016: EONET's older archive is sparse)." if ev else
            "No natural events logged by NASA EONET near here.")
    return {"n_events": len(ev), "by_year": summary, "latest": ev[:15], "headline": head,
            "source": "NASA Earth Observatory Natural Event Tracker (EONET v3)"}
