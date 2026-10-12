# Native Windows Offline Validation Plan

> **For agentic workers:** Use superpowers:executing-plans (Native); no implementation delegation.

**Goal:** Complete the pending Windows x64 synthetic validation of Phase 3 without launching Victoria 3.

**Architecture:** Move the existing Windows job unchanged into a reusable workflow. The existing tests workflow calls it; a narrowly filtered push on the research branch also runs it. Documentation-only commits do not repeat CI. Reuse all existing native binaries, hosts and tests.

**Tech Stack:** GitHub Actions Windows 2022, Visual Studio 2022 x64 Release, CMake, CTest, Python 3.13.

**Spec:** `docs/superpowers/specs/2026-10-11-offline-cpu-research-design.md`

## Global Constraints

- Preserve latest main and research branch history; save only to `research/offline-cpu-parallelism-20261011`, never merge main.
- No game launch, additional game measurement, game state change or performance patch.
- Keep exact executable hash gate `9b6f133a5dc235de9135d7b57e86ceda8282d1ba6c0e185f3ee19c22f8917f54` and pinned MinHook commit unchanged.
- CI is the final Windows gate. Retry only when new evidence or a correction requires it.
- Synthetic Windows success does not prove real-game code 4 resolution or Phase 4 acceptance.

## Review Focus

- Existing main/PR/manual workflows retain the same Windows steps and read-only permissions.
- Research branch native changes trigger Windows; documentation changes do not.
- Build/CTest/parser failures fail the job, with useful logs retained.
- Named IPC, DLL lifecycle and MinHook tests actually execute rather than being skipped.
- Evidence identifies the tested commit and does not extend synthetic conclusions to a game process.

## Task 1: Reuse the Windows final gate

**Files:** `.github/workflows/tests.yml`, new `.github/workflows/native-validation.yml`.
**Interfaces:** Existing `jobs.native` becomes a local reusable-workflow call; the extracted job keeps its runs-on, steps and artifact names. The new workflow accepts `workflow_call`, `workflow_dispatch`, and research-branch pushes limited to native sources, its workflow, native generator/parser and golden fixture paths.

- [x] Preserve the current job as a local comparison baseline; validate YAML and compare the extracted job exactly against that baseline.
- [x] Extract the existing job, add the targeted trigger, and validate the old entry points, branch/path filters, permissions and unchanged commands. Expected: same native job, no documentation trigger.
- [x] Run both generated include checks and `git diff --check`. Expected: success. Configuration changes use structural checks rather than redundant production unit tests; any native defect is fixed with TDD and systematic-debugging.
- [x] Commit the plan and verified workflow configuration, then save the branch with an expected-head lease. Expected: one Windows final-gate run.

## Task 2: Execute and record Windows evidence

**Files:** Phase 3 report, Phase 2 gate review, `src/README.md`, native runtime guide, this plan.
**Interfaces:** GitHub run/job logs and `native-profiler-validation` artifact provide tested SHA, compiler, test count and trace evidence.

- [x] Observe configure/build/CTest/parser results and inspect retained evidence. Expected: all native tests pass; failures remain failures until diagnosed and corrected.
- [x] If a defect appears, read the exact error and implicated code first; use the failing Windows test/build as RED, make the smallest correction and repeat only the affected final gate. Do not weaken validation to make CI green.
- [x] Perform one fresh review of this continuation, preserving the already completed Phase 3 review. Address material findings in one fix pass.
- [x] Record exact run/commit, test names/counts, artifact provenance, any remaining Windows gaps and real-game conditions. Update references without erasing historical Linux-only results. Expected: no claim that synthetic injection resolves game code 4.
- [x] Check documentation links and `git diff --check`, commit results and verify the remote head. Expected: documentation commit causes no additional CI run; main unchanged.

## Execution decisions

The user already authorized uninterrupted continuation within the existing design. The dedicated checkout on the named branch remains the workspace; no second checkout is needed. Skill helper resources are unavailable as executables, so use `build/windows-validation-progress.md` as the equivalent local ledger.
