"""Compare two places the right way: test the trend of the DIFFERENCE A − B.

"A is significant and B is not" does NOT show that A and B differ (Gelman &
Stern 2006, "The difference between 'significant' and 'not significant' is not
itself statistically significant"). The honest test is a trend test on the
month-by-month difference series, with the same persistence corrections.

AI-use note: drafted with Claude (Anthropic) during the hackathon.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import stats

PROVEN = {"strong", "some"}


def _overlap(a, b) -> bool:
    return not (a[1] <= b[0] or b[1] <= a[0] or a[3] <= b[2] or b[3] <= a[2])


def compare(sa: pd.Series, sb: pd.Series, units: str, box_a, box_b, name_a="Place A", name_b="Place B") -> dict:
    sa, sb = sa.dropna(), sb.dropna()
    idx = sa.index.intersection(sb.index)
    if len(idx) < 120:
        raise ValueError("The two places share fewer than 10 years of data.")
    sa, sb = sa[idx], sb[idx]
    ra, rb = stats.analyse(sa, units), stats.analyse(sb, units)
    d = (sa - sb).rename("difference")
    rd = stats.analyse(d, units)
    aa, _ = stats.deseasonalise(sa)
    ab, _ = stats.deseasonalise(sb)
    r = float(np.corrcoef(aa, ab)[0, 1])
    pa, pb, pd_ = ra["verdict"]["label"] in PROVEN, rb["verdict"]["label"] in PROVEN, rd["verdict"]["label"] in PROVEN
    sl_a, sl_b, sl_d = ra["sen_slope_per_decade"], rb["sen_slope_per_decade"], rd["sen_slope_per_decade"]
    opposite_fitted = np.sign(sl_a) * np.sign(sl_b) < 0
    supported_opposite = opposite_fitted and pa and pb
    u = units
    if pd_:
        gain, lose = (name_a, name_b) if sl_d > 0 else (name_b, name_a)
        msg = (f"The two places really are changing differently: {gain} is gaining on {lose} by {abs(sl_d):.3g} {u} per decade "
               f"(the gap {name_a} − {name_b} changes by {sl_d:+.3g}, 95% range {rd['sen_ci95_per_decade'][0]:+.3g} "
               f"to {rd['sen_ci95_per_decade'][1]:+.3g}).")
        if supported_opposite:
            msg = (f"Opposite trends, both proven: {name_a} {sl_a:+.3g} and {name_b} {sl_b:+.3g} {u}/decade, "
                   f"and the gap between them is itself a proven trend ({sl_d:+.3g} {u}/decade).")
    else:
        msg = (f"Can't tell them apart yet: the gap between {name_a} and {name_b} has no proven trend "
               f"({sl_d:+.3g} {u}/decade, 95% range {rd['sen_ci95_per_decade'][0]:+.3g} to {rd['sen_ci95_per_decade'][1]:+.3g}).")
    trap = None
    if pa != pb and not pd_:
        sig, nsig = (name_a, name_b) if pa else (name_b, name_a)
        trap = (f"Careful: {sig}'s trend is proven and {nsig}'s is not, but that does NOT mean they differ. "
                "Tested directly, the difference is not proven (Gelman & Stern 2006).")
    if opposite_fitted and not supported_opposite:
        note = "The fitted lines point in opposite directions, but at least one of them is not proven, so don't call them opposite trends."
    else:
        note = None
    return {
        "a": {"name": name_a, "box": box_a, "slope_per_decade": sl_a, "ci95": ra["sen_ci95_per_decade"],
              "label": ra["verdict"]["label"], "verdict": ra["verdict"]["headline"]},
        "b": {"name": name_b, "box": box_b, "slope_per_decade": sl_b, "ci95": rb["sen_ci95_per_decade"],
              "label": rb["verdict"]["label"], "verdict": rb["verdict"]["headline"]},
        "difference": {"slope_per_decade": sl_d, "ci95": rd["sen_ci95_per_decade"], "label": rd["verdict"]["label"],
                       "p_mk": rd["mk_hamed_rao"]["p"], "p_ols": rd["ols_neff"]["p"]},
        "labels": {"opposite_fitted_directions": bool(opposite_fitted), "supported_opposite_trends": bool(supported_opposite),
                   "rates_differ": bool(pd_)},
        "correlation": r,
        "boxes_overlap": _overlap(box_a, box_b),
        "headline": msg, "trap": trap, "note": note,
        "chart": {"dates": [x.strftime("%Y-%m") for x in idx],
                  "difference_anomaly": stats.deseasonalise(d)[0].round(4).tolist()},
        "period": f"{idx[0].year}–{idx[-1].year}",
        "method": "Trend test on the difference series A − B (Hamed–Rao Mann–Kendall + least squares with effective sample size)",
    }
