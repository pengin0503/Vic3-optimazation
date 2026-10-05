#include "Test.h"
#include "../common/TargetResolver.h"
#include <vector>
#include <cstring>
#include <limits>
#ifdef _WIN32
#include "../common/Sha256.h"
#include <fstream>
#endif
using namespace vic3;
static void Put(std::vector<std::byte>& b, size_t o, uint64_t v, size_t n) { for(size_t i=0;i<n;++i) b[o+i]=std::byte((v>>(i*8))&255); }
static std::vector<std::byte> Fixture() {
    std::vector<std::byte> b(0x4000);
    Put(b,0,0x5a4d,2); Put(b,0x3c,0x80,4); Put(b,0x80,0x4550,4);
    Put(b,0x84,0x8664,2); Put(b,0x86,2,2); Put(b,0x94,0xf0,2);
    Put(b,0x98,0x20b,2); Put(b,0xd0,0x4000,4); Put(b,0xd4,0x400,4);
    std::memcpy(b.data()+0x188,".text",5); Put(b,0x190,0x1000,4); Put(b,0x194,0x1000,4); Put(b,0x1ac,0x60000020,4);
    std::memcpy(b.data()+0x1b0,".rdata",6); Put(b,0x1b8,0x1000,4); Put(b,0x1bc,0x3000,4); Put(b,0x1d4,0x40000040,4);
    b[0x1020]=std::byte{0xde};b[0x1021]=std::byte{0xad};
    Put(b,0x3030,reinterpret_cast<uintptr_t>(b.data())+0x1010,8);
    return b;
}
int main() {
    const uint8_t pattern[]{0xde,0xad}; generated::GeneratedTargetSpec t{};
    t.pattern=pattern;t.pattern_size=2;t.offset_from_function_start=16;t.vtable_rva=0x3000;t.vtable_slot_index=6;t.expected_match_count=1;
    auto b=Fixture();auto image=PeImage::FromMapped(b);CHECK(image);
    CHECK(ResolveTarget(image.value,t).value==reinterpret_cast<uintptr_t>(b.data())+0x1010);
    b[0x1020]=std::byte{0};CHECK(ResolveTarget(image.value,t).error==ValidationError::SignatureMissing);
    b[0x1020]=std::byte{0xde};b[0x1040]=std::byte{0xde};b[0x1041]=std::byte{0xad};CHECK(ResolveTarget(image.value,t).error==ValidationError::SignatureAmbiguous);
    b[0x1040]=std::byte{0};Put(b,0x3030,1,8);CHECK(ResolveTarget(image.value,t).error==ValidationError::VtableMismatch);
    Put(b,0x3030,reinterpret_cast<uintptr_t>(b.data())+0x1010,8);
    t.offset_from_function_start=0x2000;CHECK(ResolveTarget(image.value,t).error==ValidationError::InvalidAddress);t.offset_from_function_start=16;
    t.vtable_rva=0xfffffff0;CHECK(ResolveTarget(image.value,t).error==ValidationError::UnreadableVtable);t.vtable_rva=0x3000;
    t.vtable_slot_index=5;CHECK(ResolveTarget(image.value,t).error==ValidationError::InvalidTargetSpec);t.vtable_slot_index=6;
    Put(b,0x84,0x14c,2);CHECK(PeImage::FromMapped(b).error==ValidationError::UnsupportedMachine);Put(b,0x84,0x8664,2);
    Put(b,0x98,0x10b,2);CHECK(PeImage::FromMapped(b).error==ValidationError::UnsupportedPe);Put(b,0x98,0x20b,2);
    CHECK(PeImage::FromMapped(std::span<const std::byte>(b.data(),0x90)).error==ValidationError::MalformedPe);
    Put(b,0x194,0xfffffff0,4);CHECK(PeImage::FromMapped(b).error==ValidationError::MalformedPe);Put(b,0x194,0x1000,4);
    Put(b,0x1ac,0xc0000020,4);auto noexec=PeImage::FromMapped(b);CHECK(noexec);CHECK(ResolveTarget(noexec.value,t).error==ValidationError::SignatureMissing);
    Put(b,0x1ac,0xe0000020,4);auto writable=PeImage::FromMapped(b);CHECK(writable);CHECK(ResolveTarget(writable.value,t).error==ValidationError::SignatureMissing);
    uintptr_t out{};CHECK(!CheckedAddress(std::numeric_limits<uintptr_t>::max()-1,8,out));
#ifdef _WIN32
    const std::byte abc[]{std::byte{'a'},std::byte{'b'},std::byte{'c'}};
    const unsigned char expected[]{0xba,0x78,0x16,0xbf,0x8f,0x01,0xcf,0xea,0x41,0x41,0x40,0xde,0x5d,0xae,0x22,0x23,0xb0,0x03,0x61,0xa3,0x96,0x17,0x7a,0x9c,0xb4,0x10,0xff,0x61,0xf2,0x00,0x15,0xad};
    auto digest=Sha256Bytes(abc);CHECK(std::memcmp(digest.data(),expected,32)==0);CHECK(!IsSupportedBuild(digest));
    {std::ofstream f("hash-fixture.bin",std::ios::binary);f.write("abc",3);}
    CHECK(Sha256File("hash-fixture.bin")==digest);std::filesystem::remove("hash-fixture.bin");
    bool failed=false;try{Sha256File("missing-sha-fixture.bin");}catch(const ValidationFailure& e){failed=e.code==ValidationError::FileIo;}CHECK(failed);
#endif
    std::cout << "Resolver validation passed\n";
}
