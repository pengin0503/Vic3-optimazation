#include "NativeFixture.h"

#include <limits>
#include <utility>

#include "FixtureState.h"

namespace lookup_contract {
namespace detail {

SlotFields ReadSlotFields(const FixtureState& state, std::size_t index) noexcept {
    const std::byte* base = state.bytes.data() + index * lookup_reuse::kSlotStride;
    SlotFields fields;
    fields.control = static_cast<std::uint8_t>(base[lookup_reuse::kControlOffset]);
    for (std::size_t i = 0; i < 4; ++i) {
        fields.key |= static_cast<std::uint32_t>(static_cast<std::uint8_t>(base[lookup_reuse::kKeyOffset + i]))
                      << (8 * i);
    }
    return fields;
}

std::atomic<std::uint64_t>& GenerationCounter() noexcept {
    static std::atomic<std::uint64_t> counter{0};
    return counter;
}

}  // namespace detail

namespace {

constexpr std::uint64_t kU64Max = std::numeric_limits<std::uint64_t>::max();

FixtureError AddressLayout() { return FixtureError{FixtureError::Kind::AddressLayout, std::nullopt}; }

// True when value equals base + 40 * i + 0x10 for some i < slot_count.
// Requires the table end (base + 40 * slot_count) to be representable.
bool IsDescriptorValue(const NativeFixtureSpec& spec, std::uint64_t value) noexcept {
    if (value < spec.table_base || value - spec.table_base < kDescriptorOffset) {
        return false;
    }
    const std::uint64_t offset = value - spec.table_base - kDescriptorOffset;
    return offset % lookup_reuse::kSlotStride == 0 && offset / lookup_reuse::kSlotStride < spec.slot_count;
}

bool ValidAddressLayout(const NativeFixtureSpec& spec) noexcept {
    if (spec.slot_count == 0 || spec.slot_count > kU64Max / lookup_reuse::kSlotStride) {
        return false;
    }
    const std::uint64_t size = spec.slot_count * lookup_reuse::kSlotStride;
    // The table occupies [base, base + size); the end may be exactly 2^64.
    if (spec.table_base != 0 && size - 1 > kU64Max - spec.table_base) {
        return false;
    }
    const std::uint64_t sentinel = spec.end_sentinel.value;
    const std::uint64_t fallback = spec.fallback.value;
    if (sentinel == 0 || fallback == 0 || sentinel == fallback) {
        return false;
    }
    return !IsDescriptorValue(spec, sentinel) && !IsDescriptorValue(spec, fallback);
}

// Issues the next generation, refusing to wrap.
bool NextGeneration(std::uint64_t& out) noexcept {
    auto& counter = detail::GenerationCounter();
    std::uint64_t current = counter.load();
    do {
        if (current == kU64Max) {
            return false;
        }
    } while (!counter.compare_exchange_weak(current, current + 1));
    out = current + 1;
    return true;
}

}  // namespace

bool FixtureBorrow::Valid() const noexcept { return state_ != nullptr && !state_->revoked; }

std::uint64_t FixtureBorrow::Generation() const noexcept { return state_ ? state_->generation : 0; }

OwnedNativeFixture::OwnedNativeFixture(std::shared_ptr<detail::FixtureState> state) noexcept
    : state_(std::move(state)) {}

OwnedNativeFixture::~OwnedNativeFixture() { Revoke(); }

FixtureBorrow OwnedNativeFixture::Borrow() const noexcept { return FixtureBorrow(state_); }

void OwnedNativeFixture::Revoke() noexcept { state_->revoked = true; }

std::variant<std::unique_ptr<OwnedNativeFixture>, FixtureError> OwnedNativeFixture::Create(
    const NativeFixtureSpec& spec, std::span<const std::byte> input) {
    if (spec.mask > kMaxNativeMask || !ValidAddressLayout(spec)) {
        return AddressLayout();
    }
    std::uint64_t generation = 0;
    if (!NextGeneration(generation)) {
        return FixtureError{FixtureError::Kind::EpochExhausted, std::nullopt};
    }

    auto state = std::make_shared<detail::FixtureState>();
    state->spec = spec;
    state->generation = generation;
    state->bytes.assign(input.begin(), input.end());
    const lookup_reuse::TableIdentity identity{generation, generation, generation, lookup_reuse::kLayoutVersion};
    auto created = lookup_reuse::OwnedTableFixture::Create(identity, spec.mask, spec.slot_count, state->bytes);
    if (auto* error = std::get_if<lookup_reuse::ViewError>(&created)) {
        return FixtureError{FixtureError::Kind::TableValidation, *error};
    }
    state->table = std::move(std::get<std::unique_ptr<lookup_reuse::OwnedTableFixture>>(created));
    const auto& view = state->table->View();
    state->primary_count = view.PrimaryCount();
    state->slot_count = view.SlotCount();

    // The bytes the Stage A view validated and the bytes this fixture
    // classifies must decode identically.
    for (std::size_t i = 0; i < state->slot_count; ++i) {
        const auto stage_a = view.Slot(i);
        const auto own = detail::ReadSlotFields(*state, i);
        if (!stage_a || stage_a->control != own.control || stage_a->key != own.key) {
            return FixtureError{FixtureError::Kind::TableValidation, std::nullopt};
        }
    }
    return std::unique_ptr<OwnedNativeFixture>(new OwnedNativeFixture(std::move(state)));
}

}  // namespace lookup_contract
