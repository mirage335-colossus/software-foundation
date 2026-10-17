/*
 * Copyright (C) 2024 Igalia S.L.
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions
 * are met:
 * 1. Redistributions of source code must retain the above copyright
 *    notice, this list of conditions and the following disclaimer.
 * 2. Redistributions in binary form must reproduce the above copyright
 *    notice, this list of conditions and the following disclaimer in the
 *    documentation and/or other materials provided with the distribution.
 *
 * THIS SOFTWARE IS PROVIDED BY APPLE INC. ``AS IS'' AND ANY
 * EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
 * IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
 * PURPOSE ARE DISCLAIMED.  IN NO EVENT SHALL APPLE INC. OR
 * CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
 * EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
 * PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
 * PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY
 * OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
 * (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
 * OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
 */

#include "config.h"
#include "NativeImage.h"

#if USE(SKIA)
#include "Color.h"
#include "DestinationColorSpace.h"
#include "IntSize.h"
#if !USE(SKIA_CPU_ONLY)
#include "GLContext.h"
#include "PlatformDisplay.h"
#endif
WTF_IGNORE_WARNINGS_IN_THIRD_PARTY_CODE_BEGIN // GLib/Win ports
#include <skia/core/SkPixmap.h>
WTF_IGNORE_WARNINGS_IN_THIRD_PARTY_CODE_END

namespace WebCore {

#if USE(SKIA_CPU_ONLY)
RefPtr<NativeImage> NativeImage::create(PlatformImagePtr&& platformImage)
#else
RefPtr<NativeImage> NativeImage::create(PlatformImagePtr&& platformImage, GrDirectContext* grContext)
#endif
{
    if (!platformImage)
        return nullptr;
#if USE(SKIA_CPU_ONLY)
    if (platformImage->isTextureBacked())
        return nullptr;
    return adoptRef(*new NativeImage(WTF::move(platformImage)));
#else
    return adoptRef(*new NativeImage(WTF::move(platformImage), grContext));
#endif
}

#if USE(SKIA_CPU_ONLY)
RefPtr<NativeImage> NativeImage::createTransient(PlatformImagePtr&& image)
{
    return create(WTF::move(image));
}

NativeImage::NativeImage(PlatformImagePtr&& platformImage)
#else
RefPtr<NativeImage> NativeImage::createTransient(PlatformImagePtr&& image, GrDirectContext* grContext)
{
    return create(WTF::move(image), grContext);
}

NativeImage::NativeImage(PlatformImagePtr&& platformImage, GrDirectContext* grContext)
#endif
    : m_platformImage(WTF::move(platformImage))
#if !USE(SKIA_CPU_ONLY)
    , m_grContext(grContext)
#endif
{
#if USE(SKIA_CPU_ONLY)
    RELEASE_ASSERT(!m_platformImage->isTextureBacked());
#else
    ASSERT(!m_platformImage->isTextureBacked() || m_grContext);
#endif
    computeHeadroom();
}

IntSize NativeImage::size() const
{
    return m_platformImage ? IntSize(m_platformImage->width(), m_platformImage->height()) : IntSize();
}

bool NativeImage::hasAlpha() const
{
    switch (m_platformImage->imageInfo().alphaType()) {
    case kUnknown_SkAlphaType:
    case kOpaque_SkAlphaType:
        return false;
    case kPremul_SkAlphaType:
    case kUnpremul_SkAlphaType:
        return true;
    }
    return false;
}

DestinationColorSpace NativeImage::colorSpace() const
{
    if (auto colorSpace = platformImage()->refColorSpace())
        return DestinationColorSpace(colorSpace);
    // No color space means the default - SRGB.
    return DestinationColorSpace::SRGB();
}

Headroom NativeImage::headroom() const
{
    return Headroom::None;
}

std::optional<Color> NativeImage::singlePixelSolidColor() const
{
    if (size() != IntSize(1, 1))
        return std::nullopt;

    auto platformImage = this->platformImage();
#if !USE(SKIA_CPU_ONLY)
    if (platformImage->isTextureBacked()) {
        if (!PlatformDisplay::sharedDisplay().skiaGLContext()->makeContextCurrent())
            return std::nullopt;

        ASSERT(m_grContext);
        const auto& imageInfo = platformImage->imageInfo();
        uint32_t pixel;
        SkPixmap pixmap(imageInfo, &pixel, imageInfo.minRowBytes());
        if (!platformImage->readPixels(m_grContext, pixmap, 0, 0))
            return std::nullopt;

        return pixmap.getColor(0, 0);
    }
#else
    RELEASE_ASSERT(!platformImage->isTextureBacked());
#endif

    SkPixmap pixmap;
    if (!platformImage->peekPixels(&pixmap))
        return std::nullopt;

    return pixmap.getColor(0, 0);
}

void NativeImage::clearSubimages()
{
}

#if USE(COORDINATED_GRAPHICS)
uint64_t NativeImage::uniqueID() const
{
    if (auto& image = platformImage())
        return image->uniqueID();
    return 0;
}
#endif

} // namespace WebCore

#endif // USE(SKIA)
