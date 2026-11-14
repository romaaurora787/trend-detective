# What the other teams built, and what we add next (research, Sat 14 Nov, evening)

**Sources read:**
- The judging guide.
- The challenge's Resources tab.
- About 70 public GitHub repositories made for this challenge. 1,216 teams entered it.
- Three demo videos.
- One rival's notes on the challenge author's own video.
- NASA GMAO and POWER documentation on how the data are made.

Everything below can be checked from the links at the end.

## 1. The bar is high: what is now common
Several teams already have what we called our differentiators. Our A, B and C are no longer unique on their own:

| Feature | Who else has it |
|---|---|
| Hamed-Rao / autocorrelation-aware Mann-Kendall, Sen with CI, BH-FDR | Most serious entries (Trend Detective "Signal or Noise", CaseFile Earth, Trend Detective Lab, Earth Trend Detective, a Streamlit + Earth Engine team) |
| **A. Typical vs Detective** | "Signal or Noise?" has a 3-way map toggle: naive p, shuffled noise, corrected. Trend Detective Lab shows what its earlier methods would have said |
| **B. Report card** for one place | Earth Trend Detective has a "full check-up" of 8 variables with a rule-based label |
| **C. Second witness** | Earth Trend Detective uses the nearest NOAA weather station (worldwide). Trend Detective Lab uses ERA5 + Meteostat stations + a Giovanni cross-check |
| Years-to-detect (Weatherhead) | "Signal or Noise?" |
| **Remove El Niño** (regress out Niño 3.4) | "Signal or Noise?" |
| Compare two places by testing the **trend of the difference** | CaseFile Earth, Trend Detective Lab |
| Opposite trends hiding inside one region | Earth Trend Detective, IONA, EarthSignal |
| Pre-registration committed before data | CaseFile Earth, Trend Detective Lab |
| Calibration on synthetic data (false-positive rates) | Trend Detective Lab (8.6% worst case), CaseFile (up to 16% at high memory) |
| Bilingual, offline, AI explainer grounded on computed numbers, 3D globe, "guess first" | Several |

## 2. Where we still lead (keep these at the front of the pitch)
1. **Linked clues tested out-of-sample, with a placebo.**
   - The rules were committed first, then tested on 111 global and 71 UK new places.
   - The placebo held in 0 of 182 places.
   - Others only explore correlations.
2. **Beyond the trend line.** Records vs chance (block permutation), the year it emerged from the noise, the season that changes fastest, "more erratic?", and turning points. Nobody else has records-vs-chance or emergence year.
3. **Impact in plain words.** "6 of the last 10 summers beat the old 1-in-10 summer", with a binomial test.
4. **The world report.** 15 variables × 111 places: 28% of typical claims unsupported, and soil moisture worst (57 of 86).
5. **Calibration that actually holds.** 5–7% false alarms on persistent synthetic weather. The best rival admits 8.6–16%.
6. **Breadth.** 15 variables (frost days, wind, haze, sunshine, evaporation…) and 34,215 searchable places.
7. **NEW, and the strongest of all: the instrument alibi** (section 4). We are the only team we found that tests it automatically.

## 3. Asks in the brief we don't cover yet
- **"Trend one way in one region and the opposite way in another"**: we have nearby-cells context, but no **two-place comparison** that tests the difference directly.
- **Oceans** and **levels of the atmosphere.**
- Our **second witness** works only in the UK (HadCET), for rain (GPCP) and for Europe/East Africa soil (ESA). The Resources tab lists **NOAA Climate Data Online**, which has stations worldwide.
- **"A short series of questions"** and **"demonstration examples the user could watch"** are frontend items.
- **SI suggesting data from "the characteristics of a region" (desert, rainforest, estuary, city).**
- **The challenge author's own example.** He is Dr. James Acker (NASA Goddard, Giovanni), and his example is **aerosol over Wisconsin**. A big volcanic eruption can cause "a cooling trend", per a rival team's summary of his video.

## 4. NEW finding: the instrument alibi (and a correction to our own results)
NASA POWER builds **sunshine and cloud cover** from two different satellite products. GEWEX SRB release 4 covers **1984–2000** and CERES SYN1deg covers **2001 onward**. A change of instrument can look like a trend. We tested this on our 111 world points (`backend/scripts/instrument_alibi_scan.py`):

**Cloud cover:**
- At the 2001 switch, a single **jump explains the data better than a trend at 59%** of the places we had called "proven".
- With the jump placed at 1993, 1997, 2005 or 2009, that figure is only 6–36%. Air temperature, which has no switch, gives 14%.
- At **16 places the trend vanishes on both sides of the switch.**
- Re-tested on the single-instrument record (2001–2025): **47 of 88 survive, and 15 reverse direction.**

**Sunshine:** 58 proven over 1984–2025 → **28 on CERES alone (18 survive)**.

**Lincolnshire passes.** Sunshine rises about +0.15 MJ/m²/day per decade under *both* instruments separately, and is significant on CERES alone (p = 0.015). Cloud falls under both. A good demo of the check working both ways.

