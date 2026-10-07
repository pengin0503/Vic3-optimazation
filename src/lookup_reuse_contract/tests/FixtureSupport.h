// Test-only fixtures for the B0 contract.
//
// Slots are placed by hand and the expected slots / synthetic result values
// below are written as literals from this placement record (descriptor value =
// base + 40 * slot + 0x10). Nothing here derives expectations from the
// normalizer or the Stage A search. Home slots (FNV-1a, mask 7): key 0 -> 5,
// 8 -> 5, 2 -> 7, 10 -> 7; mask 0: every key -> 0.
#pragma once

#include <cstddef>
#include <cstdint>
#include <limits>
#include <memory>
#include <span>
#include <string>
#include <utility>
#include <variant>
#include <vector>

#include "NativeFixture.h"
#include "TestSupport.h"

namespace lookup_contract::test {

using lookup_reuse::test::CheckFailure;
using lookup_reuse::test::PutSlot;
using lookup_reuse::test::RawSlots;

inline constexpr std::uint64_t kFixedBase = 0x1000;
inline constexpr std::uint64_t kFixedSentinel = 0x8000;
inline constexpr std::uint64_t kFixedFallback = 0x9000;

// mask=7, 10 slots: key0@5/control1, key8@6/control2, key2@7/control1,
// key10@8/control2 (tail). Slot 1 is empty but keeps stale key bytes 0xdead.
inline std::vector<std::byte> FixedRaw() {
    auto raw = RawSlots(10);
    PutSlot(raw, 1, 0, 0xdead);
    PutSlot(raw, 5, 1, 0);
    PutSlot(raw, 6, 2, 8);
    PutSlot(raw, 7, 1, 2);
    PutSlot(raw, 8, 2, 10);
    return raw;
}

inline NativeFixtureSpec FixedSpec() {
    return NativeFixtureSpec{7, 10, kFixedBase, OpaqueResult{kFixedSentinel}, OpaqueResult{kFixedFallback}};
}

inline std::unique_ptr<OwnedNativeFixture> MakeNativeFixture(const NativeFixtureSpec& spec,
                                                             const std::vector<std::byte>& raw) {
    auto created = OwnedNativeFixture::Create(spec, raw);
    if (auto* error = std::get_if<FixtureError>(&created)) {
        throw CheckFailure("MakeNativeFixture: rejected with FixtureError kind " +
                           std::to_string(static_cast<int>(error->kind)));
    }
    return std::move(std::get<std::unique_ptr<OwnedNativeFixture>>(created));
}

inline std::unique_ptr<OwnedNativeFixture> MakeFixedFixture() {
    return MakeNativeFixture(FixedSpec(), FixedRaw());
}

// mask=0, 2 slots: key UINT32_MAX@0/control1, slot 1 empty.
inline std::unique_ptr<OwnedNativeFixture> MakeSinglePrimaryFixture(std::uint64_t base) {
    auto raw = RawSlots(2);
    PutSlot(raw, 0, 1, std::numeric_limits<std::uint32_t>::max());
    return MakeNativeFixture(NativeFixtureSpec{0, 2, base, OpaqueResult{0x8000}, OpaqueResult{0x9000}}, raw);
}

inline FixtureError ExpectFixtureError(const NativeFixtureSpec& spec, const std::vector<std::byte>& raw) {
    auto created = OwnedNativeFixture::Create(spec, raw);
    if (auto* error = std::get_if<FixtureError>(&created)) {
        return *error;
    }
    throw CheckFailure("ExpectFixtureError: fixture was accepted");
}

}  // namespace lookup_contract::test
