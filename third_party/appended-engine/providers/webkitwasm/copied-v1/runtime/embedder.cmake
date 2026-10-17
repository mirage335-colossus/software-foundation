# BrowserInBrowser embedder target (Phase 2 first-paint gate).
#
# Included from Source/WebCore/PlatformEmscripten.cmake via
# cmake_language(DEFER CALL include ...) — i.e. this file executes in
# WebCore's directory scope AFTER the whole WebCore/CMakeLists.txt has been
# processed: the WebCore target exists and the include-dir lists are final.
# Include-dir consumption copies the WebCoreTestSupport pattern (the bottom
# of WebCore/CMakeLists.txt): WebCore's PRIVATE include dirs do not propagate
# through target_link_libraries, so internal-header consumers replicate them.

get_filename_component(BIB_EMBEDDER_DIR "${EMSCRIPTEN_EMBEDDER_CMAKE}" DIRECTORY)

# Source-only production successor. OFF preserves the complete diagnostic
# branch below. Enabling this option is a separate retained-engine maintenance
# operation; it does not select or build an application-specific owner/kernel.
option(BIB_ENGINE_PROVIDER_NEUTRAL "Enable the private app-neutral CPU engine provider candidate" OFF)
if (BIB_ENGINE_PROVIDER_NEUTRAL)
    if (NOT EMSCRIPTEN)
        message(FATAL_ERROR "BIB_ENGINE_PROVIDER_NEUTRAL currently requires the reviewed browser-Wasm Emscripten target; no native fallback exists")
    endif ()
    # Require an explicit selection, rather than changing the supplier default.
    # Source checks/import review must additionally establish that the retained
    # whole-tree objects actually use the matching non-pthread ABI.
    if (NOT DEFINED BIB_PTHREAD OR BIB_PTHREAD)
        message(FATAL_ERROR "BIB_ENGINE_PROVIDER_NEUTRAL requires explicit BIB_PTHREAD=OFF and compatible retained non-pthread engine inputs")
    endif ()
    if (CMAKE_SIZEOF_VOID_P AND NOT CMAKE_SIZEOF_VOID_P EQUAL 4)
        message(FATAL_ERROR "The first neutral provider candidate supports browser wasm32 only")
    endif ()

    # Explicit reviewed source inputs. Never infer a checkout from this ignored
    # overlay's location or silently consume another provider/header copy.
    set(BIB_ENGINE_PROVIDER_SOURCE_ROOT "" CACHE PATH "Absolute reviewed Foundation source checkout for the canonical contract and generic guard/adapters")
    set(BIB_ENGINE_PROVIDER_BINDING_ROOT "" CACHE PATH "Absolute reviewed actual-binding-v1 source root for the neutral binding and codec")
    foreach (_bib_root BIB_ENGINE_PROVIDER_SOURCE_ROOT BIB_ENGINE_PROVIDER_BINDING_ROOT)
        if (NOT IS_ABSOLUTE "${${_bib_root}}" OR NOT IS_DIRECTORY "${${_bib_root}}")
            message(FATAL_ERROR "${_bib_root} must name an explicit reviewed absolute source directory; no dependency or kernel build fallback exists")
        endif ()
    endforeach ()

    set(_bib_guard_source "${BIB_ENGINE_PROVIDER_SOURCE_ROOT}/third_party/appended-engine/src/ProviderGuard.cpp")
    set(_bib_adapters_source "${BIB_ENGINE_PROVIDER_SOURCE_ROOT}/third_party/appended-engine/src/LegacyHostAdapters.cpp")
    set(BIB_ENGINE_COPIED_SOURCE_ROOT "" CACHE PATH "Absolute reviewed copied-wasm-shim-v1 successor source root")
    set(BIB_ENGINE_COPIED_GENERATED_DIR "" CACHE PATH "Absolute build-tree-only directory with generated metadata outputs")
    if (NOT IS_ABSOLUTE "${BIB_ENGINE_COPIED_SOURCE_ROOT}" OR NOT IS_DIRECTORY "${BIB_ENGINE_COPIED_SOURCE_ROOT}")
        message(FATAL_ERROR "BIB_ENGINE_COPIED_SOURCE_ROOT must name the complete reviewed copied successor; no diagnostic fallback")
    endif ()
    if (NOT IS_ABSOLUTE "${BIB_ENGINE_COPIED_GENERATED_DIR}" OR NOT IS_DIRECTORY "${BIB_ENGINE_COPIED_GENERATED_DIR}")
        message(FATAL_ERROR "Generate reviewed metadata in an explicit build-only directory before this graph is configured")
    endif ()
    cmake_path(IS_PREFIX BIB_ENGINE_COPIED_SOURCE_ROOT "${BIB_ENGINE_COPIED_GENERATED_DIR}" NORMALIZE _bib_generated_inside_source)
    if (_bib_generated_inside_source)
        message(FATAL_ERROR "Generated identity cannot be placed inside retained copied source inputs")
    endif ()
    cmake_path(IS_PREFIX CMAKE_BINARY_DIR "${BIB_ENGINE_COPIED_GENERATED_DIR}" NORMALIZE _bib_generated_inside_build)
    if (NOT _bib_generated_inside_build)
        message(FATAL_ERROR "Copied generated metadata must be inside this explicit CMake binary tree")
    endif ()
    set(_bib_binding_source "${BIB_ENGINE_COPIED_SOURCE_ROOT}/runtime/BibCopiedPixelBinding.cpp")
    set(_bib_copied_sources
        "${BIB_ENGINE_COPIED_SOURCE_ROOT}/runtime/BibEngineWasmShim.cpp"
        "${BIB_ENGINE_COPIED_SOURCE_ROOT}/runtime/BibEngineCopiedHost.cpp"
        "${BIB_ENGINE_COPIED_SOURCE_ROOT}/portable/BibEngineCopiedDispatch.cpp"
        "${BIB_ENGINE_COPIED_SOURCE_ROOT}/portable/BibEngineCopiedRecord.cpp"
    )
    set(_bib_copied_metadata "${BIB_ENGINE_COPIED_GENERATED_DIR}/BibCopiedMetadata.generated.h")
    set(_bib_copied_provider_build "${BIB_ENGINE_COPIED_GENERATED_DIR}/provider-build.json")
    set(_bib_copied_pre "${BIB_ENGINE_COPIED_SOURCE_ROOT}/runtime/engine-copied-pre.js")
    set(_bib_copied_library "${BIB_ENGINE_COPIED_SOURCE_ROOT}/runtime/engine-copied-library.js")
    foreach (_bib_file ${_bib_copied_sources} "${_bib_copied_metadata}" "${_bib_copied_provider_build}" "${_bib_copied_pre}" "${_bib_copied_library}")
        if (NOT EXISTS "${_bib_file}" OR IS_DIRECTORY "${_bib_file}")
            message(FATAL_ERROR "Missing complete copied factory input ${_bib_file}; no configure/build/download fallback")
        endif ()
    endforeach ()
    set(_bib_preflight_source "${BIB_ENGINE_PROVIDER_BINDING_ROOT}/binding/BibEngineProviderPreflight.cpp")
    set(_bib_codec_source "${BIB_ENGINE_PROVIDER_BINDING_ROOT}/codec/BibEngineProviderCodec.cpp")
    set(_bib_neutral_sources
        ${_bib_copied_sources}
        "${_bib_copied_metadata}"
        "${BIB_EMBEDDER_DIR}/BibAppResourceProfile.cpp"
        "${BIB_EMBEDDER_DIR}/BibIDBServer.cpp"
        "${BIB_EMBEDDER_DIR}/BibMediaPlayer.cpp"
        "${BIB_EMBEDDER_DIR}/EmbedderStrategies.cpp"
        "${BIB_EMBEDDER_DIR}/main.cpp"
        "${BIB_EMBEDDER_DIR}/BibEngineProviderRuntime.h"
        "${BIB_EMBEDDER_DIR}/BibEngineProviderTimerHooks.h"
        "${BIB_EMBEDDER_DIR}/BibEngineProviderLifecycleHooks.h"
        "${BIB_EMBEDDER_DIR}/BibFoundationServiceBridge.cpp"
        "${BIB_EMBEDDER_DIR}/BibFoundationServiceBridge.h"
        "${BIB_EMBEDDER_DIR}/BibFoundationServiceHost.h"
        "${BIB_EMBEDDER_DIR}/BibFoundationServicesBootstrap.h"
        "${BIB_EMBEDDER_DIR}/BibAppResources.cpp"
        "${BIB_EMBEDDER_DIR}/BibAppResources.h"
        "${BIB_EMBEDDER_DIR}/AppResourceQueue.cpp"
        "${BIB_EMBEDDER_DIR}/resource_url.cpp"
        "${_bib_guard_source}"
        "${_bib_adapters_source}"
        "${_bib_binding_source}"
        "${_bib_preflight_source}"
        "${_bib_codec_source}"
    )
    foreach (_bib_input IN LISTS _bib_neutral_sources)
        if (NOT EXISTS "${_bib_input}" OR IS_DIRECTORY "${_bib_input}")
            message(FATAL_ERROR "Missing reviewed neutral provider source: ${_bib_input}; apply the complete source overlay before graph review")
        endif ()
    endforeach ()
    foreach (_bib_header
        "${BIB_ENGINE_PROVIDER_SOURCE_ROOT}/include/foundation/appended/engine_provider.h"
        "${BIB_ENGINE_PROVIDER_SOURCE_ROOT}/third_party/appended-engine/include/EnginePrivate.hpp"
        "${BIB_ENGINE_PROVIDER_SOURCE_ROOT}/third_party/appended-engine/include/LegacyHostAdapters.hpp"
        "${BIB_ENGINE_COPIED_SOURCE_ROOT}/runtime/private/EnginePrivate.hpp"
    )
        if (NOT EXISTS "${_bib_header}" OR IS_DIRECTORY "${_bib_header}")
            message(FATAL_ERROR "Missing reviewed canonical provider input: ${_bib_header}")
        endif ()
    endforeach ()

    # WebKitFS.cmake defines WTF_DIR for this exact source tree. Fail closed
    # rather than guess another checkout or link the unpatched timer substrate.
    # Overlay packaging verifies the full source identity; this exact definition
    # marker only checks that the required one-TU private hook was applied.
    if (NOT WTF_DIR OR NOT IS_ABSOLUTE "${WTF_DIR}")
        message(FATAL_ERROR "The neutral provider requires WebKit's explicit absolute WTF_DIR for its reviewed private timer hook")
    endif ()
    set(_bib_timer_source "${WTF_DIR}/wtf/generic/RunLoopGeneric.cpp")
    if (NOT EXISTS "${_bib_timer_source}" OR IS_DIRECTORY "${_bib_timer_source}")
        message(FATAL_ERROR "Missing actual WTF timer source: ${_bib_timer_source}")
    endif ()
    file(READ "${_bib_timer_source}" _bib_timer_source_bytes)
    string(FIND "${_bib_timer_source_bytes}" "extern \"C\" int bib_engine_provider_set_timer_scheduler_v1(" _bib_timer_hook_offset)
    if (_bib_timer_hook_offset EQUAL -1)
        message(FATAL_ERROR "Apply the reviewed private RunLoopGeneric.cpp timer overlay before enabling the neutral provider; unpatched engine inputs are incompatible")
    endif ()
    unset(_bib_timer_source_bytes)
    set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS "${_bib_timer_source}")

    add_executable(BibEmbedder ${_bib_neutral_sources})
    set_target_properties(BibEmbedder PROPERTIES OUTPUT_NAME foundation-retained-engine SUFFIX ".mjs")
    target_include_directories(BibEmbedder PRIVATE
        "${BIB_ENGINE_COPIED_GENERATED_DIR}"
        "${BIB_ENGINE_COPIED_SOURCE_ROOT}/runtime"
        "${BIB_ENGINE_COPIED_SOURCE_ROOT}/portable"
        "${BIB_ENGINE_COPIED_SOURCE_ROOT}/runtime/private"
        "${BIB_ENGINE_PROVIDER_SOURCE_ROOT}/include"
        "${BIB_ENGINE_PROVIDER_SOURCE_ROOT}/gui/shared"
        "${BIB_ENGINE_PROVIDER_SOURCE_ROOT}/third_party/appended-engine/include"
        "${BIB_ENGINE_PROVIDER_BINDING_ROOT}"
        "${BIB_ENGINE_PROVIDER_BINDING_ROOT}/binding"
        "${BIB_ENGINE_PROVIDER_BINDING_ROOT}/codec"
        "${BIB_ENGINE_PROVIDER_BINDING_ROOT}/resources"
        "${BIB_ENGINE_PROVIDER_BINDING_ROOT}/lifecycle"
        "${BIB_ENGINE_PROVIDER_BINDING_ROOT}/runtime"
        "${BIB_EMBEDDER_DIR}"
        ${WebCore_INCLUDE_DIRECTORIES}
        ${WebCore_PRIVATE_INCLUDE_DIRECTORIES}
    )
    target_include_directories(BibEmbedder SYSTEM PRIVATE ${WebCore_SYSTEM_INCLUDE_DIRECTORIES})
    target_link_libraries(BibEmbedder PRIVATE WebCore Skia::Skia)

    # The production main is a separate no-main CPU implementation; the binding
    # uses its typed runtime functions. Keep all switches source-specific: no
    # WebCore/JSC target or global compile definitions are added here.
    set_property(SOURCE
        "${BIB_EMBEDDER_DIR}/main.cpp"
        "${_bib_binding_source}"
        "${BIB_EMBEDDER_DIR}/BibAppResources.cpp"
        "${BIB_ENGINE_COPIED_SOURCE_ROOT}/runtime/BibEngineWasmShim.cpp"
        APPEND PROPERTY COMPILE_DEFINITIONS BIB_ENGINE_PROVIDER_NEUTRAL=1)
    set_property(SOURCE
        "${BIB_EMBEDDER_DIR}/main.cpp"
        "${BIB_EMBEDDER_DIR}/BibFoundationServiceBridge.cpp"
        "${BIB_EMBEDDER_DIR}/BibAppResources.cpp"
        "${_bib_binding_source}"
        APPEND PROPERTY COMPILE_DEFINITIONS BIB_FOUNDATION_SERVICES=1)
    set_property(SOURCE
        "${BIB_EMBEDDER_DIR}/main.cpp"
        "${BIB_EMBEDDER_DIR}/EmbedderStrategies.cpp"
        "${BIB_EMBEDDER_DIR}/BibAppResourceProfile.cpp"
        "${BIB_EMBEDDER_DIR}/BibAppResources.cpp"
        "${_bib_binding_source}"
        APPEND PROPERTY COMPILE_DEFINITIONS BIB_APP_RESOURCES=1)
    # Only pure guard/host/codec helpers and the released resource adapter need
    # EH. Existing main, service bridge and engine objects retain their flags.
    set_property(SOURCE
        ${_bib_copied_sources}
        "${_bib_guard_source}"
        "${_bib_adapters_source}"
        "${_bib_binding_source}"
        "${_bib_preflight_source}"
        "${_bib_codec_source}"
        "${BIB_EMBEDDER_DIR}/BibAppResources.cpp"
        "${BIB_EMBEDDER_DIR}/AppResourceQueue.cpp"
        "${BIB_EMBEDDER_DIR}/resource_url.cpp"
        APPEND PROPERTY COMPILE_OPTIONS -fexceptions)

    # Proposed source-only link mode, not a parsed/linked factory claim. There
    # is no supplier engine-pre.js, diagnostic auto-main, owner archive,
    # CandidateComposition/demo service or GPU-spike target in this branch.
    # The copied transport is engine-generic: no application owner archive,
    # payload-specific link, supplier pre-JS or permissive extra exports.
    target_link_options(BibEmbedder PRIVATE
        -fexceptions
        "SHELL:--no-entry"
        "SHELL:-sINVOKE_RUN=0"
        "SHELL:-sMODULARIZE=1"
        "SHELL:-sEXPORT_ES6=1"
        "SHELL:-sEXPORT_NAME=createFoundationRetainedEngine"
        "SHELL:-sENVIRONMENT=worker"
        "SHELL:-sWASM_ASYNC_COMPILATION=1"
        "SHELL:-sCROSS_ORIGIN_STORAGE=0"
        "SHELL:-sEXPORTED_FUNCTIONS=_bib_engine_get_provider_v1,_bib_engine_wasm_bridge_v1,_bib_engine_wasm_dispatch_v1,_malloc,_free"
        "SHELL:-sEXPORTED_RUNTIME_METHODS=HEAPU8"
        "SHELL:-sINCOMING_MODULE_JS_API=wasmBinary,noInitialRun,print,printErr,locateFile"
        "SHELL:--pre-js ${_bib_copied_pre}"
        "SHELL:--js-library ${_bib_copied_library}"
        "SHELL:-sSTACK_SIZE=8MB"
        "SHELL:-sINITIAL_MEMORY=256MB"
        "SHELL:-sALLOW_MEMORY_GROWTH=1"
        "SHELL:-sMAXIMUM_MEMORY=4GB"
        "SHELL:-sEXIT_RUNTIME=0"
        "SHELL:-Wl,--error-limit=0"
        "SHELL:--profiling-funcs"
    )
    # JS/custom import/generated metadata are real dependencies. The generator
    # is an explicit separate provenance step; this CMake overlay never mutates
    # source recipes, downloads inputs, or invents a build identity.
    set_property(TARGET BibEmbedder APPEND PROPERTY LINK_DEPENDS
        "${_bib_copied_pre}" "${_bib_copied_library}" "${_bib_copied_metadata}" "${_bib_copied_provider_build}")
    # Retain the COMPLETE reviewed engine data closure; these are not app payloads.
    if (NOT IS_ABSOLUTE "${JSC_EMBED_ICU_DATA_FILE}" OR NOT EXISTS "${JSC_EMBED_ICU_DATA_FILE}" OR IS_DIRECTORY "${JSC_EMBED_ICU_DATA_FILE}")
        message(FATAL_ERROR "Copied engine requires the exact retained ICU data file")
    endif ()
    foreach (_bib_data_dir BIB_FONTCONFIG_ETC_DIR BIB_FONTS_DIR)
        if (NOT IS_ABSOLUTE "${${_bib_data_dir}}" OR NOT IS_DIRECTORY "${${_bib_data_dir}}")
            message(FATAL_ERROR "Copied engine requires complete retained ${_bib_data_dir}; no system/network fallback")
        endif ()
    endforeach ()
    file(GLOB_RECURSE _bib_fontconfig_files CONFIGURE_DEPENDS LIST_DIRECTORIES false "${BIB_FONTCONFIG_ETC_DIR}/*")
    file(GLOB_RECURSE _bib_font_files CONFIGURE_DEPENDS LIST_DIRECTORIES false "${BIB_FONTS_DIR}/*")
    if (NOT _bib_fontconfig_files OR NOT _bib_font_files)
        message(FATAL_ERROR "Copied embedded font/config closure is empty")
    endif ()
    set_property(TARGET BibEmbedder APPEND PROPERTY LINK_DEPENDS "${JSC_EMBED_ICU_DATA_FILE}" ${_bib_fontconfig_files} ${_bib_font_files})
    if (JSC_EMBED_ICU_DATA_FILE)
        target_link_options(BibEmbedder PRIVATE
            "SHELL:--embed-file ${JSC_EMBED_ICU_DATA_FILE}@${JSC_EMBED_ICU_DATA_FILE}")
    endif ()
    if (BIB_FONTCONFIG_ETC_DIR)
        target_link_options(BibEmbedder PRIVATE
            "SHELL:--embed-file ${BIB_FONTCONFIG_ETC_DIR}@/etc/fonts")
    endif ()
    if (BIB_FONTS_DIR)
        target_link_options(BibEmbedder PRIVATE
            "SHELL:--embed-file ${BIB_FONTS_DIR}@/usr/share/fonts")
    endif ()
