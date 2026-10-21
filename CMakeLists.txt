cmake_minimum_required(VERSION 3.24)
project(Foundation VERSION 0.1.0 LANGUAGES CXX)

if(CMAKE_SOURCE_DIR STREQUAL CMAKE_BINARY_DIR)
  message(FATAL_ERROR "Use an out-of-source build directory")
endif()
include(GNUInstallDirs)
include(CMakePackageConfigHelpers)
include(CTest)
include(cmake/TestPrerequisites.cmake)
include(cmake/BuildPolicy.cmake)
cmake_language(DEFER CALL foundation_finalize_build_policy)
option(FOUNDATION_SANITIZERS "Enable address and undefined-behavior checks" OFF)
option(FOUNDATION_PORTABLE "Use a generic CPU floor and static language runtime" OFF)
include(cmake/StaticCxxRuntime.cmake)
include(cmake/SdkBuildRuntime.cmake)
if(FOUNDATION_PORTABLE AND NOT MSVC AND NOT EMSCRIPTEN)
  foundation_require_static_gnu_runtime()
endif()
option(FOUNDATION_DISTRIBUTION_TESTS "Require local Debian repository tests and their tools" OFF)
if(FOUNDATION_PORTABLE AND FOUNDATION_SANITIZERS)
  message(FATAL_ERROR "Portable release and instrumented configurations must be separate")
endif()
set(_foundation_initial_msvc_runtime "${CMAKE_MSVC_RUNTIME_LIBRARY}")
if(FOUNDATION_PORTABLE AND MSVC)
  set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>")
endif()
option(FOUNDATION_BUILD_GUI "Build optional pinned GUI boundary examples" OFF)
set(FOUNDATION_GUI_SOURCE "" CACHE PATH "Explicit pinned GUI boundary checkout")
# Appended profile options.
set(FOUNDATION_APPENDED_PROFILE "none" CACHE STRING "Optional appended kernel capabilities: none, binary, web or both")
set_property(CACHE FOUNDATION_APPENDED_PROFILE PROPERTY STRINGS none binary web both)
option(FOUNDATION_APPENDED_KERNEL_MAINTENANCE "Explicitly permit initial kernel capability production" OFF)
option(FOUNDATION_APPENDED_ENGINE_PHYSICAL_INPUT "Explicitly select the verified physical467/mouse-v1 engine contract" OFF)
set(FOUNDATION_APPENDED_ENGINE_DOCUMENT_PROFILE "" CACHE STRING "Explicit browser document-v2 engine profile: empty, pixel, physical or editor")
set_property(CACHE FOUNDATION_APPENDED_ENGINE_DOCUMENT_PROFILE PROPERTY STRINGS "" pixel physical editor)
set(FOUNDATION_APPENDED_ENGINE_NATIVE_DOCUMENT_PROFILE "" CACHE STRING "Explicit native document-v2 engine profile: empty or pixel")
set_property(CACHE FOUNDATION_APPENDED_ENGINE_NATIVE_DOCUMENT_PROFILE PROPERTY STRINGS "" pixel)
set(FOUNDATION_APPENDED_ENGINE_NATIVE_ACTIONS_PROFILE "" CACHE STRING "Explicit native document-actions engine profile: empty or document-actions-v1")
set_property(CACHE FOUNDATION_APPENDED_ENGINE_NATIVE_ACTIONS_PROFILE PROPERTY STRINGS "" document-actions-v1)
set(FOUNDATION_APPENDED_ENGINE_NATIVE_DEPENDENCY_GROUP "" CACHE PATH "Matching retained Windows dependency export group for explicit native document production")
set(FOUNDATION_APPENDED_ENGINE_GROUP "" CACHE PATH "Complete retained neutral engine group")
foreach(_engine_pin RECIPE MANIFEST PROOF RUNTIME)
  set(FOUNDATION_APPENDED_ENGINE_${_engine_pin}_SHA256 "" CACHE STRING "Independent retained engine ${_engine_pin} SHA256")
endforeach()
if(NOT FOUNDATION_APPENDED_PROFILE MATCHES "^(none|binary|web|both)$")
  message(FATAL_ERROR "FOUNDATION_APPENDED_PROFILE must be none, binary, web or both")
endif()
if(DEFINED FOUNDATION_CONFIGURED_APPENDED_PROFILE AND
    NOT FOUNDATION_CONFIGURED_APPENDED_PROFILE STREQUAL FOUNDATION_APPENDED_PROFILE)
  message(FATAL_ERROR "Appended kernel capabilities changed; configure a fresh build directory")
endif()
set(FOUNDATION_CONFIGURED_APPENDED_PROFILE "${FOUNDATION_APPENDED_PROFILE}" CACHE INTERNAL "Configured appended capability profile" FORCE)
# End appended profile options.

set(FOUNDATION_CORE_PROVIDER "rust" CACHE STRING "Text validation implementation: rust (default) or cpp")
set_property(CACHE FOUNDATION_CORE_PROVIDER PROPERTY STRINGS cpp rust)
if(NOT FOUNDATION_CORE_PROVIDER MATCHES "^(cpp|rust)$")
  message(FATAL_ERROR "FOUNDATION_CORE_PROVIDER must be cpp or rust")
endif()
if(DEFINED FOUNDATION_CONFIGURED_CORE_PROVIDER AND
    NOT FOUNDATION_CONFIGURED_CORE_PROVIDER STREQUAL FOUNDATION_CORE_PROVIDER)
  message(FATAL_ERROR "Core provider changed; configure a fresh build directory")
endif()
set(FOUNDATION_CONFIGURED_CORE_PROVIDER "${FOUNDATION_CORE_PROVIDER}" CACHE INTERNAL "Configured core provider" FORCE)
if(FOUNDATION_CORE_PROVIDER STREQUAL "cpp")
  message(STATUS "Using the selected/cached C++ core provider; fresh build trees default to Rust")
endif()
if(MSVC AND FOUNDATION_CORE_PROVIDER STREQUAL "rust")
  set(_foundation_static_msvc_runtime "MultiThreaded$<$<CONFIG:Debug>:Debug>")
  if(_foundation_initial_msvc_runtime AND
      NOT _foundation_initial_msvc_runtime STREQUAL _foundation_static_msvc_runtime)
    message(FATAL_ERROR "The Rust provider requires the static MSVC runtime: ${_foundation_static_msvc_runtime}")
  endif()
  foreach(suffix "" _DEBUG _RELEASE _RELWITHDEBINFO _MINSIZEREL)
    if(CMAKE_CXX_FLAGS${suffix} MATCHES "(^|[ ;])/MDd?($|[ ;])")
      message(FATAL_ERROR "The Rust provider cannot use dynamic MSVC CRT compiler flags")
    endif()
  endforeach()
  set(CMAKE_MSVC_RUNTIME_LIBRARY "${_foundation_static_msvc_runtime}")
endif()

add_library(foundation_core STATIC src/store.cpp src/text_validation.cpp)
add_library(foundation::core ALIAS foundation_core)
set_target_properties(foundation_core PROPERTIES EXPORT_NAME core CXX_EXTENSIONS OFF)
target_compile_features(foundation_core PUBLIC cxx_std_20)
target_include_directories(foundation_core PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<BUILD_INTERFACE:${CMAKE_CURRENT_BINARY_DIR}/generated>
  $<INSTALL_INTERFACE:${CMAKE_INSTALL_INCLUDEDIR}>)

