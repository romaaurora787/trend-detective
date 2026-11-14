"""Proof part 2: how often each method DETECTS a real trend (power).

Same synthetic setup as validate_synthetic.py (45 years, seasonal cycle,
AR(1) noise phi=0.5, sd 1) with true trends of increasing size.
Output: data/validation_power.json
"""
import json, sys, warnings
import pymannkendall as mk
from scipy import stats as sps
sys.path.insert(0, "tests")
from test_stats import synth  # noqa: E402
from trend_detective import stats  # noqa: E402
warnings.filterwarnings("ignore")
N = int(sys.argv[1]) if len(sys.argv) > 1 else 300
TRENDS = [0.0, 0.1, 0.2, 0.3, 0.4, 0.6]
methods = ["baseline_raw_ols", "naive_ols_anomalies", "ours_verdict"]
out = {"n_sims": N, "phi": 0.5, "noise_sd": 1.0, "seasonal_amp": 5.0, "trends_per_decade": TRENDS, "detection_rate": {m: [] for m in methods}}
for tr in TRENDS:
    hits = {m: 0 for m in methods}
    for k in range(N):
        s = synth(n_years=45, trend_per_decade=tr, phi=0.5, noise=1.0, amp=5.0, seed=50_000 + k)
        a, _ = stats.deseasonalise(s); t = stats.to_decimal_year(a.index); y = a.to_numpy()
        hits["baseline_raw_ols"] += stats.baseline_ols_raw(s)["p"] < 0.05
        hits["naive_ols_anomalies"] += sps.linregress(t, y).pvalue < 0.05
        hits["ours_verdict"] += (mk.hamed_rao_modification_test(y, lag=stats.HR_LAG).p < 0.05) and (stats.ols_neff(t, y)["p"] < 0.05)
    for m in methods: out["detection_rate"][m].append(hits[m] / N)
    print(tr, {m: round(hits[m] / N, 3) for m in methods}, flush=True)
json.dump(out, open("data/validation_power.json", "w"), indent=1)
