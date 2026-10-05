#pragma once
#include "V3pfFormat.h"
#include <atomic>
namespace vic3 {
static_assert(std::atomic<uint32_t>::is_always_lock_free && std::atomic<uint64_t>::is_always_lock_free);
class EventBuffer {
    std::array<WireRecord,1024> slots_{};
    alignas(64) std::atomic<uint64_t> write_{0};
    alignas(64) std::atomic<uint64_t> read_{0};
    std::atomic<uint64_t> dropped_{0};
    uint32_t sequence_{};uint64_t correlation_{};
public:
    std::atomic<uint32_t> owner{0};
    uint64_t NextCorrelation() noexcept {return ++correlation_;}
    bool TryWrite(Event event) noexcept;
    bool TryRead(WireRecord& record) noexcept;
    uint64_t Dropped() const noexcept {return dropped_.load(std::memory_order_relaxed);}
};
class EventBufferPool {
    std::array<EventBuffer,64> buffers_{};
    std::atomic<uint64_t> exhaustions_{0},missing_drops_{0};
public:
    EventBuffer* Claim(uint32_t thread) noexcept;
    void DropMissing(uint64_t count) noexcept {missing_drops_.fetch_add(count,std::memory_order_relaxed);}
    uint64_t Dropped() const noexcept;
    uint64_t Exhaustions() const noexcept {return exhaustions_.load(std::memory_order_relaxed);}
    std::array<EventBuffer,64>& Buffers() noexcept {return buffers_;}
};
}
