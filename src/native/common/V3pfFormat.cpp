#include "V3pfFormat.h"
#include <stdexcept>
namespace vic3 {
void PutLittle(std::span<std::byte> bytes,size_t offset,uint64_t value,size_t width) noexcept {for(size_t i=0;i<width;++i)bytes[offset+i]=std::byte((value>>(i*8))&255);}
WireRecord EncodeEvent(const Event& e) noexcept {
    WireRecord r;const uint16_t sizes[]{0,32,40,72,48,40,40};if(e.type<1 || e.type>6 || !e.thread || (!e.target && e.type!=6))return r;r.size=sizes[e.type];
    PutLittle(r.bytes,0,e.timestamp,8);PutLittle(r.bytes,8,e.thread,4);PutLittle(r.bytes,12,e.type,2);PutLittle(r.bytes,14,r.size,2);PutLittle(r.bytes,16,e.target,4);PutLittle(r.bytes,20,e.sequence,4);
    if(e.type!=6)PutLittle(r.bytes,24,e.correlation,8);
    switch(e.type) {
    case 1:break;
    case 2:case 5:PutLittle(r.bytes,32,e.status,4);break;
    case 3:
        if(e.decision>2 || e.range_end<e.range_begin || e.range_length!=e.range_end-e.range_begin){r.size=0;return r;}
        PutLittle(r.bytes,32,e.range_begin,8);PutLittle(r.bytes,40,e.range_end,8);PutLittle(r.bytes,48,e.range_length,8);PutLittle(r.bytes,56,e.task_threads,2);PutLittle(r.bytes,58,e.decision,1);PutLittle(r.bytes,60,e.reason_flags,4);PutLittle(r.bytes,64,e.work_count,4);break;
    case 4:PutLittle(r.bytes,32,e.wait_kind,2);PutLittle(r.bytes,40,e.object_token,8);break;
    case 6:PutLittle(r.bytes,24,e.counter_id,4);PutLittle(r.bytes,32,static_cast<uint64_t>(e.value),8);break;
    default:break;
    }
    return r;
}
std::vector<std::byte> EncodeHeader(const std::string& json,uint64_t frequency,uint64_t start,std::span<const uint8_t,32> target_hash,uint32_t flags,uint64_t dropped) {
    if(json.size()>65416 || !frequency)throw std::invalid_argument("invalid V3PF header");
    const size_t length=112+((json.size()+7)/8)*8;if(length>65528)throw std::invalid_argument("V3PF metadata too large");
    std::vector<std::byte> b(length);b[0]=std::byte{'V'};b[1]=std::byte{'3'};b[2]=std::byte{'P'};b[3]=std::byte{'F'};
    PutLittle(b,4,1,2);PutLittle(b,6,length,2);PutLittle(b,8,8,1);PutLittle(b,16,frequency,8);PutLittle(b,24,start,8);
    for(size_t i=0;i<32;++i){b[32+i]=std::byte(generated::kExecutableSha256[i]);b[68+i]=std::byte(target_hash[i]);}
    PutLittle(b,64,generated::kSignatureDbVersion,4);PutLittle(b,100,flags,4);PutLittle(b,104,dropped,8);
    for(size_t i=0;i<json.size();++i)b[112+i]=std::byte(static_cast<unsigned char>(json[i]));
    return b;
}
std::string RuntimeMetadata(uint32_t enabled_mask,bool disabled) {
    return std::string(R"({"build_ids":{"caligula_branch":"release/1.14.5","caligula_rev":"9f8281a37e85639359b3b0c2c5df0196e975ca4b","clausewitz_branch":"caligula/release/1.14.x","clausewitz_rev":"fd5e1dbd038c3c4a3f48a36abf60ebb42dd0ceef"},"profiler_build_id":"read-only-prototype-v1","targets":)")+generated::kCanonicalTargetsJson+",\"enabled_target_mask\":"+std::to_string(enabled_mask)+",\"disabled\":"+(disabled?"true}":"false}");
}
}
