// SPDX-License-Identifier: CC0-1.0
// Source-reviewed candidate, not compiled against WebCore yet.
// Include in main.cpp after engine/thread helpers, outside extern "C".
#pragma once
#include "BibPrototypeSemanticScript.h"
#include "CharacterRange.h"
#include "CompositionHighlight.h"
#include <cstring>
#include <span>
#include <wtf/text/StringBuilder.h>

namespace BIB {
inline RefPtr<WebCore::LocalFrame> prototypeCompositionFrame;
inline RefPtr<WebCore::Document> prototypeCompositionDocument;
inline RefPtr<WebCore::Element> prototypeCompositionElement;
inline uint32_t prototypeCompositionRevision { 0 };
inline uint32_t prototypeCompositionSession { 0 };
inline uint32_t prototypeCompositionInvalidation { 0 };
inline RefPtr<WebCore::Document> prototypeSemanticDocument;
inline uint32_t prototypeDocumentEpoch { 0 };
inline String prototypeReply;
inline bool prototypeRequestActive { false };
inline constexpr int prototypeReplyCapacity = 1024 * 1024 + 1;

inline void resetPrototypeComposition()
{
    prototypeCompositionSession = 0;
    prototypeCompositionFrame = nullptr;
    prototypeCompositionDocument = nullptr;
    prototypeCompositionElement = nullptr;
}

inline bool prototypeUTF16Boundary(const String& text, unsigned offset)
{
    return !offset || offset == text.length() || !(text[offset - 1] >= 0xd800 && text[offset - 1] <= 0xdbff
        && text[offset] >= 0xdc00 && text[offset] <= 0xdfff);
}
} // namespace BIB

extern "C" int bib_prototype_editor_flags();
JSC_DEFINE_HOST_FUNCTION(bibPrototypeState, (JSC::JSGlobalObject* globalObject, JSC::CallFrame*))
{
    StringBuilder state;
    state.append("{\"revision\":"_s);
    state.append(String::number(BIB::g_prototypeEditorState.revision));
    state.append(",\"flags\":"_s);
    state.append(String::number(bib_prototype_editor_flags()));
    state.append("}"_s);
    return JSC::JSValue::encode(JSC::jsString(globalObject->vm(), state.toString()));
}

JSC_DEFINE_HOST_FUNCTION(bibPrototypeEmit, (JSC::JSGlobalObject* globalObject, JSC::CallFrame* callFrame))
{
    auto& vm = globalObject->vm();
    auto scope = DECLARE_THROW_SCOPE(vm);
    String reply = callFrame->argument(0).toWTFString(globalObject);
    RETURN_IF_EXCEPTION(scope, { });
    if (BIB::prototypeRequestActive && reply.length() <= 1024 * 1024)
        BIB::prototypeReply = reply;
    return JSC::JSValue::encode(JSC::jsUndefined());
}

