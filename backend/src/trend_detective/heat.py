"""Extreme-day counts from NASA POWER DAILY data (MERRA-2), per year:

  hot_days        days hotter than this place's own 1-in-10 day (90th percentile
                  of daily highs for that calendar month, 1981–2010)
  very_hot_days   days with a high of 35 °C or more
  tropical_nights nights that stay at 20 °C or above
  humid_heat      days with a daily-mean wet-bulb temperature of 25 °C or more
                  (heat the body struggles to shed by sweating)
  frost_nights    nights below 0 °C
  cold_days       days colder than this place's own 1-in-10 cold day (10th pct of daily lows)

Each yearly count is tested with the Yue–Wang modified Mann–Kendall test and
Sen's slope. A count that is almost always zero here is reported as "rare here".

AI-use note: drafted with Claude (Anthropic) during the hackathon.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pymannkendall as mk

from . import power

INDICES = {
    "hot_days": "Days hotter than the local 1-in-10 day",
    "very_hot_days": "Days of 35 °C or more",
    "tropical_nights": "Nights that stay at 20 °C or above",
    "humid_heat": "Humid-heat days (wet-bulb 25 °C or more)",
    "frost_nights": "Frost nights (below 0 °C)",
    "cold_days": "Days colder than the local 1-in-10 cold day",
}


def counts(df: pd.DataFrame) -> pd.DataFrame:
    tx, tn, wb = df["T2M_MAX"], df["T2M_MIN"], df["T2MWET"]
    base = (df.index.year >= 1981) & (df.index.year <= 2010)
    p90 = tx[base].groupby(tx[base].index.month).quantile(0.9)
    p10 = tn[base].groupby(tn[base].index.month).quantile(0.1)
    m = df.index.month
    flags = pd.DataFrame({
        "hot_days": tx > p90.reindex(m).to_numpy(),
        "very_hot_days": tx >= 35,
        "tropical_nights": tn >= 20,
        "humid_heat": wb >= 25,
        "frost_nights": tn < 0,
        "cold_days": tn < p10.reindex(m).to_numpy(),
    }, index=df.index)
    ok = df.notna().all(axis=1)
    flags = flags[ok]
    yearly = flags.groupby(flags.index.year).sum()
    n_days = ok.groupby(ok.index.year).sum()
    return yearly[n_days >= 330]


def heat_report(lat: float, lon: float) -> dict:
    df = power.fetch_daily_point(["T2M_MAX", "T2M_MIN", "T2MWET"], lat, lon)
    y = counts(df)
    out = []
    for k, label in INDICES.items():
        s = y[k].astype(float)
        if (s > 0).mean() < 0.3 or s.mean() < 1:
            out.append({"id": k, "name": label, "rare": True, "mean_per_year": float(s.mean()),
                        "headline": f"{label}: rare here (about {s.mean():.1f} a year)."})
            continue
        r = mk.yue_wang_modification_test(s.to_numpy(), lag=1)
        slope = float(r.slope * 10)
        early = float(s[(s.index >= 1981) & (s.index <= 1990)].mean())
        late = float(s[s.index >= s.index[-1] - 9].mean())
        proven = r.p < 0.05
        word = "more" if slope > 0 else "fewer"
        if proven:
            msg = f"{label}: {word} each decade ({slope:+.1f} a year per decade, p = {r.p:.2g}). 1980s: {early:.0f} a year; last 10 years: {late:.0f}."
        else:
            msg = f"{label}: no proven change (1980s {early:.0f} a year, last 10 years {late:.0f})."
        out.append({"id": k, "name": label, "rare": False, "slope_per_decade": slope, "p": float(r.p),
                    "proven": bool(proven), "mean_1980s": early, "mean_last10": late,
                    "years": [int(i) for i in s.index], "counts": [int(v) for v in s.to_numpy()], "headline": msg})
    proven = [o for o in out if o.get("proven")]
    head = (f"{len(proven)} of {len([o for o in out if not o['rare']])} extreme-day counts show a proven change here."
            if out else "No daily data.")
    return {"lat": lat, "lon": lon, "indices": out, "headline": head,
            "source": "NASA POWER daily (MERRA-2), point at the place's centre, 1981–2025",
            "method": "Yearly counts; Yue–Wang modified Mann–Kendall + Sen's slope; local thresholds from 1981–2010"}
