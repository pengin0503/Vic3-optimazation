# Read-only native profiler event format and ring-buffer design

Date: 2026-10-05  
Target: Victoria 3 Windows 1.14.5  
Status: offline wire contract and reference tooling; no game hook, DLL injection, scheduler override, or simulation-state write is implemented by this document.

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

The v1 fixed prefix is **112 bytes**, without implicit compiler padding.
All integer fields are unsigned little-endian. Packed reference format:
`<4sHHB7xQQ32sI32sIQ` (the seven reserved bytes are zero).

| Field | Offset | Bytes |
| --- | ---: | ---: |
| magic (`V3PF`) | 0 | 4 |
| format_version (`1`) | 4 | 2 |
| header_bytes | 6 | 2 |
| pointer_size (`8`) | 8 | 1 |
| reserved (all zero) | 9 | 7 |
| qpc_frequency (positive) | 16 | 8 |
| session_start_qpc | 24 | 8 |
| executable_sha256 (raw digest) | 32 | 32 |
| signature_db_version (`1` supported) | 64 | 4 |
| target_table_hash (raw digest) | 68 | 32 |
| flags | 100 | 4 |
| total_dropped_events | 104 | 8 |

`header_bytes >= 112`, at most 65528, and a multiple of 8. The extension
`112:header_bytes` is UTF-8 JSON followed by **0..7 zero padding bytes** to the
next 8-byte boundary. No JSON NUL terminator, BOM or duplicate keys. Metadata
must be a JSON object; nonfinite JSON numbers are prohibited. Its required fields
are `build_ids`, nonempty `profiler_build_id`, and a `targets` list.
`build_ids` contains these exact strings for the only supported build:

```json
{
  "caligula_branch": "release/1.14.5",
  "caligula_rev": "9f8281a37e85639359b3b0c2c5df0196e975ca4b",
  "clausewitz_branch": "caligula/release/1.14.x",
  "clausewitz_rev": "fd5e1dbd038c3c4a3f48a36abf60ebb42dd0ceef"
}
```

A target entry requires unique nonzero uint32 `target_id`, nonempty `name`,
`kind`, and a nonempty `ranges` list of half-open `begin_rva` / `end_rva` hex
strings. Ranges in each target do not overlap. IDs are scoped to this table;
no address is used as a stable identifier. Cross-target overlaps are legal
metadata and must not be used to choose an arbitrary range winner.
`target_id=0` is reserved for a target-independent Counter only.

`target_table_hash` is SHA-256 of the exact UTF-8 canonical JSON encoding of the
metadata `targets` value: sorted object keys, compact `,` / `:` separators,
`ensure_ascii=False`, no NaN/Infinity, no trailing newline. Array order remains
significant. Hash failure disables all target interpretation. Unsupported
executable/build IDs/signature version likewise yield no interpreted events.

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
- every `record_bytes` is at least 24, at most 65528, and a multiple of 8; payload extension/padding is skipped according to that size.
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

## Exact v1 payload layout

Offsets below are relative to the 24-byte event header's end. Padding is
explicit, zeroed by the reference encoder. A reader skips extension/padding
bytes beyond each type's minimum record size; it does not infer new fields.

| Type | Payload fields and byte offsets | Packed payload | Minimum record bytes |
| --- | --- | --- | ---: |
| FunctionBegin (1) | correlation_id 0 | `<Q` | 32 |
| FunctionEnd (2) | correlation_id 0, status_flags 8, padding 12..15 | `<QI4x` | 40 |
| SchedulerDecision (3) | correlation_id 0, range_begin 8, range_end 16, range_length 24, task_thread_count 32, decision 34, padding 35, reason_flags 36, chunk_or_work_count 40, padding 44..47 | `<QQQQHBxII4x` | 72 |
| WaitBegin (4) | correlation_id 0, wait_kind 8, padding 10..15, object_token 16 | `<QH6xQ` | 48 |
| WaitEnd (5) | correlation_id 0, result_flags 8, padding 12..15 | `<QI4x` | 40 |
| Counter (6) | counter_id 0, padding 4..7, signed value 8 | `<I4xq` | 40 |

Scheduler decision values: 0 unknown, 1 serial, 2 parallel. Range end must be
>= begin, and range_length equals end-begin. Optional scheduler statistics can
be carried in future extensions, which the v1 reference parser skips.
Sequence is uint32, starts at any value per thread, and wraps modulo 2^32.
Timestamps must be >= session start and nondecreasing per thread, never globally
sorted. Begin/End keys include thread, function/wait family, correlation ID,
and target ID. Duplicate begins invalidate the pair; broken or negative pairs
remain diagnostic rather than repaired. Unknown types with a valid size are
reported and skipped while their common headers still participate in sequence
and per-thread timestamp checks. Total drops are a header count, not added to
Counter values (which may describe overlapping drop observations).

The future C++ writer must serialize fields at these exact offsets; an unpacked
C++ struct or implicit ABI padding is not a compatible wire format.

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
