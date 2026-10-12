import copy
import hashlib
import importlib
import unittest
import numpy as np
from offline_gpu_core import make_case

try:
    model = importlib.import_module('resident_lifecycle_probe')
except ImportError:
    model = None


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(model, 'lifecycle probe is not implemented')

    def test_recurrence_matches_independent_python_integer_oracle(self):
        for scenario in ('random','colliding','masked','large-int'):
            for n in (0,1,17):
                for stages in (1,4,32):
                    case = make_case('pop_growth', n, scenario)
                    a,b,c = case['inputs']; expected = []
                    for base,rate,cap in zip(a,b,c):
                        value = int(base)
                        for _ in range(stages):
                            value = min(value+value*int(rate)//1000, int(cap))
                        expected.append(value)
                    digest = hashlib.sha256(np.asarray(expected,dtype='<i4').tobytes()).hexdigest()
                    self.assertEqual(model.probe(case,stages)['final_output_sha256'],digest)

    def test_fixed_inputs_final_only_boundary_has_one_upload_one_download(self):
        r = model.probe(make_case('pop_growth',17,'random'),4)
        self.assertEqual(r['per_stage_roundtrip_transfer_bytes'],16*17*4)
        self.assertEqual(r['batched_transfer_bytes'],16*17)
        self.assertEqual(r['batched_h2d_bytes'],12*17)
        self.assertEqual(r['batched_d2h_bytes'],4*17)
        self.assertTrue(r['batching_eligible'])
        self.assertFalse(r['gpu_executed'])
        for field in ('gpu_time_ms','bandwidth_gb_per_s','speedup'):
            self.assertIsNone(r[field])

    def test_host_updates_or_intermediate_consumer_disallow_final_only_batch(self):
        case = make_case('pop_growth',17,'random')
        for flags in (dict(host_updates=True),dict(intermediate_outputs=True),
                      dict(host_updates=True,intermediate_outputs=True)):
            r = model.probe(case,4,**flags)
            self.assertFalse(r['batching_eligible'])
            self.assertIsNone(r['batched_transfer_bytes'])
            self.assertIsNone(r['batched_h2d_bytes'])
            self.assertIsNone(r['batched_d2h_bytes'])
            self.assertTrue(r['blocked_reasons'])

    def test_intermediate_observed_route_can_keep_fixed_inputs_device_resident(self):
        r = model.probe(make_case('pop_growth',17,'random'),4,intermediate_outputs=True)
        self.assertEqual(r['resident_observed_transfer_bytes'],12*17+4*17*4)
        self.assertIsNone(model.probe(make_case('pop_growth',17,'random'),4,
                                    host_updates=True)['resident_observed_transfer_bytes'])

    def test_probe_is_deterministic_and_does_not_mutate_inputs(self):
        case = make_case('pop_growth',17,'large-int'); before = copy.deepcopy(case)
        r = model.probe(case,16)
        self.assertEqual(r,model.probe(case,16))
        for a,b in zip(case['inputs'],before['inputs']):
            np.testing.assert_array_equal(a,b)
        self.assertEqual(r['source'],'synthetic_lifecycle_model_not_gpu_or_game')

    def test_stage_record_and_flag_types_are_strictly_bounded(self):
        case = make_case('pop_growth',1,'random')
        for stages in (0,33,True,1.5):
            with self.assertRaises(ValueError):model.probe(case,stages)
        for n in (-1,1000001,True):
            with self.assertRaises(ValueError):model.probe(dict(case,n=n),1)
        with self.assertRaises(ValueError):model.probe(case,1,host_updates=1)
        with self.assertRaises(ValueError):model.probe(case,1,intermediate_outputs='false')

    def test_unsupported_kind_malformed_shape_and_negative_input_rejected(self):
        for edit in ('kind','shape','dtype','negative'):
            case = make_case('pop_growth',17,'random')
            if edit=='kind':case['kind']='id_lookup'
            elif edit=='shape':case['inputs']=(case['inputs'][0][:-1],*case['inputs'][1:])
            elif edit=='dtype':case['inputs']=(case['inputs'][0].astype(np.int64),*case['inputs'][1:])
            else:case['inputs'][1][0]=-1
            with self.assertRaises(ValueError):model.probe(case,4)


if __name__=='__main__':unittest.main()