else ()
add_executable(BibEmbedder
    ${BIB_EMBEDDER_DIR}/BibAppResourceProfile.cpp
    ${BIB_EMBEDDER_DIR}/BibIDBServer.cpp
    ${BIB_EMBEDDER_DIR}/BibMediaPlayer.cpp
    ${BIB_EMBEDDER_DIR}/EmbedderStrategies.cpp
    ${BIB_EMBEDDER_DIR}/main.cpp
)
set_target_properties(BibEmbedder PROPERTIES OUTPUT_NAME embedder)

# Private source candidate; never changes the ordinary prototype by default.
option(BIB_FOUNDATION_SERVICES "Enable private unqualified in-JSC service overlay" OFF)
if (BIB_FOUNDATION_SERVICES)
    set(BIB_FOUNDATION_SERVICES_HOST_ARCHIVE "" CACHE FILEPATH "Explicit target/CRT-qualified C++20 host owner archive, including WebServices/Registry/value ABI")
    set(BIB_FOUNDATION_SERVICES_HOST_ARCHIVE_SHA256 "" CACHE STRING "Exact SHA256 of that separately prepared host archive")
    if (NOT IS_ABSOLUTE "${BIB_FOUNDATION_SERVICES_HOST_ARCHIVE}" OR NOT EXISTS "${BIB_FOUNDATION_SERVICES_HOST_ARCHIVE}")
        message(FATAL_ERROR "Provide a separately prepared BIB_FOUNDATION_SERVICES_HOST_ARCHIVE; no dependency/kernel/owner build fallback exists")
    endif ()
    file(SHA256 "${BIB_FOUNDATION_SERVICES_HOST_ARCHIVE}" _bib_service_host_sha256)
    if (NOT BIB_FOUNDATION_SERVICES_HOST_ARCHIVE_SHA256 STREQUAL _bib_service_host_sha256)
        message(FATAL_ERROR "BIB_FOUNDATION_SERVICES_HOST_ARCHIVE_SHA256 does not match the selected owner archive")
    endif ()
    # Link checked private bytes, not a mutable original path after configure.
    # This is an ordinary local copy of an already selected archive, never a
    # producer/dependency/kernel build. The build tree has one output owner.
    set(_bib_service_host_copy_dir "${CMAKE_CURRENT_BINARY_DIR}/private-foundation-service-host/${_bib_service_host_sha256}")
    set(_bib_service_host_copy "${_bib_service_host_copy_dir}/host${CMAKE_STATIC_LIBRARY_SUFFIX}")
    file(MAKE_DIRECTORY "${_bib_service_host_copy_dir}")
    configure_file("${BIB_FOUNDATION_SERVICES_HOST_ARCHIVE}" "${_bib_service_host_copy}" COPYONLY)
    file(SHA256 "${_bib_service_host_copy}" _bib_service_host_copy_sha256)
    if (NOT _bib_service_host_copy_sha256 STREQUAL _bib_service_host_sha256)
        message(FATAL_ERROR "Selected owner archive changed while copying private link input")
    endif ()
    set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS "${BIB_FOUNDATION_SERVICES_HOST_ARCHIVE}")
    if (NOT EXISTS "${BIB_EMBEDDER_DIR}/BibFoundationServicesBootstrap.h")
        message(FATAL_ERROR "Generate and review the pinned service bootstrap before enabling the private overlay")
    endif ()
    target_sources(BibEmbedder PRIVATE
        ${BIB_EMBEDDER_DIR}/BibFoundationServiceBridge.cpp
        ${BIB_EMBEDDER_DIR}/BibFoundationServiceBridge.h
        ${BIB_EMBEDDER_DIR}/BibFoundationServiceHost.h
        ${BIB_EMBEDDER_DIR}/BibFoundationServicesBootstrap.h
    )
    # Only these two translation units consume this switch; do not invalidate
    # existing WebCore/JSC or unrelated embedder objects through global flags.
    set_property(SOURCE
        "${BIB_EMBEDDER_DIR}/main.cpp"
        "${BIB_EMBEDDER_DIR}/BibFoundationServiceBridge.cpp"
        APPEND PROPERTY COMPILE_DEFINITIONS BIB_FOUNDATION_SERVICES=1)
    target_link_libraries(BibEmbedder PRIVATE "${_bib_service_host_copy}")
    # The independently built host catches exceptions before the C boundary.
    # Engine objects remain no-exception; the final Wasm link must retain the
    # matching host exception runtime. Archive provenance/toolchain/CRT still
    # require separate inspection: this content hash cannot establish them.
    if (EMSCRIPTEN)
        target_link_options(BibEmbedder PRIVATE -fexceptions)
    endif ()
