// Test-only helpers for the portable lookup reuse core.
//
// CHECK throws instead of relying on <cassert>, so failures are reported in
// Release (NDEBUG) builds as well. Raw fixtures are written slot by slot with
// hand-chosen values; nothing here derives expected slots from the reference
// search or the hash.
#pragma once

#include <cstddef>
#include <cstdint>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>

#include "TableView.h"

namespace lookup_reuse::test {

class CheckFailure : public std::runtime_error {
public:
    using std::runtime_error::runtime_error;
};

void RegisterTest(const char* name, void (*test)());

[[noreturn]] void FailCheck(const char* expression, const char* file, int line);

std::vector<std::byte> RawSlots(std::size_t slot_count);

void PutSlot(std::vector<std::byte>& raw, std::size_t index, std::uint8_t control,
             std::uint32_t key);

// Builds a fixture whose slot count is raw.size() / kSlotStride. A validation
// error is reported as a test failure.
std::unique_ptr<OwnedTableFixture> MakeFixture(const TableIdentity& identity, std::uint64_t mask,
                                               const std::vector<std::byte>& raw);

// Returns the ViewError of a rejected Create call, or fails the test when the
// input was accepted.
ViewError ExpectRejected(const TableIdentity& identity, std::uint64_t mask,
                         std::uint64_t slot_count, const std::vector<std::byte>& raw);

struct Registrar {
    Registrar(const char* name, void (*test)()) { RegisterTest(name, test); }
};

}  // namespace lookup_reuse::test

#define CHECK(expression)                                                          \
    do {                                                                           \
        if (!(expression)) {                                                       \
            ::lookup_reuse::test::FailCheck(#expression, __FILE__, __LINE__);      \
        }                                                                          \
    } while (false)

#define LOOKUP_TEST(name)                                                          \
    static void name();                                                            \
    static const ::lookup_reuse::test::Registrar name##_registrar{#name, &name};  \
    static void name()
