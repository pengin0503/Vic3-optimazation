from __future__ import annotations

import hashlib
import importlib.util
import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
TOOLS=ROOT/'tools'
if str(TOOLS) not in sys.path: sys.path.insert(0,str(TOOLS))
from analyze_vic3 import Error, PE

SPEC=importlib.util.spec_from_file_location('map_sync_callers',TOOLS/'map_sync_callers.py')
mod=importlib.util.module_from_spec(SPEC); assert SPEC.loader is not None; SPEC.loader.exec_module(mod)
RECIPE_SPEC=importlib.util.spec_from_file_location('reproduce_game_state_sync_evidence',ROOT/'research/recipes/reproduce_game_state_sync_evidence.py')
recipe=importlib.util.module_from_spec(RECIPE_SPEC); assert RECIPE_SPEC.loader is not None; RECIPE_SPEC.loader.exec_module(recipe)


def import_fixture():
    from tests.test_analyze_vic3 import minimal_pe64
    binary=bytearray(minimal_pe64(b'\x90'*0x1000)); pe=PE(binary)
    peoff=struct.unpack_from('<I',binary,0x3c)[0]; opt=peoff+4+20
    struct.pack_into('<II',binary,opt+112+8,0x1400,40)
    struct.pack_into('<IIIII',binary,pe.rva(0x1400),0x1480,0,0,0x14c0,0x14a0)
    struct.pack_into('<IIIII',binary,pe.rva(0x1414),0,0,0,0,0)
    struct.pack_into('<QQ',binary,pe.rva(0x1480),0x14e0,0)
    struct.pack_into('<QQ',binary,pe.rva(0x14a0),0x14e0,0)
    binary[pe.rva(0x14c0):pe.rva(0x14c0)+13]=b'KERNEL32.dll\0'
    struct.pack_into('<H',binary,pe.rva(0x14e0),0)
    name=b'WaitForSingleObject\0';binary[pe.rva(0x14e2):pe.rva(0x14e2)+len(name)]=name
    code=bytearray()
    code += b'\xff\x15'+struct.pack('<i',0x14a0-(0x1000+6))
    code += b'\x48\x8b\x05'+struct.pack('<i',0x14a0-(0x1006+7))
    code += b'\xff\xd0'
    code += b'\x48\xb8'+struct.pack('<Q',0x90909090000014a0)
    code += b'\xc3'
    binary[pe.rva(0x1000):pe.rva(0x1000)+len(code)]=code
    binary[pe.rva(0x1800):pe.rva(0x1800)+4]=b'\x01\x00\x00\x00'
    return bytes(binary),PE(bytes(binary)),(0x1000,0x1000+len(code),0x1800)


class SyncCallerTests(unittest.TestCase):
    def test_import_inventory_records_name_and_iat_slot(self):
        binary,pe,_=import_fixture(); imports=mod.enumerate_sync_imports(binary,pe)
        self.assertEqual(len(imports),1)
        self.assertEqual(imports[0]['name'],'WaitForSingleObject')
        self.assertEqual(imports[0]['iat_rva'],'0x14a0')

    @unittest.skipUnless(importlib.util.find_spec('capstone'),'optional callgraph dependency: capstone')
    def test_instruction_boundary_calls_address_loads_and_unresolved_indirection_are_separate(self):
        from runtime_function_groups import RuntimeFunctionIndex
        binary,pe,entry=import_fixture(); imports=mod.enumerate_sync_imports(binary,pe)
        result=mod.map_sync_references(binary,pe,RuntimeFunctionIndex(binary,pe,[entry]),imports)
        self.assertEqual([(x['instruction_rva'],x['reference_kind']) for x in result['references']], [('0x1000','direct_iat_call'),('0x1006','iat_pointer_load')])
        self.assertEqual([x['instruction_rva'] for x in result['unresolved_indirect_sites']],['0x100d'])
        self.assertNotIn('0x100f',[x['instruction_rva'] for x in result['references']])

    def test_candidate_semantics_never_assert_cscoped_identity_without_direct_evidence(self):
        doc=recipe.build_sync_callers_document({'references':[],'unresolved_indirect_sites':[],'partial_groups':[]},[])
        self.assertEqual(doc['candidate_kind'],'game_state_sync_candidate')
        self.assertFalse(doc['cscoped_game_state_release_identity_proven'])
        self.assertIsNone(doc['asserted_source_identity'])

    def test_candidate_document_preserves_scan_scope_metadata(self):
        mapping={
            'references':[], 'unresolved_indirect_sites':[], 'partial_groups':[],
            'caller_groups':{}, 'budgets':{'max_group_bytes':65536},
            'skipped_oversize_group_count':7,
        }
        doc=recipe.build_sync_callers_document(mapping,[])
        self.assertEqual(doc['budgets'],{'max_group_bytes':65536})
        self.assertEqual(doc['skipped_oversize_group_count'],7)

    def test_reproduce_is_byte_deterministic(self):
        binary=b'exact-sync-fixture'
        digest=hashlib.sha256(binary).hexdigest()
        imports=[{'dll':'KERNEL32.dll','name':'WaitForSingleObject','hint':0,'iat_rva':'0x14a0'}]
        mapping={
            'format_version':1, 'executable_sha256':digest,
            'references':[{'instruction_rva':'0x1000','caller_root_rva':'0x1000',
                           'reference_kind':'direct_iat_call','operand':'qword ptr [rip]',
                           'dll':'KERNEL32.dll','import_name':'WaitForSingleObject','iat_rva':'0x14a0'}],
            'unresolved_indirect_sites':[], 'partial_groups':[], 'caller_groups':{},
            'budgets':{'max_group_bytes':65536}, 'skipped_oversize_group_count':0,
            'warning':'static only',
        }
        class DummyPE: pass
        with tempfile.TemporaryDirectory() as d, \
             patch.object(recipe,'EXPECTED_SHA256',digest), \
             patch.object(recipe,'read_input',return_value=(binary,'fixture.exe')), \
             patch.object(recipe,'PE',return_value=DummyPE()), \
             patch.object(recipe,'enumerate_sync_imports',return_value=imports), \
             patch.object(recipe,'runtime_functions',return_value=[]), \
             patch.object(recipe,'RuntimeFunctionIndex',return_value=object()), \
             patch.object(recipe,'map_sync_references',return_value=mapping), \
             patch.object(recipe,'file_sha256',return_value='f'*64):
            first,second=Path(d)/'a',Path(d)/'b'
            recipe.reproduce(Path(d)/'input.zip',first)
            recipe.reproduce(Path(d)/'input.zip',second)
            for name in recipe.ARTIFACT_NAMES:
                self.assertEqual((first/name).read_bytes(),(second/name).read_bytes())
            index=json.loads((first/'artifact-index.json').read_text())
            for name in ('sync-imports.json','sync-callers.json'):
                self.assertEqual(index['artifacts'][name],hashlib.sha256((first/name).read_bytes()).hexdigest())

    def test_hash_mismatch_stops_recipe_before_output(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'out'
            with patch.object(recipe,'read_input',return_value=(b'wrong','fixture.exe')):
                with self.assertRaises(Error): recipe.reproduce(Path(d)/'input.zip',out)
            self.assertFalse(out.exists())


if __name__=='__main__':unittest.main()
