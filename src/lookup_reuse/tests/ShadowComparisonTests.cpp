// Contract tests for OfflineShadowEvaluator / ObserverScope.
// Fixture (mask 7, homes from FNV-1a): key0@5/control1, key8@6/control2;
// key 16 also homes at 5 and is absent.
#include <cstdint>
#include <stdexcept>

#include "ShadowComparison.h"
#include "TableView.h"
#include "TestSupport.h"

using namespace lookup_reuse;
using namespace lookup_reuse::test;

namespace {

constexpr TableIdentity kIdentity{11, 21, 1, kLayoutVersion};

std::unique_ptr<OwnedTableFixture> BaseFixture() {
    auto raw = RawSlots(10);
    PutSlot(raw, 5, 1, 0);
    PutSlot(raw, 6, 2, 8);
    return MakeFixture(kIdentity, 7, raw);
}

struct OriginalThrew {
    int id;
};

// Test double for the original lookup.
struct FakeOriginal {
    enum class Behavior { Reference, NoResult, ReturnSlot5, Throw, Reenter, ReenterCatch };

    const ValidatedTableView* view = nullptr;
    Behavior behavior = Behavior::Reference;
    int calls = 0;

    // Reenter: evaluate reenter_key through the same evaluator from inside the
    // callback, with an inner original that does the reference search.
    OfflineShadowEvaluator* evaluator = nullptr;
    std::uint32_t reenter_key = 0;
    FakeOriginal* inner = nullptr;
    ComparisonRecord inner_record{};
    SearchResult inner_result{};

    static SearchResult Invoke(void* context, std::uint32_t key) {
        auto& self = *static_cast<FakeOriginal*>(context);
        ++self.calls;
        switch (self.behavior) {
            case Behavior::Reference:
                return ReferencePositiveSearch(*self.view, key);
            case Behavior::NoResult:
                return std::nullopt;
            case Behavior::ReturnSlot5:
                return SearchResult{5};
            case Behavior::Throw:
                throw OriginalThrew{42};
            case Behavior::Reenter:
                self.inner_result =
                    self.evaluator->Evaluate(self.view, self.reenter_key, self.inner->Lookup());
                self.inner_record = self.evaluator->LastRecord();
                return ReferencePositiveSearch(*self.view, key);
            case Behavior::ReenterCatch:
                // The inner original throws; this outer original swallows it.
                try {
                    self.evaluator->Evaluate(self.view, self.reenter_key, self.inner->Lookup());
                } catch (const OriginalThrew&) {
                    self.inner_result = SearchResult{999};
                }
                return ReferencePositiveSearch(*self.view, key);
        }
        return std::nullopt;
    }

    OriginalLookup Lookup() { return OriginalLookup{this, &FakeOriginal::Invoke}; }
};

std::uint64_t Skipped(const OfflineShadowEvaluator& eval, SkipReason reason) {
    return eval.Counters().skipped_by_reason[static_cast<std::size_t>(reason)];
}

}  // namespace

LOOKUP_TEST(shadow_original_once_and_return) {
    const auto fixture = BaseFixture();
    const auto& view = fixture->View();
    FakeOriginal original{&view};
    OfflineShadowEvaluator eval;
    eval.SetMode(ObserverMode::Shadow);
    ObserverScope scope(eval);

    CHECK(eval.Evaluate(&view, 8, original.Lookup()) == SearchResult{6});
    CHECK(eval.LastRecord().status == ComparisonStatus::NoCandidate);
    CHECK(!eval.LastRecord().candidate);
    CHECK(eval.LastRecord().original == SearchResult{6});
    CHECK(eval.Evaluate(&view, 8, original.Lookup()) == SearchResult{6});
    CHECK(eval.LastRecord().status == ComparisonStatus::Equal);
    CHECK(eval.LastRecord().reason == SkipReason::None);
    CHECK(eval.LastRecord().candidate == SearchResult{6});
    CHECK(original.calls == 2);

    const auto& c = eval.Counters();
    CHECK(c.observed_calls == 2);
    CHECK(c.candidate_attempts == 2);
    CHECK(c.candidate_hits == 1);
    CHECK(c.equal == 1);
    CHECK(c.mismatch == 0);
    CHECK(c.fallback_or_no_positive == 0);
    CHECK(c.dropped_records == 0);
}

