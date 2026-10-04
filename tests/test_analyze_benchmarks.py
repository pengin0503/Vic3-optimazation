from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("analyze_benchmarks", ROOT / "tools" / "analyze_benchmarks.py")
mod = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = mod
assert SPEC.loader is not None
SPEC.loader.exec_module(mod)

CSV = """frame,task,milliseconds,calls,longest_lock
1,CTickTask_A,10,2,1
1,CTickTask_B,3,1,0.1
2,CTickTask_A,12,2,2
2,CTickTask_B,4,1,0.2
"""

def make_run(root: Path, run_id: str, threads: int, wall: float, repeat: int, variant: str = "vanilla"):
    run = root / run_id
    run.mkdir()
    (run / "ticktask_timings.csv").write_text(CSV, encoding="utf-8")
    manifest = {
        "format_version": 1,
        "run_id": run_id,
        "variant": variant,
        "repeat": repeat,
        "warmup": False,
        "task_thread_count": threads,
        "wall_clock_seconds": wall,
        "ticktask_csv": "ticktask_timings.csv",
        "game_speed": 5,
        "start_date": "1900-01-01",
        "end_date": "1901-01-01",
    }
    (run / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

class BenchmarkTests(unittest.TestCase):
    def test_aggregates_cost_lock_and_scaling(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            make_run(root, "t1-r1", 1, 40.0, 1)
            make_run(root, "t1-r2", 1, 40.4, 2)
            make_run(root, "t4-r1", 4, 20.0, 1)
            make_run(root, "t4-r2", 4, 20.2, 2)
            runs = [mod.load_run(p) for p in mod.discover_manifests(root)]
            report = mod.build_report(runs, 0.03)
            self.assertEqual(report["run_count"], 4)
            scaling = {(x["variant"], x["task_thread_count"]): x for x in report["scaling"]}
            self.assertAlmostEqual(scaling[("vanilla", 4)]["speedup_vs_1_thread"], 2.0, places=1)
            group = next(g for g in report["groups"] if g["task_thread_count"] == 1)
            self.assertEqual(group["tasks_by_cost"][0]["task"], "CTickTask_A")
            self.assertEqual(group["tasks_by_lock"][0]["task"], "CTickTask_A")
            self.assertAlmostEqual(group["tasks_by_cost"][0]["mean_total_ms"], 22.0)

    def test_noisy_runs_are_flagged(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            make_run(root, "r1", 4, 10.0, 1)
            make_run(root, "r2", 4, 20.0, 2)
            runs = [mod.load_run(p) for p in mod.discover_manifests(root)]
            report = mod.build_report(runs, 0.03)
            self.assertTrue(report["groups"][0]["wall_clock_seconds"]["noisy"])

    def test_missing_csv_column_fails(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "bad.csv"
            p.write_text("frame,task,milliseconds,calls\n1,A,1,1\n", encoding="utf-8")
            with self.assertRaises(mod.BenchmarkError):
                mod.load_ticktask_csv(p)

if __name__ == "__main__":
    unittest.main()
