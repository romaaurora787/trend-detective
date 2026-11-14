"""Trend statistics engine for Earth System Trend Detective.

Every number shown to a user comes from this module. Pure functions only:
input a monthly series, output plain dicts. No I/O.

Methods (all standard, published):
- Seasonal cycle removal: subtract each calendar month's long-term mean.
- Mann-Kendall test with the Hamed & Rao (1998) autocorrelation correction
  (via pymannkendall, lags up to 12 months); Yue & Wang (2004, lag 1) as a
  second opinion.
- Sen's (1968) slope with a confidence interval from the corrected
  Mann-Kendall variance (Gilbert 1987, sec. 16.5).
- OLS trend t-test with AR(1) effective sample size
  n_eff = n (1 - r1) / (1 + r1)  (e.g. Santer et al. 2000).
- Years needed to detect a trend: Weatherhead et al. (1998), eq. 2.
- Benjamini & Hochberg (1995) false discovery rate for maps (Wilks 2016).
- "Baseline" method from GES DISC (Acker et al.): OLS on raw monthly values,
  F-test, no seasonal or autocorrelation handling. Kept for comparison only.

AI-use note: drafted with Claude (Anthropic) during the hackathon and checked
by the team against the cited papers and synthetic tests (see tests/).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, asdict

import numpy as np
import pandas as pd
import pymannkendall as mk
from scipy import stats as sps
from statsmodels.stats.multitest import multipletests

ALPHA = 0.05  # significance level for verdicts
STRONG_ALPHA = 0.01
FDR_Q = 0.10  # map false discovery rate (Wilks 2016 recommends 0.10)
WEATHERHEAD_MAX_YEARS = 100  # beyond this we call it "no meaningful trend"
# Hamed-Rao uses only autocorrelation lags up to 12 months. With all lags
# (the pymannkendall default) spurious significant lags made the variance
# unstable (occasionally negative) and 95% CIs covered only ~86-90% in our
# synthetic tests; with 12 lags coverage was ~92-95% (scripts/diag.py).
HR_LAG = 12
YW_LAG = 1


# ---------------------------------------------------------------- helpers
def to_decimal_year(index: pd.DatetimeIndex) -> np.ndarray:
    """Month timestamps -> decimal years at mid-month (2001-01 -> 2001.0417)."""
    return index.year.to_numpy() + (index.month.to_numpy() - 0.5) / 12.0


def deseasonalise(series: pd.Series) -> tuple[pd.Series, pd.Series]:
    """Remove the mean seasonal cycle.

    Returns (anomalies, climatology) where climatology is indexed by month 1-12.
    """
    s = series.dropna()
    clim = s.groupby(s.index.month).mean()
    anomalies = s - clim.reindex(s.index.month).to_numpy()
    return anomalies, clim


def lag1_autocorr(x: np.ndarray) -> float:
    x = np.asarray(x, dtype=float)
    x = x - x.mean()
    denom = np.dot(x, x)
    if denom == 0:
        return 0.0
    return float(np.dot(x[:-1], x[1:]) / denom)


def seasonal_amplitude(clim: pd.Series) -> float:
    return float(clim.max() - clim.min())


# ---------------------------------------------------------------- tests
def sens_slope_ci(t: np.ndarray, y: np.ndarray, var_s: float, alpha: float = ALPHA):
    """Sen's slope (per unit of t) with a CI using the (corrected) MK variance."""
    t = np.asarray(t, float)
    y = np.asarray(y, float)
    i, j = np.triu_indices(len(t), k=1)
    dt = t[j] - t[i]
    keep = dt != 0
    slopes = np.sort((y[j] - y[i])[keep] / dt[keep])
    n_pairs = slopes.size
    median = float(np.median(slopes))
    c = sps.norm.ppf(1 - alpha / 2) * math.sqrt(max(var_s, 0.0))
    m1 = (n_pairs - c) / 2.0  # 1-based rank of lower limit
    m2 = (n_pairs + c) / 2.0 + 1  # 1-based rank of upper limit
    ranks = np.arange(1, n_pairs + 1)
    lo = float(np.interp(m1, ranks, slopes))
    hi = float(np.interp(m2, ranks, slopes))
    return median, lo, hi


def ols_neff(t: np.ndarray, y: np.ndarray) -> dict:
    """OLS slope with standard error inflated for AR(1) residuals."""
    t = np.asarray(t, float)
    y = np.asarray(y, float)
    n = len(y)
    res = sps.linregress(t, y)
    resid = y - (res.intercept + res.slope * t)
    r1 = lag1_autocorr(resid)
    r1c = min(max(r1, 0.0), 0.99)  # negative r1 -> no inflation
    n_eff = n * (1 - r1c) / (1 + r1c)
    n_eff = max(n_eff, 3.0)
    se = res.stderr * math.sqrt((n - 2) / (n_eff - 2))
    tstat = res.slope / se if se > 0 else 0.0
    p = 2 * sps.t.sf(abs(tstat), df=n_eff - 2)
    return {
        "slope": float(res.slope),
        "intercept": float(res.intercept),
        "se": float(se),
        "p": float(p),
        "r1": float(r1),
        "n_eff": float(n_eff),
        "resid_sd": float(np.std(resid, ddof=2)),
    }


def baseline_ols_raw(series: pd.Series) -> dict:
    """GES DISC baseline (Acker et al.): OLS on raw monthly data, F-test.

    No seasonal removal and no autocorrelation correction. Comparison only.
    """
    s = series.dropna()
    t = to_decimal_year(s.index)
    res = sps.linregress(t, s.to_numpy())
    return {"slope_per_decade": float(res.slope * 10), "p": float(res.pvalue)}


