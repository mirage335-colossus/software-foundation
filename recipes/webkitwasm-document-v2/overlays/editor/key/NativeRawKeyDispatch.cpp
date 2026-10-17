// SPDX-License-Identifier: CC0-1.0
// SOURCE-ONLY WebCore integration. Not parsed against actual engine headers.
#include "config.h"
#include "NativeRawKeyDispatch.hpp"
#include "BibNativeKeyEventOutcome.hpp"
#include "NativeRawKeyMapping.hpp"
#include "NativeRawKeyScope.hpp"
#include "Document.h"
#include "EventHandler.h"
#include "LocalFrame.h"
#include "LocalFrameInlines.h"
#include "PlatformKeyboardEvent.h"
#include "WindowProxy.h"
#include "WindowsKeyboardCodes.h"
#include <atomic>
#include <span>
#include <wtf/Assertions.h>
#include <wtf/MainThread.h>
#include <wtf/MonotonicTime.h>
#include <wtf/Ref.h>
#include <wtf/text/AtomString.h>
#include <wtf/text/Latin1Character.h>
#include <wtf/text/StringImpl.h>
#include <wtf/text/WTFString.h>

namespace foundation::appended::ndv2_physical {
namespace {
using Modifier = WebCore::PlatformEvent::Modifier;
static_assert(static_cast<unsigned>(Modifier::ShiftKey) == 8
    && static_cast<unsigned>(Modifier::ControlKey) == 2
    && static_cast<unsigned>(Modifier::AltKey) == 1
    && static_cast<unsigned>(Modifier::MetaKey) == 4
    && static_cast<unsigned>(Modifier::AltGraphKey) == 32);
static_assert(VK_BACK == 8 && VK_TAB == 9 && VK_CLEAR == 12 && VK_RETURN == 13
    && VK_SHIFT == 16 && VK_CONTROL == 17 && VK_MENU == 18 && VK_PAUSE == 19 && VK_CAPITAL == 20
    && VK_ESCAPE == 27 && VK_SPACE == 32 && VK_PRIOR == 33 && VK_NEXT == 34
    && VK_END == 35 && VK_HOME == 36 && VK_LEFT == 37 && VK_UP == 38 && VK_RIGHT == 39 && VK_DOWN == 40
    && VK_SNAPSHOT == 44 && VK_INSERT == 45 && VK_DELETE == 46 && VK_HELP == 47
    && VK_LWIN == 0x5b && VK_RWIN == 0x5c && VK_APPS == 0x5d
    && VK_NUMPAD0 == 0x60 && VK_MULTIPLY == 0x6a && VK_ADD == 0x6b
    && VK_SUBTRACT == 0x6d && VK_DECIMAL == 0x6e && VK_DIVIDE == 0x6f
    && VK_F1 == 0x70 && VK_F24 == 0x87 && VK_NUMLOCK == 144 && VK_SCROLL == 145
    && VK_LSHIFT == 0xa0 && VK_RSHIFT == 0xa1 && VK_LCONTROL == 0xa2 && VK_RCONTROL == 0xa3
    && VK_LMENU == 0xa4 && VK_RMENU == 0xa5 && VK_OEM_1 == 0xba && VK_OEM_PLUS == 0xbb
    && VK_OEM_COMMA == 0xbc && VK_OEM_MINUS == 0xbd && VK_OEM_PERIOD == 0xbe
    && VK_OEM_2 == 0xbf && VK_OEM_3 == 0xc0 && VK_OEM_4 == 0xdb && VK_OEM_5 == 0xdc
    && VK_OEM_6 == 0xdd && VK_OEM_7 == 0xde);
WTF::OptionSet<Modifier> mappedModifiers(std::uint32_t bits) {
    WTF::OptionSet<Modifier> result;
    if (bits & 1u) result.add(Modifier::ShiftKey);
    if (bits & 2u) result.add(Modifier::ControlKey);
    if (bits & 4u) result.add(Modifier::AltKey);
    if (bits & 8u) result.add(Modifier::MetaKey);
    if (bits & 16u) result.add(Modifier::AltGraphKey);
    return result;
}
WTF::String utf8(const std::string& value) {
    return WTF::String::fromUTF8(std::span<const char>(value.data(), value.size()));
}
class DispatchScope;
// Process-wide marker holds no object ownership and is never dereferenced.
// It only detects a marked event incorrectly entering on a foreign thread.
// The owners below live synchronously on the direct-owner engine main thread.
std::atomic<const void*> activeMarker{nullptr};
thread_local DispatchScope* localScope = nullptr;

class DispatchScope final {
public:
    DispatchScope(WebCore::LocalFrame& frame, WebCore::Document& document,
        WebCore::WindowProxy& view, const BibEngineDocumentV1& identity,
        std::uint64_t context, std::uint64_t sequence, KeyAuthorityCheck authority,
        void* authority_context, const WTF::AtomString& canonical,
        const WTF::String& marker, const WebCore::PlatformKeyboardEvent& event,
        std::uint32_t location)
        : frame_(frame), document_(document), view_(view), identity_(identity),
          context_(context), sequence_(sequence), authority_(authority), authority_context_(authority_context),
          canonical_(canonical), marker_(marker), expected_(event), gate_(marker.impl(), location) {
        RELEASE_ASSERT(WTF::isMainThread() && !localScope);
        RELEASE_ASSERT(marker_.length() && marker_.impl() && !marker_.impl()->isAtom());
        RELEASE_ASSERT(canonical_.impl() && marker_.impl() != canonical_.impl());
        RELEASE_ASSERT(expected_.keyIdentifier().impl() == marker_.impl());
        localScope = this;
        const void* empty = nullptr;
        RELEASE_ASSERT(activeMarker.compare_exchange_strong(empty, marker_.impl(), std::memory_order_acq_rel));
    }
    ~DispatchScope() {
        RELEASE_ASSERT(localScope == this);
        RELEASE_ASSERT(activeMarker.load(std::memory_order_acquire) == marker_.impl());
        // Disarm before any marker/canonical/frame/document owner is released.
        activeMarker.store(nullptr, std::memory_order_release);
        localScope = nullptr;
    }
    DispatchScope(const DispatchScope&) = delete;
    DispatchScope& operator=(const DispatchScope&) = delete;

