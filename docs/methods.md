# Methods: how the Detective decides (DRAFT, for Akshita to edit and own)

## The question
Is this variable really changing here, or is it just natural ups and downs? If it is changing, how fast, and how sure are we? If we can't tell yet, how long until we could?

## 1. The evidence: NASA monthly data
- **Source:** NASA POWER (NASA Langley Research Center). It serves NASA's **MERRA-2** reanalysis (GMAO), which covers temperature, rain, soil wetness, humidity, wind and aerosols, and **CERES / GEWEX SRB** satellite data for sunshine and cloud. All monthly, **January 1981 to December 2025** (45 years, 540 months).
- **Area average:** for a chosen box we average every NASA grid cell inside it (0.5° × 0.625°). Each cell is weighted by its area (cosine of latitude).

## 2. Remove the seasons
Lincoln's monthly temperature swings by about 13 °C between winter and summer. The long-term change is about 1.5 °C, so it is hidden inside that swing. We subtract each calendar month's 45-year average. What is left, the **anomaly**, is the part that can show a trend.

## 3. Two independent tests, both corrected for "sticky" noise
Natural variability is **autocorrelated**: a warm month tends to be followed by another warm month. Standard tests assume every month is independent, so they become over-confident and see trends that aren't there. Our synthetic experiment (section 6) shows this.

| Test | What it does | Correction |
|---|---|---|
| **Mann-Kendall** (Mann 1945; Kendall 1975) | Rank-based: does the series go up more often than down? No assumption of a straight line or normal data; resistant to outliers. | **Hamed & Rao (1998)** variance correction, using autocorrelation up to 12 months |
| **Least-squares trend t-test** | The classic straight-line fit | **Effective sample size** n_eff = n(1 − r₁)/(1 + r₁), where r₁ is the residuals' lag-1 autocorrelation |

**Why 12 lags:** with the library default (all lags), random "significant" lags made the correction unstable. Our 95% intervals then covered the true trend only 86–90% of the time in synthetic tests. With lags up to 12 months, coverage was 92–95%.

## 4. How fast: Sen's slope with a 95% range
**Sen's slope** (Sen 1968) is the median of the slopes between every pair of months, so a few extreme months can't drag it. The 95% range comes from the corrected Mann-Kendall variance (Gilbert 1987). We report it **per decade, in real units**. For mostly-zero variables such as frost days, most pair slopes are exactly 0, so we use the corrected least-squares slope and interval instead, and say so.

## 5. The verdict
| Verdict | Rule |
|---|---|
| **Strong evidence** | Both corrected tests p < 0.01 |
| **Some evidence** | Both corrected tests p < 0.05 |
| **Mixed** | One test p < 0.05, the other not |
| **Not significant yet** | Neither test p < 0.05, but at this rate it would show within 100 years |
| **No meaningful trend** | Neither significant, and it would take more than 100 years |

Requiring **both** tests to agree keeps false alarms at about 5% (section 6).

## 6. Proof it works (synthetic data with known answers)
We generated 45-year monthly series with a seasonal cycle and autocorrelated noise, where we know the true trend.

**No real trend** (500 series per setting): how often does each method wrongly claim one?

| Noise "stickiness" r₁ | 0.0 | 0.3 | 0.5 | 0.7 | 0.85 |
|---|---|---|---|---|---|
| Naive test (ignores autocorrelation) | 7% | 16% | 28% | 41% | **55%** |
| **Our verdict** | **5%** | **6%** | **6%** | **6%** | **7%** |
| Simple line on raw monthly data | 0% | 0% | 0% | 1% | 5% |

**Real trend** (r₁ = 0.5, noise SD 1, 300 series each): how often is it caught?

| True trend per decade | 0 | 0.1 | 0.2 | 0.3 | 0.4 |
|---|---|---|---|---|---|
| Naive test | 23% (false alarms) | 75% | 99% | 100% | 100% |
| **Our verdict** | **4%** | **39%** | **93%** | **100%** | **100%** |
| Simple line on raw monthly data | 0% | 0% | 6% | 61% | 99% |

**Reading it:** the naive test "finds" trends that don't exist. The simple raw-data line almost never raises a false alarm, but it misses real trends because the seasons drown them. Ours keeps false alarms near the promised 5% **and** still catches real trends.

