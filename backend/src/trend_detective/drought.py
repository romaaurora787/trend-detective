"""Drought months from NASA rainfall: the Standardized Precipitation Index (SPI).

SPI (McKee, Doesken & Kleist 1993; WMO-No. 1090, 2012) turns rain over the past
3 (or 12) months into "how unusual is this for this place and this time of year":
a gamma distribution is fitted to each calendar month's totals over the
1981–2010 baseline and mapped to a standard normal. SPI ≤ −1 is moderate
drought, ≤ −1.5 severe, ≤ −2 extreme.

We count drought months per year and test the counts for a trend (Yue–Wang
Mann–Kendall + Sen), and also test the SPI series itself.

AI-use note: drafted with Claude (Anthropic) during the hackathon.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pymannkendall as mk
from scipy import stats as sps

from . import power, stats

BASE = (1981, 2010)


def spi(rain_mm_day: pd.Series, scale: int = 3) -> pd.Series:
    """SPI at `scale` months from a monthly mean-rate series (mm/day)."""
    r = rain_mm_day.dropna().sort_index()
    total = r * r.index.days_in_month  # mm in the month
    acc = total.rolling(scale).sum().dropna()
    out = pd.Series(np.nan, index=acc.index)
    base = (acc.index.year >= BASE[0]) & (acc.index.year <= BASE[1])
    for m in range(1, 13):
        sel = acc.index.month == m
        ref = acc[sel & base].to_numpy()
        pos = ref[ref > 0]
        q0 = 1 - len(pos) / max(len(ref), 1)  # chance of a completely dry spell
        if len(pos) < 10:
            continue
        a, loc, b = sps.gamma.fit(pos, floc=0)
        x = acc[sel].to_numpy()
        cdf = q0 + (1 - q0) * sps.gamma.cdf(x, a, loc=0, scale=b)
        cdf = np.clip(cdf, 1e-6, 1 - 1e-6)
        out[sel] = sps.norm.ppf(cdf)
    return out.dropna()


def report(box: list[float]) -> dict:
    rain, n_cells = power.fetch_area_series("PRECTOTCORR", *box)
    s3, s12 = spi(rain, 3), spi(rain, 12)
    years = sorted(set(s3.index.year))
    yrs = [y for y in years if (s3.index.year == y).sum() >= 10]
    count = lambda thr: pd.Series([int((s3[s3.index.year == y] <= thr).sum()) for y in yrs], index=yrs, dtype=float)
    out = []
    for key, label, thr in [("drought_months", "Drought months (SPI-3 ≤ −1)", -1.0),
                            ("severe_months", "Severe drought months (SPI-3 ≤ −1.5)", -1.5)]:
        c = count(thr)
        r = mk.yue_wang_modification_test(c.to_numpy(), lag=1)
        early, late = float(c.loc[1981:1990].mean()), float(c.iloc[-10:].mean())
        proven = r.p < stats.ALPHA
        word = "more" if r.slope > 0 else "fewer"
        msg = (f"{label}: {word} over time ({r.slope * 10:+.2f} a year per decade, p = {r.p:.2g}); 1980s {early:.1f} a year, last 10 years {late:.1f}."
               if proven else f"{label}: no proven change (1980s {early:.1f} a year, last 10 years {late:.1f}).")
        out.append({"id": key, "name": label, "slope_per_decade": float(r.slope * 10), "p": float(r.p), "proven": bool(proven),
                    "mean_1980s": early, "mean_last10": late, "years": [int(y) for y in c.index],
                    "counts": [int(v) for v in c.to_numpy()], "headline": msg})
    a12 = stats.analyse(s12, "SPI")
    worst = s12.idxmin()
    return {"box": box, "n_cells": n_cells, "indices": out,
            "spi12": {"dates": [d.strftime("%Y-%m") for d in s12.index], "values": s12.round(3).tolist(),
                      "trend_headline": a12["verdict"]["headline"], "label": a12["verdict"]["label"],
                      "slope_per_decade": a12["sen_slope_per_decade"],
                      "driest": {"month": worst.strftime("%Y-%m"), "spi": float(s12.min())}},
            "headline": (" ".join(o["headline"] for o in out[:1])
                         + f" Driest 12 months on record ended {worst.strftime('%b %Y')} (SPI-12 = {s12.min():.1f})."),
            "source": "NASA POWER PRECTOTCORR (MERRA-2, gauge-corrected), area mean",
            "method": "SPI (McKee et al. 1993; WMO 2012): gamma fit per calendar month, baseline 1981–2010; "
                      "drought months per year tested with Yue–Wang Mann–Kendall + Sen."}
