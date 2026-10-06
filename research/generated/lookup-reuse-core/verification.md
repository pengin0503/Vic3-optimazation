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

## Task 3 — offline shadow observer

RED (stub calls the original once, returns its result, writes no record):

```
$ build/lookup-reuse/lookup_reuse_tests --filter shadow_original_once_and_return
[FAIL] shadow_original_once_and_return: src/lookup_reuse/tests/ShadowComparisonTests.cpp:86: CHECK(eval.LastRecord().original == SearchResult{6}) failed
0/1 tests passed
exit=1
```

(The first build attempt failed on `-Wmissing-field-initializers` in the test
double under `-Werror`; default member initializers were added to the test
double and to `ComparisonRecord`. That was a compile error, not counted as RED.)

GREEN: direct GCC (`-Werror`) 26/26, CMake Release CTest 3/3, clang++ 18
`-Werror` 26/26, GCC `-fsanitize=address,undefined` 26/26.

Behaviour fixed by tests: the original callback runs exactly once per
`Evaluate` in every path (Off, missing scope/view, disabled session, reentrant
inner, hint hit); its normal return value is returned unchanged even when it
differs from the candidate (`mismatch_disables`) or points at another key's
slot (`shadow_wrong_key_result_not_remembered`, named apart from the Task 2
test of the same plan name); exceptions propagate unchanged and leave no record
or hint (`exception_then_next_call`); a reentrant inner call is bypassed and
invalidates the outer hint, so `candidate_hits` (2) differs from completed
comparisons (`equal` 1) in `reentrant_bypasses_and_invalidates_outer`; a
mismatch disables the session and Off→Shadow does not re-enable it.

Mutation spot-check: 12 mutants of `ShadowComparison.cpp` were run. Two real
gaps were found and closed: reentry while the outer call is ineligible
(missing view) did not test hint invalidation, and an inner exception caught by
the outer callback was untested (`reentrant_exception_caught_by_outer` added).
A redundant reset of the reentry flag in the exception guard was removed (the
outermost call resets it on entry). Clearing the hint in the scope destructor
is observationally equivalent to the clear in the next scope's constructor and
was kept as defence in depth.

Decisions within the plan's latitude:

- Skip priority for a non-reentrant call: `Off`, then `SessionDisabled`, then
  `MissingScope`, then `MissingView`. A reentrant call is always
  `Skipped/Reentrant` regardless of mode.
- A nested `ObserverScope` on the same evaluator throws `std::logic_error`
  without touching the active scope.
- An `Equal` comparison keeps the hint; a `NoCandidate` call passes the
  original result to `Remember`, which validates it or clears the hint.

## Task 4 — reproducible differential runner and acceptance

RED (runner stub returning an empty summary):

```
$ build/lookup-reuse/lookup_reuse_tests --filter repeatable_and_independent_membership
[FAIL] repeatable_and_independent_membership: src/lookup_reuse/tests/OfflineRunnerTests.cpp:41: CHECK(a.core_hits > 0) failed
0/1 tests passed
exit=1
```

Independence of expectations: membership comes from a `std::set` of drawn
keys; expected slots come from the runner's own Robin-Hood insertion /
backshift placement map. The validator and `ReferencePositiveSearch` are never
used to produce expectations, and the throwaway Python model
(`research/generated/employment-reuse-2026-10-07/model-source.py.txt`) was
neither imported nor ported. The query count is whatever this generator
produces (32,948); it was not tuned toward the earlier model's 25,676.

Runner sensitivity spot-check (scratch copies of the core, not committed):

| Mutant | membership / slot / observer mismatches | exit |
|---|---|---|
| hint ignores identity and mask | 0 / 0 / 0 (full-key check on the current slot still rejects stale slots) | 0 |
| hint ignores the current slot's control/key | 0 / 0 / 0 (identity check still rejects other snapshots) | 0 |
| both of the above removed | 0 / 19 / 0 | 1 |
| reference search ignores the key | 3,493 / 8,896 / 0 | 1 |
| FNV prime changed | 0 / 0 / 0 | 0 |

The last row is expected: runner placement uses the core `HashKey`, so a
consistent hash change is invisible to the differential run; the hash itself
is pinned by `fnv1a_hash_vectors` with independently computed vectors.

