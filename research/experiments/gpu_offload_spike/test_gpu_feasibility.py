import unittest
import numpy as np
from gpu_feasibility import (transfer_floor_ms, optimistic_gpu_margin_ms, make_case, run_numba, run_numpy)


class TestGpuFeasibility(unittest.TestCase):
    def test_transfer_floor_si_units(self):
        self.assertAlmostEqual(transfer_floor_ms(12_000_000, 12), 1.0)
        self.assertEqual(transfer_floor_ms(0, 12), 0.0)
        for bytes_, bw in [(-1, 12), (1, 0), (1, -3)]:
            with self.assertRaises(ValueError):
                transfer_floor_ms(bytes_, bw)

    def test_optimistic_margin_calculation(self):
        self.assertAlmostEqual(optimistic_gpu_margin_ms(2.0, 12_000_000, 12, 0.1), 0.9)
        self.assertLess(optimistic_gpu_margin_ms(0.5, 12_000_000, 12, 0.0), 0)
        with self.assertRaises(ValueError):
            optimistic_gpu_margin_ms(1, 100, 12, -1)

    def test_case_deterministic(self):
        for kind in ['pop_growth', 'group_sum', 'id_lookup']:
            a = make_case(kind, 2048, 123)
            b = make_case(kind, 2048, 123)
            self.assertEqual(a['transfer_bytes'], b['transfer_bytes'])
            for xa, xb in zip(a['inputs'], b['inputs']):
                np.testing.assert_array_equal(xa, xb)

    def test_numba_and_numpy_exact_same_output(self):
        for kind in ['pop_growth', 'group_sum', 'id_lookup']:
            for n in [0, 1, 7, 255, 4096]:
                with self.subTest(kind=kind, n=n):
                    data = make_case(kind, n, 777)
                    expected = run_numpy(data)
                    actual = run_numba(data)
                    np.testing.assert_array_equal(expected, actual)

    def test_overflow_and_mask_edge_cases(self):
        for kind in ['pop_growth', 'group_sum', 'id_lookup']:
            case = make_case(kind, 101, 52)
            np.testing.assert_array_equal(run_numpy(case), run_numba(case))


if __name__ == '__main__':
    unittest.main()
