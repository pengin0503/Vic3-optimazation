"""Tests for tools/check_lookup_contract_locator.py (B0 Task 1).

The mini PE32+ fixture is written field by field here; its expected entry,
call and return RVAs are literals. Structural mutation tests re-hash the
mutated image and assert the specific gate by message, so a hash-only reject
cannot make them pass.
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import os
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "check_lookup_contract_locator.py"

EXE_SHA = "9b6f133a5dc235de9135d7b57e86ceda8282d1ba6c0e185f3ee19c22f8917f54"
ENTRY_PATTERN = bytes.fromhex("4c8b51304c8bc94c63593c0fb6c2")

TEXT_VA = 0x1000
TEXT_RAW = 0x200
TEXT_SIZE = 0x200
SECTION_HEADER = 0x148
ENTRY = 0x1020
CALLS = (0x1040, 0x1060, 0x1080, 0x10A0, 0x10C0, 0x10E0)
# rel32 for E8 at site → 0x1020, computed by hand: 0x1020 - (site + 5).
REL32 = {0x1040: -0x25, 0x1060: -0x45, 0x1080: -0x65, 0x10A0: -0x85, 0x10C0: -0xA5, 0x10E0: -0xC5}


def load_module():
    spec = importlib.util.spec_from_file_location("check_lookup_contract_locator", TOOL)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def raw_of(rva: int) -> int:
    return rva - TEXT_VA + TEXT_RAW


def put(image: bytearray, rva: int, data: bytes) -> None:
    o = raw_of(rva)
    image[o:o + len(data)] = data


def call_pattern(site: int, rel: int, index: int) -> bytes:
    return b"\xe8" + struct.pack("<i", rel) + bytes([0x48, 0x8B, 0x18, 0x48, 0x63, 0x40, index])


def mini_case() -> tuple[bytes, dict]:
    image = bytearray(0x400)
    image[0:2] = b"MZ"
    struct.pack_into("<I", image, 0x3C, 0x40)
    image[0x40:0x44] = b"PE\0\0"
    # COFF: AMD64, one section, optional header 0xF0 bytes.
    struct.pack_into("<HHIIIHH", image, 0x44, 0x8664, 1, 0, 0, 0, 0xF0, 0x22)
    o = 0x58
    struct.pack_into("<H", image, o, 0x20B)
    struct.pack_into("<I", image, o + 16, ENTRY)
    struct.pack_into("<Q", image, o + 24, 0x140000000)
    struct.pack_into("<I", image, o + 56, 0x2000)
    struct.pack_into("<I", image, o + 60, 0x200)
    struct.pack_into("<I", image, o + 108, 16)
    s = SECTION_HEADER
    image[s:s + 8] = b".text\0\0\0"
    struct.pack_into("<IIII", image, s + 8, TEXT_SIZE, TEXT_VA, TEXT_SIZE, TEXT_RAW)
    struct.pack_into("<I", image, s + 36, 0x60000020)
    image[TEXT_RAW:TEXT_RAW + TEXT_SIZE] = b"\xcc" * TEXT_SIZE
    put(image, ENTRY, ENTRY_PATTERN)
    callers = []
    for i, site in enumerate(CALLS, start=1):
        pattern = call_pattern(site, REL32[site], i)
        put(image, site, pattern)
        callers.append({
            "caller_id": i, "call_rva": site, "return_rva": site + 5,
            "caller_entry_rva": site - 0x10, "allowed": i <= 4,
            "pattern_hex": pattern.hex(" "),
        })
    data = bytes(image)
    manifest = {
        "schema_version": 1,
        "manifest_source_sha256": "0" * 64,
        "executable_sha256": hashlib.sha256(data).hexdigest(),
        "text_section": {"virtual_address": TEXT_VA, "virtual_size": TEXT_SIZE,
                         "raw_pointer": TEXT_RAW, "raw_size": TEXT_SIZE},
        "entry_rva": ENTRY,
        "entry_pattern_hex": ENTRY_PATTERN.hex(" "),
        "callers": callers,
    }
    return data, manifest


def rehash(image: bytes | bytearray, manifest: dict) -> tuple[bytes, dict]:
    data = bytes(image)
    manifest = copy.deepcopy(manifest)
    manifest["executable_sha256"] = hashlib.sha256(data).hexdigest()
    return data, manifest


def mutate_call_target(image: bytes, site: int, rel: int) -> bytearray:
    out = bytearray(image)
    struct.pack_into("<i", out, raw_of(site) + 1, rel)
    return out


class LocatorTests(unittest.TestCase):
    def setUp(self):
        self.mod = load_module()

    def test_mini_case_valid(self):
        image, m = mini_case()
        r = self.mod.verify_owned_image(image, m)
        self.assertEqual(r["schema_version"], 1)
        self.assertEqual(r["entry_match_count"], 1)
        self.assertEqual(len(r["callers"]), 6)
        self.assertEqual([c["call_destination_rva"] for c in r["callers"]], [ENTRY] * 6)
        self.assertEqual([c["return_rva"] for c in r["callers"]], [s + 5 for s in CALLS])
        self.assertEqual(sum(c["allowed"] for c in r["callers"]), 4)
        self.assertIs(r["static_only"], True)
        self.assertIs(r["caller_entry_rva_verified"], False)
        self.assertEqual(r["executable_sha256"], m["executable_sha256"])

    def test_bad_hash(self):
        image, m = mini_case()
        m["executable_sha256"] = "1" * 64
        with self.assertRaisesRegex(ValueError, "sha256"):
            self.mod.verify_owned_image(image, m)

    def test_changed_call_is_rejected_after_hash_matches(self):
        image, m = mini_case()
        image, m = rehash(mutate_call_target(image, 0x1040, REL32[0x1040] + 1), m)
        with self.assertRaisesRegex(ValueError, "signature"):
            self.mod.verify_owned_image(image, m)

    def test_changed_rel32_with_matching_pattern_hits_destination_gate(self):
        image, m = mini_case()
        mutated = mutate_call_target(image, 0x1040, REL32[0x1040] + 1)
        image, m = rehash(mutated, m)
        m["callers"][0]["pattern_hex"] = call_pattern(0x1040, REL32[0x1040] + 1, 1).hex(" ")
        with self.assertRaisesRegex(ValueError, "destination"):
            self.mod.verify_owned_image(image, m)

    def test_unsigned_rel32_is_not_accepted(self):
        # The valid mini case only has backward (negative rel32) calls; an
        # unsigned decode would put every destination above 4 GiB.
        image, m = mini_case()
        r = self.mod.verify_owned_image(image, m)
        self.assertEqual(r["callers"][5]["call_destination_rva"], 0x1020)
        flipped = (REL32[0x1060] & 0xFFFFFFFF) ^ 0x80000000
        rel = struct.unpack("<i", struct.pack("<I", flipped))[0]
        image, m = rehash(mutate_call_target(image, 0x1060, rel), m)
        m["callers"][1]["pattern_hex"] = call_pattern(0x1060, rel, 2).hex(" ")
        with self.assertRaisesRegex(ValueError, "destination"):
            self.mod.verify_owned_image(image, m)

    def test_duplicate_entry_signature(self):
        image, m = mini_case()
        dup = bytearray(image)
        put(dup, 0x1100, ENTRY_PATTERN)
        image, m = rehash(dup, m)
        with self.assertRaisesRegex(ValueError, "entry signature.*2"):
            self.mod.verify_owned_image(image, m)

    def test_duplicate_caller_signature(self):
        image, m = mini_case()
        dup = bytearray(image)
        put(dup, 0x1100, bytes.fromhex(m["callers"][3]["pattern_hex"].replace(" ", "")))
        image, m = rehash(dup, m)
        with self.assertRaisesRegex(ValueError, "caller 4 signature.*2"):
            self.mod.verify_owned_image(image, m)

    def test_entry_signature_at_wrong_rva(self):
        image, m = mini_case()
        m["entry_rva"] = 0x1021
        with self.assertRaisesRegex(ValueError, "entry signature"):
            self.mod.verify_owned_image(image, m)

    def test_truncated_pe(self):
        image, m = mini_case()
        for length in (0x10, 0x50, 0x150, 0x300):
            data, mm = rehash(image[:length], m)
            with self.subTest(length=length):
                with self.assertRaisesRegex(ValueError, "truncated|outside the input|outside input"):
                    self.mod.verify_owned_image(data, mm)

    def test_not_pe32_plus(self):
        image, m = mini_case()
        bad = bytearray(image)
        struct.pack_into("<H", bad, 0x58, 0x10B)
        data, mm = rehash(bad, m)
        with self.assertRaisesRegex(ValueError, "PE32\\+"):
            self.mod.verify_owned_image(data, mm)

    def test_raw_and_virtual_overflow(self):
        image, m = mini_case()
        cases = (
            # (field offset in section header, value, manifest key, message)
            (20, 0xFFFFFF00, "raw_pointer", "raw range"),
            (16, 0xFFFFFFF0, "raw_size", "raw range"),
            (12, 0xFFFFFF00, "virtual_address", "virtual range"),
        )
        for offset, value, key, message in cases:
            with self.subTest(key=key):
                bad = bytearray(image)
                struct.pack_into("<I", bad, SECTION_HEADER + offset, value)
                data, mm = rehash(bad, m)
                mm["text_section"][key] = value
                with self.assertRaisesRegex(ValueError, message):
                    self.mod.verify_owned_image(data, mm)

    def test_section_metadata_must_match_manifest(self):
        image, m = mini_case()
        m["text_section"]["raw_size"] = 0x1F0
        with self.assertRaisesRegex(ValueError, "\\.text"):
            self.mod.verify_owned_image(image, m)

    def test_changed_return_rva(self):
        image, m = mini_case()
        m["callers"][2]["return_rva"] += 1
        with self.assertRaisesRegex(ValueError, "return"):
            self.mod.verify_owned_image(image, m)

    def test_out_of_text(self):
        image, m = mini_case()
        m["callers"][0]["call_rva"] = 0x2000
        m["callers"][0]["return_rva"] = 0x2005
        with self.assertRaisesRegex(ValueError, "outside \\.text"):
            self.mod.verify_owned_image(image, m)

    def test_zero_fill_is_not_file_backed(self):
        image, m = mini_case()
        bad = bytearray(image)
        struct.pack_into("<I", bad, SECTION_HEADER + 8, 0x300)  # VirtualSize > SizeOfRawData
        data, mm = rehash(bad, m)
        mm["text_section"]["virtual_size"] = 0x300
        mm["callers"][0]["call_rva"] = 0x1250
        mm["callers"][0]["return_rva"] = 0x1255
        with self.assertRaisesRegex(ValueError, "file-backed"):
            self.mod.verify_owned_image(data, mm)

    def test_cli_has_no_manifest_or_hash_override(self):
        r = subprocess.run([sys.executable, str(TOOL), "--help"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0)
        for forbidden in ("--manifest", "--sha", "--hash", "--expected"):
            self.assertNotIn(forbidden, r.stdout)

    def test_same_input_output_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "victoria3.exe"
            p.write_bytes(b"MZ-not-really")
            alias = Path(tmp) / "sub" / ".." / "victoria3.exe"
            (Path(tmp) / "sub").mkdir()
            r = subprocess.run([sys.executable, str(TOOL), str(p), "--output", str(alias)],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 2)
            self.assertIn("same path", r.stderr)
            self.assertEqual(p.read_bytes(), b"MZ-not-really")

    def test_output_inside_directory_input_rejected(self):
        # read_input resolves <dir>/binaries/victoria3.exe; an output at that
        # member (or anywhere under the game directory) must be refused.
        with tempfile.TemporaryDirectory() as tmp:
            game = Path(tmp) / "game"
            (game / "binaries").mkdir(parents=True)
            exe = game / "binaries" / "victoria3.exe"
            exe.write_bytes(b"MZ-not-really")
            for out in (exe, game / "locator.json"):
                r = subprocess.run([sys.executable, str(TOOL), str(game), "--output", str(out)],
                                   capture_output=True, text=True)
                self.assertEqual(r.returncode, 2)
                self.assertIn("inside the input directory", r.stderr)
            self.assertEqual(exe.read_bytes(), b"MZ-not-really")
            self.assertFalse((game / "locator.json").exists())

    def test_hard_link_output_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "victoria3.exe"
            p.write_bytes(b"MZ-not-really")
            link = Path(tmp) / "out" / "locator.json"
            link.parent.mkdir()
            try:
                os.link(p, link)
            except OSError as exc:
                self.skipTest(f"hard links unavailable: {exc}")
            r = subprocess.run([sys.executable, str(TOOL), str(p), "--output", str(link)],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 2)
            self.assertIn("same file", r.stderr)
            self.assertEqual(p.read_bytes(), b"MZ-not-really")

    def test_failed_validation_does_not_write_output(self):
        image, _ = mini_case()
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "victoria3.exe"
            p.write_bytes(image)
            out = Path(tmp) / "locator.json"
            r = subprocess.run([sys.executable, str(TOOL), str(p), "--output", str(out)],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 2)
            self.assertIn("sha256", r.stderr)
            self.assertFalse(out.exists())

    def test_exact_input_optional(self):
        data = os.environ.get("VIC3_DATA")
        if not data:
            self.skipTest("VIC3_DATA is not set; exact-build locator not exercised")
        r = self.mod.verify_exact_input(Path(data))
        self.assertEqual(r["executable_sha256"], EXE_SHA)
        self.assertEqual(r["entry_rva"], 0xF3E040)
        self.assertEqual(r["entry_match_count"], 1)
        self.assertEqual([c["call_rva"] for c in r["callers"] if c["allowed"]],
                         [0x13b8632, 0x10b7db4, 0x10bd565, 0x10bd66b])
        self.assertEqual([c["call_rva"] for c in r["callers"] if not c["allowed"]],
                         [0x13b847c, 0xc6b5ca])
        self.assertEqual([c["call_destination_rva"] for c in r["callers"]], [0xF3E040] * 6)
        self.assertIs(r["static_only"], True)


if __name__ == "__main__":
    unittest.main()
