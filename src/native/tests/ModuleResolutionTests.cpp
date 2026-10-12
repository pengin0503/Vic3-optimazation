#include "Test.h"
#include "PeFixture.h"
#include "../loader/ModuleResolutionPolicy.h"
#include <array>
#include <limits>
#include <sstream>
using namespace vic3;
using namespace vic3::testing;

int main() {
    auto bytes=Fixture();auto image=PeImage::FromMapped(bytes);CHECK(image);
    const auto base=reinterpret_cast<uintptr_t>(bytes.data());
    ModuleResolutionDiagnostics d;
    CHECK(ValidateLocalExport(image.value,base,base+0x1010,d));
    CHECK(d.export_rva==0x1010 && d.local_size==0x4000);
    d.win32_error=87;
    CHECK(!ValidateLocalExport(image.value,base,base-1,d));
    CHECK(d.stage==ModuleResolutionStage::LocalAddress && d.win32_error==0);
    CHECK(!ValidateLocalExport(image.value,base,base+0x1ff1,d));
    CHECK(d.stage==ModuleResolutionStage::LocalText);
    CHECK(!ValidateLocalExport(image.value,base,base+bytes.size(),d));
    CHECK(d.stage==ModuleResolutionStage::LocalText);
    Put(bytes,0x1ac,0xe0000020,4);image=PeImage::FromMapped(bytes);CHECK(image);
    CHECK(!ValidateLocalExport(image.value,base,base+0x1010,d));
    CHECK(d.stage==ModuleResolutionStage::LocalText);

    // Uncovered structural PE errors, distinct from signature/slot validation.
    Put(bytes,0x86,0,2);CHECK(PeImage::FromMapped(bytes).error==ValidationError::MalformedPe);
    Put(bytes,0x86,97,2);CHECK(PeImage::FromMapped(bytes).error==ValidationError::MalformedPe);
    Put(bytes,0x86,2,2);Put(bytes,0x1bc,0x1800,4);
    CHECK(PeImage::FromMapped(bytes).error==ValidationError::MalformedPe);
    Put(bytes,0x1bc,0x3000,4);Put(bytes,0xd4,0x180,4);
    CHECK(PeImage::FromMapped(bytes).error==ValidationError::MalformedPe);

    d={};
    CHECK(ValidateRemoteModuleAddress(0x4000,0x1010,0x100000,0x4000,d)==0x101010);
    CHECK(d.remote_base==0x100000 && d.remote_address==0x101010);
    d.win32_error=87;
    CHECK(!ValidateRemoteModuleAddress(0x4000,0x1010,0x100000,0x5000,d));
    CHECK(d.stage==ModuleResolutionStage::ModuleSize && d.win32_error==0);
    CHECK(!ValidateRemoteModuleAddress(0x4000,0x1010,0,0x4000,d));
    CHECK(d.stage==ModuleResolutionStage::RemoteAddress);
    CHECK(ValidateRemoteModuleAddress(0x4000,0x3ff0,0x100000,0x4000,d)==0x103ff0);
    for(size_t offset:{size_t{0x3ff1},size_t{0x4000},std::numeric_limits<size_t>::max()}) {
        CHECK(!ValidateRemoteModuleAddress(0x4000,offset,0x100000,0x4000,d));
        CHECK(d.stage==ModuleResolutionStage::RemoteAddress);
    }
    const auto max=std::numeric_limits<uintptr_t>::max();
    CHECK(!ValidateRemoteModuleAddress(0x4000,0x1010,max-1,0x4000,d));
    CHECK(ValidateRemoteModuleAddress(0x4000,16,max-31,0x4000,d)==max-15);
    CHECK(!ValidateRemoteModuleAddress(0x4000,16,max-30,0x4000,d));

    for(uint64_t matches:{uint64_t{0},uint64_t{2}}) {
        d={};d.matches=matches;d.win32_error=87;
        CHECK(!CompleteModuleEnumeration(true,0,d));
        CHECK(d.stage==ModuleResolutionStage::ModuleMatch && d.win32_error==0);
    }
    d={};d.matches=1;CHECK(CompleteModuleEnumeration(true,0,d));
    // A partial enumeration with one owner is never a successful lookup.
    CHECK(!CompleteModuleEnumeration(false,299,d));
    CHECK(d.stage==ModuleResolutionStage::ModuleNext && d.win32_error==299);

    d={};d.matches=1;
    CHECK(!CompleteModuleEnumeration(false,0,d));
    CHECK(d.stage==ModuleResolutionStage::ModuleNext && d.win32_error==0);

    std::array<std::byte,16> local{},remote{};local[0]=remote[0]=std::byte{0xcc};
    d={};CHECK(ValidateRemoteExportRead(local,remote,16,d));
    for(size_t read:{size_t{0},size_t{15},size_t{17}}) {
        d.win32_error=87;CHECK(!ValidateRemoteExportRead(local,remote,read,d));
        CHECK(d.stage==ModuleResolutionStage::RemoteRead && d.bytes_read==read && d.win32_error==0);
    }
    remote[15]=std::byte{1};d.win32_error=87;
    CHECK(!ValidateRemoteExportRead(local,remote,16,d));
    CHECK(d.stage==ModuleResolutionStage::ByteMismatch && d.win32_error==0);
    std::wostringstream mismatch_log;WriteModuleResolutionDiagnostics(mismatch_log,d);
    CHECK(mismatch_log.str().find(L"local_bytes=cc000000000000000000000000000000")!=std::wstring::npos);
    CHECK(mismatch_log.str().find(L"remote_bytes=cc000000000000000000000000000001")!=std::wstring::npos);
    CHECK(mismatch_log.str().find(L"first_mismatch=15 mismatch_count=1")!=std::wstring::npos);
    const auto rendered=[](const ModuleResolutionDiagnostics& value) {
        std::wostringstream out;WriteModuleResolutionDiagnostics(out,value);return out.str();
    };
    for(size_t index=0;index<16;++index) {
        remote=local;remote[index]^=std::byte{1};d={};
        CHECK(!ValidateRemoteExportRead(local,remote,16,d));
        CHECK(rendered(d).find(L"first_mismatch="+std::to_wstring(index)+L" mismatch_count=1")!=std::wstring::npos);
    }
    remote[0]^=std::byte{1}; // differences at 0 and 15
    CHECK(!ValidateRemoteExportRead(local,remote,16,d));
    CHECK(rendered(d).find(L"first_mismatch=0 mismatch_count=2")!=std::wstring::npos);
    CHECK(!ValidateRemoteExportRead(local,remote,15,d));
    CHECK(rendered(d).find(L"probe_available=0")!=std::wstring::npos);
    CHECK(rendered(d).find(L"local_bytes=")==std::wstring::npos);
    CHECK(rendered(d).find(L"remote_bytes=")==std::wstring::npos);
    remote=local;CHECK(ValidateRemoteExportRead(local,remote,16,d));
    CHECK(rendered(d).find(L"first_mismatch=16 mismatch_count=0")!=std::wstring::npos);
    // Issue #17 hop 0. Decode only; do not call or trust this address.
    remote={};remote[0]=std::byte{0xe9};
    remote[1]=std::byte{0x57};remote[2]=std::byte{0x13};remote[3]=std::byte{0xff};remote[4]=std::byte{0xfd};
    d={};d.remote_address=0x7ffb9924ee30;
    CHECK(!ValidateRemoteExportRead(local,remote,16,d));
    CHECK(rendered(d).find(L"remote_entry=rel32_jump")!=std::wstring::npos);
    CHECK(rendered(d).find(L"branch_target="+std::to_wstring(uint64_t{0x7ffb9724018c}))!=std::wstring::npos);
    remote[1]=std::byte{7};remote[2]=remote[3]=remote[4]=std::byte{0};
    d={};d.remote_address=100;CHECK(!ValidateRemoteExportRead(local,remote,16,d));
    CHECK(rendered(d).find(L"branch_target=112")!=std::wstring::npos);
    d.remote_address=max-4;CHECK(!ValidateRemoteExportRead(local,remote,16,d));
    CHECK(rendered(d).find(L"remote_entry=rel32_overflow")!=std::wstring::npos);
    remote[1]=remote[2]=remote[3]=std::byte{0};remote[4]=std::byte{0x80}; // INT32_MIN
    d.remote_address=100;CHECK(!ValidateRemoteExportRead(local,remote,16,d));
    CHECK(rendered(d).find(L"remote_entry=rel32_overflow")!=std::wstring::npos);
    remote[0]=std::byte{0xff};CHECK(!ValidateRemoteExportRead(local,remote,16,d));
    CHECK(rendered(d).find(L"remote_entry=unknown")!=std::wstring::npos);
    CHECK(rendered(d).find(L"branch_target=0")!=std::wstring::npos);
    d.stage=ModuleResolutionStage::ModuleNext;d.win32_error=299;
    std::wostringstream log;WriteModuleResolutionDiagnostics(log,d);
    CHECK(log.str().find(L"stage=module_next")!=std::wstring::npos);
    CHECK(log.str().find(L"win32_error=299")!=std::wstring::npos);
    CHECK(log.str().find(L"remote_address=")!=std::wstring::npos);
    std::cout << "Owned PE, export bounds, enumeration and byte rejection passed\n";
}
