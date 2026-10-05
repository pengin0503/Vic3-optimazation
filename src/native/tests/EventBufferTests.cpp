#include "Test.h"
#include "../common/EventBuffer.h"
#include <memory>
#include <thread>
using namespace vic3;
int main() {
    auto pool=std::make_unique<EventBufferPool>();auto* b=pool->Claim(7);CHECK(b);CHECK(pool->Claim(7)==b);
    Event e{100,7,1,1,0,1};WireRecord out;
    for(size_t i=0;i<1024;++i){CHECK(b->TryWrite(e));}
    CHECK(!b->TryWrite(e));CHECK(pool->Dropped()==1);
    for(uint32_t i=0;i<1024;++i){CHECK(b->TryRead(out));CHECK(out.bytes[20]==std::byte(i&255));}CHECK(!b->TryRead(out));CHECK(b->TryWrite(e));CHECK(b->TryRead(out));CHECK(out.bytes[20]==std::byte{1});CHECK(out.bytes[21]==std::byte{4});
    for(uint32_t i=1;i<=63;++i){CHECK(pool->Claim(i+100));}
    CHECK(!pool->Claim(999));CHECK(pool->Exhaustions()==1);
    // One producer, one consumer with real contention; no mock of the queue.
    EventBuffer concurrent;std::thread producer([&]{for(uint32_t i=0;i<10000;++i){e.correlation=i;while(!concurrent.TryWrite(e))std::this_thread::yield();}});
    uint32_t count=0;while(count<10000){if(concurrent.TryRead(out)){uint64_t correlation{};for(size_t i=0;i<8;++i)correlation|=uint64_t(std::to_integer<unsigned>(out.bytes[24+i]))<<(8*i);CHECK(correlation==count);++count;}else std::this_thread::yield();}
    producer.join();std::cout << "Overflow, exhaustion and SPSC order passed\n";
}
