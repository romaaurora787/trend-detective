"""Station cross-check: Met Office Hadley Centre Central England Temperature
(HadCET, thermometer record) vs NASA MERRA-2 2 m air temperature (via NASA
POWER) over the Central England triangle, 1981-2025, same stats engine."""
import warnings
import pandas as pd
from trend_detective import power, stats
warnings.filterwarnings("ignore")

rows = []
for line in open("data/external/hadcet_meantemp_monthly.txt"):
    p = line.split()
    if len(p) == 14 and p[0].isdigit():
        y = int(p[0])
        for m, v in enumerate(p[1:13], 1):
            if float(v) > -99:
                rows.append((pd.Timestamp(y, m, 1), float(v)))
cet = pd.Series(dict(rows)).sort_index()
cet = cet["1981-01-01":"2025-12-01"]
nasa, n = power.fetch_area_series("T2M", 51.5, 53.5, -3.0, 0.0)  # Lancashire-London-Bristol triangle, approx.
nasa = nasa.dropna()
rc, rn = stats.analyse(cet, "°C"), stats.analyse(nasa, "°C")
a1, _ = stats.deseasonalise(cet); a2, _ = stats.deseasonalise(nasa)
corr = pd.concat([a1, a2], axis=1, join="inner").corr().iloc[0, 1]
for lab, r in [("Met Office HadCET (thermometers)", rc), (f"NASA MERRA-2 T2M ({n} cells)", rn)]:
    lo, hi = r["sen_ci95_per_decade"]
    print(f"| {lab} | {r['start']}–{r['end']} | {r['sen_slope_per_decade']:+.3f} ({lo:+.3f} to {hi:+.3f}) °C/decade | {r['verdict']['label']} |")
print(f"monthly anomaly correlation r = {corr:.3f}")
