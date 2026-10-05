# Source-Backed Offline Static Follow-ups Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the newly preserved public architecture evidence into exact-build, machine-readable static-analysis artifacts for Modifier Nodes, Employment stages, and GameState/UI synchronization candidates without introducing a runtime hook or changing simulation behavior.

**Architecture:** Reuse the existing 1.14.5 RTTI, chained-unwind, call/reference graph, exact-hash validation and recipe patterns. Add narrowly scoped reproducible analyses rather than a broad decompiler. Every output must separate direct calls, indirect sites, code-address materialization, RTTI/vtable evidence, imported synchronization APIs and semantic labels by provenance.

**Tech Stack:** Python 3 standard library, existing PE/RTTI/runtime-function helpers, optional Capstone already pinned by the repository, unittest, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-10-04-native-performance-optimization-design.md`

**Evidence:** `research/public-performance-architecture-evidence.md`

## Global Constraints

- Target build is Victoria 3 Windows 1.14.5; executable SHA-256 is `9b6f133a5dc235de9135d7b57e86ceda8282d1ba6c0e185f3ee19c22f8917f54`.
- Start from the latest `main`; do not treat the SHA current when this plan was written as fixed.
- Unsupported or mismatched builds fail closed.
- No DLL injection, detour, scheduler override, lock removal, simulation-state write, cadence change or performance patch.
- Static evidence never proves runtime reachability, critical-path cost, wait causality or performance benefit.
- Do not invent C++ field or function names from offsets.
- Preserve distinct edge classes: direct call, tail jump, indirect call/jump, code-address materialization and validated RTTI/vtable reference.
- Keep generated artifacts deterministic and reproducible from `input-data/Vic3_data.zip`.
- Use TDD for code changes and `verification-before-completion` before completion claims.
- Prefer Native / `executing-plans` if minimizing model usage is important.

## Review Focus

1. A wrong/missing executable hash must stop every new recipe before evidence is emitted; Task 1 and Task 3 tests must cover this.
2. An indirect callback or code pointer must never be promoted to a direct-call edge; Task 1 tests must cover this.
3. Employment stage names must retain provenance and `runtime_unverified=true`; Task 2 tests must reject unlabeled certainty.
4. A synchronization caller must not be named `CScopedGameStateRelease` merely because it calls a wait/lock API; Task 3 tests must enforce candidate-only semantics.
5. Re-running every recipe twice against the same exact input must produce byte-identical JSON/index artifacts; each task owns a determinism check.

---

### Task 1: Reproducible ModifierNode static follow-up

**Files:**
- Create: `research/recipes/reproduce_modifier_node_evidence.py`
- Create: `research/modifier-node-static-analysis.md`
- Create: `research/generated/modifier-node-followup-2026-10-05/modifier-node-callgraph.json`
- Create: `research/generated/modifier-node-followup-2026-10-05/modifier-node-selected-regions.json`
- Create: `research/generated/modifier-node-followup-2026-10-05/artifact-index.json`
- Test: `tests/test_modifier_node_static_followup.py`
- Reuse: `tools/map_hotspot_calls.py`, `tools/map_native_callers.py`, `tools/map_ticktask_rtti.py`, `tools/runtime_function_groups.py`

**Interfaces:**
- Consumes: exact 1.14.5 executable, the generated/current RTTI mapping, and `CTickTask_RecalculateModifierNodes`.
- Produces: deterministic exact-build JSON identifying the task tail virtual, bounded depth-2 native graph, selected decoded regions, caller evidence and explicit unresolved/uncertain paths.

- [ ] **Step 1: Write failing tests for exact-build resolution and edge separation**

Add tests that assert:
- the recipe resolves `CTickTask_RecalculateModifierNodes` by RTTI/class name rather than accepting a free-form guessed RVA;
- hash mismatch fails before output files are written;
- direct calls remain separate from indirect sites, code-address references and RTTI/vtable references;
- a selected region with partial decode fails closed;
- output includes an explicit warning that runtime reachability and optimization benefit are unproven.

Run: `python -m unittest tests.test_modifier_node_static_followup -v`  
Expected: FAIL because the recipe/output contract does not exist yet.

- [ ] **Step 2: Implement the exact-build reproduction recipe**

Implement `research/recipes/reproduce_modifier_node_evidence.py` so it:
- reads `victoria3.exe` through the existing input abstraction;
- verifies the exact SHA-256 first;
- obtains the current RTTI map or regenerates it using existing project helpers;
- resolves `CTickTask_RecalculateModifierNodes` and its `task_specific_tail_vfunc`;
- builds a bounded graph with `map_hotspot_calls.build_graph(..., max_depth=2)`;
- records whether known scheduler/range addresses from existing evidence appear only when they are actually reached by the bounded evidence;
- optionally maps direct callers with the existing caller mapper;
- emits deterministic JSON and artifact hashes.

Do not add a new general call-graph engine if existing helpers suffice.

- [ ] **Step 3: Run focused tests and reproduce against the real LFS input**

Run:
```bash
VIC3_DATA=input-data/Vic3_data.zip python -m unittest tests.test_modifier_node_static_followup -v
python research/recipes/reproduce_modifier_node_evidence.py input-data/Vic3_data.zip research/generated/modifier-node-followup-2026-10-05
```

Expected:
- focused tests PASS;
- recipe reports a resolved ModifierNode seed and deterministic artifact set;
- no game hook or state-changing output exists.

- [ ] **Step 4: Document only supported static conclusions**

Write `research/modifier-node-static-analysis.md` with:
- exact seed provenance;
- graph budget and decoded-byte coverage;
- direct/indirect/vtable/code-pointer evidence kept separate;
- any connection to shared range/scheduler helpers, only if actually observed;
- unresolved targets;
- explicit separation between Paradox's historical ModifierNode architecture and what is directly proven in 1.14.5.

Do not assign dirty-node field names from offsets.

- [ ] **Step 5: Verify deterministic regeneration**

Regenerate into a second temporary directory and compare every derived JSON/index byte-for-byte.

Run: `python -m unittest discover -s tests -v`  
Expected: full suite PASS with the normal existing optional-input behavior.

- [ ] **Step 6: Commit**

```bash
git add research/recipes/reproduce_modifier_node_evidence.py research/modifier-node-static-analysis.md research/generated/modifier-node-followup-2026-10-05 tests/test_modifier_node_static_followup.py
git commit -m "research: map modifier node native path"
```

---

### Task 2: Formalize the Employment stage target map

**Files:**
- Create: `tools/build_employment_stage_map.py`
- Create: `research/generated/employment-stage-map-1.14.5.json`
- Modify: `research/ticktask-dispatch-static-map.md`
- Test: `tests/test_build_employment_stage_map.py`

**Interfaces:**
- Consumes: existing dispatch/callback evidence under `research/generated/dispatch-followup-2026-10-05/`, plus exact-build metadata.
- Produces: one machine-readable target map for future OS/native-profiler correlation, with stage identity, address ranges, evidence provenance, confidence class and runtime-unverified status.

- [ ] **Step 1: Write failing schema/provenance tests**

Tests must require entries for at least:
- Employment Prepare,
- CollectEmployment candidate/continuation,
- SortEmployment callback,
- item-processing candidate,
- common dispatcher,
- range runner,
- scheduler heuristic.

Each entry must contain:
- stable project target ID/name,
- one or more exact-build RVA ranges or points,
- evidence type such as `rtti_type_name`, `static_control_flow`, `source_string`, `existing_exact_build_recipe`,
- confidence limited to `confirmed_static` or `candidate_static`,
- `runtime_unverified: true`.

The test must reject a schema that labels the whole `0x13b8310` duration as total Employment cost.

Run: `python -m unittest tests.test_build_employment_stage_map -v`  
Expected: FAIL because the builder does not exist.

- [ ] **Step 2: Implement the stage-map builder from existing artifacts**

Implement `tools/build_employment_stage_map.py` as a pure offline transformer/validator:
- read the existing exact-build dispatch/callback artifacts;
- require the expected executable hash;
- validate that referenced selected regions/ranges actually exist in the source artifacts;
- emit sorted deterministic JSON;
- do not re-decompile the binary or duplicate the dispatch recipe.

The stage labels must be derived from already preserved RTTI/static evidence; unknown helper semantics remain candidate labels.

- [ ] **Step 3: Generate and review the map**

Run:
```bash
python tools/build_employment_stage_map.py   --dispatch research/generated/dispatch-followup-2026-10-05/dispatch-regions.json   --callers research/generated/dispatch-followup-2026-10-05/scheduler-callers.json   --output research/generated/employment-stage-map-1.14.5.json
```

Expected: deterministic map containing the required stages and no runtime claims.

- [ ] **Step 4: Link the map from the human-readable dispatch note**

Update `research/ticktask-dispatch-static-map.md` with:
- the generated map path,
- its purpose for OS/native-profiler correlation,
- a note that stage identity does not imply measured inclusive cost.

- [ ] **Step 5: Verify determinism and full test suite**

Generate the file twice to separate paths and compare bytes.

Run: `python -m unittest discover -s tests -v`  
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add tools/build_employment_stage_map.py tests/test_build_employment_stage_map.py research/generated/employment-stage-map-1.14.5.json research/ticktask-dispatch-static-map.md
git commit -m "research: formalize employment stage targets"
```