endif ()

# Source-only combined app-URL/resource lifecycle candidate. OFF preserves the
# ordinary prototype through the always-linked profile shim's inline stubs.
# Only the five edited WebCore cpp files need their existing owning objects;
# no target-wide flags or generated-unified-source properties are changed.
option(BIB_APP_RESOURCES "Enable private combined offline application bootstrap" OFF)
if (BIB_APP_RESOURCES)
    if (NOT BIB_FOUNDATION_SERVICES)
        message(FATAL_ERROR "Combined app bootstrap requires the selected private service owner; no fallback binding exists")
    endif ()
    target_sources(BibEmbedder PRIVATE
        ${BIB_EMBEDDER_DIR}/BibAppResources.cpp
        ${BIB_EMBEDDER_DIR}/AppResourceQueue.cpp
        ${BIB_EMBEDDER_DIR}/resource_url.cpp
    )
    set_property(SOURCE
        "${BIB_EMBEDDER_DIR}/main.cpp"
        "${BIB_EMBEDDER_DIR}/EmbedderStrategies.cpp"
        "${BIB_EMBEDDER_DIR}/BibAppResourceProfile.cpp"
        "${BIB_EMBEDDER_DIR}/BibAppResources.cpp"
        APPEND PROPERTY COMPILE_DEFINITIONS BIB_APP_RESOURCES=1)
    set_property(SOURCE "${BIB_EMBEDDER_DIR}/BibAppResources.cpp"
        APPEND PROPERTY COMPILE_DEFINITIONS BIB_FOUNDATION_SERVICES=1)
    set_source_files_properties(
        ${BIB_EMBEDDER_DIR}/BibAppResources.cpp
        ${BIB_EMBEDDER_DIR}/AppResourceQueue.cpp
        ${BIB_EMBEDDER_DIR}/resource_url.cpp
        PROPERTIES COMPILE_OPTIONS "-fexceptions")
