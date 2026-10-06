cmake_minimum_required(VERSION 3.25)

# Portable offline lookup reuse core (Stage A). Platform-neutral C++20 with no
# external dependencies; it never builds the native loader, DLL or hooks.
project(lookup_reuse LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

option(LOOKUP_REUSE_WARNINGS_AS_ERRORS "Treat compiler warnings as errors" OFF)

function(lookup_reuse_warnings target)
  if(MSVC)
    target_compile_options(${target} PRIVATE /W4 /permissive- /EHsc)
    if(LOOKUP_REUSE_WARNINGS_AS_ERRORS)
      target_compile_options(${target} PRIVATE /WX)
    endif()
  else()
    target_compile_options(${target} PRIVATE -Wall -Wextra -Wpedantic)
    if(LOOKUP_REUSE_WARNINGS_AS_ERRORS)
      target_compile_options(${target} PRIVATE -Werror)
    endif()
  endif()
endfunction()

add_library(lookup_reuse_core STATIC
  core/TableView.cpp
  core/PositiveSlotHint.cpp
  core/ShadowComparison.cpp
)
target_include_directories(lookup_reuse_core PUBLIC include)
lookup_reuse_warnings(lookup_reuse_core)

# Runner library: fixture generation, differential comparison and JSON. The
# core never includes runner headers.
add_library(lookup_reuse_runner_lib STATIC
  runner/OfflineRunner.cpp
)
target_include_directories(lookup_reuse_runner_lib PUBLIC runner)
target_link_libraries(lookup_reuse_runner_lib PUBLIC lookup_reuse_core)
lookup_reuse_warnings(lookup_reuse_runner_lib)

add_executable(lookup_reuse_runner runner/main.cpp)
target_link_libraries(lookup_reuse_runner PRIVATE lookup_reuse_runner_lib)
lookup_reuse_warnings(lookup_reuse_runner)

enable_testing()

add_executable(lookup_reuse_tests
  tests/TestMain.cpp
  tests/TableViewTests.cpp
  tests/PositiveSlotHintTests.cpp
  tests/ShadowComparisonTests.cpp
  tests/OfflineRunnerTests.cpp
)
target_include_directories(lookup_reuse_tests PRIVATE tests)
target_link_libraries(lookup_reuse_tests PRIVATE lookup_reuse_runner_lib)
lookup_reuse_warnings(lookup_reuse_tests)

add_test(NAME lookup_reuse_core_tests COMMAND lookup_reuse_tests)
add_test(NAME lookup_reuse_tests_list COMMAND lookup_reuse_tests --list)
add_test(NAME lookup_reuse_tests_unknown_filter_fails
         COMMAND lookup_reuse_tests --filter no_such_test)
set_tests_properties(lookup_reuse_tests_unknown_filter_fails PROPERTIES WILL_FAIL TRUE)

# JSON / CLI checks need a Python interpreter. Without one they are registered
# as explicitly skipped tests rather than silently omitted.
set(LOOKUP_REUSE_EXPECTED_RESULTS
    "${CMAKE_CURRENT_SOURCE_DIR}/../../research/generated/lookup-reuse-core/results.json")
find_package(Python3 COMPONENTS Interpreter)
if(Python3_Interpreter_FOUND)
  add_test(NAME json_roundtrip_and_cli_rejection
           COMMAND Python3::Interpreter "${CMAKE_CURRENT_SOURCE_DIR}/tests/VerifyRunner.py"
                   $<TARGET_FILE:lookup_reuse_runner>)
  if(EXISTS "${LOOKUP_REUSE_EXPECTED_RESULTS}")
    add_test(NAME runner_matches_committed_results
             COMMAND Python3::Interpreter "${CMAKE_CURRENT_SOURCE_DIR}/tests/VerifyRunner.py"
                     $<TARGET_FILE:lookup_reuse_runner> --expected "${LOOKUP_REUSE_EXPECTED_RESULTS}")
  endif()
else()
  message(WARNING "Python3 interpreter not found: JSON/CLI runner checks are skipped")
  foreach(skipped json_roundtrip_and_cli_rejection runner_matches_committed_results)
    add_test(NAME ${skipped} COMMAND ${CMAKE_COMMAND} -E echo "SKIPPED: Python3 not found")
    set_tests_properties(${skipped} PROPERTIES SKIP_REGULAR_EXPRESSION "SKIPPED")
  endforeach()
endif()
