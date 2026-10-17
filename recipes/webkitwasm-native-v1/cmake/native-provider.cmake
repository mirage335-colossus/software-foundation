# Source-only native document-provider graph. Include through the explicit
# PORT=Foundation engine producer, deferred until the real WebCore target and
# its private/forwarding-header include lists exist. This file does not discover
# tools, prepare dependencies, configure another tree or install an SDK/kernel.
# It does not establish native link/runtime or retained-group eligibility.
include_guard(GLOBAL)

function(_bib_native_provider_require_file path label)
    if(NOT IS_ABSOLUTE "${path}" OR NOT EXISTS "${path}" OR IS_DIRECTORY "${path}" OR IS_SYMLINK "${path}")
        message(FATAL_ERROR "Native provider maintenance requires an existing absolute ordinary ${label}: ${path}; no substitute or build fallback exists")
    endif()
    if("${path}" MATCHES "[;\"\n\r]" OR "${path}" MATCHES "\\$<")
        message(FATAL_ERROR "Native provider ${label} path cannot contain list, quote, newline or generator-expression syntax")
    endif()
endfunction()

function(_bib_native_provider_require_pin path pin label)
    _bib_native_provider_require_file("${path}" "${label}")
    string(LENGTH "${pin}" _pin_length)
    if(NOT _pin_length EQUAL 64 OR NOT "${pin}" MATCHES "^[0-9a-f]+$" OR "${pin}" MATCHES "^0+$")
        message(FATAL_ERROR "Native provider maintenance requires the independent exact SHA256 of ${label}")
    endif()
    file(SHA256 "${path}" _actual)
    if(NOT _actual STREQUAL pin)
        message(FATAL_ERROR "Native provider ${label} differs from its reviewed SHA256; refresh the explicit source/metadata input, never use a fallback")
    endif()
endfunction()

