from __future__ import annotations
import hashlib, importlib.util, json, os, sys, tempfile, unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
TOOLS=ROOT/'tools'
if str(TOOLS) not in sys.path:sys.path.insert(0,str(TOOLS))
SPEC=importlib.util.spec_from_file_location('reproduce_modifier_node_evidence',ROOT/'research/recipes/reproduce_modifier_node_evidence.py')
mod=importlib.util.module_from_spec(SPEC);sys.modules[SPEC.name]=mod
assert SPEC.loader is not None;SPEC.loader.exec_module(mod)
Error=mod.Error

class ModifierNodeFollowupTests(unittest.TestCase):
    def rtti(self,digest='a'*64):
        return {'executable_sha256':digest,'classes':[{'name':mod.TASK_NAME,'vtable_candidate_count':1,
            'type_descriptor_rva':'0x10','vtable_rva':'0x20','task_specific_tail_vfunc_rva':'0x1000'}]}

    def test_resolves_by_required_rtti_class_name_and_hash(self):
        item=mod.resolve_target(self.rtti(),'a'*64)
        self.assertEqual(item['task_specific_tail_vfunc_rva'],'0x1000')
        wrong=self.rtti();wrong['classes'][0]['name']='CTickTask_Other'
        with self.assertRaises(Error):mod.resolve_target(wrong,'a'*64)
        with self.assertRaises(Error):mod.resolve_target(self.rtti(),'b'*64)

    def test_edge_classes_remain_separate(self):
        node={'direct_edges':[{'kind':'call','instruction_rva':'0x1','target_rva':'0x10'},
                              {'kind':'tail_jump_candidate','instruction_rva':'0x2','target_rva':'0x20'}],
              'indirect_sites':[{'kind':'call','instruction_rva':'0x3','operand':'rax'}],
              'code_address_references':[{'instruction_rva':'0x4','target_rva':'0x30'}],
              'vtable_address_references':[{'instruction_rva':'0x5','slots':[]}]}
        edges=mod.edge_inventory(node)
        self.assertEqual([x['kind'] for x in edges['direct_calls']],['call'])
        self.assertEqual([x['kind'] for x in edges['tail_jump_candidates']],['tail_jump_candidate'])
        self.assertEqual(len(edges['indirect_call_or_jump_sites']),1)
        self.assertEqual(len(edges['code_address_references']),1)
        self.assertEqual(len(edges['rtti_vtable_references']),1)

    def test_partial_decode_selected_region_fails_closed(self):
        nodes=[{'entry_rva':'0x1000','depth':0,'fully_decoded':False,
                'ranges':[{'begin_rva':'0x1000','end_rva':'0x1010','fully_decoded':False}]}]
        with self.assertRaisesRegex(Error,'partially decoded'):
            mod.select_regions(nodes,[0x1000])

    def test_documents_keep_runtime_and_benefit_unproven(self):
        graph={'executable_sha256':'a'*64,'budgets':{'max_depth':2},'nodes':[{
            'entry_rva':'0x1000','depth':0,'metadata':{},'fully_decoded':True,
            'ranges':[{'begin_rva':'0x1000','end_rva':'0x1010','fully_decoded':True}],
            'direct_edges':[],'indirect_sites':[],'code_address_references':[],'vtable_address_references':[]}]}
        callers={'scan_scope':'fixture','raw_candidate_count':0,'confirmed_calls':[],
                 'rejected_candidates':[],'unresolved_candidates':[]}
        callgraph,selected=mod.build_documents(self.rtti()['classes'][0],graph,callers,logical_input='x/victoria3.exe')
        self.assertTrue(callgraph['target']['runtime_unverified'])
        self.assertIn('Runtime reachability',callgraph['warning'])
        self.assertIn('optimization benefit',callgraph['warning'])
        self.assertEqual(selected['selected_regions'][0]['entry_rva'],'0x1000')

    def test_hash_mismatch_fails_before_output_directory_exists(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'out'
            with patch.object(mod,'read_input',return_value=(b'not-the-supported-exe','victoria3.exe')):
                self.assertEqual(mod.main(['unused',str(out)]),2)
            self.assertFalse(out.exists())

    def test_json_bytes_is_deterministic(self):
        a=mod.json_bytes({'b':2,'a':1});b=mod.json_bytes({'a':1,'b':2})
        self.assertEqual(a,b);self.assertEqual(hashlib.sha256(a).hexdigest(),hashlib.sha256(b).hexdigest())

    @unittest.skipUnless(os.environ.get('VIC3_DATA'),'set VIC3_DATA to Vic3_data.zip for integration test')
    def test_exact_1_14_5_reproduction(self):
        with tempfile.TemporaryDirectory() as d:
            a,b=Path(d)/'a',Path(d)/'b'
            for out in (a,b):mod.reproduce(Path(os.environ['VIC3_DATA']),out,rtti_path=None)
            for name in ('modifier-node-callgraph.json','modifier-node-selected-regions.json','artifact-index.json'):
                self.assertEqual((a/name).read_bytes(),(b/name).read_bytes())
            doc=json.loads((a/'modifier-node-callgraph.json').read_text())
            self.assertEqual(doc['target']['class_name'],mod.TASK_NAME)
            self.assertEqual(doc['target']['task_specific_tail_vfunc_rva'],'0x7da740')

if __name__=='__main__':unittest.main()
