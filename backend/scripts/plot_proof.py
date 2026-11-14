"""Draw the proof-it-works chart (PNG) from data/validation*.json."""
import json
from pathlib import Path
import matplotlib.pyplot as plt

D = Path(__file__).resolve().parents[1] / "data"
OUT = Path(__file__).resolve().parents[2] / "docs" / "images" / "proof_it_works.png"
fa = json.loads((D / "validation.json").read_text())
pw = json.loads((D / "validation_power.json").read_text())

SURF, INK, INK2, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9"
SERIES = [  # fixed categorical order: slot 1 = ours
    ("ours_verdict", "Our verdict (both corrected tests)", "#2a78d6"),
    ("naive_ols_anomalies", "Naive test (ignores autocorrelation)", "#eb6834"),
    ("baseline_raw_ols", "Simple line on raw monthly data", "#1baf7a"),
]
plt.rcParams.update({"font.family": "Helvetica Neue", "font.size": 11, "axes.edgecolor": GRID,
                     "axes.labelcolor": INK2, "xtick.color": MUTED, "ytick.color": MUTED})
fig, axes = plt.subplots(1, 2, figsize=(12, 4.8), facecolor=SURF)
panels = [
    (axes[0], [p for p in fa["phis"]], fa["false_alarm_rate"], "How 'sticky' the natural noise is (lag-1 autocorrelation)",
     "False alarms when there is NO trend", "Ideal: 5%"),
    (axes[1], pw["trends_per_decade"], pw["detection_rate"], "True trend added (units per decade; noise SD = 1)",
     "Real trends caught", None),
]
for ax, x, rates, xlabel, title, ref in panels:
    ax.set_facecolor(SURF)
    ax.grid(axis="y", color=GRID, linewidth=0.8); ax.set_axisbelow(True)
    for s in ["top", "right", "left"]:
        ax.spines[s].set_visible(False)
    if ref:
        ax.axhline(0.05, color=MUTED, linestyle=(0, (4, 3)), linewidth=1.2)
        ax.text(0.6, 0.085, ref, color=INK2, ha="center", va="bottom", fontsize=10)
    for key, label, col in SERIES:
        y = rates[key]
        ax.plot(x, y, color=col, linewidth=2, marker="o", markersize=7,
                markeredgecolor=SURF, markeredgewidth=2, label=label, zorder=3)
    ax.set_ylim(-0.02, 1.05)
    ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0%}")
    ax.set_xlabel(xlabel)
    ax.set_title(title, loc="left", color=INK, fontsize=13, fontweight="bold", pad=10)
    ax.tick_params(length=0)
h, l = axes[0].get_legend_handles_labels()
fig.legend(h, l, loc="lower center", ncol=3, frameon=False, fontsize=10.5, labelcolor=INK2, bbox_to_anchor=(0.5, -0.01))
fig.suptitle("Synthetic test: 45 years of monthly data with a seasonal cycle and natural noise "
             f"({fa['n_sims']} and {pw['n_sims']} simulated series per point)",
             x=0.01, ha="left", color=INK2, fontsize=10.5, y=0.995)
fig.tight_layout(rect=(0, 0.07, 1, 0.97))
fig.savefig(OUT, dpi=200, facecolor=SURF)
print(OUT)
