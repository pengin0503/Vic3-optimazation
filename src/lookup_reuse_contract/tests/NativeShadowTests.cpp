// Contract tests for OfflineNativeShadow / NativeScope: the original callback
// runs exactly once with its 64-bit result and exceptions unchanged, and every
// way the comparison can lose its proof clears the hint.
//
// Synthetic return RVAs come from the generated caller witnesses (spec section
// 3): 0x13b8637 = caller 1 and 0x10b7db9 = caller 2 (allowed), 0x13b8481 =
// caller 5 (excluded). Results use the FixtureSupport.h placement record.
#include <array>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <memory>
#include <optional>
#include <stdexcept>
#include <vector>

#include "FixtureSupport.h"
#include "NativeShadow.h"
#include "ResultNormalization.h"
#include "TestFaults.h"
#include "TestSupport.h"

using namespace lookup_contract;
using namespace lookup_contract::test;

namespace {

constexpr std::uint32_t kCaller1 = 0x13b8637;
constexpr std::uint32_t kCaller2 = 0x10b7db9;
constexpr std::uint32_t kExcluded = 0x13b8481;
constexpr std::uint32_t kUnknownCaller = 0x13b8638;
constexpr std::uint64_t kKey0Result = 0x10d8;  // key 0 at slot 5
constexpr std::uint64_t kU64Max = std::numeric_limits<std::uint64_t>::max();

struct Counting {
    std::uint64_t value = 0;
    int calls = 0;
    std::uint32_t last_key = 0;
};

OpaqueResult InvokeCounting(void* context, std::uint32_t key) {
    auto* c = static_cast<Counting*>(context);
    ++c->calls;
    c->last_key = key;
    return OpaqueResult{c->value};
}

OpaqueOriginal Fixed(Counting& c) { return OpaqueOriginal{&c, &InvokeCounting}; }

template <class F>
struct Trampoline {
    static OpaqueResult Invoke(void* context, std::uint32_t key) { return (*static_cast<F*>(context))(key); }
};

// Wraps any callable (owned by the caller) as an OpaqueOriginal.
template <class F>
OpaqueOriginal Call(F& f) {
    return OpaqueOriginal{&f, &Trampoline<F>::Invoke};
}

NativeRecord Last(const OfflineNativeShadow& s) {
    const auto record = s.LastRecord();
    CHECK(record.has_value());
    return *record;
}

std::uint64_t Skips(const OfflineNativeShadow& s, NativeSkip reason) {
    return s.Counters().skipped_by_reason[static_cast<std::size_t>(reason)];
}

// Key 0 via caller 1 with the original returning slot 5.
NativeRecord RunKey0(OfflineNativeShadow& s, const FixtureBorrow& b) {
    Counting c{kKey0Result};
    CHECK(s.Evaluate(b, 0, kCaller1, Fixed(c)).value == kKey0Result);
    CHECK(c.calls == 1);
    return Last(s);
}

void Warm(OfflineNativeShadow& s, const FixtureBorrow& b) {
    CHECK(RunKey0(s, b).status == NativeStatus::NoCandidate);
}

struct Marker {
    const void* token;
};

}  // namespace

LOOKUP_TEST(default_mode_is_off) {
    OfflineNativeShadow s;
    CHECK(s.Mode() == NativeMode::Off);
    CHECK(!s.SessionDisabled());
    CHECK(!s.LastRecord());
}

