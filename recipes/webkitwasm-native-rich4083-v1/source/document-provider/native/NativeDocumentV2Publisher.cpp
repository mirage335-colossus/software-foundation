// Source candidate only. No compiler, link, actual engine or browser proof.
#include "config.h"
#include "NativeDocumentV2Publisher.hpp"
#include "CombinedFormsIdentity.hpp"
#include "SharedNativeControlGuard.hpp"
#include "CommonVM.h"
#include <JavaScriptCore/VM.h>
#include <WebCore/Editor.h>
#include <WebCore/ElementInlines.h>
#include <WebCore/FocusOptions.h>
#include <WebCore/FrameSelection.h>
#include <WebCore/LocalFrameInlines.h>
#include <WebCore/LocalFrameViewLayoutContext.h>
#include <WebCore/LocalFrameView.h>
#include <WebCore/NodeInlines.h>
#include <WebCore/HTMLInputElement.h>
#include <WebCore/HTMLAnchorElement.h>
#include <WebCore/VisibleSelection.h>
#include <WebCore/HTMLBodyElement.h>
#include <WebCore/HTMLButtonElement.h>
#include <WebCore/HTMLLabelElement.h>
#include <WebCore/HTMLNames.h>
#include <WebCore/HTMLTextAreaElement.h>
#include <WebCore/HTMLTextFormControlElement.h>
#include <WebCore/TextControlInnerElements.h>
#include <WebCore/TextControlInnerTextElement.h>
#include <WebCore/NodeTraversal.h>
#include <WebCore/Position.h>
#include <WebCore/RenderStyle.h>
#include <WebCore/Settings.h>
#include <WebCore/TreeScopeInlines.h>
#include <WebCore/Text.h>
#include <WebCore/TextEvent.h>
#include <WebCore/UserGestureIndicator.h>
#include <wtf/text/AtomString.h>
#include <wtf/text/StringBuilder.h>
#include <wtf/text/WTFString.h>
#include <algorithm>
#include <limits>
#include <span>
#include <stdexcept>
#include <type_traits>
#include <utility>