def years_to_detect(trend_per_year: float, noise_sd: float, phi: float) -> float | None:
    """Weatherhead et al. (1998) eq. 2: years of monthly data needed to detect
    a trend of this size (5% level, 90% probability)."""
    if trend_per_year == 0 or not np.isfinite(trend_per_year):
        return None
    phi = min(max(phi, 0.0), 0.99)
    n_star = ((3.3 * noise_sd / abs(trend_per_year)) * math.sqrt((1 + phi) / (1 - phi))) ** (2 / 3)
    return float(n_star)


def fdr(pvalues, q: float = FDR_Q) -> np.ndarray:
    """Benjamini-Hochberg: boolean mask of discoveries. NaNs are never significant."""
    p = np.asarray(pvalues, float)
    out = np.zeros(p.shape, dtype=bool)
    ok = np.isfinite(p)
    if ok.any():
        out[ok] = multipletests(p[ok], alpha=q, method="fdr_bh")[0]
    return out


# ---------------------------------------------------------------- main entry
@dataclass
class Verdict:
    label: str  # strong | some | mixed | not_yet | none
    headline: str  # plain-English one-liner (numbers inserted by code)
    direction: str  # rising | falling | flat
    tests_agree: bool


def _verdict(p_mk, p_ols, slope, lo, hi, years_needed, record_years, units) -> Verdict:
    direction = "rising" if slope > 0 else "falling" if slope < 0 else "flat"
    sig_mk, sig_ols = p_mk < ALPHA, p_ols < ALPHA
    agree = sig_mk == sig_ols
    rate = f"{abs(slope):.3g} {units} per decade"
    if sig_mk and sig_ols and p_mk < STRONG_ALPHA and p_ols < STRONG_ALPHA:
        return Verdict("strong", f"Strong evidence it is {direction}: about {rate}.", direction, True)
    if sig_mk and sig_ols:
        return Verdict("some", f"Some evidence it is {direction}: about {rate}.", direction, True)
    if sig_mk != sig_ols:
        return Verdict(
            "mixed",
            f"Mixed evidence: one test says {direction}, the other cannot rule out chance.",
            direction,
            False,
        )
    if years_needed is not None and years_needed <= WEATHERHEAD_MAX_YEARS:
        more = max(years_needed - record_years, 0)
        return Verdict(
            "not_yet",
            f"Not significant yet. If it keeps changing at this rate, about {more:.0f} more years of data would show it.",
            direction,
            True,
        )
    return Verdict("none", "No meaningful trend: any change is lost in natural ups and downs.", direction, True)


def analyse(series: pd.Series, units: str = "", alpha: float = ALPHA) -> dict:
    """Full verdict for one monthly series (DatetimeIndex, monthly)."""
    s = series.dropna().sort_index()
    if len(s) < 36:
        raise ValueError("Need at least 3 years of monthly data")
    anomalies, clim = deseasonalise(s)
    t = to_decimal_year(anomalies.index)
    y = anomalies.to_numpy()

    hr = mk.hamed_rao_modification_test(y, alpha=alpha, lag=HR_LAG)
    yw = mk.yue_wang_modification_test(y, alpha=alpha, lag=YW_LAG)
    sen, lo, hi = sens_slope_ci(t, y, hr.var_s, alpha)
    ols = ols_neff(t, y)
    slope_method = "sen"
    if sen == 0 and ols["slope"] != 0:
        # Mostly-zero variables (frost days, snow) make most pairwise slopes 0,
        # so Sen's median is 0 even when a trend exists. Use OLS + n_eff CI.
        slope_method = "ols_neff (many repeated values)"
        half = sps.t.ppf(1 - alpha / 2, ols["n_eff"] - 2) * ols["se"]
        sen, lo, hi = ols["slope"], ols["slope"] - half, ols["slope"] + half
    record_years = (len(y)) / 12.0
    # Weatherhead et al. derive n* for a least-squares trend, so use the OLS
    # slope here (Sen's median can be far smaller for skewed data like rain).
    n_star = years_to_detect(ols["slope"], ols["resid_sd"], ols["r1"])
    v = _verdict(hr.p, ols["p"], sen * 10, lo * 10, hi * 10, n_star, record_years, units)

    return {
        "n_months": int(len(y)),
        "start": s.index[0].strftime("%Y-%m"),
        "end": s.index[-1].strftime("%Y-%m"),
        "units": units,
        "mean": float(s.mean()),
        "seasonal_amplitude": seasonal_amplitude(clim),
        "sen_slope_per_decade": sen * 10,
        "sen_ci95_per_decade": [lo * 10, hi * 10],
        "slope_method": slope_method,
        "total_change": sen * (t[-1] - t[0]),
        "mk_hamed_rao": {"p": float(hr.p), "z": float(hr.z), "tau": float(hr.Tau)},
        "mk_yue_wang": {"p": float(yw.p), "z": float(yw.z)},
        "ols_neff": {
            "slope_per_decade": ols["slope"] * 10,
            "p": ols["p"],
            "lag1_autocorr": ols["r1"],
            "n_eff": ols["n_eff"],
        },
        "baseline_raw_ols": baseline_ols_raw(s),
        "years_to_detect": n_star,
        "record_years": record_years,
        "verdict": asdict(v),
        "climatology": {int(k): float(v_) for k, v_ in clim.items()},
    }


def quick_cell_test(series: pd.Series, alpha: float = ALPHA) -> tuple[float, float]:
    """Fast per-grid-cell test for maps: (Sen slope per decade, Hamed-Rao p)."""
    anomalies, _ = deseasonalise(series)
    y = anomalies.to_numpy()
    hr = mk.hamed_rao_modification_test(y, alpha=alpha, lag=HR_LAG)
    return float(hr.slope * 120), float(hr.p)  # slope per month -> per decade
