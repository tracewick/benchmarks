#!/usr/bin/env python3
"""Render saved report data only; no benchmarks, network calls or revised measurements."""
import argparse
import csv
import hashlib
import io
import json
import math
import os
import pathlib
import re
import statistics
import tempfile

os.environ.setdefault('MPLCONFIGDIR', str(pathlib.Path(tempfile.gettempdir()) / 'tracewick-report-mpl'))
os.environ.setdefault('XDG_CACHE_HOME', str(pathlib.Path(tempfile.gettempdir()) / 'tracewick-report-cache'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = pathlib.Path(__file__).resolve().parents[1]
REPORTS = ROOT / 'reports'
BLUE, ORANGE, GREY, RED = '#176b9a', '#db8b2b', '#768496', '#b43f35'
START, END = '<!-- saved-results-plot -->', '<!-- /saved-results-plot -->'
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10, 'axes.titlesize': 11,
                     'axes.spines.top': False, 'axes.spines.right': False,
                     'axes.labelcolor': '#243746', 'text.color': '#243746',
                     'svg.fonttype': 'none', 'figure.facecolor': 'white'})


def strip_block(text):
    return re.sub(r'\n*' + re.escape(START) + r'.*?' + re.escape(END) + r'\n*', '\n', text, flags=re.S).rstrip() + '\n'


def read_json(path, sources):
    sources.add(path)
    return json.loads(path.read_text())


def read_meta(directory, sources):
    path = directory / 'meta.txt'
    if not path.exists():
        return {}
    sources.add(path)
    return dict(line.split('=', 1) for line in path.read_text().splitlines() if '=' in line)


def read_csv(path, sources):
    sources.add(path)
    with path.open() as stream:
        rows = [{k: float(v) for k, v in row.items()} for row in csv.DictReader(stream)]
    if not rows or any(b['ts_unix'] < a['ts_unix'] for a, b in zip(rows, rows[1:])):
        raise ValueError(f'Empty or nonchronological CSV: {path}')
    return rows


def metrics(path, sources):
    raw = read_json(path, sources)['metrics']
    return {key: value.get('values', value) for key, value in raw.items()}


def failure_rate(k6):
    # k6 http_req_failed's passes/fails are predicate counters, not failed/successful HTTP counts.
    value = k6['http_req_failed'].get('value', k6['http_req_failed'].get('rate'))
    if value is None:
        raise ValueError('Missing explicit HTTP failure rate')
    return value * 100


def series(rows, key, divisor=1, origin=None, time_divisor=1):
    origin = rows[0]['ts_unix'] if origin is None else origin
    gaps = [b['ts_unix'] - a['ts_unix'] for a, b in zip(rows, rows[1:]) if b['ts_unix'] > a['ts_unix']]
    usual = statistics.median(gaps) if gaps else float('inf')
    x, y = [], []
    for i, row in enumerate(rows):
        if i and row['ts_unix'] - rows[i - 1]['ts_unix'] > 3 * usual:
            x.append(float('nan')); y.append(float('nan'))
        x.append((row['ts_unix'] - origin) / time_divisor)
        y.append(row[key] / divisor)
    return x, y


def line(axis, rows, key, label, color, divisor=1, origin=None, time_divisor=1):
    x, y = series(rows, key, divisor, origin, time_divisor)
    axis.plot(x, y, label=label, color=color, linewidth=1.15)
    axis.grid(alpha=.2)


def latency(axis, arms):
    labels = ['Median', 'p95', 'p99']
    width = .7 / len(arms)
    for i, (label, k6, color) in enumerate(arms):
        values = [k6['http_req_duration'][k] for k in ('med', 'p(95)', 'p(99)')]
        bars = axis.bar([n + (i - (len(arms) - 1) / 2) * width for n in range(3)], values, width,
                        color=color, label=label)
        axis.bar_label(bars, fmt='%.2f', fontsize=8, padding=3)
    axis.set_xticks(range(3), labels)
    axis.set_ylabel('HTTP duration (ms)')
    axis.set_title('Recorded k6 latency quantiles')
    axis.margins(y=.35)
    axis.grid(axis='y', alpha=.2)
    axis.legend(fontsize=8)


