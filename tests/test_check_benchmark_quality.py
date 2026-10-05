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