function(foundation_options target)
  foundation_sdk_runtime(${target})
  if(EMSCRIPTEN)
    target_compile_options(${target} PRIVATE -fexceptions)
    target_link_options(${target} PRIVATE -fexceptions -sASSERTIONS=1)
  endif()
  if(MSVC)
    target_compile_options(${target} PRIVATE /W4 /permissive- /utf-8)
  else()
    target_compile_options(${target} PRIVATE -Wall -Wextra -Wpedantic)
  endif()
  if(FOUNDATION_PORTABLE AND NOT MSVC AND NOT EMSCRIPTEN)
    if(CMAKE_SYSTEM_PROCESSOR MATCHES "^(x86_64|AMD64|amd64)$")
      target_compile_options(${target} PRIVATE -march=x86-64 -mtune=generic)
    elseif(CMAKE_SYSTEM_PROCESSOR MATCHES "^(aarch64|arm64|ARM64)$")
      target_compile_options(${target} PRIVATE -march=armv8-a)
    else()
      message(FATAL_ERROR "Declare a CPU floor before adding a portable target")
    endif()
    foundation_link_static_gnu_runtime(${target} PRIVATE)
    # Keep the application's existing protection for every bundled static archive.
    # Installed consumers use the narrower runtime helper to retain their own API.
    target_link_options(${target} PRIVATE "-Wl,--exclude-libs,ALL" "-Wl,--disable-new-dtags")
    set_target_properties(${target} PROPERTIES INSTALL_RPATH "$ORIGIN/../lib/runtime" BUILD_RPATH_USE_ORIGIN ON)
  endif()
  if(FOUNDATION_SANITIZERS)
    if(MSVC OR NOT CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
      message(FATAL_ERROR "This sanitizer preset requires GCC or Clang")
    endif()
    target_compile_options(${target} PRIVATE -fsanitize=address,undefined -fno-omit-frame-pointer)
    target_link_options(${target} PRIVATE -fsanitize=address,undefined)
  endif()
endfunction()
foundation_options(foundation_core)
if(FOUNDATION_SANITIZERS)
  target_link_options(foundation_core INTERFACE -fsanitize=address,undefined)
endif()
configure_file(cmake/version.hpp.in generated/foundation/version.hpp @ONLY)
add_executable(foundation-cli src/main.cpp)
target_link_libraries(foundation-cli PRIVATE foundation::core)
target_include_directories(foundation-cli PRIVATE "${CMAKE_CURRENT_BINARY_DIR}/generated")
foundation_options(foundation-cli)
if(EMSCRIPTEN)
  target_link_options(foundation-cli PRIVATE -sENVIRONMENT=node
    "-sINCOMING_MODULE_JS_API=['print','printErr']"
    --pre-js "${CMAKE_CURRENT_SOURCE_DIR}/src/platform/node_console.js")
  set_property(TARGET foundation-cli APPEND PROPERTY LINK_DEPENDS
    "${CMAKE_CURRENT_SOURCE_DIR}/src/platform/node_console.js")
endif()

find_package(Python3 3.9 REQUIRED COMPONENTS Interpreter)
# Appended retained-input admission.
if(EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/foundation-project.json" OR
    IS_SYMLINK "${CMAKE_CURRENT_SOURCE_DIR}/foundation-project.json")
  execute_process(COMMAND "${Python3_EXECUTABLE}" -B
    "${CMAKE_CURRENT_SOURCE_DIR}/tools/appended_project.py" inspect
    --root "${CMAKE_CURRENT_SOURCE_DIR}" --json
    OUTPUT_VARIABLE _foundation_project COMMAND_ERROR_IS_FATAL ANY)
  string(JSON _foundation_project_mode GET "${_foundation_project}" mode)
  string(JSON _foundation_project_profile GET "${_foundation_project}" selected_profile)
  string(JSON _foundation_project_profile_setting GET "${_foundation_project}" project kernel profile)
  if((NOT _foundation_project_mode STREQUAL "neither" OR
      NOT _foundation_project_profile STREQUAL "minimal") AND FOUNDATION_APPENDED_PROFILE STREQUAL "none")
    message(FATAL_ERROR "This project uses appended payloads: compose retained kernels, or explicitly configure the required kernel capability profile for maintenance")
  endif()
  if(NOT _foundation_project_profile STREQUAL "minimal" AND
      NOT FOUNDATION_APPENDED_PROFILE STREQUAL _foundation_project_profile)
    message(FATAL_ERROR "The requested kernel build does not match the selected project kernel profile; no implicit capability build is selected")
  endif()
  if(NOT _foundation_project_profile_setting STREQUAL "auto")
    set(_foundation_requested_project_profile "${FOUNDATION_APPENDED_PROFILE}")
    if(_foundation_requested_project_profile STREQUAL "none")
      set(_foundation_requested_project_profile "minimal")
    endif()
    if(NOT _foundation_requested_project_profile STREQUAL _foundation_project_profile)
      message(FATAL_ERROR "The requested kernel build does not match the explicitly selected kernel.profile")
    endif()
  endif()
endif()
# Never trust a caller-supplied -D admission boolean. The strict verifier below
# alone establishes this local value for the graph included by this configure.
set(FOUNDATION_APPENDED_ENGINE_CONSUMER_VERIFIED FALSE)
set(FOUNDATION_APPENDED_ENGINE_DOCUMENT_CONSUMER_VERIFIED FALSE)
set(FOUNDATION_APPENDED_ENGINE_NATIVE_CONSUMER_VERIFIED FALSE)
set(FOUNDATION_APPENDED_ENGINE_NATIVE_ACTIONS_CONSUMER_VERIFIED FALSE)
set(FOUNDATION_APPENDED_ENGINE_EDITOR_CONSUMER_VERIFIED FALSE)
set(FOUNDATION_APPENDED_ENGINE_EDITOR_DIRECTORY "")
if(NOT FOUNDATION_APPENDED_ENGINE_DOCUMENT_PROFILE MATCHES "^(|pixel|physical|editor)$")
  message(FATAL_ERROR "The browser document engine profile must be empty, pixel, physical or editor")
endif()
if(NOT FOUNDATION_APPENDED_ENGINE_NATIVE_DOCUMENT_PROFILE MATCHES "^(|pixel)$")
  message(FATAL_ERROR "The native document engine profile must be empty or pixel; native physical input is not admitted")
endif()
if(NOT FOUNDATION_APPENDED_ENGINE_NATIVE_ACTIONS_PROFILE MATCHES "^(|document-actions-v1)$")
  message(FATAL_ERROR "The native actions engine profile must be empty or document-actions-v1")
endif()
if((FOUNDATION_APPENDED_ENGINE_PHYSICAL_INPUT AND
    (FOUNDATION_APPENDED_ENGINE_DOCUMENT_PROFILE OR FOUNDATION_APPENDED_ENGINE_NATIVE_DOCUMENT_PROFILE)) OR
    (FOUNDATION_APPENDED_ENGINE_DOCUMENT_PROFILE AND FOUNDATION_APPENDED_ENGINE_NATIVE_DOCUMENT_PROFILE))
  message(FATAL_ERROR "Select only one retained engine input/document/native-document contract")
endif()
if(FOUNDATION_APPENDED_ENGINE_NATIVE_ACTIONS_PROFILE AND
    (FOUNDATION_APPENDED_ENGINE_PHYSICAL_INPUT OR FOUNDATION_APPENDED_ENGINE_DOCUMENT_PROFILE OR
     FOUNDATION_APPENDED_ENGINE_NATIVE_DOCUMENT_PROFILE))
  message(FATAL_ERROR "Select only one retained engine input/document/native-document/actions contract")
endif()
if(FOUNDATION_APPENDED_ENGINE_PHYSICAL_INPUT AND
    (NOT FOUNDATION_APPENDED_PROFILE MATCHES "^(web|both)$" OR NOT FOUNDATION_APPENDED_KERNEL_MAINTENANCE))
  message(FATAL_ERROR "Physical engine input requires explicit web or both kernel maintenance")
endif()
if((FOUNDATION_APPENDED_ENGINE_DOCUMENT_PROFILE OR FOUNDATION_APPENDED_ENGINE_NATIVE_DOCUMENT_PROFILE OR
    FOUNDATION_APPENDED_ENGINE_NATIVE_ACTIONS_PROFILE) AND
    (NOT FOUNDATION_APPENDED_PROFILE MATCHES "^(web|both)$" OR NOT FOUNDATION_APPENDED_KERNEL_MAINTENANCE))
  message(FATAL_ERROR "Document engine profiles require explicit web or both kernel maintenance")
endif()
if(FOUNDATION_APPENDED_ENGINE_NATIVE_DEPENDENCY_GROUP AND
    NOT (FOUNDATION_APPENDED_ENGINE_NATIVE_DOCUMENT_PROFILE OR FOUNDATION_APPENDED_ENGINE_NATIVE_ACTIONS_PROFILE))
  message(FATAL_ERROR "The native kernel dependency group applies only to explicit native document production")
endif()
if(FOUNDATION_APPENDED_PROFILE MATCHES "^(web|both)$")
  if(NOT FOUNDATION_APPENDED_KERNEL_MAINTENANCE)
    message(FATAL_ERROR "Rich kernel production requires explicit FOUNDATION_APPENDED_KERNEL_MAINTENANCE=ON")
  endif()
  set(_foundation_engine_native FALSE)
  if(FOUNDATION_APPENDED_ENGINE_NATIVE_DOCUMENT_PROFILE OR FOUNDATION_APPENDED_ENGINE_NATIVE_ACTIONS_PROFILE)
    set(_foundation_engine_native TRUE)
  endif()
  if(NOT FOUNDATION_BUILD_GUI OR NOT FOUNDATION_GUI_SOURCE)
    message(FATAL_ERROR "Rich kernel production requires verified GUI inputs")
  endif()
  if(_foundation_engine_native)
    if(NOT CMAKE_SIZEOF_VOID_P EQUAL 8 OR
        NOT CMAKE_SYSTEM_NAME MATCHES "^(Linux|Windows)$")
      message(FATAL_ERROR "Native document kernel production requires an admitted Linux or Windows 64-bit target")
    endif()
    if(CMAKE_SYSTEM_NAME STREQUAL "Windows")
      if(NOT FOUNDATION_WINDOWS_DEPENDENCIES OR NOT FOUNDATION_APPENDED_ENGINE_NATIVE_DEPENDENCY_GROUP OR
          FOUNDATION_SDK_ROOT OR NOT MSVC OR NOT FOUNDATION_PORTABLE)
        message(FATAL_ERROR "Native Windows document production requires its existing verified portable MSVC dependency export")
      endif()
      set(_foundation_engine_sdk_root "${FOUNDATION_WINDOWS_DEPENDENCIES}")
    else()
      if(NOT FOUNDATION_SDK_ROOT OR FOUNDATION_WINDOWS_DEPENDENCIES OR FOUNDATION_APPENDED_ENGINE_NATIVE_DEPENDENCY_GROUP)
        message(FATAL_ERROR "Native Linux document production requires its existing verified native SDK")
      endif()
      set(_foundation_engine_sdk_root "${FOUNDATION_SDK_ROOT}")
    endif()
  elseif(NOT FOUNDATION_SDK_ROOT OR NOT CMAKE_SYSTEM_NAME STREQUAL "Emscripten" OR
      NOT CMAKE_SIZEOF_VOID_P EQUAL 4)
    message(FATAL_ERROR "Rich kernel production requires GUI inputs and its existing verified Emscripten wasm32 SDK")
  elseif(FOUNDATION_APPENDED_ENGINE_DOCUMENT_PROFILE STREQUAL "editor" AND
      NOT CMAKE_SYSTEM_PROCESSOR STREQUAL "wasm32")
    message(FATAL_ERROR "Editor kernel production requires the configured Emscripten wasm32 processor")
  else()
    set(_foundation_engine_sdk_root "${FOUNDATION_SDK_ROOT}")
  endif()
  if(NOT FOUNDATION_APPENDED_ENGINE_GROUP)
    message(FATAL_ERROR "Rich kernel production requires a complete retained engine group and all four independent pins")
  endif()
  foreach(_engine_pin RECIPE MANIFEST PROOF RUNTIME)
    set(_engine_value "${FOUNDATION_APPENDED_ENGINE_${_engine_pin}_SHA256}")
    string(LENGTH "${_engine_value}" _engine_pin_length)
    if(NOT _engine_pin_length EQUAL 64 OR NOT _engine_value MATCHES "^[0-9a-f]+$")
      message(FATAL_ERROR "Rich kernel production requires independent lowercase SHA256 ${_engine_pin} pin")
    endif()
  endforeach()
  execute_process(COMMAND "${Python3_EXECUTABLE}" -B "${CMAKE_CURRENT_SOURCE_DIR}/tools/sdk_verify.py"
    "${_foundation_engine_sdk_root}" OUTPUT_VARIABLE _foundation_engine_sdk_sha256
    OUTPUT_STRIP_TRAILING_WHITESPACE COMMAND_ERROR_IS_FATAL ANY)
  file(SHA256 "${_foundation_engine_sdk_root}/sdk.json" _foundation_engine_sdk_observed)
  if(NOT _foundation_engine_sdk_observed STREQUAL _foundation_engine_sdk_sha256)
    message(FATAL_ERROR "The paired SDK changed during retained-engine admission")
  endif()
  file(READ "${_foundation_engine_sdk_root}/sdk.json" _foundation_engine_sdk)
  string(JSON _foundation_engine_target_system GET "${_foundation_engine_sdk}" target system)
  string(JSON _foundation_engine_target_processor GET "${_foundation_engine_sdk}" target processor)
  string(JSON _foundation_engine_target_triple GET "${_foundation_engine_sdk}" target triple)
  if(_foundation_engine_native)
    set(_foundation_engine_actual_processor "${CMAKE_SYSTEM_PROCESSOR}")
    if(_foundation_engine_actual_processor MATCHES "^(AMD64|amd64)$")
      set(_foundation_engine_actual_processor "x86_64")
    elseif(_foundation_engine_actual_processor MATCHES "^(arm64|ARM64)$")
      set(_foundation_engine_actual_processor "aarch64")
    endif()
    if(NOT _foundation_engine_target_system STREQUAL CMAKE_SYSTEM_NAME OR
        NOT _foundation_engine_target_processor STREQUAL _foundation_engine_actual_processor OR
        NOT ((_foundation_engine_target_system STREQUAL "Linux" AND _foundation_engine_target_processor MATCHES "^(x86_64|aarch64)$") OR
             (_foundation_engine_target_system STREQUAL "Windows" AND _foundation_engine_target_processor STREQUAL "x86_64")))
      message(FATAL_ERROR "Native document engine SDK target differs from the configured admitted native target")
    endif()
  elseif(NOT _foundation_engine_target_system STREQUAL "Emscripten" OR
      NOT _foundation_engine_target_processor STREQUAL "wasm32" OR
      NOT _foundation_engine_target_triple STREQUAL "wasm32-emscripten")
    message(FATAL_ERROR "The retained rich engine requires the paired Emscripten wasm32 SDK")
  endif()
  if(NOT (_foundation_engine_native AND CMAKE_SYSTEM_NAME STREQUAL "Windows"))
    file(REAL_PATH "${CMAKE_CURRENT_SOURCE_DIR}/cmake/toolchains/sdk.cmake" _foundation_engine_required_toolchain)
    file(REAL_PATH "${CMAKE_TOOLCHAIN_FILE}" _foundation_engine_selected_toolchain
      BASE_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}")
    if(NOT _foundation_engine_selected_toolchain STREQUAL _foundation_engine_required_toolchain)
      message(FATAL_ERROR "Rich kernel production requires cmake/toolchains/sdk.cmake from this source tree")
    endif()
    string(JSON _foundation_engine_cxx GET "${_foundation_engine_sdk}" target cxx_compiler)
    file(REAL_PATH "${_foundation_engine_sdk_root}/${_foundation_engine_cxx}" _foundation_engine_expected_cxx)
    file(REAL_PATH "${CMAKE_CXX_COMPILER}" _foundation_engine_actual_cxx)
    if(NOT _foundation_engine_actual_cxx STREQUAL _foundation_engine_expected_cxx)
      message(FATAL_ERROR "The paired SDK and configured CXX compiler differ; use the retained SDK toolchain in a fresh tree")
    endif()
    if(CMAKE_C_COMPILER)
      string(JSON _foundation_engine_c ERROR_VARIABLE _foundation_engine_missing_c
        GET "${_foundation_engine_sdk}" target c_compiler)
      if(_foundation_engine_missing_c)
        if(_foundation_engine_native)
          message(FATAL_ERROR "The native rich SDK does not declare the configured C compiler")
        else()
          set(_foundation_engine_c "bin/emcc")
        endif()
      endif()
      file(REAL_PATH "${_foundation_engine_sdk_root}/${_foundation_engine_c}" _foundation_engine_expected_c)
      file(REAL_PATH "${CMAKE_C_COMPILER}" _foundation_engine_actual_c)
      if(NOT _foundation_engine_actual_c STREQUAL _foundation_engine_expected_c)
        message(FATAL_ERROR "The paired SDK and configured C compiler differ; use the retained SDK toolchain in a fresh tree")
      endif()
    endif()
  endif()
  set(_foundation_engine_target_json "${CMAKE_CURRENT_BINARY_DIR}/appended-engine-kernel-target.json")
  string(JSON _foundation_engine_kernel_target GET "${_foundation_engine_sdk}" target)
  string(JSON _foundation_engine_target_length LENGTH "${_foundation_engine_kernel_target}")
  math(EXPR _foundation_engine_target_last "${_foundation_engine_target_length} - 1")
  foreach(_index RANGE ${_foundation_engine_target_last} 0 -1)
    string(JSON _member MEMBER "${_foundation_engine_kernel_target}" ${_index})
    if(NOT _member MATCHES "^(system|processor|triple)$")
      string(JSON _foundation_engine_kernel_target REMOVE "${_foundation_engine_kernel_target}" "${_member}")
    endif()
  endforeach()
  if(_foundation_engine_native)
    set(_foundation_engine_pointer_bits 64)
  else()
    set(_foundation_engine_pointer_bits 32)
  endif()
  string(JSON _foundation_engine_kernel_target SET "${_foundation_engine_kernel_target}"
    pointer_bits ${_foundation_engine_pointer_bits})
  file(WRITE "${_foundation_engine_target_json}" "${_foundation_engine_kernel_target}\n")
  if(_foundation_engine_native)
    set(_foundation_engine_native_sdk_command
      --sdk-sha256 "${_foundation_engine_sdk_sha256}"
      --kernel-target-json "${_foundation_engine_target_json}"
      --cxx-compiler "${CMAKE_CXX_COMPILER}")
    if(CMAKE_C_COMPILER)
      list(APPEND _foundation_engine_native_sdk_command --c-compiler "${CMAKE_C_COMPILER}")
    endif()
    if(CMAKE_SYSTEM_NAME STREQUAL "Windows")
      list(APPEND _foundation_engine_native_sdk_command
        --windows-dependencies "${FOUNDATION_WINDOWS_DEPENDENCIES}"
        --dependency-group "${FOUNDATION_APPENDED_ENGINE_NATIVE_DEPENDENCY_GROUP}"
        --linker "${CMAKE_LINKER}")
    else()
      list(APPEND _foundation_engine_native_sdk_command --sdk "${FOUNDATION_SDK_ROOT}"
        --sysroot "${CMAKE_SYSROOT}" --toolchain "${_foundation_engine_selected_toolchain}")
    endif()
    execute_process(COMMAND "${Python3_EXECUTABLE}" -B
      "${CMAKE_CURRENT_SOURCE_DIR}/tools/appended_engine_kernel_sdk.py"
      ${_foundation_engine_native_sdk_command}
      OUTPUT_VARIABLE _foundation_engine_native_sdk_facts OUTPUT_STRIP_TRAILING_WHITESPACE
      COMMAND_ERROR_IS_FATAL ANY)
  endif()
  set(_foundation_engine_sdk_arguments --paired-sdk-sha256 "${_foundation_engine_sdk_sha256}")
  if(_foundation_engine_native)
    set(_foundation_engine_consumer_command
      "${CMAKE_CURRENT_SOURCE_DIR}/tools/appended_engine_native_profile.py"
      --build-dir "${CMAKE_CURRENT_BINARY_DIR}")
    if(FOUNDATION_APPENDED_ENGINE_NATIVE_ACTIONS_PROFILE)
      list(APPEND _foundation_engine_consumer_command
        --actions-profile "${FOUNDATION_APPENDED_ENGINE_NATIVE_ACTIONS_PROFILE}")
    else()
      list(APPEND _foundation_engine_consumer_command
        --document-profile "${FOUNDATION_APPENDED_ENGINE_NATIVE_DOCUMENT_PROFILE}")
    endif()
    set(_foundation_engine_sdk_arguments)
  elseif(FOUNDATION_APPENDED_ENGINE_DOCUMENT_PROFILE STREQUAL "editor")
    set(_foundation_engine_consumer_command
      "${CMAKE_CURRENT_SOURCE_DIR}/tools/appended_engine_editor_profile.py"
      --build-root "${CMAKE_CURRENT_BINARY_DIR}" --editor-profile editor)
  elseif(FOUNDATION_APPENDED_ENGINE_DOCUMENT_PROFILE)
    set(_foundation_engine_consumer_command
      "${CMAKE_CURRENT_SOURCE_DIR}/tools/appended_engine_document_profile.py"
      --build-root "${CMAKE_CURRENT_BINARY_DIR}" --document-profile "${FOUNDATION_APPENDED_ENGINE_DOCUMENT_PROFILE}")
  elseif(FOUNDATION_APPENDED_ENGINE_PHYSICAL_INPUT)
    # This adapter calls the strict physical consumer once and emits a private
    # header only after complete retained-group and runtime admission succeeds.
    set(_foundation_engine_consumer_command
      "${CMAKE_CURRENT_SOURCE_DIR}/tools/appended_engine_input_profile.py"
      --build-root "${CMAKE_CURRENT_BINARY_DIR}")
  else()
    set(_foundation_engine_consumer_command
      "${CMAKE_CURRENT_SOURCE_DIR}/tools/appended_engine_consumer.py" verify)
  endif()
  execute_process(COMMAND "${Python3_EXECUTABLE}" -B ${_foundation_engine_consumer_command}
    --group "${FOUNDATION_APPENDED_ENGINE_GROUP}"
    --recipe-sha256 "${FOUNDATION_APPENDED_ENGINE_RECIPE_SHA256}"
    --manifest-sha256 "${FOUNDATION_APPENDED_ENGINE_MANIFEST_SHA256}"
    --proof-sha256 "${FOUNDATION_APPENDED_ENGINE_PROOF_SHA256}"
    --runtime-sha256 "${FOUNDATION_APPENDED_ENGINE_RUNTIME_SHA256}"
    --kernel-target-json "${_foundation_engine_target_json}"
    ${_foundation_engine_sdk_arguments}
    OUTPUT_VARIABLE _foundation_engine_consumer OUTPUT_STRIP_TRAILING_WHITESPACE
    COMMAND_ERROR_IS_FATAL ANY)
  string(SHA256 _foundation_engine_identity
    "${FOUNDATION_APPENDED_ENGINE_GROUP}\n${FOUNDATION_APPENDED_ENGINE_RECIPE_SHA256}\n${FOUNDATION_APPENDED_ENGINE_MANIFEST_SHA256}\n${FOUNDATION_APPENDED_ENGINE_PROOF_SHA256}\n${FOUNDATION_APPENDED_ENGINE_RUNTIME_SHA256}\n${_foundation_engine_sdk_sha256}\n${_foundation_engine_consumer}")
  if(FOUNDATION_APPENDED_ENGINE_PHYSICAL_INPUT)
    string(SHA256 _foundation_engine_identity "physical-input=ON\n${_foundation_engine_identity}")
  endif()
  if(FOUNDATION_APPENDED_ENGINE_DOCUMENT_PROFILE OR FOUNDATION_APPENDED_ENGINE_NATIVE_DOCUMENT_PROFILE)
    string(SHA256 _foundation_engine_identity
      "document=${FOUNDATION_APPENDED_ENGINE_DOCUMENT_PROFILE}\nnative-document=${FOUNDATION_APPENDED_ENGINE_NATIVE_DOCUMENT_PROFILE}\n${_foundation_engine_identity}")
  endif()
  if(FOUNDATION_APPENDED_ENGINE_NATIVE_ACTIONS_PROFILE)
    string(SHA256 _foundation_engine_identity
      "native-actions=${FOUNDATION_APPENDED_ENGINE_NATIVE_ACTIONS_PROFILE}\n${_foundation_engine_identity}")
  endif()
  if(_foundation_engine_native)
    string(SHA256 _foundation_engine_identity "${_foundation_engine_native_sdk_facts}\n${_foundation_engine_identity}")
  endif()
  if(DEFINED FOUNDATION_CONFIGURED_APPENDED_ENGINE_IDENTITY AND
      NOT FOUNDATION_CONFIGURED_APPENDED_ENGINE_IDENTITY STREQUAL _foundation_engine_identity)
    message(FATAL_ERROR "Retained engine identity changed; configure a fresh build directory")
  endif()
  set(FOUNDATION_CONFIGURED_APPENDED_ENGINE_IDENTITY "${_foundation_engine_identity}"
    CACHE INTERNAL "Configured retained engine complete consumer identity" FORCE)
  set(FOUNDATION_APPENDED_ENGINE_CONSUMER_VERIFIED TRUE)
  if(_foundation_engine_native)
    set(FOUNDATION_APPENDED_ENGINE_NATIVE_CONSUMER_VERIFIED TRUE)
    if(FOUNDATION_APPENDED_ENGINE_NATIVE_ACTIONS_PROFILE)
      set(FOUNDATION_APPENDED_ENGINE_NATIVE_ACTIONS_CONSUMER_VERIFIED TRUE)
    endif()
  elseif(FOUNDATION_APPENDED_ENGINE_DOCUMENT_PROFILE STREQUAL "editor")
    set(FOUNDATION_APPENDED_ENGINE_EDITOR_CONSUMER_VERIFIED TRUE)
    set(FOUNDATION_APPENDED_ENGINE_EDITOR_DIRECTORY "${PROJECT_BINARY_DIR}/appended-engine-editor-profile")
  elseif(FOUNDATION_APPENDED_ENGINE_DOCUMENT_PROFILE)
    set(FOUNDATION_APPENDED_ENGINE_DOCUMENT_CONSUMER_VERIFIED TRUE)
  endif()
else()
  if(FOUNDATION_APPENDED_ENGINE_GROUP)
    message(FATAL_ERROR "Retained engine inputs apply only to web or both kernel maintenance")
  endif()
  foreach(_engine_pin RECIPE MANIFEST PROOF RUNTIME)
    if(FOUNDATION_APPENDED_ENGINE_${_engine_pin}_SHA256)
      message(FATAL_ERROR "Retained engine pins apply only to web or both kernel maintenance")
    endif()
  endforeach()
endif()
# End appended retained-input admission.
include(cmake/RustComponent.cmake)
foundation_rust_component(foundation_core)
include(cmake/ImportWasm.cmake)
if(FOUNDATION_SDK_ROOT)
  execute_process(COMMAND "${Python3_EXECUTABLE}" -B "${CMAKE_CURRENT_SOURCE_DIR}/tools/sdk_verify.py"
    "${FOUNDATION_SDK_ROOT}" COMMAND_ERROR_IS_FATAL ANY OUTPUT_QUIET)
  file(READ "${FOUNDATION_SDK_ROOT}/sdk.json" _verified_sdk)
  string(JSON _sdk_system GET "${_verified_sdk}" target system)
  if(_sdk_system STREQUAL "Linux")
    foreach(pair "cxx_compiler|CMAKE_CXX_COMPILER" "sysroot|CMAKE_SYSROOT")
      string(REPLACE "|" ";" parts "${pair}")
      list(GET parts 0 field)
      list(GET parts 1 configured)
      string(JSON declared GET "${_verified_sdk}" target ${field})
      file(REAL_PATH "${FOUNDATION_SDK_ROOT}/${declared}" expected)
      file(REAL_PATH "${${configured}}" actual)
      if(NOT actual STREQUAL expected)
        message(FATAL_ERROR "SDK metadata and configured ${configured} differ; select cmake/toolchains/sdk.cmake in a fresh tree")
      endif()
    endforeach()
    set(FOUNDATION_VERIFY_SDK TRUE)
  endif()
endif()
if(BUILD_TESTING)
  add_executable(foundation_core_test EXCLUDE_FROM_ALL tests/store_test.cpp)
  target_link_libraries(foundation_core_test PRIVATE foundation::core)
  foundation_options(foundation_core_test)
  if(NOT EMSCRIPTEN)
  add_test(NAME core.store COMMAND foundation_core_test)
  set_tests_properties(core.store PROPERTIES LABELS "fast;core" TIMEOUT 30)
  add_test(NAME core.cli COMMAND ${Python3_EXECUTABLE}
    "${CMAKE_CURRENT_SOURCE_DIR}/tests/check_cli.py" $<TARGET_FILE:foundation-cli>)
  set_tests_properties(core.cli PROPERTIES LABELS "fast;core" TIMEOUT 30)
  add_test(NAME docs.links COMMAND ${Python3_EXECUTABLE} "${CMAKE_CURRENT_SOURCE_DIR}/tools/check_docs.py")
  set_tests_properties(docs.links PROPERTIES LABELS "fast;tools" TIMEOUT 30)
  else()
    if(NOT FOUNDATION_NODE_EXECUTABLE OR NOT EXISTS "${FOUNDATION_NODE_EXECUTABLE}")
      message(FATAL_ERROR "Browser tests require the prepared SDK's retained Node executable")
    endif()
    add_test(NAME core.store COMMAND "${FOUNDATION_NODE_EXECUTABLE}" $<TARGET_FILE:foundation_core_test>)
    add_test(NAME core.cli COMMAND ${Python3_EXECUTABLE}
      "${CMAKE_CURRENT_SOURCE_DIR}/tests/check_cli.py" "${FOUNDATION_NODE_EXECUTABLE}" $<TARGET_FILE:foundation-cli>)
    set_tests_properties(core.store core.cli PROPERTIES LABELS "fast;core" TIMEOUT 30)
  endif()
  if(WIN32 AND MSVC AND NOT CMAKE_CROSSCOMPILING)
    add_executable(foundation_windows_arguments_test EXCLUDE_FROM_ALL
      tests/cxx_runtime/windows_arguments.cpp)
    target_include_directories(foundation_windows_arguments_test PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}/src")
    target_compile_features(foundation_windows_arguments_test PRIVATE cxx_std_20)
    foundation_options(foundation_windows_arguments_test)
    add_test(NAME core.windows_arguments COMMAND ${Python3_EXECUTABLE} -B
      "${CMAKE_CURRENT_SOURCE_DIR}/tests/cxx_runtime/check_windows_arguments.py"
      $<TARGET_FILE:foundation_windows_arguments_test>)
    set_tests_properties(core.windows_arguments PROPERTIES LABELS "core;fast" TIMEOUT 30)
    foundation_test_prerequisites(core.windows_arguments foundation_windows_arguments_test)
  endif()
  foundation_test_prerequisites(core.store foundation_core_test)
  foundation_test_prerequisites(core.cli foundation-cli)
  add_executable(foundation_rust_component_test EXCLUDE_FROM_ALL tests/rust_component_test.cpp)
  target_link_libraries(foundation_rust_component_test PRIVATE foundation::core)
  target_include_directories(foundation_rust_component_test PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}/src")
  if(FOUNDATION_CORE_PROVIDER STREQUAL "rust")
    target_compile_definitions(foundation_rust_component_test PRIVATE FOUNDATION_EXPECT_RUST=1)
  endif()
  foundation_options(foundation_rust_component_test)
  if(EMSCRIPTEN)
    add_test(NAME core.text_validation COMMAND "${FOUNDATION_NODE_EXECUTABLE}" $<TARGET_FILE:foundation_rust_component_test>)
  else()
    add_test(NAME core.text_validation COMMAND foundation_rust_component_test)
  endif()
  set_tests_properties(core.text_validation PROPERTIES LABELS "fast;core" TIMEOUT 30)
  foundation_test_prerequisites(core.text_validation foundation_rust_component_test)
  add_executable(foundation_text_status_test EXCLUDE_FROM_ALL tests/rust_component_status_test.cpp src/store.cpp)
  target_include_directories(foundation_text_status_test PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}/include" "${CMAKE_CURRENT_SOURCE_DIR}/src")
  target_compile_features(foundation_text_status_test PRIVATE cxx_std_20)
  foundation_options(foundation_text_status_test)
  if(EMSCRIPTEN)
    add_test(NAME core.text_status COMMAND "${FOUNDATION_NODE_EXECUTABLE}" $<TARGET_FILE:foundation_text_status_test>)
  else()
    add_test(NAME core.text_status COMMAND foundation_text_status_test)
  endif()
  set_tests_properties(core.text_status PROPERTIES LABELS "fast;core" TIMEOUT 30)
  foundation_test_prerequisites(core.text_status foundation_text_status_test)
  if(NOT EMSCRIPTEN)
    foundation_test_prerequisites(docs.links)
    set(_native_popup_fixture "${CMAKE_CURRENT_BINARY_DIR}/generated/native_popup_capability_fixture.cpp")
    add_custom_command(OUTPUT "${_native_popup_fixture}"
      COMMAND "${Python3_EXECUTABLE}" -B
        "${CMAKE_CURRENT_SOURCE_DIR}/tools/generate_native_popup_capability_fixture.py"
        --publisher "${CMAKE_CURRENT_SOURCE_DIR}/recipes/webkitwasm-document-v2/source/native/NativeDocumentV2Publisher.cpp"
        --forms "${CMAKE_CURRENT_SOURCE_DIR}/recipes/webkitwasm-document-v2/source/native/NativeFormsV2Combined.cpp"
        --template "${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/native_popup_capability/branch_fixture.cpp.in"
        --output "${_native_popup_fixture}"
      DEPENDS tools/generate_native_popup_capability_fixture.py tools/generate_document_label_association_fixture.py
        tests/fixtures/native_popup_capability/branch_fixture.cpp.in
        recipes/webkitwasm-document-v2/source/native/NativeDocumentV2Publisher.cpp
        recipes/webkitwasm-document-v2/source/native/NativeFormsV2Combined.cpp
      VERBATIM)
    add_executable(appended_native_popup_capability_test EXCLUDE_FROM_ALL "${_native_popup_fixture}")
    target_compile_features(appended_native_popup_capability_test PRIVATE cxx_std_20)
    add_test(NAME foundation.appended.native-popup-capability COMMAND appended_native_popup_capability_test)
    foundation_test_prerequisites(foundation.appended.native-popup-capability appended_native_popup_capability_test)
    set_tests_properties(foundation.appended.native-popup-capability PROPERTIES LABELS "fast;tools;integration" TIMEOUT 20)
    set(_native_popup_owner_fixture "${CMAKE_CURRENT_BINARY_DIR}/generated/native_popup_owner_preflight_fixture.cpp")
    add_custom_command(OUTPUT "${_native_popup_owner_fixture}"
      COMMAND "${Python3_EXECUTABLE}" -B "${CMAKE_CURRENT_SOURCE_DIR}/tools/generate_native_popup_owner_preflight_fixture.py"
        --source "${CMAKE_CURRENT_SOURCE_DIR}/recipes/webkitwasm-native-rich4083-v1/source/document-provider/popup/BibNativePopupOwner.cpp"
        --template "${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/native_popup_capability/owner_preflight.cpp.in"
        --output "${_native_popup_owner_fixture}"
      DEPENDS tools/generate_native_popup_owner_preflight_fixture.py tools/generate_document_label_association_fixture.py
        tests/fixtures/native_popup_capability/owner_preflight.cpp.in
        recipes/webkitwasm-native-rich4083-v1/source/document-provider/popup/BibNativePopupOwner.cpp VERBATIM)
    add_executable(appended_native_popup_owner_preflight_test EXCLUDE_FROM_ALL "${_native_popup_owner_fixture}")
    target_compile_features(appended_native_popup_owner_preflight_test PRIVATE cxx_std_20)
    add_test(NAME foundation.appended.native-popup-owner-preflight COMMAND appended_native_popup_owner_preflight_test)
    foundation_test_prerequisites(foundation.appended.native-popup-owner-preflight appended_native_popup_owner_preflight_test)
    set_tests_properties(foundation.appended.native-popup-owner-preflight PROPERTIES LABELS "fast;tools;integration" TIMEOUT 20)
    set(_document_label_fixture "${CMAKE_CURRENT_BINARY_DIR}/generated/document_label_association_fixture.cpp")
    add_custom_command(OUTPUT "${_document_label_fixture}"
      COMMAND "${CMAKE_COMMAND}" -E make_directory "${CMAKE_CURRENT_BINARY_DIR}/generated"
      COMMAND "${Python3_EXECUTABLE}" -B
        "${CMAKE_CURRENT_SOURCE_DIR}/tools/generate_document_label_association_fixture.py"
        --source "${CMAKE_CURRENT_SOURCE_DIR}/recipes/webkitwasm-document-v2/source/native/NativeDocumentV2Publisher.cpp"
        --template "${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/document_label_association/branch_fixture.cpp.in"
        --output "${_document_label_fixture}"
      DEPENDS tools/generate_document_label_association_fixture.py
        tests/fixtures/document_label_association/branch_fixture.cpp.in
        recipes/webkitwasm-document-v2/source/native/NativeDocumentV2Publisher.cpp
      VERBATIM)
    add_executable(appended_document_label_association_test EXCLUDE_FROM_ALL "${_document_label_fixture}")
    target_compile_features(appended_document_label_association_test PRIVATE cxx_std_20)
    set_target_properties(appended_document_label_association_test PROPERTIES CXX_EXTENSIONS OFF)
    add_test(NAME foundation.appended.document-label-association
      COMMAND appended_document_label_association_test)
    set_tests_properties(foundation.appended.document-label-association PROPERTIES
      LABELS "fast;tools;integration" TIMEOUT 20)
    foundation_test_prerequisites(foundation.appended.document-label-association
      appended_document_label_association_test)
  endif()
  # Only explicitly named suites run; adding one requires registering its label.
  set(_tool_suites appended_entry appended_project appended_container appended_policy appended_compile appended_wasm appended_kernel browser_bundle package_wasm import_wasm ci_retry build build_capacity rev_probe ci_changes package_notices test_plan artifact gui_boundary gui_source_group gui_source_group_retained_reintegration gui_visual coverage certification ci_plan qualification_tasks process_tree host_contracts sdk sdk_retention rust_build rust_sdk rust_workflow dependencies source_identity release portability release_check run_tests github_release ci_transport ci_artifacts ci_cleanup ci_cleanup_repository ci_cleanup_previous ci_cleanup_drafts ci_cleanup_expired workflow_storage legacy_artifacts verify_legacy_preservation screenshots gallery_browser latest_release windows_graphics windows_compiler)
  list(APPEND _tool_suites appended_wasm3 appended_release appended_providers_sdk package_appended_wasm
    appended_ci)
  list(APPEND _tool_suites appended_qualification appended_release_check appended_delivery)
  list(APPEND _tool_suites appended_guest_check appended_install_check appended_browser_check appended_rich_surface_actions)
  list(APPEND _tool_suites process_tree_observation appended_engine_windows_dependency_support
    appended_engine_windows_tool_versions)
  list(APPEND _tool_suites document_label_association_fixture native_popup_capability_fixture)
  list(APPEND _tool_suites engine_document_contract appended_rich_entry appended_document_entry appended_engine_kernel_sdk
    appended_native_terminal_cmake appended_native_gui_graph)
  set(_platform_exclusions "{}")
  if(UNIX)
    list(APPEND _tool_suites fork)
  else()
    string(JSON _platform_exclusions SET "${_platform_exclusions}" "tools.fork" "\"fork.sh requires a POSIX shell\"")
  endif()
  # Docker account IDs, ownership and privilege fixtures apply to Linux hosts.
  if(CMAKE_SYSTEM_NAME STREQUAL "Linux")
    list(APPEND _tool_suites appended_guest_memory)
    list(APPEND _tool_suites container_job prepare_dependencies sdk_paths sdk_build_runtime ci_apt offline_acceptance offline_namespace
      appended_checkout
      appended_engine_sdk appended_engine_consumer appended_engine_maintenance appended_engine_donor package_appended_engine_wasm appended_kernel_factory_policy browser_surface_bundle
      appended_engine_document_contract appended_engine_document_consumer appended_engine_document_profile
      appended_engine_document_maintenance appended_engine_document_metadata
      appended_engine_document_sources appended_engine_document_reuse completed_work_resume
      appended_engine_successful_donor appended_engine_document_source_successful_donor
      appended_engine_theme_successor appended_engine_showpicker_successor appended_engine_showpicker_source_assembly appended_engine_theme_source_assembly
      appended_engine_select_event_successor appended_engine_select_event_source_assembly
      appended_engine_theme_dependency_ownership
      appended_engine_editor_contract appended_engine_editor_consumer appended_engine_editor_profile browser_editor_bundle
      appended_engine_composition_undo_journal
      appended_editor_cmake
      appended_engine_native_binary appended_engine_native_consumer appended_engine_native_profile
      appended_engine_native_sources appended_engine_native_metadata appended_engine_native_bootstrap
      appended_engine_native_actions_contract appended_engine_native_actions_sources
      appended_engine_native_actions_metadata appended_engine_native_actions_cmake appended_engine_native_actions_bootstrap
      appended_engine_native_inputs appended_engine_native_role7 appended_engine_native_prototype appended_engine_native_dependencies
      appended_engine_native_sdk appended_engine_native_original_proof appended_native_dispatch
      appended_engine_windows_contract appended_engine_windows_handoff appended_engine_windows_prototype
      appended_engine_windows_publication appended_engine_windows_prepare appended_engine_windows_source_replay
      appended_engine_windows_dependency_proof appended_engine_windows_dependencies
      package_appended_engine_document_wasm)
  else()
    string(JSON _platform_exclusions SET "${_platform_exclusions}" "tools.appended_guest_memory" "\"Native guest memory ASan/UBSan fixtures are currently qualified on Linux only\"")
    string(JSON _platform_exclusions SET "${_platform_exclusions}" "tools.appended_checkout" "\"Current-checkout POSIX executable-mode, identity, symlink and owned-FD publication fixtures are currently qualified on Linux only\"")
    string(JSON _platform_exclusions SET "${_platform_exclusions}" "tools.appended_engine_sdk" "\"Retained-engine filesystem adapter fixtures are currently qualified on Linux only\"")
    foreach(_rich_tool appended_engine_consumer appended_engine_maintenance appended_engine_donor package_appended_engine_wasm appended_kernel_factory_policy browser_surface_bundle
        appended_engine_document_contract appended_engine_document_consumer appended_engine_document_profile
        appended_engine_document_maintenance appended_engine_document_metadata
        appended_engine_document_sources appended_engine_document_reuse completed_work_resume
        appended_engine_successful_donor appended_engine_document_source_successful_donor
        appended_engine_theme_successor appended_engine_showpicker_successor appended_engine_showpicker_source_assembly appended_engine_theme_source_assembly
      appended_engine_select_event_successor appended_engine_select_event_source_assembly
        appended_engine_theme_dependency_ownership
        appended_engine_editor_contract appended_engine_editor_consumer appended_engine_editor_profile browser_editor_bundle
      appended_engine_composition_undo_journal
        appended_editor_cmake
        appended_engine_native_binary appended_engine_native_consumer appended_engine_native_profile
        appended_engine_native_sources appended_engine_native_metadata appended_engine_native_bootstrap
        appended_engine_native_actions_contract appended_engine_native_actions_sources
        appended_engine_native_actions_metadata appended_engine_native_actions_cmake appended_engine_native_actions_bootstrap
        appended_engine_native_inputs appended_engine_native_role7 appended_engine_native_prototype appended_engine_native_dependencies
        appended_engine_native_sdk appended_engine_native_original_proof appended_native_dispatch
        appended_engine_windows_contract appended_engine_windows_handoff appended_engine_windows_prototype
        appended_engine_windows_publication appended_engine_windows_prepare appended_engine_windows_source_replay
        appended_engine_windows_dependency_proof appended_engine_windows_dependencies
        package_appended_engine_document_wasm)
      string(JSON _platform_exclusions SET "${_platform_exclusions}" "tools.${_rich_tool}" "\"Rich retained-engine and renderer filesystem fixtures are currently qualified on Linux only\"")
    endforeach()
    foreach(suite container_job prepare_dependencies sdk_paths sdk_build_runtime ci_apt offline_acceptance offline_namespace)
      string(JSON _platform_exclusions SET "${_platform_exclusions}" "tools.${suite}" "\"Linux native dependency and container qualification is not scheduled on this host\"")
    endforeach()
    message(STATUS "Linux Docker ownership qualification is not scheduled on this host")
  endif()
  if(FOUNDATION_DISTRIBUTION_TESTS)
    if(NOT CMAKE_SYSTEM_NAME STREQUAL "Linux")
      message(FATAL_ERROR "Debian repository tests require Linux")
    endif()
    foreach(_tool dpkg-deb gpg gpgv gpgconf gpg-agent gpg-connect-agent git cc)
      find_program(_required_${_tool} NAMES ${_tool} REQUIRED)
    endforeach()
    list(APPEND _tool_suites apt_repo distro_channel distribution_release distro_client distro_check)
  endif()
  foreach(suite IN LISTS _tool_suites)
    if(NOT EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/tests/test_${suite}.py")
      message(FATAL_ERROR "Missing required tool suite: ${suite}")
    endif()
    add_test(NAME tools.${suite} COMMAND ${Python3_EXECUTABLE} "${CMAKE_CURRENT_SOURCE_DIR}/tools/run_tests.py"
        --suite "${suite}" --output "${CMAKE_BINARY_DIR}/test-reports/${suite}.json")
    foundation_test_prerequisites(tools.${suite})
    set_tests_properties(tools.${suite} PROPERTIES LABELS "tools" TIMEOUT 120)
  endforeach()
  set_tests_properties(tools.gui_boundary tools.gui_source_group tools.gui_source_group_retained_reintegration tools.gui_visual PROPERTIES LABELS "tools;gui;focused;fast")
  set_tests_properties(tools.build tools.build_capacity tools.ci_changes PROPERTIES LABELS "tools;fast")
  if(CMAKE_SYSTEM_NAME STREQUAL "Linux")
    set_tests_properties(tools.sdk_paths PROPERTIES LABELS "tools;fast")
  endif()
  file(WRITE "${CMAKE_BINARY_DIR}/test-platform.json" "{\"schema_version\":1,\"excluded_suites\":${_platform_exclusions}}\n")
  if(NOT CMAKE_CROSSCOMPILING AND NOT EMSCRIPTEN)
    add_test(NAME integration.install COMMAND ${Python3_EXECUTABLE}
      "${CMAKE_CURRENT_SOURCE_DIR}/tests/check_install.py"
      --build "${CMAKE_BINARY_DIR}" --config $<CONFIG>
      --source "${CMAKE_CURRENT_SOURCE_DIR}")
    set_tests_properties(integration.install PROPERTIES LABELS "integration" TIMEOUT 180
      RESOURCE_LOCK install-tree)
  endif()
endif()

if(FOUNDATION_APPENDED_PROFILE STREQUAL "binary")
  include(cmake/Appended.cmake)
elseif(FOUNDATION_APPENDED_PROFILE MATCHES "^(web|both)$" AND EMSCRIPTEN)
  include(cmake/AppendedEngine.cmake)
elseif(FOUNDATION_APPENDED_PROFILE MATCHES "^(web|both)$")
  include(cmake/Appended.cmake)
elseif(BUILD_TESTING AND NOT EMSCRIPTEN AND FOUNDATION_APPENDED_PROFILE STREQUAL "none")
  # Inert native guard fixtures use only local value/codecs. Selecting a test
  # builds its prerequisites without enabling appended kernel maintenance.
  include(cmake/AppendedPortableCodecs.cmake)
  include(cmake/AppendedEngineProvider.cmake)
endif()

if(FOUNDATION_BUILD_GUI)
  add_subdirectory(gui)
endif()

# Focused document value fixtures use the same production GUI code in an ordinary
# native development tree. Their fake provider is owned by the existing tests;
# these prerequisites contain no kernel, VM or retained engine implementation.
if(BUILD_TESTING AND FOUNDATION_BUILD_GUI AND NOT EMSCRIPTEN AND
    FOUNDATION_APPENDED_PROFILE STREQUAL "none")
  add_library(foundation_native_popup_gui_fixture_support STATIC EXCLUDE_FROM_ALL
    gui/shared/appended_document.cpp
    gui/shared/appended_document_codec.cpp
    gui/shared/appended_document_controller.cpp
    gui/shared/appended_document_forms.cpp
    gui/shared/appended_document_v2_codec.cpp
    gui/shared/engine_document_broker.cpp
    gui/shared/appended_engine_owner.cpp
    gui/shared/appended_engine_input_codec.cpp
    gui/shared/engine_document_mailbox.cpp
    src/appended/container.cpp
    src/appended/resource_url.cpp
    src/appended/web_services.cpp)
  target_include_directories(foundation_native_popup_gui_fixture_support PUBLIC
    "${CMAKE_CURRENT_SOURCE_DIR}/gui" "${CMAKE_CURRENT_SOURCE_DIR}/include")
  target_link_libraries(foundation_native_popup_gui_fixture_support PUBLIC
    foundation_gui_boundary foundation_appended_document_forms
    foundation_appended_editor_codec Threads::Threads)
  target_compile_features(foundation_native_popup_gui_fixture_support PUBLIC cxx_std_20)
  set_target_properties(foundation_native_popup_gui_fixture_support PROPERTIES CXX_EXTENSIONS OFF)
  add_dependencies(foundation_native_popup_gui_fixture_support foundation_gui_contract)
  foundation_options(foundation_native_popup_gui_fixture_support)
  foreach(_popup_gui_fixture forms v2_codec)
    add_executable(foundation_native_popup_gui_${_popup_gui_fixture}_test EXCLUDE_FROM_ALL
      "gui/tests/appended_document_${_popup_gui_fixture}_test.cpp")
    target_link_libraries(foundation_native_popup_gui_${_popup_gui_fixture}_test PRIVATE
      foundation_native_popup_gui_fixture_support)
    foundation_options(foundation_native_popup_gui_${_popup_gui_fixture}_test)
    set_target_properties(foundation_native_popup_gui_${_popup_gui_fixture}_test PROPERTIES CXX_EXTENSIONS OFF)
    string(REPLACE "_" "-" _popup_gui_test_name "${_popup_gui_fixture}")
    add_test(NAME foundation.gui.appended-document-${_popup_gui_test_name}
      COMMAND foundation_native_popup_gui_${_popup_gui_fixture}_test)
    foundation_test_prerequisites(foundation.gui.appended-document-${_popup_gui_test_name}
      foundation_native_popup_gui_${_popup_gui_fixture}_test)
    set_tests_properties(foundation.gui.appended-document-${_popup_gui_test_name} PROPERTIES
      LABELS "gui;appended;focused" TIMEOUT 30)
  endforeach()
endif()
if(BUILD_TESTING)
  if(TEST integration.install)
    set(install_prerequisites foundation-cli foundation_core)
    if(TARGET foundation-appended-kernel)
      list(APPEND install_prerequisites foundation-appended-kernel)
    endif()
    if(TARGET foundation-gui-hosts)
      list(APPEND install_prerequisites foundation-gui-hosts)
    endif()
    foundation_test_prerequisites(integration.install ${install_prerequisites})
  endif()
  if(CMAKE_SYSTEM_NAME STREQUAL "Linux" AND NOT CMAKE_CROSSCOMPILING)
    add_test(NAME integration.cxx_runtime COMMAND ${Python3_EXECUTABLE} -B
      "${CMAKE_CURRENT_SOURCE_DIR}/tests/check_cxx_runtime.py"
      --compiler "${CMAKE_CXX_COMPILER}" --cmake "${CMAKE_COMMAND}"
      --temporary-root "${CMAKE_CURRENT_BINARY_DIR}")
    set_tests_properties(integration.cxx_runtime PROPERTIES LABELS "integration;portable" TIMEOUT 240)
    foundation_test_prerequisites(integration.cxx_runtime)
  endif()
  cmake_language(DEFER CALL foundation_finalize_test_prerequisites)
endif()

install(TARGETS foundation_core foundation-cli EXPORT FoundationTargets
  ARCHIVE DESTINATION ${CMAKE_INSTALL_LIBDIR}
  RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR})
if(EMSCRIPTEN)
  install(FILES "$<TARGET_FILE_DIR:foundation-cli>/foundation-cli.wasm"
    DESTINATION ${CMAKE_INSTALL_BINDIR})
endif()
install(DIRECTORY include/ DESTINATION ${CMAKE_INSTALL_INCLUDEDIR})
install(FILES "${CMAKE_CURRENT_BINARY_DIR}/generated/foundation/version.hpp"
  DESTINATION ${CMAKE_INSTALL_INCLUDEDIR}/foundation)
install(EXPORT FoundationTargets NAMESPACE foundation::
  DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/Foundation)
configure_package_config_file(cmake/FoundationConfig.cmake.in
  "${CMAKE_CURRENT_BINARY_DIR}/FoundationConfig.cmake"
  INSTALL_DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/Foundation
  PATH_VARS CMAKE_INSTALL_LIBDIR)
write_basic_package_version_file("${CMAKE_CURRENT_BINARY_DIR}/FoundationConfigVersion.cmake"
  VERSION ${PROJECT_VERSION} COMPATIBILITY SameMajorVersion)
install(FILES "${CMAKE_CURRENT_BINARY_DIR}/FoundationConfig.cmake"
  "${CMAKE_CURRENT_BINARY_DIR}/FoundationConfigVersion.cmake"
  "${CMAKE_CURRENT_SOURCE_DIR}/cmake/StaticCxxRuntime.cmake"
  DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/Foundation)
install(FILES docs/man/foundation-cli.1 DESTINATION "${CMAKE_INSTALL_MANDIR}/man1")
install(FILES docs/man/software-foundation.7 DESTINATION "${CMAKE_INSTALL_MANDIR}/man7")
install(FILES LICENSE DESTINATION ${CMAKE_INSTALL_DOCDIR})
install(FILES docs/installed.md DESTINATION ${CMAKE_INSTALL_DOCDIR} RENAME README.md)
install(FILES third_party/dependencies.json DESTINATION ${CMAKE_INSTALL_DOCDIR}/third_party)
set(FOUNDATION_DEPENDENCY_RECIPE "native-unprepared" CACHE STRING "Primary prepared dependency recipe")
set(FOUNDATION_DEPENDENCY_RECIPES "" CACHE STRING "Complete retained recipe identities")
set(_sdk_recipe "${FOUNDATION_DEPENDENCY_RECIPE}")
set(_sdk_digest "none")
if(FOUNDATION_SDK_ROOT)
  file(READ "${FOUNDATION_SDK_ROOT}/sdk.json" _sdk_metadata)
  string(JSON _sdk_recipe GET "${_sdk_metadata}" recipe_id)
  file(SHA256 "${FOUNDATION_SDK_ROOT}/sdk.json" _sdk_digest)
endif()
set(_source_args "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tools/source_identity.py" digest --root "${CMAKE_CURRENT_SOURCE_DIR}")
if(FOUNDATION_BUILD_GUI)
  list(APPEND _source_args --supplement "${FOUNDATION_GUI_SOURCE}")
endif()
execute_process(COMMAND ${_source_args} OUTPUT_VARIABLE _source_identity
  OUTPUT_STRIP_TRAILING_WHITESPACE COMMAND_ERROR_IS_FATAL ANY)
# Direct incremental builds also regenerate provenance when existing source inputs
# change. The wrapper additionally checks the complete inventory before/after work.
execute_process(COMMAND "${Python3_EXECUTABLE}" -c
  "import sys;sys.path.insert(0,sys.argv[1]);from source_identity import selected_files;print(';'.join(str(p) for p in selected_files(sys.argv[2]).values()))"
  "${CMAKE_CURRENT_SOURCE_DIR}/tools" "${CMAKE_CURRENT_SOURCE_DIR}"
  OUTPUT_VARIABLE _source_paths OUTPUT_STRIP_TRAILING_WHITESPACE COMMAND_ERROR_IS_FATAL ANY)
set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS ${_source_paths})
string(TOLOWER "${CMAKE_SYSTEM_NAME}" _target_os)
string(TOLOWER "${CMAKE_SYSTEM_PROCESSOR}" _target_cpu)
if(_target_cpu STREQUAL "amd64")
  set(_target_cpu x86_64)
