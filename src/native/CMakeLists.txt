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
# DisableThreadLibraryCalls is incompatible with the static CRT (Microsoft documentation).
# Use the shared CRT; operators need the current Visual C++ x64 runtime.
set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>DLL")

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

add_library(vic3_common STATIC common/Sha256.cpp common/PeImage.cpp common/TargetResolver.cpp)
target_compile_definitions(vic3_common PUBLIC WIN32_LEAN_AND_MEAN NOMINMAX)
target_link_libraries(vic3_common PUBLIC bcrypt vic3_generated)
vic3_set_warnings(vic3_common)
function(vic3_test name file)
  add_executable(${name} tests/${file})
  target_link_libraries(${name} PRIVATE vic3_common)
  vic3_set_warnings(${name})
  add_test(NAME ${name} COMMAND ${name})
endfunction()
vic3_test(NativeResolverTests TargetResolverTests.cpp)

target_sources(vic3_common PRIVATE common/V3pfFormat.cpp common/EventBuffer.cpp common/TraceWriter.cpp)
add_executable(NativeFormatTests tests/V3pfFormatTests.cpp)
target_link_libraries(NativeFormatTests PRIVATE vic3_common)
vic3_set_warnings(NativeFormatTests)
add_test(NAME NativeFormatTests COMMAND NativeFormatTests
  ${CMAKE_CURRENT_SOURCE_DIR}/../../research/generated/native-profiler-v1-golden/trace-v1.bin
  ${CMAKE_CURRENT_BINARY_DIR}/runtime-format.v3pf)
vic3_test(NativeBufferTests EventBufferTests.cpp)
find_package(Python3 REQUIRED COMPONENTS Interpreter)
add_test(NAME NativePythonCompatibility COMMAND ${Python3_EXECUTABLE}
  ${CMAKE_CURRENT_SOURCE_DIR}/tests/CheckTrace.py ${CMAKE_CURRENT_BINARY_DIR}/runtime-format.v3pf)
set_tests_properties(NativePythonCompatibility PROPERTIES DEPENDS NativeFormatTests)

add_library(vic3_hooks STATIC profiler/TickTaskHooks.cpp profiler/MinHookBackend.cpp)
target_link_libraries(vic3_hooks PUBLIC vic3_common vic3_minhook)
vic3_set_warnings(vic3_hooks)
add_library(vic3_runtime STATIC profiler/ProfilerRuntime.cpp)
target_link_libraries(vic3_runtime PUBLIC vic3_hooks)
vic3_set_warnings(vic3_runtime)
add_library(Vic3OptimizationProfiler SHARED profiler/DllMain.cpp)
target_link_libraries(Vic3OptimizationProfiler PRIVATE vic3_runtime)
vic3_set_warnings(Vic3OptimizationProfiler)
add_executable(NativeRuntimeTests tests/ProfilerRuntimeTests.cpp)
target_link_libraries(NativeRuntimeTests PRIVATE vic3_runtime)
vic3_set_warnings(NativeRuntimeTests)
add_test(NAME NativeRuntimeTests COMMAND NativeRuntimeTests $<TARGET_FILE:Vic3OptimizationProfiler>)

add_executable(NativeHookTests tests/TickTaskHookTests.cpp)
target_link_libraries(NativeHookTests PRIVATE vic3_hooks)
vic3_set_warnings(NativeHookTests)
add_test(NAME NativeHookTests COMMAND NativeHookTests ${CMAKE_CURRENT_BINARY_DIR}/hook-format.v3pf)
add_test(NAME NativeHookPythonCompatibility COMMAND ${Python3_EXECUTABLE}
  ${CMAKE_CURRENT_SOURCE_DIR}/tests/CheckTrace.py ${CMAKE_CURRENT_BINARY_DIR}/hook-format.v3pf)
set_tests_properties(NativeHookPythonCompatibility PROPERTIES DEPENDS NativeHookTests)

add_library(vic3_injector STATIC loader/Injector.cpp)
target_link_libraries(vic3_injector PUBLIC vic3_common)
vic3_set_warnings(vic3_injector)
add_executable(Vic3OptimizationLoader loader/Main.cpp)
target_link_libraries(Vic3OptimizationLoader PRIVATE vic3_injector)
vic3_set_warnings(Vic3OptimizationLoader)
add_executable(InjectorHost tests/InjectorHost.cpp)
target_link_libraries(InjectorHost PRIVATE vic3_common)
vic3_set_warnings(InjectorHost)
add_library(InjectionProbe SHARED tests/InjectionProbe.cpp)
target_compile_definitions(InjectionProbe PRIVATE WIN32_LEAN_AND_MEAN NOMINMAX)
vic3_set_warnings(InjectionProbe)
add_executable(NativeInjectorTests tests/InjectorTests.cpp)
target_link_libraries(NativeInjectorTests PRIVATE vic3_injector)
vic3_set_warnings(NativeInjectorTests)
add_test(NAME NativeInjectorTests COMMAND NativeInjectorTests $<TARGET_FILE:InjectorHost> $<TARGET_FILE:InjectionProbe> $<TARGET_FILE:Vic3OptimizationLoader>)
set_tests_properties(NativeRuntimeTests NativeInjectorTests PROPERTIES TIMEOUT 90)
