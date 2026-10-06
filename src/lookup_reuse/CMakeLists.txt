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
)
target_include_directories(lookup_reuse_core PUBLIC include)
lookup_reuse_warnings(lookup_reuse_core)

enable_testing()

add_executable(lookup_reuse_tests
  tests/TestMain.cpp
  tests/TableViewTests.cpp
  tests/PositiveSlotHintTests.cpp
)
target_include_directories(lookup_reuse_tests PRIVATE tests)
target_link_libraries(lookup_reuse_tests PRIVATE lookup_reuse_core)
lookup_reuse_warnings(lookup_reuse_tests)

add_test(NAME lookup_reuse_core_tests COMMAND lookup_reuse_tests)
add_test(NAME lookup_reuse_tests_list COMMAND lookup_reuse_tests --list)
add_test(NAME lookup_reuse_tests_unknown_filter_fails
         COMMAND lookup_reuse_tests --filter no_such_test)
set_tests_properties(lookup_reuse_tests_unknown_filter_fails PROPERTIES WILL_FAIL TRUE)
