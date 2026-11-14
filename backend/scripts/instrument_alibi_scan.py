"""Instrument-alibi scan (research, Sat 14 Nov). NASA POWER sunshine and cloud switch
source in 2001 (GEWEX SRB R4 1984-2000 -> CERES SYN1deg 2001-). Does a step at the
switch explain the world-report "trends" better than a trend? Placebo: other years, and
T2M (no switch). Then re-test on the single-source 2001-2025 record.
Run from backend/: uv run python scripts/instrument_alibi_scan.py

AI-use note: drafted with Claude (Anthropic) during the hackathon.
"""
import json, warnings
from pathlib import Path
import numpy as np
from trend_detective import power, stats
warnings.filterwarnings("ignore")
DATA = Path("data")
W = json.loads((DATA / "world_report.json").read_text())
pts = [(p["lat"], p["lon"]) for p in W["points"]]
labels = {v["id"]: v["cells"] for v in W["variables"]}

def annual(s):
    a = stats.deseasonalise(s)[0]
    g = a.groupby(a.index.year)
    m = g.mean()[g.count() == 12]
    return m.index.values.astype(float), m.values

def bic(y, X):
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    rss = float(((y - X @ beta) ** 2).sum()); n = len(y)
    return n * np.log(rss / n) + X.shape[1] * np.log(n), beta

def run(var, year):
    n_proven = n_step_better = n_seg_flip = 0
    for (lat, lon), c in zip(pts, labels[var]):
        if not c or c["label"] not in ("strong", "some"):
            continue
        s = power.fetch_point(var, lat, lon).dropna()
        t, y = annual(s)
        one = np.ones_like(t); st = (t >= year).astype(float); tt = t - t.mean()
        bT, _ = bic(y, np.c_[one, tt]); bS, _ = bic(y, np.c_[one, st])
        n_proven += 1
        if bS < bT: n_step_better += 1
        # trend within each segment
        pre, post = t < year, t >= year
        sp = np.polyfit(t[pre], y[pre], 1)[0]; sq = np.polyfit(t[post], y[post], 1)[0]
        if np.sign(sp) != np.sign(c["slope"]) and np.sign(sq) != np.sign(c["slope"]): n_seg_flip += 1
    return n_proven, n_step_better, n_seg_flip

def part1():
  for var in ["ALLSKY_SFC_SW_DWN", "CLOUD_AMT", "T2M", "PRECTOTCORR"]:
      for yr in [1993, 1997, 2001, 2005, 2009]:
          n, sb, fl = run(var, yr)
          print(f"{var:18s} step@{yr}: proven {n:3d} | step explains better than trend {sb:3d} ({sb/max(n,1):.0%}) | trend gone within both segments {fl}", flush=True)
def part2():
  for var, units in [("CLOUD_AMT", "%"), ("ALLSKY_SFC_SW_DWN", "kW-hr/m^2/day")]:
      full = both = flip = new = n = up = dn = 0
      for (lat, lon), c in zip(pts, labels[var]):
          s = power.fetch_point(var, lat, lon).dropna()
          s2 = s[s.index.year >= 2001]
          if len(s2) < 120: continue
          r = stats.analyse(s2, units); n += 1
          p2 = r["verdict"]["label"] in ("strong", "some")
          p1 = bool(c) and c["label"] in ("strong", "some")
          full += p1; new += p2 and not p1; both += p1 and p2
          if p2: up += r["sen_slope_per_decade"] > 0; dn += r["sen_slope_per_decade"] < 0
          if p1 and p2 and (r["sen_slope_per_decade"] > 0) != (c["slope"] > 0): flip += 1
      print(f"{var}: points {n} | proven 1984-2025 {full} | proven CERES-only 2001-2025 {both+new} ({up} up, {dn} down) | survive {both} | direction flips {flip}")


if __name__ == "__main__":
    part1()
    part2()
