# B0 offline native shadow contract

Portable C++20 library, tests and (Task 4) offline runner for the
[B0 contract design](../../docs/superpowers/specs/2026-10-07-offline-native-shadow-contract-design.md),
implemented from the
[B0 plan](../../docs/superpowers/plans/2026-10-07-offline-native-shadow-contract.md).
Status: Tasks 1-4 implemented and verified; see the
[verification record](../../research/generated/lookup-reuse-contract/verification.md).

**Scope.** Owned fixtures only. No live process memory, detour, native ABI
call, DLL, loader, Windows SDK or MinHook, and no lookup-bypass mode. Passing
these tests means only that the owned-fixture connection contract holds; it is
not evidence of native equivalence, ABI, memory lifetime or game speed, and it
does not satisfy the Stage B native gate (spec section 9).

## Components

| File | Responsibility |
|---|---|
| `../../tools/render_lookup_contract_manifest.py` | Derives the locator manifest from the pinned native-shadow static evidence and renders `generated/manifest_1_14_5.inc` (`--check` never writes) |
| `../../tools/check_lookup_contract_locator.py` | Offline exact-build locator: owned exe/ZIP/directory input, checked PE bounds, unique entry/caller signatures, signed rel32, return = call + 5, and reconstructed caller roots from exception/chained-unwind metadata. Static witnesses only |
| `include/NativeFixture.h`, `core/NativeFixture.cpp` | `OwnedNativeFixture` owns a validated copy (Stage A `OwnedTableFixture` underneath), private generation, revocation; `FixtureBorrow` pins the state |
| `include/ResultNormalization.h`, `core/ResultNormalization.cpp` | Classifies a synthetic 64-bit result value into six classes without dereferencing it |
| `include/NativeShadow.h`, `include/NativeRecords.h`, `core/NativeShadow.cpp` | `OfflineNativeShadow` / `NativeScope`: original exactly once, scope/session rules, fixed 256-record collector and saturating counters |
| `tests/TestFaults.h` | Test-only fault seam (`LOOKUP_CONTRACT_TESTING`): candidate override before comparison, generation/session/scope exhaustion. Built only into `lookup_contract_test_core` and the unit test executable |

## Fixture contract

The locator now sets `caller_entry_rva_verified=true` only after reconstructing
all six caller roots from the owned executable. Each caller carries
`caller_metadata` with disjoint ranges and runtime-function fragments.
This is metadata association, not validation of unwind operations, native ABI,
hook safety or actual runtime return addresses. Output protection also refuses
external hard links to an executable selected from a directory input; it is
not a security boundary against concurrent filesystem replacement.
See the [offline hardening verification](../../docs/superpowers/reports/2026-10-08-offline-locator-hardening-verification.md).

40-byte slots, control `+4`, uint32 key `+8`, descriptor value
`table_base + 40 * slot + 0x10`. Creation rejects, in this order: a mask above
`0x7fffffff` (not a non-negative native int32) or an address layout that
overflows, zero/equal declared sentinel and fallback values or values equal to
any slot's descriptor value (`AddressLayout`); generation exhaustion
(`EpochExhausted`, never wraps); and Stage A validation errors
(`TableValidation`).

| Class | Condition |
|---|---|
| PrimaryPositive | primary descriptor position, occupied, full key equal |
| TailPositive | tail descriptor position, occupied, full key equal |
| EndSentinel / Fallback | equals the declared value |
| InvalidPrimaryResult | primary descriptor position, empty or different key |
| Unknown | everything else (0, below base, misaligned, past the end, tail failures, invalid borrow) |

## Shadow contract

- Default `Off`; the only other mode is `Shadow`. Every call with a non-null
  callback runs it exactly once and returns its 64-bit value unchanged;
  exceptions propagate as the same object, the hint is cleared and no record
  is written for that call.
- Order: reentrancy guard on every call; candidate only for Shadow, live
  session, active scope, allowed caller (generated witnesses 1..4) and a valid
  borrow; original; re-check (mode, session, inner call, scope, borrow, mode
  round trip); normalize; compare only `PrimaryPositive` with a candidate.
- Skip priority: Off, SessionDisabled, Reentrant, MissingScope,
  CallerExcluded, MissingFixture, ProofLost, then the result-class reasons.
  Borrow invalid at entry is `MissingFixture`; lost during the callback is
  `ProofLost`. Every skip clears the hint; `NoCandidate` clears and remembers
  the verified original primary slot.
- A mismatch disables the evaluator's session for good; mode changes and new
  scopes do not revive it. Only a new evaluator starts a new session.
- `Evaluate`, normalization and record collection perform no heap allocation,
  I/O, mutex or full-table validation (allocation is counted in a test).

## Build and test

```bash
cmake -S src/lookup_reuse_contract -B build/lookup-contract -DCMAKE_BUILD_TYPE=Release -DLOOKUP_CONTRACT_WARNINGS_AS_ERRORS=ON
cmake --build build/lookup-contract --config Release
ctest --test-dir build/lookup-contract -C Release --output-on-failure
python -m unittest discover -s tests -p 'test_lookup_contract_*.py' -v
```

The CTest run includes the Stage A tests (built from `../lookup_reuse` as a
subdirectory, unchanged).
