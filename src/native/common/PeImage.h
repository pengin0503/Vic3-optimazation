#pragma once
#include "Validation.h"
#include <cstddef>
#include <cstdint>
#include <span>
#include <vector>
#ifdef _WIN32
#include <windows.h>
#endif
namespace vic3 {
bool CheckedAddress(uintptr_t base, size_t offset, uintptr_t& out) noexcept;
struct ImageSection { size_t rva{}, size{}; bool scan_text{}; };
class PeImage {
public:
    static ValidationResult<PeImage> FromMapped(std::span<const std::byte> image);
#ifdef _WIN32
    static ValidationResult<PeImage> FromModule(HMODULE module);
#endif
    bool Readable(size_t rva,size_t size) const noexcept;
    bool ExecutableText(size_t rva,size_t size=1) const noexcept;
    uintptr_t Address(size_t rva) const noexcept;
    std::span<const std::byte> bytes{};
    std::vector<ImageSection> sections;
private:
    bool check_pages_{};
};
}
