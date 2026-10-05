import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import correlate_os_profile as mod
SHA='9b6f133a5dc235de9135d7b57e86ceda8282d1ba6c0e185f3ee19c22f8917f54'


class CorrelationTests(unittest.TestCase):
    def fixture(self):
        r={'event_type':'cpu_sample','timestamp_ns':1,'thread_id':'7','module':'victoria3.exe','instruction_va':'0x140001010','module_base':'0x140000000','cpu_time_ns':100}
        p={'format_version':1,'run_id':'r1','executable_sha256':SHA,'source':'synthetic','source_filename':'x.csv','rows':[r]}
        c={'format_version':1,'module':'victoria3.exe','executable_sha256':SHA,'targets':[{'target_id':1,'name':'A','ranges':[{'begin_rva':'0x1000','end_rva':'0x1020'}]}]}
        return p,c

    def test_hit_aggregation_by_target_thread_and_event_preserves_absent_metrics(self):
        p,c=self.fixture();p['rows'] += [dict(p['rows'][0],cpu_time_ns=50),dict(p['rows'][0],thread_id='8',event_type='wait',wait_time_ns=25,duration_ns=30)]
        d=mod.correlate(p,c,expected_run_id='r1');self.assertEqual(d['matched_rows'],3)
        self.assertEqual(d['aggregates'][0]['count'],2);self.assertEqual(d['aggregates'][0]['cpu_time_ns'],150)
        self.assertNotIn('wait_time_ns',d['aggregates'][0]);self.assertEqual(d['aggregates'][1]['wait_time_ns'],25)
        self.assertIn('causal',mod.render_markdown(d))

    def test_half_open_range_no_hit_wrong_module_and_missing_base(self):
        p,c=self.fixture();p['rows']=[dict(p['rows'][0],instruction_va='0x140001020'),dict(p['rows'][0],module='other.dll'),{k:v for k,v in p['rows'][0].items() if k!='module_base'}]
        d=mod.correlate(p,c);self.assertEqual(d['matched_rows'],0);self.assertEqual(d['unmatched_rows'],3)
        self.assertEqual([r['reason'] for r in d['unmatched']],['no_range','wrong_module','missing_address'])

    def test_overlap_reports_and_never_selects_winner(self):
        p,c=self.fixture();c['targets'].append(dict(c['targets'][0],target_id=2,name='B'))
        d=mod.correlate(p,c);self.assertEqual(d['ambiguous_rows'],1);self.assertEqual(d['aggregates'],[])
        self.assertEqual(d['unmatched'][0]['target_ids'],[1,2])

    def test_va_below_base_is_invalid(self):
        p,c=self.fixture();p['rows'][0]['instruction_va']='0x10'
        d=mod.correlate(p,c);self.assertEqual(d['invalid_address_rows'],1);self.assertEqual(d['matched_rows'],0)

    def test_run_and_build_mismatch_fail_closed(self):
        p,c=self.fixture()
        with self.assertRaises(ValueError):mod.correlate(p,c,expected_run_id='r2')
        p['executable_sha256']='0'*64
        with self.assertRaises(ValueError):mod.correlate(p,c)
        c['executable_sha256']='0'*64
        with self.assertRaises(ValueError):mod.correlate(p,c)

    def test_negative_metric_and_duplicate_target_id_rejected(self):
        p,c=self.fixture();p['rows'][0]['cpu_time_ns']=-1
        with self.assertRaises(ValueError):mod.correlate(p,c)
        p,c=self.fixture();c['targets'].append(dict(c['targets'][0],name='B'))
        with self.assertRaises(ValueError):mod.correlate(p,c)
