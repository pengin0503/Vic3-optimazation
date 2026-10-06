#include "TableView.h"

#include <algorithm>
#include <limits>

namespace lookup_reuse {
namespace {

// Explicit little-endian reads; no reliance on struct layout or alignment.
SlotRecord ReadSlot(const std::byte* bytes, std::size_t index) noexcept {
    const std::byte* base = bytes + index * kSlotStride;
    SlotRecord record;
    record.control = static_cast<std::uint8_t>(base[kControlOffset]);
    std::uint32_t key = 0;
    for (std::size_t i = 0; i < 4; ++i) {
        key |= static_cast<std::uint32_t>(static_cast<std::uint8_t>(base[kKeyOffset + i])) << (8 * i);
    }
    record.key = key;
    return record;
}

std::size_t HomeSlot(std::uint32_t key, std::uint64_t mask) noexcept {
    return static_cast<std::size_t>(static_cast<std::uint64_t>(HashKey(key)) & mask);
}

}  // namespace

TableIdentity ValidatedTableView::Identity() const noexcept { return owner_->identity_; }
std::uint64_t ValidatedTableView::Mask() const noexcept { return owner_->mask_; }
std::size_t ValidatedTableView::PrimaryCount() const noexcept { return owner_->primary_count_; }
std::size_t ValidatedTableView::SlotCount() const noexcept { return owner_->slot_count_; }

std::optional<SlotRecord> ValidatedTableView::Slot(std::size_t index) const noexcept {
    if (index >= owner_->slot_count_) {
        return std::nullopt;
    }
    return ReadSlot(owner_->bytes_.data(), index);
}

OwnedTableFixture::OwnedTableFixture(const TableIdentity& identity, std::uint64_t mask,
                                     std::size_t primary_count, std::size_t slot_count,
                                     std::span<const std::byte> bytes)
    : identity_(identity),
      mask_(mask),
      primary_count_(primary_count),
      slot_count_(slot_count),
      bytes_(bytes.begin(), bytes.end()),
      view_(*this) {}

std::variant<std::unique_ptr<OwnedTableFixture>, ViewError> OwnedTableFixture::Create(
    const TableIdentity& identity, std::uint64_t mask, std::uint64_t slot_count,
    std::span<const std::byte> bytes) {
    if (identity.layout_version != kLayoutVersion) {
        return ViewError::UnsupportedLayout;
    }
    // mask must be 2^n - 1 (n = 0 .. 64).
    if ((mask & (mask + 1)) != 0) {
        return ViewError::InvalidMask;
    }

    // Checked size arithmetic before any copy.
    constexpr std::uint64_t kSizeMax = std::numeric_limits<std::size_t>::max();
    if (mask == std::numeric_limits<std::uint64_t>::max() || mask + 1 > kSizeMax) {
        return ViewError::SizeOverflow;
    }
    if (slot_count > kSizeMax / kSlotStride) {
        return ViewError::SizeOverflow;
    }
    const auto primary = static_cast<std::size_t>(mask + 1);
    const auto slots = static_cast<std::size_t>(slot_count);

    if (bytes.size() != slots * kSlotStride || slots < primary) {
        return ViewError::TruncatedSpan;
    }
    // Every run of occupied slots must end in an empty slot inside the span,
    // so a probe never needs to read past the last slot.
    if (ReadSlot(bytes.data(), slots - 1).control != 0) {
        return ViewError::TruncatedSpan;
    }

    std::vector<std::uint32_t> keys;
    for (std::size_t i = 0; i < slots; ++i) {
        const SlotRecord record = ReadSlot(bytes.data(), i);
        if (record.control == 0) {
            continue;
        }
        const std::size_t home = HomeSlot(record.key, mask);
        if (home > i || i - home != static_cast<std::size_t>(record.control) - 1) {
            return ViewError::InvalidControl;
        }
        keys.push_back(record.key);
    }

    std::sort(keys.begin(), keys.end());
    if (std::adjacent_find(keys.begin(), keys.end()) != keys.end()) {
        return ViewError::DuplicateKey;
    }

    // Independent sequential reachability check (does not call the reference
    // search): every slot between home and the key's slot must let the probe
    // continue, i.e. hold control >= (its distance from this home) + 1.
    for (std::size_t i = 0; i < slots; ++i) {
        const SlotRecord record = ReadSlot(bytes.data(), i);
        if (record.control == 0) {
            continue;
        }
        const std::size_t home = HomeSlot(record.key, mask);
        for (std::size_t j = home; j < i; ++j) {
            const std::size_t needed = (j - home) + 1;
            if (static_cast<std::size_t>(ReadSlot(bytes.data(), j).control) < needed) {
                return ViewError::UnreachableKey;
            }
        }
    }

    return std::unique_ptr<OwnedTableFixture>(
        new OwnedTableFixture(identity, mask, primary, slots, bytes));
}

std::uint32_t HashKey(std::uint32_t key) noexcept {
    std::uint32_t hash = 0x811c9dc5u;
    for (int i = 0; i < 4; ++i) {
        hash ^= (key >> (8 * i)) & 0xffu;
        hash *= 0x01000193u;
    }
    return hash;
}

SearchResult ReferencePositiveSearch(const ValidatedTableView& view, std::uint32_t key) noexcept {
    const std::size_t home = HomeSlot(key, view.Mask());
    for (std::size_t distance = 0; distance <= kMaxProbeDistance; ++distance) {
        const auto slot = view.Slot(home + distance);
        if (!slot) {
            break;
        }
        const std::size_t expected = distance + 1;
        if (static_cast<std::size_t>(slot->control) < expected) {
            break;
        }
        if (slot->control == expected && slot->key == key) {
            return home + distance;
        }
    }
    return std::nullopt;
}

}  // namespace lookup_reuse