LOOKUP_TEST(original_once_all_modes_and_skips) {
    auto f = MakeFixedFixture();
    const auto b = f->Borrow();
    struct Case {
        std::uint32_t key;
        std::uint32_t return_rva;
        std::uint64_t value;
        NativeSkip reason;
        std::optional<ResultClass> result_class;
    };
    const Case shadow_cases[] = {
        {10, kCaller1, 0x1150, NativeSkip::TailPositive, ResultClass::TailPositive},
        {0, kCaller1, 0x8000, NativeSkip::EndSentinel, ResultClass::EndSentinel},
        {0, kCaller1, 0x9000, NativeSkip::Fallback, ResultClass::Fallback},
        {0, kCaller1, 0x1010, NativeSkip::InvalidPrimaryResult, ResultClass::InvalidPrimaryResult},
        {0, kCaller1, 0, NativeSkip::UnknownResult, ResultClass::Unknown},
        {0, kCaller1, kU64Max, NativeSkip::UnknownResult, ResultClass::Unknown},
        {0, kCaller1, 0x10d9, NativeSkip::UnknownResult, ResultClass::Unknown},
        {0, kExcluded, kKey0Result, NativeSkip::CallerExcluded, std::nullopt},
        {0, kUnknownCaller, kU64Max, NativeSkip::CallerExcluded, std::nullopt},
    };
    {
        OfflineNativeShadow s;  // Off by default
        Counting c{kU64Max};
        CHECK(s.Evaluate(b, 0, kCaller1, Fixed(c)).value == kU64Max);
        CHECK(c.calls == 1);
        CHECK(Last(s).reason == NativeSkip::Off);
        CHECK(!Last(s).result_class);
    }
    {
        OfflineNativeShadow s;
        s.SetMode(NativeMode::Shadow);  // no scope
        Counting c{0};
        CHECK(s.Evaluate(b, 0, kCaller1, Fixed(c)).value == 0);
        CHECK(c.calls == 1);
        CHECK(Last(s).reason == NativeSkip::MissingScope);
    }
    for (const Case& k : shadow_cases) {
        OfflineNativeShadow s;
        s.SetMode(NativeMode::Shadow);
        NativeScope scope(s);
        Counting c{k.value};
        CHECK(s.Evaluate(b, k.key, k.return_rva, Fixed(c)).value == k.value);
        CHECK(c.calls == 1);
        CHECK(c.last_key == k.key);
        const NativeRecord r = Last(s);
        CHECK(r.status == NativeStatus::Skipped);
        CHECK(r.reason == k.reason);
        CHECK(r.result_class == k.result_class);
        CHECK(r.original.value == k.value);
        CHECK(Skips(s, k.reason) == 1);
        CHECK(s.Counters().original_calls == 1);
    }
    for (const bool revoked : {false, true}) {
        OfflineNativeShadow s;
        s.SetMode(NativeMode::Shadow);
        NativeScope scope(s);
        auto g = MakeFixedFixture();
        FixtureBorrow borrow;
        if (revoked) {
            borrow = g->Borrow();
            g->Revoke();
        }
        Counting c{kKey0Result};
        CHECK(s.Evaluate(borrow, 0, kCaller1, Fixed(c)).value == kKey0Result);
        CHECK(c.calls == 1);
        CHECK(Last(s).reason == NativeSkip::MissingFixture);
        CHECK(!Last(s).result_class);
    }
}

LOOKUP_TEST(primary_warm_then_equal) {
    auto f = MakeFixedFixture();
    const auto b = f->Borrow();
    OfflineNativeShadow s;
    s.SetMode(NativeMode::Shadow);
    NativeScope scope(s);
    const NativeRecord first = RunKey0(s, b);
    CHECK(first.status == NativeStatus::NoCandidate);
    CHECK(!first.candidate_slot);
    CHECK(first.original_slot == std::optional<std::size_t>{5});
    const NativeRecord second = RunKey0(s, b);
    CHECK(second.status == NativeStatus::Equal);
    CHECK(second.reason == NativeSkip::None);
    CHECK(second.candidate_slot == std::optional<std::size_t>{5});
    CHECK(second.original_slot == std::optional<std::size_t>{5});
    CHECK(second.result_class == std::optional<ResultClass>{ResultClass::PrimaryPositive});
    CHECK(second.version == kNativeRecordVersion);
    CHECK(second.caller_id == 1);
    CHECK(second.key == 0);
    CHECK(second.session_id != 0);
    CHECK(second.session_id == first.session_id);
    CHECK(second.scope_id != 0);
    CHECK(second.scope_id == first.scope_id);
    CHECK(second.original.value == kKey0Result);
    const auto& n = s.Counters();
    CHECK(n.original_calls == 2);
    CHECK(n.candidate_attempts == 2);
    CHECK(n.candidate_hits == 1);
    CHECK(n.no_candidate == 1);
    CHECK(n.equal == 1);
    CHECK(n.mismatch == 0);
    CHECK(n.result_class_counts[static_cast<std::size_t>(ResultClass::PrimaryPositive)] == 2);
}