function(_bib_add_native_document_provider)
    if(NOT CMAKE_SYSTEM_NAME STREQUAL "Linux" OR EMSCRIPTEN OR WIN32)
        message(FATAL_ERROR "Native document-provider production currently requires the explicit Linux CPU port; Windows native dependencies, ABI/loader and runtime prerequisites remain unfinished")
    endif()
    if(NOT PORT STREQUAL "Foundation" OR NOT CMAKE_SIZEOF_VOID_P EQUAL 8)
        message(FATAL_ERROR "Native document provider requires PORT=Foundation and a real 64-bit native engine target")
    endif()
    if(WTF_CPU_X86_64 AND NOT WTF_CPU_ARM64)
        set(_dependency_target linux-x86_64)
    elseif(WTF_CPU_ARM64 AND NOT WTF_CPU_X86_64)
        set(_dependency_target linux-aarch64)
    else()
        message(FATAL_ERROR "Native document provider requires exactly one native x86_64 or aarch64 CPU selection")
    endif()
    foreach(_enabled IN ITEMS ENABLE_STATIC_JSC ENABLE_C_LOOP USE_SYSTEM_MALLOC USE_SKIA USE_SKIA_CPU_ONLY USE_GENERIC_EVENT_LOOP)
        if(NOT DEFINED ${_enabled} OR NOT ${_enabled})
            message(FATAL_ERROR "Native document provider requires the explicit CPU/CLoop port setting ${_enabled}=ON")
        endif()
    endforeach()
    foreach(_disabled IN ITEMS ENABLE_JIT ENABLE_DFG_JIT ENABLE_FTL_JIT ENABLE_WEBASSEMBLY ENABLE_REMOTE_INSPECTOR ENABLE_WEBGL ENABLE_WEBGPU)
        if(NOT DEFINED ${_disabled} OR ${_disabled})
            message(FATAL_ERROR "Native document provider requires the explicit CPU/CLoop port setting ${_disabled}=OFF")
        endif()
    endforeach()
    if(WTF_DEFAULT_EVENT_LOOP OR USE_WINDOWS_EVENT_LOOP OR CMAKE_CXX_COMPILER_TARGET MATCHES "wasm|emscripten")
        message(FATAL_ERROR "Native document provider cannot select a hidden GUI event loop or a Wasm compiler target")
    endif()

    # The explicit producer verifies architecture, provenance, runtime baseline,
    # PIC and the complete dependency/data closure BEFORE configuring WebKit.
    # Prefix/target agreement here is consistency only, never self-certification
    # of an arbitrary directory. No Wasm archives or ambient prefix may replace
    # the externally verified native inputs.
    if(NOT IS_ABSOLUTE "${BIB_NATIVE_PROVIDER_DEPENDENCY_PREFIX}" OR
            NOT IS_DIRECTORY "${BIB_NATIVE_PROVIDER_DEPENDENCY_PREFIX}" OR
            NOT IS_ABSOLUTE "${FOUNDATION_NATIVE_DEPENDENCY_PREFIX}" OR
            NOT IS_DIRECTORY "${FOUNDATION_NATIVE_DEPENDENCY_PREFIX}")
        message(FATAL_ERROR "Provide the externally verified BIB_NATIVE_PROVIDER_DEPENDENCY_PREFIX and matching FOUNDATION_NATIVE_DEPENDENCY_PREFIX; native dependency preparation is a separate maintenance prerequisite")
    endif()
    file(REAL_PATH "${BIB_NATIVE_PROVIDER_DEPENDENCY_PREFIX}" _dependency_prefix)
    file(REAL_PATH "${FOUNDATION_NATIVE_DEPENDENCY_PREFIX}" _port_prefix)
    if(NOT _dependency_prefix STREQUAL _port_prefix OR
            NOT BIB_NATIVE_PROVIDER_DEPENDENCY_TARGET STREQUAL _dependency_target OR
            NOT FOUNDATION_NATIVE_DEPENDENCY_TARGET STREQUAL _dependency_target OR
            _dependency_prefix MATCHES "(^|/)(wasm-sysroot|emsdk)(/|$)")
        message(FATAL_ERROR "Native provider and PORT=Foundation must use the same verified ${_dependency_target} dependency prefix; no cross-target or Wasm fallback exists")
    endif()
    if(NOT IS_ABSOLUTE "${BIB_NATIVE_PROVIDER_SOURCE_ROOT}" OR
            NOT IS_DIRECTORY "${BIB_NATIVE_PROVIDER_SOURCE_ROOT}" OR
            IS_SYMLINK "${BIB_NATIVE_PROVIDER_SOURCE_ROOT}")
        message(FATAL_ERROR "Provide the complete reviewed absolute BIB_NATIVE_PROVIDER_SOURCE_ROOT assembled for this native recipe")
    endif()
    file(REAL_PATH "${BIB_NATIVE_PROVIDER_SOURCE_ROOT}" _root)
    set(_engine "${_root}/source/engine")
    set(_embedder "${_root}/source/wrapper/src/embedder")
    set(_document "${_root}/source/document-provider")
    set(_foundation "${_root}/source/foundation")
    set(_binding "${_root}/source/provider-binding")

    # These MUST be supplied as exact reviewed native inputs; the browser
    # binding and copied Wasm transport cannot stand in. The single public
    # getter calls the implemented hidden C++ declaration
    # bib::provider_candidate::ensureNativeDocumentProviderBound() noexcept,
    # returning std::int32_t in the existing provider status domain. It runs
    # BEFORE GetterGate, on the same intended owner thread as START, without
    # constructors, Host/Page/VM calls or an exported registration function.
    # A declaration alone is insufficient: no implementation/success stub is
    # generated here. The selected Guard includes the native hook explicitly.
    _bib_native_provider_require_pin("${BIB_NATIVE_PROVIDER_BINDING_SOURCE}" "${BIB_NATIVE_PROVIDER_BINDING_SOURCE_SHA256}" "native binding source")
    _bib_native_provider_require_pin("${BIB_NATIVE_PROVIDER_BINDING_HEADER}" "${BIB_NATIVE_PROVIDER_BINDING_HEADER_SHA256}" "native binding header")
    _bib_native_provider_require_pin("${BIB_NATIVE_PROVIDER_METADATA_HEADER}" "${BIB_NATIVE_PROVIDER_METADATA_HEADER_SHA256}" "generated native metadata header")
    # Changed pinned bytes must cause a pin recheck before an incremental build;
    # LINK_DEPENDS alone would merely link the newly compiled unreviewed input.
    set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS
        "${BIB_NATIVE_PROVIDER_BINDING_SOURCE}" "${BIB_NATIVE_PROVIDER_BINDING_HEADER}"
        "${BIB_NATIVE_PROVIDER_METADATA_HEADER}")
    if(BIB_NATIVE_PROVIDER_BINDING_SOURCE STREQUAL BIB_NATIVE_PROVIDER_BINDING_HEADER OR
            BIB_NATIVE_PROVIDER_BINDING_SOURCE STREQUAL BIB_NATIVE_PROVIDER_METADATA_HEADER OR
            BIB_NATIVE_PROVIDER_BINDING_HEADER STREQUAL BIB_NATIVE_PROVIDER_METADATA_HEADER)
        message(FATAL_ERROR "Native binding source, header and generated metadata must be distinct reviewed inputs")
    endif()
    get_filename_component(_binding_name "${BIB_NATIVE_PROVIDER_BINDING_SOURCE}" NAME)
    if(_binding_name MATCHES "^(BibCopied.*|BibEngine.*Wasm.*|BibNativeHost|NativeHost)(\\.|$)")
        message(FATAL_ERROR "Native provider requires its actual reviewed native document binding, not a copied-Wasm binding or diagnostic host")
    endif()
    file(REAL_PATH "${BIB_NATIVE_PROVIDER_METADATA_HEADER}" _metadata)
    cmake_path(IS_PREFIX _root "${_metadata}" NORMALIZE _metadata_in_sources)
    file(REAL_PATH "${CMAKE_BINARY_DIR}" _build)
    cmake_path(IS_PREFIX _build "${_metadata}" NORMALIZE _metadata_in_build)
    if(_metadata_in_sources OR NOT _metadata_in_build)
        message(FATAL_ERROR "Generated native metadata must be outside reviewed sources and inside this explicit engine build tree")
    endif()

    foreach(_target IN ITEMS WebCore JavaScriptCore WTF PAL Skia::Skia Threads::Threads)
        if(NOT TARGET "${_target}")
            message(FATAL_ERROR "Native provider requires the already-created ${_target} target from the selected native engine/dependencies; no target discovery or build fallback exists")
        endif()
    endforeach()
    # A DSO's own PIC flag cannot repair non-PIC static engine archives. Set the
    # port's PIC policy before target creation; do not mutate engine flags here.
    foreach(_target IN ITEMS WebCore JavaScriptCore WTF PAL Skia::Skia)
        get_target_property(_aliased "${_target}" ALIASED_TARGET)
        if(_aliased)
            set(_actual_target "${_aliased}")
        else()
            set(_actual_target "${_target}")
        endif()
        get_target_property(_imported "${_actual_target}" IMPORTED)
        get_target_property(_kind "${_actual_target}" TYPE)
        get_target_property(_pic "${_actual_target}" POSITION_INDEPENDENT_CODE)
        if(NOT _imported AND _kind STREQUAL "STATIC_LIBRARY" AND NOT _pic)
            message(FATAL_ERROR "Native provider requires PIC ${_target} inputs selected before native engine configuration; this graph never rebuilds an incompatible archive")
        endif()
    endforeach()
    if(NOT WebCore_INCLUDE_DIRECTORIES OR NOT WebCore_PRIVATE_INCLUDE_DIRECTORIES)
        message(FATAL_ERROR "Include native-provider.cmake after WebCore target creation in its directory scope, with the actual private and forwarding-header include lists")
    endif()
    if(TARGET BibNativeProvider)
        message(FATAL_ERROR "This explicit engine tree already owns BibNativeProvider; use one producer graph")
    endif()

    # Closed 18-TU shared document/runtime selection plus ONE required native
    # binding. Reuse the patched WebCore/JSC/WTF/PAL/CPU-Skia targets rather than
    # compiling engine owners twice. In particular the modern Generic RunLoop
    # timer hook belongs to WTF, not another provider-side RunLoop object.
    set(_sources
        "${_embedder}/main.cpp"
        "${_embedder}/BibNativeMediaDisabled.cpp"
        "${_embedder}/BibIDBServer.cpp"
        "${_embedder}/EmbedderStrategies.cpp"
        "${_embedder}/BibAppResourceProfile.cpp"
        "${_embedder}/BibAppResources.cpp"
        "${_embedder}/BibFoundationServiceBridge.cpp"
        "${_embedder}/AppResourceQueue.cpp"
        "${_embedder}/resource_url.cpp"
        "${_document}/native/NativeFormsV2Combined.cpp"
        "${_document}/native/NativeDocumentV2Publisher.cpp"
        "${_document}/portable/NativeDocumentV2Types.cpp"
        "${_document}/portable/NativeDocumentV2Codec.cpp"
        "${_foundation}/third_party/appended-engine/src/ProviderGuard.cpp"
        "${_foundation}/third_party/appended-engine/src/LegacyHostAdapters.cpp"
        "${_foundation}/src/appended/document_forms.cpp"
        "${_foundation}/src/appended/abi.cpp"
        "${_binding}/binding/BibEngineProviderPreflight.cpp"
        "${BIB_NATIVE_PROVIDER_BINDING_SOURCE}")
    # document_forms.cpp supplies actual form selection/state validation used by
    # NativeForms/Publisher/Types; abi.cpp supplies its valid_utf8 implementation.
    set(_headers
        "${_embedder}/BibEngineProviderRuntime.h"
        "${_embedder}/BibEngineProviderLifecycleHooks.h"
        "${_embedder}/BibEngineProviderTimerHooks.h"
        "${_embedder}/BibEngineProviderDocumentProjection.h"
        "${_embedder}/BibFoundationServicesBootstrap.h"
        "${_document}/runtime/BibCopiedDocumentCatalog.hpp"
        "${_foundation}/include/foundation/appended/engine_provider.h"
        "${_foundation}/include/foundation/appended/engine_provider_document_v2.h"
        "${_foundation}/third_party/appended-engine/include/EnginePrivate.hpp"
        "${_foundation}/third_party/appended-engine/include/LegacyHostAdapters.hpp"
        "${_engine}/Source/WTF/wtf/generic/RunLoopGeneric.cpp"
        "${_root}/source/native/BibNativeProviderOnce.hpp"
        "${BIB_NATIVE_PROVIDER_BINDING_HEADER}"
        "${BIB_NATIVE_PROVIDER_METADATA_HEADER}")
    foreach(_source IN LISTS _sources _headers)
        _bib_native_provider_require_file("${_source}" "selected native source/header")
    endforeach()
    # RunLoop is a prerequisite check only, not another translation unit.
    list(REMOVE_ITEM _headers "${_engine}/Source/WTF/wtf/generic/RunLoopGeneric.cpp")
    get_filename_component(_native_binding_directory "${BIB_NATIVE_PROVIDER_BINDING_HEADER}" DIRECTORY)
    get_filename_component(_native_metadata_directory "${BIB_NATIVE_PROVIDER_METADATA_HEADER}" DIRECTORY)
    set(_exports "${CMAKE_CURRENT_FUNCTION_LIST_DIR}/native-provider.exports")
    _bib_native_provider_require_file("${_exports}" "anonymous getter-only ELF export map")

    add_library(BibNativeProvider SHARED EXCLUDE_FROM_ALL ${_sources} ${_headers})
    set_target_properties(BibNativeProvider PROPERTIES
        OUTPUT_NAME foundation-webcore-native-provider
        POSITION_INDEPENDENT_CODE ON
        CXX_VISIBILITY_PRESET hidden VISIBILITY_INLINES_HIDDEN YES
        CXX_EXTENSIONS OFF
        BUILD_WITH_INSTALL_RPATH TRUE INSTALL_RPATH "$ORIGIN"
        INSTALL_RPATH_USE_LINK_PATH FALSE)
    # Minimum language requirement only. Preserve the supplier's higher current
    # standard for engine-facing headers rather than forcing C++20 on WebCore.
    target_compile_features(BibNativeProvider PRIVATE cxx_std_20)
    target_compile_definitions(BibNativeProvider PRIVATE
        BIB_ENGINE_PROVIDER_NEUTRAL=1 BIB_ENGINE_PROVIDER_NATIVE=1
        BIB_ENGINE_PROVIDER_DOCUMENT_V2=1 BIB_APP_RESOURCES=1
        BIB_FOUNDATION_SERVICES=1 BIB_CPU_ONLY=1 BIB_ENGINE_BUILD_DLL=1
        "BIB_NATIVE_PROVIDER_BINDING_HEADER=\"${BIB_NATIVE_PROVIDER_BINDING_HEADER}\""
        "BIB_NATIVE_PROVIDER_METADATA_HEADER=\"${BIB_NATIVE_PROVIDER_METADATA_HEADER}\"")
    target_include_directories(BibNativeProvider PRIVATE
        "${_foundation}/include"
        "${_foundation}/third_party/appended-engine/include"
        "${_binding}/binding"
        "${_document}/native" "${_document}/portable" "${_document}/runtime"
        "${_embedder}" "${_native_binding_directory}" "${_native_metadata_directory}"
        ${WebCore_INCLUDE_DIRECTORIES} ${WebCore_PRIVATE_INCLUDE_DIRECTORIES})
    target_include_directories(BibNativeProvider SYSTEM PRIVATE ${WebCore_SYSTEM_INCLUDE_DIRECTORIES})
    target_link_libraries(BibNativeProvider PRIVATE WebCore Skia::Skia Threads::Threads)

    # These released helpers/bindings catch or throw C++ exceptions. Preserve
    # the existing flags of main, IDB, strategies, service bridge and all engine
    # targets; do not add -fexceptions globally or through an engine interface.
    set(_exception_sources
        "${_document}/native/NativeFormsV2Combined.cpp"
        "${_document}/native/NativeDocumentV2Publisher.cpp"
        "${_document}/portable/NativeDocumentV2Types.cpp"
        "${_document}/portable/NativeDocumentV2Codec.cpp"
        "${_foundation}/third_party/appended-engine/src/ProviderGuard.cpp"
        "${_foundation}/third_party/appended-engine/src/LegacyHostAdapters.cpp"
        "${_foundation}/src/appended/document_forms.cpp"
        "${_foundation}/src/appended/abi.cpp"
        "${_binding}/binding/BibEngineProviderPreflight.cpp"
        "${_embedder}/BibAppResources.cpp"
        "${_embedder}/AppResourceQueue.cpp"
        "${_embedder}/resource_url.cpp"
        "${BIB_NATIVE_PROVIDER_BINDING_SOURCE}")
    set_property(SOURCE ${_exception_sources} APPEND PROPERTY COMPILE_OPTIONS -fexceptions)
    # Anonymous map: a named ELF version node would be another public symbol
    # and fail native consumer admission. Guard is a direct DSO source so the
    # required getter is not hidden by static-archive exclusion switches.
    target_link_options(BibNativeProvider PRIVATE
        "LINKER:SHELL:--version-script \"${_exports}\""
        "LINKER:--no-undefined-version" "LINKER:-z,defs")
    set_property(TARGET BibNativeProvider APPEND PROPERTY LINK_DEPENDS
        "${_exports}" "${BIB_NATIVE_PROVIDER_BINDING_SOURCE}"
        "${BIB_NATIVE_PROVIDER_BINDING_HEADER}" "${BIB_NATIVE_PROVIDER_METADATA_HEADER}")
    # No install/publish or fake runtime evidence. A later actual native link,
    # private dependency audit, data/notices inventory and original runtime
    # checks must feed the existing native consumer before Foundation upkeep.
endfunction()

_bib_add_native_document_provider()
