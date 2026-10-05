import csv
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import normalize_os_profile as mod

SHA='9b6f133a5dc235de9135d7b57e86ceda8282d1ba6c0e185f3ee19c22f8917f54'

class NormalizerTests(unittest.TestCase):
    def normalize(self, values=None, **options):
        mapping={'event_type':'cpu_sample','timestamp_column':'time','timestamp_unit':'ms',
                 'thread_id_column':'tid','executable_sha256':SHA,**options}
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'profile.csv'
            with p.open('w',newline='') as f:
                w=csv.writer(f,delimiter=mapping.get('delimiter',','));w.writerow(['time','tid','module','base','va','duration','cpu','wait','switches','stack','extra']);w.writerow(values or ['1.25','007','victoria3.exe','0x140000000','5368713216','2','3','4','5','frame, quoted "x"','ignored'])
            return mod.normalize_csv(p,mapping,run_id='run-1',source='synthetic')

    def test_cpu_sample_quoted_stack_and_both_address_notations(self):
        doc=self.normalize(module_column='module',module_base_column='base',instruction_va_column='va',stack_column='stack')
        r=doc['rows'][0]
        self.assertEqual(r['timestamp_ns'],1250000)
        self.assertEqual(r['thread_id'],'007')
        self.assertEqual(r['instruction_va'],'0x140001000')
        self.assertEqual(r['module_base'],'0x140000000')
        self.assertEqual(r['stack'],'frame, quoted "x"')
        self.assertNotIn('raw_source_row',r)
        self.assertEqual(doc['source_filename'],'profile.csv')
        self.assertEqual(doc['run_id'],'run-1')
        self.assertEqual(doc['unmapped_columns'],['cpu','duration','extra','switches','wait'])

    def test_wait_and_context_switch_metrics_only_when_mapped(self):
        doc=self.normalize(event_type='wait',duration_column='duration',duration_unit='us',wait_time_column='wait',wait_time_unit='ms',cpu_time_column='cpu',cpu_time_unit='ns',context_switches_column='switches')
        self.assertEqual({k:doc['rows'][0][k] for k in ('duration_ns','wait_time_ns','cpu_time_ns','context_switches')},{'duration_ns':2000,'wait_time_ns':4000000,'cpu_time_ns':3,'context_switches':5})
        self.assertEqual(self.normalize(event_type='context_switch')['rows'][0]['event_type'],'context_switch')

    def test_localized_decimal_requires_explicit_separator(self):
        r=self.normalize(['1,25','1','','','','','','','','',''],decimal_separator=',',delimiter=';')['rows'][0]
        self.assertEqual(r['timestamp_ns'],1250000)
        with self.assertRaises(ValueError): self.normalize(['1,25','1','','','','','','','','',''])

    def test_reject_invalid_unit_negative_and_nonfinite_values(self):
        for unit in ('ticks',''):
            with self.assertRaises(ValueError): self.normalize(timestamp_unit=unit)
        for value in ('-1','NaN','Infinity','0.0000001'):
            with self.assertRaises(ValueError): self.normalize([value,'1','','','','','','','','',''])
        with self.assertRaises(ValueError): self.normalize(['1','1','','','','-1','','','','',''],duration_column='duration',duration_unit='ms')
        with self.assertRaises(ValueError): self.normalize(duration_column='duration')

    def test_missing_required_or_optional_mapped_column_errors(self):
        for field in ('timestamp_column','duration_column'):
            with self.assertRaises(ValueError): self.normalize(**{field:'missing','duration_unit':'ns'})

    def test_missing_base_keeps_va_without_invented_rva(self):
        r=self.normalize(module_column='module',instruction_va_column='va')['rows'][0]
        self.assertNotIn('rva',r)
        self.assertNotIn('module_base',r)

    def test_impossible_address_and_negative_address_fail(self):
        for va in ('-1','0x10'):
            with self.assertRaises(ValueError): self.normalize(['1','1','victoria3.exe','0x100',va,'','','','','',''],module_base_column='base',instruction_va_column='va')

    def test_reject_unknown_event_and_missing_build_identity(self):
        with self.assertRaises(ValueError): self.normalize(event_type='mystery')
        with self.assertRaises(ValueError): self.normalize(executable_sha256='')