LOOKUP_TEST(caller_change_keeps_or_clears_hint) {
    auto f = MakeFixedFixture();
    const auto b = f->Borrow();
    OfflineNativeShadow s;
    s.SetMode(NativeMode::Shadow);
    NativeScope scope(s);
    Warm(s, b);
    Counting c{kKey0Result};
    s.Evaluate(b, 0, kCaller2, Fixed(c));  // another allowed caller
    CHECK(Last(s).status == NativeStatus::Equal);
    CHECK(Last(s).caller_id == 2);
    s.Evaluate(b, 0, kExcluded, Fixed(c));
    CHECK(Last(s).reason == NativeSkip::CallerExcluded);
    CHECK(Last(s).caller_id == 5);
    CHECK(RunKey0(s, b).status == NativeStatus::NoCandidate);  // the skip cleared the hint
    CHECK(c.calls == 2);
}

LOOKUP_TEST(fixture_change_has_no_candidate) {
    auto a = MakeFixedFixture();
    auto other = FixedRaw();
    PutSlot(other, 6, 0, 0);  // drop key 8; key 0 stays at slot 5
    auto b = MakeNativeFixture(FixedSpec(), other);
    OfflineNativeShadow s;
    s.SetMode(NativeMode::Shadow);
    NativeScope scope(s);
    Warm(s, a->Borrow());
    CHECK(RunKey0(s, b->Borrow()).status == NativeStatus::NoCandidate);
    CHECK(RunKey0(s, b->Borrow()).status == NativeStatus::Equal);
}

LOOKUP_TEST(address_reuse_has_no_candidate) {
    OfflineNativeShadow s;
    s.SetMode(NativeMode::Shadow);
    NativeScope scope(s);
    auto a = MakeFixedFixture();
    Warm(s, a->Borrow());
    a.reset();
    auto again = MakeFixedFixture();  // same base, bytes and address values
    CHECK(RunKey0(s, again->Borrow()).status == NativeStatus::NoCandidate);
}

LOOKUP_TEST(revoked_during_callback) {
    auto f = MakeFixedFixture();
    const auto b = f->Borrow();
    OfflineNativeShadow s;
    s.SetMode(NativeMode::Shadow);
    NativeScope scope(s);
    Warm(s, b);
    int calls = 0;
    auto revoke = [&](std::uint32_t) {
        ++calls;
        f->Revoke();
        return OpaqueResult{kKey0Result};
    };
    CHECK(s.Evaluate(b, 0, kCaller1, Call(revoke)).value == kKey0Result);
    CHECK(calls == 1);
    const NativeRecord r = Last(s);
    CHECK(r.status == NativeStatus::Skipped);
    CHECK(r.reason == NativeSkip::ProofLost);
    CHECK(!r.candidate_slot);
    CHECK(!r.result_class);
    CHECK(s.Counters().equal == 0);
    auto fresh = MakeFixedFixture();
    CHECK(RunKey0(s, fresh->Borrow()).status == NativeStatus::NoCandidate);
}

LOOKUP_TEST(owner_destroyed_in_callback_is_proof_lost) {
    auto f = MakeFixedFixture();
    auto b = f->Borrow();
    OfflineNativeShadow s;
    s.SetMode(NativeMode::Shadow);
    NativeScope scope(s);
    int calls = 0;
    auto destroy = [&](std::uint32_t) {
        ++calls;
        f.reset();
        return OpaqueResult{kKey0Result};
    };
    CHECK(s.Evaluate(b, 0, kCaller1, Call(destroy)).value == kKey0Result);
    CHECK(s.Counters().original_calls == 1);
    CHECK(calls == 1);
    CHECK(s.LastRecord()->reason == NativeSkip::ProofLost);
    CHECK(!b.Valid());  // bytes remain owned by b; no dangling access
}

