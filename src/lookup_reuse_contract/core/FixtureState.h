// Private state shared by an OwnedNativeFixture and its borrows. Not part of
// the public include directory: only B0 core sources (and the test-only
// fault seam) see it.
#pragma once

#include <atomic>
#include <cstddef>
#include <cstdint>
#include <memory>
#include <vector>

#include "NativeFixture.h"
#include "TableView.h"

namespace lookup_contract::detail {

struct FixtureState {
    NativeFixtureSpec spec;
    std::uint64_t generation = 0;
    std::size_t primary_count = 0;
    std::size_t slot_count = 0;
    // Private immutable copy used for classification; the Stage A fixture
    // owns a second copy whose decoded slots were checked equal at creation.
    std::vector<std::byte> bytes;
    std::unique_ptr<lookup_reuse::OwnedTableFixture> table;
    bool revoked = false;
};

struct SlotFields {
    std::uint8_t control = 0;
    std::uint32_t key = 0;
};

// Little-endian field reads; index must be < state.slot_count.
SlotFields ReadSlotFields(const FixtureState& state, std::size_t index) noexcept;

// Process-wide monotonic generation source (0 is never issued).
std::atomic<std::uint64_t>& GenerationCounter() noexcept;

struct BorrowAccess {
    static const FixtureState* State(const FixtureBorrow& borrow) noexcept { return borrow.state_.get(); }
};

}  // namespace lookup_contract::detail