LOOKUP_TEST(mismatch_disables) {
    const auto fixture = BaseFixture();
    const auto& view = fixture->View();
    FakeOriginal original{&view};
    FakeOriginal changed_original{&view, FakeOriginal::Behavior::NoResult};
    OfflineShadowEvaluator eval;
    eval.SetMode(ObserverMode::Shadow);
    ObserverScope scope(eval);

    CHECK(eval.Evaluate(&view, 8, original.Lookup()) == SearchResult{6});
    CHECK(eval.Evaluate(&view, 8, original.Lookup()) == SearchResult{6});
    // The original result (nullopt) is returned, not the candidate.
    CHECK(!eval.Evaluate(&view, 8, changed_original.Lookup()));
    CHECK(eval.LastRecord().status == ComparisonStatus::Mismatch);
    CHECK(eval.LastRecord().candidate == SearchResult{6});
    CHECK(!eval.LastRecord().original);
    CHECK(eval.Counters().mismatch == 1);
    CHECK(eval.Counters().fallback_or_no_positive == 1);
    CHECK(eval.SessionDisabled());

    // Candidate computation has stopped for this session.
    CHECK(eval.Evaluate(&view, 8, original.Lookup()) == SearchResult{6});
    CHECK(eval.LastRecord().status == ComparisonStatus::Skipped);
    CHECK(eval.LastRecord().reason == SkipReason::SessionDisabled);
    CHECK(eval.Counters().candidate_attempts == 3);
    CHECK(Skipped(eval, SkipReason::SessionDisabled) == 1);
    CHECK(original.calls == 3);
    CHECK(changed_original.calls == 1);
}

LOOKUP_TEST(exception_then_next_call) {
    const auto fixture = BaseFixture();
    const auto& view = fixture->View();
    FakeOriginal original{&view};
    FakeOriginal throwing{&view, FakeOriginal::Behavior::Throw};
    OfflineShadowEvaluator eval;
    eval.SetMode(ObserverMode::Shadow);
    ObserverScope scope(eval);

    CHECK(eval.Evaluate(&view, 8, original.Lookup()) == SearchResult{6});
    CHECK(eval.Evaluate(&view, 8, original.Lookup()) == SearchResult{6});
    CHECK(eval.LastRecord().status == ComparisonStatus::Equal);

    bool caught = false;
    try {
        eval.Evaluate(&view, 8, throwing.Lookup());
    } catch (const OriginalThrew& error) {
        caught = error.id == 42;
    }
    CHECK(caught);
    CHECK(throwing.calls == 1);
    // No record is fabricated for the throwing call.
    CHECK(eval.LastRecord().status == ComparisonStatus::Equal);
    CHECK(eval.Counters().equal == 1);
    CHECK(eval.Counters().mismatch == 0);
    CHECK(!eval.SessionDisabled());

    // Next call: not treated as reentrant, and the old hint is gone.
    CHECK(eval.Evaluate(&view, 8, original.Lookup()) == SearchResult{6});
    CHECK(eval.LastRecord().status == ComparisonStatus::NoCandidate);
    CHECK(eval.Counters().reentrant_bypass == 0);
    CHECK(Skipped(eval, SkipReason::Reentrant) == 0);
    CHECK(original.calls + throwing.calls == 4);
    CHECK(eval.Counters().observed_calls == 4);
    CHECK(eval.Counters().candidate_attempts == 4);
    CHECK(eval.Counters().candidate_hits == 2);
}

