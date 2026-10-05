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
DB_PATH = ROOT / "research" / "native-profiler-runtime-targets-1.14.5.json"
INC_PATH = ROOT / "src" / "native" / "generated" / "targets_1_14_5.inc"
TOOL = ROOT / "tools" / "render_native_profiler_targets.py"

EXPECTED_CANONICAL = (
    '[{"kind":"ticktask_tail_anchor","name":"HandleAutonomousInvestment",'
    '"ranges":[{"begin_rva":"0xf6e590","end_rva":"0xf6e7a3"}],"target_id":1},'
    '{"kind":"ticktask_tail_anchor","name":"ProcessEconomicMigration",'
    '"ranges":[{"begin_rva":"0x11b0c00","end_rva":"0x11b0dde"}],"target_id":2},'
    '{"kind":"ticktask_tail_anchor","name":"UpdateEmployment",'
    '"ranges":[{"begin_rva":"0x13b8310","end_rva":"0x13b853b"}],"target_id":3}]'
)
EXPECTED_TABLE_SHA256 = "ccc665fb9462659e166f596827aeff5c9d0c1f33c2986a3e8f750b83f690e24f"
EXPECTED_EXE_SHA256 = "9b6f133a5dc235de9135d7b57e86ceda8282d1ba6c0e185f3ee19c22f8917f54"


def load_module():
    spec = importlib.util.spec_from_file_location("render_native_profiler_targets", TOOL)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


class RenderTargetsTests(unittest.TestCase):
    def setUp(self):
        self.mod = load_module()
        self.raw = json.loads(DB_PATH.read_text(encoding="utf-8"))

    def test_pins_three_targets_and_exact_signatures(self):
        db = self.mod.validate_database(self.raw)
        got = [(t["target_id"], t["runtime_task"], t["offset_from_function_start"], bytes(t["pattern"]))
               for t in db["targets"]]
        self.assertEqual(got, [
            (1, "HandleAutonomousInvestment", 29, bytes.fromhex("0000488b4208488bf24c8bf9")),
            (2, "ProcessEconomicMigration", 3, bytes.fromhex("4881ecb80000004889580848")),
            (3, "UpdateEmployment", 20, bytes.fromhex("415641574883ec60488b4208")),
        ])
        self.assertEqual(db["executable_sha256"], EXPECTED_EXE_SHA256)

    def test_canonical_target_json_and_table_hash(self):
        db = self.mod.validate_database(self.raw)
        canonical = self.mod.canonical_target_bytes(db)
        self.assertEqual(canonical.decode("utf-8"), EXPECTED_CANONICAL)
        self.assertEqual(hashlib.sha256(canonical).hexdigest(), EXPECTED_TABLE_SHA256)

    def test_rendered_include_contains_constants_and_provenance(self):
        text = self.mod.render(self.mod.validate_database(self.raw))
        self.assertIn("research/native-profiler-runtime-targets-1.14.5.json", text)
        self.assertIn(EXPECTED_EXE_SHA256, text)
        self.assertIn(EXPECTED_TABLE_SHA256, text)
        self.assertIn("DO NOT EDIT", text)
        self.assertIn("0x9b, 0x6f, 0x13, 0x3a", text)
        self.assertIn("0x00, 0x00, 0x48, 0x8b, 0x42, 0x08, 0x48, 0x8b, 0xf2, 0x4c, 0x8b, 0xf9", text)
        self.assertIn("0x4558d98", text)
        self.assertIn(json.dumps(EXPECTED_CANONICAL), text)

    def test_render_is_deterministic_and_committed_include_is_current(self):
        db = self.mod.validate_database(self.raw)
        first = self.mod.render(db)
        second = self.mod.render(self.mod.validate_database(json.loads(DB_PATH.read_text(encoding="utf-8"))))
        self.assertEqual(first, second)
        self.assertEqual(INC_PATH.read_bytes(), first.encode("utf-8"))

    def test_cli_check_mode(self):
        ok = subprocess.run([sys.executable, str(TOOL), "--check"], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(ok.returncode, 0, ok.stderr)
        with tempfile.TemporaryDirectory() as td:
            stale = Path(td) / "stale.inc"
            stale.write_text("// stale\n", encoding="utf-8")
            bad = subprocess.run([sys.executable, str(TOOL), "--output", str(stale), "--check"],
                                 cwd=ROOT, capture_output=True, text=True)
            self.assertNotEqual(bad.returncode, 0)
            self.assertEqual(stale.read_text(encoding="utf-8"), "// stale\n")

    def _reject(self, mutate, message):
        raw = copy.deepcopy(self.raw)
        mutate(raw)
        with self.assertRaisesRegex(ValueError, message):
            self.mod.validate_database(raw)

    def test_rejects_duplicate_target_id(self):
        self._reject(lambda r: r["targets"][1].__setitem__("target_id", 1), "duplicate target_id")

    def test_rejects_zero_target_id(self):
        self._reject(lambda r: r["targets"][0].__setitem__("target_id", 0), "target_id")

    def test_rejects_invalid_hex_range(self):
        self._reject(lambda r: r["targets"][0]["ranges"][0].__setitem__("end_rva", "0xzz"), "range")
        self._reject(lambda r: r["targets"][0]["ranges"][0].__setitem__("end_rva", "0xf6e590"), "range")
        self._reject(lambda r: r["targets"][0]["ranges"][0].__setitem__("begin_rva", "f6e590"), "range")

    def test_rejects_non_unique_declared_match_count(self):
        self._reject(lambda r: r["targets"][2].__setitem__("match_count_in_text", 2), "match_count_in_text")
        self._reject(lambda r: r["signature_policy"].__setitem__("expected_match_count", 2), "expected_match_count")

    def test_rejects_unsupported_slot_index(self):
        self._reject(lambda r: r["targets"][0].__setitem__("vtable_slot_index", 5), "vtable_slot_index")
        self._reject(lambda r: r["dispatcher_abi"].__setitem__("vtable_slot_index", 7), "vtable_slot_index")

    def test_rejects_inconsistent_signature_offset(self):
        self._reject(lambda r: r["targets"][0].__setitem__("offset_from_function_start", 28), "offset_from_function_start")

    def test_rejects_short_or_malformed_pattern(self):
        self._reject(lambda r: r["targets"][0].__setitem__("pattern_hex", "48 8b"), "pattern")
        self._reject(lambda r: r["targets"][0].__setitem__("pattern_hex", "00 00 48 8b 42 08 48 8b f2 4c 8b ??"), "pattern")

    def test_rejects_function_outside_declared_range(self):
        def mutate(r):
            r["targets"][0]["ranges"] = [{"begin_rva": "0xf6e591", "end_rva": "0xf6e7a3"}]
        self._reject(mutate, "function_rva")

    def test_rejects_wrong_executable_hash_or_prototype(self):
        self._reject(lambda r: r.__setitem__("executable_sha256", "0" * 64), "executable_sha256")
        self._reject(lambda r: r["dispatcher_abi"].__setitem__("prototype", "int(void*)"), "prototype")

    def test_rejects_target_set_other_than_three_pinned(self):
        self._reject(lambda r: r["targets"].pop(), "targets")


if __name__ == "__main__":
    unittest.main()
