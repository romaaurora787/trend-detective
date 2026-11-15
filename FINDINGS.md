# Findings so far (one page for the team)

All numbers come from code in `backend/` on NASA POWER monthly data, 1981–2025, unless stated. Details are in `docs/`.

## 1. Our method is right (proof)
- **No real trend:** the naive test claims one up to **55%** of the time. Our verdict: **5–7%**. ([methods.md](docs/methods.md))
- **Real trend of 0.2/decade:** ours catches it **93%** of the time; the simple raw-data line catches **6%**.
- **Checked against independent records:**
  - Met Office HadCET thermometers: **+0.31** vs NASA **+0.32 °C/decade**, monthly r = **0.99**.
  - GPCP rainfall: r = 0.97.
  - ESA soil moisture: agrees there's no regional trend.

## 2. What makes us different (features A, B, C)
- **A. Typical vs Detective.** England soil: a typical map shows **89 of 137** places changing; **0** survive our checks.
- **B. Place report card.** Lincolnshire: **10 proven, 1 not yet (wind, ~24 more years), 4 no trend.**
- **C. Second witness.** Met Office, NASA GPCP (global rainfall) and ESA soil moisture each confirm or caution against a verdict.

## 2b. The world report: 15 variables × 111 land points (`/api/world`, `backend/scripts/world_report.py`)
Across **1,615 place-variable checks** worldwide, a typical analysis claims a trend in **1,166 (72%)**. The Detective proves **834 (52%)**. **332 of the typical claims (28%) can't be supported** once natural persistence is accounted for. The Detective never proved a trend the typical analysis missed (0 cases), so it isn't finding different trends, only refusing to over-claim.

| Variable | Proven (↑ / ↓) | Typical claims | Unsupported |
|---|---|---|---|
| **Root-zone soil wetness** | 29 (20 / 9) of 109 | 86 | **57**, more than half the world's points |
| **Topsoil wetness** | 35 (25 / 10) of 110 | 83 | **48** |
| Evaporation from land | 43 (31 / 12) | 77 | 34 |
| Air temperature | **80 (79 / 1)** of 111 | 96 | 16 |
| **Night-time lows** | **88 (88 / 0)** | 93 | 5 |
| **Frost days** | **35 (0 / 35)** of 64 frost places | 52 | 17 |
| Humidity (water in the air) | 83 (81 / 2) | 100 | 17 |
| **Wind speed** | 40 (**8 / 32**) | 52 | 12 |
| Rainfall | 39 (26 / 13) | 50 | 11 |
| Cloud cover ⚠️ | ~~88 (39 / 49)~~ **47 survive the instrument check** (see 2c) | 97 | 9 |

**Takeaways:**
- **Soil moisture is where typical analyses mislead most:** over half the world's apparent soil trends don't survive.
- **Nights warming everywhere** (88 up, 0 down) and **frost retreating everywhere** it's proven (35 of 35).
- **Winds mostly slowing** where a change is proven (32 of 40), consistent with the reported global "stilling" of surface winds.
- "Unsupported" means *not proven once persistence is allowed for*, not proven false.

## 2c. The instrument alibi: we caught our own data (`backend/scripts/instrument_alibi_scan.py`)
NASA POWER sunshine and cloud come from **GEWEX SRB (1984–2000)** and then **CERES (2001 on)**.

**Cloud cover:**
- A single jump at 2001 explains the "trend" better than a trend at **59%** of proven places. With the jump at other years it's 6–36%; temperature (no switch) gives 14%.
- On CERES alone (2001–2025), **47 of 88** survive and **15 reverse direction**.

**Sunshine:** 58 → 28 proven on CERES alone.

**Lincolnshire passes:** sunshine rises about +0.15 per decade under *both* instruments, and is significant on CERES alone (p = 0.015).

Details and the other documented source changes (haze 2014, soil streams 1991/2001/2011, rain by latitude) are in [docs/methods.md](docs/methods.md) and `backend/src/trend_detective/api.py` (instrument check).

