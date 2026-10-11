#pragma once
#include <cstddef>
#include <cstdint>
#include <vector>
#include <cstring>

namespace vic3::testing {
inline void Put(std::vector<std::byte>& b, size_t o, uint64_t v, size_t n) { for(size_t i=0;i<n;++i) b[o+i]=std::byte((v>>(i*8))&255); }
inline std::vector<std::byte> Fixture() {
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
}
