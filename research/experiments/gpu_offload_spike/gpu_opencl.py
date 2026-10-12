"""Optional, real OpenCL GPU executor. Never silently falls back to CPU OpenCL."""
from __future__ import annotations
import platform
import time
import numpy as np
from offline_gpu_core import pack_case

KERNEL_SOURCE = r'''
__kernel void pop_growth(__global const int *base, __global const int *rate,
                         __global const int *cap, __global int *output, int n) {
    int i = (int)get_global_id(0);
    if (i >= n) return;
    long original = (long)base[i];
    long grown = original + (original * (long)rate[i]) / 1000L;
    long limit = (long)cap[i];
    output[i] = (int)(grown < limit ? grown : limit);
}
__kernel void id_lookup(__global const int *ids, __global const int *values,
                        __global const uchar *live, __global int *output, int n) {
    int i = (int)get_global_id(0);
    if (i >= n) return;
    int id = ids[i];
    output[i] = (id >= 0 && id < n && live[id] != 0) ? values[id] : -1;
}
'''

class NoGpuAvailable(RuntimeError):
    """OpenCL GPU unavailable, never substitute CPU device."""

def select_device(cl, platforms, required_substring='7800'):
    selected = []
    for p in platforms:
        try:
            devices = p.get_devices()
        except Exception:
            continue
        for d in devices:
            if (int(d.type) & int(cl.device_type.GPU)) and required_substring.lower() in d.name.lower():
                selected.append((p, d))
    if len(selected) != 1:
        raise NoGpuAvailable(f'expected exactly one GPU matching {required_substring!r}, found {len(selected)}')
    return selected[0]

def device_catalog():
    try:
        import pyopencl as cl
    except (ImportError, OSError) as ex:
        raise NoGpuAvailable('pyopencl not installed or OpenCL ICD loader missing') from ex
    try:
        platforms = cl.get_platforms()
    except Exception as ex:
        raise NoGpuAvailable(f'OpenCL platform unavailable: {ex}') from ex
    result = []
    for p in platforms:
        for d in p.get_devices():
            result.append({'platform': p.name, 'vendor': d.vendor, 'device': d.name,
                           'type': 'GPU' if int(d.type) & int(cl.device_type.GPU) else 'NOT_GPU',
                           'driver': d.driver_version})
    return result

class OpenCLExecutor:
    def __init__(self, name_substring='7800'):
        try:
            import pyopencl as cl
        except (ImportError, OSError) as ex:
            raise NoGpuAvailable('pyopencl not installed or OpenCL ICD loader missing') from ex
        self.cl = cl
        try:
            platform_, device = select_device(cl, cl.get_platforms(), name_substring)
            self.context = cl.Context([device])
            self.queue = cl.CommandQueue(self.context, properties=cl.command_queue_properties.PROFILING_ENABLE)
            self.program = cl.Program(self.context, KERNEL_SOURCE).build(options=['-cl-std=CL1.2'])
        except NoGpuAvailable:
            raise
        except Exception as ex:
            raise NoGpuAvailable(f'GPU initialization/build failed: {ex}') from ex
        self.metadata = {'platform': platform_.name, 'platform_vendor': platform_.vendor,
                         'device': device.name, 'vendor': device.vendor,
                         'driver': device.driver_version, 'opencl': device.version,
                         'compute_units': int(device.max_compute_units),
                         'global_mem_bytes': int(device.global_mem_size),
                         'backend': 'OpenCL', 'python_platform': platform.platform()}

    def allocate(self, case):
        cl = self.cl
        return {'inputs': [cl.Buffer(self.context, cl.mem_flags.READ_ONLY, size=max(4, a.nbytes))
                           for a in case['inputs']],
                'output': cl.Buffer(self.context, cl.mem_flags.WRITE_ONLY, size=max(4, case['n'] * 4))}

    @staticmethod
    def _event_durations_ms(events):
        return [(int(e.profile.end) - int(e.profile.start)) / 1_000_000 for e in events]

    @staticmethod
    def _event_ms(events):
        return sum(OpenCLExecutor._event_durations_ms(events))

    def _upload(self, buffers, case):
        events=[]
        for buf, array in zip(buffers['inputs'], case['inputs']):
            if array.nbytes:
                events.append(self.cl.enqueue_copy(self.queue, buf, array, is_blocking=False))
        if events: events[-1].wait()
        return events

    def preload(self, buffers, case):
        """Resident-input setup outside the timed iteration."""
        packed = pack_case(case)
        self._upload(buffers, packed)
        self.queue.finish()

    def run_once(self, buffers, case, mode):
        if mode not in ('cold', 'resident') or case['n'] == 0:
            raise ValueError('mode must be cold/resident and records > 0')
        t0=time.perf_counter_ns()
        if mode=='cold':
            packed = pack_case(case)
        else:
            packed = case  # preloaded, excluded from this iteration
        t1=time.perf_counter_ns()
        upload_events=[]
        upload_submit_ns=upload_wait_ns=0
        if mode=='cold':
            u0=time.perf_counter_ns()
            for buf, array in zip(buffers['inputs'], packed['inputs']):
                if array.nbytes:
                    upload_events.append(self.cl.enqueue_copy(self.queue, buf, array, is_blocking=False))
            u1=time.perf_counter_ns()
            if upload_events: upload_events[-1].wait()
            u2=time.perf_counter_ns()
            upload_submit_ns=u1-u0
            upload_wait_ns=u2-u1
        kernel = self.cl.Kernel(self.program, case['kind'])
        for i, buf in enumerate(buffers['inputs']):
            kernel.set_arg(i, buf)
        kernel.set_arg(len(buffers['inputs']), buffers['output'])
        kernel.set_arg(len(buffers['inputs']) + 1, np.int32(case['n']))
        k0=time.perf_counter_ns()
        ev_kernel=self.cl.enqueue_nd_range_kernel(self.queue, kernel, (case['n'],), None)
        k1=time.perf_counter_ns()
        ev_kernel.wait()
        k2=time.perf_counter_ns()
        output_host = np.empty(case['n'], np.int32)
        d0=time.perf_counter_ns()
        ev_download=self.cl.enqueue_copy(self.queue, output_host, buffers['output'], is_blocking=False)
        d1=time.perf_counter_ns()
        ev_download.wait()
        d2=time.perf_counter_ns()
        a0=time.perf_counter_ns()
        applied=np.array(output_host, copy=True)
        a1=time.perf_counter_ns()
        upload_profile=self._event_durations_ms(upload_events)
        return applied, {
            'pack_ms': (t1-t0)/1e6,
            'h2d_host_submit_ms': upload_submit_ns/1e6,
            'h2d_host_wait_ms': upload_wait_ns/1e6,
            'h2d_device_event_ms': sum(upload_profile),
            'h2d_device_event_durations_ms': upload_profile,
            'h2d_copy_bytes': [a.nbytes for a in packed['inputs'] if a.nbytes] if mode=='cold' else [],
            'kernel_host_submit_ms': (k1-k0)/1e6,
            'kernel_host_wait_ms': (k2-k1)/1e6,
            'kernel_device_event_ms': self._event_ms([ev_kernel]),
            'd2h_host_submit_ms': (d1-d0)/1e6,
            'd2h_host_wait_ms': (d2-d1)/1e6,
            'd2h_device_event_ms': self._event_ms([ev_download]),
            'apply_ms': (a1-a0)/1e6,
            'e2e_wall_ms': (a1-t0)/1e6,
            'h2d_bytes': 0 if mode=='resident' else sum(a.nbytes for a in packed['inputs']),
            'd2h_bytes': case['n']*4,
        }
