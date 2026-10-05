# GameState/UI synchronization candidate static analysis

Date: 2026-10-05  
Target: Victoria 3 Windows 1.14.5  
Executable SHA-256: `9b6f133a5dc235de9135d7b57e86ceda8282d1ba6c0e185f3ee19c22f8917f54`

## Scope

This is an import-driven, read-only static inventory. It identifies instruction-boundary validated references to Windows synchronization APIs that the exact executable actually imports. It does not infer a lock/wait primitive from arbitrary opcode patterns and does not assign a source-level function name to a caller group.

In particular, no caller is named `CScopedGameStateRelease`. Paradox's public architecture description establishes that profiler regions with that name existed in the described architecture, but the 1.14.5 evidence used here contains no direct symbol, RTTI, or string identity tying any mapped caller group to that source-level construct.

## Exact-build synchronization imports

The exact executable imports these candidate primitives from `KERNEL32.dll`:

| Import | IAT RVA |
|---|---:|
| `AcquireSRWLockExclusive` | `0x4386778` |
| `AcquireSRWLockShared` | `0x4386228` |
| `EnterCriticalSection` | `0x43865f0` |
| `LeaveCriticalSection` | `0x43865e8` |
| `ReleaseSRWLockExclusive` | `0x4386760` |
| `ReleaseSRWLockShared` | `0x4386230` |
| `SleepConditionVariableSRW` | `0x4386220` |
| `WaitForSingleObject` | `0x4386738` |

`WaitForMultipleObjects`, `WaitOnAddress`, and the `WakeByAddress*` APIs from the candidate inventory are not required or fabricated when absent from this executable's import table.

## Caller-map semantics

The mapper decodes only resolved x64 `RUNTIME_FUNCTION` groups and accepts only instruction-boundary references to the exact IAT slots. Evidence classes remain separate:

- `direct_iat_call`: a machine-indirect call whose RIP-relative memory operand is the exact IAT slot;
- `direct_iat_jump`: the corresponding IAT-resolved jump form;
- `iat_pointer_load`, `iat_slot_address`, and `iat_address_reference`: address/reference evidence, not invocation;
- unresolved indirect paths stay unresolved rather than receiving an import identity.

A `direct_iat_call` is not promoted to a direct native call edge: the machine instruction remains indirect through the IAT even though the imported API identity is statically resolved.

## Exact result

The exact 1.14.5 scan produced:

- 8 imported synchronization APIs;
- 3,996 instruction-boundary validated IAT references in 1,689 resolved caller groups;
- 3,579 `direct_iat_call` sites and 417 `direct_iat_jump` sites;
- 6 caller ranges with partial linear decode, preserved explicitly rather than treated as fully decoded;
- 0 groups skipped for the 65,536-byte group budget;
- 0 unresolved indirect sites associated with an accepted IAT address-load path in this result;
- 0 caller groups overlapping the already-known scheduler heuristic, range-runner, or dispatcher ranges.

Reference counts by imported API:

| Import | Validated references |
|---|---:|
| `AcquireSRWLockExclusive` | 1,867 |
| `ReleaseSRWLockExclusive` | 2,116 |
| `EnterCriticalSection` | 3 |
| `LeaveCriticalSection` | 2 |
| `SleepConditionVariableSRW` | 3 |
| `WaitForSingleObject` | 5 |
| `AcquireSRWLockShared` | 0 |
| `ReleaseSRWLockShared` | 0 |

The zero counts for the shared SRW imports mean only that no reference satisfying this mapper's resolved-unwind/instruction-boundary contract was emitted. They do not prove runtime non-use.

Likewise, the zero overlap with the three known scheduler/range regions is a bounded static location result, not evidence that GameState/UI synchronization cannot interact with those systems through callers, callees, indirect control flow, or runtime scheduling.

Generated artifacts:

- `research/generated/game-state-sync-followup-2026-10-05/sync-imports.json`
- `research/generated/game-state-sync-followup-2026-10-05/sync-callers.json`
- `research/generated/game-state-sync-followup-2026-10-05/artifact-index.json`

## Reproduction and determinism

```text
python -m pip install -r tools/requirements-callgraph.txt
python research/recipes/reproduce_game_state_sync_evidence.py \
  input-data/Vic3_data.zip \
  research/generated/game-state-sync-followup-2026-10-05
```

CI reproduced the recipe twice from the retained LFS archive. Both runs reported 8 imports and 3,996 validated references, and the generated artifacts were byte-identical. The same verification run also used the exact executable size and SHA-256 gate before analysis.

## Non-conclusions

This inventory does not establish runtime reachability, critical-path cost, wait duration, wait causality, thread ownership, a `CScopedGameStateRelease` identity, or any performance benefit. OS tracing is still required for those questions.

Nothing here authorizes DLL injection, detours, scheduler override, lock removal, simulation-state writes, cadence changes, or any other behavior-changing patch.
