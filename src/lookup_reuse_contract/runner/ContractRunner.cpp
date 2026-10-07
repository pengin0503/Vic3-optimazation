#include "ContractRunner.h"

#include <array>
#include <limits>
#include <map>
#include <memory>
#include <optional>
#include <ostream>
#include <span>
#include <stdexcept>
#include <string>
#include <utility>
#include <variant>
#include <vector>

#include "NativeFixture.h"
#include "NativeShadow.h"
#include "ResultNormalization.h"
#include "TableView.h"
#include "manifest_1_14_5.inc"

namespace lookup_contract::runner {
namespace {

constexpr std::array<std::uint64_t, 3> kMasks{7, 15, 31};
constexpr std::size_t kMaxKeys = 16;
// Every seeded fixture reuses the same numeric addresses, so a hint that
// survived by address alone would be caught.
constexpr std::uint64_t kSeededBase = 0x10000000;
constexpr std::uint64_t kSeededSentinel = kSeededBase - 0x100;  // below the table
constexpr std::uint64_t kSeededFallback = kSeededBase + 8;      // inside, not a descriptor
constexpr std::uint32_t kUnknownReturnRva = 0x1;

// Runner-local fixed PRNG (SplitMix64); no standard distributions.
class SplitMix64 {
public:
    explicit SplitMix64(std::uint64_t seed) : state_(seed) {}
    std::uint64_t Next() {
        std::uint64_t z = (state_ += 0x9e3779b97f4a7c15ull);
        z = (z ^ (z >> 30)) * 0xbf58476d1ce4e5b9ull;
        z = (z ^ (z >> 27)) * 0x94d049bb133111ebull;
        return z ^ (z >> 31);
    }
    std::uint64_t Below(std::uint64_t bound) { return Next() % bound; }

private:
    std::uint64_t state_;
};

// A table as the runner placed it. placement is the runner's own record.
struct PlacedTable {
    NativeFixtureSpec spec;
    std::vector<std::byte> raw;
    std::map<std::uint32_t, std::size_t> placement;  // ordered: deterministic iteration
    std::size_t primary_count = 0;

