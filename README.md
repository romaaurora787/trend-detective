# Earth System Trend Detective

NASA Space Apps Challenge 2026, team Akshita + Kanishk.

Pick a place and a question. The app pulls NASA monthly data and answers in plain English: is it really changing, how fast, how sure are we, where, and how many more years until we would know.

## Run the backend

```bash
cd backend
uv sync
uv run uvicorn trend_detective.api:app --reload --port 8000
uv run pytest -q          # stats tests
```

No login needed: data comes from the **NASA POWER** API (MERRA-2 and CERES, monthly, 1981–2025). Every response is cached in `backend/data/cache/`, so demo cases work offline. Commit the cache for the demo regions.

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

### NEW: what makes us different (show these prominently)
**A. Typical vs Detective.** Every `/api/analyse` result has `result.typical_vs_detective`:
`typical_says` (what a typical straight-line analysis would claim), `outcome` (`fooled`, `agree_trend`, `missed`, `agree_none`) and `note` (one sentence for the card). Show the two side by side: *"A typical analysis says… / The Detective says…"*. On maps, `summary.story` gives the sentence and `summary.n_significant_typical` vs `summary.n_significant_fdr` gives the numbers. Each cell also has `significant_typical`, so you can toggle "typical map" vs "Detective map" (**the key demo**: England soil, typical 89 of 137 cells → Detective 0).

**B. Place report card.** `GET /api/report-card?lat_min=..&lat_max=..&lon_min=..&lon_max=..` runs all 15 variables for the place. `groups` contains **Proven change / Not proven yet / No trend detected**. Each item has `name`, `headline`, `slope_per_decade`, `ci95`, `units`, `more_years_needed` (for "not yet"), `typical_note` and `second_witness`. `summary` is one sentence. First call takes ~10–20 s (15 NASA requests), then it's cached. Example: [`docs/examples/report_card_lincolnshire.json`](docs/examples/report_card_lincolnshire.json).

**C. Second witness.** `/api/analyse` and each report-card item have `second_witness`: `available`, `name` (e.g. Met Office HadCET, NASA GPCP, ESA CCI soil moisture), `badge` (`confirmed` → ✔ "Confirmed": an independent record proves the same trend; `consistent` → "Consistent": both find no proven trend, or the witness shares input data with MERRA-2, as GPCP does; `caution` → ⚠ "Caution": they disagree), `agrees` (kept for compatibility: true for confirmed or consistent), `independence`, `note`, `monthly_correlation`, `period`. If `available` is false, show nothing or "no second witness yet".

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
- NASA POWER Project (NASA Langley Research Center), Prediction Of Worldwide Energy Resources, https://power.larc.nasa.gov. MERRA-2 (GMAO) meteorology; CERES / GEWEX SRB solar and cloud.
- Methods: Mann (1945); Kendall (1975); Sen (1968); Hamed & Rao (1998); Yue & Wang (2004); Weatherhead et al. (1998); Benjamini & Hochberg (1995); Wilks (2016).
- Libraries: pymannkendall, statsmodels, scipy, numpy, pandas, FastAPI.

## AI use
Code was drafted with help from Claude (Anthropic) during the hackathon, and the team checked it with tests and synthetic experiments. Files with AI-assisted code say so in their header. Verdict numbers are always computed by code, never by the AI.