namespace BIB::FormsV2Combined {
using namespace WebCore;
using namespace WTF::StringLiterals;
static void require(bool value, const char* why)
{
    if (!value) throw std::invalid_argument(why);
}
namespace {
constexpr uint32_t authorShadow = 1, frameContent = 2, generatedContent = 4,
    selectionUnavailable = 8, labelUnavailable = 16, unknownStyle = 32, unsupportedWhitespace = 64;
bool exhausted(const N::Counter& counter)
{
    return counter.retired() || counter.highWater() == std::numeric_limits<uint64_t>::max();
}
bool descriptor(const Session::Capture& control)
{
    return control.node && (is<HTMLInputElement>(*control.node) || is<HTMLTextAreaElement>(*control.node)
        || is<HTMLSelectElement>(*control.node));
}

// Public projection only. Private attributes/control baselines still use the
// unchanged strict Session::copy path. These helpers never invoke author code.
// BEGIN PURE PUBLIC PROJECTION HELPERS
template<typename CharacterAt>
size_t publicTextPrefixUnits(size_t length, size_t bodyRemaining, CharacterAt at)
{
    auto units = std::min({ length, N::maxFieldUnits, bodyRemaining });
    if (units && units < length) {
        const auto last = at(units - 1);
        if (last >= 0xd800 && last <= 0xdbff) {
            const auto next = at(units); // At most one bounded boundary unit.
            if (next >= 0xdc00 && next <= 0xdfff) --units;
        }
    }
    return units;
}
template<typename Controls, typename IsDescriptor>
bool publicControlBodyFits(const Controls& controls, size_t remaining, IsDescriptor isDescriptor)
{
    bool fits = true;
    for (const auto& captured : controls) {
        if (!isDescriptor(captured)) continue;
        const auto& control = captured.observed;
        if (control.kind == F::FormKind::secure_readonly || control.omitted) continue;
        auto charge = [&](std::string_view value) {
            const auto units = N::utf16Units(value); // Strict scalar/field validation remains.
            if (units > remaining) { fits = false; remaining = 0; }
            else remaining -= units;
        };
        charge(control.label);
        if (const auto* text = std::get_if<F::FormTextState>(&control.state))
            charge(text->value);
    }
    return fits; // All retained fields validate even after known pool exhaustion.
}
// END PURE PUBLIC PROJECTION HELPERS
bool copyPublicText(const WTF::String& source, std::string& output, N::ReadBudget& budget)
{
    // String::length/operator[] read the existing immutable 8/16-bit storage.
    // Never copy/upconvert the unbounded remainder or call whole-string utf8().
    const auto units = publicTextPrefixUnits(source.length(), budget.remaining(N::TextSection::body),
        [&](size_t index) { return source[static_cast<unsigned>(index)]; });
    budget.chargeBody(units); // Before any bounded allocation/copy.
    std::u16string prefix;
    prefix.reserve(units);
    for (size_t index = 0; index < units; ++index)
        prefix.push_back(source[static_cast<unsigned>(index)]);
    // NUL/unpaired surrogates IN the retained prefix still fail strictly.
    output = N::utf16ToUtf8(prefix);
    return units == source.length();
}

// BEGIN-FORM-FOCUS-SELECTION-HELPER
// BEGIN alone may adopt an actual stable postfocus text selection. This changes
// only its comparison copy; every other public/private field remains exact.
// The caller supplies a second native range sample taken after the full capture.
bool normalizeBeginTextSelection(F::FormControl& comparison, const F::FormControl& captured,
    const std::optional<F::FormControlRange>& verified)
{
    auto* before = std::get_if<F::FormTextState>(&comparison.state);
    const auto* actual = std::get_if<F::FormTextState>(&captured.state);
    if (!before && !actual) return !verified;
    if (!before || !actual || !before->selection || !actual->selection || !verified
        || *actual->selection != *verified) return false;
    (void)F::form_byte_selection(actual->editing_text, *verified);
    before->selection = actual->selection;
    return true;
}
// END-FORM-FOCUS-SELECTION-HELPER

const char* displayName(unsigned raw)
{
    switch (static_cast<DisplayType>(raw)) {
    case DisplayType::None: return "none";
    case DisplayType::Contents: return "contents";
    case DisplayType::Inline: return "inline";
    case DisplayType::InlineBlock: return "inline-block";
    case DisplayType::Block: return "block";
    case DisplayType::ListItem: return "list-item";
    case DisplayType::Table: return "table";
    case DisplayType::InlineTable: return "inline-table";
    case DisplayType::TableRowGroup: return "table-row-group";
    case DisplayType::TableHeaderGroup: return "table-header-group";
    case DisplayType::TableFooterGroup: return "table-footer-group";
    case DisplayType::TableRow: return "table-row";
    case DisplayType::TableColumnGroup: return "table-column-group";
    case DisplayType::TableColumn: return "table-column";
    case DisplayType::TableCell: return "table-cell";
    case DisplayType::TableCaption: return "table-caption";
    case DisplayType::Flex: return "flex";
    case DisplayType::InlineFlex: return "inline-flex";
    case DisplayType::Grid: return "grid";
    case DisplayType::InlineGrid: return "inline-grid";
    case DisplayType::FlowRoot: return "flow-root";
    default: return "unsupported";
    }
}
const char* whitespaceName(const Presentation& value)
{
    auto collapse = static_cast<WhiteSpaceCollapse>(value.collapse);
    auto wrap = static_cast<TextWrapMode>(value.wrap);
    if (collapse == WhiteSpaceCollapse::Collapse) return wrap == TextWrapMode::Wrap ? "normal" : "nowrap";
    if (collapse == WhiteSpaceCollapse::Preserve) return wrap == TextWrapMode::Wrap ? "pre-wrap" : "pre";
    if (collapse == WhiteSpaceCollapse::PreserveBreaks && wrap == TextWrapMode::Wrap) return "pre-line";
    if (collapse == WhiteSpaceCollapse::BreakSpaces && wrap == TextWrapMode::Wrap) return "break-spaces";
    return "unsupported";
}
// Counts the native search space WITHOUT reading fields or creating a NodeList.
// Secure descendants are never entered. Such a scope is incomplete for native
// for= lookup; implicit labels can still use their separately complete subtree.
struct ScopeBound { size_t nodes { 0 }; bool complete { true }; };
ScopeBound boundLabelScope(Element& root, N::ReadBudget& budget, std::vector<RefPtr<HTMLLabelElement>>* labels = nullptr)
{
    ScopeBound result;
    RefPtr<Node> cursor = &root;
    size_t depth = 1;
    while (cursor) {
        budget.visitRaw(depth);
        ++result.nodes;
        bool descend = true;
        if (auto* input = dynamicDowncast<HTMLInputElement>(*cursor); input && input->isSecureField()) {
            // Approved PRIVATE structural-presence probe only. A secure input's
            // editor is UA shadow, never these light DOM children. No child is
            // entered, counted, or read. Nonempty means hidden label scope unknown.
            if (cursor->firstChild()) result.complete = false;
            descend = false;
        } else if (auto* element = dynamicDowncast<Element>(*cursor)) {
            // Separate count-only LIGHT-DOM discovery may cross foreign native
            // identities/kinds/pointers to prove there are no HTML labels. It
            // reads no foreign attrs/style/text/length or synchronizing getter.
            if (labels) if (auto* label = dynamicDowncast<HTMLLabelElement>(*element)) labels->push_back(label);
            // Author shadow trees have their separate projection degradation;
            // ordinary label association stays in this actual native TreeScope.
        } // Native reference-target searches are not projected.
        if (descend && cursor->firstChild()) { cursor = cursor->firstChild(); ++depth; continue; }
        while (cursor && cursor.get() != &root && !cursor->nextSibling()) { cursor = cursor->parentNode(); --depth; }
        if (!cursor || cursor.get() == &root) break;
        cursor = cursor->nextSibling();
    }
    return result;
}
// The native association getter can read IDs during a lazy ordered-map scan.
// Prebind its EXACT safe search prefix, not merely label literal-text input.
// Unknown references never call control() and never grant affected authority.
RefPtr<HTMLElement> associatedControl(HTMLLabelElement& label, const AtomString& forID,
    bool explicitFor, N::ReadBudget& budget)
{
    require(!label.document().settings().shadowRootReferenceTargetEnabled(), "native label reference targets unsupported");
    size_t work = 0;
    RefPtr<HTMLElement> expected;
    if (explicitFor) {
        if (auto* map = label.explicitlySetAttrElementsMapIfExists())
            require(!map->contains(HTMLNames::forAttr), "explicit native for-element override unsupported");
        if (forID.isEmpty() || !label.treeScope().hasElementWithId(forID)) {
            budget.evidence(); // Hash presence only, no native fallback traversal.
            NativeAttributeRead::prechargeNativeForScans(label, budget, true);
            auto actual = label.control();
            require(!actual, "native absent label association changed");
            return nullptr;
        }
    }
    RefPtr<Node> root;
    if (explicitFor) root = &label.treeScope().rootNode();
    else root = &label;
    RefPtr<Node> cursor = root->firstChild();
    size_t depth = 1;
    bool resolved = false;
    while (cursor) {
        budget.visitRaw(depth);
        ++work;
        auto* element = dynamicDowncast<Element>(*cursor);
        auto* input = element ? dynamicDowncast<HTMLInputElement>(*element) : nullptr;
        bool secure = input && input->isSecureField(); // BEFORE candidate attrs/ID.
        if (explicitFor) {
            require(!secure, "native for-label lookup would read secure ID");
            // Stop at an explicit/inherited author omit BEFORE any ID probe or
            // descent. Automatic public foreign-unavailable markers are distinct
            // from this narrowly preflighted native author hint. Preorder cannot
            // reach a descendant of an omitted root because that root rejects.
            if (element) require(!NativeAttributeRead::authorOmittedForAssociation(*element, budget),
                "native for-label lookup would cross author omission");
            if (element && element->isInTreeScope()) {
                // Native false hasID does not scan attrs. Positive hasID uses
                // exact null-namespace QName semantics; both this scan and the
                // eventual native fallback scan are precharged before probing.
                const auto& candidateID = NativeAttributeRead::nativeID(*element, budget, true);
                budget.chargePrivate(candidateID.length());
                if (candidateID == forID) {
                    auto* html = dynamicDowncast<HTMLElement>(*element);
                    if (html && html->isLabelable()) expected = html;
                    resolved = true;
                    break; // Native lazy scan also stops at this first match.
                }
            }
        } else if (auto* html = element ? dynamicDowncast<HTMLElement>(*element) : nullptr; html && html->isLabelable()) {
            // isLabelable is native type state, no attrs/value/length. A secure
            // input may be this PRIVATE identity; native control() stops here.
            expected = html;
            resolved = true;
            break;
        }
        require(!secure, "native implicit-label scan would enter secure children");
        if (cursor->firstChild()) { cursor = cursor->firstChild(); ++depth; continue; }
        while (cursor && cursor.get() != root.get() && !cursor->nextSibling()) { cursor = cursor->parentNode(); --depth; }
        if (!cursor || cursor.get() == root.get()) break;
        cursor = cursor->nextSibling();
    }
    require(!explicitFor || resolved, "native for-label positive map did not resolve bounded prefix");
    budget.chargeTraversal(work); // Native getter's repeated prefix walk charged BEFORE call.
    NativeAttributeRead::prechargeNativeForScans(label, budget, explicitFor);
    auto actual = label.control();
    require(actual == expected, "native label association changed after bounded prefix");
    return actual;
}

// BEGIN EXCLUDED-LABEL-ASSOCIATION-HELPER
// CSS-hidden labels still participate in native HTML association. Retain only
// that bounded PRIVATE relationship: no excluded label text, style, value or
// subtree contents are captured. Explicit author omission stays unavailable.
Session::LabelState excludedLabelAssociation(Session::PreparedRead& read,
    HTMLLabelElement& label, N::ReadBudget& budget)
{
    Session::LabelState evidence;
    evidence.node = &label;
    evidence.privateComplete = false; // Excluded content is not an exact baseline.
    try {
        require(read.valid() && label.isConnected()
            && &label.document() == read.context().document.get(), "excluded label context unavailable");
        size_t depth = 0;
        for (RefPtr<Node> ancestor = &label; ancestor; ancestor = ancestor->parentOrShadowHostNode()) {
            budget.visitRaw(++depth);
            if (auto* element = dynamicDowncast<Element>(*ancestor))
                require(!NativeAttributeRead::authorOmittedForAssociation(*element, budget),
                    "excluded label association crosses author omission");
        }
        require(!label.document().settings().shadowRootReferenceTargetEnabled(),
            "excluded label reference targets unsupported");
        if (auto* map = label.explicitlySetAttrElementsMapIfExists())
            require(!map->contains(HTMLNames::forAttr), "excluded native for-element override unsupported");
        const auto& forID = NativeAttributeRead::qualified(label, HTMLNames::forAttr, budget);
        budget.chargePrivate(forID.length()); // BEFORE validation or retained String copy.
        for (unsigned i = 0; i < forID.length(); ++i) {
            auto unit = forID[i];
            require(unit && !(unit >= 0xdc00 && unit <= 0xdfff), "non-scalar excluded label for");
            if (unit >= 0xd800 && unit <= 0xdbff)
                require(++i < forID.length() && forID[i] >= 0xdc00 && forID[i] <= 0xdfff,
                    "non-scalar excluded label for");
        }
        const bool explicitAssociation = !forID.isNull();
        evidence.forAttribute = forID;
        // If later native resolution is unavailable, the exact supported for=
        // relation still proves that differently named controls are unaffected.
        evidence.onlyMatchingID = explicitAssociation;
        evidence.target = associatedControl(label, forID, explicitAssociation, budget);
        require(read.valid(), "excluded label context changed during association");
        evidence.associationComplete = !evidence.target
            || (&evidence.target->document() == read.context().document.get() && evidence.target->isConnected());
    } catch (const std::invalid_argument&) {
        // Preserve genuinely unknown association and all existing fail-closed
        // rules. No native getter is retried; label text/style/value stay unread.
    }
    return evidence;
}
// END EXCLUDED-LABEL-ASSOCIATION-HELPER
}

Publisher::Publisher(Session& owner, PublisherHooks value) : session(owner), hooks(std::move(value))
{
    require(!session.refreshPaired, "one Publisher per native Session");
    session.refreshPaired = [this]() -> std::optional<Context> {
        if (!refresh(false)) return std::nullopt;
        return session.boundContext;
    };
    session.captureForFacade = [this](HTMLFormControlElement& control, bool graphical) {
        return registerFacade(control, graphical);
    };
}
Publisher::~Publisher()
{
    session.refreshPaired = {};
    session.captureForFacade = {};
    session.invalidate(); // Composition destroys popup/facades before Publisher/Session.
}
void Publisher::revoke() noexcept
{
    session.admission = false;
    session.activeLease.reset();
}
void Publisher::invalidateAuthority() noexcept
{
    // The binding has already checked the immutable owner/worker. In contrast
    // with Session::invalidate(), this lifecycle entry calls no ownership hook.
    // Preserve phase: an interrupted capture/action still owns its busy guard.
    if (session.invalidationSerial == std::numeric_limits<uint64_t>::max()) session.retired = true;
    else ++session.invalidationSerial;
    session.admission = false;
    session.activeLease.reset();
    session.registry.clear();
    session.publishedControls.clear();
    session.boundContext.reset();
    publishedFocus = nullptr;
    publishedLabels.clear();
    publishedEditable = false;
    // slot, retained, enteredEffects and every counter/high-water are untouched.
}
std::optional<Context> Publisher::exactContext() const
{
    if (!session.thread() || !hooks.currentFrame) return std::nullopt;
    RefPtr frame = hooks.currentFrame();
    if (!frame || !frame->document()) return std::nullopt;
    return contextFromAppDocument(*frame, *frame->document(), revisions.highWater() ? revisions.highWater() : 1);
}
bool Publisher::checkpoint(const Context& expected)
{
    // This is an actual backend operation, never cached validation. The binding
    // holds the existing complete Host -> Bridge -> JSLock scopes throughout.
    const auto serial = session.invalidationSerial;
    if (!session.exactCurrent(expected, serial) || !hooks.captureCheckpoint) return false;
    if (!hooks.captureCheckpoint(expected) || !session.exactCurrent(expected, serial)) return false;
    auto current = exactContext();
    return current && session.sameDocument(expected, *current) && session.exactCurrent(expected, serial);
}
void Publisher::restrictPopup(Session::Capture& capture) const
{
    // Profile1795 has no native popup owner. Keep actual safe selection/body
    // values while refusing Begin/Finish/lease authority for single-select.
    if (capture.observed.kind == F::FormKind::select_one && !session.hooks.openNativeUserPopup) {
        capture.observed.capabilities = 0;
        capture.observed.lease.reset();
    }
}
void Publisher::bodyControl(const Session::Capture& captured, N::Node& out, N::ReadBudget& budget)
{
    const auto& control = captured.observed;
    out.disabled = control.disabled;
    out.editable = false; // Native control edit authority is only the paired descriptor.
    out.masked = control.kind == F::FormKind::secure_readonly;
    out.omitted = control.omitted;
    out.text.clear(); out.name.clear(); out.value.clear(); out.href.clear();
    if (out.masked || out.omitted) return;
    // All display fields come from the SAME captured control, no native reread.
    budget.chargeBody(N::utf16Units(control.label));
    out.name = control.label;
    if (const auto* text = std::get_if<F::FormTextState>(&control.state)) {
        budget.chargeBody(N::utf16Units(text->value));
        out.value = text->value;
    }
}
Publisher::CapturedBody Publisher::capture(const Context& context, N::ReadBudget& budget, const Session::PreparedRead* seed)
{
    CapturedBody result;
    result.read = session.beginRead(context, budget);
    auto& read = *result.read;
    if (seed) {
        require(seed->valid() && session.sameDocument(seed->exact, context), "facade seed identity changed");
        // Seed before traversal, so a newly observed same native pointer cannot
        // receive competing IDs in the graphical and whole-TUI prepared stages.
        for (const auto& entry : seed->registry) if (entry.node) {
            auto existing = read.knownID(*entry.node);
            if (existing) require(*existing == entry.id, "conflicting native seed identity");
            else {
                require(read.registry.size() < Session::maxLiveHandles, "native seed registry bound");
                read.registry.push_back(entry);
            }
        }
    }
    auto& out = result.publication;
    out.identity = wireIdentity(context);
    out.version = out.forms.version = context.version;
    // This seam intentionally projects light DOM, not CSS generated content.
    out.degradation = generatedContent;
    result.focused = context.document->focusedElement();
    out.editor.flags = session.editorFlags(context);
    result.editorEditable = (out.editor.flags & 1) != 0;
    RefPtr<Element> root = context.document->body();
    if (!root) root = context.document->documentElement();
    if (!root) return result; // Empty forest, never a synthetic root.
    bool rootExcluded = false;
    size_t outerDepth = 0;
    for (RefPtr<Element> outer = root->parentElement(); outer; outer = outer->parentElement()) {
        budget.visitRaw(++outerDepth);
        if (!is<HTMLElement>(*outer)) { rootExcluded = true; out.degradation |= unknownStyle; break; }
        rootExcluded = session.presentation(*outer, budget).omitted || rootExcluded;
    }
    struct Ancestor { RefPtr<Node> node; uint64_t id; };
    std::vector<Ancestor> ancestry;
    std::vector<RefPtr<HTMLLabelElement>> labels;
    RefPtr<Node> cursor = root;
    uint64_t parent = 0;
    size_t depth = 1;
    while (cursor) {
        // Whole-body prefix exhaustion keeps only complete paired descriptors.
        if (out.nodes.size() == N::maxNodes) { out.truncated = true; break; }
        budget.visitRaw(depth);
        bool descend = true, emitted = false;
        uint64_t emittedID = parent;
        if (auto* element = dynamicDowncast<Element>(*cursor)) {
            // Secure detection precedes localName/attributes/style/focusable/
            // child-count/label/value/selection/length and descendant reads.
            auto* input = dynamicDowncast<HTMLInputElement>(*element);
            bool secure = input && input->isSecureField();
            bool foreign = !is<HTMLElement>(*element);
            Presentation decision;
            if (secure || foreign) decision.omitted = true; // No foreign attrs/style/descendants.
            else decision = session.presentation(*element, budget, cursor.get() == root.get() && rootExcluded);
            if (!secure && !decision.styleKnown) out.degradation |= unknownStyle;
            N::Node node;
            auto id = read.idFor(*element);
            require(id.has_value(), "body native registry capacity");
            node.id = emittedID = *id;
            node.parent = parent;
            node.kind = N::NodeKind::element;
            node.masked = secure;
            node.omitted = decision.omitted;
            // localName is safe native tag metadata after the secure branch.
            session.copy(element->localName(), node.tag, N::TextSection::metadata, budget);
            auto* formControl = dynamicDowncast<HTMLFormControlElement>(*element);
            bool hasDescriptor = formControl && (is<HTMLInputElement>(*formControl)
                || is<HTMLTextAreaElement>(*formControl) || is<HTMLSelectElement>(*formControl));
            if (hasDescriptor) {
                read.controls.push_back(read.capture(*formControl, decision));
                restrictPopup(read.controls.back());
                descend = false; // No stale default/UA text beside live fields.
            } else if (node.omitted) descend = false;
            else {
                // BUTTON/FIELDSET/OUTPUT remain body elements with their actual
                // child caption/structure; they are not unsupported draft rows.
                node.disabled = formControl && formControl->isDisabledFormControl();
                node.editable = element->isContentEditable();
                static const AtomString name("name"_s), href("href"_s), aria("aria-label"_s);
                const auto& ariaName = NativeAttributeRead::literal(*element, aria, budget);
                session.copy(ariaName.isEmpty() ? NativeAttributeRead::literal(*element, name, budget) : ariaName, node.name, N::TextSection::body, budget);
                if (element->localName() == "a"_s)
                    session.copy(NativeAttributeRead::literal(*element, href, budget), node.href, N::TextSection::body, budget);
                if (auto* label = dynamicDowncast<HTMLLabelElement>(*element)) labels.push_back(label);
                if (element->openOrClosedShadowRoot()) out.degradation |= authorShadow;
                if (element->localName() == "iframe"_s || element->localName() == "frame"_s) out.degradation |= frameContent;
            }
            if (!node.masked && !node.omitted) {
                // Count ALL actual direct children under the raw-work budget,
                // including unpublished children. Never Node::length().
                for (RefPtr<Node> child = element->firstChild(); child; child = child->nextSibling()) {
                    budget.visitRaw(depth + 1);
                    require(node.native_child_count < N::maxTraversal, "native child-count bound");
                    ++node.native_child_count;
                }
                N::Metadata metadata;
                metadata.node = *id;
                static const AtomString role("role"_s);
                if (hasDescriptor) {
                    // Do not reread control attrs after its Capture. The exact
                    // private attribute row supplies this public allowlisted field.
                    budget.evidence(read.controls.back().attributes.size());
                    for (const auto& attribute : read.controls.back().attributes)
                        if (attribute.name == "role"_s && attribute.prefix.isNull()) {
                            session.copy(attribute.value, metadata.role, N::TextSection::metadata, budget);
                            break;
                        }
                } else session.copy(NativeAttributeRead::literal(*element, role, budget), metadata.role, N::TextSection::metadata, budget);
                metadata.display = displayName(decision.display);
                metadata.white_space = whitespaceName(decision);
                budget.chargeMetadata(metadata.display.size());
                budget.chargeMetadata(metadata.white_space.size());
                if (metadata.display == "unsupported") out.degradation |= unknownStyle;
                if (metadata.white_space == "unsupported") out.degradation |= unsupportedWhitespace;
                out.metadata.push_back(std::move(metadata));
            }
            budget.chargeNode();
            out.nodes.push_back(std::move(node));
            emitted = true;
        } else if (auto* text = dynamicDowncast<Text>(*cursor)) {
            N::Node node;
            node.kind = N::NodeKind::text;
            auto id = read.idFor(*text);
            require(id.has_value(), "body text registry capacity");
            node.id = emittedID = *id;
            node.parent = parent;
            // Ordinary public text may be longer than one wire field/pool.
            // Keep one scalar-safe native preorder prefix, with no edit authority.
            const bool complete = copyPublicText(text->data(), node.text, budget);
            budget.chargeNode();
            out.nodes.push_back(std::move(node));
            emitted = true;
            if (!complete) { out.truncated = true; break; }
        }
        if (descend && cursor->firstChild()) {
            ancestry.push_back({ cursor, emitted ? emittedID : parent });
            parent = emitted ? emittedID : parent;
            cursor = cursor->firstChild(); ++depth;
            continue;
        }
        while (cursor && cursor.get() != root.get() && !cursor->nextSibling()) {
            cursor = cursor->parentNode();
            require(!ancestry.empty(), "native traversal ancestry");
            ancestry.pop_back(); --depth;
            parent = ancestry.empty() ? 0 : ancestry.back().id;
        }
        if (!cursor || cursor.get() == root.get()) break;
        cursor = cursor->nextSibling();
    }
    // Discover hidden/outside-prefix label identities without reading their
    // fields. Missing private association scope cannot silently grant a lease.
    if (out.truncated) {
        result.labels.push_back({}); // Prefix is explicitly capability-free.
    } else {
        std::vector<RefPtr<HTMLLabelElement>> allLabels;
        bool completeLabelScope = true;
        if (RefPtr<Element> scopeRoot = context.document->documentElement())
            completeLabelScope = boundLabelScope(*scopeRoot, budget, &allLabels).complete;
        result.labels = captureLabels(read, labels, budget, out.degradation);
        for (const auto& label : allLabels) if (std::find(labels.begin(), labels.end(), label) == labels.end()) {
            auto association = excludedLabelAssociation(read, *label, budget);
            if (!association.associationComplete) out.degradation |= labelUnavailable;
            result.labels.push_back(std::move(association));
        }
        if (!completeLabelScope) result.labels.push_back({}); // Explicit unknown private scope marker.
    }
    session.attachLabels(read, result.labels, out.degradation);
    for (const auto& control : read.controls) if (!control.styleComplete) out.degradation |= unknownStyle;
    // Associated labels/values are final now. Preflight their exact deferred
    // public body cost; do not turn expected projection exhaustion into a fault.
    if (!publicControlBodyFits(read.controls, budget.remaining(N::TextSection::body),
        [](const auto& control) { return descriptor(control); })) {
        // A coherent empty forest is preferable to holes/partial paired rows.
        // Keep context/serial/focus/editor facts and all monotonic counters.
        out.truncated = true;
        out.nodes.clear(); out.metadata.clear(); out.forms.controls.clear();
        out.selection.reset(); out.editor.active_node = 0;
        read.controls.clear(); read.registry.clear(); result.labels.clear();
    } else {
        // Install fields from the FINAL SAME captured controls; no native reread.
        for (auto& node : out.nodes) for (const auto& control : read.controls)
            if (descriptor(control) && control.observed.node == node.id) bodyControl(control, node, budget);
    }
    if (out.truncated) {
        out.degradation |= selectionUnavailable | labelUnavailable;
        for (auto& control : read.controls) { control.observed.capabilities = 0; control.observed.lease.reset(); }
    } else selection(result, budget);
    if (result.focused) {
        auto id = read.knownID(*result.focused);
        if (id) for (const auto& node : out.nodes)
            if (node.id == *id) out.editor.active_node = *id;
        if (!out.editor.active_node) out.degradation |= selectionUnavailable;
    }
    require(context.document->focusedElement() == result.focused, "native focus changed during paired read");
    require(session.editorFlags(context) == out.editor.flags, "native editor/client state changed during paired read");
    require(read.valid(), "identity/thread/invalidation changed after native traversal");
    return result;
}

std::vector<Session::LabelState> Publisher::captureLabels(Session::PreparedRead& read,
    const std::vector<RefPtr<HTMLLabelElement>>& labels, N::ReadBudget& budget, uint32_t& degradation)
{
    std::vector<Session::LabelState> labelEvidence;
    for (const auto& label : labels) {
        Session::LabelState evidence;
        evidence.node = label;
        evidence.styleComplete = session.attributes(*label, evidence.attributes, budget);
        session.rawSubtree(read, *label, evidence.subtree, true);
        evidence.styleComplete = evidence.styleComplete && session.subtreeStyleComplete(evidence.subtree);
        evidence.privateComplete = evidence.styleComplete && session.subtreeComplete(evidence.subtree);
        if (!evidence.styleComplete) degradation |= unknownStyle;
        size_t units = 0;
        for (const auto& row : evidence.subtree) {
            require(row.text.length() <= N::maxFieldUnits - units, "label literal field bound");
            units += row.text.length();
        }
        budget.chargePrivate(units); // Bound StringBuilder BEFORE allocation.
        StringBuilder text;
        for (const auto& row : evidence.subtree) text.append(row.text);
        evidence.text = text.toString();
        const auto& forID = NativeAttributeRead::qualified(*label, HTMLNames::forAttr, budget);
        bool explicitAssociation = !forID.isNull();
        evidence.forAttribute = forID;
        evidence.onlyMatchingID = explicitAssociation && !read.exact.document->settings().shadowRootReferenceTargetEnabled();
        if (auto* map = label->explicitlySetAttrElementsMapIfExists())
            if (map->contains(HTMLNames::forAttr)) evidence.onlyMatchingID = false;
        try {
            evidence.target = associatedControl(*label, forID, explicitAssociation, budget);
            evidence.associationComplete = true;
            if (evidence.target && (&evidence.target->document() != read.exact.document.get()
                || !evidence.target->isConnected())) evidence.associationComplete = false;
        } catch (const std::invalid_argument&) {
            // Optional naming degradation is explicit and bounded; no partially
            // captured control becomes actionable due to a missing name.
            degradation |= labelUnavailable;
        }
        labelEvidence.push_back(std::move(evidence));
    }
    return labelEvidence;
}

void Session::attachLabels(PreparedRead& read, const std::vector<LabelState>& evidence, uint32_t& degradation)
{
    for (auto& control : read.controls) {
        if (control.observed.kind == F::FormKind::secure_readonly || control.observed.omitted) continue;
        std::string associated;
        for (const auto& label : evidence) {
            if (!label.associationComplete) {
                degradation |= labelUnavailable;
                // This is the SAME captured exact native hasID/QName result,
                // not AtomString literal semantics or a second attribute read.
                bool affected = !label.onlyMatchingID || control.nativeID == label.forAttribute;
                if (affected) {
                    // Unknown private association is never edit authority. An
                    // exact different/absent ID proves an explicit ordinary
                    // for-label cannot affect this candidate when references
                    // and explicit element overrides are disabled.
                    control.privateComplete = control.observed.complete = false;
                    control.observed.capabilities = 0;
                    control.observed.lease.reset();
                    if (auto* text = std::get_if<F::FormTextState>(&control.observed.state)) text->selection.reset();
                }
                continue;
            }
            if (label.target.get() != control.node.get()) continue;
            control.labels.push_back(label); // Exact native association + bounded evidence.
            if (!label.privateComplete) {
                control.privateComplete = control.observed.complete = false;
                control.styleComplete = control.styleComplete && label.styleComplete;
                control.observed.capabilities = 0;
                control.observed.lease.reset();
                if (auto* text = std::get_if<F::FormTextState>(&control.observed.state)) text->selection.reset();
            }
            if (!control.observed.label.empty()) continue; // Native aria-label precedence.
            std::string part;
            copy(label.text, part, N::TextSection::forms, read.bounds);
            if (!associated.empty() && !part.empty()) {
                read.bounds.chargeForms(1);
                associated += ' ';
            }
            require(N::utf16Units(associated) <= N::maxFieldUnits - N::utf16Units(part), "joined label field bound");
            associated += part;
        }
        if (control.observed.label.empty()) control.observed.label = std::move(associated);
    }
}

void Publisher::selection(CapturedBody& captured, N::ReadBudget& budget)
{
    auto& read = *captured.read;
    auto& publication = captured.publication;
    const auto& native = read.exact.frame->selection().selection();
    if (native.isNone()) return;
    auto point = [&](const Position& position) -> std::optional<N::Endpoint> {
        RefPtr<Node> anchor = position.anchorNode();
        if (!anchor || !anchor->isConnected() || &anchor->document() != read.exact.document.get()) return std::nullopt;
        // Never ask a secure/omitted/unpublished node for its length or offset.
        auto find = [&](Node& node) -> const N::Node* {
            auto id = read.knownID(node);
            if (!id) return nullptr;
            for (const auto& record : publication.nodes)
                if (record.id == *id && !record.masked && !record.omitted) return &record;
            return nullptr;
        };
        const N::Node* record = find(*anchor);
        if (!record) return std::nullopt;
        uint32_t offset = 0;
        switch (position.anchorType()) {
        case Position::PositionIsOffsetInAnchor: {
            int raw = position.offsetInContainerNode(); // O(1) ONLY in this case.
            if (raw < 0) return std::nullopt;
            offset = static_cast<uint32_t>(raw);
            break;
        }
        case Position::PositionIsBeforeChildren: offset = 0; break;
        case Position::PositionIsAfterChildren: offset = record->native_child_count; break;
        case Position::PositionIsBeforeAnchor:
        case Position::PositionIsAfterAnchor: {
            RefPtr<Node> parent = anchor->parentNode();
            if (!parent) return std::nullopt;
            record = find(*parent);
            if (!record || record->kind != N::NodeKind::element) return std::nullopt;
            bool found = false;
            for (RefPtr<Node> sibling = parent->firstChild(); sibling; sibling = sibling->nextSibling()) {
                budget.visitRaw(1);
                if (sibling == anchor) { found = true; break; }
                ++offset;
            }
            if (!found) return std::nullopt;
            if (position.anchorType() == Position::PositionIsAfterAnchor) ++offset;
            break;
        }
        }
        if (record->kind == N::NodeKind::text) {
            if (position.anchorType() != Position::PositionIsOffsetInAnchor
                || !N::scalarBoundary(record->text, offset)) return std::nullopt;
            return N::Endpoint { record->id, N::EndpointKind::text_utf16, offset };
        }
        if (offset > record->native_child_count) return std::nullopt;
        return N::Endpoint { record->id, N::EndpointKind::element_child, offset };
    };
    auto anchor = point(native.anchor()), focus = point(native.focus());
    if (!anchor || !focus) { publication.degradation |= selectionUnavailable; return; }
    publication.selection = N::NativeSelection { *anchor, *focus, std::nullopt };
}

bool Publisher::samePublic(const N::OwnedPublication& a, const N::OwnedPublication& b) const
{
    if (a.identity != b.identity || a.nodes != b.nodes || a.metadata != b.metadata || a.selection != b.selection
        || a.editor.active_node != b.editor.active_node || a.editor.flags != b.editor.flags
        || a.truncated != b.truncated || a.degradation != b.degradation || a.forms.controls.size() != b.forms.controls.size()) return false;
    for (size_t i = 0; i < a.forms.controls.size(); ++i)
        if (!F::form_control_state_matches(a.forms.controls[i], b.forms.controls[i])) return false;
    return true;
}
bool Publisher::refresh(bool trustedAction, std::optional<uint64_t> issueLease, bool force,
    const Session::Capture* focusBaseline)
{
    if (!session.thread() || (!trustedAction && session.phase != Session::Phase::idle)
        || (trustedAction && session.phase != Session::Phase::action)) return false;
    auto previous = session.phase;
    struct PhaseExit { Session::Phase& current; Session::Phase previous; ~PhaseExit() { current = previous; } } exit { session.phase, previous };
    session.phase = trustedAction ? Session::Phase::actionCapture : Session::Phase::capture;
    try {
        auto context = exactContext();
        require(context.has_value(), "canonical ready document unavailable");
        require(checkpoint(*context), "native style checkpoint unavailable");
        if (session.boundContext && !session.sameDocument(*session.boundContext, *context)) {
            if (trustedAction) throw std::invalid_argument("action crossed native document identity");
            session.invalidate();
        }
        N::ReadBudget budget;
        auto native = capture(*context, budget);
        return commitCaptured(native, issueLease, force, focusBaseline);
    } catch (...) {
        revoke(); // Old immutable bytes remain historical, never action authority.
        return false;
    }
}
bool Publisher::commitCaptured(CapturedBody& native, std::optional<uint64_t> issueLease,
    bool force, const Session::Capture* focusBaseline)
{
    auto& read = *native.read;
    if (focusBaseline) {
        auto found = std::find_if(read.controls.begin(), read.controls.end(), [&](const auto& value) { return value.node == focusBaseline->node; });
        require(found != read.controls.end() && session.actionable(*found), "focus handler retargeted control");
        auto expected = *focusBaseline;
        expected.focused = found->focused;
        expected.observed.focused = found->observed.focused;
        // BEGIN adopts stable postfocus canEdit and input-method state.
        // Composition, undo/redo and every other flag remain exact.
        expected.editorFlags = (expected.editorFlags & ~(1U | 16U))
            | (found->editorFlags & (1U | 16U));
        std::optional<F::FormControlRange> verifiedSelection;
        if (std::holds_alternative<F::FormTextState>(found->observed.state)) {
            auto* text = dynamicDowncast<HTMLTextFormControlElement>(*found->node);
            require(text && found->innerRoot, "focused native text selection unavailable");
            // Passive existing native getters only: no second focus, style or
            // layout checkpoint, DOM dispatch, value flattening or retry loop.
            auto sameFocusedContext = [&] {
                return read.valid() && found->node->isConnected()
                    && &found->node->document() == read.exact.document.get()
                    && read.exact.document->focusedElement() == found->node.get()
                    && text->innerTextElement() == found->innerRoot.get()
                    && session.editorFlags(read.exact) == found->editorFlags
                    && session.hooks.foreground && session.hooks.foreground();
            };
            require(sameFocusedContext(), "focused native selection context changed");
            F::FormControlRange sampled { text->selectionStart(), text->selectionEnd(), F::FormDirection::none };
            const auto direction = text->selectionDirection();
            require(direction == "none"_s || direction == "forward"_s || direction == "backward"_s,
                "focused native selection direction unavailable");
            if (direction == "forward"_s) sampled.direction = F::FormDirection::forward;
            else if (direction == "backward"_s) sampled.direction = F::FormDirection::backward;
            require(sameFocusedContext(), "focused native selection context changed during sample");
            verifiedSelection = sampled;
        }
        require(normalizeBeginTextSelection(expected.observed, found->observed, verifiedSelection)
            && session.sameCapture(expected, *found), "focus handler changed full control baseline");
    }
    auto& publication = native.publication;
    for (const auto& control : read.controls) if (descriptor(control)) publication.forms.controls.push_back(control.observed);
    const auto& old = slot.current();
    bool oldLease = false;
    if (old.publication()) for (const auto& control : old.publication()->forms.controls) oldLease |= control.lease.has_value();
    bool survivingLease = !publication.truncated && session.leaseWillSurvive(read);
    // Unsupported private graph/foreign evidence cannot establish full native
    // equality. Re-publish cap-free observations rather than silently retaining
    // a full-baseline revision across an unobservable private change.
    bool privateEvidenceComplete = !publication.truncated && std::all_of(read.controls.begin(), read.controls.end(), [](const auto& control) {
        return control.styleComplete;
    }) && std::all_of(native.labels.begin(), native.labels.end(), [&](const auto& label) {
        // Association-only evidence is complete for unrelated captured controls.
        // Compare ONLY already-captured pointers/IDs: no new native reads here.
        // An unresolved exact for= relation excludes differently named controls;
        // matching or genuinely unknown association still prevents reuse.
        return label.privateComplete || (label.associationComplete
            ? std::none_of(read.controls.begin(), read.controls.end(), [&](const auto& control) {
                return label.target.get() == control.node.get();
            })
            : label.onlyMatchingID && std::none_of(read.controls.begin(), read.controls.end(), [&](const auto& control) {
                return control.nativeID == label.forAttribute;
            }));
    });
    bool identical = privateEvidenceComplete && old.publication() && samePublic(publication, *old.publication())
        && session.matchesCommitted(read) && publishedFocus == native.focused
        && publishedEditable == native.editorEditable && publishedLabels == native.labels && oldLease == survivingLease;
    if (!force && !issueLease && identical) {
        require(read.valid(), "native identity changed before identical-publication reuse");
        session.admission = true;
        return true;
    }
    auto revision = revisions.reserve(), editorRevision = editorRevisions.reserve();
    if (!revision || !editorRevision) session.retired = true;
    require(revision && editorRevision, "native publication/editor counter exhausted");
    publication.version = { read.exact.version.generation, read.exact.version.epoch, *revision };
    publication.editor.revision = *editorRevision;
    publication.forms.version = publication.version;
    auto forms = session.prepareCommit(std::move(read), publication.version, issueLease, publication.truncated);
    publication.forms.controls.clear();
    for (const auto& control : forms.controls) if (descriptor(control)) publication.forms.controls.push_back(control.observed);
    // Validation, UTF8 conversion and ALL owned allocation/encoding precede
    // either install. preparePublication constructs an immutable owned pair.
    auto prepared = N::preparePublication(std::move(publication));
    require(session.exactCurrent(forms.context, native.read->serial), "native identity changed just before commit");
    // Serialized engine turn, no script/callback/allocating operation between
    // these two no-throw moves; no observer can see an intermediate half pair.
    session.commit(std::move(forms));
    slot.commit(std::move(prepared));
    publishedFocus = std::move(native.focused);
    publishedLabels.swap(native.labels);
    publishedEditable = native.editorEditable;
    return true;
}
std::optional<Session::Capture> Publisher::registerFacade(HTMLFormControlElement& control, bool graphical)
{
    if (!session.thread()) return std::nullopt;
    const auto beforePhase = session.phase;
    if (beforePhase != Session::Phase::idle
        && (beforePhase != Session::Phase::action || !session.trustedPopupFacade)) return std::nullopt;
    struct Exit { Session::Phase& out; Session::Phase value; ~Exit() { out = value; } } exit { session.phase, beforePhase };
    session.phase = beforePhase == Session::Phase::action ? Session::Phase::actionCapture : Session::Phase::capture;
    try {
        auto context = exactContext();
        require(context && session.boundContext && session.sameDocument(*context, *session.boundContext), "facade native identity changed");
        require(checkpoint(*context), "facade style checkpoint unavailable");
        N::ReadBudget budget;
        auto staged = session.beginRead(*context, budget, true);
        staged->graphical = graphical;
        Presentation decision;
        // Secure branch before ancestor hints/style or any control fields.
        if (auto* input = dynamicDowncast<HTMLInputElement>(control); input && input->isSecureField()) decision.omitted = true;
        else {
            std::vector<RefPtr<Element>> ancestry;
            for (RefPtr<Element> element = &control; element; element = element->parentElement()) {
                budget.visitRaw(ancestry.size() + 1);
                ancestry.push_back(element);
            }
            bool inherited = false;
            for (auto it = ancestry.rbegin(); it != ancestry.rend(); ++it) {
                decision = session.presentation(**it, budget, inherited);
                if (graphical) decision.omitted = inherited || !decision.styleKnown || decision.inert
                    || decision.display == static_cast<unsigned>(DisplayType::None)
                    || decision.visibility != static_cast<unsigned>(Visibility::Visible);
                inherited = decision.omitted;
            }
        }
        auto first = staged->capture(control, decision);
        restrictPopup(first);
        // Fresh graphical labels are read from the actual native document, even
        // when TUI omission excludes their body markers. This pass uses no live
        // NodeList and never enters secure subtrees; incomplete associations are
        // explicitly capability-free rather than copied from old publication.
        std::vector<RefPtr<HTMLLabelElement>> labels;
        bool completeLabelScope = true;
        if (RefPtr<Element> root = context->document->documentElement())
            completeLabelScope = boundLabelScope(*root, budget, &labels).complete;
        uint32_t degradation = 0;
        auto labelEvidence = captureLabels(*staged, labels, budget, degradation);
        if (!completeLabelScope) labelEvidence.push_back({});
        staged->controls.push_back(std::move(first));
        session.attachLabels(*staged, labelEvidence, degradation);
        auto observed = staged->controls.front(); // Owned return allocated before commit.
        require(staged->valid(), "facade identity changed after capture");
        // A fresh full TUI read owns public state. Only weak native identity
        // additions are merged from the graphical stage; hidden native values,
        // graphical capabilities and label text never enter the TUI projection.
        bool addedIDs = false;
        for (const auto& entry : staged->registry) if (entry.node && !session.knownID(*entry.node)) addedIDs = true;
        auto whole = capture(*context, budget, staged.get());
        for (const auto& entry : staged->registry) {
            auto pointer = entry.node.get();
            if (!pointer) continue;
            auto found = std::find_if(whole.read->registry.begin(), whole.read->registry.end(), [&](const auto& value) { return value.node.get() == pointer; });
            if (found != whole.read->registry.end()) require(found->id == entry.id, "facade staged native identity conflict");
            else {
                require(whole.read->registry.size() < Session::maxLiveHandles, "facade native registry bound");
                whole.read->registry.push_back(entry);
                addedIDs = true;
            }
        }
        // Re-read the same graphical control against the merged staged registry
        // after the whole TUI read. No callback may mutate this baseline while
        // its IDs are being installed. Keep label association evidence fresh.
        auto verification = session.beginRead(*context, budget, false);
        verification->registry = whole.read->registry;
        verification->graphical = graphical;
        auto second = verification->capture(control, decision);
        restrictPopup(second);
        uint32_t verifiedDegradation = 0;
        auto verifiedLabels = captureLabels(*verification, labels, budget, verifiedDegradation);
        if (!completeLabelScope) verifiedLabels.push_back({});
        verification->controls.push_back(std::move(second));
        session.attachLabels(*verification, verifiedLabels, verifiedDegradation);
        require(session.sameCapture(observed, verification->controls.front()) && verification->valid(), "facade baseline changed before paired install");
        require(commitCaptured(whole, {}, addedIDs, nullptr), "facade paired commit failed");
        return observed;
    } catch (...) { revoke(); return std::nullopt; }
}

std::shared_ptr<const N::OwnedPublication> Publisher::refreshAndCopy()
{
    if (!refresh(false)) return {};
    return slot.current().publication();
}
N::Completion Publisher::failure(const N::Query& request, N::CompletionCode code, bool effects) const
{
    N::Completion reply;
    reply.request = request;
    reply.code = code;
    reply.effects_entered = effects;
    reply.outcome = effects ? F::FormDraftOutcome::unknown : F::FormDraftOutcome::rejected;
    return reply;
}
bool Publisher::afterEffects(const Context& before, uint64_t serial, uint64_t node, bool lease, N::Completion& reply)
{
    if (!session.exactCurrent(before, serial) || !refresh(true, lease ? std::optional<uint64_t>(node) : std::nullopt, true)) {
        revoke();
        if (session.exactCurrent(before, serial) && refresh(true, {}, true))
            reply.publication = *slot.current().publication(); // Owned concealed/deleted/readonly poststate, no lease.
        return false;
    }
    const auto& current = slot.current().publication();
    if (!current || current->identity != wireIdentity(before)) { revoke(); return false; }
    auto found = std::find_if(current->forms.controls.begin(), current->forms.controls.end(), [&](const auto& value) { return value.node == node; });
    reply.publication = *current; // Actual owned post-handler state, not desired value.
    if (found == current->forms.controls.end() || !found->complete || (lease && !found->lease)) { revoke(); return false; }
    reply.outcome = F::FormDraftOutcome::accepted;
    reply.code = N::CompletionCode::ok;
    return true;
}
N::Completion Publisher::begin(const N::ActionRequest& action, const F::BeginFormControl& request)
{
    auto context = session.boundContext;
    const auto* live = session.captured(request.node);
    if (!context || context->version != request.expected || !live || !descriptor(*live))
        return failure(action.request, N::CompletionCode::stale_document);
    if (!live->privateComplete || !live->observed.capabilities || !session.hooks.foreground || !session.hooks.foreground())
        return failure(action.request, N::CompletionCode::unavailable);
    auto baseline = *live; // ALL allocations/retained baseline copying before focus.
    RefPtr<HTMLFormControlElement> control = live->node;
    auto serial = session.invalidationSerial;
    session.activeLease.reset(); // Before any author handler can reenter.
    auto reply = failure(action.request, N::CompletionCode::readback_failed, true);
    enteredEffects = true;
    UserGestureIndicator gesture(IsProcessingUserGesture::Yes, context->document.get());
    control->focus(FocusOptions { .preventScroll = true });
    if (!session.exactCurrent(*context, serial) || !control->isConnected()
        || !refresh(true, request.node, true, &baseline)) {
        revoke();
        if (session.exactCurrent(*context, serial) && refresh(true, {}, true)) reply.publication = *slot.current().publication();
        return reply;
    }
    const auto& publication = slot.current().publication();
    auto updated = publication ? std::find_if(publication->forms.controls.begin(), publication->forms.controls.end(),
        [&](const auto& v) { return v.node == request.node; }) : std::vector<F::FormControl>::const_iterator { };
    if (!publication || updated == publication->forms.controls.end() || !updated->lease) { revoke(); return reply; }
    reply.publication = *publication;
    reply.outcome = F::FormDraftOutcome::accepted;
    reply.code = N::CompletionCode::ok;
    return reply;
}
N::Completion Publisher::open(const N::ActionRequest& action, const F::OpenFormPopup& request)
{
    auto context = session.boundContext;
    const auto* live = session.captured(request.node);
    auto* select = live && live->node ? dynamicDowncast<HTMLSelectElement>(*live->node) : nullptr;
    if (!context || context->version != request.expected || !live)
        return failure(action.request, N::CompletionCode::stale_document);
    if (!select || !live->privateComplete || !F::form_has(live->observed.capabilities, F::FormCapability::open_popup)
        || !session.hooks.foreground || !session.hooks.foreground() || !session.hooks.openNativeUserPopup)
        return failure(action.request, N::CompletionCode::unsupported);
    auto serial = session.invalidationSerial;
    session.activeLease.reset();
    auto reply = failure(action.request, N::CompletionCode::readback_failed, true);
    enteredEffects = true;
    UserGestureIndicator gesture(IsProcessingUserGesture::Yes, context->document.get());
    {
        SharedGuard trusted(session, *context); // Private constructor; no external bypass.
        reply.popup_opened = session.hooks.openNativeUserPopup(*select, trusted);
    }
    if (!afterEffects(*context, serial, request.node, false, reply)) return reply;
    if (!reply.popup_opened) {
        reply.outcome = F::FormDraftOutcome::unknown;
        reply.code = N::CompletionCode::readback_failed;
    }
    return reply;
}
N::Completion Publisher::apply(const N::ActionRequest& action, const F::FormLease& expected)
{
    auto context = session.boundContext;
    if (!context || !session.activeLease || session.activeLease->wire != expected
        || !session.sameDocument(session.activeLease->context, *context) || context->version.revision < expected.captured.revision)
        return failure(action.request, N::CompletionCode::stale_document);
    const auto* live = session.captured(expected.node);
    if (!live || !session.sameCapture(session.activeLease->baseline, *live) || !session.actionable(*live)
        || !session.hooks.foreground || !session.hooks.foreground())
        return failure(action.request, N::CompletionCode::stale_control);
    RefPtr<HTMLFormControlElement> control = live->node;
    RefPtr<HTMLTextFormControlElement> text;
    RefPtr<HTMLInputElement> checkbox;
    RefPtr<HTMLSelectElement> select;
    RefPtr<HTMLOptionElement> option;
    unsigned optionIndex = 0;
    String insertion;
    // All validation/copies/conversion precede lease consumption and effects.
    if (const auto* request = std::get_if<F::ReplaceFormText>(&action.action)) {
        text = dynamicDowncast<HTMLTextFormControlElement>(*control);
        const auto* state = std::get_if<F::FormTextState>(&live->observed.state);
        if (!text || !state || !F::form_has(live->observed.capabilities, F::FormCapability::replace_text)
            || (live->editorFlags & 2)) return failure(action.request, N::CompletionCode::unsupported);
        (void)F::form_byte_selection(state->editing_text, request->range);
        (void)F::form_control_range(request->text, { 0, request->text.size() });
        require(N::utf16Units(request->text) <= N::maxFieldUnits, "insertion field bound");
        insertion = String::fromUTF8(std::span<const char>(request->text.data(), request->text.size()));
    } else if (const auto* request = std::get_if<F::SetFormChecked>(&action.action)) {
        checkbox = dynamicDowncast<HTMLInputElement>(*control);
        if (!checkbox || !checkbox->isCheckbox() || !F::form_has(live->observed.capabilities, F::FormCapability::set_checked))
            return failure(action.request, N::CompletionCode::invalid_action);
        (void)request;
    } else if (const auto* request = std::get_if<F::SetFormOption>(&action.action)) {
        select = dynamicDowncast<HTMLSelectElement>(*control);
        const auto* state = std::get_if<F::FormSelectState>(&live->observed.state);
        if (!select || !state || !select->multiple() || select->usesMenuList()
            || !F::form_has(live->observed.capabilities, F::FormCapability::set_option))
            return failure(action.request, N::CompletionCode::invalid_action);
        bool found = false;
        for (size_t i = 0; i < state->options.size(); ++i) if (state->options[i].node == request->option) {
            if (state->options[i].disabled || state->options[i].omitted || i >= live->options.size())
                return failure(action.request, N::CompletionCode::invalid_action);
            option = live->options[i].node;
            optionIndex = static_cast<unsigned>(i);
            found = option && option->ownerSelectElement() == select && select->item(optionIndex) == option.get();
            break;
        }
        if (!found) return failure(action.request, N::CompletionCode::stale_control);
    } else if (!std::holds_alternative<F::FinishFormControl>(action.action)
        || !F::form_has(live->observed.capabilities, F::FormCapability::finish))
        return failure(action.request, N::CompletionCode::invalid_action);
    auto baseline = *live;
    auto serial = session.invalidationSerial;
    session.activeLease.reset(); // Consumed BEFORE selection/editor/click/blur callbacks.
    auto reply = failure(action.request, N::CompletionCode::readback_failed);
    UserGestureIndicator gesture(IsProcessingUserGesture::Yes, context->document.get());
    if (const auto* request = std::get_if<F::ReplaceFormText>(&action.action)) {
        auto normalized = request->range.direction;
        if (normalized == F::FormDirection::none && context->frame->editor().behavior().shouldConsiderSelectionAsDirectional())
            normalized = F::FormDirection::forward;
        auto direction = normalized == F::FormDirection::backward ? SelectionHasBackwardDirection
            : normalized == F::FormDirection::forward ? SelectionHasForwardDirection : SelectionHasNoDirection;
        reply.outcome = F::FormDraftOutcome::unknown;
        reply.effects_entered = enteredEffects = true;
        text->setSelectionRange(request->range.start, request->range.end, direction, SelectionRevealMode::DoNotReveal);
        if (!session.exactCurrent(*context, serial) || !control->isConnected()) { revoke(); return reply; }
        const auto& selected = context->frame->selection().selection();
        if (enclosingTextFormControl(selected.start()) != text || enclosingTextFormControl(selected.end()) != text) { revoke(); return reply; }
        // Native selection setters may run callbacks. Re-read the WHOLE current
        // document into a discarded prepared stage; do not commit an unrelated
        // intermediate forms revision. Only the deliberate range may differ.
        N::ReadBudget budget;
        session.phase = Session::Phase::actionCapture;
        CapturedBody staged;
        try {
            auto current = exactContext();
            require(current && session.sameDocument(*context, *current) && checkpoint(*current)
                && session.exactCurrent(*context, serial), "post-selection style checkpoint unavailable");
            staged = capture(*context, budget);
        }
        catch (...) { session.phase = Session::Phase::action; throw; }
        session.phase = Session::Phase::action;
        auto found = std::find_if(staged.read->controls.begin(), staged.read->controls.end(), [&](const auto& v) { return v.node == control; });
        if (found == staged.read->controls.end()) { revoke(); return reply; }
        auto* state = std::get_if<F::FormTextState>(&found->observed.state);
        if (!state || !state->selection || state->selection->start != request->range.start
            || state->selection->end != request->range.end || state->selection->direction != normalized) { revoke(); return reply; }
        std::get<F::FormTextState>(baseline.observed.state).selection = state->selection;
        if (!session.sameCapture(baseline, *found) || !session.actionable(*found)
            || !staged.read->valid() || !context->frame->editor().canEdit()) { revoke(); return reply; }
        if (!insertion.isEmpty()) context->frame->editor().insertText(insertion, nullptr, TextEventInputKeyboard);
        else if (request->range.start != request->range.end)
            context->frame->editor().deleteWithDirection(SelectionDirection::Backward, TextGranularity::CharacterGranularity, false, true);
    } else if (const auto* request = std::get_if<F::SetFormChecked>(&action.action)) {
        const auto& state = std::get<F::FormCheckState>(baseline.observed.state);
        if (state.checked != request->checked) {
            reply.outcome = F::FormDraftOutcome::unknown;
            reply.effects_entered = enteredEffects = true;
            checkbox->dispatchSimulatedClick(nullptr, SendNoEvents, DoNotShowPressedLook);
        }
    } else if (const auto* request = std::get_if<F::SetFormOption>(&action.action)) {
        const auto& state = std::get<F::FormSelectState>(baseline.observed.state);
        if (state.options[optionIndex].selected != request->selected) {
            reply.outcome = F::FormDraftOutcome::unknown;
            reply.effects_entered = enteredEffects = true;
            select->optionSelectedByUser(static_cast<int>(optionIndex), true, true);
        }
    } else {
        reply.outcome = F::FormDraftOutcome::unknown;
        reply.effects_entered = enteredEffects = true;
        control->blur();
    }
    bool finish = std::holds_alternative<F::FinishFormControl>(action.action);
    afterEffects(*context, serial, expected.node, !finish, reply);
    return reply;
}
N::Completion Publisher::executeAndReadback(const N::ActionRequest& action)
{
    if (session.phase != Session::Phase::idle) return failure(action.request, N::CompletionCode::busy);
    if (!refresh(false) || !session.boundContext || wireIdentity(*session.boundContext) != action.request.identity)
        return failure(action.request, N::CompletionCode::stale_document);
    bool needsLease = !std::holds_alternative<F::OpenFormPopup>(action.action) && !std::holds_alternative<F::FinishFormControl>(action.action);
    auto liveHandles = std::count_if(session.registry.begin(), session.registry.end(), [](const auto& entry) { return !!entry.node; });
    if (exhausted(revisions) || exhausted(editorRevisions) || exhausted(session.nodeIDs)
        || static_cast<size_t>(liveHandles) >= Session::maxLiveHandles || (needsLease && exhausted(session.leaseIDs))) {
        revoke();
        return failure(action.request, N::CompletionCode::limit); // Known impossible readback: BEFORE effects.
    }
    session.phase = Session::Phase::action;
    struct Exit { Session::Phase& phase; ~Exit() { phase = Session::Phase::idle; } } exit { session.phase };
    return std::visit([&](const auto& request) -> N::Completion {
        using T = std::decay_t<decltype(request)>;
        if constexpr (std::is_same_v<T, F::BeginFormControl>) return begin(action, request);
        else if constexpr (std::is_same_v<T, F::OpenFormPopup>) return open(action, request);
        else return apply(action, request.expected);
    }, action.action);
}
std::shared_ptr<const N::ReplyReservation> Publisher::queryPacket(std::span<const uint8_t> packet, size_t capacity)
{
    // Capacity and fixed binary prefix are accepted BEFORE native traversal.
    auto output = std::make_shared<N::ReplyReservation>(capacity);
    require(session.thread() && session.phase == Session::Phase::idle, "v2 query reentry/wrong thread");
    auto context = exactContext();
    require(context.has_value(), "v2 ready identity unavailable");
    auto prefix = N::admitRequestPrefix(packet, N::PacketKind::query, wireIdentity(*context));
    auto request = N::decodeQuery(packet);
    require(request == prefix && request.document_request_id, "v2 query correlation");
    require(refresh(false), "v2 current capture unavailable");
    const auto& publication = slot.current().publication();
    require(publication && publication->identity == request.identity, "v2 document changed before query return");
    auto encoded = N::encodeReply({ request, *publication });
    output->retain(encoded);
    return output;
}
std::shared_ptr<const N::ReplyReservation> Publisher::executePacket(std::span<const uint8_t> packet, size_t capacity)
{
    require(capacity >= N::maxReplyBytes, "v2 action reply capacity");
    require(session.thread() && session.phase == Session::Phase::idle, "v2 action reentry/wrong thread");
    if (retained) {
        if (!retained->body && packet.size() == retained->input.size() && std::equal(packet.begin(), packet.end(), retained->input.begin()))
            return retained->completion; // Exact consumed retry: no native refresh/action.
        throw std::invalid_argument("v2 prior action completion requires ACK");
    }
    auto output = std::make_shared<N::ReplyReservation>(capacity); // Full1MiB before effects.
    auto action = N::decodeAction(packet); // Own ALL action text before any focus/editor call.
    // Binding has already checked the exact canonical owner/worker/document
    // packet. Keep these checks owned-only: live replacement/unavailability is
    // an entered-operation inner rejection, retained below for checked ACK.
    auto prefix = N::admitRequestPrefix(packet, N::PacketKind::action, action.request.identity);
    require(prefix.outer_sequence > actionHighWater && !prefix.document_request_id, "v2 action expired/correlation");
    require(action.request == prefix, "v2 action prefix changed");
    auto unknown = failure(prefix, N::CompletionCode::readback_failed, true);
    auto rejected = failure(prefix, N::CompletionCode::readback_failed, false);
    auto fallbackUnknown = N::encodeCompletion(unknown), fallbackRejected = N::encodeCompletion(rejected);
    Retained pending { prefix, std::nullopt, N::Bytes(packet.begin(), packet.end()), output };
    retained = std::move(pending); // Request+outcome storage exists BEFORE effects.
    actionHighWater = prefix.outer_sequence;
    enteredEffects = false;
    try {
        auto completion = executeAndReadback(action);
        auto encoded = N::encodeCompletion(completion);
        output->retain(encoded);
    } catch (...) {
        revoke(); // Cannot restore a consumed lease after uncertain processing/encoding.
        output->retain(enteredEffects ? std::span<const uint8_t>(fallbackUnknown) : std::span<const uint8_t>(fallbackRejected));
    }
    return output;
}
CachedRequestStatus Publisher::inspectCachedRequest(const N::Query& request,
    const std::optional<N::ActionRequest>& action) const
{
    try {
        // The caller deep-decodes the entire canonical packet. Validate the
        // supplied owned values too, including query/action token separation.
        // No native pointer, Session helper or hook is dereferenced below.
        if (action) {
            N::validateActionRequest(*action);
            if (action->request != request) return CachedRequestStatus::invalid;
        } else N::validateQuery(request);
        if (session.phase != Session::Phase::idle) return CachedRequestStatus::busy;
        if (session.retired || exhausted(revisions) || exhausted(editorRevisions) || exhausted(session.nodeIDs))
            return CachedRequestStatus::limit;
        // Query deliberately needs no cached publication or admission. Actual
        // backend capture establishes its current same-engine publication.
        if (!action) return CachedRequestStatus::ok;
        if (retained) return CachedRequestStatus::busy; // Guard handles exact replay first.
        if (actionHighWater == std::numeric_limits<uint64_t>::max()) return CachedRequestStatus::limit;
        if (request.outer_sequence <= actionHighWater) return CachedRequestStatus::stale;
        const auto& publication = slot.current().publication();
        if (!session.admission || !publication || publication->identity != request.identity)
            return CachedRequestStatus::stale;
        const bool needsLease = !std::holds_alternative<F::OpenFormPopup>(action->action)
            && !std::holds_alternative<F::FinishFormControl>(action->action);
        if (needsLease && exhausted(session.leaseIDs)) return CachedRequestStatus::limit;
        return std::visit([&](const auto& operation) -> CachedRequestStatus {
            using T = std::decay_t<decltype(operation)>;
            const uint64_t node = [&]() {
                if constexpr (std::is_same_v<T, F::BeginFormControl> || std::is_same_v<T, F::OpenFormPopup>) return operation.node;
                else return operation.expected.node;
            }();
            const auto found = std::find_if(publication->forms.controls.begin(), publication->forms.controls.end(),
                [&](const auto& control) { return control.node == node; });
            if (found == publication->forms.controls.end()) return CachedRequestStatus::stale;
            const auto& control = *found;
            if (!control.complete || control.omitted || control.disabled || control.read_only || !control.focusable
                || control.kind == F::FormKind::secure_readonly || control.kind == F::FormKind::unsupported)
                return CachedRequestStatus::unsupported;
            if constexpr (std::is_same_v<T, F::BeginFormControl> || std::is_same_v<T, F::OpenFormPopup>) {
                if (operation.expected != publication->version) return CachedRequestStatus::stale;
                if constexpr (std::is_same_v<T, F::OpenFormPopup>)
                    return control.kind == F::FormKind::select_one && F::form_has(control.capabilities, F::FormCapability::open_popup)
                        ? CachedRequestStatus::ok : CachedRequestStatus::unsupported;
                else return control.capabilities ? CachedRequestStatus::ok : CachedRequestStatus::unsupported;
            } else {
                if (!session.activeLease || session.activeLease->wire != operation.expected
                    || operation.expected.captured.generation != publication->version.generation
                    || operation.expected.captured.epoch != publication->version.epoch
                    || operation.expected.captured.revision > publication->version.revision
                    || !F::form_control_state_matches(control, session.activeLease->baseline.observed))
                    return CachedRequestStatus::stale;
                if constexpr (std::is_same_v<T, F::ReplaceFormText>) {
                    const auto* text = std::get_if<F::FormTextState>(&control.state);
                    if (!text || !F::form_has(control.capabilities, F::FormCapability::replace_text))
                        return CachedRequestStatus::unsupported;
                    // Cached editing text only; authoritative native scalar
                    // conversion is repeated by apply() before author effects.
                    (void)F::form_byte_selection(text->editing_text, operation.range);
                    (void)N::utf16Units(operation.text);
                } else if constexpr (std::is_same_v<T, F::SetFormChecked>) {
                    if (control.kind != F::FormKind::checkbox || !F::form_has(control.capabilities, F::FormCapability::set_checked))
                        return CachedRequestStatus::unsupported;
                } else if constexpr (std::is_same_v<T, F::SetFormOption>) {
                    const auto* select = std::get_if<F::FormSelectState>(&control.state);
                    if (control.kind != F::FormKind::select_many || !select || select->menu_list
                        || !F::form_has(control.capabilities, F::FormCapability::set_option)) return CachedRequestStatus::unsupported;
                    const auto option = std::find_if(select->options.begin(), select->options.end(),
                        [&](const auto& row) { return row.node == operation.option; });
                    if (option == select->options.end() || option->disabled || option->omitted) return CachedRequestStatus::stale;
                } else if (!F::form_has(control.capabilities, F::FormCapability::finish)) return CachedRequestStatus::unsupported;
                return CachedRequestStatus::ok;
            }
        }, action->action);
    } catch (...) { return CachedRequestStatus::invalid; }
}
bool Publisher::matchesOwnedReply(const N::Query& request, std::span<const uint8_t> packet) const
{
    try {
        if (request.document_request_id) {
            N::validateQuery(request);
            auto decoded = N::decodeReply(packet); // Full portable bounds/redaction/join validation.
            const auto& current = slot.current();
            if (decoded.request != request || !current.publication() || !current.encoded()
                || current.publication()->identity != request.identity) return false;
            // Canonical re-encoding compares EVERY owned field, revisions and
            // lease included, and preserves exact native Rect double bits.
            auto encoded = N::encodePublication(decoded.publication);
            const auto& committed = *current.encoded();
            return encoded.size() == committed.size() && std::equal(encoded.begin(), encoded.end(), committed.begin());
        }
        N::validateActionPrefix(request);
        auto decoded = N::decodeCompletion(packet); // Includes outcome/code/effects/popup and full paired readback.
        if (decoded.request != request || !retained || retained->body || retained->request != request || !retained->completion) return false;
        const auto owned = retained->completion->bytes();
        // Retained completion, not mutable slot.current(): a later query or
        // lifecycle invalidation cannot erase an action's exact owned outcome.
        return packet.size() == owned.size() && std::equal(packet.begin(), packet.end(), owned.begin());
    } catch (...) { return false; }
}
bool Publisher::retireActionMetadata(const N::Identity& identity, uint64_t sequence,
    std::span<const uint8_t> exactInput) noexcept
{
    // Binding checks immutable worker and owner; no Session::thread(), hook,
    // native identity lookup, admission test or counter check belongs in ACK.
    if (session.phase != Session::Phase::idle || !retained || retained->body || retained->request.identity != identity
        || retained->request.outer_sequence != sequence || exactInput.size() != retained->input.size()
        || !std::equal(exactInput.begin(), exactInput.end(), retained->input.begin())) return false;
    retained.reset(); // Only owned retained metadata; preserve next lease/high-waters.
    return true;
}

const N::Node* Publisher::bodyRecord(uint64_t id) const noexcept
{
    const auto& publication = slot.current().publication();
    if (!publication || publication->truncated) return nullptr;
    const auto found = std::find_if(publication->nodes.begin(), publication->nodes.end(),
        [id](const auto& node) { return node.id == id; });
    if (found == publication->nodes.end() || found->omitted || found->masked || found->disabled) return nullptr;
    return &*found;
}
CachedRequestStatus Publisher::inspectCachedBodyRequest(const A::Request& request) const
{
    try {
        // Re-encode to validate all typed fields/padding. No live pointer or
        // Session::thread/hook is consulted by this owned-only admission.
        const auto canonical = A::encodeRequest(request.key, request.expected, request.action);
        if (canonical.bytes != request.bytes) return CachedRequestStatus::invalid;
        if (session.phase != Session::Phase::idle || retained || session.activeLease) return CachedRequestStatus::busy;
        if (session.retired || exhausted(revisions) || exhausted(editorRevisions) || exhausted(session.nodeIDs)
            || actionHighWater == UINT64_MAX) return CachedRequestStatus::limit;
        const auto& publication = slot.current().publication();
        if (!session.admission || !publication || publication->identity != A::identity(request.key)
            || publication->version != request.expected || request.key.request_sequence <= actionHighWater)
            return CachedRequestStatus::stale;
        return std::visit([&](const auto& operation) -> CachedRequestStatus {
            using T = std::decay_t<decltype(operation)>;
            if constexpr (std::is_same_v<T, A::Select>) {
                const auto* anchor = bodyRecord(operation.anchor.node);
                const auto* focus = bodyRecord(operation.focus.node);
                if (!anchor || !focus) return CachedRequestStatus::stale;
                const auto point = [](const N::Node& node, const N::Endpoint& endpoint) {
                    if (endpoint.kind == N::EndpointKind::text_utf16)
                        return node.kind == N::NodeKind::text && N::scalarBoundary(node.text, endpoint.offset);
                    return node.kind == N::NodeKind::element && endpoint.offset <= node.native_child_count;
                };
                return point(*anchor, operation.anchor) && point(*focus, operation.focus)
                    ? CachedRequestStatus::ok : CachedRequestStatus::invalid;
            } else {
                const auto* node = bodyRecord(operation.node);
                if (!node || node->kind != N::NodeKind::element) return CachedRequestStatus::stale;
                if constexpr (std::is_same_v<T, A::ChooseSingleOption>) {
                    const auto control = std::find_if(publication->forms.controls.begin(), publication->forms.controls.end(),
                        [&](const auto& value) { return value.node == operation.node; });
                    if (control == publication->forms.controls.end() || control->kind != F::FormKind::select_one
                        || !control->complete || control->disabled || control->read_only || control->omitted || !control->focusable)
                        return CachedRequestStatus::unsupported;
                    const auto* select = std::get_if<F::FormSelectState>(&control->state);
                    if (!select || select->multiple) return CachedRequestStatus::unsupported;
                    const auto option = std::find_if(select->options.begin(), select->options.end(),
                        [&](const auto& value) { return value.node == operation.option; });
                    return option != select->options.end() && !option->omitted && !option->disabled
                        ? CachedRequestStatus::ok : CachedRequestStatus::stale;
                } else if constexpr (std::is_same_v<T, A::Activate>) {
                    // Hints only. Actual native kinds and disabled/focusability
                    // are checked again after the fenced whole-document read.
                    if (node->tag == "a" && !node->href.empty()) return CachedRequestStatus::ok;
                    if (node->tag == "button") return CachedRequestStatus::ok;
                    if (node->tag != "input") return CachedRequestStatus::unsupported;
                    const auto control = std::find_if(publication->forms.controls.begin(), publication->forms.controls.end(),
                        [&](const auto& value) { return value.node == operation.node; });
                    return control != publication->forms.controls.end() && control->complete && !control->disabled
                        && !control->omitted && (control->native_type == "button" || control->native_type == "reset"
                            || control->native_type == "submit") ? CachedRequestStatus::ok : CachedRequestStatus::unsupported;
                } else return CachedRequestStatus::ok;
            }
        }, request.action);
    } catch (...) { return CachedRequestStatus::invalid; }
}
A::Completion Publisher::executeBodyNativeAction(const A::Request& request)
{
    auto reply = A::Completion { request.key, A::Result::rejected, A::Code::unavailable, false, std::nullopt };
    // The complete cached admission ran immediately before the global slot
    // was reserved. Recheck live authority without treating our own debt as
    // a competing action.
    if (session.phase != Session::Phase::idle || session.activeLease) { reply.code = A::Code::busy; return reply; }
    if (!session.thread() || !session.hooks.foreground || !session.hooks.foreground()) return reply;
    const auto& displayed = slot.current().publication();
    if (!session.admission || !displayed || displayed->identity != A::identity(request.key)
        || displayed->version != request.expected) { reply.code = A::Code::stale_document; return reply; }
    auto context = exactContext();
    if (!context || wireIdentity(*context) != A::identity(request.key)) { reply.code = A::Code::stale_document; return reply; }
    auto liveHandles = std::count_if(session.registry.begin(), session.registry.end(), [](const auto& entry) { return !!entry.node; });
    if (exhausted(revisions) || exhausted(editorRevisions) || exhausted(session.nodeIDs)
        || static_cast<size_t>(liveHandles) >= Session::maxLiveHandles) { reply.code = A::Code::limit; return reply; }
    session.phase = Session::Phase::action;
    struct Exit { Session::Phase& phase; ~Exit() { phase = Session::Phase::idle; } } exit { session.phase };
    const auto serial = session.invalidationSerial;
    require(bodyContinuation.has_value(), "body continuation was not reserved");
    bodyContinuation->before = *context;
    bodyContinuation->serial = serial;
    // A layout checkpoint is explicitly effect-capable. From here on any
    // admission/readback uncertainty is effects-entered and never replayable.
    reply.result = A::Result::indeterminate;
    reply.code = A::Code::readback_failed;
    reply.effects_entered = enteredEffects = true;
    if (!refresh(true) || !session.exactCurrent(*context, serial)) { revoke(); return reply; }
    const auto& fresh = slot.current().publication();
    if (!fresh || fresh->identity != A::identity(request.key) || fresh->version != request.expected) {
        return reply;
    }
    // Resolve weak native handles only after exact displayed-version/live
    // equality. Registry history alone never grants present publication scope.
    auto resolve = [&](uint64_t id) -> RefPtr<Node> {
        if (!bodyRecord(id)) return nullptr;
        auto node = session.resolve(id);
        if (!node || !node->isConnected() || &node->document() != context->document.get()) return nullptr;
        return node;
    };
    RefPtr<Element> element;
    RefPtr<HTMLSelectElement> select;
    RefPtr<HTMLOptionElement> option;
    std::optional<VisibleSelection> nativeSelection;
    unsigned optionIndex = 0;
    bool admitted = std::visit([&](const auto& operation) -> bool {
        using T = std::decay_t<decltype(operation)>;
        if constexpr (std::is_same_v<T, A::Select>) {
            auto position = [&](const N::Endpoint& endpoint) -> std::optional<Position> {
                auto node = resolve(endpoint.node);
                const auto* record = bodyRecord(endpoint.node);
                if (!node || !record) return std::nullopt;
                if (endpoint.kind == N::EndpointKind::text_utf16) {
                    auto* text = dynamicDowncast<Text>(*node);
                    if (!text || record->kind != N::NodeKind::text || text->length() > N::maxFieldUnits
                        || !N::scalarBoundary(record->text, endpoint.offset) || endpoint.offset > text->length()) return std::nullopt;
                    const auto& value = text->data(); // Already bounded current published text only.
                    if (endpoint.offset && endpoint.offset < value.length()
                        && value[endpoint.offset - 1] >= 0xd800 && value[endpoint.offset - 1] <= 0xdbff
                        && value[endpoint.offset] >= 0xdc00 && value[endpoint.offset] <= 0xdfff) return std::nullopt;
                } else {
                    if (!is<Element>(*node) || record->kind != N::NodeKind::element) return std::nullopt;
                    unsigned count = 0;
                    for (RefPtr<Node> child = node->firstChild(); child; child = child->nextSibling()) {
                        if (++count > N::maxTraversal) return std::nullopt;
                    }
                    if (count != record->native_child_count || endpoint.offset > count) return std::nullopt;
                }
                return makeContainerOffsetPosition(std::move(node), endpoint.offset);
            };
            auto anchor = position(operation.anchor), focus = position(operation.focus);
            if (!anchor || !focus) return false;
            nativeSelection.emplace(*anchor, *focus, Affinity::Downstream, Directionality::Strong);
            return !nativeSelection->isNone();
        } else {
            auto node = resolve(operation.node);
            element = node ? dynamicDowncast<Element>(*node) : nullptr;
            if (!element) return false;
            if (auto* control = dynamicDowncast<HTMLFormControlElement>(*element); control && control->isDisabledFormControl()) return false;
            if constexpr (std::is_same_v<T, A::Focus>) return element->isFocusable();
            else if constexpr (std::is_same_v<T, A::Activate>) {
                const auto* record = bodyRecord(operation.node);
                if (auto* anchor = dynamicDowncast<HTMLAnchorElement>(*element)) return record && !record->href.empty() && anchor->isLink();
                if (is<HTMLButtonElement>(*element)) return true;
                auto* input = dynamicDowncast<HTMLInputElement>(*element);
                const auto* control = session.captured(operation.node);
                return input && input->isTextButton() && control && control->privateComplete && control->styleComplete
                    && control->observed.complete && !control->observed.omitted;
            } else {
                select = dynamicDowncast<HTMLSelectElement>(*element);
                const auto* live = session.captured(operation.node);
                const auto* state = live ? std::get_if<F::FormSelectState>(&live->observed.state) : nullptr;
                if (!select || select->multiple() || !live || !state || state->multiple || !live->privateComplete
                    || !live->styleComplete || !live->observed.complete || live->observed.disabled || live->observed.read_only
                    || live->observed.omitted || !live->observed.focusable || state->options.size() != live->options.size()
                    || state->options.empty() || state->options.size() > N::maxOptions) return false;
                // length()/item() repeated work is bounded by the just-captured
                // complete native option graph, never a projected ordinal.
                if (select->length() != state->options.size()) return false;
                bool found = false;
                for (unsigned i = 0; i < state->options.size(); ++i) {
                    auto actual = select->item(i);
                    const auto& row = state->options[i];
                    if (!actual || actual != live->options[i].node.get() || actual->ownerSelectElement() != select
                        || !actual->isConnected() || &actual->document() != context->document.get()
                        || session.knownID(*actual) != std::optional<uint64_t>(row.node) || row.omitted) return false;
                    if (row.node != operation.option) continue;
                    if (row.disabled || actual->isDisabledFormControl()) return false;
                    option = actual; optionIndex = i; found = true;
                }
                return found && option && option->ownerSelectElement() == select;
            }
        }
    }, request.action);
    if (!admitted || !session.exactCurrent(*context, serial)) return reply;
    // Keep all targets/context strongly alive across author reentry; dispatch
    // completion never requires an activated target to survive its own handler.
    UserGestureIndicator gesture(IsProcessingUserGesture::Yes, context->document.get());
    std::visit([&](const auto& operation) {
        using T = std::decay_t<decltype(operation)>;
        if constexpr (std::is_same_v<T, A::Focus>) element->focus(FocusOptions { .preventScroll = true });
        else if constexpr (std::is_same_v<T, A::Activate>)
            (void)element->dispatchSimulatedClick(nullptr, SendNoEvents, DoNotShowPressedLook);
        else if constexpr (std::is_same_v<T, A::Select>) context->frame->selection().setSelection(*nativeSelection);
        else select->optionSelectedByUser(static_cast<int>(optionIndex), true, false);
    }, request.action);
    bodyContinuation->nativeReturned = true;
    return reply; // Final native microtasks MUST run before actual readback.
}

std::shared_ptr<const N::ReplyReservation> Publisher::executeBodyPacket(std::span<const uint8_t> packet, size_t capacity)
{
    require(capacity >= N::maxReplyBytes, "body action reply capacity");
    if (retained) {
        if (!bodyContinuation && retained->body && packet.size() == retained->input.size()
            && std::equal(packet.begin(), packet.end(), retained->input.begin())) return retained->completion;
        throw std::invalid_argument("global form/body action result requires family ACK");
    }
    require(session.thread() && session.phase == Session::Phase::idle, "body action reentry/wrong thread");
    auto request = A::decodeRequest(packet);
    const auto cached = inspectCachedBodyRequest(request);
    auto output = std::make_shared<N::ReplyReservation>(capacity);
    A::Completion unknown { request.key, A::Result::indeterminate, A::Code::readback_failed, true, std::nullopt };
    A::Completion rejected { request.key, A::Result::rejected, A::Code::readback_failed, false, std::nullopt };
    auto fallbackUnknown = A::encodeCompletion(request, unknown), fallbackRejected = A::encodeCompletion(request, rejected);
    require(request.key.request_sequence > actionHighWater, "body action expired sequence");
    N::Query outer { A::identity(request.key), request.key.request_sequence, 0 };
    // Full output, exact request, continuation and both fallback outcomes are
    // owned BEFORE any layout/native/author effects can enter.
    BodyContinuation continuation { request, std::nullopt, 0, false, rejected,
        std::move(fallbackUnknown), std::move(fallbackRejected), std::nullopt };
    Retained pending { outer, request, N::Bytes(packet.begin(), packet.end()), output };
    bodyContinuation = std::move(continuation);
    retained = std::move(pending);
    actionHighWater = request.key.request_sequence;
    enteredEffects = false;
    try {
        if (cached != CachedRequestStatus::ok) {
            auto reason = A::Code::invalid_action;
            if (cached == CachedRequestStatus::busy) reason = A::Code::busy;
            else if (cached == CachedRequestStatus::limit) reason = A::Code::limit;
            else if (cached == CachedRequestStatus::stale) reason = A::Code::stale_document;
            else if (cached == CachedRequestStatus::unsupported) reason = A::Code::unsupported;
            bodyContinuation->completion = { request.key, A::Result::rejected, reason, false, std::nullopt };
        } else bodyContinuation->completion = executeBodyNativeAction(request);
    } catch (...) {
        revoke();
        bodyContinuation->completion = enteredEffects ? unknown : rejected;
    }
    // The first Bridge's final microtasks may run author code. Its callbacks
    // see this same action phase busy; lifecycle invalidation preserves it.
    session.phase = Session::Phase::action;
    return output;
}
std::shared_ptr<const N::ReplyReservation> Publisher::finishBodyPacket()
{
    // Binding already checks the immutable owner. Retired native counters may
    // still need this owned fallback completion; no Session thread hook is
    // needed before the continuation can be finalized.
    require(session.phase == Session::Phase::action && bodyContinuation
        && retained && retained->body && retained->completion, "body finalization lacks reserved continuation");
    auto output = retained->completion;
    auto& continuation = *bodyContinuation;
    auto& reply = continuation.completion;
    try {
        if (continuation.nativeReturned && continuation.before) {
            const auto& before = *continuation.before;
            const auto replaced = [&]() {
                auto now = exactContext();
                if (now) return !session.sameDocument(before, *now);
                if (!hooks.currentFrame) return false;
                auto frame = hooks.currentFrame();
                return frame && frame->document() && frame->document() != before.document.get();
            };
            const auto contextReplaced = [&]() {
                revoke();
                reply.publication.reset();
                reply.result = A::Result::completed_needs_current_observation;
                reply.code = A::Code::context_replaced;
            };
            if (replaced()) contextReplaced();
            else if (!session.exactCurrent(before, continuation.serial) || !refresh(true)) {
                // A native call returned. A replacement during final microtasks
                // OR the readback checkpoint is a certain consumed operation.
                if (replaced()) contextReplaced();
                else revoke();
            } else {
                const auto& actual = slot.current().publication();
                if (!actual || actual->identity != A::identity(continuation.request.key)
                    || actual->version.revision < continuation.request.expected.revision) revoke();
                else {
                    continuation.witness = bodyReadbackWitness(before);
                    reply.publication = *actual;
                    reply.result = A::Result::completed;
                    reply.code = A::Code::ok;
                }
            }
        }
        if (reply.result == A::Result::indeterminate) revoke();
    } catch (...) {
        revoke();
        reply = { continuation.request.key, enteredEffects ? A::Result::indeterminate : A::Result::rejected,
            A::Code::readback_failed, enteredEffects, std::nullopt };
        continuation.witness.reset();
    }
    // Remain busy and keep tentative owned readback across the final natural
    // JSLock/Bridge unwind. No completed bytes are committed yet.
    return output;
}

Publisher::BodyReadbackWitness Publisher::bodyReadbackWitness(const Context& context) const
{
    BodyReadbackWitness witness;
    witness.context = context;
    witness.serial = session.invalidationSerial;
    witness.view = context.frame->view();
    require(witness.view && !context.document->needsStyleRecalc() && !witness.view->needsLayout(), "body readback needs rendering");
    witness.tree = context.document->domTreeVersion();
    witness.style = context.document->styleRecalcCount();
    witness.layout = witness.view->layoutContext().layoutUpdateCount();
    witness.focused = context.document->focusedElement();
    const auto& selection = context.frame->selection().selection();
    witness.selectionNone = selection.isNone();
    witness.anchor = selection.anchor(); witness.focus = selection.focus();
    witness.baseFirst = selection.isBaseFirst();
    witness.composition = context.frame->editor().compositionRange();
    witness.compositionNode = context.frame->editor().compositionNode();
    witness.editorFlags = session.editorFlags(context);
    witness.controls = session.publishedControls; // Preserve complete private evidence across invalidation.
    return witness;
}
bool Publisher::stableBodyReadback(const BodyReadbackWitness& witness) const
{
    const auto& context = witness.context;
    // value() privacy checks can consult Page hooks under an author stack.
    // Natural Bridge/lock unwind must have removed it; fail closed before any
    // getter rather than relying on that composition assumption implicitly.
    auto* vm = WebCore::commonVMOrNull();
    if (!vm || vm->topCallFrame) return false;
    // Same pattern as the native editor's stable_after_unwind. These reads are
    // deliberately passive and bounded: no checkpoint/computed-style request,
    // collection rebuilding, editor mutation, DOM dispatch or author API.
    if (!session.exactCurrent(context, witness.serial) || context.frame->view() != witness.view.get()
        || !witness.view || context.document->domTreeVersion() != witness.tree
        || context.document->needsStyleRecalc() || witness.view->needsLayout()
        || context.document->styleRecalcCount() != witness.style
        || witness.view->layoutContext().layoutUpdateCount() != witness.layout
        || context.document->focusedElement() != witness.focused.get()
        || !session.hooks.foreground || !session.hooks.foreground()
        || session.editorFlags(context) != witness.editorFlags) return false;
    const auto& selection = context.frame->selection().selection();
    if (selection.isNone() != witness.selectionNone || selection.anchor() != witness.anchor
        || selection.focus() != witness.focus || selection.isBaseFirst() != witness.baseFirst
        || context.frame->editor().compositionRange() != witness.composition
        || context.frame->editor().compositionNode() != witness.compositionNode.get()) return false;
    for (const auto& control : witness.controls) {
        if (!control.node || !control.node->isConnected() || &control.node->document() != context.document.get()) return false;
        // A masked/omitted row carries no value evidence. Never read its secret
        // storage to attest an unchanged public marker. Native tree/style/focus
        // fences above cover all captured structural/presentation fields.
        if (control.observed.kind == F::FormKind::secure_readonly || control.observed.omitted) continue;
        if (!control.privateComplete || !control.styleComplete || !control.observed.complete) return false;
        if (control.node->isDisabledFormControl() != control.observed.disabled
            || control.node->isReadOnly() != control.observed.read_only) return false;
        if (const auto* expected = std::get_if<F::FormTextState>(&control.observed.state)) {
            auto* text = dynamicDowncast<HTMLTextFormControlElement>(*control.node);
            if (!text || !expected->selection || !control.innerRoot || text->innerTextElement() != control.innerRoot.get()) return false;
            // A textarea value() can synchronize renderer state. The frozen
            // public cached predicate proves updateValue returns immediately;
            // otherwise do not call it outside the Bridge. The exact unchanged
            // complete inner subtree prebounds the passive innerTextValue walk.
            if (is<HTMLTextAreaElement>(*text) && !text->formControlValueMatchesRenderer()) return false;
            auto actual = text->value();
            auto editing = text->innerTextValue();
            if (actual->length() > N::maxFieldUnits || actual.get() != control.nativeValue
                || editing.length() > N::maxFieldUnits || editing != control.editingValue
                || text->selectionStart() != expected->selection->start || text->selectionEnd() != expected->selection->end) return false;
            const auto direction = text->selectionDirection();
            const auto wanted = expected->selection->direction == F::FormDirection::backward ? "backward"_s
                : expected->selection->direction == F::FormDirection::forward ? "forward"_s : "none"_s;
            if (direction != wanted) return false;
        } else if (const auto* expected = std::get_if<F::FormCheckState>(&control.observed.state)) {
            auto* input = dynamicDowncast<HTMLInputElement>(*control.node);
            if (!input || !input->isCheckbox() || input->checked() != expected->checked
                || input->indeterminate() != expected->indeterminate) return false;
        } else if (const auto* expected = std::get_if<F::FormSelectState>(&control.observed.state)) {
            auto* select = dynamicDowncast<HTMLSelectElement>(*control.node);
            if (!select || select->multiple() != expected->multiple || select->usesMenuList() != expected->menu_list
                || select->size() != control.selectSize || expected->options.size() != control.options.size()) return false;
            // Walk only already-retained native options. Never call length(),
            // item(), listItems() or an option text/value/label getter here.
            for (size_t i = 0; i < expected->options.size(); ++i) {
                const auto& row = expected->options[i];
                const auto& option = control.options[i].node;
                if (!option || !option->isConnected() || &option->document() != context.document.get()
                    || option->ownerSelectElement() != select || option->selectedWithoutUpdate() != row.selected
                    || option->isDisabledFormControl() != row.disabled) return false;
            }
        }
    }
    // The passive getter group may fail or expose changed cached state; never
    // use it to repair/move the tentative readback or perform another capture.
    return session.exactCurrent(context, witness.serial) && context.document->domTreeVersion() == witness.tree
        && !context.document->needsStyleRecalc() && !witness.view->needsLayout()
        && context.document->styleRecalcCount() == witness.style
        && witness.view->layoutContext().layoutUpdateCount() == witness.layout;
}
std::shared_ptr<const N::ReplyReservation> Publisher::completeBodyPacketAfterUnwind()
{
    // Binding supplies the checked serialized owner and retains its outer Host
    // TURN. No Bridge/lock/native checkpoint is entered on this final fence.
    require(session.phase == Session::Phase::action && bodyContinuation && retained && retained->body
        && retained->completion, "body unwind completion lacks reserved continuation");
    struct Exit { Session::Phase& phase; ~Exit() { phase = Session::Phase::idle; } } exit { session.phase };
    auto output = retained->completion;
    auto& continuation = *bodyContinuation;
    auto& reply = continuation.completion;
    try {
        if (continuation.nativeReturned && continuation.before) {
            auto now = exactContext();
            bool replaced = now && !session.sameDocument(*continuation.before, *now);
            if (!now && hooks.currentFrame) {
                auto frame = hooks.currentFrame();
                replaced = frame && frame->document() && frame->document() != continuation.before->document.get();
            }
            if (replaced) {
                revoke(); reply.publication.reset();
                reply.result = A::Result::completed_needs_current_observation;
                reply.code = A::Code::context_replaced;
            } else if (reply.result == A::Result::completed
                && (!continuation.witness || !stableBodyReadback(*continuation.witness))) {
                revoke(); reply.publication.reset();
                reply.result = A::Result::indeterminate;
                reply.code = A::Code::readback_failed;
            }
        }
        if (reply.result == A::Result::indeterminate) { revoke(); reply.publication.reset(); }
        const auto encoded = A::encodeCompletion(continuation.request, reply);
        output->retain(encoded);
    } catch (...) {
        revoke();
        output->retain(enteredEffects ? std::span<const uint8_t>(continuation.fallbackUnknown)
            : std::span<const uint8_t>(continuation.fallbackRejected));
    }
    bodyContinuation.reset();
    return output;
}

bool Publisher::matchesOwnedBodyReply(const A::Request& request, std::span<const uint8_t> packet) const
{
    try {
        (void)A::decodeCompletion(packet, request);
        if (!retained || !retained->body || retained->body->bytes != request.bytes || !retained->completion) return false;
        const auto owned = retained->completion->bytes();
        return packet.size() == owned.size() && std::equal(packet.begin(), packet.end(), owned.begin());
    } catch (...) { return false; }
}
bool Publisher::retireBodyMetadata(const A::Key& key, std::span<const uint8_t> exactInput) noexcept
{
    // Pure retained metadata only. No thread hook, native getter, capture,
    // Session hook, host TURN, registry callback or allocation on this path.
    if (session.phase != Session::Phase::idle || !retained || !retained->body || retained->body->key != key
        || exactInput.size() != retained->input.size()
        || !std::equal(exactInput.begin(), exactInput.end(), retained->input.begin())) return false;
    retained.reset();
    return true;
}
} // namespace BIB::FormsV2Combined
