# Two harness translation units plus exact PREBUILT generic static archives.
# No add_subdirectory/include of the Foundation or supplier build is permitted.
# Imported targets have no sources, custom commands or transitive build owners.
if(NOT CMAKE_HOST_SYSTEM_NAME STREQUAL "Windows" OR NOT CMAKE_SYSTEM_NAME STREQUAL "Windows" OR
        NOT MSVC OR NOT CMAKE_CXX_COMPILER_ID STREQUAL "Clang" OR
        NOT CMAKE_CXX_COMPILER_FRONTEND_VARIANT STREQUAL "MSVC" OR
        NOT CMAKE_SIZEOF_VOID_P EQUAL 8 OR NOT CMAKE_CXX_COMPILER_TARGET STREQUAL "x86_64-pc-windows-msvc" OR
        NOT CMAKE_GENERATOR STREQUAL "Ninja" OR NOT CMAKE_BUILD_TYPE STREQUAL "Release" OR
        NOT CMAKE_MSVC_RUNTIME_LIBRARY STREQUAL "MultiThreaded")
    message(FATAL_ERROR "Raw runtime harness requires admitted native Windows x64 clang-cl Release /MT inputs")
endif()
function(_raw_file path sha label)
    string(LENGTH "${sha}" _length)
    if(NOT IS_ABSOLUTE "${path}" OR NOT EXISTS "${path}" OR IS_DIRECTORY "${path}" OR IS_SYMLINK "${path}" OR
            "${path}" MATCHES "[;\"\n\r]" OR "${path}" MATCHES "\\$<" OR
            NOT _length EQUAL 64 OR NOT "${sha}" MATCHES "^[0-9a-f]+$" OR "${sha}" MATCHES "^0+$")
        message(FATAL_ERROR "Raw runtime harness needs exact retained ordinary ${label}; explicit generic-link maintenance is required, no rebuild fallback")
    endif()
    file(SHA256 "${path}" _actual)
    if(NOT _actual STREQUAL sha)
        message(FATAL_ERROR "Retained raw runtime ${label} differs from its independent SHA256")
    endif()
    set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS "${path}")
endfunction()
_raw_file("${BIB_RAW_RUNTIME_GENERIC_MANIFEST}" "${BIB_RAW_RUNTIME_GENERIC_MANIFEST_SHA256}" "generic-link manifest")
file(SIZE "${BIB_RAW_RUNTIME_GENERIC_MANIFEST}" _manifest_bytes)
if(_manifest_bytes GREATER 1048576)
    message(FATAL_ERROR "Raw runtime generic-link manifest exceeds 1MiB")
endif()
file(READ "${BIB_RAW_RUNTIME_GENERIC_MANIFEST}" _manifest)
string(JSON _kind GET "${_manifest}" kind)
string(JSON _schema GET "${_manifest}" schema_version)
string(JSON _target GET "${_manifest}" target)
string(JSON _crt GET "${_manifest}" crt)
if(NOT _kind STREQUAL "foundation-raw-runtime-generic-link-inputs-v1" OR NOT _schema EQUAL 1 OR
        NOT _target STREQUAL "windows-x86_64" OR NOT _crt STREQUAL "static-mt")
    message(FATAL_ERROR "Raw runtime generic-link manifest subject differs")
endif()
set(_roles
    foundation_appended_abi foundation_appended_container foundation_appended_resource_url
    foundation_appended_web_services foundation_appended_document_forms foundation_appended_editor_codec
    foundation_appended_engine_owner foundation_appended_native_engine_driver foundation_appended_native_engine_loader
    foundation_gui_appended_demo_services foundation_gui_appended_document foundation_gui_appended_document_codec
    foundation_gui_appended_document_controller foundation_gui_appended_document_forms
    foundation_gui_appended_document_v2_codec foundation_gui_document_action_v1_codec
    foundation_gui_engine_document_broker foundation_gui_appended_engine_document_application
    foundation_gui_native_engine_document_composition)
string(JSON _count LENGTH "${_manifest}" archives)
list(LENGTH _roles _expected_count)
if(NOT _count EQUAL _expected_count)
    message(FATAL_ERROR "Complete exact generic runtime archive roles are required; no engine/kernel/provider library is admitted")
endif()
foreach(_role IN LISTS _roles)
    string(JSON _path GET "${_manifest}" archives "${_role}" path)
    string(JSON _sha GET "${_manifest}" archives "${_role}" sha256)
    _raw_file("${_path}" "${_sha}" "${_role} static archive")
    if(NOT _path MATCHES "[.]lib$")
        message(FATAL_ERROR "Raw runtime generic inputs must be actual retained Windows static .lib archives")
    endif()
    add_library("${_role}" STATIC IMPORTED)
    set_target_properties("${_role}" PROPERTIES IMPORTED_LOCATION "${_path}")
endforeach()
string(JSON _include_count LENGTH "${_manifest}" include_directories)
if(_include_count LESS 1 OR _include_count GREATER 32)
    message(FATAL_ERROR "Raw runtime harness needs finite complete retained generic headers")
endif()
math(EXPR _include_last "${_include_count} - 1")
set(_includes)
foreach(_index RANGE 0 ${_include_last})
    string(JSON _include GET "${_manifest}" include_directories ${_index})
    if(NOT IS_ABSOLUTE "${_include}" OR NOT IS_DIRECTORY "${_include}" OR IS_SYMLINK "${_include}" OR
            "${_include}" MATCHES "[;\"\n\r]" OR "${_include}" MATCHES "\\$<")
        message(FATAL_ERROR "Retained generic header root is missing/aliased; explicit maintenance is required")
    endif()
    list(APPEND _includes "${_include}")
endforeach()
add_executable(foundation_raw_windows_candidate_runtime EXCLUDE_FROM_ALL
    "${CMAKE_CURRENT_LIST_DIR}/windows-runtime-main.cpp"
    "${CMAKE_CURRENT_LIST_DIR}/common/raw_candidate_probe.cpp")
target_include_directories(foundation_raw_windows_candidate_runtime PRIVATE
    "${CMAKE_CURRENT_LIST_DIR}" "${CMAKE_CURRENT_LIST_DIR}/common" ${_includes})
target_compile_features(foundation_raw_windows_candidate_runtime PRIVATE cxx_std_20)
target_compile_options(foundation_raw_windows_candidate_runtime PRIVATE /EHsc /GR /clang:-msse2)
target_compile_definitions(foundation_raw_windows_candidate_runtime PRIVATE NOMINMAX _HAS_EXCEPTIONS=1)
set_target_properties(foundation_raw_windows_candidate_runtime PROPERTIES
    CXX_EXTENSIONS OFF MSVC_RUNTIME_LIBRARY MultiThreaded)
target_link_libraries(foundation_raw_windows_candidate_runtime PRIVATE ${_roles})
# No INSTALL, provider, supplier, kernel or SDK target joins this standalone graph.
file(GENERATE OUTPUT "${CMAKE_BINARY_DIR}/runtime-target.json" CONTENT
    "{\"schema_version\":1,\"kind\":\"foundation-raw-windows-runtime-target-v1\",\"file\":\"$<TARGET_FILE:foundation_raw_windows_candidate_runtime>\",\"filename\":\"$<TARGET_FILE_NAME:foundation_raw_windows_candidate_runtime>\"}\n")
