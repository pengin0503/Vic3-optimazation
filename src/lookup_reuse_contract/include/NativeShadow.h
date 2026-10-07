// B0 offline shadow over owned native-shaped fixtures.
//
// Evaluate calls the original exactly once per valid call, whatever the mode,
// caller, scope or fixture, and returns its 64-bit result bit for bit;
// exceptions propagate unchanged. A hint candidate is only compared with the
// normalized original slot. One evaluator is used synchronously by one
// thread; scopes are bound explicitly to one evaluator and are never
// inherited. return_rva is a synthetic fixture value matched against the
// generated static caller witnesses, not a runtime return address.
#pragma once

#include <array>
#include <cstddef>
#include <cstdint>
#include <optional>
#include <span>

#include "NativeFixture.h"
#include "NativeRecords.h"
#include "PositiveSlotHint.h"
#include "ResultNormalization.h"

namespace lookup_contract {

#if defined(LOOKUP_CONTRACT_TESTING)
namespace testing {
struct FaultAccess;
}
#endif

// invoke must be non-null; Evaluate throws std::invalid_argument otherwise,
// before any state change.
struct OpaqueOriginal {
    void* context = nullptr;
    OpaqueResult (*invoke)(void*, std::uint32_t) = nullptr;
};

class NativeScope;

class OfflineNativeShadow {
public:
    // Issues a private, non-wrapping session id (std::overflow_error when
    // exhausted). Starts Off.
    OfflineNativeShadow();
    OfflineNativeShadow(const OfflineNativeShadow&) = delete;
    OfflineNativeShadow(OfflineNativeShadow&&) = delete;
    OfflineNativeShadow& operator=(const OfflineNativeShadow&) = delete;
    OfflineNativeShadow& operator=(OfflineNativeShadow&&) = delete;

    // A mismatch stops comparisons for this evaluator's session forever;
    // changing the mode or opening a new scope never re-enables it.
    void SetMode(NativeMode mode) noexcept;
    NativeMode Mode() const noexcept { return mode_; }
    bool SessionDisabled() const noexcept { return session_disabled_; }

    OpaqueResult Evaluate(FixtureBorrow borrow, std::uint32_t key, std::uint32_t return_rva,
                          OpaqueOriginal original);

    // Last call that returned normally; a later-completing outer call
    // overwrites an inner call's record.
    std::optional<NativeRecord> LastRecord() const noexcept { return last_record_; }
    const NativeCounters& Counters() const noexcept { return counters_; }
    // Moves up to output.size() collected records out (oldest first) and frees
    // their capacity. Call outside Evaluate, on the owning thread.
    std::size_t DrainRecords(std::span<NativeRecord> output) noexcept;

private:
    friend class NativeScope;
#if defined(LOOKUP_CONTRACT_TESTING)
    friend struct testing::FaultAccess;
    std::optional<std::size_t> fault_candidate_override_;
#endif

    void Finish(const NativeRecord& record) noexcept;

    NativeMode mode_ = NativeMode::Off;
    std::uint64_t mode_epoch_ = 0;
    bool session_disabled_ = false;
    std::uint64_t session_id_ = 0;
    std::uint64_t scope_id_ = 0;  // 0: no scope
    std::uint64_t last_scope_id_ = 0;
    std::uint32_t depth_ = 0;
    bool outer_invalidated_ = false;
    lookup_reuse::PositiveSlotHint hint_;
    NativeCounters counters_;
    std::optional<NativeRecord> last_record_;
    std::array<NativeRecord, kNativeRecordCapacity> records_{};
    std::size_t record_count_ = 0;
};

// Binds a scope to one evaluator. Entering and leaving clear the hint. A
// second scope on the same evaluator is rejected with std::logic_error; scope
// id exhaustion with std::overflow_error.
class NativeScope {
public:
    explicit NativeScope(OfflineNativeShadow& shadow);
    ~NativeScope();
    NativeScope(const NativeScope&) = delete;
    NativeScope(NativeScope&&) = delete;
    NativeScope& operator=(const NativeScope&) = delete;
    NativeScope& operator=(NativeScope&&) = delete;

private:
    OfflineNativeShadow& shadow_;
};

}  // namespace lookup_contract
