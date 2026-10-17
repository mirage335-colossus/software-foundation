# Value/container and queued transport targets shared by optional appended
# profiles. This fragment has no guest VM or engine implementation dependency.
include_guard(GLOBAL)
get_filename_component(_foundation_appended_source_root "${CMAKE_CURRENT_LIST_DIR}/.." ABSOLUTE)

function(foundation_appended_options target)
  target_compile_features(${target} PUBLIC cxx_std_20)
  target_include_directories(${target} PUBLIC
    "$<BUILD_INTERFACE:${_foundation_appended_source_root}/include>"
    "$<INSTALL_INTERFACE:${CMAKE_INSTALL_INCLUDEDIR}>")
  set_target_properties(${target} PROPERTIES CXX_EXTENSIONS OFF)
  foundation_options(${target})
endfunction()

function(foundation_appended_test name target timeout)
  foundation_options(${target})
  if(EMSCRIPTEN)
    # Ordinary test runners are CommonJS even when GUI factories are ESM.
    set_target_properties(${target} PROPERTIES SUFFIX .cjs)
    add_test(NAME ${name} COMMAND "${FOUNDATION_NODE_EXECUTABLE}" "$<TARGET_FILE:${target}>")
  else()
    add_test(NAME ${name} COMMAND ${target})
  endif()
  foundation_test_prerequisites(${name} ${target})
  set_tests_properties(${name} PROPERTIES LABELS "appended;focused" TIMEOUT ${timeout})
endfunction()

add_library(foundation_appended_abi STATIC src/appended/abi.cpp src/appended/registry.cpp)
add_library(foundation_appended_container STATIC src/appended/container.cpp)
# Native carrier discovery is independent of the portable-module runtime. Keep
# its single boundary stamp in one optional object for every loader-enabled
# composition; declaring the target does not add it to ordinary component builds.
add_library(foundation_appended_startup STATIC EXCLUDE_FROM_ALL src/appended/startup.cpp)
target_link_libraries(foundation_appended_startup PUBLIC foundation_appended_container)
add_library(foundation_appended_resource_url STATIC EXCLUDE_FROM_ALL src/appended/resource_url.cpp)
add_library(foundation_appended_web_services STATIC EXCLUDE_FROM_ALL src/appended/web_services.cpp)
target_link_libraries(foundation_appended_web_services PUBLIC foundation_appended_abi)
include("${CMAKE_CURRENT_LIST_DIR}/AppendedDemoServices.cmake")
if(NOT EMSCRIPTEN)
  find_package(Threads REQUIRED)
  target_link_libraries(foundation_appended_web_services PUBLIC Threads::Threads)
endif()
add_library(foundation_appended_document_forms STATIC EXCLUDE_FROM_ALL src/appended/document_forms.cpp)
target_link_libraries(foundation_appended_document_forms PUBLIC foundation_appended_abi)
# Generic input policy, independent of supplier GUI and HTML implementations.
add_library(foundation_gui_surface STATIC EXCLUDE_FROM_ALL src/gui/surface.cpp)
# The copied editor wire and owner controller contain no HTML engine or VM.
# The pure C protocol leaf is private to this source graph; it is not an
# installed SDK include directory. Owner headers need it transitively in-tree.
add_library(foundation_appended_editor_codec STATIC EXCLUDE_FROM_ALL
  gui/shared/native_editor_codec.cpp)
target_include_directories(foundation_appended_editor_codec PUBLIC
  "$<BUILD_INTERFACE:${_foundation_appended_source_root}/abi/appended>")
add_library(foundation_appended_editor_controller STATIC EXCLUDE_FROM_ALL
  gui/shared/native_editor_controller.cpp gui/shared/native_editor_context_adapter.cpp)
target_link_libraries(foundation_appended_editor_controller PUBLIC foundation_gui_surface)
if(NOT EMSCRIPTEN)
  target_link_libraries(foundation_appended_editor_controller PRIVATE Threads::Threads)
endif()
add_library(foundation_appended_engine_owner STATIC EXCLUDE_FROM_ALL
  gui/shared/appended_engine_owner.cpp gui/shared/appended_engine_input_codec.cpp
  gui/shared/engine_document_mailbox.cpp)
target_link_libraries(foundation_appended_engine_owner PUBLIC
  foundation_appended_container foundation_appended_resource_url foundation_appended_web_services
  foundation_appended_editor_codec)
foreach(_appended_target foundation_appended_abi foundation_appended_container foundation_appended_startup
    foundation_appended_resource_url foundation_appended_web_services
    foundation_appended_document_forms foundation_gui_surface foundation_appended_editor_codec
    foundation_appended_editor_controller foundation_appended_engine_owner)
  foundation_appended_options(${_appended_target})
