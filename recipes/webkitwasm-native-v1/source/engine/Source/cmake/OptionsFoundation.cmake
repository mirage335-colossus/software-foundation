# Private source-only candidate for the pinned direct WebCore embedder.
# This is an engine port, not the Foundation project's ordinary CMake profile.
# Windows remains an explicit follow-up: clang-cl/C++23, native WTF services,
# Generic RunLoop (no hidden message window), DirectWrite and native resources.
if (NOT CMAKE_SYSTEM_NAME STREQUAL "Linux" OR EMSCRIPTEN)
    message(FATAL_ERROR "PORT=Foundation candidate supports only native Linux x86_64/aarch64; Windows clang-cl and browser builds need their own qualified port configuration")
endif ()
if (NOT WTF_CPU_X86_64 AND NOT WTF_CPU_ARM64)
    message(FATAL_ERROR "PORT=Foundation candidate requires native x86_64 or aarch64 target detection")
endif ()

set(FOUNDATION_NATIVE_DEPENDENCY_PREFIX "" CACHE PATH "Verified dependencies for this native engine target; never the supplier Wasm sysroot")
set(FOUNDATION_NATIVE_DEPENDENCY_TARGET "" CACHE STRING "Dependency identity: linux-x86_64 or linux-aarch64")
if (WTF_CPU_ARM64)
    set(_foundation_dependency_target linux-aarch64)
else ()
    set(_foundation_dependency_target linux-x86_64)
endif ()
if (NOT IS_ABSOLUTE "${FOUNDATION_NATIVE_DEPENDENCY_PREFIX}" OR NOT IS_DIRECTORY "${FOUNDATION_NATIVE_DEPENDENCY_PREFIX}")
    message(FATAL_ERROR "Provide an existing absolute FOUNDATION_NATIVE_DEPENDENCY_PREFIX with native target libraries and provenance; no dependency preparation or fallback is performed")
endif ()
if (NOT FOUNDATION_NATIVE_DEPENDENCY_TARGET STREQUAL _foundation_dependency_target)
    message(FATAL_ERROR "FOUNDATION_NATIVE_DEPENDENCY_TARGET must match ${_foundation_dependency_target}; Wasm archives cannot be reused")
endif ()
file(REAL_PATH "${FOUNDATION_NATIVE_DEPENDENCY_PREFIX}" FOUNDATION_NATIVE_DEPENDENCY_PREFIX)
if (FOUNDATION_NATIVE_DEPENDENCY_PREFIX MATCHES "(^|/)(wasm-sysroot|emsdk)(/|$)" OR CMAKE_CXX_COMPILER_TARGET MATCHES "wasm|emscripten")
    message(FATAL_ERROR "A Wasm dependency prefix/toolchain cannot configure this native candidate")
endif ()

# Root dependency lookup in the selected prefix. Build tools still run on the
# host. This does not certify archive architecture/provenance: verify the retained
# prefix before configuring, and inspect the final native link separately.
set(CMAKE_FIND_ROOT_PATH "${FOUNDATION_NATIVE_DEPENDENCY_PREFIX}")
set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)
set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_PACKAGE ONLY)
list(PREPEND CMAKE_PREFIX_PATH "${FOUNDATION_NATIVE_DEPENDENCY_PREFIX}")
set(_foundation_pkgconfig_dirs "${FOUNDATION_NATIVE_DEPENDENCY_PREFIX}/lib/pkgconfig:${FOUNDATION_NATIVE_DEPENDENCY_PREFIX}/share/pkgconfig")
if (CMAKE_LIBRARY_ARCHITECTURE)
    string(PREPEND _foundation_pkgconfig_dirs "${FOUNDATION_NATIVE_DEPENDENCY_PREFIX}/lib/${CMAKE_LIBRARY_ARCHITECTURE}/pkgconfig:")
