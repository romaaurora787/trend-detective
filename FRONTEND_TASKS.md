# Frontend tasks for Kanishk (written Sat 14 Nov, ~19:20)

Your site (branch `frontend`) works end to end. Akshita and Claude clicked through every view: case, report card, map (England soil 89 → 0), methods; no console errors, a clean build, and the phone layout fits. This file lists **what to add or fix next**, in priority order. Every backend endpoint below is **already built, tested and on `main`**. Real example responses are in `docs/examples/`.

## 0. First: get the latest backend
```bash
git checkout frontend
git merge origin/main            # new endpoints: /api/places, /api/context, /api/beyond, /api/links
git merge origin/wording-fixes   # your own wording branch; both merge cleanly (checked)
cd backend && uv sync && uv run uvicorn trend_detective.api:app --reload
```

---

## 1. Any place in the world: search box (HIGH)
**Problem Akshita found:** the place menu only has 11 presets (one city per country), and "Pick on a map" is hidden.

**Endpoint:** `GET /api/places?q=delhi&limit=8` searches 34,215 world cities and towns (GeoNames, offline, no API key, ~0.3 s first call, then instant).
```json
{"results": [{"name": "New Delhi", "country": "India", "region": "Delhi", "lat": 28.636, "lon": 77.224,
  "population": 317797, "label": "New Delhi, Delhi, India", "box": [27.87, 29.37, 76.47, 77.97]}]}
```
- Put a **type-ahead search input** first in the controls row ("Search any city or town…"). Debounce ~200 ms; show `label` plus a muted population. On select → `go({ box: result.box })`.
- Supports "paris, fr" (city, country prefix) and accents ("sao paulo" finds São Paulo).
- Keep the presets as "Demo cases" (they have cached data and load instantly).
- `placeName(box)` should show the searched name, not coordinates. Keep the chosen `label` in state or the URL hash (e.g. `&name=New%20Delhi`).
- Attribution in the footer: "Places: GeoNames (CC BY 4.0)".

## 2. The case file: what's around it, what it means, what else is happening (HIGH)
**Problem Akshita found:** for New Delhi rainfall the page shows a verdict and stops. There's nothing about nearby places, whether that's significant, what it means, or what else is happening.

**Endpoint:** `GET /api/context?var=PRECTOTCORR&lat_min=..&lat_max=..&lon_min=..&lon_max=..` takes ~4 s uncached (2–4 NASA calls), instant when cached. Examples: `docs/examples/context_PRECTOTCORR_new_delhi.json`, `docs/examples/context_T2M_lincolnshire.json`. **Each section can come back as `{"error": "..."}` on its own.** Hide that section, never the page.

Add a new block **below the figure plate** on the case page: "**The case file**", with four parts.

### 2a. Nearby: local or regional? → `nearby`
- `headline`: the main sentence. Real examples:
  - New Delhi rain: *"Not proven at this spot, but the area around it is changing: 99 cells rising and 0 falling after the correction."*
  - Lincolnshire temperature: *"Regional, not just here: 120 of 120 surrounding cells show the same proven rising trend."*
