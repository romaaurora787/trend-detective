"""Tests for cross-examination, comparison and the guide helpers (synthetic data).

AI-use note: drafted with Claude (Anthropic) during the hackathon.
"""
import numpy as np
import pandas as pd

from trend_detective import compare, crossexam, guide

IDX = pd.date_range("1984-01-01", "2025-12-01", freq="MS")


def _series(trend_per_year=0.0, step=0.0, step_at="2001-01", noise=0.3, seed=0):
    rng = np.random.default_rng(seed)
    t = np.arange(len(IDX)) / 12
    season = 5 * np.sin(2 * np.pi * IDX.month / 12)
    y = 50 + season + trend_per_year * t + step * (IDX >= step_at) + rng.normal(0, noise, len(IDX))
    return pd.Series(y, index=IDX)


def test_alibi_catches_a_pure_step_at_the_source_switch():
    s = _series(step=-3.0)  # no trend at all, only a jump at the 2001 instrument change
    a = crossexam.alibi("CLOUD_AMT", s, "%")
    assert a["status"] == "could_be_instrument"


def test_alibi_lets_a_real_trend_through():
    s = _series(trend_per_year=0.08)
    a = crossexam.alibi("CLOUD_AMT", s, "%")
    assert a["status"] in ("survives", "survives_weakly")


def test_alibi_silent_without_documented_change():
    assert crossexam.alibi("T2M", _series(0.05), "°C")["status"] == "no_known_change"


def test_walk_forward_and_windows_on_steady_trend():
    s = _series(trend_per_year=0.05)
    assert crossexam.walk_forward(s, "x")["status"] == "confirmed"
    w = crossexam.all_windows(s)
    assert w["proven_opposite"] == 0 and w["same_direction"] / w["n_windows"] > 0.9


def test_leave_one_out_runs_and_names_a_year():
    lo = crossexam.leave_one_out(_series(0.05))
    assert lo["most_influential_year"] in range(1984, 2026) and not lo["flips"]


def test_el_nino_check_runs():
    e = crossexam.el_nino(_series(0.05), "°C")
    assert e["status"] in ("survives", "weakens", "revealed", "none") and 0 <= e["lag_months"] <= 6


def test_compare_same_trend_cannot_be_told_apart():
    a, b = _series(0.05, seed=1), _series(0.05, seed=2)
    out = compare.compare(a, b, "°C", [0, 1, 0, 1], [5, 6, 5, 6])
    assert not out["labels"]["rates_differ"]


def test_compare_opposite_trends_found():
    a, b = _series(0.06, seed=1), _series(-0.06, seed=2)
    out = compare.compare(a, b, "°C", [0, 1, 0, 1], [5, 6, 5, 6])
    assert out["labels"]["supported_opposite_trends"] and out["labels"]["rates_differ"]


def test_parse_csv_daily_to_monthly_with_header():
    days = pd.date_range("2000-01-01", "2012-12-31", freq="D")
    text = "date,value\n" + "\n".join(f"{d:%Y-%m-%d},{i % 7}" for i, d in enumerate(days))
    s = guide.parse_csv(text)
    assert len(s) == 156 and s.index[0] == pd.Timestamp("2000-01-01")


def test_hunch_seasons_flip_in_the_south():
    assert guide._season_months("summer", -30) == [12, 1, 2]
    assert guide._season_months("summer", 50) == [6, 7, 8]
