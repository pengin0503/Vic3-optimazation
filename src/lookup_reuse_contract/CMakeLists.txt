cmake_minimum_required(VERSION 3.25)

# B0 offline native shadow contract. Platform-neutral C++20 on owned fixtures
# only; it depends on the Stage A core and never builds the native loader,
# DLL, hooks or any Windows SDK / MinHook code.
project(lookup_reuse_contract LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

option(LOOKUP_CONTRACT_WARNINGS_AS_ERRORS "Treat compiler warnings as errors" OFF)
# Stage A follows the same warning policy when built as part of B0.
set(LOOKUP_REUSE_WARNINGS_AS_ERRORS ${LOOKUP_CONTRACT_WARNINGS_AS_ERRORS} CACHE BOOL "" FORCE)

enable_testing()
add_subdirectory(../lookup_reuse stage-a)

function(lookup_contract_warnings target)
  if(MSVC)
    target_compile_options(${target} PRIVATE /W4 /permissive- /EHsc)
    if(LOOKUP_CONTRACT_WARNINGS_AS_ERRORS)
      target_compile_options(${target} PRIVATE /WX)
    endif()
  else()
    target_compile_options(${target} PRIVATE -Wall -Wextra -Wpedantic)
    if(LOOKUP_CONTRACT_WARNINGS_AS_ERRORS)
      target_compile_options(${target} PRIVATE -Werror)
    endif()
  endif()
endfunction()

set(LOOKUP_CONTRACT_CORE_SOURCES
  core/NativeFixture.cpp
  core/ResultNormalization.cpp
  core/NativeShadow.cpp
)

# Production core: what the runner links. No fault seam.
add_library(lookup_contract_core STATIC ${LOOKUP_CONTRACT_CORE_SOURCES})
target_include_directories(lookup_contract_core PUBLIC include generated PRIVATE core)
target_link_libraries(lookup_contract_core PUBLIC lookup_reuse_core)
lookup_contract_warnings(lookup_contract_core)

# Test variant of the same sources with the private fault seam. Only the unit
# test executable links it; the two variants never share a binary.
add_library(lookup_contract_test_core STATIC ${LOOKUP_CONTRACT_CORE_SOURCES})
target_include_directories(lookup_contract_test_core PUBLIC include generated PRIVATE core)
target_compile_definitions(lookup_contract_test_core PUBLIC LOOKUP_CONTRACT_TESTING=1)
target_link_libraries(lookup_contract_test_core PUBLIC lookup_reuse_core)
lookup_contract_warnings(lookup_contract_test_core)

set(STAGE_A_TEST_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../lookup_reuse/tests")

add_executable(lookup_contract_tests
  ${STAGE_A_TEST_DIR}/TestMain.cpp
  tests/NativeFixtureTests.cpp
  tests/ResultNormalizationTests.cpp
  tests/NativeShadowTests.cpp
  tests/AllocationTests.cpp
)
target_include_directories(lookup_contract_tests PRIVATE tests ${STAGE_A_TEST_DIR})
target_link_libraries(lookup_contract_tests PRIVATE lookup_contract_test_core)
lookup_contract_warnings(lookup_contract_tests)

add_test(NAME lookup_contract_unit_tests COMMAND lookup_contract_tests)
add_test(NAME lookup_contract_tests_unknown_filter_fails
         COMMAND lookup_contract_tests --filter no_such_test)
set_tests_properties(lookup_contract_tests_unknown_filter_fails PROPERTIES WILL_FAIL TRUE)

# The fault seam must not compile against the production core: neither the
# header nor its private members. Each target is built on demand by CTest and
# must fail with the named diagnostic.
foreach(negative faults_header seam_member)
  add_executable(lookup_contract_negative_${negative} EXCLUDE_FROM_ALL tests/negative/${negative}.cpp)
  target_include_directories(lookup_contract_negative_${negative} PRIVATE tests ${STAGE_A_TEST_DIR})
  target_link_libraries(lookup_contract_negative_${negative} PRIVATE lookup_contract_core)
  add_test(NAME lookup_contract_negative_${negative}
           COMMAND ${CMAKE_COMMAND} --build ${CMAKE_BINARY_DIR}
                   --target lookup_contract_negative_${negative} --config $<CONFIG>)
endforeach()
set_tests_properties(lookup_contract_negative_faults_header PROPERTIES
  PASS_REGULAR_EXPRESSION "requires LOOKUP_CONTRACT_TESTING")
set_tests_properties(lookup_contract_negative_seam_member PROPERTIES
  PASS_REGULAR_EXPRESSION "fault_candidate_override_")
