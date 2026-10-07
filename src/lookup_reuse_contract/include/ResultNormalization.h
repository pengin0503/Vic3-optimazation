// Classification of a synthetic native-style result value against an owned
// fixture. Pure arithmetic on uint64 values with checked bounds; the value is
// never dereferenced. Only PrimaryPositive and TailPositive carry a slot.
#pragma once

#include <cstddef>
#include <cstdint>
#include <optional>

#include "NativeFixture.h"

namespace lookup_contract {

enum class ResultClass { PrimaryPositive, TailPositive, EndSentinel, Fallback, InvalidPrimaryResult, Unknown };
inline constexpr std::size_t kResultClassCount = 6;

struct NormalizedResult {
    ResultClass kind = ResultClass::Unknown;
    std::optional<std::size_t> slot;
};

// An empty or invalid borrow classifies everything as Unknown.
NormalizedResult NormalizeResult(const FixtureBorrow& borrow, std::uint32_t key, OpaqueResult result) noexcept;

}  // namespace lookup_contract