elseif(_target_cpu STREQUAL "arm64")
  set(_target_cpu aarch64)
endif()
set(_backends "")
if(EMSCRIPTEN)
  set(_target_os browser)
  set(_target_cpu wasm32)
endif()
if(FOUNDATION_BUILD_GUI)
  if(EMSCRIPTEN)
    set(_backends wasm)
  else()
    set(_backends terminal framebuffer)
    foreach(_frontend FLTK REV SDL WEB)
      if(FOUNDATION_GUI_${_frontend})
        if(_frontend STREQUAL "WEB")
          list(APPEND _backends hosted-web)
        else()
          string(TOLOWER "${_frontend}" _name)
          list(APPEND _backends "${_name}")
        endif()
      endif()
    endforeach()
  endif()
endif()
if(FOUNDATION_SDK_ROOT AND NOT _sdk_recipe IN_LIST FOUNDATION_DEPENDENCY_RECIPES)
  list(APPEND FOUNDATION_DEPENDENCY_RECIPES "${_sdk_recipe}")
endif()
if(FOUNDATION_CORE_PROVIDER STREQUAL "rust" AND FOUNDATION_RUST_SDK_ROOT AND
    NOT FOUNDATION_RUST_SDK_RECIPE_ID IN_LIST FOUNDATION_DEPENDENCY_RECIPES)
  list(APPEND FOUNDATION_DEPENDENCY_RECIPES "${FOUNDATION_RUST_SDK_RECIPE_ID}")
