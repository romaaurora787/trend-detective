"""NASA vs ESA: compare MERRA-2 topsoil wetness (NASA POWER) with ESA CCI
satellite soil moisture over the same box, and map ESA trends with FDR.

Also writes a compact UK subset (data/external/esa_cci_sm_monthly_uk.nc) that
the app can serve. Prints a markdown summary.

usage: uv run python scripts/compare_esa.py data/external/esa_cci_sm_monthly_europe.nc
"""
import sys
import warnings

import numpy as np
import pandas as pd
import xarray as xr

from trend_detective import power, stats

warnings.filterwarnings("ignore")
src = sys.argv[1]
ds = xr.open_dataset(src)
START = "1992-01-01"  # before ~1991 only SMMR/SSM-I: sparse and less consistent
MIN_DAYS = 5  # a monthly cell value needs >= 5 valid days

uk = ds.sel(lat=slice(56.0, 49.5), lon=slice(-6.5, 2.0))
uk.to_netcdf("data/external/esa_cci_sm_monthly_uk.nc")


def box_series(d, la0, la1, lo0, lo1):
    b = d.sel(lat=slice(la1, la0), lon=slice(lo0, lo1))
    sm = b.sm.where(b.n_days >= MIN_DAYS)
    w = np.cos(np.radians(b.lat))
    s = sm.weighted(w).mean(("lat", "lon")).to_series()
    return s[s.index >= START].dropna()


print("| Box | Dataset | Period | Trend per decade (95% range) | Verdict |\n|---|---|---|---|---|")
for name, box in [("Lincoln (server box)", (52.4, 53.8, -2.0, 0.8)), ("England & Wales", (50.0, 55.5, -6.0, 2.0)),
                  ("Iberia", (36.0, 44.0, -10.0, 0.0)), ("Northern Europe", (50.0, 60.0, 0.0, 10.0))]:
    e = box_series(ds, *box)
    re_ = stats.analyse(e, "m³/m³")
    p, _ = power.fetch_area_series("GWETTOP", *box)
    p = p.dropna()
    p = p[p.index >= START]
    rp = stats.analyse(p, "fraction")
    a1, _ = stats.deseasonalise(e)
    a2, _ = stats.deseasonalise(p)
    j = pd.concat([a1, a2], axis=1, join="inner")
    corr = j.corr().iloc[0, 1]
    for lab, r in [("ESA CCI (satellite)", re_), ("NASA MERRA-2 topsoil", rp)]:
        lo, hi = r["sen_ci95_per_decade"]
        print(f"| {name} | {lab} | {r['start']}–{r['end']} | {r['sen_slope_per_decade']:+.4f} ({lo:+.4f} to {hi:+.4f}) | {r['verdict']['label']} |")
    print(f"| {name} | anomaly correlation ESA vs NASA | | r = {corr:.2f} (n={len(j)}) | |")

print("\nESA map, England & Wales box, cells with >= 80% valid months since 1992:")
b = ds.sel(lat=slice(55.5, 50.0), lon=slice(-6.0, 2.0), time=slice(START, None))
sm = b.sm.where(b.n_days >= MIN_DAYS)
sl, ps = [], []
for i in range(sm.sizes["lat"]):
    for k in range(sm.sizes["lon"]):
        s = sm.isel(lat=i, lon=k).to_series().dropna()
        if len(s) < 0.8 * sm.sizes["time"]:
            continue
        a, p = stats.quick_cell_test(s)
        sl.append(a)
        ps.append(p)
sl, ps = np.array(sl), np.array(ps)
sig = stats.fdr(ps)
print(f"cells {len(ps)}, significant alone {(ps < 0.05).sum()}, after FDR {sig.sum()}, rising {(sig & (sl > 0)).sum()}, falling {(sig & (sl < 0)).sum()}")
