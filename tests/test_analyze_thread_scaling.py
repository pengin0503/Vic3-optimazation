from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"

SPEC = importlib.util.spec_from_file_location(
    "analyze_thread_scaling", TOOLS / "analyze_thread_scaling.py"
)
mod = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = mod
assert SPEC.loader is not None
SPEC.loader.exec_module(mod)


def group(threads, wall, noisy=False, runs=3):
    return {
        "variant": "vanilla",
        "task_thread_count": threads,
        "runs": runs,
        "wall_clock_seconds": {"median": wall, "noisy": noisy, "cv":0.0},
    }


class ScalingTests(unittest.TestCase):
    def test_ideal_scaling_has_zero_effective_serial_fraction(self):
        report = {"groups": [group(1, 40.0), group(4, 10.0)]}
        result = mod.analyze(report)
        row = result["variants"][0]["rows"][1]
        self.assertAlmostEqual(row["speedup_vs_base"], 4.0)
        self.assertAlmostEqual(row["amdahl_effective_serial_fraction"], 0.0)

    def test_plateau_screen(self):
        report = {
            "groups": [
                group(1, 40.0),
                group(4, 20.0),
                group(8, 19.5),
            ]
        }
        result = mod.analyze(report, plateau_threshold=0.05)
        self.assertEqual(
            result["variants"][0]["first_plateau_screen_thread_count"], 8
        )

    def test_noise_prevents_plateau_flag(self):
        report = {
            "groups": [
                group(1, 40.0),
                group(4, 20.0),
                group(8, 19.5, noisy=True),
            ]
        }
        result = mod.analyze(report, plateau_threshold=0.05)
        self.assertIsNone(
            result["variants"][0]["first_plateau_screen_thread_count"]
        )

    def test_single_observation_is_not_a_plateau(self):
        result = mod.analyze({'groups': [group(8, 37.51, noisy=None, runs=1), group(12, 36.67, noisy=None, runs=1)]})
        self.assertIsNone(result['variants'][0]['first_plateau_screen_thread_count'])
        row = result['variants'][0]['rows'][1]
        self.assertIsNone(row['wall_clock_noisy'])
        self.assertIsNone(row['plateau_screen'])
        self.assertIn('unknown', mod.markdown(result))

    def test_two_runs_and_legacy_missing_run_count_do_not_prove_plateau(self):
        for runs in (2, None):
            groups = [group(8, 37.51, runs=runs), group(12, 36.67, runs=runs)]
            if runs is None:
                for item in groups:
                    del item['runs']
            result = mod.analyze({'groups': groups})
            self.assertIsNone(result['variants'][0]['rows'][1]['plateau_screen'])

    def test_legacy_false_noise_with_unknown_cv_is_not_a_plateau(self):
        for remove_cv in (False, True):
            groups = [group(8, 37.51), group(12, 36.67)]
            for item in groups:
                item['wall_clock_seconds']['cv'] = None
                if remove_cv:
                    del item['wall_clock_seconds']['cv']
            result = mod.analyze({'groups':groups})
            row = result['variants'][0]['rows'][1]
            self.assertIsNone(row['wall_clock_noisy'])
            self.assertFalse(row['repeatability_assessed'])
            self.assertIsNone(row['plateau_screen'])


if __name__ == "__main__":
    unittest.main()
