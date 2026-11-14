# Trend Detective: full status report and handover

*Written Sat 14 Nov 2026, ~21:30 (UK), by Claude on Akshita's laptop. It is for **Kanishk and Kanishk's Claude**: read this first, then [FRONTEND_TASKS.md](../FRONTEND_TASKS.md) for UI details, [FINDINGS.md](../FINDINGS.md) for results and [docs/methods.md](methods.md) for the statistics.*

**Deadline:** project page submitted by **Sun 15 Nov 23:59** (aim for 22:00). **Judging:** impact, creativity, validity, relevance, presentation (1–5 each). Demo = **≤7 slides or a ≤30 s video**. Challenge author: Dr James Acker (NASA GES DISC).

---

## 1. Snapshot

| | |
|---|---|
| Repo / branch | `romaaurora787/trend-detective`, **`main`** has all backend work (latest commits `fcf6565`, `7ca7400`) |
| Tests | **60 pass**: `cd backend && uv run pytest -q` (about 20 s with the cache) |
| Variables | **23**: 19 NASA POWER (MERRA-2 / CERES), 1 derived (VPD), 3 NASA MODIS satellite (NDVI, day/night land surface temperature) |
| Endpoints | **23**, all GET except `POST /api/upload` (table in §4) |
| Frontend | Kanishk's **`origin/frontend`** (`5afd88c`, Sat 18:49): case, report card, map, methods views. **Not merged into `main`**, and it doesn't use anything built after ~19:00 |
| Other branch | **`origin/wording-fixes`** (`b1e78e8`): edits `witnesses.py` and `docs/methods.md`. **Both files changed a lot on `main` since: merging will conflict.** Re-apply the wording by hand on top of `main` |
| Merging rule | Merge only when Akshita or Kanishk says so. Never force-push `main` |
| Cache | `backend/data/cache/` is committed (about 420 MB). Demo places load instantly from it. NASA POWER, Open-Meteo and Planetary Computer all rate-limit, so **the live demo must use cached places** |

---

## 2. Run it

```bash
cd backend && uv sync && uv run uvicorn trend_detective.api:app --reload --port 8000
```
```bash
cd frontend && npm ci && npm run dev
```
(Run the second one on the `frontend` branch.)

API docs: http://127.0.0.1:8000/docs. Python ≥3.12 with `uv`. `rasterio` is now a dependency (for satellite reads).

---

## 3. Code map (`backend/src/trend_detective/`)

| File | What it does |
|---|---|
| `stats.py` | Core engine: deseasonalise; Hamed–Rao Mann–Kendall (lag 12) + Sen slope; OLS with effective n; verdict labels; Weatherhead years-to-detect; robustness; BH-FDR; **`shuffled_control`** (pure-noise map control) |
| `power.py` | NASA POWER client (monthly regional / point, **daily point**), cache, pacing, 429 retry; **`DERIVED`** variables (VPD); routes satellite variables to `ndvi.py` |
| `catalogue.py` | The 23 variables (id, name, units, source, plain text, tags, caveat, `satellite`/`derived`/`citation` flags) |
| `crossexam.py` | The sceptic's checks (§5) |
| `compare.py` | Two places: trend of the **difference A − B** (Gelman & Stern trap warning) |
| `witnesses.py`, `era5.py`, `stations.py` | Second witnesses: HadCET, GPCP v3.3, ESA CCI soil (regional files), ERA5 via Open-Meteo, nearest NOAA GHCN station |
| `ndvi.py` | MODIS reader (Planetary Computer COGs, no login): `NDVI` (MOD13Q1 250 m), `LST_DAY`, `LST_NIGHT` (MOD11A2 1 km); Terra + Aqua; multi-tile, exact lat/lon mask, quality flags |
| `heat.py` | Extreme-day counts from POWER daily data |
| `drought.py` | SPI-3 / SPI-12 drought months |
| `models.py` | 7 CMIP6 HighResMIP models via Open-Meteo Climate API |
| `globalref.py` | Rate vs NASA GISTEMP global ("1.6× the planet") |
| `guide.py` | Place profile, hunches (17), CSV upload parser |
| `events.py` | NASA EONET events near the place |
| `reproduce.py` | "Check our work" links: exact POWER request, Giovanni, GPM IMERG |
| `beyond.py`, `context.py`, `places.py` | Beyond-the-line stats, case file, GeoNames place search |
| `api.py` | FastAPI app, in-memory memo cache |

