"""Synthetic-only task DAG scheduling regression tests."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import compare_schedulers as mod


def fixture():
    return {'format_version': 1, 'worker_counts': [1, 2, 4], 'dispatch_cost_units': 0,
            'tasks': [
                {'id': 'a', 'work_units': 8, 'depends_on': []},
                {'id': 'b', 'work_units': 2, 'depends_on': []},
                {'id': 'c', 'work_units': 3, 'depends_on': ['b']},
                {'id': 'd', 'work_units': 1, 'depends_on': ['c']},
            ]}


class ValidationTests(unittest.TestCase):
    def test_validated_chain_and_fork_critical_path(self):
        tasks, workers, dispatch = mod.validate_workload(fixture())
        self.assertEqual(workers, [1, 2, 4])
        self.assertEqual(dispatch, 0)
        self.assertEqual(mod.critical_path_work_units(tasks), 8)

    def test_rejects_duplicate_missing_and_cycles(self):
        cases = []
        x = fixture(); x['tasks'][1]['id'] = 'a'; cases.append(x)
        x = fixture(); x['tasks'][1]['depends_on'] = ['missing']; cases.append(x)
        x = fixture(); x['tasks'][1]['depends_on'] = ['d']; cases.append(x)
        x = fixture(); x['tasks'][0]['depends_on'] = ['a']; cases.append(x)
        x = fixture(); x['tasks'][2]['depends_on'] = ['b', 'b']; cases.append(x)
        for case in cases:
            with self.subTest(case=case), self.assertRaises(ValueError):
                mod.validate_workload(case)

    def test_rejects_bad_units_workers_and_format(self):
        for key, bad in [('format_version', 2), ('worker_counts', [0]),
                         ('worker_counts', [2, 2]), ('worker_counts', []),
                         ('dispatch_cost_units', -1), ('dispatch_cost_units', True)]:
            case = fixture(); case[key] = bad
            with self.subTest(key=key), self.assertRaises(ValueError):
                mod.validate_workload(case)
        for bad in [0, -1, True, 1.5, '12']:
            case = fixture(); case['tasks'][0]['work_units'] = bad
            with self.subTest(work=bad), self.assertRaises(ValueError):
                mod.validate_workload(case)
        with self.assertRaises(ValueError):
            mod.validate_workload([])
        case = fixture(); case['tasks'] = []
        with self.assertRaises(ValueError):
            mod.validate_workload(case)


if __name__ == '__main__':
    unittest.main()

class SchedulingTests(unittest.TestCase):
    def test_unbalanced_layers_compare_ready_against_global_barrier(self):
        tasks, _, cost = mod.validate_workload(fixture())
        ready = mod.simulate(tasks, 2, cost, policy='ready')
        barrier = mod.simulate(tasks, 2, cost, policy='layer-barrier')
        self.assertEqual(ready['makespan_units'], 8)
        self.assertEqual(barrier['makespan_units'], 12)
        self.assertEqual(ready['useful_work_units'], 14)
        self.assertEqual(ready['worker_busy_units'], 14)
        self.assertEqual(ready['worker_idle_units'], 2)
        self.assertEqual(barrier['worker_idle_units'], 10)

    def test_one_worker_topological_order_and_independent_tasks(self):
        tasks, _, _ = mod.validate_workload(fixture())
        self.assertEqual(mod.simulate(tasks, 1, 0, policy='ready')['makespan_units'], 14)
        self.assertEqual(mod.simulate(tasks, 1, 0, policy='layer-barrier')['makespan_units'], 14)
        case = fixture()
        case['tasks'] = [
            {'id': 'x', 'work_units': 5, 'depends_on': []},
            {'id': 'y', 'work_units': 5, 'depends_on': []}]
        tasks, _, _ = mod.validate_workload(case)
        self.assertEqual(mod.simulate(tasks, 2, 0, policy='ready')['makespan_units'], 5)
        self.assertEqual(mod.simulate(tasks, 2, 0, policy='layer-barrier')['makespan_units'], 5)

    def test_dispatch_cost_is_worker_occupancy_not_useful_work(self):
        tasks, _, _ = mod.validate_workload(fixture())
        result = mod.simulate(tasks, 2, 1, policy='ready')
        self.assertEqual(result['makespan_units'], 9)
        self.assertEqual(result['useful_work_units'], 14)
        self.assertEqual(result['dispatch_overhead_units'], 4)
        self.assertEqual(result['worker_busy_units'], 18)
        self.assertEqual(result['worker_idle_units'], 0)
        self.assertAlmostEqual(result['useful_utilization'], 14/18)

    def test_unknown_policy_rejects_and_runs_are_deterministic(self):
        tasks, _, cost = mod.validate_workload(fixture())
        with self.assertRaises(ValueError):
            mod.simulate(tasks, 2, cost, policy='unknown')
        with self.assertRaises(ValueError):
            mod.simulate(tasks, 0, cost, policy='ready')
        self.assertEqual(mod.simulate(tasks, 2, cost, policy='ready'),
                         mod.simulate(tasks, 2, cost, policy='ready'))

class ComparisonCliTests(unittest.TestCase):
    def test_comparison_has_ideal_lower_bounds_and_clear_synthetic_warning(self):
        comparison = mod.build_comparison(fixture())
        self.assertEqual(comparison['critical_path_work_units'], 8)
        self.assertEqual(comparison['total_work_units'], 14)
        results = comparison['results']
        self.assertEqual([row['workers'] for row in results], [1, 2, 4])
        self.assertEqual([row['idealized_lower_bound_units'] for row in results], [14, 8, 8])
        self.assertEqual(results[1]['ready']['makespan_units'], 8)
        self.assertEqual(results[1]['layer_barrier']['makespan_units'], 12)
        self.assertTrue(comparison['synthetic_only'])
        self.assertIn('not Victoria 3', comparison['warning'])

    def test_cli_source_hash_and_deterministic_bytes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / 'fixture.json'
            source.write_text(json.dumps(fixture()), encoding='utf-8')
            out1, out2 = root / 'o1.json', root / 'o2.json'
            self.assertEqual(mod.main([str(source), '--output', str(out1)]), 0)
            self.assertEqual(mod.main([str(source), '--output', str(out2)]), 0)
            self.assertEqual(out1.read_bytes(), out2.read_bytes())
            self.assertEqual(json.loads(out1.read_text())['source_json_sha256'],
                             hashlib.sha256(source.read_bytes()).hexdigest())

    def test_cli_fail_closed_without_overwrite(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source, output = root / 'input.json', root / 'out.json'
            source.write_text('{bad JSON', encoding='utf-8')
            output.write_bytes(b'KEEP')
            self.assertEqual(mod.main([str(source), '--output', str(output)]), 2)
            self.assertEqual(output.read_bytes(), b'KEEP')
            source.write_text(json.dumps(fixture()), encoding='utf-8')
            original = source.read_bytes()
            self.assertEqual(mod.main([str(source), '--output', str(source)]), 2)
            self.assertEqual(source.read_bytes(), original)

class ResourceLimitTests(unittest.TestCase):
    def test_validation_rejects_unbounded_synthetic_work(self):
        tasks, _, _ = mod.validate_workload(fixture())
        with self.assertRaises(ValueError):
            mod.simulate(tasks, 100_000_000, 0, policy='ready')
        case = fixture(); case['worker_counts'] = [100_000_000]
        with self.assertRaises(ValueError):
            mod.validate_workload(case)
        case = fixture(); case['dispatch_cost_units'] = 1 << 100
        with self.assertRaises(ValueError):
            mod.validate_workload(case)
        case = fixture(); case['tasks'][0]['work_units'] = 1 << 100
        with self.assertRaises(ValueError):
            mod.validate_workload(case)
        case = fixture(); case['tasks'] = [
            {'id': str(i), 'work_units': 1, 'depends_on': []}
            for i in range(4097)]
        with self.assertRaises(ValueError):
            mod.validate_workload(case)
