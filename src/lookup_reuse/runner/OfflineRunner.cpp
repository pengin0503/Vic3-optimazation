#include "OfflineRunner.h"

#include <array>
#include <cstddef>
#include <iterator>
#include <limits>
#include <map>
#include <ostream>
#include <random>
#include <set>
#include <stdexcept>
#include <string>
#include <vector>

#include "PositiveSlotHint.h"
#include "TableView.h"

namespace lookup_reuse::runner {
namespace {

constexpr std::uint64_t kMapId = 1;
constexpr std::array<std::uint64_t, 3> kMasks{7, 15, 31};
constexpr std::size_t kMaxKeys = 16;
constexpr std::size_t kAbsentQueries = 4;
constexpr int kRepeatQueries = 4;

// Runner-local table under construction. It does not use the core's
// validator or reference search; only the shared hash definition decides the
// home slot. The placement map is the runner's own record of where each key
// went.
class PlacedTable {
public:
    explicit PlacedTable(std::uint64_t mask)
        // Up to kMaxKeys keys can spill past the last primary slot; one more
        // slot keeps an empty terminator.
        : mask_(mask), controls_(mask + 1 + kMaxKeys + 1, 0), keys_(controls_.size(), 0) {}

    std::uint64_t Mask() const { return mask_; }
    const std::map<std::uint32_t, std::size_t>& Placement() const { return placement_; }

    // Robin-Hood insertion: a key displaces a resident that is closer to its
    // own home, and the displaced key continues probing.
    void Insert(std::uint32_t key) {
        std::size_t index = Home(key);
        std::size_t distance = 0;
        std::uint32_t carried = key;
        for (;;) {
            if (index + 1 >= controls_.size() || distance > kMaxProbeDistance) {
                throw std::logic_error("runner table capacity exceeded");
            }
            if (controls_[index] == 0) {
                Put(index, carried, distance);
                return;
            }
            const std::size_t resident_distance = static_cast<std::size_t>(controls_[index]) - 1;
            if (resident_distance < distance) {
                const std::uint32_t displaced = keys_[index];
                Put(index, carried, distance);
                carried = displaced;
                distance = resident_distance;
            }
            ++index;
            ++distance;
        }
    }

    // Backshift deletion: following entries that are not at their home move
    // back by one slot.
    void Erase(std::uint32_t key) {
        auto found = placement_.find(key);
        if (found == placement_.end()) {
            throw std::logic_error("runner erase of absent key");
        }
        std::size_t index = found->second;
        placement_.erase(found);
        while (controls_[index + 1] > 1) {
            const std::uint32_t moved = keys_[index + 1];
            Put(index, moved, static_cast<std::size_t>(controls_[index + 1]) - 2);
            ++index;
        }
        controls_[index] = 0;
        keys_[index] = 0;
    }

    std::vector<std::byte> Serialize() const {
        std::vector<std::byte> raw(controls_.size() * kSlotStride, std::byte{0});
        for (std::size_t i = 0; i < controls_.size(); ++i) {
            std::byte* base = raw.data() + i * kSlotStride;
            base[kControlOffset] = std::byte{controls_[i]};
            for (std::size_t b = 0; b < 4; ++b) {
                base[kKeyOffset + b] = std::byte{static_cast<unsigned char>((keys_[i] >> (8 * b)) & 0xffu)};
            }
        }
        return raw;
    }

    std::size_t SlotCount() const { return controls_.size(); }

private:
    std::size_t Home(std::uint32_t key) const {
        return static_cast<std::size_t>(static_cast<std::uint64_t>(HashKey(key)) & mask_);
    }
    void Put(std::size_t index, std::uint32_t key, std::size_t distance) {
        controls_[index] = static_cast<std::uint8_t>(distance + 1);
        keys_[index] = key;
        placement_[key] = index;
    }