Scripts (`backend/scripts/`): `prewarm.py` (fills the cache for demo places), `world_report.py` (111 land points × all POWER variables, with alibi), `instrument_alibi_scan.py`, validation scripts. Notebook: `notebooks/reproduce_lincolnshire.ipynb`.

---

## 4. Endpoints

Boxes are `lat_min, lat_max, lon_min, lon_max` query params (compare uses `a=..&b=..` as comma lists).

| Endpoint | Gives | Speed |
|---|---|---|
| `/api/variables` | catalogue + place types | instant |
| `/api/analyse?var&box[&start&end]` | verdict, slopes, CIs, chart, robustness, **`vs_world`**, **`coverage`**, **`reproduce[]`**, second witness, citation | fast if cached |
| `/api/cross-examine?var&box` | alibi, el_nino, **climate_modes**, leave_one_out, walk_forward, all_windows (+**timeline**, **became_proven**), decades, extremes, resolution, **seasons**, **change_point**, could_overturn, score | 1–5 s |
| `/api/compare?var&a&b&name_a&name_b` | difference-series test, labels, trap | fast |
| `/api/witnesses?var&box` | all witnesses + "X of Y agree" (Aqua satellite for MODIS variables) | ERA5 first time ~10 s |
| `/api/models?var&box` | observed vs 7 climate models + 2026–2050 range + caveat | Open-Meteo, cached after |
| `/api/drought?box` | SPI drought months, SPI-12 series | fast |
| `/api/extreme-days?box` | hot days, 35 °C days, tropical nights, humid heat, frost, cold nights | POWER daily, ~2 s |
| `/api/report-card?box` | every variable sorted by verdict; `not_yet_read` lists unread satellite variables | slow first time |
| `/api/map?var&box` | per-cell trends, FDR, **`shuffled_control`** (422 for satellite variables) | medium |
| `/api/profile`, `/api/hunches`, `/api/hunch?id` | place type + suggestions; belief checker | fast |
| `POST /api/upload` | your own CSV through the same engine | fast |
| `/api/events`, `/api/beyond`, `/api/context`, `/api/places`, `/api/evidence.csv`, `/api/world`, `/api/links`, `/api/validation`, `/api/health` | as named | fast |

**Satellite variables** (`NDVI`, `LST_DAY`, `LST_NIGHT`): the first read of a new box takes **0.5–4 min** (hundreds of images). Cached for the demo places: NDVI for 12 places; LST still filling in the background (Delhi, London, Lincolnshire done).

---

## 5. What makes us different (pitch material)

1. **We cross-examine every trend**, not just test it: instrument alibi (documented satellite/model changes), climate modes removed jointly (El Niño, NAO, IOD, PDO), one-year influence, two halves, every start/end year with a **replay of when the evidence became strong**, speed-up, which months, when it changed, grid resolution.
2. **We caught our own data:** cloud and sunshine "trends" at many places are the 2001 satellite switch. 42 of 88 proven cloud points could be the instrument.
3. **Independent witnesses:** Met Office HadCET, NASA GPCP, ESA CCI, ERA5, NOAA stations, a second MODIS satellite, and climate models.
4. **Honest maps:** BH-FDR plus a shuffled-years control showing how many cells a typical map lights up in pure noise.
5. **Reproducible:** every case links the exact NASA request and the Giovanni view; the notebook rebuilds the headline number from NASA's API alone.
6. **Proof the method works:** synthetic validation (`/api/validation`), a pre-registration record (methods §8g).

