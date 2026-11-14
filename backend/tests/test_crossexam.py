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


def test_seasons_finds_a_winter_only_trend():
    s = _series(noise=0.3, seed=3)
    winter = s.index.month.isin([12, 1, 2])
    s = s + np.where(winter, 0.1 * (s.index.year - 1984), 0.0)  # +1 per decade, winter only
    a = crossexam.seasons(s, "°C", 52)
    proven = {r["month"] for r in a["months"] if r["proven_fdr"]}
    assert {"Dec", "Jan", "Feb"} <= proven
    assert len(proven & {"Jun", "Jul", "Aug"}) <= 1  # FDR q=0.10 allows the odd false month
    assert max(a["by_season"], key=lambda b: b["slope_per_decade"])["season"] == "winter"


def test_seasons_flip_names_south_of_equator():
    a = crossexam.seasons(_series(trend_per_year=0.05), "°C", -30)
    assert next(b for b in a["by_season"] if b["months"] == "DJF")["season"] == "summer"


def test_change_point_tells_step_from_steady_trend():
    step = crossexam.change_point("T2M", _series(step=2.0, step_at="2005-01"), "°C")
    assert step["status"] == "sudden_shift" and abs(step["year"] - 2005) <= 1
    ramp = crossexam.change_point("T2M", _series(trend_per_year=0.06), "°C")
    assert ramp["status"] in ("gradual", "none")
    flat = crossexam.change_point("T2M", _series(seed=5), "°C")
    assert flat["status"] == "none"


def test_change_point_flags_documented_data_change():
    cp = crossexam.change_point("CLOUD_AMT", _series(step=-3.0, step_at="2001-01"), "%")
    assert cp["status"] == "sudden_shift" and cp["near_data_change"]


def test_climate_modes_finds_the_mode_and_keeps_the_real_trend():
    nao = crossexam.climate_indices()["NAO"].reindex(IDX).fillna(0).to_numpy()
    s = _series(trend_per_year=0.03, noise=0.3, seed=7) + 1.0 * nao
    c = crossexam.climate_modes(s, "°C")
    assert c["links"][0]["mode"] == "NAO" and c["links"][0]["correlation"] > 0.5
    assert "NAO" in c["removed"] and c["status"] == "survives"
    assert abs(c["after"]["slope_per_decade"] - 0.3) < 0.1


def test_climate_modes_none_linked_for_pure_noise():
    assert crossexam.climate_modes(_series(seed=11), "°C")["status"] == "none_linked"
