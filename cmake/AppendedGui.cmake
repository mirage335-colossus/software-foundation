include("${CMAKE_CURRENT_LIST_DIR}/AppendedDemoServices.cmake")

# Pure editor value helpers remain generic GUI fixtures, independently of any
# appended or production editor profile selection.
if(BUILD_TESTING AND FOUNDATION_NODE_EXECUTABLE)
    foreach(_editor_helper text controller conduit)
        add_test(NAME foundation.gui.browser-editor-${_editor_helper} COMMAND "${FOUNDATION_NODE_EXECUTABLE}"
            "${CMAKE_CURRENT_SOURCE_DIR}/tests/browser_surface_editor_${_editor_helper}_test.mjs")
        foundation_test_prerequisites(foundation.gui.browser-editor-${_editor_helper})
        set_tests_properties(foundation.gui.browser-editor-${_editor_helper} PROPERTIES LABELS "gui;focused" TIMEOUT 30)
    endforeach()
    foreach(_editor_endpoint endpoint bootstrap)
        add_test(NAME foundation.gui.browser-editor-${_editor_endpoint} COMMAND "${FOUNDATION_NODE_EXECUTABLE}"
            "${CMAKE_CURRENT_SOURCE_DIR}/tests/browser_editor_${_editor_endpoint}_test.mjs")
        foundation_test_prerequisites(foundation.gui.browser-editor-${_editor_endpoint})
        set_tests_properties(foundation.gui.browser-editor-${_editor_endpoint} PROPERTIES LABELS "gui;focused" TIMEOUT 30)
    endforeach()
    add_test(NAME foundation.gui.browser-document-endpoint COMMAND "${FOUNDATION_NODE_EXECUTABLE}"
        "${CMAKE_CURRENT_SOURCE_DIR}/tests/browser_document_endpoint_test.mjs")
    foundation_test_prerequisites(foundation.gui.browser-document-endpoint)
    set_tests_properties(foundation.gui.browser-document-endpoint PROPERTIES LABELS "gui;focused" TIMEOUT 30)
endif()

# Generic lifecycle values are independently selectable in a default GUI tree.
# No engine, appended library or product application is linked by these fixtures.
if(BUILD_TESTING AND NOT EMSCRIPTEN)
    add_executable(foundation_gui_terminal_runner_test EXCLUDE_FROM_ALL tests/terminal_runner_test.cpp)
    target_link_libraries(foundation_gui_terminal_runner_test PRIVATE foundation_gui_boundary)
    target_include_directories(foundation_gui_terminal_runner_test PRIVATE
        "${CMAKE_CURRENT_SOURCE_DIR}" "${CMAKE_CURRENT_BINARY_DIR}")
    add_dependencies(foundation_gui_terminal_runner_test foundation_gui_contract)
    foundation_options(foundation_gui_terminal_runner_test)
    foundation_gui_check(terminal-runner foundation_gui_terminal_runner_test focused)
endif()
if(BUILD_TESTING AND CMAKE_SYSTEM_NAME STREQUAL "Linux" AND NOT EMSCRIPTEN)
    # Physical composition boundaries only are mocked. In particular, the both
    # fixture supplies its own counted factory; it never links the real VM leaf.
    set(_native_terminal_cases
        help cli-missing cli-relative cli-normalized cli-flag cli-extra
        missing-payload corrupt-payload invalid-startup plan-root physical-profile browser-profile
        invalid-profile verify-failure load-failure bind-failure graceful start-waiting
        runner-hooks unconfigured-start unadopted-start start-terminal start-blocked start-bound
        runner-terminal runner-blocked close-terminal close-blocked unfinished-close tty-failure
        tty-nonstd tty-return-failure binary-payload profile-0 profile-1 profile-2
        profile-3 profile-4 profile-5 profile-6 profile-7 profile-8
        profile-9 profile-10 profile-11 profile-12 profile-13 profile-14
        profile-15 profile-16 profile-17 profile-18 profile-19 profile-20
        profile-21 profile-22 profile-23 profile-24 profile-25 profile-26
        profile-27 profile-28 profile-29 profile-30 profile-31 profile-32
        profile-33 profile-34 profile-35 profile-36)
    foreach(_native_terminal_mode web both)
        set(_native_terminal_target foundation_gui_native_terminal_main_${_native_terminal_mode}_test)
        add_executable(${_native_terminal_target} EXCLUDE_FROM_ALL
            "${PROJECT_SOURCE_DIR}/tests/appended_engine_terminal_main_test.cpp")
        target_link_libraries(${_native_terminal_target} PRIVATE
            foundation_gui_boundary foundation_gui_appended_demo_services)
        target_include_directories(${_native_terminal_target} BEFORE PRIVATE
            "${PROJECT_SOURCE_DIR}/tests/fixtures/appended_engine_terminal"
            "${CMAKE_CURRENT_SOURCE_DIR}" "${CMAKE_CURRENT_SOURCE_DIR}/shared"
            "${PROJECT_SOURCE_DIR}/include" "${PROJECT_SOURCE_DIR}/abi/appended")
        target_compile_definitions(${_native_terminal_target} PRIVATE
            FOUNDATION_APPENDED_ENGINE_NATIVE_PROFILE_ENABLED=1)
        if(_native_terminal_mode STREQUAL "both")
            target_compile_definitions(${_native_terminal_target} PRIVATE FOUNDATION_APPENDED_BINARY_CAPABILITY=1)
        else()
            target_compile_definitions(${_native_terminal_target} PRIVATE FOUNDATION_APPENDED_BINARY_CAPABILITY=0)
        endif()
        target_compile_features(${_native_terminal_target} PRIVATE cxx_std_20)
        set_target_properties(${_native_terminal_target} PROPERTIES CXX_EXTENSIONS OFF)
        add_dependencies(${_native_terminal_target} foundation_gui_contract)
        foundation_options(${_native_terminal_target})
        foreach(_native_terminal_case IN LISTS _native_terminal_cases)
            set(_native_terminal_test foundation.gui.native-terminal-${_native_terminal_mode}-${_native_terminal_case})
            add_test(NAME ${_native_terminal_test} COMMAND ${_native_terminal_target} ${_native_terminal_case})
            foundation_test_prerequisites(${_native_terminal_test} ${_native_terminal_target})
            set_tests_properties(${_native_terminal_test} PROPERTIES LABELS "gui;appended;focused" TIMEOUT 15)
        endforeach()
    endforeach()
endif()

# Independent document-actions4083 main fixtures preserve the pixel selectors.
if(BUILD_TESTING AND CMAKE_SYSTEM_NAME STREQUAL "Linux" AND NOT EMSCRIPTEN)
    set(_native_terminal_actions_cases ${_native_terminal_cases})
    list(FILTER _native_terminal_actions_cases EXCLUDE REGEX "^profile-")
    list(REMOVE_ITEM _native_terminal_actions_cases cli-missing physical-profile browser-profile invalid-profile)
    list(APPEND _native_terminal_actions_cases default-runtime default-runtime-failure actions-cli-missing
        actions-browser actions-legacy-document actions-legacy-editor
        actions-legacy-document-dirty actions-legacy-editor-dirty actions-linux-arm64 actions-windows)
    foreach(_native_actions_index RANGE 0 96)
        list(APPEND _native_terminal_actions_cases actions-plan-${_native_actions_index})
    endforeach()
    foreach(_native_actions_index RANGE 0 90)
        list(APPEND _native_terminal_actions_cases actions-facts-${_native_actions_index})
    endforeach()
    foreach(_native_terminal_mode web both)
        set(_native_terminal_target foundation_gui_native_terminal_actions_main_${_native_terminal_mode}_test)
        add_executable(${_native_terminal_target} EXCLUDE_FROM_ALL
            "${PROJECT_SOURCE_DIR}/tests/appended_engine_terminal_main_test.cpp")
        target_link_libraries(${_native_terminal_target} PRIVATE
            foundation_gui_boundary foundation_gui_appended_demo_services)
        target_include_directories(${_native_terminal_target} BEFORE PRIVATE
            "${PROJECT_SOURCE_DIR}/tests/fixtures/appended_engine_terminal"
            "${CMAKE_CURRENT_SOURCE_DIR}" "${CMAKE_CURRENT_SOURCE_DIR}/shared"
            "${PROJECT_SOURCE_DIR}/include" "${PROJECT_SOURCE_DIR}/abi/appended")
        target_compile_definitions(${_native_terminal_target} PRIVATE
            FOUNDATION_APPENDED_ENGINE_NATIVE_PROFILE_ENABLED=1
            FOUNDATION_APPENDED_ENGINE_NATIVE_DOCUMENT_ACTIONS_PROFILE=1
            "FOUNDATION_APPENDED_ENGINE_NATIVE_RUNTIME_HINT=\"../share/software-foundation/engine-native\"")
        if(_native_terminal_mode STREQUAL "both")
            target_compile_definitions(${_native_terminal_target} PRIVATE FOUNDATION_APPENDED_BINARY_CAPABILITY=1)
        else()
            target_compile_definitions(${_native_terminal_target} PRIVATE FOUNDATION_APPENDED_BINARY_CAPABILITY=0)
        endif()
        target_compile_features(${_native_terminal_target} PRIVATE cxx_std_20)
        set_target_properties(${_native_terminal_target} PROPERTIES CXX_EXTENSIONS OFF)
        add_dependencies(${_native_terminal_target} foundation_gui_contract)
        foundation_options(${_native_terminal_target})
        foreach(_native_terminal_case IN LISTS _native_terminal_actions_cases)
            set(_native_terminal_test foundation.gui.native-terminal-actions-${_native_terminal_mode}-${_native_terminal_case})
            add_test(NAME ${_native_terminal_test} COMMAND ${_native_terminal_target} ${_native_terminal_case})
            foundation_test_prerequisites(${_native_terminal_test} ${_native_terminal_target})
            set_tests_properties(${_native_terminal_test} PROPERTIES LABELS "gui;appended;focused" TIMEOUT 15)
        endforeach()
    endforeach()
