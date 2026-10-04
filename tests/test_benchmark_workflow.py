from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


PREP = load("prepare_benchmark_matrix", ROOT / "tools" / "prepare_benchmark_matrix.py")
FIN = load("finalize_benchmark_run", ROOT / "tools" / "finalize_benchmark_run.py")


class WorkflowTests(unittest.TestCase):
    def test_default_shape(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "runs"
            matrix = PREP.create_matrix(
                root,
                variant="vanilla",
                threads=[1, 2, 4, 6, 8, 12, 16],
                repeats=3,
                include_warmup=True,
                start_date="1900-01-01",
                end_date="1901-01-01",
                save_filename="heavy.v3",
                save_sha256="a" * 64,
                country="JAP",
                cpu="AMD Ryzen 7 9700X",
            )
            self.assertEqual(matrix["run_count"], 28)
            self.assertTrue((root / "vanilla-t16-r03" / "manifest.template.json").is_file())
            manifest = json.loads(
                (root / "vanilla-t08-r02" / "manifest.template.json").read_text(encoding="utf-8")
            )
            self.assertEqual(manifest["task_thread_count"], 8)
            self.assertIsNone(manifest["wall_clock_seconds"])

    def test_nonempty_output_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "runs"
            root.mkdir()
            (root / "keep.txt").write_text("x", encoding="utf-8")
            with self.assertRaises(PREP.Error):
                PREP.create_matrix(
                    root,
                    variant="vanilla",
                    threads=[1],
                    repeats=1,
                    include_warmup=False,
                    start_date=None,
                    end_date=None,
                    save_filename=None,
                    save_sha256=None,
                    country=None,
                    cpu=None,
                )

    def test_finalize_hashes_csv(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "runs"
            PREP.create_matrix(
                root,
                variant="vanilla",
                threads=[4],
                repeats=1,
                include_warmup=False,
                start_date="1900-01-01",
                end_date="1901-01-01",
                save_filename=None,
                save_sha256=None,
                country=None,
                cpu=None,
            )
            run = root / "vanilla-t04-r01"
            csv_path = run / "ticktask_timings.csv"
            csv_path.write_text(
                "frame,task,milliseconds,calls,longest_lock\n"
                "1,CTickTask_A,10,2,1\n",
                encoding="utf-8",
            )
            manifest = FIN.finalize(run, 12.5, "ok")
            self.assertEqual(manifest["wall_clock_seconds"], 12.5)
            self.assertEqual(manifest["capture"]["ticktask_csv_rows"], 1)
            self.assertEqual(len(manifest["capture"]["ticktask_csv_sha256"]), 64)
            self.assertTrue((run / "manifest.json").is_file())

    def test_finalize_rejects_bad_csv(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "runs"
            PREP.create_matrix(
                root,
                variant="vanilla",
                threads=[4],
                repeats=1,
                include_warmup=False,
                start_date=None,
                end_date=None,
                save_filename=None,
                save_sha256=None,
                country=None,
                cpu=None,
            )
            run = root / "vanilla-t04-r01"
            (run / "ticktask_timings.csv").write_text(
                "frame,task,milliseconds,calls\n1,A,1,1\n", encoding="utf-8"
            )
            with self.assertRaises(FIN.Error):
                FIN.finalize(run, 10.0)


if __name__ == "__main__":
    unittest.main()
