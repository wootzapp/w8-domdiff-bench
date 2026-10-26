#!/usr/bin/env python3
"""Regenerate technical-report figures from its tables.

Requires Matplotlib. From the repository root, run:
    python scripts/generate_evaluation_figures.py

Counts come from the report, and the displayed rates and Wilson intervals
are checked before plotting. Outputs are PNG (embedded in Markdown) and SVG.
"""

from dataclasses import dataclass
from math import sqrt
from pathlib import Path
from statistics import NormalDist
import os
import re
import tempfile

os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "evaluation-matplotlib"))
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from matplotlib.ticker import PercentFormatter

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "assets" / "evaluations"
COLORS = ("#C65316", "#0072B2")
INK = "#243447"
MUTED = "#526273"
CATEGORIES = (
    "Exact text and values", "Control states", "Table entries",
    "Label–value links", "Capture omissions",
)


@dataclass(frozen=True)
class Comparison:
    denominator: int
    counts: tuple[int, int]
    intervals: tuple[tuple[float, float], tuple[float, float]]


def wilson(count, denominator):
    z = NormalDist().inv_cdf(0.975)
    p = count / denominator
    divisor = 1 + z * z / denominator
    center = (p + z * z / (2 * denominator)) / divisor
    half = z * sqrt(p * (1 - p) / denominator + z * z / (4 * denominator**2)) / divisor
    return 100 * (center - half), 100 * (center + half)


def report_data():
    report = (ROOT / "docs" / "technical-report.md").read_text()
    blocks = re.findall(r"(?:^\|.*\n)+", report, re.MULTILINE)
    tables = [
        [[cell.strip() for cell in line.strip().strip("|").split("|")]
         for line in block.splitlines()]
        for block in blocks
    ]
    rate_rows = [row for table in tables
                 if table[0][1] == "Screenshot: count, 95% CI, rate"
                 for row in table[2:]]
    prefixes = (
        "All source-evidence loss categories",
        "URL loss category excluded; all audited criteria retained",
        "Listed access-blocked tasks excluded; all source-evidence loss categories",
        "Listed access-blocked tasks and URL loss category excluded;",
    )
    comparisons = []
    for prefix in prefixes:
        matches = [row for row in rate_rows if row[0].startswith(prefix)]
        if len(matches) != 1:
            raise ValueError(f"Expected one rate row for {prefix!r}")
        counts, denominators, intervals = [], [], []
        for cell in matches[0][1:3]:
            count, denominator, lo, hi, rate = re.fullmatch(
                r"\*\*(\d+)/(\d+)\*\*; 95% CI \*\*([\d.]+)–([\d.]+)%\*\* "
                r"\(rate ([\d.]+)%\)", cell,
            ).groups()
            count, denominator = int(count), int(denominator)
            interval = wilson(count, denominator)
            if (f"{100 * count / denominator:.2f}", *(f"{v:.2f}" for v in interval)) != (rate, lo, hi):
                raise ValueError(f"Rate or Wilson interval disagrees with counts: {cell}")
            counts.append(count)
            denominators.append(denominator)
            intervals.append(interval)
        if denominators[0] != denominators[1]:
            raise ValueError("Representations must use the same denominator")
        comparisons.append(Comparison(denominators[0], tuple(counts), tuple(intervals)))

    category_tables = [table for table in tables
                       if table[0] == ["Category", "Screenshots", "DOM"]]
    if len(category_tables) != 2:
        raise ValueError("Expected full-dataset and filtered category tables")
    categories = []
    for table, all_losses, non_url in zip(category_tables, comparisons[::2], comparisons[1::2]):
        data = {row[0].strip("*"): tuple(int(v.strip("*")) for v in row[1:])
                for row in table[2:]}
        if data["All categories"] != all_losses.counts or data["Non-URL subtotal"] != non_url.counts:
            raise ValueError("Category totals disagree with the rate table")
        for modality in range(2):
            if sum(data[c][modality] for c in CATEGORIES) != non_url.counts[modality]:
                raise ValueError("Non-URL categories do not sum to their subtotal")
            if non_url.counts[modality] + data["URLs"][modality] != all_losses.counts[modality]:
                raise ValueError("URL and non-URL counts do not sum to all losses")
        categories.append(data)

    blocker_section = report.split("## Website access blockers and unavailable content\n", 1)[1]
    blocker_section = blocker_section.split("### Analysis excluding", 1)[0]
    excluded_tasks = set(re.findall(r"^\| (task_\d+) \|", blocker_section, re.MULTILINE))
    full_task_count = int(re.search(r"for (\d+) browser tasks", report)[1])
    if comparisons[0].denominator != comparisons[1].denominator or comparisons[2].denominator != comparisons[3].denominator:
        raise ValueError("Excluding URL losses must retain the cohort denominator")
    return comparisons, categories, full_task_count, len(excluded_tasks)