endif()

# Optional compositions share the generic GUI boundary. A declared project
# mode alone does not admit rich production; top-level retained-engine checks do.
if(NOT FOUNDATION_APPENDED_PROFILE MATCHES "^(binary|web|both)$")
    return()
endif()

function(foundation_gui_appended_test name target timeout)
    foundation_appended_test(${name} ${target} ${timeout})
    set_tests_properties(${name} PROPERTIES LABELS "gui;appended;focused")
endfunction()

# Common semantic tools are usable by all optional profiles. They remain pure
# document/view helpers rather than an HTML parser or JavaScript runtime.
# Same-document semantic projection is engine-independent application code.
# This utility does not add an HTML parser or JavaScript runtime to a binary kernel.
add_library(foundation_gui_appended_document STATIC EXCLUDE_FROM_ALL shared/appended_document.cpp)
target_link_libraries(foundation_gui_appended_document PUBLIC foundation_gui_boundary)
target_include_directories(foundation_gui_appended_document PUBLIC
    "${CMAKE_CURRENT_SOURCE_DIR}" "${PROJECT_SOURCE_DIR}/include")
add_dependencies(foundation_gui_appended_document foundation_gui_contract)
foundation_options(foundation_gui_appended_document)
add_library(foundation_gui_appended_document_codec STATIC EXCLUDE_FROM_ALL shared/appended_document_codec.cpp)
target_link_libraries(foundation_gui_appended_document_codec PUBLIC foundation_gui_appended_document)
foundation_options(foundation_gui_appended_document_codec)
add_library(foundation_gui_appended_document_controller STATIC EXCLUDE_FROM_ALL shared/appended_document_controller.cpp)
target_link_libraries(foundation_gui_appended_document_controller PUBLIC foundation_gui_appended_document_codec)
foundation_options(foundation_gui_appended_document_controller)
# One presenter joins the semantic body with native-v2 form observations.
# This remains engine-independent and does not add a browser to this profile.
add_library(foundation_gui_appended_document_forms STATIC EXCLUDE_FROM_ALL shared/appended_document_forms.cpp)
target_link_libraries(foundation_gui_appended_document_forms PUBLIC
    foundation_gui_appended_document_controller foundation_appended_document_forms)
foundation_options(foundation_gui_appended_document_forms)
add_library(foundation_gui_appended_document_v2_codec STATIC EXCLUDE_FROM_ALL
    shared/appended_document_v2_codec.cpp)
target_link_libraries(foundation_gui_appended_document_v2_codec PUBLIC
    foundation_gui_appended_document foundation_appended_document_forms)
set_target_properties(foundation_gui_appended_document_v2_codec PROPERTIES CXX_EXTENSIONS OFF)
foundation_options(foundation_gui_appended_document_v2_codec)

# Pure typed document-action packets reuse the existing same-document codec.
# This adds no provider, HTML implementation or guest VM to the target.
add_library(foundation_gui_document_action_v1_codec STATIC EXCLUDE_FROM_ALL
    shared/document_action_v1_codec.cpp)
target_link_libraries(foundation_gui_document_action_v1_codec PUBLIC
    foundation_gui_appended_document_v2_codec)
set_target_properties(foundation_gui_document_action_v1_codec PROPERTIES CXX_EXTENSIONS OFF)
foundation_options(foundation_gui_document_action_v1_codec)

# One application-side native document ledger and FormDraft recovery owner.
# Bitmap/editor and terminal compositions share this implementation; presentation
# and layout remain with their respective sole application presenter.
add_library(foundation_gui_engine_document_broker STATIC EXCLUDE_FROM_ALL
    shared/engine_document_broker.cpp)
target_link_libraries(foundation_gui_engine_document_broker PUBLIC
    foundation_gui_appended_document_v2_codec foundation_appended_engine_owner)
set_target_properties(foundation_gui_engine_document_broker PROPERTIES CXX_EXTENSIONS OFF)
foundation_options(foundation_gui_engine_document_broker)
target_link_libraries(foundation_gui_appended_document_forms PUBLIC foundation_gui_engine_document_broker)

# Application-side same-document terminal composition. The engine remains an
# external C-table provider; this target has no parser, renderer or guest VM.
add_library(foundation_gui_appended_engine_document_application STATIC EXCLUDE_FROM_ALL
    shared/appended_engine_document_application.cpp)
target_link_libraries(foundation_gui_appended_engine_document_application PUBLIC
    foundation_gui_appended_document_forms foundation_gui_appended_document_v2_codec
    foundation_gui_document_action_v1_codec foundation_appended_engine_owner foundation_gui_engine_document_broker)
set_target_properties(foundation_gui_appended_engine_document_application PROPERTIES CXX_EXTENSIONS OFF)
foundation_options(foundation_gui_appended_engine_document_application)

# The separate rich application consumes copied frames from the neutral owner.
# Its application logic and C++20 boundary do not include engine-private headers.
add_library(foundation_gui_appended_engine_application STATIC EXCLUDE_FROM_ALL
    shared/appended_engine_application.cpp)
target_link_libraries(foundation_gui_appended_engine_application PUBLIC
    foundation_gui_boundary foundation_appended_engine_owner foundation_gui_surface
    foundation_appended_editor_controller foundation_gui_engine_document_broker)
target_include_directories(foundation_gui_appended_engine_application PUBLIC "${CMAKE_CURRENT_SOURCE_DIR}")
add_dependencies(foundation_gui_appended_engine_application foundation_gui_contract)
set_target_properties(foundation_gui_appended_engine_application PROPERTIES CXX_EXTENSIONS OFF)
foundation_options(foundation_gui_appended_engine_application)

# Optional native C-table loading stays outside every default application graph.
# Only the matching OS source supplies acquisition; no engine is built or fetched.
if(NOT EMSCRIPTEN AND (WIN32 OR CMAKE_SYSTEM_NAME STREQUAL "Linux"))
    add_library(foundation_appended_native_engine_loader STATIC EXCLUDE_FROM_ALL
        shared/native_engine_loader.cpp)
    if(WIN32)
        target_sources(foundation_appended_native_engine_loader PRIVATE
            "${PROJECT_SOURCE_DIR}/src/appended/native_engine_loader_windows.cpp")
    else()
        target_sources(foundation_appended_native_engine_loader PRIVATE
            "${PROJECT_SOURCE_DIR}/src/appended/native_engine_loader_posix.cpp")
        target_link_libraries(foundation_appended_native_engine_loader PRIVATE ${CMAKE_DL_LIBS})
    endif()
    target_link_libraries(foundation_appended_native_engine_loader PUBLIC
        foundation_appended_native_engine_driver)
    target_include_directories(foundation_appended_native_engine_loader PRIVATE
        "${CMAKE_CURRENT_SOURCE_DIR}/shared" "${PROJECT_SOURCE_DIR}/src/appended")
    foundation_appended_options(foundation_appended_native_engine_loader)
endif()

# The native facade injects an already started Driver and the same real Owner.
# Its sole semantic presenter is separate from the bitmap browser composition.
if(NOT EMSCRIPTEN)
    add_library(foundation_gui_native_engine_document_composition STATIC EXCLUDE_FROM_ALL
        shared/native_engine_document_composition.cpp)
    target_link_libraries(foundation_gui_native_engine_document_composition PUBLIC
        foundation_gui_appended_engine_document_application foundation_appended_native_engine_driver)
    target_include_directories(foundation_gui_native_engine_document_composition PRIVATE
        "${CMAKE_CURRENT_SOURCE_DIR}/shared")
    target_compile_features(foundation_gui_native_engine_document_composition PUBLIC cxx_std_20)
    set_target_properties(foundation_gui_native_engine_document_composition PROPERTIES CXX_EXTENSIONS OFF)
    foundation_options(foundation_gui_native_engine_document_composition)

    # The bitmap facade shares the same started native Driver and Owner. This
    # library is independent of toolkit selection and contains no loader or VM.
    add_library(foundation_gui_native_engine_bitmap_composition STATIC EXCLUDE_FROM_ALL
        shared/native_engine_bitmap_composition.cpp)
    target_link_libraries(foundation_gui_native_engine_bitmap_composition PUBLIC
        foundation_gui_appended_engine_application foundation_appended_native_engine_driver)
    target_compile_features(foundation_gui_native_engine_bitmap_composition PUBLIC cxx_std_20)
    set_target_properties(foundation_gui_native_engine_bitmap_composition PROPERTIES CXX_EXTENSIONS OFF)
    foundation_options(foundation_gui_native_engine_bitmap_composition)
