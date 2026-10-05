# Native Profiler Offline Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement and verify the offline wire-format/parser foundation for the future read-only native profiler without adding any game hook, DLL injection, or simulation modification.

**Architecture:** First remove remaining wire-format ambiguity, then implement a dependency-free Python reference codec/parser with synthetic golden traces. The parser validates build/target metadata, event alignment, per-thread sequence, begin/end pairing, truncation, unknown types, and dropped-event reporting. This plan deliberately does not model or claim lock-free C++ ring-buffer correctness.

**Tech Stack:** Python 3 standard library, struct/hashlib/json, unittest.

**Spec:** `research/native-profiler-event-format.md`  
**Parent design:** `docs/superpowers/specs/2026-10-04-native-performance-optimization-design.md`

## Global Constraints

- Observation only; no loader, injector, detour, hook, scheduler override, or state write.
- File format is little-endian and versioned.
- Unsupported format/build/target metadata fails closed.
- Per-thread order is authoritative; cross-thread total ordering is not invented.
- Parser reports broken pairs, sequence gaps, truncation, unknown event types, and dropped events.
- No hot-path performance claims can be made from the Python reference implementation.

## Review Focus

- Header extension/padding must not shift event boundaries silently.
- Unknown event types with valid `record_bytes` must be skippable and reported.
- Malformed `record_bytes` or non-8-byte alignment must terminate parsing of that segment.
- Begin/end correlation must never pair across threads.
- Target-table hash mismatch must invalidate target interpretation.

---

### Task 1: Pin the v1 wire layout in the spec

**Files:**
- Modify: `research/native-profiler-event-format.md`

**Interfaces:**
- Produces these v1 invariants for later tasks:
  - fixed prefix size: 112 bytes
  - offsets: magic 0, format_version 4, header_bytes 6, pointer_size 8, reserved[7] 9-15, qpc_frequency 16, session_start_qpc 24, executable_sha256 32, signature_db_version 64, target_table_hash 68, flags 100, total_dropped_events 104
  - `header_bytes >= 112` and multiple of 8
  - bytes `112:header_bytes` are UTF-8 metadata JSON followed by zero padding to the 8-byte boundary
  - metadata includes build IDs, profiler build ID, and `targets`
  - `target_table_hash` is SHA-256 of the exact UTF-8 JSON bytes of the metadata `targets` value encoded canonically with sorted keys and compact separators
  - common event header remains 24 bytes
  - every `record_bytes` is at least 24 and a multiple of 8; payload extension/padding bytes are skipped according to `record_bytes`

- [ ] **Step 1: Edit the spec only**

Clarify the exact byte layout and canonical target-table hashing. Do not add implementation yet.

- [ ] **Step 2: Self-check offsets and sizes**

Verify the fixed prefix totals exactly 112 bytes and leaves no implicit compiler padding assumptions.

- [ ] **Step 3: Commit**

Commit message: `docs: pin native profiler v1 wire layout`

---

### Task 2: Add shared v1 format constants and reference encoder

**Files:**
- Create: `tools/native_profiler_format.py`
- Create: `tests/test_native_profiler_format.py`

**Interfaces:**
- Produces constants for magic/version/event IDs and functions:
  - `canonical_target_bytes(targets: list[dict]) -> bytes`
  - `encode_header(metadata: dict, *, qpc_frequency: int, session_start_qpc: int, executable_sha256: str, signature_db_version: int, flags: int = 0, total_dropped_events: int = 0) -> bytes`
  - `encode_event(event: dict) -> bytes`
  - `encode_trace(header: bytes, events: list[bytes]) -> bytes`

- [ ] **Step 1: Write failing golden-vector tests**

Pin header offsets/length, target hash, 8-byte alignment, and one record for each known event type.

- [ ] **Step 2: Verify RED**

Run: `python -m unittest tests.test_native_profiler_format -v`.

- [ ] **Step 3: Implement the minimal reference encoder**

The encoder exists to create deterministic fixtures and future C++ cross-language golden vectors; it is not a runtime profiler writer.

- [ ] **Step 4: Verify GREEN**

Run focused tests.

- [ ] **Step 5: Commit**

Commit message: `feat: add native profiler wire-format reference codec`

---

### Task 3: Implement strict offline trace parsing and diagnostics

**Files:**
- Create: `tools/parse_native_profiler_trace.py`
- Create: `tests/test_parse_native_profiler_trace.py`
- Modify: `tools/README.md`

**Interfaces:**
- Produces: `parse_trace(data: bytes, *, expected_executable_sha256: str | None = None) -> dict`.
- Output includes `header`, `metadata`, `events`, `diagnostics`, and summary counters.
- Diagnostics include at least `unknown_event_type`, `sequence_gap`, `broken_begin_end`, `truncated_record`, `invalid_record_bytes`, `target_table_hash_mismatch`, and `build_mismatch`.

- [ ] **Step 1: Write failing parser tests**

Cover valid trace, unknown event skip/report, truncated record, bad alignment, bad header version, target hash mismatch, same-thread begin/end pair, cross-thread non-pair, sequence gap, and total dropped-events reporting.

- [ ] **Step 2: Verify RED**

Run: `python -m unittest tests.test_parse_native_profiler_trace -v`.

- [ ] **Step 3: Implement the parser**

Stop parsing a malformed buffer segment rather than guessing the next boundary. Do not sort events across threads into a synthetic total order.

- [ ] **Step 4: Verify GREEN**

Run focused tests.

- [ ] **Step 5: Commit**

Commit message: `feat: parse native profiler traces offline`

---

### Task 4: Add golden trace artifacts and future C++ compatibility contract

**Files:**
- Create: `research/generated/native-profiler-v1-golden/README.md`
- Create: `research/generated/native-profiler-v1-golden/trace-v1.bin`
- Create: `research/generated/native-profiler-v1-golden/trace-v1.json`
- Create: `tests/test_native_profiler_golden.py`
- Modify: `research/native-profiler-event-format.md`

**Interfaces:**
- Consumes: Tasks 2-3.
- Produces: one deterministic binary golden trace plus expected parsed JSON that a future C++ writer must reproduce semantically.

- [ ] **Step 1: Write the failing golden round-trip test**

The expected JSON is checked from the committed binary artifact; regeneration is a separate explicit command.

- [ ] **Step 2: Generate the fixture with the reference encoder**

Include multiple threads, one SchedulerDecision, one wait pair, FunctionBegin/End pairs, and a Counter event. Do not include invalid events in the primary golden file.

- [ ] **Step 3: Verify parser output against the expected JSON**

Run focused tests.

- [ ] **Step 4: Run full repository tests**

Run: `python -m unittest discover -s tests -v`  
Expected: PASS.

- [ ] **Step 5: Commit**

Commit message: `test: add native profiler v1 golden trace`

---

## Explicit stop point

After Task 4, stop. Do **not** implement:

- `Vic3OptimizationLoader.exe`
- `Vic3OptimizationProfiler.dll`
- process attach/injection
- any game-function detour
- scheduler/worker overrides
- Employment parallelization
- wait-hook installation
- simulation-state writes

Those remain behind the runtime evidence gate in the parent design.
