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
    CHECK(ParseLoaderArgs({L"--pid",L"123",L"--diagnose-loadlibrary"}));
    CHECK(ParseLoaderArgs({L"--diagnose-loadlibrary",L"--pid",L"123"}));
    for(const auto& option:{L"--disabled",L"--stop",L"--allow-partial-targets"})
        CHECK(!ParseLoaderArgs({L"--pid",L"123",L"--diagnose-loadlibrary",option}));
    for(const auto& option:{L"--dll",L"--output",L"--targets"})
        CHECK(!ParseLoaderArgs({L"--pid",L"123",L"--diagnose-loadlibrary",option,L"anything"}));
    // Missing-value options must not swallow a safety mode and turn it into attach.
    CHECK(!ParseLoaderArgs({L"--output",L"--diagnose-loadlibrary",L"--pid",L"123"}));
    CHECK(!ParseLoaderArgs({L"--pid",L"123",L"--output",L"--diagnose-loadlibrary"}));
    for(const auto& value:{L"--diagnose-loadlibrary",L"--stop",L"--disabled",L"--allow-partial-targets",L"--pid",L"--dll",L"--output",L"--targets"})
        for(const auto& option:{L"--pid",L"--dll",L"--output",L"--targets"})
            CHECK(!ParseLoaderArgs({L"--pid",L"123",option,value}));
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
    ModuleResolutionDiagnostics identity_detail;
    CHECK(!DiagnoseLoadLibraryForValidatedProcess(host.get(),GetCurrentProcessId(),identity_detail));
    CHECK(identity_detail.stage==ModuleResolutionStage::ProcessIdentity && identity_detail.win32_error==0);
    CHECK(identity_detail.requested_pid==GetCurrentProcessId() && identity_detail.handle_pid==pid);
    auto diagnosis_args=ParseLoaderArgs({L"--pid",std::to_wstring(pid),L"--diagnose-loadlibrary"});CHECK(diagnosis_args);
    CHECK(LoaderProcessRights(diagnosis_args.value)==(PROCESS_QUERY_INFORMATION|PROCESS_VM_READ));
    WinHandle read_only(OpenProcess(LoaderProcessRights(diagnosis_args.value),FALSE,pid));CHECK(read_only);
    CHECK(DiagnoseLoadLibraryForValidatedProcess(read_only.get(),pid,identity_detail));
    CHECK(identity_detail.probe_available && identity_detail.requested_pid==pid && identity_detail.handle_pid==pid);
    CHECK(identity_detail.process_start_filetime!=0);
    FILETIME created{},exited{},kernel{},user{};CHECK(GetProcessTimes(host.get(),&created,&exited,&kernel,&user));
    CHECK(identity_detail.process_start_filetime==((static_cast<uint64_t>(created.dwHighDateTime)<<32)|created.dwLowDateTime));
    CHECK(WaitForSingleObject(probe.get(),0)==WAIT_TIMEOUT);
    std::wstring loader=L"\""+std::filesystem::path(argv[3]).wstring()+L"\" --pid "+std::to_wstring(pid)+L" --dll \""+std::filesystem::path(argv[2]).wstring()+L"\"";
    PROCESS_INFORMATION rejected{};CHECK(CreateProcessW(nullptr,loader.data(),nullptr,nullptr,FALSE,0,nullptr,nullptr,&startup,&rejected));WinHandle rejected_process(rejected.hProcess),rejected_thread(rejected.hThread);
    CHECK(WaitForSingleObject(rejected_process.get(),10000)==WAIT_OBJECT_0);DWORD exit_code{};CHECK(GetExitCodeProcess(rejected_process.get(),&exit_code));CHECK(exit_code!=0);CHECK(WaitForSingleObject(probe.get(),0)==WAIT_TIMEOUT);
    // Fail before remote allocation/write: nonexistent PID and invalid query handle.
    ModuleResolutionDiagnostics rejected_resolution;
    CHECK(InjectLibraryForValidatedProcess(host.get(),0xffffffffu,std::filesystem::absolute(argv[2]),&rejected_resolution)==InjectionError::ModuleResolution);
    CHECK(rejected_resolution.stage==ModuleResolutionStage::ProcessIdentity && rejected_resolution.win32_error==0);
    CHECK(WaitForSingleObject(probe.get(),0)==WAIT_TIMEOUT);
    CHECK(InjectLibraryForValidatedProcess(nullptr,pid,std::filesystem::absolute(argv[2]),&rejected_resolution)==InjectionError::ModuleResolution);
    CHECK(rejected_resolution.stage==ModuleResolutionStage::ProcessIdentity && rejected_resolution.win32_error==ERROR_INVALID_HANDLE);
    CHECK(WaitForSingleObject(probe.get(),0)==WAIT_TIMEOUT);
    ModuleResolutionDiagnostics success_resolution;
    CHECK(InjectLibraryForValidatedProcess(host.get(),pid,std::filesystem::absolute(argv[2]),&success_resolution)==InjectionError::None);
    CHECK(success_resolution.stage==ModuleResolutionStage::None && success_resolution.win32_error==0);CHECK(WaitForSingleObject(probe.get(),10000)==WAIT_OBJECT_0);
    WinHandle stop(OpenEventW(EVENT_MODIFY_STATE,FALSE,(L"Local\\Vic3NativeInjectorHostStop-"+std::to_wstring(pid)).c_str()));CHECK(stop);CHECK(SetEvent(stop.get()));CHECK(WaitForSingleObject(host.get(),10000)==WAIT_OBJECT_0);
    // A separate controlled child installs its own synthetic E9 entry.
    // No Steam DLL, game process or third-party hook is modified by this test.
    std::wstring detour_command=command+L" --synthetic-detour";PROCESS_INFORMATION detoured{};
    CHECK(CreateProcessW(nullptr,detour_command.data(),nullptr,nullptr,FALSE,0,nullptr,nullptr,&startup,&detoured));
    WinHandle detour_host(detoured.hProcess),detour_thread(detoured.hThread);const DWORD detour_pid=detoured.dwProcessId;
    WinHandle detour_ready(CreateEventW(nullptr,TRUE,FALSE,(L"Local\\Vic3NativeInjectorHostReady-"+std::to_wstring(detour_pid)).c_str()));CHECK(detour_ready);
    CHECK(WaitForSingleObject(detour_ready.get(),10000)==WAIT_OBJECT_0);
    WinHandle detour_probe(CreateEventW(nullptr,TRUE,FALSE,(L"Local\\Vic3NativeInjectionProbe-"+std::to_wstring(detour_pid)).c_str()));CHECK(detour_probe);
    WinHandle detour_read(OpenProcess(PROCESS_QUERY_INFORMATION|PROCESS_VM_READ,FALSE,detour_pid));CHECK(detour_read);
    ModuleResolutionDiagnostics detour_detail;
    CHECK(!DiagnoseLoadLibraryForValidatedProcess(detour_read.get(),detour_pid,detour_detail));
    CHECK(detour_detail.stage==ModuleResolutionStage::ByteMismatch && detour_detail.win32_error==0);
    CHECK(detour_detail.probe_available && detour_detail.remote_bytes[0]==std::byte{0xe9});
    CHECK(detour_detail.remote_entry==RemoteEntryObservation::Rel32Jump && detour_detail.branch_target==detour_detail.remote_address+5);
    CHECK(detour_detail.branch_query_available && detour_detail.branch_query_error==0);
    CHECK(detour_detail.branch_state==MEM_COMMIT && detour_detail.branch_type==MEM_IMAGE);
    CHECK(InjectLibraryForValidatedProcess(detour_host.get(),detour_pid,std::filesystem::absolute(argv[2]),&detour_detail)==InjectionError::ModuleResolution);
    CHECK(detour_detail.stage==ModuleResolutionStage::ByteMismatch);
    CHECK(WaitForSingleObject(detour_probe.get(),0)==WAIT_TIMEOUT);
    std::wstring diagnose_loader=L"\""+std::filesystem::path(argv[3]).wstring()+L"\" --diagnose-loadlibrary --pid "+std::to_wstring(detour_pid);
    PROCESS_INFORMATION rejected_diagnose{};CHECK(CreateProcessW(nullptr,diagnose_loader.data(),nullptr,nullptr,FALSE,0,nullptr,nullptr,&startup,&rejected_diagnose));
    WinHandle diagnose_process(rejected_diagnose.hProcess),diagnose_thread(rejected_diagnose.hThread);
    CHECK(WaitForSingleObject(diagnose_process.get(),10000)==WAIT_OBJECT_0);CHECK(GetExitCodeProcess(diagnose_process.get(),&exit_code));
    CHECK(exit_code==4); // exact Victoria build gate also applies to read-only mode
    CHECK(WaitForSingleObject(detour_probe.get(),0)==WAIT_TIMEOUT);
    WinHandle detour_stop(OpenEventW(EVENT_MODIFY_STATE,FALSE,(L"Local\\Vic3NativeInjectorHostStop-"+std::to_wstring(detour_pid)).c_str()));CHECK(detour_stop);
    CHECK(SetEvent(detour_stop.get()));CHECK(WaitForSingleObject(detour_host.get(),10000)==WAIT_OBJECT_0);
#endif
    std::cout << "Explicit PID/options and wrong-process gate passed\n";
}
