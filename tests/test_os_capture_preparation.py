"""Prepared evidence must never be partially overwritten by a rejected rerun."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]


class PreparationOutputTests(unittest.TestCase):
    def test_rejected_generation_preserves_existing_catalog_and_files(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            (output / 'run-templates').mkdir()
            (output / 'run-templates' / 'keep.txt').write_bytes(b'keep')
            (output / 'native-region-catalog.json').write_bytes(b'preserved catalog bytes')
            before = {p.relative_to(output).as_posix(): p.read_bytes()
                      for p in output.rglob('*') if p.is_file()}
            result = subprocess.run(
                [sys.executable, str(REPO / 'research/generated/os-capture-preparation-2026-10-05/generation-source.py.txt'),
                 '--repo', str(REPO), '--output', str(output)], capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            after = {p.relative_to(output).as_posix(): p.read_bytes()
                     for p in output.rglob('*') if p.is_file()}
            self.assertEqual(before, after)


if __name__ == '__main__':
    unittest.main()
