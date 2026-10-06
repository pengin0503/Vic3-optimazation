// Contract tests for PositiveSlotHint. Hand-placed fixtures; home slots
// (FNV-1a, see TableViewTests.cpp):
//   mask 7:  key 0 -> 5, 8 -> 5, 16 -> 5, 0x08000008 -> 5, 2 -> 7, 10 -> 7
//   mask 15: key 0 -> 5, 8 -> 13
//   mask 3:  key 8, 20, 24, 28, 32, 36 -> 1
#include <cstdint>
#include <limits>

#include "PositiveSlotHint.h"
#include "TableView.h"
#include "TestSupport.h"

using namespace lookup_reuse;
using namespace lookup_reuse::test;

namespace {

constexpr TableIdentity kIdentity{11, 21, 1, kLayoutVersion};

// mask=7, slots=10: key0@5/control1, key8@6/control2.
std::vector<std::byte> BaseRaw() {
    auto raw = RawSlots(10);
    PutSlot(raw, 5, 1, 0);
    PutSlot(raw, 6, 2, 8);
    return raw;
}

TableIdentity NextEpoch(TableIdentity identity) {
    ++identity.lifetime_epoch;
    return identity;
}

}  // namespace

LOOKUP_TEST(repeat_hit_avoids_reference) {
    const auto fixture = MakeFixture(kIdentity, 7, BaseRaw());
    const auto& view = fixture->View();
    PositiveSlotHint hint;
    CHECK(!hint.Try(view, 8));
    hint.Remember(view, 8, SearchResult{6});
    CHECK(hint.Try(view, 8) == SearchResult{6});
    CHECK(hint.Try(view, 8) == SearchResult{6});
    CHECK(!hint.Try(view, 0));
}

LOOKUP_TEST(repeat_four_lookups_one_search) {
    // A core caller doing Try -> (Reference only when needed) -> Remember.
    const auto fixture = MakeFixture(kIdentity, 7, BaseRaw());
    const auto& view = fixture->View();
    PositiveSlotHint hint;
    int reference_calls = 0;
    for (int i = 0; i < 4; ++i) {
        SearchResult slot = hint.Try(view, 8);
        if (!slot) {
            ++reference_calls;
            slot = ReferencePositiveSearch(view, 8);
            hint.Remember(view, 8, slot);
        }
        CHECK(slot == SearchResult{6});
    }
    CHECK(reference_calls == 1);
}

LOOKUP_TEST(tail_positive_never_cached) {
    // key2@7 (last primary slot), key10@8 (tail slot).
    auto raw = RawSlots(10);
    PutSlot(raw, 7, 1, 2);
    PutSlot(raw, 8, 2, 10);
    const auto tail = MakeFixture(kIdentity, 7, raw);
    const auto& view = tail->View();
    CHECK(ReferencePositiveSearch(view, 10) == SearchResult{8});

    PositiveSlotHint hint;
    hint.Remember(view, 10, SearchResult{8});
    CHECK(!hint.Try(view, 10));

    // The last primary slot is still eligible.
    hint.Remember(view, 2, SearchResult{7});
    CHECK(hint.Try(view, 2) == SearchResult{7});
    // A rejected tail Remember clears the previous primary hint.
    hint.Remember(view, 10, SearchResult{8});
    CHECK(!hint.Try(view, 2));
    CHECK(!hint.Try(view, 10));
}

LOOKUP_TEST(wrong_key_result_not_remembered) {
    const auto fixture = MakeFixture(kIdentity, 7, BaseRaw());
    const auto& view = fixture->View();
    PositiveSlotHint hint;
    // Slot 5 holds key 0, not key 8.
    hint.Remember(view, 8, SearchResult{5});
    CHECK(!hint.Try(view, 8));
    CHECK(!hint.Try(view, 0));
}

LOOKUP_TEST(identity_and_mask_changes) {
    const auto base = MakeFixture(kIdentity, 7, BaseRaw());
    PositiveSlotHint hint;
    hint.Remember(base->View(), 8, SearchResult{6});
    CHECK(hint.Try(base->View(), 8) == SearchResult{6});

    // Same bytes, new snapshot identity: each field alone forces NeedsOriginal.
    TableIdentity other_map = kIdentity;
    other_map.map_id = 12;
    TableIdentity other_storage = kIdentity;
    other_storage.storage_id = 22;
    for (const TableIdentity& identity : {other_map, other_storage, NextEpoch(kIdentity)}) {
        const auto snapshot = MakeFixture(identity, 7, BaseRaw());
        CHECK(ReferencePositiveSearch(snapshot->View(), 8) == SearchResult{6});
        CHECK(!hint.Try(snapshot->View(), 8));
    }

    // mask 15 snapshot: key0@5/control1, key8@13/control1.
    auto mask15_raw = RawSlots(17);
    PutSlot(mask15_raw, 5, 1, 0);
    PutSlot(mask15_raw, 13, 1, 8);
    const auto mask15 = MakeFixture(NextEpoch(kIdentity), 15, mask15_raw);
    CHECK(!hint.Try(mask15->View(), 8));

    // An owner that (wrongly) keeps the identity while changing the mask:
    // mask 3, keys 20/24/28/32/36 at slots 1..5, key8 at slot 6 / distance 5.
    // Slot 6 still holds key 8, yet the hint is not used. On validated views
    // this is also rejected by the primary-range check (slot 6 is tail under
    // mask 3); the mask comparison is kept as an extra guard.
    auto mask3_raw = RawSlots(8);
    const std::uint32_t mask3_keys[] = {20, 24, 28, 32, 36};
    for (std::size_t i = 0; i < 5; ++i) {
        PutSlot(mask3_raw, i + 1, static_cast<std::uint8_t>(i + 1), mask3_keys[i]);
    }
    PutSlot(mask3_raw, 6, 6, 8);
    const auto mask3 = MakeFixture(kIdentity, 3, mask3_raw);
    CHECK(mask3->View().Slot(6)->key == 8);
    CHECK(!hint.Try(mask3->View(), 8));

    // The hint itself is unchanged and still valid on the original snapshot.
    CHECK(hint.Try(base->View(), 8) == SearchResult{6});
}

