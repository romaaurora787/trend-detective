"""Proof part 3 (B4): our monthly test vs the "yearly averages" shortcut.

Several tools (and many papers) average each year first, then run Mann-Kendall on
~45 yearly values. That keeps false alarms near 5% too, so the fair question is POWER:
at the SAME false-alarm rate, which method catches more real trends?

Same synthetic setup as validate_synthetic.py / validate_power.py: 45 years of monthly data,
seasonal cycle, AR(1) noise (sd 1), known true trends. For each phi we:
  1. record every method's p-value on N no-trend series and N series per trend size;
  2. report detection at the usual p < 0.05 ("as used"), and
  3. report "size-adjusted" detection: each method's threshold set so it has exactly 5%
     false alarms on the no-trend series (a like-for-like comparison).

Methods
  yearly_mk      Mann-Kendall on calendar-year means (the shortcut)
  yearly_mk_hr   Hamed-Rao Mann-Kendall on calendar-year means
  ours_verdict   our monthly test: Hamed-Rao MK AND OLS with effective sample size, both p < 0.05

Output: data/validation_yearly.json. Run: uv run python scripts/validate_yearly.py [N]

AI-use note: drafted with Claude (Anthropic) during the hackathon.
"""
import json
import sys
import warnings

import numpy as np
import pymannkendall as mk

sys.path.insert(0, "tests")
from test_stats import synth  # noqa: E402
from trend_detective import stats  # noqa: E402

warnings.filterwarnings("ignore")
N = int(sys.argv[1]) if len(sys.argv) > 1 else 400
PHIS = [0.5, 0.85]
TRENDS = [0.0, 0.05, 0.1, 0.15, 0.2, 0.3]
METHODS = ["yearly_mk", "yearly_mk_hr", "ours_verdict"]


def pvals(s):
    yearly = s.groupby(s.index.year).mean().to_numpy()
    a, _ = stats.deseasonalise(s)
    t, y = stats.to_decimal_year(a.index), a.to_numpy()
    ours = max(mk.hamed_rao_modification_test(y, lag=stats.HR_LAG).p, stats.ols_neff(t, y)["p"])
    out = {"yearly_mk": mk.original_test(yearly).p,
           "yearly_mk_hr": mk.hamed_rao_modification_test(yearly).p,
           "ours_verdict": ours}
    return {k: (v if np.isfinite(v) else 1.0) for k, v in out.items()}  # Hamed-Rao on 45 points can return NaN


out = {"n_sims": N, "n_years": 45, "noise_sd": 1.0, "seasonal_amp": 5.0, "phis": PHIS,
       "trends_per_decade": TRENDS, "results": {}}
for phi in PHIS:
    P = {}
    for tr in TRENDS:
        rows = [pvals(synth(n_years=45, trend_per_decade=tr, phi=phi, noise=1.0, amp=5.0, seed=70_000 + k))
                for k in range(N)]
        P[tr] = {m: np.array([r[m] for r in rows]) for m in METHODS}
    thr = {m: float(np.quantile(P[0.0][m], 0.05)) for m in METHODS}  # 5% false alarms exactly
    res = {"false_alarm_at_0.05": {m: float((P[0.0][m] < 0.05).mean()) for m in METHODS},
           "threshold_for_5pct": thr,
           "detection_at_0.05": {m: [float((P[tr][m] < 0.05).mean()) for tr in TRENDS] for m in METHODS},
           "detection_size_adjusted": {m: [float((P[tr][m] <= thr[m]).mean()) for tr in TRENDS] for m in METHODS}}
    out["results"][str(phi)] = res
    print("phi", phi, "false alarms", {m: round(v, 3) for m, v in res["false_alarm_at_0.05"].items()}, flush=True)
    for m in METHODS:
        print("   ", m.ljust(13), "as used", [round(x, 2) for x in res["detection_at_0.05"][m]],
              "| size-adjusted", [round(x, 2) for x in res["detection_size_adjusted"][m]], flush=True)
json.dump(out, open("data/validation_yearly.json", "w"), indent=1)
