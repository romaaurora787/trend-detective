"""World place search (GeoNames cities15000, CC BY 4.0): every city and town
with more than 15,000 people. Offline: no external geocoding service.

AI-use note: drafted with Claude (Anthropic) during the hackathon.
"""

from __future__ import annotations

import gzip
import json
import unicodedata
from functools import lru_cache
from pathlib import Path

PATH = Path(__file__).resolve().parents[2] / "data" / "places.json.gz"
HALF_BOX = 0.75  # degrees: a city gets a 1.5 x 1.5 degree box (~3-6 NASA cells)


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return " ".join(s.casefold().replace("-", " ").split())


@lru_cache(maxsize=1)
def _rows():
    d = json.loads(gzip.open(PATH, "rt", encoding="utf-8").read())
    return [(r, _norm(r[0]), _norm(r[1]), _norm(r[2])) for r in d["rows"]]  # sorted by population


def box_for(lat: float, lon: float, half: float = HALF_BOX) -> list[float]:
    la0, la1 = max(lat - half, -90.0), min(lat + half, 90.0)
    lo0, lo1 = max(lon - half, -180.0), min(lon + half, 180.0)
    return [round(la0, 2), round(la1, 2), round(lo0, 2), round(lo1, 2)]


def search(q: str, limit: int = 8) -> list[dict]:
    """'delhi', 'paris, france', 'san jose costa rica'. Ranked: exact name,
    then name starts with, then a word starts with; ties by population."""
    q = q.strip()
    if len(q) < 2:
        return []
    city_q, _, country_q = q.partition(",")
    cq, kq = _norm(city_q), _norm(country_q)
    hits = []
    for r, n, a, c in _rows():
        if kq and not c.startswith(kq):
            continue
        if n == cq or a == cq:
            rank = 0
        elif n.startswith(cq) or a.startswith(cq):
            rank = 1
        elif any(w.startswith(cq) for w in n.split()) or any(w.startswith(cq) for w in a.split()):
            rank = 2
        else:
            continue
        hits.append((rank, -r[6], r))
        if len(hits) > 400:
            break
    hits.sort(key=lambda h: (h[0], h[1]))
    out = []
    for _, _, r in hits[:limit]:
        name, _, country, region, lat, lon, pop = r
        out.append({"name": name, "country": country, "region": region, "lat": lat, "lon": lon,
                    "population": pop, "label": ", ".join(x for x in (name, region if region != name else "", country) if x),
                    "box": box_for(lat, lon)})
    return out


def search_box(box: list[float], limit: int = 5) -> list[dict]:
    """Largest places inside a box (for 'big city' detection and labels)."""
    out = []
    for r, *_ in _rows():  # already sorted by population, largest first
        name, _, country, region, lat, lon, pop = r
        if box[0] <= lat <= box[1] and box[2] <= lon <= box[3]:
            out.append({"name": name, "country": country, "lat": lat, "lon": lon, "population": pop})
            if len(out) >= limit:
                break
    return out
