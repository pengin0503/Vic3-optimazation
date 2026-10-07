#include "../common/WinHandle.h"
#include <string>
int main() {
    const auto pid=std::to_wstring(GetCurrentProcessId());
    vic3::WinHandle stop(CreateEventW(nullptr,TRUE,FALSE,(L"Local\\Vic3NativeInjectorHostStop-"+pid).c_str()));
    vic3::WinHandle ready(CreateEventW(nullptr,TRUE,FALSE,(L"Local\\Vic3NativeInjectorHostReady-"+pid).c_str()));
    if(!stop || !ready)return 1;
    SetEvent(ready.get());return WaitForSingleObject(stop.get(),30000)==WAIT_OBJECT_0?0:1;
}
