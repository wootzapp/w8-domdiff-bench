#!/usr/bin/env python3
"""Regenerate Figures 2–3 from the missed-evidence report's saved statistics.

Install plotting dependencies with: python -m pip install -e '.[report]'
Run generate_missed_evidence_report.py first. No model or API calls are made.
"""

import argparse
import json
import math
from pathlib import Path

import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import PercentFormatter


REPOSITORY = Path(__file__).resolve().parent.parent
COLORS = {'screenshot': '#C16B52', 'dom': '#3F659F'}
LABELS = {'screenshot': 'Screenshots', 'dom': 'DOM-diff Optimized'}
INK = '#202D40'
MUTED = '#687489'
GRID = '#E8ECF2'


def save_figure(fig, output):
    fig.savefig(output, bbox_inches='tight', metadata={'Date': None})
    plt.close(fig)


def heading(fig, title, subtitle):
    fig.text(0.055, 0.94, 'W8-DOMDIFF-BENCH  /  EVIDENCE PRESERVATION',
             color=MUTED, fontsize=9, weight='bold')
    fig.text(0.055, 0.865, title, fontsize=24, weight='bold', color=INK)
    fig.text(0.055, 0.805, subtitle, fontsize=11, color=MUTED)


def footer(fig, text):
    fig.add_artist(Line2D([0.055, 0.95], [0.125, 0.125], transform=fig.transFigure,
                          color=GRID, linewidth=1))
    fig.text(0.055, 0.072, text, fontsize=9, color=MUTED)


def style_axis(ax):
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(axis='both', length=0, labelcolor=MUTED, labelsize=10, pad=10)
    ax.set_axisbelow(True)
    ax.grid(axis='x', color=GRID, linewidth=0.9)


def generate_figures(summary, output_dir):
    output_dir.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({
        'font.family': ['Lato', 'DejaVu Sans'], 'font.size': 11,
        'figure.facecolor': 'white', 'axes.facecolor': 'white',
        'text.color': INK, 'axes.labelcolor': MUTED,
        'svg.fonttype': 'none', 'svg.hashsalt': 'w8-domdiff-bench',
    })
    statistics = summary['statistics']
    total = summary['counts']['audited_criteria']
    tasks = summary['counts']['audited_tasks']
    # Keep the public figure focused on source preservation. Counts and intervals
    # sit in a separate aligned column so labels never collide with the whiskers.
    stat = statistics['evidence_loss']
    if stat['denominator'] != total:
        raise ValueError('Figure statistics must share the audited denominator')
    fig = plt.figure(figsize=(12, 4.8))
    heading(fig, 'Source-evidence loss', f'{tasks} browser tasks  ·  {total} audited criteria  ·  Lower is better')
    ax = fig.add_axes([0.255, 0.29, 0.425, 0.365])
    style_axis(ax)
    maximum = max(stat[mode]['ci95'][1] * 100 for mode in COLORS)
    ax.set_xlim(0, max(30, math.ceil(maximum / 5) * 5))
    ax.set_xticks([i * ax.get_xlim()[1] / 3 for i in range(4)])
    ax.xaxis.set_major_formatter(PercentFormatter(xmax=100, decimals=0))
    ax.set_ylim(-0.55, 1.55)
    ax.set_yticks([])
    ax.set_xlabel('Share of audited criteria with source loss', fontsize=10, labelpad=14)
    fig.text(0.755, 0.70, 'CRITERIA WITH A GAP', fontsize=9, color=MUTED, weight='bold')
    for y, mode in [(1, 'screenshot'), (0, 'dom')]:
        item = stat[mode]
        rate = 100 * item['rate']
        lower, upper = [100 * bound for bound in item['ci95']]
        ax.barh(y, rate, height=0.20, color=COLORS[mode], alpha=0.20, zorder=2)
        ax.errorbar(rate, y, xerr=[[rate - lower], [upper - rate]], fmt='o',
                    color=COLORS[mode], capsize=5, markersize=8, linewidth=2, zorder=3)
        row_y = fig.transFigure.inverted().transform(ax.transData.transform((0, y)))[1]
        fig.text(0.055, row_y, LABELS[mode], va='center', fontsize=12, weight='bold')
        fig.text(0.755, row_y + 0.004, f'{item["count"]} / {total}', fontsize=25,
                 weight='bold', color=COLORS[mode], va='baseline')
        fig.text(0.755, row_y - 0.049, f'95% CI  {lower:.2f}–{upper:.2f}%', fontsize=11)
    footer(fig, 'Whiskers: 95% Wilson intervals. Automated audits; intervals do not adjust for within-task correlation or audit error.')
    rate_path = output_dir / 'evidence-rates.svg'
    save_figure(fig, rate_path)

    categories = summary['category_counts']
    for mode in COLORS:
        if sum(item[mode] for item in categories.values()) != statistics['evidence_loss'][mode]['count']:
            raise ValueError(f'Category counts do not sum to the {mode} loss count')
    fig = plt.figure(figsize=(12, 6.3))
    heading(fig, 'Where evidence is lost',
            f'Primary evidence categories  ·  {stat["screenshot"]["count"]} screenshot losses  ·  {stat["dom"]["count"]} DOM losses')
    ax = fig.add_axes([0.255, 0.255, 0.425, 0.445])
    style_axis(ax)
    ax.set_ylim(len(categories) - 0.5, -0.5)
    ax.set_yticks([])
    maximum = max(item[mode] for item in categories.values() for mode in COLORS)
    axis_max = max(5, math.ceil(maximum / 20) * 20)
    ax.set_xlim(0, axis_max)
    ax.set_xticks([round(i * axis_max / 4) for i in range(5)])
    ax.set_xlabel('Criteria with source-evidence loss', fontsize=10, labelpad=14)
    for i, category in enumerate(categories):
        row_y = fig.transFigure.inverted().transform(ax.transData.transform((0, i)))[1]
        fig.text(0.055, row_y, category, va='center', fontsize=11)
        for mode, column in [('screenshot', 0.785), ('dom', 0.92)]:
            fig.text(column, row_y, str(categories[category][mode]), ha='center', va='center',
                     fontsize=15, color=COLORS[mode], weight='bold')
    for mode, column, label in [('screenshot', 0.785, 'Screenshots'),
                                ('dom', 0.92, 'DOM-diff\nOptimized')]:
        fig.text(column, 0.727, label, color=COLORS[mode], ha='center', va='bottom',
                 fontsize=11, weight='bold', linespacing=1.3)
    for offset, mode in [(-0.18, 'screenshot'), (0.18, 'dom')]:
        positions = [i + offset for i in range(len(categories))]
        values = [item[mode] for item in categories.values()]
        ax.barh(positions, values, height=0.22, color=COLORS[mode], zorder=3)
    footer(fig, 'One primary category per representation/criterion loss. Categories interpret saved automated audits. Lower is better.')
    category_path = output_dir / 'evidence-categories.svg'
    save_figure(fig, category_path)
    return [rate_path, category_path]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--statistics', type=Path, default=REPOSITORY / 'docs' / 'benchmark_statistics.json')
    parser.add_argument('--output-dir', type=Path, default=REPOSITORY / 'docs' / 'figures')
    args = parser.parse_args()
    summary = json.loads(args.statistics.read_text(encoding='utf-8'))
    for path in generate_figures(summary, args.output_dir):
        print(path)


if __name__ == '__main__':
    main()
