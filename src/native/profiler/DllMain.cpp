#include <windows.h>
#include "ProfilerRuntime.h"
static DWORD WINAPI Initialize(void* module) {vic3::RunProfilerRuntime(module);return 0;}
BOOL WINAPI DllMain(HINSTANCE module,DWORD reason,LPVOID) {
    if(reason==DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(module);
        HANDLE thread=CreateThread(nullptr,0,Initialize,module,0,nullptr);
        if(!thread)return FALSE;
        CloseHandle(thread);
    }
    return TRUE;
}
