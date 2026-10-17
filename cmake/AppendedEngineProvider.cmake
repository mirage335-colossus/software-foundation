# Engine-private guard fixtures. These targets do not supply a WebCore binding
# or add an engine to a Foundation kernel. Ordinary and payload-only builds do
# not compile them; the actual retained-engine producer has its own toolchain.
add_library(foundation_appended_engine_actions_codec STATIC EXCLUDE_FROM_ALL
    third_party/appended-engine/portable/NativeDocumentActionsV1Codec.cpp
    third_party/appended-engine/portable/NativeDocumentV2Codec.cpp
    third_party/appended-engine/portable/NativeDocumentV2Types.cpp)
target_compile_features(foundation_appended_engine_actions_codec PUBLIC cxx_std_20)
target_include_directories(foundation_appended_engine_actions_codec PRIVATE
    "${CMAKE_CURRENT_SOURCE_DIR}/third_party/appended-engine/portable")
target_link_libraries(foundation_appended_engine_actions_codec PRIVATE foundation_appended_document_forms)
set_target_properties(foundation_appended_engine_actions_codec PROPERTIES CXX_EXTENSIONS OFF)
foundation_options(foundation_appended_engine_actions_codec)
add_library(foundation_appended_engine_provider STATIC EXCLUDE_FROM_ALL
    third_party/appended-engine/src/ProviderGuard.cpp
    third_party/appended-engine/src/LegacyHostAdapters.cpp)
target_compile_features(foundation_appended_engine_provider PUBLIC cxx_std_20)
target_include_directories(foundation_appended_engine_provider PUBLIC
    "${CMAKE_CURRENT_SOURCE_DIR}/include"
    "${CMAKE_CURRENT_SOURCE_DIR}/third_party/appended-engine/include")
target_include_directories(foundation_appended_engine_provider PRIVATE
    "${CMAKE_CURRENT_SOURCE_DIR}/gui/shared"
    "${CMAKE_CURRENT_SOURCE_DIR}/third_party/appended-engine/portable")
target_link_libraries(foundation_appended_engine_provider PRIVATE foundation_appended_editor_codec
    foundation_appended_engine_actions_codec)
set_target_properties(foundation_appended_engine_provider PROPERTIES
    CXX_EXTENSIONS OFF CXX_VISIBILITY_PRESET hidden VISIBILITY_INLINES_HIDDEN YES)
foundation_options(foundation_appended_engine_provider)
if(MSVC)
    target_compile_options(foundation_appended_engine_actions_codec PRIVATE /EHsc)
    target_compile_options(foundation_appended_engine_provider PRIVATE /EHsc)
else()
    target_compile_options(foundation_appended_engine_actions_codec PRIVATE -fexceptions)
    target_compile_options(foundation_appended_engine_provider PRIVATE -fexceptions)
endif()
if(EMSCRIPTEN)
    target_link_options(foundation_appended_engine_provider INTERFACE -fexceptions)
else()
    find_package(Threads REQUIRED)
    target_link_libraries(foundation_appended_engine_provider PRIVATE Threads::Threads)
endif()

