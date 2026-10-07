// Owned native-shaped fixtures for the B0 offline contract.
//
// An OwnedNativeFixture copies slot bytes, validates them with the Stage A
// OwnedTableFixture and declares synthetic 64-bit address values (table base,
// end sentinel, fallback). Those values are only classified; they are never
// converted to C++ pointers or dereferenced, and they are not evidence about
// the native ABI. Identity/generation is issued privately by the owner, so no
// external span, raw pointer, caller-supplied epoch or bool can create a
// borrow. Single-thread, synchronous use only.
#pragma once

#include <cstddef>
#include <cstdint>
#include <memory>
#include <optional>
#include <span>
#include <variant>

#include "TableView.h"

namespace lookup_contract {

inline constexpr std::uint64_t kDescriptorOffset = 0x10;
// mask must be representable as a non-negative native signed int32.
inline constexpr std::uint64_t kMaxNativeMask = 0x7fffffff;

// A synthetic 64-bit address value returned by a host fixture callback. It is
// a plain integer: never cast to a pointer, never dereferenced.
struct OpaqueResult {
    std::uint64_t value = 0;

    friend bool operator==(const OpaqueResult&, const OpaqueResult&) = default;
};

struct NativeFixtureSpec {
    std::uint64_t mask = 0;
    std::uint64_t slot_count = 0;
    std::uint64_t table_base = 0;
    OpaqueResult end_sentinel;
    OpaqueResult fallback;
};

struct FixtureError {
    // AddressLayout: signed-mask representation, address arithmetic overflow,
    // or declared sentinel/fallback values that are zero, equal, or collide
    // with any slot's descriptor value. TableValidation: Stage A ViewError.
    enum class Kind { TableValidation, AddressLayout, EpochExhausted };
    Kind kind;
    std::optional<lookup_reuse::ViewError> table_error;
};

namespace detail {
struct FixtureState;
struct BorrowAccess;
}  // namespace detail

class OfflineNativeShadow;

// Copyable handle that pins a fixture's private state. Default-empty; only
// OwnedNativeFixture::Borrow creates a non-empty one. Valid() reports whether
// the owner still vouches for the state (not revoked, not destroyed).
class FixtureBorrow {
public:
    FixtureBorrow() noexcept = default;

    bool Empty() const noexcept { return state_ == nullptr; }
    bool Valid() const noexcept;
    // 0 for an empty borrow.
    std::uint64_t Generation() const noexcept;

private:
    friend class OwnedNativeFixture;
    friend struct detail::BorrowAccess;
    explicit FixtureBorrow(std::shared_ptr<const detail::FixtureState> state) noexcept
        : state_(std::move(state)) {}

    std::shared_ptr<const detail::FixtureState> state_;
};

class OwnedNativeFixture {
public:
    static std::variant<std::unique_ptr<OwnedNativeFixture>, FixtureError> Create(
        const NativeFixtureSpec& spec, std::span<const std::byte> input);

    OwnedNativeFixture(const OwnedNativeFixture&) = delete;
    OwnedNativeFixture(OwnedNativeFixture&&) = delete;
    OwnedNativeFixture& operator=(const OwnedNativeFixture&) = delete;
    OwnedNativeFixture& operator=(OwnedNativeFixture&&) = delete;
    // Revokes, then releases its reference; borrows keep the bytes alive.
    ~OwnedNativeFixture();

    FixtureBorrow Borrow() const noexcept;
    // Simulates loss of evidence: every borrow becomes invalid. The bytes are
    // not released while borrows exist.
    void Revoke() noexcept;

private:
    explicit OwnedNativeFixture(std::shared_ptr<detail::FixtureState> state) noexcept;

    std::shared_ptr<detail::FixtureState> state_;
};

}  // namespace lookup_contract
