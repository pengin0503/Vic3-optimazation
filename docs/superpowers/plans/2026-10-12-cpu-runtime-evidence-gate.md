# Phase 4 CPU Runtime Evidence Gate Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans / Native. No implementation subagents.

**Goal:** Finish the offline Phase 4 gate and handoff, keeping actual runtime acceptance blocked when evidence is missing.
**Architecture:** A read-only bundle auditor wraps existing benchmark quality and V3PF/target validation. Current evidence is indexed by raw hash and class; future run manifests extend the existing format. No runtime instrumentation is added.
**Tech Stack:** Python standard library, existing unittest/tools, Markdown/JSON.
**Spec:** `docs/superpowers/specs/2026-10-12-cpu-runtime-evidence-gate-design.md`

## Global Constraints

- Exact SHA-256 `9b6f133a5dc235de9135d7b57e86ceda8282d1ba6c0e185f3ee19c22f8917f54`; preserve existing Phase 1–3 work.
- No game launch/measurement, state changes, scheduler/lock/parallelism/performance patch, or main merge.
- Save each verified task to `research/offline-cpu-parallelism-20261011` without force.
- Use focused local tests; one final Python suite. No Windows CI rerun for a standard-library Python/Markdown change.
- Missing measurements stay null/missing. Ready-for-review does not mean runtime accepted.

## Review Focus

- Synthetic/historical bytes must not certify game captures, even with matching metadata.
- Paths, symlinks and hard links must not allow evidence overwrite or root escape.
- Three targets, mode masks, error exit codes and parser diagnostics must agree.
- Missing identity/context, 12_r2-style extra frames, reused process sessions or repeat labels must block readiness.
- Review records must cover exact measured run IDs; initial save equality and outer OS markers cannot replace runtime judgment.

## Task 1: Provenance contract and inventory

**Files:** `tools/check_cpu_runtime_gate.py`, `tests/test_check_cpu_runtime_gate.py`.
**Interface:** `audit(document, root) -> deterministic dict` with inventory, issues, requirements, status and null overhead.

- [x] Write failing tests for empty/missing runtime evidence, valid inventory, wrong hash/version/types, duplicate IDs/paths, absolute/traversal/symlink escape, missing/mismatched bytes, unknown hypothesis reference and deterministic nonmutation. Expected: RED missing auditor.
- [x] Implement strict schema, confined artifact resolution/hash verification and static/historical/synthetic classification. Missing runtime evidence is blocked, not zero or success.
- [x] Run focused unittest. Expected: GREEN, no input mutation. Commit provenance task.

## Task 2: Runtime completeness checks and CLI

**Files:** same auditor/tests; consume existing benchmark quality, native parser and target renderer without rewriting them.
**Interfaces:** verified `runs_root` manifests + indexed raw artifacts; four scoped review records; CLI exit 0/1/2.

- [x] Add positive owned fixture for all four 12/16 × disabled/enabled groups, three repeats each, alternating order, exact CSV and all targets, plus explicit reviewed evidence. Expected: current implementation stays blocked (RED).
- [x] Add rejects for historical/synthetic runtime roles, missing identities/context, wrong target table/mask, drops/broken pairs, attach/stop disagreement, CSV extra frame/hash, insufficient/duplicate repeats, reused process instance, unknown OS boundary/states/loss and incomplete/rejected review scope.
- [x] Reuse the production parser/renderer/benchmark checker; calculate overhead only from complete groups. Return ready-for-review only after all mechanical checks, never performance-patch authorization.
- [x] Add CLI tests for blocked/invalid/ready exit codes, atomic output, duplicate JSON keys and input/artifact output aliases including hard links. Expected: each new behavior RED→GREEN.
- [x] Run focused suite plus existing quality/parser tests; commit runtime gate task.

## Task 3: Current audit and measurement handoff

**Files:** `research/phase4/` evidence index, report, null run template and README; Phase 4 report/guide and source-of-truth links; `.gitattributes` raw-hash evidence LF preservation.

- [x] Index current static evidence, historical repeats/OS/save records and Phase 3 Windows result by exact bytes. Record hypotheses and falsification conditions. Run the auditor twice and compare bytes; expected blocked with no game runtime captures and null overhead.
- [x] Create a null-filled measured manifest extension and exact manual capture/review workflow. Keep old measurements distinct; do not repair 12_r2 wall time or import stale CSV as synchronized OS evidence.
- [x] Run the complete repository Python suite once, scheduler model tests, generated checks and diff/link checks. Expected: no new failures; optional exact-input skips remain reported separately. No native/B0 rerun absent changes.
- [x] One final fresh review of Phase 4 work; fix material findings in one TDD pass. Record any unverified judgments.
- [x] Commit handoff/report, verify remote head and unchanged main. Report offline implementation complete and actual runtime gate blocked with exact evidence requirements.

## Execution decisions

User explicitly authorized uninterrupted Phase 4 continuation; approved parent design defines the offline workstream. No additional approval gate is introduced. Reuse the dedicated clean checkout. Equivalent ledger: `build/phase4-progress.md` (skill helper executables unavailable).