endif ()

target_include_directories(BibEmbedder PRIVATE
    ${WebCore_INCLUDE_DIRECTORIES}
    ${WebCore_PRIVATE_INCLUDE_DIRECTORIES}
)
target_include_directories(BibEmbedder SYSTEM PRIVATE
    ${WebCore_SYSTEM_INCLUDE_DIRECTORIES}
)

# WebCore is static: its PRIVATE link deps (JSC/WTF/PAL/curl tier/ICU) reach
# the final link as $<LINK_ONLY:> interface entries. Skia is linked directly
# for its INTERFACE include dirs (<skia/...> resolves via symlinked headers).
target_link_libraries(BibEmbedder PRIVATE WebCore Skia::Skia)

# Same engine-sized stack/heap as the Phase 1 jsc shell
# (Source/JavaScriptCore/shell/CMakeLists.txt).
#
# W-B1: the engine runs on a dedicated pthread (-sPROXY_TO_PTHREAD moves
# main() off the browser main thread). The whole tree compiles -pthread
# (CMAKE_C/CXX_FLAGS at configure; sysroot deps were always -pthread).
# W-B0 spike (2497a89) proved: SOCKFS sockets proxy to MAIN scope (wisp
# dispatcher unchanged), 4GB growable shared memory instantiates, abort
# stacks stay symbolized. POOL_SIZE=4: 1 taken by proxied main + headroom
# for W-C real workers / future curl threads.
# BIB_PTHREAD=OFF (tools/build-webcore.sh knob): single-threaded engine for
# no-SAB deployments. The TREE's compile flags must match (the script keeps
# them in sync — a -pthread-compiled tree links fine either way, but a
# plain tree cannot link -sPROXY_TO_PTHREAD). The embedder C++ is dual-mode:
# entries run direct when the caller IS the engine thread, and
# engine-pre.js's worker hooks self-disable outside workers (browser.html
# keeps page-side pump fallbacks).
option(BIB_PTHREAD "Run the engine on a dedicated pthread (needs COOP/COEP + SharedArrayBuffer)" ON)
if (BIB_PTHREAD)
    target_link_options(BibEmbedder PRIVATE
        "SHELL:-pthread"
        "SHELL:-sPROXY_TO_PTHREAD"
        "SHELL:-sPTHREAD_POOL_SIZE=4"
        # W-B2: the engine pthread drives the page canvas through an
        # OffscreenCanvas transferred at proxied-main spawn. The transfer
        # list is RUNTIME-decided (GPU mode only) via __wrap_pthread_create
        # in main.cpp — deliberately NOT -sOFFSCREENCANVASES_TO_PTHREAD:
        # that list is compile-time-fixed and a missing canvas fails
        # pthread_create outright (node gates have no DOM; raster mode
        # must keep the page's 2d context on the canvas).
        "SHELL:-sOFFSCREENCANVAS_SUPPORT=1"
        # NOTE: -sOFFSCREEN_FRAMEBUFFER=1 was required ONLY by the legacy
        # Approach R readback present — renderViaOffscreenBackBuffer (in
        # PlatformDisplayEmscripten) needed it to force preserveDrawingBuffer.
        # The zero-copy bitmap present (transferToImageBitmap → page
        # bitmaprenderer) needs the OffscreenCanvas' REAL default framebuffer,
        # which an offscreen backbuffer would hide → blank/stale ImageBitmaps.
        # So it is intentionally NOT set. To debug the old path, re-add it AND
        # compile PlatformDisplayEmscripten with -DBIB_GPU_READBACK_PRESENT.
        # See handoff-2026-06-13-gpu-present-rearchitecture.md.
        "SHELL:-Wl,--wrap=pthread_create"
    )
