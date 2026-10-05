#include "Test.h"
#include "../common/SharedConfig.h"
#include "../profiler/ProfilerRuntime.h"
#include <algorithm>
#ifdef _WIN32
#include "../common/WinHandle.h"
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
    SharedConfig received;CHECK(ReadSharedConfig(GetCurrentProcessId(),received)==ConfigError::MissingMapping);
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
