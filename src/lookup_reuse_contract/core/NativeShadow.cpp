#include "NativeShadow.h"

#include <atomic>
#include <limits>
#include <stdexcept>

#include "FixtureState.h"
#include "manifest_1_14_5.inc"

namespace lookup_contract {
namespace {

constexpr std::uint64_t kU64Max = std::numeric_limits<std::uint64_t>::max();

std::atomic<std::uint64_t>& SessionCounter() noexcept {
    static std::atomic<std::uint64_t> counter{0};
    return counter;
}

std::uint64_t NextSessionId() {
    auto& counter = SessionCounter();
    std::uint64_t current = counter.load();
    do {
        if (current == kU64Max) {
            throw std::overflow_error("OfflineNativeShadow: session ids exhausted");
        }
    } while (!counter.compare_exchange_weak(current, current + 1));
    return current + 1;
}

void Bump(std::uint64_t& counter) noexcept {
    if (counter != kU64Max) {
        ++counter;
    }
}

// Generated static witness lookup: 0 for an unknown return RVA.
const generated::CallerWitness* FindCaller(std::uint32_t return_rva) noexcept {
    for (const auto& caller : generated::kCallers) {
        if (caller.return_rva == return_rva) {
            return &caller;
        }
    }
    return nullptr;
}

NativeSkip SkipFor(ResultClass kind) noexcept {
    switch (kind) {
        case ResultClass::TailPositive:
            return NativeSkip::TailPositive;
        case ResultClass::EndSentinel:
            return NativeSkip::EndSentinel;
        case ResultClass::Fallback:
            return NativeSkip::Fallback;
        case ResultClass::InvalidPrimaryResult:
            return NativeSkip::InvalidPrimaryResult;
        case ResultClass::PrimaryPositive:
        case ResultClass::Unknown:
            break;
    }
    return NativeSkip::UnknownResult;
}

// Restores the reentrancy depth and, on an exception, clears the hint and
// counts the throw; the exception itself is never caught here.
class CallGuard {
public:
    CallGuard(std::uint32_t& depth, lookup_reuse::PositiveSlotHint& hint, NativeCounters& counters) noexcept
        : depth_(depth), hint_(hint), counters_(counters) {
        ++depth_;
    }
    ~CallGuard() {
        --depth_;
        if (!returned_) {
            hint_.Clear();
            Bump(counters_.exception_calls);
        }
    }
    CallGuard(const CallGuard&) = delete;
    CallGuard& operator=(const CallGuard&) = delete;