endif ()
set(ENV{PKG_CONFIG_LIBDIR} "${_foundation_pkgconfig_dirs}")
set(ENV{PKG_CONFIG_PATH} "")
unset(ENV{PKG_CONFIG_SYSROOT_DIR})

find_package(Threads REQUIRED)
set(CMAKE_C_VISIBILITY_PRESET hidden)
set(CMAKE_CXX_VISIBILITY_PRESET hidden)
set(CMAKE_VISIBILITY_INLINES_HIDDEN ON)
add_definitions(-DBUILDING_FOUNDATION_EMBEDDER__)

set(PROJECT_VERSION_MAJOR 1)
set(PROJECT_VERSION_MINOR 0)
set(PROJECT_VERSION_MICRO 0)
set(PROJECT_VERSION 1.0.0)

set(ENABLE_JAVASCRIPTCORE ON)
set(ENABLE_WEBCORE ON)
set(ENABLE_WEBKIT OFF)
set(ENABLE_WEBKIT_LEGACY OFF)
set(ENABLE_WEBINSPECTORUI OFF)
set(ENABLE_TOOLS OFF)

WEBKIT_OPTION_BEGIN()
WEBKIT_OPTION_DEFINE(ENABLE_STATIC_JSC "Build the private engine's JavaScriptCore statically" PUBLIC ON)
WEBKIT_OPTION_DEFINE(USE_SKIA_CPU_ONLY "Exclude Skia/WebCore graphics driver dependencies" PRIVATE ON)
WEBKIT_OPTION_DEFAULT_PORT_VALUE(ENABLE_JIT PRIVATE OFF)
WEBKIT_OPTION_DEFAULT_PORT_VALUE(ENABLE_DFG_JIT PRIVATE OFF)
WEBKIT_OPTION_DEFAULT_PORT_VALUE(ENABLE_FTL_JIT PRIVATE OFF)
WEBKIT_OPTION_DEFAULT_PORT_VALUE(ENABLE_C_LOOP PRIVATE ON)
WEBKIT_OPTION_DEFAULT_PORT_VALUE(ENABLE_SAMPLING_PROFILER PRIVATE OFF)
WEBKIT_OPTION_DEFAULT_PORT_VALUE(ENABLE_WEBASSEMBLY PRIVATE OFF)
WEBKIT_OPTION_DEFAULT_PORT_VALUE(ENABLE_REMOTE_INSPECTOR PRIVATE OFF)
WEBKIT_OPTION_DEFAULT_PORT_VALUE(USE_SYSTEM_MALLOC PRIVATE ON)
WEBKIT_OPTION_DEFAULT_PORT_VALUE(USE_SKIA PRIVATE ON)
WEBKIT_OPTION_DEFAULT_PORT_VALUE(USE_SKIA_ENCODERS PRIVATE OFF)

# Match the browser prototype's bounded HTML surface, retaining actual DOM,
# editing, layout, storage and script execution. Video has no registered native
# media engine; the browser-only media host bridge is not linked here.
WEBKIT_OPTION_DEFAULT_PORT_VALUE(ENABLE_VIDEO PRIVATE ON)
foreach (_feature IN ITEMS ENABLE_FTPDIR ENABLE_WEB_AUDIO ENABLE_WEBGL ENABLE_WEBGPU
    ENABLE_MEDIA_SOURCE ENABLE_MEDIA_STREAM ENABLE_WEB_RTC ENABLE_ENCRYPTED_MEDIA
    ENABLE_GAMEPAD ENABLE_SPEECH_SYNTHESIS ENABLE_NOTIFICATIONS ENABLE_GEOLOCATION
    ENABLE_FULLSCREEN_API ENABLE_WEBXR ENABLE_XSLT ENABLE_MATHML ENABLE_WEBDRIVER
    ENABLE_MINIBROWSER ENABLE_API_TESTS USE_AVIF USE_JPEGXL USE_LCMS USE_WOFF2)
    WEBKIT_OPTION_DEFAULT_PORT_VALUE(${_feature} PRIVATE OFF)