def runtime_name(stem):
    if '-rr-' in stem: return 'RoadRunner'
    if '-swoole-' in stem: return 'Swoole'
    return 'FPM'


def historical_footnote():
    return 'Historical run, before the 2026-11-17 flush fix. Host/configuration-specific; see original report pins.'


def finish(fig, output, title, footnote, zero_baseline=True):
    # Fix the zero baseline only after every series has contributed to autoscaling.
    for axis in fig.axes:
        if zero_baseline:
            axis.set_ylim(bottom=0)
        for trace in axis.lines:
            finite = [float(v) for v in trace.get_ydata() if math.isfinite(float(v))]
            if finite and max(finite) > axis.get_ylim()[1] + 1e-9:
                raise ValueError('A saved series would be clipped by the plot scale')
    fig.suptitle(title, fontsize=14, fontweight='semibold', y=.99)
    fig.text(.5, .012, footnote, ha='center', fontsize=8, color='#586a78')
    fig.tight_layout(rect=(0, .055, 1, .955))
    with matplotlib.rc_context({'svg.hashsalt': str(output.relative_to(ROOT))}):
        buffer = io.StringIO()
        fig.savefig(buffer, format='svg', metadata={'Date': None, 'Creator': None})
    plt.close(fig)
    return '\n'.join(line.rstrip() for line in buffer.getvalue().splitlines()) + '\n'


def overhead(directory, sources):
    fig, axes = plt.subplots(2, 2, figsize=(11.5, 7))
    k = [metrics(directory / (arm + '-k6.json'), sources) for arm in ('baseline', 'on')]
    latency(axes[0, 0], [('Off', k[0], GREY), ('On', k[1], BLUE)])
    stats = [read_csv(directory / (arm + '-fpm-stats.csv'), sources) for arm in ('baseline', 'on')]
    for rows, label, color in zip(stats, ('Off', 'On'), (GREY, BLUE)):
        line(axes[0, 1], rows, 'cpu_percent', label, color)
        line(axes[1, 0], rows, 'mem_usage_bytes', label, color, 2**20)
    axes[0, 1].set(title='Container CPU — separate A/B windows', ylabel='CPU % (100% = one core)', xlabel='Seconds since each arm began')
    axes[1, 0].set(title='Container memory usage — not process RSS', ylabel='MiB', xlabel='Seconds since each arm began')
    axes[0, 1].legend(); axes[1, 0].legend()
    rates = [item['http_reqs']['rate'] for item in k]
    bars = axes[1, 1].bar(['Off', 'On'], rates, color=[GREY, BLUE], width=.5)
    axes[1, 1].bar_label(bars, fmt='%.3f', padding=4)
    axes[1, 1].set(title='Achieved request rate', ylabel='Requests / second')
    axes[1, 1].set_ylim(0, max(rates) * 1.25)
    axes[1, 1].text(.5, .9, f'HTTP failures: {failure_rate(k[0]):g}% / {failure_rate(k[1]):g}%',
                       transform=axes[1, 1].transAxes, ha='center', fontsize=9)
    axes[1, 1].grid(axis='y', alpha=.2)
    return fig, {'latency_ms': [{name: item['http_req_duration'][name] for name in ('med', 'p(95)', 'p(99)')} for item in k],
                 'achieved_rps': rates, 'http_failed_percent': [failure_rate(item) for item in k]}


