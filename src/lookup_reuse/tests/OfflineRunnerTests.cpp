// Tests for the offline differential runner. The JSON/CLI checks that need a
// Python interpreter live in VerifyRunner.py (CTest: json_roundtrip_and_cli_rejection).
#include <sstream>
#include <string>

#include "OfflineRunner.h"
#include "TestSupport.h"

using namespace lookup_reuse;
using namespace lookup_reuse::runner;

namespace {

bool SameCounters(const ObserverCounters& a, const ObserverCounters& b) {
    return a.observed_calls == b.observed_calls && a.candidate_attempts == b.candidate_attempts &&
           a.candidate_hits == b.candidate_hits && a.equal == b.equal &&
           a.mismatch == b.mismatch && a.fallback_or_no_positive == b.fallback_or_no_positive &&
           a.reentrant_bypass == b.reentrant_bypass && a.dropped_records == b.dropped_records &&
           a.skipped_by_reason == b.skipped_by_reason;
}

std::string Json(const RunSummary& summary) {
    std::ostringstream out;
    WriteJson(summary, out);
    return out.str();
}

}  // namespace

LOOKUP_TEST(repeatable_and_independent_membership) {
    auto a = RunOffline(RunConfig{20261007, 1000});
    auto b = RunOffline(RunConfig{20261007, 1000});
    CHECK(a.query_count == b.query_count);
    CHECK(a.fixture_count == b.fixture_count);
    CHECK(a.core_hits == b.core_hits);
    CHECK(a.reference_calls == b.reference_calls);
    CHECK(SameCounters(a.observer, b.observer));
    CHECK(Json(a) == Json(b));
    CHECK(a.membership_mismatches == 0);
    CHECK(a.slot_mismatches == 0);
    CHECK(a.core_hits > 0);
    CHECK(a.observer.observed_calls > 0);
    CHECK(a.observer.dropped_records == 0);
    CHECK(a.observer.mismatch == 0);
    CHECK(a.observer.equal > 0);
    CHECK(a.observer.fallback_or_no_positive > 0);
    CHECK(Passed(a));

    // Every query goes through the shadow evaluator once.
    CHECK(a.observer.observed_calls == a.query_count);
    // Every core query is either a hint hit or one reference search.
    CHECK(a.core_hits + a.reference_calls == a.query_count);
    // Two snapshots per rebuild plus the boundary fixtures.
    CHECK(a.fixture_count == 2 * 1000 + a.boundary_fixture_count);

    // A different seed generates different fixtures but still agrees.
    auto other = RunOffline(RunConfig{7, 50});
    CHECK(other.query_count != a.query_count);
    CHECK(Passed(other));
}

LOOKUP_TEST(boundary_fixtures_independent_of_seed) {
    const auto boundary = RunBoundaryFixtures();
    CHECK(boundary.boundary_fixture_count == 4);
    CHECK(boundary.fixture_count == 4);
    CHECK(boundary.query_count > 0);
    CHECK(boundary.core_hits > 0);
    CHECK(boundary.membership_mismatches == 0);
    CHECK(boundary.slot_mismatches == 0);
    CHECK(boundary.observer.mismatch == 0);
    CHECK(boundary.observer.equal > 0);

    // The boundary part is identical for any seed: a run with one rebuild
    // contributes exactly two seeded fixtures on top of it.
    for (std::uint32_t seed : {1u, 2u, 20261007u}) {
        const auto run = RunOffline(RunConfig{seed, 1});
        CHECK(run.boundary_fixture_count == 4);
        CHECK(run.fixture_count == 6);
        CHECK(run.query_count > boundary.query_count);
        CHECK(Passed(run));
    }
}

LOOKUP_TEST(json_contains_required_fields) {
    const auto summary = RunOffline(RunConfig{20261007, 3});
    const std::string json = Json(summary);
    for (const char* field :
         {"\"schema_version\": 1", "\"scope\": \"offline-synthetic\"", "\"seed\": 20261007",
          "\"rebuilds\": 3", "\"fixture_count\"", "\"query_count\"", "\"core_hits\"",
          "\"reference_calls\"", "\"membership_mismatches\"", "\"slot_mismatches\"",
          "\"observed_calls\"", "\"candidate_attempts\"", "\"candidate_hits\"", "\"equal\"",
          "\"mismatch\"", "\"fallback_or_no_positive\"", "\"reentrant_bypass\"",
          "\"dropped_records\"", "\"skipped_by_reason\"", "\"SessionDisabled\""}) {
        CHECK(json.find(field) != std::string::npos);
    }
    CHECK(json.back() == '\n');
    CHECK(json.find('\r') == std::string::npos);
}