    std::uint64_t Descriptor(std::size_t slot) const {
        return spec.table_base + lookup_reuse::kSlotStride * slot + kDescriptorOffset;
    }
    bool Occupied(std::size_t slot) const {
        for (const auto& [key, at] : placement) {
            if (at == slot) {
                return true;
            }
        }
        return false;
    }
    std::uint32_t AbsentKey(std::uint32_t start) const {
        std::uint32_t key = start;
        while (placement.count(key) != 0) {
            ++key;
        }
        return key;
    }
};

void PutRaw(std::vector<std::byte>& raw, std::size_t slot, std::uint8_t control, std::uint32_t key) {
    std::byte* base = raw.data() + slot * lookup_reuse::kSlotStride;
    base[lookup_reuse::kControlOffset] = std::byte{control};
    for (std::size_t i = 0; i < 4; ++i) {
        base[lookup_reuse::kKeyOffset + i] = std::byte{static_cast<unsigned char>((key >> (8 * i)) & 0xffu)};
    }
}

// Robin-Hood insertion over controls/keys; only the shared hash decides the
// home slot.
PlacedTable BuildSeededTable(SplitMix64& rng) {
    const std::uint64_t mask = kMasks[rng.Below(kMasks.size())];
    const std::size_t slots = static_cast<std::size_t>(mask) + 1 + kMaxKeys + 1;
    std::vector<std::uint8_t> controls(slots, 0);
    std::vector<std::uint32_t> keys(slots, 0);
    const std::size_t count = 1 + static_cast<std::size_t>(rng.Below(kMaxKeys));
    std::map<std::uint32_t, bool> chosen;
    while (chosen.size() < count) {
        chosen[static_cast<std::uint32_t>(rng.Next())] = true;
    }
    for (const auto& [key, unused] : chosen) {
        (void)unused;
        std::size_t index = static_cast<std::size_t>(static_cast<std::uint64_t>(lookup_reuse::HashKey(key)) & mask);
        std::size_t distance = 0;
        std::uint32_t carried = key;
        for (;;) {
            if (index + 1 >= slots || distance > lookup_reuse::kMaxProbeDistance) {
                throw std::logic_error("runner table capacity exceeded");
            }
            if (controls[index] == 0) {
                controls[index] = static_cast<std::uint8_t>(distance + 1);
                keys[index] = carried;
                break;
            }
            const std::size_t resident = static_cast<std::size_t>(controls[index]) - 1;
            if (resident < distance) {
                std::swap(keys[index], carried);
                controls[index] = static_cast<std::uint8_t>(distance + 1);
                distance = resident;
            }
            ++index;
            ++distance;
        }
    }
    PlacedTable table;
    table.spec = NativeFixtureSpec{mask, slots, kSeededBase, OpaqueResult{kSeededSentinel},
                                   OpaqueResult{kSeededFallback}};
    table.raw.assign(slots * lookup_reuse::kSlotStride, std::byte{0});
    table.primary_count = static_cast<std::size_t>(mask) + 1;
    for (std::size_t i = 0; i < slots; ++i) {
        if (controls[i] != 0) {
            PutRaw(table.raw, i, controls[i], keys[i]);
            table.placement[keys[i]] = i;
        }
    }
    return table;
}

// Boundary 1: the hand-placed unit-test fixture (mask 7, tail key 10 at 8).
PlacedTable FixedBoundaryTable() {
    PlacedTable table;
    table.spec = NativeFixtureSpec{7, 10, 0x1000, OpaqueResult{0x8000}, OpaqueResult{0x9000}};
    table.raw.assign(10 * lookup_reuse::kSlotStride, std::byte{0});
    table.primary_count = 8;
    const std::pair<std::uint32_t, std::size_t> keys[] = {{0, 5}, {8, 6}, {2, 7}, {10, 8}};
    const std::uint8_t controls[] = {1, 2, 1, 2};
    for (std::size_t i = 0; i < 4; ++i) {
        PutRaw(table.raw, keys[i].second, controls[i], keys[i].first);
        table.placement[keys[i].first] = keys[i].second;
    }
    return table;
}

// Boundary 2: mask 0, one key, table ending exactly at 2^64.
PlacedTable TopOfAddressSpaceTable() {
    PlacedTable table;
    const std::uint64_t base = std::numeric_limits<std::uint64_t>::max() - 80 + 1;
    table.spec = NativeFixtureSpec{0, 2, base, OpaqueResult{1}, OpaqueResult{2}};
    table.raw.assign(2 * lookup_reuse::kSlotStride, std::byte{0});
    table.primary_count = 1;
    PutRaw(table.raw, 0, 1, std::numeric_limits<std::uint32_t>::max());
    table.placement[std::numeric_limits<std::uint32_t>::max()] = 0;
    return table;
}

std::unique_ptr<OwnedNativeFixture> CreateFixture(const PlacedTable& table) {
    auto created = OwnedNativeFixture::Create(table.spec, table.raw);
    if (std::holds_alternative<FixtureError>(created)) {
        throw std::logic_error("runner produced a fixture the core rejected");
    }
    return std::move(std::get<std::unique_ptr<OwnedNativeFixture>>(created));
}

// What the runner expects of one normal return.
struct Expected {
    NativeSkip reason = NativeSkip::None;  // None: an eligible primary positive
    std::optional<ResultClass> result_class;
    std::optional<std::size_t> original_slot;
};

Expected Skip(NativeSkip reason) { return Expected{reason, std::nullopt, std::nullopt}; }
Expected ClassSkip(NativeSkip reason, ResultClass kind, std::optional<std::size_t> slot = std::nullopt) {
    return Expected{reason, kind, slot};
}
Expected Primary(std::size_t slot) { return Expected{NativeSkip::None, ResultClass::PrimaryPositive, slot}; }

struct RunnerSignal {
    const void* token;
};

class Run {
public:
    explicit Run(const RunConfig& config) : rng_(config.seed) {
        summary_.config = config;
        summary_.default_mode_off = shadow_.Mode() == NativeMode::Off;
        shadow_.SetMode(NativeMode::Shadow);
    }

