#pragma once
#include "Validation.h"
#include <array>
#include <cstddef>
#include <filesystem>
#include <span>
namespace vic3 {
using Digest=std::array<std::byte,32>;
Digest Sha256File(const std::filesystem::path& path);
Digest Sha256Bytes(std::span<const std::byte> bytes);
bool IsSupportedBuild(const Digest& digest) noexcept;
}