LOOKUP_TEST(backshift_and_slot_reuse) {
    const auto base = MakeFixture(kIdentity, 7, BaseRaw());
    PositiveSlotHint hint;
    hint.Remember(base->View(), 8, SearchResult{6});

    // Regenerated snapshot: key0 deleted, key8 backshifted to slot 5/control1.
    const TableIdentity epoch2 = NextEpoch(kIdentity);
    auto backshift_raw = RawSlots(10);
    PutSlot(backshift_raw, 5, 1, 8);
    const auto backshift = MakeFixture(epoch2, 7, backshift_raw);
    CHECK(!hint.Try(backshift->View(), 8));
    const SearchResult fresh = ReferencePositiveSearch(backshift->View(), 8);
    CHECK(fresh == SearchResult{5});
    hint.Remember(backshift->View(), 8, fresh);
    CHECK(hint.Try(backshift->View(), 8) == SearchResult{5});

    // Another snapshot where slot 6 is reused by a different full key (16).
    auto reuse_raw = RawSlots(10);
    PutSlot(reuse_raw, 5, 1, 0);
    PutSlot(reuse_raw, 6, 2, 16);
    const auto reuse = MakeFixture(NextEpoch(epoch2), 7, reuse_raw);
    PositiveSlotHint old_hint;
    old_hint.Remember(base->View(), 8, SearchResult{6});
    CHECK(!old_hint.Try(reuse->View(), 8));
    CHECK(!old_hint.Try(reuse->View(), 16));

    // Even if an owner failed to advance the epoch, the full-key check on the
    // current slot rejects the stale location.
    const auto reuse_same_identity = MakeFixture(kIdentity, 7, reuse_raw);
    CHECK(!old_hint.Try(reuse_same_identity->View(), 8));
    CHECK(!old_hint.Try(reuse_same_identity->View(), 16));
    old_hint.Remember(reuse->View(), 16, ReferencePositiveSearch(reuse->View(), 16));
    CHECK(old_hint.Try(reuse->View(), 16) == SearchResult{6});
}

LOOKUP_TEST(full_key_and_uncacheable) {
    const auto fixture = MakeFixture(kIdentity, 7, BaseRaw());
    const auto& view = fixture->View();
    PositiveSlotHint hint;

    // Same low 24 bits and same home slot as key 8.
    hint.Remember(view, 8, SearchResult{6});
    CHECK(!hint.Try(view, 0x08000008u));

    // A miss clears the hint and is not remembered.
    hint.Remember(view, 8, std::nullopt);
    CHECK(!hint.Try(view, 8));

    // Out-of-span and empty-slot indices are not remembered.
    hint.Remember(view, 8, SearchResult{10});
    CHECK(!hint.Try(view, 8));
    hint.Remember(view, 8, SearchResult{std::numeric_limits<std::size_t>::max()});
    CHECK(!hint.Try(view, 8));
    hint.Remember(view, 8, SearchResult{2});
    CHECK(!hint.Try(view, 8));

    // An empty slot whose stale key bytes equal the queried key (control 0,
    // key 8 left at slot 4) is not a positive location.
    auto stale_raw = BaseRaw();
    PutSlot(stale_raw, 4, 0, 8);
    const auto stale = MakeFixture(kIdentity, 7, stale_raw);
    CHECK(stale->View().Slot(4)->key == 8);
    hint.Remember(stale->View(), 8, SearchResult{4});
    CHECK(!hint.Try(stale->View(), 8));
    // Also for key 0, whose bytes match every zero-filled empty slot.
    hint.Remember(view, 0, SearchResult{2});
    CHECK(!hint.Try(view, 0));

    // Clear removes a valid hint.
    hint.Remember(view, 8, SearchResult{6});
    CHECK(hint.Try(view, 8) == SearchResult{6});
    hint.Clear();
    CHECK(!hint.Try(view, 8));
}
