"""Fill data/cache for every demo place x variable, for every endpoint the
website calls, so demos never wait on (or get rate-limited by) NASA POWER.
Run with the API code in-process (no server needed):
    POWER_RETRY_WAITS="10,30,60,120" uv run python scripts/prewarm.py
"""
import warnings
from fastapi.testclient import TestClient

from trend_detective.api import app
from trend_detective.catalogue import CATALOGUE

warnings.filterwarnings("ignore")
# Same boxes as frontend/src/lib.ts PLACES
PLACES = {
    "Lincolnshire": (52.6, 53.7, -1.0, 0.4), "England & Wales": (50.0, 55.5, -6.0, 2.0),
    "Wash estuary": (52.7, 53.2, 0.0, 0.6), "London": (51.2, 51.8, -0.6, 0.4),
    "Svalbard": (77.0, 80.0, 10.0, 20.0), "East Africa": (-5.0, 5.0, 33.0, 43.0),
    "Sahel": (12.0, 16.0, -5.0, 5.0), "Delhi": (28.0, 29.5, 76.5, 78.0),
    "Beijing": (39.0, 41.0, 115.5, 117.5), "Amazon (Rondonia)": (-12.0, -8.0, -66.0, -60.0),
    "Spain (Iberia)": (37.0, 42.0, -7.0, -1.0),
}
c = TestClient(app)
fails = []
for name, b in PLACES.items():
    q = f"lat_min={b[0]}&lat_max={b[1]}&lon_min={b[2]}&lon_max={b[3]}"
    r = c.get(f"/api/report-card?{q}")
    print(name, "report-card", r.status_code, flush=True)
    for v in CATALOGUE:
        for ep in ("analyse", "map", "context"):
            r = c.get(f"/api/{ep}?var={v['id']}&{q}")
            if r.status_code != 200:
                fails.append((name, v["id"], ep, r.status_code, r.text[:80]))
        print(f"  {name} {v['id']} done", flush=True)
print("FAILED:", len(fails))
for f in fails:
    print("  ", f)
