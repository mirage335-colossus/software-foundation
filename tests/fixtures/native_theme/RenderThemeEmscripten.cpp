/*
 * PORT=Emscripten RenderTheme, cribbed from
 * rendering/playstation/RenderThemePlayStation — base RenderTheme paints
 * usable generic form controls; nothing to override for first paint.
 */

#include "config.h"
#include "RenderTheme.h"

#include <wtf/NeverDestroyed.h>

namespace WebCore {

class RenderThemeEmscripten final : public RenderTheme {
public:
    bool popsMenuBySpaceOrReturn() const override { return true; }
    friend NeverDestroyed<RenderThemeEmscripten>;
};

RenderTheme& RenderTheme::singleton()
{
    static NeverDestroyed<RenderThemeEmscripten> theme;
    return theme;
}

} // namespace WebCore
