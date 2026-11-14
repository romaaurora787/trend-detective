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
| Cloud cover | 88 (39 / 49) | 97 | 9 |

**Takeaways:**
- **Soil moisture is where typical analyses mislead most:** over half the world's apparent soil trends don't survive.
- **Nights warming everywhere** (88 up, 0 down) and **frost retreating everywhere** it's proven (35 of 35).
- **Winds mostly slowing** where a change is proven (32 of 40), consistent with the reported global "stilling" of surface winds.
- "Unsupported" means *not proven once persistence is allowed for*, not proven false.

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

## 5. Data
- **NASA POWER:** no login; MERRA-2 and CERES; 1981–2025.
- **NASA GPCP v3.3:** global, 1983–2025; downloaded on the team server.
- **ESA CCI soil moisture v09.2:** 1978–2024; aggregated on the team server.
- **Met Office HadCET.**
- **Caveat:** NASA POWER rate-limits bursts. Demo cases must come from the cache.