LOOKUP_TEST(off_outer_reentry_invalidates) {
    auto f = MakeFixedFixture();
    const auto b = f->Borrow();
    OfflineNativeShadow s;
    s.SetMode(NativeMode::Shadow);
    NativeScope scope(s);
    Warm(s, b);
    s.SetMode(NativeMode::Off);
    Counting inner{kKey0Result};
    std::optional<NativeRecord> inner_record;
    int outer_calls = 0;
    auto outer = [&](std::uint32_t) {
        ++outer_calls;
        s.SetMode(NativeMode::Shadow);
        CHECK(s.Evaluate(b, 0, kCaller1, Fixed(inner)).value == kKey0Result);
        inner_record = s.LastRecord();
        return OpaqueResult{0x1234};
    };
    const auto attempts = s.Counters().candidate_attempts;
    CHECK(s.Evaluate(b, 0, kExcluded, Call(outer)).value == 0x1234);
    CHECK(outer_calls == 1);
    CHECK(inner.calls == 1);
    CHECK(inner_record && inner_record->reason == NativeSkip::Reentrant);
    CHECK(inner_record && !inner_record->candidate_slot);
    CHECK(Last(s).reason == NativeSkip::Off);
    CHECK(s.Counters().candidate_attempts == attempts);
    CHECK(s.Counters().reentrant_calls == 1);
    CHECK(RunKey0(s, b).status == NativeStatus::NoCandidate);
}

LOOKUP_TEST(excluded_outer_reentry_invalidates) {
    auto f = MakeFixedFixture();
    const auto b = f->Borrow();
    OfflineNativeShadow s;
    s.SetMode(NativeMode::Shadow);
    NativeScope scope(s);
    Warm(s, b);
    Counting inner{kKey0Result};
    std::optional<NativeRecord> inner_record;
    auto outer = [&](std::uint32_t) {
        s.Evaluate(b, 0, kCaller1, Fixed(inner));
        inner_record = s.LastRecord();
        return OpaqueResult{kKey0Result};
    };
    const auto attempts = s.Counters().candidate_attempts;
    CHECK(s.Evaluate(b, 0, kExcluded, Call(outer)).value == kKey0Result);
    CHECK(inner.calls == 1);
    CHECK(inner_record && inner_record->reason == NativeSkip::Reentrant);
    CHECK(Last(s).reason == NativeSkip::CallerExcluded);
    CHECK(s.Counters().candidate_attempts == attempts);
    CHECK(RunKey0(s, b).status == NativeStatus::NoCandidate);
}

LOOKUP_TEST(eligible_outer_reentry_skips_comparison) {
    auto f = MakeFixedFixture();
    const auto b = f->Borrow();
    OfflineNativeShadow s;
    s.SetMode(NativeMode::Shadow);
    NativeScope scope(s);
    Warm(s, b);
    Counting inner{kKey0Result};
    auto outer = [&](std::uint32_t) {
        s.Evaluate(b, 8, kCaller2, Fixed(inner));
        return OpaqueResult{kKey0Result};
    };
    CHECK(s.Evaluate(b, 0, kCaller1, Call(outer)).value == kKey0Result);
    CHECK(inner.calls == 1);
    CHECK(Last(s).status == NativeStatus::Skipped);
    CHECK(Last(s).reason == NativeSkip::Reentrant);
    CHECK(!Last(s).candidate_slot);
    CHECK(s.Counters().equal == 0);
    CHECK(RunKey0(s, b).status == NativeStatus::NoCandidate);
}

LOOKUP_TEST(inner_throw_caught_by_outer) {
    auto f = MakeFixedFixture();
    const auto b = f->Borrow();
    OfflineNativeShadow s;
    s.SetMode(NativeMode::Shadow);
    NativeScope scope(s);
    Warm(s, b);
    int token = 0;
    int inner_calls = 0;
    auto thrower = [&](std::uint32_t) -> OpaqueResult {
        ++inner_calls;
        throw Marker{&token};
    };
    bool caught = false;
    auto outer = [&](std::uint32_t) {
        try {
            s.Evaluate(b, 0, kCaller1, Call(thrower));
        } catch (const Marker& m) {
            caught = m.token == &token;
        }
        return OpaqueResult{kKey0Result};
    };
    CHECK(s.Evaluate(b, 0, kCaller1, Call(outer)).value == kKey0Result);
    CHECK(caught);
    CHECK(inner_calls == 1);
    CHECK(Last(s).reason == NativeSkip::Reentrant);
    CHECK(s.Counters().equal == 0);
    CHECK(s.Counters().exception_calls == 1);
    CHECK(s.Counters().original_calls == 3);  // warm + outer + inner
    CHECK(RunKey0(s, b).status == NativeStatus::NoCandidate);
}

