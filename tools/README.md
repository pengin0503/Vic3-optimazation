# Tools

## `analyze_vic3.py`

Dependency-free static analysis for a local Victoria 3 install, executable, or ZIP archive.

```text
python tools/analyze_vic3.py C:\path\to\Vic3_data.zip \
  --output research/generated/static-analysis-local.json
```

It extracts SHA-256, PE metadata/sections, import/export tables, embedded PDB paths, source-path strings, `CTickTask_*` names, task/job/parallelism-related RTTI strings, and profiler/console commands. It writes derived JSON only.

For the 1.14.5 integration test:

```powershell
$env:VIC3_DATA = "C:\path\to\Vic3_data.zip"
python -m unittest discover -s tests -v
```

## `analyze_benchmarks.py`

```text
python tools/analyze_benchmarks.py benchmarks/runs \
  --json benchmarks/report.json \
  --markdown benchmarks/report.md
```

Reports TickTask cumulative cost, call counts, max record time, longest observed lock, run-to-run coefficient of variation, TaskThreadCount scaling, and later variant-vs-vanilla comparisons.

The report deliberately does not claim causality from a single timing metric.