endif()
list(JOIN FOUNDATION_DEPENDENCY_RECIPES "," _dependency_recipes)
list(JOIN _backends "," _backend_names)
set(_build_info "source_tree_sha256=${_source_identity}\ntarget=${_target_os}-${_target_cpu}\ngui_backends=${_backend_names}\ndependency_recipes=${_dependency_recipes}\nsdk_recipe_id=${_sdk_recipe}\nsdk_manifest_sha256=${_sdk_digest}\ncore_provider=${FOUNDATION_CORE_PROVIDER}\nrust_sdk_recipe_id=${FOUNDATION_RUST_SDK_RECIPE_ID}\nrust_sdk_manifest_sha256=${FOUNDATION_RUST_SDK_MANIFEST_SHA256}\nrust_compiler_version=${FOUNDATION_RUST_COMPILER_VERSION}\nrust_compiler_sha256=${FOUNDATION_RUST_COMPILER_SHA256}\nrust_target=${FOUNDATION_RUST_SELECTED_TARGET}\nportable=${FOUNDATION_PORTABLE}\nVersion: ${PROJECT_VERSION}\nCompiler: ${CMAKE_CXX_COMPILER_ID} ${CMAKE_CXX_COMPILER_VERSION}\nTarget: ${CMAKE_SYSTEM_NAME} ${CMAKE_SYSTEM_PROCESSOR}\nBuild type: ${CMAKE_BUILD_TYPE}\nGUI enabled: ${FOUNDATION_BUILD_GUI}\nSanitizers: ${FOUNDATION_SANITIZERS}\nCompatibility: native build; no older OS qualification implied\n")
file(CONFIGURE OUTPUT "${CMAKE_CURRENT_BINARY_DIR}/build-info.txt" CONTENT "${_build_info}" @ONLY)
install(FILES "${CMAKE_CURRENT_BINARY_DIR}/build-info.txt" DESTINATION ${CMAKE_INSTALL_DOCDIR})