![Proof it works](images/proof_it_works.png)

**Starting point:** NASA GES DISC's own published approach (Acker et al., SeaWiFS chlorophyll time series) fits a least-squares line to monthly Giovanni data and tests it with an F-test. We build on it with seasonal removal, a robust slope, autocorrelation correction and multiple-testing control.

## 6b. Cross-checks against other records (real data, same engine)
| Check | Other record | NASA (via POWER) | Monthly anomaly correlation |
|---|---|---|---|
| **Temperature, Central England, 1981–2025** | Met Office HadCET (thermometers): **+0.31 °C/decade** (0.21 to 0.41), strong | MERRA-2 T2M, 25 cells: **+0.32 °C/decade** (0.21 to 0.43), strong | **0.99** |
| **Rainfall, Lincoln box, 1983–2025** | NASA GPCP v3.3 (satellite + gauges): +0.031 mm/day/decade, not significant yet | MERRA-2 PRECTOTCORR, 15 cells: +0.029 mm/day/decade, not significant yet | **0.97** |

| **Soil moisture, 1992–2024** (Space Agency partner data) | **ESA CCI Soil Moisture COMBINED v09.2** (satellite microwave, daily → monthly, months with ≥5 valid days) | MERRA-2 topsoil wetness | 0.38 (Lincoln box) to 0.74 (Iberia) |

**Soil moisture:** NASA and ESA agree that **no region we tested (Lincoln, England & Wales, Iberia, Northern Europe) shows a significant soil-moisture trend since 1992.** Their month-to-month agreement is only moderate (r = 0.4–0.7). They measure different things: ESA sees the top few centimetres from space, while MERRA-2 is a model's topsoil layer in different units. At grid-cell level they disagree. ESA flags 39 of 205 England cells after the correction (16 wetter, 23 drier), while MERRA-2 flags none. Satellite soil-moisture records can contain jumps when sensors change, so we treat single-cell soil trends as **"needs a second witness"**, not a finding.

MERRA-2 does not assimilate land station air temperatures, so the HadCET agreement is close to an independent confirmation. MERRA-2's corrected rainfall partly uses gauge and GPCP information, so the rainfall agreement shows consistency, not independence.

## 7. How long until we'd know?
For trends that are not significant yet, we estimate the years of monthly data needed to detect a trend of the current size (5% level, 90% probability), following **Weatherhead et al. (1998)**:

n* ≈ [ (3.3 σ / |ω|) · √((1 + φ)/(1 − φ)) ]^(2/3)

Here ω is the trend per year, σ is the monthly noise standard deviation and φ is its lag-1 autocorrelation. Example: Lincolnshire wind speed is falling slightly, but not significantly yet; at that rate it needs about 69 years of data, so about 24 more.

## 8. Maps: many tests at once
Testing 150 grid cells at the 5% level gives about 7 "significant" cells by pure chance. We control the **false discovery rate** with Benjamini & Hochberg (1995) at q = 0.10, as recommended for climate maps by Wilks (2016).

**Real example:** root-zone soil wetness over England and Wales, 137 cells. **18** look significant on their own; **0** survive the correction. Without the correction we would have reported a drying or wetting signal that isn't there.

## 8b. Does the verdict depend on the years chosen? (robustness)
Where a trend line starts and ends can make or break it. Every verdict is re-run on four windows: the full record, starting 5 and 10 years later, and ending 5 years earlier. It is **Robust** if all windows agree on proven or not proven, and on direction. Otherwise it is **Fragile**, and the app says so. Lincolnshire warming is robust (+0.28 to +0.33 °C/decade across all four windows); Lincolnshire evaporation is fragile ("some evidence" for 1981–2025, "mixed" if the record ends in 2020).

## 8c. Beyond the trend line, and how we checked those methods
| Question | Method | False alarms on no-trend synthetic weather |
|---|---|---|
| Are records broken more often than chance? | Record counts in the last third of the record vs a permutation null that shuffles **whole years in 5-year blocks** | 5–7% (two-sided limit 10%). Shuffling single months gave **13–22%**, so we changed it |
| Is it getting more erratic? | Spread of detrended anomalies, second half vs first, same block permutation | 4.5–7.5% (target 5%). A standard Levene test on months gave **15–19%** |
| Did the trend turn at some year? | Straight line vs "hinge" (two joined lines), BIC gain > 10 | ≤ 7.7% even with strongly persistent years; real breaks found 93% of the time |
| When did it rise out of the noise? | First year the trend-implied change stays above 2× the year-to-year noise | ~0% |
| Which season? | Mann-Kendall per season, **Holm-corrected** across the four seasons | ≤ 10% (single seasons uncorrected gave 12%) |

