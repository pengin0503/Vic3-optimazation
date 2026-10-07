#pragma once
#include "../common/Validation.h"
#include <cstdint>
#include <ostream>
#include <string>
namespace vic3 {
enum class ModuleResolutionStage {
    None,ExportLookup,OwnerLookup,LocalPe,LocalAddress,LocalText,LocalPath,
    Snapshot,ModuleFirst,ModuleMatch,ModuleSize,RemoteAddress,RemoteQuery,
    RemoteProtection,RemoteRead,ByteMismatch
};
struct ModuleResolutionDiagnostics {
    ModuleResolutionStage stage{ModuleResolutionStage::None};
    uint32_t win32_error{};
    ValidationError pe_error{ValidationError::None};
    std::wstring owner_path;
    uint64_t local_size{},remote_size{},export_rva{},matches{},bytes_read{};
    uint32_t remote_protection{},remote_state{};
};
inline const wchar_t* ModuleResolutionStageName(ModuleResolutionStage stage) noexcept {
    switch(stage) {
    case ModuleResolutionStage::None:return L"none";
    case ModuleResolutionStage::ExportLookup:return L"export_lookup";
    case ModuleResolutionStage::OwnerLookup:return L"owner_lookup";
    case ModuleResolutionStage::LocalPe:return L"local_pe";
    case ModuleResolutionStage::LocalAddress:return L"local_address";
    case ModuleResolutionStage::LocalText:return L"local_text";
    case ModuleResolutionStage::LocalPath:return L"local_path";
    case ModuleResolutionStage::Snapshot:return L"snapshot";
    case ModuleResolutionStage::ModuleFirst:return L"module_first";
    case ModuleResolutionStage::ModuleMatch:return L"module_match";
    case ModuleResolutionStage::ModuleSize:return L"module_size";
    case ModuleResolutionStage::RemoteAddress:return L"remote_address";
    case ModuleResolutionStage::RemoteQuery:return L"remote_query";
    case ModuleResolutionStage::RemoteProtection:return L"remote_protection";
    case ModuleResolutionStage::RemoteRead:return L"remote_read";
    case ModuleResolutionStage::ByteMismatch:return L"byte_mismatch";
    }
    return L"unknown";
}
inline void WriteModuleResolutionDiagnostics(std::wostream& out,const ModuleResolutionDiagnostics& d) {
    out<<L"Module resolution diagnostics v1: stage="<<ModuleResolutionStageName(d.stage)
       <<L" win32_error="<<d.win32_error<<L" pe_error="<<static_cast<int>(d.pe_error)<<L'\n'
       <<L"owner_path="<<d.owner_path<<L" local_size="<<d.local_size<<L" remote_size="<<d.remote_size
       <<L" export_rva="<<d.export_rva<<L" matches="<<d.matches<<L" bytes_read="<<d.bytes_read
       <<L" remote_state="<<d.remote_state<<L" remote_protection="<<d.remote_protection<<L'\n';
}
}