foundation_install_sdk_runtime()

if(FOUNDATION_PORTABLE AND CMAKE_SYSTEM_NAME STREQUAL "Linux")
  string(TOLOWER "${CMAKE_SYSTEM_PROCESSOR}" _portable_processor)
  if(_portable_processor STREQUAL "amd64")
    set(_portable_processor x86_64)
  elseif(_portable_processor STREQUAL "arm64")
    set(_portable_processor aarch64)
  endif()
  set(FOUNDATION_RUNTIME_ROOTS "${CMAKE_SYSROOT}" CACHE STRING "Explicit target library roots for runtime collection")
  configure_file(cmake/InstallRuntime.cmake.in "${CMAKE_BINARY_DIR}/InstallRuntime.cmake" @ONLY)
  install(SCRIPT "${CMAKE_BINARY_DIR}/InstallRuntime.cmake")
endif()

set(CPACK_PACKAGE_NAME software-foundation)
set(CPACK_PACKAGE_VENDOR "mirage335")
set(CPACK_RESOURCE_FILE_LICENSE "${CMAKE_CURRENT_SOURCE_DIR}/LICENSE")
set(CPACK_PACKAGE_VERSION ${PROJECT_VERSION})
set(CPACK_PACKAGE_DESCRIPTION_SUMMARY "Generic software development reference")
set(CPACK_PACKAGE_DIRECTORY "${CMAKE_BINARY_DIR}/packages")
set(CPACK_PACKAGE_FILE_NAME "${CPACK_PACKAGE_NAME}-${PROJECT_VERSION}-${_target_os}-${_target_cpu}")
set(CPACK_VERBATIM_VARIABLES TRUE)
if(WIN32)
  set(CPACK_GENERATOR ZIP)
else()
  set(CPACK_GENERATOR TGZ)
endif()
# Direct CPack also observes release exclusions; bypassing the wrapper is no waiver.
configure_file(cmake/PackagePolicy.cmake.in "${CMAKE_BINARY_DIR}/PackagePolicy.cmake" @ONLY)
set(CPACK_PROJECT_CONFIG_FILE "${CMAKE_BINARY_DIR}/PackagePolicy.cmake")
include(CPack)
