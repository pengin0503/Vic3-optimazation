# TickTask Dependency Static Reconstruction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reproducible, bounded static-evidence pipeline that maps the Victoria 3 1.14.5 TickTask registry/graph code and records only dependency relationships that static evidence can support.

**Architecture:** Extend the existing Python static-analysis toolkit rather than starting a new reverse-engineering stack. Start from the validated `TickTask.Graph` and `TickTask.List` handlers, reuse PE/unwind/RTTI helpers, and use bounded Capstone decoding. The output must separate confirmed static facts, candidates, and unresolved relationships; an incomplete graph is preferable to invented parent/child edges.

**Tech Stack:** Python 3, standard library, Capstone through `tools/requirements-callgraph.txt`, existing PE/RTTI/runtime-function helpers, unittest.

**Spec:** `docs/superpowers/specs/2026-10-04-native-performance-optimization-design.md`

## Global Constraints

- Target Victoria 3 Windows 1.14.5 executable SHA-256: `9b6f133a5dc235de9135d7b57e86ceda8282d1ba6c0e185f3ee19c22f8917f54`.
- Read-only/static work only; no injection, detour, scheduler override, state mutation, or performance patch.
- Build-specific RVAs are research metadata, never stable APIs.
- Exact-build/hash validation must fail closed.
- Static call/reference evidence does not prove runtime reachability, critical-path membership, lock causality, or optimization benefit.
- Do not broaden into full decompilation of Employment/Market/AI/Pop.

## Review Focus

- Wrong executable hash must stop analysis rather than emit a plausible-looking graph.
- Indirect calls/data references must not be mislabeled as dependency edges.
- Cycles, duplicate edges, and malformed/unbacked runtime-function metadata must remain explicit and deterministic.
- Unmapped TickTask names must stay unresolved rather than being guessed from nearby strings.
- Analysis budgets must terminate cleanly on unexpectedly large graphs.

---

### Task 1: Add bounded TickTask graph evidence extraction

**Files:**
- Create: `tools/map_ticktask_dependencies.py`
- Create: `tests/test_map_ticktask_dependencies.py`
- Modify: `tools/README.md`

**Interfaces:**
- Consumes: `analyze_vic3.PE`, `analyze_vic3.read_input`, `RuntimeFunctionIndex`, and an RTTI JSON document compatible with `tools/map_ticktask_rtti.py`.
- Produces: `analyze_dependency_evidence(binary: bytes, logical_path: str, rtti: dict, *, graph_root_rva: int = 0x28cf820, list_root_rva: int = 0x28cf5b0, max_depth: int = 3, max_functions: int = 256) -> dict`.

- [ ] **Step 1: Write failing tests**

Cover: exact-hash rejection, deterministic traversal, budget stop, direct-call vs indirect-call separation, duplicate-edge deduplication, and unresolved evidence preservation.

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `python -m unittest tests.test_map_ticktask_dependencies -v`  
Expected: FAIL because the new module/interfaces do not exist.

- [ ] **Step 3: Implement the bounded extractor**

Use Capstone only through the existing optional dependency. Decode complete validated runtime-function groups from the two known command roots and bounded descendants. Record direct calls, tail-jump candidates, indirect-call sites, RIP-relative data references, referenced TickTask vtables/type descriptors, decode/budget failures, and provenance.

Output must contain at least:

- `format_version`
- `executable_sha256`
- `roots`
- `functions`
- `ticktask_references`
- `candidate_dependency_edges`
- `unresolved`
- `warning`

Do not emit a candidate dependency edge unless both endpoints can be identified as TickTask objects/classes and the edge has an explicit evidence record.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run: `python -m unittest tests.test_map_ticktask_dependencies -v`  
Expected: all focused tests PASS.

- [ ] **Step 5: Commit**

Commit message: `feat: add bounded TickTask dependency evidence extractor`

---

### Task 2: Classify static dependency evidence without inventing semantics

**Files:**
- Modify: `tools/map_ticktask_dependencies.py`
- Modify: `tests/test_map_ticktask_dependencies.py`
- Create: `research/ticktask-dependency-static-map.md`

**Interfaces:**
- Consumes: Task 1's `candidate_dependency_edges` and TickTask RTTI identities.
- Produces: each relationship with `source_task`, `target_task`, `evidence_kind`, `evidence_rvas`, and `confidence` where confidence is exactly one of `confirmed-static`, `candidate`, `unresolved`.

- [ ] **Step 1: Add failing classification tests**

Pin that a direct structural traversal with two resolved TickTask identities can become `confirmed-static`, while an indirect call, shared helper, or one-sided identity cannot.

- [ ] **Step 2: Verify RED**

Run: `python -m unittest tests.test_map_ticktask_dependencies -v`.

- [ ] **Step 3: Implement minimal classification and Markdown rendering**

The Markdown must explain what was recovered, what remains unresolved, and why the result is not runtime proof. If no parent/child relationship reaches `confirmed-static`, state that clearly instead of weakening the threshold.

- [ ] **Step 4: Verify GREEN**

Run the focused tests.

- [ ] **Step 5: Commit**

Commit message: `research: classify TickTask dependency evidence`

---

### Task 3: Add exact-build reproduction and generated artifacts

**Files:**
- Create: `research/recipes/reproduce_ticktask_dependency_evidence.py`
- Create: `tests/test_reproduce_ticktask_dependency_evidence.py`
- Create when exact input is available: `research/generated/ticktask-dependencies-1.14.5.json`
- Modify: `research/ticktask-dependency-static-map.md`

**Interfaces:**
- Consumes: `input-data/Vic3_data.zip` or a path supplied by `VIC3_DATA`, plus the exact-build RTTI output.
- Produces: deterministic JSON artifact and hashes/provenance needed to reproduce it.

- [ ] **Step 1: Write failing recipe tests**

Verify wrong hash fails closed, missing optional dependency reports the existing install instruction, and the artifact is deterministic for identical inputs.

- [ ] **Step 2: Verify RED**

Run: `python -m unittest tests.test_reproduce_ticktask_dependency_evidence -v`.

- [ ] **Step 3: Implement the recipe**

Prefer existing generated RTTI input when its executable hash matches; otherwise regenerate it through the existing mapper. Do not silently mix artifacts from different executable hashes.

- [ ] **Step 4: Run focused tests, then full repository tests**

Run:
- `python -m unittest tests.test_reproduce_ticktask_dependency_evidence -v`
- `python -m unittest discover -s tests -v`

Expected: PASS, with optional binary integration skipped only when the real input is unavailable.

- [ ] **Step 5: Run exact-input integration when available**

Run the recipe against the approved LFS `Vic3_data.zip`; record the generated artifact/hash and update the research note. An incomplete/unresolved result is acceptable if honestly represented.

- [ ] **Step 6: Commit**

Commit message: `research: reproduce TickTask dependency evidence`
