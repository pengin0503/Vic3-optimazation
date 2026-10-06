// Reproducible offline differential runner for the lookup reuse core.
//
// Builds synthetic owned tables with a runner-local Robin-Hood insertion and
// backshift deletion, keeps the expected membership in an independent
// std::set and the expected slot in the runner's own placement map, then
// compares the reference search, the core hint caller and the shadow
// evaluator against them. Results describe synthetic tables only.
#pragma once

#include <cstddef>
#include <cstdint>
#include <iosfwd>

#include "ShadowComparison.h"

namespace lookup_reuse::runner {

struct RunConfig {
    std::uint32_t seed = 20261007;
    std::size_t rebuilds = 1000;
};

struct RunSummary {
    RunConfig config;
    // Fixed boundary fixtures (independent of the seed) are included in
    // fixture_count and query_count; boundary_fixture_count says how many.
    std::uint64_t boundary_fixture_count = 0;
    std::uint64_t fixture_count = 0;
    std::uint64_t query_count = 0;
    // Core caller path: Try, and the reference search only when Try misses.
    std::uint64_t core_hits = 0;
    std::uint64_t reference_calls = 0;
    // Reference membership vs the independent key set.
    std::uint64_t membership_mismatches = 0;
    // Reference slot vs placement map, core slot vs reference, shadow return
    // vs reference.
    std::uint64_t slot_mismatches = 0;
    ObserverCounters observer;
};

// Seed-independent boundary fixtures only (tail, backshift, max key).
RunSummary RunBoundaryFixtures();

// Boundary fixtures followed by config.rebuilds seeded rebuilds.
RunSummary RunOffline(const RunConfig& config);

// True when no membership, slot or observer mismatch was seen.
bool Passed(const RunSummary& summary) noexcept;

void WriteJson(const RunSummary& summary, std::ostream& out);

}  // namespace lookup_reuse::runner
