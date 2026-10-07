# B0 offline native shadow contract — verification record

Plan: [`docs/superpowers/plans/2026-10-07-offline-native-shadow-contract.md`](../../../docs/superpowers/plans/2026-10-07-offline-native-shadow-contract.md)
Spec: [`docs/superpowers/specs/2026-10-07-offline-native-shadow-contract-design.md`](../../../docs/superpowers/specs/2026-10-07-offline-native-shadow-contract-design.md)
Base main: `f94a2d0333fedeb43f56a6ad880bd14fb2c79872` (fetched at the start of the work, 2026-10-07 UTC)

Environment (Linux container):

- Ubuntu 24.04, kernel 6.18.44
- g++ 13.3.0, clang++ 18.1.3 (`libclang-rt-18-dev` installed for Clang ASan/UBSan)
- CMake 3.28.3, Python 3.13.16 (`capstone==5.0.7` from `tools/requirements-callgraph.txt` for the existing suite)

This record lists commands that were actually run and their observed results.
Everything here concerns owned fixtures and synthetic 64-bit address values.
It says nothing about native equivalence, live memory lifetime, ABI, hook
relocation, real return addresses or game speed, and it does not satisfy the
Stage B native gate.

## Execution notes

Superpowers `executing-plans` (inline), `test-driven-development`,
`systematic-debugging` and `verification-before-completion` were used. Each
task observed RED before implementation. Beyond the planned tests, each task
was checked by temporary source mutations (reverted, not committed) to confirm
that its tests fail when the guarded rule is removed.

## Task 1 — manifest and offline locator (`5efc13f`, fix `2c87dd1`)

RED: `python -m unittest discover -s tests -p 'test_lookup_contract_*.py'` →
34 errors (`render_lookup_contract_manifest.py` / `check_lookup_contract_locator.py` absent).

GREEN:

```
$ python -m unittest discover -s tests -p 'test_lookup_contract_*.py'
Ran 36 tests ... OK (skipped=1)        # exact-input test skipped: VIC3_DATA unset
$ python tools/render_lookup_contract_manifest.py --check   # exit 0
```

Mutations caught: unsigned rel32 decode, no zero-fill (file-backed) gate, no
`return = call + 5` check, no signature uniqueness check.

Exact-build locator (optional, executed). The LFS archive was fetched with
`git lfs pull --include=input-data/Vic3_data.zip`; its SHA-256
`79f4f6d2c54528be378ffb09aa2d62d02c1f01279b967dd3189178146d5e8c34` equals the
evidence `archive_sha256`.

```
$ VIC3_DATA=input-data/Vic3_data.zip python -m unittest discover -s tests -p 'test_lookup_contract_*.py'
Ran 36 tests ... OK                      # no skip
$ python tools/check_lookup_contract_locator.py input-data/Vic3_data.zip --output build/lookup-contract/locator.json
static locator witnesses match: entry 0xf3e040, 4 allowed / 2 excluded callers (static only)
```