    RunSummary Execute() {
        // Before any scope exists.
        {
            const PlacedTable table = FixedBoundaryTable();
            auto fixture = CreateFixture(table);
            Query(fixture->Borrow(), 0, Allowed(0), table.Descriptor(5), Skip(NativeSkip::MissingScope));
            FinishFixture();
        }
        RunBoundary(FixedBoundaryTable(), false);
        RunBoundary(TopOfAddressSpaceTable(), true);
        PlacedTable table;
        for (std::size_t r = 0; r < summary_.config.rebuilds; ++r) {
            const bool fresh = r % 2 == 0;
            if (fresh) {
                // A new table in a new scope; the odd rebuild re-creates the
                // same bytes at the same addresses inside the same scope.
                table = BuildSeededTable(rng_);
                scope_.reset();
                scope_.emplace(shadow_);
                ForgetHint();
            }
            auto fixture = CreateFixture(table);
            RunFixture(table, *fixture, !fresh);
            ++summary_.fixture_count;
        }
        scope_.reset();
        summary_.native = shadow_.Counters();
        RunCollectorCase();
        return summary_;
    }

private:
    static std::uint32_t Allowed(std::size_t i) { return generated::kCallers[i % 4].return_rva; }
    static std::uint32_t Excluded(std::size_t i) { return generated::kCallers[4 + i % 2].return_rva; }

    void ForgetHint() { hint_.reset(); }

    void RunBoundary(const PlacedTable& table, bool revoke_at_end) {
        scope_.reset();
        scope_.emplace(shadow_);
        ForgetHint();
        auto fixture = CreateFixture(table);
        RunFixture(table, *fixture, revoke_at_end);
        ++summary_.boundary_fixture_count;
        ++summary_.fixture_count;
    }