endif()

if(FOUNDATION_APPENDED_PROFILE STREQUAL "binary")
    add_library(foundation_gui_appended_application STATIC shared/appended_application.cpp)
    target_link_libraries(foundation_gui_appended_application PUBLIC foundation_gui_boundary
        foundation_appended_module foundation_appended_startup foundation_appended_providers)
    target_include_directories(foundation_gui_appended_application PUBLIC "${CMAKE_CURRENT_SOURCE_DIR}")
    add_dependencies(foundation_gui_appended_application foundation_gui_contract)
    foundation_options(foundation_gui_appended_application)
    if(EMSCRIPTEN)
        add_executable(foundation-gui-appended-web-wasm hosts/appended_wasm_main.cpp)
        target_link_libraries(foundation-gui-appended-web-wasm PRIVATE foundation_gui_appended_application)
        set_target_properties(foundation-gui-appended-web-wasm PROPERTIES OUTPUT_NAME gui_appended_web_wasm SUFFIX .js)
        foundation_options(foundation-gui-appended-web-wasm)
        target_link_options(foundation-gui-appended-web-wasm PRIVATE --no-entry
            -sMODULARIZE=1 -sEXPORT_ES6=1 -sALLOW_MEMORY_GROWTH=1
            # Keep raw function export names inspectable in optimized outputs.
            # Emscripten's supported export-lookup library disables renaming.
            -lexports.js
            "-sEXPORTED_FUNCTIONS=['_gui_web_prepare','_gui_web_create','_gui_web_receive','_gui_web_destroy','_gui_web_providers_v1','_malloc','_free']"
            "-sEXPORTED_RUNTIME_METHODS=['ccall','HEAPU8']" -sENVIRONMENT=web,worker,node
            "-sINCOMING_MODULE_JS_API=['wasmBinary','locateFile','print','printErr','onRuntimeInitialized']")
        foreach(module appended_wasm_worker appended_browser_bootstrap)
            configure_file("host/${module}.mjs" "${CMAKE_CURRENT_BINARY_DIR}/web/${module}.mjs" COPYONLY)
        endforeach()
    else()
        add_executable(foundation-appended-terminal hosts/appended_terminal_main.cpp)
        target_link_libraries(foundation-appended-terminal PRIVATE foundation_gui_appended_application)
        target_include_directories(foundation-appended-terminal PRIVATE "${CMAKE_CURRENT_BINARY_DIR}")
        foundation_options(foundation-appended-terminal)
        add_dependencies(foundation-gui-hosts foundation-appended-terminal)
        if(FOUNDATION_GUI_DISTRIBUTABLE)
            install(TARGETS foundation-appended-terminal RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR})
        endif()
    endif()