def configure_style():
    plt.rcParams.update({
        "font.family": "DejaVu Sans", "font.size": 12,
        "text.color": INK, "axes.labelcolor": INK,
        "xtick.color": MUTED, "ytick.color": INK,
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.spines.left": False, "axes.spines.bottom": False,
        "axes.axisbelow": True, "grid.color": "#E3E8ED", "grid.linewidth": 0.8,
        "figure.facecolor": "white", "axes.facecolor": "white",
        "svg.fonttype": "none", "svg.hashsalt": "browser-evidence-evaluations",
    })


def heading(fig, title, subtitle):
    fig.text(0.03, 0.965, title, fontsize=20, weight="bold", va="top")
    fig.text(0.03, 0.902, subtitle, fontsize=11.5, color=MUTED, va="top")


def legend(fig, points=False, excluded=False):
    if points:
        handles = [Line2D([], [], color=color, marker=marker, linestyle="none", markersize=8, label=label)
                   for color, marker, label in zip(COLORS, ("o", "D"), ("Screenshots", "DOM"))]
    else:
        handles = [Patch(facecolor=color, label=label)
                   for color, label in zip(COLORS, ("Screenshots", "DOM"))]
    if excluded:
        handles.append(Patch(facecolor="#F4DACB", edgecolor=COLORS[0], hatch="///", label="Losses excluded"))
    fig.legend(handles=handles, loc="upper left", bbox_to_anchor=(0.023, 0.862),
               frameon=False, ncol=len(handles), fontsize=11.5, handlelength=1.5)


def save(fig, name, title):
    OUTPUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUTPUT / f"{name}.png", dpi=180, bbox_inches="tight", pad_inches=0.18,
                metadata={"Title": title, "Description": "Source: docs/technical-report.md tables"})
    fig.savefig(OUTPUT / f"{name}.svg", bbox_inches="tight", pad_inches=0.18,
                metadata={"Title": title, "Description": "Source: docs/technical-report.md tables",
                          "Date": None, "Creator": "scripts/generate_evaluation_figures.py"})
    plt.close(fig)