endif ()

# Stamp the engine-threading mode into a tiny JS the host page (web/browser.html)
# loads BEFORE it picks #screen's canvas context — context type is EXCLUSIVE
# (2d / bitmaprenderer / engine-owned webgl2), and BIB_PTHREAD=ON vs OFF needs
# different ones (gpu-bitmap vs gpu-implicit). Emitted next to embedder.js so the
# dev server's /engine mount serves it at /engine/bib-build-config.js. Regenerates
# on reconfigure (the script re-syncs BIB_PTHREAD when the env var flips).
file(GENERATE
    OUTPUT "$<TARGET_FILE_DIR:BibEmbedder>/bib-build-config.js"
    CONTENT "// Generated by embedder.cmake — do not edit. Stamps the build's threading mode.\nwindow.BIB_PTHREAD_BUILD = $<IF:$<BOOL:${BIB_PTHREAD}>,true,false>;\n")

target_link_options(BibEmbedder PRIVATE
    # Worker-scope Module hooks (pump, wasm2js, injection text): the engine
    # pthread's EM_ASM blocks read the WORKER's Module, which inherits
    # nothing from the page (W-B0). NOTE: cmake does not track pre-js edits —
    # touch main.cpp to force a relink after changing it.
    "SHELL:--pre-js ${BIB_EMBEDDER_DIR}/../../web/engine-pre.js"
    "SHELL:-sSTACK_SIZE=8MB"
    "SHELL:-sINITIAL_MEMORY=256MB"
    "SHELL:-sALLOW_MEMORY_GROWTH=1"
    "SHELL:-sMAXIMUM_MEMORY=4GB"
    # W-B1: EXIT_RUNTIME=0 — under PROXY_TO_PTHREAD a keepalive underflow
    # on the proxied-main pthread with EXIT_RUNTIME=1 tears down the WHOLE
    # runtime mid-session (observed: page Module gutted, exports vanish).
    # The interactive engine must be un-teardownable; gate/node mode calls
    # exit() explicitly in main() so Module.onExit still fires there.
    "SHELL:-sEXIT_RUNTIME=0"
    # FS: the node runner (tools/run-embedder.cjs) reads /out.ppm out of
    # MEMFS in Module.onExit, and both hosts pre-create fontconfig's cache
    # dir in preRun. HEAPU8: the browser host page (web/browser.html) wraps
    # bib_render()'s pixel pointer in a Uint8ClampedArray for putImageData.
    # ccall: browser.html marshals bib_key()'s string args. stringToUTF8/
    # lengthBytesUTF8: main.cpp reads Module.bibHTML inside EM_ASM — export
    # forces them into the runtime so the EM_ASM block can call them.
    # ENV: lets the host page set engine env vars in preRun (e.g.
    # DEBUG_CURL=1 turns on libcurl verbose tracing -> printErr).
    # UTF8ToString: the persistence push (bibMaybePersist) reads the JSON
    # blob out of the shared heap on the MAIN thread inside an EM_ASM block.
    "SHELL:-sEXPORTED_RUNTIME_METHODS=FS,HEAPU8,ccall,stringToUTF8,lengthBytesUTF8,UTF8ToString,ENV"
    # Surface the COMPLETE undefined-symbol list per link attempt instead of
    # wasm-ld's default 20-error cutoff — each stub iteration costs minutes.
    "SHELL:-Wl,--error-limit=0"
    # Keep the wasm name section: abort/crash stacks in the browser show
    # real function names instead of wasm-function[N]. Costs binary size
    # only (no codegen change) — load-bearing for site-abort diagnosis.
    "SHELL:--profiling-funcs"
    # Skia GPU (decision-005 G2): Ganesh drives a WebGL2 context created at
    # boot when Module.bibGPU is set. FULL_ES3 ships the JS shadow-buffer
    # emulation of glMapBufferRange & co — the SK_ASSUME_GL_ES=1 archive's
    # GLES3 interface validation requires them (G1 finding 3). Inert in
    # node/gate mode: nothing creates a context there.
    "SHELL:-sMAX_WEBGL_VERSION=2"
    "SHELL:-sFULL_ES3=1"
)

