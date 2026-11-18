#!/usr/bin/env python3
"""Optional report figure from the complete summary; requires Matplotlib."""
import argparse
import json
import pathlib


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('summary', type=pathlib.Path)
    parser.add_argument('output', type=pathlib.Path)
    args = parser.parse_args()
    summary = json.loads(args.summary.read_text())
    if not summary['complete'] or len(summary['results']) != 18:
        raise ValueError('Only complete 18-run evidence can be plotted')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(11, 4.5))
    keys = [(scenario, hz) for scenario in ('busy-70', 'busy-20', 'mixed-70') for hz in (100, 1000)]
    for index, (scenario, hz) in enumerate(keys):
        rows = [r for r in summary['results'] if r['id'].startswith(f'{scenario}-{hz}hz-')]
        if len(rows) != 3:
            raise ValueError('Missing matrix cell')
        for offset, result in zip((-0.15, 0, 0.15), sorted(rows, key=lambda r: r['id'])):
            ax.scatter(index + offset, max(result['error_pp'].values()), color='#146b99', s=45, zorder=3)
    ax.axhline(5, color='#b73c2f', linestyle='--', label='Per-run acceptance limit: 5 pp')
    ax.set_xticks(range(len(keys)), [f'{s}\n{hz} Hz' for s, hz in keys])
    ax.set_ylabel('Absolute wall-time share error (percentage points)')
    ax.set_ylim(-0.1, 5.5)
    ax.set_title('Known-function wall-time shares: all 18 predeclared runs')
    ax.grid(axis='y', alpha=0.25)
    ax.legend(loc='upper right')
    fig.tight_layout()
    if args.output.suffix == '.svg':
        fig.savefig(args.output, metadata={'Date': None, 'Creator': None})
        args.output.write_text('\n'.join(line.rstrip() for line in args.output.read_text().splitlines()) + '\n')
    else:
        fig.savefig(args.output)
    plt.close(fig)


if __name__ == '__main__':
    main()
