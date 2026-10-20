# Focused shared composition regressions; optional targets remain EXCLUDE_FROM_ALL.
include_guard(GLOBAL)
if(BUILD_TESTING)
  add_executable(foundation_gui_binary_view_model_test EXCLUDE_FROM_ALL
    tests/appended_binary_view_model_test.cpp)
  target_link_libraries(foundation_gui_binary_view_model_test PRIVATE
    foundation_gui_boundary foundation_appended_abi)
  target_include_directories(foundation_gui_binary_view_model_test PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}")
  add_dependencies(foundation_gui_binary_view_model_test foundation_gui_contract)
  target_compile_features(foundation_gui_binary_view_model_test PRIVATE cxx_std_20)
  set_target_properties(foundation_gui_binary_view_model_test PROPERTIES CXX_EXTENSIONS OFF)
  foundation_gui_appended_test(foundation.gui.binary-view-model foundation_gui_binary_view_model_test 30)

  add_executable(foundation_gui_region_composition_test EXCLUDE_FROM_ALL
    tests/appended_compiled_region_composition_test.cpp)
  target_link_libraries(foundation_gui_region_composition_test PRIVATE foundation_gui_appended_engine_application)
  add_executable(foundation_gui_prepared_service_poll_test EXCLUDE_FROM_ALL
    tests/browser_prepared_service_poll_test.cpp)
  target_link_libraries(foundation_gui_prepared_service_poll_test PRIVATE
    foundation_gui_boundary foundation_gui_surface foundation_appended_document_forms)
  add_executable(foundation_gui_native_closed_service_poll_test EXCLUDE_FROM_ALL
    tests/native_closed_service_poll_test.cpp)
  target_link_libraries(foundation_gui_native_closed_service_poll_test PRIVATE foundation_gui_native_surface)
  foreach(_target foundation_gui_region_composition_test foundation_gui_prepared_service_poll_test foundation_gui_native_closed_service_poll_test)
    target_include_directories(${_target} PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}" "${CMAKE_CURRENT_SOURCE_DIR}/shared")
    target_compile_features(${_target} PRIVATE cxx_std_20)
    set_target_properties(${_target} PROPERTIES CXX_EXTENSIONS OFF)
    add_dependencies(${_target} foundation_gui_contract)
  endforeach()
  add_executable(foundation_gui_compiled_redaction_identity_test EXCLUDE_FROM_ALL
    tests/compiled_redaction_identity_test.cpp)
  target_link_libraries(foundation_gui_compiled_redaction_identity_test PRIVATE foundation_gui_boundary)
  target_include_directories(foundation_gui_compiled_redaction_identity_test PRIVATE
    "${CMAKE_CURRENT_SOURCE_DIR}" "${CMAKE_CURRENT_SOURCE_DIR}/shared")
  target_compile_features(foundation_gui_compiled_redaction_identity_test PRIVATE cxx_std_20)
  set_target_properties(foundation_gui_compiled_redaction_identity_test PROPERTIES CXX_EXTENSIONS OFF)
  add_dependencies(foundation_gui_compiled_redaction_identity_test foundation_gui_contract)
  foundation_gui_appended_test(foundation.gui.compiled-redaction-identity foundation_gui_compiled_redaction_identity_test 15)

  foundation_gui_appended_test(foundation.gui.region-composition foundation_gui_region_composition_test 15)
  foundation_gui_appended_test(foundation.gui.prepared-service-poll foundation_gui_prepared_service_poll_test 15)
  foundation_gui_appended_test(foundation.gui.native-closed-service-poll foundation_gui_native_closed_service_poll_test 15)
endif()