---

### Task 3: Map GameState/UI synchronization candidates without naming unproven functions

**Files:**
- Create: `tools/map_sync_callers.py`
- Create: `research/recipes/reproduce_game_state_sync_evidence.py`
- Create: `research/game-state-sync-static-analysis.md`
- Create: `research/generated/game-state-sync-followup-2026-10-05/sync-imports.json`
- Create: `research/generated/game-state-sync-followup-2026-10-05/sync-callers.json`
- Create: `research/generated/game-state-sync-followup-2026-10-05/artifact-index.json`
- Test: `tests/test_map_sync_callers.py`

**Interfaces:**
- Consumes: PE import/IAT information from the existing analyzer, runtime-function/unwind metadata, exact 1.14.5 executable.
- Produces: validated static caller candidates for imported Windows synchronization primitives, with optional proximity/call-chain evidence to known game-state/scheduler regions; never emits an asserted `CScopedGameStateRelease` identity without direct symbol/RTTI/string evidence.

- [ ] **Step 1: Write failing PE/IAT caller tests**

Build minimal-PE fixtures that include/import representative synchronization APIs where the existing test helpers allow it, and assert:
- imported API name and IAT slot are recorded;
- only instruction-boundary validated references/calls are accepted;
- immediate bytes that resemble an IAT address are rejected;
- unresolved indirect paths remain unresolved;
- output uses `game_state_sync_candidate`, not `CScopedGameStateRelease`, when no direct identity evidence exists;
- hash mismatch stops the recipe.