LOOKUP_TEST(same_exception_propagates) {
    auto f = MakeFixedFixture();
    const auto b = f->Borrow();
    for (const NativeMode mode : {NativeMode::Off, NativeMode::Shadow}) {
        for (const std::uint32_t caller : {kCaller1, kExcluded}) {
            OfflineNativeShadow s;
            s.SetMode(NativeMode::Shadow);
            std::optional<NativeScope> scope(std::in_place, s);
            Warm(s, b);
            s.SetMode(mode);
            const NativeRecord before = Last(s);
            int token = 0;
            int calls = 0;
            const void* thrown_at = nullptr;
            auto thrower = [&](std::uint32_t) -> OpaqueResult {
                ++calls;
                try {
                    throw Marker{&token};
                } catch (const Marker& m) {
                    thrown_at = &m;
                    throw;
                }
            };
            bool same_object = false;
            try {
                s.Evaluate(b, 0, caller, Call(thrower));
            } catch (const Marker& m) {
                same_object = (&m == thrown_at) && m.token == &token;
            }
            CHECK(same_object);
            CHECK(calls == 1);
            CHECK(s.Counters().exception_calls == 1);
            CHECK(s.Counters().original_calls == 2);
            // No normal-return record for the throwing call.
            CHECK(Last(s).status == before.status);
            CHECK(Last(s).original.value == before.original.value);
            CHECK(s.Counters().no_candidate == 1);
            // Guard restored (not reentrant) and hint cleared.
            s.SetMode(NativeMode::Shadow);
            CHECK(RunKey0(s, b).status == NativeStatus::NoCandidate);
        }
    }
}

LOOKUP_TEST(scope_boundaries_and_nested_rejection) {
    auto f = MakeFixedFixture();
    const auto b = f->Borrow();
    OfflineNativeShadow s;
    s.SetMode(NativeMode::Shadow);
    std::uint64_t first_scope = 0;
    {
        NativeScope scope(s);
        Warm(s, b);
        first_scope = Last(s).scope_id;
        bool rejected = false;
        try {
            NativeScope nested(s);
        } catch (const std::logic_error&) {
            rejected = true;
        }
        CHECK(rejected);
        const NativeRecord r = RunKey0(s, b);
        CHECK(r.status == NativeStatus::Equal);  // rejected nesting changed nothing
        CHECK(r.scope_id == first_scope);
    }
    CHECK(RunKey0(s, b).reason == NativeSkip::MissingScope);
    NativeScope second(s);
    const NativeRecord r = RunKey0(s, b);
    CHECK(r.status == NativeStatus::NoCandidate);
    CHECK(r.scope_id > first_scope);
}

LOOKUP_TEST(scope_exit_clears_hint) {
    auto f = MakeFixedFixture();
    const auto b = f->Borrow();
    OfflineNativeShadow s;
    s.SetMode(NativeMode::Shadow);
    { NativeScope scope(s); Warm(s, b); }
    NativeScope scope(s);
    CHECK(RunKey0(s, b).status == NativeStatus::NoCandidate);
}

LOOKUP_TEST(mode_roundtrip_during_callback_invalidates) {
    auto f = MakeFixedFixture();
    const auto b = f->Borrow();
    OfflineNativeShadow s;
    s.SetMode(NativeMode::Shadow);
    NativeScope scope(s);
    Warm(s, b);
    auto roundtrip = [&](std::uint32_t) {
        s.SetMode(NativeMode::Off);
        s.SetMode(NativeMode::Shadow);
        return OpaqueResult{kKey0Result};
    };
    CHECK(s.Evaluate(b, 0, kCaller1, Call(roundtrip)).value == kKey0Result);
    CHECK(Last(s).reason == NativeSkip::ProofLost);
    CHECK(RunKey0(s, b).status == NativeStatus::NoCandidate);
    auto turn_off = [&](std::uint32_t) {
        s.SetMode(NativeMode::Off);
        return OpaqueResult{kKey0Result};
    };
    s.Evaluate(b, 0, kCaller1, Call(turn_off));
    CHECK(Last(s).reason == NativeSkip::Off);
    // Setting the current mode again is not a change.
    s.SetMode(NativeMode::Shadow);
    Warm(s, b);
    auto same = [&](std::uint32_t) {
        s.SetMode(NativeMode::Shadow);
        return OpaqueResult{kKey0Result};
    };
    s.Evaluate(b, 0, kCaller1, Call(same));
    CHECK(Last(s).status == NativeStatus::Equal);
}

