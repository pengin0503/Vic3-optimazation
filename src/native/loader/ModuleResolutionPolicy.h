#pragma once
#include "ModuleResolutionDiagnostics.h"
#include "../common/PeImage.h"
#include <span>
namespace vic3 {
inline constexpr size_t kExportProbeSize=16;
// Pure checks over a validated mapped image and values collected by the
// Windows adapter. No process access, retry, allocation or address fallback.
bool ValidateLocalExport(const PeImage& image,uintptr_t owner_base,uintptr_t export_address,ModuleResolutionDiagnostics& d) noexcept;
uintptr_t ValidateRemoteModuleAddress(size_t local_size,size_t export_rva,uintptr_t remote_base,size_t remote_size,ModuleResolutionDiagnostics& d) noexcept;
// Clean end is explicit: an API failure with error zero still fails closed.
bool CompleteModuleEnumeration(bool reached_end,uint32_t enumeration_error,ModuleResolutionDiagnostics& d) noexcept;
bool ValidateRemoteExportRead(std::span<const std::byte,kExportProbeSize> local,std::span<const std::byte,kExportProbeSize> remote,size_t bytes_read,ModuleResolutionDiagnostics& d) noexcept;
}
