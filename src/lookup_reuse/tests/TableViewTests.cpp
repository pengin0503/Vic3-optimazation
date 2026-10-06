// Contract tests for OwnedTableFixture / ValidatedTableView / ReferencePositiveSearch.
//
// Every slot placement below is written by hand. Home slots were derived once
// from the FNV-1a definition (basis 0x811c9dc5, prime 0x01000193, key bytes in
// little-endian order) and are recorded as literals in the comments:
//   mask 7:  key 0 -> 5, 8 -> 5, 16 -> 5, 0x08000008 -> 5, 2 -> 7, 10 -> 7, 3 -> 6
//   mask 0:  every key -> 0
#include <cstdint>
#include <limits>
#include <type_traits>

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

}  // namespace

LOOKUP_TEST(fnv1a_hash_vectors) {
    // Independent FNV-1a vectors (32-bit wraparound, little-endian key bytes).
    CHECK(HashKey(0) == 0x4b95f515u);
    CHECK(HashKey(1) == 0xfb69b604u);
    CHECK(HashKey(8) == 0xccf7ed9du);
    CHECK(HashKey(10) == 0x6d506bbfu);
    CHECK(HashKey(std::numeric_limits<std::uint32_t>::max()) == 0xe3160fb1u);
}

LOOKUP_TEST(positive_search_fixed_layout) {
    const auto fixture = MakeFixture(kIdentity, 7, BaseRaw());
    const auto& view = fixture->View();
    CHECK(view.Mask() == 7);
    CHECK(view.PrimaryCount() == 8);
    CHECK(view.SlotCount() == 10);
    CHECK(view.Identity().map_id == 11 && view.Identity().storage_id == 21);
    CHECK(view.Identity().lifetime_epoch == 1 && view.Identity().layout_version == 1);

    CHECK(ReferencePositiveSearch(view, 0) == SearchResult{5});
    CHECK(ReferencePositiveSearch(view, 8) == SearchResult{6});
    CHECK(!ReferencePositiveSearch(view, 16));
    CHECK(!ReferencePositiveSearch(view, 2));

    const auto slot6 = view.Slot(6);
    CHECK(slot6.has_value() && slot6->control == 2 && slot6->key == 8);
    const auto slot0 = view.Slot(0);
    CHECK(slot0.has_value() && slot0->control == 0);
    CHECK(!view.Slot(10));
    CHECK(!view.Slot(std::numeric_limits<std::size_t>::max()));
}

LOOKUP_TEST(full_key_not_low24) {
    // 0x08000008 shares the low 24 bits and the home slot with key 8.
    const auto base = MakeFixture(kIdentity, 7, BaseRaw());
    CHECK(!ReferencePositiveSearch(base->View(), 0x08000008u));

    auto raw = RawSlots(10);
    PutSlot(raw, 5, 1, 8);
    PutSlot(raw, 6, 2, 0x08000008u);
    const auto both = MakeFixture(kIdentity, 7, raw);
    CHECK(ReferencePositiveSearch(both->View(), 8) == SearchResult{5});
    CHECK(ReferencePositiveSearch(both->View(), 0x08000008u) == SearchResult{6});
}

LOOKUP_TEST(tail_positive_search) {
    // Probe runs from the last primary slot (7) into the tail slot 8.
    auto raw = RawSlots(10);
    PutSlot(raw, 7, 1, 2);
    PutSlot(raw, 8, 2, 10);
    const auto fixture = MakeFixture(kIdentity, 7, raw);
    CHECK(ReferencePositiveSearch(fixture->View(), 2) == SearchResult{7});
    CHECK(ReferencePositiveSearch(fixture->View(), 10) == SearchResult{8});
    CHECK(fixture->View().PrimaryCount() == 8);
}

LOOKUP_TEST(one_primary_and_max_key) {
    constexpr std::uint32_t kMax = std::numeric_limits<std::uint32_t>::max();
    auto raw = RawSlots(2);
    PutSlot(raw, 0, 1, kMax);
    const auto one = MakeFixture(kIdentity, 0, raw);
    CHECK(one->View().PrimaryCount() == 1);
    CHECK(ReferencePositiveSearch(one->View(), kMax) == SearchResult{0});
    CHECK(!ReferencePositiveSearch(one->View(), 0));
    CHECK(!ReferencePositiveSearch(one->View(), 1));

    // An empty single-slot table is its own terminator.
    const auto empty = MakeFixture(kIdentity, 0, RawSlots(1));
    CHECK(!ReferencePositiveSearch(empty->View(), kMax));
}

