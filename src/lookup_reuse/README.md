# Lookup reuse core (Stage A, offline)

Portable C++20 static library, tests and offline runner for the
[employment lookup reuse / shadow design](../../docs/superpowers/specs/2026-10-07-employment-lookup-reuse-shadow-design.md),
implemented from the
[Stage A plan](../../docs/superpowers/plans/2026-10-06-offline-lookup-reuse-core.md).

**Scope.** Everything here runs on owned, immutable synthetic tables. There is
no native adapter, DLL, detour, live process memory, game input or lookup
bypass, and the library does not know Win32, MinHook or the profiler codec.
The V3PF v1 format, target IDs and goldens are untouched. Passing these tests
says nothing about native container equivalence, ABI, memory lifetime or game
speed.

## Components

| File | Responsibility |
|---|---|
| `include/TableView.h`, `core/TableView.cpp` | `OwnedTableFixture` copies bounded bytes and validates them before issuing a `ValidatedTableView`; FNV-1a `HashKey`; bounded `ReferencePositiveSearch` |
| `include/PositiveSlotHint.h`, `core/PositiveSlotHint.cpp` | One remembered positive primary slot (identity, mask, full key, index), re-validated on every `Try` |
| `include/ShadowComparison.h`, `core/ShadowComparison.cpp` | `OfflineShadowEvaluator` / `ObserverScope`: the original lookup runs exactly once, its result and exceptions pass through unchanged; the hint candidate is only compared |
| `runner/` | Fixed-seed differential runner and standalone JSON (runner-only formatting and I/O) |
| `tests/` | Release-safe `CHECK` tests, `--list` / `--filter <exact-name>`, `VerifyRunner.py` (JSON/CLI, stdlib only) |

### Table contract (layout_version 1)

40-byte little-endian records read field by field: control byte at +4
(`0` empty, otherwise non-wrapping probe distance from `HashKey(key) & mask`
plus 1, so at most 255), full uint32 key at +8. `mask` is `2^n - 1`; slots
`0..mask` are primary, later slots are tail. Validation rejects, in this order:
unsupported layout, invalid mask, size overflow, truncated span (byte size
mismatch, fewer slots than primary, or no empty terminator at the end),
inconsistent control, duplicate full key, and keys the normal probe cannot
reach (it stops when `control < distance + 1`).

### Ownership and identity

`OwnedTableFixture` and `ValidatedTableView` are neither copyable nor movable;
the view is borrowed and must not outlive its fixture. `TableIdentity`
(`map_id`, `storage_id`, `lifetime_epoch`, `layout_version`) is set by the
fixture owner, who advances the epoch on every mutation, relocation or
regeneration. The epoch is an offline construct, not an assumed game field.

### Hint and shadow rules

- A hint is used only when identity, mask and full key match and the current
  primary slot at that index is occupied by the same full key; otherwise the
  caller runs the normal search (`NeedsOriginal`).
- Misses, tail slots, out-of-range or empty slots, and results pointing at a
  different key are never remembered.
- Modes: `Off` (default) and `Shadow`. There is no optimizing mode.
- Statuses: `NoCandidate`, `Equal`, `Mismatch`, `Skipped` (`Off`,
  `MissingView`, `MissingScope`, `Reentrant`, `SessionDisabled`).
- A mismatch stops candidate work for the rest of that evaluator's session;
  changing the mode does not re-enable it.
- A reentrant call bypasses candidate work and invalidates the outer hint; the
  outer call then completes as `Skipped/Reentrant`.

## Build and test

CMake (3.25+), from the repository root:

```bash
cmake -S src/lookup_reuse -B build/lookup-reuse -DCMAKE_BUILD_TYPE=Release
cmake --build build/lookup-reuse --config Release
ctest --test-dir build/lookup-reuse -C Release --output-on-failure
```

Add `-DLOOKUP_REUSE_WARNINGS_AS_ERRORS=ON` for `-Werror` / `/WX` (CI uses it).
With the Visual Studio generator the executables are under
`build/lookup-reuse/Release/`. If CMake finds no Python 3 interpreter, the
JSON/CLI tests are registered as explicitly *Skipped*.

Without CMake (GCC):

```bash
mkdir -p build/lookup-reuse
g++ -std=c++20 -O2 -DNDEBUG -Wall -Wextra -Wpedantic -Isrc/lookup_reuse/include -Isrc/lookup_reuse/tests -Isrc/lookup_reuse/runner src/lookup_reuse/core/*.cpp src/lookup_reuse/runner/OfflineRunner.cpp src/lookup_reuse/tests/*.cpp -o build/lookup-reuse/lookup_reuse_tests
build/lookup-reuse/lookup_reuse_tests
g++ -std=c++20 -O2 -DNDEBUG -Wall -Wextra -Wpedantic -Isrc/lookup_reuse/include -Isrc/lookup_reuse/runner src/lookup_reuse/core/*.cpp src/lookup_reuse/runner/*.cpp -o build/lookup-reuse/lookup_reuse_runner
python src/lookup_reuse/tests/VerifyRunner.py build/lookup-reuse/lookup_reuse_runner
```

MSVC without CMake: `cl /std:c++20 /O2 /DNDEBUG /EHsc /W4 /permissive- /Isrc\lookup_reuse\include ...`
with the same source lists.

## Runner

```bash
build/lookup-reuse/lookup_reuse_runner --seed 20261007 --rebuilds 1000 --output research/generated/lookup-reuse-core/results.json
```

`--seed` is an unsigned 32-bit decimal and `--rebuilds` a positive decimal;
signs, hex, overflow, duplicates and unknown options are rejected (exit 2).
`--output` may be omitted to write to stdout. Exit codes: 0 all comparisons
agreed, 1 a mismatch was seen (JSON is still written), 3 output I/O failure.

Each rebuild draws 1–16 unique full uint32 keys (`std::mt19937` raw output with
explicit modulo; small keys, shared low 24 bits and keys near `UINT32_MAX` are
mixed in), cycles masks 7/15/31, inserts them with a runner-local Robin-Hood
insertion, and validates two snapshots: a new storage, then the same storage at
a new epoch after one backshift deletion. Four seed-independent boundary
snapshots (tail, backshift before/after, mask 0 with `UINT32_MAX`) run first.
Expected membership comes from an independent `std::set` and expected slots
from the runner's own placement map; the validator and the reference search
are never used to generate expectations. Each query is checked through the
reference search, the core hint caller (`Try`, reference only on a miss) and
the shadow evaluator.

The committed [results](../../research/generated/lookup-reuse-core/results.json)
and [verification record](../../research/generated/lookup-reuse-core/verification.md)
come from this command. `core_hits` counts avoided reference searches in this
synthetic workload; it is not a timing and not evidence of a game speedup.

## Stage B is not started

Native shadow remains gated on the conditions in §8 of the design: exact-build
locator, internal ABI, hook entry, caller scope, worker lifetime, table
invariants, read lifetime, profiler prerequisites (Task 9 loader/DLL), and
observation cost with coverage. None of them is established by this directory.
