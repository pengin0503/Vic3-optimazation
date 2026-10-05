#pragma once
#include "PeImage.h"
#include "../generated/targets_1_14_5.inc"
namespace vic3 {
ValidationResult<uintptr_t> ResolveTarget(const PeImage& image,const generated::GeneratedTargetSpec& spec) noexcept;
}
