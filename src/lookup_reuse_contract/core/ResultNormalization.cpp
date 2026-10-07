#include "ResultNormalization.h"

#include "FixtureState.h"

namespace lookup_contract {

NormalizedResult NormalizeResult(const FixtureBorrow& borrow, std::uint32_t key, OpaqueResult result) noexcept {
    const NormalizedResult unknown{ResultClass::Unknown, std::nullopt};
    if (!borrow.Valid()) {
        return unknown;
    }
    const detail::FixtureState& state = *detail::BorrowAccess::State(borrow);
    const std::uint64_t value = result.value;
    if (value == state.spec.end_sentinel.value) {
        return {ResultClass::EndSentinel, std::nullopt};
    }
    if (value == state.spec.fallback.value) {
        return {ResultClass::Fallback, std::nullopt};
    }
    // Subtractions only after the comparisons that make them non-negative.
    if (value < state.spec.table_base || value - state.spec.table_base < kDescriptorOffset) {
        return unknown;
    }
    const std::uint64_t offset = value - state.spec.table_base - kDescriptorOffset;
    if (offset % lookup_reuse::kSlotStride != 0) {
        return unknown;
    }
    const std::uint64_t index = offset / lookup_reuse::kSlotStride;
    if (index >= state.slot_count) {
        return unknown;
    }
    const auto slot = static_cast<std::size_t>(index);
    const detail::SlotFields fields = detail::ReadSlotFields(state, slot);
    const bool primary = slot < state.primary_count;
    if (fields.control != 0 && fields.key == key) {
        return {primary ? ResultClass::PrimaryPositive : ResultClass::TailPositive, slot};
    }
    return primary ? NormalizedResult{ResultClass::InvalidPrimaryResult, std::nullopt} : unknown;
}

}  // namespace lookup_contract
