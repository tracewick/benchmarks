"""The share checker must reject a wrong split even when total weight is preserved."""
import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('share_analysis', ROOT / 'scripts/share-accuracy/analyze.py')
analysis = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analysis)


def graph(alpha=7000, beta=3000, other=0):
    total = alpha + beta + other
    return {'flamegraph': {'names': ['total', 'shareAlpha', 'shareBeta', 'leaf'], 'total': str(total),
                          'levels': [{'values': [0, total, other, 0]},
                                     {'values': [0, alpha, 0, 1, alpha, beta, beta, 2]},
                                     {'values': [0, alpha, alpha, 3]}]}}


def oracle():
    return {'elapsed_ns': {'alpha': 7_000_000, 'beta': 3_000_000},
            'spec': {'period_ns': 1, 'min_periods': 3000}}


class ShareAccuracyTest(unittest.TestCase):
    def test_uses_inclusive_phase_weight_not_leaf_self_weight(self):
        weights = analysis.phase_weights(graph())
        self.assertEqual(weights, {'alpha': 7000, 'beta': 3000, 'other': 0, 'total': 10000})
        self.assertTrue(analysis.assess(oracle(), weights)['pass'])

    def test_swapped_symbols_fail_while_total_stays_equal(self):
        weights = analysis.phase_weights(graph(alpha=3000, beta=7000))
        result = analysis.assess(oracle(), weights)
        self.assertEqual(weights['total'], 10000)
        self.assertEqual(result['failures'], ['share_error'])
        self.assertAlmostEqual(result['error_pp']['alpha'], 40)

    def test_hidden_unclassified_weight_fails_despite_correct_normalized_split(self):
        result = analysis.assess(oracle(), analysis.phase_weights(graph(other=10000)))
        self.assertEqual(result['failures'], ['unclassified_weight'])
        self.assertEqual(result['error_pp']['alpha'], 0)

    def test_too_few_weighted_periods_fail(self):
        result = analysis.assess(oracle(), analysis.phase_weights(graph(alpha=700, beta=300)))
        self.assertEqual(result['failures'], ['insufficient_period_weight'])

    def test_reference_comes_from_elapsed_time_not_nominal_ratio(self):
        reference = oracle()
        reference['elapsed_ns'] = {'alpha': 3, 'beta': 7}
        reference['spec']['alpha_percent'] = 70
        result = analysis.assess(reference, analysis.phase_weights(graph(alpha=3000, beta=7000)))
        self.assertTrue(result['pass'])

    def test_exactly_five_percentage_points_pass(self):
        self.assertTrue(analysis.assess(oracle(), analysis.phase_weights(graph(alpha=7500, beta=2500)))['pass'])

    def test_just_above_five_percentage_points_fails(self):
        self.assertIn('share_error', analysis.assess(oracle(), analysis.phase_weights(graph(alpha=7501, beta=2499)))['failures'])

    def test_exactly_one_percent_unclassified_passes(self):
        self.assertTrue(analysis.assess(oracle(), analysis.phase_weights(graph(alpha=6930, beta=2970, other=100)))['pass'])

    def test_just_above_one_percent_unclassified_fails(self):
        self.assertIn('unclassified_weight', analysis.assess(oracle(), analysis.phase_weights(graph(alpha=6930, beta=2970, other=101)))['failures'])

    def test_exactly_minimum_period_weight_passes(self):
        self.assertTrue(analysis.assess(oracle(), analysis.phase_weights(graph(alpha=2100, beta=900)))['pass'])

    def test_fixed_matrix_contains_every_cell_and_unique_seed(self):
        runner_spec = importlib.util.spec_from_file_location('share_runner', ROOT / 'scripts/share-accuracy/run.py')
        runner = importlib.util.module_from_spec(runner_spec)
        runner_spec.loader.exec_module(runner)
        cases = runner.matrix('test')
        self.assertEqual(len(cases), 18)
        self.assertEqual(len({c['seed'] for c in cases}), 18)
        self.assertEqual(len({c['id'] for c in cases}), 18)
        for period in (10000000, 1000000):
            for share, sleep in ((70, False), (20, False), (70, True)):
                self.assertEqual(sum(c['period_ns'] == period and c['alpha_percent'] == share and c['sleep_beta'] == sleep for c in cases), 3)

    def test_missing_phase_is_not_reported_as_zero_error(self):
        with self.assertRaises(ValueError):
            analysis.phase_weights(graph(beta=0))

    def test_overlapping_phase_nodes_are_rejected(self):
        value = graph()
        value['flamegraph']['levels'].append({'values': [0, 7000, 0, 1]})
        with self.assertRaises(ValueError):
            analysis.phase_weights(value)

    def test_malformed_graph_is_rejected(self):
        value = graph()
        value['flamegraph']['levels'][0]['values'].append(10)
        with self.assertRaises(ValueError):
            analysis.phase_weights(value)


if __name__ == '__main__':
    unittest.main()
