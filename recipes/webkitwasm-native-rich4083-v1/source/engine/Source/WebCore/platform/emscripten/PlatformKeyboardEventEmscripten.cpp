/*
 * PORT=Emscripten keyboard platform half.
 * The embedder sends RawKeyDown/Char/KeyUp (never combined KeyDown), so
 * disambiguateKeyDownEvent is only here to satisfy the link and to behave
 * correctly if anything synthesizes a KeyDown; logic cribbed from
 * platform/libwpe/PlatformKeyboardEventLibWPE.cpp.
 */

#include "config.h"
#include "PlatformKeyboardEvent.h"

namespace WebCore {

OptionSet<PlatformEvent::Modifier> PlatformKeyboardEvent::currentStateOfModifierKeys()
{
    // Last actual mapped mask, cleared by trusted focus/context retirement.
    if (s_currentModifiers)
        return *s_currentModifiers;
    return { };
}

void PlatformKeyboardEvent::disambiguateKeyDownEvent(Type type, bool backwardsCompatibility)
{
    ASSERT(m_type == PlatformEvent::Type::KeyDown);
    m_type = type;
    // No m_handledByInputMethod check: that member is guarded to IME-capable
    // ports (GTK/LIBWPE/APPKIT) and this port has no input method.
    if (backwardsCompatibility)
        return;

    if (type == PlatformEvent::Type::RawKeyDown) {
        m_text = String();
        m_unmodifiedText = String();
    } else
        m_keyIdentifier = String();
}

} // namespace WebCore
