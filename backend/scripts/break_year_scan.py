"""Is there a worldwide jump in NASA POWER rain / evaporation / soil moisture around 1998-99?

Prompted by a break detector elsewhere that found a 1999 jump in
rain, evaporation and soil moisture. A real data-source jump shows up as many places
across the world preferring the SAME break year; climate does not do that. For each of the
111 world-report places and each variable:
  - yearly anomalies 1981-2025 (complete years only)
  - best single break year (1986-2020, at least 5 years each side): the year that minimises
    the residual sum of squares of a "two flat levels" model (like Pettitt, but by least squares)
  - whether that step beats a straight-line trend by BIC (the same rule as our instrument check)
T2M, which has no known source change, is the control. Output: data/break_year_scan.json

Run from backend/: uv run python scripts/break_year_scan.py

AI-use note: drafted with Claude (Anthropic) during the hackathon.
"""
import json
import warnings
from collections import Counter
from pathlib import Path

import numpy as np

from trend_detective import power, stats

warnings.filterwarnings("ignore")
DATA = Path(__file__).resolve().parents[1] / "data"
W = json.loads((DATA / "world_report.json").read_text())
PTS = [(p["lat"], p["lon"]) for p in W["points"]]
VARS = ["T2M", "QV2M", "PRECTOTCORR", "EVLAND", "GWETTOP", "GWETROOT"]
YEARS = range(1986, 2021)


def annual(s):
    a = stats.deseasonalise(s.dropna())[0]
    g = a.groupby(a.index.year)
    m = g.mean()[g.count() == 12]
    return m.index.values.astype(float), m.values


def bic(rss, n, k):
    return n * np.log(rss / n) + k * np.log(n)


def best_break(t, y):
    best = None
    for yr in YEARS:
        a, b = y[t < yr], y[t >= yr]
        if len(a) < 5 or len(b) < 5:
            continue
        rss = ((a - a.mean()) ** 2).sum() + ((b - b.mean()) ** 2).sum()
        if best is None or rss < best[1]:
            best = (yr, rss, b.mean() - a.mean())
    return best


out = {}
for var in VARS:
    years, step_wins, rows = [], [], []
    for lat, lon in PTS:
        try:
            t, y = annual(power.fetch_point(var, lat, lon))
        except Exception:
            continue
        if len(y) < 30 or np.std(y) == 0:
            continue
        yr, rss_step, jump = best_break(t, y)
        tt = t - t.mean()
        coef = np.polyfit(tt, y, 1)
        rss_trend = ((y - np.polyval(coef, tt)) ** 2).sum()
        wins = bic(rss_step, len(y), 3) < bic(rss_trend, len(y), 2)  # step has 3 params (2 levels + year)
        years.append(yr)
        step_wins.append(wins)
        rows.append({"lat": lat, "lon": lon, "year": yr, "jump_sd": float(jump / np.std(y)), "step_beats_trend": bool(wins)})
    c = Counter(years)
    n = len(years)
    near = sum(c[y] for y in (1997, 1998, 1999))
    near_w = sum(r["step_beats_trend"] for r in rows if r["year"] in (1997, 1998, 1999))
    expected = n * 3 / len(YEARS)  # if break years were spread evenly
    out[var] = {"n": n, "top_years": c.most_common(5), "in_1997_99": near, "expected_if_random": round(expected, 1),
                "in_1997_99_and_step_beats_trend": near_w, "step_beats_trend_any_year": int(sum(step_wins)), "places": rows}
    print(f"{var:12s} n={n:3d}  top break years {c.most_common(4)}  | 1997-99: {near} (random ~{expected:.0f}), "
          f"{near_w} of them where a step beats a trend", flush=True)
(DATA / "break_year_scan.json").write_text(json.dumps(out, indent=1))
