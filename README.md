# Trend Detective: is it really changing?

**NASA Space Apps Challenge 2026 · "Be An Earth System Trend Detective!" · Team Paani Ke Batashe (Akshita Srivastava, Kanishk K. Sachan) · Lincoln, UK**

**Live site:** https://kaakserver.tail042e87.ts.net/trend-detective/ · **Deck:** [docs/demo/trend_detective_slides.pdf](docs/demo/trend_detective_slides.pdf) · **30 s video:** [docs/demo/trend_detective_demo.mp4](docs/demo/trend_detective_demo.mp4) · **Project text:** [docs/SUBMISSION.md](docs/SUBMISSION.md)

Pick any place on Earth and a NASA variable (temperature, rain, soil moisture, haze, greenness and more). Trend Detective tells you honestly whether it is really changing or could be chance, then tries to break its own answer.

## What sets it apart

It has what the strongest projects in this challenge have: any place, tests corrected for "sticky" noise, a false-discovery check on maps, a world globe, a second NASA record, a sudden-jump test, El Niño removed, two places compared, plain and detailed wording, and citations. On top of that, it puts six things together in one tool:

1. **An instrument check for the documented changes in NASA's data sources** (2001 sunlight, cloud and heat radiation; 2014 aerosols; deep soil; 1987 rain), re-tested on single-source years. Worldwide, **42 of 88 proven cloud-cover trends could be the instrument, not the sky.**
2. **False alarms measured on monthly data:** 6% on pure noise vs 28–55% for a typical test, with 99.7% of real 0.3-per-decade trends still caught.
3. **Witnesses counted for independence:** station thermometers, rain gauges, GPCP, IMERG, ESA CCI, GLDAS, GRACE and ERA5, each labelled for how independent it is.
4. **Four ocean cycles removed together** (El Niño, NAO, Indian Ocean Dipole, PDO), with a careful "hidden change" flag.
5. **The world on trial:** 2,013 checks (111 places × 19 variables) show that 29% of typical trend claims don't hold. A luck test on 4,498 land squares: a typical test is fooled 22% of the time, ours 7%.
6. **Around 2050, three what-ifs:** our trend drawn on, 7 CMIP6 models and 3 IPCC emission paths, with a refusal when the change is one sudden jump.

Every number is computed from the data, never written by AI. Each case links to a CSV, the exact NASA request, NASA Giovanni and a notebook that rebuilds it.

---

*For developers (and the Claude agents helping us): start with [docs/FULL_REPORT.md](docs/FULL_REPORT.md) for status, every endpoint and demo numbers.*

## Run the backend

```bash
cd backend
uv sync
uv run uvicorn trend_detective.api:app --reload --port 8000
uv run pytest -q          # stats tests
```

No login needed: data comes from the **NASA POWER** API (MERRA-2 and CERES, monthly, 1981–2025). Every response is cached in `backend/data/cache/`, so demo cases work offline. Commit the cache for the demo regions.

## Run the website

```bash
cd frontend
npm install
npm run dev               # http://localhost:5173, talks to http://localhost:8000
```

Vite + React + TypeScript, no UI or chart library (charts are hand-drawn SVG; Leaflet for the maps). Views: Case (place → variable → verdict), Report card, Map (typical vs Detective toggle), How it works (proof charts). The saved responses in `docs/examples/` show instantly while the live server answers, so the demo never opens on a spinner.

**Deploy to Vercel:** import the repo, set Root Directory to `frontend`, and add the env var `VITE_API_URL` = your Render backend URL (no trailing slash).

## API for the frontend (Kanishk)

Base URL locally: `http://localhost:8000`. GET only, CORS open. Real example responses are in [`docs/examples/`](docs/examples/).

### `GET /api/variables`
The fixed catalogue ("suspects"). The AI variable finder may only return ids from this list.
```json
{"variables": [{"id": "T2M", "name": "Air temperature", "units": "°C", "source": "MERRA-2",
  "plain": "...", "tags": ["city", "farm", ...], "caveat": ""}, ...],
 "place_types": {"city": "Big city", "farm": "Farmland", ...}}
```

