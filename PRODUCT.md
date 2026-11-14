# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Vite + React + TypeScript frontend in `frontend/`, deployed to Vercel as a static site. It calls the existing FastAPI backend (`backend/`, deployed to Render) over GET-only JSON endpoints documented in README.md.

## Users

Primary tonight: NASA Space Apps 2026 judges (including Lincoln event judges and UK Space Agency judges). They spend about a minute on the live link, so one polished case must land at once, and then they can explore. Secondary: curious members of the public who want to ask about their own place.

## Product Purpose

Earth System Trend Detective answers one question for any place and any of 15 NASA variables: is it really changing, how fast, how sure are we, where, and how many more years until we would know. Success means a judge picks a place and variable and gets a plain-English verdict they trust, with the evidence one click away.

## Positioning

Most trend tools fit a straight line and report whatever comes out. The Detective corrects for autocorrelated natural variability, requires two different tests to agree, controls false discoveries on maps (Benjamini-Hochberg), estimates years-to-detect (Weatherhead), checks against a second witness (HadCET thermometers, GPCP, ESA CCI soil moisture), and shows side by side what a typical analysis would have claimed. Headline proof: England soil wetness, where a typical analysis flags many cells and the Detective flags none after correction.

## Operating Context

Judged on a laptop or phone through a public link, in a time-boxed judging round; also shown in a 30-second screen recording. Data comes from NASA POWER (MERRA-2, CERES), 1981 to 2025, cached by the backend so demo cases load fast.

## Capabilities and Constraints

- Endpoints: `/api/variables`, `/api/analyse`, `/api/report-card`, `/api/map`, `/api/validation`.
- Verdict labels: strong, some, mixed, not_yet, none ("No trend detected"). Second-witness badge: confirmed, consistent, caution.
- Boxes up to 10 by 10 degrees; maps widen boxes under 2 degrees.
- Verdict numbers are always computed by code, never by AI. An optional AI variable finder may only choose ids from `/api/variables`.
- Undecided: final three demo cases (candidates in docs/demo_scan.md).

## Brand Commitments

Name: Earth System Trend Detective. Plain English for non-scientists, honest about limits ("trend is not cause"). Must credit NASA POWER, MERRA-2, CERES and partner data sources, and state AI use.

## Evidence on Hand

Real API responses in `docs/examples/`; synthetic validation results (false alarms about 5 to 7% vs up to 55% for a naive test) in `docs/methods.md` and `docs/images/proof_it_works.png`; demo scan in `docs/demo_scan.md`. No testimonials, users or press exist; do not invent any.

## Product Principles

1. Never claim more than the statistics support.
2. One clear answer first, evidence second, method third.
3. Show the contrast with a typical analysis; it is what makes this different.
4. Every number traces to code and a cited NASA dataset.