---

## 6. Demo stories with numbers (all from code; see FINDINGS.md)

- **Lincolnshire (home):** warming +0.33 °C/decade, strong; passes 5/5 cross-examination checks; proven by 1999 and every year since; 1.6× the global rate; 3 of 3 witnesses agree; **faster than all 7 climate models** (+0.14 to +0.30); hot days 30 → 59 a year, frost nights 44 → 22; winter follows the NAO (r = +0.53) and the warming survives removing it.
- **Delhi:** greening +0.020 NDVI/decade (both satellites); **ground at night +0.70 °C/decade** (both satellites); daytime ground heat *not rising* (one satellite says cooling, the other doesn't prove it); air less "thirsty" (VPD falling); tropical nights and humid-heat days increasing.
- **Amazon (Rondônia):** rain −0.53 mm/day/decade, confirmed by GPCP; **drought months 0.9 → 9.4 a year**; driest year ended Jan 2016; VPD rising; browning (both satellites). **Stronger than any climate model** (−0.11 to +0.03), so present it with care.
- **Beijing:** greening +0.030 NDVI/decade (China's tree planting). Haze: Delhi up, Beijing down.
- **Svalbard:** +0.60 °C/decade (3× global), **weaker than all models** (reanalyses disagree in the Arctic: say so).
- **Spain:** winter rain follows the NAO (r = −0.65).
- **England & Wales soil map:** 89 cells "significant" on a typical map → 0 after our checks; in pure noise a typical test still marks ~60 of 137.
- **London vs Lincolnshire nights** (MODIS): London's ground at night +0.37/+0.46 °C/decade (both satellites, strong); Lincolnshire +0.29 (Terra) / +0.26 (Aqua, not proven). Good for compare mode (urban heat).
- **Comparisons:** Sahel vs Amazon rain = opposite, both proven; Lincolnshire vs London air temperature = can't tell apart.

**Don't say:** "Delhi days are cooling"; "cloud cover is falling" (instrument alibi); anything about cause (we detect, we don't attribute); "the models are wrong" (they had real ocean temperatures until 2014).

---

## 7. What Kanishk's Claude should CHECK first (in this order)

1. `git pull` on `main`; `cd backend && uv sync && uv run pytest -q` → expect **60 passed**.
2. Start the API and open each demo case in `/docs`: `/api/analyse`, `/api/cross-examine`, `/api/witnesses`, `/api/models`, `/api/drought`, `/api/extreme-days` for Lincolnshire `52.6,53.7,-1.0,0.4`. Check the numbers in §6 match.
3. Run the notebook (`notebooks/reproduce_lincolnshire.ipynb`) → +0.333 °C/decade.
4. Open 2–3 of the `result.reproduce[]` Giovanni links while logged in to Earthdata. **The Giovanni ids were built from its naming pattern; T2M, PRECTOTCORR, GWETTOP, AOD were confirmed against public examples, the rest (GWETROOT, SNODP, T2MDEW, CLDTOT, SWGDN, LWGAB, IMERG) have not been opened yet.** Remove any that don't load (`reproduce.py` `GIO` dict).
5. On the `frontend` branch, check that `api.ts` still matches the response shapes (new fields only were added; nothing renamed, except `report-card` gained `not_yet_read`).
6. Read every number the website shows against the API (no hand-typed numbers in the UI).

---

## 8. What to WORK ON (priority order)

**P0, needed for submission**
- Merge or rebase `frontend` onto `main` (with the team's OK) so the site gets the new backend. Deploy: backend (Render / Docker, `Dockerfile` exists) with the committed cache; frontend (Vercel). Test the live link in a private window.
- One polished case end-to-end on the live link: place → variable → chart → verdict → cross-examination block → witnesses → "check our work" links.
- Methods page: proof chart + pre-registration table (methods §8g) + "what this does not tell you".
- 30-second video or ≤7 slides, references list, AI-use statement.

**P1, the features that win "creativity" and "validity"** (UI specs in FRONTEND_TASKS §8–11)
- Cross-examination block (one row per check, ✔/⚠) with the **replay slider** and the **all-windows heat map**.
- Witnesses list ("3 of 3 agree") + **"Did the models see it coming?"** card.
- Compare mode with the trap warning.
- Map: FDR hatching + the **shuffled-noise control** box.
- Satellite variables with a "reading satellite images…" spinner; Delhi and Amazon stories.
- Drought panel and extreme-days table.

**P2, nice to have**
- Hunch "guess first" quiz, place profile chips, CSV upload, events list, climate stripes, share links, second language, accessibility pass.
- An AI explainer that only rephrases numbers the API returned (needs Kanishk's API key; never let it invent numbers).

**Backend left to do (Akshita's Claude can do these)**
- Climate models for Sahel and Spain: Open-Meteo **daily** limit hit; retry tomorrow (cache then fills).
- Finish the LST cache for the remaining demo places (background job running), and rerun `scripts/prewarm.py` once Open-Meteo resets (it now backs off instead of hammering).
- **With the new Earthdata accounts:** GPM IMERG rainfall as a witness for any place, Giovanni link verification, maybe OMI NO₂ (2020 lockdown dip) and GRACE groundwater. See §10.

---

## 9. Known limits and gotchas

- **Rate limits:** NASA POWER (bursts → 429, paced); Open-Meteo (per hour and per day across ERA5 + climate API; now backs off 20 min); Planetary Computer (fine so far). The demo must use the cache.
- **MERRA-2 is a reanalysis**, not a thermometer; cloud/sunshine/LW records switch source in 2001 (alibi check covers this); MERRA-2 aerosol inputs change in 2014; rain above 42.5° latitude is model-only (`rain_provenance`).
- **Satellite records start in 2000** (shorter, so harder to prove). Cloudy months are dropped, never filled (see `coverage`).
- **Climate models** are a grid cell at the box centre; they had real ocean temperatures until 2014.
- **The ORNL MODIS web service was down**; we use Planetary Computer instead (same NASA product, open COGs).
- Prewarm and other long jobs: run them in the background; logs go to `backend/data/*.log` (git-ignored).

---

## 10. Accounts and data access

- **NASA Earthdata** (both) and **CEDA** (Akshita) accounts now exist. Nothing in the code uses them yet: everything above runs without a login.
- To let code use Earthdata **without anyone pasting a password into chat**: the account owner creates an Earthdata **user token** (urs.earthdata.nasa.gov → *Generate Token*) and puts it in `backend/.env` as `EARTHDATA_TOKEN=...` themselves. `.env` is git-ignored; code reads the environment variable; Claude must not open or print the file.
- Also approve **NASA GESDISC DATA ARCHIVE** and **LP DAAC** under *Applications → Authorized Apps* (needed for IMERG and AppEEARS downloads).

---

## 11. House rules for any Claude working on this repo

- **AI use is disclosed**: every code file has an AI-use note in its header; keep it. Verdict numbers always come from code, never from an AI.
- **No secrets in git, chat or logs.** Don't read `.env`, `~/.netrc` or tokens. No passwords typed by Claude; account sign-ups are done by people.
- **Commits:** author "Akshita Srivastava" (noreply email) on her laptop; Kanishk commits as himself. End messages with the Co-Authored-By line the session gives you.
- **Don't merge `frontend` or `wording-fixes` into `main`, and don't send messages for anyone, without being asked.**
- **Honesty over hype:** if a new check weakens a claim, change the claim (we did this for cloud cover and for Delhi's daytime temperature). FINDINGS.md is the source of truth for demo numbers.
