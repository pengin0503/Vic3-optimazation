// Contract tests for OwnedNativeFixture / FixtureBorrow: private ownership,
// generation, revocation and creation-time rejection.
#include <cstddef>
#include <cstdint>
#include <initializer_list>
#include <limits>
#include <memory>
#include <optional>
#include <span>
#include <type_traits>

#include "FixtureSupport.h"
#include "NativeFixture.h"
#include "ResultNormalization.h"
#include "TestSupport.h"

using namespace lookup_contract;
using namespace lookup_contract::test;

// Views and borrows can only come from an owner that validated its own copy.
static_assert(!std::is_default_constructible_v<OwnedNativeFixture>);
static_assert(!std::is_copy_constructible_v<OwnedNativeFixture>);
static_assert(!std::is_move_constructible_v<OwnedNativeFixture>);
static_assert(!std::is_constructible_v<OwnedNativeFixture, const NativeFixtureSpec&, std::span<const std::byte>>);
static_assert(!std::is_constructible_v<FixtureBorrow, bool>);
static_assert(!std::is_constructible_v<FixtureBorrow, std::uint64_t>);
static_assert(!std::is_constructible_v<FixtureBorrow, const void*>);
static_assert(!std::is_constructible_v<FixtureBorrow, std::span<const std::byte>>);
static_assert(!std::is_constructible_v<FixtureBorrow, const OwnedNativeFixture&>);
static_assert(std::is_nothrow_copy_constructible_v<FixtureBorrow>);

namespace {

FixtureError::Kind KindOf(const NativeFixtureSpec& spec, const std::vector<std::byte>& raw) {
    return ExpectFixtureError(spec, raw).kind;
}

}  // namespace

LOOKUP_TEST(fixed_fixture_borrow_is_valid) {
    const auto fixture = MakeFixedFixture();
    const FixtureBorrow borrow = fixture->Borrow();
    CHECK(borrow.Valid());
    CHECK(!borrow.Empty());
    CHECK(borrow.Generation() != 0);
    CHECK(fixture->Borrow().Generation() == borrow.Generation());
}

LOOKUP_TEST(default_borrow_is_empty) {
    const FixtureBorrow borrow;
    CHECK(borrow.Empty());
    CHECK(!borrow.Valid());
    CHECK(borrow.Generation() == 0);
}

LOOKUP_TEST(regenerated_fixture_gets_new_generation) {
    const auto first = MakeFixedFixture();
    const auto second = MakeFixedFixture();  // same base, bytes and values
    CHECK(first->Borrow().Generation() != second->Borrow().Generation());
    CHECK(second->Borrow().Generation() > first->Borrow().Generation());
}

LOOKUP_TEST(revoke_invalidates_existing_and_new_borrows) {
    const auto fixture = MakeFixedFixture();
    const FixtureBorrow before = fixture->Borrow();
    fixture->Revoke();
    CHECK(!before.Valid());
    CHECK(!before.Empty());
    CHECK(!fixture->Borrow().Valid());
    CHECK(NormalizeResult(before, 0, OpaqueResult{0x10d8}).kind == ResultClass::Unknown);
}

LOOKUP_TEST(owner_destruction_revokes_but_borrow_keeps_state) {
    auto fixture = MakeFixedFixture();
    const FixtureBorrow borrow = fixture->Borrow();
    const auto generation = borrow.Generation();
    fixture.reset();
    CHECK(!borrow.Valid());
    CHECK(borrow.Generation() == generation);
    const auto result = NormalizeResult(borrow, 0, OpaqueResult{0x10d8});
    CHECK(result.kind == ResultClass::Unknown);
    CHECK(!result.slot);
}

LOOKUP_TEST(input_is_copied_at_creation) {
    auto raw = FixedRaw();
    const auto fixture = MakeNativeFixture(FixedSpec(), raw);
    // Overwrite the caller's buffer: clear slot 5 and move key 0 elsewhere.
    PutSlot(raw, 5, 0, 0);
    PutSlot(raw, 6, 0, 0);
    const auto result = NormalizeResult(fixture->Borrow(), 0, OpaqueResult{0x10d8});
    CHECK(result.kind == ResultClass::PrimaryPositive);
    CHECK(result.slot == std::optional<std::size_t>{5});
}

