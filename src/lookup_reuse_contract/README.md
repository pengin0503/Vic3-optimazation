# B0 offline native shadow contract

Portable C++20 library, tests and (Task 4) offline runner for the
[B0 contract design](../../docs/superpowers/specs/2026-10-07-offline-native-shadow-contract-design.md),
implemented from the
[B0 plan](../../docs/superpowers/plans/2026-10-07-offline-native-shadow-contract.md).
Status: in progress (Tasks 1-2 implemented).

**Scope.** Owned fixtures only. No live process memory, detour, native ABI
call, DLL, loader, Windows SDK or MinHook, and no lookup-bypass mode. Passing
these tests means only that the owned-fixture connection contract holds; it is
not evidence of native equivalence, ABI, memory lifetime or game speed, and it
does not satisfy the Stage B native gate (spec section 9).

## Components

| File | Responsibility |
|---|---|
| `../../tools/render_lookup_contract_manifest.py` | Derives the locator manifest from the pinned native-shadow static evidence and renders `generated/manifest_1_14_5.inc` (`--check` never writes) |
| `../../tools/check_lookup_contract_locator.py` | Offline exact-build locator: owned exe/ZIP/directory input, checked PE bounds, unique entry/caller signatures, signed rel32, return = call + 5. Static witnesses only |
| `include/NativeFixture.h`, `core/NativeFixture.cpp` | `OwnedNativeFixture` owns a validated copy (Stage A `OwnedTableFixture` underneath), private generation, revocation; `FixtureBorrow` pins the state |
| `include/ResultNormalization.h`, `core/ResultNormalization.cpp` | Classifies a synthetic 64-bit result value into six classes without dereferencing it |

## Fixture contract

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

## Build and test

```bash
cmake -S src/lookup_reuse_contract -B build/lookup-contract -DCMAKE_BUILD_TYPE=Release -DLOOKUP_CONTRACT_WARNINGS_AS_ERRORS=ON
cmake --build build/lookup-contract --config Release
ctest --test-dir build/lookup-contract -C Release --output-on-failure
python -m unittest discover -s tests -p 'test_lookup_contract_*.py' -v
```

The CTest run includes the Stage A tests (built from `../lookup_reuse` as a
subdirectory, unchanged).