    // One fixture's query sequence. Starts with the primary keys (so a hint
    // left by the previous fixture meets the same key and address first) and
    // ends with a warm primary hint, or (when revoke_at_end) with a
    // revocation during the callback.
    void RunFixture(const PlacedTable& table, OwnedNativeFixture& fixture, bool revoke_at_end) {
        const FixtureBorrow borrow = fixture.Borrow();
        ++fixture_ordinal_;
        std::vector<std::pair<std::uint32_t, std::size_t>> primary;
        std::vector<std::pair<std::uint32_t, std::size_t>> tail;
        for (const auto& entry : table.placement) {
            (entry.second < table.primary_count ? primary : tail).push_back(entry);
        }
        if (primary.empty()) {
            throw std::logic_error("runner fixture without a primary key");
        }
        const std::uint32_t absent = table.AbsentKey(static_cast<std::uint32_t>(rng_.Next()));
        std::size_t turn = 0;

        // Rotate callers so that every allowed witness sees both NoCandidate
        // and Equal outcomes across fixtures.
        for (std::size_t k = 0; k < primary.size(); ++k) {
            for (std::size_t repeat = 0; repeat < 2; ++repeat) {
                Query(borrow, primary[k].first, Allowed(fixture_ordinal_ + k + repeat),
                      table.Descriptor(primary[k].second), Primary(primary[k].second));
            }
        }
        for (const auto& [key, slot] : tail) {
            Query(borrow, key, Allowed(turn++), table.Descriptor(slot),
                  ClassSkip(NativeSkip::TailPositive, ResultClass::TailPositive, slot));
        }
        // Each skip below is preceded by a warm primary query on the first
        // key, so the next warm query checks that the skip cleared the hint.
        const std::uint32_t k0 = primary[0].first;
        const std::size_t s0 = primary[0].second;
        const std::uint64_t d0 = table.Descriptor(s0);
        const auto warm = [&] { Query(borrow, k0, Allowed(turn++), d0, Primary(s0)); };
        warm();
        Query(borrow, absent, Allowed(turn++), table.spec.end_sentinel.value,
              ClassSkip(NativeSkip::EndSentinel, ResultClass::EndSentinel));
        warm();
        Query(borrow, absent, Allowed(turn++), table.spec.fallback.value,
              ClassSkip(NativeSkip::Fallback, ResultClass::Fallback));
        // Wrong key on an occupied primary slot, and an empty primary slot.
        warm();
        Query(borrow, absent, Allowed(turn++), d0,
              ClassSkip(NativeSkip::InvalidPrimaryResult, ResultClass::InvalidPrimaryResult));
        for (std::size_t slot = 0; slot < table.primary_count; ++slot) {
            if (!table.Occupied(slot)) {
                warm();
                Query(borrow, absent, Allowed(turn++), table.Descriptor(slot),
                      ClassSkip(NativeSkip::InvalidPrimaryResult, ResultClass::InvalidPrimaryResult));
                break;
            }
        }
        warm();
        Query(borrow, k0, Allowed(turn++), 0, ClassSkip(NativeSkip::UnknownResult, ResultClass::Unknown));
        warm();
        Query(borrow, k0, Allowed(turn++), d0 + 1, ClassSkip(NativeSkip::UnknownResult, ResultClass::Unknown));
        warm();
        Query(FixtureBorrow{}, k0, Allowed(turn++), d0, Skip(NativeSkip::MissingFixture));
        warm();
        shadow_.SetMode(NativeMode::Off);
        Query(borrow, k0, Allowed(turn++), d0, Skip(NativeSkip::Off));
        shadow_.SetMode(NativeMode::Shadow);
        for (std::size_t i = 0; i < 2; ++i) {
            warm();
            Query(borrow, k0, Excluded(i), d0, Skip(NativeSkip::CallerExcluded));
        }
        warm();
        Query(borrow, k0, kUnknownReturnRva, d0, Skip(NativeSkip::CallerExcluded));
        warm();
        QueryReentrant(table, borrow, primary, turn);
        warm();
        QueryThrowing(borrow, primary[0].first, Allowed(turn++));

        // End warm on the first primary key: the next (odd) rebuild starts by
        // querying the same key at the same address under a new identity.
        const auto& [first_key, first_slot] = primary[0];
        Query(borrow, first_key, Allowed(turn++), table.Descriptor(first_slot), Primary(first_slot));
        if (revoke_at_end) {
            QueryRevoking(fixture, borrow, first_key, Allowed(turn++), table.Descriptor(first_slot));
        }
        FinishFixture();
    }

    // Issues one call with a plain callback and checks it against `expected`.
    void Query(const FixtureBorrow& borrow, std::uint32_t key, std::uint32_t return_rva, std::uint64_t value,
               const Expected& expected) {
        Plain plain{this, value};
        Check(Invoke(borrow, key, return_rva, OpaqueOriginal{&plain, &Plain::Invoke}, value), key, return_rva,
              value, expected);
    }

    void QueryReentrant(const PlacedTable& table, const FixtureBorrow& borrow,
                        const std::vector<std::pair<std::uint32_t, std::size_t>>& primary, std::size_t& turn) {
        const auto& [key, slot] = primary[0];
        const std::uint32_t outer_rva = Allowed(turn++);
        const std::uint32_t inner_rva = Allowed(turn++);
        Reentering reentering{this, &borrow, key, inner_rva, table.Descriptor(slot)};
        const std::uint64_t value = table.Descriptor(slot);
        // The outer call observes its own callback and the inner one.
        Check(Invoke(borrow, key, outer_rva, OpaqueOriginal{&reentering, &Reentering::Invoke}, value), key,
              outer_rva, value, Skip(NativeSkip::Reentrant), 2);
    }

