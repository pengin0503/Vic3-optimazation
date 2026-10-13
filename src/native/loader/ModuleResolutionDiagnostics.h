#pragma once
#include "../common/Validation.h"
#include <cstdint>
#include <ostream>
#include <string>
#include <array>
#include <cstddef>
namespace vic3 {
inline constexpr size_t kExportProbeSize=16;
enum class RemoteEntryObservation {Unknown,Rel32Jump,Rel32Overflow};
inline constexpr size_t kMaxObservedJumps=4;
struct JumpObservation {
    uint64_t address{},allocation_base{},module_base{},next_address{};
    uint32_t state{},protection{},type{},query_error{},read_error{};
    bool probe_available{};
    std::array<std::byte,kExportProbeSize> bytes{};
    std::wstring module_path;
};
enum class ModuleResolutionStage {
    None,ExportLookup,OwnerLookup,LocalPe,LocalAddress,LocalText,LocalPath,
    Snapshot,ModuleFirst,ModuleMatch,ModuleSize,RemoteAddress,RemoteQuery,
    RemoteProtection,RemoteRead,ByteMismatch,ModuleNext,ProcessIdentity,ProcessTimes
};
struct ModuleResolutionDiagnostics {
    ModuleResolutionStage stage{ModuleResolutionStage::None};
    uint32_t win32_error{};
    ValidationError pe_error{ValidationError::None};
    std::wstring owner_path;
    uint64_t local_size{},remote_size{},export_rva{},matches{},bytes_read{};
    uint64_t local_base{},local_address{},remote_base{},remote_address{};
    uint32_t remote_protection{},remote_state{};
    bool probe_available{};
    std::array<std::byte,kExportProbeSize> local_bytes{},remote_bytes{};
    size_t first_mismatch{kExportProbeSize},mismatch_count{};
    RemoteEntryObservation remote_entry{RemoteEntryObservation::Unknown};
    uint64_t branch_target{};
    bool branch_query_available{};
    uint32_t branch_query_error{},branch_state{},branch_protection{},branch_type{};
    uint64_t branch_allocation_base{};
    uint32_t requested_pid{},handle_pid{};
    uint64_t process_start_filetime{};
    std::array<JumpObservation,kMaxObservedJumps> chain{};
    size_t chain_count{};
    std::wstring chain_stop{L"not_requested"};
    uint32_t chain_module_error{};
};
// Completion describes collected evidence, never permission to inject.
struct LoadLibraryDiagnosis {bool complete{},entry_matches{};};
inline int DiagnosisExitCode(const LoadLibraryDiagnosis& result) noexcept {return result.complete?0:8;}
inline void WriteLoadLibraryDiagnosisResult(std::wostream& out,const LoadLibraryDiagnosis& result) {
    out<<L"diagnosis_status="<<(result.complete?L"complete":L"incomplete")
       <<L" entry_status="<<(!result.complete?L"unknown":result.entry_matches?L"matched":L"modified")
       <<L" connection_status="<<(result.complete && result.entry_matches?L"entry_probe_passed":L"blocked")<<L'\n';
}
inline const wchar_t* ModuleResolutionStageName(ModuleResolutionStage stage) noexcept {
    switch(stage) {
    case ModuleResolutionStage::None:return L"none";
    case ModuleResolutionStage::ProcessIdentity:return L"process_identity";
    case ModuleResolutionStage::ProcessTimes:return L"process_times";
    case ModuleResolutionStage::ExportLookup:return L"export_lookup";
    case ModuleResolutionStage::OwnerLookup:return L"owner_lookup";
    case ModuleResolutionStage::LocalPe:return L"local_pe";
    case ModuleResolutionStage::LocalAddress:return L"local_address";
    case ModuleResolutionStage::LocalText:return L"local_text";
    case ModuleResolutionStage::LocalPath:return L"local_path";
    case ModuleResolutionStage::Snapshot:return L"snapshot";
    case ModuleResolutionStage::ModuleFirst:return L"module_first";
    case ModuleResolutionStage::ModuleNext:return L"module_next";
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
    // Always decimal numeric fields, without changing the caller's stream flags.
    const auto flags=out.flags();out<<std::dec;
    out<<L"Module resolution diagnostics v3: stage="<<ModuleResolutionStageName(d.stage)
       <<L" win32_error="<<d.win32_error<<L" pe_error="<<static_cast<int>(d.pe_error)<<L'\n'
       <<L"owner_path="<<d.owner_path<<L" local_size="<<d.local_size<<L" remote_size="<<d.remote_size
       <<L" export_rva="<<d.export_rva<<L" matches="<<d.matches<<L" bytes_read="<<d.bytes_read
       <<L" remote_state="<<d.remote_state<<L" remote_protection="<<d.remote_protection<<L'\n'
       <<L"local_base="<<d.local_base<<L" local_address="<<d.local_address
       <<L" remote_base="<<d.remote_base<<L" remote_address="<<d.remote_address<<L'\n'
       <<L"requested_pid="<<d.requested_pid<<L" handle_pid="<<d.handle_pid
       <<L" process_start_filetime="<<d.process_start_filetime<<L'\n'
       <<L"probe_available="<<(d.probe_available?1:0)<<L" first_mismatch="<<d.first_mismatch
       <<L" mismatch_count="<<d.mismatch_count<<L'\n';
    if(d.probe_available) {
        constexpr wchar_t hex[]=L"0123456789abcdef";
        const auto write_bytes=[&](const auto& bytes) {for(auto b:bytes){const auto v=std::to_integer<unsigned>(b);out<<hex[v>>4]<<hex[v&15];}};
        out<<L"local_bytes=";write_bytes(d.local_bytes);
        out<<L" remote_bytes=";write_bytes(d.remote_bytes);out<<L'\n';
    }
    const auto entry=d.remote_entry==RemoteEntryObservation::Rel32Jump?L"rel32_jump":
        d.remote_entry==RemoteEntryObservation::Rel32Overflow?L"rel32_overflow":L"unknown";
    out<<L"remote_entry="<<entry<<L" branch_target="<<d.branch_target
       <<L" branch_query_available="<<(d.branch_query_available?1:0)
       <<L" branch_query_error="<<d.branch_query_error<<L" branch_state="<<d.branch_state
       <<L" branch_protection="<<d.branch_protection<<L" branch_type="<<d.branch_type
       <<L" branch_allocation_base="<<d.branch_allocation_base<<L'\n';
    out<<L"chain_count="<<d.chain_count<<L" chain_stop="<<d.chain_stop<<L" chain_module_error="<<d.chain_module_error<<L'\n';
    for(size_t i=0;i<d.chain_count && i<d.chain.size();++i) {
        const auto& hop=d.chain[i];
        out<<L"hop="<<i<<L" address="<<hop.address<<L" state="<<hop.state<<L" protection="<<hop.protection
           <<L" type="<<hop.type<<L" allocation_base="<<hop.allocation_base<<L" query_error="<<hop.query_error
           <<L" read_error="<<hop.read_error<<L" probe_available="<<(hop.probe_available?1:0)
           <<L" next_address="<<hop.next_address<<L" module_base="<<hop.module_base<<L" module_path="<<hop.module_path<<L'\n';
        if(hop.probe_available) {
            constexpr wchar_t hex[]=L"0123456789abcdef";out<<L"hop_bytes=";
            for(auto b:hop.bytes){const auto v=std::to_integer<unsigned>(b);out<<hex[v>>4]<<hex[v&15];}out<<L'\n';
        }
    }
    out.flags(flags);
}
}
