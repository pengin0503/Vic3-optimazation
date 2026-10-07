#pragma once
#include "../common/EventBuffer.h"
#include "HookBackend.h"
namespace vic3 {
using TickTaskTailFn=void(*)(void*,void*);
using ThreadIdFn=uint32_t(*)() noexcept;
using TimestampFn=uint64_t(*)() noexcept;
class TickTaskHooks {
    EventBufferPool& pool_;ThreadIdFn thread_;TimestampFn time_;
    std::array<TickTaskTailFn,3> originals_{};
    std::atomic<bool> recording_{false};std::atomic<uint64_t> active_{0};
public:
    TickTaskHooks(EventBufferPool& pool,ThreadIdFn thread,TimestampFn time) noexcept;
    void SetOriginal(size_t index,TickTaskTailFn original) noexcept {originals_[index]=original;}
    void StartRecording() noexcept {recording_.store(true,std::memory_order_release);}
    void StopRecording() noexcept {recording_.store(false,std::memory_order_release);}
    uint64_t Active() const noexcept {return active_.load(std::memory_order_acquire);}
    void Invoke(size_t index,void* task,void* context);
    void* Detour(size_t index) const noexcept;
};
}
