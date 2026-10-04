from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

SPEC = importlib.util.spec_from_file_location("generate_signatures", TOOLS / "generate_signatures.py")
mod = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = mod
assert SPEC.loader is not None
SPEC.loader.exec_module(mod)


class SignatureTests(unittest.TestCase):
    def test_finds_unique_window(self):
        text = b"A" * 40 + b"0123456789abcdef" + b"A" * 40
        sig = mod.choose_signature(text, 40, min_length=4, max_length=16, max_start_offset=8)
        self.assertIsNotNone(sig)
        self.assertEqual(sig["match_count_in_text"], 1)
        self.assertGreaterEqual(sig["length"], 4)

    def test_returns_none_when_no_window_is_unique(self):
        text = b"ABCD" * 40
        sig = mod.choose_signature(text, 0, min_length=4, max_length=8, max_start_offset=4)
        self.assertIsNone(sig)

    def test_count_occurrences_is_overlapping(self):
        self.assertEqual(mod.count_occurrences(b"AAAA", b"AA"), 3)


if __name__ == "__main__":
    unittest.main()