def rate_figure(comparisons, task_count, blocked_count):
    title = "Evidence-loss rates across analysis choices"
    fig = plt.figure(figsize=(12.7, 6.6))
    heading(fig, title, f"{task_count} tasks in the full dataset; {task_count - blocked_count} after excluding the listed blocked task IDs")
    legend(fig, points=True)
    grid = fig.add_gridspec(1, 2, width_ratios=(2.4, 1.25), wspace=0.08,
                           left=0.32, right=0.985, top=0.735, bottom=0.19)
    ax = fig.add_subplot(grid[0])
    values = fig.add_subplot(grid[1], sharey=ax)
    centers = (3.45, 2.30, 1.15, 0.0)
    labels = [f"{cohort}\n{kind} · {comparison.denominator} criteria"
              for comparison, cohort, kind in zip(
                  comparisons,
                  ("Full dataset", "Full dataset", "Listed blocked task IDs excluded", "Listed blocked task IDs excluded"),
                  ("All categories", "URL losses excluded", "All categories", "URL losses excluded"))]
    for row, (center, comparison) in enumerate(zip(centers, comparisons)):
        if row % 2 == 0:
            for target in (ax, values):
                target.axhspan(center - 0.48, center + 0.48, color="#F4F6F8", zorder=0)
        for index, (color, marker, offset) in enumerate(zip(COLORS, ("o", "D"), (0.17, -0.17))):
            count = comparison.counts[index]
            rate = 100 * count / comparison.denominator
            lo, hi = comparison.intervals[index]
            ax.errorbar(rate, center + offset, xerr=[[rate - lo], [hi - rate]],
                        fmt=marker, color=color, markersize=7, elinewidth=1.8, capsize=4)
            values.text(0.25 + 0.54 * index, center,
                        f"{count}/{comparison.denominator}\n{rate:.2f}%",
                        color=color, ha="center", va="center", fontsize=12, linespacing=1.5)
    ax.set(yticks=centers, yticklabels=labels, xlim=(0, 30), ylim=(-0.6, 4.0),
           xlabel="Criteria with source-evidence loss (%)")
    ax.set_xticks(range(0, 31, 5))
    ax.xaxis.set_major_formatter(PercentFormatter(xmax=100, decimals=0))
    ax.tick_params(axis="y", length=0, pad=12, labelsize=11)
    ax.grid(axis="x")
    values.set_xlim(0, 1.08)
    values.set_axis_off()
    for index, label in enumerate(("Screenshots", "DOM")):
        values.text(0.25 + 0.54 * index, 4.06, label, ha="center", fontsize=11,
                    weight="bold", color=COLORS[index])
    fig.text(0.03, 0.07, "Points show rates; horizontal bars show 95% Wilson intervals.", fontsize=10.5, color=MUTED)
    fig.text(0.03, 0.035, "URL exclusions retain all criteria. Intervals do not adjust for correlation within tasks.", fontsize=10.5, color=MUTED)
    save(fig, "evidence-loss-rates", title)


def category_figure(comparisons, categories, task_count, blocked_count):
    title = "Non-URL evidence losses by category"
    fig, axes = plt.subplots(1, 2, figsize=(12.7, 6.3), sharex=True, sharey=True)
    heading(fig, title, "The same five categories, with a shared count scale in both panels")
    legend(fig)
    fig.subplots_adjust(left=0.195, right=0.97, bottom=0.18, top=0.69, wspace=0.18)
    centers = list(range(len(CATEGORIES) - 1, -1, -1))
    for ax, data, comparison, tasks, label in zip(
        axes, categories, comparisons[::2], (task_count, task_count - blocked_count),
        ("Full dataset", "Listed blocked task IDs excluded"),
    ):
        for index, (color, offset) in enumerate(zip(COLORS, (0.17, -0.17))):
            counts = [data[c][index] for c in CATEGORIES]
            positions = [y + offset for y in centers]
            ax.barh(positions, counts, height=0.28, color=color, zorder=3)
            for y, count in zip(positions, counts):
                ax.text(count + 0.17, y, str(count), va="center", color=color, fontsize=11, weight="bold")
        ax.set_title(f"{label}\n{tasks} tasks · {comparison.denominator} criteria", loc="left", fontsize=12.5, pad=14)
        ax.set(xlim=(0, 18.5), ylim=(-0.6, 4.6), xlabel="Non-URL evidence losses (count)")
        ax.set_xticks(range(0, 19, 4))
        ax.grid(axis="x")
        ax.tick_params(axis="y", length=0, pad=10, labelsize=11)
    axes[0].set_yticks(centers, CATEGORIES)
    fig.text(0.03, 0.055, "Counts of representation/criterion losses. The URL category is omitted; all criteria remain eligible.",
             fontsize=10.5, color=MUTED)
    save(fig, "non-url-loss-categories", title)


