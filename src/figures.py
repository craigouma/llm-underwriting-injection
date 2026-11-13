"""Paper figures from the cached decision tables. Palette: first four slots of the validated reference
palette in fixed order (blue, orange, aqua, yellow), validated for adjacent pairs in light mode; the
contrast warning on aqua and yellow is covered by the legend, direct labels and the tables in the paper.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src import analysis as an

FIGURES = Path("paper/figures")
ARM_COLORS = {"A": "#2a78d6", "A_def": "#eb6834", "B": "#1baf7a", "C": "#eda100"}
ARM_LABELS = {"A": "A: LLM decides", "A_def": "A + prompt defense", "B": "B: LLM extracts", "C": "C: B + checks",
              "B_oracle": "B, oracle extractor", "C_oracle": "C, oracle extractor"}
ORACLE = "#8a8987"
INK, INK2, GRID, NAVY = "#0b0b0b", "#52514e", "#e4e3df", "#1a3a5c"
CAT_LABELS = {"instruction_override": "Override", "hidden_instruction": "Hidden\nnote", "fake_authority": "Fake\nauthority",
              "delimiter_format": "Delimiter", "extraction_manipulation": "Extraction"}
MODEL_LABELS = {"Qwen/Qwen2.5-1.5B-Instruct": "Qwen2.5 1.5B", "microsoft/Phi-4-mini-instruct": "Phi-4-mini 3.8B",
                "allenai/Olmo-3-7B-Instruct": "Olmo-3 7B"}
MODEL_ORDER = list(MODEL_LABELS)


def style() -> None:
    plt.rcParams.update({
        "font.family": "serif", "font.serif": ["cmr10"], "mathtext.fontset": "cm", "axes.formatter.use_mathtext": True,
        "font.size": 9, "axes.titlesize": 10, "axes.labelsize": 9, "xtick.labelsize": 8, "ytick.labelsize": 8,
        "text.color": INK, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
        "axes.edgecolor": GRID, "axes.linewidth": 0.8, "axes.spines.top": False, "axes.spines.right": False,
        "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "grid.linestyle": "-", "axes.axisbelow": True,
        "legend.frameon": False, "figure.dpi": 150, "savefig.bbox": "tight", "pdf.fonttype": 42})


def models_in(df: pd.DataFrame) -> list[str]:
    present = set(df["model"])
    return [m for m in MODEL_ORDER if m in present]


def pct(ax, axis: str = "y") -> None:
    fmt = matplotlib.ticker.PercentFormatter(1.0, decimals=0)
    (ax.yaxis if axis == "y" else ax.xaxis).set_major_formatter(fmt)


def save(fig, name: str) -> Path:
    FIGURES.mkdir(parents=True, exist_ok=True)
    path = FIGURES / f"{name}.pdf"
    fig.savefig(path)
    plt.close(fig)
    return path


def fig_asr_by_category(df: pd.DataFrame) -> Path:
    t = an.asr(df, ["category"])
    floor = an.clean_approve_rate(df).set_index(["model", "arm"])["rate"]
    models = models_in(t)
    fig, axes = plt.subplots(1, len(models), figsize=(3.4 * len(models), 3.2), sharey=True, squeeze=False)
    arms = ["A", "A_def", "B", "C"]
    width, gap = 0.17, 0.02
    for ax, model in zip(axes[0], models):
        if floor[(model, "A")] > 0.02:
            ax.axhline(floor[(model, "A")], color=ARM_COLORS["A"], lw=0.9, ls=(0, (4, 3)), zorder=2)
        for j, arm in enumerate(arms):
            sub = t[(t["model"] == model) & (t["arm"] == arm)].set_index("category").reindex(an.CATEGORIES)
            x = np.arange(len(an.CATEGORIES)) + (j - 1.5) * (width + gap)
            err = [(sub["rate"] - sub["lo"]).clip(lower=0), (sub["hi"] - sub["rate"]).clip(lower=0)]
            ax.bar(x, sub["rate"], width, color=ARM_COLORS[arm], label=ARM_LABELS[arm], zorder=3)
            ax.errorbar(x, sub["rate"], yerr=err, fmt="none", ecolor=INK2, elinewidth=0.8, capsize=0, zorder=4)
        ax.set_xticks(range(len(an.CATEGORIES)), [CAT_LABELS[c] for c in an.CATEGORIES], rotation=0, fontsize=7)
        ax.set_title(MODEL_LABELS[model], color=NAVY)
        ax.set_ylim(0, 1.04)
        ax.set_yticks([0, 0.2, 0.4, 0.6, 0.8, 1.0])
        pct(ax)
        ax.grid(axis="x", visible=False)
    axes[0][0].set_ylabel("Attack success rate (Wilson 95% CI)")
    handles, labels = axes[0][0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=4, bbox_to_anchor=(0.5, -0.08))
    return save(fig, "fig_asr_by_category")


def fig_plausibility(df: pd.DataFrame) -> Path:
    att = an.attacked_targets(df)
    att = att[att["plausibility"].notna() & att["arm"].isin(["B", "C", "B_oracle"])].copy()
    att["bin"] = pd.cut(att["plausibility"], [0, 0.25, 0.5, 0.75, 1.0], include_lowest=True)
    models = models_in(att)
    fig, axes = plt.subplots(1, len(models), figsize=(3.4 * len(models), 3.0), sharey=True, squeeze=False)
    for ax, model in zip(axes[0], models):
        for arm, color, ls in (("B", ARM_COLORS["B"], "-"), ("C", ARM_COLORS["C"], "-"), ("B_oracle", ORACLE, "--")):
            g = att[(att["model"] == model) & (att["arm"] == arm)].groupby("bin", observed=True)["success"].agg(k="sum", n="size").reset_index()
            g = an.add_ci(g)
            x = [iv.mid for iv in g["bin"]]
            ax.plot(x, g["rate"], color=color, lw=2, ls=ls, marker="o", ms=5, mec="white", mew=1.5, label=ARM_LABELS[arm], zorder=3)
            ax.vlines(x, g["lo"], g["hi"], color=color, lw=0.9, alpha=0.8, zorder=2)
        ax.set_title(MODEL_LABELS[model], color=NAVY)
        ax.set_xlabel("Plausibility of the falsified value")
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        pct(ax)
    axes[0][0].set_ylabel("Attack success rate")
    handles, labels = axes[0][0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=3, bbox_to_anchor=(0.5, -0.1))
    return save(fig, "fig_plausibility")


def fig_tradeoff(df: pd.DataFrame) -> Path:
    LABELS = {"none": "no checks", "range": "+ range", "range+currency": "+ currency", "range+currency+xdoc": "+ cross-document",
              "range+currency+xdoc+segment": "+ band"}
    t = an.cumulative_check_tradeoff(df)
    models = models_in(t)
    fig, axes = plt.subplots(1, len(models), figsize=(3.4 * len(models), 3.0), sharey=True, squeeze=False)
    for ax, model in zip(axes[0], models):
        g = t[t["model"] == model].reset_index(drop=True)
        ax.plot(g["clean_review_rate"], g["asr_extraction"], color=ARM_COLORS["C"], lw=2, marker="o", ms=5, mec="white", mew=1.5, zorder=3)
        for i, r in g.iterrows():
            ax.annotate(LABELS.get(r["checks"], ""), (r["clean_review_rate"], r["asr_extraction"]), xytext=(6, 6 if i % 2 == 0 else -12),
                        textcoords="offset points", fontsize=7, color=INK2)
        ax.set_title(MODEL_LABELS[model], color=NAVY)
        ax.set_xlabel("Review rate on clean inputs")
        pct(ax, "x")
        pct(ax)
        ax.set_yticks([0, 0.05, 0.10, 0.15, 0.20])
        ax.set_ylim(0, 0.215)
    axes[0][0].set_ylabel("ASR, extraction manipulation")
    return save(fig, "fig_tradeoff")


def fig_clean_utility(df: pd.DataFrame) -> Path:
    u = an.clean_utility(df)
    u = u[u["arm"].isin(["A", "A_def", "B", "C"])]
    models = models_in(u)
    panels = [("auroc", "Decision AUROC"), ("refer_share", "Share referred to a human"), ("agree_reference", "Agreement with the tabular scorecard")]
    fig, axes = plt.subplots(1, 3, figsize=(10.2, 3.0), squeeze=False)
    for ax, (col, title) in zip(axes[0], panels):
        for j, arm in enumerate(["A", "A_def", "B", "C"]):
            vals = [u[(u["model"] == m) & (u["arm"] == arm)][col].iloc[0] for m in models]
            ax.bar(np.arange(len(models)) + (j - 1.5) * 0.19, vals, 0.17, color=ARM_COLORS[arm], label=ARM_LABELS[arm], zorder=3)
        ax.set_xticks(range(len(models)), [MODEL_LABELS[m] for m in models], fontsize=7)
        ax.set_title(title, color=NAVY)
        ax.set_ylim(0, 1)
        ax.grid(axis="x", visible=False)
    handles, labels = axes[0][0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=4, bbox_to_anchor=(0.5, -0.08))
    return save(fig, "fig_clean_utility")


def fig_variants(df: pd.DataFrame) -> Path:
    t = an.asr(df[df["category"].isin(["extraction_manipulation"])], ["attack_id"])
    ids = [f"EM{i}" for i in range(1, 15)]
    models = models_in(t)
    fig, axes = plt.subplots(1, len(models), figsize=(3.4 * len(models), 4.2), sharey=True, squeeze=False)
    for ax, model in zip(axes[0], models):
        y = np.arange(len(ids))[::-1]
        for arm, color, marker, fill in (("B_oracle", ORACLE, "o", False), ("B", ARM_COLORS["B"], "o", True), ("C", ARM_COLORS["C"], "o", True)):
            sub = t[(t["model"] == model) & (t["arm"] == arm)].set_index("attack_id").reindex(ids)
            ax.scatter(sub["rate"], y, s=34, marker=marker, facecolor=color if fill else "white", edgecolor=color if not fill else "white",
                       linewidth=1.4 if not fill else 1.2, label=ARM_LABELS[arm], zorder=3)
        ax.set_yticks(y, ids)
        ax.set_title(MODEL_LABELS[model], color=NAVY)
        ax.set_xlim(0, 1)
        pct(ax, "x")
        ax.set_xlabel("Attack success rate")
        ax.grid(axis="y", visible=False)
    handles, labels = axes[0][0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=3, bbox_to_anchor=(0.5, -0.04))
    return save(fig, "fig_variants")


def make_all(df: pd.DataFrame) -> list[Path]:
    style()
    return [fig_asr_by_category(df), fig_plausibility(df), fig_tradeoff(df), fig_clean_utility(df), fig_variants(df)]
