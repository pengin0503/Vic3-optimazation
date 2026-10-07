// Reproducible offline runner for the B0 contract.
//
// Builds owned native-shaped fixtures with a runner-local Robin-Hood
// insertion. The runner's own placement map records each key's slot; host
// callbacks return synthetic address values computed from that map
// (base + 40 * slot + 0x10), and the runner predicts every outcome from its
// own rule model, never from the normalizer or the Stage A search. Links the
// production core only (no fault seam), so it cannot force a mismatch.
// Results describe owned fixtures only.
#pragma once

#include <array>
#include <cstddef>
#include <cstdint>
#include <iosfwd>

#include "NativeRecords.h"

namespace lookup_contract::runner {

inline constexpr std::size_t kMaxRebuilds = 100000;
inline constexpr std::size_t kCallerRows = 7;  // unknown (0) and witnesses 1..6

struct RunConfig {
    std::uint32_t seed = 20261007;
    std::size_t rebuilds = 1000;
};

struct CallerCoverage {
    std::uint64_t calls = 0;     // normal returns attributed to this caller
    std::uint64_t compared = 0;  // Equal or Mismatch
    std::uint64_t skipped = 0;
};

struct CollectorCase {
    std::uint64_t calls = 0;
    std::uint64_t original_calls = 0;
    std::uint64_t dropped = 0;
    std::uint64_t drained = 0;
    std::uint64_t drained_after_refill = 0;
};

struct RunSummary {
    RunConfig config;
    bool default_mode_off = false;
    // Seed-independent boundary fixtures are included in fixture_count.
    std::uint64_t boundary_fixture_count = 0;
    std::uint64_t fixture_count = 0;
    // Evaluate calls on the main evaluator, including reentrant inner calls
    // and calls whose original threw.
    std::uint64_t query_count = 0;
    std::uint64_t callback_invocations = 0;
    // Any disagreement with the runner's placement map or rule model: return
    // value, callback count, status, reason, class, slots, record count,
    // exception identity.
    std::uint64_t oracle_mismatches = 0;
    NativeCounters native;
    std::array<CallerCoverage, kCallerRows> callers{};
    CollectorCase collector;
    // B0 never meets the Stage B native gate.
    bool all_game_gates_met = false;
};

RunSummary RunContract(const RunConfig& config);

bool Passed(const RunSummary& summary) noexcept;

void WriteJson(const RunSummary& summary, std::ostream& out);

}  // namespace lookup_contract::runner
