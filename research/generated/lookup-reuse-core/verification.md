# Lookup reuse core (Stage A) — verification record

Plan: [`docs/superpowers/plans/2026-10-06-offline-lookup-reuse-core.md`](../../../docs/superpowers/plans/2026-10-06-offline-lookup-reuse-core.md)
Spec: [`docs/superpowers/specs/2026-10-07-employment-lookup-reuse-shadow-design.md`](../../../docs/superpowers/specs/2026-10-07-employment-lookup-reuse-shadow-design.md)
Base main: `788e29d34b6f5d00eb403183c4ecef51aac1480f` (fetched at the start of the work, 2026-10-06 UTC)

Environment (Linux container):

- Ubuntu 24.04, kernel 6.18.44
- g++ 13.3.0 (Ubuntu 13.3.0-6ubuntu2~24.04.1), clang++ 18.1.3 (cross-check only)
- CMake 3.28.3, CTest 3.28.3
- Python 3.13.16

This record lists commands that were actually run and their observed results.
Everything here is about an owned, immutable **synthetic** table. It says
nothing about native container equivalence, game memory safety or game speed.

## Execution notes

- The Superpowers skills named in the request (`executing-plans`,
  test-driven-development, verification-before-completion,
  systematic-debugging) are not installed in this environment. Their steps were
  followed manually: tests first, observed RED before implementation, GREEN on
  Release builds, root-cause analysis before any fix.
- CMake was available, so both the CMake/CTest path and the plan's direct GCC
  path were run.

## Task 1 — owned table and reference positive search

Hash definition check: the instruction witness in
`research/generated/employment-reuse-2026-10-07/evidence.json` shows
`xor eax,0x811c9dc5` on the first key byte followed by `imul …,0x1000193`
(FNV-1a order), and the probe compares `BYTE PTR [slot+0x4]` against a
distance counter starting at 1 with `jb` to the stop path. The reference search
therefore stops when `control < distance + 1`. The fixture home slots in the
plan (mask 7: keys 0/8/16 → 5, keys 2/10 → 7) were re-derived from the FNV-1a
definition and recorded as literals in `TableViewTests.cpp`; the tests do not
compute expected slots through `HashKey` or the reference search.

RED (API missing):

```
$ g++ -std=c++20 -O2 -DNDEBUG -Wall -Wextra -Wpedantic -Isrc/lookup_reuse/include -Isrc/lookup_reuse/tests src/lookup_reuse/tests/*.cpp -o build/lookup-reuse/lookup_reuse_tests
src/lookup_reuse/tests/TableViewTests.cpp:12:10: fatal error: TableView.h: No such file or directory
exit=1
```

RED (declaration-only stub returning typed error / nullopt):

```
$ build/lookup-reuse/lookup_reuse_tests --filter one_primary_and_max_key
[FAIL] one_primary_and_max_key: MakeFixture: fixture rejected with ViewError 0
0/1 tests passed
exit=1
$ build/lookup-reuse/lookup_reuse_tests --filter no_such
no test named: no_such
exit=2
```

GREEN (direct GCC, `-Werror` added):

```
$ g++ -std=c++20 -O2 -DNDEBUG -Wall -Wextra -Wpedantic -Werror -Isrc/lookup_reuse/include -Isrc/lookup_reuse/tests src/lookup_reuse/core/*.cpp src/lookup_reuse/tests/*.cpp -o build/lookup-reuse/lookup_reuse_tests
$ build/lookup-reuse/lookup_reuse_tests
9/9 tests passed   (fnv1a_hash_vectors, positive_search_fixed_layout, full_key_not_low24,
                    tail_positive_search, one_primary_and_max_key, invalid_layout_mask_size,
                    invalid_duplicate_distance_reachability, control_distance_overflow,
                    borrow_is_immutable)
exit=0
```

GREEN (CMake Release, `-DLOOKUP_REUSE_WARNINGS_AS_ERRORS=ON`): CTest 3/3
passed (`lookup_reuse_core_tests`, `lookup_reuse_tests_list`,
`lookup_reuse_tests_unknown_filter_fails` with `WILL_FAIL`). clang++ 18
`-Werror` build: 9/9 passed.

Mutation spot-check (scratch copy, not committed): removing the reachability
stop (`< needed` → `< 1`) and removing the empty-terminator check each made one
test fail. Four further mutants survived and were analysed as equivalent on
validated tables: dropping the `control == distance + 1` hit condition (a
unique key's slot always matches its distance), stopping only at empty slots
(absent keys still miss; only probe length changes and it is not observable
through the API), raising the distance limit (no reachable slot can sit at
distance 255), and removing `home > i` (unsigned underflow still mismatches the
control).

Naming note: the plan lists `tail_positive_never_cached` under both Task 1
(search portion) and Task 2. To keep `--filter` names unique, the Task 1 search
portion is `tail_positive_search`; Task 2 owns `tail_positive_never_cached`.

## Task 2 — single positive-slot hint

RED (stub `Try` always returns `std::nullopt`):

```
$ build/lookup-reuse/lookup_reuse_tests --filter repeat_hit_avoids_reference
[FAIL] repeat_hit_avoids_reference: src/lookup_reuse/tests/PositiveSlotHintTests.cpp:41: CHECK(hint.Try(view, 8) == SearchResult{6}) failed
0/1 tests passed
exit=1
```

GREEN: direct GCC (`-Werror`) 16/16 passed; CMake Release CTest 3/3 passed;
clang++ 18 `-Werror` 16/16 passed. `repeat_four_lookups_one_search` observed
one reference search for four lookups of key 8, each returning slot 6. This is
a lookup-count property of the offline core caller, not a speed measurement.

Mutation spot-check found one real gap: removing the `control != 0` check in
the hint survived because no test placed stale key bytes in an empty slot.
`full_key_and_uncacheable` now covers an empty slot carrying key 8 and the
zero-filled empty slots for key 0; the mutant then fails. Remaining survivors
were analysed as equivalent on validated views: the mask comparison (with an
unchanged identity, a different mask cannot keep key 8 in a primary slot of a
valid table — under mask 3 slot 6 is tail, under masks ≥ 15 key 8 homes at
13+; `identity_and_mask_changes` documents both cases) and the `occupied_`
flag (a cleared hint has layout_version 0, which no validated view has).
