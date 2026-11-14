---
version: 1
slug: "frontend-src-app-tsx"
primary_target: "frontend/src/App.tsx"
related_targets: []
---

## Scope
Whole web app in `frontend/` (Vite + React + TS). Mode: Operate (judges complete one case: place → variable → verdict). Routes: Case (home), Report card, Map, Methods.

## Audience and job
Space Apps judges, about a minute each. Job: pick a place and a variable, read a verdict they trust, see why. Proof: real API output from NASA POWER, the synthetic validation, and England soil (89 typical → 0 after FDR).

## Direction contract
THESIS: every screen is a figure plate from a paper: lettered panels (a, b, c) with a figure legend that *is* the verdict. Refuses the space-dashboard default (black, glowing globe, KPI tiles).
OWN-WORLD: cool grey-white plate paper, ink-navy shell band, RdBu-style diverging data colours (rising = vermilion, falling = cobalt), hatched fills for "not yet". Panel letters set bold in the sans; hairline axes; tabular figures. Verdict states: strong = solid ink, some = ink outline, mixed = amber, not yet = hatched, none = grey.
STORY: the judge sees a finished case (Lincolnshire, air temperature) at once. The legend says the verdict in one sentence. Panel letters tie each sentence to its chart. Typical vs Detective sits side by side. Then they change place or variable.
FIRST VIEWPORT: top band with name, 4 nav tabs and the place + variable controls (presets + select). Left two-thirds: Fig. 1 with panel a (raw monthly) above panel b (seasons removed + Sen trend). Right third: the legend column with verdict badge, headline, slope ± 95%, panel c (typical vs Detective), and the second-witness badge.
FORM: scientific figure plate, candidate 4 of 7. Signature move: hovering a legend clause highlights its lettered panel; "years to know" drawn as an exact-length bar (record years vs years needed). Raises: fixed row columns where status restyles the row only (split-flap); one message per line (airport wayfinding); length = exact quantity (labanotation). seed:9c3ece1f1a7f4ba4
FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
