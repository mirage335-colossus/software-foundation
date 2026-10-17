# Deliberately selected portable-module capability. The common fragment stays
# usable without a C compiler, interpreter validation or third-party VM notices.
include_guard(GLOBAL)
include("${CMAKE_CURRENT_LIST_DIR}/AppendedCommon.cmake")

enable_language(C)
execute_process(COMMAND "${Python3_EXECUTABLE}" -B "${CMAKE_CURRENT_SOURCE_DIR}/tools/appended_wasm3.py"
  COMMAND_ERROR_IS_FATAL ANY OUTPUT_QUIET)
set(_wasm3_source "${CMAKE_CURRENT_SOURCE_DIR}/third_party/wasm3/source")
if(NOT EXISTS "${_wasm3_source}/m3_env.c")
  message(FATAL_ERROR "The pinned appended runtime source is missing; no dependency is downloaded automatically")
endif()

add_library(foundation_appended_wasm3 STATIC
  "${_wasm3_source}/m3_bind.c" "${_wasm3_source}/m3_code.c"
  "${_wasm3_source}/m3_compile.c" "${_wasm3_source}/m3_core.c"
  "${_wasm3_source}/m3_deterministic.c" "${_wasm3_source}/m3_env.c"
  "${_wasm3_source}/m3_exec.c" "${_wasm3_source}/m3_function.c"
  "${_wasm3_source}/m3_info.c" "${_wasm3_source}/m3_module.c"
  "${_wasm3_source}/m3_parse.c" "${_wasm3_source}/m3_snapshot.c"
  "${_wasm3_source}/m3_validate.c" "${_wasm3_source}/m3_xxh64.c")
set_target_properties(foundation_appended_wasm3 PROPERTIES C_STANDARD 99 C_STANDARD_REQUIRED ON C_EXTENSIONS OFF)
foundation_options(foundation_appended_wasm3)
target_include_directories(foundation_appended_wasm3 PUBLIC "$<BUILD_INTERFACE:${_wasm3_source}>")
target_compile_definitions(foundation_appended_wasm3 PUBLIC
  d_m3HasRefTypes=0 d_m3HasExtendedConst=0 d_m3HasMultiMemory=0
  d_m3HasMemory64=0 d_m3HasCompactImports=0 d_m3HasWideArithmetic=0
  d_m3HasAtomics=0 d_m3HasExceptionHandling=0 d_m3HasTypedRefs=0
  d_m3HasStackSwitching=0 d_m3HasSnapshots=0
  d_m3MaxLinearMemoryPages=256 d_m3MaxNativeStack=131072 d_m3MaxFunctionStackHeight=4096
  d_m3MaxFunctionSlots=8192 d_m3ValStack=1024 d_m3ValCtrlDepth=512)
if(EMSCRIPTEN)
  target_link_options(foundation_appended_wasm3 INTERFACE -sSTACK_SIZE=524288)
endif()
if(NOT MSVC)
  target_link_libraries(foundation_appended_wasm3 PRIVATE m)
endif()

add_library(foundation_appended_module STATIC src/appended/module_wasm3.cpp)
add_library(foundation_appended_providers STATIC src/appended/providers.cpp)
target_link_libraries(foundation_appended_module PUBLIC foundation_appended_abi PRIVATE foundation_appended_wasm3)
target_link_libraries(foundation_appended_providers PUBLIC foundation_appended_module)
# The neutral owner references this leaf only through an explicitly supplied
# factory. It introduces no dependency on legacy startup or native self-loading.
add_library(foundation_appended_engine_module_binding STATIC EXCLUDE_FROM_ALL gui/shared/appended_engine_module.cpp)
target_link_libraries(foundation_appended_engine_module_binding PUBLIC
  foundation_appended_providers foundation_appended_web_services)
foreach(_appended_target foundation_appended_module foundation_appended_providers
    foundation_appended_engine_module_binding)
  foundation_appended_options(${_appended_target})
endforeach()
foundation_notice_file("${CMAKE_CURRENT_SOURCE_DIR}/third_party/wasm3/LICENSE")
foundation_notice_file("${CMAKE_CURRENT_SOURCE_DIR}/third_party/wasm3/XXHASH-LICENSE")

if(BUILD_TESTING)
  foreach(_suite module providers)
    add_executable(foundation_appended_${_suite}_test EXCLUDE_FROM_ALL "tests/appended/${_suite}_test.cpp")
    if(_suite STREQUAL "module")
      target_link_libraries(foundation_appended_${_suite}_test PRIVATE foundation_appended_module)
    else()
      target_link_libraries(foundation_appended_${_suite}_test PRIVATE foundation_appended_providers)
    endif()
    foundation_appended_test(appended.${_suite} foundation_appended_${_suite}_test 30)
  endforeach()
  add_executable(foundation_appended_web_services_test EXCLUDE_FROM_ALL tests/appended/web_services_test.cpp)
  target_link_libraries(foundation_appended_web_services_test PRIVATE
    foundation_appended_web_services foundation_appended_providers)
  foundation_appended_test(appended.web_services foundation_appended_web_services_test 30)

  # This fixture hand-assembles its own provider module. It needs no guest SDK,
  # external module path or sample compilation to exercise the real interpreter.
  add_executable(foundation_appended_engine_owner_test EXCLUDE_FROM_ALL tests/appended_engine_owner_test.cpp)
  target_link_libraries(foundation_appended_engine_owner_test PRIVATE
    foundation_appended_engine_owner foundation_appended_engine_module_binding)
  foundation_appended_test(appended.engine-owner foundation_appended_engine_owner_test 30)
  if(NOT EMSCRIPTEN)
    add_executable(foundation_appended_native_engine_driver_both_test EXCLUDE_FROM_ALL
      tests/appended_native_engine_driver_test.cpp)
    target_compile_definitions(foundation_appended_native_engine_driver_both_test PRIVATE
      FOUNDATION_NATIVE_ENGINE_TEST_MODULE=1)
    target_link_libraries(foundation_appended_native_engine_driver_both_test PRIVATE
      foundation_appended_native_engine_driver foundation_appended_engine_module_binding)
    foundation_appended_options(foundation_appended_native_engine_driver_both_test)
    add_test(NAME appended.native-engine-both
      COMMAND foundation_appended_native_engine_driver_both_test both)
    foundation_test_prerequisites(appended.native-engine-both
      foundation_appended_native_engine_driver_both_test)
    set_tests_properties(appended.native-engine-both PROPERTIES
      LABELS "appended;focused" TIMEOUT 15)
  endif()
endif()
