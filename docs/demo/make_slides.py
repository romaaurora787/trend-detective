"""Build the 7-slide demo deck (docs/demo/trend_detective_slides.pdf) from live-site screenshots.

Usage (from the repo root):
    backend/.venv/bin/python docs/demo/make_slides.py --team "Your Team Name"

The screenshots in docs/demo/img/ were taken from the live site on Sun 15 Nov 2026
(browser at 1280x800); refreshed ~17:30 after the look-freeze. Every number on the slides comes from FINDINGS.md / the API;
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


def edge(ax, elsewhere, here):
    """Full-width strip: what judges will usually see elsewhere vs what we add."""
    from matplotlib.patches import Rectangle
    ax.add_patch(Rectangle((0.45, 0.68), W - 0.9, 0.42, facecolor="#efe2c6", edgecolor=RULE, lw=1))
    ax.text(0.62, 0.89, "ELSEWHERE", color=MUTED, fontsize=10, va="center", **MONO_B)
    ax.text(1.62, 0.89, elsewhere, color=INK, fontsize=13, va="center", **BODY)
    ax.text(6.85, 0.89, "HERE", color=RED, fontsize=10, va="center", **MONO_B)
    ax.text(7.35, 0.89, here, color=INK, fontsize=13, va="center", **BODY_B)


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
        picture(fig, "hero2.jpg", (6.35, 1.55, 6.55, 4.09))
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

        # 3. What sets it apart
        fig, ax = new_slide(3, "What sets it apart", team)
        title(ax, 6.55, "EVERYTHING THE BEST PROJECTS DO.", "THEN SIX THINGS MORE.", size=40)
        ax.text(0.45, 5.2, "IN THE STRONGEST ENTRIES, AND HERE TOO", color=BLUE, fontsize=17, va="top", **DISPLAY)
        y = 4.72
        for t in ["Any place on Earth, 23 NASA variables", "Tests corrected for sticky noise (Hamed–Rao, n_eff)",
                  "False-discovery check on maps", "A world globe: 4,498 land squares",
                  "A second NASA record (GISTEMP, GLDAS)", "Sudden jump vs steady trend", "El Niño removed",
                  "Compare two places, opposite trends", "“Not yet: about N more years of data”",
                  "Plain / Detailed wording, guided first visit", "Cite this (APA, Harvard, BibTeX), CSV, notebook"]:
            ax.text(0.45, y, "✓", color=BLUE, fontsize=14, va="top", family="DejaVu Sans", weight="bold")
            ax.text(0.78, y, t, color=INK, fontsize=14, va="top", **BODY)
            y -= 0.335
        ax.plot([5.55, 5.55], [0.75, 5.25], color=RULE, lw=1)
        ax.text(5.85, 5.2, "WHAT WE ADD, ALL IN ONE PLACE", color=RED, fontsize=17, va="top", **DISPLAY)
        rows = [
            ("INSTRUMENT CHECK FOR EVERY KNOWN DATA SWITCH",
             "2001 sunlight, cloud, heat radiation · 2014 aerosols · deep soil · 1987 rain, re-tested on single-source years.",
             "Worldwide: 42 of 88 proven cloud trends could be the instrument. Elsewhere: early years cut, or one variable."),
            ("FALSE ALARMS MEASURED ON MONTHLY DATA",
             "6% on pure noise (typical test 28–55%), while 99.7% of real 0.3/decade trends are still caught.",
             "Elsewhere: rarely measured, or reached by averaging to years (we check that shortcut too)."),
            ("WITNESSES, COUNTED FOR INDEPENDENCE",
             "Thermometers, rain gauges, GPCP, IMERG, ESA CCI, GLDAS, GRACE, ERA5: each says how independent it is.",
             "Lincolnshire: 4 of 4 agree. Delhi: the thermometers disagree with the model. Elsewhere: one second record."),
            ("FOUR OCEAN CYCLES REMOVED TOGETHER",
             "El Niño, NAO, Indian Ocean Dipole and PDO, plus a careful “hidden change” flag. Elsewhere: usually El Niño only.", None),
            ("THE WORLD ON TRIAL, ON NASA'S OWN DATA",
             "2,013 checks (111 places × 19 variables): 29% of typical claims don't hold.",
             "Luck test on 4,498 squares: a typical test is fooled 22% of the time, ours 7%."),
            ("AROUND 2050: THREE WHAT-IFS, WITH REFUSALS",
             "Our trend drawn on + 7 CMIP6 models + 3 IPCC emission paths. No straight line when the change is one jump.", None),
        ]
        y = 4.78
        for i, (head, l1, l2) in enumerate(rows, 1):
            ax.text(5.85, y + 0.03, f"{i}", color=RED, fontsize=26, va="top", **DISPLAY)
            ax.text(6.3, y, head, color=BLUE, fontsize=14.5, va="top", **DISPLAY)
            ax.text(6.3, y - 0.27, l1, color=INK, fontsize=11.5, va="top", **BODY)
            if l2:
                ax.text(6.3, y - 0.46, l2, color=INK, fontsize=11.5, va="top", **BODY)
            y -= 0.72 if l2 else 0.53
        save(pdf, fig)
        plt.close(fig)

        # 4. The detective part
        fig, ax = new_slide(4, "The detective part", team)
        title(ax, 6.55, "THEN WE TRY TO", "BREAK OUR OWN ANSWER.", size=44)
        bullets(ax, 0.45, 4.7, [
            "**Was it a change of satellite? Every documented\nswitch in NASA's sources is tested, worldwide.",
            "We caught our own data: at 42 of 88 places,\ncloud cover's “trend” is better explained by\nNASA POWER's 2001 GEWEX → CERES switch.",
            "El Niño, NAO, Indian Ocean Dipole and PDO\nremoved together. One year left out at a time.\nEvery start and end year. Sudden jump or trend?",
        ], size=16, gap=0.47)
        picture(fig, "alibi_wisc.jpg", (6.35, 1.25, 6.55, 4.09))
        edge(ax, "The years before 2001 are cut, or one variable is tested at one date.",
             "Every documented switch (4 dates), re-tested, with a worldwide count.")
        caption(ax, 6.35, 5.66, "Central Wisconsin cloud cover: “could be the instrument”", color=BLUE, size=12)
        save(pdf, fig)
        plt.close(fig)

        # 5. Witnesses
        fig, ax = new_slide(5, "Witnesses", team)
        title(ax, 6.55, "INDEPENDENT RECORDS", "MUST AGREE.", size=44)
        bullets(ax, 0.45, 4.7, [
            "Lincolnshire: 4 of 4 other records agree,\n3 of them fully independent (+0.33 °C/decade).",
            "**Delhi: NASA's model shows no proven warming.\nNASA's own station thermometers (GISTEMP)\nshow +0.21 °C per decade.",
            "Rain there: 0 of 3 records back the model.",
            "GRACE satellites, which weigh water, see the\nregion losing ~52 cm of water per decade.",
        ], size=16, gap=0.47)
        picture(fig, "delhi_wit.jpg", (6.35, 1.25, 6.55, 4.09), crop=(0, 15, 400, 265))
        edge(ax, "One second record per variable, and agreement isn't weighed.",
             "Up to 7 kinds of witness, each labelled for how independent it is.")
        caption(ax, 6.35, 5.66, "Each witness says how independent it is, and the headline counts them.", size=11)
        save(pdf, fig)
        plt.close(fig)

        # 6. The world on trial
        fig, ax = new_slide(6, "The world on trial", team)
        title(ax, 6.55, "THE SAME TEST,", "4,498 LAND SQUARES.", size=44)
        bullets(ax, 0.45, 4.7, [
            "Air temperature, 1981–2025, every 2° land square.",
            "A typical test calls 84% of squares “changing”.\nOur test proves 72%.",
            "**The luck test: shuffle each square's years so no\ntrend can exist. A typical test still “finds” one in\n22% of squares. Ours: 7%.",
            "England & Wales soil: 89 cells look like change\non a typical map. 0 survive our checks.",
        ], size=16, gap=0.47)
        picture(fig, "globe_luck.jpg", (6.35, 1.3, 6.55, 3.77), crop=(0, 40, 800, 500))
        edge(ax, "A trend map, rarely showing how often its method is fooled.",
             "Typical vs ours on every square, and the luck test shown: 22% vs 7%.")
        save(pdf, fig)
        plt.close(fig)

        # 7. Around 2050 + try it
        fig, ax = new_slide(7, "Around 2050", team)
        title(ax, 6.55, "WHAT IF IT KEEPS GOING?", "THREE WHAT-IFS, NOT A FORECAST.", size=40)
        bullets(ax, 0.45, 4.8, [
            "Today's proven trend drawn on (refused when the\nchange is one sudden jump).",
            "7 CMIP6 high-resolution climate models.",
            "**Three IPCC emission paths. Lincolnshire around\n2050: +0.67 °C with big cuts, +1.75 °C with very\nhigh emissions. The choice makes 1.09 °C.",
        ], size=16, gap=0.47)
        ax.text(0.45, 2.3, "TRY IT", color=RED, fontsize=20, va="top", **DISPLAY)
        ax.text(0.45, 1.95, SITE, color=BLUE, fontsize=13.5, va="top", **MONO_B)
        ax.text(0.45, 1.62, CODE, color=MUTED, fontsize=13, va="top", **MONO)
        edge(ax, "No outlook, or a single projection.",
             "Three what-ifs side by side, and a refusal when a line would mislead.")
        picture(fig, "y2050.jpg", (6.35, 1.6, 6.55, 3.28), crop=(0, 20, 800, 420))
        save(pdf, fig)
        plt.close(fig)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--team", default="Paani Ke Batashe")
    p.add_argument("--out", default=str(HERE / "trend_detective_slides.pdf"))
    p.add_argument("--png", help="also write one PNG per slide into this folder")
    a = p.parse_args()
    PNG_DIR = Path(a.png) if a.png else None
    build(a.team, Path(a.out))
    print("wrote", a.out)