# Integration fragment for cmake/AppendedGui.cmake (already optional-profile scoped).
# All paths are maintained checkout paths; no private runner/source projection.
if(BUILD_TESTING)
  add_executable(foundation_gui_document_owned_service_hold_test EXCLUDE_FROM_ALL
    "${PROJECT_SOURCE_DIR}/tests/appended_document_owned_service_hold_test.cpp")
  target_link_libraries(foundation_gui_document_owned_service_hold_test PRIVATE
    foundation_gui_appended_engine_document_application)
  target_include_directories(foundation_gui_document_owned_service_hold_test PRIVATE "${PROJECT_SOURCE_DIR}/gui")
  set_target_properties(foundation_gui_document_owned_service_hold_test PROPERTIES CXX_EXTENSIONS OFF)
  foundation_options(foundation_gui_document_owned_service_hold_test)
  foreach(_case publication query apply-ack native-effect)
    if(EMSCRIPTEN)
      set_target_properties(foundation_gui_document_owned_service_hold_test PROPERTIES SUFFIX .cjs)
      add_test(NAME "foundation.gui.document-owned-service.${_case}"
        COMMAND "${FOUNDATION_NODE_EXECUTABLE}" "$<TARGET_FILE:foundation_gui_document_owned_service_hold_test>" --case "${_case}")
    else()
      add_test(NAME "foundation.gui.document-owned-service.${_case}"
        COMMAND foundation_gui_document_owned_service_hold_test --case "${_case}")
    endif()
    foundation_test_prerequisites("foundation.gui.document-owned-service.${_case}" foundation_gui_document_owned_service_hold_test)
    set_tests_properties("foundation.gui.document-owned-service.${_case}" PROPERTIES TIMEOUT 15 LABELS "gui;appended;focused")
  endforeach()

  if(NOT EMSCRIPTEN AND TARGET foundation_gui_native_engine_document_composition)
    add_executable(foundation_gui_semantic_primary_document_test EXCLUDE_FROM_ALL
      "${PROJECT_SOURCE_DIR}/tests/semantic_primary_document_test.cpp")
    target_link_libraries(foundation_gui_semantic_primary_document_test PRIVATE
      foundation_gui_native_engine_document_composition)
    target_include_directories(foundation_gui_semantic_primary_document_test PRIVATE "${PROJECT_SOURCE_DIR}/gui")
    set_target_properties(foundation_gui_semantic_primary_document_test PROPERTIES CXX_EXTENSIONS OFF)
    foundation_options(foundation_gui_semantic_primary_document_test)
    foreach(_case compiled-html retry-before retry-after close-publication low-control-html offered-close native-effect effect-before-handle effect-after-handle)
      add_test(NAME "foundation.gui.semantic-primary.${_case}"
        COMMAND foundation_gui_semantic_primary_document_test --case "${_case}")
      foundation_test_prerequisites("foundation.gui.semantic-primary.${_case}" foundation_gui_semantic_primary_document_test)
      set_tests_properties("foundation.gui.semantic-primary.${_case}" PROPERTIES TIMEOUT 15 LABELS "gui;appended;focused")
    endforeach()
  endif()

  if(TARGET foundation_appended_providers AND TARGET foundation_appended_web_services)
    # Test-only selected leaf; default/provider-only production target is unchanged.
    add_library(foundation_gui_engine_module_view_binding_fixture STATIC EXCLUDE_FROM_ALL
      "${PROJECT_SOURCE_DIR}/gui/shared/appended_engine_module.cpp")
    target_compile_definitions(foundation_gui_engine_module_view_binding_fixture PRIVATE FOUNDATION_APPENDED_MODULE_VIEW_CAPABILITY=1)
    target_link_libraries(foundation_gui_engine_module_view_binding_fixture PUBLIC
      foundation_appended_providers foundation_appended_web_services PRIVATE foundation_gui_boundary)
    add_dependencies(foundation_gui_engine_module_view_binding_fixture foundation_gui_contract)
    foundation_appended_options(foundation_gui_engine_module_view_binding_fixture)
    add_library(foundation_appended_engine_module_no_gui_compile OBJECT EXCLUDE_FROM_ALL
      "${PROJECT_SOURCE_DIR}/gui/shared/appended_engine_module.cpp")
    target_compile_definitions(foundation_appended_engine_module_no_gui_compile PRIVATE FOUNDATION_APPENDED_MODULE_VIEW_CAPABILITY=0)
    target_link_libraries(foundation_appended_engine_module_no_gui_compile PRIVATE
      foundation_appended_providers foundation_appended_web_services)
    foundation_appended_options(foundation_appended_engine_module_no_gui_compile)
    add_executable(foundation_gui_engine_module_view_test EXCLUDE_FROM_ALL
      "${PROJECT_SOURCE_DIR}/gui/tests/appended_engine_module_view_test.cpp")
    target_link_libraries(foundation_gui_engine_module_view_test PRIVATE
      foundation_gui_engine_module_view_binding_fixture foundation_gui_boundary)
    target_include_directories(foundation_gui_engine_module_view_test PRIVATE "${PROJECT_SOURCE_DIR}/gui")
    set_target_properties(foundation_gui_engine_module_view_test PROPERTIES CXX_EXTENSIONS OFF)
    add_dependencies(foundation_gui_engine_module_view_test foundation_appended_engine_module_no_gui_compile)
    foundation_gui_appended_test(foundation.gui.engine-module-view foundation_gui_engine_module_view_test 30)
  endif()
endif()
