#include "TickTaskHooks.h"
namespace vic3 {
static TickTaskHooks* instance{};
static void Investment(void* a,void* b){instance->Invoke(0,a,b);}
static void Migration(void* a,void* b){instance->Invoke(1,a,b);}
static void Employment(void* a,void* b){instance->Invoke(2,a,b);}
TickTaskHooks::TickTaskHooks(EventBufferPool& pool,ThreadIdFn thread,TimestampFn time) noexcept:pool_(pool),thread_(thread),time_(time){instance=this;}
void* TickTaskHooks::Detour(size_t index) const noexcept {const TickTaskTailFn functions[]{Investment,Migration,Employment};return reinterpret_cast<void*>(functions[index]);}
void TickTaskHooks::Invoke(size_t index,void* task,void* context) {
    active_.fetch_add(1,std::memory_order_acq_rel);
    struct Exit {std::atomic<uint64_t>& active;~Exit(){active.fetch_sub(1,std::memory_order_release);}} exit{active_};
    EventBuffer* buffer=nullptr;uint64_t correlation=0;uint32_t thread=0;
    if(recording_.load(std::memory_order_acquire)) {
        thread=thread_();buffer=pool_.Claim(thread);
        if(buffer) {
            correlation=buffer->NextCorrelation();const uint64_t now=time_();
            if(now)buffer->TryWrite(Event{now,thread,1,static_cast<uint32_t>(index+1),0,correlation});
            else pool_.DropMissing(1);
        } else pool_.DropMissing(2);
    }
    // No catch or argument/return transformation. The trampoline is installed before enable.
    originals_[index](task,context);
    if(buffer) {
        const uint64_t now=time_();if(now)buffer->TryWrite(Event{now,thread,2,static_cast<uint32_t>(index+1),0,correlation});else pool_.DropMissing(1);
    }
}
}
