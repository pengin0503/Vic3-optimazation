#include "Test.h"
#include "../common/SharedConfig.h"
#include "../profiler/ProfilerRuntime.h"
#include <algorithm>
#ifdef _WIN32
#include "../common/WinHandle.h"
#include <new>
#include <utility>
static bool fail_next_allocation=false;
void* operator new(std::size_t size) {if(std::exchange(fail_next_allocation,false))throw std::bad_alloc();if(void* p=std::malloc(size?size:1))return p;throw std::bad_alloc();}
void operator delete(void* p) noexcept {std::free(p);}
void operator delete(void* p,std::size_t) noexcept {std::free(p);}
#endif
using namespace vic3;
int main(int argc,char** argv) {
    (void)argc;(void)argv;
    SharedConfig c;c.target_mask=7;c.output[0]=u'C';c.output[1]=u':';c.output[2]=u'\\';c.output[3]=u't';
    CHECK(ValidateConfig(c)==ConfigError::None);CHECK(!c.Disabled());
    c.flags=ConfigDisabled;CHECK(c.Disabled());CHECK(ValidateConfig(c)==ConfigError::None);
    c.version=2;CHECK(ValidateConfig(c)==ConfigError::Version);c.version=1;
    c.magic=0;CHECK(ValidateConfig(c)==ConfigError::Magic);c.magic=kConfigMagic;
    c.structure_bytes=0;CHECK(ValidateConfig(c)==ConfigError::Size);c.structure_bytes=sizeof(SharedConfig);
    std::fill(std::begin(c.output),std::end(c.output),u'x');CHECK(ValidateConfig(c)==ConfigError::OutputPath);
    std::fill(std::begin(c.output),std::end(c.output),char16_t{});CHECK(ValidateConfig(c)==ConfigError::OutputPath);
    c.output[0]=u'x';c.target_mask=8;CHECK(ValidateConfig(c)==ConfigError::Targets);c.target_mask=7;
    c.flags=8;CHECK(ValidateConfig(c)==ConfigError::Flags);
#ifdef _WIN32
    // Regression: allocating named-object setup must not escape the noexcept entry boundary.
    fail_next_allocation=true;RunProfilerRuntime(GetModuleHandleW(nullptr));CHECK(!fail_next_allocation);
    SharedConfig received;
    fail_next_allocation=true;bool allocation_reported=false;try{ReadSharedConfig(GetCurrentProcessId(),received);}catch(const std::bad_alloc&){allocation_reported=true;}CHECK(allocation_reported && !fail_next_allocation);
    CHECK(ReadSharedConfig(GetCurrentProcessId(),received)==ConfigError::MissingMapping);
    const auto name=ObjectName(L"Config",GetCurrentProcessId());
    WinHandle mapping(CreateFileMappingW(INVALID_HANDLE_VALUE,nullptr,PAGE_READWRITE,0,sizeof(SharedMapping),name.c_str()));CHECK(mapping);
    auto* view=static_cast<SharedMapping*>(MapViewOfFile(mapping.get(),FILE_MAP_ALL_ACCESS,0,0,sizeof(SharedMapping)));CHECK(view);
    c.flags=ConfigDisabled;view->config=c;CHECK(ReadSharedConfig(GetCurrentProcessId(),received)==ConfigError::None);CHECK(received.Disabled());
    CHECK(argc==2);
    WinHandle ready(CreateEventW(nullptr,TRUE,FALSE,ObjectName(L"Ready",GetCurrentProcessId()).c_str()));CHECK(ready);
    HMODULE dll=LoadLibraryW(std::filesystem::path(argv[1]).c_str());CHECK(dll);
    CHECK(WaitForSingleObject(ready.get(),10000)==WAIT_OBJECT_0);
    CHECK(view->status==static_cast<LONG>(RuntimeStatus::ValidationFailed));CHECK(view->enabled_mask==0);
    WinHandle stop(OpenEventW(EVENT_MODIFY_STATE,FALSE,ObjectName(L"Stop",GetCurrentProcessId()).c_str()));CHECK(stop);CHECK(SetEvent(stop.get()));
    UnmapViewOfFile(view);FreeLibrary(dll);
#endif
    std::cout << "Config validation and fail-closed lifecycle passed\n";
}
