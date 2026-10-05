#pragma once
#include <cstdint>
#include <cstddef>
#include <algorithm>
#ifdef _WIN32
#include <windows.h>
#include <string>
#endif
namespace vic3 {
inline constexpr uint32_t kConfigMagic=0x56334346;
inline constexpr uint32_t ConfigDisabled=1,ConfigPartialTargets=2;
enum class ConfigError {None,MissingMapping,Magic,Version,Size,Flags,Targets,OutputPath};
struct SharedConfig {
    uint32_t magic{kConfigMagic},version{1},structure_bytes{sizeof(SharedConfig)},flags{},target_mask{7};
    char16_t output[1024]{};
    bool Disabled() const noexcept{return (flags&ConfigDisabled)!=0;}
};
inline ConfigError ValidateConfig(const SharedConfig& c) noexcept {
    if(c.magic!=kConfigMagic)return ConfigError::Magic;
    if(c.version!=1)return ConfigError::Version;
    if(c.structure_bytes!=sizeof(SharedConfig))return ConfigError::Size;
    if(c.flags&~(ConfigDisabled|ConfigPartialTargets))return ConfigError::Flags;
    if(c.target_mask==0 || (c.target_mask&~7u))return ConfigError::Targets;
    if(!c.output[0] || std::find(std::begin(c.output),std::end(c.output),char16_t{})==std::end(c.output))return ConfigError::OutputPath;
    return ConfigError::None;
}
#ifdef _WIN32
struct SharedMapping {SharedConfig config;volatile LONG status{};uint32_t enabled_mask{},validation_errors[3]{};};
inline std::wstring ObjectName(const wchar_t* kind,DWORD pid){return std::wstring(L"Local\\Vic3OptimizationProfiler")+kind+L"-"+std::to_wstring(pid);}
ConfigError ReadSharedConfig(DWORD pid,SharedConfig& config) noexcept;
#endif
}