# The current fake owner deliberately creates native threads. Its test inventory
# is native only; direct-worker Wasm binding requires its own focused tests.
if(BUILD_TESTING AND NOT EMSCRIPTEN)
    add_executable(foundation_appended_engine_provider_header_test EXCLUDE_FROM_ALL
        tests/appended_engine_provider_header_c11.c)
    target_include_directories(foundation_appended_engine_provider_header_test PRIVATE
        "${CMAKE_CURRENT_SOURCE_DIR}/include")
    set_target_properties(foundation_appended_engine_provider_header_test PROPERTIES
        C_STANDARD 11 C_STANDARD_REQUIRED ON C_EXTENSIONS OFF)
    foundation_options(foundation_appended_engine_provider_header_test)
    add_test(NAME appended.engine-provider-header COMMAND foundation_appended_engine_provider_header_test)
    foundation_test_prerequisites(appended.engine-provider-header foundation_appended_engine_provider_header_test)
    set_tests_properties(appended.engine-provider-header PROPERTIES LABELS "appended;focused" TIMEOUT 15)
    foreach(_provider_part guard adapters)
        add_executable(foundation_appended_engine_provider_${_provider_part}_test EXCLUDE_FROM_ALL
            "tests/appended_engine_provider_${_provider_part}_test.cpp")
        target_link_libraries(foundation_appended_engine_provider_${_provider_part}_test PRIVATE
            foundation_appended_engine_provider Threads::Threads)
        foundation_options(foundation_appended_engine_provider_${_provider_part}_test)
    endforeach()
    add_executable(foundation_appended_engine_document_provider_guard_test EXCLUDE_FROM_ALL
        tests/appended_engine_document_provider_guard_test.cpp)
    target_link_libraries(foundation_appended_engine_document_provider_guard_test PRIVATE
        foundation_appended_engine_provider Threads::Threads)
    foundation_options(foundation_appended_engine_document_provider_guard_test)
    add_executable(foundation_appended_engine_editor_provider_guard_test EXCLUDE_FROM_ALL
        tests/appended_engine_editor_provider_guard_test.cpp)
    target_include_directories(foundation_appended_engine_editor_provider_guard_test PRIVATE
        "${CMAKE_CURRENT_SOURCE_DIR}/gui/shared")
    target_link_libraries(foundation_appended_engine_editor_provider_guard_test PRIVATE
        foundation_appended_engine_provider foundation_appended_editor_codec Threads::Threads)
    foundation_options(foundation_appended_engine_editor_provider_guard_test)
    foreach(_editor_provider_case bind-validation minor-optin project project-noneditable
            project-unavailable apply revoke revoke-observed full-width malformed-observation
            malformed-revocation malformed-query deep-request-rejection retire-authority
            admission-rejected native-pending form-backpressure shared-sequence stale-no-replay
            sequence-max owned-observation owned-revocation owned-query owned-bindings
            enter-rejection reentry query-reentry revoke-reentry wrong-thread error throw unknown
            malformed-header malformed-target malformed-body reply-rejected reply-throw leave-throw
            size overflow handled sequence admit-throw query-error query-throw query-malformed-header
            query-malformed-target query-malformed-body query-reply-rejected query-reply-throw
            query-leave-throw query-size query-overflow query-zero-revision query-wrong-revision
            query-wrong-document query-navigation query-admit-throw revoke-error revoke-throw
            revoke-unknown revoke-malformed-header revoke-malformed-target revoke-malformed-body
            revoke-reply-rejected revoke-reply-throw revoke-leave-throw revoke-size revoke-overflow
            revoke-handled revoke-sequence revoke-admit-throw
            historical-revoke-once historical-revoke-bad-material historical-revoke-full-target
            historical-current-lanes historical-revoke-admit-reject historical-revoke-enter-reject
            historical-revoke-form-barrier historical-revoke-unknown)
        add_test(NAME "appended.engine-editor-provider-${_editor_provider_case}"
            COMMAND foundation_appended_engine_editor_provider_guard_test "${_editor_provider_case}")
        foundation_test_prerequisites("appended.engine-editor-provider-${_editor_provider_case}"
            foundation_appended_engine_editor_provider_guard_test)
        set_tests_properties("appended.engine-editor-provider-${_editor_provider_case}" PROPERTIES
            LABELS "appended;focused" TIMEOUT 15)
    endforeach()
    foreach(_document_provider_case bind-validation full-width physical-profile
            physical-command-lane physical-command-unknown physical-command-nonzero-reply minor-optin
            startup-validation malformed-command malformed-query action-shapes
            action-replay backpressure ack-metadata ack-old-document ack-capacity
            malformed-ack ack-retained-replies ack-unmatched ack-expired
            shared-query-sequence sequence-max request-validation enter-rejection
            reply-validation query-zero-revision query-wrong-revision query-error
            query-navigation query-malformed query-reply-validator inner-unknown
            terminal-unknown command-error command-malformed leave-throw retire-error
            retire-throw wrong-thread reentry)
        add_test(NAME "appended.engine-document-provider-${_document_provider_case}"
            COMMAND foundation_appended_engine_document_provider_guard_test "${_document_provider_case}")
        foundation_test_prerequisites("appended.engine-document-provider-${_document_provider_case}"
            foundation_appended_engine_document_provider_guard_test)
        set_tests_properties("appended.engine-document-provider-${_document_provider_case}" PROPERTIES
            LABELS "appended;focused" TIMEOUT 15)
    endforeach()
    add_test(NAME appended.engine-provider-adapters COMMAND foundation_appended_engine_provider_adapters_test)
    foundation_test_prerequisites(appended.engine-provider-adapters foundation_appended_engine_provider_adapters_test)
    set_tests_properties(appended.engine-provider-adapters PROPERTIES LABELS "appended;focused" TIMEOUT 15)
    foreach(_provider_case unbound bind-validation prefix startup-validation startup-failure
            enter-failure copied-start command-validation captured-reentry wrong-thread
            command-error command-malformed command-throw leave-throw command-token
            status-domain sequence-max query query-identity semantic-mode exit-latch
            outputs-alias enter-status-rejection)
        add_test(NAME "appended.engine-provider-${_provider_case}"
            COMMAND foundation_appended_engine_provider_guard_test "${_provider_case}")
        foundation_test_prerequisites("appended.engine-provider-${_provider_case}"
            foundation_appended_engine_provider_guard_test)
        set_tests_properties("appended.engine-provider-${_provider_case}" PROPERTIES
            LABELS "appended;focused" TIMEOUT 15)
    endforeach()
endif()
