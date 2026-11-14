"""Beyond the trend line: five questions a straight-line test can't answer.

1. records     Are records being broken more often than chance allows?
               Without change, the chance a year sets a record is 1/n for the
               n-th year (Benestad 2003; Rahmstorf & Coumou 2011). We compare
               observed vs expected counts in the recent third of the record,
               with a permutation p-value (whole years shuffled in 5-year
               blocks, which keeps natural persistence).
2. emergence   When did the change rise out of the noise? First year after
               which the trend-implied change stays above 2x the year-to-year
               noise (signal-to-noise > 2; Hawkins & Sutton 2012 style).
3. seasons     Which season is changing? Sen slope + Mann-Kendall (Hamed-Rao)
               per season on yearly seasonal means, Holm-corrected across
               the four seasons.
4. variability Is it getting more erratic? Spread of detrended anomalies in
               the second half vs the first half; permutation test that
               shuffles whole years in 5-year blocks.
5. turning     Did the trend change at some year? Compare a straight line with
               a "hinge" (two connected lines) by BIC (gain > 10 required).

All numbers come from code. AI-use note: drafted with Claude (Anthropic)
during the hackathon; checked with synthetic tests (tests/test_beyond.py).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pymannkendall as mk
from scipy import stats as sps

from .stats import deseasonalise, to_decimal_year

SEASONS = {"Winter (Dec–Feb)": [12, 1, 2], "Spring (Mar–May)": [3, 4, 5],
           "Summer (Jun–Aug)": [6, 7, 8], "Autumn (Sep–Nov)": [9, 10, 11]}


def _annual(anom: pd.Series) -> pd.Series:
    """Yearly mean anomaly, complete years only."""
    g = anom.groupby(anom.index.year)
    return g.mean()[g.count() == 12]


BIC_THRESHOLD = 10.0
BLOCK_YEARS = 5  # shuffle whole 5-year blocks: keeps within-year and year-to-year persistence


def _block_order(n: int, rng, block: int = BLOCK_YEARS) -> np.ndarray:
    """Row order from shuffling consecutive blocks of years (last block may be short)."""
    blocks = [np.arange(i, min(i + block, n)) for i in range(0, n, block)]
    return np.concatenate([blocks[k] for k in rng.permutation(len(blocks))])


# ---------------------------------------------------------------- 1. records
def _count_records(mat: np.ndarray, start: int, high: bool) -> int:
    """mat: years x 12 anomalies. Count records set in rows >= start."""
    x = mat if high else -mat
    run = np.maximum.accumulate(x, axis=0)
    is_rec = np.zeros_like(x, dtype=bool)
    is_rec[1:] = x[1:] > run[:-1]
    return int(is_rec[start:].sum())


def records(series: pd.Series, recent_fraction: float = 1 / 3, n_perm: int = 2000, seed: int = 0) -> dict:
    anom, _ = deseasonalise(series)
    df = anom.to_frame("a")
    df["y"], df["m"] = df.index.year, df.index.month
    mat = df.pivot(index="y", columns="m", values="a").dropna()
    years = mat.index.to_numpy()
    n = len(years)
    start = int(round(n * (1 - recent_fraction)))
    m = mat.to_numpy()
    expected_textbook = 12 * sum(1 / k for k in range(start + 1, n + 1))  # 1/k rule, no ties
    obs_hi, obs_lo = _count_records(m, start, True), _count_records(m, start, False)
    rng = np.random.default_rng(seed)
    perm_hi, perm_lo = np.empty(n_perm), np.empty(n_perm)
    for i in range(n_perm):
        # Whole years move together, in 5-year blocks: shuffling months one by one
        # gave 13-22% false alarms (ideal 10%, two-sided) on persistent synthetic
        # weather; see scripts/validate_beyond.py.
        p = m[_block_order(n, rng)]
        perm_hi[i], perm_lo[i] = _count_records(p, start, True), _count_records(p, start, False)
    p_hi = (1 + (perm_hi >= obs_hi).sum()) / (n_perm + 1)
    p_lo = (1 + (perm_lo >= obs_lo).sum()) / (n_perm + 1)
    # Expected counts come from the shuffles themselves, which handles ties
    # (e.g. frost days, mostly zero) where the textbook 1/n rule does not hold.
    exp_hi, exp_lo = float(perm_hi.mean()), float(perm_lo.mean())
    period = f"{years[start]}–{years[-1]}"
    ratio = obs_hi / exp_hi if exp_hi else np.nan
    ratio_lo = obs_lo / exp_lo if exp_lo else np.nan
    if p_hi < 0.05 and obs_hi > exp_hi:
        msg = (f"Since {years[start]}, {obs_hi} monthly highs were records. Without any change we'd expect about "
               f"{exp_hi:.0f}, so record highs are being broken {ratio:.1f}× as often as chance allows.")
    elif p_lo < 0.05 and obs_lo > exp_lo:
        msg = (f"Since {years[start]}, {obs_lo} monthly lows were records. Without any change we'd expect about "
               f"{exp_lo:.0f}, so record lows are being set {ratio_lo:.1f}× as often as chance allows.")
    else:
        msg = (f"Records since {years[start]} ({obs_hi} highs, {obs_lo} lows) are about what chance alone gives "
               f"(~{exp_hi:.0f} each).")
    expected = exp_hi
    return {"period": period, "expected": expected, "expected_lows": exp_lo, "textbook_expected": float(expected_textbook),
            "record_highs": obs_hi, "record_lows": obs_lo, "ratio_highs": ratio, "ratio_lows": ratio_lo,
            "p_highs": float(p_hi), "p_lows": float(p_lo), "headline": msg}


# ---------------------------------------------------------------- 2. emergence
def emergence(series: pd.Series, sn: float = 2.0) -> dict:
    anom, _ = deseasonalise(series)
    ann = _annual(anom)
    yrs = ann.index.to_numpy().astype(float)
    if len(ann) < 15:
        return {"year": None, "headline": "Record too short to judge emergence."}
    res = sps.theilslopes(ann.to_numpy(), yrs)
    slope = res[0]
    resid = ann.to_numpy() - (res[1] + slope * yrs)
    noise = float(np.std(resid, ddof=2))
    change = slope * (yrs - yrs[0])  # trend-implied change since the start
    above = np.abs(change) > sn * noise
    year = None
    for k in range(len(above)):
        if above[k:].all():
            year = int(yrs[k])
            break
    if year is None:
        n_needed = (sn * noise / abs(slope)) if slope else np.inf
        yr = yrs[0] + n_needed
        msg = (f"Not yet out of the noise. At this rate it would emerge around {yr:.0f}."
               if np.isfinite(yr) and yr < yrs[0] + 300 else "No emergence: the change is tiny next to natural ups and downs.")
    else:
        msg = f"The change rose clearly out of natural year-to-year noise in {year} and has stayed out since."
    return {"year": year, "noise_sd_annual": noise, "slope_per_year": float(slope), "signal_to_noise_now": float(abs(change[-1]) / noise) if noise else None,
            "headline": msg}


# ---------------------------------------------------------------- 3. seasons
def seasons(series: pd.Series) -> dict:
    s = series.dropna()
    out = []
    for name, months in SEASONS.items():
        sub = s[s.index.month.isin(months)]
        # winter belongs to the year of its January
        yr = np.where(sub.index.month == 12, sub.index.year + 1, sub.index.year)
        g = sub.groupby(yr)
        ys = g.mean()[g.count() == 3]
        if len(ys) < 15:
            continue
        r = mk.hamed_rao_modification_test(ys.to_numpy(), lag=3)
        out.append({"season": name, "slope_per_decade": float(r.slope * 10), "p": float(r.p),
                    "n_years": int(len(ys))})
    # Four seasons = four chances to be fooled: Holm correction across them.
    if out:
        from statsmodels.stats.multitest import multipletests
        rej, p_adj, *_ = multipletests([o["p"] for o in out], alpha=0.05, method="holm")
        for o, r_, pa in zip(out, rej, p_adj):
            o["p_adjusted"], o["significant"] = float(pa), bool(r_)
    sig = [o for o in out if o["significant"]]
    if sig:
        top = max(sig, key=lambda o: abs(o["slope_per_decade"]))
        msg = f"{top['season'].split(' ')[0]} is changing fastest ({top['slope_per_decade']:+.3g} per decade)."
        quiet = [o["season"].split(" ")[0] for o in out if not o["significant"]]
        if quiet:
            msg += f" No proven change in: {', '.join(quiet)}."
    else:
        msg = "No single season shows a proven change on its own."
    return {"seasons": out, "headline": msg}


# ---------------------------------------------------------------- 4. variability
def variability(series: pd.Series, n_perm: int = 2000, seed: int = 0) -> dict:
    anom, _ = deseasonalise(series)
    t = to_decimal_year(anom.index)
    fit = sps.linregress(t, anom.to_numpy())
    resid = pd.Series(anom.to_numpy() - (fit.intercept + fit.slope * t), index=anom.index)
    df = resid.to_frame("r")
    df["y"], df["m"] = df.index.year, df.index.month
    mat = df.pivot(index="y", columns="m", values="r").dropna().to_numpy()
    n = len(mat)
    half = n // 2
    years = sorted(set(resid.index.year))

    def stat(x):
        return float(np.log(x[half:].std() / x[:half].std()))

    obs = stat(mat)
    # Whole years shuffled in 5-year blocks (a Levene test on months gave 15-19%
    # false alarms at a 5% level on persistent synthetic weather).
    rng = np.random.default_rng(seed)
    perm = np.array([stat(mat[_block_order(n, rng)]) for _ in range(n_perm)])
    p = float((1 + (np.abs(perm) >= abs(obs)).sum()) / (n_perm + 1))
    ratio = float(np.exp(obs))
    split = years[half] if half < len(years) else years[-1]
    if p < 0.05:
        msg = (f"More erratic: month-to-month swings are {100*(ratio-1):+.0f}% bigger since {split}."
               if ratio > 1 else f"Calmer: month-to-month swings are {100*(1-ratio):.0f}% smaller since {split}.")
    else:
        msg = f"No proven change in how erratic it is (spread changed {100*(ratio-1):+.0f}%, could be chance)."
    return {"first_half": f"{years[0]}–{years[half-1]}", "second_half": f"{split}–{years[-1]}",
            "spread_ratio": ratio, "p": p, "headline": msg}


# ---------------------------------------------------------------- 5. turning point
def turning_point(series: pd.Series, min_seg: int = 6) -> dict:
    anom, _ = deseasonalise(series)
    ann = _annual(anom)
    y = ann.to_numpy()
    x = ann.index.to_numpy().astype(float)
    n = len(y)
    if n < 2 * min_seg + 2:
        return {"year": None, "headline": "Record too short to look for a turning point."}

    def sse(X):
        beta, *_ = np.linalg.lstsq(X, y, rcond=None)
        r = y - X @ beta
        return float(r @ r), beta

    X1 = np.column_stack([np.ones(n), x])
    sse1, b1 = sse(X1)
    bic1 = n * np.log(sse1 / n) + 2 * np.log(n)
    best = None
    for k in range(min_seg, n - min_seg):
        hinge = np.maximum(x - x[k], 0)
        s2, b2 = sse(np.column_stack([np.ones(n), x, hinge]))
        if best is None or s2 < best[0]:
            best = (s2, int(x[k]), b2)
    sse2, year, b2 = best
    bic2 = n * np.log(sse2 / n) + 4 * np.log(n)  # +1 slope, +1 break year
    delta = bic1 - bic2
    before, after = b2[1] * 10, (b2[1] + b2[2]) * 10
    # BIC gain > 10 = "very strong" evidence. With > 6, false alarms on very
    # persistent no-trend weather reached 11%; with > 10, 7.7%, and a real
    # break was still found 93% of the time (scripts/validate_beyond.py).
    if delta > BIC_THRESHOLD:
        msg = f"Turning point around {year}: {before:+.3g} per decade before, {after:+.3g} per decade after."
    else:
        msg = "A single straight trend explains it as well as any turning point."
    return {"year": year if delta > BIC_THRESHOLD else None, "candidate_year": year, "bic_gain": float(delta),
            "slope_before_per_decade": float(before), "slope_after_per_decade": float(after),
            "headline": msg}


def beyond(series: pd.Series) -> dict:
    s = series.dropna().sort_index()
    return {"records": records(s), "emergence": emergence(s), "seasons": seasons(s),
            "variability": variability(s), "turning_point": turning_point(s)}
