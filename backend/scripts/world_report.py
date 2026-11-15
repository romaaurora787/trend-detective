"""World report: run the Detective on every catalogue variable at the 111
global land test points (regular grid, 45S-65N) and compare with a typical
analysis. Writes data/world_report.json (served by /api/world).

AI-use note: drafted with Claude (Anthropic) during the hackathon.
"""
import json
import warnings
from pathlib import Path

import numpy as np

from collections import Counter

from trend_detective import crossexam, power, stats
from trend_detective.catalogue import CATALOGUE

warnings.filterwarnings("ignore")
DATA = Path(__file__).resolve().parents[1] / "data"
rows = json.loads((DATA / "links_regions.json").read_text())["rows"]
points = sorted({(r["lat"], r["lon"]) for r in rows if r["grid"] == "global"})
print(len(points), "land points", flush=True)

out = {"n_points": len(points), "points": [{"lat": a, "lon": b} for a, b in points], "variables": []}
for v in CATALOGUE:
    if v.get("satellite"):  # MODIS greenness is read per box, not on the POWER grid
        continue
    res = []
    for lat, lon in points:
        try:
            s = power.fetch_point(v["id"], lat, lon).dropna()
            if len(s) < 120 or s.value_counts(normalize=True).iloc[0] > 0.9:
                res.append(None)
                continue
            r = stats.analyse(s, v["units"])
            row = {"label": r["verdict"]["label"], "slope": r["sen_slope_per_decade"],
                   "typical_p": r["typical_vs_detective"]["typical_p"], "p_mk": r["mk_hamed_rao"]["p"]}
            if row["label"] in ("strong", "some"):  # instrument alibi on every proven trend
                try:
                    row["alibi"] = crossexam.alibi(v["id"], s, v["units"], lat)["status"]
                except Exception:
                    row["alibi"] = "error"
            res.append(row)
        except Exception as e:
            print("  skip", v["id"], lat, lon, str(e)[:60], flush=True)
            res.append(None)
    ok = [r for r in res if r]
    n = len(ok)
    proven = [r for r in ok if r["label"] in ("strong", "some")]
    typical = [r for r in ok if r["typical_p"] < 0.05]
    fooled = [r for r in ok if r["typical_p"] < 0.05 and r["label"] not in ("strong", "some")]
    rise = sum(r["slope"] > 0 for r in proven)
    fall = sum(r["slope"] < 0 for r in proven)
    # BH across points: how many survive the world-wide multiple-testing correction?
    fdr = stats.fdr([r["p_mk"] for r in ok])
    entry = {"id": v["id"], "name": v["name"], "units": v["units"], "n_points": n,
             "n_proven": len(proven), "n_rising": int(rise), "n_falling": int(fall),
             "n_typical": len(typical), "n_fooled": len(fooled), "n_fdr": int(fdr.sum()),
             "median_slope_proven": float(np.median([r["slope"] for r in proven])) if proven else None,
             "alibi": dict(Counter(r.get("alibi", "no_known_change") for r in proven)),
             "n_proven_after_alibi": sum(r.get("alibi") != "could_be_instrument" for r in proven),
             "cells": [None if r is None else {"label": r["label"], "slope": r["slope"], "alibi": r.get("alibi"),
                                                 "typical": bool(r["typical_p"] < 0.05)}
                       for r in res]}
    out["variables"].append(entry)
    print(f"{v['name']:34s} points {n:3d} | proven {len(proven):3d} ({rise} up, {fall} down) | typical claims {len(typical):3d} | fooled {len(fooled):3d} | alibi {entry['alibi']}", flush=True)
(DATA / "world_report.json").write_text(json.dumps(out, default=float))
print("DONE", flush=True)
