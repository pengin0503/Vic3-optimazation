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
    "validate_exact_signatures", TOOLS / "validate_exact_signatures.py"
)
mod = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = mod
assert SPEC.loader is not None
SPEC.loader.exec_module(mod)


class SignatureValidationHelpers(unittest.TestCase):
    def test_parse_hex_pattern(self):
        self.assertEqual(mod.parse_hex_pattern("48 8b 01"), b"\x48\x8b\x01")

    def test_empty_pattern_fails(self):
        with self.assertRaises(mod.Error):
            mod.parse_hex_pattern("")

    def test_occurrence_count_is_overlapping(self):
        self.assertEqual(mod.count_occurrences(b"AAAA", b"AA"), 3)


if __name__ == "__main__":
    unittest.main()