### `GET /api/analyse?var=T2M&lat_min=52.6&lat_max=53.7&lon_min=-1.0&lon_max=0.4`
Area-averaged monthly series for the box, with the full verdict. The box can be at most 10° × 10°. Small boxes are fine: we use the grid cells inside, or the nearest one.

Key fields (see [`docs/examples/analyse_T2M_lincolnshire.json`](docs/examples/analyse_T2M_lincolnshire.json)):

| Field | Show it as |
|---|---|
| `result.verdict.label` | Badge colour: `strong`, `some`, `mixed`, `not_yet`, `none` |
| `result.verdict.headline` | The big sentence on the verdict card (numbers already filled in by code) |
| `result.verdict.tests_agree` | "Both tests agree" tick |
| `result.sen_slope_per_decade`, `result.sen_ci95_per_decade` | "+0.33 °C per decade (95% range 0.23 to 0.44)" |
| `result.total_change` | "about +1.5 °C since 1981" |
| `result.years_to_detect`, `result.record_years` | For `not_yet`: "about N more years needed" = years_to_detect − record_years |
| `result.mk_hamed_rao.p`, `result.ols_neff.p` | Details panel |
| `result.baseline_raw_ols` | Methods comparison: simple straight-line fit on raw data |
| `result.seasonal_amplitude` | "The seasons swing by 13 °C; the trend is hidden inside that" |
| `chart.dates`, `chart.values` | Chart 1: raw monthly values |
| `chart.anomalies`, `chart.trend_line` | Chart 2: seasons removed + trend line (`trend_line` = [y at first date, y at last date]) |
| `chart.annual_years`, `chart.annual_anomalies` | Optional bar chart of yearly anomalies (warming-stripes style) |
| `citation` | Put under the chart and in the case report |
| `n_cells` | "Average of N NASA grid cells" |

Errors: 400 bad box, 404 unknown variable, 422 too little data, 502 NASA POWER failed. Show the `detail` text.

