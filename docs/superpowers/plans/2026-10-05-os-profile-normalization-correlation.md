# OS Profile Normalization and Correlation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prepare version-tolerant offline tooling that can ingest future WPA/AMD uProf CSV exports through explicit column mappings and correlate their addresses/threads with Victoria 3 native targets without pretending unknown export schemas are known.

**Architecture:** Define one normalized JSON schema, a mapping-driven CSV normalizer, a build-specific native target catalog, and a correlator. The importer never hard-codes unverified WPA/uProf column names; each export supplies an explicit mapping file. Correlation is address/range matching plus aggregation, not causal classification.

**Tech Stack:** Python 3 standard library, csv/json/decimal, existing generated RTTI/native mapping artifacts, unittest.

**Spec:** `docs/superpowers/specs/2026-10-04-native-performance-optimization-design.md`  
**Supporting protocol:** `research/os-profiling-plan.md`

## Global Constraints

- No ETL/uProf database parser is implemented without a real fixture/schema.
- Unknown columns are ignored only when explicitly unmapped; required mapped columns missing from an export are errors.
- Preserve `run_id`, source tool, source filename, thread identity, raw stack text, and address provenance.
- Convert VA to RVA only when a module base is present and the module is the expected Victoria 3 executable.
- A matched RVA identifies a static target range only; it does not prove critical-path or wait causality.
- Raw large traces remain outside Git unless explicitly approved.

## Review Focus

- Localized decimal/CSV quoting must not silently corrupt numeric fields.
- Hex/decimal addresses and missing module bases must be distinguished.
- Negative durations/timestamps and impossible VA < module-base rows must be rejected.
- Build/run identity mismatches must prevent cross-run correlation.
- Duplicate target ranges/overlaps must be reported rather than arbitrarily choosing one.

---

### Task 1: Define normalized OS-profile schema and mapping-driven CSV import

**Files:**
- Create: `research/os-profile-normalized-schema.md`
- Create: `tools/normalize_os_profile.py`
- Create: `tests/test_normalize_os_profile.py`
- Modify: `tools/README.md`

**Interfaces:**
- Produces: `normalize_csv(path: Path, mapping: dict, *, run_id: str, source: str) -> dict`.
- Mapping fields include `event_type`, `timestamp_column`, `timestamp_unit`, `thread_id_column`, and optional columns for process/module/module_base/instruction_va/duration/cpu_time/wait_time/context_switches/stack.
- Normalized timestamp/duration values are integer nanoseconds; addresses are integers internally and hex strings at the JSON boundary.

- [ ] **Step 1: Write failing tests**

Cover CPU sample, wait record, context-switch aggregate, quoted stack, hex address, decimal address, missing required column, invalid timestamp unit, negative duration, and unknown extra columns.

- [ ] **Step 2: Verify RED**

Run: `python -m unittest tests.test_normalize_os_profile -v`.

- [ ] **Step 3: Implement the schema and importer**

Use `decimal.Decimal` for unit conversion before integer nanoseconds. Keep `raw_source_row` optional/off by default so large exports do not balloon the normalized file.

- [ ] **Step 4: Verify GREEN**

Run focused tests.

- [ ] **Step 5: Commit**

Commit message: `feat: add mapping-driven OS profile normalizer`

---

### Task 2: Build a hash-gated Victoria 3 native target catalog

**Files:**
- Create: `tools/build_native_target_catalog.py`
- Create: `tests/test_build_native_target_catalog.py`
- Create: `research/native-target-overrides-1.14.5.json`
- Generate: `research/generated/native-target-catalog-1.14.5.json`

**Interfaces:**
- Produces: `build_catalog(rtti_doc: dict, overrides: dict, *, executable_sha256: str) -> dict`.
- Each target entry contains `target_id`, `name`, `kind`, one or more non-overlapping `ranges`, `source_evidence`, and `confidence`.
- `overrides` is limited to already documented dispatcher/range-heuristic and high-value callback/body ranges; it must cite the research artifact/doc that supports each range.

- [ ] **Step 1: Write failing tests**

Cover deterministic target IDs, wrong executable hash, overlapping ranges, duplicate names, and chained function-group ranges.

- [ ] **Step 2: Verify RED**

Run: `python -m unittest tests.test_build_native_target_catalog -v`.

- [ ] **Step 3: Implement catalog generation**

Use current RTTI/native artifacts for TickTask tail ranges and explicit overrides only for already documented non-TickTask targets. Do not add speculative ranges.

- [ ] **Step 4: Verify GREEN and generate the 1.14.5 catalog**

Run focused tests, then build the catalog and verify its recorded executable SHA-256.

- [ ] **Step 5: Commit**

Commit message: `research: add native target catalog`

---

### Task 3: Correlate normalized OS evidence with native ranges

**Files:**
- Create: `tools/correlate_os_profile.py`
- Create: `tests/test_correlate_os_profile.py`
- Modify: `tools/README.md`

**Interfaces:**
- Produces: `correlate(profile: dict, catalog: dict, *, expected_run_id: str | None = None) -> dict`.
- A row can match a target only when its module is Victoria 3, `instruction_va` and `module_base` are valid, and the derived RVA lies in exactly one target range.

- [ ] **Step 1: Write failing tests**

Cover exact range hit, no hit, overlapping hit error/report, wrong module, VA below base, run mismatch, build mismatch, and aggregation by target/thread/event type.

- [ ] **Step 2: Verify RED**

Run: `python -m unittest tests.test_correlate_os_profile -v`.

- [ ] **Step 3: Implement correlation and Markdown/JSON summary**

Aggregate counts plus CPU/wait/duration metrics only when those metrics exist in normalized rows. Preserve unmatched and invalid-address counts.

- [ ] **Step 4: Verify GREEN**

Run focused tests.

- [ ] **Step 5: Commit**

Commit message: `feat: correlate OS profile rows with native targets`

---

### Task 4: Document the future real-trace workflow without inventing vendor schemas

**Files:**
- Modify: `research/os-profiling-plan.md`
- Modify: `research/os-profile-normalized-schema.md`
- Modify: `tools/README.md`

**Interfaces:**
- Consumes: Tasks 1-3.
- Produces: exact workflow: export CSV from WPA/uProf -> create/verify mapping JSON -> normalize -> correlate -> inspect unmatched/invalid rows.

- [ ] **Step 1: Add documentation assertions/tests only where existing test conventions support them**

Do not add brittle tests for prose.

- [ ] **Step 2: Add example mapping templates with placeholder column names clearly marked as examples**

They must not be labeled as verified WPA/uProf schemas until a real export is supplied.

- [ ] **Step 3: Run full repository tests**

Run: `python -m unittest discover -s tests -v`  
Expected: PASS.

- [ ] **Step 4: Commit**

Commit message: `docs: define OS profile import and correlation workflow`
