#include "ModuleResolutionPolicy.h"
#include <cstring>
namespace vic3 {
RelativeJump DecodeRelativeJump(uintptr_t address,std::span<const std::byte,kExportProbeSize> bytes) noexcept {
    if(bytes[0]!=std::byte{0xe9})return {};
    int32_t displacement{};std::memcpy(&displacement,bytes.data()+1,sizeof(displacement));
    uintptr_t next{},target{};bool valid=CheckedAddress(address,5,next);
    if(valid && displacement>=0)valid=CheckedAddress(next,static_cast<size_t>(displacement),target);
    else if(valid) {
        const auto distance=static_cast<uintptr_t>(-static_cast<int64_t>(displacement));
        valid=distance<=next;if(valid)target=next-distance;
    }
    return {valid?RemoteEntryObservation::Rel32Jump:RemoteEntryObservation::Rel32Overflow,valid?target:0};
}
LoadLibraryDiagnosis ClassifyLoadLibraryDiagnosis(const ModuleResolutionDiagnostics& d) noexcept {
    const bool identity=d.requested_pid && d.requested_pid==d.handle_pid && d.process_start_filetime;
    const bool evidence=identity && d.matches==1 && d.probe_available && d.bytes_read==kExportProbeSize &&
        d.win32_error==0 && d.pe_error==ValidationError::None;
    if(!evidence)return {};
    if(d.stage==ModuleResolutionStage::None && d.mismatch_count==0)return {true,true};
    if(d.stage==ModuleResolutionStage::ByteMismatch && d.mismatch_count>0)return {true,false};
    return {};
}
static bool Reject(ModuleResolutionDiagnostics& d,ModuleResolutionStage stage,uint32_t error=0) noexcept {
    d.stage=stage;d.win32_error=error;return false;
}
static bool Accept(ModuleResolutionDiagnostics& d) noexcept {
    d.stage=ModuleResolutionStage::None;d.win32_error=0;return true;
}
bool ValidateLocalExport(const PeImage& image,uintptr_t owner_base,uintptr_t export_address,ModuleResolutionDiagnostics& d) noexcept {
    d.local_base=owner_base;d.local_address=export_address;d.local_size=image.bytes.size();
    if(!owner_base || export_address<owner_base)return Reject(d,ModuleResolutionStage::LocalAddress);
    const size_t offset=export_address-owner_base;d.export_rva=offset;
    if(!image.ExecutableText(offset,kExportProbeSize))return Reject(d,ModuleResolutionStage::LocalText);
    return Accept(d);
}
uintptr_t ValidateRemoteModuleAddress(size_t local_size,size_t export_rva,uintptr_t remote_base,size_t remote_size,ModuleResolutionDiagnostics& d) noexcept {
    d.remote_base=remote_base;d.remote_size=remote_size;d.remote_address=0;
    if(remote_size!=local_size){Reject(d,ModuleResolutionStage::ModuleSize);return 0;}
    uintptr_t address{},last{};
    if(!remote_base || export_rva>remote_size || kExportProbeSize>remote_size-export_rva ||
       !CheckedAddress(remote_base,export_rva,address) || !CheckedAddress(address,kExportProbeSize-1,last)) {
        Reject(d,ModuleResolutionStage::RemoteAddress);return 0;
    }
    d.remote_address=address;Accept(d);return address;
}
bool CompleteModuleEnumeration(bool reached_end,uint32_t enumeration_error,ModuleResolutionDiagnostics& d) noexcept {
    if(!reached_end)return Reject(d,ModuleResolutionStage::ModuleNext,enumeration_error);
    if(d.matches!=1)return Reject(d,ModuleResolutionStage::ModuleMatch);
    return Accept(d);
}
bool ValidateRemoteExportRead(std::span<const std::byte,kExportProbeSize> local,std::span<const std::byte,kExportProbeSize> remote,size_t bytes_read,ModuleResolutionDiagnostics& d) noexcept {
    d.bytes_read=bytes_read;
    d.probe_available=false;d.local_bytes={};d.remote_bytes={};
    d.first_mismatch=kExportProbeSize;d.mismatch_count=0;
    d.remote_entry=RemoteEntryObservation::Unknown;d.branch_target=0;
    d.branch_query_available=false;d.branch_query_error=0;d.branch_state=0;
    d.branch_protection=0;d.branch_type=0;d.branch_allocation_base=0;
    if(bytes_read!=kExportProbeSize)return Reject(d,ModuleResolutionStage::RemoteRead);
    d.probe_available=true;
    for(size_t i=0;i<kExportProbeSize;++i) {
        d.local_bytes[i]=local[i];d.remote_bytes[i]=remote[i];
        if(local[i]!=remote[i]) {if(!d.mismatch_count)d.first_mismatch=i;++d.mismatch_count;}
    }
    // Observation only. No jump target ever becomes an injection address.
    const auto jump=DecodeRelativeJump(static_cast<uintptr_t>(d.remote_address),remote);
    d.remote_entry=jump.kind;d.branch_target=jump.target;
    if(std::memcmp(local.data(),remote.data(),kExportProbeSize)!=0)return Reject(d,ModuleResolutionStage::ByteMismatch);
    return Accept(d);
}
}
