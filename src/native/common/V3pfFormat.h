#pragma once
#include "../generated/targets_1_14_5.inc"
#include <array>
#include <cstddef>
#include <cstdint>
#include <span>
#include <string>
#include <vector>
namespace vic3 {
struct Event {
    uint64_t timestamp{};uint32_t thread{};uint16_t type{};uint32_t target{},sequence{};uint64_t correlation{};
    uint32_t status{};uint64_t range_begin{},range_end{},range_length{};uint16_t task_threads{};uint8_t decision{};uint32_t reason_flags{},work_count{};
    uint16_t wait_kind{};uint64_t object_token{};uint32_t counter_id{};int64_t value{};
};
struct WireRecord {std::array<std::byte,72> bytes{};uint16_t size{};};
void PutLittle(std::span<std::byte> bytes,size_t offset,uint64_t value,size_t width) noexcept;
WireRecord EncodeEvent(const Event& event) noexcept;
std::vector<std::byte> EncodeHeader(const std::string& metadata,uint64_t frequency,uint64_t start,std::span<const uint8_t,32> target_hash,uint32_t flags,uint64_t dropped);
std::string RuntimeMetadata(uint32_t enabled_mask,bool disabled);
}