# ICU data archive at the same absolute path ICU compiled in as its default
# data dir (jsc-shell trick — works in node and browser with no env setup).
if (JSC_EMBED_ICU_DATA_FILE)
    target_link_options(BibEmbedder PRIVATE
        "SHELL:--embed-file ${JSC_EMBED_ICU_DATA_FILE}@${JSC_EMBED_ICU_DATA_FILE}")
endif ()

# Fonts are load-bearing: fontconfig config tree at /etc/fonts (compiled-in
# --sysconfdir) and at least one real TTF at /usr/share/fonts (compiled-in
# --with-default-fonts). Without both, text paints nothing.
if (BIB_FONTCONFIG_ETC_DIR)
    target_link_options(BibEmbedder PRIVATE
        "SHELL:--embed-file ${BIB_FONTCONFIG_ETC_DIR}@/etc/fonts")
endif ()
if (BIB_FONTS_DIR)
    target_link_options(BibEmbedder PRIVATE
        "SHELL:--embed-file ${BIB_FONTS_DIR}@/usr/share/fonts")
endif ()

# CA bundle for in-engine TLS verification (Phase 4) — the path is
# compiled into CurlSSLHandleEmscripten.cpp.
if (BIB_CA_BUNDLE)
    target_link_options(BibEmbedder PRIVATE
        "SHELL:--embed-file ${BIB_CA_BUNDLE}@/etc/ssl/cacert.pem")
