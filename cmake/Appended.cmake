# Optional native startup routes: the legacy binary console and separately
# admitted document composition. Browser producers use AppendedEngine.cmake.
include_guard(GLOBAL)
# The native document route is separate from the legacy binary console. Only
# the top-level strict verifier may admit it; a project mode/header alone cannot.
if(FOUNDATION_APPENDED_PROFILE MATCHES "^(web|both)$")
  if(NOT FOUNDATION_APPENDED_KERNEL_MAINTENANCE OR NOT FOUNDATION_BUILD_GUI OR
      NOT FOUNDATION_APPENDED_ENGINE_CONSUMER_VERIFIED OR
      NOT FOUNDATION_APPENDED_ENGINE_NATIVE_CONSUMER_VERIFIED OR
      NOT (FOUNDATION_APPENDED_ENGINE_NATIVE_DOCUMENT_PROFILE STREQUAL "pixel" OR
           (FOUNDATION_APPENDED_ENGINE_NATIVE_ACTIONS_PROFILE STREQUAL "document-actions-v1" AND
            FOUNDATION_APPENDED_ENGINE_NATIVE_ACTIONS_CONSUMER_VERIFIED)) OR
      EMSCRIPTEN OR NOT CMAKE_SIZEOF_VOID_P EQUAL 8 OR
      NOT (WIN32 OR CMAKE_SYSTEM_NAME STREQUAL "Linux"))
    message(FATAL_ERROR "Native appended production requires explicit verified pixel1795 or document-actions4083 native kernel maintenance")
  endif()
  if(FOUNDATION_APPENDED_ENGINE_NATIVE_ACTIONS_PROFILE)
    set(_foundation_native_profile_directory "${PROJECT_BINARY_DIR}/appended-engine-native-actions-profile")
  else()
    set(_foundation_native_profile_directory "${PROJECT_BINARY_DIR}/appended-engine-native-profile")
  endif()
  if(NOT EXISTS "${_foundation_native_profile_directory}/appended_engine_compiled_native_profile.hpp")
    message(FATAL_ERROR "Native appended production is missing its verified private native profile; retained engine maintenance is required")
  endif()
  include("${CMAKE_CURRENT_LIST_DIR}/AppendedCommon.cmake")
  if(FOUNDATION_APPENDED_PROFILE STREQUAL "both")
    include("${CMAKE_CURRENT_LIST_DIR}/AppendedBinary.cmake")
  endif()
  # The retained group is three archives/checksum files, not a runnable SDK
  # directory. Restore only its verified binary inventory into an owned tree.
  set(FOUNDATION_APPENDED_ENGINE_NATIVE_RUNTIME_ROOT "${PROJECT_BINARY_DIR}/appended-engine-native-runtime")
  if(EXISTS "${FOUNDATION_APPENDED_ENGINE_NATIVE_RUNTIME_ROOT}")
    execute_process(COMMAND "${Python3_EXECUTABLE}" -B "${PROJECT_SOURCE_DIR}/tools/appended_engine_sdk.py" verify
      --root "${FOUNDATION_APPENDED_ENGINE_NATIVE_RUNTIME_ROOT}"
      --recipe "${FOUNDATION_APPENDED_ENGINE_RECIPE_SHA256}"
      --manifest-sha256 "${FOUNDATION_APPENDED_ENGINE_MANIFEST_SHA256}"
      COMMAND_ERROR_IS_FATAL ANY OUTPUT_QUIET)
  else()
    execute_process(COMMAND "${Python3_EXECUTABLE}" -B "${PROJECT_SOURCE_DIR}/tools/appended_engine_sdk.py" restore
      --group "${FOUNDATION_APPENDED_ENGINE_GROUP}"
      --recipe "${FOUNDATION_APPENDED_ENGINE_RECIPE_SHA256}"
      --output "${FOUNDATION_APPENDED_ENGINE_NATIVE_RUNTIME_ROOT}"
      COMMAND_ERROR_IS_FATAL ANY OUTPUT_QUIET)
    # Restore verifies the complete group; also join the restored manifest to
    # the independent binary pin used by this exact native admission.
    execute_process(COMMAND "${Python3_EXECUTABLE}" -B "${PROJECT_SOURCE_DIR}/tools/appended_engine_sdk.py" verify
      --root "${FOUNDATION_APPENDED_ENGINE_NATIVE_RUNTIME_ROOT}"
      --recipe "${FOUNDATION_APPENDED_ENGINE_RECIPE_SHA256}"
      --manifest-sha256 "${FOUNDATION_APPENDED_ENGINE_MANIFEST_SHA256}"
      COMMAND_ERROR_IS_FATAL ANY OUTPUT_QUIET)
  endif()
  # Quote generated install-script arguments as data. Source/build paths may
  # contain spaces, quotes or dollar signs and must not become CMake code.
  function(_foundation_appended_native_literal output value)
    string(REPLACE "\\" "\\\\" _literal "${value}")
    string(REPLACE "\"" "\\\"" _literal "${_literal}")
    string(REPLACE "$" "\\$" _literal "${_literal}")
    set(${output} "\"${_literal}\"" PARENT_SCOPE)
  endfunction()
  function(foundation_appended_native_install_runtime destination)
    _foundation_appended_native_literal(_python "${Python3_EXECUTABLE}")
    _foundation_appended_native_literal(_verifier "${PROJECT_SOURCE_DIR}/tools/appended_engine_sdk.py")
    _foundation_appended_native_literal(_runtime "${FOUNDATION_APPENDED_ENGINE_NATIVE_RUNTIME_ROOT}")
    _foundation_appended_native_literal(_recipe "${FOUNDATION_APPENDED_ENGINE_RECIPE_SHA256}")
    _foundation_appended_native_literal(_manifest "${FOUNDATION_APPENDED_ENGINE_MANIFEST_SHA256}")
    _foundation_appended_native_literal(_destination "${destination}")
    set(_verify_prefix "execute_process(COMMAND ${_python} -B ${_verifier} verify --root ")
    set(_verify_suffix " --recipe ${_recipe} --manifest-sha256 ${_manifest} COMMAND_ERROR_IS_FATAL ANY OUTPUT_QUIET)\n")
    set(_before "${PROJECT_BINARY_DIR}/appended-engine-native-install-before.cmake")
    set(_after "${PROJECT_BINARY_DIR}/appended-engine-native-install-after.cmake")
    file(WRITE "${_before}" "${_verify_prefix}${_runtime}${_verify_suffix}")
    set(_post "set(_foundation_native_destination ${_destination})\n")
    string(APPEND _post "if(IS_ABSOLUTE \"\${_foundation_native_destination}\")\n")
    string(APPEND _post "  set(_foundation_native_root \"\$ENV{DESTDIR}\${_foundation_native_destination}\")\n")
    string(APPEND _post "else()\n  set(_foundation_native_root \"\$ENV{DESTDIR}\${CMAKE_INSTALL_PREFIX}/\${_foundation_native_destination}\")\nendif()\n")
    string(APPEND _post "${_verify_prefix}\"\${_foundation_native_root}\"${_verify_suffix}")
    file(WRITE "${_after}" "${_post}")
    install(SCRIPT "${_before}")
    install(DIRECTORY "${FOUNDATION_APPENDED_ENGINE_NATIVE_RUNTIME_ROOT}/"
      DESTINATION "${destination}" USE_SOURCE_PERMISSIONS)
    # A changed source/copy or an extra pre-existing destination member must
    # fail installation rather than silently publish a mismatched runtime.
    install(SCRIPT "${_after}")
  endfunction()
  return()
