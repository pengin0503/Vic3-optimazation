import importlib.util
import unittest
from gpu_opencl import KERNEL_SOURCE, NoGpuAvailable, select_device, device_catalog, OpenCLExecutor

class BackendTests(unittest.TestCase):
    def test_backend_preserves_each_copy_event_duration_before_summing(self):
        from types import SimpleNamespace
        events=[SimpleNamespace(profile=SimpleNamespace(start=0,end=end)) for end in (0,200000,200000)]
        helper=getattr(OpenCLExecutor,'_event_durations_ms',None)
        self.assertTrue(callable(helper), 'per-copy profile information missing')
        self.assertEqual(helper(events),[0,0.2,0.2])
        self.assertAlmostEqual(OpenCLExecutor._event_ms(events),0.4)

    def test_source_defines_both_kernels(self):
        self.assertIn('__kernel void pop_growth', KERNEL_SOURCE)
        self.assertIn('__kernel void id_lookup', KERNEL_SOURCE)
        self.assertIn('long grown', KERNEL_SOURCE)

    def test_missing_or_nonmatching_gpu_fails_closed(self):
        class DummyCL:
            class device_type:
                GPU=4
        class DummyPlatform:
            name='CPU platform'
            vendor='No GPU'
            def get_devices(self):
                class DummyDevice:
                    type=2
                    name='CPU only'
                return [DummyDevice()]
        with self.assertRaises(NoGpuAvailable):
            select_device(DummyCL, [DummyPlatform()], '7800')

    def test_python_backend_gating(self):
        if importlib.util.find_spec('pyopencl') is None:
            with self.assertRaisesRegex(NoGpuAvailable, 'pyopencl'):
                OpenCLExecutor('7800')

    def test_non_gpu_is_not_passed_off_as_gpu(self):
        class FakeCL:
            class device_type:
                GPU=4
        class Platform:
            name='test'
            vendor='AMD'
            def get_devices(self):
                class Device:
                    name='RX 7800 XT (CPU simulator)'
                    type=2
                return [Device()]
        with self.assertRaises(NoGpuAvailable):
            select_device(FakeCL, [Platform()], '7800')

if __name__=='__main__': unittest.main()