    std::uint64_t mask_;
    std::vector<std::uint8_t> controls_;
    std::vector<std::uint32_t> keys_;
    std::map<std::uint32_t, std::size_t> placement_;
};

struct OriginalContext {
    const ValidatedTableView* view = nullptr;
};

SearchResult InvokeReference(void* context, std::uint32_t key) {
    return ReferencePositiveSearch(*static_cast<OriginalContext*>(context)->view, key);
}

// Shared state of one run: one core hint that persists across snapshots (so
// identity changes are exercised) and one shadow evaluator session.
struct RunState {
    RunSummary summary;
    PositiveSlotHint core_hint;
    OfflineShadowEvaluator evaluator;
    std::uint64_t next_storage_id = 1;
    std::uint64_t next_epoch = 1;

    RunState() { evaluator.SetMode(ObserverMode::Shadow); }
};

void QueryOne(RunState& state, const ValidatedTableView& view,
              const std::set<std::uint32_t>& present,
              const std::map<std::uint32_t, std::size_t>& placement, std::uint32_t key) {
    RunSummary& summary = state.summary;
    ++summary.query_count;

    const SearchResult reference = ReferencePositiveSearch(view, key);
    if (reference.has_value() != (present.count(key) != 0)) {
        ++summary.membership_mismatches;
    }
    const auto placed = placement.find(key);
    const SearchResult expected_slot =
        placed == placement.end() ? SearchResult{} : SearchResult{placed->second};
    if (reference != expected_slot) {
        ++summary.slot_mismatches;
    }

    SearchResult core = state.core_hint.Try(view, key);
    if (core) {
        ++summary.core_hits;
    } else {
        ++summary.reference_calls;
        core = ReferencePositiveSearch(view, key);
        state.core_hint.Remember(view, key, core);
    }
    if (core != reference) {
        ++summary.slot_mismatches;
    }

    OriginalContext context{&view};
    const SearchResult shadow =
        state.evaluator.Evaluate(&view, key, OriginalLookup{&context, &InvokeReference});
    if (shadow != reference) {
        ++summary.slot_mismatches;
    }
}

// Validates one snapshot and runs all queries in a fresh observer scope.
void CheckSnapshot(RunState& state, const PlacedTable& table, const TableIdentity& identity,
                   const std::set<std::uint32_t>& present,
                   const std::vector<std::uint32_t>& queries) {
    const std::vector<std::byte> raw = table.Serialize();
    auto created = OwnedTableFixture::Create(identity, table.Mask(), table.SlotCount(), raw);
    if (std::holds_alternative<ViewError>(created)) {
        throw std::logic_error("runner generated a table the validator rejected: " +
                               std::to_string(static_cast<int>(std::get<ViewError>(created))));
    }
    const auto fixture = std::move(std::get<std::unique_ptr<OwnedTableFixture>>(created));
    ++state.summary.fixture_count;

    ObserverScope scope(state.evaluator);
    for (std::uint32_t key : queries) {
        QueryOne(state, fixture->View(), present, table.Placement(), key);
    }
}

TableIdentity NewStorage(RunState& state) {
    return TableIdentity{kMapId, state.next_storage_id++, state.next_epoch++, kLayoutVersion};
}

TableIdentity NextEpoch(RunState& state, TableIdentity identity) {
    identity.lifetime_epoch = state.next_epoch++;
    return identity;
}

std::vector<std::uint32_t> RepeatedQueries(const std::set<std::uint32_t>& present,
                                           const std::vector<std::uint32_t>& absent,
                                           std::uint32_t repeated) {
    std::vector<std::uint32_t> queries(present.begin(), present.end());
    queries.insert(queries.end(), absent.begin(), absent.end());
    for (int i = 0; i < kRepeatQueries; ++i) {
        queries.push_back(repeated);
    }
    return queries;
}

// Seed-independent fixtures matching the hand-derived Task 1/2 layouts.
void RunBoundaryInto(RunState& state) {
    // Tail: keys 2 and 10 both home at slot 7 (mask 7); key 10 lands in the
    // tail slot 8 and must never become a hint.
    {
        PlacedTable table(7);
        table.Insert(2);
        table.Insert(10);
        const std::set<std::uint32_t> present{2, 10};
        CheckSnapshot(state, table, NewStorage(state), present,
                      RepeatedQueries(present, {18, 0x08000002u}, 10));
    }
    // Backshift: keys 0 and 8 home at slot 5; erase 0 so 8 moves to slot 5,
    // as a new epoch of the same storage.
    {
        PlacedTable table(7);
        table.Insert(0);
        table.Insert(8);
        const TableIdentity identity = NewStorage(state);
        const std::set<std::uint32_t> before{0, 8};
        // This snapshot primes the core hint for key 8 at slot 6.
        CheckSnapshot(state, table, identity, before, RepeatedQueries(before, {16}, 8));
        table.Erase(0);
        const std::set<std::uint32_t> after{8};
        CheckSnapshot(state, table, NextEpoch(state, identity), after,
                      RepeatedQueries(after, {0, 16}, 8));
    }
    // One primary slot (mask 0) with the maximum key.
    {
        constexpr std::uint32_t kMax = std::numeric_limits<std::uint32_t>::max();
        PlacedTable table(0);
        table.Insert(kMax);
        const std::set<std::uint32_t> present{kMax};
        CheckSnapshot(state, table, NewStorage(state), present,
                      RepeatedQueries(present, {0, 1, kMax - 1}, kMax));
    }
}

// mt19937 yields 32-bit values in a result_type whose width differs between
// standard libraries; fix it to uint32_t so every platform draws the same keys.
std::uint32_t Next(std::mt19937& rng) { return static_cast<std::uint32_t>(rng()); }

std::size_t PickIndex(std::mt19937& rng, std::size_t size) { return Next(rng) % size; }

std::uint32_t DrawKey(std::mt19937& rng, const std::set<std::uint32_t>& keys) {
    switch (Next(rng) % 4) {
        case 0:
            // Small keys: many share home slots.
            return Next(rng) % 64;
        case 1:
            // Same low 24 bits as an existing key, different high byte.
            if (!keys.empty()) {
                auto it = keys.begin();
                std::advance(it, static_cast<std::ptrdiff_t>(PickIndex(rng, keys.size())));
                return (*it & 0x00ffffffu) | ((Next(rng) % 256) << 24);
            }
            return Next(rng);
        case 2:
            return std::numeric_limits<std::uint32_t>::max() - Next(rng) % 4;
        default:
            return Next(rng);
    }
}

std::vector<std::uint32_t> DrawAbsent(std::mt19937& rng, const std::set<std::uint32_t>& keys) {
    std::vector<std::uint32_t> absent;
    while (absent.size() < kAbsentQueries) {
        const std::uint32_t candidate = DrawKey(rng, keys);
        if (keys.count(candidate) == 0) {
            absent.push_back(candidate);
        }
    }
    return absent;
}

void RunSeededInto(RunState& state, const RunConfig& config) {
    std::mt19937 rng(config.seed);
    for (std::size_t rebuild = 0; rebuild < config.rebuilds; ++rebuild) {
        const std::uint64_t mask = kMasks[rebuild % kMasks.size()];
        const std::size_t key_count = 1 + PickIndex(rng, kMaxKeys);

        std::set<std::uint32_t> keys;
        while (keys.size() < key_count) {
            keys.insert(DrawKey(rng, keys));
        }
        PlacedTable table(mask);
        for (std::uint32_t key : keys) {
            table.Insert(key);
        }

        // Snapshot 1: new storage.
        auto it = keys.begin();
        std::advance(it, static_cast<std::ptrdiff_t>(PickIndex(rng, keys.size())));
        const std::uint32_t repeated = *it;
        const TableIdentity identity = NewStorage(state);
        CheckSnapshot(state, table, identity, keys,
                      RepeatedQueries(keys, DrawAbsent(rng, keys), repeated));

        // Snapshot 2: same storage, new epoch, one key removed by backshift.
        it = keys.begin();
        std::advance(it, static_cast<std::ptrdiff_t>(PickIndex(rng, keys.size())));
        const std::uint32_t erased = *it;
        table.Erase(erased);
        keys.erase(erased);
        std::vector<std::uint32_t> absent = DrawAbsent(rng, keys);
        absent.push_back(erased);
        const std::uint32_t repeated_after = keys.empty() ? erased : *keys.begin();
        CheckSnapshot(state, table, NextEpoch(state, identity), keys,
                      RepeatedQueries(keys, absent, repeated_after));
    }
}

void WriteField(std::ostream& out, const char* indent, const char* name, std::uint64_t value,
                bool last = false) {
    out << indent << '"' << name << "\": " << value << (last ? "\n" : ",\n");
}

}  // namespace

RunSummary RunBoundaryFixtures() {
    RunState state;
    RunBoundaryInto(state);
    state.summary.boundary_fixture_count = state.summary.fixture_count;
    state.summary.config.rebuilds = 0;
    state.summary.observer = state.evaluator.Counters();
    return state.summary;
}

RunSummary RunOffline(const RunConfig& config) {
    RunState state;
    state.summary.config = config;
    RunBoundaryInto(state);
    state.summary.boundary_fixture_count = state.summary.fixture_count;
    RunSeededInto(state, config);
    state.summary.observer = state.evaluator.Counters();
    return state.summary;
}

bool Passed(const RunSummary& summary) noexcept {
    return summary.membership_mismatches == 0 && summary.slot_mismatches == 0 &&
           summary.observer.mismatch == 0 && summary.observer.dropped_records == 0;
}

void WriteJson(const RunSummary& s, std::ostream& out) {
    static constexpr std::array<const char*, kSkipReasonCount> kReasonNames{
        "None", "Off", "MissingView", "MissingScope", "Reentrant", "SessionDisabled"};
    const auto& o = s.observer;
    out << "{\n";
    out << "  \"schema_version\": 1,\n";
    out << "  \"scope\": \"offline-synthetic\",\n";
    out << "  \"config\": {\n";
    WriteField(out, "    ", "seed", s.config.seed);
    WriteField(out, "    ", "rebuilds", s.config.rebuilds, true);
    out << "  },\n";
    out << "  \"table\": {\n";
    out << "    \"layout_version\": " << kLayoutVersion << ",\n";
    out << "    \"slot_stride\": " << kSlotStride << ",\n";
    out << "    \"hash\": \"fnv1a-32 over little-endian uint32 key\",\n";
    out << "    \"masks\": [7, 15, 31],\n";
    out << "    \"max_keys_per_table\": " << kMaxKeys << ",\n";
    out << "    \"generator\": \"std::mt19937 raw output with explicit modulo; runner-local "
           "Robin-Hood insertion and backshift deletion\"\n";
    out << "  },\n";
    out << "  \"counts\": {\n";
    WriteField(out, "    ", "boundary_fixture_count", s.boundary_fixture_count);
    WriteField(out, "    ", "fixture_count", s.fixture_count);
    WriteField(out, "    ", "query_count", s.query_count);
    WriteField(out, "    ", "core_hits", s.core_hits);
    WriteField(out, "    ", "reference_calls", s.reference_calls);
    WriteField(out, "    ", "membership_mismatches", s.membership_mismatches);
    WriteField(out, "    ", "slot_mismatches", s.slot_mismatches, true);
    out << "  },\n";
    out << "  \"observer\": {\n";
    WriteField(out, "    ", "observed_calls", o.observed_calls);
    WriteField(out, "    ", "candidate_attempts", o.candidate_attempts);
    WriteField(out, "    ", "candidate_hits", o.candidate_hits);
    WriteField(out, "    ", "equal", o.equal);
    WriteField(out, "    ", "mismatch", o.mismatch);
    WriteField(out, "    ", "fallback_or_no_positive", o.fallback_or_no_positive);
    WriteField(out, "    ", "reentrant_bypass", o.reentrant_bypass);
    WriteField(out, "    ", "dropped_records", o.dropped_records);
    out << "    \"skipped_by_reason\": {\n";
    for (std::size_t i = 1; i < kSkipReasonCount; ++i) {
        WriteField(out, "      ", kReasonNames[i], o.skipped_by_reason[i],
                   i + 1 == kSkipReasonCount);
    }
    out << "    }\n";
    out << "  },\n";
    out << "  \"passed\": " << (Passed(s) ? "true" : "false") << ",\n";
    out << "  \"limits\": [\n";
    out << "    \"Owned immutable synthetic tables only; not the native container.\",\n";
    out << "    \"Lookup counts are not timings and do not measure game speed.\",\n";
    out << "    \"No statement about native ABI, live memory lifetime or game-side safety.\"\n";
    out << "  ]\n";
    out << "}\n";
}

}  // namespace lookup_reuse::runner
