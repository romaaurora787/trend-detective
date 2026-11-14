# Linked clues: which connections between variables are real? (screen run Sat 14 Nov)

Script: `backend/scripts/links_screen.py`. Raw results: `backend/data/links_screen.json`.

**Protocol, fixed before looking:**
- Each link has a physical mechanism and a predicted sign.
- Seasons **and** trends are removed from both series, so two things that merely both rise can't look linked.
- Cause comes before effect where a lag is stated.
- Significance uses an effective sample size for autocorrelated series (Bretherton et al. 1999).
- A link **holds** at a place only if it has the predicted sign with p < 0.05 in **both halves** of the record.
- Tested in 10 contrasting climates. A **placebo** (random computer-generated noise) must fail.

## Results
| Link | Mechanism | Holds in | Verdict |
|---|---|---|---|
| Rain this month → wetter root zone next month | Soil stores rain for weeks | **10 / 10** | Universal (expected) |
| More haze → less sunshine at the ground (cloud held fixed) | Particles reflect and absorb sunlight | **8 / 10** | Robust. Two different sources: MERRA-2 aerosols vs CERES / GEWEX sunshine |
| Dry soil last month → hotter days this month (warm season) | Wet soil cools by evaporating; dry soil can't | **7 / 10** | Robust **except in wet places**, as the evaporation regime below predicts |
| Warmer months → more water vapour | Warm air can hold ~7% more vapour per °C | 4 / 10 | **Only in cool, wet places.** In Delhi and Nairobi hot months have *less* vapour: heat and drought arrive together |
| More cloud → smaller day–night range | Clouds block the sun by day and trap heat at night | 4 / 10 | Not reliable in this data. Don't use |
| Windier cold months → fewer frosts | Frost needs calm, clear nights | 1 / 5 (Lincolnshire only, r = −0.65) | A local fact about the UK, not a law |
| **Your chain:** dry soil → hotter → windier | A hot surface mixes faster wind down | 5 / 10 | **Not reliable.** It can also run the other way (wind dries soil), so we can't claim a direction |
| **Placebo:** random noise vs rainfall | None | **0 / 10** | The test doesn't invent links |

## The non-obvious finding that ties it together
**What controls evaporation in the warm season?**
- In **9 of 10** places it's **soil water**: wetter soil means more evaporation (r = +0.74 to +0.92).
- In **Lincolnshire alone** it's **sunshine** (r = +0.55 vs +0.40 for soil). The UK is wet enough that the limit is energy, not water.

This predicts the soil → heat result **before we look at it**. Dry soil should heat the air where soil controls evaporation (Kansas r = −0.59, Amazon −0.84, Beijing −0.40, Sahel −0.37), but not in Lincolnshire, where soil doesn't control evaporation (r = −0.15, fails). Two separate analyses agree.

**Humidity per °C of warming** (theory: about 7%): Lincolnshire **+5.8%**, close to theory. Delhi **−7.2%** and Nairobi **−6.2%**, the opposite sign. The famous rule describes how much water the air **can** hold, not how much it **does**. Over dry land the water isn't there to evaporate.

## Honest limits
- Soil, evaporation, humidity and temperature here all come from **one model (MERRA-2)**. Links inside it partly show the model's own physics. To confirm with independent data, test soil → heat with **ESA satellite soil moisture** (we have Europe and East Africa) against MERRA-2 or station temperatures.
- 10 places is a screen, not a global proof. The map version (every grid cell) would show where each link holds.
- Correlation over months shows a consistent link, not proof of cause. The mechanism, the time order and the regime check together make the case.
