# Physical loader/facade/window boundaries are explicit mocks here. These
# process-isolated entry fixtures need neither an eligible engine nor a toolkit.
include_guard(GLOBAL)
if(NOT BUILD_TESTING OR EMSCRIPTEN)
    return()
endif()

function(foundation_native_bitmap_entry_fixture target source selector binary)
    add_executable(${target} EXCLUDE_FROM_ALL "${PROJECT_SOURCE_DIR}/${source}")
    target_include_directories(${target} BEFORE PRIVATE
        "${PROJECT_SOURCE_DIR}/tests/fixtures/appended_engine_bitmap"
        "${CMAKE_CURRENT_SOURCE_DIR}" "${CMAKE_CURRENT_SOURCE_DIR}/shared"
        "${PROJECT_SOURCE_DIR}/include" "${PROJECT_SOURCE_DIR}/abi/appended")
    target_compile_definitions(${target} PRIVATE
        FOUNDATION_APPENDED_ENGINE_NATIVE_PROFILE_ENABLED=1
        FOUNDATION_APPENDED_ENGINE_NATIVE_DOCUMENT_ACTIONS_PROFILE=${selector}
        FOUNDATION_APPENDED_BINARY_CAPABILITY=${binary}
        "FOUNDATION_APPENDED_ENGINE_NATIVE_RUNTIME_HINT=\"../share/software-foundation/engine-native\"")
    target_link_libraries(${target} PRIVATE
        foundation_gui_native_surface foundation_appended_abi
        foundation_gui_appended_demo_services Threads::Threads)
    target_compile_features(${target} PRIVATE cxx_std_20)
    set_target_properties(${target} PROPERTIES CXX_EXTENSIONS OFF)
    foundation_options(${target})
endfunction()
function(foundation_native_bitmap_entry_case name target case)
    add_test(NAME ${name} COMMAND ${target} "${case}")
    foundation_test_prerequisites(${name} ${target})
    set_tests_properties(${name} PROPERTIES LABELS "gui;appended;focused" TIMEOUT 30)
endfunction()

set(_bitmap_entry_common_cases
    help cli-missing cli-relative cli-normalized cli-flag cli-extra cli-duplicate-root
    cli-duplicate-view cli-empty cli-many default-runtime default-runtime-failure
    view-only read-only-default output-required output-missing output-extra binary-payload
    graceful start-waiting runner-hooks missing-payload corrupt-payload invalid-startup
    plan-root verify-failure load-failure bind-failure unconfigured-start unadopted-start
    start-terminal start-blocked start-bound runner-terminal runner-blocked close-terminal
    close-blocked close-timeout runner-failure runner-nonstd runner-return-failure
    runner-no-app peer-not-ready facade-failure runner-after-app-failure
    runner-after-app-nonstd runner-after-app-return-failure runner-unresolved foreign-native-target
    runner-detached-without-shutdown runner-detached-metadata-debt runner-detached-metadata-drained
    utf8-root utf8-output utf8-both utf8-path-helper utf8-root-overlong utf8-root-surrogate
    utf8-root-truncated utf8-root-range utf8-root-continuation utf8-output-overlong
    utf8-output-surrogate utf8-output-truncated utf8-output-range utf8-output-continuation)
foreach(_bitmap_entry_profile pixel actions)
    set(_bitmap_entry_cases ${_bitmap_entry_common_cases})
    set(_bitmap_entry_selector 0)
    if(_bitmap_entry_profile STREQUAL "pixel")
        list(APPEND _bitmap_entry_cases physical-profile browser-profile pixel-legacy-actions
            pixel-legacy-actions-dirty pixel-legacy-editor pixel-legacy-editor-dirty
            pixel-valid-build-divergence pixel-valid-recipe-divergence)
        foreach(_bitmap_entry_index RANGE 0 36)
            list(APPEND _bitmap_entry_cases "profile-${_bitmap_entry_index}")
        endforeach()
    else()
        set(_bitmap_entry_selector 1)
        list(APPEND _bitmap_entry_cases actions-browser actions-legacy-document
            actions-legacy-editor actions-legacy-document-dirty actions-legacy-editor-dirty
            actions-valid-build-divergence actions-valid-recipe-divergence unsupported-editor)
        foreach(_bitmap_entry_index RANGE 0 96)
            list(APPEND _bitmap_entry_cases "actions-plan-${_bitmap_entry_index}")
        endforeach()
        foreach(_bitmap_entry_index RANGE 0 90)
            list(APPEND _bitmap_entry_cases "actions-facts-${_bitmap_entry_index}")
        endforeach()
    endif()
    foreach(_bitmap_entry_mode web both)
        set(_bitmap_entry_binary 0)
        if(_bitmap_entry_mode STREQUAL "both")
            set(_bitmap_entry_binary 1)
        endif()
        set(_bitmap_entry_target "foundation_gui_native_bitmap_entry_${_bitmap_entry_profile}_${_bitmap_entry_mode}_test")
        foundation_native_bitmap_entry_fixture(${_bitmap_entry_target}
            tests/appended_native_engine_bitmap_entry_test.cpp ${_bitmap_entry_selector} ${_bitmap_entry_binary})
        foreach(_bitmap_entry_case IN LISTS _bitmap_entry_cases)
            foundation_native_bitmap_entry_case(
                "appended.native-bitmap-entry-${_bitmap_entry_profile}-${_bitmap_entry_mode}-${_bitmap_entry_case}"
                ${_bitmap_entry_target} "${_bitmap_entry_case}")
        endforeach()
    endforeach()
endforeach()

set(_bitmap_framebuffer_target foundation_gui_native_bitmap_entry_framebuffer_loop_test)
foundation_native_bitmap_entry_fixture(${_bitmap_framebuffer_target}
    tests/fixtures/appended_engine_bitmap/framebuffer/render_loop_test.cpp 1 0)
target_include_directories(${_bitmap_framebuffer_target} BEFORE PRIVATE
    "${PROJECT_SOURCE_DIR}/tests/fixtures/appended_engine_bitmap/framebuffer")
foreach(_bitmap_framebuffer_case success error-frame error-detached)
    foundation_native_bitmap_entry_case("appended.native-bitmap-entry-framebuffer-loop-${_bitmap_framebuffer_case}"
        ${_bitmap_framebuffer_target} "${_bitmap_framebuffer_case}")
endforeach()
