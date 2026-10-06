// Owned, immutable offline lookup tables and the reference positive search.
//
// This is a bounded offline representation of a 40-byte-slot ID array: the
// control byte at +4 is (non-wrapping probe distance from home) + 1, or 0 for
// an empty slot, and the full uint32 key is at +8. Descriptor contents are not
// modelled; results are slot indices. It is not an emulator of the native
// container (no fallback, sentinel, global initialization or empty-array
// address), and nothing here touches live process memory.
#pragma once

#include <cstddef>
#include <cstdint>
#include <memory>
#include <optional>
#include <span>
#include <variant>
#include <vector>

namespace lookup_reuse {

inline constexpr std::uint32_t kLayoutVersion = 1;
inline constexpr std::size_t kSlotStride = 40;
inline constexpr std::size_t kControlOffset = 4;
inline constexpr std::size_t kKeyOffset = 8;
// control = distance + 1 must fit in one byte.
inline constexpr std::size_t kMaxProbeDistance = 254;

// Identity of one immutable snapshot. lifetime_epoch is advanced by the
// fixture owner on every mutation, relocation or regeneration; the core never
// infers it. It is an offline construct, not an assumed game field.
struct TableIdentity {
    std::uint64_t map_id = 0;
    std::uint64_t storage_id = 0;
    std::uint64_t lifetime_epoch = 0;
    std::uint32_t layout_version = 0;

    friend bool operator==(const TableIdentity&, const TableIdentity&) = default;
};

struct SlotRecord {
    std::uint8_t control = 0;
    std::uint32_t key = 0;
};

// Slot index of a positive result; std::nullopt means NoPositiveResult.
// The index is not a descriptor pointer.
using SearchResult = std::optional<std::size_t>;

// Ordered: validation reports the first applicable error in this order.
enum class ViewError {
    UnsupportedLayout,
    InvalidMask,
    SizeOverflow,
    TruncatedSpan,
    InvalidControl,
    DuplicateKey,
    UnreachableKey,
};

class OwnedTableFixture;

// Read-only view borrowed from an OwnedTableFixture. Only the fixture can
// create it, after validation; it must not be used after the owner is
// destroyed. It exposes no mutable access to the bytes.
class ValidatedTableView {
public:
    ValidatedTableView(const ValidatedTableView&) = delete;
    ValidatedTableView(ValidatedTableView&&) = delete;
    ValidatedTableView& operator=(const ValidatedTableView&) = delete;
    ValidatedTableView& operator=(ValidatedTableView&&) = delete;

    TableIdentity Identity() const noexcept;
    std::uint64_t Mask() const noexcept;
    std::size_t PrimaryCount() const noexcept;
    std::size_t SlotCount() const noexcept;
    // std::nullopt when index >= SlotCount().
    std::optional<SlotRecord> Slot(std::size_t index) const noexcept;

private:
    friend class OwnedTableFixture;
    explicit ValidatedTableView(const OwnedTableFixture& owner) noexcept : owner_(&owner) {}

    const OwnedTableFixture* owner_;
};

// Privately owned copy of validated slot bytes. Neither copyable nor movable,
// so the address of View() is stable for the fixture's lifetime.
class OwnedTableFixture {
public:
    static std::variant<std::unique_ptr<OwnedTableFixture>, ViewError> Create(
        const TableIdentity& identity, std::uint64_t mask, std::uint64_t slot_count,
        std::span<const std::byte> bytes);

    OwnedTableFixture(const OwnedTableFixture&) = delete;
    OwnedTableFixture(OwnedTableFixture&&) = delete;
    OwnedTableFixture& operator=(const OwnedTableFixture&) = delete;
    OwnedTableFixture& operator=(OwnedTableFixture&&) = delete;

    const ValidatedTableView& View() const noexcept { return view_; }

private:
    friend class ValidatedTableView;
    OwnedTableFixture(const TableIdentity& identity, std::uint64_t mask, std::size_t primary_count,
                      std::size_t slot_count, std::span<const std::byte> bytes);

    const TableIdentity identity_;
    const std::uint64_t mask_;
    const std::size_t primary_count_;
    const std::size_t slot_count_;
    const std::vector<std::byte> bytes_;
    const ValidatedTableView view_;
};

// FNV-1a over the key's four little-endian bytes with 32-bit wraparound.
std::uint32_t HashKey(std::uint32_t key) noexcept;

// Bounded positive probe from HashKey(key) & mask: stops at the end of the
// span, when a slot's control is below (distance + 1), or past
// kMaxProbeDistance. A hit requires control == distance + 1 and the full key.
SearchResult ReferencePositiveSearch(const ValidatedTableView& view, std::uint32_t key) noexcept;

}  // namespace lookup_reuse
