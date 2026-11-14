"""False-alarm check for beyond.py methods on NO-trend synthetic series with
year-to-year persistence (AR(1) on annual anomalies + monthly noise).
A good 5% test should alarm ~5% of the time."""
import sys, warnings, numpy as np, pandas as pd
warnings.filterwarnings("ignore")
from trend_detective import beyond

def series(phi_year, seed, n_years=45):
    rng = np.random.default_rng(seed)
    yr = np.zeros(n_years)
    for i in range(1, n_years):
        yr[i] = phi_year * yr[i - 1] + rng.normal(0, np.sqrt(1 - phi_year**2))
    idx = pd.date_range("1981-01-01", periods=n_years * 12, freq="MS")
    m = np.repeat(yr, 12) * 0.6 + rng.normal(0, 1, len(idx)) + 5 * np.sin(2 * np.pi * idx.month / 12)
    return pd.Series(m, index=idx)

N = int(sys.argv[1]) if len(sys.argv) > 1 else 200
for phi in [0.0, 0.3, 0.6]:
    rec = tp = var = emg = 0
    for s in range(N):
        x = series(phi, 1000 + s)
        r = beyond.records(x, n_perm=300)
        rec += (r["p_highs"] < 0.05) or (r["p_lows"] < 0.05)
        tp += beyond.turning_point(x)["year"] is not None
        var += beyond.variability(x)["p"] < 0.05
        emg += beyond.emergence(x)["year"] is not None
    print(f"phi_year={phi}: records {rec/N:.1%} (two-sided, ideal ~10%), turning point {tp/N:.1%}, variability {var/N:.1%}, emergence {emg/N:.1%}", flush=True)
