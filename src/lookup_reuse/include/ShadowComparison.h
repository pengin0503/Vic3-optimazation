// Offline shadow comparison: the original lookup always runs exactly once and
// its result is returned unchanged; a hint candidate is only compared.
//
// Offline contract: one thread per evaluator, synchronous callbacks only.
// There is no mode that skips the original lookup. Records and counters are
// fixed-size values; formatting and I/O belong to the runner.
#pragma once

#include <array>
#include <cstddef>
#include <cstdint>

#include "PositiveSlotHint.h"
#include "TableView.h"

namespace lookup_reuse {

enum class ObserverMode { Off, Shadow };

enum class ComparisonStatus { NoCandidate, Equal, Mismatch, Skipped };

enum class SkipReason { None, Off, MissingView, MissingScope, Reentrant, SessionDisabled };
inline constexpr std::size_t kSkipReasonCount = 6;

// invoke must be non-null (API precondition).
struct OriginalLookup {
    void* context = nullptr;
    SearchResult (*invoke)(void*, std::uint32_t) = nullptr;
};

struct ComparisonRecord {
    ComparisonStatus status = ComparisonStatus::NoCandidate;
    SkipReason reason = SkipReason::None;
    SearchResult candidate{};
    SearchResult original{};
};

struct ObserverCounters {
    std::uint64_t observed_calls = 0;
    std::uint64_t candidate_attempts = 0;
    std::uint64_t candidate_hits = 0;
    std::uint64_t equal = 0;
    std::uint64_t mismatch = 0;
    std::uint64_t fallback_or_no_positive = 0;
    std::uint64_t reentrant_bypass = 0;
    std::uint64_t dropped_records = 0;
    // Indexed by SkipReason; the None entry stays 0.
    std::array<std::uint64_t, kSkipReasonCount> skipped_by_reason{};
};

class ObserverScope;

class OfflineShadowEvaluator {
public:
    OfflineShadowEvaluator() = default;
    OfflineShadowEvaluator(const OfflineShadowEvaluator&) = delete;
    OfflineShadowEvaluator& operator=(const OfflineShadowEvaluator&) = delete;

    // Changing the mode never re-enables a session stopped by a mismatch; only
    // a new evaluator starts a new session.
    void SetMode(ObserverMode mode) noexcept;
    ObserverMode Mode() const noexcept { return mode_; }
    bool SessionDisabled() const noexcept { return session_disabled_; }

    // Calls original.invoke exactly once and returns its result unchanged.
    // Exceptions from the original propagate unchanged; the hint and in-call
    // state are cleared and no record is written for that call.
    SearchResult Evaluate(const ValidatedTableView* view, std::uint32_t key,
                          OriginalLookup original);

    // Record of the last call that returned normally. An outer call that
    // completes after a reentrant inner call overwrites the inner record.
    ComparisonRecord LastRecord() const noexcept { return last_record_; }
    const ObserverCounters& Counters() const noexcept { return counters_; }

private:
    friend class ObserverScope;

    ObserverMode mode_ = ObserverMode::Off;
    bool session_disabled_ = false;
    bool scope_active_ = false;
    std::uint32_t depth_ = 0;
    bool outer_invalidated_ = false;
    PositiveSlotHint hint_;
    ComparisonRecord last_record_;
    ObserverCounters counters_;
};

// Lookup scope of one evaluator. Construction and destruction clear the hint,
// so nothing is reused across scopes. Nested scopes on the same evaluator are
// rejected with std::logic_error.
class ObserverScope {
public:
    explicit ObserverScope(OfflineShadowEvaluator& evaluator);
    ~ObserverScope();
    ObserverScope(const ObserverScope&) = delete;
    ObserverScope(ObserverScope&&) = delete;
    ObserverScope& operator=(const ObserverScope&) = delete;
    ObserverScope& operator=(ObserverScope&&) = delete;

private:
    OfflineShadowEvaluator& evaluator_;
};

}  // namespace lookup_reuse
