from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"

SPEC = importlib.util.spec_from_file_location(
    "triage_benchmark_targets", TOOLS / "triage_benchmark_targets.py"
)
mod = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = mod
assert SPEC.loader is not None
SPEC.loader.exec_module(mod)


class TriageTests(unittest.TestCase):
    def report(self):
        task = {
            "task": "UpdateEmployment",
            "mean_total_ms": 100.0,
            "median_total_ms": 99.0,
            "max_total_ms": 110.0,
            "mean_calls": 10,
            "longest_lock_ms": 3.0,
            "total_ms_cv": 0.01,
            "noisy": False,
        }
        return {
            "groups": [
                {
                    "variant": "vanilla",
                    "task_thread_count": 8,
                    "wall_clock_seconds": {"median": 20.0},
                    "tasks_by_cost": [task],
                    "tasks_by_lock": [task],
                }
            ]
        }

    def test_joins_runtime_name_to_rtti_class(self):
        rtti = {
            "classes": [
                {
                    "name": "CTickTask_UpdateEmployment",
                    "task_specific_tail_vfunc_rva": "0x1234",
                    "vtable_rva": "0x2000",
                }
            ]
        }
        result = mod.triage(
            self.report(), rtti, variant="vanilla", threads=8, top=10
        )
        row = result["top_by_cost"][0]
        self.assertTrue(row["native_mapping_available"])
        self.assertEqual(
            row["native"]["task_specific_tail_vfunc_rva"], "0x1234"
        )

    def test_requires_threads_when_multiple_groups_exist(self):
        report = self.report()
        report["groups"].append(
            {
                **report["groups"][0],
                "task_thread_count": 16,
            }
        )
        with self.assertRaises(mod.Error):
            mod.triage(report, {"classes": []}, variant="vanilla", threads=None, top=10)

    def test_supports_compact_tasks_document(self):
        rtti = {
            "tasks": [
                {
                    "name": "CTickTask_UpdateEmployment",
                    "task_specific_tail_vfunc_rva": "0x1234",
                }
            ]
        }
        result = mod.triage(
            self.report(), rtti, variant="vanilla", threads=8, top=1
        )
        self.assertEqual(result["mapped_cost_count"], 1)


if __name__ == "__main__":
    unittest.main()