    void QueryThrowing(const FixtureBorrow& borrow, std::uint32_t key, std::uint32_t return_rva) {
        const auto before = shadow_.LastRecord();
        Throwing throwing{this};
        ++summary_.query_count;
        const std::uint64_t calls_before = summary_.callback_invocations;
        bool same = false;
        try {
            shadow_.Evaluate(borrow, key, return_rva, OpaqueOriginal{&throwing, &Throwing::Invoke});
        } catch (const RunnerSignal& signal) {
            same = signal.token == &throwing;
        }
        const auto after = shadow_.LastRecord();
        const bool record_unchanged = before.has_value() == after.has_value() &&
                                      (!before || (before->key == after->key && before->status == after->status &&
                                                   before->original == after->original));
        if (!same || !record_unchanged || summary_.callback_invocations != calls_before + 1) {
            ++summary_.oracle_mismatches;
        }
        ForgetHint();
    }

    void QueryRevoking(OwnedNativeFixture& fixture, const FixtureBorrow& borrow, std::uint32_t key,
                       std::uint32_t return_rva, std::uint64_t value) {
        Revoking revoking{this, &fixture, value};
        Check(Invoke(borrow, key, return_rva, OpaqueOriginal{&revoking, &Revoking::Invoke}, value), key,
              return_rva, value, Skip(NativeSkip::ProofLost));
    }

    struct Call {
        OpaqueResult returned;
        std::uint64_t callbacks = 0;
    };

    Call Invoke(const FixtureBorrow& borrow, std::uint32_t key, std::uint32_t return_rva, OpaqueOriginal original,
                std::uint64_t) {
        ++summary_.query_count;
        ++normal_returns_;
        const std::uint64_t before = summary_.callback_invocations;
        const OpaqueResult returned = shadow_.Evaluate(borrow, key, return_rva, original);
        return Call{returned, summary_.callback_invocations - before};
    }

    // Compares the record of the call that just returned with the runner's
    // own prediction and updates the runner's one-hint model.
    void Check(const Call& call, std::uint32_t key, std::uint32_t return_rva, std::uint64_t value,
               const Expected& expected, std::uint64_t expected_callbacks = 1) {
        const std::optional<NativeRecord> record = shadow_.LastRecord();
        bool ok = call.returned.value == value && call.callbacks == expected_callbacks && record.has_value();
        if (ok) {
            const NativeRecord& r = *record;
            ok = r.key == key && r.original.value == value && r.result_class == expected.result_class &&
                 r.original_slot == expected.original_slot && r.caller_id == CallerId(return_rva);
            if (expected.reason == NativeSkip::None) {
                const bool warm = hint_ && hint_->first == fixture_ordinal_ && hint_->second == key;
                ok = ok && r.reason == NativeSkip::None &&
                     r.status == (warm ? NativeStatus::Equal : NativeStatus::NoCandidate) &&
                     r.candidate_slot == (warm ? expected.original_slot : std::nullopt);
            } else {
                ok = ok && r.status == NativeStatus::Skipped && r.reason == expected.reason && !r.candidate_slot;
            }
        }
        if (!ok) {
            ++summary_.oracle_mismatches;
        }
        if (expected.reason == NativeSkip::None) {
            hint_.emplace(fixture_ordinal_, key);
        } else {
            ForgetHint();
        }
    }

    static std::uint32_t CallerId(std::uint32_t return_rva) {
        for (const auto& caller : generated::kCallers) {
            if (caller.return_rva == return_rva) {
                return caller.caller_id;
            }
        }
        return generated::kUnknownCallerId;
    }

