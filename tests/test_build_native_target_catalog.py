import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import build_native_target_catalog as mod
SHA='9b6f133a5dc235de9135d7b57e86ceda8282d1ba6c0e185f3ee19c22f8917f54'


def task(name, ranges):
    return {'name':name,'vtable_candidate_count':1,'tail_function_group':{'status':'resolved','ranges':ranges}}


class CatalogTests(unittest.TestCase):
    def build(self,classes=None,overrides=None,sha=SHA):
        return mod.build_catalog({'executable_sha256':SHA,'classes':classes or [task('CTickTask_A',[{'begin_rva':'0x1000','end_rva':'0x1010'}])]},overrides or {'executable_sha256':SHA,'targets':[]},executable_sha256=sha)

    def test_ids_and_chained_ranges_deterministic(self):
        a=task('CTickTask_A',[{'begin_rva':'0x1100','end_rva':'0x1120'},{'begin_rva':'0x1000','end_rva':'0x1010'}]);b=task('CTickTask_B',[{'begin_rva':'0x1200','end_rva':'0x1210'}])
        doc=self.build([b,a])
        self.assertEqual(doc,self.build([a,b]))
        self.assertEqual([t['target_id'] for t in doc['targets']],[1,2])
        self.assertEqual(doc['targets'][0]['ranges'],[{'begin_rva':'0x1000','end_rva':'0x1010'},{'begin_rva':'0x1100','end_rva':'0x1120'}])

    def test_hash_gate_all_inputs(self):
        with self.assertRaises(ValueError): self.build(sha='0'*64)
        with self.assertRaises(ValueError): self.build(overrides={'executable_sha256':'0'*64,'targets':[]})
        with self.assertRaises(ValueError): mod.build_catalog({'executable_sha256':'0'*64}, {}, executable_sha256=SHA)

    def test_cross_target_overlap_reported_without_arbitrary_winner(self):
        doc=self.build([task('CTickTask_A',[{'begin_rva':'0x1000','end_rva':'0x1020'}]),task('CTickTask_B',[{'begin_rva':'0x1010','end_rva':'0x1030'}])])
        self.assertEqual(len(doc['range_conflicts']),1)
        self.assertEqual(doc['range_conflicts'][0]['target_ids'],[1,2])

    def test_duplicate_names_and_internal_overlap_rejected(self):
        a=task('CTickTask_A',[{'begin_rva':'0x1000','end_rva':'0x1020'}])
        with self.assertRaises(ValueError): self.build([a,a])
        a['tail_function_group']['ranges'].append({'begin_rva':'0x1010','end_rva':'0x1030'})
        with self.assertRaises(ValueError): self.build([a])

    def test_unresolved_unwind_does_not_invent_range(self):
        a=task('CTickTask_A',[]);a['tail_function_group']['status']='invalid'
        doc=self.build([a]);self.assertEqual(doc['targets'],[]);self.assertEqual(len(doc['unresolved']),1)

    def test_override_requires_cited_evidence(self):
        t={'name':'dispatcher_candidate','kind':'dispatcher','ranges':[{'begin_rva':'0x2000','end_rva':'0x2010'}]}
        with self.assertRaises(ValueError): self.build(overrides={'executable_sha256':SHA,'targets':[t]})