### Final verification (Linux container)

All commands from the repository root at the Task 4 tree.

| Check | Command | Result |
|---|---|---|
| Direct GCC Release tests | `g++ -std=c++20 -O2 -DNDEBUG -Wall -Wextra -Wpedantic -Isrc/lookup_reuse/include -Isrc/lookup_reuse/tests -Isrc/lookup_reuse/runner src/lookup_reuse/core/*.cpp src/lookup_reuse/runner/OfflineRunner.cpp src/lookup_reuse/tests/*.cpp -o build/lookup-reuse/lookup_reuse_tests && build/lookup-reuse/lookup_reuse_tests` | build exit 0, 29/29 passed, exit 0 |
| Direct GCC runner | `g++ … src/lookup_reuse/core/*.cpp src/lookup_reuse/runner/*.cpp -o build/lookup-reuse/lookup_reuse_runner && build/lookup-reuse/lookup_reuse_runner --seed 20261007 --rebuilds 1000 --output research/generated/lookup-reuse-core/results.json` | exit 0 |
| JSON well-formed | `python -m json.tool research/generated/lookup-reuse-core/results.json` | exit 0 |
| JSON / CLI | `python src/lookup_reuse/tests/VerifyRunner.py build/lookup-reuse/lookup_reuse_runner --expected research/generated/lookup-reuse-core/results.json` | all checks passed (13 CLI rejection cases incl. `/dev/full`) |
| CMake Release | `cmake -S src/lookup_reuse -B build/lookup-reuse -DCMAKE_BUILD_TYPE=Release -DLOOKUP_REUSE_WARNINGS_AS_ERRORS=ON`, `cmake --build build/lookup-reuse --config Release`, `ctest --test-dir build/lookup-reuse -C Release --output-on-failure` | 0 warnings; CTest 5/5 passed |
| CMake without Python | configure with `-DCMAKE_DISABLE_FIND_PACKAGE_Python3=ON` | 3 passed, `json_roundtrip_and_cli_rejection` and `runner_matches_committed_results` reported **Skipped** |
| clang++ 18 `-Werror` | tests and runner | 29/29; runner output byte-identical (`cmp` exit 0) after fixing one `-Wfor-loop-analysis` error in the CLI loop |
| GCC ASan + UBSan | tests and full fixed-seed runner | 29/29; runner output byte-identical |
| Existing Python suite | `python -m unittest discover -s tests -v` | 121 tests OK, 1 skipped (`set VIC3_DATA to Vic3_data.zip for integration test`) |
| Unchanged V3PF / targets | `git diff origin/main -- research/generated/native-profiler-v1-golden research/native-profiler-event-format.md research/native-profiler-runtime-targets-1.14.5.json research/native-target-overrides-1.14.5.json tools tests` | empty |

Python suite note: before installing `tools/requirements-callgraph.txt`
(`capstone==5.0.7`, as the existing CI does), the same suite had 3 errors
(`ModuleNotFoundError: No module named 'capstone'`) and 14 skips; after the
install it was 121 OK / 1 skip. Both observations were on the unmodified
base; this work does not touch those tests.

`results.json` (fixed seed 20261007, 1,000 rebuilds), SHA-256
`ea6753fabb6d911e156c1e92abefcbb30dbb2227fb00e6aa4e50c85d25f17d2f`:

- fixtures 2,004 (4 boundary + 2 × 1,000 seeded snapshots), queries 32,948
- membership mismatches 0, slot mismatches 0
- core caller: 5,355 hint hits, 27,593 reference searches
- shadow: 32,948 observed calls and candidate attempts, 5,355 candidate hits,
  5,355 equal, 0 mismatch, 9,256 original no-positive results, 0 skipped,
  0 reentrant, 0 dropped

These are lookup counts on synthetic tables. They are not timings and do not
show a game speedup, native equivalence or game-side memory safety.

### CI

`.github/workflows/lookup-reuse-core.yml` runs Release configure/build/CTest
and the fixed-seed runner on `ubuntu-24.04` (GCC) and `windows-2022` (MSVC),
compares the fresh run with the committed `results.json` (parsed JSON on both,
byte-identical on Linux). The MSVC result could not be run locally; see the
CI section appended below for what was actually observed.
