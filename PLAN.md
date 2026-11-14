# Tonight's plan (Sat 14 Nov)

Repo: https://github.com/romaaurora787/trend-detective (private until submission). The backend, statistics, proof chart, demo-case scan and Methods draft are **done** (see README, `docs/`). The Friday checklist is done.

**Rule:** submit a complete draft tonight. The Project tab can be edited and resubmitted until **Sun 23:59**, so Sunday is only for polish.

### Who does what
| Time | Kanishk (website, AI, deploy) | Akshita (statistics, words, pitch) | Claude (on Akshita's laptop) |
|---|---|---|---|
| **17:00–17:30** | Accept the GitHub invite, then `git clone`. Run the backend (`cd backend && uv sync && uv run uvicorn trend_detective.api:app --reload`). Read the README API section. | Open the shared doc: **references list** and **AI-use log**. Copy in the references from `docs/methods.md`. | Check the Tailscale server download; plan how to use that data |
| **17:30–20:00** | **One full case working:** pick a place (map + presets) → choose a variable → chart (raw + seasons removed + trend line) → **verdict card**. Use `docs/examples/*.json` while building. | **Own the design:** confirm or change the verdict cut-offs (p<0.01 / p<0.05 / 100 years). Rewrite `docs/methods.md` in your own words. Pick the **3 demo cases** from `docs/demo_scan.md`. | Weather-station cross-check (Met Office Central England Temperature vs our NASA number); `/api/case` presets for the 3 demo cases; `/api/report` (one-page case summary) |
| **20:00–21:30** | **Map view:** colour each cell by trend, mark cells that pass the correction, show the summary counts. **Methods page:** proof chart + text. | **Project page text** (draft in the shared doc): summary, how it works, benefits, NASA data, Space Agency data, references, AI use | Data from the Tailscale server joins the catalogue (if usable); deploy config (Render + Vercel) |
| **21:30–22:00** | Deploy: backend to Render, frontend to Vercel. Test the live link in a private window. | Write the video script (section 7) with the real demo numbers | Check every number on the site against the backend |
| **22:00 CHECKPOINT (together, 10 min)** | Does one case work **on the live link**, from place to verdict to chart? If not, cut the next item on the drop list now. | | |
| **22:00–23:00** | AI variable finder (Claude API, picks **only** from `/api/variables`; dropdown fallback). Fix bugs. | Record the screen for the video; edit to **≤30 s** with subtitles. Take screenshots (verdict card, map, proof chart). | Draft README AI-use notes; final references list |
| **23:00–23:30** | **Together:** paste the project page text, upload images, add the video link, make the GitHub repo **public**, test all links in a private window, tick both boxes, **SUBMIT**. | | |

### Sunday (polish only, already submitted)
FortiGuard classification request for the site · fix anything the night revealed · re-record the video if needed · resubmit by **22:00**, not 23:59.

### Drop list, in this order, if behind at 22:00
1. AI variable finder (use a dropdown)
2. Case report export
3. Data from the Tailscale server
4. Map view (keep the proof chart and a static map screenshot)

**Never drop:** one polished case on the live link, the verdict card, the proof chart, the ≤30 s video, the references list, the AI-use notes.

### Demo cases (choose 3; real numbers from `docs/demo_scan.md`)
- **Lincolnshire, your home case:** warming +0.33 °C/decade (strong), frost days falling, rain no trend, wind "not significant yet, about 24 more years". Shows every verdict type.
- **England soil, the false-alarm lesson:** 18 cells "significant" alone → 0 after correction.
- **East Africa rainfall, opposite trends:** 86 cells wetter and 24 drier in one region.
- **City air:** Delhi haze rising vs Beijing haze falling.
- **Arctic:** Svalbard +0.60 °C/decade, twice Lincoln's rate.

---

