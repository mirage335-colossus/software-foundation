/*
 * Portable application-local text/HTML clipboard for the selected rich engine.
 * Shared browser/Wasm and native source successor. No OS clipboard or Host call.
 * Existing WebCore headers, class layout and public ABI remain unchanged.
 */

#include "config.h"
#if !defined(BIB_INTERNAL_RICH_CLIPBOARD) || !BIB_INTERNAL_RICH_CLIPBOARD
#error "This source successor requires the shared internal clipboard selection"
#endif
#include "Pasteboard.h"
#include "BibInternalClipboard.hpp"
#include "Document.h"
#include "PagePasteboardContext.h"
#include <array>
#include <span>
#include <wtf/Function.h>

namespace BIB::Clipboard {
using namespace WebCore;
namespace {
struct BibClipboardState { Store store; ReceiptBook receipts; bool retirement_bound{}; };
BibClipboardState& bibClipboardState() noexcept { static BibClipboardState state; return state; }
OwnerKey bibClipboardOwner(const EngineUI::Identity& id) noexcept { return {id.runtime_generation, id.worker, id.application}; }
void bibClipboardRetire(void* raw) noexcept {
    auto& state = *static_cast<BibClipboardState*>(raw);
    state.receipts.retire(); state.store.retire();
}
bool bibClipboardAccess(const Pasteboard& pasteboard, EngineUI::Snapshot& snapshot) noexcept {
    if (!EngineUI::onOwner() || !EngineUI::borrowCurrent(snapshot) || pasteboard.isStatic()) return false;
    const auto* context = pasteboard.context();
    if (!context || !context->isPagePasteboardContext()) return false;
    const auto pageID = static_cast<const PagePasteboardContext&>(*context).pageID();
    if (!pageID || pageID->toUInt64() != snapshot.page_identifier) return false;
    auto& state = bibClipboardState();
    if (!state.retirement_bound) {
        if (!EngineUI::registerRetirementHook(&state, bibClipboardRetire)) { EngineUI::fault(); return false; }
        state.retirement_bound = true;
    }
    return state.store.bind(bibClipboardOwner(snapshot.owner));
}
Format bibClipboardFormat(const String& type) noexcept {
    std::array<char, 32> ascii{};
    if (type.length() > ascii.size()) return Format::unsupported;
    for (unsigned index = 0; index < type.length(); ++index) {
        const auto unit = type.is8Bit() ? type.span8()[index] : type.span16()[index];
        if (unit > 0x7f) return Format::unsupported;
        ascii[index] = static_cast<char>(unit);
    }
    return formatForMime({ascii.data(), type.length()});
}
TextInput bibClipboardInput(const String& value) noexcept {
    if (value.is8Bit()) return {nullptr, value.span8().data(), value.length()};
    return {value.span16().data(), nullptr, value.length()};
}
String bibClipboardString(const OwnedText& text) {
    if (!text.present()) return {};
    return String { std::span<const char16_t> { text.data(), text.size() } };
}
void bibClipboardFailed(const Pasteboard& pasteboard) noexcept {
    if (EngineUI::onOwner()) bibClipboardState().receipts.fail(&pasteboard);
}
template<class Write> WriteResult bibClipboardWrite(Pasteboard& pasteboard, Write&& write) noexcept {
    EngineUI::Snapshot snapshot;
    if (!bibClipboardAccess(pasteboard, snapshot)) { bibClipboardFailed(pasteboard); return {}; }
    auto& state = bibClipboardState(); const auto owner = bibClipboardOwner(snapshot.owner);
    const auto reservation = state.receipts.reserveWrite(&pasteboard, owner);
    if (reservation.status != Status::ok) return {reservation.status, 0};
    const auto result = write(state.store, owner);
    state.receipts.complete(reservation.token, result); return result;
}
bool bibClipboardRead(const Pasteboard& pasteboard, Record& record) noexcept {
    EngineUI::Snapshot snapshot;
    return bibClipboardAccess(pasteboard, snapshot)
        && bibClipboardState().store.snapshot(bibClipboardOwner(snapshot.owner), record) == Status::ok;
}
Input bibClipboardContent(const String& plain, const String& html) noexcept {
    return {{!plain.isNull(), bibClipboardInput(plain)}, {!html.isNull(), bibClipboardInput(html)}};
}
WriteResult bibClipboardBatch(Pasteboard& pasteboard, const PasteboardCustomData& data, bool includeCustom) noexcept {
    String plain, html; bool unsupported = false;
    const WTF::Function<void(const String&, const String&)> collect = [&](const String& type, const String& value) {
        switch (bibClipboardFormat(type)) {
        case Format::plain: plain = value; break;
        case Format::html: html = value; break;
        case Format::unsupported: unsupported = true; break;
        }
    };
    data.forEachPlatformString(collect);
    if (includeCustom) data.forEachCustomString(collect);
    // Unknown-only nonempty data cannot masquerade as an accepted clear.
    if (plain.isNull() && html.isNull() && (unsupported || data.hasData())) {
        bibClipboardFailed(pasteboard); return {Status::unsupported, 0};
    }
    return bibClipboardWrite(pasteboard, [&](Store& store, OwnerKey owner) noexcept {
        return store.replace(owner, bibClipboardContent(plain, html));
    });
}
}
bool isInternal(const Pasteboard& pasteboard) noexcept { return !pasteboard.isStatic(); }
BatchResult commitPublicData(Pasteboard& pasteboard, const PasteboardCustomData& data, bool includeCustom) noexcept {
    if (!isInternal(pasteboard)) return BatchResult::not_internal;
    return bibClipboardBatch(pasteboard, data, includeCustom).status == Status::ok ? BatchResult::committed : BatchResult::rejected;
}
CutWriteScope::CutWriteScope(const Pasteboard& pasteboard, const Document& document) noexcept
    : pasteboard_(&pasteboard) {
    if (!bibClipboardAccess(pasteboard, snapshot_) || !document.pageID()
        || document.pageID()->toUInt64() != snapshot_.page_identifier) return;
    attempt_.emplace(bibClipboardState().receipts, &pasteboard, bibClipboardOwner(snapshot_.owner));
}
bool CutWriteScope::consume() noexcept {
    if (consumed_) return false;
    consumed_ = true;
    if (!attempt_ || !pasteboard_ || !EngineUI::matches(snapshot_)) return false;
    EngineUI::Snapshot now;
    if (!bibClipboardAccess(*pasteboard_, now)) return false;
    const auto owner = bibClipboardOwner(now.owner);
    const auto* record = bibClipboardState().store.current(owner);
    return record && attempt_->consume(owner, record->revision, EngineUI::matches(snapshot_));
}
} // namespace BIB::Clipboard