LOOKUP_TEST(scope_replaced_during_callback_invalidates) {
    auto f = MakeFixedFixture();
    const auto b = f->Borrow();
    OfflineNativeShadow s;
    s.SetMode(NativeMode::Shadow);
    std::optional<NativeScope> scope(std::in_place, s);
    Warm(s, b);
    auto replace = [&](std::uint32_t) {
        scope.reset();
        scope.emplace(s);
        return OpaqueResult{kKey0Result};
    };
    CHECK(s.Evaluate(b, 0, kCaller1, Call(replace)).value == kKey0Result);
    CHECK(Last(s).reason == NativeSkip::MissingScope);
    CHECK(RunKey0(s, b).status == NativeStatus::NoCandidate);
    auto end = [&](std::uint32_t) {
        scope.reset();
        return OpaqueResult{kKey0Result};
    };
    s.Evaluate(b, 0, kCaller1, Call(end));
    CHECK(Last(s).reason == NativeSkip::MissingScope);
}

LOOKUP_TEST(other_evaluator_does_not_inherit_scope) {
    auto f = MakeFixedFixture();
    const auto b = f->Borrow();
    OfflineNativeShadow first;
    first.SetMode(NativeMode::Shadow);
    NativeScope scope(first);
    OfflineNativeShadow second;
    second.SetMode(NativeMode::Shadow);
    CHECK(RunKey0(second, b).reason == NativeSkip::MissingScope);
    CHECK(RunKey0(first, b).status == NativeStatus::NoCandidate);
    CHECK(Last(first).session_id != Last(second).session_id);
}

LOOKUP_TEST(mismatch_disables_until_new_evaluator) {
    auto f = MakeFixedFixture();
    const auto b = f->Borrow();
    OfflineNativeShadow s;
    s.SetMode(NativeMode::Shadow);
    {
        NativeScope scope(s);
        Warm(s, b);
        testing::FaultAccess::OverrideCandidate(s, 6);
        const NativeRecord r = RunKey0(s, b);  // original stays slot 5
        CHECK(r.status == NativeStatus::Mismatch);
        CHECK(r.candidate_slot == std::optional<std::size_t>{6});
        CHECK(r.original_slot == std::optional<std::size_t>{5});
        CHECK(r.original.value == kKey0Result);
        CHECK(s.SessionDisabled());
        CHECK(s.Counters().mismatch == 1);
        testing::FaultAccess::OverrideCandidate(s, std::nullopt);
        CHECK(RunKey0(s, b).reason == NativeSkip::SessionDisabled);
    }
    s.SetMode(NativeMode::Off);
    s.SetMode(NativeMode::Shadow);
    NativeScope scope(s);
    CHECK(RunKey0(s, b).reason == NativeSkip::SessionDisabled);
    CHECK(RunKey0(s, b).reason == NativeSkip::SessionDisabled);
    OfflineNativeShadow fresh;
    fresh.SetMode(NativeMode::Shadow);
    NativeScope fresh_scope(fresh);
    CHECK(RunKey0(fresh, b).status == NativeStatus::NoCandidate);
    CHECK(RunKey0(fresh, b).status == NativeStatus::Equal);
}

