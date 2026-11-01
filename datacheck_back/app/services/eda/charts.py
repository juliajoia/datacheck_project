"""Gráficos da EDA para o PDF (Matplotlib, backend sem interface). Todos usam dados já calculados pelo motor."""
from __future__ import annotations

import io
from typing import Any, Optional

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

BLUE, PURPLE, GRAY, RED = "#2563EB", "#7C3AED", "#94A3B8", "#DC2626"
plt.rcParams.update({"font.size": 8, "axes.spines.top": False, "axes.spines.right": False, "axes.edgecolor": "#CBD5E1",
                     "axes.labelcolor": "#334155", "xtick.color": "#475569", "ytick.color": "#475569", "figure.dpi": 150})


def _png(fig) -> bytes:
    buf = io.BytesIO()
    fig.tight_layout()
    fig.savefig(buf, format="png")
    plt.close(fig)
    return buf.getvalue()


def histogram(col: str, d: dict[str, Any]) -> bytes:
    fig, ax = plt.subplots(figsize=(4.4, 2.6))
    h = d["histogram"]
    bins = h["bins"]
    if h["discrete"]:
        ax.bar([str(round(b["x0"], 4)).rstrip("0").rstrip(".") for b in bins], [b["count"] for b in bins], color=BLUE)
    else:
        widths = [b["x1"] - b["x0"] for b in bins]
        ax.bar([b["x0"] for b in bins], [b["count"] for b in bins], width=widths, align="edge", color=BLUE, edgecolor="white", linewidth=0.4)
        if d.get("density"):
            ax2 = ax.twinx()
            ax2.plot(d["density"]["x"], d["density"]["y"], color=PURPLE, linewidth=1.4)
            ax2.set_yticks([])
            ax2.spines["right"].set_visible(False)
    ax.set_title(f"Histograma — {col}", fontsize=9, loc="left")
    ax.set_ylabel("Frequência")
    return _png(fig)


def boxplot(col: str, b: dict[str, Any]) -> bytes:
    fig, ax = plt.subplots(figsize=(2.6, 2.6))
    stats = [{"med": b["median"], "q1": b["q1"], "q3": b["q3"], "whislo": b["whisker_low"], "whishi": b["whisker_high"], "fliers": b["outliers"]}]
    bp = ax.bxp(stats, patch_artist=True, showfliers=True, widths=0.5)
    bp["boxes"][0].set(facecolor="#DBEAFE", edgecolor=BLUE)
    bp["medians"][0].set(color=PURPLE, linewidth=1.6)
    for f in bp["fliers"]:
        f.set(marker="o", markersize=3, markerfacecolor=RED, markeredgecolor=RED, alpha=0.7)
    ax.set_xticks([])
    ax.set_title(f"Boxplot — {col}", fontsize=9, loc="left")
    return _png(fig)


def bars(col: str, f: dict[str, Any]) -> bytes:
    items = f["top"][:12]
    fig, ax = plt.subplots(figsize=(4.4, max(1.8, 0.3 * len(items) + 0.9)))
    labels = [(i["value"][:28] + "…") if len(i["value"]) > 28 else i["value"] for i in items]
    y = np.arange(len(items))
    ax.barh(y, [i["pct"] for i in items], color=PURPLE)
    ax.set_yticks(y, labels)
    ax.invert_yaxis()
    for yi, i in zip(y, items):
        ax.text(i["pct"], yi, f" {i['pct']:.1f}% (n={i['count']})".replace(".", ","), va="center", fontsize=7)
    ax.set_xlim(0, max(i["pct"] for i in items) * 1.35)
    ax.set_xlabel("% dos registros válidos")
    ax.set_title(f"Frequência — {col}", fontsize=9, loc="left")
    return _png(fig)


def heatmap(c: dict[str, Any]) -> bytes:
    cols, m = c["columns"], np.array([[np.nan if v is None else v for v in row] for row in c["matrix"]], dtype=float)
    k = len(cols)
    fig, ax = plt.subplots(figsize=(max(3.6, 0.7 * k + 1.8), max(3.2, 0.65 * k + 1.4)))
    im = ax.imshow(m, cmap="coolwarm", vmin=-1, vmax=1)
    ax.set_xticks(range(k), [x[:14] for x in cols], rotation=40, ha="right")
    ax.set_yticks(range(k), [x[:14] for x in cols])
    for i in range(k):
        for j in range(k):
            if not np.isnan(m[i, j]):
                ax.text(j, i, f"{m[i, j]:.2f}".replace(".", ","), ha="center", va="center", fontsize=7, color="white" if abs(m[i, j]) > 0.6 else "#0F172A")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    ax.set_title(f"Correlação de {c['method'].capitalize()}", fontsize=9, loc="left")
    ax.spines[:].set_visible(False)
    return _png(fig)


def scatter(s: dict[str, Any]) -> bytes:
    fig, ax = plt.subplots(figsize=(3.8, 2.9))
    xs, ys = zip(*s["points"]) if s["points"] else ([], [])
    ax.scatter(xs, ys, s=9, color=BLUE, alpha=0.6, edgecolors="none")
    ax.set_xlabel(s["x"][:30])
    ax.set_ylabel(s["y"][:30])
    ax.set_title(f"r = {s['r']:.2f} (n = {s['n']})".replace(".", ","), fontsize=9, loc="left")
    return _png(fig)


def line(title: str, points: list[tuple[str, Optional[float]]], ylabel: str, bar: bool = False) -> bytes:
    fig, ax = plt.subplots(figsize=(6.4, 2.6))
    labels = [p[0] for p in points]
    vals = [np.nan if p[1] is None else p[1] for p in points]
    x = np.arange(len(points))
    (ax.bar if bar else ax.plot)(x, vals, **({"color": BLUE} if bar else {"color": BLUE, "linewidth": 1.8, "marker": "o", "markersize": 3}))
    step = max(1, len(labels) // 10)
    ax.set_xticks(x[::step], labels[::step], rotation=35, ha="right")
    ax.set_ylabel(ylabel)
    ax.set_title(title, fontsize=9, loc="left")
    return _png(fig)
