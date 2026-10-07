// lookup_contract_runner [--seed <uint32>] [--rebuilds <1..100000>] --output <path>
//
// Exit codes: 0 every check agreed; 1 the contract check failed (the JSON is
// still written); 2 usage error; 3 output I/O failure.
#include <cstdint>
#include <cstring>
#include <exception>
#include <fstream>
#include <iostream>
#include <limits>
#include <optional>
#include <string>

#include "ContractRunner.h"

namespace {

constexpr int kExitFailed = 1;
constexpr int kExitUsage = 2;
constexpr int kExitIo = 3;

constexpr const char* kUsage =
    "usage: lookup_contract_runner [--seed <uint32>] [--rebuilds <1..100000>] --output <path>\n";

// Strict unsigned decimal: digits only, no sign or whitespace, no overflow.
std::optional<std::uint64_t> ParseUnsigned(const char* text, std::uint64_t max) {
    if (text == nullptr || *text == '\0') {
        return std::nullopt;
    }
    std::uint64_t value = 0;
    for (const char* p = text; *p != '\0'; ++p) {
        if (*p < '0' || *p > '9') {
            return std::nullopt;
        }
        const auto digit = static_cast<std::uint64_t>(*p - '0');
        if (value > (max - digit) / 10) {
            return std::nullopt;
        }
        value = value * 10 + digit;
    }
    return value;
}

int Usage(const std::string& message) {
    std::cerr << "error: " << message << "\n" << kUsage;
    return kExitUsage;
}

}  // namespace

int main(int argc, char** argv) {
    namespace runner = lookup_contract::runner;
    if (argc == 2 && std::strcmp(argv[1], "--help") == 0) {
        std::cout << kUsage;
        return 0;
    }
    runner::RunConfig config;
    bool have_seed = false;
    bool have_rebuilds = false;
    const char* output = nullptr;

    // Every option takes exactly one value.
    for (int i = 1; i < argc; i += 2) {
        const char* option = argv[i];
        const char* value = i + 1 < argc ? argv[i + 1] : nullptr;
        if (std::strcmp(option, "--seed") == 0) {
            const auto parsed = ParseUnsigned(value, std::numeric_limits<std::uint32_t>::max());
            if (have_seed || !parsed) {
                return Usage("--seed needs one unsigned 32-bit decimal value");
            }
            config.seed = static_cast<std::uint32_t>(*parsed);
            have_seed = true;
        } else if (std::strcmp(option, "--rebuilds") == 0) {
            const auto parsed = ParseUnsigned(value, runner::kMaxRebuilds);
            if (have_rebuilds || !parsed || *parsed == 0) {
                return Usage("--rebuilds needs one decimal value in 1..100000");
            }
            config.rebuilds = static_cast<std::size_t>(*parsed);
            have_rebuilds = true;
        } else if (std::strcmp(option, "--output") == 0) {
            if (output != nullptr || value == nullptr || *value == '\0') {
                return Usage("--output needs one path");
            }
            output = value;
        } else {
            return Usage(std::string("unknown option: ") + option);
        }
    }
    if (output == nullptr) {
        return Usage("--output is required");
    }

    runner::RunSummary summary;
    try {
        summary = runner::RunContract(config);
    } catch (const std::exception& error) {
        std::cerr << "error: runner failed: " << error.what() << "\n";
        return kExitFailed;
    }

    // Binary mode keeps "\n" line endings on every platform.
    std::ofstream file(output, std::ios::binary | std::ios::trunc);
    if (!file) {
        std::cerr << "error: cannot open output: " << output << "\n";
        return kExitIo;
    }
    runner::WriteJson(summary, file);
    file.close();
    if (!file) {
        std::cerr << "error: failed to write output: " << output << "\n";
        return kExitIo;
    }
    return runner::Passed(summary) ? 0 : kExitFailed;
}
