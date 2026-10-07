#include "Injector.h"
#include "../common/WinHandle.h"
#include "../common/SharedConfig.h"
#include "../common/Sha256.h"
#include "../common/PeImage.h"
#include <tlhelp32.h>
#include <array>
#include <cstring>
namespace vic3 {
RuntimeStatus StopProfilerSession(DWORD pid,DWORD timeout_ms) {
    WinHandle stop(OpenEventW(EVENT_MODIFY_STATE,FALSE,ObjectName(L"Stop",pid).c_str()));
    WinHandle stopped(OpenEventW(SYNCHRONIZE,FALSE,ObjectName(L"Stopped",pid).c_str()));
    // Acquire the status mapping before signaling, retaining it even after the control thread exits.
    WinHandle mapping(OpenFileMappingW(FILE_MAP_READ,FALSE,ObjectName(L"Config",pid).c_str()));
    MappedView view(mapping?MapViewOfFile(mapping.get(),FILE_MAP_READ,0,0,sizeof(SharedMapping)):nullptr);
    if(!stop || !stopped || !view.get() || !SetEvent(stop.get()) || WaitForSingleObject(stopped.get(),timeout_ms)!=WAIT_OBJECT_0)return RuntimeStatus::StopFailed;
    return static_cast<RuntimeStatus>(static_cast<SharedMapping*>(view.get())->status);
}
std::filesystem::path ProcessImagePath(HANDLE process) {
    std::wstring path(32768,L'\0');DWORD size=static_cast<DWORD>(path.size());
    if(!QueryFullProcessImageNameW(process,0,path.data(),&size))throw ValidationFailure(ValidationError::FileIo);
    path.resize(size);return path;
}
InjectionError ValidateVictoriaProcess(HANDLE process,const std::filesystem::path& path) {
    if(_wcsicmp(path.filename().c_str(),L"victoria3.exe")!=0)return InjectionError::UnsupportedProcess;
    USHORT machine{},native{};if(!IsWow64Process2(process,&machine,&native) || machine!=IMAGE_FILE_MACHINE_UNKNOWN || native!=IMAGE_FILE_MACHINE_AMD64)return InjectionError::UnsupportedProcess;
    return IsSupportedBuild(Sha256File(path))?InjectionError::None:InjectionError::UnsupportedBuild;
}
static uintptr_t RemoteLoadLibrary(HANDLE process,DWORD pid,ModuleResolutionDiagnostics& d) {
    const auto reject=[&](ModuleResolutionStage stage,DWORD error=0)->uintptr_t {d.stage=stage;d.win32_error=error;return 0;};
    const auto function=GetProcAddress(GetModuleHandleW(L"kernel32.dll"),"LoadLibraryW");
    if(!function)return reject(ModuleResolutionStage::ExportLookup,GetLastError());
    HMODULE owner{};
    if(!GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS|GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,reinterpret_cast<const wchar_t*>(function),&owner))return reject(ModuleResolutionStage::OwnerLookup,GetLastError());
    auto image=PeImage::FromModule(owner);
    if(!image){d.pe_error=image.error;return reject(ModuleResolutionStage::LocalPe);}
    d.local_size=image.value.bytes.size();
    const uintptr_t address=reinterpret_cast<uintptr_t>(function),base=reinterpret_cast<uintptr_t>(owner);
    if(address<base)return reject(ModuleResolutionStage::LocalAddress);
    const size_t offset=address-base;d.export_rva=offset;
    if(!image.value.ExecutableText(offset,16))return reject(ModuleResolutionStage::LocalText);
    std::wstring local_path(32768,L'\0');const DWORD length=GetModuleFileNameW(owner,local_path.data(),static_cast<DWORD>(local_path.size()));
    if(!length || length>=local_path.size())return reject(ModuleResolutionStage::LocalPath,GetLastError());
    local_path.resize(length);d.owner_path=local_path;
    // One explicit-PID module snapshot. A failed/ambiguous lookup is final; no address fallback.
    WinHandle snapshot(CreateToolhelp32Snapshot(TH32CS_SNAPMODULE,pid));if(!snapshot)return reject(ModuleResolutionStage::Snapshot,GetLastError());
    MODULEENTRY32W entry{};entry.dwSize=sizeof(entry);uintptr_t remote=0;size_t matches=0;
    if(!Module32FirstW(snapshot.get(),&entry))return reject(ModuleResolutionStage::ModuleFirst,GetLastError());
    do {
        if(_wcsicmp(entry.szExePath,local_path.c_str())!=0)continue;
        d.remote_size=entry.modBaseSize;
        if(entry.modBaseSize!=image.value.bytes.size())return reject(ModuleResolutionStage::ModuleSize);
        if(offset>=entry.modBaseSize || !CheckedAddress(reinterpret_cast<uintptr_t>(entry.modBaseAddr),offset,remote))return reject(ModuleResolutionStage::RemoteAddress);
        ++matches;d.matches=matches;
    }while(Module32NextW(snapshot.get(),&entry));
    if(matches!=1)return reject(ModuleResolutionStage::ModuleMatch);
    MEMORY_BASIC_INFORMATION region{};
    if(!VirtualQueryEx(process,reinterpret_cast<void*>(remote),&region,sizeof(region)))return reject(ModuleResolutionStage::RemoteQuery,GetLastError());
    d.remote_state=region.State;d.remote_protection=region.Protect;
    if(region.State!=MEM_COMMIT || region.Protect!=PAGE_EXECUTE_READ)return reject(ModuleResolutionStage::RemoteProtection);
    std::array<std::byte,16> bytes{};SIZE_T read{};
    if(!ReadProcessMemory(process,reinterpret_cast<void*>(remote),bytes.data(),bytes.size(),&read)){const DWORD error=GetLastError();d.bytes_read=read;return reject(ModuleResolutionStage::RemoteRead,error);}
    d.bytes_read=read;
    if(read!=bytes.size())return reject(ModuleResolutionStage::RemoteRead);
    if(std::memcmp(bytes.data(),reinterpret_cast<const void*>(function),bytes.size())!=0)return reject(ModuleResolutionStage::ByteMismatch);
    return remote;
}
InjectionError InjectLibraryForValidatedProcess(HANDLE process,DWORD pid,const std::filesystem::path& dll,ModuleResolutionDiagnostics* diagnostics) {
    ModuleResolutionDiagnostics local_diagnostics;
    auto& detail=diagnostics?*diagnostics:local_diagnostics;detail={};
    if(!dll.is_absolute() || !std::filesystem::is_regular_file(dll))return InjectionError::InvalidPath;
    const uintptr_t address=RemoteLoadLibrary(process,pid,detail);if(!address)return InjectionError::ModuleResolution;
    const std::wstring path=dll.wstring();if(path.size()>32766)return InjectionError::InvalidPath;const SIZE_T size=(path.size()+1)*sizeof(wchar_t);
    void* remote=VirtualAllocEx(process,nullptr,size,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE);if(!remote)return InjectionError::RemoteAllocation;
    struct RemoteMemory {HANDLE process;void* value;~RemoteMemory(){if(value)VirtualFreeEx(process,value,0,MEM_RELEASE);}} memory{process,remote};
    SIZE_T written{};if(!WriteProcessMemory(process,remote,path.c_str(),size,&written) || written!=size)return InjectionError::RemoteWrite;
    WinHandle thread(CreateRemoteThread(process,nullptr,0,reinterpret_cast<LPTHREAD_START_ROUTINE>(address),remote,0,nullptr));if(!thread)return InjectionError::RemoteThread;
    const DWORD wait=WaitForSingleObject(thread.get(),30000);
    if(wait!=WAIT_OBJECT_0){memory.value=nullptr;return InjectionError::Timeout;} // Never free a path still potentially in use by LoadLibraryW.
    DWORD exit_code{};if(!GetExitCodeThread(thread.get(),&exit_code) || !exit_code)return InjectionError::LoadFailed;
    return InjectionError::None;
}
}
