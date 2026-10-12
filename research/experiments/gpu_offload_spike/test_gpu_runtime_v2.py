import unittest
import hashlib
import numpy as np
from offline_gpu_core import make_case, cpu_reference, exact_match
from gpu_runtime_v2 import optimized_cpu, cpu_sample, run_v2, summarize_h2d, gpu_digest

class FakeGPU:
    metadata={'device': 'FAKE', 'driver': 'unit-test', 'backend': 'fake'}
    def allocate(self, case): return {}
    def preload(self, buffers, case): pass
    def run_once(self, buffers, case, mode):
        out = cpu_reference(case)
        return out, dict(pack_ms=0, h2d_host_submit_ms=0.04 if mode=='cold' else 0,
            h2d_host_wait_ms=0.12 if mode=='cold' else 0,
            h2d_device_event_ms=0, kernel_host_submit_ms=0.01,
            h2d_device_event_durations_ms=[0,0,0] if mode=='cold' else [],
            h2d_copy_bytes=[a.nbytes for a in case['inputs']] if mode=='cold' else [],
            kernel_host_wait_ms=0.03, kernel_device_event_ms=0.006,
            d2h_host_submit_ms=0.01, d2h_host_wait_ms=0.1,
            d2h_device_event_ms=0.08, apply_ms=0.01,
            e2e_wall_ms=0.31, h2d_bytes=0 if mode=='resident' else sum(a.nbytes for a in case['inputs']),
            d2h_bytes=4*case['n'])

class CPUv2Tests(unittest.TestCase):
    def test_numba_variants_are_exact_for_all_scenarios_and_edges(self):
        for k in ('pop_growth', 'id_lookup'):
            for scenario in ('random', 'colliding', 'masked', 'large-int'):
                for n in (0,1,17,10001):
                    with self.subTest(kind=k,scenario=scenario,n=n):
                        case=make_case(k,n,scenario,1877)
                        for backend in ('numba-serial','numba-parallel'):
                            actual=optimized_cpu(case,backend)
                            exact_match(cpu_reference(case),actual)

    def test_cpu_modes_have_expected_copy_semantics(self):
        case=make_case('pop_growth',17,'large-int')
        for backend in ('numpy','numba-serial','numba-parallel'):
            for mode in ('cold','resident'):
                output,times=cpu_sample(case,backend,mode)
                exact_match(cpu_reference(case),output)
                self.assertGreaterEqual(times['e2e_wall_ms'],times['cpu_compute_ms'])
                if mode=='resident':
                    self.assertEqual(times['pack_ms'],0)
                else:
                    self.assertGreaterEqual(times['pack_ms'],0)

    def test_h2d_zero_profile_not_called_zero_transfer(self):
        samples=[{'h2d_bytes':120,'h2d_device_event_ms':0,'h2d_host_submit_ms':0.01,'h2d_host_wait_ms':0.2} for _ in range(3)]
        m=summarize_h2d(samples)
        self.assertFalse(m['device_event_valid'])
        self.assertIsNone(m['observed_device_gb_per_s'])
        self.assertEqual(m['zero_duration_events'],3)
        self.assertGreater(m['host_phase_median_ms'],0.2)

    def test_h2d_positive_events_valid(self):
        samples=[{'h2d_bytes':1200000,'h2d_device_event_ms':0.2,
                  'h2d_device_event_durations_ms':[0.05,0.05,0.1], 'h2d_copy_bytes':[400000]*3,
                  'h2d_host_submit_ms':0.02,'h2d_host_wait_ms':0.3} for _ in range(3)]
        m=summarize_h2d(samples)
        self.assertTrue(m['device_event_valid'])
        self.assertAlmostEqual(m['observed_device_gb_per_s'],6)

    def test_mixed_zero_copy_profile_cannot_certify_transfer_bandwidth(self):
        samples=[dict(h2d_bytes=1200000, h2d_device_event_ms=0.4,
            h2d_device_event_durations_ms=[0,0.2,0.2], h2d_copy_bytes=[400000]*3,
            h2d_host_submit_ms=0.02, h2d_host_wait_ms=0.3)]
        r=summarize_h2d(samples)
        self.assertFalse(r['device_event_valid'])
        self.assertIsNone(r['observed_device_gb_per_s'])
        self.assertEqual(r.get('zero_duration_copy_events'),1)

    def test_aggregate_only_missing_misaligned_and_invalid_copy_profiles_fail_closed(self):
        base=dict(h2d_bytes=1200000,h2d_device_event_ms=0.6,
                  h2d_host_submit_ms=0.02,h2d_host_wait_ms=0.3)
        for fields in ({},dict(h2d_device_event_durations_ms=[0.2]*3,h2d_copy_bytes=[400000]),
                       dict(h2d_device_event_durations_ms=[-0.2,0.4,0.4],h2d_copy_bytes=[400000]*3),
                       dict(h2d_device_event_durations_ms=[float('nan'),0.2,0.2],h2d_copy_bytes=[400000]*3)):
            with self.subTest(fields=fields):
                r=summarize_h2d([dict(base,**fields)])
                self.assertFalse(r['device_event_valid'])
                self.assertIsNone(r['observed_device_gb_per_s'])

    def test_fake_gpu_output_digest_and_baseline_records(self):
        gpu=FakeGPU()
        results=run_v2(gpu,[23],['id_lookup'],['masked'],repeats=3,warmups=1,seed=1877,numba_threads=2,session_id='session-1')
        self.assertEqual(results['schema_version'],2)
        self.assertTrue(results['gpu_executed'])
        row=results['results'][0]
        self.assertEqual(len(row['cpu']['numba-serial']['cold']['samples']),3)
        self.assertEqual(len(row['cpu']['numba-parallel']['resident']['samples']),3)
        self.assertEqual(row['modes']['cold']['gpu_output_sha256'],row['reference_output_sha256'])
        self.assertFalse(row['modes']['cold']['h2d']['device_event_valid'])
        self.assertEqual(row['modes']['cold']['gpu_output_verified_iterations'],4)
        self.assertIn('ratio_vs_numba_serial_cpu_cold',row['modes']['cold'])
        self.assertIn('ratio_vs_numba_parallel_cpu_resident',row['modes']['resident'])
        self.assertEqual(results['session_id'],'session-1')

    def test_bad_gpu_result_aborts(self):
        class Corrupt(FakeGPU):
            def run_once(self, buffers, case, mode):
                out,times=super().run_once(buffers,case,mode)
                out[0] += 1
                return out,times
        with self.assertRaises(ValueError):
            run_v2(Corrupt(),[23],['id_lookup'],['masked'],repeats=3,warmups=1,seed=1877,numba_threads=2,session_id='test')

    def test_digest_is_independent_of_result_array_ownership(self):
        a=np.array([1,2,3],dtype=np.int32)
        self.assertEqual(gpu_digest(a),hashlib.sha256(a.tobytes()).hexdigest())

if __name__=='__main__':unittest.main()
