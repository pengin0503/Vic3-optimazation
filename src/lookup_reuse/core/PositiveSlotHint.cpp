#include "PositiveSlotHint.h"

namespace lookup_reuse {
namespace {

// The location is usable only if it is a primary slot of this view that is
// currently occupied by exactly this full key.
bool HoldsKeyInPrimary(const ValidatedTableView& view, std::size_t index,
                       std::uint32_t key) noexcept {
    if (view.Identity().layout_version != kLayoutVersion || index >= view.PrimaryCount()) {
        return false;
    }
    const auto slot = view.Slot(index);
    return slot && slot->control != 0 && slot->key == key;
}

}  // namespace

SearchResult PositiveSlotHint::Try(const ValidatedTableView& view,
                                   std::uint32_t key) const noexcept {
    if (!occupied_ || key != key_ || !(view.Identity() == identity_) || view.Mask() != mask_) {
        return std::nullopt;
    }
    if (!HoldsKeyInPrimary(view, index_, key)) {
        return std::nullopt;
    }
    return index_;
}

void PositiveSlotHint::Remember(const ValidatedTableView& view, std::uint32_t key,
                                SearchResult result) noexcept {
    Clear();
    if (!result || !HoldsKeyInPrimary(view, *result, key)) {
        return;
    }
    identity_ = view.Identity();
    mask_ = view.Mask();
    key_ = key;
    index_ = *result;
    occupied_ = true;
}

void PositiveSlotHint::Clear() noexcept {
    identity_ = TableIdentity{};
    mask_ = 0;
    key_ = 0;
    index_ = 0;
    occupied_ = false;
}

}  // namespace lookup_reuse
