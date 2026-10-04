from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

SPEC = importlib.util.spec_from_file_location("map_ticktask_rtti", TOOLS / "map_ticktask_rtti.py")
mod = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = mod
assert SPEC.loader is not None
SPEC.loader.exec_module(mod)


class TickTaskRttiTests(unittest.TestCase):
    def test_rtti_regex_accepts_anonymous_namespace_suffix(self):
        data = (
            b".?AVCTickTask_UpdateEmployment@?A0x0778c8c9@@\x00"
            b".?AVCTickTask_OnePlain@@\x00"
        )
        names = [m.group(1).decode("ascii") for m in mod.RTTI_TICKTASK.finditer(data)]
        self.assertEqual(
            names,
            ["CTickTask_UpdateEmployment", "CTickTask_OnePlain"],
        )

    def test_slot_frequency_counts_common_slots(self):
        classes = [
            {"vtable_slots_rva": [0x100, 0x200, 0x300]},
            {"vtable_slots_rva": [0x110, 0x200, 0x310]},
        ]
        summary = mod.slot_frequency(classes)
        self.assertEqual(summary["1"][0]["function_rva"], "0x200")
        self.assertEqual(summary["1"][0]["class_count"], 2)

    def test_runtime_function_containing_fallback(self):
        functions = [(0x1000, 0x1100, 0x5000), (0x1200, 0x1300, 0x5100)]
        self.assertEqual(
            mod.runtime_function_for(functions, 0x1080),
            (0x1000, 0x1100, 0x5000),
        )
        self.assertIsNone(mod.runtime_function_for(functions, 0x1150))


if __name__ == "__main__":
    unittest.main()
