// SPDX-License-Identifier: CC0-1.0
#pragma once
#include "appended_engine_input_codec.hpp"
#include <foundation/appended/engine_provider.h>
#include <cstdint>
#include <string_view>

namespace WebCore { class LocalFrame; struct KeyEventDispatchOutcome; }
namespace foundation::appended::ndv2_physical {
// Non-author, synchronous authority probe. The parent owns the actual focus,
// DocumentV1/context/sequence receipt, Bridge-before-JSLock and direct-owner turn.
using KeyAuthorityCheck = bool (*)(void*, const WebCore::LocalFrame&,
    const BibEngineDocumentV1&, std::uint64_t input_context,
    std::uint64_t request_sequence) noexcept;
// Returns the actual EventHandler handled bit, not a consumption disposition.
// Pre-admit the command before calling. Allocation can throw: the parent must
// retain consumed-unknown evidence rather than replaying the physical request.
bool dispatchKey(WebCore::LocalFrame&, const engine_input::Key&,
    const BibEngineDocumentV1&, std::uint64_t request_sequence,
    KeyAuthorityCheck, void* authority_context);
// Optional actual native outcome; partial/unwound results remain incomplete.
bool dispatchKeyWithOutcome(WebCore::LocalFrame&, const engine_input::Key&,
    const BibEngineDocumentV1&, std::uint64_t request_sequence,
    KeyAuthorityCheck, void* authority_context, WebCore::KeyEventDispatchOutcome&);
// Actual native text data already admitted and bounded by the parent editor
// protocol; not inferred from a raw key or supplied by author DOM callbacks.
struct NativeTextInput {
    std::string_view utf8;
    std::uint64_t input_context{};
    std::uint32_t modifiers{}; // Original native observation group; zero allowed.
};
// One native Char/keypress route, with the real helper's default flags observed.
// No synthetic raw keydown, retained raw event or direct Editor::insertText.
bool dispatchTextWithOutcome(WebCore::LocalFrame&, const NativeTextInput&,
    const BibEngineDocumentV1&, std::uint64_t request_sequence,
    KeyAuthorityCheck, void* authority_context, WebCore::KeyEventDispatchOutcome&);
// Engine-main-thread metadata only; no DOM/Host/getter/cancellation work.
// Parent invokes after trusted focus loss/inactivation and on context/document
// retirement. This clears the complete mapped mask, including AltGraph.
// Trusted native modifier observation on the engine owner only. No event,
// dispatch, focus mutation or inferred CapsLock/NumLock toggle state.
void updateRawKeyModifiers(std::uint32_t bits) noexcept;
void clearRawKeyModifiers() noexcept;
} // namespace foundation::appended::ndv2_physical
