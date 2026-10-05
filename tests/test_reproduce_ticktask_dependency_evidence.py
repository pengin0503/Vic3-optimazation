import builtins
import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
sys.path.insert(0, str(ROOT/'tests'))
sys.path.insert(0, str(ROOT/'research/recipes'))
from test_map_ticktask_dependencies import fixture
from analyze_vic3 import Error
import map_ticktask_dependencies as dep
import reproduce_ticktask_dependency_evidence as mod


class RecipeTests(unittest.TestCase):
    def test_wrong_hash_writes_no_output(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'bad.exe';p.write_bytes(b'bad')
            out=Path(d)/'out'
            with self.assertRaises(Error): mod.reproduce(p,out)
            self.assertFalse(out.exists())

    def test_missing_capstone_has_install_instruction(self):
        original=builtins.__import__
        def missing(name,*a,**kw):
            if name=='capstone': raise ImportError('fixture')
            return original(name,*a,**kw)
        with patch('builtins.__import__',side_effect=missing):
            with self.assertRaisesRegex(Error,'requirements-callgraph.txt'): dep.require_capstone()

    def test_recipe_reuses_matching_rtti_and_is_byte_deterministic(self):
        b=fixture();digest=hashlib.sha256(b).hexdigest()
        with tempfile.TemporaryDirectory() as d, patch.object(dep,'EXPECTED_SHA256',digest):
            p=Path(d)/'fixture.exe';p.write_bytes(b)
            r=Path(d)/'rtti.json';r.write_text(json.dumps({'executable_sha256':digest,'classes':[]}))
            for dest in ('a','b'):
                mod.reproduce(p,Path(d)/dest,rtti_path=r,graph_root_rva=0x1000,list_root_rva=0x1000)
            self.assertEqual((Path(d)/'a/ticktask-dependencies-1.14.5.json').read_bytes(),(Path(d)/'b/ticktask-dependencies-1.14.5.json').read_bytes())
            index=json.loads((Path(d)/'a/artifact-index.json').read_text())
            self.assertEqual(index['artifacts']['ticktask-dependencies-1.14.5.json'],hashlib.sha256((Path(d)/'a/ticktask-dependencies-1.14.5.json').read_bytes()).hexdigest())
