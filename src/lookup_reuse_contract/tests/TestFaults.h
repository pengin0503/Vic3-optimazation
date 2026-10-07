// Test-only fault seam for the B0 contract.
//
// Exists only in binaries compiled with LOOKUP_CONTRACT_TESTING (the
// lookup_contract_test_core library and the unit test executable). The
// production core, runner, CLI and release artifacts are built without it,
// and CTest checks that this header and the seam members do not compile there.
#pragma once

#ifndef LOOKUP_CONTRACT_TESTING
#error "TestFaults.h requires LOOKUP_CONTRACT_TESTING (test binaries only)"
#endif

#include <cstddef>
#include <cstdint>
#include <optional>

#include "NativeShadow.h"

namespace lookup_contract::testing {

// Defined in the test variant of the core only.
std::uint64_t ExchangeGenerationCounterForTest(std::uint64_t value) noexcept;
std::uint64_t ExchangeSessionCounterForTest(std::uint64_t value) noexcept;

struct FaultAccess {
    // Replaces the candidate slot after the hint produced one and before the
    // comparison. The original callback, fixture validation and normalization
    // are not touched.
    static void OverrideCandidate(OfflineNativeShadow& shadow, std::optional<std::size_t> slot) noexcept {
        shadow.fault_candidate_override_ = slot;
    }
    static void SetLastScopeId(OfflineNativeShadow& shadow, std::uint64_t value) noexcept {
        shadow.last_scope_id_ = value;
    }
};

}  // namespace lookup_contract::testing