LOOKUP_TEST(no_candidate_does_not_count_as_mismatch) {
    auto f = MakeFixedFixture();
    const auto b = f->Borrow();
    OfflineNativeShadow s;
    s.SetMode(NativeMode::Shadow);
    NativeScope scope(s);
    Warm(s, b);
    Counting key8{0x1100};
    s.Evaluate(b, 8, kCaller1, Fixed(key8));  // different key: NoCandidate, remembers slot 6
    CHECK(Last(s).status == NativeStatus::NoCandidate);
    s.Evaluate(b, 8, kCaller1, Fixed(key8));
    CHECK(Last(s).status == NativeStatus::Equal);
    CHECK(Last(s).candidate_slot == std::optional<std::size_t>{6});
    CHECK(RunKey0(s, b).status == NativeStatus::NoCandidate);  // one hint only
    CHECK(s.Counters().mismatch == 0);
    CHECK(!s.SessionDisabled());
}

LOOKUP_TEST(record_full_and_drain) {
    auto f = MakeFixedFixture();
    const auto b = f->Borrow();
    auto s = std::make_unique<OfflineNativeShadow>();
    s->SetMode(NativeMode::Shadow);
    NativeScope scope(*s);
    Counting c{kKey0Result};
    for (std::size_t i = 0; i < kNativeRecordCapacity; ++i) {
        s->Evaluate(b, 0, kCaller1, Fixed(c));
    }
    CHECK(s->Counters().dropped_records == 0);
    Counting last{0x1100};
    CHECK(s->Evaluate(b, 8, kCaller2, Fixed(last)).value == 0x1100);
    CHECK(c.calls == static_cast<int>(kNativeRecordCapacity));
    CHECK(last.calls == 1);
    CHECK(s->Counters().original_calls == kNativeRecordCapacity + 1);
    CHECK(s->Counters().dropped_records == 1);
    CHECK(Last(*s).key == 8);
    CHECK(Last(*s).caller_id == 2);

    std::vector<NativeRecord> out(kNativeRecordCapacity + 4);
    CHECK(s->DrainRecords(std::span<NativeRecord>(out.data(), 10)) == 10);
    CHECK(out[0].status == NativeStatus::NoCandidate);
    CHECK(out[1].status == NativeStatus::Equal);
    CHECK(s->DrainRecords(out) == kNativeRecordCapacity - 10);
    CHECK(out[kNativeRecordCapacity - 11].key == 0);
    CHECK(s->DrainRecords(out) == 0);
    s->Evaluate(b, 8, kCaller2, Fixed(last));
    CHECK(s->Counters().dropped_records == 1);
    CHECK(s->DrainRecords(out) == 1);
    CHECK(out[0].key == 8);
    CHECK(out[0].status == NativeStatus::Equal);
}

LOOKUP_TEST(full_records_reentrant_throw_preserves_outer_bits) {
    auto f = MakeFixedFixture();
    const auto b = f->Borrow();
    auto s = std::make_unique<OfflineNativeShadow>();
    s->SetMode(NativeMode::Shadow);
    NativeScope scope(*s);
    Counting fill{kKey0Result};
    for (std::size_t i = 0; i < kNativeRecordCapacity; ++i) {
        s->Evaluate(b, 0, kCaller1, Fixed(fill));
    }
    int token = 0, outer_calls = 0, inner_calls = 0;
    const std::uint64_t bits = 0xfedcba9876543210ULL;
    auto inner = [&](std::uint32_t) -> OpaqueResult {
        ++inner_calls;
        throw Marker{&token};
    };
    auto outer = [&](std::uint32_t) {
        ++outer_calls;
        try { s->Evaluate(b, 0, kCaller1, Call(inner)); }
        catch (const Marker& m) { CHECK(m.token == &token); }
        return OpaqueResult{bits};
    };
    CHECK(s->Evaluate(b, 0, kCaller1, Call(outer)).value == bits);
    CHECK(outer_calls == 1 && inner_calls == 1);
    CHECK(s->Counters().original_calls == kNativeRecordCapacity + 2);
    CHECK(s->Counters().exception_calls == 1);
    CHECK(s->Counters().reentrant_calls == 1);
    CHECK(s->Counters().dropped_records == 1); // only the normally returned outer call
    CHECK(Last(*s).original.value == bits && Last(*s).reason == NativeSkip::Reentrant);
    std::vector<NativeRecord> records(kNativeRecordCapacity);
    CHECK(s->DrainRecords(records) == kNativeRecordCapacity);
    CHECK(RunKey0(*s, b).status == NativeStatus::NoCandidate); // recovered depth and cleared hint
}