### NEW (Sat night): cross-examination, comparison, witnesses, guides
All `GET` unless marked. Boxes are `lat_min,lat_max,lon_min,lon_max`. `/api/analyse` and `/api/cross-examine` take optional `start`/`end` years (≥10 years).
- `/api/cross-examine?var=..&lat_min=..` — the sceptic's questions. `alibi` (documented satellite/model input changes: step-vs-trend + each single-source segment), `el_nino` (NOAA ONI regressed out, Foster & Rahmstorf 2011; El Niño vs La Niña years), `leave_one_out`, `walk_forward` (first half → second half), `all_windows` (every start/end year ≥15 yrs), `decades` (+ speed-up test), `extremes` (early vs recent, top years), `resolution` (grid cells behind the number), `could_overturn[]`, `score`.
- `/api/compare?var=T2M&a=52.6,53.7,-1.0,0.4&b=50.5,51.8,-0.6,0.8&name_a=..&name_b=..` — tests the trend of A − B; labels `opposite_fitted_directions` / `supported_opposite_trends` / `rates_differ`, plus a `trap` warning when "one significant, one not" would mislead.
- `/api/witnesses?var=..&lat_min=..` — every independent record: Met Office / GPCP / ESA where available, **ERA5 anywhere** (Open-Meteo, ~1 request/min first time, then cached), **nearest NOAA weather station** (GHCN monthly) for temperature, rain and frost.
- `/api/profile?lat_min=..` — what kind of place this is, from its own data (hot desert, wet tropics, cold/snowy, hot, temperate, + coast, big city), with suggested variables.
- `/api/hunches`, `/api/hunch?id=hotter_summers&lat_min=..` — fact-check common beliefs: real / leaning / not backed up / the opposite (seasons flip south of the equator).
- `POST /api/upload` `{"csv": "date,value\n2001-01,4.2...", "units": "°C", "name": "My station"}` — your own data through the same Detective, cross-examination and beyond-the-line.
- `/api/events?lat_min=..` — NASA EONET natural events nearby (sparse before 2016).
- `/api/analyse` now also returns `result.vs_world` for temperature variables (rate vs NASA GISTEMP global).
- Catalogue now has 19 variables (added snow depth, dew point, day–night range, heat radiation from the sky).
- **Vegetation greenness `NDVI`** (20th variable): NASA MODIS Terra MOD13Q1 v6.1, 250 m, 16-day composites 2000–2025, read from the open Cloud-Optimised GeoTIFFs on Microsoft Planetary Computer (no login). Good-quality land pixels inside the box are averaged (cloud, snow and water left out) and turned into a monthly series, so `/api/analyse`, `/api/cross-examine`, `/api/compare`, `/api/hunch?id=greener` all work on it. **First look at a new box takes ~0.5–2 min** (hundreds of satellite images); cached after. `/api/witnesses?var=NDVI` adds **MODIS on Aqua** as an independent second satellite. Not on the grid map or in the world report (it isn't on the POWER grid). Code: `ndvi.py`.
- `/api/extreme-days?lat_min=..` — yearly counts from NASA POWER **daily** data: hot days (above the place's own 1-in-10 day), 35 °C days, tropical nights (≥20 °C), humid-heat days (wet-bulb ≥25 °C), frost nights, cold nights; each tested (Yue–Wang MK) with 1980s vs last-10-years. Code: `heat.py`.
- `/api/cross-examine` has three more checks: **`seasons`** (each calendar month tested alone, Benjamini–Hochberg across the 12, + seasonal Kendall and the correlated-seasons version; "is this a winter story or a summer story?"), **`change_point`** ("when did it change?": Pettitt test, then sudden shift vs steady trend by BIC, and whether the year sits next to a documented data change), **`climate_modes`** (which big climate mode this place follows — El Niño, North Atlantic Oscillation, Indian Ocean Dipole, Pacific Decadal Oscillation — and whether the trend survives removing all the linked ones together; Spain's winter rain vs NAO r = −0.65, Lincolnshire winter temperature vs NAO r = +0.53).
- **`VPD`**, vapour pressure deficit ("thirst of the air"), computed from POWER temperature and dew point; works on the map too. Amazon (Rondônia) +0.08 kPa/decade, strong.
- `/api/drought?lat_min=..` — Standardized Precipitation Index (McKee 1993; WMO 2012): drought months per year (SPI-3 ≤ −1 and ≤ −1.5) tested for a trend, plus the SPI-12 record and the driest 12 months. Rondônia: 0.9 → 9.4 drought months a year; Sahel driest = 1984.
- `/api/map` now returns **`shuffled_control`**: the years are shuffled (same shuffle for every cell, so the region stays realistic), destroying any trend, and we count how many cells a typical test still calls "changing". England & Wales soil wetness: about 60 of 137 cells in pure noise.
- `/api/analyse` returns **`result.reproduce[]`**: the exact NASA POWER API request (CSV, no login), the same box in **NASA Giovanni**, and for rain the **GPM IMERG** satellite record in Giovanni as an independent check.
- [`notebooks/reproduce_lincolnshire.ipynb`](notebooks/reproduce_lincolnshire.ipynb): rebuilds the Lincolnshire verdict straight from the NASA POWER API with no server code; it gets the same +0.333 °C/decade.
- **`LST_DAY` / `LST_NIGHT`**: MODIS land surface temperature (MOD11A2 v6.1, 1 km, 8-day), same reader as NDVI, Aqua as second satellite. Delhi: nights +0.70 °C/decade (Aqua agrees), late-morning −0.43 (Aqua's afternoon pass: −0.24, not proven).
- `all_windows` (cross-examine) now has **`timeline` + `became_proven`**: replay the record year by year — "the evidence became strong by 1999 and has stayed strong since".
- `/api/analyse` returns **`result.coverage`** (months present / expected, longest gap; missing months are never filled).
- `/api/models?var=T2M&lat_min=..` — **did climate models see it coming?** Observed trend vs 7 CMIP6 HighResMIP models for the same years, and their 2026–2050 range (Open-Meteo Climate API; caveats returned with it).
- **NASA GPM IMERG** satellite rainfall (V07 monthly, 0.1°, 1998 onward) is now a witness in `/api/witnesses?var=PRECTOTCORR` for any box: only the box is downloaded through NASA's cloud OPeNDAP (~1 min the first time, cached after). Needs `EARTHDATA_TOKEN` in `backend/.env` (git-ignored; see `creds.py`) and the "NASA GESDISC DATA ARCHIVE" app approved on that Earthdata account. Code: `imerg.py`.
- `data/world_report.json` now has an **instrument alibi** per variable (`alibi` counts and `n_proven_after_alibi`; per point `cells[].alibi`): e.g. cloud cover 88 proven points, 42 of them could be the 2001 instrument switch.

### NEW: what makes us different (show these prominently)
**A. Typical vs Detective.** Every `/api/analyse` result has `result.typical_vs_detective`:
`typical_says` (what a typical straight-line analysis would claim), `outcome` (`fooled`, `agree_trend`, `missed`, `agree_none`) and `note` (one sentence for the card). Show the two side by side: *"A typical analysis says… / The Detective says…"*. On maps, `summary.story` gives the sentence and `summary.n_significant_typical` vs `summary.n_significant_fdr` gives the numbers. Each cell also has `significant_typical`, so you can toggle "typical map" vs "Detective map" (**the key demo**: England soil, typical 89 of 137 cells → Detective 0).

**B. Place report card.** `GET /api/report-card?lat_min=..&lat_max=..&lon_min=..&lon_max=..` runs all 15 variables for the place. `groups` contains **Proven change / Not proven yet / No trend detected**. Each item has `name`, `headline`, `slope_per_decade`, `ci95`, `units`, `more_years_needed` (for "not yet"), `typical_note` and `second_witness`. `summary` is one sentence. First call takes ~10–20 s (15 NASA requests), then it's cached. Example: [`docs/examples/report_card_lincolnshire.json`](docs/examples/report_card_lincolnshire.json).

**C. Second witness.** `/api/analyse` and each report-card item have `second_witness`: `available`, `name` (e.g. Met Office HadCET, NASA GPCP, ESA CCI soil moisture), `badge` (`confirmed` → ✔ "Confirmed": a fully independent record proves the same trend; `consistent` → "Consistent": both find no proven trend, or the witness shares input data with MERRA-2, as GPCP, IMERG and ERA5 do; `caution` → ⚠ "Caution": they disagree), `agrees` (kept for compatibility: true for confirmed or consistent), `independence`, `note`, `monthly_correlation`, `period`. If `available` is false, show nothing or "no second witness yet".

### NEW: any place + the case file (see [FRONTEND_TASKS.md](FRONTEND_TASKS.md) for how to show them)
- `GET /api/places?q=delhi`: search 34,215 world cities and towns (GeoNames, offline). Each result has a ready `box`.
- `GET /api/context?var=..&lat_min=..&lat_max=..&lon_min=..&lon_max=..`: the case file around a verdict. `nearby` (local or regional? every surrounding cell tested with FDR), `impact` (change as % of normal; how often recent years beat old 1-in-10 extremes), `linked` (tested links re-checked at this place, with a story) and `beyond` (records, emergence, seasons, variability, turning point). Each section can independently be `{"error": ...}`.

### NEW: beyond the trend line
`GET /api/beyond?var=T2M_MAX&lat_min=..&lat_max=..&lon_min=..&lon_max=..` returns five panels. Each has a `headline` with the numbers already filled in:
- `records`: record highs and lows in the recent third of the record vs what chance gives (`record_highs`, `expected`, `ratio_highs`, `p_highs`, and the same for `_lows`). Show as **"Records broken 3.1× as often as chance"**.
- `emergence`: `year` the change rose out of the noise (null if not yet). Show as **"Emerged from the noise in 2016"**.
- `seasons`: per-season `slope_per_decade`, `significant` (Holm-corrected). Show as 4 small bars, with the significant ones solid.
- `variability`: `spread_ratio`, `p`. Is it getting more erratic?
- `turning_point`: `year` (null if a straight line is enough), `slope_before_per_decade`, `slope_after_per_decade`.

Example: [`docs/examples/beyond_T2M_MAX_lincolnshire.json`](docs/examples/beyond_T2M_MAX_lincolnshire.json). Real findings: [`docs/beyond_scan.md`](docs/beyond_scan.md).

### NEW: linked clues (Methods / "how variables connect" page)
`GET /api/links` returns the pre-registered rules and out-of-sample hit rates (`summary[]`: `link`, `grid` = global/uk, `inside_holds`/`inside_n`, `outside_holds`/`outside_n`). Static; just render it. Write-up: [`docs/linked_clues.md`](docs/linked_clues.md).

### `GET /api/map?var=GWETROOT&lat_min=50&lat_max=55.5&lon_min=-6&lon_max=2`
One trend per grid cell (0.5° × 0.625°). Each cell: `lat`, `lon` (cell centre), `slope_per_decade`, `p`, `significant_raw`, `significant_fdr`.
- Colour: diverging by `slope_per_decade` (blue falling, red rising; reverse for rainfall and soil).
- Mark `significant_fdr` cells (dot or outline). These survive the false-discovery-rate correction.
- `summary` gives the counts. Teaching moment from the example: soil moisture over England has **18 cells "significant" on their own, 0 after correction**.
- Boxes smaller than 2° are widened to 2° (NASA POWER rule). About 2 seconds uncached.

### `GET /api/validation`
Synthetic-data proof for the Methods page (JSON from `backend/scripts/validate_*.py`):
- `validation.false_alarm_rate[method][i]` for `validation.phis[i]` (no real trend; the ideal is 0.05)
- `validation_power.detection_rate[method][i]` for `validation_power.trends_per_decade[i]`

## Repo layout
```
backend/src/trend_detective/
  stats.py      every number (Akshita)
  power.py      NASA POWER client + cache
  catalogue.py  the 15 allowed variables
  api.py        FastAPI
backend/tests/  synthetic tests with known answers
backend/scripts/validate_synthetic.py, validate_power.py   proof experiments
docs/examples/  real API responses
```

## Data and credits
Full list with licence wording: [docs/methods.md → Data credits and licences](docs/methods.md#data-credits-and-licences).
- **NASA:** POWER (MERRA-2 / GMAO; CERES / GEWEX SRB), GPM IMERG V07, GPCP v3.3, GISTEMP v4, EONET, MODIS MOD13Q1/MYD13Q1 and MOD11A2/MYD11A2 v6.1 (LP DAAC, via Microsoft Planetary Computer). NASA does not endorse this project.
- **ERA5:** contains modified Copernicus Climate Change Service information [2026]; served by Open-Meteo (CC BY 4.0), which also serves CMIP6 HighResMIP model data.
- **ESA CCI Soil Moisture** v09.2 (Dorigo et al. 2017; Gruber et al. 2019). **Met Office HadCET** (© Crown copyright, Open Government Licence v3.0). **NOAA** CPC, PSL, NCEI indices and GHCN stations. **GeoNames** (CC BY 4.0).
- Methods: Mann (1945); Kendall (1975); Sen (1968); Hamed & Rao (1998); Yue & Wang (2004); Weatherhead et al. (1998); Benjamini & Hochberg (1995); Wilks (2016); full list in docs/methods.md.
- Libraries: pymannkendall, statsmodels, scipy, numpy, pandas, FastAPI, rasterio.

## AI use
Code was drafted with help from Claude (Anthropic) during the hackathon, and the team checked it with tests and synthetic experiments. Files with AI-assisted code say so in their header. Verdict numbers are always computed by code, never by the AI.
