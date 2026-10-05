#pragma once
#include <span>
namespace vic3 {
class HookBackend {
public:
    virtual ~HookBackend()=default;
    virtual bool Initialize() noexcept=0;
    virtual bool Create(void* target,void* detour,void** original) noexcept=0;
    virtual bool Enable(std::span<void* const> targets) noexcept=0;
    virtual bool Disable(std::span<void* const> targets) noexcept=0;
    virtual bool Remove(void* target) noexcept=0;
    virtual bool Shutdown() noexcept=0;
};
#ifdef _WIN32
class MinHookBackend final:public HookBackend {
public:
    bool Initialize() noexcept override;
    bool Create(void*,void*,void**) noexcept override;
    bool Enable(std::span<void* const>) noexcept override;
    bool Disable(std::span<void* const>) noexcept override;
    bool Remove(void*) noexcept override;
    bool Shutdown() noexcept override;
};
#endif
}
