from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

SPEC = importlib.util.spec_from_file_location("map_static_xrefs", TOOLS / "map_static_xrefs.py")
mod = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = mod
assert SPEC.loader is not None
SPEC.loader.exec_module(mod)


class StaticXrefTests(unittest.TestCase):
    def test_scans_all_displacement_alignments(self):
        text_rva = 0x1000
        target = 0x345678
        for displacement_offset in range(4):
            raw = bytearray(b"\x90" * 32)
            disp = target - (text_rva + displacement_offset + 4)
            raw[displacement_offset : displacement_offset + 4] = int(disp).to_bytes(
                4, "little", signed=True
            )
            hits = mod.scan_rip_displacements(raw, text_rva, {target})
            self.assertIn(text_rva + displacement_offset, hits[target])

    def test_maps_runtime_function_range(self):
        functions = [(0x1000, 0x1100, 0x5000), (0x1200, 0x1300, 0x5100)]
        self.assertEqual(
            mod.find_containing_function(functions, 0x1080),
            (0x1000, 0x1100, 0x5000),
        )
        self.assertIsNone(mod.find_containing_function(functions, 0x1150))

    def test_missing_target_has_empty_hits(self):
        hits = mod.scan_rip_displacements(b"\x90" * 16, 0x1000, {0x5000})
        self.assertEqual(hits[0x5000], [])


if __name__ == "__main__":
    unittest.main()
