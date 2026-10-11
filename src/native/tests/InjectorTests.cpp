#include "Test.h"
#include "../loader/Injector.h"
#include "../profiler/ProfilerRuntime.h"
#include "../common/SharedConfig.h"
#include <thread>
#include <sstream>
#ifdef _WIN32
#include "../common/WinHandle.h"
#endif
using namespace vic3;
int main(int argc,char** argv) {
    (void)argc;(void)argv;
    // Diagnostics must distinguish validation rejection from an OS API failure.
    ModuleResolutionDiagnostics detail;
    detail.stage=ModuleResolutionStage::RemoteProtection;
    detail.owner_path=LR"(C:\Windows\System32\KERNELBASE.dll)";
    detail.local_size=4202496;detail.remote_size=4202496;
    detail.remote_protection=64;detail.remote_state=4096;
    std::wostringstream diagnostic_log;
    WriteModuleResolutionDiagnostics(diagnostic_log,detail);
    CHECK(diagnostic_log.str().find(L"stage=remote_protection")!=std::wstring::npos);
    CHECK(diagnostic_log.str().find(L"win32_error=0")!=std::wstring::npos);
    CHECK(diagnostic_log.str().find(L"remote_protection=64")!=std::wstring::npos);
    CHECK(diagnostic_log.str().find(L"4202496")!=std::wstring::npos);
    detail.stage=ModuleResolutionStage::Snapshot;detail.win32_error=87;
    std::wostringstream failed_api_log;WriteModuleResolutionDiagnostics(failed_api_log,detail);
    CHECK(failed_api_log.str().find(L"stage=snapshot")!=std::wstring::npos);
    CHECK(failed_api_log.str().find(L"win32_error=87")!=std::wstring::npos);
    CHECK(StopResult(RuntimeStatus::Stopped)==0);
    CHECK(StopResult(RuntimeStatus::StopFailed)!=0);CHECK(StopResult(RuntimeStatus::TraceFailed)!=0);CHECK(StopResult(RuntimeStatus::Pending)!=0);
    CHECK(!ParseLoaderArgs({}));CHECK(!ParseLoaderArgs({L"--pid",L"0"}));CHECK(!ParseLoaderArgs({L"--pid",L"-1"}));CHECK(!ParseLoaderArgs({L"--pid",L"4294967296"}));CHECK(!ParseLoaderArgs({L"--pid",L"12x"}));
    auto args=ParseLoaderArgs({L"--pid",L"123",L"--disabled",L"--targets",L"investment,employment"});CHECK(args && args.value.pid==123 && args.value.disabled && args.value.target_mask==5);
    CHECK(!ParseLoaderArgs({L"--pid",L"123",L"--targets",L"investment,investment"}));CHECK(!ParseLoaderArgs({L"--pid",L"123",L"--targets",L"ai"}));CHECK(!ParseLoaderArgs({L"--pid",L"123",L"--stop",L"--disabled"}));CHECK(!ParseLoaderArgs({L"--pid",L"123",L"--pid",L"124"}));
#ifdef _WIN32
    // Exercise the actual stop subscriber with real named IPC. Producer errors are never success.
    for(auto terminal:{RuntimeStatus::Stopped,RuntimeStatus::StopFailed,RuntimeStatus::TraceFailed,RuntimeStatus::Pending,RuntimeStatus::Ready}) {
        const DWORD self=GetCurrentProcessId();
        WinHandle stop_event(CreateEventW(nullptr,TRUE,FALSE,ObjectName(L"Stop",self).c_str()));
        WinHandle stopped_event(CreateEventW(nullptr,TRUE,FALSE,ObjectName(L"Stopped",self).c_str()));
        WinHandle config(CreateFileMappingW(INVALID_HANDLE_VALUE,nullptr,PAGE_READWRITE,0,sizeof(SharedMapping),ObjectName(L"Config",self).c_str()));CHECK(config);
        MappedView view(MapViewOfFile(config.get(),FILE_MAP_ALL_ACCESS,0,0,sizeof(SharedMapping)));CHECK(view.get());
        auto* shared=static_cast<SharedMapping*>(view.get());shared->status=static_cast<LONG>(RuntimeStatus::Ready);
        std::thread controller([&]{CHECK(WaitForSingleObject(stop_event.get(),5000)==WAIT_OBJECT_0);InterlockedExchange(&shared->status,static_cast<LONG>(terminal));SetEvent(stopped_event.get());});
        CHECK(StopProfilerSession(self,5000)==terminal);CHECK(StopResult(terminal)==(terminal==RuntimeStatus::Stopped?0:1));controller.join();
    }
    // Missing IPC and a stop signal without completion are never a success.
    const DWORD self=GetCurrentProcessId();
    CHECK(StopProfilerSession(self,0)==RuntimeStatus::StopFailed);
    {
        WinHandle stop_event(CreateEventW(nullptr,TRUE,FALSE,ObjectName(L"Stop",self).c_str()));CHECK(stop_event);
        WinHandle stopped_event(CreateEventW(nullptr,TRUE,FALSE,ObjectName(L"Stopped",self).c_str()));CHECK(stopped_event);
        CHECK(StopProfilerSession(self,0)==RuntimeStatus::StopFailed); // mapping is absent
        CHECK(WaitForSingleObject(stop_event.get(),0)==WAIT_TIMEOUT); // do not signal an incomplete session
        WinHandle config(CreateFileMappingW(INVALID_HANDLE_VALUE,nullptr,PAGE_READWRITE,0,sizeof(SharedMapping),ObjectName(L"Config",self).c_str()));CHECK(config);
        MappedView view(MapViewOfFile(config.get(),FILE_MAP_ALL_ACCESS,0,0,sizeof(SharedMapping)));CHECK(view.get());
        auto* shared=static_cast<SharedMapping*>(view.get());shared->status=static_cast<LONG>(RuntimeStatus::Ready);
        CHECK(StopProfilerSession(self,0)==RuntimeStatus::StopFailed);
        CHECK(WaitForSingleObject(stop_event.get(),0)==WAIT_OBJECT_0);
        CHECK(WaitForSingleObject(stopped_event.get(),0)==WAIT_TIMEOUT);
        InterlockedExchange(&shared->status,static_cast<LONG>(RuntimeStatus::Stopped));CHECK(SetEvent(stopped_event.get()));
        CHECK(StopProfilerSession(self,0)==RuntimeStatus::Stopped);
    }
    CHECK(argc==4);
    std::wstring command=L"\""+std::filesystem::path(argv[1]).wstring()+L"\"";STARTUPINFOW startup{};startup.cb=sizeof(startup);PROCESS_INFORMATION process{};
    CHECK(CreateProcessW(nullptr,command.data(),nullptr,nullptr,FALSE,0,nullptr,nullptr,&startup,&process));WinHandle host(process.hProcess),host_thread(process.hThread);
    const DWORD pid=process.dwProcessId;
    WinHandle host_ready(CreateEventW(nullptr,TRUE,FALSE,(L"Local\\Vic3NativeInjectorHostReady-"+std::to_wstring(pid)).c_str()));CHECK(host_ready);CHECK(WaitForSingleObject(host_ready.get(),10000)==WAIT_OBJECT_0);
    WinHandle probe(CreateEventW(nullptr,TRUE,FALSE,(L"Local\\Vic3NativeInjectionProbe-"+std::to_wstring(pid)).c_str()));CHECK(probe);
    std::wstring loader=L"\""+std::filesystem::path(argv[3]).wstring()+L"\" --pid "+std::to_wstring(pid)+L" --dll \""+std::filesystem::path(argv[2]).wstring()+L"\"";
    PROCESS_INFORMATION rejected{};CHECK(CreateProcessW(nullptr,loader.data(),nullptr,nullptr,FALSE,0,nullptr,nullptr,&startup,&rejected));WinHandle rejected_process(rejected.hProcess),rejected_thread(rejected.hThread);
    CHECK(WaitForSingleObject(rejected_process.get(),10000)==WAIT_OBJECT_0);DWORD exit_code{};CHECK(GetExitCodeProcess(rejected_process.get(),&exit_code));CHECK(exit_code!=0);CHECK(WaitForSingleObject(probe.get(),0)==WAIT_TIMEOUT);
    // Fail before remote allocation/write: nonexistent PID and invalid query handle.
    ModuleResolutionDiagnostics rejected_resolution;
    CHECK(InjectLibraryForValidatedProcess(host.get(),0xffffffffu,std::filesystem::absolute(argv[2]),&rejected_resolution)==InjectionError::ModuleResolution);
    CHECK(rejected_resolution.stage==ModuleResolutionStage::Snapshot && rejected_resolution.win32_error!=0);
    CHECK(WaitForSingleObject(probe.get(),0)==WAIT_TIMEOUT);
    CHECK(InjectLibraryForValidatedProcess(nullptr,pid,std::filesystem::absolute(argv[2]),&rejected_resolution)==InjectionError::ModuleResolution);
    CHECK(rejected_resolution.stage==ModuleResolutionStage::RemoteQuery && rejected_resolution.win32_error==ERROR_INVALID_HANDLE);
    CHECK(WaitForSingleObject(probe.get(),0)==WAIT_TIMEOUT);
    ModuleResolutionDiagnostics success_resolution;
    CHECK(InjectLibraryForValidatedProcess(host.get(),pid,std::filesystem::absolute(argv[2]),&success_resolution)==InjectionError::None);
    CHECK(success_resolution.stage==ModuleResolutionStage::None && success_resolution.win32_error==0);CHECK(WaitForSingleObject(probe.get(),10000)==WAIT_OBJECT_0);
    WinHandle stop(OpenEventW(EVENT_MODIFY_STATE,FALSE,(L"Local\\Vic3NativeInjectorHostStop-"+std::to_wstring(pid)).c_str()));CHECK(stop);CHECK(SetEvent(stop.get()));CHECK(WaitForSingleObject(host.get(),10000)==WAIT_OBJECT_0);
#endif
    std::cout << "Explicit PID/options and wrong-process gate passed\n";
}