## 3. Beyond the trend line ([beyond_scan.md](docs/beyond_scan.md))
The methods were re-checked for false alarms on synthetic weather where nothing is changing (`backend/scripts/validate_beyond.py`). Shuffling month by month gave too many false alarms (records 13–22%, "more erratic" 15–19%). We now shuffle **whole years in 5-year blocks**: records 5–7% (two-sided limit 10%), "erratic" 4.5–7.5%, and turning points need a BIC gain > 10 (7.7% even in very persistent weather; real breaks still found 93% of the time). **Claims that didn't survive were removed**: Amazon "22% more erratic", Lincolnshire mean-temperature records, and haze record counts in London, Beijing and Delhi (record too short).

| Place | Finding (passes the corrected tests) |
|---|---|
| **Lincolnshire, daytime highs** | Record highs **3.2× as often as chance** since 2011; **summer** warming fastest (+0.51 °C/decade); emerged from the noise in **2016** |
| **Lincolnshire, air temperature** | **Winter** fastest (+0.42 °C/decade); emerged **2008** |
| **Lincolnshire, frost days** | Record-low frost months **4.8× as often as chance** |
| **Lincolnshire, sunshine** | Record highs **2.1×** chance; **spring** brightening fastest; emerged 2014 |
| **Svalbard (Arctic)** | Record highs **3.2×** chance; **winter** warming **+1.3 °C/decade** |
| **Amazon (Rondônia)** | Record daytime highs **4.2×** and record-dry months **3.8×** chance; drying emerged in **1999** |
| **Sahel** | Record-wet months **1.8×** chance; rain recovery emerged 2017 |
| **Beijing haze** | **Turning point ~2010**: rising before, falling after (BIC gain 16) |
| **Delhi haze** | **18% more erratic** since 2013 (p = 0.04) |

## 4. Linked clues that hold on NEW places ([linked_clues.md](docs/linked_clues.md))
Rules were committed **before** testing, then tested on 111 global and 71 UK grid points:
- **Cool places: a warmer month is a more humid month.** 94% of new cool places; 100% of the UK.
- **UK: windy winters mean fewer frosts.** 94% of UK points (r = −0.61). The rule did *not* hold in other mild-winter climates.
- **Haze dims the sunshine reaching the ground** (cloud held fixed): 83% of places.
- **Rain fills next month's soil:** 99%.
- **Rejected:** dry soil → wind, cloud → day–night range. The placebo held in **0 of 182** places.

