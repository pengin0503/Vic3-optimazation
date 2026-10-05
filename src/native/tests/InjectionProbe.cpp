#include <windows.h>
#include <string>
BOOL WINAPI DllMain(HINSTANCE,DWORD reason,LPVOID) {
    if(reason==DLL_PROCESS_ATTACH){const auto name=L"Local\\Vic3NativeInjectionProbe-"+std::to_wstring(GetCurrentProcessId());HANDLE event=OpenEventW(EVENT_MODIFY_STATE,FALSE,name.c_str());if(!event)return FALSE;SetEvent(event);CloseHandle(event);}return TRUE;
}
