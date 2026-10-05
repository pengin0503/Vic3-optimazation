#include "Sha256.h"
#include "../generated/targets_1_14_5.inc"
#include <windows.h>
#include <bcrypt.h>
#include <algorithm>
#include <fstream>
#include <vector>
#include <limits>
namespace vic3 {
class Hash {
    BCRYPT_ALG_HANDLE algorithm_{}; BCRYPT_HASH_HANDLE hash_{};std::vector<UCHAR> object_;
public:
    Hash() {
        if(BCryptOpenAlgorithmProvider(&algorithm_,BCRYPT_SHA256_ALGORITHM,nullptr,0)<0)throw ValidationFailure(ValidationError::HashFailed);
        DWORD length{},written{};
        if(BCryptGetProperty(algorithm_,BCRYPT_OBJECT_LENGTH,reinterpret_cast<PUCHAR>(&length),sizeof(length),&written,0)<0){BCryptCloseAlgorithmProvider(algorithm_,0);throw ValidationFailure(ValidationError::HashFailed);}
        try { object_.resize(length); } catch(...) { BCryptCloseAlgorithmProvider(algorithm_,0);throw; }
        if(BCryptCreateHash(algorithm_,&hash_,object_.data(),length,nullptr,0,0)<0){BCryptCloseAlgorithmProvider(algorithm_,0);throw ValidationFailure(ValidationError::HashFailed);}
    }
    ~Hash(){if(hash_)BCryptDestroyHash(hash_);if(algorithm_)BCryptCloseAlgorithmProvider(algorithm_,0);}
    Hash(const Hash&)=delete;Hash& operator=(const Hash&)=delete;
    void Add(std::span<const std::byte> b) {
        while(!b.empty()) { const size_t n=std::min(b.size(),size_t{0x100000});if(BCryptHashData(hash_,reinterpret_cast<PUCHAR>(const_cast<std::byte*>(b.data())),static_cast<ULONG>(n),0)<0)throw ValidationFailure(ValidationError::HashFailed);b=b.subspan(n); }
    }
    Digest Finish(){Digest d{};if(BCryptFinishHash(hash_,reinterpret_cast<PUCHAR>(d.data()),32,0)<0)throw ValidationFailure(ValidationError::HashFailed);return d;}
};
Digest Sha256Bytes(std::span<const std::byte> bytes){Hash h;h.Add(bytes);return h.Finish();}
Digest Sha256File(const std::filesystem::path& path) {
    std::ifstream file(path,std::ios::binary);if(!file)throw ValidationFailure(ValidationError::FileIo);
    Hash h;std::array<std::byte,65536> b{};
    while(file) {file.read(reinterpret_cast<char*>(b.data()),static_cast<std::streamsize>(b.size()));h.Add(std::span(b).first(static_cast<size_t>(file.gcount())));}
    if(!file.eof())throw ValidationFailure(ValidationError::FileIo);
    return h.Finish();
}
bool IsSupportedBuild(const Digest& digest) noexcept { for(size_t i=0;i<32;++i)if(digest[i]!=std::byte(generated::kExecutableSha256[i]))return false;return true; }
}
