"""Synthetic known-answer tests for beyond.py."""
import numpy as np
import pandas as pd

import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from trend_detective import beyond
from test_stats import synth


def test_records_no_trend_matches_chance():
    hits = sum(beyond.records(synth(trend_per_decade=0, phi=0.0, seed=s), n_perm=300)["p_highs"] < 0.05 for s in range(40))
    assert hits <= 6  # ~5% false alarms expected


def test_records_with_trend_detected():
    r = beyond.records(synth(trend_per_decade=1.0, noise=0.5, seed=1), n_perm=300)
    assert r["record_highs"] > r["expected"] and r["p_highs"] < 0.05


def test_emergence_found_for_strong_trend_not_for_none():
    assert beyond.emergence(synth(trend_per_decade=1.0, noise=0.5, seed=2))["year"] is not None
    assert beyond.emergence(synth(trend_per_decade=0.0, seed=3))["year"] is None


def test_seasons_finds_summer_only_trend():
    found, false_winter = 0, 0
    for seed in range(30):
        s = synth(trend_per_decade=0.0, noise=0.3, seed=seed)
        t = (s.index.year - s.index.year[0]).to_numpy()
        s = s + np.where(s.index.month.isin([6, 7, 8]), 0.15 * t, 0.0)  # summer only
        out = {o["season"].split(" ")[0]: o for o in beyond.seasons(s)["seasons"]}
        found += out["Summer"]["significant"]
        false_winter += out["Winter"]["significant"]
    assert found >= 28 and false_winter <= 3


def test_variability_detects_doubling():
    s = synth(trend_per_decade=0, phi=0.0, noise=1.0, seed=5)
    half = len(s) // 2
    s.iloc[half:] = s.iloc[half:] + np.random.default_rng(6).normal(0, 1.7, len(s) - half)
    r = beyond.variability(s)
    assert r["p"] < 0.05 and r["spread_ratio"] > 1


def test_turning_point_found_at_right_year():
    idx = pd.date_range("1981-01-01", periods=45 * 12, freq="MS")
    yrs = idx.year.to_numpy()
    rng = np.random.default_rng(7)
    y = np.where(yrs < 2005, 0.08 * (yrs - 1981), 0.08 * 24 - 0.10 * (yrs - 2005)) + rng.normal(0, 0.3, len(idx))
    r = beyond.turning_point(pd.Series(y + 3 * np.sin(2 * np.pi * idx.month / 12), index=idx))
    assert r["year"] is not None and abs(r["year"] - 2005) <= 3


def test_no_turning_point_for_straight_trend():
    r = beyond.turning_point(synth(trend_per_decade=0.5, noise=0.5, phi=0.0, seed=8))
    assert r["year"] is None
