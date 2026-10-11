#!/usr/bin/env python3
"""Compare abstract scheduling policies on owned synthetic DAG workloads only."""

import argparse
import hashlib
import heapq
import json
import os
from pathlib import Path
import sys
import tempfile

MAX_TASKS = 4096
MAX_WORKERS = 256
MAX_UNITS = 1_000_000_000

WARNING = ('Synthetic integer work units only; not Victoria 3 tasks, timings, '
           'CPU utilization, dependencies, or engine speedup evidence.')


def _graph(tasks: list[dict]):
    ids = {task['id']: i for i, task in enumerate(tasks)}
    children = [[] for _ in tasks]
    indegree = [0] * len(tasks)
    for i, task in enumerate(tasks):
        for parent in task['depends_on']:
            j = ids[parent]
            children[j].append(i)
            indegree[i] += 1
    remaining = indegree.copy()
    ready = [i for i, count in enumerate(remaining) if count == 0]
    heapq.heapify(ready)
    order = []
    while ready:
        i = heapq.heappop(ready)
        order.append(i)
        for j in children[i]:
            remaining[j] -= 1
            if remaining[j] == 0:
                heapq.heappush(ready, j)
    if len(order) != len(tasks):
        raise ValueError('task dependency cycle')
    return order, children, indegree


def validate_workload(doc: dict) -> tuple[list[dict], list[int], int]:
    if not isinstance(doc, dict) or type(doc.get('format_version')) is not int or doc['format_version'] != 1:
        raise ValueError('unsupported synthetic workload format')
    tasks = doc.get('tasks')
    if not isinstance(tasks, list) or not tasks or len(tasks) > MAX_TASKS:
        raise ValueError('tasks must be a nonempty list')
    worker_counts = doc.get('worker_counts')
    if (not isinstance(worker_counts, list) or not worker_counts or
            any(type(n) is not int or not 1 <= n <= MAX_WORKERS for n in worker_counts) or
            len(set(worker_counts)) != len(worker_counts)):
        raise ValueError('worker_counts must be distinct positive integers')
    dispatch_cost = doc.get('dispatch_cost_units')
    if type(dispatch_cost) is not int or not 0 <= dispatch_cost <= MAX_UNITS:
        raise ValueError('dispatch cost must be nonnegative integer')
    identifiers = set()
    for task in tasks:
        if not isinstance(task, dict):
            raise ValueError('tasks contain non-object')
        ident = task.get('id')
        work = task.get('work_units')
        parents = task.get('depends_on')
        if not isinstance(ident, str) or not ident or ident in identifiers:
            raise ValueError('missing or duplicate task id')
        identifiers.add(ident)
        if type(work) is not int or not 1 <= work <= MAX_UNITS:
            raise ValueError('work units must be positive integers')
        if (not isinstance(parents, list) or
                any(not isinstance(p, str) or not p for p in parents) or
                len(set(parents)) != len(parents)):
            raise ValueError('depends_on must contain distinct task ids')
    for task in tasks:
        if any(p not in identifiers for p in task['depends_on']):
            raise ValueError('missing dependency')
    _graph(tasks)
    return tasks, worker_counts, dispatch_cost


def critical_path_work_units(tasks: list[dict]) -> int:
    order, children, _ = _graph(tasks)
    longest = [task['work_units'] for task in tasks]
    for i in order:
        for child in children[i]:
            longest[child] = max(longest[child], longest[i] + tasks[child]['work_units'])
    return max(longest, default=0)


