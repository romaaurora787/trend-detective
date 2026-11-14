"""Aggregate ESA CCI Soil Moisture COMBINED v09.2 daily files to monthly means.

Runs on the team server where the daily files live. For each region box it
writes a monthly NetCDF (mean of valid days per 0.25 deg cell, plus the count
of valid days). Daily files are only read, never modified.

usage: python esa_monthly.py DAILY_DIR OUT_DIR [workers]

AI-use note: drafted with Claude (Anthropic) during the hackathon.
"""
import os
import sys
import glob
import re
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import xarray as xr

REGIONS = {  # name: (lat_min, lat_max, lon_min, lon_max)
    "europe": (35.0, 72.0, -12.0, 40.0),
    "east_africa": (-5.0, 5.0, 33.0, 43.0),
}
LAT = np.arange(89.875, -90, -0.25)  # CCI grid, north to south
LON = np.arange(-179.875, 180, 0.25)


def idx(region):
    la0, la1, lo0, lo1 = REGIONS[region]
    ilat = np.where((LAT >= la0) & (LAT <= la1))[0]
    ilon = np.where((LON >= lo0) & (LON <= lo1))[0]
    return slice(ilat[0], ilat[-1] + 1), slice(ilon[0], ilon[-1] + 1)


SLICES = {r: idx(r) for r in REGIONS}


def month_job(args):
    ym, files = args
    sums = {r: None for r in REGIONS}
    counts = {r: None for r in REGIONS}
    for f in files:
        try:
            with xr.open_dataset(f, engine="h5netcdf", decode_timedelta=False) as ds:
                sm = ds["sm"]
                for r, (sl_lat, sl_lon) in SLICES.items():
                    a = sm.isel(time=0, lat=sl_lat, lon=sl_lon).values.astype("float64")
                    ok = np.isfinite(a)
                    if sums[r] is None:
                        sums[r] = np.zeros_like(a)
                        counts[r] = np.zeros(a.shape, dtype="int16")
                    sums[r] += np.where(ok, a, 0.0)
                    counts[r] += ok
        except Exception as e:  # skip unreadable day, keep going
            print("skip", f, e, flush=True)
    out = {}
    for r in REGIONS:
        if sums[r] is None:
            continue
        with np.errstate(invalid="ignore", divide="ignore"):
            mean = np.where(counts[r] > 0, sums[r] / np.maximum(counts[r], 1), np.nan)
        out[r] = (mean.astype("float32"), counts[r])
    return ym, out


def main():
    daily, outdir = sys.argv[1], sys.argv[2]
    workers = int(sys.argv[3]) if len(sys.argv) > 3 else 6
    os.makedirs(outdir, exist_ok=True)
    by_month = defaultdict(list)
    for f in glob.glob(os.path.join(daily, "*", "*.nc")):
        m = re.search(r"COMBINED-(\d{6})\d{8}-", os.path.basename(f))
        if m:
            by_month[m.group(1)].append(f)
    months = sorted(by_month)
    print(len(months), "months,", sum(len(v) for v in by_month.values()), "daily files", flush=True)
    results = {}
    with ProcessPoolExecutor(workers) as ex:
        for n, (ym, out) in enumerate(ex.map(month_job, [(m, by_month[m]) for m in months]), 1):
            results[ym] = out
            if n % 24 == 0:
                print(n, "of", len(months), flush=True)
    times = np.array([np.datetime64(f"{m[:4]}-{m[4:]}-01") for m in months])
    for r in REGIONS:
        sl_lat, sl_lon = SLICES[r]
        lat, lon = LAT[sl_lat], LON[sl_lon]
        shape = (len(months), len(lat), len(lon))
        sm = np.full(shape, np.nan, dtype="float32")
        nd = np.zeros(shape, dtype="int16")
        for i, m in enumerate(months):
            if r in results[m]:
                sm[i], nd[i] = results[m][r]
        ds = xr.Dataset(
            {"sm": (("time", "lat", "lon"), sm, {"units": "m3 m-3", "long_name": "monthly mean of valid daily surface soil moisture"}),
             "n_days": (("time", "lat", "lon"), nd, {"long_name": "valid days in month"})},
            coords={"time": times, "lat": lat, "lon": lon},
            attrs={"source": "ESA CCI Soil Moisture COMBINED v09.2 daily (CEDA), aggregated to monthly", "region": str(REGIONS[r])},
        )
        p = os.path.join(outdir, f"esa_cci_sm_monthly_{r}.nc")
        ds.to_netcdf(p, engine="h5netcdf")
        print("wrote", p, shape, flush=True)
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
