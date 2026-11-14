"""Monte Carlo: CI coverage and false-alarm rates on synthetic data."""
import sys, numpy as np
sys.path.insert(0, "tests")
from test_stats import synth
from trend_detective import stats
import pymannkendall as mk

N = int(sys.argv[1]) if len(sys.argv) > 1 else 200
phi = float(sys.argv[2]) if len(sys.argv) > 2 else 0.5
cov = 0; ci_w = []
for k in range(N):
    r = stats.analyse(synth(trend_per_decade=0.5, phi=phi, noise=0.5, seed=1000 + k))
    lo, hi = r["sen_ci95_per_decade"]; cov += lo < 0.5 < hi; ci_w.append(hi - lo)
print(f"phi={phi} Sen CI95 coverage: {cov/N:.3f}, mean width {np.mean(ci_w):.3f}")
