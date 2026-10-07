// Fixed-size records and counters for the B0 offline shadow. B0-specific
// enums; the Stage A enums are not widened. Formatting and I/O belong to the
// runner.
#pragma once

#include <array>
#include <cstddef>
#include <cstdint>
#include <optional>

#include "NativeFixture.h"
#include "ResultNormalization.h"

namespace lookup_contract {

enum class NativeMode { Off, Shadow };

enum class NativeStatus { Equal, Mismatch, NoCandidate, Skipped };

// Precondition skips in priority order (Off .. ProofLost), then result-class
// skips. None is never counted.
enum class NativeSkip {
    None,
    Off,
    SessionDisabled,
    Reentrant,
    MissingScope,
    CallerExcluded,
    MissingFixture,
    ProofLost,
    TailPositive,
    EndSentinel,
    Fallback,
    InvalidPrimaryResult,
    UnknownResult,
};
inline constexpr std::size_t kNativeSkipCount = 13;

inline constexpr std::uint32_t kNativeRecordVersion = 1;
inline constexpr std::size_t kNativeRecordCapacity = 256;

struct NativeRecord {
    std::uint32_t version = kNativeRecordVersion;
    std::uint32_t caller_id = 0;
    std::uint32_t key = 0;
    std::uint64_t session_id = 0;
    std::uint64_t scope_id = 0;  // 0 when no scope was active
    NativeStatus status = NativeStatus::Skipped;
    NativeSkip reason = NativeSkip::None;
    // nullopt when the result was not normalized.
    std::optional<ResultClass> result_class;
    std::optional<std::size_t> candidate_slot;
    std::optional<std::size_t> original_slot;
    OpaqueResult original;
};

// All counters saturate instead of wrapping.
struct NativeCounters {
    std::uint64_t original_calls = 0;  // includes calls that threw
    std::uint64_t candidate_attempts = 0;
    std::uint64_t candidate_hits = 0;
    std::uint64_t equal = 0;
    std::uint64_t mismatch = 0;
    std::uint64_t no_candidate = 0;
    std::uint64_t reentrant_calls = 0;
    std::uint64_t exception_calls = 0;
    std::uint64_t dropped_records = 0;
    std::array<std::uint64_t, kNativeSkipCount> skipped_by_reason{};
    // Only calls whose result was normalized.
    std::array<std::uint64_t, kResultClassCount> result_class_counts{};
};

}  // namespace lookup_contract
