import sys, numpy as np, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, "tests")
from test_stats import synth
from trend_detective import stats
import pymannkendall as mk
N=150
for phi in [0.0, 0.5]:
    res = {}
    for k in range(N):
        s = synth(trend_per_decade=0.5, phi=phi, noise=0.5, seed=1000 + k)
        a,_ = stats.deseasonalise(s); t = stats.to_decimal_year(a.index); y = a.to_numpy()
        vs = {"orig": mk.original_test(y).var_s,
              "hr_all": mk.hamed_rao_modification_test(y).var_s,
              "hr_lag12": mk.hamed_rao_modification_test(y, lag=12).var_s,
              "hr_lag3": mk.hamed_rao_modification_test(y, lag=3).var_s,
              "yw": mk.yue_wang_modification_test(y).var_s,
              "yw_lag1": mk.yue_wang_modification_test(y, lag=1).var_s}
        for name, v in vs.items():
            if not np.isfinite(v) or v <= 0: res.setdefault(name, []).append(np.nan); continue
            _, lo, hi = stats.sens_slope_ci(t, y, v)
            res.setdefault(name, []).append(lo*10 < 0.5 < hi*10)
    for name, v in res.items():
        v = np.array(v, float); print(f"phi={phi} {name:9s} coverage={np.nanmean(v):.3f} nan={np.isnan(v).sum()}")
