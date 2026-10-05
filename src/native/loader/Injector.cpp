#include "Injector.h"
#include "../common/WinHandle.h"
#include "../common/Sha256.h"
#include "../common/PeImage.h"
#include <tlhelp32.h>
#include <array>
#include <cstring>
namespace vic3 {
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
static uintptr_t RemoteLoadLibrary(HANDLE process,DWORD pid) {
    const auto function=GetProcAddress(GetModuleHandleW(L"kernel32.dll"),"LoadLibraryW");if(!function)return 0;
    HMODULE owner{};
    if(!GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS|GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,reinterpret_cast<const wchar_t*>(function),&owner))return 0;
    auto image=PeImage::FromModule(owner);if(!image)return 0;
    const uintptr_t address=reinterpret_cast<uintptr_t>(function),base=reinterpret_cast<uintptr_t>(owner);if(address<base)return 0;const size_t offset=address-base;
    if(!image.value.ExecutableText(offset,16))return 0;
    std::wstring local_path(32768,L'\0');const DWORD length=GetModuleFileNameW(owner,local_path.data(),static_cast<DWORD>(local_path.size()));if(!length || length>=local_path.size())return 0;local_path.resize(length);
    // One explicit-PID module snapshot. A failed/ambiguous lookup is final; no address fallback.
    WinHandle snapshot(CreateToolhelp32Snapshot(TH32CS_SNAPMODULE,pid));if(!snapshot)return 0;
    MODULEENTRY32W entry{};entry.dwSize=sizeof(entry);uintptr_t remote=0;size_t matches=0;
    if(!Module32FirstW(snapshot.get(),&entry))return 0;
    do {
        if(_wcsicmp(entry.szExePath,local_path.c_str())!=0)continue;
        if(entry.modBaseSize!=image.value.bytes.size() || offset>=entry.modBaseSize || !CheckedAddress(reinterpret_cast<uintptr_t>(entry.modBaseAddr),offset,remote))return 0;
        ++matches;
    }while(Module32NextW(snapshot.get(),&entry));
    if(matches!=1)return 0;
    MEMORY_BASIC_INFORMATION region{};if(!VirtualQueryEx(process,reinterpret_cast<void*>(remote),&region,sizeof(region)) || region.State!=MEM_COMMIT || region.Protect!=PAGE_EXECUTE_READ)return 0;
    std::array<std::byte,16> bytes{};SIZE_T read{};if(!ReadProcessMemory(process,reinterpret_cast<void*>(remote),bytes.data(),bytes.size(),&read) || read!=bytes.size() || std::memcmp(bytes.data(),reinterpret_cast<const void*>(function),bytes.size())!=0)return 0;
    return remote;
}
InjectionError InjectLibraryForValidatedProcess(HANDLE process,DWORD pid,const std::filesystem::path& dll) {
    if(!dll.is_absolute() || !std::filesystem::is_regular_file(dll))return InjectionError::InvalidPath;
    const uintptr_t address=RemoteLoadLibrary(process,pid);if(!address)return InjectionError::ModuleResolution;
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
