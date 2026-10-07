#include "Test.h"
#include "../profiler/TickTaskHooks.h"
#include "../common/TraceWriter.h"
#include <memory>
#include <stdexcept>
using namespace vic3;
static int calls=0;static void* first;static void* second;
#ifdef _WIN32
__declspec(noinline)
#endif
static void Original(void* a,void* b){++calls;first=a;second=b;}
static void Throwing(void*,void*){++calls;throw std::runtime_error("fixture");}
static uint32_t Thread() noexcept{return 7;}
static uint64_t Time() noexcept{static uint64_t now=100;return ++now;}
int main(int argc,char** argv) {
    CHECK(argc==2);auto pool=std::make_unique<EventBufferPool>();
    TickTaskHooks hooks(*pool,Thread,Time);int a=1,b=2;hooks.SetOriginal(0,Original);hooks.SetOriginal(1,Original);hooks.SetOriginal(2,Throwing);
    hooks.StartRecording();hooks.Invoke(0,&a,&b);CHECK(calls==1);CHECK(first==&a && second==&b);
    WireRecord begin,end;auto* buffer=pool->Claim(7);CHECK(buffer->TryRead(begin));CHECK(buffer->TryRead(end));CHECK(begin.size==32 && end.size==40);CHECK(begin.bytes[12]==std::byte{1} && end.bytes[12]==std::byte{2});
    for(size_t i=8;i<12;++i){CHECK(begin.bytes[i]==end.bytes[i]);}
    for(size_t i=16;i<20;++i){CHECK(begin.bytes[i]==end.bytes[i]);}
    for(size_t i=24;i<32;++i){CHECK(begin.bytes[i]==end.bytes[i]);}
    std::filesystem::remove(argv[1]);TraceWriter writer;writer.Open(argv[1],RuntimeMetadata(7,false),1000,90,generated::kTargetTableSha256);CHECK(writer.Write(begin));CHECK(writer.Write(end));CHECK(writer.Finalize(0));
    Event event{200,7,1,1,0,1};for(size_t i=0;i<1024;++i){CHECK(buffer->TryWrite(event));}hooks.Invoke(1,&a,&b);CHECK(calls==2);CHECK(pool->Dropped()==2);
    hooks.StopRecording();hooks.Invoke(0,&a,&b);CHECK(calls==3);CHECK(pool->Dropped()==2);
    // The original exception propagates unchanged; no synthetic normal End.
    while(buffer->TryRead(begin)){}hooks.StartRecording();bool threw=false;try{hooks.Invoke(2,&a,&b);}catch(const std::runtime_error&){threw=true;}CHECK(threw && calls==4);CHECK(hooks.Active()==0);CHECK(buffer->TryRead(begin));CHECK(!buffer->TryRead(end));
#ifdef _WIN32
    hooks.StopRecording();MinHookBackend backend;CHECK(backend.Initialize());void* original=nullptr;void* address=reinterpret_cast<void*>(Original);CHECK(backend.Create(address,hooks.Detour(0),&original));hooks.SetOriginal(0,reinterpret_cast<TickTaskTailFn>(original));
    const std::array<void*,1> addresses{address};CHECK(backend.Enable(addresses));hooks.StartRecording();
    TickTaskTailFn volatile call=Original;const int before=calls;call(&a,&b);CHECK(calls==before+1 && first==&a && second==&b);
    CHECK(buffer->TryRead(begin));CHECK(buffer->TryRead(end));CHECK(!buffer->TryRead(begin));
    hooks.StopRecording();CHECK(backend.Disable(addresses));call(&a,&b);CHECK(calls==before+2);CHECK(!buffer->TryRead(begin));CHECK(backend.Remove(address));CHECK(backend.Shutdown());
#endif
    std::cout << "Arguments, original exactly once, drops and exception path passed\n";
}