Candidate APIs to inventory if present include:
`WaitForSingleObject`, `WaitForMultipleObjects`, `WaitOnAddress`, `SleepConditionVariableSRW`, `AcquireSRWLockExclusive`, `AcquireSRWLockShared`, `EnterCriticalSection`, and corresponding release/wake functions. Do not require APIs that the actual executable does not import.

Run: `python -m unittest tests.test_map_sync_callers -v`  
Expected: FAIL because the mapper does not exist.

- [ ] **Step 2: Implement an import-driven caller mapper**

Implement `tools/map_sync_callers.py` using the existing PE parser and instruction decoder:
- enumerate present synchronization imports/IAT slots;
- validate executable-section instruction references to those slots;
- associate each site with a resolved runtime-function group when available;
- classify direct IAT calls, address loads and unresolved indirection separately;
- optionally compute bounded reverse/forward relationships to already-known `gamestatetick.cpp`/dispatcher regions without fabricating source identity.

Do not scan for arbitrary lock-looking opcodes and call them synchronization functions.

- [ ] **Step 3: Add an exact-build reproduction recipe**

`research/recipes/reproduce_game_state_sync_evidence.py` must:
- verify exact executable SHA-256;
- run the import inventory/caller map;
- preserve deterministic JSON + artifact hashes;
- include a warning that OS tracing is required to establish wait duration and whether a candidate corresponds to GameState release.

- [ ] **Step 4: Run against the real input and document the result**

Run:
```bash
python research/recipes/reproduce_game_state_sync_evidence.py   input-data/Vic3_data.zip   research/generated/game-state-sync-followup-2026-10-05
```

Write `research/game-state-sync-static-analysis.md` documenting:
- which sync APIs are actually imported;
- validated caller groups;
- whether any group intersects/reaches existing game-state/scheduler evidence;
- all unresolved paths;
- why none is called `CScopedGameStateRelease` unless direct identity evidence was found.

An empty/weak result is valid and must be reported rather than expanded into broad speculative reverse engineering.

- [ ] **Step 5: Verify full suite and deterministic regeneration**

Run the recipe twice, compare bytes, then run:

`python -m unittest discover -s tests -v`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add tools/map_sync_callers.py research/recipes/reproduce_game_state_sync_evidence.py research/game-state-sync-static-analysis.md research/generated/game-state-sync-followup-2026-10-05 tests/test_map_sync_callers.py
git commit -m "research: map game state sync candidates"
```

---

## Final verification and handoff

After all three tasks:

- [ ] Re-run the exact-input integration suite with `VIC3_DATA=input-data/Vic3_data.zip`.
- [ ] Re-run all three new recipes into temporary directories and confirm committed generated artifacts are byte-identical.
- [ ] Confirm `git diff --check` is clean.
- [ ] Review every use of `confirmed_static`, `candidate_static`, `runtime_unverified`, `CScopedGameStateRelease`, `parallel`, `serial`, and `wait` for overclaiming.
- [ ] Update Issue #3 with links to the new static results. Do not close Issue #3.
- [ ] Do not start Issue #4 Task 9/native hooks from these static results alone.