def queue(directory, sources, kind):
    rows = read_csv(directory / 'spool-timeseries.csv', sources)
    health_path = directory / 'health.json'
    sources.add(health_path)
    health_valid = True
    try:
        health = json.loads(health_path.read_text())
    except (ValueError, OSError):
        # Some archived health captures contain build output. Do not invent a limit or data.
        health = {}
        health_valid = False
    k6 = metrics(directory / 'k6.json', sources)
    meta = read_meta(directory, sources)
    fig, axes = plt.subplots(2, 2, figsize=(11.5, 7))
    line(axes[0, 0], rows, 'files', 'Saved spool-file count', BLUE)
    if any(row.get('claimed_or_tmp', 0) for row in rows):
        line(axes[0, 0], rows, 'claimed_or_tmp', 'Claim/temp entries (separate column)', ORANGE)
    limit = health.get('spool_max_files')
    if limit is not None:
        axes[0, 0].axhline(limit, color=RED, linestyle='--', label=f'Soft admission setting: {limit}')
    axes[0, 0].set(title='Recorded queue counts', xlabel='Seconds since first observation', ylabel='Files / entries')
    axes[0, 0].legend(fontsize=8)
    line(axes[0, 1], rows, 'bytes', 'Saved spool bytes', BLUE, 2**20)
    axes[0, 1].set(title='Recorded spool size', xlabel='Seconds since first observation', ylabel='MiB')
    latency(axes[1, 0], [('Run', k6, BLUE)])
    axes[1, 1].axis('off')
    detail = [f"Achieved: {k6['http_reqs']['rate']:.3f} requests/s", f'HTTP failures: {failure_rate(k6):g}%',
              f"Peak saved file count: {max(r['files'] for r in rows):g}",
              f"Last saved file count: {rows[-1]['files']:g}"]
    derived = {'achieved_rps': k6['http_reqs']['rate'], 'http_failed_percent': failure_rate(k6),
               'max_files': max(row['files'] for row in rows), 'last_files': rows[-1]['files'], 'soft_setting': limit}
    if not health_valid:
        detail += ['Soft limit: not decoded from archived health capture']
        derived['health_note'] = 'Archived capture is not JSON; no soft threshold inferred'
    if 'RATE' in meta: detail.insert(0, f"Requested: {meta['RATE']} requests/s")
    catchup = directory / 'drain-catchup.txt'
    if catchup.exists():
        sources.add(catchup)
        seconds = int(re.search(r'drain_catchup_sec=(\d+)', catchup.read_text())[1])
        derived['catchup_seconds'] = seconds
        detail += ['', f'Catch-up after reader restart: {seconds} s', '(separately recorded scalar; not a fitted curve)']
    toxic = directory / 'toxic.json'
    if toxic.exists():
        spec = read_json(toxic, sources)
        attributes = spec.get('attributes', {})
        detail += ['', f"Injected latency: {attributes.get('latency', 'see toxic.json')} ms"]
    detail += ['', 'Lines connect saved samples only.', 'Gaps >3x typical interval are left blank.']
    axes[1, 1].text(.05, .95, '\n'.join(detail), va='top', linespacing=1.6, fontsize=10)
    return fig, derived


def soak(directory, sources):
    paths = sorted(directory.glob('app-*-stats.csv'))
    if len(paths) != 2: raise ValueError(f'Expected application and reader stats: {directory}')
    series_data = [(p.stem.removesuffix('-stats'), read_csv(p, sources)) for p in paths]
    origin = min(rows[0]['ts_unix'] for _, rows in series_data)
    fig, axes = plt.subplots(2, 1, figsize=(11.5, 7), sharex=True)
    derived = {}
    for (label, rows), color in zip(series_data, (ORANGE, BLUE)):
        line(axes[0], rows, 'mem_usage_bytes', label, color, 2**20, origin, 3600)
        line(axes[1], rows, 'cpu_percent', label, color, 1, origin, 3600)
        derived[label] = {'samples': len(rows), 'hours': (rows[-1]['ts_unix']-rows[0]['ts_unix'])/3600,
                          'memory_first_mib': rows[0]['mem_usage_bytes']/2**20,
                          'memory_last_mib': rows[-1]['mem_usage_bytes']/2**20}
    axes[0].set(title='Container memory usage (all saved observations)', ylabel='MiB')
    axes[1].set(title='Container CPU (no smoothing)', ylabel='CPU % (100% = one core)', xlabel='Hours since first observation')
    for ax in axes: ax.legend()
    return fig, derived


