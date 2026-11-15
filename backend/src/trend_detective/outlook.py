"""Outlook to 2050: three honest ways to look ahead, each clearly labelled. None is a forecast.

1. "If today's trend keeps going": our proven Sen slope drawn straight on, with its 95% range.
   Refused when the change is one sudden jump (a straight line would be wrong) or not proven.
2. "What climate models expect": 7 CMIP6 HighResMIP models at the place (high-emissions path),
   2041–2050 average vs 2016–2025 (models.py, Open-Meteo Climate API).
3. "If the world's emissions go differently" (pattern scaling): how strongly this place has followed
   global temperature since 1981 (local yearly anomaly regressed on NASA GISTEMP global, standard
   error corrected for year-to-year stickiness), times the extra global warming each IPCC AR6 scenario
   gives for 2041–2060 compared with today. Only offered when that link is proven (p < 0.05).

Global warming for 2041–2060 vs 1850–1900, IPCC AR6 WGI SPM Table SPM.1 (best estimate, very likely
range): SSP1-2.6 1.7 (1.3–2.2), SSP2-4.5 2.0 (1.6–2.5), SSP5-8.5 2.4 (1.9–3.0) °C. "Today" (2016–2025)
is the GISTEMP mean shifted so that 2011–2020 = 1.09 °C above 1850–1900 (AR6 assessed value).

Numbers are computed, never written by AI. AI-use note: drafted with Claude (Anthropic) during the hackathon.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import globalref, models, stats

SCENARIOS = [  # id, plain name, 2041-2060 warming vs 1850-1900 (best, low, high), IPCC AR6 SPM Table SPM.1
    ("SSP1-2.6", "Big emission cuts (net zero around 2070)", 1.7, 1.3, 2.2),
    ("SSP2-4.5", "Middle of the road (roughly today's policies)", 2.0, 1.6, 2.5),
    ("SSP5-8.5", "Very high emissions (fossil-fuelled growth)", 2.4, 1.9, 3.0),
]
AR6_2011_2020 = 1.09
SOURCE = ("IPCC (2021) AR6 WGI Summary for Policymakers, Table SPM.1; NASA GISTEMP v4 global temperature; "
          "pattern scaling as in Tebaldi & Arblaster (2014), Climatic Change 122, 459–471")


def _f(x: float) -> str:
    """Signed number with sensible decimals: +1.13, +12.4, +0.046."""
    a = abs(x)
    return f"{x:+.0f}" if a >= 100 else f"{x:+.1f}" if a >= 10 else f"{x:+.2f}" if a >= 0.1 else f"{x:+.3f}"


def _annual(series: pd.Series) -> pd.Series:
    a = stats.deseasonalise(series.dropna())[0]
    g = a.groupby(a.index.year)
    return g.mean()[g.count() == 12]


def _global_annual() -> pd.Series:
    g = globalref.gistemp()
    gy = g.groupby(g.index.year)
    return gy.mean()[gy.count() == 12]


def global_today() -> dict:
    """Global warming now (2016–2025 mean) above 1850–1900, on the AR6 scale."""
    g = _global_annual()
    offset = AR6_2011_2020 - float(g.loc[2011:2020].mean())
    return {"now": float(g.loc[2016:2025].mean()) + offset, "offset": offset}


def trend_whatif(a: dict, cp_status: str | None, units: str) -> dict:
    proven = a["verdict"]["label"] in ("strong", "some")
    if not proven:
        return {"available": False, "reason": "No proven trend here, so there is nothing to draw on."}
    if cp_status == "sudden_shift":
        return {"available": False, "reason": "The change here is one sudden jump, not a steady trend, so a straight line "
                                              "drawn on to 2050 would be misleading."}
    s, (lo, hi) = a["sen_slope_per_decade"], a["sen_ci95_per_decade"]
    dec = 3.0  # 2016–2025 average (centre 2020.5) to 2041–2060 average (centre 2050.5)
    return {"available": True, "change_by_2050": s * dec, "range": [lo * dec, hi * dec], "units": units,
            "headline": f"If today's trend simply keeps going: {_f(s * dec)} {units} around 2050 "
                        f"(range {_f(lo * dec)} to {_f(hi * dec)}) compared with the last 10 years.",
            "note": "A straight line, not a forecast: it ignores anything that could speed the change up or slow it down."}


def model_view(var: str, lat: float, lon: float, units: str) -> dict:
    if var not in models.MAP:
        return {"available": False, "reason": "No climate-model data for this variable."}
    daily = models._fetch(var, lat, lon)
    ann = daily.resample("YS").mean()
    d = (ann.loc["2041":"2050"].mean() - ann.loc["2016":"2025"].mean()).dropna()
    if d.empty:
        return {"available": False, "reason": "Model data too short here."}
    med, lo, hi = float(d.median()), float(d.min()), float(d.max())
    same = int((np.sign(d) == np.sign(med)).sum())
    return {"available": True, "change_by_2050": med, "range": [lo, hi], "n_models": int(len(d)), "agree_on_direction": same,
            "per_model": {k: float(v) for k, v in d.items()}, "units": units, "units_note": models.MAP[var][1],
            "headline": f"Climate models (high-emissions path): {_f(med)} {units} for 2041–2050 vs 2016–2025 "
                        f"(range {_f(lo)} to {_f(hi)}; {same} of {len(d)} models agree on the direction).",
            "credit": "CMIP6 HighResMIP (Haarsma et al. 2016), via the Open-Meteo Climate API (CC BY 4.0)"}


def scenarios(series: pd.Series, units: str) -> dict:
    loc, glob = _annual(series), _global_annual()
    both = pd.concat([loc, glob], axis=1, join="inner").dropna()
    if len(both) < 20:
        return {"available": False, "reason": "Record too short to link this place to global temperature."}
    x, y = both.iloc[:, 1].to_numpy(), both.iloc[:, 0].to_numpy()
    fit = stats.ols_neff(x, y)  # slope of local anomaly per °C of global warming, stickiness-corrected
    beta, se, p = fit["slope"], fit["se"], fit["p"]
    if not (p < 0.05):
        return {"available": False, "beta": beta, "p": p,
                "reason": "This place hasn't followed global temperature closely enough since 1981 to scale it to "
                          "future scenarios (no proven link), so we don't."}
    today = global_today()["now"]
    bl, bh = beta - 1.96 * se, beta + 1.96 * se
    rows = []
    for sid, name, best, glo, ghi in SCENARIOS:
        extra, extra_lo, extra_hi = best - today, max(glo - today, 0.0), ghi - today
        cands = [b * e for b in (bl, bh) for e in (extra_lo, extra_hi)]
        rows.append({"id": sid, "name": name, "global_warming_2050": best, "extra_global_warming": extra,
                     "change_by_2050": beta * extra, "range": [min(cands), max(cands)]})
    lo_s, hi_s = rows[0]["change_by_2050"], rows[-1]["change_by_2050"]
    return {"available": True, "beta_per_global_degree": beta, "beta_p": p, "global_today": today, "units": units,
            "scenarios": rows,
            "headline": (f"Since 1981 this place has changed {_f(beta)} {units} for every 1 °C the world warmed. "
                         f"Around 2050 that means {_f(lo_s)} {units} with big emission cuts, up to {_f(hi_s)} "
                         f"with very high emissions (compared with 2016–2025)."),
            "choice_matters": f"The emissions choice alone makes a difference of {_f(hi_s - lo_s)[1:]} {units} here by 2050.",
            "note": ("Assumes this place keeps responding to global warming the way it has since 1981. Ranges combine "
                     "that uncertainty with IPCC's range for each scenario."),
            "source": SOURCE}


def outlook(var: str, series: pd.Series, units: str, lat: float, lon: float, cp_status: str | None) -> dict:
    a = stats.analyse(series, units)
    if cp_status == "sudden_shift":
        sc = {"available": False, "reason": "The change here is one sudden jump, so its link to global temperature may be "
                                            "a coincidence of timing; we don't scale it to future scenarios."}
    else:
        sc = scenarios(series, units)
    out = {"trend": trend_whatif(a, cp_status, units), "scenarios": sc}
    try:
        out["models"] = model_view(var, lat, lon, units)
    except Exception as e:  # a model-service problem must not hide the other two views
        out["models"] = {"available": False, "reason": f"Climate-model service unavailable ({type(e).__name__})."}
    m = out["models"]
    if sc.get("available") and m.get("available"):
        mid = sc["scenarios"][-1]["change_by_2050"]  # the models follow a high-emissions path: compare with SSP5-8.5
        agree = bool(np.sign(mid) == np.sign(m["change_by_2050"]))
        sc["agrees_with_models"] = agree
        if not agree:
            sc["caution"] = ("Careful: the climate models point the other way here. Scaling from the past and the "
                             "models disagree, so treat both as very uncertain.")
    out["disclaimer"] = ("Three what-ifs, not forecasts: a straight line, climate models, and emission scenarios. "
                         "They show the range of futures, not what will happen in any one year.")
    return out
