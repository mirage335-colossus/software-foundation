list(APPEND WebCore_PRIVATE_INCLUDE_DIRECTORIES
    "${WEBCORE_DIR}/platform/graphics/harfbuzz"
    "${WEBCORE_DIR}/platform/graphics/filters/skia"
    "${WEBCORE_DIR}/platform/graphics/skia"
)

list(APPEND WebCore_UNIFIED_SOURCE_LIST_FILES
    "platform/SourcesSkia.txt"
)

# These translation units require GL/Ganesh even when WebGL is disabled.
# Keep them out of the CPU graph rather than providing native GL stubs.
if (NOT USE_SKIA_CPU_ONLY)
    list(APPEND WebCore_SOURCES
        platform/graphics/skia/GraphicsContextGLSkia.cpp
        platform/graphics/skia/ImageBufferSkiaAcceleratedBackend.cpp
        platform/graphics/skia/PlatformDisplaySkia.cpp
        platform/graphics/skia/SkiaPaintingEngine.cpp
        platform/graphics/skia/SkiaRecordingResult.cpp
        platform/graphics/skia/SkiaReplayCanvas.cpp
    )
    list(APPEND WebCore_PRIVATE_FRAMEWORK_HEADERS
        platform/graphics/skia/SkiaPaintingEngine.h
        platform/graphics/skia/SkiaRecordingResult.h
        platform/graphics/skia/SkiaReplayCanvas.h
    )
endif ()

list(APPEND WebCore_PRIVATE_FRAMEWORK_HEADERS
    platform/graphics/harfbuzz/HbUniquePtr.h

    platform/graphics/skia/FontCascadeSkiaInlines.h
    platform/graphics/skia/GraphicsContextSkia.h
    platform/graphics/skia/ImageBufferSkiaBackend.h
    platform/graphics/skia/SkiaHarfBuzzFont.h
    platform/graphics/skia/SkiaHarfBuzzFontCache.h
    platform/graphics/skia/SkiaSpanExtras.h
    platform/graphics/skia/SkiaSystemFallbackFontCache.h
)

list(APPEND WebCore_LIBRARIES
    HarfBuzz::HarfBuzz
    HarfBuzz::ICU
    Skia::Skia
)