Claims that failed the corrected tests were removed from our findings (for example "Amazon daytime highs 22% more erratic").

## 8d. The world report
The same engine run on 15 variables at 111 land points (a regular grid, 45°S–65°N): **1,615 checks**. A typical analysis (months treated as independent) claims a trend in 72% of them; the Detective proves 52%. **28% of typical claims can't be supported.** For root-zone soil moisture it is more than half (57 of 86). The Detective never proved a trend the typical analysis missed, so the difference is entirely over-claiming, not different findings.

## 8e. The cross-examination (questions a sceptic asks)
Run on every case (`/api/cross-examine`):
- **Instrument alibi:** a step at each documented change of satellite or model input vs a steady trend (BIC), and the trend re-tested on each single-source segment.
- **Climate modes:** El Niño (ONI), North Atlantic Oscillation, Indian Ocean Dipole and Pacific Decadal Oscillation are fitted **together with** the trend and removed (Foster & Rahmstorf 2011), so a mode that drifts itself can't take credit for a real trend.
- **One year carrying it?** (leave-one-year-out) · **two halves** (found in the first, does it hold in the second?) · **every start and end year** (15+ years), with a replay of when the evidence became strong · **speeding up?** (decade rates + a quadratic test with effective sample size).
- **Which months?** Each calendar month tested alone, Benjamini–Hochberg across the 12, plus the seasonal Kendall test and its correlated-seasons version (Hirsch et al. 1982; Hirsch & Slack 1984).
- **When did it change?** Pettitt (1979) change point, then "sudden shift or gradual?" by BIC, and whether the year sits next to a documented data change.
- **Grid resolution:** how many ~50 km cells really sit behind the number.

## 8f. Other witnesses and checks
- **Satellites:** MODIS NDVI (MOD13Q1) and land surface temperature (MOD11A2), Collection 6.1, Terra with Aqua as an independent second satellite. Only good-quality land pixels inside the box are averaged; missing months stay missing.
- **ERA5** (via Open-Meteo), **NOAA GHCN** weather stations, **NASA GPCP v3.3**, **ESA CCI soil moisture**, **Met Office HadCET**.
- **Climate models:** 7 CMIP6 HighResMIP models over the same years, with the caveat that they were given the real ocean temperatures until 2014.
- **Drought:** SPI-3 and SPI-12 (McKee et al. 1993; WMO 2012), gamma fit per calendar month on 1981–2010.
- **Map control:** whole years shuffled (same shuffle for every cell, so neighbours stay alike) to show how many cells a typical test marks as "changing" in pure noise.

## 8g. Decided before looking, and what changed afterwards
Git history (timestamps are public in the repo) shows the order:
| When (Sat 14 Nov) | Commit | What was fixed in advance |
|---|---|---|
| 13:28 | `d34e67c` | Tests (Hamed–Rao MK, OLS with effective n), verdict cut-offs (p < 0.01 strong, p < 0.05 some, "not yet" via Weatherhead), synthetic validation. **Before any demo place was scanned.** |
| 13:35 | `3d36213` | First demo-case scan, run with those rules. |
| 17:41 | `6414be3` | Region rules for the linked clues **written down before** the out-of-sample test (`4b741d3`, 18:07). Two rules failed and are reported as rejected. |

**Changed afterwards, and why:**
- `0aa226c` (19:25): the records and variability tests gave false alarms in our own synthetic checks, so they moved to a 5-year block permutation and some claims were **removed** because they no longer passed.
- `86d11b2` (19:45): our instrument-alibi scan showed many cloud and sunshine trends could be the 2001 satellite switch, so FINDINGS was corrected downward.

## 8h. Reproduce it yourself
`notebooks/reproduce_lincolnshire.ipynb` downloads NASA POWER directly (no server code) and gets the same +0.333 °C/decade. Every case also returns the exact NASA POWER request and the same box in NASA Giovanni (`result.reproduce`).

