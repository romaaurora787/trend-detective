"""Build the 7-slide demo deck (docs/demo/trend_detective_slides.pdf) from live-site screenshots.

Usage (from the repo root):
    backend/.venv/bin/python docs/demo/make_slides.py --team "Your Team Name"

The screenshots in docs/demo/img/ were taken from the live site on Sun 15 Nov 2026
(browser at 1280x800). Every number on the slides comes from FINDINGS.md / the API;
keep them in step with docs/SUBMISSION.md if anything changes.

AI-use note: drafted with Claude (Anthropic) during the hackathon.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.image as mpimg  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402

HERE = Path(__file__).resolve().parent
IMG = HERE / "img"
SITE = "kaakserver.tail042e87.ts.net/trend-detective"
CODE = "github.com/romaaurora787/trend-detective"
CHALLENGE = "Be An Earth System Trend Detective!"
NAMES = "Akshita Srivastava · Kanishk K. Sachan"

# Site palette (Relief Grid style)
BG, BLUE, RED, INK, MUTED, RULE = "#f7efdf", "#1b3fb0", "#c42a12", "#1d2433", "#5b6170", "#cfc4ad"

# Fonts: macOS system fonts if present, else matplotlib's bundled DejaVu.
SUP = Path("/System/Library/Fonts/Supplemental")


def _font(name: str, fallback: dict) -> dict:
    p = SUP / name
    if p.exists():
        font_manager.fontManager.addfont(str(p))
        return {"fontproperties": font_manager.FontProperties(fname=str(p))}
    return fallback


DISPLAY = _font("DIN Condensed Bold.ttf", {"family": "DejaVu Sans", "weight": "bold"})
BODY = _font("Arial Narrow.ttf", {"family": "DejaVu Sans"})
BODY_B = _font("Arial Narrow Bold.ttf", {"family": "DejaVu Sans", "weight": "bold"})
MONO = _font("Courier New.ttf", {"family": "DejaVu Sans Mono"})
MONO_B = _font("Courier New Bold.ttf", {"family": "DejaVu Sans Mono", "weight": "bold"})

W, H = 13.333, 7.5  # 16:9 inches


def new_slide(n: int, label: str, team: str):
    fig = plt.figure(figsize=(W, H), facecolor=BG)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, W)
    ax.set_ylim(0, H)
    ax.axis("off")
    ax.text(0.45, H - 0.42, f"[{n:02d}/07] {label.upper()}", color=BLUE, fontsize=11, **MONO_B)
    ax.text(W - 0.45, H - 0.42, "TREND DETECTIVE", color=BLUE, fontsize=15, ha="right", **DISPLAY)
    ax.plot([0.45, W - 0.45], [H - 0.6, H - 0.6], color=RULE, lw=1)
    ax.plot([0.45, W - 0.45], [0.55, 0.55], color=RULE, lw=1)
    ax.text(0.45, 0.25, f"Team {team} · {NAMES}", color=MUTED, fontsize=9, **MONO)
    ax.text(W - 0.45, 0.25, f"NASA Space Apps 2026 · {CHALLENGE}", color=MUTED, fontsize=9, ha="right", **MONO)
    return fig, ax


def title(ax, y, line1, line2=None, size=46):
    ax.text(0.45, y, line1, color=BLUE, fontsize=size, va="top", **DISPLAY)
    if line2:
        ax.text(0.45, y - size / 72 * 1.05, line2, color=RED, fontsize=size, va="top", **DISPLAY)


def bullets(ax, x, y, items, size=17, gap=0.52, width=None):
    for it in items:
        bold = it.startswith("**")
        txt = it.strip("*")
        ax.text(x, y, "■", color=RED if bold else BLUE, fontsize=size * 0.55, va="top")
        ax.text(x + 0.28, y + 0.03, txt, color=INK, fontsize=size, va="top", wrap=False,
                **(BODY_B if bold else BODY))
        y -= gap * (1 + txt.count("\n"))
    return y


def picture(fig, name, rect, crop=None, frame=BLUE):
    im = mpimg.imread(IMG / name)
    if crop:  # (x0, y0, x1, y1) in image pixels
        x0, y0, x1, y1 = crop
        im = im[y0:y1, x0:x1]
    a = fig.add_axes([rect[0] / W, rect[1] / H, rect[2] / W, rect[3] / H])
    a.imshow(im, interpolation="lanczos")
    a.set_xticks([])
    a.set_yticks([])
    for s in a.spines.values():
        s.set_color(frame)
        s.set_linewidth(1.5)
    return a


def caption(ax, x, y, text, color=MUTED, size=11):
    ax.text(x, y, text, color=color, fontsize=size, va="top", **MONO)


PNG_DIR: Path | None = None


def save(pdf, fig) -> None:
    pdf.savefig(fig, facecolor=BG)
    if PNG_DIR:
        PNG_DIR.mkdir(parents=True, exist_ok=True)
        fig.savefig(PNG_DIR / f"slide{len(list(PNG_DIR.glob('slide*.png'))) + 1}.png", facecolor=BG, dpi=150)


def build(team: str, out: Path) -> None:
    with PdfPages(out) as pdf:
        # 1. Title
        fig, ax = new_slide(1, "Title", team)
        ax.text(0.45, 6.25, "TREND", color=BLUE, fontsize=96, va="top", **DISPLAY)
        ax.text(0.45, 4.85, "DETECTIVE", color=BLUE, fontsize=96, va="top", **DISPLAY)
        ax.text(0.45, 3.45, "IS IT REALLY CHANGING?", color=RED, fontsize=40, va="top", **DISPLAY)
        ax.text(0.45, 2.45, f"Team {team}", color=INK, fontsize=22, va="top", **BODY_B)
        ax.text(0.45, 1.95, NAMES, color=INK, fontsize=20, va="top", **BODY)
        ax.text(0.45, 1.4, f"NASA Space Apps Challenge 2026: “{CHALLENGE}”", color=MUTED, fontsize=15,
                va="top", **BODY)
        ax.text(0.45, 1.02, "Lincoln, UK  ·  15 November 2026", color=MUTED, fontsize=15, va="top", **BODY)
        picture(fig, "hero.jpg", (6.35, 1.55, 6.55, 4.09))
        caption(ax, 6.35, 1.42, "The live site: pick a place and a NASA variable, scroll the evidence.", size=10)
        save(pdf, fig)
        plt.close(fig)

        # 2. The problem
        fig, ax = new_slide(2, "The problem", team)
        title(ax, 6.55, "A STRAIGHT LINE ON NOISY DATA", "LOOKS LIKE A TREND.", size=44)
        y = bullets(ax, 0.45, 4.75, [
            "Climate data is “sticky”: one warm month\nmakes the next likely to be warm too.",
            "A typical test treats every month as new\nevidence, so it finds trends in pure noise.",
            "**On NASA's own data (111 places × 19 variables),\n29% of typical trend claims can't be supported.",
        ], size=18, gap=0.5)
        # chart: false-alarm rate in 500 pure-noise simulations
        c = fig.add_axes([7.15 / W, 1.75 / H, 5.5 / W, 3.85 / H], facecolor=BG)
        groups = ["Some stickiness\n(φ = 0.5)", "Strong stickiness\n(φ = 0.85)"]
        typical, ours = [28, 55], [6, 7]
        x = [0, 1]
        bw = 0.32
        b1 = c.bar([i - bw / 2 - 0.01 for i in x], typical, bw, color=RED, label="Typical test")
        b2 = c.bar([i + bw / 2 + 0.01 for i in x], ours, bw, color=BLUE, label="Trend Detective")
        for bars in (b1, b2):
            for b in bars:
                c.text(b.get_x() + b.get_width() / 2, b.get_height() + 1.2, f"{b.get_height():.0f}%",
                       ha="center", va="bottom", color=INK, fontsize=18, **DISPLAY)
        c.axhline(5, color=INK, lw=1, ls=(0, (4, 3)), label="Should be 5%")
        c.set_xticks(x, groups)
        for t in c.get_xticklabels():
            t.set(color=INK, fontsize=12, **({"fontproperties": BODY["fontproperties"]} if "fontproperties" in BODY else {}))
        c.set_ylim(0, 65)
        c.set_xlim(-0.55, 1.55)
        c.set_yticks([0, 20, 40, 60], ["0", "20%", "40%", "60%"])
        c.tick_params(colors=MUTED, length=0, labelsize=10)
        c.grid(axis="y", color=RULE, lw=0.8)
        c.set_axisbelow(True)
        for s in ("top", "right", "left"):
            c.spines[s].set_visible(False)
        c.spines["bottom"].set_color(MUTED)
        fp = BODY["fontproperties"].copy() if "fontproperties" in BODY else font_manager.FontProperties()
        fp.set_size(14)
        c.legend(loc="upper left", frameon=False, labelcolor=INK, prop=fp)
        ax.text(7.15, 6.35, "FALSE ALARMS ON PURE NOISE", color=BLUE, fontsize=22, va="top", **DISPLAY)
        caption(ax, 7.15, 6.0, "500 simulated records with no trend at all")
        caption(ax, 7.15, 0.95, "Real 0.3/decade trends are still caught 99.7% of the time.", color=INK)
        save(pdf, fig)
        plt.close(fig)

        # 3. What it does
        fig, ax = new_slide(3, "What it does", team)
        title(ax, 6.55, "PICK ANY PLACE.", "GET AN HONEST ANSWER.", size=44)
        bullets(ax, 0.45, 4.7, [
            "Any town on Earth, 23 NASA variables:\nair temperature, rain, soil, haze, greenness…",
            "A 7-step scroll story: raw record, seasons\nremoved, trend, “could it be chance?”",
            "Corrected tests (Mann–Kendall with\nHamed–Rao, least squares with n_eff).",
            "**A verdict in plain words: strong evidence,\nsome, not yet (“about N more years”), none.",
        ], size=17, gap=0.48)
        picture(fig, "chance.jpg", (6.0, 1.0, 6.88, 4.3))
        caption(ax, 6.0, 5.95, "Lincolnshire air temperature: 540 months carry the evidence of", color=INK)
        caption(ax, 6.0, 5.67, "only ~326 independent ones. Still proven: +0.33 °C per decade.", color=INK)
        save(pdf, fig)
        plt.close(fig)

        # 4. The detective part
        fig, ax = new_slide(4, "The detective part", team)
        title(ax, 6.55, "THEN WE CROSS-EXAMINE IT.", size=44)
        ax.text(0.45, 5.75, "A sceptic's checks try to explain the trend away: a change of satellite? El Niño? "
                "one lucky year? convenient dates?", color=INK, fontsize=16, va="top", **BODY)
        ax.text(0.45, 5.4, "Then independent witnesses must agree: Met Office, weather stations, a second NASA "
                "satellite, other rain records.", color=INK, fontsize=16, va="top", **BODY)
        picture(fig, "crossexam.jpg", (0.45, 1.3, 7.3, 2.47), crop=(0, 230, 800, 500))
        picture(fig, "witnesses.jpg", (8.05, 0.85, 4.85, 3.35), crop=(0, 225, 400, 500))
        save(pdf, fig)
        plt.close(fig)

        # 5. We caught our own data
        fig, ax = new_slide(5, "We caught our own data", team)
        for i, (line, col) in enumerate([("89 CELLS LOOK", BLUE), ("LIKE CHANGE.", BLUE), ("0 SURVIVE.", RED)]):
            ax.text(0.45, 6.55 - i * 0.64, line, color=col, fontsize=44, va="top", **DISPLAY)
        y = 4.45
        for line, col, f in [
            ("Root-zone soil wetness, England & Wales,", INK, BODY),
            ("137 grid cells. Top: a typical analysis.", INK, BODY),
            ("Bottom: the Detective, after correcting for", INK, BODY),
            ("sticky noise and for testing 137 places.", INK, BODY),
            ("", INK, BODY),
            ("Shuffle the years so no trend is left, and a", INK, BODY),
            ("typical test still marks ~60 of 137 cells.", INK, BODY),
            ("", INK, BODY),
            ("We caught our own data too: at 42 of 88", RED, BODY_B),
            ("places, cloud cover's “trend” is better", RED, BODY_B),
            ("explained by NASA POWER's 2001 satellite", RED, BODY_B),
            ("switch. The app now flags it.", RED, BODY_B),
        ]:
            ax.text(0.45, y, line, color=col, fontsize=16, va="top", **f)
            y -= 0.3
        picture(fig, "map_typical.jpg", (5.85, 3.6, 7.05, 2.38), crop=(0, 225, 800, 500), frame=RED)
        picture(fig, "map_detective.jpg", (5.85, 0.85, 7.05, 2.38), crop=(0, 225, 800, 500))
        save(pdf, fig)
        plt.close(fig)

        # 6. NASA data
        fig, ax = new_slide(6, "NASA data behind it", team)
        title(ax, 6.55, "BUILT ON NASA DATA.", "CHECKABLE BY ANYONE.", size=44)
        bullets(ax, 0.45, 4.7, [
            "NASA POWER: MERRA-2 and CERES, 1981–2025",
            "MODIS Terra + Aqua: greenness, ground temperature",
            "GPM IMERG and GPCP rainfall, GISTEMP, EONET",
            "Partners: ESA CCI soil moisture, Met Office HadCET,\nNOAA indices and stations, ERA5",
            "**Every case links to the exact NASA request, NASA Giovanni,\na CSV, and a notebook that rebuilds the number.",
        ], size=16, gap=0.47)
        picture(fig, "witnesses.jpg", (7.6, 1.0, 5.3, 4.6), crop=(400, 225, 800, 500))
        caption(ax, 7.6, 5.92, "The notebook gets +0.333 °C per decade from", color=INK)
        caption(ax, 7.6, 5.68, "NASA's public API alone, the same as the app.", color=INK)
        save(pdf, fig)
        plt.close(fig)

        # 7. What it can do
        fig, ax = new_slide(7, "What it can do", team)
        title(ax, 6.55, "AN HONEST ANSWER,", "FOR ANYONE, ANYWHERE.", size=44)
        bullets(ax, 0.45, 4.7, [
            "**Lincolnshire: +0.33 °C per decade, proven by 1999,\n1.6× the global rate. 3 of 3 witnesses agree.",
            "**Amazon (Rondônia): rain falling, confirmed by two\nNASA rain records (GPCP, IMERG). Drought months\n~1 a year in the 1980s → ~9 a year in the last decade.",
            "Delhi: the land is greening (both MODIS satellites agree).",
        ], size=16, gap=0.47)
        ax.text(0.45, 1.65, "TRY IT", color=RED, fontsize=20, va="top", **DISPLAY)
        ax.text(0.45, 1.3, SITE, color=BLUE, fontsize=17, va="top", **MONO_B)
        ax.text(0.45, 0.95, CODE, color=MUTED, fontsize=13, va="top", **MONO)
        picture(fig, "amazon_verdict.jpg", (6.85, 1.1, 6.05, 3.78))
        caption(ax, 6.85, 5.3, "Amazon rainfall: −0.53 mm/day per decade, strong evidence", color=BLUE, size=13)
        save(pdf, fig)
        plt.close(fig)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--team", default="[TEAM NAME]")
    p.add_argument("--out", default=str(HERE / "trend_detective_slides.pdf"))
    p.add_argument("--png", help="also write one PNG per slide into this folder")
    a = p.parse_args()
    PNG_DIR = Path(a.png) if a.png else None
    build(a.team, Path(a.out))
    print("wrote", a.out)
