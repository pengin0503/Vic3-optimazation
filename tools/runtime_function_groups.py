"""Index x64 RUNTIME_FUNCTION fragments by their chained-unwind root.

This is metadata reconstruction, not proof of a source-level function or a
complete execution path. Keep disjoint ranges disjoint and never group by
UnwindInfoAddress alone: unrelated procedures may share unwind records.
"""

from __future__ import annotations

from bisect import bisect_right
import collections
import struct

from analyze_vic3 import Error


def backed_bytes(binary, pe, rva: int, size: int) -> bytes:
    """Read only within one file-backed PE span, including header spans."""
    if rva < 0 or size < 0:
        raise Error('negative RVA or size')
    if rva < pe.size_headers and rva + size <= pe.size_headers:
        offset = rva
    else:
        section = next((s for s in pe.sections
                        if s['virtual_address'] <= rva
                        and rva + size <= s['virtual_address'] + s['raw_size']), None)
        if section is None:
            raise Error(f'unbacked/truncated span at 0x{rva:x} ({size} bytes)')
        offset = section['raw_pointer'] + rva - section['virtual_address']
    if offset + size > len(binary):
        raise Error(f'truncated file at RVA 0x{rva:x}')
    return bytes(binary[offset:offset + size])


def merge_ranges(entries):
    ranges = []
    for begin, end, _ in sorted(entries):
        if ranges and begin <= ranges[-1][1]:
            ranges[-1] = (ranges[-1][0], max(ranges[-1][1], end))
        else:
            ranges.append((begin, end))
    return ranges


class RuntimeFunctionIndex:
    """Resolve chains iteratively; malformed chains retain an explicit error."""

    def __init__(self, binary, pe, functions):
        self.functions = sorted(set(functions))
        self.starts = [f[0] for f in self.functions]
        self.roots = {}
        self.errors = {}
        self.overlap_ranges = []
        known = set(self.functions)

        # Quarantine whole connected overlap spans, including the outer range's
        # tail. A bisect on starts alone cannot safely choose nested entries.
        cluster = []
        cluster_end = 0

        def finish_cluster():
            if len(cluster) > 1:
                self.overlap_ranges.append((cluster[0][0], cluster_end))
                for item in cluster:
                    self.errors[item] = 'overlap/conflict in RUNTIME_FUNCTION ranges'

        for entry in self.functions:
            if cluster and entry[0] >= cluster_end:
                finish_cluster()
                cluster = []
            cluster.append(entry)
            cluster_end = max(cluster_end, entry[1]) if len(cluster) > 1 else entry[1]
        finish_cluster()
        self.overlap_starts = [begin for begin, _ in self.overlap_ranges]

        def parent(entry):
            begin, end, unwind = entry
            if not begin < end:
                raise Error('invalid function range')
            # RVA mapping alone can cross section padding into unrelated bytes.
            backed_bytes(binary, pe, begin, end - begin)
            if unwind % 4:
                raise Error(f'unaligned unwind RVA 0x{unwind:x}')
            header = backed_bytes(binary, pe, unwind, 4)
            version, flags = header[0] & 7, header[0] >> 3
            if version not in (1, 2):
                raise Error(f'unsupported unwind version {version}')
            if flags & ~7 or (flags & 4 and flags & 3):
                raise Error(f'invalid unwind flags {flags}')
            size = 4 + ((header[2] + 1) & ~1) * 2
            backed_bytes(binary, pe, unwind, size)
            if not flags & 4:
                if flags & 3:
                    backed_bytes(binary, pe, unwind + size, 4)
                return None
            target = struct.unpack('<III', backed_bytes(binary, pe, unwind + size, 12))
            if target not in known:
                raise Error(f'chained target {target!r} absent from RUNTIME_FUNCTION table')
            return target

        for entry in self.functions:
            if entry in self.roots or entry in self.errors:
                continue
            path, visited = [], set()
            current = entry
            error = None
            while current not in self.roots and current not in self.errors:
                if current in visited:
                    error = 'cycle in chained unwind metadata'
                    break
                visited.add(current)
                path.append(current)
                try:
                    previous = parent(current)
                except Error as exc:
                    error = str(exc)
                    break
                if previous is None:
                    self.roots[current] = current
                    break
                current = previous
            error = error or self.errors.get(current)
            if error:
                for item in path:
                    self.errors[item] = error
            else:
                root = self.roots[current]
                for item in path:
                    self.roots[item] = root

        fragments = collections.defaultdict(list)
        for entry, root in self.roots.items():
            fragments[root].append(entry)
        self.groups = {}
        for root, entries in fragments.items():
            ranges = merge_ranges(entries)
            self.groups[root] = {
                'status': 'resolved', 'root': root, 'fragments': sorted(entries),
                'fragment_count': len(entries), 'ranges': ranges,
                'size_bytes': sum(end - begin for begin, end in ranges),
            }

    def function_for(self, rva: int):
        index = bisect_right(self.starts, rva) - 1
        if index >= 0:
            entry = self.functions[index]
            if entry[0] <= rva < entry[1]:
                return entry
        return None

    def group_for(self, rva: int):
        overlap = bisect_right(self.overlap_starts, rva) - 1
        if overlap >= 0 and rva < self.overlap_ranges[overlap][1]:
            return self.invalid_group('overlap/conflict in RUNTIME_FUNCTION ranges')
        entry = self.function_for(rva)
        if entry is None:
            return None
        if entry in self.errors:
            return self.invalid_group(self.errors[entry])
        return self.groups[self.roots[entry]]

    @staticmethod
    def invalid_group(error):
        return {'status': 'invalid', 'error': error,
                'ranges': [], 'fragments': [], 'fragment_count': 0,
                'size_bytes': 0, 'root': None}


def group_metadata(group):
    """JSON-friendly metadata; callers keep their original first-fragment field."""
    if group is None:
        return None
    if group['status'] != 'resolved':
        return {'status': group['status'], 'error': group['error'], 'ranges': []}

    def record(entry):
        begin, end, unwind = entry
        return {'begin_rva': f'0x{begin:x}', 'end_rva': f'0x{end:x}',
                'unwind_rva': f'0x{unwind:x}', 'size_bytes': end - begin}

    return {'status': 'resolved', 'root_runtime_function': record(group['root']),
            'fragments': [record(f) for f in group['fragments']],
            'fragment_count': group['fragment_count'], 'size_bytes': group['size_bytes'],
            'ranges': [{'begin_rva': f'0x{b:x}', 'end_rva': f'0x{e:x}'}
                       for b, e in group['ranges']]}