def simulate(tasks: list[dict], workers: int, dispatch_cost: int, *, policy: str) -> dict:
    """Schedule synthetic DAG nodes in integer units, with no preemption."""
    if policy not in ('ready', 'layer-barrier'):
        raise ValueError('unknown synthetic scheduling policy')
    if (type(workers) is not int or not 1 <= workers <= MAX_WORKERS or
            type(dispatch_cost) is not int or not 0 <= dispatch_cost <= MAX_UNITS):
        raise ValueError('invalid worker count or dispatch cost')
    order, children, indegree = _graph(tasks)
    if policy == 'layer-barrier':
        layer = [0] * len(tasks)
        for i in order:
            for child in children[i]:
                layer[child] = max(layer[child], layer[i] + 1)
        time = 0
        for depth in range(max(layer, default=-1) + 1):
            free_times = [time] * workers
            heapq.heapify(free_times)
            for i, task in enumerate(tasks):
                if layer[i] != depth:
                    continue
                earliest = heapq.heappop(free_times)
                heapq.heappush(free_times, earliest + task['work_units'] + dispatch_cost)
            time = max(free_times)
    else:
        waiting = indegree.copy()
        ready = [i for i, count in enumerate(waiting) if count == 0]
        heapq.heapify(ready)
        free_workers = list(range(workers))
        heapq.heapify(free_workers)
        events = []
        time = 0
        completed = 0
        while completed < len(tasks):
            while ready and free_workers:
                index = heapq.heappop(ready)
                worker = heapq.heappop(free_workers)
                finish = time + tasks[index]['work_units'] + dispatch_cost
                heapq.heappush(events, (finish, worker, index))
            if not events:
                raise ValueError('deadlock in synthetic workload')
            time = events[0][0]
            while events and events[0][0] == time:
                _, worker, index = heapq.heappop(events)
                heapq.heappush(free_workers, worker)
                completed += 1
                for child in children[index]:
                    waiting[child] -= 1
                    if waiting[child] == 0:
                        heapq.heappush(ready, child)
    useful_work = sum(task['work_units'] for task in tasks)
    overhead = len(tasks) * dispatch_cost
    busy = useful_work + overhead
    return {'policy': policy, 'workers': workers, 'makespan_units': time,
            'useful_work_units': useful_work,
            'dispatch_overhead_units': overhead, 'worker_busy_units': busy,
            'worker_idle_units': workers * time - busy,
            'useful_utilization': useful_work / (workers * time) if time else 0.0,
            'synthetic_only': True, 'warning': WARNING}


def build_comparison(doc: dict) -> dict:
    """Compare hypothetical policies without fitting any actual game data."""
    tasks, counts, dispatch = validate_workload(doc)
    total_work = sum(task['work_units'] for task in tasks)
    longest = critical_path_work_units(tasks)
    rows = []
    for workers in counts:
        rows.append({
            'workers': workers,
            'idealized_lower_bound_units': max((total_work + workers - 1) // workers, longest),
            'ready': simulate(tasks, workers, dispatch, policy='ready'),
            'layer_barrier': simulate(tasks, workers, dispatch, policy='layer-barrier'),
        })
    return {'format_version': 1, 'synthetic_only': True, 'warning': WARNING,
            'task_count': len(tasks), 'total_work_units': total_work,
            'critical_path_work_units': longest,
            'dispatch_cost_units': dispatch, 'results': rows}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.input.resolve() == args.output.resolve():
            raise ValueError('input and output must differ')
        raw = args.input.read_bytes()
        result = build_comparison(json.loads(raw.decode('utf-8')))
        result['source_json_sha256'] = hashlib.sha256(raw).hexdigest()
        encoded = (json.dumps(result, sort_keys=True, indent=2) + '\n').encode('utf-8')
        args.output.parent.mkdir(parents=True, exist_ok=True)
        temp = None
        try:
            with tempfile.NamedTemporaryFile(dir=args.output.parent,
                                             prefix='.scheduler-synthetic-',
                                             delete=False) as stream:
                temp = stream.name
                stream.write(encoded)
            os.replace(temp, args.output)
        finally:
            if temp is not None and os.path.exists(temp):
                os.unlink(temp)
    except (ValueError, OSError, UnicodeError) as exc:
        print(f'error: {exc}', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
