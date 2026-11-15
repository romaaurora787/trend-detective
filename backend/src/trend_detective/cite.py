"""'Cite this': ready-to-paste references (APA 7, Harvard, BibTeX) for one case.

Students are the brief's audience, so every case can be cited in a report. The list is built
from the data the case actually used: NASA POWER and its source product (MERRA-2, MERRA-2
aerosols, CERES / GEWEX SRB or MODIS), the trend method, and this tool. Strings only, no AI.

AI-use note: drafted with Claude (Anthropic) during the hackathon.
"""
from __future__ import annotations

import datetime as dt

from .catalogue import BY_ID

SITE = "https://kaakserver.tail042e87.ts.net/trend-detective/"

REFS = {
    "power": dict(authors=["NASA Langley Research Center POWER Project"], year=2026,
                  title="NASA Prediction Of Worldwide Energy Resources (POWER): monthly and daily data",
                  container="NASA Langley Research Center", url="https://power.larc.nasa.gov/", kind="misc",
                  note="These data were obtained from the NASA Langley Research Center POWER Project funded through "
                       "the NASA Earth Science Directorate Applied Science Program."),
    "merra2": dict(authors=["Gelaro, R.", "McCarty, W.", "Suárez, M. J.", "et al."], year=2017,
                   title="The Modern-Era Retrospective Analysis for Research and Applications, Version 2 (MERRA-2)",
                   container="Journal of Climate", volume="30", issue="14", pages="5419–5454",
                   doi="10.1175/JCLI-D-16-0758.1", kind="article"),
    "merra2_aer": dict(authors=["Randles, C. A.", "da Silva, A. M.", "Buchard, V.", "et al."], year=2017,
                       title="The MERRA-2 aerosol reanalysis, 1980 onward. Part I: System description and data "
                             "assimilation evaluation",
                       container="Journal of Climate", volume="30", issue="17", pages="6823–6850",
                       doi="10.1175/JCLI-D-16-0609.1", kind="article"),
    "ceres": dict(authors=["Doelling, D. R.", "Loeb, N. G.", "Keyes, D. F.", "et al."], year=2013,
                  title="Geostationary enhanced temporal interpolation for CERES flux products",
                  container="Journal of Atmospheric and Oceanic Technology", volume="30", issue="6",
                  pages="1072–1090", doi="10.1175/JTECH-D-12-00136.1", kind="article"),
    "gewex": dict(authors=["Stackhouse, P. W., Jr.", "Gupta, S. K.", "Cox, S. J.", "et al."], year=2011,
                  title="The NASA/GEWEX Surface Radiation Budget Release 3.0: 24.5-year dataset",
                  container="GEWEX News", volume="21", issue="1", pages="10–12", kind="article"),
    "hamed_rao": dict(authors=["Hamed, K. H.", "Rao, A. R."], year=1998,
                      title="A modified Mann-Kendall trend test for autocorrelated data",
                      container="Journal of Hydrology", volume="204", issue="1–4", pages="182–196",
                      doi="10.1016/S0022-1694(97)00125-X", kind="article"),
    "sen": dict(authors=["Sen, P. K."], year=1968,
                title="Estimates of the regression coefficient based on Kendall's tau",
                container="Journal of the American Statistical Association", volume="63", issue="324",
                pages="1379–1389", doi="10.1080/01621459.1968.10480934", kind="article"),
}


def _source_keys(var: str) -> list[str]:
    meta = BY_ID.get(var, {})
    src = meta.get("source", "")
    if meta.get("satellite"):
        return []  # MODIS: the catalogue carries its own citation
    if "CERES" in src:
        return ["power", "ceres", "gewex"]
    if "aerosol" in src:
        return ["power", "merra2_aer"]
    return ["power", "merra2"]


def _authors_apa(a: list[str]) -> str:
    if len(a) == 1:
        return a[0]
    return ", ".join(a[:-1]) + (", " if a[-1] == "et al." else ", & ") + a[-1]


def _authors_harvard(a: list[str]) -> str:
    if len(a) == 1:
        return a[0]
    if a[-1] == "et al.":
        return a[0] + " et al."
    return ", ".join(a[:-1]) + " and " + a[-1]


def _fmt(key: str, r: dict, accessed: str) -> dict:
    a, y, t = r["authors"], r["year"], r["title"]
    doi = f"https://doi.org/{r['doi']}" if r.get("doi") else r.get("url", "")
    if r["kind"] == "article":
        vol = f"*{r.get('volume', '')}*" + (f"({r['issue']})" if r.get("issue") else "")
        apa = f"{_authors_apa(a)} ({y}). {t}. *{r['container']}*, {vol}, {r.get('pages', '')}. {doi}".strip()
        harvard = (f"{_authors_harvard(a)} ({y}) '{t}', *{r['container']}*, {r.get('volume', '')}"
                   f"{'(' + r['issue'] + ')' if r.get('issue') else ''}, pp. {r.get('pages', '')}. {doi}").strip()
        bib = (f"@article{{{key}{y},\n  author = {{{' and '.join(x for x in a if x != 'et al.')}"
               f"{' and others' if 'et al.' in a else ''}}},\n  title = {{{t}}},\n  journal = {{{r['container']}}},\n"
               f"  year = {{{y}}},\n  volume = {{{r.get('volume', '')}}},\n  number = {{{r.get('issue', '')}}},\n"
               f"  pages = {{{r.get('pages', '').replace('–', '--')}}}"
               + (f",\n  doi = {{{r['doi']}}}" if r.get("doi") else "") + "\n}")
    else:
        label = "" if r["kind"] == "app" else " [Data set]"
        apa = f"{_authors_apa(a).rstrip('.')}. ({y}). *{t}*{label}. {r['container']}. Retrieved {accessed}, from {r['url']}"
        harvard = f"{_authors_harvard(a)} ({y}) *{t}*. {r['container']}. Available at: {r['url']} (Accessed: {accessed})."
        who = f"{{{a[0]}}}" if len(a) == 1 else " and ".join(a)  # an organisation stays one braced name
        bib = (f"@misc{{{key}{y},\n  author = {{{who}}},\n  title = {{{t}}},\n  year = {{{y}}},\n"
               f"  howpublished = {{\\url{{{r['url']}}}}},\n  note = {{Accessed {accessed}}}\n}}")
    out = {"key": key, "apa": apa, "harvard": harvard, "bibtex": bib}
    if r.get("note"):
        out["acknowledgement"] = r["note"]
    return out


def citations(var: str, case_url: str = SITE, name: str = "") -> dict:
    d = dt.date.today()
    accessed = f"{d.day} {d:%B %Y}"  # not %-d: that is Linux/macOS only and fails on Windows
    meta = BY_ID.get(var, {})
    items = [_fmt(k, REFS[k], accessed) for k in _source_keys(var)]
    if meta.get("citation"):
        c = meta["citation"]
        items.append({"key": "modis", "apa": c, "harvard": c,
                      "bibtex": "% MODIS product: use the reference above (LP DAAC)\n"})
    items += [_fmt(k, REFS[k], accessed) for k in ("hamed_rao", "sen")]
    tool = dict(authors=["Srivastava, A.", "Sachan, K. K."], year=2026,
                title=f"Trend Detective: is it really changing?{' ' + name + ',' if name else ''} "
                      f"{meta.get('name', var).lower()} [Web application]",
                container="NASA Space Apps Challenge 2026", url=case_url, kind="app")
    items.insert(0, _fmt("trenddetective", tool, accessed))
    return {"variable": var, "accessed": accessed, "items": items,
            "how_to_use": "Cite the tool and the data. The first entry is this case; the rest are the data and methods behind it."}
