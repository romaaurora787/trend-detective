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

## 3. Beyond the trend line ([beyond_scan.md](docs/beyond_scan.md))
| Place | Finding |
|---|---|
| **Lincolnshire, daytime highs** | Record highs broken **3.1× as often as chance** since 2011; **summer** warming fastest (+0.51 °C/decade); emerged from the noise in **2016** |
| **Lincolnshire, air temperature** | Records 2.1× chance; **winter** fastest (+0.42 °C/decade); emerged **2008** |
| **Lincolnshire, frost days** | Record-low frost months **4.9× as often as chance** |
| **Lincolnshire, sunshine** | Records 2.3× chance; **spring** brightening fastest; emerged 2014 |
| **Svalbard (Arctic)** | Record highs **3.8×**; **winter** warming **+1.3 °C/decade** |
| **Amazon (Rondônia)** | Daytime-high records **4.6×**, **22% more erratic** since 2003; record-dry months **3.7×**; drying emerged in **1999** |
| **Beijing haze** | **Turning point ~2010**: rising before, falling after; record-clean months 2.6× chance since 2018; **19% calmer** since 2013 |
| **Delhi haze** | Record-haze months **2.5×** chance since 2018; **20% more erratic** since 2013 |
| **London haze** | Record-clean months **4.5×** chance since 2018 |

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
