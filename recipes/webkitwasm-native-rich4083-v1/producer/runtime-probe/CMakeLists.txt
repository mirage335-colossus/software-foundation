cmake_minimum_required(VERSION 3.24)
project(FoundationNativePrivateRuntimeProbe LANGUAGES CXX)

# An explicitly selected, inspect-only DSO. No engine sources, test execution,
# installation, dlopen or dynamic SDK publication belong to this graph.
include("${CMAKE_CURRENT_LIST_DIR}/../native-private-runtime.cmake")
add_library(BibNativeRuntimeProbe SHARED runtime_probe.cpp)
target_compile_features(BibNativeRuntimeProbe PRIVATE cxx_std_23)
target_compile_options(BibNativeRuntimeProbe PRIVATE -fexceptions)
set_target_properties(BibNativeRuntimeProbe PROPERTIES
    OUTPUT_NAME "bib-native-runtime-probe"
    POSITION_INDEPENDENT_CODE ON
    CXX_VISIBILITY_PRESET hidden
    VISIBILITY_INLINES_HIDDEN ON)
bib_apply_private_cpp_runtime(BibNativeRuntimeProbe)

# This is a separate diagnostic C entry, not the provider/Engine ABI. Keep only
# its one ordinary C function public, including with a statically linked runtime.
set(_exports "${CMAKE_CURRENT_BINARY_DIR}/runtime-probe.exports.map")
set(_export_policy "{\n  global: bib_native_runtime_probe_v1;\n  local: *;\n};\n")
if(IS_SYMLINK "${_exports}" OR IS_DIRECTORY "${_exports}")
    message(FATAL_ERROR "Runtime probe refuses a linked or non-file export policy")
elseif(EXISTS "${_exports}")
    # A pre-link CMake regeneration may reuse these exact derived bytes. Never
    # replace a foreign policy or rewrite an existing same-byte input.
    _bib_native_runtime_file("${_exports}" "runtime probe export policy")
    string(LENGTH "${_export_policy}" _expected_bytes)
    file(SIZE "${_exports}" _actual_bytes)
    string(SHA256 _expected_sha "${_export_policy}")
    file(SHA256 "${_exports}" _actual_sha)
    if(NOT _actual_bytes EQUAL _expected_bytes OR NOT _actual_sha STREQUAL _expected_sha)
        message(FATAL_ERROR "Runtime probe refuses an existing different export policy")
    endif()
else()
    file(WRITE "${_exports}" "${_export_policy}")
endif()
target_link_options(BibNativeRuntimeProbe PRIVATE "LINKER:--version-script,${_exports}")
set_property(TARGET BibNativeRuntimeProbe APPEND PROPERTY LINK_DEPENDS "${_exports}")