**Other documented source changes to build into the check:**
- **Haze (MERRA-2 aerosol):** MISR stopped being assimilated in June 2014 and AERONET in Oct 2014 (Randles et al. 2017, Table 2).
- **Root-zone soil wetness:** MERRA-2 was run in 4 streams, with breaks at 1990–91, 2000–01 and 2010–11. These cause discontinuities in deep soil layers (NCAR Climate Data Guide, GMAO).
- **Rain:**
  - A discernible jump in MERRA-2 model rain when SSM/I F08 arrived in 1987 (GMAO).
  - The corrected rain we use is gauge-based at low and mid latitudes, tapers to pure model between 42.5° and 62.5°, and is pure model poleward of 62.5°. Over Africa it uses CMAP.
  - So "what's behind this number" depends on latitude, and the app can say so.

**Correction:** the world report's cloud row ("88 proven: 39 up, 49 down") overstates the case. Use the CERES-only figures until the alibi check is in the app.

## 5. Shortlist, ranked (effort is backend unless marked)
| # | Addition | Why | Effort | Who |
|---|---|---|---|---|
| 1 | **Instrument alibi check** in `/api/analyse`: list the documented source changes inside the window; step-vs-trend (BIC); re-test on each single-source segment. Verdict: *survives* / *could be the instrument* | Unique; scientifically strong ("Best Use of Science"); already caught our own error | 2 h | Claude |
| 2 | **Compare two places**: `/api/compare` tests the trend of A − B and says "rates differ" / "can't tell apart". It warns that "one significant, one not" is *not* a difference (Gelman & Stern 2006). Rival team AstroLogic's headline demo makes exactly that mistake (Sylhet p = 0.0497 vs Dhaka p = 0.19) | Explicit brief ask; 2 rivals have it | 1 h + frontend | Claude, Kanishk |
| 3 | **Wisconsin haze** as a demo case (the challenge author's own example) | Speaks to the person who wrote the challenge | 15 min | Claude |
| 4 | **El Niño-adjusted check**: regress out NOAA's Niño 3.4 / ONI (public, checked: it downloads, up to ASO 2026 = +2.46, a strong El Niño *now*), as in Foster & Rahmstorf (2011; GRL 2026 "Global warming has accelerated significantly") | Topical; one rival has it | 1.5 h | Claude |
| 5 | **Leave-one-year-out** ("which single year is the case leaning on?") added to robustness | Cheap; makes "Fragile" more precise | 30 min | Claude |
| 6 | **Weather-station witness worldwide** from NOAA NCEI Global Summary of the Month (listed in the Resources tab; access API needs no token) | Turns our UK-only witness global | 2–3 h | Claude |
| 7 | **An ocean case** (skin temperature over the sea) | Brief asks for oceans; the author's own research is coastal ocean | 30 min | Claude |
| 8 | **Place-type suggestions** (hot desert, wet tropics, cold, big city…) computed from the place's own data → suggested variables | Brief's SI ask, no AI guessing | 1 h | Claude |
| 9 | **Guided questions + watchable demo tours** ("Guess first: is it really getting hotter here?") | Brief asks; strong for presentation | frontend | Kanishk |
| 10 | Levels of the atmosphere (surface warms, stratosphere cools = greenhouse fingerprint), via MERRA-2 pressure levels on the team server | Brief asks; strongest science story, but heavy | stretch | Kanishk's server |

## 6. What this means for the pitch
- **Judging:** 5 criteria scored 1–5: impact, creativity, validity, relevance (NASA data as the core), and **presentation**. The demo is **7 slides max or a 30-second video**.
- **Story:** "Every team can fit a line. We built a detective that cross-examines it: is it just persistence (Typical vs Detective)? Did the satellite change (instrument alibi)? Is one El Niño year carrying it? Does another witness agree? And it caught our own data lying about clouds."
- **Lead with what is truly ours:** instrument alibi, linked clues out-of-sample, records and emergence, impact, and the world report's "28% unsupported".

## Sources
- Judging criteria: https://www.spaceappschallenge.org/resources/judging-awards-guide/
- Challenge resources: https://www.spaceappschallenge.org/2026/challenges/earth-system-trend-detective/?tab=resources
- Rival repos (read only):
  - github.com/asifff113/Nasapretest (CaseFile Earth)
  - github.com/Arush763/trend-detective
  - github.com/GiuseppePrbst/trend-detective-lab
  - github.com/adilsay3d22/earth-trend-detective
  - github.com/NaveenHerath/Mostly-Significant
  - github.com/el-pitchula/IONA
- Rival videos: youtube.com/watch?v=kurz82CKaUY (CaseFile Earth), youtube.com/watch?v=ifttH-iTz4o (Megacity Climate Intelligence)
- POWER solar sources (GEWEX SRB R4 1984–2000, CERES SYN1deg 2001–): POWER Data Access Viewer overview (arcgis.com item db2adab099f246f6b4d4c113f2a5ea09); https://power.larc.nasa.gov/docs/methodology/
- MERRA-2 aerosol observing system: Randles et al. 2017, J. Climate 30, 6823, Table 2 (https://pmc.ncbi.nlm.nih.gov/articles/PMC5859955/)
- MERRA-2 streams, rain correction by latitude: https://climatedataguide.ucar.edu/climate-data/nasas-merra2-reanalysis
- MERRA-2 precipitation jumps: https://gmao.gsfc.nasa.gov/science-snapshots/merra-2-global-precipitation-time-series/
- Foster & Rahmstorf 2026, GRL 53, e2025GL118804; NOAA ONI: https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt
