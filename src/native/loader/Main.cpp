#include "Injector.h"
#include "../generated/targets_1_14_5.inc"
#include "../common/SharedConfig.h"
#include "../common/WinHandle.h"
#include "../profiler/ProfilerRuntime.h"
#include <iostream>
#include <cstring>
using namespace vic3;
int wmain(int argc,wchar_t** argv) {
    try {
        std::vector<std::wstring> arguments(argv+1,argv+argc);auto parsed=ParseLoaderArgs(arguments);
        if(!parsed){std::wcerr<<L"Usage: Vic3OptimizationLoader --pid PID [--disabled] [--dll PATH] [--output TRACE] [--targets investment,migration,employment] [--allow-partial-targets]\n       Vic3OptimizationLoader --stop --pid PID\n";return 2;}
        auto args=parsed.value;
        // Stop also requires an explicitly selected exact Victoria build; it is not a generic process tool.
        const DWORD rights=args.stop?PROCESS_QUERY_LIMITED_INFORMATION:(PROCESS_QUERY_INFORMATION|PROCESS_CREATE_THREAD|PROCESS_VM_OPERATION|PROCESS_VM_WRITE|PROCESS_VM_READ);
        WinHandle process(OpenProcess(rights,FALSE,args.pid));if(!process){std::wcerr<<L"Cannot open explicit PID. No privileges are changed.\n";return 3;}
        const auto image=ProcessImagePath(process.get());
        WinHandle executable(CreateFileW(image.c_str(),GENERIC_READ,FILE_SHARE_READ,nullptr,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,nullptr));if(!executable)return 3;
        const auto gate=ValidateVictoriaProcess(process.get(),image);
        if(gate!=InjectionError::None){std::wcerr<<L"Unsupported process/build; no remote write or injection. Gate code: "<<static_cast<int>(gate)<<L"\n";return 4;}
        if(args.stop) {
            WinHandle stop(OpenEventW(EVENT_MODIFY_STATE,FALSE,ObjectName(L"Stop",args.pid).c_str()));
            WinHandle stopped(OpenEventW(SYNCHRONIZE,FALSE,ObjectName(L"Stopped",args.pid).c_str()));
            if(!stop || !stopped){std::wcerr<<L"No active profiler session.\n";return 5;}
            if(!SetEvent(stop.get()) || WaitForSingleObject(stopped.get(),35000)!=WAIT_OBJECT_0){std::wcerr<<L"Stop/finalization not confirmed. Do not reattach this process.\n";return 5;}
            std::wcout<<L"Profiler stop event acknowledged. DLL remains loaded and inert.\n";return 0;
        }
        std::wstring own(32768,L'\0');DWORD own_length=GetModuleFileNameW(nullptr,own.data(),static_cast<DWORD>(own.size()));if(!own_length || own_length>=own.size())return 3;own.resize(own_length);
        if(args.dll.empty())args.dll=std::filesystem::path(own).parent_path()/L"Vic3OptimizationProfiler.dll";
        args.dll=std::filesystem::absolute(args.dll);
        if(_wcsicmp(args.dll.filename().c_str(),L"Vic3OptimizationProfiler.dll")!=0 || !std::filesystem::is_regular_file(args.dll)){std::wcerr<<L"Select the built Vic3OptimizationProfiler.dll.\n";return 6;}
        if(args.output.empty())args.output=L"vic3-profiler-"+std::to_wstring(args.pid)+L"-"+std::to_wstring(GetTickCount64())+L".v3pf";
        const auto output=std::filesystem::absolute(args.output).wstring();SharedConfig config;config.flags=(args.disabled?ConfigDisabled:0)|(args.partial?ConfigPartialTargets:0);config.target_mask=args.target_mask;
        if(output.size()>=std::size(config.output))return 2;
        for(size_t i=0;i<output.size();++i)config.output[i]=static_cast<char16_t>(output[i]);
        if(ValidateConfig(config)!=ConfigError::None || std::filesystem::exists(output))return 2;
        WinHandle existing(OpenEventW(SYNCHRONIZE,FALSE,ObjectName(L"Stop",args.pid).c_str()));if(existing){std::wcerr<<L"Profiler already loaded; restart the game for another capture.\n";return 7;}
        WinHandle mapping(CreateFileMappingW(INVALID_HANDLE_VALUE,nullptr,PAGE_READWRITE,0,sizeof(SharedMapping),ObjectName(L"Config",args.pid).c_str()));const DWORD mapping_error=GetLastError();
        if(!mapping || mapping_error==ERROR_ALREADY_EXISTS)return 7;
        MappedView view(MapViewOfFile(mapping.get(),FILE_MAP_ALL_ACCESS,0,0,sizeof(SharedMapping)));if(!view.get())return 7;
        auto* shared=static_cast<SharedMapping*>(view.get());std::memset(shared,0,sizeof(SharedMapping));shared->config=config;
        WinHandle ready(CreateEventW(nullptr,TRUE,FALSE,ObjectName(L"Ready",args.pid).c_str()));const DWORD ready_error=GetLastError();if(!ready || ready_error==ERROR_ALREADY_EXISTS)return 7;
        auto injection=InjectLibraryForValidatedProcess(process.get(),args.pid,args.dll);
        if(injection!=InjectionError::None){std::wcerr<<L"Attach failed (no retry), code "<<static_cast<int>(injection)<<L"\n";return 8;}
        if(WaitForSingleObject(ready.get(),30000)!=WAIT_OBJECT_0){std::wcerr<<L"Profiler ready timed out. Do not retry; restart the game.\n";return 9;}
        for(size_t i=0;i<3;++i)std::cout<<generated::kTargets[i].runtime_task<<" validation="<<shared->validation_errors[i]<<'\n';
        if(shared->status!=static_cast<LONG>(RuntimeStatus::Ready)){std::wcerr<<L"DLL rejected initialization, status "<<shared->status<<L"\n";return 10;}
        std::wcout<<L"Profiler ready; enabled mask="<<shared->enabled_mask<<L"; output="<<output<<L"\n";return 0;
    }catch(const ValidationFailure& e){std::cerr<<"Validation failed, code "<<static_cast<int>(e.code)<<'\n';return 11;}
    catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 12;}
}