def weights(directory, sources):
    rows = read_json(directory / 'summary.json', sources)
    fig, ax = plt.subplots(figsize=(11, 4.8))
    stages = ['Native', 'Profile', 'Spool', 'PHP pprof', 'Go pprof', 'Pyroscope']
    values = []
    colors = [GREY, '#5293b3', '#70a98a', '#dfa850', BLUE, '#495b87']
    for row in rows:
        path = directory / row['captures_file']; sources.add(path)
        captures = [json.loads(line) for line in path.read_text().splitlines()]
        periods = {c['period_ns'] for c in captures}
        if len(periods) != 1: raise ValueError('Mixed periods need a different chart')
        period = periods.pop()
        values.append([row['native_events'], sum(c['profile_events'] for c in captures), row['spool_events'],
                       row['php_pprof_ns']/period, row['agent_pprof_ns']/period, row['pyroscope_ns']/period])
    for stage, (name, color) in enumerate(zip(stages, colors)):
        ax.bar([i + (stage - 2.5) * .12 for i in range(len(rows))], [v[stage] for v in values],
               width=.11, color=color, label=name)
    for i, v in enumerate(values):
        text = f'{v[0]:g} at every stage' if len(set(v)) == 1 else f'Range: {min(v):g}–{max(v):g}'
        ax.text(i, max(v) + 6, text, ha='center', fontsize=10)
    ax.set_xticks(range(len(rows)), [r['runtime'].upper() for r in rows])
    ax.set_ylabel('Weighted events (encoded/backend ns divided by period)')
    ax.set_ylim(0, max(max(v) for v in values)*1.2)
    ax.grid(axis='y', alpha=.2); ax.legend(ncol=3, loc='upper center', bbox_to_anchor=(.5, -.1), fontsize=8)
    return fig, {'stages': stages, 'runtime_values': {row['runtime']: v for row, v in zip(rows, values)}}


def research(directory, sources):
    rows = read_json(directory / 'overhead.json', sources)['rows']
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    settings = [(depth, hz) for depth in (48, 256) for hz in (100, 1000)]
    derived = []
    for index, (depth, hz) in enumerate(settings):
        selected = [r for r in rows if r['depth'] == depth and r['hz'] == hz]
        pairs = {mode: {r['round']: r for r in selected if r['mode'] == mode} for mode in ('batched', 'otel')}
        if set(pairs['batched']) != set(range(1, 8)) or set(pairs['otel']) != set(range(1, 8)):
            raise ValueError('Research requires all seven matched rounds')
        entry = {'depth': depth, 'hz': hz}
        for axis, metric, color in zip(axes, ('total_cpu_ns', 'work_wall_ns'), (BLUE, ORANGE)):
            changes = []
            for round_id in range(1, 8):
                off, on = pairs['batched'][round_id], pairs['otel'][round_id]
                if off['iterations'] != on['iterations'] or off['checksum'] != on['checksum']:
                    raise ValueError('Unmatched research work')
                changes.append((on[metric] / off[metric] - 1) * 100)
            median = statistics.median(changes)
            axis.scatter([index + (i - 3) * .05 for i in range(7)], changes, color=color, alpha=.7,
                         s=33, label='Matched round' if index == 0 else None)
            axis.scatter(index, median, marker='D', s=35, color='#243746',
                         label='Median of paired changes' if index == 0 else None)
            axis.annotate(f'{median:+.2f}%', (index, median), xytext=(7, 10), textcoords='offset points', fontsize=9)
            entry[metric + '_paired_percent'] = changes
            entry[metric + '_median_percent'] = median
        derived.append(entry)
    for axis, title in zip(axes, ('Total CPU, including final flush', 'Work-only wall time, excluding final flush')):
        axis.axhline(0, color=GREY, linestyle='--', linewidth=1)
        axis.set_xticks(range(4), [f'depth {d}\n{hz} Hz' for d, hz in settings])
        axis.set(title=title, ylabel='Relative change to batched (%)')
        axis.grid(axis='y', alpha=.2); axis.legend(fontsize=8, loc='upper left')
        axis.margins(y=.3)
    return fig, {'matched_rounds': 7, 'settings': derived}


def smoke(report, sources):
    sources.add(report)
    text = strip_block(report.read_text())
    value = re.search(r'\| Latency p50 / p95 / max \|([^|]+)', text)[1]
    latency_values = [float(v) for v in re.findall(r'~([0-9.]+)', value)]
    if len(latency_values) != 3: raise ValueError('Smoke sample rounded values not found')
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.8))
    bars = axes[0].bar(['p50', 'p95', 'max'], latency_values, color=GREY, width=.55)
    axes[0].bar_label(bars, labels=[f'≈{v:g}' for v in latency_values], padding=4)
    axes[0].set(ylabel='HTTP duration (ms)', title='Rounded values from Markdown sample')
    axes[0].margins(y=.2); axes[0].grid(axis='y', alpha=.2)
    axes[1].axis('off'); axes[1].text(.05, .85, 'Illustrative laptop wiring run\n\nNo raw k6 artifact is retained.\nNo A/B comparison.\nNo cloud capacity claim.\n\nValues retain their approximate precision.', va='top', linespacing=1.6)
    return fig, {'approximate_latency_ms_from_markdown': latency_values}


