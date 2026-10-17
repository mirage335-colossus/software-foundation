# Linux direct WebCore candidate. These supplier files have generic C++ bodies;
# their directory name does not mean native code defines __EMSCRIPTEN__.
# Empty host services remain explicit prototype limitations (see candidate.json).
include(platform/Curl.cmake)
include(platform/ImageDecoders.cmake)
include(platform/Skia.cmake)

if (WIN32)
    list(APPEND WebCore_LIBRARIES FoundationNative::nghttp2 Brotli::dec Brotli::common
        dwrite gdi32 user32 usp10 ole32)
    if (USE_WOFF2)
        list(APPEND WebCore_LIBRARIES WOFF2::dec WOFF2::common)
    endif ()
    list(APPEND WebCore_PRIVATE_INCLUDE_DIRECTORIES ${WEBCORE_DIR}/platform/win)
    list(APPEND WebCore_PRIVATE_FRAMEWORK_HEADERS platform/win/COMPtr.h)
    list(APPEND WebCore_SOURCES
        platform/graphics/win/FontCacheSkiaWin.cpp
        platform/win/LoggingWin.cpp platform/win/SharedMemoryWin.cpp
        platform/network/win/CurlSSLHandleWin.cpp)
else ()
find_library(NGHTTP2_LIBRARY nghttp2 REQUIRED)
find_library(BROTLIDEC_LIBRARY brotlidec REQUIRED)
find_library(BROTLICOMMON_LIBRARY brotlicommon REQUIRED)
list(APPEND WebCore_LIBRARIES
    ${NGHTTP2_LIBRARY}
    ${BROTLIDEC_LIBRARY}
    ${BROTLICOMMON_LIBRARY}
    Fontconfig::Fontconfig
)
endif ()

list(APPEND WebCore_PRIVATE_INCLUDE_DIRECTORIES
    ${WEBCORE_DIR}/platform
    ${WEBCORE_DIR}/platform/generic
    ${WEBCORE_DIR}/platform/mediacapabilities
    ${WEBCORE_DIR}/platform/video-codecs
)
list(APPEND WebCore_SOURCES
    accessibility/emscripten/AXObjectCacheEmscripten.cpp
    accessibility/emscripten/AccessibilityObjectEmscripten.cpp
    crypto/emscripten/CryptoStubsEmscripten.cpp
    editing/emscripten/EditorEmscripten.cpp
    platform/emscripten/MIMETypeRegistryEmscripten.cpp
    platform/emscripten/PasteboardEmscripten.cpp
    platform/emscripten/PlatformKeyboardEventEmscripten.cpp
    platform/emscripten/PlatformScreenEmscripten.cpp
    platform/emscripten/ScrollbarThemeEmscripten.cpp
    platform/emscripten/ThemeEmscripten.cpp
    platform/emscripten/UserAgentEmscripten.cpp
    platform/network/emscripten/CurlSSLHandleEmscripten.cpp
    platform/network/emscripten/NetworkStateNotifierEmscripten.cpp
    platform/generic/KeyedDecoderGeneric.cpp
    platform/generic/KeyedEncoderGeneric.cpp
    platform/graphics/emscripten/SystemFontDatabaseEmscripten.cpp
    platform/text/Hyphenation.cpp
    platform/text/LocaleICU.cpp
    platform/unix/LoggingUnix.cpp
    platform/unix/SharedMemoryUnix.cpp
    rendering/emscripten/RenderThemeEmscripten.cpp
)

if (WIN32)
    list(REMOVE_ITEM WebCore_SOURCES platform/unix/LoggingUnix.cpp
        platform/unix/SharedMemoryUnix.cpp platform/network/emscripten/CurlSSLHandleEmscripten.cpp)
endif ()

# The CPU component separately gates SourcesSkia, ImageBuffer and driver links.
# No Emscripten display/GLContext, EGL implementation, WPE or GPU stubs are added.
if (NOT USE_SKIA_CPU_ONLY)
    message(FATAL_ERROR "Apply the matching CPU-only source component first")
endif ()
cmake_language(DEFER CALL include "${BIB_NATIVE_EMBEDDER_CMAKE}")
