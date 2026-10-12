#include "Test.h"
#include "../profiler/TickTaskHooks.h"
#include <memory>
#include <vector>
using namespace vic3;
namespace {
TickTaskHooks* active_hooks{};
void* expected_task{};void* expected_context{};
int outer_calls{},inner_calls{};bool throw_inner{},zero_time{};
struct Marker {const void* token;};
int token{};const Marker* thrown_at{};
uint32_t Thread() noexcept {return 7;}
uint64_t Time() noexcept {static uint64_t value=100;return zero_time?0:++value;}
void CheckArgs(void* a,void* b) {CHECK(a==expected_task && b==expected_context);}
void Inner(void* a,void* b) {
    ++inner_calls;CheckArgs(a,b);CHECK(active_hooks->Active()==2);
    if(throw_inner)try {throw Marker{&token};}catch(const Marker& m){thrown_at=&m;throw;}
}
void Outer(void* a,void* b) {
    ++outer_calls;CheckArgs(a,b);CHECK(active_hooks->Active()==1);
    active_hooks->Invoke(1,a,b);CHECK(active_hooks->Active()==1);
}
void Plain(void* a,void* b) {++outer_calls;CheckArgs(a,b);CHECK(active_hooks->Active()==1);}
void StopDuringOriginal(void* a,void* b) {Plain(a,b);active_hooks->StopRecording();}
uint64_t Read(const WireRecord& r,size_t offset,size_t width) {
    uint64_t value=0;for(size_t i=0;i<width;++i)value|=uint64_t(std::to_integer<unsigned>(r.bytes[offset+i]))<<(8*i);
    return value;
}
std::vector<WireRecord> Drain(EventBuffer& buffer) {
    std::vector<WireRecord> out;WireRecord record;while(buffer.TryRead(record))out.push_back(record);return out;
}
}
int main() {
    int a{},b{};expected_task=&a;expected_context=&b;
    auto pool=std::make_unique<EventBufferPool>();TickTaskHooks hooks(*pool,Thread,Time);active_hooks=&hooks;
    auto* buffer=pool->Claim(7);CHECK(buffer);hooks.SetOriginal(0,Outer);hooks.SetOriginal(1,Inner);
    hooks.StartRecording();hooks.Invoke(0,&a,&b);
    CHECK(outer_calls==1 && inner_calls==1 && hooks.Active()==0);
    auto records=Drain(*buffer);CHECK(records.size()==4);
    CHECK(Read(records[0],12,2)==1 && Read(records[1],12,2)==1);
    CHECK(Read(records[2],12,2)==2 && Read(records[3],12,2)==2);
    CHECK(Read(records[0],24,8)==Read(records[3],24,8));
    CHECK(Read(records[1],24,8)==Read(records[2],24,8));
    CHECK(Read(records[0],24,8)!=Read(records[1],24,8));

    throw_inner=true;bool same_exception=false;
    try {hooks.Invoke(0,&a,&b);}catch(const Marker& m){same_exception=&m==thrown_at && m.token==&token;}
    CHECK(same_exception && outer_calls==2 && inner_calls==2 && hooks.Active()==0);
    records=Drain(*buffer);CHECK(records.size()==2);
    CHECK(Read(records[0],12,2)==1 && Read(records[1],12,2)==1);
    throw_inner=false;hooks.Invoke(0,&a,&b);
    CHECK(outer_calls==3 && inner_calls==3 && hooks.Active()==0);CHECK(Drain(*buffer).size()==4);

    // One remaining slot: Begin succeeds, End drops, original still runs once.
    hooks.SetOriginal(0,Plain);Event filler{500,7,1,1,0,99};
    for(size_t i=0;i<1023;++i)CHECK(buffer->TryWrite(filler));
    const auto drops=pool->Dropped();hooks.Invoke(0,&a,&b);
    CHECK(outer_calls==4 && hooks.Active()==0 && pool->Dropped()==drops+1);
    records=Drain(*buffer);CHECK(records.size()==1024);
    CHECK(Read(records.back(),12,2)==1 && Read(records.back(),24,8)!=99);

    zero_time=true;hooks.Invoke(0,&a,&b);zero_time=false;
    CHECK(outer_calls==5 && hooks.Active()==0 && pool->Dropped()==drops+3);
    CHECK(Drain(*buffer).empty());
    hooks.SetOriginal(0,StopDuringOriginal);hooks.Invoke(0,&a,&b);
    CHECK(outer_calls==6 && hooks.Active()==0);records=Drain(*buffer);CHECK(records.size()==2);
    CHECK(Read(records[0],12,2)==1 && Read(records[1],12,2)==2);
    CHECK(Read(records[0],24,8)==Read(records[1],24,8));
    hooks.Invoke(0,&a,&b);CHECK(outer_calls==7 && hooks.Active()==0);CHECK(Drain(*buffer).empty());

    // No thread buffer available: drop telemetry without changing the original.
    auto exhausted=std::make_unique<EventBufferPool>();
    for(uint32_t i=100;i<164;++i)CHECK(exhausted->Claim(i));
    TickTaskHooks exhausted_hooks(*exhausted,Thread,Time);active_hooks=&exhausted_hooks;
    exhausted_hooks.SetOriginal(0,Plain);exhausted_hooks.StartRecording();exhausted_hooks.Invoke(0,&a,&b);
    CHECK(outer_calls==8 && exhausted_hooks.Active()==0);
    CHECK(exhausted->Dropped()==2 && exhausted->Exhaustions()==1);
    std::cout << "Reentry, exception identity, partial drops and in-flight stop passed\n";
}
