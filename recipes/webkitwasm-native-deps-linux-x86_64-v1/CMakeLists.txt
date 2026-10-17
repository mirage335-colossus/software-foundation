cmake_minimum_required(VERSION 3.24)
project(FoundationNativeDependencies LANGUAGES NONE)

# The wrapper performs byte/inventory admission before this graph is reachable.
# This graph accepts already materialized sources, never archive URLs.
file(READ "${CMAKE_CURRENT_LIST_DIR}/profile.json" _native_profile)
string(JSON _native_input_count LENGTH "${_native_profile}" cmake_inputs)
math(EXPR _native_last_input "${_native_input_count} - 1")
foreach(_index RANGE 0 ${_native_last_input})
  string(JSON _name GET "${_native_profile}" cmake_inputs ${_index})
  if(NOT DEFINED ${_name} OR
     (NOT _name STREQUAL "NATIVE_LINK_FLAGS" AND "${${_name}}" STREQUAL ""))
    message(FATAL_ERROR "Missing admitted initial-cache input: ${_name}")
  endif()
endforeach()
foreach(_name NATIVE_PREFIX NATIVE_WORK NATIVE_TOOLCHAIN NATIVE_SYSROOT)
  if(NOT IS_ABSOLUTE "${${_name}}" OR IS_SYMLINK "${${_name}}")
    message(FATAL_ERROR "${_name} must be an absolute ordinary path")
  endif()
endforeach()
if(NOT EXISTS "${NATIVE_TOOLCHAIN}" OR IS_DIRECTORY "${NATIVE_TOOLCHAIN}")
  message(FATAL_ERROR "Missing admitted native-toolchain.cmake")
endif()
if(NOT IS_DIRECTORY "${NATIVE_SYSROOT}")
  message(FATAL_ERROR "Missing admitted native sysroot")
endif()
set(_native_fixed_flags "-fPIC -march=x86-64 -mtune=generic --sysroot=${NATIVE_SYSROOT}")
if(NOT NATIVE_C_FLAGS STREQUAL _native_fixed_flags OR
   NOT NATIVE_CXX_FLAGS STREQUAL _native_fixed_flags)
  message(FATAL_ERROR "Native dependency CPU/PIC flags differ from the fixed policy")
endif()
# An empty link-flags cache value is intentional, and is validated separately
# from required path/list values. no-shared, rather than linker -static, is used.
if(NOT NATIVE_LINK_FLAGS STREQUAL "")
  message(FATAL_ERROR "Native dependency linker overrides are not supported")
endif()
if(NOT NATIVE_PIC_RUNTIME_MODE STREQUAL "generic-pic-v1" AND
   NOT NATIVE_PIC_RUNTIME_MODE STREQUAL "private-static-gcc-sdk-v1")
  message(FATAL_ERROR "Unsupported explicit native PIC runtime mode")
endif()
set(_native_private_inputs
  NATIVE_PRIVATE_RUNTIME_HELPER NATIVE_PRIVATE_RUNTIME_HELPER_SHA256
  BIB_NATIVE_RUNTIME_COMPILER_TRIPLE BIB_NATIVE_RUNTIME_POLICY_SHA256
  BIB_NATIVE_RUNTIME_SELECTION_PATH BIB_NATIVE_RUNTIME_SELECTION_SHA256
  BIB_NATIVE_RUNTIME_LIBSTDCXX_PATH BIB_NATIVE_RUNTIME_LIBSTDCXX_SHA256
  BIB_NATIVE_RUNTIME_LIBGCC_PATH BIB_NATIVE_RUNTIME_LIBGCC_SHA256
  BIB_NATIVE_RUNTIME_LIBGCC_EH_PATH BIB_NATIVE_RUNTIME_LIBGCC_EH_SHA256
  BIB_NATIVE_RUNTIME_CRTBEGINS_PATH BIB_NATIVE_RUNTIME_CRTBEGINS_SHA256
  BIB_NATIVE_RUNTIME_CRTENDS_PATH BIB_NATIVE_RUNTIME_CRTENDS_SHA256
  BIB_NATIVE_RUNTIME_LINK_MAP)
string(JSON _private_input_count LENGTH "${_native_profile}" private_runtime cmake_inputs)
if(NOT _private_input_count EQUAL 17)
  message(FATAL_ERROR "Private native PIC cache contract must contain exactly 17 inputs")
endif()
set(_profile_private_inputs)
foreach(_index RANGE 0 16)
  string(JSON _name GET "${_native_profile}" private_runtime cmake_inputs ${_index})
  list(APPEND _profile_private_inputs "${_name}")
endforeach()
if(NOT _profile_private_inputs STREQUAL _native_private_inputs)
  message(FATAL_ERROR "Private native PIC cache names differ from the fixed contract")
endif()
get_cmake_property(_native_variables VARIABLES)
foreach(_name IN LISTS _native_variables)
  if(_name MATCHES "^(NATIVE_PRIVATE_RUNTIME_|BIB_NATIVE_RUNTIME_)" AND
     NOT _name IN_LIST _native_private_inputs)
    message(FATAL_ERROR "Unknown private native PIC cache input: ${_name}")
  endif()
