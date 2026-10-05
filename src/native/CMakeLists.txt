cmake_minimum_required(VERSION 3.25)

project(Vic3OptimizationNative LANGUAGES C CXX)

# Victoria 3 1.14.5 is a Windows x64 executable; the loader, the profiler DLL
# and their tests are meaningful only there.
if(NOT WIN32)
  message(FATAL_ERROR
    "Vic3 native profiler supports only Windows x64 builds. "
    "Configure on Windows with Visual Studio 2022: cmake -S src/native -B build/native -A x64")
endif()
if(NOT CMAKE_SIZEOF_VOID_P EQUAL 8)
  message(FATAL_ERROR
    "Vic3 native profiler supports only x64 (pointer size 8); configure with -A x64.")
endif()

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
# Static CRT: the injected DLL must not depend on a redistributable being present.
set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>")

list(APPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_SOURCE_DIR}/cmake")
include(CompilerWarnings)
include(FetchContent)

# MinHook is pinned to an exact commit and built from source by this project;
# its own CMake project is intentionally not added (SOURCE_SUBDIR has no CMakeLists).
# License: third_party/licenses/MinHook.txt
set(VIC3_MINHOOK_COMMIT c3fcafdc10146beb5919319d0683e44e3c30d537)
FetchContent_Declare(minhook
  GIT_REPOSITORY https://github.com/TsudaKageyu/minhook.git
  GIT_TAG ${VIC3_MINHOOK_COMMIT}
  SOURCE_SUBDIR vic3-do-not-add-upstream-cmake)
FetchContent_MakeAvailable(minhook)

add_library(vic3_minhook STATIC
  ${minhook_SOURCE_DIR}/src/buffer.c
  ${minhook_SOURCE_DIR}/src/hook.c
  ${minhook_SOURCE_DIR}/src/trampoline.c
  ${minhook_SOURCE_DIR}/src/hde/hde64.c)
target_include_directories(vic3_minhook PUBLIC ${minhook_SOURCE_DIR}/include)

# Generated exact-build target table (tools/render_native_profiler_targets.py).
add_library(vic3_generated INTERFACE)
target_include_directories(vic3_generated INTERFACE ${CMAKE_CURRENT_SOURCE_DIR}/generated)

if(MINGW)
  # Self-contained binaries: no libstdc++/libgcc/winpthread DLL dependencies.
  add_link_options(-static -static-libgcc -static-libstdc++)
endif()

enable_testing()
