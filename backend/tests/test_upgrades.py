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


def test_gistemp_cells_overlap_and_wrap():
    import numpy as np
    from trend_detective import gistemp
    c = np.array([-179.0, -1.0, 1.0, 77.0, 79.0, 179.0])
    assert list(gistemp._overlap(c, -0.6, 0.4)) == [False, True, True, False, False, False]  # Lincolnshire: both sides of 0°
    assert list(gistemp._overlap(c, 76.9, 77.4)) == [False, False, False, True, False, False]  # small box: one cell


def test_gldas_reads_both_layers_and_skips_sea():
    from trend_detective import gldas
    i0, i1, j0, j1 = gldas._indices([52.6, 53.6, -0.6, 0.4])
    assert (i1 - i0 + 1, j1 - j0 + 1) == (5, 5)  # a 1° box off the 0.25° lines touches 5 cells each way
    text = ("Dataset: x\n/lat, 52.625, 52.875\n"
            "/RootMoist_inst[0][0], 300, -9999\n/RootMoist_inst[0][1], 310, 320\n"
            "/SoilMoi0_10cm_inst[0][0], 30, -9999\n/SoilMoi0_10cm_inst[0][1], 31, 32\n")
    lat, arrs = gldas._parse(text)
    assert arrs["RootMoist_inst"].shape == (2, 2) and list(lat) == [52.625, 52.875]


def test_grace_witness_is_supporting_not_proof():
    from trend_detective import grace, witnesses
    assert not witnesses.fully_independent(grace.INDEPENDENCE)  # different quantity: never "confirmed"
    s = grace.monthly((-5, 5, 33, 43))
    assert len(s) > 200 and s.index.is_monotonic_increasing
    assert not ((s.index >= "2017-08-01") & (s.index <= "2018-04-01")).any()  # the mission gap stays empty


def test_globe_and_opposites():
    from trend_detective import api
    g = api.globe("T2M", land_only=True)
    assert len(g["cells"]) > 4000 and all("L" in c[3] for c in g["cells"])
    assert not any(abs(c[0]) == 90 for c in g["cells"])
    c = g["counts"]["land"]
    assert c["luck_ours"] < c["luck_typical"]  # on shuffled years our test is fooled far less often
    o = api.opposite_places("PRECTOTCORR", 3)
    assert o["rising"] and o["falling"] and o["rising"][0]["slope_per_decade"] > 0 > o["falling"][0]["slope_per_decade"]


def test_outlook_trend_and_scenarios_are_honest():
    from trend_detective import outlook
    g = outlook._global_annual().loc[1981:2025]
    rng = np.random.default_rng(7)
    # a place that warms 1.5x the globe, plus noise
    vals = []
    for yr in range(1981, 2026):
        for m in range(1, 13):
            vals.append(8 * np.sin(2 * np.pi * m / 12) + 1.5 * g.loc[yr] + rng.normal(0, 0.3))
    s = pd.Series(vals, index=MONTHS)
    sc = outlook.scenarios(s, "°C")
    assert sc["available"] and 1.2 < sc["beta_per_global_degree"] < 1.8
    low, mid, high = (r["change_by_2050"] for r in sc["scenarios"])
    assert 0 < low < mid < high  # more emissions, more change
    assert 0.9 < outlook.global_today()["now"] < 1.6
    a = {"verdict": {"label": "strong"}, "sen_slope_per_decade": 0.3, "sen_ci95_per_decade": [0.2, 0.4]}
    assert outlook.trend_whatif(a, "sudden_shift", "°C")["available"] is False  # a jump is never drawn on
    assert abs(outlook.trend_whatif(a, None, "°C")["change_by_2050"] - 0.9) < 1e-9
    noise = pd.Series(rng.normal(0, 1, len(MONTHS)), index=MONTHS)
    assert outlook.scenarios(noise, "mm/day")["available"] is False  # no proven link, no scenarios


def test_small_boxes_never_fall_under_powers_2_degree_minimum():
    from trend_detective import power
    # -2.3 .. -0.3 is 1.9999999 in floating point: POWER answered 422 for Nairobi on Sunday
    for lo, hi in [(-1.8, -0.8), (-2.03, -0.53), (28.0, 29.5), (51.2, 51.8), (-0.6, 0.4), (88.5, 89.5), (-89.9, -89.0)]:
        a, b = power._widen(lo, hi, 90)
        assert round(b, 2) - round(a, 2) >= 2.0 and a <= lo and b >= hi and -90 <= a and b <= 90
    assert tuple(round(x, 2) for x in power._widen(52.6, 53.7, 90)) == (52.15, 54.15)  # boxes that already worked keep their request (and cache)
