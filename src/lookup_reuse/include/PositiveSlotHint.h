// One remembered positive lookup location, validated against the current view
// before use.
//
// The hint stores only identity, mask, full key and a primary slot index. It
// never stores a view, bytes, descriptor or object pointer, and it never
// remembers a miss or a tail slot.
#pragma once

#include <cstddef>
#include <cstdint>

#include "TableView.h"

namespace lookup_reuse {

class PositiveSlotHint {
public:
    // Returns the remembered slot only when identity, mask and full key match
    // and the current slot at that primary index is occupied by the same full
    // key. std::nullopt means NeedsOriginal: the caller performs the normal
    // search. Never calls the reference search itself.
    SearchResult Try(const ValidatedTableView& view, std::uint32_t key) const noexcept;

    // Clears first, then keeps the result only when it is a primary slot of
    // the current view holding key with a positive control.
    void Remember(const ValidatedTableView& view, std::uint32_t key, SearchResult result) noexcept;

    void Clear() noexcept;

private:
    TableIdentity identity_{};
    std::uint64_t mask_ = 0;
    std::uint32_t key_ = 0;
    std::size_t index_ = 0;
    bool occupied_ = false;
};

}  // namespace lookup_reuse
