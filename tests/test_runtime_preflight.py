"""Validity regressions for the development runtime campaign."""
import copy
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts/runtime-preflight'))
from overhead import Overhead
from recovery import Recovery
from soaklib import Continuity
from test_soak import sample


class PreflightTest(unittest.TestCase):
    def test_disabled_measurement_retains_health_validation_during_drain(self):
        runner = Overhead.__new__(Overhead)
        runner.enabled = False
        runner.runtime = 'rr'
        runner.sample_rate = 0.1
        runner.env = {'WORK_STACK_DEPTH': '48'}
        runner.base_url = 'http://localhost'
        health = {'ok': True, 'excimer': True, 'tracewick': True,
                  'profiling_enabled': False, 'work_stack_depth': 48,
                  'rr_num_workers': 1, 'sample_rate': 0.1}
        with patch('soak.get_json', return_value=health):
            self.assertEqual(health, runner.health(True))
        with patch('soak.get_json', return_value={**health, 'profiling_enabled': True}):
            with self.assertRaisesRegex(ValueError, 'Wrong profiling state'):
                runner.health(True)

    def test_recovery_injection_does_not_allow_application_worker_replacement(self):
        runner = Recovery.__new__(Recovery)
        runner.started = 1
        runner.phase = 'steady'
        runner.reader_epoch = 1
        runner.reader_running = True
        runner.backend_running = True
        runner.paused = False
        runner.ids = {'app': 'app'}
        runner.health = lambda _: {}
        runner.app_guard = Continuity(15)
        old = sample()
        runner.app_guard.check(old)
        replaced = copy.deepcopy(old['containers']['app'])
        replaced['processes'][0]['start_ticks'] += 1
        runner.docker = SimpleNamespace(sample=lambda *args, **kwargs: replaced)
        with patch('recovery.time.monotonic', return_value=15):
            with self.assertRaisesRegex(ValueError, 'worker/process identity changed'):
                runner.take()


if __name__ == '__main__':
    unittest.main()