endforeach()

# Native C-table consumer only. This supplies neither an OS engine loader nor
# an admitted engine artifact, and the neutral closure has no guest VM.
if(NOT EMSCRIPTEN)
  add_library(foundation_appended_native_engine_driver STATIC EXCLUDE_FROM_ALL
    gui/shared/native_engine_driver.cpp)
  target_link_libraries(foundation_appended_native_engine_driver PUBLIC
    foundation_appended_engine_owner)
  foundation_appended_options(foundation_appended_native_engine_driver)
endif()

if(BUILD_TESTING)
  if(CMAKE_SYSTEM_NAME STREQUAL "Linux" AND NOT EMSCRIPTEN)
    add_executable(foundation_appended_self_relative_path_test EXCLUDE_FROM_ALL
      tests/appended_self_relative_path_test.cpp)
    target_link_libraries(foundation_appended_self_relative_path_test PRIVATE foundation_appended_startup)
    foundation_appended_options(foundation_appended_self_relative_path_test)
    add_test(NAME appended.self-relative-path COMMAND "${Python3_EXECUTABLE}" -B
      "${_foundation_appended_source_root}/tests/run_appended_self_relative_path_fixture.py"
      "$<TARGET_FILE:foundation_appended_self_relative_path_test>")
    foundation_test_prerequisites(appended.self-relative-path foundation_appended_self_relative_path_test)
    set_tests_properties(appended.self-relative-path PROPERTIES LABELS "appended;focused" TIMEOUT 90)
  endif()
  # Portable editor values and lifecycle fixtures need no engine, VM, supplier
  # GUI, or application. The coordinate helper is needed only by its selected
  # fixture in this graph; production engines retain their own private closure.
  add_library(foundation_appended_editor_projection STATIC EXCLUDE_FROM_ALL
    gui/shared/native_editor_projection.cpp)
  foundation_appended_options(foundation_appended_editor_projection)
  foreach(_editor_part controller codec projection)
    add_executable(foundation_gui_native_editor_${_editor_part}_test EXCLUDE_FROM_ALL
      "gui/tests/native_editor_${_editor_part}_test.cpp")
    target_include_directories(foundation_gui_native_editor_${_editor_part}_test PRIVATE
      "${_foundation_appended_source_root}/gui"
      "${_foundation_appended_source_root}/gui/shared")
    target_link_libraries(foundation_gui_native_editor_${_editor_part}_test PRIVATE
      foundation_appended_editor_${_editor_part})
    foundation_appended_options(foundation_gui_native_editor_${_editor_part}_test)
    foundation_appended_test(foundation.gui.native-editor-${_editor_part}
      foundation_gui_native_editor_${_editor_part}_test 30)
    set_tests_properties(foundation.gui.native-editor-${_editor_part} PROPERTIES
      LABELS "gui;appended;focused")
  endforeach()
  if(NOT EMSCRIPTEN)
    # These cases exercise real foreign std::threads, independently of an
    # engine. The non-pthread browser profile must not advertise this fixture.
    add_executable(foundation_gui_native_editor_context_adapter_test EXCLUDE_FROM_ALL
      gui/tests/native_editor_context_adapter_test.cpp)
    target_include_directories(foundation_gui_native_editor_context_adapter_test PRIVATE
      "${_foundation_appended_source_root}/gui/shared")
    target_link_libraries(foundation_gui_native_editor_context_adapter_test PRIVATE
      foundation_appended_editor_controller)
    foundation_appended_options(foundation_gui_native_editor_context_adapter_test)
    foundation_appended_test(foundation.gui.native-editor-context-adapter
      foundation_gui_native_editor_context_adapter_test 30)
    set_tests_properties(foundation.gui.native-editor-context-adapter PROPERTIES
      LABELS "gui;appended;focused")
  endif()
  if(FOUNDATION_BUILD_GUI)
    # GUI inputs are initialized by the later GUI subdirectory. Forward target
    # references keep this fixture on that exact patched boundary and guard,
    # without introducing supplier inputs into the portable fixtures above.
    add_executable(foundation_gui_browser_surface_editor_test EXCLUDE_FROM_ALL
      gui/tests/browser_surface_editor_test.cpp)
    target_link_libraries(foundation_gui_browser_surface_editor_test PRIVATE
      foundation_gui_boundary foundation_gui_surface)
    target_include_directories(foundation_gui_browser_surface_editor_test PRIVATE
      "${_foundation_appended_source_root}/gui")
    add_dependencies(foundation_gui_browser_surface_editor_test foundation_gui_contract)
    foundation_appended_options(foundation_gui_browser_surface_editor_test)
    foundation_appended_test(foundation.gui.browser-surface-editor
      foundation_gui_browser_surface_editor_test 30)
    set_tests_properties(foundation.gui.browser-surface-editor PROPERTIES
      LABELS "gui;appended;focused")
  endif()
  if(NOT EMSCRIPTEN)
    add_executable(foundation_appended_engine_editor_owner_test EXCLUDE_FROM_ALL
      tests/appended_engine_editor_owner_test.cpp)
    target_link_libraries(foundation_appended_engine_editor_owner_test PRIVATE foundation_appended_engine_owner)
    foundation_appended_options(foundation_appended_engine_editor_owner_test)
    foundation_appended_test(appended.engine-editor-owner foundation_appended_engine_editor_owner_test 30)
    foreach(_editor_owner_case unknown-query unknown-observation unknown-revoke close-claimed close-active
        notify-claimed notify-natural-return malformed-query-revision malformed-query-key unretired-query-token
        unproved-observation-token mismatched-revoke-proof inner-unknown-observation inner-unknown-revoke
        same-token-gui-owner matched-wrong-body-sequence matched-wrong-body-kind global-terminal-idle-sibling
        malformed-reserved-prefix malformed-short-prefix)
      add_test(NAME "appended.engine-editor-owner-${_editor_owner_case}"
        COMMAND foundation_appended_engine_editor_owner_test --case "${_editor_owner_case}")
      foundation_test_prerequisites("appended.engine-editor-owner-${_editor_owner_case}"
        foundation_appended_engine_editor_owner_test)
      set_tests_properties("appended.engine-editor-owner-${_editor_owner_case}" PROPERTIES
        LABELS "appended;focused" TIMEOUT 30)
    endforeach()
    add_executable(foundation_appended_native_editor_driver_test EXCLUDE_FROM_ALL
      tests/appended_native_editor_driver_test.cpp)
    target_link_libraries(foundation_appended_native_editor_driver_test PRIVATE foundation_appended_native_engine_driver)
    foundation_appended_options(foundation_appended_native_editor_driver_test)
    foreach(_editor_driver_case close-queued-revoke close-deferred-revoke close-unknown-revoke
        effect-retirement-drain effect-form-ack-drain effect-old-document-drain startup reservation metadata
        admission legacy-lanes query-owned query-null query-rejected-preentry query-success-noenter
        query-unknown-noenter query-malformed-buffer query-wrong-target query-wrong-revision query-wrong-document
        query-unknown query-unknown-opaque query-throw query-unbalanced observation-owned observation-navigation
        observation-rejected-preentry observation-success-noenter observation-unknown-noenter
        observation-negative-unknown-noenter observation-malformed-buffer observation-wrong-target
        observation-wrong-sequence observation-malformed-reply observation-unknown-status observation-unknown-zero
        observation-unknown-disposition observation-semantic-unknown observation-throw observation-unbalanced
        revoke-owned revoke-rejected-preentry revoke-success-noenter revoke-unknown-noenter
        revoke-negative-unknown-noenter revoke-malformed-buffer revoke-wrong-target revoke-wrong-sequence
        revoke-malformed-reply revoke-wrong-material revoke-unknown-status revoke-unknown-zero
        revoke-unknown-disposition revoke-semantic-unknown revoke-throw revoke-unbalanced)
      add_test(NAME "appended.native-editor-${_editor_driver_case}"
        COMMAND foundation_appended_native_editor_driver_test "${_editor_driver_case}")
      foundation_test_prerequisites("appended.native-editor-${_editor_driver_case}"
        foundation_appended_native_editor_driver_test)
      set_tests_properties("appended.native-editor-${_editor_driver_case}" PROPERTIES
        LABELS "appended;focused" TIMEOUT 15)
    endforeach()
  endif()
  add_executable(foundation_appended_engine_document_contract_test EXCLUDE_FROM_ALL
    tests/appended/engine_document_contract_test.cpp)
  target_include_directories(foundation_appended_engine_document_contract_test PRIVATE
    "${_foundation_appended_source_root}/include" "${_foundation_appended_source_root}/gui")
  target_compile_features(foundation_appended_engine_document_contract_test PRIVATE cxx_std_20)
  set_target_properties(foundation_appended_engine_document_contract_test PROPERTIES CXX_EXTENSIONS OFF)
  foundation_appended_test(appended.engine-document-contract
    foundation_appended_engine_document_contract_test 30)

  foreach(_suite abi registry container)
    add_executable(foundation_appended_${_suite}_test EXCLUDE_FROM_ALL "tests/appended/${_suite}_test.cpp")
    if(_suite STREQUAL "container")
      target_link_libraries(foundation_appended_${_suite}_test PRIVATE foundation_appended_container)
    else()
      target_link_libraries(foundation_appended_${_suite}_test PRIVATE foundation_appended_abi)
    endif()
    foundation_appended_test(appended.${_suite} foundation_appended_${_suite}_test 30)
  endforeach()
  add_executable(foundation_appended_resource_url_test EXCLUDE_FROM_ALL tests/appended_resource_url_test.cpp)
  target_link_libraries(foundation_appended_resource_url_test PRIVATE foundation_appended_resource_url)
  foundation_appended_test(appended.resource-url foundation_appended_resource_url_test 30)

  add_executable(foundation_appended_document_forms_test EXCLUDE_FROM_ALL tests/appended_document_forms_test.cpp)
  target_link_libraries(foundation_appended_document_forms_test PRIVATE foundation_appended_document_forms)
  foundation_appended_test(appended.document_forms foundation_appended_document_forms_test 30)

  add_executable(foundation_gui_surface_test EXCLUDE_FROM_ALL tests/gui_surface_test.cpp)
  target_link_libraries(foundation_gui_surface_test PRIVATE foundation_gui_surface)
  foundation_appended_test(foundation.gui.surface foundation_gui_surface_test 30)
  set_tests_properties(foundation.gui.surface PROPERTIES LABELS "gui;appended;focused")

  add_executable(foundation_appended_web_services_native_test EXCLUDE_FROM_ALL tests/appended/web_services_native_test.cpp)
  target_link_libraries(foundation_appended_web_services_native_test PRIVATE
    foundation_appended_web_services foundation_gui_appended_demo_services)
  foundation_appended_test(appended.web_services_native foundation_appended_web_services_native_test 30)

  # This executable proves the neutral owner's VM-free link closure. The other
  # owner fixture belongs to the optional binary leaf and uses actual guest code.
  add_executable(foundation_appended_engine_owner_web_test EXCLUDE_FROM_ALL tests/appended_engine_owner_web_test.cpp)
  target_link_libraries(foundation_appended_engine_owner_web_test PRIVATE foundation_appended_engine_owner)
  foundation_appended_test(appended.engine-owner-web foundation_appended_engine_owner_web_test 30)

  add_executable(foundation_appended_engine_document_owner_test EXCLUDE_FROM_ALL
    tests/appended_engine_document_owner_test.cpp)
  target_link_libraries(foundation_appended_engine_document_owner_test PRIVATE
    foundation_appended_engine_owner)
  foundation_appended_options(foundation_appended_engine_document_owner_test)
  foundation_appended_test(appended.engine-document-owner
    foundation_appended_engine_document_owner_test 30)
  foreach(_document_case unknown-query unknown-form unknown-form-zero close-claimed
      close-active module-unknown module-claimed module-unbalanced-turn
      module-unacked-form unknown-ack-raw module-held-ui module-multiple
      notify-direct notify-foreign-thread notify-claimed notify-natural-return)
    # Terminal provider state is process-lived; every case starts independently.
    if(EMSCRIPTEN)
      add_test(NAME "appended.engine-document-owner-${_document_case}"
        COMMAND "${FOUNDATION_NODE_EXECUTABLE}"
          "$<TARGET_FILE:foundation_appended_engine_document_owner_test>"
          --case "${_document_case}")
    else()
      add_test(NAME "appended.engine-document-owner-${_document_case}"
        COMMAND foundation_appended_engine_document_owner_test --case "${_document_case}")
    endif()
    foundation_test_prerequisites("appended.engine-document-owner-${_document_case}"
      foundation_appended_engine_document_owner_test)
    set_tests_properties("appended.engine-document-owner-${_document_case}" PROPERTIES
      LABELS "appended;focused" TIMEOUT 30)
  endforeach()

  foreach(_input_part codec owner)
    add_executable(foundation_appended_engine_input_${_input_part}_test EXCLUDE_FROM_ALL
      "tests/appended_engine_input_${_input_part}_test.cpp")
    target_include_directories(foundation_appended_engine_input_${_input_part}_test PRIVATE
      "${_foundation_appended_source_root}/gui/shared")
    target_link_libraries(foundation_appended_engine_input_${_input_part}_test PRIVATE
      foundation_appended_engine_owner)
    set_target_properties(foundation_appended_engine_input_${_input_part}_test PROPERTIES
      CXX_EXTENSIONS OFF)
    foundation_appended_test(appended.engine-input-${_input_part}
      foundation_appended_engine_input_${_input_part}_test 30)
  endforeach()

  if(NOT EMSCRIPTEN)
    add_executable(foundation_appended_native_engine_driver_test EXCLUDE_FROM_ALL
      tests/appended_native_engine_driver_test.cpp)
    target_link_libraries(foundation_appended_native_engine_driver_test PRIVATE
      foundation_appended_native_engine_driver)
    foundation_appended_options(foundation_appended_native_engine_driver_test)
    foreach(_native_case metadata startup services resources frames-scheduling
        replacement-close fatal-provider fatal-frame ready-timeout wrong-thread
        prestart-close owner-policy wake-progress fatal-delivery audit-reentry
        held-resource-close prospective-epoch waiting-close bound-wake-close)
      # One process per case: the real provider lifetime has no reset API.
      add_test(NAME "appended.native-engine-${_native_case}"
        COMMAND foundation_appended_native_engine_driver_test "${_native_case}")
      foundation_test_prerequisites("appended.native-engine-${_native_case}"
        foundation_appended_native_engine_driver_test)
      set_tests_properties("appended.native-engine-${_native_case}" PROPERTIES
        LABELS "appended;focused" TIMEOUT 15)
    endforeach()

    add_executable(foundation_appended_native_document_driver_test EXCLUDE_FROM_ALL
      tests/appended_native_document_driver_test.cpp)
    target_link_libraries(foundation_appended_native_document_driver_test PRIVATE
      foundation_appended_native_engine_driver)
    foundation_appended_options(foundation_appended_native_document_driver_test)
    foreach(_native_document_case ack-wire-boundaries metadata admission query-owned
        form-rejected query-rejected-preentry form-rejected-preentry
        query-success-noenter query-unknown-noenter query-malformed-buffer
        form-negative-unknown-noenter form-ack0 form-ack1 form-old-ack1 form-old-ack2
        ack-reentry ack-host-callback ack-host-callback-foreign ack-host-enter ack-unknown query-unknown
        form-unknown-status form-unknown-disposition query-throw query-unbalanced
        physical-order physical-unknown)
      add_test(NAME "appended.native-document-${_native_document_case}"
        COMMAND foundation_appended_native_document_driver_test "${_native_document_case}")
      foundation_test_prerequisites("appended.native-document-${_native_document_case}"
        foundation_appended_native_document_driver_test)
      set_tests_properties("appended.native-document-${_native_document_case}" PROPERTIES
        LABELS "appended;focused" TIMEOUT 15)
    endforeach()

    # Explicit4083 transport fixtures use native64 synthetic targets. They do
    # not establish an admitted provider or actual HTML engine runtime.
    add_executable(foundation_appended_engine_document_actions_owner_test EXCLUDE_FROM_ALL
      tests/appended_engine_document_actions_owner_test.cpp)
    target_link_libraries(foundation_appended_engine_document_actions_owner_test PRIVATE
      foundation_appended_engine_owner)
    foundation_appended_options(foundation_appended_engine_document_actions_owner_test)
    foundation_appended_test(appended.engine-document-actions-owner
      foundation_appended_engine_document_actions_owner_test 30)

    add_executable(foundation_appended_native_document_actions_driver_test EXCLUDE_FROM_ALL
      tests/appended_native_document_actions_driver_test.cpp)
    target_link_libraries(foundation_appended_native_document_actions_driver_test PRIVATE
      foundation_appended_native_engine_driver)
    foundation_appended_options(foundation_appended_native_document_actions_driver_test)
    foreach(_native_document_actions_case metadata body-ack0 body-ack1 body-old-ack1 body-old-ack2
        ack-reentry form-cross-body-ack body-cross-form-ack body-rejected-preentry
        body-unknown-status body-unknown-disposition body-consumed-no-turn body-unknown-no-turn
        body-malformed-buffer body-throw body-unbalanced ack-host-callback
        ack-host-callback-foreign ack-host-enter ack-unknown)
      # Each provider binding and terminal-state scenario needs a fresh process.
      add_test(NAME "appended.native-document-actions-${_native_document_actions_case}"
        COMMAND foundation_appended_native_document_actions_driver_test "${_native_document_actions_case}")
      foundation_test_prerequisites("appended.native-document-actions-${_native_document_actions_case}"
        foundation_appended_native_document_actions_driver_test)
      set_tests_properties("appended.native-document-actions-${_native_document_actions_case}" PROPERTIES
        LABELS "appended;focused" TIMEOUT 15)
    endforeach()
  endif()
endif()