LOOKUP_TEST(reentrant_bypasses_and_invalidates_outer) {
    const auto fixture = BaseFixture();
    const auto& view = fixture->View();
    OfflineShadowEvaluator eval;
    FakeOriginal plain{&view};
    FakeOriginal inner{&view};
    FakeOriginal outer{&view, FakeOriginal::Behavior::Reenter};
    outer.evaluator = &eval;
    outer.reenter_key = 0;
    outer.inner = &inner;
    eval.SetMode(ObserverMode::Shadow);
    ObserverScope scope(eval);

    // Prime the hint for key 8.
    CHECK(eval.Evaluate(&view, 8, plain.Lookup()) == SearchResult{6});
    CHECK(eval.Evaluate(&view, 8, plain.Lookup()) == SearchResult{6});
    CHECK(eval.Counters().candidate_hits == 1);

    CHECK(eval.Evaluate(&view, 8, outer.Lookup()) == SearchResult{6});
    CHECK(outer.calls == 1);
    CHECK(inner.calls == 1);
    CHECK(outer.inner_result == SearchResult{5});
    CHECK(outer.inner_record.status == ComparisonStatus::Skipped);
    CHECK(outer.inner_record.reason == SkipReason::Reentrant);
    CHECK(!outer.inner_record.candidate);
    CHECK(outer.inner_record.original == SearchResult{5});
    // The outer call found a candidate before the callback but must not compare.
    CHECK(eval.LastRecord().status == ComparisonStatus::Skipped);
    CHECK(eval.LastRecord().reason == SkipReason::Reentrant);
    CHECK(eval.LastRecord().original == SearchResult{6});

    const auto& c = eval.Counters();
    CHECK(c.reentrant_bypass == 1);
    CHECK(Skipped(eval, SkipReason::Reentrant) == 2);
    CHECK(c.candidate_hits == 2);
    CHECK(c.equal == 1);
    CHECK(c.candidate_hits != c.equal + c.mismatch);
    CHECK(c.candidate_attempts == 3);
    CHECK(c.observed_calls == 4);

    // The outer hint was invalidated.
    CHECK(eval.Evaluate(&view, 8, plain.Lookup()) == SearchResult{6});
    CHECK(eval.LastRecord().status == ComparisonStatus::NoCandidate);

    // Reentry also invalidates the hint when the outer call itself was not
    // eligible for a candidate (missing view).
    CHECK(eval.Evaluate(&view, 8, plain.Lookup()) == SearchResult{6});
    CHECK(eval.LastRecord().status == ComparisonStatus::Equal);
    const ValidatedTableView* missing = nullptr;
    CHECK(eval.Evaluate(missing, 8, outer.Lookup()) == SearchResult{6});
    CHECK(eval.LastRecord().reason == SkipReason::MissingView);
    CHECK(outer.inner_record.reason == SkipReason::Reentrant);
    CHECK(eval.Evaluate(&view, 8, plain.Lookup()) == SearchResult{6});
    CHECK(eval.LastRecord().status == ComparisonStatus::NoCandidate);
    CHECK(eval.Counters().reentrant_bypass == 2);
}

LOOKUP_TEST(off_missing_view_scope) {
    const auto fixture = BaseFixture();
    const auto& view = fixture->View();
    FakeOriginal original{&view};
    OfflineShadowEvaluator eval;

    // Default mode is Off.
    CHECK(eval.Mode() == ObserverMode::Off);
    {
        ObserverScope scope(eval);
        CHECK(eval.Evaluate(&view, 8, original.Lookup()) == SearchResult{6});
        CHECK(eval.LastRecord().status == ComparisonStatus::Skipped);
        CHECK(eval.LastRecord().reason == SkipReason::Off);
        CHECK(eval.LastRecord().original == SearchResult{6});
    }

    eval.SetMode(ObserverMode::Shadow);
    CHECK(eval.Evaluate(&view, 8, original.Lookup()) == SearchResult{6});
    CHECK(eval.LastRecord().status == ComparisonStatus::Skipped);
    CHECK(eval.LastRecord().reason == SkipReason::MissingScope);

    // A rejected snapshot (layout 2) yields no view; the nullptr path still
    // runs the original once.
    auto raw = RawSlots(10);
    TableIdentity v2 = kIdentity;
    v2.layout_version = 2;
    auto rejected = OwnedTableFixture::Create(v2, 7, 10, raw);
    CHECK(std::holds_alternative<ViewError>(rejected));
    const ValidatedTableView* missing = nullptr;
    {
        ObserverScope scope(eval);
        CHECK(eval.Evaluate(missing, 8, original.Lookup()) == SearchResult{6});
        CHECK(eval.LastRecord().status == ComparisonStatus::Skipped);
        CHECK(eval.LastRecord().reason == SkipReason::MissingView);
    }

    CHECK(original.calls == 3);
    CHECK(eval.Counters().observed_calls == 3);
    CHECK(eval.Counters().candidate_attempts == 0);
    CHECK(Skipped(eval, SkipReason::Off) == 1);
    CHECK(Skipped(eval, SkipReason::MissingScope) == 1);
    CHECK(Skipped(eval, SkipReason::MissingView) == 1);
    CHECK(Skipped(eval, SkipReason::None) == 0);
    CHECK(eval.Counters().mismatch == 0);

    // Skipped calls left no hint behind.
    ObserverScope scope(eval);
    CHECK(eval.Evaluate(&view, 8, original.Lookup()) == SearchResult{6});
    CHECK(eval.LastRecord().status == ComparisonStatus::NoCandidate);
}

