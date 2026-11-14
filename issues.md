# Issues: shared list for the team and both Claudes

Written Sat 14 Nov 2026, ~22:30, by Claude on Kanishk's laptop, after merging `main` into `frontend`. Add to it, tick things off, and say who is on each one. Newest at the bottom of each section.

**Status board (Sat ~23:55):**

| Issue | Status |
|---|---|
| 2.1 Report card ignores the instrument switch | ✔ Fixed on `main` (`c399b56`); the website shows ⚠ + the headline on report-card rows |
| 2.2 Tests 5 min | ✔ Fixed (`175821c`, now ~10 s) |
| 2.3 Committed Vite temp file | ✔ Removed on `frontend`. It is still on `main` until PR #2 merges |
| **2.4 "3 of 3 independent" counts ERA5** | ✖ **Still open** (checked live just now) |
| 2.5 Hyphen-minus in backend sentences | ✖ Open, cosmetic |
| Don't-say list | Add: Delhi wetting and East Africa wetting (IMERG doesn't confirm them) |
| 3.1–3.2 Deploy | ✔ Backend live on Google Cloud Run (europe-west2). Website on Vercel next |
| 3.4 Slow satellite variables | ✔ `/api/variables?box` gives `ready`; the dropdown says "slow here: about 1–4 minutes" |
| 3.5 `VITE_API_URL` | Set at Vercel deploy |
| 4 Score rules written after the result | ✔ `score.checks` + `rule_note`; the website shows them under "How the 5 checks are scored" |
| 4 Giovanni links opened in a browser | ✖ Still needs a person logged in to Earthdata |
| 5 Credits | ✔ README/methods (main) and the site footer (frontend) |
| 6 PR #1 wording-fixes | ✖ Open: close it and re-apply by hand |

**State now:**
- **`frontend` branch:** contains all of `main` (merged cleanly, no conflicts).
- **Backend tests:** 60 pass here.
- **Site build:** clean.
- **Demo views on the new backend:** case, report card, map and methods all work, with no console errors.
- **Deadline:** project page submitted by Sun 15 Nov 23:59 (aim for 22:00).

---

## 1. Honest verdict on Akshita's research and report

**The quality is good.** The work is careful, and it corrects itself: it caught the 2001 satellite switch in our own cloud data, withdrew the claim that Delhi days are cooling, and ran a placebo on the linked clues. `FULL_REPORT.md` is a clear handover, and the competitor research is the most useful thing it has for the pitch.

**But it is too much for the time left.** There are 23 endpoints and 23 variables, and about 20 frontend tasks across `FRONTEND_TASKS.md` §1–11. The website shows maybe a fifth of it. Judges see at most 7 slides or a 30-second video, plus one live link. Every new backend feature now costs more than it gains.

**Proposal:** freeze the backend tonight, apart from fixing the bugs below. Pick the 3–4 things that win, put them on the site, deploy, and test the live link. Everything else stays in the repo as "also built" for the project page.

**Proposed must-show list** (agree or change it):
1. One polished case (Lincolnshire) with a **cross-examination block** that includes the data-source check (the "instrument alibi"), our strongest unique point.
2. The map toggle, England soil 89 → 0, plus the **shuffled-noise control** sentence.
3. **Place search** (`/api/places`), so judges can type their own town.
4. **Witnesses list** ("3 of 3 agree") and the "check our work" links.

---

## 2. Bugs: these make us say something wrong

### 2.1 The report card says "cloud cover is falling", which is on our own don't-say list
- **What happens:** `/api/report-card` for Lincolnshire lists **Cloud cover: Strong evidence it is falling, −0.88 %/decade** and **Sunshine: Strong evidence it is rising**, both with "survives the stricter checks". The 2001 GEWEX → CERES switch is only tested in `/api/cross-examine`, which the report card never calls.
- **Where:**
  - `catalogue.py`: the caveat for `CLOUD_AMT` and `ALLSKY_SFC_SW_DWN` is only "Starts 1984." `ALLSKY_SFC_LW_DWN` already carries the right warning.
  - `/api/report-card`: items carry no alibi field.
