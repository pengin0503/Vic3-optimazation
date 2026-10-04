from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
import struct
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("analyze_vic3", ROOT / "tools" / "analyze_vic3.py")
mod = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = mod
assert SPEC.loader is not None
SPEC.loader.exec_module(mod)

def minimal_pe64(payload: bytes = b"") -> bytes:
    pe_off = 0x80
    optional_size = 0xF0
    section_raw = 0x200
    section_size = max(0x200, ((len(payload) + 0x1FF) // 0x200) * 0x200)
    data = bytearray(section_raw + section_size)
    data[:2] = b"MZ"
    struct.pack_into("<I", data, 0x3C, pe_off)
    data[pe_off:pe_off + 4] = b"PE\0\0"
    coff = pe_off + 4
    struct.pack_into("<HHIIIHH", data, coff, 0x8664, 1, 123456, 0, 0, optional_size, 0x22)
    opt = coff + 20
    struct.pack_into("<H", data, opt, 0x20B)
    data[opt + 2] = 14
    data[opt + 3] = 44
    struct.pack_into("<I", data, opt + 16, 0x1000)
    struct.pack_into("<Q", data, opt + 24, 0x140000000)
    struct.pack_into("<I", data, opt + 32, 0x1000)
    struct.pack_into("<I", data, opt + 36, 0x200)
    struct.pack_into("<I", data, opt + 56, 0x2000)
    struct.pack_into("<I", data, opt + 60, 0x200)
    struct.pack_into("<H", data, opt + 68, 2)
    struct.pack_into("<H", data, opt + 70, 0x8160)
    struct.pack_into("<I", data, opt + 108, 16)
    sec = opt + optional_size
    data[sec:sec + 8] = b".text\0\0\0"
    struct.pack_into("<IIIIIIHHI", data, sec + 8, len(payload), 0x1000, section_size, section_raw, 0, 0, 0, 0, 0x60000020)
    data[section_raw:section_raw + len(payload)] = payload
    return bytes(data)

class AnalyzerTests(unittest.TestCase):
    def test_missing_path_fails_cleanly(self):
        self.assertEqual(mod.main([str(ROOT / "definitely-does-not-exist")]), 2)

    def test_minimal_pe_analysis_is_deterministic(self):
        raw = minimal_pe64(
            b"CTickTask_Example\0"
            b"Threading.TaskThreadCount\0"
            b"source/logic/example.cpp\0"
            b"CPdxParallelForDescriptor\0"
        )
        a = mod.analyze_executable(raw, "fixture.exe")
        b = mod.analyze_executable(raw, "fixture.exe")
        self.assertEqual(a, b)
        self.assertEqual(a["pe"]["kind"], "PE32+")
        self.assertEqual(a["pe"]["linker_version"], "14.44")
        self.assertIn("CTickTask_Example", a["ticktasks"])
        self.assertIn("Threading.TaskThreadCount", a["profiler_and_console_commands"])

    @unittest.skipUnless(os.environ.get("VIC3_DATA"), "set VIC3_DATA to Vic3_data.zip for integration test")
    def test_known_1_14_5_fixture(self):
        raw, logical = mod.read_target(Path(os.environ["VIC3_DATA"]), "victoria3.exe")
        result = mod.analyze_executable(raw, logical)
        self.assertEqual(result["sha256"], "9b6f133a5dc235de9135d7b57e86ceda8282d1ba6c0e185f3ee19c22f8917f54")
        self.assertEqual(result["size_bytes"], 97_774_200)
        self.assertEqual(result["pe"]["kind"], "PE32+")
        self.assertEqual(result["pe"]["linker_version"], "14.44")
        self.assertEqual([s["name"] for s in result["pe"]["sections"]], [".text", ".rdata", ".data", ".pdata", ".rsrc", ".reloc"])
        self.assertGreaterEqual(len(result["ticktasks"]), 260)
        for command in (
            "TickTask.List",
            "TickTask.Graph",
            "clear_ticktask_timings",
            "dump_ticktask_timings",
            "Threading.TaskThreadCount",
            "Threading.EnableTaskThreads",
        ):
            self.assertIn(command, result["profiler_and_console_commands"])
        self.assertIn(
            "C:\\mnt\\gsg\\caligula\\caligula\\outputdir_windows\\binaries\\victoria3.pdb",
            result["pdb_paths"],
        )

if __name__ == "__main__":
    unittest.main()