extern "C" {
// All prototype exports are synchronous engine-thread operations. They reject
// calls from a pthread host rather than calling a queued request "success".
// -1 = not ready/wrong thread; -2 = invalid input; -3 = not editable;
// -4 = stale composition; -5 = script/result failure; -6 = reentrant request.
EMSCRIPTEN_KEEPALIVE int bib_prototype_editor_flags()
{
    if (!bibOnEngineThread() || !g_engine)
        return -1;
    BIB::FoundationServiceEngineCall foundationServiceTurn;
    if (!foundationServiceTurn)
        return -1;

    RefPtr frame = g_engine->page->focusController().focusedOrMainFrame();
    if (!frame)
        return -1;
    auto& editor = frame->editor();
    return (editor.canEdit() ? 1 : 0) | (editor.hasComposition() ? 2 : 0)
        | (editor.canUndo() ? 4 : 0) | (editor.canRedo() ? 8 : 0)
        | (BIB::g_prototypeEditorState.inputMethodEnabled ? 16 : 0);
}

// Operations 0=begin, 1=update, 2=commit, 3=cancel. A begin session must be
// nonzero; update/commit use the same token. UTF-16 length/ranges are code units.
// Cancel token 0 deliberately cancels any active session (foreground blur).
EMSCRIPTEN_KEEPALIVE int bib_prototype_composition(int operation, uint32_t session,
    const uint16_t* units, int length, int selectionStart, int selectionEnd)
{
    if (!bibOnEngineThread() || !g_engine)
        return -1;
    BIB::FoundationServiceEngineCall foundationServiceTurn;
    if (!foundationServiceTurn)
        return -1;

    if (operation < 0 || operation > 3 || length < 0 || length > 32768 || (length && !units)
        || selectionStart < 0 || selectionEnd < selectionStart || selectionEnd > length)
        return -2;
    if (operation == 3) {
        if (session && session != BIB::prototypeCompositionSession)
            return -4;
        RefPtr frame = BIB::prototypeCompositionFrame;
        bool sameTarget = frame && BIB::prototypeCompositionDocument && frame->document() == BIB::prototypeCompositionDocument
            && frame->document()->focusedElement() == BIB::prototypeCompositionElement;
        BIB::resetPrototypeComposition();
        if (sameTarget && frame->editor().hasComposition())
            frame->editor().setComposition(emptyString(), { }, { }, { }, 0, 0);
        return 0;
    }
    if (!session)
        return -2;
    RefPtr focused = g_engine->page->focusController().focusedOrMainFrame();
    if (!focused || !focused->document() || !focused->document()->focusedElement() || !focused->editor().canEdit())
        return -3;
    String text(std::span<const char16_t>(reinterpret_cast<const char16_t*>(units), static_cast<size_t>(length)));
    if (!BIB::prototypeUTF16Boundary(text, selectionStart) || !BIB::prototypeUTF16Boundary(text, selectionEnd))
        return -2;
    if (operation == 0) {
        if (BIB::prototypeCompositionSession)
            return -4; // Host must cancel the preceding session explicitly.
        BIB::prototypeCompositionFrame = focused;
        BIB::prototypeCompositionDocument = focused->document();
        BIB::prototypeCompositionElement = focused->document()->focusedElement();
        BIB::prototypeCompositionSession = session;
        BIB::prototypeCompositionInvalidation = BIB::g_prototypeEditorState.compositionInvalidation;
    } else if (session != BIB::prototypeCompositionSession || focused != BIB::prototypeCompositionFrame
        || focused->document() != BIB::prototypeCompositionDocument
        || focused->document()->focusedElement() != BIB::prototypeCompositionElement
        || BIB::prototypeCompositionRevision != BIB::g_prototypeEditorState.revision
        || BIB::prototypeCompositionInvalidation != BIB::g_prototypeEditorState.compositionInvalidation) {
        // Keep the saved target for explicit cancellation after stale rejection.
        return -4;
    }
    RefPtr frame = BIB::prototypeCompositionFrame;
    if (operation == 2) {
        BIB::resetPrototypeComposition(); // Clear before script-capable commit.
        frame->editor().confirmComposition(text);
    } else if (length || operation == 1)
        frame->editor().setComposition(text, { }, { }, { }, selectionStart, selectionEnd);
    BIB::g_prototypeEditorState.changed();
    if (BIB::prototypeCompositionSession) {
        BIB::prototypeCompositionRevision = BIB::g_prototypeEditorState.revision;
        BIB::prototypeCompositionInvalidation = BIB::g_prototypeEditorState.compositionInvalidation;
    }
    return 0;
}

EMSCRIPTEN_KEEPALIVE int bib_prototype_blur()
{
    if (!bibOnEngineThread() || !g_engine)
        return -1;
    BIB::FoundationServiceEngineCall foundationServiceTurn;
    if (!foundationServiceTurn)
        return -1;

    bib_prototype_composition(3, 0, nullptr, 0, 0, 0);
    g_engine->page->focusController().setFocused(false);
    return 0;
}

EMSCRIPTEN_KEEPALIVE int bib_prototype_focus()
{
    if (!bibOnEngineThread() || !g_engine)
        return -1;
    BIB::FoundationServiceEngineCall foundationServiceTurn;
    if (!foundationServiceTurn)
        return -1;

    g_engine->page->focusController().setFocused(true);
    return 0;
}

// A fixed maximum output buffer is required BEFORE any semantic action runs.
// Return bytes excluding NUL, or a negative status. No retry can repeat an
// already-applied action merely because its response buffer was undersized.
EMSCRIPTEN_KEEPALIVE int bib_prototype_semantics(const char* requestJSON, char* output, int capacity)
{
    if (!bibOnEngineThread() || !g_engine)
        return -1;
    BIB::FoundationServiceEngineCall foundationServiceTurn;
    if (!foundationServiceTurn)
        return -1;

    if (!requestJSON || !output || capacity != BIB::prototypeReplyCapacity || strnlen(requestJSON, 65537) > 65536)
        return -2;
    if (BIB::prototypeRequestActive)
        return -6;
    auto request = JSON::Value::parseJSON(String::fromUTF8(requestJSON));
    if (!request || !request->asObject())
        return -2;
    RefPtr frame = g_engine->mainFrame;
    RefPtr document = frame->document();
    if (!document)
        return -1;
    if (document != BIB::prototypeSemanticDocument) {
        if (BIB::prototypeDocumentEpoch == 0xffffffff)
            return -5; // Exhaustion requires a fresh engine session.
        BIB::prototypeSemanticDocument = document;
        ++BIB::prototypeDocumentEpoch;
    }
    auto& world = WebCore::mainThreadNormalWorldSingleton();
    auto* globalObject = frame->script().globalObject(world);
    if (!globalObject)
        return -5;
    auto& vm = globalObject->vm();
    JSC::JSLockHolder lock(vm);
    globalObject->putDirect(vm, JSC::Identifier::fromString(vm, "__foundationPrototypeEmit"_s),
        JSC::JSFunction::create(vm, globalObject, 1, "__foundationPrototypeEmit"_s,
            bibPrototypeEmit, JSC::ImplementationVisibility::Public),
        static_cast<unsigned>(JSC::PropertyAttribute::DontEnum));
    globalObject->putDirect(vm, JSC::Identifier::fromString(vm, "__foundationPrototypeState"_s),
        JSC::JSFunction::create(vm, globalObject, 0, "__foundationPrototypeState"_s,
            bibPrototypeState, JSC::ImplementationVisibility::Public),
        static_cast<unsigned>(JSC::PropertyAttribute::DontEnum));
    StringBuilder script;
    script.append("__foundationPrototypeEmit(JSON.stringify(("_s, String::fromUTF8(bibPrototypeSemanticScript), ")("_s);
    script.append(String::number(BIB::prototypeDocumentEpoch));
    script.append(","_s, request->toJSONString(), ",function(){return JSON.parse(__foundationPrototypeState());})))"_s);
    BIB::prototypeReply = String();
    BIB::prototypeRequestActive = true;
    frame->script().executeScriptIgnoringException(script.toString(), JSC::SourceTaintedOrigin::Untainted);
    BIB::prototypeRequestActive = false;
    if (BIB::prototypeReply.isNull())
        return -5;
    auto utf8 = BIB::prototypeReply.utf8();
    if (utf8.length() >= static_cast<size_t>(capacity))
        return -5;
    memcpy(output, utf8.data(), utf8.length());
    output[utf8.length()] = 0;
    return static_cast<int>(utf8.length());
}
} // extern "C"
