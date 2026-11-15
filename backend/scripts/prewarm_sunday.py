"""B7: pre-warm everything the Sunday site upgrades will call, so the demo never waits.

Covers what scripts/prewarm.py (Saturday) doesn't:
  - the G2 case cards (incl. central Wisconsin cloud and Delhi) on every endpoint a case page calls
  - the P2 compare presets
  - the new witnesses (GISTEMP for air temperature, GLDAS + GRACE for soil) at every demo place
  - report card (B5 clearest), cite (B6), validation (B4), world, globe (B3), opposites (B8), outlook (B9)

Run it twice:
  1. on a laptop, then commit backend/data/cache (the disk caches travel with git), and
  2. on the server after `git pull` + redeploy, against the live URL, to fill the in-memory caches:
       uv run python scripts/prewarm_sunday.py https://kaakserver.tail042e87.ts.net/trend-detective
With no URL it runs the API in-process (no server needed).

AI-use note: drafted with Claude (Anthropic) during the hackathon.
"""
import sys
import time
import warnings
from urllib.parse import quote

warnings.filterwarnings("ignore")

if len(sys.argv) > 1:
    import httpx
    BASE = sys.argv[1].rstrip("/")
    _c = httpx.Client(timeout=600)
    get = lambda path: _c.get(BASE + path)  # noqa: E731
else:
    from fastapi.testclient import TestClient
    from trend_detective.api import app
    _c = TestClient(app)
    get = _c.get

# Same boxes as frontend/src/lib.ts PLACES (+ the case-card boxes)
PLACES = {
    "Lincolnshire": (52.6, 53.7, -1.0, 0.4), "England & Wales": (50.0, 55.5, -6.0, 2.0),
    "Wash estuary": (52.7, 53.2, 0.0, 0.6), "London": (51.2, 51.8, -0.6, 0.4),
    "Svalbard": (77.0, 80.0, 10.0, 20.0), "East Africa": (-5.0, 5.0, 33.0, 43.0),
    "Sahel": (12.0, 16.0, -5.0, 5.0), "Delhi": (28.0, 29.5, 76.5, 78.0),
    "Beijing": (39.0, 41.0, 115.5, 117.5), "Amazon (Rondonia)": (-12.0, -8.0, -66.0, -60.0),
    "Spain (Iberia)": (37.0, 42.0, -7.0, -1.0),
    "Wisconsin": (42.5, 47.0, -92.9, -86.8), "Mediterranean Sea": (37.0, 40.0, 4.0, 8.0),
}
CASES = [  # (var, box, name): the G2 cards and other links in docs/SITE_UPGRADES.md
    ("T2M", (52.6, 53.7, -1.0, 0.4), "Lincolnshire"),
    ("GWETROOT", (50.0, 55.5, -6.0, 2.0), "England & Wales"),
    ("CLOUD_AMT", (44.0, 46.0, -91.0, -89.0), "Central Wisconsin"),
    ("PRECTOTCORR", (28.0, 29.5, 76.5, 78.0), "Delhi"),
    ("T2M", (28.0, 29.5, 76.5, 78.0), "Delhi"),
]
COMPARE = [  # (var, A, B)
    ("PRECTOTCORR", "Amazon (Rondonia)", "Sahel"),
    ("T2M", "Svalbard", "Lincolnshire"),
    ("T2M", "Lincolnshire", "London"),
]
q = lambda b: f"lat_min={b[0]}&lat_max={b[1]}&lon_min={b[2]}&lon_max={b[3]}"  # noqa: E731
box_s = lambda b: ",".join(str(x) for x in b)  # noqa: E731
fails = []


def hit(path):
    t = time.time()
    try:
        r = get(path)
        ok = r.status_code == 200
        if not ok:
            fails.append((path, r.status_code, r.text[:100]))
    except Exception as e:  # keep going: one slow source must not stop the rest
        ok = False
        fails.append((path, type(e).__name__, str(e)[:100]))
    print(f"{'ok ' if ok else 'ERR'} {time.time() - t:5.1f}s {path[:110]}", flush=True)


for p in ["/api/validation", "/api/world", "/api/globe?var=T2M&land_only=true", "/api/globe?var=PRECTOTCORR&land_only=true",
          "/api/opposites?var=T2M", "/api/opposites?var=PRECTOTCORR", "/api/hunches"]:
    hit(p)
for var, b, name in CASES:
    for ep in ("analyse", "cross-examine", "witnesses", "map", "context", "beyond", "drought" if var == "PRECTOTCORR" else None):
        if ep:
            hit(f"/api/{ep}?var={var}&{q(b)}" if ep != "drought" else f"/api/drought?{q(b)}")
    hit(f"/api/report-card?{q(b)}")
    hit(f"/api/cite?var={var}&name={quote(name)}")
    hit(f"/api/outlook?var={var}&{q(b)}")
for var, a, b in COMPARE:
    hit(f"/api/compare?var={var}&a={box_s(PLACES[a])}&b={box_s(PLACES[b])}&name_a={quote(a)}&name_b={quote(b)}")
for name, b in PLACES.items():  # new witnesses + B5 report card everywhere
    for var in ("T2M", "GWETTOP", "GWETROOT"):
        hit(f"/api/witnesses?var={var}&{q(b)}")
    for var in ("T2M", "PRECTOTCORR"):  # outlook: climate models via Open-Meteo (daily request limit per IP!)
        hit(f"/api/outlook?var={var}&{q(b)}")
    hit(f"/api/report-card?{q(b)}")
print("FAILED:", len(fails))
for f in fails:
    print("  ", f)