elseif(FOUNDATION_APPENDED_PROFILE MATCHES "^(web|both)$")
    if(FOUNDATION_APPENDED_PROFILE STREQUAL "both")
        target_compile_definitions(foundation_appended_engine_module_binding PRIVATE
            FOUNDATION_APPENDED_MODULE_VIEW_CAPABILITY=1)
        target_link_libraries(foundation_appended_engine_module_binding PRIVATE foundation_gui_boundary)
        add_dependencies(foundation_appended_engine_module_binding foundation_gui_contract)
    endif()
    if(EMSCRIPTEN)
        add_executable(foundation-gui-appended-engine-wasm hosts/appended_engine_wasm_main.cpp)
        target_link_libraries(foundation-gui-appended-engine-wasm PRIVATE
            foundation_gui_appended_engine_application foundation_gui_appended_demo_services)
        if(FOUNDATION_APPENDED_ENGINE_DOCUMENT_PROFILE)
            if(FOUNDATION_APPENDED_ENGINE_PHYSICAL_INPUT OR
                    NOT FOUNDATION_APPENDED_ENGINE_DOCUMENT_PROFILE MATCHES "^(pixel|physical|editor)$")
                message(FATAL_ERROR "Document engine GUI requires its separately verified retained profile")
            endif()
            if(FOUNDATION_APPENDED_ENGINE_DOCUMENT_PROFILE STREQUAL "editor")
                set(_foundation_engine_editor_profile_directory "${PROJECT_BINARY_DIR}/appended-engine-editor-profile")
                if(NOT FOUNDATION_APPENDED_ENGINE_EDITOR_CONSUMER_VERIFIED OR
                        NOT FOUNDATION_APPENDED_ENGINE_EDITOR_DIRECTORY STREQUAL _foundation_engine_editor_profile_directory OR
                        NOT EXISTS "${_foundation_engine_editor_profile_directory}/appended_engine_compiled_editor_profile.hpp")
                    message(FATAL_ERROR "Editor engine GUI is missing its separately verified private editor profile")
                endif()
                target_include_directories(foundation-gui-appended-engine-wasm PRIVATE "${_foundation_engine_editor_profile_directory}")
                target_compile_definitions(foundation-gui-appended-engine-wasm PRIVATE FOUNDATION_APPENDED_ENGINE_DOCUMENT_PROFILE=3)
            else()
                set(_foundation_engine_document_profile_directory "${PROJECT_BINARY_DIR}/appended-engine-document-profile")
                if(NOT FOUNDATION_APPENDED_ENGINE_DOCUMENT_CONSUMER_VERIFIED OR
                        NOT EXISTS "${_foundation_engine_document_profile_directory}/appended_engine_compiled_document_profile.hpp")
                    message(FATAL_ERROR "Document engine GUI is missing its verified private compiled profile")
                endif()
                target_include_directories(foundation-gui-appended-engine-wasm PRIVATE "${_foundation_engine_document_profile_directory}")
                if(FOUNDATION_APPENDED_ENGINE_DOCUMENT_PROFILE STREQUAL "pixel")
                    target_compile_definitions(foundation-gui-appended-engine-wasm PRIVATE FOUNDATION_APPENDED_ENGINE_DOCUMENT_PROFILE=1)
                else()
                    target_compile_definitions(foundation-gui-appended-engine-wasm PRIVATE FOUNDATION_APPENDED_ENGINE_DOCUMENT_PROFILE=2)
                endif()
            endif()
        elseif(FOUNDATION_APPENDED_ENGINE_PHYSICAL_INPUT)
            if(NOT FOUNDATION_APPENDED_ENGINE_CONSUMER_VERIFIED)
                message(FATAL_ERROR "Physical engine input requires the verified retained-engine admission")
            endif()
            set(_foundation_engine_input_profile_directory "${PROJECT_BINARY_DIR}/appended-engine-physical-input")
            if(NOT EXISTS "${_foundation_engine_input_profile_directory}/appended_engine_compiled_input_profile.hpp")
                message(FATAL_ERROR "Physical engine input is missing its verified private compiled profile")
            endif()
            target_include_directories(foundation-gui-appended-engine-wasm PRIVATE "${_foundation_engine_input_profile_directory}")
            target_compile_definitions(foundation-gui-appended-engine-wasm PRIVATE FOUNDATION_APPENDED_ENGINE_INPUT_PROFILE_ENABLED=1)
        endif()
        if(FOUNDATION_APPENDED_PROFILE STREQUAL "both")
            target_compile_definitions(foundation-gui-appended-engine-wasm PRIVATE FOUNDATION_APPENDED_BINARY_CAPABILITY=1)
            target_link_libraries(foundation-gui-appended-engine-wasm PRIVATE foundation_appended_engine_module_binding)
        else()
            target_compile_definitions(foundation-gui-appended-engine-wasm PRIVATE FOUNDATION_APPENDED_BINARY_CAPABILITY=0)
        endif()
        set_target_properties(foundation-gui-appended-engine-wasm PROPERTIES
            OUTPUT_NAME gui_appended_engine_wasm SUFFIX .js)
        foundation_options(foundation-gui-appended-engine-wasm)
        set(_foundation_engine_kernel_exports "-sEXPORTED_FUNCTIONS=['_gui_web_engine_bridge_v1','_gui_web_engine_profile_v1','_gui_web_application_composition_v1','_gui_web_engine_input_describe_v1','_gui_web_engine_document_describe_v1','_gui_web_engine_dispatch_v1','_gui_web_create','_gui_web_receive','_gui_web_destroy','_malloc','_free']")
        if(FOUNDATION_APPENDED_ENGINE_DOCUMENT_PROFILE STREQUAL "editor")
            string(REPLACE "'_gui_web_engine_dispatch_v1'" "'_gui_web_engine_editor_describe_v1','_gui_web_engine_dispatch_v1'"
                _foundation_engine_kernel_exports "${_foundation_engine_kernel_exports}")
        endif()
        target_link_options(foundation-gui-appended-engine-wasm PRIVATE --no-entry
            -sMODULARIZE=1 -sEXPORT_ES6=1 -sALLOW_MEMORY_GROWTH=1 -lexports.js
            "${_foundation_engine_kernel_exports}"
            "-sEXPORTED_RUNTIME_METHODS=['ccall','HEAPU8']" -sENVIRONMENT=web,worker,node
            "-sINCOMING_MODULE_JS_API=['wasmBinary','locateFile','print','printErr','onRuntimeInitialized']")
        # Retain the old bootstrap only for the rich graph's data-only base64 helper.
        # The binary factory/Worker and producer policy are not selected here.
        foreach(module appended_browser_bootstrap appended_engine_browser_bootstrap
                appended_engine_wasm_worker engine_kernel_bridge)
            configure_file("host/${module}.mjs" "${CMAKE_CURRENT_BINARY_DIR}/web/${module}.mjs" COPYONLY)
            configure_file("host/${module}.mjs" "${CMAKE_CURRENT_BINARY_DIR}/web-physical/${module}.mjs" COPYONLY)
            if(FOUNDATION_APPENDED_ENGINE_DOCUMENT_PROFILE STREQUAL "editor")
                configure_file("host/${module}.mjs" "${CMAKE_CURRENT_BINARY_DIR}/web-editor/${module}.mjs" COPYONLY)
                if(FOUNDATION_GUI_DISTRIBUTABLE)
                    install(FILES "${CMAKE_CURRENT_BINARY_DIR}/web-editor/${module}.mjs"
                        DESTINATION "${CMAKE_INSTALL_DATADIR}/software-foundation/web-editor")
                endif()
            endif()
            if(FOUNDATION_GUI_DISTRIBUTABLE AND (FOUNDATION_APPENDED_ENGINE_PHYSICAL_INPUT OR
                    FOUNDATION_APPENDED_ENGINE_DOCUMENT_PROFILE STREQUAL "physical"))
                install(FILES "${CMAKE_CURRENT_BINARY_DIR}/web-physical/${module}.mjs"
                    DESTINATION "${CMAKE_INSTALL_DATADIR}/software-foundation/web-physical")
            endif()
        endforeach()
        if(FOUNDATION_APPENDED_ENGINE_DOCUMENT_PROFILE STREQUAL "editor")
            configure_file("host/browser_document_endpoint.mjs"
                "${CMAKE_CURRENT_BINARY_DIR}/web-editor/browser_document_endpoint.mjs" COPYONLY)
            if(FOUNDATION_GUI_DISTRIBUTABLE)
                install(FILES "${CMAKE_CURRENT_BINARY_DIR}/web-editor/browser_document_endpoint.mjs"
                    DESTINATION "${CMAKE_INSTALL_DATADIR}/software-foundation/web-editor")
            endif()
        endif()
    else()
        if(NOT FOUNDATION_APPENDED_KERNEL_MAINTENANCE OR
                NOT FOUNDATION_APPENDED_ENGINE_CONSUMER_VERIFIED OR
                NOT FOUNDATION_APPENDED_ENGINE_NATIVE_CONSUMER_VERIFIED OR
                NOT (FOUNDATION_APPENDED_ENGINE_NATIVE_DOCUMENT_PROFILE STREQUAL "pixel" OR
                    (FOUNDATION_APPENDED_ENGINE_NATIVE_ACTIONS_PROFILE STREQUAL "document-actions-v1" AND
                     FOUNDATION_APPENDED_ENGINE_NATIVE_ACTIONS_CONSUMER_VERIFIED)) OR
                NOT CMAKE_SIZEOF_VOID_P EQUAL 8 OR
                NOT TARGET foundation_appended_native_engine_loader OR
                NOT FOUNDATION_APPENDED_ENGINE_NATIVE_RUNTIME_ROOT)
            message(FATAL_ERROR "Native rich GUI requires verified pixel1795 or document-actions4083 admission and its restored runtime closure")
        endif()
        file(RELATIVE_PATH _foundation_native_runtime_hint "${CMAKE_INSTALL_FULL_BINDIR}"
            "${CMAKE_INSTALL_FULL_DATADIR}/software-foundation/engine-native")
        if(NOT _foundation_native_runtime_hint OR IS_ABSOLUTE "${_foundation_native_runtime_hint}" OR
                _foundation_native_runtime_hint MATCHES "[\r\n]")
            message(FATAL_ERROR "Native rich GUI requires an executable-relative installed runtime layout")
        endif()
        string(REPLACE "\\" "\\\\" _foundation_native_runtime_hint_cpp "${_foundation_native_runtime_hint}")
        string(REPLACE "\"" "\\\"" _foundation_native_runtime_hint_cpp "${_foundation_native_runtime_hint_cpp}")
        if(FOUNDATION_APPENDED_ENGINE_NATIVE_ACTIONS_PROFILE)
            set(_foundation_native_profile_directory "${PROJECT_BINARY_DIR}/appended-engine-native-actions-profile")
        else()
            set(_foundation_native_profile_directory "${PROJECT_BINARY_DIR}/appended-engine-native-profile")
        endif()
        if(NOT EXISTS "${_foundation_native_profile_directory}/appended_engine_compiled_native_profile.hpp")
            message(FATAL_ERROR "Native rich GUI is missing its verified private compiled profile")
        endif()
        add_executable(foundation-appended-engine-terminal hosts/appended_engine_terminal_main.cpp)
        target_link_libraries(foundation-appended-engine-terminal PRIVATE
            foundation_gui_appended_demo_services
            foundation_gui_native_engine_document_composition
            foundation_appended_native_engine_loader foundation_appended_startup)
        target_include_directories(foundation-appended-engine-terminal PRIVATE
            "${CMAKE_CURRENT_SOURCE_DIR}" "${CMAKE_CURRENT_BINARY_DIR}"
            "${_foundation_native_profile_directory}" "${PROJECT_SOURCE_DIR}/abi/appended")
        target_compile_definitions(foundation-appended-engine-terminal PRIVATE
            FOUNDATION_APPENDED_ENGINE_NATIVE_PROFILE_ENABLED=1)
        if(FOUNDATION_APPENDED_ENGINE_NATIVE_ACTIONS_PROFILE)
            target_compile_definitions(foundation-appended-engine-terminal PRIVATE
                FOUNDATION_APPENDED_ENGINE_NATIVE_DOCUMENT_ACTIONS_PROFILE=1
                "FOUNDATION_APPENDED_ENGINE_NATIVE_RUNTIME_HINT=\"${_foundation_native_runtime_hint_cpp}\"")
        endif()
        if(FOUNDATION_APPENDED_PROFILE STREQUAL "both")
            target_compile_definitions(foundation-appended-engine-terminal PRIVATE FOUNDATION_APPENDED_BINARY_CAPABILITY=1)
            target_link_libraries(foundation-appended-engine-terminal PRIVATE foundation_appended_engine_module_binding)
        else()
            target_compile_definitions(foundation-appended-engine-terminal PRIVATE FOUNDATION_APPENDED_BINARY_CAPABILITY=0)
        endif()
        target_compile_features(foundation-appended-engine-terminal PRIVATE cxx_std_20)
        set_target_properties(foundation-appended-engine-terminal PROPERTIES CXX_EXTENSIONS OFF)
        add_dependencies(foundation-appended-engine-terminal foundation_gui_contract)
        add_dependencies(foundation-gui-hosts foundation-appended-engine-terminal)
        foundation_options(foundation-appended-engine-terminal)
        if(FOUNDATION_GUI_DISTRIBUTABLE)
            install(TARGETS foundation-appended-engine-terminal RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR})
            # Installed resources are the complete restored binary archive,
            # including metadata and notices; never the retained source archive.
            foundation_appended_native_install_runtime("${CMAKE_INSTALL_DATADIR}/software-foundation/engine-native")
        endif()
    endif()
endif()

