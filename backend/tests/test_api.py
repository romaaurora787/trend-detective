"""Smoke tests: every endpoint the website uses, on demo places whose NASA
responses are cached in data/cache (no network needed)."""
from fastapi.testclient import TestClient

from trend_detective.api import app
from trend_detective.catalogue import CATALOGUE

c = TestClient(app)
LINCS = "lat_min=52.6&lat_max=53.7&lon_min=-1.0&lon_max=0.4"
ENGLAND = "lat_min=50&lat_max=55.5&lon_min=-6&lon_max=2"


def ok(path):
    r = c.get(path)
    assert r.status_code == 200, (path, r.status_code, r.text[:300])
    return r


def test_health_and_variables():
    assert ok("/api/health").json()["ok"]
    assert len(ok("/api/variables").json()["variables"]) == len(CATALOGUE)


def test_analyse_has_all_panels():
    d = ok(f"/api/analyse?var=T2M&{LINCS}").json()
    r = d["result"]
    assert r["verdict"]["label"] == "strong"
    for k in ("typical_vs_detective", "robustness", "sen_ci95_per_decade"):
        assert k in r
    assert d["second_witness"]["available"]


def test_report_card_groups():
    d = ok(f"/api/report-card?{LINCS}").json()
    assert sum(len(g["items"]) for g in d["groups"]) + len(d["errors"]) + len(d["not_yet_read"]) == len(CATALOGUE)
    for g in d["groups"]:
        for i in g["items"]:  # issue 2.1: every item says whether a data-source change was checked
            assert i["instrument_check"]["status"]


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


def test_new_cached_endpoints_on_lincolnshire():
    q = "lat_min=52.6&lat_max=53.7&lon_min=-1.0&lon_max=0.4"
    x = ok(f"/api/cross-examine?var=T2M&{q}").json()
    assert x["score"]["passed"] == 5 and x["alibi"]["status"] == "no_known_change"
    c = ok("/api/compare?var=T2M&a=52.6,53.7,-1.0,0.4&b=50.5,51.8,-0.6,0.8").json()
    assert "rates_differ" in c["labels"]
    h = ok(f"/api/hunch?id=hotter_summers&{q}").json()
    assert h["verdict"] == "real"
    a = ok(f"/api/analyse?var=T2M&{q}&start=1991&end=2020").json()
    assert a["result"]["start"] == "1991-01" and a["result"]["vs_world"]["ratio"] > 0


def test_variables_ready_flag_for_satellite_variables():
    d = c.get("/api/variables?lat_min=52.6&lat_max=53.7&lon_min=-1.0&lon_max=0.4").json()
    by = {v["id"]: v for v in d["variables"]}
    assert by["T2M"]["ready"] and by["NDVI"]["ready"]  # Lincolnshire is pre-read
    far = c.get("/api/variables?lat_min=10&lat_max=10.5&lon_min=10&lon_max=10.5").json()
    assert not {v["id"]: v for v in far["variables"]}["NDVI"]["ready"]
