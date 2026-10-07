#pragma once
#include <windows.h>
#include <utility>
namespace vic3 {
class WinHandle {
    HANDLE handle_{};
public:
    WinHandle()=default;explicit WinHandle(HANDLE h):handle_(h){};
    ~WinHandle(){if(*this)CloseHandle(handle_);}
    WinHandle(const WinHandle&)=delete;WinHandle& operator=(const WinHandle&)=delete;
    WinHandle(WinHandle&& other) noexcept:handle_(std::exchange(other.handle_,nullptr)){}
    WinHandle& operator=(WinHandle&& other) noexcept {if(this!=&other){if(*this)CloseHandle(handle_);handle_=std::exchange(other.handle_,nullptr);}return *this;}
    explicit operator bool() const noexcept {return handle_ && handle_!=INVALID_HANDLE_VALUE;}
    HANDLE get() const noexcept{return handle_;}
    HANDLE release() noexcept{return std::exchange(handle_,nullptr);}
};
class MappedView {
    void* pointer_{};
public:
    explicit MappedView(void* p):pointer_(p){}~MappedView(){if(pointer_)UnmapViewOfFile(pointer_);}
    MappedView(const MappedView&)=delete;MappedView& operator=(const MappedView&)=delete;
    void* get() const noexcept{return pointer_;}
};
}
