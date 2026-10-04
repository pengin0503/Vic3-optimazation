from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"

SPEC = importlib.util.spec_from_file_location(
    "compare_static_analysis", TOOLS / "compare_static_analysis.py"
)
mod = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = mod
assert SPEC.loader is not None
SPEC.loader.exec_module(mod)


def snapshot(sha: str, tasks: list[str], commands: list[str]) -> dict:
    return {
        "executable": {
            "sha256": sha,
            "size_bytes": 10,
            "logical_path": "victoria3.exe",
            "pe": {
                "sections": [
                    {
                        "name": ".text",
                        "virtual_size": 100,
                        "raw_size": 100,
                        "characteristics": "0x60000020",
                    }
                ]
            },
            "imports": [{"dll": "KERNEL32.dll", "symbols": []}],
            "ticktasks": tasks,
            "profiler_and_console_commands": commands,
            "source_paths": ["a.cpp"],
        }
    }


class CompareTests(unittest.TestCase):
    def test_same_snapshot_is_stable(self):
        a = snapshot("a", ["CTickTask_A"], ["TickTask.List"])
        result = mod.compare(a, a)
        self.assertTrue(result["same_executable_hash"])
        self.assertTrue(result["static_interface_stable"])
        self.assertEqual(result["migration_decision"], "same-binary")

    def test_changed_hash_forces_revalidation(self):
        a = snapshot("a", ["CTickTask_A"], ["TickTask.List"])
        b = snapshot("b", ["CTickTask_A", "CTickTask_B"], ["TickTask.List"])
        result = mod.compare(a, b)
        self.assertEqual(result["ticktasks"]["added"], ["CTickTask_B"])
        self.assertEqual(
            result["migration_decision"],
            "revalidate-all-native-targets-before-enabling-hooks",
        )

    def test_rtti_tail_change_is_reported(self):
        base = snapshot("a", [], [])
        r1 = {"classes": [{"name": "CTickTask_A", "task_specific_tail_vfunc_rva": "0x1",
                           "vtable_slots_rva": ["0x1"]}]}
        r2 = {"classes": [{"name": "CTickTask_A", "task_specific_tail_vfunc_rva": "0x2",
                           "vtable_slots_rva": ["0x2"]}]}
        result = mod.compare(base, base, r1, r2)
        self.assertEqual(result["rtti"]["changed_common_class_count"], 1)


if __name__ == "__main__":
    unittest.main()
