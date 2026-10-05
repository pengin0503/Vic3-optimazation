# Read-only native profiler event format and ring-buffer design

Date: 2026-10-05  
Target: Victoria 3 Windows 1.14.5  
Status: design only; no game hook, DLL injection, scheduler override, or simulation-state write is implemented by this document.

## Goal

Define the minimum telemetry contract required by the Phase 4 read-only native profiler before any detour is written.

The profiler must answer:

- which validated native target ran
- on which OS thread
- when it began/ended
- whether the scheduler selected serial or parallel range execution
- what range/work size was visible at the decision point
- whether a measured thread entered a wait
- whether events were dropped
- which exact Victoria 3 build/signature database produced the trace

It must not change simulation behavior.

## File header

A trace file starts with a fixed little-endian header followed by versioned metadata.

Required fields:

| Field | Type | Purpose |
| --- | --- | --- |
| magic | 4 bytes | ASCII `V3PF` |
| format_version | uint16 | Starts at 1 |
| header_bytes | uint16 | Allows forward-compatible extension |
| pointer_size | uint8 | Must be 8 for current x64 target |
| qpc_frequency | uint64 | Convert QPC ticks to seconds |
| session_start_qpc | uint64 | Session reference point |
| executable_sha256 | 32 bytes | Exact `victoria3.exe` gate |
| signature_db_version | uint32 | Signature/target table revision |
| target_table_hash | 32 bytes | Hash of resolved target metadata |
| flags | uint32 | Address/token/privacy/feature flags |
| total_dropped_events | uint64 | Final aggregate drop count |

Build metadata additionally records the known 1.14.5 branch/revision strings and the profiler build identifier.

No absolute address is used as a stable target identifier. Runtime addresses may appear only as explicitly marked diagnostic tokens.

## Common event header

Every record is 8-byte aligned and begins with this 24-byte header:

| Field | Type |
| --- | --- |
| timestamp_qpc | uint64 |
| thread_id | uint32 |
| event_type | uint16 |
| record_bytes | uint16 |
| target_id | uint32 |
| sequence | uint32 |

Rules:

- `timestamp_qpc` comes from `QueryPerformanceCounter`.
- `thread_id` is the Windows thread ID.
- `target_id` indexes the validated target table in the file/session metadata.
- `sequence` is monotonic per thread buffer. It does not require a global atomic counter.
- unknown event types can be skipped using `record_bytes`.
- a malformed record terminates parsing of that buffer segment; parsers must not guess the next boundary.

## Event types

### 1. FunctionBegin

Payload:

- `correlation_id: uint64`

Purpose:

- begin timing of a validated function/function-family target.

### 2. FunctionEnd

Payload:

- `correlation_id: uint64`
- `status_flags: uint32`

The same thread-local correlation ID must pair Begin/End. Missing pairs are reported rather than repaired silently.

### 3. SchedulerDecision

Minimum payload:

- `correlation_id: uint64`
- `range_begin: uint64`
- `range_end: uint64`
- `range_length: uint64`
- `task_thread_count: uint16`
- `decision: uint8` — unknown / serial / parallel
- `reason_flags: uint32`
- `chunk_or_work_count: uint32`

Optional payload fields are emitted only if they are already available at the observed decision point without additional scanning or simulation work:

- heuristic threshold
- min
- max
- mean
- variance / standard deviation

The profiler must not compute expensive statistics in the hooked hot path merely to populate optional telemetry.

### 4. WaitBegin

Payload:

- `correlation_id: uint64`
- `wait_kind: uint16`
- `object_token: uint64`

`object_token` is process-local and unstable across runs. It is for grouping waits inside one trace, not for signatures.

### 5. WaitEnd

Payload:

- `correlation_id: uint64`
- `result_flags: uint32`

### 6. Counter

Payload:

- `counter_id: uint32`
- `value: int64`

Initial counters include:

- dropped events
- unknown target attempts
- signature validation failures
- thread-buffer exhaustion
- flush backlog high-water mark

## Ring-buffer architecture

### Writer path

Each observed game thread writes to a preallocated per-thread single-producer ring buffer.

The hot writer path must:

- allocate no heap memory
- perform no file I/O
- acquire no mutex/critical section
- avoid global sequence atomics
- write one bounded record or drop it
- increment a drop counter if insufficient space exists

Thread-buffer storage is allocated before target hooks are armed. A fixed pool is claimed by thread using a bounded lock-free/atomic registration path. If the pool is exhausted, tracing for that new thread fails closed and increments a diagnostic counter.

### Reader/flush path

One profiler-owned background thread:

- drains completed records from each ring
- writes binary chunks to disk
- periodically writes drop/backlog counters
- never blocks a game writer waiting for disk

If disk I/O falls behind, events are dropped rather than stalling simulation threads.

### Ordering

Guaranteed:

- record order inside one thread buffer
- per-thread monotonic `sequence`

Not guaranteed:

- exact total ordering between different OS threads

Offline correlation uses QPC timestamps plus per-thread sequence. Equal timestamps are not treated as a causal ordering proof.

## Target resolution contract

A target is armed only after all configured checks pass:

1. executable SHA-256 is supported
2. target signature matches expected count
3. target lies in an executable PE section
4. surrounding instruction/control-flow checks pass
5. RTTI/vtable cross-check passes when required
6. target metadata matches the signature DB version

Any required mismatch disables that target. A global unsupported-build result arms zero game hooks.

## Scheduler telemetry target

Current exact-build research identifies the scheduler/range-parallel heuristic family around:

- `MaybeRunRangeExecutionParallelWithHeuristic`
- static region currently mapped near `0x7db150–0x7dba91`
- common dispatcher candidate near `0x7dc160`

These are 1.14.5 research RVAs, not stable APIs. Runtime implementation must resolve them through the build/signature validation contract above.

## Parser invariants

An offline parser must report, never hide:

- dropped events
- unknown event types
- broken Begin/End pairs
- sequence gaps
- truncated records
- unsupported format version
- target-table hash mismatch
- trace/build mismatch

Derived duration:

`duration_qpc = end.timestamp_qpc - begin.timestamp_qpc`

Negative or cross-thread FunctionBegin/FunctionEnd pairs are invalid.

## Minimum useful Phase 4 capture

Before using telemetry to justify any optimization:

1. capture the same known heavy save and fixed 3-month interval used by the TickTask benchmark
2. preserve the run manifest and TickTask CSV
3. record one read-only native trace
4. record profiler enabled/disabled wall-clock measurements
5. prove the profiler overhead is below the benchmark's resolvable noise
6. correlate target timings with TickTask ranking and OS CPU/wait evidence

No native performance patch is justified merely because a SchedulerDecision reports serial execution.

## Explicit non-goals for the first prototype

Do not implement yet:

- scheduler return-value override
- forced chunk count
- worker-count override
- lock removal
- Employment parallelization
- state mutation
- automatic patching of unknown game builds

The first native milestone remains observation only.
