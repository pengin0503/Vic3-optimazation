import copy
import struct
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
sys.path.insert(0,str(Path(__file__).resolve().parent))
import native_profiler_format as fmt
import parse_native_profiler_trace as mod
from test_native_profiler_format import META,SHA,events


class ParserTests(unittest.TestCase):
    def trace(self,ev=None,**kw):
        h=fmt.encode_header(META,qpc_frequency=1000,session_start_qpc=90,executable_sha256=SHA,signature_db_version=1,**kw)
        e=events()[:2] if ev is None else ev
        if ev is None:e=[dict(e[0],sequence=5,timestamp_qpc=100),dict(e[1],sequence=6,timestamp_qpc=120)]
        return fmt.encode_trace(h,[fmt.encode_event(x) for x in e])

    def kinds(self,d):return [x['kind'] for x in d['diagnostics']]

    def test_valid_pair_drops_and_per_thread_order_not_global_sort(self):
        a,b=events()[:2]
        ev=[dict(a,sequence=10,timestamp_qpc=100),dict(a,thread_id=8,sequence=1,timestamp_qpc=95),dict(b,sequence=11,timestamp_qpc=130),dict(b,thread_id=8,sequence=2,timestamp_qpc=125)]
        d=mod.parse_trace(self.trace(ev,total_dropped_events=9),expected_executable_sha256=SHA)
        self.assertTrue(d['header_valid']);self.assertEqual(d['summary']['paired_functions'],2)
        self.assertEqual([e['timestamp_qpc'] for e in d['events']],[100,95,130,125])
        self.assertEqual([p['duration_qpc'] for p in d['pairs']],[30,30])
        self.assertEqual(d['summary']['dropped_events'],9);self.assertIn('dropped_events',self.kinds(d))

    def test_unknown_type_skipped_by_size_and_sequence_still_checked(self):
        raw=self.trace([]);raw+=struct.pack('<QIHHII',100,7,999,32,1,1)+b'12345678'
        raw+=fmt.encode_event(dict(events()[5],sequence=3,timestamp_qpc=101))
        d=mod.parse_trace(raw)
        self.assertEqual(len(d['events']),1);self.assertIn('unknown_event_type',self.kinds(d));self.assertIn('sequence_gap',self.kinds(d))
        self.assertEqual(d['summary']['record_count'],2)

    def test_truncation_alignment_and_known_short_payload_stop(self):
        raw=self.trace()
        d=mod.parse_trace(raw[:-1]);self.assertIn('truncated_record',self.kinds(d));self.assertEqual(len(d['events']),1)
        for size in (23,25,24):
            b=bytearray(raw);h=struct.unpack_from('<H',b,6)[0];struct.pack_into('<H',b,h+14,size)
            d=mod.parse_trace(bytes(b));self.assertIn('invalid_record_bytes',self.kinds(d));self.assertEqual(d['events'],[])

    def test_invalid_header_and_hash_fail_closed(self):
        for offset,value in ((4,2),(6,113),(8,4)):
            b=bytearray(self.trace());struct.pack_into('<H' if offset!=8 else '<B',b,offset,value)
            d=mod.parse_trace(bytes(b));self.assertFalse(d['header_valid']);self.assertEqual(d['events'],[])
        b=bytearray(self.trace());b[68]^=1
        d=mod.parse_trace(bytes(b));self.assertIn('target_table_hash_mismatch',self.kinds(d));self.assertEqual(d['events'],[])
        d=mod.parse_trace(self.trace(),expected_executable_sha256='0'*64);self.assertIn('build_mismatch',self.kinds(d));self.assertEqual(d['events'],[])
        b=bytearray(self.trace());b[32]^=1
        self.assertIn('build_mismatch',self.kinds(mod.parse_trace(bytes(b))))

    def test_never_pair_across_threads_targets_or_families(self):
        a,b=events()[:2]
        for change in ({'thread_id':8},{'event_type':5,'result_flags':0}):
            d=mod.parse_trace(self.trace([a,dict(b,sequence=2,timestamp_qpc=110,**change)]))
            self.assertEqual(d['pairs'],[]);self.assertIn('broken_begin_end',self.kinds(d))

    def test_duplicate_begin_sequence_gap_and_negative_pair_reported(self):
        a,b=events()[:2]
        d=mod.parse_trace(self.trace([a,dict(a,sequence=2),dict(b,sequence=4,timestamp_qpc=110)]))
        self.assertIn('sequence_gap',self.kinds(d));self.assertIn('broken_begin_end',self.kinds(d));self.assertEqual(d['pairs'],[])
        d=mod.parse_trace(self.trace([a,dict(b,sequence=2,timestamp_qpc=99)]))
        self.assertIn('invalid_timestamp',self.kinds(d));self.assertEqual(d['pairs'],[])

    def test_wait_pair_and_wraparound(self):
        a,b=events()[3:5]
        d=mod.parse_trace(self.trace([dict(a,sequence=0xffffffff),dict(b,sequence=0,timestamp_qpc=120)]))
        self.assertEqual(d['summary']['paired_waits'],1);self.assertNotIn('sequence_gap',self.kinds(d))

    def test_extensions_respected_without_shifting_following_record(self):
        h=self.trace([]);a=bytearray(fmt.encode_event(events()[0]));struct.pack_into('<H',a,14,40);a+=b'extended'
        b=fmt.encode_event(dict(events()[1],sequence=2,timestamp_qpc=120))
        d=mod.parse_trace(h+a+b);self.assertEqual(len(d['events']),2);self.assertEqual(len(d['pairs']),1)

    def test_invalid_metadata_and_unknown_target(self):
        raw=bytearray(self.trace());raw[9]=1
        self.assertFalse(mod.parse_trace(bytes(raw))['header_valid'])
        d=mod.parse_trace(self.trace([dict(events()[0],target_id=99)]))
        self.assertIn('unknown_target',self.kinds(d));self.assertEqual(d['pairs'],[])
