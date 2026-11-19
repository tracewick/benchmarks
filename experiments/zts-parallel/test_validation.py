"""Negative controls for the compatibility verdict, without Docker or extensions."""

import importlib.util
from pathlib import Path
import unittest

SPEC = importlib.util.spec_from_file_location("zts_probe", Path(__file__).with_name("run.py"))
RUN = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUN)


class VerdictTest(unittest.TestCase):
    def setUp(self):
        self.data = {"php": "8.5.12", "zts": True, "mode": "native", "event": "wall",
            "scenario": "one", "spool": [], "rows": [{"actor": "alpha", "mode": "native",
            "events": 200, "markers": {"probeAlpha": 200}, "callbacks": 2,
            "callback_actors": ["alpha"], "diagnostics": None, "labels": []}]}

    def test_valid_native_result_passes(self):
        self.assertEqual([], RUN.validate(self.data))

    def test_swapped_thread_marker_is_rejected(self):
        self.data["rows"][0]["markers"] = {"probeBeta": 200}
        self.assertTrue(RUN.validate(self.data))

    def test_callback_from_other_interpreter_is_rejected(self):
        self.data["rows"][0]["callback_actors"] = ["beta"]
        self.assertTrue(RUN.validate(self.data))

    def test_no_samples_is_not_a_success(self):
        self.data["rows"][0]["events"] = 0
        self.assertTrue(RUN.validate(self.data))

    def test_sleeping_thread_cannot_inherit_busy_sibling_cpu(self):
        self.data.update(scenario="idle-cpu", event="cpu")
        self.assertTrue(RUN.validate(self.data))

    def test_corrupt_spool_weights_are_rejected(self):
        self.data["mode"] = "uow"
        self.data["spool"] = [{"labels": {"actor": "alpha"}, "events": 199,
                               "markers": {"probeAlpha": 199}}]
        self.assertTrue(RUN.validate(self.data))

    def test_unflushed_shutdown_is_rejected(self):
        self.data["scenario"] = "shutdown"
        self.assertTrue(RUN.validate(self.data))

    def test_persistent_worker_threads_are_rejected(self):
        self.data.update(scenario="churn", threads_after_close=[1, 2])
        self.assertTrue(RUN.validate(self.data))


if __name__ == "__main__":
    unittest.main()
