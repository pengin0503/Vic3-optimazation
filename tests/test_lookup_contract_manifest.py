"""Tests for tools/render_lookup_contract_manifest.py (B0 Task 1).

Expected values are literals copied from the approved B0 spec section 3, not
derived from the renderer itself.
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "render_lookup_contract_manifest.py"
EVIDENCE = ROOT / "research" / "generated" / "native-shadow-preparation-2026-10-07" / "static-evidence.json"
INDEX = ROOT / "research" / "generated" / "native-shadow-preparation-2026-10-07" / "artifact-index.json"
INC = ROOT / "src" / "lookup_reuse_contract" / "generated" / "manifest_1_14_5.inc"

EXE_SHA = "9b6f133a5dc235de9135d7b57e86ceda8282d1ba6c0e185f3ee19c22f8917f54"
SOURCE_SHA = "3e37e77f0a2600120046282c03775d2322787fec0f66613c47c2cc7f020929aa"
ENTRY_PATTERN = "4c 8b 51 30 4c 8b c9 4c 63 59 3c 0f b6 c2"
EXPECTED_CALLERS = [
    # caller_id, call, return, caller entry, allowed
    (1, 0x13b8632, 0x13b8637, 0x13b8540, True),
    (2, 0x10b7db4, 0x10b7db9, 0x10b7c60, True),
    (3, 0x10bd565, 0x10bd56a, 0x10bd490, True),
    (4, 0x10bd66b, 0x10bd670, 0x10bd490, True),
    (5, 0x13b847c, 0x13b8481, 0x13b8310, False),
    (6, 0xc6b5ca, 0xc6b5cf, 0xc6b4d0, False),
]


def load_module():
    spec = importlib.util.spec_from_file_location("render_lookup_contract_manifest", TOOL)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


class ManifestTests(unittest.TestCase):
    def setUp(self):
        self.mod = load_module()
        self.evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
        self.source_sha = hashlib.sha256(EVIDENCE.read_bytes()).hexdigest()

    def test_source_sha_matches_artifact_index(self):
        self.assertEqual(self.source_sha, SOURCE_SHA)
        evidence, sha = self.mod.load_source(EVIDENCE, INDEX)
        self.assertEqual(sha, SOURCE_SHA)
        self.assertEqual(evidence, self.evidence)

    def test_index_sha_or_size_mismatch_is_rejected(self):
        index = json.loads(INDEX.read_text(encoding="utf-8"))
        for field, value in (("sha256", "0" * 64), ("size_bytes", 1)):
            bad = copy.deepcopy(index)
            for f in bad["files"]:
                if f["path"].endswith("static-evidence.json"):
                    f[field] = value
            with tempfile.TemporaryDirectory() as tmp:
                p = Path(tmp) / "artifact-index.json"
                p.write_text(json.dumps(bad), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "artifact index"):
                    self.mod.load_source(EVIDENCE, p)

    def test_manifest_pins_entry_hash_and_pattern(self):
        m = self.mod.derive_manifest(self.evidence, self.source_sha)
        self.assertEqual(m["schema_version"], 1)
        self.assertEqual(m["manifest_source_sha256"], SOURCE_SHA)
        self.assertEqual(m["executable_sha256"], EXE_SHA)
        self.assertEqual(m["entry_rva"], 0xF3E040)
        self.assertEqual(m["entry_pattern_hex"], ENTRY_PATTERN)
        self.assertEqual(m["text_section"], {
            "virtual_address": 4096, "virtual_size": 70799024,
            "raw_pointer": 1024, "raw_size": 70799360,
        })

    def test_manifest_keeps_four_allowed_two_excluded(self):
        m = self.mod.derive_manifest(self.evidence, self.source_sha)
        self.assertEqual([c["call_rva"] for c in m["callers"] if c["allowed"]],
                         [0x13b8632, 0x10b7db4, 0x10bd565, 0x10bd66b])
        self.assertEqual([c["call_rva"] for c in m["callers"] if not c["allowed"]],
                         [0x13b847c, 0xc6b5ca])

    def test_caller_ids_returns_and_metadata_root_begin(self):
        m = self.mod.derive_manifest(self.evidence, self.source_sha)
        got = [(c["caller_id"], c["call_rva"], c["return_rva"], c["caller_entry_rva"], c["allowed"])
               for c in m["callers"]]
        self.assertEqual(got, EXPECTED_CALLERS)
        for c in m["callers"]:
            self.assertEqual(c["return_rva"], c["call_rva"] + 5)
            self.assertTrue(c["pattern_hex"].startswith("e8 "))
        self.assertEqual(m["callers"][0]["pattern_hex"], "e8 09 5a b8 ff 48 8b 18 48 63 40 0c")

    def test_schema_change_is_rejected(self):
        bad = copy.deepcopy(self.evidence)
        bad["schema_version"] = 2
        with self.assertRaisesRegex(ValueError, "schema_version"):
            self.mod.derive_manifest(bad, self.source_sha)

    def test_unpinned_executable_hash_is_rejected(self):
        bad = copy.deepcopy(self.evidence)
        bad["executable_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "executable_sha256"):
            self.mod.derive_manifest(bad, self.source_sha)

    def test_missing_caller_is_rejected(self):
        bad = copy.deepcopy(self.evidence)
        del bad["verified_callers"][2]
        with self.assertRaisesRegex(ValueError, "allowed"):
            self.mod.derive_manifest(bad, self.source_sha)

    def test_duplicate_caller_is_rejected(self):
        bad = copy.deepcopy(self.evidence)
        bad["verified_callers"][1] = copy.deepcopy(bad["verified_callers"][0])
        with self.assertRaisesRegex(ValueError, "duplicate"):
            self.mod.derive_manifest(bad, self.source_sha)

    def test_allowlist_flag_must_be_bool(self):
        bad = copy.deepcopy(self.evidence)
        bad["verified_callers"][0]["future_candidate_allowlist"] = 1
        with self.assertRaisesRegex(ValueError, "bool"):
            self.mod.derive_manifest(bad, self.source_sha)

    def test_inconsistent_call_bytes_are_rejected(self):
        bad = copy.deepcopy(self.evidence)
        bad["verified_callers"][0]["return_rva"] = "0x13b8638"
        with self.assertRaisesRegex(ValueError, "return_rva"):
            self.mod.derive_manifest(bad, self.source_sha)
        bad = copy.deepcopy(self.evidence)
        bad["verified_callers"][0]["call_bytes"] = "e8095ab8fe"
        with self.assertRaisesRegex(ValueError, "rel32"):
            self.mod.derive_manifest(bad, self.source_sha)

    def test_entry_signature_must_match_excerpt(self):
        bad = copy.deepcopy(self.evidence)
        bad["entry_signature"]["pattern_hex"] = "4c 8b 51 31 4c 8b c9 4c 63 59 3c 0f b6 c2"
        with self.assertRaisesRegex(ValueError, "entry"):
            self.mod.derive_manifest(bad, self.source_sha)

    def test_rendering_is_deterministic_and_carries_ids(self):
        m = self.mod.derive_manifest(self.evidence, self.source_sha)
        a = self.mod.render_manifest(m)
        b = self.mod.render_manifest(copy.deepcopy(m))
        self.assertEqual(a, b)
        self.assertIn("namespace lookup_contract::generated", a)
        self.assertIn("{1, 0x13b8632, 0x13b8637, 0x13b8540, true}", a)
        self.assertIn("{6, 0xc6b5ca, 0xc6b5cf, 0xc6b4d0, false}", a)
        self.assertIn(f'kManifestSourceSha256[] = "{SOURCE_SHA}"', a)
        self.assertNotIn("\r", a)

    def test_committed_include_is_current(self):
        r = subprocess.run([sys.executable, str(TOOL), "--check"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(INC.read_bytes(),
                         self.mod.render_manifest(self.mod.derive_manifest(self.evidence, self.source_sha)).encode())

    def test_stale_check_fails_without_writing(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "manifest.inc"
            out.write_text("// stale\n", encoding="utf-8")
            r = subprocess.run([sys.executable, str(TOOL), "--check", "--output", str(out)],
                               capture_output=True, text=True)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("stale", r.stderr)
            self.assertEqual(out.read_text(encoding="utf-8"), "// stale\n")


if __name__ == "__main__":
    unittest.main()