## 4b. New evidence (Sat evening): satellites, seasons, climate modes, drought
**Satellite greenness (MODIS NDVI, 2000–2025; Terra and Aqua agree everywhere below):**
- **Delhi greening** +0.020 NDVI/decade (p ≈ 6e-9), **Beijing** +0.030 (p ≈ 0), **Spain** +0.016, **Sahel** +0.006 (the "re-greening"). Matches Chen et al. 2019 (China and India lead the world's greening).
- **Amazon (Rondônia) browning** −0.0045/decade (Aqua −0.0067, p ≈ 4e-8): deforestation and drought.
- **Lincolnshire:** not proven over the whole year (p = 0.09), but the **seasonal Kendall test is significant (p = 0.009), driven by autumn**: a longer growing season.

**Delhi: nights hotter at the ground, days not** (MODIS land surface temperature): night +0.70 °C/decade (Aqua satellite agrees: +0.62, both proven). Late morning −0.43 °C/decade on Terra (proven), but Aqua's afternoon pass only leans the same way (−0.24, p = 0.18), so say "daytime ground heat is not rising", not "days are cooling". Same place: greener (NDVI up) and the air less "thirsty" (VPD −0.11 kPa/decade). Irrigation and greening are a likely reason the daytime surface isn't heating; nights keep warming.

**Cities hold heat at night (MODIS, ground temperature at ~22:30):** London +0.37 °C/decade (Aqua +0.46), both proven; Lincolnshire +0.29 (Aqua +0.26, not proven).

**NASA GPM IMERG satellite rainfall as a witness (1998–2025, 0.1°, needs Earthdata login):** monthly correlation with NASA POWER rain at Lincolnshire r = 0.96.
- **Amazon drying confirmed:** IMERG −0.63 vs NASA POWER −0.65 mm/day/decade over the same 1998–2025 years (GPCP agrees too).
- **Sahel wetting:** GPCP confirms it from 1983; IMERG (from 1998) only leans wetter, because most of the recovery happened before 1998. Say "wetter since the 1980s droughts".
- **Delhi rain rising: NOT confirmed** by GPCP or IMERG (NASA POWER's rate is about twice theirs). Treat as unproven.
- **Beijing rain rising: confirmed** (IMERG +0.12 vs NASA POWER +0.11 mm/day/decade since 1998, both proven). All 13 demo places now have IMERG cached; UK places correlate with NASA POWER at r ≈ 0.95–0.97.
- **East Africa rain rising since 1998:** NASA POWER +0.30 vs IMERG +0.07 mm/day/decade, not confirmed. MERRA-2 probably overstates it.

**Amazon drying is real and growing:** rain −0.53 mm/day/decade, confirmed by NASA GPCP v3.3; **drought months (SPI-3 ≤ −1) 0.9 a year in the 1980s → 9.4 a year in the last 10 years**; driest 12 months ended Jan 2016 (the 2015–16 El Niño). VPD +0.08 kPa/decade (strong).

**Climate modes:** Spain's winter rain follows the North Atlantic Oscillation (r = −0.65); Lincolnshire's winter temperature too (r = +0.53), and its warming survives removing the NAO (+0.36 °C/decade). East Africa rain follows the Indian Ocean Dipole and El Niño.

**Did climate models see it coming?** (7 CMIP6 HighResMIP models, same years, point at the box centre): Lincolnshire warming +0.33 °C/decade is **stronger than every model** (+0.14 to +0.30); Svalbard +0.60 is **weaker than every model** (+0.82 to +1.2; reanalyses also disagree on Arctic trends); Delhi night-time lows +0.13 sit **inside** the model range; Amazon drying −0.53 mm/day/decade is **far stronger than any model** (−0.11 to +0.03), so treat it with care even though GPCP agrees. Caveat: these runs had the real ocean temperatures until 2014.

**When did the evidence become strong?** Replaying each record from 1981: Lincolnshire warming proven by 1999 and every year since; Svalbard by 2005; Amazon drying by 2005; Delhi greening by 2015.

**Change points:** Lincolnshire warming is gradual (a steady trend fits as well as a jump). East Africa cloud shows a sudden shift around 1998 (near the data-source change: see 2c).

**A typical map lights up on pure noise:** shuffle the years (destroying any trend) and a typical test still marks ~60 of 137 England & Wales soil cells "changing" (up to 111).

**Reproducible from scratch:** `notebooks/reproduce_lincolnshire.ipynb` downloads NASA POWER directly and gets the same +0.333 °C/decade.

## 5. Data
- **NASA POWER:** no login; MERRA-2 and CERES; 1981–2025.
- **NASA GPCP v3.3:** global, 1983–2025; downloaded on the team server.
- **ESA CCI soil moisture v09.2:** 1978–2024; aggregated on the team server.
- **Met Office HadCET.**
- **NASA MODIS** MOD13Q1 (NDVI) and MOD11A2 (land surface temperature), Terra + Aqua, via Microsoft Planetary Computer (no login).
- **NOAA climate indices:** ONI, NAO, Dipole Mode Index (IOD), PDO. **NASA GISTEMP v4.** **ERA5** via Open-Meteo. **NOAA GHCN** stations. **NASA EONET.**
- **Caveat:** NASA POWER rate-limits bursts. Demo cases must come from the cache.