LOOKUP_TEST(shadow_wrong_key_result_not_remembered) {
    const auto fixture = BaseFixture();
    const auto& view = fixture->View();
    FakeOriginal wrong{&view, FakeOriginal::Behavior::ReturnSlot5};
    OfflineShadowEvaluator eval;
    eval.SetMode(ObserverMode::Shadow);
    ObserverScope scope(eval);

    // The original's slot 5 (key 0) is returned unchanged for key 8 ...
    CHECK(eval.Evaluate(&view, 8, wrong.Lookup()) == SearchResult{5});
    CHECK(eval.LastRecord().status == ComparisonStatus::NoCandidate);
    // ... but never becomes a hint.
    CHECK(eval.Evaluate(&view, 8, wrong.Lookup()) == SearchResult{5});
    CHECK(eval.LastRecord().status == ComparisonStatus::NoCandidate);
    CHECK(eval.Counters().candidate_hits == 0);
    CHECK(wrong.calls == 2);
}

LOOKUP_TEST(mode_toggle_keeps_disabled) {
    const auto fixture = BaseFixture();
    const auto& view = fixture->View();
    FakeOriginal original{&view};
    FakeOriginal changed{&view, FakeOriginal::Behavior::NoResult};
    OfflineShadowEvaluator eval;
    eval.SetMode(ObserverMode::Shadow);
    ObserverScope scope(eval);
    eval.Evaluate(&view, 8, original.Lookup());
    eval.Evaluate(&view, 8, original.Lookup());
    eval.Evaluate(&view, 8, changed.Lookup());
    CHECK(eval.LastRecord().status == ComparisonStatus::Mismatch);

    eval.SetMode(ObserverMode::Off);
    CHECK(eval.Evaluate(&view, 8, original.Lookup()) == SearchResult{6});
    CHECK(eval.LastRecord().reason == SkipReason::Off);
    eval.SetMode(ObserverMode::Shadow);
    for (int i = 0; i < 2; ++i) {
        CHECK(eval.Evaluate(&view, 8, original.Lookup()) == SearchResult{6});
        CHECK(eval.LastRecord().status == ComparisonStatus::Skipped);
        CHECK(eval.LastRecord().reason == SkipReason::SessionDisabled);
        CHECK(!eval.LastRecord().candidate);
    }
    CHECK(eval.SessionDisabled());
    CHECK(eval.Counters().candidate_attempts == 3);
    CHECK(eval.Counters().candidate_hits == 2);

    // Only a new evaluator starts a new session.
    OfflineShadowEvaluator fresh;
    fresh.SetMode(ObserverMode::Shadow);
    ObserverScope fresh_scope(fresh);
    fresh.Evaluate(&view, 8, original.Lookup());
    CHECK(fresh.Evaluate(&view, 8, original.Lookup()) == SearchResult{6});
    CHECK(fresh.LastRecord().status == ComparisonStatus::Equal);
}

