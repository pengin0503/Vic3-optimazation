#include "ProfilerRuntime.h"
#include "TickTaskHooks.h"
#include "../common/SharedConfig.h"
#include "../common/WinHandle.h"
#include "../common/Sha256.h"
#include "../common/TargetResolver.h"
#include "../common/TraceWriter.h"
#include <memory>
#include <cstring>
namespace vic3 {
ConfigError ReadSharedConfig(DWORD pid,SharedConfig& config) {
    WinHandle mapping(OpenFileMappingW(FILE_MAP_READ,FALSE,ObjectName(L"Config",pid).c_str()));
    if(!mapping)return ConfigError::MissingMapping;
    MappedView view(MapViewOfFile(mapping.get(),FILE_MAP_READ,0,0,sizeof(SharedMapping)));if(!view.get())return ConfigError::Size;
    std::memcpy(&config,&static_cast<SharedMapping*>(view.get())->config,sizeof(config));return ValidateConfig(config);
}
static uint32_t CurrentThread() noexcept {return GetCurrentThreadId();}
static uint64_t CurrentQpc() noexcept {LARGE_INTEGER value{};return QueryPerformanceCounter(&value)?static_cast<uint64_t>(value.QuadPart):0;}
static TickTaskHooks* retained_hooks{};
static EventBufferPool* retained_pool{};
static MinHookBackend* retained_backend{};
static HANDLE stop_event{},stopped_event{}; // Remain available for the inert, pinned DLL's lifetime.
void RunProfilerRuntime(void* module) noexcept {
    try {
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
        uint32_t validated=0;std::array<uintptr_t,3> resolved{};
        for(size_t i=0;i<3;++i)if(config.target_mask&(1u<<i)) {
            auto result=ResolveTarget(image.value,generated::kTargets[i]);
            if(shared)shared->validation_errors[i]=static_cast<uint32_t>(result.error);
            if(result){validated|=(1u<<i);resolved[i]=result.value;}
        }
        const uint32_t arm_mask=config.Disabled()?0:validated;
        if(!config.Disabled() && ((!validated) || (!(config.flags&ConfigPartialTargets) && validated!=config.target_mask))){publish(RuntimeStatus::ValidationFailed);return;}
        auto pool=std::make_unique<EventBufferPool>();
        LARGE_INTEGER frequency{},start{};if(!QueryPerformanceFrequency(&frequency)||frequency.QuadPart<=0||!QueryPerformanceCounter(&start)){publish(RuntimeStatus::TraceFailed);return;}
        std::wstring output;for(char16_t c:config.output){if(!c)break;output.push_back(static_cast<wchar_t>(c));}
        TraceWriter writer;writer.Open(output,RuntimeMetadata(arm_mask,config.Disabled()),static_cast<uint64_t>(frequency.QuadPart),static_cast<uint64_t>(start.QuadPart),generated::kTargetTableSha256);
        // Signature failures are diagnostics only in disabled mode; zero hooks exist.
        Event diagnostic{static_cast<uint64_t>(start.QuadPart),GetCurrentThreadId(),6,0,0,0};diagnostic.counter_id=3;diagnostic.value=static_cast<int64_t>(config.target_mask&~validated);writer.Write(EncodeEvent(diagnostic));
        std::array<void*,3> hook_addresses{};size_t address_count=0;
        if(arm_mask) {
            retained_pool=pool.release();
            retained_hooks=new TickTaskHooks(*retained_pool,CurrentThread,CurrentQpc);
            retained_backend=new MinHookBackend;
            if(!retained_backend->Initialize()){writer.Finalize(0);publish(RuntimeStatus::HookFailed);return;}
            for(size_t i=0;i<3;++i)if(arm_mask&(1u<<i)) {
                void* original=nullptr;void* address=reinterpret_cast<void*>(resolved[i]);
                if(!retained_backend->Create(address,retained_hooks->Detour(i),&original)) {
                    for(size_t j=0;j<address_count;++j)retained_backend->Remove(hook_addresses[j]);
                    retained_backend->Shutdown();writer.Finalize(0);publish(RuntimeStatus::HookFailed);return;
                }
                retained_hooks->SetOriginal(i,reinterpret_cast<TickTaskTailFn>(original));hook_addresses[address_count++]=address;
            }
            retained_hooks->StartRecording();
            if(!retained_backend->Enable(std::span(hook_addresses).first(address_count))){retained_hooks->StopRecording();retained_backend->Disable(std::span(hook_addresses).first(address_count));writer.Finalize(retained_pool->Dropped());publish(RuntimeStatus::HookFailed);return;}
        }
        EventBufferPool& active_pool=arm_mask?*retained_pool:*pool;
        if(shared)shared->enabled_mask=arm_mask;
        publish(RuntimeStatus::Ready);
        bool healthy=true;
        while(WaitForSingleObject(stop_event,10)==WAIT_TIMEOUT)if(!writer.Drain(active_pool)){healthy=false;break;}
        if(arm_mask) {
            retained_hooks->StopRecording();
            if(!retained_backend->Disable(std::span(hook_addresses).first(address_count))){publish(RuntimeStatus::StopFailed);return;}
            // Only the profiler control thread waits. Preserve trampolines and pool until process exit.
            const ULONGLONG deadline=GetTickCount64()+30000;
            while(retained_hooks->Active()!=0 && GetTickCount64()<deadline){writer.Drain(active_pool);Sleep(1);}
            if(retained_hooks->Active()!=0){writer.Drain(active_pool);writer.Finalize(active_pool.Dropped());publish(RuntimeStatus::StopFailed);SetEvent(stopped_event);return;}
        }
        writer.Drain(active_pool);
        Event drops{CurrentQpc(),GetCurrentThreadId(),6,0,1,0};drops.counter_id=1;drops.value=static_cast<int64_t>(active_pool.Dropped());writer.Write(EncodeEvent(drops));
        drops.sequence=2;drops.counter_id=4;drops.value=static_cast<int64_t>(active_pool.Exhaustions());writer.Write(EncodeEvent(drops));
        healthy=writer.Finalize(active_pool.Dropped())&&healthy;
        if(shared)shared->enabled_mask=0;
        publish(healthy?RuntimeStatus::Stopped:RuntimeStatus::TraceFailed);SetEvent(stopped_event);
    } catch(const ValidationFailure&) {publish(RuntimeStatus::ValidationFailed);}catch(...) {
        if(retained_hooks)retained_hooks->StopRecording();
        // A no-throw writer failure cannot free game trampolines; retained storage is process-lifetime.
        publish(RuntimeStatus::TraceFailed);
    }
    } catch(...) {
        // Even allocation of the first object name must not terminate the game.
        // Initialization did not reach ready; the loader reports a timeout and never retries.
    }
}
}