LOOKUP_TEST(declared_values_must_be_nonzero_and_distinct) {
    auto spec = FixedSpec();
    spec.end_sentinel = OpaqueResult{0};
    CHECK(KindOf(spec, FixedRaw()) == FixtureError::Kind::AddressLayout);
    spec = FixedSpec();
    spec.fallback = OpaqueResult{0};
    CHECK(KindOf(spec, FixedRaw()) == FixtureError::Kind::AddressLayout);
    spec = FixedSpec();
    spec.fallback = spec.end_sentinel;
    CHECK(KindOf(spec, FixedRaw()) == FixtureError::Kind::AddressLayout);
}

LOOKUP_TEST(declared_values_must_not_hit_any_descriptor) {
    // Occupied primary (slot 5), occupied tail (slot 8), empty primary
    // (slot 0, slot 1 with a stale key) and the empty last slot 9.
    for (const std::uint64_t value : {0x10d8ull, 0x1150ull, 0x1010ull, 0x1038ull, 0x1178ull}) {
        auto spec = FixedSpec();
        spec.end_sentinel = OpaqueResult{value};
        CHECK(KindOf(spec, FixedRaw()) == FixtureError::Kind::AddressLayout);
        spec = FixedSpec();
        spec.fallback = OpaqueResult{value};
        CHECK(KindOf(spec, FixedRaw()) == FixtureError::Kind::AddressLayout);
    }
    // Inside the table but not a descriptor position: accepted.
    auto spec = FixedSpec();
    spec.end_sentinel = OpaqueResult{0x10d9};
    spec.fallback = OpaqueResult{0x11a0};  // first value past the last descriptor
    CHECK(MakeNativeFixture(spec, FixedRaw()) != nullptr);
}

LOOKUP_TEST(address_overflow_is_rejected) {
    constexpr auto kMax = std::numeric_limits<std::uint64_t>::max();
    auto spec = FixedSpec();
    spec.table_base = kMax - 0x100;  // 10 * 40 = 0x190 bytes do not fit
    CHECK(KindOf(spec, FixedRaw()) == FixtureError::Kind::AddressLayout);
    spec.table_base = kMax - 8;  // even the first descriptor offset overflows
    CHECK(KindOf(spec, FixedRaw()) == FixtureError::Kind::AddressLayout);
    spec = FixedSpec();
    spec.slot_count = kMax / 40 + 1;  // 40 * slot_count overflows
    CHECK(KindOf(spec, FixedRaw()) == FixtureError::Kind::AddressLayout);
    // Exactly at the top of the address space is representable.
    auto raw = RawSlots(2);
    PutSlot(raw, 0, 1, std::numeric_limits<std::uint32_t>::max());
    CHECK(MakeNativeFixture(NativeFixtureSpec{0, 2, kMax - 80 + 1, OpaqueResult{1}, OpaqueResult{2}}, raw) !=
          nullptr);
}

LOOKUP_TEST(mask_outside_signed_int32_is_rejected) {
    for (const std::uint64_t mask : std::initializer_list<std::uint64_t>{0xffffffffull, 0x1ffffffffull, std::numeric_limits<std::uint64_t>::max()}) {
        auto spec = FixedSpec();
        spec.mask = mask;
        CHECK(KindOf(spec, FixedRaw()) == FixtureError::Kind::AddressLayout);
    }
}

LOOKUP_TEST(stage_a_validation_errors_are_reported) {
    auto spec = FixedSpec();
    spec.mask = 6;
    auto error = ExpectFixtureError(spec, FixedRaw());
    CHECK(error.kind == FixtureError::Kind::TableValidation);
    CHECK(error.table_error == std::optional<lookup_reuse::ViewError>{lookup_reuse::ViewError::InvalidMask});

    spec = FixedSpec();
    spec.slot_count = 11;  // bytes describe 10 slots
    error = ExpectFixtureError(spec, FixedRaw());
    CHECK(error.table_error == std::optional<lookup_reuse::ViewError>{lookup_reuse::ViewError::TruncatedSpan});

    auto raw = FixedRaw();
    PutSlot(raw, 6, 2, 0);  // key 0 twice
    error = ExpectFixtureError(FixedSpec(), raw);
    CHECK(error.table_error == std::optional<lookup_reuse::ViewError>{lookup_reuse::ViewError::DuplicateKey});

    raw = FixedRaw();
    PutSlot(raw, 5, 2, 0);  // key 0 home is 5, so control must be 1
    error = ExpectFixtureError(FixedSpec(), raw);
    CHECK(error.table_error == std::optional<lookup_reuse::ViewError>{lookup_reuse::ViewError::InvalidControl});
}
