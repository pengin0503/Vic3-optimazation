#pragma once
#include "EventBuffer.h"
#include <filesystem>
#include <fstream>
namespace vic3 {
// Owned by the profiler control/flush thread. Never called by a detour.
class TraceWriter {
    std::fstream file_;uint64_t io_drops_{};
public:
    void Open(const std::filesystem::path& path,const std::string& metadata,uint64_t frequency,uint64_t start,std::span<const uint8_t,32> target_hash);
    bool Write(const WireRecord& event);
    bool Drain(EventBufferPool& pool);
    bool Finalize(uint64_t dropped);
};
}
