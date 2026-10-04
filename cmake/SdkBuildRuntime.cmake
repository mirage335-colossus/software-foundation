include_guard(GLOBAL)

# Target sysroot directories are compiler inputs, never runtime loader paths:
# adding one to RPATH could load the SDK libc into an ordinary host process.
if(FOUNDATION_SDK_ROOT AND CMAKE_SYSTEM_NAME STREQUAL "Linux")
  foreach(language C CXX)
    foreach(directory lib lib64 usr/lib usr/lib64)
      list(APPEND CMAKE_${language}_IMPLICIT_LINK_DIRECTORIES "${CMAKE_SYSROOT}/${directory}")
    endforeach()
    list(REMOVE_DUPLICATES CMAKE_${language}_IMPLICIT_LINK_DIRECTORIES)
  endforeach()
endif()

function(foundation_sdk_runtime target)
  if(NOT FOUNDATION_SDK_ROOT OR NOT CMAKE_SYSTEM_NAME STREQUAL "Linux")
    return()
  endif()
  if(NOT FOUNDATION_PORTABLE)
    get_property(checked GLOBAL PROPERTY FOUNDATION_SDK_STATIC_RUNTIME_CHECKED)
    if(NOT checked)
      foundation_require_static_gnu_runtime()
      set_property(GLOBAL PROPERTY FOUNDATION_SDK_STATIC_RUNTIME_CHECKED TRUE)
    endif()
    foundation_link_static_gnu_runtime(${target} PRIVATE)
  endif()
  get_target_property(type "${target}" TYPE)
  if(NOT type STREQUAL "EXECUTABLE")
    return()
  endif()
  if(NOT target MATCHES "^[A-Za-z0-9_][A-Za-z0-9_.+-]*$")
    message(FATAL_ERROR "Unsafe SDK runtime target name: ${target}")
  endif()
  get_target_property(registered "${target}" FOUNDATION_SDK_RUNTIME)
  if(registered)
    message(FATAL_ERROR "SDK runtime already registered: ${target}")
  endif()
  set_property(TARGET "${target}" PROPERTY FOUNDATION_SDK_RUNTIME TRUE)
  # DT_RPATH is deliberately inherited by indirect private dependencies.
  target_link_options(${target} PRIVATE "LINKER:--disable-new-dtags")
  set_target_properties(${target} PROPERTIES
    BUILD_RPATH "$ORIGIN/.sdk-runtime/${target}" BUILD_RPATH_USE_ORIGIN ON)
  set_property(DIRECTORY APPEND PROPERTY FOUNDATION_SDK_RUNTIME_TARGETS "${target}")
  get_property(scheduled DIRECTORY PROPERTY FOUNDATION_SDK_RUNTIME_SCHEDULED)
  if(NOT scheduled)
    set_property(DIRECTORY PROPERTY FOUNDATION_SDK_RUNTIME_SCHEDULED TRUE)
    cmake_language(DEFER CALL _foundation_finalize_sdk_runtime)
  endif()
endfunction()

function(_foundation_finalize_sdk_runtime)
  get_property(targets DIRECTORY PROPERTY FOUNDATION_SDK_RUNTIME_TARGETS)
  file(SHA256 "${FOUNDATION_SDK_ROOT}/sdk.json" manifest)
  set(helper "${CMAKE_CURRENT_FUNCTION_LIST_DIR}/../tools/sdk_build_runtime.py")
  foreach(target IN LISTS targets)
    # Components do not create a dependency under CMP0112 NEW (CMake >=3.24).
    # TARGET_FILE here would create a target/guard dependency cycle.
    add_custom_target("foundation-sdk-runtime-${target}"
      COMMAND "${Python3_EXECUTABLE}" -B "${helper}" --guard
        --sdk "${FOUNDATION_SDK_ROOT}" --manifest-sha256 "${manifest}"
        --executable "$<TARGET_FILE_DIR:${target}>/$<TARGET_FILE_NAME:${target}>"
        --target "${target}" --processor "${CMAKE_SYSTEM_PROCESSOR}"
      COMMENT "Checking SDK development runtime for ${target}" VERBATIM)
    add_dependencies("${target}" "foundation-sdk-runtime-${target}")
    add_custom_command(TARGET "${target}" POST_BUILD
      COMMAND "${Python3_EXECUTABLE}" -B "${helper}"
        --sdk "${FOUNDATION_SDK_ROOT}" --manifest-sha256 "${manifest}"
        --executable "$<TARGET_FILE:${target}>" --target "${target}"
        --processor "${CMAKE_SYSTEM_PROCESSOR}"
      COMMENT "Auditing private SDK development runtime for ${target}" VERBATIM)
    set_property(TARGET "${target}" APPEND PROPERTY LINK_DEPENDS
      "${helper}" "${CMAKE_CURRENT_FUNCTION_LIST_DIR}/../tools/stage_runtime.py"
      "${CMAKE_CURRENT_FUNCTION_LIST_DIR}/../tools/verify_abi.py"
      "${CMAKE_CURRENT_FUNCTION_LIST_FILE}")
  endforeach()
endfunction()