## 9. What this does *not* tell you
- **Trend ≠ cause.** We detect change; we don't attribute it.
- **MERRA-2 is a reanalysis:** a model constrained by observations. Soil wetness and evaporation are model estimates.
- **Straight-line trends** summarise 45 years; real change can speed up, slow down or jump (for example after a change in the satellite record).
- **Grid cells are about 50 km.** Your street may differ.

## References
- Benjamini, Y. & Hochberg, Y. (1995). Controlling the false discovery rate. *J. R. Stat. Soc. B* 57, 289–300.
- Gilbert, R. O. (1987). *Statistical Methods for Environmental Pollution Monitoring*. Van Nostrand Reinhold.
- Hamed, K. H. & Rao, A. R. (1998). A modified Mann-Kendall trend test for autocorrelated data. *J. Hydrology* 204, 182–196.
- Kendall, M. G. (1975). *Rank Correlation Methods*. Griffin.
- Mann, H. B. (1945). Nonparametric tests against trend. *Econometrica* 13, 245–259.
- Sen, P. K. (1968). Estimates of the regression coefficient based on Kendall's tau. *JASA* 63, 1379–1389.
- Weatherhead, E. C. et al. (1998). Factors affecting the detection of trends. *J. Geophys. Res.* 103(D14), 17149–17161.
- Wilks, D. S. (2016). "The stippling shows statistically significant grid points". *BAMS* 97, 2263–2273.
- Benestad, R. E. (2003). How often can we expect a record event? *Climate Research* 25, 3–13.
- Holm, S. (1979). A simple sequentially rejective multiple test procedure. *Scand. J. Statist.* 6, 65–70.
- Yue, S. & Wang, C. (2004). The Mann-Kendall test modified by effective sample size. *Water Resour. Manage.* 18, 201–218.
- Acker, J. G. et al. Time-series analysis of SeaWiFS chlorophyll (NASA GES DISC, NTRS).
- NASA POWER Project, power.larc.nasa.gov. Gelaro, R. et al. (2017), MERRA-2, *J. Climate* 30, 5419–5454.
- Foster, G. & Rahmstorf, S. (2011). Global temperature evolution 1979–2010. *Environ. Res. Lett.* 6, 044022.
- Gelman, A. & Stern, H. (2006). The difference between "significant" and "not significant" is not itself statistically significant. *Am. Stat.* 60, 328–331.
- Hirsch, R. M., Slack, J. R. & Smith, R. A. (1982). Techniques of trend analysis for monthly water quality data. *Water Resour. Res.* 18, 107–121.
- Hirsch, R. M. & Slack, J. R. (1984). A nonparametric trend test for seasonal data with serial dependence. *Water Resour. Res.* 20, 727–732.
- Pettitt, A. N. (1979). A non-parametric approach to the change-point problem. *Appl. Statist.* 28, 126–135.
- McKee, T. B., Doesken, N. J. & Kleist, J. (1993). The relationship of drought frequency and duration to time scales. *8th Conf. Applied Climatology*, AMS. WMO (2012) *Standardized Precipitation Index User Guide*, WMO-No. 1090.
- Randles, C. A. et al. (2017). The MERRA-2 aerosol reanalysis. *J. Climate* 30, 6823–6850.
- Lyapustin, A. et al. (2014). Scientific impact of MODIS C5 calibration degradation and C6+ improvements. *Atmos. Meas. Tech.* 7, 4353–4365.
- Didan, K. (2021). MOD13Q1 v061, NASA LP DAAC, doi:10.5067/MODIS/MOD13Q1.061. Wan, Z., Hook, S. & Hulley, G. (2021). MOD11A2 v061, doi:10.5067/MODIS/MOD11A2.061.
- Haarsma, R. J. et al. (2016). High Resolution Model Intercomparison Project (HighResMIP v1.0) for CMIP6. *Geosci. Model Dev.* 9, 4185–4208.
- Chen, C. et al. (2019). China and India lead in greening of the world through land-use management. *Nature Sustainability* 2, 122–129.
- Allen, R. G. et al. (1998). *Crop evapotranspiration* (FAO-56), for saturation vapour pressure / VPD.