endforeach()
set(_native_pic_runtime_args "-DNATIVE_PIC_RUNTIME_MODE:STRING=${NATIVE_PIC_RUNTIME_MODE}")
foreach(_name IN LISTS _native_private_inputs)
  if(NATIVE_PIC_RUNTIME_MODE STREQUAL "generic-pic-v1")
    if(DEFINED ${_name})
      message(FATAL_ERROR "Generic native PIC mode refuses private runtime input: ${_name}")
    endif()
  else()
    if(NOT DEFINED ${_name} OR "${${_name}}" STREQUAL "")
      message(FATAL_ERROR "Missing explicit private native PIC input: ${_name}")
    endif()
    if(NOT "${${_name}}" MATCHES "^[A-Za-z0-9_./+-]+$")
      message(FATAL_ERROR "Private native PIC cache input is not a scalar literal: ${_name}")
    endif()
    list(APPEND _native_pic_runtime_args "-D${_name}:STRING=${${_name}}")
  endif()
endforeach()
if(NATIVE_PIC_RUNTIME_MODE STREQUAL "private-static-gcc-sdk-v1" AND
   NOT BIB_NATIVE_RUNTIME_LINK_MAP STREQUAL "${NATIVE_WORK}/pic/evidence/dependency-runtime-link.map")
  message(FATAL_ERROR "Private native PIC mode requires its fixed derived evidence link map")
endif()
set(_native_order icu zlib brotli png jpeg webp freetype harfbuzz xml2 sqlite
                  openssl nghttp2 psl curl fontconfig)
foreach(_component IN LISTS _native_order)
  if(NOT IS_ABSOLUTE "${SOURCE_${_component}}" OR
     NOT IS_DIRECTORY "${SOURCE_${_component}}" OR
     IS_SYMLINK "${SOURCE_${_component}}")
    message(FATAL_ERROR "Missing ordinary admitted source root: ${_component}")
  endif()
endforeach()
foreach(_role cmake ninja make sh perl python gperf pkg_config c cxx archiver ranlib)
  if(NOT IS_ABSOLUTE "${PROGRAM_${_role}}" OR
     NOT EXISTS "${PROGRAM_${_role}}" OR
     IS_DIRECTORY "${PROGRAM_${_role}}" OR
     IS_SYMLINK "${PROGRAM_${_role}}")
    message(FATAL_ERROR "Missing ordinary admitted program: ${_role}")
  endif()
endforeach()
if(NOT CMAKE_COMMAND STREQUAL PROGRAM_cmake)
  message(FATAL_ERROR "The invoked CMake must be the admitted CMake program")
endif()
include(ExternalProject)
add_custom_target(native-assets
  COMMAND "${PROGRAM_cmake}"
    "-DNATIVE_PREFIX=${NATIVE_PREFIX}"
    "-DNATIVE_ASSETS_FONT_CONFIG=${NATIVE_ASSETS_FONT_CONFIG}"
    "-DNATIVE_ASSETS_ICU_DATA=${NATIVE_ASSETS_ICU_DATA}"
    "-DNATIVE_ASSETS_CA_BUNDLE=${NATIVE_ASSETS_CA_BUNDLE}"
    "-DNATIVE_ASSETS_FONTS=${NATIVE_ASSETS_FONTS}"
    "-DNATIVE_NOTICE_FILES=${NATIVE_NOTICE_FILES}"
    -P "${CMAKE_CURRENT_LIST_DIR}/cmake/install-assets.cmake"
  VERBATIM)
include("${CMAKE_CURRENT_LIST_DIR}/cmake/components.cmake")
ExternalProject_Add(native-pic
  SOURCE_DIR "${CMAKE_CURRENT_LIST_DIR}/pic"
  BINARY_DIR "${NATIVE_WORK}/pic" PREFIX "${NATIVE_WORK}/ep-pic"
  DOWNLOAD_COMMAND "" UPDATE_COMMAND "" PATCH_COMMAND ""
  LIST_SEPARATOR "|"
  CONFIGURE_COMMAND ${_native_env} "${PROGRAM_cmake}"
    -S "${CMAKE_CURRENT_LIST_DIR}/pic" -B "${NATIVE_WORK}/pic" -G Ninja
    ${_native_cmake_args}
    "-DNATIVE_PREFIX:PATH=${NATIVE_PREFIX}"
    "-DNATIVE_PROFILE:FILEPATH=${CMAKE_CURRENT_LIST_DIR}/profile.json"
    ${_native_pic_runtime_args}
  BUILD_COMMAND ${_native_env} "${PROGRAM_cmake}" --build "${NATIVE_WORK}/pic"
    --target foundation-native-dependencies-pic-check --parallel 4 --verbose
  INSTALL_COMMAND ""
  DEPENDS native-fontconfig EXCLUDE_FROM_ALL TRUE)
add_custom_target(native-dependencies DEPENDS native-pic)
