#!/usr/bin/env python3
"""Plot measured on-minus-off deltas for each pair."""

import argparse
from itertools import groupby
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt

from summarize import pair_deltas, read


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("measurements", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    groups = [(runtime, [delta for _, delta in pairs])
              for runtime, pairs in groupby(pair_deltas(read(args.measurements)), key=lambda row: row[0])]

    figure, axes = plt.subplots(1, 4, sharey=True, figsize=(12, 3.8), layout="constrained")
    figure.suptitle("HTTP adapter overhead · profiling on minus off")
    labels = {"franken": "FrankenPHP", "laravel": "Laravel", "rr": "RoadRunner",
              "swoole": "Swoole", "symfony": "Symfony"}
    styles = [("#05658a", "o", -0.10), ("#a34223", "D", 0.10)]
    for metric, (ax, title) in enumerate(zip(axes, ["CPU/req (%)", "End RSS (MiB)", "p95 (ms)", "p99 (ms)"])):
        ax.set_title(title)
        ax.axvline(0, linewidth=1, color="#74787c")
        ax.grid(axis="x", color="#d8dfe5", linewidth=0.7)
        for row, (_, deltas) in enumerate(groups):
            for delta, (color, marker, offset) in zip(deltas, styles):
                ax.scatter(delta[metric], row + offset, color=color, marker=marker, s=31, zorder=3)
    axes[0].set_yticks(range(len(groups)), [labels[runtime] for runtime, _ in groups])
    axes[0].invert_yaxis()
    handles = [axes[0].scatter([], [], color=color, marker=marker, label=label)
               for (color, marker, _), label in zip(styles, ["Off → on", "On → off"])]
    figure.legend(handles=handles, loc="outside lower center", ncol=2, frameon=False)
    figure.savefig(args.output, dpi=160)


if __name__ == "__main__":
    main()
