#include "ShadowComparison.h"

#include <stdexcept>

namespace lookup_reuse {
namespace {

// Tracks one in-flight call. If the original lookup throws, the destructor
// runs without Complete() and clears the hint; the exception itself is never
// caught here. The next outermost call resets the reentry flag on entry.
class InCallGuard {
public:
    InCallGuard(std::uint32_t& depth, PositiveSlotHint& hint) noexcept : depth_(depth), hint_(hint) {
        ++depth_;
    }
    ~InCallGuard() {
        --depth_;
        if (!completed_) {
            hint_.Clear();
        }
    }
    InCallGuard(const InCallGuard&) = delete;
    InCallGuard& operator=(const InCallGuard&) = delete;

    void Complete() noexcept { completed_ = true; }

private:
    std::uint32_t& depth_;
    PositiveSlotHint& hint_;
    bool completed_ = false;
};

}  // namespace

void OfflineShadowEvaluator::SetMode(ObserverMode mode) noexcept { mode_ = mode; }

SearchResult OfflineShadowEvaluator::Evaluate(const ValidatedTableView* view, std::uint32_t key,
                                              OriginalLookup original) {
    ++counters_.observed_calls;

    if (depth_ > 0) {
        // Reentrant call: bypass candidate work and invalidate the outer call.
        ++counters_.reentrant_bypass;
        outer_invalidated_ = true;
        hint_.Clear();
        InCallGuard guard(depth_, hint_);
        const SearchResult result = original.invoke(original.context, key);
        guard.Complete();
        if (!result) {
            ++counters_.fallback_or_no_positive;
        }
        ++counters_.skipped_by_reason[static_cast<std::size_t>(SkipReason::Reentrant)];
        last_record_ = ComparisonRecord{ComparisonStatus::Skipped, SkipReason::Reentrant,
                                        std::nullopt, result};
        return result;
    }

    SkipReason skip = SkipReason::None;
    if (mode_ == ObserverMode::Off) {
        skip = SkipReason::Off;
    } else if (session_disabled_) {
        skip = SkipReason::SessionDisabled;
    } else if (!scope_active_) {
        skip = SkipReason::MissingScope;
    } else if (view == nullptr) {
        skip = SkipReason::MissingView;
    }

    // The candidate is taken before the original runs.
    SearchResult candidate;
    if (skip == SkipReason::None) {
        ++counters_.candidate_attempts;
        candidate = hint_.Try(*view, key);
        if (candidate) {
            ++counters_.candidate_hits;
        }
    }

    outer_invalidated_ = false;
    SearchResult result;
    {
        InCallGuard guard(depth_, hint_);
        result = original.invoke(original.context, key);
        guard.Complete();
    }
    if (!result) {
        ++counters_.fallback_or_no_positive;
    }

    ComparisonRecord record{ComparisonStatus::Skipped, skip, candidate, result};
    if (skip == SkipReason::None && outer_invalidated_) {
        // A reentrant call ran inside the original: do not compare or keep the
        // candidate.
        outer_invalidated_ = false;
        hint_.Clear();
        record.reason = SkipReason::Reentrant;
    } else if (skip == SkipReason::None && candidate) {
        if (*candidate == result) {
            ++counters_.equal;
            record.status = ComparisonStatus::Equal;
        } else {
            ++counters_.mismatch;
            record.status = ComparisonStatus::Mismatch;
            hint_.Clear();
            session_disabled_ = true;
        }
    } else if (skip == SkipReason::None) {
        record.status = ComparisonStatus::NoCandidate;
        // Remember validates the location and clears the hint on a miss.
        hint_.Remember(*view, key, result);
    }
    outer_invalidated_ = false;

    if (record.status == ComparisonStatus::Skipped) {
        ++counters_.skipped_by_reason[static_cast<std::size_t>(record.reason)];
    }
    last_record_ = record;
    return result;
}

ObserverScope::ObserverScope(OfflineShadowEvaluator& evaluator) : evaluator_(evaluator) {
    if (evaluator_.scope_active_) {
        throw std::logic_error("nested ObserverScope on the same evaluator");
    }
    evaluator_.hint_.Clear();
    evaluator_.scope_active_ = true;
}

ObserverScope::~ObserverScope() {
    evaluator_.hint_.Clear();
    evaluator_.scope_active_ = false;
}

}  // namespace lookup_reuse
