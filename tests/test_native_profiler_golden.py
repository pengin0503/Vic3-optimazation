import hashlib
import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from parse_native_profiler_trace import parse_trace

ROOT=Path(__file__).resolve().parents[1]
GOLDEN=ROOT/'research/generated/native-profiler-v1-golden'


class GoldenTests(unittest.TestCase):
    def test_committed_binary_matches_committed_json_without_regeneration(self):
        raw=(GOLDEN/'trace-v1.bin').read_bytes()
        expected=json.loads((GOLDEN/'trace-v1.json').read_text(encoding='utf-8'))
        parsed=parse_trace(raw)
        self.assertEqual(parsed,expected)
        self.assertTrue(parsed['header_valid']);self.assertTrue(parsed['segment_complete'])
        self.assertEqual(parsed['diagnostics'],[])
        self.assertEqual(parsed['summary']['record_count'],8)
        self.assertEqual(parsed['summary']['paired_functions'],2)
        self.assertEqual(parsed['summary']['paired_waits'],1)
        self.assertEqual([p['duration_qpc'] for p in parsed['pairs']],[5,18,30])
        self.assertEqual({e['thread_id'] for e in parsed['events']},{7,8})
        self.assertEqual([e['event_type'] for e in parsed['events']],[1,3,4,1,5,2,2,6])
        hashes=json.loads((GOLDEN/'artifact-index.json').read_text())
        for name in ('trace-v1.bin','trace-v1.json'):
            self.assertEqual(hashlib.sha256((GOLDEN/name).read_bytes()).hexdigest(),hashes[name])
