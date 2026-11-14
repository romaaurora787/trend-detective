"""Tests for extreme-day counts and the MODIS greenness geometry (synthetic data, no network).

AI-use note: drafted with Claude (Anthropic) during the hackathon.
"""
import numpy as np
import pandas as pd

from trend_detective import heat, ndvi

DAYS = pd.date_range("1981-01-01", "2025-12-31", freq="D")


def _daily(warming_per_year=0.0, seed=0):
    rng = np.random.default_rng(seed)
    yrs = (DAYS.year - 1981).to_numpy()
    season = 10 * np.sin(2 * np.pi * (DAYS.day_of_year - 100) / 365)
    base = 10 + season + warming_per_year * yrs
    tx = base + 5 + rng.normal(0, 3, len(DAYS))
    tn = base - 5 + rng.normal(0, 3, len(DAYS))
    return pd.DataFrame({"T2M_MAX": tx, "T2M_MIN": tn, "T2MWET": base - 2}, index=DAYS)


def test_counts_are_per_year_and_local_thresholds_give_about_10_percent():
    y = heat.counts(_daily())
    assert list(y.index) == list(range(1981, 2026))
    # by construction the 1981–2010 base period has ~10% days above its own 90th percentile
    assert 30 <= y.loc[1981:2010, "hot_days"].mean() <= 43
    assert y["very_hot_days"].sum() <= 3  # highs peak near 25 °C, so 35 °C days are near-impossible


def test_warming_gives_more_hot_days_and_fewer_frosts():
    y = heat.counts(_daily(warming_per_year=0.08))
    early, late = y.loc[1981:1990].mean(), y.loc[2016:2025].mean()
    assert late["hot_days"] > early["hot_days"] * 1.5
    assert late["frost_nights"] < early["frost_nights"]


def test_short_years_are_dropped():
    df = _daily()
    df.loc["2025-03-01":"2025-12-31"] = np.nan
    assert 2025 not in heat.counts(df).index


# MODIS sinusoidal tile h17v03 (just west of 0° longitude, 50–60° N)
TILE = {"transform": [231.65635826395834, 0.0, -1111950.519667, 0.0, -231.65635826395825, 6671703.118],
        "shape": [4800, 4800], "date": "2020-01-01", "id": "x"}


def test_window_is_inside_the_tile_and_clipped_at_its_edge():
    r0, r1, c0, c1 = ndvi._window([52.6, 53.7, -1.0, 0.4], TILE)
    assert 0 <= r0 < r1 <= 4800 and 0 <= c0 < c1 <= 4800
    assert c1 == 4800  # the box crosses 0° longitude, which is this tile's east edge


def test_box_outside_the_tile_has_no_window():
    assert ndvi._window([52.6, 53.7, 1.0, 2.0], TILE) is None


def test_in_box_mask_follows_the_skewed_grid():
    box = [52.6, 53.7, -1.0, -0.2]
    win = ndvi._window(box, TILE)
    m = ndvi._in_box(box, TILE, win, (50, 50))
    # the bounding rectangle of a lat/lon box in sinusoidal space is wider than the box itself
    assert 0.6 < m.mean() < 1.0


def test_sinusoidal_projection_matches_modis_definition():
    x, y = ndvi._sinu(60.0, 10.0)
    assert abs(y - 6671703.118) < 1  # 60° N is the top of the v03 row
    assert abs(x - ndvi.R * np.radians(10) * 0.5) < 1e-6


# ----- drought index, derived VPD, reproduce links, shuffled map control
from trend_detective import drought, power, reproduce, stats  # noqa: E402

MONTHS = pd.date_range("1981-01-01", "2025-12-01", freq="MS")


def test_spi_is_standard_normal_over_the_baseline():
    rng = np.random.default_rng(1)
    rain = pd.Series(rng.gamma(2.0, 1.5, len(MONTHS)), index=MONTHS)
    s = drought.spi(rain, 3)
    base = s["1981":"2010"]
    assert abs(base.mean()) < 0.15 and 0.85 < base.std() < 1.15


def test_spi_sees_a_drying_climate():
    rng = np.random.default_rng(2)
    scale = np.linspace(2.0, 0.8, len(MONTHS))  # rain falls over time
    rain = pd.Series(rng.gamma(2.0, scale), index=MONTHS)
    s = drought.spi(rain, 3)
    assert (s["2016":] <= -1).mean() > (s["1981":"1990"] <= -1).mean()


def test_vpd_formula():
    t, td = pd.Series([20.0]), pd.Series([10.0])
    v = power.DERIVED["VPD"][1](t, td)
    assert abs(float(v.iloc[0]) - (2.338 - 1.228)) < 0.01  # FAO-56 table values, kPa
    assert float(power.DERIVED["VPD"][1](t, t).iloc[0]) == 0


def test_reproduce_links_widen_small_boxes_and_add_imerg_for_rain():
    ls = reproduce.links("PRECTOTCORR", [52.6, 53.7, -1.0, 0.4])
    power_url = ls[0]["url"]
    assert "latitude-min=52.15" in power_url and "latitude-max=54.15" in power_url
    assert any("GPM_3IMERGM" in l["url"] for l in ls)
    assert any("bbox=-1.0,52.6,0.4,53.7" in l["url"] for l in ls)
    assert len(reproduce.links("VPD", [50, 55, -6, 2])) == 2  # one POWER request per ingredient


def test_shuffled_control_flags_false_alarms_in_autocorrelated_noise():
    rng = np.random.default_rng(3)
    n, cells = len(MONTHS), 30
    common = np.zeros(n)
    for i in range(1, n):  # red noise shared by all cells (like a real region)
        common[i] = 0.9 * common[i - 1] + rng.normal()
    df = pd.DataFrame({c: common + 0.3 * rng.normal(size=n) for c in range(cells)}, index=MONTHS)
    c = stats.shuffled_control(df, n_perm=10)
    assert c["n_cells"] == cells and c["typical_hits_max"] >= 1