    LocationResult consume(const WebCore::PlatformKeyboardEvent& event,
        WebCore::WindowProxy* view, unsigned& location) noexcept {
        const bool record_matches = event.type() == expected_.type()
            && event.timestamp() == expected_.timestamp()
            && event.key() == expected_.key() && event.code() == expected_.code()
            && event.keyIdentifier().impl() == marker_.impl()
            && event.windowsVirtualKeyCode() == expected_.windowsVirtualKeyCode()
            && event.isAutoRepeat() == expected_.isAutoRepeat()
            && event.isKeypad() == expected_.isKeypad()
            && !event.isSystemKey() && !event.isSyntheticEvent()
            && event.text().isNull() && event.unmodifiedText().isNull()
            && event.modifiers() == expected_.modifiers() && !event.authorizationToken();
        const bool valid = record_matches && WTF::isMainThread()
            && view == view_.ptr() && frame_->document() == document_.ptr()
            && &frame_->windowProxy() == view_.ptr() && document_->windowProxy() == view_.ptr()
            && authority_(authority_context_, frame_.get(), identity_, context_, sequence_);
        return gate_.consume(event.keyIdentifier().impl(), record_matches, valid, location);
    }
private:
    WTF::Ref<WebCore::LocalFrame> frame_;
    WTF::Ref<WebCore::Document> document_;
    WTF::Ref<WebCore::WindowProxy> view_;
    BibEngineDocumentV1 identity_;
    std::uint64_t context_, sequence_;
    KeyAuthorityCheck authority_;
    void* authority_context_;
    WTF::AtomString canonical_; // Must be pinned BEFORE fresh marker allocation.
    WTF::String marker_;
    WebCore::PlatformKeyboardEvent expected_;
    MarkerLocationGate gate_;
};
} // namespace

void updateRawKeyModifiers(std::uint32_t bits) noexcept {
    // Trusted owner observation only: no raw dispatch or toggle-key inference.
    RELEASE_ASSERT(WTF::isMainThread() && !(bits & ~31u));
    WebCore::PlatformKeyboardEvent::setCurrentModifierState(mappedModifiers(bits));
}

void clearRawKeyModifiers() noexcept {
    RELEASE_ASSERT(WTF::isMainThread());
    WebCore::PlatformKeyboardEvent::setCurrentModifierState({});
}

static bool dispatchKeyImpl(WebCore::LocalFrame& frame, const engine_input::Key& input,
    const BibEngineDocumentV1& identity, std::uint64_t sequence,
    KeyAuthorityCheck authority, void* authority_context, WebCore::KeyEventDispatchOutcome* outcome) {
    if (outcome)
        *outcome = { };
    RELEASE_ASSERT(WTF::isMainThread() && !localScope && !activeMarker.load(std::memory_order_acquire));
    RELEASE_ASSERT(identity.application_instance && identity.document_sequence && identity.service_generation);
    RELEASE_ASSERT(sequence && authority && engine_input::validate_key(input) == engine_input::Status::ok);
    RELEASE_ASSERT(authority(authority_context, frame, identity, input.input_context, sequence));
    WTF::RefPtr document = frame.document();
    RELEASE_ASSERT(document && document->windowProxy() == &frame.windowProxy());
    auto compatibility = mapCompatibilityKey(input);
    RELEASE_ASSERT(compatibility && !compatibility->identifier.empty());
    // Atomize and pin the visible spelling first. Only then allocate a distinct,
    // positive-length, ordinary StringImpl. DOM atomization must find canonical.
    WTF::AtomString canonical{utf8(compatibility->identifier)};
    std::span<Latin1Character> characters;
    WTF::String marker = WTF::String::createUninitialized(
        static_cast<unsigned>(compatibility->identifier.size()), characters);
    RELEASE_ASSERT(characters.size() == compatibility->identifier.size());
    for (std::size_t i = 0; i < characters.size(); ++i)
        characters[i] = static_cast<Latin1Character>(compatibility->identifier[i]);
    RELEASE_ASSERT(marker.impl() && marker.impl() != canonical.impl() && !marker.impl()->isAtom());
    auto key = utf8(input.key);
    auto code = utf8(input.code);
    RELEASE_ASSERT(!key.isNull() && !code.isNull());
    const auto modifiers = mappedModifiers(input.modifiers);
    const auto type = input.phase == 0 ? WebCore::PlatformEvent::Type::RawKeyDown : WebCore::PlatformEvent::Type::KeyUp;
    WebCore::PlatformKeyboardEvent event(type, WTF::String(), WTF::String(), key, code,
        marker, compatibility->virtual_key, input.repeat != 0, compatibility->keypad,
        false, modifiers, WTF::MonotonicTime::now());
    DispatchScope scope(frame, *document, frame.windowProxy(), identity, input.input_context,
        sequence, authority, authority_context, canonical, marker, event, input.location);
    // Last actual physical mask; trusted parent retirement/focus paths clear it.
    // Never synthesize CapsLock/NumLock or collapse AltGraph into Ctrl+Alt.
    WebCore::PlatformKeyboardEvent::setCurrentModifierState(modifiers);
    return outcome ? WebCore::dispatchKeyEventWithNativeOutcome(frame.eventHandler(), event, *outcome)
        : frame.eventHandler().keyEvent(event);
}

bool dispatchKey(WebCore::LocalFrame& frame, const engine_input::Key& input,
    const BibEngineDocumentV1& identity, std::uint64_t sequence,
    KeyAuthorityCheck authority, void* authority_context) {
    return dispatchKeyImpl(frame, input, identity, sequence, authority, authority_context, nullptr);
}

bool dispatchKeyWithOutcome(WebCore::LocalFrame& frame, const engine_input::Key& input,
    const BibEngineDocumentV1& identity, std::uint64_t sequence,
    KeyAuthorityCheck authority, void* authority_context, WebCore::KeyEventDispatchOutcome& outcome) {
    return dispatchKeyImpl(frame, input, identity, sequence, authority, authority_context, &outcome);
}

bool dispatchTextWithOutcome(WebCore::LocalFrame& frame, const NativeTextInput& input,
    const BibEngineDocumentV1& identity, std::uint64_t sequence,
    KeyAuthorityCheck authority, void* authority_context, WebCore::KeyEventDispatchOutcome& outcome) {
    outcome = { }; // Allocation/unwind before native entry must remain incomplete.
    RELEASE_ASSERT(WTF::isMainThread() && !localScope && !activeMarker.load(std::memory_order_acquire));
    RELEASE_ASSERT(identity.application_instance && identity.document_sequence && identity.service_generation);
    RELEASE_ASSERT(sequence && authority && input.input_context && input.modifiers <= 31 && !input.utf8.empty());
    RELEASE_ASSERT(authority(authority_context, frame, identity, input.input_context, sequence));
    WTF::RefPtr document = frame.document();
    RELEASE_ASSERT(document && document->windowProxy() == &frame.windowProxy());
    // Parent admitted these exact bounded native bytes; fromUTF8 rejects malformed
    // UTF8. Span length is retained (no C-string truncation or normalization).
    auto text = WTF::String::fromUTF8(std::span<const char>(input.utf8.data(), input.utf8.size()));
    RELEASE_ASSERT(!text.isNull() && !text.isEmpty());
    const auto modifiers = mappedModifiers(input.modifiers);
    WebCore::PlatformKeyboardEvent event(WebCore::PlatformEvent::Type::Char,
        text, WTF::String(), WTF::String(), WTF::String(), WTF::String(), 0,
        false, false, false, modifiers, WTF::MonotonicTime::now());
    // No unmodified OS-layout text, logical key/code or VK is inferred.
    // No raw marked event is retained or repurposed as a text event. Char reaches
    // the existing Element keypress/default path exactly once, with actual flags.
    RELEASE_ASSERT(frame.document() == document.get()
        && document->windowProxy() == &frame.windowProxy()
        && authority(authority_context, frame, identity, input.input_context, sequence));
    WebCore::PlatformKeyboardEvent::setCurrentModifierState(modifiers);
    return WebCore::dispatchKeyEventWithNativeOutcome(frame.eventHandler(), event, outcome);
}

int consumeRawKeyLocation(const WebCore::PlatformKeyboardEvent* event,
    WebCore::WindowProxy* view, unsigned* location) noexcept {
    if (!event) return static_cast<int>(LocationResult::invalid);
    const auto* marker = event->keyIdentifier().impl();
    const auto* active = activeMarker.load(std::memory_order_acquire);
    if (!active || marker != active) return static_cast<int>(LocationResult::inactive);
    // A marked foreign-thread call cannot dereference the owning stack scope.
    if (!localScope || !location) return static_cast<int>(LocationResult::invalid);
    return static_cast<int>(localScope->consume(*event, view, *location));
}
} // namespace foundation::appended::ndv2_physical

// Private always-linked hook. It does not throw across the C-linkage boundary.
// -1 is an invariant violation; KeyboardEvent's native constructor release-
// asserts before returning, hence before author dispatch. Distinct ordinary
// markers return 0 and preserve the supplier's normal location inference.
extern "C" int bib_ndv2_physical_key_location_v1(const WebCore::PlatformKeyboardEvent* event,
    WebCore::WindowProxy* view, unsigned* location) noexcept {
    return foundation::appended::ndv2_physical::consumeRawKeyLocation(event, view, location);
}
