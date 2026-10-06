// Minimal test runner: runs all registered tests, or exactly one with
// --filter <exact-name>. --list prints the registered names. An unknown filter
// or option exits non-zero.
#include <cstring>
#include <exception>
#include <iostream>
#include <string>
#include <utility>
#include <vector>

#include "TestSupport.h"

namespace lookup_reuse::test {
namespace {

std::vector<std::pair<std::string, void (*)()>>& Registry() {
    static std::vector<std::pair<std::string, void (*)()>> registry;
    return registry;
}

}  // namespace

void RegisterTest(const char* name, void (*test)()) { Registry().emplace_back(name, test); }

void FailCheck(const char* expression, const char* file, int line) {
    throw CheckFailure(std::string(file) + ":" + std::to_string(line) + ": CHECK(" + expression +
                       ") failed");
}

std::vector<std::byte> RawSlots(std::size_t slot_count) {
    return std::vector<std::byte>(slot_count * kSlotStride, std::byte{0});
}

void PutSlot(std::vector<std::byte>& raw, std::size_t index, std::uint8_t control,
             std::uint32_t key) {
    const std::size_t base = index * kSlotStride;
    if (base + kSlotStride > raw.size()) {
        throw CheckFailure("PutSlot index outside raw fixture");
    }
    raw[base + kControlOffset] = std::byte{control};
    for (std::size_t i = 0; i < 4; ++i) {
        raw[base + kKeyOffset + i] = std::byte{static_cast<unsigned char>((key >> (8 * i)) & 0xffu)};
    }
}

std::unique_ptr<OwnedTableFixture> MakeFixture(const TableIdentity& identity, std::uint64_t mask,
                                               const std::vector<std::byte>& raw) {
    auto created = OwnedTableFixture::Create(identity, mask, raw.size() / kSlotStride, raw);
    if (auto* error = std::get_if<ViewError>(&created)) {
        throw CheckFailure("MakeFixture: fixture rejected with ViewError " +
                           std::to_string(static_cast<int>(*error)));
    }
    return std::move(std::get<std::unique_ptr<OwnedTableFixture>>(created));
}

ViewError ExpectRejected(const TableIdentity& identity, std::uint64_t mask,
                         std::uint64_t slot_count, const std::vector<std::byte>& raw) {
    auto created = OwnedTableFixture::Create(identity, mask, slot_count, raw);
    if (auto* error = std::get_if<ViewError>(&created)) {
        return *error;
    }
    throw CheckFailure("ExpectRejected: fixture was accepted");
}

}  // namespace lookup_reuse::test

int main(int argc, char** argv) {
    using lookup_reuse::test::Registry;
    const char* filter = nullptr;
    for (int i = 1; i < argc; ++i) {
        if (std::strcmp(argv[i], "--list") == 0) {
            for (const auto& entry : Registry()) {
                std::cout << entry.first << '\n';
            }
            return 0;
        }
        if (std::strcmp(argv[i], "--filter") == 0 && i + 1 < argc && filter == nullptr) {
            filter = argv[++i];
            continue;
        }
        std::cerr << "unknown or malformed argument: " << argv[i] << '\n';
        return 2;
    }

    int run = 0;
    int failed = 0;
    for (const auto& [name, test] : Registry()) {
        if (filter != nullptr && name != filter) {
            continue;
        }
        ++run;
        try {
            test();
            std::cout << "[PASS] " << name << '\n';
        } catch (const std::exception& error) {
            ++failed;
            std::cout << "[FAIL] " << name << ": " << error.what() << '\n';
        } catch (...) {
            ++failed;
            std::cout << "[FAIL] " << name << ": unknown exception\n";
        }
    }
    if (filter != nullptr && run == 0) {
        std::cerr << "no test named: " << filter << '\n';
        return 2;
    }
    std::cout << run - failed << "/" << run << " tests passed\n";
    return failed == 0 ? 0 : 1;
}
