from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import tempfile
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load_module():
    path = ROOT / "tools" / "check_benchmark_quality.py"
    spec = importlib.util.spec_from_file_location("check_benchmark_quality", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def write_run(root: Path, run_id: str, *, threads: int, wall: float = 10.0,
              repeat: int | None = 1, warmup: bool = False,
              build_hash: str = "a" * 64, save_hash: str = "b" * 64,
              pop: str = "aggressive_consolidation", csv_text: str | None = None,
              csv_hash_override: str | None = None) -> Path:
    run = root / run_id
    run.mkdir(parents=True)
    csv_text = csv_text or "frame,task,milliseconds,calls,longest_lock\n1,CTickTask_A,1,1,0\n"
    csv_path = run / "ticktask_timings.csv"
    csv_path.write_text(csv_text, encoding="utf-8")
    digest = hashlib.sha256(csv_path.read_bytes()).hexdigest()
    manifest = {
        "run_id": run_id,
        "variant": "baseline",
        "task_thread_count": threads,
        "wall_clock_seconds": wall,
        "ticktask_csv": "ticktask_timings.csv",
        "repeat": repeat,
        "warmup": warmup,
        "build": {"victoria3_exe_sha256": build_hash},
        "save": {"sha256": save_hash},
        "game_rules": {"pop_consolidation": pop},
        "capture": {"ticktask_csv_sha256": csv_hash_override or digest},
    }
    (run / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return run


class QualityTests(unittest.TestCase):
    def setUp(self):
        self.mod = load_module()

    def test_accepts_consistent_complete_matrix(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "runs"
            write_run(root, "baseline-t04-r01", threads=4, repeat=1, wall=10.0)
            write_run(root, "baseline-t04-r02", threads=4, repeat=2, wall=10.1)
            write_run(root, "baseline-t04-r03", threads=4, repeat=3, wall=9.9)
            matrix = {
                "runs": [
                    {"run_id": f"baseline-t04-r0{i}", "task_thread_count": 4, "repeat": i, "warmup": False}
                    for i in (1, 2, 3)
                ]
            }
            matrix_path = Path(td) / "matrix.json"
            matrix_path.write_text(json.dumps(matrix), encoding="utf-8")
            report = self.mod.check(root, matrix_path=matrix_path)
            self.assertEqual(report["errors"], [])
            self.assertEqual(report["warnings"], [])
            self.assertTrue(report["valid"])

    def test_detects_duplicate_run_id_and_matrix_mismatch(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "runs"
            write_run(root / "a", "dup", threads=4)
            write_run(root / "b", "dup", threads=8)
            matrix = {"runs": [
                {"run_id": "dup", "task_thread_count": 4, "repeat": 1, "warmup": False},
                {"run_id": "missing", "task_thread_count": 8, "repeat": 1, "warmup": False},
            ]}
            matrix_path = Path(td) / "matrix.json"
            matrix_path.write_text(json.dumps(matrix), encoding="utf-8")
            report = self.mod.check(root, matrix_path=matrix_path)
            codes = {x["code"] for x in report["errors"]}
            self.assertIn("duplicate_run_id", codes)
            self.assertIn("missing_run", codes)

    def test_detects_identity_and_csv_hash_mismatch(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "runs"
            write_run(root, "r1", threads=4)
            write_run(root, "r2", threads=4, repeat=2, build_hash="c" * 64,
                      save_hash="d" * 64, pop="minor_consolidation",
                      csv_hash_override="0" * 64)
            report = self.mod.check(root)
            codes = {x["code"] for x in report["errors"]}
            self.assertIn("build_hash_mismatch", codes)
            self.assertIn("save_hash_mismatch", codes)
            self.assertIn("pop_consolidation_mismatch", codes)
            self.assertIn("csv_hash_mismatch", codes)

    def test_detects_warmup_contamination(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "runs"
            write_run(root, "warmup", threads=4, repeat=1, warmup=True)
            report = self.mod.check(root)
            codes = {x["code"] for x in report["errors"]}
            self.assertIn("warmup_has_repeat", codes)

    def test_flags_outlier_and_excessive_cv(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "runs"
            write_run(root, "r1", threads=8, repeat=1, wall=10.0)
            write_run(root, "r2", threads=8, repeat=2, wall=10.1)
            write_run(root, "r3", threads=8, repeat=3, wall=15.0)
            report = self.mod.check(root, cv_threshold=0.03, outlier_fraction=0.10)
            codes = {x["code"] for x in report["warnings"]}
            self.assertIn("excessive_cv", codes)
            self.assertIn("wall_clock_outlier", codes)
            self.assertFalse(report["valid_for_performance_claim"])

    def test_measured_run_without_wall_clock_is_not_performance_ready(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "runs"
            write_run(root, "r1", threads=8, repeat=1, wall=None)
            report = self.mod.check(root)
            codes = {x["code"] for x in report["errors"]}
            self.assertIn("missing_wall_clock", codes)
            self.assertFalse(report["valid"])
            self.assertFalse(report["valid_for_performance_claim"])

    def test_extra_frame_is_workload_boundary_mismatch(self):
        base = "frame,task,milliseconds,calls,longest_lock\n10,A,1,1,0\n10,B,2,3,0\n11,A,1,1,0\n"
        extended = base + "12,A,1,1,0\n"
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "runs"
            write_run(root, "r1", threads=12, repeat=1, wall=10.0, csv_text=base)
            write_run(root, "r2", threads=12, repeat=2, wall=10.0, csv_text=extended)
            write_run(root, "r3", threads=12, repeat=3, wall=10.0, csv_text=base)
            report = self.mod.check(root)
            mismatches = [w for w in report["warnings"] if w["code"] == "workload_boundary_mismatch"]
            self.assertEqual([w["run_id"] for w in mismatches], ["r2"])
            self.assertIn("frames 10..12", mismatches[0]["message"])
            self.assertIn("frames 10..11", mismatches[0]["message"])
            self.assertEqual(report["errors"], [])
            self.assertTrue(report["valid"])
            self.assertFalse(report["valid_for_performance_claim"])
            boundaries = {b["run_id"]: b for b in report["workload_boundaries"]}
            self.assertEqual(boundaries["r2"]["frame_count"], 3)
            self.assertEqual((boundaries["r2"]["min_frame"], boundaries["r2"]["max_frame"]), (10, 12))
            self.assertEqual(boundaries["r1"]["fingerprint_sha256"], boundaries["r3"]["fingerprint_sha256"])
            self.assertNotEqual(boundaries["r1"]["fingerprint_sha256"], boundaries["r2"]["fingerprint_sha256"])

    def test_same_row_count_different_frame_task_calls_is_mismatch(self):
        a = "frame,task,milliseconds,calls,longest_lock\n10,A,1,1,0\n11,B,1,2,0\n"
        b = "frame,task,milliseconds,calls,longest_lock\n10,A,1,1,0\n11,B,1,5,0\n"
        c = "frame,task,milliseconds,calls,longest_lock\n10,A,1,1,0\n11,C,1,2,0\n"
        d = "frame,task,milliseconds,calls,longest_lock\n10,A,1,1,0\n12,B,1,2,0\n"
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "runs"
            write_run(root, "r1", threads=8, repeat=1, csv_text=a)
            write_run(root, "r2", threads=8, repeat=2, csv_text=a)
            write_run(root, "r3", threads=8, repeat=3, csv_text=b)
            write_run(root, "r4", threads=8, repeat=4, csv_text=c)
            write_run(root, "r5", threads=8, repeat=5, csv_text=d)
            report = self.mod.check(root)
            flagged = sorted(w["run_id"] for w in report["warnings"] if w["code"] == "workload_boundary_mismatch")
            self.assertEqual(flagged, ["r3", "r4", "r5"])
            self.assertFalse(report["valid_for_performance_claim"])

    def test_timing_and_lock_columns_are_not_workload_identity(self):
        a = "frame,task,milliseconds,calls,longest_lock\n10,A,1,1,0\n11,B,1,2,0\n"
        b = "frame,task,milliseconds,calls,longest_lock\n11,B,9.5,2,4\n10,A,3,1,7\n"
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "runs"
            write_run(root, "r1", threads=8, repeat=1, wall=10.0, csv_text=a)
            write_run(root, "r2", threads=8, repeat=2, wall=10.1, csv_text=b)
            write_run(root, "r3", threads=8, repeat=3, wall=9.9, csv_text=a)
            report = self.mod.check(root)
            self.assertEqual(report["warnings"], [])
            self.assertTrue(report["valid_for_performance_claim"])
            prints = {b["fingerprint_sha256"] for b in report["workload_boundaries"]}
            self.assertEqual(len(prints), 1)

    def test_boundaries_compared_across_thread_groups(self):
        a = "frame,task,milliseconds,calls,longest_lock\n10,A,1,1,0\n"
        b = "frame,task,milliseconds,calls,longest_lock\n10,A,1,1,0\n11,A,1,1,0\n"
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "runs"
            for i in (1, 2, 3):
                write_run(root, f"t12-r{i}", threads=12, repeat=i, csv_text=a)
                write_run(root, f"t16-r{i}", threads=16, repeat=i, csv_text=b if i == 2 else a)
            report = self.mod.check(root)
            flagged = [w["run_id"] for w in report["warnings"] if w["code"] == "workload_boundary_mismatch"]
            self.assertEqual(flagged, ["t16-r2"])

    def test_deterministic_fingerprint_is_order_independent_multiset(self):
        rows = [(10, "A", 1), (10, "A", 1), (11, "B", 2)]
        first = self.mod.workload_fingerprint(rows)
        second = self.mod.workload_fingerprint(list(reversed(rows)))
        self.assertEqual(first, second)
        self.assertNotEqual(first, self.mod.workload_fingerprint(rows[1:]))
        self.assertEqual(first["frame_count"], 2)
        self.assertEqual(first["row_count"], 3)

    def test_unparseable_ticktask_csv_is_error(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "runs"
            write_run(root, "r1", threads=8, repeat=1,
                      csv_text="frame,task,milliseconds,calls,longest_lock\nx,A,1,1,0\n")
            report = self.mod.check(root)
            codes = {x["code"] for x in report["errors"]}
            self.assertIn("invalid_ticktask_csv", codes)
            self.assertFalse(report["valid"])

    def test_single_observation_is_repeatability_warning_not_error(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "runs"
            write_run(root, "r1", threads=16, repeat=1, wall=9.0)
            report = self.mod.check(root)
            self.assertEqual(report["errors"], [])
            codes = {x["code"] for x in report["warnings"]}
            self.assertIn("insufficient_repeats", codes)
            self.assertTrue(report["valid"])
            self.assertFalse(report["valid_for_performance_claim"])


if __name__ == "__main__":
    unittest.main()
