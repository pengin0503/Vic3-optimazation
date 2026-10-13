#include "../common/WinHandle.h"
#include <string>
#include <cstring>
int main(int argc,char** argv) {
    const auto pid=std::to_wstring(GetCurrentProcessId());
    vic3::WinHandle stop(CreateEventW(nullptr,TRUE,FALSE,(L"Local\\Vic3NativeInjectorHostStop-"+pid).c_str()));
    vic3::WinHandle ready(CreateEventW(nullptr,TRUE,FALSE,(L"Local\\Vic3NativeInjectorHostReady-"+pid).c_str()));
    if(!stop || !ready)return 1;
    // Opt-in, test-owned child only. Never run this mode in a game process.
    // The synthetic entry is never executed: resolver must reject its bytes.
    if(argc==2 && std::strcmp(argv[1],"--synthetic-detour")==0) {
        const auto entry=GetProcAddress(GetModuleHandleW(L"kernel32.dll"),"LoadLibraryW");
        if(!entry)return 2;
        DWORD old{};if(!VirtualProtect(reinterpret_cast<void*>(entry),5,PAGE_EXECUTE_READWRITE,&old))return 2;
        const unsigned char jump[]={0xe9,0,0,0,0}; // observed destination = entry + 5
        std::memcpy(reinterpret_cast<void*>(entry),jump,sizeof(jump));
        DWORD ignored{};if(!VirtualProtect(reinterpret_cast<void*>(entry),5,old,&ignored))return 2;
        if(!FlushInstructionCache(GetCurrentProcess(),reinterpret_cast<void*>(entry),5))return 2;
    } else if(argc!=1)return 2;
    SetEvent(ready.get());return WaitForSingleObject(stop.get(),30000)==WAIT_OBJECT_0?0:1;
}
