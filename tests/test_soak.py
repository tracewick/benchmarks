"""Behavioral regression tests for misleading soak results and telemetry loss."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from soaklib import Docker, Continuity, parse_processes, prometheus, summarize, write_report
from soak import Soak, pin, seconds


def sample(t=0, requests=1):
    container = {'id': 'container', 'started_at': 'start', 'restarts': 0,
                 'cpu_ns': int(t * 2e9), 'throttled_ns': 0, 'memory_bytes': 1000 + t,
                 'processes': [{'pid': 1, 'start_ticks': 123, 'rss_bytes': 2000 + t,
                                'anon_bytes': 1000 + t, 'fds': 4, 'threads': 2, 'cpu_seconds': t}]}
    return {'monotonic': t, 'ts': t, 'phase': 'steady', 'k6': {'requests': requests},
            'containers': {'app': container}}


class ContinuityTest(unittest.TestCase):
    def test_worker_recycling_cannot_hide_memory_growth(self):
        guard = Continuity(15)
        guard.check(sample())
        restarted = sample(15, 150)
        restarted['containers']['app']['processes'][0]['start_ticks'] += 1
        with self.assertRaisesRegex(ValueError, 'identity changed'):
            guard.check(restarted)

    def test_detects_container_restart_and_replacement(self):
        for key, value in [('id', 'replacement'), ('started_at', 'new'), ('restarts', 1)]:
            with self.subTest(key=key):
                guard = Continuity(15)
                guard.check(sample())
                row = sample(15, 150)
                row['containers']['app'][key] = value
                with self.assertRaisesRegex(ValueError, 'restarted or was replaced'):
                    guard.check(row)

    def test_missing_samples_and_counter_resets_invalidate(self):
        for t, cpu in [(120, 100), (15, -1)]:
            guard = Continuity(15)
            guard.check(sample())
            row = sample(t)
            row['containers']['app']['cpu_ns'] = cpu
            with self.assertRaises(ValueError):
                guard.check(row)

    def test_snapshot_is_not_mutated_by_added_observations(self):
        row = sample()
        guard = Continuity(15)
        guard.check(row)
        row['containers']['generator'] = {}
        guard.check(sample(15, 150))


class EvidenceTest(unittest.TestCase):
    def test_process_rss_and_container_memory_are_separate_and_cpu_is_normalized(self):
        rows = [sample(0, 0), sample(1800, 18000), sample(3600, 36000)]
        report = summarize(rows)['services']['app']
        self.assertEqual(200, report['cpu_ms_per_request'])
        self.assertEqual(3600, report['rss_bytes']['slope_per_hour'])
        self.assertEqual(1000, report['container_memory_first_bytes'])
        self.assertEqual(2000, report['rss_bytes']['first'])

    def test_no_or_truncated_telemetry_does_not_pass(self):
        for rows in ([], [sample()]):
            with self.assertRaises(ValueError):
                summarize(rows)
        for raw in ('', '@ 1\n', '@ 1\n@end\n'):
            with self.assertRaises(ValueError):
                parse_processes(raw)

    def test_real_proc_record_including_parentheses_in_comm(self):
        # Fields 3..22 include utime/stime at indexes 11/12 and starttime at 19.
        stat = ['S'] + ['0'] * 19
        stat[11], stat[12], stat[19] = '100', '50', '12345'
        raw = '@ 1\n1 (php (worker)) ' + ' '.join(stat) + '\nVmRSS:\t8 kB\nRssAnon:\t4 kB\nThreads:\t2\nFDs:\t3\n@end\n'
        row = parse_processes(raw)[0]
        self.assertEqual(8192, row['rss_bytes'])
        self.assertEqual(4096, row['anon_bytes'])
        self.assertEqual(12345, row['start_ticks'])
        self.assertEqual('php (worker)', row['comm'])

    def test_absent_or_nonfinite_agent_metrics_are_not_zero_queue(self):
        for text in ('', 'spool_files 0\n', 'spool_files NaN\n'):
            with self.assertRaises(ValueError):
                prometheus(text)

    def test_failure_report_is_written_without_false_green(self):
        with tempfile.TemporaryDirectory() as directory:
            write_report(directory, {'status': 'invalid', 'error': 'missing telemetry'})
            result = json.loads((Path(directory) / 'result.json').read_text())
            self.assertEqual('invalid', result['status'])
            self.assertIn('missing telemetry', (Path(directory) / 'soak-report.md').read_text())



    def test_parent_cgroup_cpu_is_not_attributed_to_a_new_container(self):
        from datetime import datetime, timezone
        engine = Docker.__new__(Docker)
        engine.inspect = lambda _: {'State': {'Running': True, 'StartedAt': datetime.now(timezone.utc).isoformat()},
                                    'Id': 'new', 'Image': 'image', 'RestartCount': 0}
        engine.get = lambda _: {'cpu_stats': {'cpu_usage': {'total_usage': 10**18}},
                                'memory_stats': {'usage': 100, 'stats': {}}}
        with self.assertRaisesRegex(ValueError, 'cgroup accounting'):
            engine.sample('new')

    def test_shared_cgroup_cannot_be_used_for_a_long_soak(self):
        env = {'TRACEWICK_VERSION': '0.2.0', 'AGENT_VERSION': '0.2.1',
               'SOAK_SMOKE_SHARED_CGROUP': '1', 'DURATION': '72h'}
        with patch.dict(os.environ, env, clear=True), patch('soak.Docker'):
            with self.assertRaisesRegex(ValueError, '60 seconds'):
                Soak()

    def test_disabled_or_inactive_profiling_is_not_a_healthy_run(self):
        runner = Soak.__new__(Soak)
        runner.base_url = 'http://localhost'
        runner.runtime = 'rr'
        runner.sample_rate = 0.1
        runner.env = {'WORK_STACK_DEPTH': '48'}
        healthy = {'ok': True, 'excimer': True, 'tracewick': True,
                   'profiling_enabled': True, 'work_stack_depth': 48,
                   'rr_num_workers': 1, 'sample_rate': 0.1}
        with patch('soak.get_json', return_value=healthy):
            self.assertEqual(healthy, runner.health(True))
        for changes in ({'excimer': False}, {'profiling_enabled': False},
                        {'work_stack_depth': 0}, {'rr_num_workers': 2}, {'sample_rate': 1},
                        {'diagnostics': {'inactiveSampler': 'disabled'}}):
            with patch('soak.get_json', return_value={**healthy, **changes}):
                with self.assertRaises(ValueError):
                    runner.health(True)

    def test_wrong_installed_reference_is_rejected_before_traffic(self):
        runner = Soak.__new__(Soak)
        runner.package = 'dev-develop#' + 'a' * 40
        runner.ids = {'app': 'test-container'}
        with patch('soak.command', return_value=json.dumps({'reference': 'b' * 40})):
            with self.assertRaisesRegex(ValueError, 'reference'):
                runner.runtime_identity()

    def test_wrong_excimer_version_is_rejected_before_traffic(self):
        runner = Soak.__new__(Soak)
        runner.package = '0.2.0'
        runner.env = {'EXCIMER_VERSION': '1.2.7'}
        runner.ids = {'app': 'test-container'}
        actual = {'version': '0.2.0', 'excimer': '1.2.6'}
        with patch('soak.command', return_value=json.dumps(actual)):
            with self.assertRaisesRegex(ValueError, 'Excimer version'):
                runner.runtime_identity()

    def test_k6_must_complete_the_scheduled_workload(self):
        runner = Soak.__new__(Soak)
        runner.rate = 10
        for iterations, drops in ((600, 0), (599, 0), (601, 0), (598, 0), (602, 0), (600, 1)):
            with self.subTest(iterations=iterations, drops=drops):
                summary = {'metrics': {'iterations': {'count': iterations},
                                       'dropped_iterations': {'count': drops}}}
                if abs(iterations - 600) <= 1 and drops == 0:
                    runner.check_load_summary(summary, '1m')
                else:
                    with self.assertRaisesRegex(ValueError, 'Incomplete load'):
                        runner.check_load_summary(summary, '1m')

    def test_exact_pins_and_combined_durations(self):
        self.assertEqual(5400, seconds('1h30m'))
        self.assertEqual('dev-develop#' + 'a' * 40, pin('dev-develop#' + 'a' * 40))
        for value in ('latest', 'dev-develop', '^0.2', '0.2'):
            with self.assertRaises(ValueError):
                pin(value)
        for value in ('0s', '-1h', '72hours'):
            with self.assertRaises(ValueError):
                seconds(value)


if __name__ == '__main__':
    unittest.main()