    void Returned() noexcept { returned_ = true; }

private:
    std::uint32_t& depth_;
    lookup_reuse::PositiveSlotHint& hint_;
    NativeCounters& counters_;
    bool returned_ = false;
};

}  // namespace

#if defined(LOOKUP_CONTRACT_TESTING)
namespace testing {
std::uint64_t ExchangeSessionCounterForTest(std::uint64_t value) noexcept { return SessionCounter().exchange(value); }
}  // namespace testing
#endif

OfflineNativeShadow::OfflineNativeShadow() : session_id_(NextSessionId()) {}

void OfflineNativeShadow::SetMode(NativeMode mode) noexcept {
    if (mode != mode_) {
        mode_ = mode;
        ++mode_epoch_;  // a round trip during a callback still counts as a change
    }
}

OpaqueResult OfflineNativeShadow::Evaluate(FixtureBorrow borrow, std::uint32_t key, std::uint32_t return_rva,
                                           OpaqueOriginal original) {
    if (original.invoke == nullptr) {
        throw std::invalid_argument("OfflineNativeShadow::Evaluate: original callback is null");
    }

    // 1. Reentrancy guard first, for every call. Any inner call invalidates
    //    the outer call's candidate.
    const bool reentrant = depth_ != 0;
    if (reentrant) {
        outer_invalidated_ = true;
        Bump(counters_.reentrant_calls);
    } else {
        outer_invalidated_ = false;
    }
    CallGuard guard(depth_, hint_, counters_);

    const generated::CallerWitness* caller = FindCaller(return_rva);
    NativeRecord record;
    record.caller_id = caller ? caller->caller_id : generated::kUnknownCallerId;
    record.key = key;
    record.session_id = session_id_;
    record.scope_id = scope_id_;

    // 2. Preconditions, in the spec's priority order.
    NativeSkip reason = NativeSkip::None;
    if (mode_ == NativeMode::Off) {
        reason = NativeSkip::Off;
    } else if (session_disabled_) {
        reason = NativeSkip::SessionDisabled;
    } else if (reentrant) {
        reason = NativeSkip::Reentrant;
    } else if (scope_id_ == 0) {
        reason = NativeSkip::MissingScope;
    } else if (caller == nullptr || !caller->allowed) {
        reason = NativeSkip::CallerExcluded;
    } else if (!borrow.Valid()) {
        reason = NativeSkip::MissingFixture;
    }

    const detail::FixtureState* state = detail::BorrowAccess::State(borrow);
    const bool eligible = reason == NativeSkip::None;
    const std::uint64_t mode_epoch = mode_epoch_;
    const std::uint64_t scope_id = scope_id_;
    std::optional<std::size_t> candidate;
    if (eligible) {
        Bump(counters_.candidate_attempts);
        candidate = hint_.Try(state->table->View(), key);
        if (candidate) {
            Bump(counters_.candidate_hits);
#if defined(LOOKUP_CONTRACT_TESTING)
            if (fault_candidate_override_) {
                candidate = fault_candidate_override_;
            }
#endif
        }
    }

    // 3. The original, exactly once. Exceptions propagate unchanged; the
    //    guard restores the depth and clears the hint.
    Bump(counters_.original_calls);
    const OpaqueResult result = original.invoke(original.context, key);
    guard.Returned();
    record.original = result;

    // 4. Re-check what the comparison depends on.
    if (eligible) {
        if (mode_ == NativeMode::Off) {
            reason = NativeSkip::Off;
        } else if (session_disabled_) {
            reason = NativeSkip::SessionDisabled;
        } else if (outer_invalidated_) {
            reason = NativeSkip::Reentrant;
        } else if (scope_id_ != scope_id) {
            reason = NativeSkip::MissingScope;
        } else if (!borrow.Valid() || mode_epoch_ != mode_epoch) {
            reason = NativeSkip::ProofLost;
        }
    }
    if (reason != NativeSkip::None) {
        hint_.Clear();
        record.status = NativeStatus::Skipped;
        record.reason = reason;
        Finish(record);
        return result;
    }

    // 5. Normalize; compare only a primary positive against a candidate.
    const NormalizedResult normalized = NormalizeResult(borrow, key, result);
    Bump(counters_.result_class_counts[static_cast<std::size_t>(normalized.kind)]);
    record.result_class = normalized.kind;
    record.original_slot = normalized.slot;
    if (normalized.kind != ResultClass::PrimaryPositive) {
        hint_.Clear();
        record.status = NativeStatus::Skipped;
        record.reason = SkipFor(normalized.kind);
        Finish(record);
        return result;
    }
    const auto& view = state->table->View();
    record.candidate_slot = candidate;
    if (!candidate) {
        record.status = NativeStatus::NoCandidate;
        Bump(counters_.no_candidate);
        hint_.Remember(view, key, normalized.slot);  // clears first
    } else if (*candidate == *normalized.slot) {
        record.status = NativeStatus::Equal;
        Bump(counters_.equal);
        hint_.Remember(view, key, normalized.slot);  // only the verified original slot
    } else {
        record.status = NativeStatus::Mismatch;
        Bump(counters_.mismatch);
        session_disabled_ = true;
        hint_.Clear();
    }
    Finish(record);
    return result;
}

void OfflineNativeShadow::Finish(const NativeRecord& record) noexcept {
    if (record.status == NativeStatus::Skipped) {
        Bump(counters_.skipped_by_reason[static_cast<std::size_t>(record.reason)]);
    }
    last_record_ = record;
    if (record_count_ < records_.size()) {
        records_[record_count_++] = record;
    } else {
        Bump(counters_.dropped_records);
    }
}

std::size_t OfflineNativeShadow::DrainRecords(std::span<NativeRecord> output) noexcept {
    const std::size_t moved = output.size() < record_count_ ? output.size() : record_count_;
    for (std::size_t i = 0; i < moved; ++i) {
        output[i] = records_[i];
    }
    for (std::size_t i = moved; i < record_count_; ++i) {
        records_[i - moved] = records_[i];
    }
    record_count_ -= moved;
    return moved;
}

NativeScope::NativeScope(OfflineNativeShadow& shadow) : shadow_(shadow) {
    if (shadow.scope_id_ != 0) {
        throw std::logic_error("NativeScope: nested scope on the same evaluator");
    }
    if (shadow.last_scope_id_ == kU64Max) {
        throw std::overflow_error("NativeScope: scope ids exhausted");
    }
    shadow.scope_id_ = ++shadow.last_scope_id_;
    shadow.hint_.Clear();
}

NativeScope::~NativeScope() {
    shadow_.hint_.Clear();
    shadow_.scope_id_ = 0;
}

}  // namespace lookup_contract
