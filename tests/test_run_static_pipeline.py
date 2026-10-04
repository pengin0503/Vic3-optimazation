from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

SPEC = importlib.util.spec_from_file_location(
    "run_static_pipeline", TOOLS / "run_static_pipeline.py"
)
mod = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = mod
assert SPEC.loader is not None
SPEC.loader.exec_module(mod)


class PipelineSummaryTests(unittest.TestCase):
    def test_build_summary(self):
        static = {
            "executable": {
                "sha256": "abc",
                "size_bytes": 100,
                "ticktasks": ["A", "B"],
                "source_paths": ["x.cpp"],
                "profiler_and_console_commands": ["TickTask.List"],
            }
        }
        xrefs = {
            "items": [
                {"anchor": "A", "candidate_references": [{"x": 1}]},
                {"anchor": "B", "candidate_references": []},
            ]
        }
        rtti = {
            "mapped_class_count": 2,
            "unmapped_ticktask_names": [],
            "task_specific_tail_vfunc_unique_count": 2,
        }
        sig = {"hash_ok": True, "all_targets_ok": True, "target_count": 3}
        result = mod.build_summary(static, xrefs, rtti, sig)
        self.assertEqual(result["ticktask_name_count"], 2)
        self.assertEqual(result["xref_anchors_with_candidates"], 1)
        self.assertTrue(result["signature_validation"]["all_targets_ok"])


if __name__ == "__main__":
    unittest.main()
