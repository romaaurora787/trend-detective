"""Smoke tests: every endpoint the website uses, on demo places whose NASA
responses are cached in data/cache (no network needed)."""
from fastapi.testclient import TestClient

from trend_detective.api import app

c = TestClient(app)
LINCS = "lat_min=52.6&lat_max=53.7&lon_min=-1.0&lon_max=0.4"
ENGLAND = "lat_min=50&lat_max=55.5&lon_min=-6&lon_max=2"


def ok(path):
    r = c.get(path)
    assert r.status_code == 200, (path, r.status_code, r.text[:300])
    return r


def test_health_and_variables():
    assert ok("/api/health").json()["ok"]
    assert len(ok("/api/variables").json()["variables"]) == 15


def test_analyse_has_all_panels():
    d = ok(f"/api/analyse?var=T2M&{LINCS}").json()
    r = d["result"]
    assert r["verdict"]["label"] == "strong"
    for k in ("typical_vs_detective", "robustness", "sen_ci95_per_decade"):
        assert k in r
    assert d["second_witness"]["available"]


def test_report_card_groups():
    d = ok(f"/api/report-card?{LINCS}").json()
    assert sum(len(g["items"]) for g in d["groups"]) + len(d["errors"]) == 15


def test_map_story():
    d = ok(f"/api/map?var=GWETROOT&{ENGLAND}").json()
    assert d["summary"]["n_significant_fdr"] == 0 and d["summary"]["n_significant_typical"] > 50


def test_beyond_and_context():
    b = ok(f"/api/beyond?var=T2M_MAX&{LINCS}").json()
    assert b["records"]["p_highs"] < 0.05
    ctx = ok(f"/api/context?var=T2M&{LINCS}").json()
    assert ctx["nearby"]["kind"] == "regional"
    assert "extremes_headline" in ctx["impact"] and isinstance(ctx["linked"], list)


def test_places_and_csv():
    res = ok("/api/places?q=lincoln").json()["results"]
    assert any(p["country"] == "United Kingdom" for p in res)
    csv = ok(f"/api/evidence.csv?var=T2M&{LINCS}").text
    assert csv.count("\n") > 500 and "month,value" in csv


def test_static_endpoints():
    assert ok("/api/links").json()["summary"]
    assert "validation" in ok("/api/validation").json()


def test_bad_input():
    assert c.get(f"/api/analyse?var=NOPE&{LINCS}").status_code == 404
    assert c.get("/api/analyse?var=T2M&lat_min=0&lat_max=20&lon_min=0&lon_max=5").status_code == 400