endif ()

# G1 GPU context spike (decision-005): standalone Skia-over-WebGL2 proof,
# linked against the same libSkia.a the engine uses. EXCLUDE_FROM_ALL —
# built only on demand via `ninja BibGpuSpike`. SK_GL/SK_GANESH are PRIVATE
# defines on the Skia target, so a TU using the Ganesh public headers must
# set them itself (the PUBLIC ABI defines — SK_TRIVIAL_ABI, SK_R32_SHIFT,
# SK_ASSUME_GL_ES — propagate through Skia::Skia).
add_executable(BibGpuSpike EXCLUDE_FROM_ALL
    ${BIB_EMBEDDER_DIR}/../spike/gpu-spike.cpp
)
set_target_properties(BibGpuSpike PROPERTIES OUTPUT_NAME gpu-spike)
target_compile_definitions(BibGpuSpike PRIVATE SK_GL SK_GANESH)
target_link_libraries(BibGpuSpike PRIVATE Skia::Skia)
target_link_options(BibGpuSpike PRIVATE
    "SHELL:-sMAX_WEBGL_VERSION=2"
    # The SK_ASSUME_GL_ES=1 archive validates the GLES3 interface strictly:
    # glMapBufferRange/glUnmapBuffer/glFlushMappedBufferRange must resolve.
    # Emscripten only ships those (JS shadow-buffer emulation) with FULL_ES3.
    "SHELL:-sFULL_ES3=1"
    "SHELL:-sINITIAL_MEMORY=64MB"
    "SHELL:-sALLOW_MEMORY_GROWTH=1"
    "SHELL:--profiling-funcs"
)

endif () # BIB_ENGINE_PROVIDER_NEUTRAL
