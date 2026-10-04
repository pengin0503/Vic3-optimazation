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


def group(threads, wall, noisy=False):
    return {
        "variant": "vanilla",
        "task_thread_count": threads,
        "wall_clock_seconds": {"median": wall, "noisy": noisy},
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


if __name__ == "__main__":
    unittest.main()
