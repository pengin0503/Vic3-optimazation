# Phase 4 CPU runtime evidence gate

Date: 2026-10-12 (JST)
Parent: [offline CPU research design](2026-10-11-offline-cpu-research-design.md)

## Purpose and boundary

Complete Phase 4's offline evidence inventory, rejection checks and measurement handoff. The separate runtime acceptance gate remains blocked until actual game evidence exists. No game launch, new measurement, performance patch, main merge or repeated approval is part of this increment.

Existing benchmark quality checks, V3PF parser, exact target renderer and OS normalization/correlation remain authoritative and are reused. Historical CSV summaries, outer-envelope OS samples and synthetic Windows success must not fill missing runtime fields.

## Interface

`tools/check_cpu_runtime_gate.py`: `audit(document: dict, root: Path) -> dict` and CLI `INDEX --root ROOT --output REPORT`.

Index v1 contains the exact executable SHA-256, `artifacts`, `runs_root` (relative path or null), `reviews`, and `hypotheses`. Artifacts have unique `id`, root-relative `path`, SHA-256, `kind` (`static`, `historical`, `synthetic`, `game`) and `role`. Resolve and verify bytes before using any artifact. Reject absolute/escaping paths and duplicate identities; absent/mismatched bytes block readiness. No inferred file discovery outside the explicit run directory.

Run directory uses existing `manifest.json` / TickTask CSV conventions. Every discovered manifest and CSV must be indexed as game evidence. Each measured manifest adds `warmup_performed`, unique `execution_order`, fresh `native_profiler` process identity, attach/stop exit codes and artifact IDs, source commit, verified loader/DLL artifacts, initial identity hash log, raw V3PF, and an `os_capture` record with raw trace and exact boundary evidence. Build/save hashes, date interval, speed, pop consolidation, camera/UI and profiler binaries must be known and consistent. Require at least three repeats for disabled/enabled at both 12 and 16 threads, unique repeat IDs and alternating mode order per thread group. Do not change thread counts automatically.

Native checks reuse `parse_trace`: exact target table, disabled mask 0 or enabled mask 7, complete segment, all three enabled function pairs, no unexplained diagnostics. Conservatively block captures with any drops/diagnostics; retain details for review rather than suppressing them. Attach/stop log text and successful exit codes must agree. A metadata hash is not proof of actual game execution; `kind=game` and capture identity are operator declarations checked for consistency, not authentication.

Reuse `check_benchmark_quality.check` for raw CSV hashes, full frame/task/call fingerprints, repeats, CV and outliers. Report per-thread enabled/disabled median overhead and baseline CV without inventing a noise threshold or treating missing data as zero.

Four explicit review records cover `native_csv_relationship`, `observer_overhead`, `os_running_ready_waiting`, `save_stability`. Each accepted record identifies verified game review bytes, every measured run ID, and notes. OS evidence requires recorded exact boundaries, all Running/Ready/Waiting states and zero known loss; the actual exporter methodology/clock alignment and causality remain review judgments. A raw ETL is inventoried, not decoded by this tool. Save stability is reviewed; equal initial save hashes alone do not prove unchanged simulation state.

Output is deterministic JSON: verified inventory, per-run issues, benchmark quality, overhead (null when absent), explicit missing/rejected requirements, and `status=blocked|ready_for_review`. This is a mechanical completeness check, not automatic runtime acceptance or authorization of a performance patch. `performance_patch_authorized` remains false. Hypotheses require artifact references, a falsification condition and `runtime_verified=false`.

CLI returns 0 only for ready-for-review, 1 for a well-formed but blocked bundle, 2 for invalid schema/I/O. Write atomically; refuse output aliases of the index or any source artifact (including hard links). Never overwrite game data or evidence inputs.

## Completion evidence

- TDD for schema/provenance, missing data, forged declarations, parser/CSV failures, exact workload comparisons and review scope.
- Synthetic positive bundle is labeled synthetic testing; never count it as a captured game run.
- Audit current repository evidence and record every remaining runtime blocker and hypothesis/refutation condition.
- Prepare a null-filled capture template and manual, observation-only handoff using existing tools; no automatic process selection, game start or console setting.
- One final review, focused tests plus one repository Python suite; CI only if a changed platform dependency requires it.
