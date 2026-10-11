# Phase 4 evidence handoff

The offline evidence infrastructure is implemented. **Actual runtime acceptance is blocked.** No game capture was collected by this work.

- `current-evidence-index.json`: 13 existing source artifacts, byte hashes, static/historical/synthetic classification and three falsifiable hypotheses.
- `current-gate-report.json`: reproducible audit; provenance valid, zero accepted runtime captures, five missing requirements, overhead null.
- `run-manifest.template.json`: measured-run extension with unknown values explicitly null; not a captured `manifest.json`.
- `runtime-evidence-index.template.json`: future bundle index; empty artifacts/reviews do not pass.

Reproduce from repository root:

```sh
python tools/check_cpu_runtime_gate.py research/phase4/current-evidence-index.json --root . --output local-data/phase4-current-report.json
```

Exit **1** is expected for the current blocked evidence. Exit 0 means mechanically complete **ready for review**, not accepted game evidence or a performance patch. Exit 2 means invalid schema/I/O; an existing report may remain unchanged, so check the exit code before using output.

Index paths use forward slashes relative to `--root`. IDs/paths are unique, bytes must match lowercase SHA-256, and evidence cannot escape that root. Output cannot alias the index/artifacts, including hard links, or be placed inside the source run directory. Reports replace atomically after validation. Artifacts and the index are never written by the audit.

Future bundle artifacts identify `kind=game` only for actual collected game data. This label and the process/clock metadata are operator declarations: a matching metadata hash or a relabeled synthetic file is not proof of game execution. The checker validates consistency and keeps semantic/causal conclusions separate.

Each measured manifest uses the existing benchmark format plus the fields in the run template. Artifact IDs connect manifests to raw CSV, attach/stop/identity logs, V3PF, OS trace, exact boundary evidence and actual profiler binaries. The benchmark checker and native parser are reused. An unexplained parser diagnostic or any loss blocks the conservative automatic route; no diagnostic suppression or threshold bypass is supplied.

Reviews cover `native_csv_relationship`, `observer_overhead`, `os_running_ready_waiting` and `save_stability`. A record has `artifact_id`, `accepted`, `run_ids`, `notes`, and `evidence_sha256` (all non-review artifact IDs/digests). Reviews bind the exact capture bytes, not only reusable run labels. These are analyst evidence judgments, not requests for additional user approval. Missing data cannot be replaced by approval.

Raw ETL/state data and save semantics are not decoded/verified by this checker. Running/Ready/Waiting and clock alignment require source evidence and analysis; initial save equality does not prove long-run state stability. Overhead numbers are descriptive medians/CV from complete, valid matched comparisons, with no invented noise threshold. Performance patch authorization remains false.

See [capture guide](../../docs/superpowers/guides/2026-10-12-phase4-runtime-evidence-handoff-ja.md), [design](../../docs/superpowers/specs/2026-10-12-cpu-runtime-evidence-gate-design.md) and [execution report](../../docs/superpowers/reports/2026-10-12-cpu-runtime-evidence-gate-ja.md).
