"""Tests for the stats engine using synthetic series with known answers."""
import numpy as np
import pandas as pd
import pytest

from trend_detective import stats


def synth(n_years=40, trend_per_decade=0.0, phi=0.5, noise=1.0, amp=5.0, seed=0):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("1981-01-01", periods=n_years * 12, freq="MS")
    t = stats.to_decimal_year(idx)
    e = np.zeros(len(idx))
    innov = rng.normal(0, noise * np.sqrt(1 - phi**2), len(idx))
    e[0] = rng.normal(0, noise)
    for i in range(1, len(idx)):
        e[i] = phi * e[i - 1] + innov[i]
    season = amp * np.sin(2 * np.pi * (idx.month.to_numpy() - 1) / 12)
    y = 10 + season + trend_per_decade / 10 * (t - t[0]) + e
    return pd.Series(y, index=idx)


def test_deseasonalise_removes_cycle():
    s = synth(amp=10, noise=0.1)
    anom, clim = stats.deseasonalise(s)
    assert stats.seasonal_amplitude(clim) == pytest.approx(20, rel=0.05)
    assert abs(anom.groupby(anom.index.month).mean()).max() < 1e-9


def test_recovers_known_trend():
    r = stats.analyse(synth(trend_per_decade=0.5, noise=0.5, seed=1), units="C")
    lo, hi = r["sen_ci95_per_decade"]
    assert lo < 0.5 < hi
    assert r["verdict"]["label"] == "strong"
    assert r["verdict"]["direction"] == "rising"


def test_no_trend_is_not_significant():
    r = stats.analyse(synth(trend_per_decade=0.0, seed=3))
    assert r["verdict"]["label"] in {"not_yet", "none"}


def test_falling_trend():
    r = stats.analyse(synth(trend_per_decade=-0.8, noise=0.5, seed=2))
    assert r["verdict"]["direction"] == "falling"
    assert r["sen_ci95_per_decade"][1] < 0


def test_neff_smaller_with_autocorrelation():
    a = stats.analyse(synth(phi=0.0, seed=4))
    b = stats.analyse(synth(phi=0.8, seed=4))
    assert b["ols_neff"]["n_eff"] < a["ols_neff"]["n_eff"]


def test_weatherhead_monotonic():
    # bigger noise or autocorrelation -> more years needed; bigger trend -> fewer
    base = stats.years_to_detect(0.02, 1.0, 0.5)
    assert stats.years_to_detect(0.02, 2.0, 0.5) > base
    assert stats.years_to_detect(0.02, 1.0, 0.8) > base
    assert stats.years_to_detect(0.04, 1.0, 0.5) < base
    assert stats.years_to_detect(0.0, 1.0, 0.5) is None


def test_weatherhead_reference_value():
    # sigma=1, |w|=0.1/yr, phi=0: n* = (33)^(2/3) = 10.29 years
    assert stats.years_to_detect(0.1, 1.0, 0.0) == pytest.approx(33 ** (2 / 3))


def test_fdr():
    p = [0.001, 0.01, 0.03, 0.2, 0.5, np.nan]
    m = stats.fdr(p, q=0.10)
    assert m.tolist() == [True, True, True, False, False, False]


def test_too_short():
    with pytest.raises(ValueError):
        stats.analyse(synth(n_years=2))


def test_typical_vs_detective_outcomes():
    tv = stats.typical_vs_detective
    assert tv(0.01, 0.2, "not_yet", "C")["outcome"] == "fooled"
    assert tv(0.001, 0.2, "strong", "C")["outcome"] == "agree_trend"
    assert tv(0.3, 0.2, "none", "C")["outcome"] == "agree_none"
    r = stats.analyse(synth(trend_per_decade=0.5, noise=0.5, seed=1), units="C")
    assert r["typical_vs_detective"]["outcome"] == "agree_trend"