endif()
if(FOUNDATION_APPENDED_ENGINE_NATIVE_DOCUMENT_PROFILE OR FOUNDATION_APPENDED_ENGINE_NATIVE_ACTIONS_PROFILE)
  message(FATAL_ERROR "The native document selector requires the explicit web or both appended profile")
endif()
if(NOT FOUNDATION_APPENDED_PROFILE STREQUAL "binary")
  message(FATAL_ERROR "The appended entry graph requires binary or an explicitly verified native document profile")
endif()
include("${CMAKE_CURRENT_LIST_DIR}/AppendedBinary.cmake")
# Historical native guard/header fixtures are development-only and do not supply
# the retained engine. Their C11 header test uses the explicitly enabled C leaf.
include("${CMAKE_CURRENT_LIST_DIR}/AppendedEngineProvider.cmake")

if(NOT EMSCRIPTEN)
  add_executable(foundation-appended-kernel src/appended/kernel_main.cpp)
  target_link_libraries(foundation-appended-kernel PRIVATE
    foundation_appended_module foundation_appended_providers foundation_appended_container foundation_appended_startup)
  target_include_directories(foundation-appended-kernel PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}/src")
  foundation_options(foundation-appended-kernel)
  install(TARGETS foundation-appended-kernel RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR})
  if(BUILD_TESTING)
    add_test(NAME appended.kernel COMMAND "${Python3_EXECUTABLE}" -B
      "${CMAKE_CURRENT_SOURCE_DIR}/tests/appended/check_kernel.py"
      --kernel "$<TARGET_FILE:foundation-appended-kernel>")
    foundation_test_prerequisites(appended.kernel foundation-appended-kernel)
    set_tests_properties(appended.kernel PROPERTIES LABELS "appended;focused" TIMEOUT 45)
  endif()
endif()
