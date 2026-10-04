# Benchmarks

This directory stores small benchmark metadata and derived reports.

Raw game binaries, saves, ETL traces, and other large/proprietary captures are not committed here.

## Run layout

Each measured run uses:

```text
runs/<run-id>/
  manifest.json
  ticktask_timings.csv
```

Create manifests from `manifest.example.json` and follow `research/profiling-plan.md`.

Analyze all runs with:

```text
python tools/analyze_benchmarks.py benchmarks/runs \
  --json benchmarks/report.json \
  --markdown benchmarks/report.md
```
