#include "TraceWriter.h"
#include <stdexcept>
namespace vic3 {
void TraceWriter::Open(const std::filesystem::path& path,const std::string& metadata,uint64_t frequency,uint64_t start,std::span<const uint8_t,32> target_hash) {
    auto header=EncodeHeader(metadata,frequency,start,target_hash,0,0);
    // Refuse to overwrite any previous capture.
    if(std::filesystem::exists(path))throw std::runtime_error("trace already exists");
    file_.open(path,std::ios::binary|std::ios::out|std::ios::in|std::ios::trunc);
    if(!file_)throw std::runtime_error("cannot open trace");
    file_.write(reinterpret_cast<const char*>(header.data()),static_cast<std::streamsize>(header.size()));
    if(!file_)throw std::runtime_error("cannot write trace header");
}
bool TraceWriter::Write(const WireRecord& record) {
    if(!record.size)return false;
    if(file_)file_.write(reinterpret_cast<const char*>(record.bytes.data()),record.size);
    if(!file_){++io_drops_;return false;}return true;
}
bool TraceWriter::Drain(EventBufferPool& pool) {
    bool ok=true;WireRecord record;
    // Bounded per cycle even when producers continuously fill their buffers.
    for(auto& buffer:pool.Buffers())for(size_t i=0;i<1024 && buffer.TryRead(record);++i)if(!Write(record))ok=false;
    return ok;
}
bool TraceWriter::Finalize(uint64_t dropped) {
    std::array<std::byte,8> b{};PutLittle(b,0,dropped+io_drops_,8);
    if(file_){file_.seekp(104);file_.write(reinterpret_cast<const char*>(b.data()),8);file_.flush();}
    const bool ok=bool(file_);file_.close();return ok;
}
}
