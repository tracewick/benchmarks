"""Strict, independent analysis of actual Pyroscope flamegraph node weights."""

PHASES = {'shareAlpha': 'alpha', 'shareBeta': 'beta'}
MAX_ERROR_PP = 5
MAX_OTHER_PERCENT = 1


def phase_weights(response):
    graph = response['flamegraph']
    total = int(graph['total'])
    if total <= 0:
        raise ValueError('Empty profile')
    names = graph['names']
    weights = {'alpha': 0, 'beta': 0}
    for level in graph['levels']:
        row = level['values']
        if len(row) % 4:
            raise ValueError('Malformed flamegraph tuples')
        for offset in range(0, len(row), 4):
            width, own, name_id = map(int, row[offset + 1:offset + 4])
            if width < 0 or own < 0 or own > width or name_id < 0 or name_id >= len(names):
                raise ValueError('Invalid node')
            phase = PHASES.get(names[name_id])
            if phase:
                weights[phase] += width
    if min(weights.values()) <= 0 or sum(weights.values()) > total:
        raise ValueError('Missing, overlapping or invalid phase weights')
    return weights | {'other': total - sum(weights.values()), 'total': total}


def assess(oracle, weights):
    measured = oracle['elapsed_ns']
    duration = sum(measured.values())
    classified = weights['alpha'] + weights['beta']
    total = weights['total']
    if duration <= 0 or min(measured.values()) <= 0 or classified <= 0 or total <= 0:
        raise ValueError('Invalid oracle or observations')
    expected = {p: measured[p] / duration for p in ('alpha', 'beta')}
    observed = {p: weights[p] / classified for p in ('alpha', 'beta')}
    errors = {p: abs(expected[p] - observed[p]) * 100 for p in expected}
    other_percent = weights['other'] / total * 100
    effective_periods = classified / oracle['spec']['period_ns']
    floor = oracle['spec']['min_periods']
    failures = []
    # Integer cross-products keep the inclusive 5 pp boundary exact.
    if any(abs(measured[p] * classified - weights[p] * duration) * 100
           > MAX_ERROR_PP * duration * classified for p in expected):
        failures.append('share_error')
    if weights['other'] * 100 > MAX_OTHER_PERCENT * total:
        failures.append('unclassified_weight')
    if classified < floor * oracle['spec']['period_ns']:
        failures.append('insufficient_period_weight')
    return {'expected': expected, 'observed': observed, 'error_pp': errors,
            'other_percent': other_percent, 'weighted_periods': effective_periods,
            'weights_ns': weights, 'pass': not failures, 'failures': failures}
