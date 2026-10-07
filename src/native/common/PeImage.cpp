#include "PeImage.h"
#include <cstring>
#include <limits>
namespace vic3 {
bool CheckedAddress(uintptr_t base,size_t offset,uintptr_t& out) noexcept { if(offset>std::numeric_limits<uintptr_t>::max()-base)return false;out=base+offset;return true; }
static bool Fits(size_t o,size_t n,size_t length) noexcept { return o<=length && n<=length-o; }
static uint32_t U32(std::span<const std::byte> b,size_t o) noexcept { uint32_t v{};std::memcpy(&v,b.data()+o,4);return v; }
static uint16_t U16(std::span<const std::byte> b,size_t o) noexcept { uint16_t v{};std::memcpy(&v,b.data()+o,2);return v; }
#ifdef _WIN32
static bool Pages(uintptr_t p,size_t n,bool exec) noexcept {
    uintptr_t end{};if(!CheckedAddress(p,n,end))return false;
    while(p<end) {
        MEMORY_BASIC_INFORMATION m{};if(!VirtualQuery(reinterpret_cast<void*>(p),&m,sizeof(m)))return false;
        const DWORD protection=m.Protect & 0xff;
        const bool readable=protection==PAGE_READONLY || protection==PAGE_READWRITE || protection==PAGE_WRITECOPY || protection==PAGE_EXECUTE_READ || protection==PAGE_EXECUTE_READWRITE || protection==PAGE_EXECUTE_WRITECOPY;
        const bool executable=protection==PAGE_EXECUTE_READ;
        if(m.State!=MEM_COMMIT || (m.Protect&(PAGE_GUARD|PAGE_NOACCESS)) || !readable || (exec&&!executable))return false;
        uintptr_t next{};if(!CheckedAddress(reinterpret_cast<uintptr_t>(m.BaseAddress),m.RegionSize,next)||next<=p)return false;
        p=next;
    }
    return true;
}
#endif
ValidationResult<PeImage> PeImage::FromMapped(std::span<const std::byte> b) {
    const auto bad=[](ValidationError e){return ValidationResult<PeImage>{{},e};};
    if(b.size()<64 || U16(b,0)!=0x5a4d)return bad(ValidationError::MalformedPe);
    const size_t pe=U32(b,0x3c);if(pe<64 || !Fits(pe,24,b.size()) || U32(b,pe)!=0x4550)return bad(ValidationError::MalformedPe);
    if(U16(b,pe+4)!=0x8664)return bad(ValidationError::UnsupportedMachine);
    const size_t count=U16(b,pe+6),opt_size=U16(b,pe+20),opt=pe+24;
    if(count==0 || count>96 || opt_size<112 || !Fits(opt,opt_size,b.size()))return bad(ValidationError::MalformedPe);
    if(U16(b,opt)!=0x20b)return bad(ValidationError::UnsupportedPe);
    const size_t image_size=U32(b,opt+56),headers=U32(b,opt+60),table=opt+opt_size;
    if(image_size==0 || image_size>b.size() || headers>image_size || !Fits(table,count*40,headers))return bad(ValidationError::MalformedPe);
    PeImage image;image.bytes=b.first(image_size);
    for(size_t i=0;i<count;++i) {
        const size_t s=table+i*40,rva=U32(b,s+12),length=U32(b,s+8);const uint32_t flags=U32(b,s+36);
        if(!Fits(rva,length,image_size) || (length && rva<headers))return bad(ValidationError::MalformedPe);
        for(const auto& previous:image.sections)if(length && previous.size && rva<previous.rva+previous.size && previous.rva<rva+length)return bad(ValidationError::MalformedPe);
        const char text[8]={'.','t','e','x','t',0,0,0};
        image.sections.push_back({rva,length,std::memcmp(b.data()+s,text,8)==0 && (flags&0x20000000u)!=0 && (flags&0x80000000u)==0});
    }
    return {std::move(image),ValidationError::None};
}
bool PeImage::Readable(size_t rva,size_t length) const noexcept {
    if(!Fits(rva,length,bytes.size()))return false;
    const auto address=Address(rva);if(!address)return false;
#ifdef _WIN32
    if(check_pages_)return Pages(address,length,false);
#endif
    return true;
}
bool PeImage::ExecutableText(size_t rva,size_t length) const noexcept {
    for(const auto& s:sections)if(s.scan_text && rva>=s.rva && Fits(rva-s.rva,length,s.size) && Readable(rva,length)) {
#ifdef _WIN32
        if(check_pages_ && !Pages(Address(rva),length,true))return false;
#endif
        return true;
    }
    return false;
}
uintptr_t PeImage::Address(size_t rva) const noexcept { uintptr_t out{};return CheckedAddress(reinterpret_cast<uintptr_t>(bytes.data()),rva,out)?out:0; }
#ifdef _WIN32
ValidationResult<PeImage> PeImage::FromModule(HMODULE module) {
    const auto base=reinterpret_cast<uintptr_t>(module);
    if(!base || !Pages(base,64,false))return {{},ValidationError::MalformedPe};
    auto b=std::span(reinterpret_cast<const std::byte*>(module),size_t{64});const size_t pe=U32(b,0x3c);uintptr_t nt{};
    if(pe<64 || !CheckedAddress(base,pe,nt) || !Pages(nt,24+112,false))return {{},ValidationError::MalformedPe};
    auto n=std::span(reinterpret_cast<const std::byte*>(nt),size_t{136});
    const size_t headers=U32(n,24+60),image_size=U32(n,24+56);
    if(headers<pe+136 || headers>image_size || !Pages(base,headers,false))return {{},ValidationError::MalformedPe};
    // FromMapped reads only headers here; section byte access is page-checked later.
    auto result=FromMapped(std::span(reinterpret_cast<const std::byte*>(module),image_size));
    if(result)result.value.check_pages_=true;
    return result;
}
#endif
}
