import hashlib
import struct
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import native_profiler_format as mod

SHA='9b6f133a5dc235de9135d7b57e86ceda8282d1ba6c0e185f3ee19c22f8917f54'
BUILD_IDS={'caligula_branch':'release/1.14.5','caligula_rev':'9f8281a37e85639359b3b0c2c5df0196e975ca4b','clausewitz_branch':'caligula/release/1.14.x','clausewitz_rev':'fd5e1dbd038c3c4a3f48a36abf60ebb42dd0ceef'}
META={'build_ids':BUILD_IDS,'profiler_build_id':'synthetic-reference-v1','targets':[{'target_id':1,'name':'fixture','kind':'synthetic','ranges':[{'begin_rva':'0x1000','end_rva':'0x1100'}]}]}


def events():
    common={'timestamp_qpc':100,'thread_id':7,'target_id':1,'sequence':1,'correlation_id':42}
    return [dict(common,event_type=1),dict(common,event_type=2,status_flags=9),dict(common,event_type=3,range_begin=10,range_end=20,range_length=10,task_thread_count=16,decision=2,reason_flags=3,chunk_or_work_count=4),dict(common,event_type=4,wait_kind=2,object_token=99),dict(common,event_type=5,result_flags=8),dict(common,event_type=6,target_id=0,counter_id=5,value=-3)]


class FormatTests(unittest.TestCase):
    def header(self,**kw):
        return mod.encode_header(META,qpc_frequency=1000,session_start_qpc=90,executable_sha256=SHA,signature_db_version=1,**kw)

    def test_header_offsets_hash_and_alignment(self):
        h=self.header(total_dropped_events=12)
        self.assertEqual(h[:4],b'V3PF');self.assertEqual(struct.unpack_from('<HH',h,4),(1,len(h)))
        self.assertEqual(h[8:16],b'\x08'+b'\0'*7)
        self.assertEqual(struct.unpack_from('<QQ',h,16),(1000,90))
        self.assertEqual(h[32:64],bytes.fromhex(SHA));self.assertEqual(struct.unpack_from('<I',h,64)[0],1)
        target_bytes=b'[{"kind":"synthetic","name":"fixture","ranges":[{"begin_rva":"0x1000","end_rva":"0x1100"}],"target_id":1}]'
        self.assertEqual(mod.canonical_target_bytes(META['targets']),target_bytes)
        self.assertEqual(h[68:100],hashlib.sha256(target_bytes).digest())
        self.assertEqual(struct.unpack_from('<IQ',h,100),(0,12));self.assertEqual(len(h)%8,0)
        self.assertTrue(h[112:].rstrip(b'\0').startswith(b'{'))
        self.assertEqual(h,self.header(total_dropped_events=12))

    def test_golden_payload_for_every_known_type(self):
        records=[mod.encode_event(e) for e in events()]
        self.assertEqual([len(r) for r in records],[32,40,72,48,40,40])
        self.assertEqual(records[0],bytes.fromhex('6400000000000000070000000100200001000000010000002a00000000000000'))
        self.assertEqual(records[1][24:],bytes.fromhex('2a000000000000000900000000000000'))
        self.assertEqual(records[2][24:],bytes.fromhex('2a000000000000000a0000000000000014000000000000000a0000000000000010000200030000000400000000000000'))
        self.assertEqual(records[3][24:],bytes.fromhex('2a0000000000000002000000000000006300000000000000'))
        self.assertEqual(records[4][24:],bytes.fromhex('2a000000000000000800000000000000'))
        self.assertEqual(records[5][24:],bytes.fromhex('0500000000000000fdffffffffffffff'))
        for r in records:self.assertEqual(struct.unpack_from('<H',r,14)[0],len(r))
        h=self.header();self.assertEqual(mod.encode_trace(h,records),h+b''.join(records))

    def test_reject_bad_metadata_and_numeric_layout(self):
        with self.assertRaises(ValueError):mod.encode_header({},qpc_frequency=1,session_start_qpc=0,executable_sha256=SHA,signature_db_version=1)
        with self.assertRaises(ValueError):mod.encode_header(META,qpc_frequency=0,session_start_qpc=0,executable_sha256=SHA,signature_db_version=1)
        with self.assertRaises(ValueError):mod.encode_header(META,qpc_frequency=1,session_start_qpc=0,executable_sha256='0'*64,signature_db_version=1)
        with self.assertRaises(ValueError):mod.encode_event(dict(events()[0],thread_id=-1))
        with self.assertRaises(ValueError):mod.encode_event(dict(events()[2],decision=3))
        with self.assertRaises(ValueError):mod.encode_event(dict(events()[2],range_length=9))
