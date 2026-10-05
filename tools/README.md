# Tools

All repository-side research tools are dependency-free Python 3 unless noted otherwise. They operate on a local Victoria 3 install or the supplied research ZIP; proprietary binaries are not committed to the repository.

## Offline static pipeline

### `run_static_pipeline.py`

Runs the core static research passes in one command:

```text
python tools/run_static_pipeline.py C:\path\to\Vic3_data.zip out\static \
  --signature-manifest research/generated/exact-signatures-1.14.5.json
```

Outputs:

- `static-analysis.json`
- `static-xrefs.json`
- `ticktask-rtti.json`
- `signature-validation.json` when a signature manifest is supplied
- `summary.json`

A signature-validation failure returns a non-zero exit code.

### `analyze_vic3.py`

Dependency-free PE/static metadata extraction:

```text
python tools/analyze_vic3.py C:\path\to\Vic3_data.zip \
  --output research/generated/static-analysis-local.json
```

Extracts:

- SHA-256
- PE metadata and sections
- import/export tables
- embedded PDB paths
- source-path strings
- `CTickTask_*` names
- task/job/parallelism-related RTTI strings
- profiler/console command identifiers

### `map_static_xrefs.py`

Maps selected ASCII anchors to **candidate** x64 RIP-relative code references and PE `.pdata` function ranges:

```text
python tools/map_static_xrefs.py C:\path\to\Vic3_data.zip \
  --output out\static-xrefs.json
```

Raw disp32 matches can be false positives. Validate important candidates in a real disassembler before assigning semantics.

### `map_ticktask_rtti.py`

Recovers MSVC x64 RTTI, Complete Object Locators and vtables for concrete TickTask classes:

```text
python tools/map_ticktask_rtti.py C:\path\to\Vic3_data.zip \
  --output out\ticktask-rtti.json
```

For 1.14.5 this maps 258 concrete TickTask classes. The final virtual slot is recorded as `task_specific_tail_vfunc`; the tool deliberately does not invent a source-level method name.

### `generate_signatures.py`

Generates the shortest unique **exact-build** byte window near a known RVA:

```text
python tools/generate_signatures.py C:\path\to\Vic3_data.zip \
  --target employment=0x13b8310
```

These signatures are secondary validators only after the executable hash matches. They are not cross-version signatures.

### `validate_exact_signatures.py`

Fail-closed validation of an exact-build signature manifest:

```text
python tools/validate_exact_signatures.py \
  C:\path\to\Vic3_data.zip \
  research/generated/exact-signatures-1.14.5.json
```

Checks:

- exact executable SHA-256
- pattern bytes at the expected RVA
- expected occurrence count inside `.text`

### `compare_static_analysis.py`

Compares two build-analysis outputs when Victoria 3 updates:

```text
python tools/compare_static_analysis.py old.json new.json \
  --before-rtti old-rtti.json \
  --after-rtti new-rtti.json \
  --output migration.json
```

Any executable hash change produces the migration decision:

`revalidate-all-native-targets-before-enabling-hooks`

even when strings/RTTI appear unchanged.

### `extract_performance_controls.py`

Extracts the known performance-sensitive define values and nearby shipped comments:

```text
python tools/extract_performance_controls.py C:\path\to\Vic3_data.zip \
  --output out\performance-controls.json
```

These values are causal-test controls, not automatic recommendations. Changing update cadence, search breadth or Pop consolidation can change simulation semantics.

## Benchmark preparation

### `prepare_benchmark_matrix.py`

Creates the complete Phase 1 run matrix without pretending unmeasured runs are valid data:

```powershell
python tools/prepare_benchmark_matrix.py benchmarks/runs `
  --threads 1,2,4,6,8,12,16 `
  --repeats 3 `
  --start-date 1900-01-01 `
  --end-date 1901-01-01 `
  --save-filename heavy-save.v3 `
  --save-sha256 <64-hex-save-hash> `
  --country JAP `
  --pop-consolidation moderate_consolidation
```