LOOKUP_TEST(zero_and_partial_drain_preserve_fifo_after_refill) {
    OfflineNativeShadow s; // Off: opaque values are returned without normalization.
    Counting c{0};
    for (std::uint32_t i = 0; i < 4; ++i) {
        c.value = 0x8000000000000000ULL + i;
        CHECK(s.Evaluate({}, i, kCaller1, Fixed(c)).value == c.value);
    }
    CHECK(s.DrainRecords({}) == 0);
    CHECK(s.Counters().original_calls == 4 && s.Counters().dropped_records == 0);
    std::array<NativeRecord, 2> first;
    CHECK(s.DrainRecords(first) == 2);
    CHECK(first[0].key == 0 && first[1].key == 1);
    CHECK(first[0].original.value == 0x8000000000000000ULL);
    CHECK(first[1].original.value == 0x8000000000000001ULL);
    for (std::uint32_t i = 4; i < 6; ++i) {
        c.value = 0x8000000000000000ULL + i;
        s.Evaluate({}, i, kCaller1, Fixed(c));
    }
    std::array<NativeRecord, 5> rest;
    rest[4].key = 999;
    CHECK(s.DrainRecords(rest) == 4);
    for (std::uint32_t i = 0; i < 4; ++i) {
        CHECK(rest[i].key == i + 2);
        CHECK(rest[i].original.value == 0x8000000000000000ULL + i + 2);
    }
    CHECK(rest[4].key == 999 && s.DrainRecords(rest) == 0);
    CHECK(c.calls == 6 && s.Counters().original_calls == 6 && s.Counters().dropped_records == 0);
}

LOOKUP_TEST(null_invoke_is_rejected_before_any_state_change) {
    auto f = MakeFixedFixture();
    OfflineNativeShadow s;
    s.SetMode(NativeMode::Shadow);
    NativeScope scope(s);
    bool rejected = false;
    try {
        s.Evaluate(f->Borrow(), 0, kCaller1, OpaqueOriginal{nullptr, nullptr});
    } catch (const std::invalid_argument&) {
        rejected = true;
    }
    CHECK(rejected);
    CHECK(s.Counters().original_calls == 0);
    CHECK(!s.LastRecord());
    CHECK(RunKey0(s, f->Borrow()).status == NativeStatus::NoCandidate);  // guard not left set
}

LOOKUP_TEST(generation_exhaustion_is_rejected_without_wrap) {
    constexpr auto kMax = std::numeric_limits<std::uint64_t>::max();
    const std::uint64_t saved = testing::ExchangeGenerationCounterForTest(kMax - 1);
    auto last = OwnedNativeFixture::Create(FixedSpec(), FixedRaw());
    auto exhausted = OwnedNativeFixture::Create(FixedSpec(), FixedRaw());
    testing::ExchangeGenerationCounterForTest(saved);
    CHECK(std::holds_alternative<std::unique_ptr<OwnedNativeFixture>>(last));
    CHECK(std::get<std::unique_ptr<OwnedNativeFixture>>(last)->Borrow().Generation() == kMax);
    CHECK(std::holds_alternative<FixtureError>(exhausted));
    CHECK(std::get<FixtureError>(exhausted).kind == FixtureError::Kind::EpochExhausted);
}

LOOKUP_TEST(session_and_scope_ids_do_not_wrap) {
    constexpr auto kMax = std::numeric_limits<std::uint64_t>::max();
    const std::uint64_t saved = testing::ExchangeSessionCounterForTest(kMax - 1);
    bool session_rejected = false;
    {
        OfflineNativeShadow last;  // receives kMax
        try {
            OfflineNativeShadow exhausted;
        } catch (const std::overflow_error&) {
            session_rejected = true;
        }
    }
    testing::ExchangeSessionCounterForTest(saved);
    CHECK(session_rejected);

    OfflineNativeShadow s;
    testing::FaultAccess::SetLastScopeId(s, kMax);
    bool scope_rejected = false;
    try {
        NativeScope scope(s);
    } catch (const std::overflow_error&) {
        scope_rejected = true;
    }
    CHECK(scope_rejected);
}