    void FinishFixture() {
        const std::size_t drained = shadow_.DrainRecords(drain_);
        if (drained != normal_returns_) {
            ++summary_.oracle_mismatches;
        }
        for (std::size_t i = 0; i < drained; ++i) {
            const NativeRecord& r = drain_[i];
            if (r.caller_id >= kCallerRows) {
                ++summary_.oracle_mismatches;
                continue;
            }
            CallerCoverage& row = summary_.callers[r.caller_id];
            ++row.calls;
            if (r.status == NativeStatus::Equal || r.status == NativeStatus::Mismatch) {
                ++row.compared;
            } else if (r.status == NativeStatus::Skipped) {
                ++row.skipped;
            }
        }
        normal_returns_ = 0;
    }

    void RunCollectorCase() {
        const PlacedTable table = FixedBoundaryTable();
        auto fixture = CreateFixture(table);
        auto shadow = std::make_unique<OfflineNativeShadow>();
        shadow->SetMode(NativeMode::Shadow);
        NativeScope scope(*shadow);
        std::uint64_t callbacks = 0;
        Counter counter{&callbacks, table.Descriptor(5)};
        CollectorCase& out = summary_.collector;
        for (std::size_t i = 0; i < kNativeRecordCapacity + 1; ++i) {
            shadow->Evaluate(fixture->Borrow(), 0, Allowed(i), OpaqueOriginal{&counter, &Counter::Invoke});
            ++out.calls;
        }
        out.original_calls = shadow->Counters().original_calls;
        out.dropped = shadow->Counters().dropped_records;
        out.drained = shadow->DrainRecords(drain_);
        shadow->Evaluate(fixture->Borrow(), 0, Allowed(0), OpaqueOriginal{&counter, &Counter::Invoke});
        out.drained_after_refill = shadow->DrainRecords(drain_);
        if (callbacks != out.calls + 1) {
            ++summary_.oracle_mismatches;
        }
    }

    struct Plain {
        Run* run;
        std::uint64_t value;
        static OpaqueResult Invoke(void* context, std::uint32_t) {
            auto* self = static_cast<Plain*>(context);
            ++self->run->summary_.callback_invocations;
            return OpaqueResult{self->value};
        }
    };

    struct Reentering {
        Run* run;
        const FixtureBorrow* borrow;
        std::uint32_t key;
        std::uint32_t inner_rva;
        std::uint64_t value;
        static OpaqueResult Invoke(void* context, std::uint32_t) {
            auto* self = static_cast<Reentering*>(context);
            ++self->run->summary_.callback_invocations;
            Plain inner{self->run, self->value};
            const Call call = self->run->Invoke(*self->borrow, self->key, self->inner_rva,
                                                OpaqueOriginal{&inner, &Plain::Invoke}, self->value);
            self->run->Check(call, self->key, self->inner_rva, self->value, Skip(NativeSkip::Reentrant));
            return OpaqueResult{self->value};
        }
    };

    struct Throwing {
        Run* run;
        static OpaqueResult Invoke(void* context, std::uint32_t) {
            auto* self = static_cast<Throwing*>(context);
            ++self->run->summary_.callback_invocations;
            throw RunnerSignal{self};
        }
    };

    struct Revoking {
        Run* run;
        OwnedNativeFixture* fixture;
        std::uint64_t value;
        static OpaqueResult Invoke(void* context, std::uint32_t) {
            auto* self = static_cast<Revoking*>(context);
            ++self->run->summary_.callback_invocations;
            self->fixture->Revoke();
            return OpaqueResult{self->value};
        }
    };

    struct Counter {
        std::uint64_t* calls;
        std::uint64_t value;
        static OpaqueResult Invoke(void* context, std::uint32_t) {
            auto* self = static_cast<Counter*>(context);
            ++*self->calls;
            return OpaqueResult{self->value};
        }
    };

