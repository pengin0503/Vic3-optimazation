#include "EventBuffer.h"
namespace vic3 {
bool EventBuffer::TryWrite(Event event) noexcept {
    event.sequence=sequence_++;const uint64_t write=write_.load(std::memory_order_relaxed);
    if(write-read_.load(std::memory_order_acquire)>=slots_.size()){dropped_.fetch_add(1,std::memory_order_relaxed);return false;}
    const auto record=EncodeEvent(event);if(!record.size){dropped_.fetch_add(1,std::memory_order_relaxed);return false;}
    slots_[write%slots_.size()]=record;write_.store(write+1,std::memory_order_release);return true;
}
bool EventBuffer::TryRead(WireRecord& record) noexcept {
    const uint64_t read=read_.load(std::memory_order_relaxed);if(read==write_.load(std::memory_order_acquire))return false;
    record=slots_[read%slots_.size()];read_.store(read+1,std::memory_order_release);return true;
}
EventBuffer* EventBufferPool::Claim(uint32_t thread) noexcept {
    if(!thread)return nullptr;
    for(auto& b:buffers_)if(b.owner.load(std::memory_order_relaxed)==thread)return &b;
    for(auto& b:buffers_){uint32_t empty=0;if(b.owner.compare_exchange_strong(empty,thread,std::memory_order_relaxed))return &b;}
    exhaustions_.fetch_add(1,std::memory_order_relaxed);return nullptr;
}
uint64_t EventBufferPool::Dropped() const noexcept {uint64_t sum=missing_drops_.load(std::memory_order_relaxed);for(const auto& b:buffers_)sum+=b.Dropped();return sum;}
}
