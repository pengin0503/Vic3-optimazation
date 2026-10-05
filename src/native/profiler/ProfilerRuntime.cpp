#include "ProfilerRuntime.h"
#include "../common/SharedConfig.h"
#include "../common/WinHandle.h"
#include "../common/Sha256.h"
#include "../common/TargetResolver.h"
#include "../common/TraceWriter.h"
#include <memory>
#include <cstring>
namespace vic3 {
ConfigError ReadSharedConfig(DWORD pid,SharedConfig& config) noexcept {
    WinHandle mapping(OpenFileMappingW(FILE_MAP_READ,FALSE,ObjectName(L"Config",pid).c_str()));
    if(!mapping)return ConfigError::MissingMapping;
    MappedView view(MapViewOfFile(mapping.get(),FILE_MAP_READ,0,0,sizeof(SharedMapping)));if(!view.get())return ConfigError::Size;
    std::memcpy(&config,&static_cast<SharedMapping*>(view.get())->config,sizeof(config));return ValidateConfig(config);
}
static HANDLE stop_event{},stopped_event{}; // Remain available for the inert, pinned DLL's lifetime.
void RunProfilerRuntime(void* module) noexcept {
    HMODULE pinned{};
    if(!GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS|GET_MODULE_HANDLE_EX_FLAG_PIN,reinterpret_cast<const wchar_t*>(module),&pinned))return;
    const DWORD pid=GetCurrentProcessId();
    WinHandle ready(OpenEventW(EVENT_MODIFY_STATE,FALSE,ObjectName(L"Ready",pid).c_str()));
    stop_event=CreateEventW(nullptr,TRUE,FALSE,ObjectName(L"Stop",pid).c_str());
    stopped_event=CreateEventW(nullptr,TRUE,FALSE,ObjectName(L"Stopped",pid).c_str());
    WinHandle mapping(OpenFileMappingW(FILE_MAP_ALL_ACCESS,FALSE,ObjectName(L"Config",pid).c_str()));
    MappedView view(mapping?MapViewOfFile(mapping.get(),FILE_MAP_ALL_ACCESS,0,0,sizeof(SharedMapping)):nullptr);
    auto* shared=static_cast<SharedMapping*>(view.get());
    const auto publish=[&](RuntimeStatus status){if(shared)InterlockedExchange(&shared->status,static_cast<LONG>(status));if(ready)SetEvent(ready.get());};
    try {
        SharedConfig config;
        if(!stop_event || !stopped_event || ReadSharedConfig(pid,config)!=ConfigError::None){publish(RuntimeStatus::ConfigRejected);return;}
        std::wstring path(32768,L'\0');const DWORD length=GetModuleFileNameW(nullptr,path.data(),static_cast<DWORD>(path.size()));
        if(!length || length>=path.size()){publish(RuntimeStatus::ValidationFailed);return;}path.resize(length);
        if(!IsSupportedBuild(Sha256File(path))){publish(RuntimeStatus::ValidationFailed);return;}
        auto image=PeImage::FromModule(GetModuleHandleW(nullptr));if(!image){publish(RuntimeStatus::ValidationFailed);return;}
        uint32_t validated=0;
        for(size_t i=0;i<3;++i)if(config.target_mask&(1u<<i)) {
            auto result=ResolveTarget(image.value,generated::kTargets[i]);
            if(shared)shared->validation_errors[i]=static_cast<uint32_t>(result.error);
            if(result)validated|=(1u<<i);
        }
        if(!config.Disabled()){publish(RuntimeStatus::HookFailed);return;} // Task 5 intentionally supports no-hook mode first.
        auto pool=std::make_unique<EventBufferPool>();
        LARGE_INTEGER frequency{},start{};if(!QueryPerformanceFrequency(&frequency)||frequency.QuadPart<=0||!QueryPerformanceCounter(&start)){publish(RuntimeStatus::TraceFailed);return;}
        std::wstring output;for(char16_t c:config.output){if(!c)break;output.push_back(static_cast<wchar_t>(c));}
        TraceWriter writer;writer.Open(output,RuntimeMetadata(0,true),static_cast<uint64_t>(frequency.QuadPart),static_cast<uint64_t>(start.QuadPart),generated::kTargetTableSha256);
        // Signature failures are diagnostics only in disabled mode; zero hooks exist.
        Event diagnostic{static_cast<uint64_t>(start.QuadPart),GetCurrentThreadId(),6,0,0,0};diagnostic.counter_id=3;diagnostic.value=static_cast<int64_t>(config.target_mask&~validated);writer.Write(EncodeEvent(diagnostic));
        if(shared)shared->enabled_mask=0;publish(RuntimeStatus::Ready);
        bool healthy=true;
        while(WaitForSingleObject(stop_event,10)==WAIT_TIMEOUT)if(!writer.Drain(*pool)){healthy=false;break;}
        writer.Drain(*pool);healthy=writer.Finalize(pool->Dropped())&&healthy;
        publish(healthy?RuntimeStatus::Stopped:RuntimeStatus::TraceFailed);SetEvent(stopped_event);
    } catch(const ValidationFailure&) {publish(RuntimeStatus::ValidationFailed);}catch(...) {publish(RuntimeStatus::TraceFailed);}
}
}
