"""Tests for the Sunday backend upgrades (no network).

AI-use note: drafted with Claude (Anthropic) during the hackathon.
"""
import numpy as np
import pandas as pd

from trend_detective import beyond, cite

MONTHS = pd.date_range("1981-01-01", "2025-12-01", freq="MS")


def test_cite_lists_tool_data_and_method_in_three_formats():
    j = cite.citations("CLOUD_AMT", name="Central Wisconsin")
    keys = [i["key"] for i in j["items"]]
    assert keys[0] == "trenddetective" and "ceres" in keys and "gewex" in keys and "hamed_rao" in keys
    for i in j["items"]:
        assert i["apa"] and i["harvard"] and i["bibtex"]
    assert "Srivastava, A. and Sachan, K. K." in j["items"][0]["bibtex"]
    assert ".." not in j["items"][0]["apa"]
    assert [i["key"] for i in cite.citations("T2M")["items"]][1:3] == ["power", "merra2"]
    assert "modis" in [i["key"] for i in cite.citations("NDVI")["items"]]


def test_clarity_noise_is_the_year_to_year_swing():
    rng = np.random.default_rng(4)
    t = np.arange(len(MONTHS)) / 120  # decades
    season = 8 * np.sin(2 * np.pi * MONTHS.month.to_numpy() / 12)
    s = pd.Series(season + 0.5 * t + rng.normal(0, 0.4, len(MONTHS)), index=MONTHS)
    em = beyond.emergence(s)
    noise = em["noise_sd_annual"]
    # annual means of N(0, 0.4) monthly noise have sd about 0.4/sqrt(12) ≈ 0.12
    assert 0.07 < noise < 0.18
    total = 0.5 * 4.5  # 45 years at 0.5 per decade
    assert total / noise > 10  # a strong, clean trend is many times the normal swing
