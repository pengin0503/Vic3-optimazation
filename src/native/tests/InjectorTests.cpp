#include "Test.h"
#include "../loader/Injector.h"
#ifdef _WIN32
#include "../common/WinHandle.h"
#endif
using namespace vic3;
int main(int argc,char** argv) {
    (void)argc;(void)argv;
    CHECK(!ParseLoaderArgs({}));CHECK(!ParseLoaderArgs({L"--pid",L"0"}));CHECK(!ParseLoaderArgs({L"--pid",L"-1"}));CHECK(!ParseLoaderArgs({L"--pid",L"4294967296"}));CHECK(!ParseLoaderArgs({L"--pid",L"12x"}));
    auto args=ParseLoaderArgs({L"--pid",L"123",L"--disabled",L"--targets",L"investment,employment"});CHECK(args && args.value.pid==123 && args.value.disabled && args.value.target_mask==5);
    CHECK(!ParseLoaderArgs({L"--pid",L"123",L"--targets",L"investment,investment"}));CHECK(!ParseLoaderArgs({L"--pid",L"123",L"--targets",L"ai"}));CHECK(!ParseLoaderArgs({L"--pid",L"123",L"--stop",L"--disabled"}));CHECK(!ParseLoaderArgs({L"--pid",L"123",L"--pid",L"124"}));
#ifdef _WIN32
    CHECK(argc==4);
    std::wstring command=L"\""+std::filesystem::path(argv[1]).wstring()+L"\"";STARTUPINFOW startup{};startup.cb=sizeof(startup);PROCESS_INFORMATION process{};
    CHECK(CreateProcessW(nullptr,command.data(),nullptr,nullptr,FALSE,0,nullptr,nullptr,&startup,&process));WinHandle host(process.hProcess),host_thread(process.hThread);
    const DWORD pid=process.dwProcessId;
    WinHandle host_ready(CreateEventW(nullptr,TRUE,FALSE,(L"Local\\Vic3NativeInjectorHostReady-"+std::to_wstring(pid)).c_str()));CHECK(host_ready);CHECK(WaitForSingleObject(host_ready.get(),10000)==WAIT_OBJECT_0);
    WinHandle probe(CreateEventW(nullptr,TRUE,FALSE,(L"Local\\Vic3NativeInjectionProbe-"+std::to_wstring(pid)).c_str()));CHECK(probe);
    std::wstring loader=L"\""+std::filesystem::path(argv[3]).wstring()+L"\" --pid "+std::to_wstring(pid)+L" --dll \""+std::filesystem::path(argv[2]).wstring()+L"\"";
    PROCESS_INFORMATION rejected{};CHECK(CreateProcessW(nullptr,loader.data(),nullptr,nullptr,FALSE,0,nullptr,nullptr,&startup,&rejected));WinHandle rejected_process(rejected.hProcess),rejected_thread(rejected.hThread);
    CHECK(WaitForSingleObject(rejected_process.get(),10000)==WAIT_OBJECT_0);DWORD exit_code{};CHECK(GetExitCodeProcess(rejected_process.get(),&exit_code));CHECK(exit_code!=0);CHECK(WaitForSingleObject(probe.get(),0)==WAIT_TIMEOUT);
    CHECK(InjectLibraryForValidatedProcess(host.get(),pid,std::filesystem::absolute(argv[2]))==InjectionError::None);CHECK(WaitForSingleObject(probe.get(),10000)==WAIT_OBJECT_0);
    WinHandle stop(OpenEventW(EVENT_MODIFY_STATE,FALSE,(L"Local\\Vic3NativeInjectorHostStop-"+std::to_wstring(pid)).c_str()));CHECK(stop);CHECK(SetEvent(stop.get()));CHECK(WaitForSingleObject(host.get(),10000)==WAIT_OBJECT_0);
#endif
    std::cout << "Explicit PID/options and wrong-process gate passed\n";
}
