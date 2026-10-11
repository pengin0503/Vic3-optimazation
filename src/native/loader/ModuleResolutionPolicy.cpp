#include "ModuleResolutionPolicy.h"
#include <cstring>
namespace vic3 {
static bool Reject(ModuleResolutionDiagnostics& d,ModuleResolutionStage stage,uint32_t error=0) noexcept {
    d.stage=stage;d.win32_error=error;return false;
}
bool ValidateLocalExport(const PeImage& image,uintptr_t owner_base,uintptr_t export_address,ModuleResolutionDiagnostics& d) noexcept {
    d.local_base=owner_base;d.local_address=export_address;d.local_size=image.bytes.size();
    if(!owner_base || export_address<owner_base)return Reject(d,ModuleResolutionStage::LocalAddress);
    const size_t offset=export_address-owner_base;d.export_rva=offset;
    if(!image.ExecutableText(offset,kExportProbeSize))return Reject(d,ModuleResolutionStage::LocalText);
    return true;
}
uintptr_t ValidateRemoteModuleAddress(size_t local_size,size_t export_rva,uintptr_t remote_base,size_t remote_size,ModuleResolutionDiagnostics& d) noexcept {
    d.remote_base=remote_base;d.remote_size=remote_size;d.remote_address=0;
    if(remote_size!=local_size){Reject(d,ModuleResolutionStage::ModuleSize);return 0;}
    uintptr_t address{},last{};
    if(!remote_base || export_rva>remote_size || kExportProbeSize>remote_size-export_rva ||
       !CheckedAddress(remote_base,export_rva,address) || !CheckedAddress(address,kExportProbeSize-1,last)) {
        Reject(d,ModuleResolutionStage::RemoteAddress);return 0;
    }
    d.remote_address=address;return address;
}
bool CompleteModuleEnumeration(bool reached_end,uint32_t enumeration_error,ModuleResolutionDiagnostics& d) noexcept {
    if(!reached_end)return Reject(d,ModuleResolutionStage::ModuleNext,enumeration_error);
    if(d.matches!=1)return Reject(d,ModuleResolutionStage::ModuleMatch);
    return true;
}
bool ValidateRemoteExportRead(std::span<const std::byte,kExportProbeSize> local,std::span<const std::byte,kExportProbeSize> remote,size_t bytes_read,ModuleResolutionDiagnostics& d) noexcept {
    d.bytes_read=bytes_read;
    if(bytes_read!=kExportProbeSize)return Reject(d,ModuleResolutionStage::RemoteRead);
    if(std::memcmp(local.data(),remote.data(),kExportProbeSize)!=0)return Reject(d,ModuleResolutionStage::ByteMismatch);
    return true;
}
}
