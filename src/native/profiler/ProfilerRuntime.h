#pragma once
#include <cstdint>
#include <filesystem>
namespace vic3 {
enum class RuntimeStatus : int32_t {Pending,Ready,Stopped,ConfigRejected,ValidationFailed,TraceFailed,HookFailed,StopFailed};
#ifdef _WIN32
void RunProfilerRuntime(void* module) noexcept;
#endif
}