def block(image, caption):
    return f'\n{START}\n## Recorded results at a glance\n\n![Recorded results]({image})\n\n{caption}\n{END}\n'


def overview(sources):
    pairs = [('FPM', '2026-11-06-overhead-depth48-cloud'), ('RoadRunner', '2026-11-07-overhead-rr-agent-depth48-cloud'),
             ('Swoole', '2026-11-07-overhead-swoole-agent-depth48-cloud')]
    fig, axes = plt.subplots(2, 3, figsize=(13, 7.5))
    data = {}
    for index, (label, stem) in enumerate(pairs):
        k = [metrics(REPORTS/stem/(arm+'-k6.json'), sources) for arm in ('baseline','on')]
        latency(axes[0, index], [('Off',k[0],GREY),('On',k[1],BLUE)])
        axes[0, index].set_title(label)
        stats = [read_csv(REPORTS/stem/(arm+'-fpm-stats.csv'), sources) for arm in ('baseline','on')]
        for rows, arm, color in zip(stats, ('Off','On'), (GREY,BLUE)):
            line(axes[1,index], rows, 'cpu_percent', arm, color)
        axes[1,index].set(xlabel='Seconds since each arm began', ylabel='Container CPU % (100% = one core)')
        axes[1,index].legend(fontsize=8)
        data[label] = {arm:{p: item['http_req_duration'][p] for p in ('med','p(95)','p(99)')} for arm,item in zip(('off','on'),k)}
        data[label]['cpu_samples'] = [len(rows) for rows in stats]
    return fig, data


def soak_overview(sources):
    paths = [('FPM','2026-11-07-soak-fpm-agent-depth48-cloud','app-fpm-stats.csv'),
             ('RoadRunner','2026-11-08-soak-rr-agent-depth48-cloud','app-rr-stats.csv'),
             ('Swoole','2026-11-07-soak-swoole-agent-depth48-cloud','app-swoole-stats.csv')]
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.7))
    data = {}
    for ax,(label,stem,app) in zip(axes,paths):
        series_data = [('App container',read_csv(REPORTS/stem/app,sources)),('Agent container',read_csv(REPORTS/stem/'app-agent-stats.csv',sources))]
        origin=min(rows[0]['ts_unix'] for _,rows in series_data)
        for (role,rows),color in zip(series_data,(BLUE,ORANGE)):
            line(ax,rows,'mem_usage_bytes',role,color,2**20,origin,3600)
        title=label+'\nworker-scoped profiler rerun' if label=='RoadRunner' else label
        ax.set(title=title,xlabel='Hours since first observation',ylabel='Container memory usage (MiB)');ax.legend(fontsize=8)
        data[label]={'samples':{role:len(rows) for role,rows in series_data},'hours':max((rows[-1]['ts_unix']-origin)/3600 for _,rows in series_data)}
    return fig,data