LOOKUP_TEST(scope_end_and_miss) {
    const auto fixture = BaseFixture();
    const auto& view = fixture->View();
    FakeOriginal original{&view};
    OfflineShadowEvaluator eval;
    eval.SetMode(ObserverMode::Shadow);
    {
        ObserverScope scope(eval);
        eval.Evaluate(&view, 8, original.Lookup());
        eval.Evaluate(&view, 8, original.Lookup());
        CHECK(eval.LastRecord().status == ComparisonStatus::Equal);
    }
    {
        ObserverScope scope(eval);
        CHECK(eval.Evaluate(&view, 8, original.Lookup()) == SearchResult{6});
        CHECK(eval.LastRecord().status == ComparisonStatus::NoCandidate);

        // Misses go to the original every time and are never remembered.
        for (int i = 0; i < 3; ++i) {
            CHECK(!eval.Evaluate(&view, 16, original.Lookup()));
            CHECK(eval.LastRecord().status == ComparisonStatus::NoCandidate);
            CHECK(!eval.LastRecord().original);
        }
        // A miss also clears the previous positive hint.
        CHECK(eval.Evaluate(&view, 8, original.Lookup()) == SearchResult{6});
        CHECK(eval.LastRecord().status == ComparisonStatus::NoCandidate);
    }
    CHECK(original.calls == 7);
    CHECK(eval.Counters().fallback_or_no_positive == 3);
    CHECK(eval.Counters().candidate_attempts == 7);
    CHECK(eval.Counters().candidate_hits == 1);
}

LOOKUP_TEST(nested_scope_rejected) {
    const auto fixture = BaseFixture();
    const auto& view = fixture->View();
    FakeOriginal original{&view};
    OfflineShadowEvaluator eval;
    eval.SetMode(ObserverMode::Shadow);
    ObserverScope scope(eval);
    eval.Evaluate(&view, 8, original.Lookup());

    bool rejected = false;
    try {
        ObserverScope nested(eval);
    } catch (const std::logic_error&) {
        rejected = true;
    }
    CHECK(rejected);
    // The outer scope and its hint are unaffected.
    CHECK(eval.Evaluate(&view, 8, original.Lookup()) == SearchResult{6});
    CHECK(eval.LastRecord().status == ComparisonStatus::Equal);
}

LOOKUP_TEST(reentrant_exception_caught_by_outer) {
    const auto fixture = BaseFixture();
    const auto& view = fixture->View();
    OfflineShadowEvaluator eval;
    FakeOriginal plain{&view};
    FakeOriginal throwing{&view, FakeOriginal::Behavior::Throw};
    FakeOriginal outer{&view, FakeOriginal::Behavior::ReenterCatch};
    outer.evaluator = &eval;
    outer.reenter_key = 0;
    outer.inner = &throwing;
    eval.SetMode(ObserverMode::Shadow);
    ObserverScope scope(eval);

    eval.Evaluate(&view, 8, plain.Lookup());
    CHECK(eval.Evaluate(&view, 8, outer.Lookup()) == SearchResult{6});
    CHECK(outer.inner_result == SearchResult{999});
    CHECK(throwing.calls == 1);
    CHECK(eval.LastRecord().status == ComparisonStatus::Skipped);
    CHECK(eval.LastRecord().reason == SkipReason::Reentrant);
    CHECK(eval.Counters().equal == 0);
    // Only the outer completion is recorded as a Reentrant skip.
    CHECK(Skipped(eval, SkipReason::Reentrant) == 1);

    // Depth is back to zero: the next call is not reentrant and has no hint.
    CHECK(eval.Evaluate(&view, 8, plain.Lookup()) == SearchResult{6});
    CHECK(eval.LastRecord().status == ComparisonStatus::NoCandidate);
    CHECK(eval.Counters().reentrant_bypass == 1);
    CHECK(eval.Evaluate(&view, 8, plain.Lookup()) == SearchResult{6});
    CHECK(eval.LastRecord().status == ComparisonStatus::Equal);
}
