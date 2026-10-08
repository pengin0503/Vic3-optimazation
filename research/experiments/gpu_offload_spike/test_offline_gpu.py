import unittest
import numpy as np
from offline_gpu_core import make_case, cpu_reference, pack_case, transfer_bytes, cpu_pipeline, exact_match

class SyntheticGpuTests(unittest.TestCase):
    def test_workloads_and_scenarios(self):
        for kind in ('pop_growth', 'id_lookup'):
            for scenario in ('random', 'colliding', 'masked', 'large-int'):
                for n in (0, 1, 17, 4096):
                    with self.subTest(kind=kind, scenario=scenario, n=n):
                        case = make_case(kind, n, scenario, 1877)
                        packed = pack_case(case)
                        self.assertEqual(case['n'], n)
                        self.assertEqual(cpu_reference(case).dtype, np.dtype('int32'))
                        self.assertEqual(len(cpu_reference(case)), n)
                        exact_match(cpu_reference(case), cpu_reference(packed))
                        self.assertEqual(transfer_bytes(case), sum(a.nbytes for a in case['inputs'])+n*4)

    def test_copy_isolation_and_determinism(self):
        a = make_case('id_lookup', 101, 'masked', 19)
        b = make_case('id_lookup', 101, 'masked', 19)
        for x,y in zip(a['inputs'], b['inputs']): np.testing.assert_array_equal(x,y)
        packed = pack_case(a)
        for x,y in zip(a['inputs'], packed['inputs']):
            self.assertFalse(np.shares_memory(x,y))

    def test_collisions_and_masks(self):
        a = make_case('id_lookup', 1000, 'colliding', 4)
        self.assertLessEqual(len(np.unique(a['inputs'][0])), 16)
        m = make_case('id_lookup', 1000, 'masked', 4)
        self.assertTrue(np.any(cpu_reference(m) == -1))

    def test_integer_extremes(self):
        a = make_case('pop_growth', 100, 'large-int', 9)
        expected = cpu_reference(a)
        self.assertTrue(np.all(expected >= 0))
        self.assertTrue(np.all(expected <= a['inputs'][2]))
        a = make_case('id_lookup', 100, 'large-int', 9)
        self.assertGreater(np.max(cpu_reference(a)), 2_000_000_000)

    def test_cpu_pipeline_and_error(self):
        a = make_case('id_lookup', 32, 'masked', 18)
        result, timing = cpu_pipeline(a)
        exact_match(result, cpu_reference(a))
        self.assertGreaterEqual(timing['e2e_wall_ms'], 0)
        self.assertIn('pack_ms', timing)
        with self.assertRaises(ValueError):
            exact_match(result, result.astype('int64'))
        with self.assertRaises(ValueError):
            make_case('id_lookup', -1, 'masked', 18)

if __name__=='__main__': unittest.main()
