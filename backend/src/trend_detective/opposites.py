"""'Opposite-direction places': where on land a variable is proven to rise, and where it is proven to fall.

Built from the globe dataset (data/globe_<VAR>.json, scripts/globe_grid.py). Only cells our
test proves (strong / some) AND that survive the false-discovery check are used. Examples are
the steepest such cells, kept at least ~15° apart so they come from different regions, and
labelled with the largest town inside the cell (GeoNames) when there is one.

This answers the brief's "one region up, another down" directly; the compare tool
(/api/compare) then tests any pair properly.

AI-use note: drafted with Claude (Anthropic) during the hackathon.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from . import places

DATA = Path(__file__).resolve().parents[2] / "data"
SITE_CASE = "#/case?var={var}&box={la0},{la1},{lo0},{lo1}"


@lru_cache(maxsize=8)
def _globe(var: str) -> dict | None:
    p = DATA / f"globe_{var}.json"
    return json.loads(p.read_text()) if p.exists() else None


def _far(c, chosen, min_deg=15.0):
    return all(abs(c[0] - d[0]) >= min_deg or abs(c[1] - d[1]) >= min_deg for d in chosen)


def _example(c, var, units):
    lat, lon, slope, _ = c
    box = [lat - 1.0, lat + 1.0, lon - 1.25, lon + 1.25]
    near = places.search_box(box, limit=1)
    name = f"{near[0]['name']}, {near[0]['country']}" if near else f"{abs(lat):.0f}°{'N' if lat >= 0 else 'S'} {abs(lon):.1f}°{'E' if lon >= 0 else 'W'}"
    return {"name": name, "lat": lat, "lon": lon, "slope_per_decade": slope, "units": units,
            "case": SITE_CASE.format(var=var, la0=box[0], la1=box[1], lo0=box[2], lo1=box[3])}


def opposites(var: str, n: int = 5) -> dict | None:
    g = _globe(var)
    if g is None:
        return None
    land = [c for c in g["cells"] if "L" in c[3] and c[3][0] in "Ss" and "f" in c[3]]
    up = sorted((c for c in land if c[2] > 0), key=lambda c: -c[2])
    down = sorted((c for c in land if c[2] < 0), key=lambda c: c[2])
    pick = {}
    for key, cells in (("rising", up), ("falling", down)):
        chosen = []
        for c in cells:
            if _far(c, chosen):
                chosen.append(c)
            if len(chosen) >= n:
                break
        pick[key] = [_example(c, var, g["units"]) for c in chosen]
    n_land = sum("L" in c[3] for c in g["cells"])
    pct = lambda k: round(100 * k / n_land) if n_land else 0  # noqa: E731
    head = (f"On land, {len(up):,} places ({pct(len(up))}%) are proven to be rising and {len(down):,} ({pct(len(down))}%) "
            f"proven to be falling, out of {n_land:,}. ")
    if pick["rising"] and pick["falling"]:
        head += (f"Steepest rise: near {pick['rising'][0]['name']}; steepest fall: near {pick['falling'][0]['name']}. "
                 "Open the compare tool to test any pair.")
    elif not down:
        head += "Nowhere on land is it proven to be falling."
    return {"variable": var, "period": g["period"], "source": g["source"], "n_land_cells": n_land,
            "n_rising": len(up), "n_falling": len(down), "headline": head, **pick,
            "method": "Cells proven by our test (Hamed-Rao Mann-Kendall + OLS with effective sample size) that also "
                      "survive the false-discovery check; examples are the steepest, at least 15° apart."}
