#include "HookBackend.h"
#include <MinHook.h>
namespace vic3 {
bool MinHookBackend::Initialize() noexcept {return MH_Initialize()==MH_OK;}
bool MinHookBackend::Create(void* target,void* detour,void** original) noexcept {return MH_CreateHook(target,detour,original)==MH_OK;}
bool MinHookBackend::Enable(std::span<void* const> targets) noexcept {
    for(auto* target:targets)if(MH_QueueEnableHook(target)!=MH_OK)return false;
    if(MH_ApplyQueued()==MH_OK)return true;
    Disable(targets);return false;
}
bool MinHookBackend::Disable(std::span<void* const> targets) noexcept {
    bool ok=true;
    for(auto* target:targets)if(MH_QueueDisableHook(target)!=MH_OK)ok=false;
    return MH_ApplyQueued()==MH_OK && ok;
}
bool MinHookBackend::Remove(void* target) noexcept {return MH_RemoveHook(target)==MH_OK;}
bool MinHookBackend::Shutdown() noexcept {return MH_Uninitialize()==MH_OK;}
}