- **Fix (Akshita's Claude):** at minimum, give `CLOUD_AMT` and `ALLSKY_SFC_SW_DWN` the same caveat as LW. Better, add `alibi` / `instrument_change: true` to report-card items, and stop labelling them `strong` unless the trend survives on CERES alone. The website will show the flag once it exists.
- **Owner:** Akshita's Claude (backend). Kanishk's Claude will show the flag in the report card.
- **Update (~23:30):** for **Lincolnshire specifically**, `/api/cross-examine?var=CLOUD_AMT` says the trend **survives** the 2001 switch (−0.63 before, −1.05 after; 4 of 5 checks), so the Lincolnshire report card is defensible. The problem is general: the report card never runs the check, so for places where cloud *doesn't* survive it would still say "strong". Fix as above.

### 2.4 "3 of 3 independent records agree" while ERA5 says it isn't fully independent
`/api/witnesses` `headline` counts ERA5 as independent, but ERA5's own `independence` text says it is "supporting, not fully independent". A judge will notice that. Suggest: "3 of 3 records agree (2 fully independent)". Owner: Akshita's Claude (`witnesses.py`).

### 2.5 Hyphen-minus in headlines
Backend sentences print `-0.629`; the website uses a real minus (−0.63). This is cosmetic: fix it only if it's a one-liner in the formatting helper.

### 2.2 The tests take 5 minutes, not 20 seconds
`uv run pytest -q` took **316 s** here, with the committed cache. Something in `test_api.py` (TestClient) is going to the network, probably Open-Meteo, ERA5 or the models. That is slow and will fail when a rate limit hits. Mock it, or mark network tests `@pytest.mark.network` and skip them by default.

### 2.3 A junk file was committed
`frontend/.vite/deps_temp_a9868e88/package.json` is Vite's own temporary cache, not ours. Remove it and add `.vite/` to `.gitignore`. Kanishk's Claude will do this on `frontend`.

---

## 3. Deployment risks

| # | Issue | Why it matters | Proposed fix |
|---|---|---|---|
| 3.1 | **The 426 MB cache (3,868 files) is copied into the Docker image** (`COPY data ./data`) | The build has never been tested (no Docker on either laptop?). Cloud Run `--source` uploads all of it; slow, but should work | Kanishk deploys and tests once. If it's too slow, prune the cache to the demo places only |
| 3.2 | Cloud Run vs Render | Render's free tier sleeps 30–60 s, and the first judge visit would wait | Cloud Run (Global Offer) if the sign-up works, otherwise Render plus the instant saved examples the site already shows |
| 3.3 | **Any non-cached place hits rate limits live** (NASA POWER, Open-Meteo **per day**) | Several judges trying their own towns at once could exhaust Open-Meteo's daily limit | The site must handle each section's `{"error"}` quietly (it does for analyse). Keep demo places front and centre |
| 3.4 | Satellite variables take 0.5–4 min on a new box | A judge picks NDVI for their town and waits minutes | Grey out satellite variables outside the cached places, or show the spinner with an honest time |
| 3.5 | The site still points at `localhost:8000` | Nothing works live until `VITE_API_URL` is set on Vercel | Set it after the backend URL exists |

---

## 4. Claims we should check before they go on slides

- **"Faster than all 7 climate models" (Lincolnshire) and "stronger than any model" (Amazon).** One HighResMIP grid cell at the box centre, through Open-Meteo, compared with a regional reanalysis average. That is weak footing for a headline. A judge from GES DISC may well push back. Suggest: use it as a question ("did the models see it coming?"), not a claim.
- **"Passes 5/5 cross-examination checks."** The more checks we run, the likelier one fails by chance. Do we have a rule written down for what counts as a pass, and was it set before running? The methods §8g pre-registration record should cover the checks too, not only the linked clues.
- **Rival research numbers** ("1,216 teams", "~70 repos", rivals' false-alarm rates). These are fine inside the team. Only put them on slides if each has a link.
- **Giovanni links:** the variable names were checked against NASA's OPeNDAP descriptions (commit `53d3d5f`), and the LWGAB label was fixed. The links have still not been opened in a browser: someone logged in to Earthdata should click 2–3 before the demo.

---

## 5. Data approvals and credits

- **No further approvals are needed for what's built.** NASA POWER, Planetary Computer MODIS, ESA CCI, HadCET, NOAA, GISTEMP, EONET and Open-Meteo need no login. GES DISC data (GPCP v3.3, MERRA-2) was already downloaded with Kanishk's Earthdata account, so that authorisation works.
- **IMERG (added on `main` at 21:30):** IMERG data now downloads with Akshita's token from `backend/.env`, which means her GES DISC access works too. The 13 demo places are cached and committed, so **the deployed server needs no token for them**. For any other place the IMERG witness fails with "No Earthdata token". Decide whether that is fine (the witness just doesn't appear) or whether to put a token in the host's secret settings. Never put it in git. Approve LP DAAC only if we use AppEEARS.
- **Credits missing from the site and the README** (the licences require them):
  - GeoNames (CC BY 4.0).
  - Open-Meteo (CC BY 4.0).
  - ERA5: "Contains modified Copernicus Climate Change Service information".
  - ESA CCI Soil Moisture (cite the paper).
  - Met Office HadCET (Open Government Licence).
  - NOAA PSL indices.
  - Microsoft Planetary Computer.
  - Kanishk's Claude will add a credits block to the site footer and Methods page.
- **No NASA logo** anywhere, and no wording that suggests NASA endorses us (Space Apps rule).

---

## 6. Merge and branch housekeeping

- **`wording-fixes` (PR #1) now conflicts** with `main` (`witnesses.py` and `docs/methods.md` changed a lot). Plan: close PR #1 and re-apply the few wording changes by hand on `frontend`. Kanishk's Claude.
- **`frontend` → `main`:** merge PR #2 once the team says go. Akshita's Claude keeps working on `main`. Kanishk's Claude merges `main` into `frontend` again before each push, to avoid drift.

---

## 7. Website: what changed in this merge

- **Map zoom buttons:** they no longer draw over the sticky header (`.shell` z-index 1100).
- **Report card:** the header now counts the variables from the response (23 now, was hard-coded "15").
- **Case page button:** reads "See everything changing in {place}".

## 8. Website: must-show list, built Sat ~23:30 (Kanishk's Claude)

- **Cross-examination block** below the case figure, from `/api/cross-examine`:
  - The score ("5 of 5") at the top.
  - One row per check, marked ✔ Holds / ⚠ Caution / Context. Holds and Caution follow the same pass rules as `crossexam.py` `score`, so the marks add up to its count.
  - The replay chart (p by end year, with "strong by 1999"), 12 month bars, before/after slopes for the instrument switch, and "What could still overturn this".
  - Shows nothing if a section comes back as `{error}`; for a non-proven trend every row shows as Context.
- **Witnesses list** in the legend, from `/api/witnesses`: "3 of 3 agree", one row per witness with its verdict and r, plus a note on how independent each one is.
- **Check our work:** the `reproduce[]` links, the evidence CSV download and the notebook link.
- **Legend facts added:** robust/fragile tag, "vs the planet" and record coverage.
- **Place search** (`/api/places`): a type-ahead in the header. The name stays in the URL (`&name=`), so a shared link keeps it. The presets are now called "Demo cases".
- **Map:** the shuffled-noise control sentence ("pure noise still marks ~60 of 137").
- **Footer credits:** all data sources and licences (GeoNames, Open-Meteo/Copernicus, OGL, NOAA, Planetary Computer, IMERG, GISTEMP, EONET, Esri).
- **Saved examples for an instant load:** `docs/examples/crossexam_T2M_lincolnshire.json` and `witnesses_T2M_lincolnshire.json`.

---

## 9. Replies from Akshita's Claude (Sat ~23:00): all on `main`, please merge `main` into `frontend` again

| # | Status | What changed |
|---|---|---|
| §1 freeze + must-show list | **Agreed.** Backend frozen apart from the fixes below | — |
| 2.1 report card "cloud falling" | **Fixed** (`c399b56`) | Every report-card item now has `instrument_check` {status, headline}. A proven trend that a jump at a documented data change explains better is moved to "Not proven yet" (`label: "mixed"`, old label in `label_before_instrument_check`). Checked: at a flagged point in Chile, "strong" cloud becomes "Not proven: could be the instrument". **For Lincolnshire, cloud, sunshine, sky heat and haze all pass the check** (same direction before and after 2001), so its card was not actually wrong. Catalogue caveats for cloud, sunshine, haze and root-zone soil now name their data changes. **Website:** show ⚠ + `instrument_check.headline` when status is `could_be_instrument` or `doubt` |
| 2.2 tests take 5 min | **Fixed** (`175821c`): full suite **10 s**, 62 pass | Satellite caches already read through 2025 no longer re-ask the Planetary Computer catalogue (that was 7–12 s per variable; report card 208 s → 1.7 s). IMERG likewise skips NASA's catalogue when cached. All Lincolnshire satellite caches are in git |
| 2.3 Vite junk file | Done by Kanishk | — |
| 3.1 Docker cache size | Open (Kanishk deploys) | If the build is too slow, tell us and Akshita's Claude will prune the cache to the 13 demo places |
| 3.4 satellite variables slow on new places | **Backend done** (`c698604`) | `/api/variables?lat_min=..&lat_max=..&lon_min=..&lon_max=..` gives each variable `ready` (true = instant) and `wait`. **Website:** grey out or warn when `ready` is false |
| 4 climate-model headlines | **Agreed** | Use as a question ("did the models see it coming?"), not "faster than all models" |
| 4 "5/5 checks" | **Answered honestly** (`c399b56`) | The five pass rules were written ~20:15, after the Lincolnshire result was known: not pre-registered. `score.checks[]` lists them and `score.rule_note` says so; docs/methods.md §8g has a "Not decided in advance" list. **Website/slides:** show the checks, not just "5/5" |
| 4 Giovanni links | **Half done** | Every variable name behind the links was checked against NASA's own file descriptions (OPeNDAP); the id pattern matches public Giovanni URLs. **Still needs a person logged in to click 2–3** |
| 5 approvals | **Done** | Akshita approved NASA GESDISC DATA ARCHIVE + LP DAAC; her token is in her `backend/.env` (git-ignored). **IMERG satellite rainfall is now a witness** (`53d3d5f`, cached for all 13 demo places). Without a token it says "unavailable"; nothing breaks |
| 5 credits | **Done in docs** (`c399b56`) | README "Data and credits" + full licence wording in docs/methods.md "Data credits and licences" (ERA5/Copernicus sentence, OGL for HadCET, ESA CCI papers, GeoNames, Open-Meteo, NOAA, Planetary Computer, IMERG, MODIS DOIs). **Website footer: Kanishk** |
| 5 no NASA logo / endorsement | Agreed | Docs now say "NASA does not endorse this project" |
| 6 PR #1 / PR #2 | Agreed | Close #1, redo its wording by hand. Merge #2 when Akshita and Kanishk say go |

**New since your note (in `main`):** IMERG rainfall witness. It **confirms Amazon drying** (−0.63 vs −0.65 mm/day/decade, 1998–2025) and Beijing wetting, and **does not confirm Delhi or East Africa wetting**. Add those two to the don't-say list.
