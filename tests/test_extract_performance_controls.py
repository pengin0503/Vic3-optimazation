from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"

SPEC = importlib.util.spec_from_file_location(
    "extract_performance_controls", TOOLS / "extract_performance_controls.py"
)
mod = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = mod
assert SPEC.loader is not None
SPEC.loader.exec_module(mod)


class PerformanceControlTests(unittest.TestCase):
    def test_extracts_value_and_comment(self):
        text = """
# Lower values are fresher but hurt performance
NON_TRADE_CENTER_STATE_TRADE_POTENTIAL_UPDATE_FREQUENCY = 30 # days
OTHER_VALUE = 2
"""
        rows = mod.extract_from_text(
            "game/common/defines/00_defines.txt",
            text,
            {"NON_TRADE_CENTER_STATE_TRADE_POTENTIAL_UPDATE_FREQUENCY"},
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["value"], "30")
        self.assertIn("hurt performance", rows[0]["preceding_comments"][0])

    def test_missing_key_is_reported_by_aggregate_logic(self):
        rows = mod.extract_from_text("x.txt", "A = 1\n", {"B"})
        self.assertEqual(rows, [])

    def test_candidate_file_filters_macos_metadata(self):
        self.assertTrue(
            mod.candidate_file("Vic3_data/game/common/defines/00_ai.txt")
        )
        self.assertFalse(
            mod.candidate_file("__MACOSX/Vic3_data/game/common/defines/._00_ai.txt")
        )


if __name__ == "__main__":
    unittest.main()
