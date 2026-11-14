"""NASA GISTEMP v4 global temperature: how does this place compare with the planet?

AI-use note: drafted with Claude (Anthropic) during the hackathon.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import pandas as pd

from . import stats

PATH = Path(__file__).resolve().parents[2] / "data" / "external" / "gistemp_GLB.Ts+dSST.csv"
TEMPERATURE_VARS = {"T2M", "T2M_MAX", "T2M_MIN", "TS", "T2MDEW"}


@lru_cache(maxsize=1)
def gistemp() -> pd.Series:
    df = pd.read_csv(PATH, skiprows=1, na_values="***")
    rows = []
    for _, r in df.iterrows():
        for m, mon in enumerate(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1):
            if pd.notna(r[mon]):
                rows.append((pd.Timestamp(int(r["Year"]), m, 1), float(r[mon])))
    return pd.Series(dict(rows)).sort_index()


@lru_cache(maxsize=8)
def global_rate(start: str, end: str) -> dict:
    g = gistemp()
    g = g[(g.index >= start) & (g.index <= end)]
    r = stats.analyse(g, "°C")
    return {"slope_per_decade": r["sen_slope_per_decade"], "ci95": r["sen_ci95_per_decade"],
            "period": f"{start[:4]}–{end[:4]}"}


def vs_world(var: str, place_slope: float, start: str, end: str) -> dict | None:
    if var not in TEMPERATURE_VARS:
        return None
    g = global_rate(start[:7] + "-01", end[:7] + "-01")
    ratio = place_slope / g["slope_per_decade"] if g["slope_per_decade"] else None
    if ratio is None:
        return None
    if ratio >= 1.2:
        txt = f"Warming {ratio:.1f}× as fast as the planet as a whole ({g['slope_per_decade']:+.2f} °C/decade, NASA GISTEMP)."
    elif ratio >= 0.8:
        txt = f"Warming at about the planet's rate ({g['slope_per_decade']:+.2f} °C/decade, NASA GISTEMP)."
    elif ratio > 0:
        txt = f"Warming more slowly than the planet ({ratio:.1f}× the global {g['slope_per_decade']:+.2f} °C/decade)."
    else:
        txt = f"Not following the planet: the world warmed {g['slope_per_decade']:+.2f} °C/decade (NASA GISTEMP)."
    note = "Land warms faster than the ocean-inclusive global mean, so most land places run above 1×."
    return {"global": g, "ratio": ratio, "headline": txt, "note": note,
            "source": "NASA GISS Surface Temperature Analysis (GISTEMP v4), land + ocean"}