namespace WebCore {
std::unique_ptr<Pasteboard> Pasteboard::createForCopyAndPaste(std::unique_ptr<PasteboardContext>&& context) {
    return makeUnique<Pasteboard>(WTF::move(context));
}
Pasteboard::Pasteboard(std::unique_ptr<PasteboardContext>&& context) : m_context(WTF::move(context)) { }
bool Pasteboard::hasData() {
    BIB::Clipboard::Record record; return BIB::Clipboard::bibClipboardRead(*this, record) && record.hasData();
}
Vector<String> Pasteboard::typesSafeForBindings(const String&) {
    BIB::Clipboard::Record record; Vector<String> types;
    if (!BIB::Clipboard::bibClipboardRead(*this, record)) return types;
    if (record.plain.present()) types.append("text/plain"_s);
    if (record.html.present()) types.append("text/html"_s);
    return types;
}
Vector<String> Pasteboard::typesForLegacyUnsafeBindings() {
    auto types = typesSafeForBindings({});
    if (types.contains("text/plain"_s)) types.append("text/plain;charset=utf-8"_s);
    return types;
}
String Pasteboard::readOrigin() { return {}; }
String Pasteboard::readString(const String& type) {
    BIB::Clipboard::Record record;
    if (!BIB::Clipboard::bibClipboardRead(*this, record)) return {};
    switch (BIB::Clipboard::bibClipboardFormat(type)) {
    case BIB::Clipboard::Format::plain: return BIB::Clipboard::bibClipboardString(record.plain);
    case BIB::Clipboard::Format::html: return BIB::Clipboard::bibClipboardString(record.html);
    case BIB::Clipboard::Format::unsupported: return {};
    }
    return {};
}
String Pasteboard::readStringInCustomData(const String&) { return {}; }
void Pasteboard::writeString(const String& type, const String& value) {
    BIB::Clipboard::bibClipboardWrite(*this, [&](auto& store, auto owner) noexcept {
        return store.set(owner, BIB::Clipboard::bibClipboardFormat(type), BIB::Clipboard::bibClipboardInput(value));
    });
}
void Pasteboard::clear() {
    BIB::Clipboard::bibClipboardWrite(*this, [](auto& store, auto owner) noexcept { return store.clear(owner); });
}
void Pasteboard::clear(const String& type) {
    BIB::Clipboard::bibClipboardWrite(*this, [&](auto& store, auto owner) noexcept {
        return store.erase(owner, BIB::Clipboard::bibClipboardFormat(type));
    });
}
void Pasteboard::read(PasteboardPlainText& text, PlainTextURLReadingPolicy, std::optional<size_t> index) {
    text.text = {}; if (index && *index) return; text.text = readString("text/plain"_s);
}
// The selected Foundation reader has no HTML/text virtuals. EditorEmscripten
// uses owned readString; DataTransfer's guarded CPP branch sanitizes HTML.
void Pasteboard::read(PasteboardWebContentReader&, WebContentReadingPolicy, std::optional<size_t>) { }
void Pasteboard::read(PasteboardFileReader&, std::optional<size_t>) { }
void Pasteboard::write(const PasteboardURL&) { BIB::Clipboard::bibClipboardFailed(*this); }
void Pasteboard::writeTrustworthyWebURLsPboardType(const PasteboardURL&) { BIB::Clipboard::bibClipboardFailed(*this); }
void Pasteboard::write(const PasteboardImage&) { BIB::Clipboard::bibClipboardFailed(*this); }
void Pasteboard::write(const PasteboardBuffer&) { BIB::Clipboard::bibClipboardFailed(*this); }
void Pasteboard::write(const PasteboardWebContent& content) {
    BIB::Clipboard::bibClipboardWrite(*this, [&](auto& store, auto owner) noexcept {
        return store.replace(owner, BIB::Clipboard::bibClipboardContent(content.text, content.markup));
    });
}
Pasteboard::FileContentState Pasteboard::fileContentState() { return FileContentState::NoFileOrImageData; }
bool Pasteboard::canSmartReplace() { return false; }
void Pasteboard::writeMarkup(const String& markup) {
    BIB::Clipboard::bibClipboardWrite(*this, [&](auto& store, auto owner) noexcept {
        return store.replace(owner, {{}, {true, BIB::Clipboard::bibClipboardInput(markup)}});
    });
}
void Pasteboard::writePlainText(const String& text, SmartReplaceOption) {
    BIB::Clipboard::bibClipboardWrite(*this, [&](auto& store, auto owner) noexcept {
        return store.replace(owner, {{true, BIB::Clipboard::bibClipboardInput(text)}, {}});
    });
}
void Pasteboard::writeCustomData(const Vector<PasteboardCustomData>& items) {
    if (items.isEmpty()) { clear(); return; }
    if (items.size() != 1) { BIB::Clipboard::bibClipboardFailed(*this); return; }
    BIB::Clipboard::bibClipboardBatch(*this, items[0], false);
}
void Pasteboard::write(const Color&) { BIB::Clipboard::bibClipboardFailed(*this); }
} // namespace WebCore