def fingerprint(path):
    content = strip_block(path.read_text()).encode() if path.suffix == '.md' else path.read_bytes()
    return hashlib.sha256(content).hexdigest()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');args=parser.parse_args()
    previous = json.loads((REPORTS/'plot-manifest.json').read_text()) if args.check else None
    entries=[]
    for report in sorted(REPORTS.glob('20*.md')):
        stem=report.stem;directory=report.with_suffix('');sources=set()
        if 'profile-shares' in stem: continue  # already has its own complete experiment plot
        if 'otel-callback-preflight' in stem: kind='research';fig,derived=research(directory,sources)
        elif 'overhead' in stem: kind='overhead';fig,derived=overhead(directory,sources)
        elif 'soak' in stem: kind='soak';fig,derived=soak(directory,sources)
        elif any(k in stem for k in ('spool-pressure','chaos','rps-pipeline')):
            kind=next(k for k in ('spool-pressure','chaos','rps-pipeline') if k in stem);fig,derived=queue(directory,sources,kind)
        elif 'signal-weights' in stem:kind='weights';fig,derived=weights(directory,sources)
        elif 'smoke-sample' in stem:kind='smoke';fig,derived=smoke(report,sources)
        else: raise ValueError(f'No plotting method for {report}')
        output=directory/'results.svg'
        historical=kind not in ('weights','smoke') and stem[:10] < '2026-11-17'
        title=f'{"Historical " if historical else ""}{kind.replace("-"," ").title()} · {runtime_name(stem) if kind not in ("weights","smoke","research") else "saved evidence"} · {stem[:10]}'
        if kind=='research':
            title='Deferred OTel callback research · seven matched rounds per setting'
            footer='Deferred research, not product overhead or an RC commitment. Dots show all pairs; diamonds show paired medians.'
        elif historical:
            footer=historical_footnote()
        elif kind=='weights':
            footer='Exact event conservation only; not function-share accuracy or overhead.'
        elif kind=='smoke':
            footer='Illustrative rounded laptop sample, not a capacity result; no raw k6 artifact retained.'
        else:
            footer='Recorded measurements on the versions/configuration in the report; no universal performance claim.'
        svg=finish(fig,output,title,footer,zero_baseline=kind!='research')
        image=output.relative_to(report.parent).as_posix()
        caption=('Historical saved measurements on the versions/configuration in this report; no current-version performance claim. '
                 'Lines connect recorded samples; gaps over three typical intervals are not connected.' if historical else footer)
        if kind in ('soak','overhead'):caption+=' Memory is container usage from saved docker stats, not per-process RSS or proof of leak freedom.'
        if kind=='research':caption+=' Comparisons use matching rounds; the median paired ratio is not the ratio of marginal medians.'
        if kind=='spool-pressure':caption+=' Catch-up annotation comes from the saved restart measurement; no synthetic drain curve is added.'
        targets=[(report,image)]+[(p,'results.svg') for p in directory.glob('*.md')]
        entry={'report':report.relative_to(ROOT).as_posix(),'kind':kind,'image':output.relative_to(ROOT).as_posix(),
               'sources':{p.relative_to(ROOT).as_posix():fingerprint(p) for p in sorted(sources)},'derived':derived,
               'svg_sha256':hashlib.sha256(svg.encode()).hexdigest()}
        if args.check:
            if not output.exists() or output.read_text()!=svg:raise ValueError(f'Stale figure: {output}')
            for target,url in targets:
                if target.read_text()!=strip_block(target.read_text()).rstrip()+'\n'+block(url,caption):raise ValueError(f'Stale embedded plot: {target}')
        else:
            directory.mkdir(exist_ok=True);output.write_text(svg)
            for target,url in targets:target.write_text(strip_block(target.read_text()).rstrip()+'\n'+block(url,caption))
        entries.append(entry)
    for name,make,title,footer in [
        ('overhead',overview,'Historical overhead A/B · depth 48 · sampleRate 0.1 · 20 requests/s',
         'Core 0.1.0. Each panel is a separate A/B pair, not a runtime ranking. Host/configuration-specific.'),
        ('soak-memory',soak_overview,'Historical completed 6h depth-48 soaks · Go-agent reader',
         'Core/agent 0.1.0. RR rerun after lifecycle fix. Container memory, not process RSS or proof of leak freedom.')]:
        sources=set();fig,derived=make(sources);output=REPORTS/'overview'/(name+'.svg');svg=finish(fig,output,title,footer)
        if args.check:
            if output.read_text()!=svg:raise ValueError(f'Stale overview: {output}')
        else:output.parent.mkdir(exist_ok=True);output.write_text(svg)
        entries.append({'report':'README candidate','kind':name,'image':output.relative_to(ROOT).as_posix(),
                        'sources':{p.relative_to(ROOT).as_posix():fingerprint(p) for p in sorted(sources)},'derived':derived,
                        'svg_sha256':hashlib.sha256(svg.encode()).hexdigest()})
    manifest={'matplotlib':matplotlib.__version__,'figures':entries}
    if args.check:
        if manifest!=previous:raise ValueError('Plot provenance manifest differs')
    else:(REPORTS/'plot-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(f'{"Verified" if args.check else "Rendered"} {len(entries)} figures; source files and report numbers unchanged')


if __name__=='__main__':main()
