// Independent vectors for NormalizeResult. Every value is written by hand
// from the FixtureSupport.h placement record (descriptor = base + 40*slot + 0x10).
#include <cstddef>
#include <cstdint>
#include <initializer_list>
#include <limits>
#include <optional>

#include "FixtureSupport.h"
#include "NativeFixture.h"
#include "ResultNormalization.h"
#include "TestSupport.h"

using namespace lookup_contract;
using namespace lookup_contract::test;

namespace {

using Slot = std::optional<std::size_t>;

bool Is(const NormalizedResult& r, ResultClass kind, Slot slot) { return r.kind == kind && r.slot == slot; }

}  // namespace

LOOKUP_TEST(primary_tail_unknown_vectors) {
    auto f = MakeFixedFixture();
    auto b = f->Borrow();
    CHECK(NormalizeResult(b, 0, {0x10d8}).slot == std::optional<std::size_t>{5});
    CHECK(NormalizeResult(b, 2, {0x1128}).kind == ResultClass::PrimaryPositive);
    CHECK(NormalizeResult(b, 10, {0x1150}).kind == ResultClass::TailPositive);
    CHECK(NormalizeResult(b, 0, {0}).kind == ResultClass::Unknown);
    CHECK(NormalizeResult(b, 0, {0x10d9}).kind == ResultClass::Unknown);
}

LOOKUP_TEST(primary_positive_slots) {
    auto f = MakeFixedFixture();
    auto b = f->Borrow();
    CHECK(Is(NormalizeResult(b, 0, {0x10d8}), ResultClass::PrimaryPositive, 5));
    CHECK(Is(NormalizeResult(b, 8, {0x1100}), ResultClass::PrimaryPositive, 6));
    CHECK(Is(NormalizeResult(b, 2, {0x1128}), ResultClass::PrimaryPositive, 7));  // last primary
}

LOOKUP_TEST(first_primary_slot) {
    auto f = MakeSinglePrimaryFixture(0x1000);
    CHECK(Is(NormalizeResult(f->Borrow(), std::numeric_limits<std::uint32_t>::max(), {0x1010}),
             ResultClass::PrimaryPositive, 0));
}

LOOKUP_TEST(tail_positive_and_tail_failures) {
    auto f = MakeFixedFixture();
    auto b = f->Borrow();
    CHECK(Is(NormalizeResult(b, 10, {0x1150}), ResultClass::TailPositive, 8));
    CHECK(Is(NormalizeResult(b, 0, {0x1150}), ResultClass::Unknown, std::nullopt));   // tail wrong key
    CHECK(Is(NormalizeResult(b, 10, {0x1178}), ResultClass::Unknown, std::nullopt));  // tail empty
}

LOOKUP_TEST(declared_sentinel_and_fallback) {
    auto f = MakeFixedFixture();
    auto b = f->Borrow();
    CHECK(Is(NormalizeResult(b, 0, {0x8000}), ResultClass::EndSentinel, std::nullopt));
    CHECK(Is(NormalizeResult(b, 0, {0x9000}), ResultClass::Fallback, std::nullopt));
}

LOOKUP_TEST(invalid_primary_results) {
    auto f = MakeFixedFixture();
    auto b = f->Borrow();
    CHECK(Is(NormalizeResult(b, 0, {0x1010}), ResultClass::InvalidPrimaryResult, std::nullopt));       // empty slot 0
    CHECK(Is(NormalizeResult(b, 0xdead, {0x1038}), ResultClass::InvalidPrimaryResult, std::nullopt));  // stale key
    CHECK(Is(NormalizeResult(b, 8, {0x10d8}), ResultClass::InvalidPrimaryResult, std::nullopt));       // wrong key
}

LOOKUP_TEST(unknown_values_are_not_merged) {
    auto f = MakeFixedFixture();
    auto b = f->Borrow();
    for (const std::uint64_t value : std::initializer_list<std::uint64_t>{0x0ull, 0xff0ull, 0x1000ull, 0x100full, 0x10d9ull, 0x10e7ull, 0x11a0ull,
                                      0x8001ull, std::numeric_limits<std::uint64_t>::max()}) {
        CHECK(Is(NormalizeResult(b, 0, {value}), ResultClass::Unknown, std::nullopt));
    }
}

LOOKUP_TEST(top_of_address_space_has_no_overflow) {
    constexpr auto kMax = std::numeric_limits<std::uint64_t>::max();
    const std::uint64_t base = kMax - 80 + 1;  // two slots end exactly at 2^64
    auto f = MakeSinglePrimaryFixture(base);
    auto b = f->Borrow();
    const auto key = std::numeric_limits<std::uint32_t>::max();
    CHECK(Is(NormalizeResult(b, key, {base + 0x10}), ResultClass::PrimaryPositive, 0));
    CHECK(Is(NormalizeResult(b, key, {base + 0x10 + 40}), ResultClass::Unknown, std::nullopt));  // empty tail
    CHECK(Is(NormalizeResult(b, key, {kMax}), ResultClass::Unknown, std::nullopt));
    CHECK(Is(NormalizeResult(b, key, {base - 1}), ResultClass::Unknown, std::nullopt));
}

LOOKUP_TEST(empty_or_revoked_borrow_is_unknown) {
    CHECK(Is(NormalizeResult(FixtureBorrow{}, 0, {0x10d8}), ResultClass::Unknown, std::nullopt));
    auto f = MakeFixedFixture();
    auto b = f->Borrow();
    f->Revoke();
    CHECK(Is(NormalizeResult(b, 0, {0x10d8}), ResultClass::Unknown, std::nullopt));
    CHECK(Is(NormalizeResult(b, 0, {0x8000}), ResultClass::Unknown, std::nullopt));
}