`locator.json`: executable SHA-256 `9b6f133a…8f54`, entry match count 1,
callers 1–4 (`0x13b8632`, `0x10b7db4`, `0x10bd565`, `0x10bd66b`) and excluded
5–6 (`0x13b847c`, `0xc6b5ca`), every E8 destination `0xf3e040`, return = call
+ 5, `static_only: true`, `caller_entry_rva_verified: false` (caller entry
RVAs come from the evidence's unwind metadata and are not re-verified).

CI regression (fixed): the first MSVC job failed at the manifest `--check`
step with `artifact index: static evidence size or sha256 does not match`.
Windows `core.autocrlf` rewrote the hash-pinned `static-evidence.json`; the
evidence folder is now `-text` in `.gitattributes`, with tests for the
attribute and for CRLF rejection.

## Task 2 — owned fixtures and normalization (`1a129ff`)

RED: CMake generation failed (`core/NativeFixture.cpp` absent; API missing).
GREEN: `lookup_contract_tests` 20/20, CTest 7/7 including Stage A.

Mutations caught: descriptor-collision check, signed-mask limit, address
overflow, revoked flag in `Valid()`, primary/tail split, alignment check,
`InvalidPrimaryResult` classification.

## Task 3 — shadow, scope/session, records (`f185e53`)

RED: a stub `Evaluate` that only called the original made 20 shadow tests fail
and the null-callback test crash. GREEN: 46/46.

Mutations caught: outer invalidation (set and check), mode-epoch check, scope
check, session disable on mismatch, hint clear on exception, `LastRecord` on a
dropped record. One equivalent mutant: the hint clear at `NativeScope` entry
(a hint can only be remembered inside a scope, and scope exit plus every
out-of-scope skip already clear it).

Negative compile checks (CTest): `tests/negative/faults_header.cpp` fails with
`#error "TestFaults.h requires LOOKUP_CONTRACT_TESTING"`;
`tests/negative/seam_member.cpp` fails with `no member named
'fault_candidate_override_'` against the production core. The allocation test
replaces global `operator new` in the test binary and observed 0 allocations
over NoCandidate/Equal/tail/excluded/reentrant `Evaluate` calls,
normalization, `LastRecord` and `DrainRecords`.

## Task 4 — runner, CLI, CI (`f865d78`)

RED: `VerifyContractRunner.py` → runner executable absent.

Debugging during GREEN (systematic): the first run reported 1002 oracle
mismatches, one per fixture; the runner expected 1 callback for the reentrant
outer call, which legitimately observes its own and the inner callback.
Caller rotation initially put every Equal on callers 2/4; it now rotates by
fixture ordinal and key index. The B0 CMake scope lacked
`find_package(Python3)`, so the runner CTests were reported as skipped; fixed,
and CI now fails if `LastTest.log` contains `SKIPPED`.

Runner fault injection (core mutated, runner rebuilt, reverted): skip without
hint clear, class skip without clear, no outer invalidation, constant fixture
identity (address-only reuse), no ProofLost on revoke, tail treated as
primary, excluded callers allowed, exception without hint clear — each made
the runner exit 1 with 500–6012 oracle mismatches.

Fixed-seed results (`research/generated/lookup-reuse-contract/results.json`,
SHA-256 `caf35becdb9cf9bb9fedaa37be0e5a0f9051b48ce512637060d73ae57e4c159e`):

| item | value |
|---|---|
| seed / rebuilds | 20261007 / 1000 |
| fixtures (boundary) | 1002 (2) |
| Evaluate calls = callbacks = original_calls | 43,979 |
| oracle mismatches | 0 |
| Equal / NoCandidate / Mismatch | 7,423 / 21,244 / 0 |
| exceptions / reentrant inner calls | 1,002 / 1,002 |
| skips: Off / Reentrant / MissingScope / CallerExcluded / MissingFixture / ProofLost | 1,002 / 2,004 / 1 / 3,006 / 1,002 / 501 |
| skips: Tail / EndSentinel / Fallback / InvalidPrimary / Unknown | 879 / 1,002 / 1,002 / 1,907 / 2,004 |
| SessionDisabled | 0 (unreachable without the test-only seam) |
| dropped records (main run) | 0 |
| collector case | 257 calls, 1 dropped, 256 drained, 1 drained after refill |

Caller coverage (normal returns / compared / skipped): unknown 0:
1,002/0/1,002; allowed 1: 10,652/1,904/1,898; 2: 10,299/1,838/4,719;
3: 9,898/1,835/1,181; 4: 9,122/1,846/3,506; excluded 5 and 6: 1,002/0/1,002
each.

About 37 % of normal returns are skipped by design, and Mismatch is
unreachable in the production runner. Zero mismatches here is not evidence
of native equivalence; the Mismatch path and the permanent session stop are
proven only by `mismatch_disables_until_new_evaluator` with the test-only
seam.

## Local verification at the final head

```
python -m unittest discover -s tests -v                       # 193 tests OK (skipped=2: VIC3_DATA)
VIC3_DATA=input-data/Vic3_data.zip python -m unittest discover -s tests -p 'test_lookup_contract_*.py'   # OK, no skip
python tools/render_lookup_contract_manifest.py --check       # exit 0
python tools/render_native_profiler_targets.py --check        # exit 0
cmake -S src/lookup_reuse_contract -B build/lookup-contract -DCMAKE_BUILD_TYPE=Release -DLOOKUP_CONTRACT_WARNINGS_AS_ERRORS=ON
cmake --build build/lookup-contract --config Release
ctest --test-dir build/lookup-contract -C Release --output-on-failure   # 11/11
build/lookup-contract/lookup_contract_runner --seed 20261007 --rebuilds 1000 --output build/lookup-contract/results.json
python src/lookup_reuse_contract/tests/VerifyContractRunner.py build/lookup-contract/lookup_contract_runner --expected research/generated/lookup-reuse-contract/results.json   # all checks passed
git diff --check                                              # clean
```

Additional local configurations, all CTest 11/11 with warnings as errors:
Clang 18 Release, Clang 18 ASan+UBSan (`-fno-sanitize-recover=all`),
GCC 13 ASan+UBSan.

Preserved assets: `git diff --stat f94a2d0 -- src/lookup_reuse src/native
research/native-profiler-runtime-targets-1.14.5.json
research/generated/native-profiler-v1-golden research/generated/lookup-reuse-core`
is empty (Stage A code and results, native code, target JSON and V3PF golden
unchanged).

## CI

At `2c87dd1` (branch `claude/b0-offline-native-shadow-1nl7c8`):

- `lookup-reuse-contract` (push) run
  [37558045817](https://github.com/pengin0503/Vic3-optimazation/actions/runs/37558045817):
  success on all four jobs — gcc-release, clang-release, clang-asan-ubsan,
  msvc-x64-release. Each job ran codegen `--check`, the manifest/locator tests
  (exact input skipped), CTest, the no-`SKIPPED` check, `VerifyContractRunner
  --expected` and the fixed-seed JSON equality; Linux jobs also compared bytes.
  The MSVC log shows `100% tests passed, 0 tests failed out of 11`.
- `tests` (workflow_dispatch) run
  [37558051747](https://github.com/pengin0503/Vic3-optimazation/actions/runs/37558051747):
  success (Python full suite on ubuntu and the existing windows-2022 native
  job: target `--check`, x64 Release build, native CTest, V3PF parse).
- `lookup-reuse-core` (workflow_dispatch, at `f865d78`; no Stage A file changed
  afterwards) run
  [37557890534](https://github.com/pengin0503/Vic3-optimazation/actions/runs/37557890534): success.

The first `lookup-reuse-contract` run at `f865d78`
([37557874507](https://github.com/pengin0503/Vic3-optimazation/actions/runs/37557874507))
failed only in msvc-x64-release (CRLF regression described under Task 1).

## Not executed

- MSVC was not run locally; MSVC x64 Release evidence is CI only (see above).
- No real game, live process, loader, DLL or hook was run or changed. Task 9
  loader code 4, live read windows, worker/job scope, real pointer results,
  native ABI, leaf-hook relocation/unwind, actual return-address allowlist and
  observer overhead remain open (spec section 9).
- `caller_entry_rva` is not re-verified against `.pdata` by the locator.