The default matrix is one warm-up plus three measured runs for each thread count: 28 run templates.

Each run initially gets `manifest.template.json`, not `manifest.json`. The tool refuses to write into a non-empty output directory.

### `finalize_benchmark_run.py`

After a run produced `ticktask_timings.csv`:

```powershell
python tools/finalize_benchmark_run.py `
  benchmarks/runs/vanilla-t08-r01 `
  --wall-clock-seconds 123.456
```

Before creating `manifest.json`, it verifies the required columns:

- `frame`
- `task`
- `milliseconds`
- `calls`
- `longest_lock`

It also records the CSV SHA-256, byte size and row count.

## Benchmark analysis

### `analyze_benchmarks.py`

```text
python tools/analyze_benchmarks.py benchmarks/runs \
  --json benchmarks/report.json \
  --markdown benchmarks/report.md
```

Reports:

- TickTask cumulative cost
- calls
- maximum record time
- longest observed lock
- run-to-run coefficient of variation
- TaskThreadCount scaling
- later variant-vs-vanilla comparisons

It deliberately does not claim causality from a single timing metric.

### `analyze_thread_scaling.py`

Adds cautious scaling diagnostics:

```text
python tools/analyze_thread_scaling.py benchmarks/report.json \
  --json benchmarks/scaling.json \
  --markdown benchmarks/scaling.md
```

Provides:

- incremental benefit from each higher TaskThreadCount
- parallel efficiency relative to a 1-thread baseline
- an Amdahl-style **effective** serial fraction
- a configurable plateau screen

The Amdahl value is diagnostic only. TaskThreadCount is not the total number of Victoria 3 threads, and lock/scheduler/memory effects violate ideal Amdahl assumptions.

### `triage_benchmark_targets.py`

Joins measured runtime hotspots to the static TickTask RTTI map:

```text
python tools/triage_benchmark_targets.py \
  benchmarks/report.json \
  out/static/ticktask-rtti.json \
  --threads 8 \
  --json benchmarks/native-targets.json \
  --markdown benchmarks/native-targets.md
```

This converts a runtime row such as `UpdateEmployment` into its concrete TickTask class and static native tail-function anchor when available.

It narrows reverse engineering after the benchmark; it does not declare a patch safe.

## Tests

Run all repository tests:

```text
python -m unittest discover -s tests -v
```

Optional local 1.14.5 integration test:

```powershell
$env:VIC3_DATA = "C:\path\to\Vic3_data.zip"
python -m unittest discover -s tests -v
```

GitHub Actions installs the optional callgraph dependency and runs the unit suite on every push to `main` and every pull request. Binary integration still requires a locally supplied `VIC3_DATA` input.

## 2026-10-05: source-backed follow-up

`map_ticktask_rtti.py` now retains `tail_runtime_function` as the first fragment
and adds `tail_function_group`: root triple, chained fragments, disjoint ranges,
byte count, and explicit invalid-metadata status. Shared unwind records never
merge unrelated functions. Overlap, cycles and bad/truncated chains fail closed.

Benchmark/scaling format version 2 uses `noisy=null` when CV is unknown.
`repeatability_assessed` requires >=3 observations and a usable CV; low CV is
not statistical significance. Legacy unknown-CV reports cannot establish a
plateau. Old historical JSON files remain unchanged: rerun raw CSV to update.

Optional `map_hotspot_calls.py` produces bounded static candidate graphs from
selected RTTI anchors, guarded by both executable and RTTI hash. Install
`python -m pip install -r tools/requirements-callgraph.txt` only for this tool.
Direct call, tail-jump candidate, code-address candidate, referenced callable
vtable slot and unresolved indirect sites are separate. This is linear metadata
range decoding, not runtime reachability or task-dependency reconstruction.

Commands and verification: [continuation report](../docs/superpowers/reports/2026-10-05-source-backed-continuation-ja.md).