    SplitMix64 rng_;
    RunSummary summary_;
    OfflineNativeShadow shadow_;
    std::optional<NativeScope> scope_;
    // Runner model of the single hint: (fixture ordinal, key) of the last
    // eligible primary positive, cleared by every other outcome.
    std::optional<std::pair<std::uint64_t, std::uint32_t>> hint_;
    std::uint64_t fixture_ordinal_ = 0;
    std::uint64_t normal_returns_ = 0;
    std::array<NativeRecord, kNativeRecordCapacity> drain_{};
};

const char* SkipName(std::size_t index) {
    static constexpr const char* kNames[kNativeSkipCount] = {
        "None",         "Off",         "SessionDisabled", "Reentrant", "MissingScope",
        "CallerExcluded", "MissingFixture", "ProofLost",  "TailPositive", "EndSentinel",
        "Fallback",     "InvalidPrimaryResult", "UnknownResult"};
    return kNames[index];
}

const char* ClassName(std::size_t index) {
    static constexpr const char* kNames[kResultClassCount] = {
        "PrimaryPositive", "TailPositive", "EndSentinel", "Fallback", "InvalidPrimaryResult", "Unknown"};
    return kNames[index];
}

}  // namespace

RunSummary RunContract(const RunConfig& config) {
    if (config.rebuilds == 0 || config.rebuilds > kMaxRebuilds) {
        throw std::invalid_argument("rebuilds must be 1..100000");
    }
    // Run holds a 256-record drain buffer and the evaluator: keep it off the stack.
    auto run = std::make_unique<Run>(config);
    return run->Execute();
}

bool Passed(const RunSummary& s) noexcept {
    const NativeCounters& n = s.native;
    std::uint64_t statuses = n.equal + n.mismatch + n.no_candidate;
    for (const std::uint64_t skipped : n.skipped_by_reason) {
        statuses += skipped;
    }
    std::uint64_t caller_calls = 0;
    for (const CallerCoverage& row : s.callers) {
        caller_calls += row.calls;
    }
    const CollectorCase& c = s.collector;
    return s.default_mode_off && !s.all_game_gates_met && s.oracle_mismatches == 0 && n.mismatch == 0 &&
           n.dropped_records == 0 && n.original_calls == s.callback_invocations &&
           n.original_calls == s.query_count && statuses == n.original_calls - n.exception_calls &&
           caller_calls == statuses && c.calls == kNativeRecordCapacity + 1 && c.original_calls == c.calls &&
           c.dropped == 1 && c.drained == kNativeRecordCapacity && c.drained_after_refill == 1;
}

void WriteJson(const RunSummary& s, std::ostream& out) {
    const NativeCounters& n = s.native;
    out << "{\n"
        << "  \"schema_version\": 1,\n"
        << "  \"scope\": \"offline-owned-fixtures\",\n"
        << "  \"config\": {\n"
        << "    \"seed\": " << s.config.seed << ",\n"
        << "    \"rebuilds\": " << s.config.rebuilds << "\n"
        << "  },\n"
        << "  \"default_mode\": \"" << (s.default_mode_off ? "Off" : "Shadow") << "\",\n"
        << "  \"fixture\": {\n"
        << "    \"slot_stride\": " << lookup_reuse::kSlotStride << ",\n"
        << "    \"control_offset\": " << lookup_reuse::kControlOffset << ",\n"
        << "    \"key_offset\": " << lookup_reuse::kKeyOffset << ",\n"
        << "    \"descriptor_offset\": " << kDescriptorOffset << ",\n"
        << "    \"masks\": [7, 15, 31],\n"
        << "    \"max_keys_per_table\": " << kMaxKeys << ",\n"
        << "    \"seeded_table_base\": \"0x10000000\",\n"
        << "    \"generator\": \"runner-local SplitMix64 with explicit modulo; Robin-Hood insertion; "
           "odd rebuilds re-create the previous bytes at the same addresses in the same scope\",\n"
        << "    \"oracle\": \"runner placement map and synthetic address formula; runner-side one-hint model\"\n"
        << "  },\n"
        << "  \"counts\": {\n"
        << "    \"boundary_fixture_count\": " << s.boundary_fixture_count << ",\n"
        << "    \"fixture_count\": " << s.fixture_count << ",\n"
        << "    \"query_count\": " << s.query_count << ",\n"
        << "    \"callback_invocations\": " << s.callback_invocations << ",\n"
        << "    \"oracle_mismatches\": " << s.oracle_mismatches << "\n"
        << "  },\n"
        << "  \"native\": {\n"
        << "    \"original_calls\": " << n.original_calls << ",\n"
        << "    \"candidate_attempts\": " << n.candidate_attempts << ",\n"
        << "    \"candidate_hits\": " << n.candidate_hits << ",\n"
        << "    \"equal\": " << n.equal << ",\n"
        << "    \"mismatch\": " << n.mismatch << ",\n"
        << "    \"no_candidate\": " << n.no_candidate << ",\n"
        << "    \"reentrant_calls\": " << n.reentrant_calls << ",\n"
        << "    \"exception_calls\": " << n.exception_calls << ",\n"
        << "    \"dropped_records\": " << n.dropped_records << ",\n"
        << "    \"skipped_by_reason\": {\n";
    for (std::size_t i = 1; i < kNativeSkipCount; ++i) {
        out << "      \"" << SkipName(i) << "\": " << n.skipped_by_reason[i] << (i + 1 < kNativeSkipCount ? ",\n" : "\n");
    }
    out << "    },\n"
        << "    \"result_class_counts\": {\n";
    for (std::size_t i = 0; i < kResultClassCount; ++i) {
        out << "      \"" << ClassName(i) << "\": " << n.result_class_counts[i]
            << (i + 1 < kResultClassCount ? ",\n" : "\n");
    }
    out << "    }\n"
        << "  },\n"
        << "  \"callers\": [\n";
    for (std::size_t id = 0; id < kCallerRows; ++id) {
        const CallerCoverage& row = s.callers[id];
        const bool allowed = id >= 1 && id <= 6 && generated::kCallers[id - 1].allowed;
        out << "    {\"caller_id\": " << id << ", \"allowed\": " << (allowed ? "true" : "false")
            << ", \"calls\": " << row.calls << ", \"compared\": " << row.compared << ", \"skipped\": " << row.skipped
            << "}" << (id + 1 < kCallerRows ? ",\n" : "\n");
    }
    const CollectorCase& c = s.collector;
    out << "  ],\n"
        << "  \"collector_case\": {\n"
        << "    \"capacity\": " << kNativeRecordCapacity << ",\n"
        << "    \"calls\": " << c.calls << ",\n"
        << "    \"original_calls\": " << c.original_calls << ",\n"
        << "    \"dropped\": " << c.dropped << ",\n"
        << "    \"drained\": " << c.drained << ",\n"
        << "    \"drained_after_refill\": " << c.drained_after_refill << "\n"
        << "  },\n"
        << "  \"all_game_gates_met\": " << (s.all_game_gates_met ? "true" : "false") << ",\n"
        << "  \"passed\": " << (Passed(s) ? "true" : "false") << ",\n"
        << "  \"limits\": [\n"
        << "    \"Owned native-shaped fixtures and synthetic address values only; no live memory or game input.\",\n"
        << "    \"Mismatch is unreachable here by design; its path is proven only by unit tests with a test-only "
           "fault seam.\",\n"
        << "    \"Counts are not timings and say nothing about native ABI, hook relocation, real return "
           "addresses or game speed.\",\n"
        << "    \"Many calls are skipped by design; zero mismatches does not mean native equivalence.\"\n"
        << "  ]\n"
        << "}\n";
}

}  // namespace lookup_contract::runner