def waterfall_figure(comparisons, blocked_count):
    full, _, retained, non_url = comparisons
    title = "How exclusions change evidence-loss counts"
    fig, ax = plt.subplots(figsize=(12.7, 6.5))
    heading(fig, title, "Exclude the listed blocked task IDs, then exclude the remaining URL-loss findings")
    legend(fig, excluded=True)
    fig.subplots_adjust(left=0.08, right=0.98, top=0.75, bottom=0.25)
    centers = (0, 1.4, 2.8, 4.2, 5.6)
    width = 0.30
    for index, (color, offset) in enumerate(zip(COLORS, (-0.18, 0.18))):
        start, middle, end = full.counts[index], retained.counts[index], non_url.counts[index]
        removed_tasks, removed_urls = start - middle, middle - end
        heights = (start, removed_tasks, middle, removed_urls, end)
        bottoms = (0, middle, 0, end, 0)
        levels = (start, middle, middle, end)
        for step, (center, height, bottom) in enumerate(zip(centers, heights, bottoms)):
            x = center + offset
            is_exclusion = step in (1, 3)
            ax.bar(x, height, width=width, bottom=bottom,
                   color=color if not is_exclusion else "#F4DACB",
                   edgecolor=color, linewidth=0.9,
                   hatch="///" if is_exclusion else None, zorder=3)
            if is_exclusion and height:
                ax.text(x, bottom + height / 2, f"−{height}", ha="center", va="center", fontsize=12,
                        weight="bold", color=color, bbox={"facecolor": "white", "edgecolor": "none", "pad": 2})
            else:
                if is_exclusion:
                    ax.plot([x - width / 2, x + width / 2], [bottom, bottom], color=color, linewidth=2, zorder=4)
                ax.text(x, bottom + height + 3.5, str(height), ha="center", va="bottom", fontsize=12,
                        weight="bold", color=color)
        for step, level in enumerate(levels):
            ax.plot([centers[step] + offset + width / 2, centers[step + 1] + offset - width / 2],
                    [level, level], color=color, alpha=0.5, linewidth=1.2, linestyle=(0, (3, 3)), zorder=2)
    labels = (
        f"Full dataset\n{full.denominator} criteria",
        f"Exclude {blocked_count} listed\nblocked task IDs",
        f"Retained subset\n{retained.denominator} criteria",
        "Exclude remaining\nURL losses",
        f"Non-URL losses\n{non_url.denominator} criteria",
    )
    ax.set(xticks=centers, xticklabels=labels, xlim=(-0.65, 6.25),
           ylim=(0, max(full.counts) * 1.17), ylabel="Source-evidence losses (count)")
    ax.set_yticks(range(0, max(full.counts) + 25, 25))
    ax.tick_params(axis="x", length=0, pad=12, labelsize=11)
    ax.grid(axis="y")
    fig.text(0.03, 0.065,
             f"The task exclusion removes {full.denominator - retained.denominator} criteria; excluding URL losses retains the remaining {retained.denominator} criteria.",
             fontsize=10.5, color=MUTED)
    fig.text(0.03, 0.03, "Bars show loss counts; use the rate comparison above when comparing cohorts with different denominators.",
             fontsize=10.5, color=MUTED)
    save(fig, "exclusion-waterfall", title)


def main():
    comparisons, categories, task_count, blocked_count = report_data()
    configure_style()
    rate_figure(comparisons, task_count, blocked_count)
    category_figure(comparisons, categories, task_count, blocked_count)
    waterfall_figure(comparisons, blocked_count)
    print("Validated report counts, rates, category sums, and Wilson intervals.")
    print(f"Generated three PNG/SVG figure pairs in {OUTPUT.relative_to(ROOT)}.")


if __name__ == "__main__":
    main()