LOOKUP_TEST(invalid_layout_mask_size) {
    const auto raw = BaseRaw();
    TableIdentity v2 = kIdentity;
    v2.layout_version = 2;
    CHECK(ExpectRejected(v2, 7, 10, raw) == ViewError::UnsupportedLayout);
    // Layout is reported before the (also invalid) mask.
    CHECK(ExpectRejected(v2, 6, 10, raw) == ViewError::UnsupportedLayout);

    CHECK(ExpectRejected(kIdentity, 6, 10, raw) == ViewError::InvalidMask);
    CHECK(ExpectRejected(kIdentity, 0x10, 10, raw) == ViewError::InvalidMask);

    // 2^64-1 has the 2^n-1 shape, but mask+1 overflows.
    CHECK(ExpectRejected(kIdentity, std::numeric_limits<std::uint64_t>::max(), 10, raw) ==
          ViewError::SizeOverflow);
    // slot_count * 40 overflows.
    CHECK(ExpectRejected(kIdentity, 7, std::numeric_limits<std::uint64_t>::max(), raw) ==
          ViewError::SizeOverflow);

    // A 39-byte record cannot hold one 40-byte slot.
    const std::vector<std::byte> short_record(39, std::byte{0});
    CHECK(ExpectRejected(kIdentity, 0, 1, short_record) == ViewError::TruncatedSpan);
    // Span longer than the declared slots is not silently accepted either.
    CHECK(ExpectRejected(kIdentity, 7, 9, raw) == ViewError::TruncatedSpan);
    // Fewer slots than primary slots.
    const auto four = RawSlots(4);
    CHECK(ExpectRejected(kIdentity, 7, 4, four) == ViewError::TruncatedSpan);
    // mask0, one occupied slot and no empty terminator after it.
    auto no_terminator = RawSlots(1);
    PutSlot(no_terminator, 0, 1, 5);
    CHECK(ExpectRejected(kIdentity, 0, 1, no_terminator) == ViewError::TruncatedSpan);
}

LOOKUP_TEST(invalid_duplicate_distance_reachability) {
    // Same full key twice (both controls consistent with home 5).
    auto duplicate = RawSlots(10);
    PutSlot(duplicate, 5, 1, 0);
    PutSlot(duplicate, 6, 2, 0);
    CHECK(ExpectRejected(kIdentity, 7, 10, duplicate) == ViewError::DuplicateKey);

    // key0 (home 5) at slot 6 claims distance 0.
    auto wrong_distance = RawSlots(10);
    PutSlot(wrong_distance, 6, 1, 0);
    CHECK(ExpectRejected(kIdentity, 7, 10, wrong_distance) == ViewError::InvalidControl);

    // key2 (home 7) placed before its home.
    auto before_home = RawSlots(10);
    PutSlot(before_home, 6, 1, 2);
    CHECK(ExpectRejected(kIdentity, 7, 10, before_home) == ViewError::InvalidControl);

    // key8 at slot 6 with a consistent control, but slot 5 is empty: the
    // normal search stops at slot 5.
    auto gap = RawSlots(10);
    PutSlot(gap, 6, 2, 8);
    CHECK(ExpectRejected(kIdentity, 7, 10, gap) == ViewError::UnreachableKey);

    // key16 (home 5) at slot 7 / distance 2; slot 6 holds key3 at its own
    // home (control 1 < 2), so the probe for key16 stops at slot 6.
    auto robin_hood_stop = RawSlots(10);
    PutSlot(robin_hood_stop, 5, 1, 0);
    PutSlot(robin_hood_stop, 6, 1, 3);
    PutSlot(robin_hood_stop, 7, 3, 16);
    CHECK(ExpectRejected(kIdentity, 7, 10, robin_hood_stop) == ViewError::UnreachableKey);

    // Error order: InvalidControl is reported before DuplicateKey.
    auto mixed = RawSlots(10);
    PutSlot(mixed, 5, 1, 0);
    PutSlot(mixed, 6, 2, 0);
    PutSlot(mixed, 2, 1, 2);
    CHECK(ExpectRejected(kIdentity, 7, 10, mixed) == ViewError::InvalidControl);
}

LOOKUP_TEST(control_distance_overflow) {
    // mask 0: every key homes at slot 0. Slot i holds key 100+i at distance i
    // (control i+1) for i = 0..254, so control 255 is the largest valid value.
    auto valid = RawSlots(257);
    for (std::size_t i = 0; i < 255; ++i) {
        PutSlot(valid, i, static_cast<std::uint8_t>(i + 1), static_cast<std::uint32_t>(100 + i));
    }
    const auto max_distance = MakeFixture(kIdentity, 0, valid);
    CHECK(ReferencePositiveSearch(max_distance->View(), 354) == SearchResult{254});
    CHECK(!ReferencePositiveSearch(max_distance->View(), 999));

    // Distance 255 needs control 256, which a byte cannot represent.
    auto overflow = valid;
    PutSlot(overflow, 255, 255, 999);
    CHECK(ExpectRejected(kIdentity, 0, 257, overflow) == ViewError::InvalidControl);
}

LOOKUP_TEST(borrow_is_immutable) {
    static_assert(!std::is_copy_constructible_v<OwnedTableFixture>);
    static_assert(!std::is_move_constructible_v<OwnedTableFixture>);
    static_assert(!std::is_copy_assignable_v<OwnedTableFixture>);
    static_assert(!std::is_move_assignable_v<OwnedTableFixture>);
    static_assert(!std::is_copy_constructible_v<ValidatedTableView>);
    static_assert(!std::is_move_constructible_v<ValidatedTableView>);
    static_assert(!std::is_copy_assignable_v<ValidatedTableView>);
    static_assert(!std::is_move_assignable_v<ValidatedTableView>);
    static_assert(!std::is_default_constructible_v<ValidatedTableView>);

    auto raw = BaseRaw();
    const auto fixture = MakeFixture(kIdentity, 7, raw);
    const ValidatedTableView* first = &fixture->View();

    // Mutating the caller's buffer after Create must not affect the owned copy.
    PutSlot(raw, 6, 2, 16);
    PutSlot(raw, 5, 0, 0);
    CHECK(&fixture->View() == first);
    CHECK(ReferencePositiveSearch(fixture->View(), 8) == SearchResult{6});
    CHECK(ReferencePositiveSearch(fixture->View(), 0) == SearchResult{5});
    CHECK(!ReferencePositiveSearch(fixture->View(), 16));
}
