"""Proof-it-works experiment: false-alarm rate when there is NO trend.

Synthetic monthly series, 45 years (1981-2025, like NASA POWER), seasonal cycle
plus AR(1) noise of increasing persistence (phi). A correct 5% test should
raise a false alarm in about 5% of series. Output: data/validation.json
"""
import json, sys, warnings
import numpy as np
import pymannkendall as mk
from scipy import stats as sps

sys.path.insert(0, "tests")
from test_stats import synth  # noqa: E402
from trend_detective import stats  # noqa: E402

warnings.filterwarnings("ignore")
N = int(sys.argv[1]) if len(sys.argv) > 1 else 500
PHIS = [0.0, 0.3, 0.5, 0.7, 0.85]
methods = ["baseline_raw_ols", "naive_ols_anomalies", "naive_mann_kendall", "ours_mk_hamed_rao", "ours_ols_neff", "ours_verdict"]
out = {"n_sims": N, "n_years": 45, "alpha": 0.05, "phis": PHIS, "false_alarm_rate": {m: [] for m in methods}}
for phi in PHIS:
    hits = {m: 0 for m in methods}
    for k in range(N):
        s = synth(n_years=45, trend_per_decade=0.0, phi=phi, noise=1.0, amp=5.0, seed=10_000 + k)
        a, _ = stats.deseasonalise(s)
        t = stats.to_decimal_year(a.index); y = a.to_numpy()
        hits["baseline_raw_ols"] += stats.baseline_ols_raw(s)["p"] < 0.05
        hits["naive_ols_anomalies"] += sps.linregress(t, y).pvalue < 0.05
        hits["naive_mann_kendall"] += mk.original_test(y).p < 0.05
        p_hr = mk.hamed_rao_modification_test(y, lag=stats.HR_LAG).p
        p_ols = stats.ols_neff(t, y)["p"]
        hits["ours_mk_hamed_rao"] += p_hr < 0.05
        hits["ours_ols_neff"] += p_ols < 0.05
        hits["ours_verdict"] += (p_hr < 0.05) and (p_ols < 0.05)
    for m in methods:
        out["false_alarm_rate"][m].append(hits[m] / N)
    print(phi, {m: round(hits[m] / N, 3) for m in methods}, flush=True)
json.dump(out, open("data/validation.json", "w"), indent=1)
