#include "TargetResolver.h"
#include <cstring>
namespace vic3 {
ValidationResult<uintptr_t> ResolveTarget(const PeImage& image,const generated::GeneratedTargetSpec& t) noexcept {
    const auto bad=[](ValidationError e){return ValidationResult<uintptr_t>{0,e};};
    if(!t.pattern || t.pattern_size==0 || t.expected_match_count!=1 || t.vtable_slot_index!=6)return bad(ValidationError::InvalidTargetSpec);
    size_t count=0,match=0;
    for(const auto& s:image.sections) {
        if(!s.scan_text || t.pattern_size>s.size || !image.ExecutableText(s.rva,s.size))continue;
        for(size_t offset=0;offset<=s.size-t.pattern_size;++offset)if(std::memcmp(image.bytes.data()+s.rva+offset,t.pattern,t.pattern_size)==0){match=s.rva+offset;if(++count>1)return bad(ValidationError::SignatureAmbiguous);}
    }
    if(count!=1)return bad(ValidationError::SignatureMissing);
    if(match<t.offset_from_function_start)return bad(ValidationError::InvalidAddress);
    const size_t rva=match-t.offset_from_function_start;
    if(!image.ExecutableText(rva) || !image.ExecutableText(rva,match-rva+t.pattern_size))return bad(ValidationError::InvalidAddress);
    const size_t slot=static_cast<size_t>(t.vtable_rva)+6*8;
    if(!image.Readable(t.vtable_rva,7*8) || !image.Readable(slot,8))return bad(ValidationError::UnreadableVtable);
    uintptr_t value{};std::memcpy(&value,image.bytes.data()+slot,8);
    const auto address=image.Address(rva);if(!address)return bad(ValidationError::InvalidAddress);
    if(value!=address)return bad(ValidationError::VtableMismatch);
    return {address,ValidationError::None};
}
}
