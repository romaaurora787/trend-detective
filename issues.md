# Issues: shared list for the team and both Claudes

Written Sat 14 Nov 2026, ~22:30, by Claude on Kanishk's laptop, after merging `main` into `frontend`. Add to it, tick things off, and say who is on each one. Newest at the bottom of each section.

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
