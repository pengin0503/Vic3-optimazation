#pragma once
#include "../common/Validation.h"
#include "../profiler/ProfilerRuntime.h"
#include <filesystem>
#include <string>
#include <vector>
#include <set>
#include <limits>
#ifdef _WIN32
#include <windows.h>
#endif
namespace vic3 {
struct LoaderArgs {uint32_t pid{},target_mask{7};bool stop{},disabled{},partial{};std::filesystem::path dll,output;};
struct ArgsResult {LoaderArgs value;bool valid{};explicit operator bool()const noexcept{return valid;}};
inline ArgsResult ParseLoaderArgs(const std::vector<std::wstring>& args) {
    LoaderArgs result;std::set<std::wstring> seen;
    for(size_t i=0;i<args.size();++i) {
        const auto& option=args[i];if(!seen.insert(option).second)return {};
        if(option==L"--stop")result.stop=true;
        else if(option==L"--disabled")result.disabled=true;
        else if(option==L"--allow-partial-targets")result.partial=true;
        else if(option==L"--pid" || option==L"--dll" || option==L"--output" || option==L"--targets") {
            if(++i==args.size() || args[i].empty())return {};
            const auto& value=args[i];
            if(option==L"--pid") {
                uint64_t pid=0;
                for(wchar_t c:value){if(c<L'0' || c>L'9')return {};pid=pid*10+static_cast<uint32_t>(c-L'0');if(pid>std::numeric_limits<uint32_t>::max())return {};}
                if(!pid)return {};
                result.pid=static_cast<uint32_t>(pid);
            } else if(option==L"--dll")result.dll=value;
            else if(option==L"--output")result.output=value;
            else {
                result.target_mask=0;size_t begin=0;
                while(begin<value.size()) {
                    const size_t comma=value.find(L',',begin);const auto name=value.substr(begin,comma==std::wstring::npos?comma:comma-begin);
                    uint32_t bit=0;if(name==L"investment")bit=1;else if(name==L"migration")bit=2;else if(name==L"employment")bit=4;else return {};
                    if(result.target_mask&bit)return {};
                    result.target_mask|=bit;
                    if(comma==std::wstring::npos)break;
                    begin=comma+1;if(begin==value.size())return {};
                }
            }
        } else return {};
    }
    if(!result.pid || (result.stop && seen.size()!=2))return {};
    return {result,true};
}
inline int StopResult(RuntimeStatus status) noexcept {return status==RuntimeStatus::Stopped?0:1;}
#ifdef _WIN32
RuntimeStatus StopProfilerSession(DWORD pid,DWORD timeout_ms=35000);
#endif
enum class InjectionError {None,InvalidPath,UnsupportedProcess,UnsupportedBuild,ModuleResolution,RemoteAllocation,RemoteWrite,RemoteThread,Timeout,LoadFailed};
#ifdef _WIN32
std::filesystem::path ProcessImagePath(HANDLE process);
InjectionError ValidateVictoriaProcess(HANDLE process,const std::filesystem::path& path);
// Private native primitive. The production CLI always passes the exact Victoria gate first.
InjectionError InjectLibraryForValidatedProcess(HANDLE process,DWORD pid,const std::filesystem::path& dll);
#endif
}