- `kind`: `regional` | `local` | `patchy` | `opposite` | `around` | `quiet` | `unknown`. Use it for a small tag.
- `cells[]`: `lat`, `lon`, `slope_per_decade`, `p`, `significant_fdr`, `inside` (true = inside the user's box). Draw a **small static map** (an SVG grid is enough, no Leaflet needed): each cell coloured by slope (use your `dirTone`), significant cells solid or outlined, the user's box outlined. Cells with `p: null` are "no data / never changes" (grey).
- `region_box` is the area shown (about 6° × 6° around the place). `fdr_q` = 0.1.

### 2b. What it means → `impact`
- `size_headline`: *"Change so far: +0.243 mm/day since 1981, +13% of the long-term average (1.91 mm/day)."* (`percent_of_mean` is null for temperatures; that's on purpose.)
- `extremes_headline`: the big one. Example (Lincolnshire temperature): *"6 of the last 10 summers were warmer than what used to be a 1-in-10 summer (1981–2010). By chance we'd expect about 1."*
- `extremes[]`: `period` (year / winter / spring / summer / autumn), `count`, `out_of`, `expected`, `p`. Show as a small table or 5 mini bars of count vs expected (1). Make the `p < 0.05` rows bold.

### 2c. What else is changing here, and is it connected? → `linked[]`
Only links that passed our out-of-sample test (`docs/linked_clues.md`), re-tested **at this place**.
- Each item: `text` (the link), `evidence` (how often it held worldwide), `partner_name`, `holds_here` (bool), `r`, `partner_verdict`, `partner_slope_per_decade`, `partner_units`, `role` (cause/effect), `story` (the sentence to show).
- Show: link text → ✔ "holds here (r = +0.71)" or ✖ "doesn't hold here" → the partner's verdict badge → `story`. Make the partner name a link that opens that variable's case (`go({ varId: partner })`).
- An empty list is normal (no tested link for that variable). Show "No tested links for this variable yet" plus a button to the **report card** ("See everything else changing here").

### 2d. Beyond the trend line → `beyond`
Same as `/api/beyond` (see README). Five small tiles:
- **Records:** `records.headline`; big number `ratio_highs` (or `ratio_lows`) "× chance" when `p_highs` (or `p_lows`) < 0.05.
- **Emerged from the noise:** `emergence.year` (or "not yet": show `headline`).
- **Seasons:** 4 small bars from `seasons.seasons[]` (`slope_per_decade`, solid if `significant`).
- **More erratic?** `variability.headline`.
- **Turning point:** `turning_point.headline`; if `year` is not null, draw a vertical line at that year on chart b.

## 2e. NEW (Sat ~19:30): three more backend pieces to show

**Robustness badge** → `/api/analyse` now has `result.robustness`:
- `robust` (true / false / null), `headline`, `windows[]` (`window`, `period`, `label`, `slope_per_decade`).
- Show a small tag next to the verdict: **"Robust"** (green) or **"Fragile: depends on the years chosen"** (amber), with `headline` on hover or tap. Real examples: Lincolnshire warming is *Robust (+0.28 to +0.33 °C/decade across 4 windows)*; Lincolnshire evaporation is *Fragile ('some' for 1981–2025, 'mixed' if it ends in 2020)*.

**Download the evidence** → `GET /api/evidence.csv?var=..&lat_min=..` (a file download):
- A button on the case page: "Download the evidence (CSV)". Just an `<a href>` to the URL; the server sets the filename.
- Contains every month (value, seasonal normal, anomaly, trend line) plus header lines with the verdict, slope, p-values and citation. For teachers, and for judges who want to check our numbers.

**World report** → `GET /api/world` (precomputed, instant):
- `variables[]`: `name`, `n_points` (111 land points worldwide), `n_proven`, `n_rising`, `n_falling`, `n_typical` (how many a typical analysis would call a trend), `n_fooled` (typical says trend, Detective says not proven), `n_fdr`; `cells[]` aligned with `points[]` (`lat`, `lon`) → `label`, `slope`.
- Suggested view: a new tab, **"The world"**. A table with one row per variable: proven ↑ / proven ↓ / typical-would-claim / fooled, plus a small world dot map for the selected variable (dot colour = direction, solid = proven). Headline example: *"Air temperature: proven warming at 80 of 111 land points; a typical analysis would claim 96, so 16 of its 'trends' are false alarms."*

## 3. Small fixes (QUICK)
1. **Map zoom control over the header:** when you scroll the map page, Leaflet's "+/−" control draws on top of the sticky header. Give `.shell` a `z-index` above 1000 (Leaflet controls use 1000) or lower `.leaflet-top`.
2. **"p = 2e-18" in the Typical box:** fixed in the backend on `main` (now says "p < 0.0001"). Nothing to do once you merge.
3. **Report card for a new place** fires 15 NASA calls. The backend now spaces them out (one at a time, 0.4 s apart) to avoid NASA's rate limit, so the **first** report card for a new place takes ~10–20 s. Show a progress message like "Checking 15 NASA records…". Don't fire extra calls in parallel from the browser.

## 4. Methods page additions (MEDIUM)
- **Cross-checks table** from `docs/methods.md` §6b: HadCET 0.99, GPCP 0.97, ESA soil.
- **Linked clues:** `GET /api/links` (pre-registered rules + hit rates on 111 global and 71 UK new places) → a small table. Text: `docs/linked_clues.md` ("The links we can stand behind" + "What we rejected"). Mention the placebo held in 0 of 182 places.
- **Beyond the line:** one paragraph per method (records vs 1/n chance with a permutation test; emergence = signal-to-noise > 2; seasons with Holm correction; variability with Brown-Forsythe; turning point by BIC). Source: the top docstring of `backend/src/trend_detective/beyond.py`.

## 5. Things Claude can't do from Akshita's laptop (need you or Akshita)
| Task | Who | Notes |
|---|---|---|
| Merge `frontend` + `wording-fixes` into `main` | Kanishk (or say "go" to Akshita) | Both merge cleanly with the current `main` |
| **Deploy backend** | Kanishk | **`backend/Dockerfile` is ready** (not built locally: Docker isn't installed on Akshita's laptop, so please `docker build` once). Google Cloud Run (Global Offer) preferred over Render (Render sleeps 30–60 s). 1 GB RAM. `gcloud run deploy trend-detective-api --source backend --region europe-west2 --memory 1Gi --allow-unauthenticated` |
| **Deploy frontend** | Kanishk | Vercel; set `VITE_API_URL` to the Cloud Run URL |
| Cloud / GoDaddy / Microsoft sign-ups | Whoever signs up | Card verification must be entered by the person |
| AI variable finder | Kanishk | Needs your Claude API key in the backend env (never in the frontend). Must pick only from `/api/variables` ids |
| FortiGuard classification request | Kanishk | For the final URL, Sunday afternoon |
| Make the GitHub repo **public** | Akshita (owner) | Just before submitting |
| Video, screenshots, project page text | Akshita | |

## 6. Data limits to show in the UI (honesty)
- NASA POWER monthly data ends **Dec 2025**. Haze (AOD) starts **2001**; sunshine and cloud start **1984**.
- Soil wetness and evaporation have no data over the sea (cells come back null).
- A searched city gets a 1.5° × 1.5° box (~3–6 NASA cells, about 50 km each), so it's a **regional** picture, not a street-level one.

## 7. NEW (Sat ~19:45): research on the other 1,216 teams → read `docs/research_competition.md`
- Many rivals already have Hamed-Rao, FDR, a check-up, a second witness, and compare-two-places. Our pitch should lead with what only we have: the **instrument alibi**, linked clues tested on new places, records and emergence, and the world report.
- Frontend ideas from it, for you:
  - **"Guess first" question cards** ("Is it really getting hotter here?" → the user guesses → we reveal the verdict).
  - **Watchable demo tours** (the brief asks for "demonstration examples the user could watch").
  - A **compare-two-places** view once `/api/compare` lands.
- **Correction:** don't show the world report's cloud row as "88 proven" (see FINDINGS §2c).

## 8. NEW (Sat ~20:15): parity with every good rival feature + more. Backend is ready for all of these (see README "cross-examination…")
**Case page, new "Cross-examination" block** (`/api/cross-examine`), one row per check with ✔ / ⚠:
- Instrument alibi (`alibi.headline`; if `changes[].tested`, a tiny before/after slope pair; draw a dashed vertical line at `changes[].date` on the chart)
- El Niño removed (`el_nino.before` vs `.after` slope; `how_linked` sentence)
- One year carrying it? (`leave_one_out.headline`)
- Two halves (`walk_forward.status`: confirmed / continuing / faded / reversed / emerging)
- **"Did you pick good dates?" heat map** (`all_windows.cells[]`: x = start, y = end, colour = slope sign, solid = p<0.05). TerraPulse has this; ours adds the verdict sentence.
- Speeding up? (`decades.decades[]` as 4–5 bars + `decades.headline`)
- Early vs recent + top 3 years (`extremes`)
- "What could overturn this" list (`could_overturn[]`) and `score.headline`
- Resolution badge (`resolution.label`: resolved / marginal / sub-cell)
**Witnesses panel** → switch to `/api/witnesses` (list): one row per witness with name, `independence`, verdicts, r; header `headline` ("3 of 3 independent records agree"). Show station distance.
**Compare mode** (`/api/compare`): pick a second place → two lines + difference chart (`chart.difference_anomaly`), the headline, and the `trap` box in amber. Demo pairs: Sahel vs Amazon rain (opposite, both proven); Lincolnshire vs London temperature (can't tell apart); Lincolnshire vs Svalbard (rates differ).
**Custom period**: start/end year selectors → pass `start`/`end` to `/api/analyse` and `/api/cross-examine`.
**"Guess first" hunches** (`/api/hunches` + `/api/hunch`): user picks a hunch, guesses true/false, then sees the verdict. Works anywhere.
**Place profile** (`/api/profile`): a line under the place name ("Looks like: hot climate, big city") + suggested variables as chips.
**Upload your data** (`POST /api/upload`): textarea / file → same result layout.
**vs the world** (`result.vs_world.headline`): "Warming 1.6× as fast as the planet".
**Natural events** (`/api/events`): small list under the chart; note the sparse archive.
**From rivals, frontend-only, worth copying:** climate stripes per verdict; shareable link (state in URL hash, you have this); time-lapse/year slider on the map; hatching for cells that fail FDR; a 6-question quiz; a teacher page (lesson plan + printable case); English + one more language; accessibility check (axe); 30-second demo video and ≤7 slides.

## 9. NEW (Sat ~20:40): greenness from space + extreme days
**Greenness (NDVI)** is now an ordinary variable (`id: "NDVI"`, `satellite: true`, `period: "2000–2025"`), so it appears in `/api/variables` and works in analyse / cross-examine / compare / hunches / witnesses.
- Show a **"reading satellite images… (~1 min the first time)"** spinner when `variable.satellite` is true; demo boxes are pre-cached.
- Hide the grid-map button for it (`/api/map` returns 422 for satellite variables).
- Use `variable.citation` for the credit line (it's no longer always "NASA POWER").
- Demo story: **Delhi greening** (+0.023 NDVI/decade, p ≈ 2e-9, Aqua satellite agrees) vs **Rondônia browning** (−0.006/decade, deforestation) — use compare mode. The Sahel is greening too (the "re-greening of the Sahel").
- Hunches `greener` / `browner` are in `/api/hunches`.
**Extreme days** (`/api/extreme-days?lat_min=..`): a small table / bar pairs "1980s → last 10 years" per index (`indices[].mean_1980s`, `.mean_last10`, `.headline`), and a mini-chart from `years[]`/`counts[]`. Rows with `rare: true` show "rare here". Lincolnshire: hot days 30 → 59 a year; frost nights 44 → 22.
**World page**: `variables[].alibi` and `n_proven_after_alibi` → add a column "survive the instrument check" next to "proven" (cloud: 88 proven, 42 could be the 2001 switch).

## 10. NEW (Sat ~20:50): more cross-examination, drought, VPD, control map, "check our work"
- **Cross-examination block**: three more rows. `seasons`: 12 small bars (Jan–Dec, `months[].slope_per_decade`, solid if `proven_fdr`) + `headline`. `change_point`: "When did it change?" sentence (`headline`); draw a dotted line at `change_point.year` when `status` is `sudden_shift`. `climate_modes`: `strongest` sentence + `headline` (before/after slope pair like El Niño).
- **Drought panel** (`/api/drought`): SPI-12 line chart (`spi12.dates/values`, shade below −1 in amber) + the two count rows like extreme days. Show for rain-related cases.
- **VPD** is a normal variable (`id: "VPD"`); nothing special.
- **Map**: under the summary, the `shuffled_control.headline` in a grey box ("pure noise would still light up ~60 cells on a typical map"). Great for the "why our map is honest" story. Optional toggle: real vs shuffled.
- **"Check our work" box** on every case: list `result.reproduce[]` as links (name + note). Put the notebook link (GitHub) there too.

## 11. NEW (Sat ~21:00): replay slider, coverage, land heat from space, climate models
- **Replay slider** (rival xFr05en has one): `cross-examine.all_windows.timeline[]` (end year → p). Drag the end year; show "proven by {became_proven}" when reached. Simple line of p (log scale) with a 0.05 line also works.
- **Coverage chip** under every verdict: `result.coverage.headline` (e.g. "306 of 310 months present; longest gap 4 months").
- **LST_DAY / LST_NIGHT** are satellite variables like NDVI (same spinner, no map). Best demo: **Delhi, nights hotter / days cooler** next to Delhi greening.
- **"Did the models see it coming?"** card (`/api/models`): observed slope as a dot over the model range bar (`model_range`, each `models[]` as a tick), `headline`, `next`, and `caveat` in small grey text. Only for T2M, T2M_MAX, T2M_MIN, rain, humidity, wind, sunshine.