endforeach ()
WEBKIT_OPTION_END()

if (NOT ENABLE_STATIC_JSC OR NOT ENABLE_C_LOOP OR NOT USE_SYSTEM_MALLOC OR NOT USE_SKIA OR NOT USE_SKIA_CPU_ONLY)
    message(FATAL_ERROR "This candidate requires static JSC, CLoop, system malloc and CPU-only Skia")
endif ()
if (ENABLE_JIT OR ENABLE_DFG_JIT OR ENABLE_FTL_JIT OR ENABLE_SAMPLING_PROFILER OR ENABLE_WEBASSEMBLY OR ENABLE_REMOTE_INSPECTOR OR ENABLE_WEBGL OR ENABLE_WEBGPU)
    message(FATAL_ERROR "This candidate excludes JIT, profiler, guest Wasm, inspector and GPU APIs")
endif ()

# Separate shared embedder behavior from actual compiler/OS restrictions. Never
# define __EMSCRIPTEN__ on a native target: native WorkQueues/GC remain native.
SET_AND_EXPOSE_TO_BUILD(USE_FOUNDATION_EMBEDDER ON)
SET_AND_EXPOSE_TO_BUILD(USE_SKIA_CPU_ONLY ON)
SET_AND_EXPOSE_TO_BUILD(USE_GENERIC_EVENT_LOOP ON)
SET_AND_EXPOSE_TO_BUILD(USE_WINDOWS_EVENT_LOOP OFF)
SET_AND_EXPOSE_TO_BUILD(WTF_DEFAULT_EVENT_LOOP OFF)
SET_AND_EXPOSE_TO_BUILD(USE_UNIX_DOMAIN_SOCKETS ON)
SET_AND_EXPOSE_TO_BUILD(USE_INSPECTOR_SOCKET_SERVER OFF)
SET_AND_EXPOSE_TO_BUILD(USE_CURL ON)
SET_AND_EXPOSE_TO_BUILD(USE_OPENSSL ON)
SET_AND_EXPOSE_TO_BUILD(USE_HARFBUZZ ON)
set(LOWERCASE_EVENT_LOOP_TYPE generic)

find_package(ICU 70.1 REQUIRED COMPONENTS data i18n uc)
find_package(HarfBuzz 1.4.2 REQUIRED COMPONENTS ICU)
find_package(Freetype 2.9.0 REQUIRED)
find_package(Fontconfig 2.13.0 REQUIRED)
include(WOFF2Checks)
if (NOT FREETYPE_WOFF2_SUPPORT_IS_AVAILABLE)
    message(FATAL_ERROR "Native FreeType needs Brotli/WOFF2 support in the selected dependency prefix")
endif ()
SET_AND_EXPOSE_TO_BUILD(HAVE_WOFF_SUPPORT ON)
find_package(JPEG REQUIRED)
find_package(LibXml2 2.9.7 REQUIRED)
find_package(PNG REQUIRED)
find_package(SQLite3 REQUIRED)
if (NOT TARGET SQLite3::SQLite3)
    add_library(SQLite3::SQLite3 ALIAS SQLite::SQLite3)
endif ()
find_package(WebP REQUIRED COMPONENTS demux)
find_package(ZLIB REQUIRED)
find_package(CURL 7.85.0 REQUIRED)
find_package(OpenSSL REQUIRED)
find_package(LibPSL 0.20.2 REQUIRED)
target_link_libraries(LibPSL::LibPSL INTERFACE ICU::uc)

if (NOT BIB_NATIVE_EMBEDDER_CMAKE OR NOT IS_ABSOLUTE "${BIB_NATIVE_EMBEDDER_CMAKE}" OR NOT EXISTS "${BIB_NATIVE_EMBEDDER_CMAKE}")
    message(FATAL_ERROR "Provide BIB_NATIVE_EMBEDDER_CMAKE=/absolute/wrapper/src/embedder/native.cmake after composing the native host and CPU source patches")
endif ()
