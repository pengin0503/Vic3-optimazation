#pragma once
#include "ModuleResolutionDiagnostics.h"
#include "../common/PeImage.h"
#include <span>
namespace vic3 {
struct RelativeJump {RemoteEntryObservation kind{RemoteEntryObservation::Unknown};uintptr_t target{};};
RelativeJump DecodeRelativeJump(uintptr_t address,std::span<const std::byte,kExportProbeSize> bytes) noexcept;
LoadLibraryDiagnosis ClassifyLoadLibraryDiagnosis(const ModuleResolutionDiagnostics& d) noexcept;
// Pure checks over a validated mapped image and values collected by the
// Windows adapter. No process access, retry, allocation or address fallback.
// Each call reports its own latest result: success clears stage/win32_error.
// Callers must still stop at a failed preceding check; this is no retry policy.
bool ValidateLocalExport(const PeImage& image,uintptr_t owner_base,uintptr_t export_address,ModuleResolutionDiagnostics& d) noexcept;
uintptr_t ValidateRemoteModuleAddress(size_t local_size,size_t export_rva,uintptr_t remote_base,size_t remote_size,ModuleResolutionDiagnostics& d) noexcept;
// Clean end is explicit: an API failure with error zero still fails closed.
bool CompleteModuleEnumeration(bool reached_end,uint32_t enumeration_error,ModuleResolutionDiagnostics& d) noexcept;
bool ValidateRemoteExportRead(std::span<const std::byte,kExportProbeSize> local,std::span<const std::byte,kExportProbeSize> remote,size_t bytes_read,ModuleResolutionDiagnostics& d) noexcept;
}
