import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from offline_gpu_core import cpu_reference
from gpu_runtime import conduct, build_parser

class FakeExecutor:
    metadata={'device':'fake', 'backend':'FAKE - tests only'}
    def __init__(self): self.calls=[]
    def allocate(self, case): return object()
    def preload(self, buffers, case): self.calls.append('preload')
    def run_once(self, buffers, case, mode):
        self.calls.append(mode)
        return cpu_reference(case), {'e2e_wall_ms':1.0, 'h2d_bytes':0 if mode=='resident' else 10,
                                     'd2h_bytes':case['n']*4,'h2d_device_event_ms':0.1,
                                     'd2h_device_event_ms':0.1}

class RunnerTests(unittest.TestCase):
    def test_modes_and_metadata(self):
        exe=FakeExecutor()
        report=conduct(exe, [17], ['id_lookup'], ['colliding'], repeats=3, warmups=1, seed=1877)
        self.assertEqual(report['status'], 'measured')
        self.assertEqual(report['source'], 'synthetic_not_game')
        self.assertTrue(report['gpu_executed'])
        self.assertEqual(report['results'][0]['modes']['cold']['count'], 3)
        self.assertEqual(report['results'][0]['modes']['resident']['count'], 3)
        self.assertEqual(exe.calls, ['preload', 'cold','resident','cold','resident','resident','cold','cold','resident'])
        self.assertIn('cpu_samples',report['results'][0])

    def test_cli_invalid_inputs(self):
        p=build_parser()
        with self.assertRaises(SystemExit):
            p.parse_args(['--repeats','foo'])

    def test_fail_closed_without_device(self):
        if __import__('importlib').util.find_spec('pyopencl') is None:
            with tempfile.TemporaryDirectory() as d:
                dst=Path(d)/'failed.json'
                result=subprocess.run([sys.executable,'gpu_runtime.py','--sizes','8', '--output',str(dst)],capture_output=True,text=True)
                self.assertNotEqual(result.returncode,0)
                r=json.loads(dst.read_text('utf-8'))
                self.assertEqual(r['status'],'error')
                self.assertFalse(r['gpu_executed'])
                self.assertNotIn('results',r)

if __name__=='__main__': unittest.main()