if(BUILD_TESTING)
    include("${PROJECT_SOURCE_DIR}/cmake/AppendedNativeGuiTests.cmake")
    foreach(_surface_fixture browser_surface browser_surface_codec browser_composition browser_editor_composition
            browser_document_codec browser_document_composition)
        string(REPLACE "_" "-" _surface_test_name "${_surface_fixture}")
        add_executable(foundation_gui_${_surface_fixture}_test EXCLUDE_FROM_ALL
            "tests/${_surface_fixture}_test.cpp")
        target_link_libraries(foundation_gui_${_surface_fixture}_test PRIVATE
            foundation_gui_boundary foundation_gui_surface foundation_appended_document_forms)
        target_include_directories(foundation_gui_${_surface_fixture}_test PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}")
        set_target_properties(foundation_gui_${_surface_fixture}_test PROPERTIES CXX_EXTENSIONS OFF)
        add_dependencies(foundation_gui_${_surface_fixture}_test foundation_gui_contract)
        foundation_gui_appended_test(foundation.gui.${_surface_test_name}
            foundation_gui_${_surface_fixture}_test 30)
    endforeach()
    add_executable(foundation_gui_document_endpoint_values_test EXCLUDE_FROM_ALL tests/document_endpoint_values_test.cpp)
    target_link_libraries(foundation_gui_document_endpoint_values_test PRIVATE foundation_gui_appended_document_forms)
    target_include_directories(foundation_gui_document_endpoint_values_test PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}")
    set_target_properties(foundation_gui_document_endpoint_values_test PROPERTIES CXX_EXTENSIONS OFF)
    foundation_options(foundation_gui_document_endpoint_values_test)
    foundation_gui_appended_test(foundation.gui.document-endpoint-values foundation_gui_document_endpoint_values_test 30)

    add_executable(foundation_gui_engine_document_broker_test EXCLUDE_FROM_ALL tests/engine_document_broker_test.cpp)
    target_link_libraries(foundation_gui_engine_document_broker_test PRIVATE foundation_gui_engine_document_broker)
    set_target_properties(foundation_gui_engine_document_broker_test PROPERTIES CXX_EXTENSIONS OFF)
    foundation_options(foundation_gui_engine_document_broker_test)
    foreach(_broker_case IN ITEMS
        "exact editor2035 profile admission"
        "query3 publication and metadata take fence"
        "one outstanding local ticket"
        "form6 publication before exact ACK7"
        "local UTF8 edit selection and native Apply"
        "stale public handles cannot stage work"
        "form presenter gate blocks Begin"
        "foreign publication candidate cannot commit"
        "Owner reservation preserves native sequence"
        "earlier pending publication cannot ACK native readback"
        "known pre-entry rejection has no ACK"
        "stale ACK2 cannot release action"
        "unknown transport has no ACK or replay"
        "malformed native packet is terminal"
        "terminal notification is metadata only"
        "local shutdown issues no cleanup"
        "Apply retains typed request across Owner busy"
        "clean Apply is rejected without native work"
        "service safe redaction and explicit query restore"
        "lease-free query preserves typed native authority"
        "typed native lease capacity rejects before effects and Finish releases it"
        "successive closed native form sessions do not exhaust lease capacity")
        string(TOLOWER "${_broker_case}" _broker_slug)
        string(REGEX REPLACE "[^a-z0-9]+" "-" _broker_slug "${_broker_slug}")
        set(_broker_test "foundation.gui.engine-document-broker-${_broker_slug}")
        if(EMSCRIPTEN)
            set_target_properties(foundation_gui_engine_document_broker_test PROPERTIES SUFFIX .cjs)
            add_test(NAME "${_broker_test}" COMMAND "${FOUNDATION_NODE_EXECUTABLE}"
                "$<TARGET_FILE:foundation_gui_engine_document_broker_test>" --case "${_broker_case}")
        else()
            add_test(NAME "${_broker_test}" COMMAND foundation_gui_engine_document_broker_test --case "${_broker_case}")
        endif()
        foundation_test_prerequisites("${_broker_test}" foundation_gui_engine_document_broker_test)
        set_tests_properties("${_broker_test}" PROPERTIES LABELS "gui;appended;focused" TIMEOUT 30)
    endforeach()

    add_executable(foundation_gui_engine_document_bitmap_broker_test EXCLUDE_FROM_ALL tests/engine_document_bitmap_broker_test.cpp)
    target_link_libraries(foundation_gui_engine_document_bitmap_broker_test PRIVATE foundation_gui_appended_engine_application)
    set_target_properties(foundation_gui_engine_document_bitmap_broker_test PROPERTIES CXX_EXTENSIONS OFF)
    foundation_options(foundation_gui_engine_document_bitmap_broker_test)
    foreach(_bitmap_broker_case IN ITEMS
        "Observe query3 sole publication and metadata Take"
        "Begin retires editor9 then physical3 before form6"
        "query publication failure preserves accepted State and pending candidate"
        "form publication failure preserves State and withholds ACK7"
        "ACK7 and Take preserve accepted content and publication revision"
        "document terminal notification stays metadata only"
        "terminal candidate redacts without semantic commit")
        string(TOLOWER "${_bitmap_broker_case}" _bitmap_broker_slug)
        string(REGEX REPLACE "[^a-z0-9]+" "-" _bitmap_broker_slug "${_bitmap_broker_slug}")
        set(_bitmap_broker_test "foundation.gui.engine-document-bitmap-${_bitmap_broker_slug}")
        if(EMSCRIPTEN)
            set_target_properties(foundation_gui_engine_document_bitmap_broker_test PROPERTIES SUFFIX .cjs)
            add_test(NAME "${_bitmap_broker_test}" COMMAND "${FOUNDATION_NODE_EXECUTABLE}"
                "$<TARGET_FILE:foundation_gui_engine_document_bitmap_broker_test>" --case "${_bitmap_broker_case}")
        else()
            add_test(NAME "${_bitmap_broker_test}" COMMAND foundation_gui_engine_document_bitmap_broker_test --case "${_bitmap_broker_case}")
        endif()
        foundation_test_prerequisites("${_bitmap_broker_test}" foundation_gui_engine_document_bitmap_broker_test)
        set_tests_properties("${_bitmap_broker_test}" PROPERTIES LABELS "gui;appended;focused" TIMEOUT 30)
    endforeach()
    if(FOUNDATION_NODE_EXECUTABLE AND NOT EMSCRIPTEN AND
            (WIN32 OR CMAKE_SYSTEM_NAME STREQUAL "Linux"))
        # Exercise the existing editor value codecs across C++/JS without
        # selecting editor input in any production host or renderer.
        add_test(NAME foundation.gui.browser-editor-codec-interop
            COMMAND "${Python3_EXECUTABLE}" -B
                "${PROJECT_SOURCE_DIR}/tests/run_appended_gui_fixture.py" editor
                "$<TARGET_FILE:foundation_gui_browser_surface_codec_test>"
                "${FOUNDATION_NODE_EXECUTABLE}"
                "${CMAKE_CURRENT_SOURCE_DIR}/tests/browser_surface_protocol_test.mjs")
        foundation_test_prerequisites(foundation.gui.browser-editor-codec-interop
            foundation_gui_browser_surface_codec_test)
        set_tests_properties(foundation.gui.browser-editor-codec-interop PROPERTIES
            LABELS "gui;appended;focused" TIMEOUT 60)
    endif()

    # These runtime-created plans and small providers are Linux component
    # fixtures, never native SDK eligibility or Windows execution evidence.
    if(CMAKE_SYSTEM_NAME STREQUAL "Linux" AND NOT EMSCRIPTEN)
        set(_native_loader_variants valid missing-symbol wrong-table
            getter-reject getter-throw getter-mutates)
        set(_native_loader_case_code 0)
        foreach(_native_loader_variant IN LISTS _native_loader_variants)
            string(REPLACE "-" "_" _native_loader_variant_target "${_native_loader_variant}")
            set(_native_loader_fixture "foundation_appended_native_engine_fixture_${_native_loader_variant_target}")
            add_library(${_native_loader_fixture} SHARED EXCLUDE_FROM_ALL
                "${PROJECT_SOURCE_DIR}/tests/fixtures/appended_native_engine_loader_provider.cpp")
            target_compile_definitions(${_native_loader_fixture} PRIVATE
                BIB_ENGINE_BUILD_DLL=1 "LOADER_FIXTURE_CASE=${_native_loader_case_code}")
            target_include_directories(${_native_loader_fixture} PRIVATE
                "${CMAKE_CURRENT_SOURCE_DIR}/shared" "${PROJECT_SOURCE_DIR}/abi/appended")
            foundation_appended_options(${_native_loader_fixture})
            set_target_properties(${_native_loader_fixture} PROPERTIES
                CXX_VISIBILITY_PRESET hidden VISIBILITY_INLINES_HIDDEN YES)
            math(EXPR _native_loader_case_code "${_native_loader_case_code} + 1")
        endforeach()
        add_executable(foundation_appended_native_engine_loader_test EXCLUDE_FROM_ALL
            "${PROJECT_SOURCE_DIR}/tests/appended_native_engine_loader_test.cpp")
        target_link_libraries(foundation_appended_native_engine_loader_test PRIVATE
            foundation_appended_native_engine_loader)
        target_include_directories(foundation_appended_native_engine_loader_test PRIVATE
            "${CMAKE_CURRENT_SOURCE_DIR}/shared" "${PROJECT_SOURCE_DIR}/src/appended")
        foundation_appended_options(foundation_appended_native_engine_loader_test)
        foreach(_native_loader_case IN ITEMS
                valid missing-symbol wrong-table getter-reject getter-throw getter-mutates
                missing-pin recipe-pin build-expectation legacy-profile physical-profile wrong-target
                relative-root traversal-entry unlisted-entry alias-case missing-parent missing-file
                extra-file extra-directory hash short-file long-file mode missing-notice reserved-path
                reserved-spaced-stem symlink-file symlink-directory symlink-root hardlink special-file)
            set(_native_loader_variant valid)
            if(_native_loader_case IN_LIST _native_loader_variants)
                set(_native_loader_variant "${_native_loader_case}")
            endif()
            string(REPLACE "-" "_" _native_loader_variant_target "${_native_loader_variant}")
            set(_native_loader_fixture "foundation_appended_native_engine_fixture_${_native_loader_variant_target}")
            set(_native_loader_test "appended.native-loader-${_native_loader_case}")
            add_test(NAME "${_native_loader_test}"
                COMMAND "${Python3_EXECUTABLE}" -B
                    "${PROJECT_SOURCE_DIR}/tests/run_appended_gui_fixture.py" loader
                    "${_native_loader_case}"
                    "$<TARGET_FILE:foundation_appended_native_engine_loader_test>"
                    "$<TARGET_FILE:${_native_loader_fixture}>")
            foundation_test_prerequisites("${_native_loader_test}"
                foundation_appended_native_engine_loader_test "${_native_loader_fixture}")
            set_tests_properties("${_native_loader_test}" PROPERTIES
                LABELS "gui;appended;focused" TIMEOUT 45)
        endforeach()
        set(_native_actions_loader_variants valid missing-symbol wrong-table getter-reject getter-throw
            getter-mutates command-limit query-limit reply-limit larger-limits)
        set(_native_loader_case_code 0)
        foreach(_native_loader_variant IN LISTS _native_actions_loader_variants)
            string(REPLACE "-" "_" _native_loader_variant_target "${_native_loader_variant}")
            set(_native_loader_fixture "foundation_appended_native_actions_fixture_${_native_loader_variant_target}")
            add_library(${_native_loader_fixture} SHARED EXCLUDE_FROM_ALL
                "${PROJECT_SOURCE_DIR}/tests/fixtures/appended_native_engine_loader_provider.cpp")
            target_compile_definitions(${_native_loader_fixture} PRIVATE BIB_ENGINE_BUILD_DLL=1
                LOADER_FIXTURE_PROFILE_KIND=4 "LOADER_FIXTURE_CASE=${_native_loader_case_code}")
            target_include_directories(${_native_loader_fixture} PRIVATE
                "${CMAKE_CURRENT_SOURCE_DIR}/shared" "${PROJECT_SOURCE_DIR}/abi/appended")
            foundation_appended_options(${_native_loader_fixture})
            set_target_properties(${_native_loader_fixture} PROPERTIES
                CXX_VISIBILITY_PRESET hidden VISIBILITY_INLINES_HIDDEN YES)
            math(EXPR _native_loader_case_code "${_native_loader_case_code} + 1")
        endforeach()
        foreach(_native_loader_case IN ITEMS actions-valid actions-missing-symbol actions-wrong-table
                actions-getter-reject actions-getter-throw actions-getter-mutates actions-command-limit
                actions-query-limit actions-reply-limit actions-larger-limits actions-profile-fields
                actions-plan-fields actions-inactive-profiles actions-old-table pixel-actions-table)
            set(_native_loader_variant valid)
            if(_native_loader_case STREQUAL "actions-old-table")
                set(_native_loader_fixture foundation_appended_native_engine_fixture_valid)
            else()
                string(REGEX REPLACE "^actions-" "" _native_actions_variant "${_native_loader_case}")
                if(_native_actions_variant IN_LIST _native_actions_loader_variants)
                    set(_native_loader_variant "${_native_actions_variant}")
                endif()
                string(REPLACE "-" "_" _native_loader_variant_target "${_native_loader_variant}")
                set(_native_loader_fixture "foundation_appended_native_actions_fixture_${_native_loader_variant_target}")
            endif()
            set(_native_loader_test "appended.native-loader-${_native_loader_case}")
            add_test(NAME "${_native_loader_test}" COMMAND "${Python3_EXECUTABLE}" -B
                "${PROJECT_SOURCE_DIR}/tests/run_appended_gui_fixture.py" loader "${_native_loader_case}"
                "$<TARGET_FILE:foundation_appended_native_engine_loader_test>" "$<TARGET_FILE:${_native_loader_fixture}>")
            foundation_test_prerequisites("${_native_loader_test}"
                foundation_appended_native_engine_loader_test "${_native_loader_fixture}")
            set_tests_properties("${_native_loader_test}" PROPERTIES LABELS "gui;appended;focused" TIMEOUT 45)
        endforeach()
    endif()
    if(FOUNDATION_NODE_EXECUTABLE)
        add_test(NAME foundation.gui.appended-web-services COMMAND "${FOUNDATION_NODE_EXECUTABLE}"
            "${CMAKE_CURRENT_SOURCE_DIR}/tests/appended_web_services_test.mjs")
        foundation_test_prerequisites(foundation.gui.appended-web-services)
        set_tests_properties(foundation.gui.appended-web-services PROPERTIES LABELS "gui;appended;focused" TIMEOUT 30)
        # These source fixtures use explicit factory/dispatcher fakes. They need
        # neither generated browser assets nor a retained engine/guest compiler.
        add_test(NAME foundation.gui.appended-engine-bridge COMMAND "${FOUNDATION_NODE_EXECUTABLE}"
            "${CMAKE_CURRENT_SOURCE_DIR}/tests/engine_kernel_bridge_test.mjs")
        foundation_test_prerequisites(foundation.gui.appended-engine-bridge)
        set_tests_properties(foundation.gui.appended-engine-bridge PROPERTIES LABELS "gui;appended;focused" TIMEOUT 30)
        add_test(NAME foundation.gui.appended-engine-worker COMMAND "${FOUNDATION_NODE_EXECUTABLE}"
            "${CMAKE_CURRENT_SOURCE_DIR}/tests/appended_engine_worker_test.mjs")
        foundation_test_prerequisites(foundation.gui.appended-engine-worker)
        set_tests_properties(foundation.gui.appended-engine-worker PROPERTIES LABELS "gui;appended;focused" TIMEOUT 30)
        add_test(NAME foundation.gui.appended-engine-input-transport COMMAND "${FOUNDATION_NODE_EXECUTABLE}"
            "${CMAKE_CURRENT_SOURCE_DIR}/tests/appended_engine_input_transport_test.mjs")
        foundation_test_prerequisites(foundation.gui.appended-engine-input-transport)
        set_tests_properties(foundation.gui.appended-engine-input-transport PROPERTIES
            LABELS "gui;appended;focused" TIMEOUT 30)
    endif()

    if(FOUNDATION_APPENDED_PROFILE STREQUAL "binary")
        add_executable(foundation_gui_appended_application_test EXCLUDE_FROM_ALL tests/appended_application_test.cpp)
        target_link_libraries(foundation_gui_appended_application_test PRIVATE foundation_gui_appended_application)
        foundation_gui_appended_test(foundation.gui.appended-application foundation_gui_appended_application_test 45)
    endif()

    add_executable(foundation_gui_appended_document_test EXCLUDE_FROM_ALL tests/appended_document_test.cpp)
    target_link_libraries(foundation_gui_appended_document_test PRIVATE foundation_gui_appended_document)
    foundation_gui_appended_test(foundation.gui.appended-document foundation_gui_appended_document_test 30)
    foreach(_document_part codec controller forms)
        add_executable(foundation_gui_appended_document_${_document_part}_test EXCLUDE_FROM_ALL
            tests/appended_document_${_document_part}_test.cpp)
        target_link_libraries(foundation_gui_appended_document_${_document_part}_test PRIVATE
            foundation_gui_appended_document_${_document_part})
        foundation_gui_appended_test(foundation.gui.appended-document-${_document_part}
            foundation_gui_appended_document_${_document_part}_test 30)
    endforeach()

    add_executable(foundation_gui_appended_document_v2_codec_test EXCLUDE_FROM_ALL
        tests/appended_document_v2_codec_test.cpp)
    target_link_libraries(foundation_gui_appended_document_v2_codec_test PRIVATE
        foundation_gui_appended_document_v2_codec)
    set_target_properties(foundation_gui_appended_document_v2_codec_test PROPERTIES CXX_EXTENSIONS OFF)
    foundation_gui_appended_test(foundation.gui.appended-document-v2-codec
        foundation_gui_appended_document_v2_codec_test 30)

    add_executable(foundation_gui_document_action_v1_codec_test EXCLUDE_FROM_ALL
        tests/document_action_v1_codec_test.cpp)
    target_link_libraries(foundation_gui_document_action_v1_codec_test PRIVATE
        foundation_gui_document_action_v1_codec)
    set_target_properties(foundation_gui_document_action_v1_codec_test PROPERTIES CXX_EXTENSIONS OFF)
    foundation_gui_appended_test(foundation.gui.document-action-v1-codec
        foundation_gui_document_action_v1_codec_test 30)
    if(EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/tests/document_action_v1_contract_test.py")
        add_test(NAME foundation.gui.document-action-v1-contract
            COMMAND "${Python3_EXECUTABLE}" -B
                "${CMAKE_CURRENT_SOURCE_DIR}/tests/document_action_v1_contract_test.py")
        foundation_test_prerequisites(foundation.gui.document-action-v1-contract)
        set_tests_properties(foundation.gui.document-action-v1-contract PROPERTIES
            LABELS "gui;appended;focused" TIMEOUT 30)
    endif()

    add_executable(foundation_gui_appended_engine_document_application_test EXCLUDE_FROM_ALL
        tests/appended_engine_document_application_test.cpp)
    target_link_libraries(foundation_gui_appended_engine_document_application_test PRIVATE
        foundation_gui_appended_engine_document_application)
    set_target_properties(foundation_gui_appended_engine_document_application_test PROPERTIES CXX_EXTENSIONS OFF)
    foundation_options(foundation_gui_appended_engine_document_application_test)
    if(EMSCRIPTEN)
        set_target_properties(foundation_gui_appended_engine_document_application_test PROPERTIES SUFFIX .cjs)
    endif()
    foreach(_document_case IN ITEMS
        "initial paired query and actual terminal Apply"
        "form publication fault before actual install"
        "form publication fault after actual install"
        "Cancel after delivered Apply retains cleanup"
        "retained query after actual publication fault"
        "semantic rejection/unknown versus acceptance"
        "endpoint unknown has no replay/ACK"
        "unsupported body action has positive no-entry proof"
        "navigation retains original four-field cleanup"
        "background retains exact action and fresh restore query"
        "real Registry safe publication before-install fault"
        "real Registry safe publication after-install fault"
        "typed body command10 and ACK11 fresh-query barrier"
        "certain body semantic outcomes have no replay"
        "body navigation retains exact old ACK11 target"
        "body publication fault before actual install"
        "body publication fault after actual install"
        "malformed body packet has no ACK or replay"
        "second effect requires new safe publication origin"
        "old in-flight query cannot release native gate"
        "rejected paired join cannot release native gate"
        "callback reentry cannot stage or acknowledge"
        "actual owner callback depth defers admission"
        "shutdown is local and idempotent")
        string(TOLOWER "${_document_case}" _document_case_slug)
        string(REGEX REPLACE "[^a-z0-9]+" "-" _document_case_slug "${_document_case_slug}")
        set(_document_test "foundation.gui.engine-document-${_document_case_slug}")
        if(EMSCRIPTEN)
            add_test(NAME "${_document_test}" COMMAND "${FOUNDATION_NODE_EXECUTABLE}"
                "$<TARGET_FILE:foundation_gui_appended_engine_document_application_test>"
                --case "${_document_case}")
        else()
            add_test(NAME "${_document_test}"
                COMMAND foundation_gui_appended_engine_document_application_test --case "${_document_case}")
        endif()
        foundation_test_prerequisites("${_document_test}" foundation_gui_appended_engine_document_application_test)
        set_tests_properties("${_document_test}" PROPERTIES LABELS "gui;appended;focused" TIMEOUT 30)
    endforeach()

    if(TARGET foundation_gui_native_engine_document_composition)
        add_executable(foundation_gui_native_engine_document_composition_test EXCLUDE_FROM_ALL
            "${PROJECT_SOURCE_DIR}/tests/appended_native_engine_document_composition_test.cpp")
        target_link_libraries(foundation_gui_native_engine_document_composition_test PRIVATE
            foundation_gui_native_engine_document_composition)
        target_include_directories(foundation_gui_native_engine_document_composition_test PRIVATE
            "${CMAKE_CURRENT_SOURCE_DIR}/shared")
        set_target_properties(foundation_gui_native_engine_document_composition_test PROPERTIES CXX_EXTENSIONS OFF)
        foundation_options(foundation_gui_native_engine_document_composition_test)
        foreach(_native_composition_case IN ITEMS query-apply-ack actual-cells callback-barriers
                presentation-retry registry-gate navigation-close uncertain-close owner-agreement
                callback-facts callback-close close-held-result observation-poll observation-modal
                observation-lifecycle observation-deadline observation-retry
                actions-start-progress actions-selection actions-ack-barriers actions-publication-retry
                actions-legacy-selection-refused)
            set(_native_composition_test "appended.native-document-composition-${_native_composition_case}")
            add_test(NAME "${_native_composition_test}"
                COMMAND foundation_gui_native_engine_document_composition_test "${_native_composition_case}")
            foundation_test_prerequisites("${_native_composition_test}"
                foundation_gui_native_engine_document_composition_test)
            set_tests_properties("${_native_composition_test}" PROPERTIES
                LABELS "gui;appended;focused" TIMEOUT 30)
        endforeach()
    endif()

    # Native binary-maintenance trees can run these source-level fixtures too.
    # They exercise the real neutral owner/host, not an integrated HTML engine.
    add_executable(foundation_gui_appended_engine_application_web_test EXCLUDE_FROM_ALL
        tests/appended_engine_application_test.cpp hosts/appended_engine_wasm_main.cpp)
    target_compile_definitions(foundation_gui_appended_engine_application_web_test PRIVATE
        FOUNDATION_APPENDED_BINARY_CAPABILITY=0)
    target_link_libraries(foundation_gui_appended_engine_application_web_test PRIVATE
        foundation_gui_appended_demo_services
        foundation_gui_appended_engine_application)
    foundation_gui_appended_test(foundation.gui.appended-engine-application-web
        foundation_gui_appended_engine_application_web_test 30)
    if(NOT EMSCRIPTEN)
        add_executable(foundation_gui_appended_engine_actions_bitmap_test EXCLUDE_FROM_ALL
            tests/appended_engine_actions_bitmap_test.cpp)
        target_link_libraries(foundation_gui_appended_engine_actions_bitmap_test PRIVATE
            foundation_gui_appended_engine_application Threads::Threads)
        set_target_properties(foundation_gui_appended_engine_actions_bitmap_test PROPERTIES CXX_EXTENSIONS OFF)
        foundation_options(foundation_gui_appended_engine_actions_bitmap_test)
        foreach(_actions_bitmap_case IN ITEMS
                "exact4083 admission" "view-only actual frames" "view-only Registry redaction"
                "interactive checked editor head" "interactive Registry editor9"
                "historical full-target editor9" "normal close after Owner retirement"
                "known head metadata close" "foreign editor close callback")
            string(TOLOWER "${_actions_bitmap_case}" _actions_bitmap_slug)
            string(REGEX REPLACE "[^a-z0-9]+" "-" _actions_bitmap_slug "${_actions_bitmap_slug}")
            set(_actions_bitmap_test "foundation.gui.engine-actions-bitmap-${_actions_bitmap_slug}")
            add_test(NAME ${_actions_bitmap_test}
                COMMAND foundation_gui_appended_engine_actions_bitmap_test --case "${_actions_bitmap_case}")
            foundation_test_prerequisites(${_actions_bitmap_test} foundation_gui_appended_engine_actions_bitmap_test)
            set_tests_properties(${_actions_bitmap_test} PROPERTIES LABELS "gui;appended;focused" TIMEOUT 30)
        endforeach()

        add_executable(foundation_gui_native_engine_bitmap_composition_test EXCLUDE_FROM_ALL
            "${PROJECT_SOURCE_DIR}/tests/appended_native_engine_bitmap_composition_test.cpp")
        target_link_libraries(foundation_gui_native_engine_bitmap_composition_test PRIVATE
            foundation_gui_native_engine_bitmap_composition Threads::Threads)
        set_target_properties(foundation_gui_native_engine_bitmap_composition_test PROPERTIES CXX_EXTENSIONS OFF)
        foundation_options(foundation_gui_native_engine_bitmap_composition_test)
        foreach(_native_bitmap_case readonly-frames owner-agreement presentation-retry
                wake-barriers callback-facts ordinary-turns independent-holds interactive-close
                unknown-retention close-timeout registry-gate completed-head-close)
            set(_native_bitmap_test "appended.native-bitmap-composition-${_native_bitmap_case}")
            add_test(NAME ${_native_bitmap_test}
                COMMAND foundation_gui_native_engine_bitmap_composition_test ${_native_bitmap_case})
            foundation_test_prerequisites(${_native_bitmap_test} foundation_gui_native_engine_bitmap_composition_test)
            set_tests_properties(${_native_bitmap_test} PROPERTIES LABELS "gui;appended;focused" TIMEOUT 30)
        endforeach()
    endif()
    # Each editor case owns process-lived retirement and terminal state. Never
    # combine them in one invocation or select a production engine to run them.
    add_executable(foundation_gui_appended_engine_editor_application_test EXCLUDE_FROM_ALL
        tests/appended_engine_editor_application_test.cpp)
    target_link_libraries(foundation_gui_appended_engine_editor_application_test PRIVATE
        foundation_gui_appended_engine_application)
    set_target_properties(foundation_gui_appended_engine_editor_application_test PROPERTIES
        CXX_EXTENSIONS OFF)
    foundation_options(foundation_gui_appended_engine_editor_application_test)
    if(EMSCRIPTEN)
        set_target_properties(foundation_gui_appended_engine_editor_application_test PROPERTIES SUFFIX .cjs)
    endif()
    foreach(_editor_application_case IN ITEMS
        "typed admission"
        "bind before query4"
        "checked-null mouse refresh"
        "accepted head and checked publication"
        "callback resync and native9"
        "actual Registry editor9 retirement"
        "unknown native8 retains opaque evidence"
        "consumed native8 publication throw before install"
        "consumed native8 publication throw after install"
        "explicit Owner terminal notification"
        "unclaimed head q4 native-effect cancellation"
        "consumed body key owns exact real release"
        "navigation checks old editor9 before new frame"
        "applied null retirement survives trusted redaction")
        string(TOLOWER "${_editor_application_case}" _editor_application_case_slug)
        string(REGEX REPLACE "[^a-z0-9]+" "-" _editor_application_case_slug "${_editor_application_case_slug}")
        set(_editor_application_test "foundation.gui.engine-editor-${_editor_application_case_slug}")
        if(EMSCRIPTEN)
            add_test(NAME "${_editor_application_test}" COMMAND "${FOUNDATION_NODE_EXECUTABLE}"
                "$<TARGET_FILE:foundation_gui_appended_engine_editor_application_test>"
                --case "${_editor_application_case}")
        else()
            add_test(NAME "${_editor_application_test}"
                COMMAND foundation_gui_appended_engine_editor_application_test
                    --case "${_editor_application_case}")
        endif()
        foundation_test_prerequisites("${_editor_application_test}"
            foundation_gui_appended_engine_editor_application_test)
        set_tests_properties("${_editor_application_test}" PROPERTIES
            LABELS "gui;appended;focused" TIMEOUT 30)
    endforeach()

    if(NOT EMSCRIPTEN)
        # FAKE TEST FACTS ONLY: deliberately ineligible synthetic pins. This is
        # the exact focused native fixture, not verified compiled-profile output,
        # retained SDK evidence or permission to enable a production consumer.
        # Only these four test targets receive this private include directory.
        set(_editor_host_fixture_directory "${CMAKE_CURRENT_BINARY_DIR}/test-fixtures/editor-host-ineligible")
        file(MAKE_DIRECTORY "${_editor_host_fixture_directory}")
        file(WRITE "${_editor_host_fixture_directory}/appended_engine_compiled_editor_profile.hpp" [=[
// Synthetic compiler fixture only. Not generated admission or SDK evidence.
#pragma once
#include "shared/engine_editor_profile.hpp"
#ifndef FOUNDATION_EDITOR_HOST_FIXTURE_FAULT
#define FOUNDATION_EDITOR_HOST_FIXTURE_FAULT 0
#endif
namespace foundation::appended::engine_editor {
inline const EngineEditorProfileFacts compiled_engine_editor_profile = [] {
    EngineEditorProfileFacts f;
    f.enabled = true; f.kind = ProfileKind::editor; f.name = kProfileName;
    f.provider_abi_major = 1; f.provider_abi_minor = 1;
    f.host_abi_major = 1; f.host_abi_minor = 0;
    f.target_system = BIB_ENGINE_TARGET_BROWSER_WASM;
    f.target_processor = BIB_ENGINE_CPU_WASM32; f.pointer_bits = 32;
    f.lifetime = BIB_ENGINE_LIFETIME_PROCESS; f.maximum_starts = 1;
    f.viewport_width = 800; f.viewport_height = 600;
    f.provider_capabilities = kProviderCapabilities;
    f.surface_capabilities = kSurfaceCapabilities;
    f.surface_protocol_version = 2; f.editor_protocol_version = 1;
    f.base_header_sha256 = engine_document::kBaseHeaderSha256;
    f.document_header_sha256 = engine_document::kExtensionHeaderSha256;
    f.document_contract_sha256 = engine_document::kContractSha256;
    f.document_catalog_sha256 = engine_document::kCatalogSha256;
    f.physical_catalog_sha256 = engine_document::kPhysicalCatalogSha256;
    f.editor_header_sha256 = kHeaderSha256; f.contract_sha256 = kContractSha256;
    f.catalog_sha256 = kCatalogSha256; f.schema_sha256 = kSchema;
    f.build_sha256.fill(0x51); f.source_recipe_sha256.fill(0x61);
    f.queries = kQueries; f.commands = kCommands;
    f.query_count = 2; f.command_count = 7;
#if FOUNDATION_EDITOR_HOST_FIXTURE_FAULT == 1
    f.enabled = false;
#elif FOUNDATION_EDITOR_HOST_FIXTURE_FAULT == 2
    f.target_system = BIB_ENGINE_TARGET_LINUX;
    f.target_processor = BIB_ENGINE_CPU_X86_64; f.pointer_bits = 64;
#elif FOUNDATION_EDITOR_HOST_FIXTURE_FAULT == 3
    f.contract_sha256[0] ^= 1;
#elif FOUNDATION_EDITOR_HOST_FIXTURE_FAULT == 4
    f.provider_capabilities = 2003;
#elif FOUNDATION_EDITOR_HOST_FIXTURE_FAULT == 5
    f.build_sha256 = {};
#elif FOUNDATION_EDITOR_HOST_FIXTURE_FAULT != 0
#error "Unknown synthetic editor fixture fault"
#endif
    return f;
}();
}
]=])
        foreach(_editor_host_variant IN ITEMS valid disabled invalid-target invalid-contract)
            set(_editor_host_selector 3)
            set(_editor_host_fault 0)
            set(_editor_host_argument unavailable)
            if(_editor_host_variant STREQUAL "valid")
                set(_editor_host_argument valid)
            elseif(_editor_host_variant STREQUAL "disabled")
                set(_editor_host_selector 0)
            elseif(_editor_host_variant STREQUAL "invalid-target")
                set(_editor_host_fault 2)
            elseif(_editor_host_variant STREQUAL "invalid-contract")
                set(_editor_host_fault 3)
            endif()
            string(REPLACE "-" "_" _editor_host_variant_target "${_editor_host_variant}")
            set(_editor_host_target "foundation_gui_appended_engine_editor_host_${_editor_host_variant_target}_test")
            add_executable(${_editor_host_target} EXCLUDE_FROM_ALL
                tests/appended_engine_editor_host_test.cpp hosts/appended_engine_wasm_main.cpp)
            target_include_directories(${_editor_host_target} PRIVATE "${_editor_host_fixture_directory}")
            target_compile_definitions(${_editor_host_target} PRIVATE
                FOUNDATION_APPENDED_BINARY_CAPABILITY=0
                FOUNDATION_APPENDED_ENGINE_DOCUMENT_PROFILE=${_editor_host_selector}
                FOUNDATION_EDITOR_HOST_FIXTURE_FAULT=${_editor_host_fault})
            target_link_libraries(${_editor_host_target} PRIVATE
                foundation_gui_appended_engine_application foundation_gui_appended_demo_services)
            set_target_properties(${_editor_host_target} PROPERTIES CXX_EXTENSIONS OFF)
            foundation_options(${_editor_host_target})
            set(_editor_host_test "foundation.gui.engine-editor-host-${_editor_host_variant}")
            add_test(NAME "${_editor_host_test}" COMMAND ${_editor_host_target} "${_editor_host_argument}")
            foundation_test_prerequisites("${_editor_host_test}" ${_editor_host_target})
            set_tests_properties("${_editor_host_test}" PROPERTIES LABELS "gui;appended;focused" TIMEOUT 30)
        endforeach()
    endif()

    add_executable(foundation_gui_appended_engine_bitmap_document_test EXCLUDE_FROM_ALL
        tests/appended_engine_bitmap_document_test.cpp)
    target_link_libraries(foundation_gui_appended_engine_bitmap_document_test PRIVATE
        foundation_gui_appended_engine_application)
    set_target_properties(foundation_gui_appended_engine_bitmap_document_test PROPERTIES
        CXX_EXTENSIONS OFF)
    foundation_gui_appended_test(foundation.gui.appended-engine-bitmap-document
        foundation_gui_appended_engine_bitmap_document_test 30)
    foreach(_bitmap_document_case IN ITEMS terminal-notify terminal-input terminal-native
            terminal-port-gate closed-presenter-debt)
        set(_bitmap_document_test "foundation.gui.appended-engine-bitmap-document-${_bitmap_document_case}")
        if(EMSCRIPTEN)
            add_test(NAME "${_bitmap_document_test}" COMMAND "${FOUNDATION_NODE_EXECUTABLE}"
                "$<TARGET_FILE:foundation_gui_appended_engine_bitmap_document_test>"
                --case "${_bitmap_document_case}")
        else()
            add_test(NAME "${_bitmap_document_test}"
                COMMAND foundation_gui_appended_engine_bitmap_document_test --case "${_bitmap_document_case}")
        endif()
        foundation_test_prerequisites("${_bitmap_document_test}"
            foundation_gui_appended_engine_bitmap_document_test)
        set_tests_properties("${_bitmap_document_test}" PROPERTIES
            LABELS "gui;appended;focused" TIMEOUT 30)
    endforeach()
    add_executable(foundation_gui_appended_engine_input_application_test EXCLUDE_FROM_ALL
        tests/appended_engine_input_application_test.cpp)
    target_link_libraries(foundation_gui_appended_engine_input_application_test PRIVATE
        foundation_gui_appended_engine_application)
    set_target_properties(foundation_gui_appended_engine_input_application_test PROPERTIES
        CXX_EXTENSIONS OFF)
    foundation_gui_appended_test(foundation.gui.appended-engine-input-application
        foundation_gui_appended_engine_input_application_test 30)
    if(TARGET foundation_appended_engine_module_binding)
        add_executable(foundation_gui_appended_engine_application_both_test EXCLUDE_FROM_ALL
            tests/appended_engine_application_test.cpp hosts/appended_engine_wasm_main.cpp)
        target_compile_definitions(foundation_gui_appended_engine_application_both_test PRIVATE
            FOUNDATION_APPENDED_BINARY_CAPABILITY=1)
        target_link_libraries(foundation_gui_appended_engine_application_both_test PRIVATE
        foundation_gui_appended_demo_services
            foundation_gui_appended_engine_application foundation_appended_engine_module_binding)
        foundation_gui_appended_test(foundation.gui.appended-engine-application-both
            foundation_gui_appended_engine_application_both_test 30)
    endif()
endif()

# Shared compiled/binary-primary composition and semantic service regressions.
include("${CMAKE_CURRENT_LIST_DIR}/AppendedCompositionTests.cmake")
