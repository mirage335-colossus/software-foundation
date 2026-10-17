// Source candidate only. No WebCore compilation, link or execution is claimed.
#include "config.h"
#include "NativeFormsV2Combined.hpp"
#include "CombinedFormsIdentity.hpp"
#include <WebCore/Attribute.h>
#include <WebCore/ContainerNodeInlines.h>
#include <WebCore/ElementInlines.h>
#include <WebCore/ElementData.h>
#include <WebCore/QualifiedName.h>
#include <WebCore/StyleProperties.h>
#include <WebCore/StylePropertiesInlines.h>
#include <WebCore/CSSPrimitiveValue.h>
#include <WebCore/CSSColorValue.h>
#include <WebCore/Color.h>
#include <WebCore/Editor.h>
#include <WebCore/HTMLBRElement.h>
#include <WebCore/HTMLInputElement.h>
#include <WebCore/HTMLTextAreaElement.h>
#include <WebCore/HTMLTextFormControlElement.h>
#include <WebCore/NodeTraversal.h>
#include <WebCore/NodeInlines.h>
#include <WebCore/LocalFrameInlines.h>
#include <WebCore/RenderStyle.h>
#include <WebCore/RenderStyle+GettersInlines.h>
#include <WebCore/Text.h>
#include <WebCore/TextControlInnerElements.h>
#include <wtf/text/AtomString.h>
#include <algorithm>
#include <bit>
#include <cmath>
#include <limits>
#include <span>
#include <stdexcept>
#include <utility>

namespace BIB::FormsV2Combined {
using namespace WebCore;
using namespace WTF::StringLiterals;
static void require(bool value, const char* reason)
{
    if (!value) throw std::invalid_argument(reason);
}
static bool scalarText(const String& input)
{
    for (unsigned i = 0; i < input.length(); ++i) {
        auto unit = input[i];
        if (!unit || (unit >= 0xdc00 && unit <= 0xdfff)) return false;
        if (unit >= 0xd800 && unit <= 0xdbff)
            if (++i == input.length() || input[i] < 0xdc00 || input[i] > 0xdfff) return false;
    }
    return true;
}
static F::FormDirection nativeDirection(const AtomString& direction)
{
    if (direction == "forward"_s) return F::FormDirection::forward;
    if (direction == "backward"_s) return F::FormDirection::backward;
    return F::FormDirection::none;
}
namespace NativeAttributeRead {
static std::span<const Attribute> raw(Element& element)
{
    auto* input = dynamicDowncast<HTMLInputElement>(element);
    require(!input || !input->isSecureField(), "secure attribute read forbidden");
    auto* data = element.elementData();
    return data ? data->attributes() : std::span<const Attribute> { };
}
const AtomString& literal(Element& element, const AtomString& name, N::ReadBudget& budget)
{
    require(is<HTMLElement>(element), "literal foreign field read forbidden");
    const auto span = raw(element);
    budget.evidence(span.size()); // BEFORE the whole linear search.
    // Callers supply fixed lowercase colon-free literals only. This reproduces
    // AtomString getAttribute: absent prefix, localName exact, namespace ignored.
    // Skipping prefixed attrs avoids unbounded QualifiedName::toString entirely.
    for (const auto& attribute : span)
        if (!attribute.name().hasPrefix() && attribute.localName() == name) return attribute.value();
    return nullAtom();
}
const AtomString& qualified(Element& element, const QualifiedName& name, N::ReadBudget& budget)
{
    const auto span = raw(element);
    budget.evidence(span.size());
    // Actual native for/id QName matching: localName+namespace, prefix ignored.
    for (const auto& attribute : span) if (attribute.name().matches(name)) return attribute.value();
    return nullAtom();
}
const AtomString& nativeID(Element& element, N::ReadBudget& budget, bool reserveNativeRepeat)
{
    auto* input = dynamicDowncast<HTMLInputElement>(element);
    require(!input || !input->isSecureField(), "secure native ID read forbidden");
    // Native false fast path does not inspect attribute storage, including SVG.
    if (!element.hasID()) return nullAtom();
    const auto span = raw(element);
    budget.evidence(span.size()); // getIdAttribute's unsynchronizing QName scan.
    if (reserveNativeRepeat) budget.evidence(span.size()); // Native label fallback repeats it.
    return element.getIdAttribute(); // Exact hasID/QName semantics, no allocation/sync.
}
bool authorOmittedForAssociation(Element& element, N::ReadBudget& budget)
{
    static const AtomString omitName("data-foundation-tui"_s);
    const AtomString* hint = &nullAtom();
    if (is<HTMLElement>(element)) hint = &literal(element, omitName, budget);
    else {
        // Narrow SOURCE003 foreign grant: ONE fixed null-namespace raw hint,
        // before any association-only positive ID probe. No sync/stringification,
        // other attr values, style or public foreign fields are read here.
        const auto span = raw(element);
        budget.evidence(span.size());
        for (const auto& attribute : span)
            if (attribute.localName() == omitName && attribute.namespaceURI().isNull()) {
                hint = &attribute.value();
                break;
            }
    }
    budget.chargePrivate(hint->length());
    require(scalarText(*hint), "non-scalar association omit hint");
    return *hint == "omit"_s;
}
void prechargeNativeForScans(Element& label, N::ReadBudget& budget, bool explicitFor)
{
    const auto span = raw(label);
    budget.evidence(span.size()); // control(): hasAttributeWithoutSynchronization(forAttr).
    if (explicitFor) budget.evidence(span.size()); // elementForAttributeInternal(): getAttribute(forAttr).
}
} // namespace NativeAttributeRead
Session::Session(Hooks value) : hooks(std::move(value)) { }
bool Session::thread() const { return hooks.onEngineThread && hooks.onEngineThread() && !retired; }
void Session::invalidate() noexcept
{
    // Lifecycle owner calls this on the engine thread. Wrong-thread/throwing
    // ownership probes cannot race mutation of registry, captures or leases.
    try { if (!hooks.onEngineThread || !hooks.onEngineThread()) return; }
    catch (...) { return; }
    if (invalidationSerial == std::numeric_limits<uint64_t>::max()) retired = true;
    else ++invalidationSerial;
    admission = false;
    activeLease.reset();
    registry.clear();
    publishedControls.clear();
    boundContext.reset();
    // phase is NOT reset: an interrupted action/read retains its busy guard.
}
bool Session::sameDocument(const Context& a, const Context& b) const
{
    return a.version.generation == b.version.generation && a.version.epoch == b.version.epoch
        && a.documentSequence == b.documentSequence && a.resourceEpoch == b.resourceEpoch
        && a.document == b.document && a.frame == b.frame;
}
bool Session::exactCurrent(const Context& expected, uint64_t serial) const
{
    if (!thread() || serial != invalidationSerial || !expected.document || !expected.frame) return false;
    auto actual = contextFromAppDocument(*expected.frame, *expected.document, expected.version.revision);
    return actual && sameDocument(expected, *actual);
}
std::optional<Context> Session::current()
{
    // Capture-internal paths cannot enter this callback. External reentry from
    // focus/input/change handlers fails closed rather than observing half state.
    if (!thread() || phase != Phase::idle || !refreshPaired) return std::nullopt;
    auto actual = refreshPaired();
    if (!actual || !admission || !exactCurrent(*actual, invalidationSerial)) return std::nullopt;
    return actual;
}
Session::PreparedRead::PreparedRead(Session& owner, Context context, N::ReadBudget& budget, bool allocate)
    : session(owner), exact(std::move(context)), serial(owner.invalidationSerial), bounds(budget), allowNew(allocate)
{
    require(valid(), "prepared native context unavailable");
    registry.reserve(owner.registry.size());
    for (const auto& entry : owner.registry) if (entry.node) registry.push_back(entry);
}
bool Session::PreparedRead::valid() const { return session.exactCurrent(exact, serial); }
std::unique_ptr<Session::PreparedRead> Session::beginRead(const Context& context, N::ReadBudget& budget, bool allocate)
{
    require(phase == Phase::capture || phase == Phase::actionCapture || trustedPopupFacade,
        "prepared native read outside owner phase");
    return std::unique_ptr<PreparedRead>(new PreparedRead(*this, context, budget, allocate));
}
std::optional<uint64_t> Session::PreparedRead::idFor(Node& node)
{
    if (!node.isConnected() || &node.document() != exact.document.get()) return std::nullopt;
    for (const auto& entry : registry) if (entry.node.get() == &node) return entry.id;
    if (!allowNew || registry.size() >= maxLiveHandles) return std::nullopt;
    auto id = session.nodeIDs.reserve(); // Burn even if the transaction later fails.
    if (!id) { session.retired = true; session.admission = false; return std::nullopt; }
    registry.push_back({ *id, WeakPtr<Node, WeakPtrImplWithEventTargetData>(node) });
    return id;
}
std::optional<uint64_t> Session::PreparedRead::knownID(Node& node) const
{
    for (const auto& entry : registry) if (entry.node.get() == &node) return entry.id;
    return std::nullopt;
}
std::optional<uint64_t> Session::knownID(Node& node) const
{
    for (const auto& entry : registry) if (entry.node.get() == &node) return entry.id;
    return std::nullopt;
}
RefPtr<Node> Session::resolve(uint64_t id) const
{
    for (const auto& entry : registry) if (entry.id == id) return entry.node.get();
    return nullptr;
}
bool Session::copy(const String& input, std::string& out, N::TextSection section, N::ReadBudget& budget) const
{
    // String/native atom length is inspected before conversion or owned copy.
    budget.chargeString(section, input.length());
    require(scalarText(input), "native string is not scalar/NUL-free UTF16");
    auto bytes = input.utf8();
    out.assign(bytes.data(), bytes.length());
    return true;
}
bool Session::attributes(Element& element, std::vector<AttributeState>& out, N::ReadBudget& budget)
{
    // Every caller has already rejected secure input before accessing attrs.
    // hasAttributes() synchronizes dirty inline CSS through asTextAtom BEFORE
    // any string bound. Use public raw storage plus bounded live scalar CSSOM
    // evidence. Unsupported graphs mark authority incomplete, without serialization.
    require(is<HTMLElement>(element), "non-HTML private attribute baseline unsupported");
    const auto* data = element.elementData();
    if (!data) return true;
    auto liveStyle = inlineStyle(element, budget);
    for (const auto& attribute : element.attributes()) {
        for (const auto* part : { &attribute.prefix(), &attribute.localName(), &attribute.namespaceURI(), &attribute.value() }) {
            budget.evidence(); // components, not just rows, count against 4096.
            budget.chargePrivate(part->length());
            require(scalarText(*part), "non-scalar private attribute");
        }
        out.push_back({ attribute.prefix(), attribute.localName(), attribute.namespaceURI(), attribute.value(), {} });
    }
    bool complete = liveStyle.complete;
    out.push_back({ {}, {}, {}, {}, std::move(liveStyle) });
    return complete;
}
Session::InlineStyleState Session::inlineStyle(Element& element, N::ReadBudget& budget)
{
    InlineStyleState out;
    const auto* data = element.elementData();
    const auto* style = data ? data->inlineStyle() : nullptr;
    if (!style) return out;
    out.present = true;
    out.mutableProperties = style->isMutable();
    out.parserMode = static_cast<unsigned>(style->cssParserMode());
    auto count = style->propertyCount();
    budget.evidence(count); // Atomic before reserve/iteration/allocation.
    out.properties.reserve(count);
    for (unsigned i = 0; i < count; ++i) {
        auto property = style->propertyAt(i);
        // Unknown graphs are never traversed, serialized, hashed or compared.
        // They make this private declaration unavailable without failing safe
        // public body/value reads. Raw style text cannot substitute: a CSP-
        // blocked attribute replacement can leave an older immutable live style.
        if (property.id() == CSSPropertyCustom || !property.value()) { out.complete = false; continue; }
        auto nativeProperty = property.toCSSProperty(); // Ref copy, no deep equality/serialization.
        const auto& metadata = nativeProperty.metadata();
        ScalarStyleProperty saved;
        saved.property = metadata.m_propertyID;
        saved.shorthand = metadata.m_isSetFromShorthand;
        saved.shorthandIndex = metadata.m_indexInShorthandsVector;
        saved.important = metadata.m_important;
        saved.implicit = metadata.m_implicit;
        if (const auto* colorValue = dynamicDowncast<CSSColorValue>(*property.value())) {
            // resolved() only reads an already-resolved variant; never resolves
            // a nested color graph. Packed inline Color is fixed-size evidence.
            auto resolved = colorValue->color().resolved();
            if (!resolved || !resolved->value.isValid()) { out.complete = false; continue; }
            auto packed = resolved->value.tryGetAsPackedInline();
            if (!packed) { out.complete = false; continue; }
            saved.kind = 4;
            saved.identifier = packed->value;
            saved.semanticColor = resolved->value.isSemantic();
            saved.colorFunctionSerialization = resolved->value.usesColorFunctionSerialization();
            out.properties.push_back(saved);
            continue;
        }
        const auto* primitive = dynamicDowncast<CSSPrimitiveValue>(*property.value());
        if (!primitive || primitive->isCalculated() || primitive->isAttr()) { out.complete = false; continue; }
        saved.implicitInitial = primitive->isImplicitInitialValue();
        if (primitive->isValueID()) { saved.kind = 1; saved.identifier = static_cast<unsigned>(primitive->valueID()); }
        else if (primitive->isPropertyID()) { saved.kind = 2; saved.identifier = static_cast<unsigned>(primitive->propertyID()); }
        else {
            auto unit = primitive->primitiveType(); // Only after calc/attr + ID branches.
            bool supported = true;
            switch (unit) {
            case CSSUnitType::CSS_NUMBER: case CSSUnitType::CSS_INTEGER: case CSSUnitType::CSS_PERCENTAGE:
            case CSSUnitType::CSS_EM: case CSSUnitType::CSS_QUIRKY_EM: case CSSUnitType::CSS_EX:
            case CSSUnitType::CSS_CAP: case CSSUnitType::CSS_CH: case CSSUnitType::CSS_IC:
            case CSSUnitType::CSS_RCAP: case CSSUnitType::CSS_RCH: case CSSUnitType::CSS_REM:
            case CSSUnitType::CSS_REX: case CSSUnitType::CSS_RIC: case CSSUnitType::CSS_PX:
            case CSSUnitType::CSS_CM: case CSSUnitType::CSS_MM: case CSSUnitType::CSS_IN:
            case CSSUnitType::CSS_PT: case CSSUnitType::CSS_PC: case CSSUnitType::CSS_Q:
            case CSSUnitType::CSS_DPPX: case CSSUnitType::CSS_X: case CSSUnitType::CSS_DPI: case CSSUnitType::CSS_DPCM:
            case CSSUnitType::CSS_DEG: case CSSUnitType::CSS_RAD: case CSSUnitType::CSS_GRAD: case CSSUnitType::CSS_TURN:
            case CSSUnitType::CSS_MS: case CSSUnitType::CSS_S: case CSSUnitType::CSS_HZ: case CSSUnitType::CSS_KHZ:
            case CSSUnitType::CSS_VW: case CSSUnitType::CSS_VH: case CSSUnitType::CSS_VMIN: case CSSUnitType::CSS_VMAX:
            case CSSUnitType::CSS_VB: case CSSUnitType::CSS_VI: case CSSUnitType::CSS_SVW: case CSSUnitType::CSS_SVH:
            case CSSUnitType::CSS_SVMIN: case CSSUnitType::CSS_SVMAX: case CSSUnitType::CSS_SVB: case CSSUnitType::CSS_SVI:
            case CSSUnitType::CSS_LVW: case CSSUnitType::CSS_LVH: case CSSUnitType::CSS_LVMIN: case CSSUnitType::CSS_LVMAX:
            case CSSUnitType::CSS_LVB: case CSSUnitType::CSS_LVI: case CSSUnitType::CSS_DVW: case CSSUnitType::CSS_DVH:
            case CSSUnitType::CSS_DVMIN: case CSSUnitType::CSS_DVMAX: case CSSUnitType::CSS_DVB: case CSSUnitType::CSS_DVI:
            case CSSUnitType::CSS_FR: case CSSUnitType::CSS_LH: case CSSUnitType::CSS_RLH:
            case CSSUnitType::CSS_CQW: case CSSUnitType::CSS_CQH: case CSSUnitType::CSS_CQI: case CSSUnitType::CSS_CQB:
            case CSSUnitType::CSS_CQMIN: case CSSUnitType::CSS_CQMAX: break;
            default: supported = false; break;
            }
            if (!supported) { out.complete = false; continue; }
            auto number = primitive->valueIfNotCalculated<double>(); // Raw, no clamp hiding infinity.
            if (!number || !std::isfinite(*number)) { out.complete = false; continue; }
            saved.kind = 3;
            saved.unit = static_cast<unsigned>(unit);
            saved.numberBits = std::bit_cast<uint64_t>(*number);
        }
        out.properties.push_back(saved);
    }
    return out;
}
Presentation Session::presentation(Element& element, N::ReadBudget& budget, bool inherited)
{
    // Never call for secure input. Foreign markup is marked before ANY
    // synchronizing attribute/style getter (notably SVG animated href).
    require(is<HTMLElement>(element), "foreign presentation requires unavailable marker");
    // Inherited omission is resolved BEFORE capture.
    Presentation out;
    out.omitted = out.terminalOmit = inherited;
    static const AtomString omitName("data-foundation-tui"_s);
    const auto& hint = NativeAttributeRead::literal(element, omitName, budget);
    budget.chargePrivate(hint.length());
    require(scalarText(hint), "non-scalar omit hint");
    out.terminalOmit = out.terminalOmit || hint == "omit"_s;
    out.omitted = out.terminalOmit;
    // Menu-list options/optgroups normally lack renderers/cached style. The
    // actual native editability accessor resolves their bounded requested style
    // after the owner's rendering checkpoint. Its engine cost is not a claimed
    // constant-time deadline; lifecycle/phase are rechecked before installation.
    auto* style = element.computedStyleForEditability();
    out.styleKnown = style;
    out.renderer = element.renderer();
    if (!style) { out.omitted = true; return out; }
    out.display = static_cast<unsigned>(style->display());
    out.visibility = static_cast<unsigned>(style->visibility());
    out.collapse = static_cast<unsigned>(style->whiteSpaceCollapse());
    out.wrap = static_cast<unsigned>(style->textWrapMode());
    out.inert = style->effectiveInert();
    out.omitted = out.omitted || style->display() == DisplayType::None
        || style->visibility() != Visibility::Visible || out.inert;
    return out;
}
void Session::rawSubtree(PreparedRead& read, ContainerNode& root, std::vector<RawNode>& out,
    bool skipControls, size_t* flattenedUnits, bool applyOmission)
{
    // No flattening getter is called here. Exact raw structure/text is retained,
    // so equal flattened editing text cannot conceal an inner-editor mutation.
    RefPtr<Node> cursor = root.firstChild();
    size_t baseDepth = 0;
    for (RefPtr<Node> ancestor = &root; ancestor; ancestor = ancestor->parentOrShadowHostNode()) {
        read.bounds.visitRaw(++baseDepth);
    }
    size_t depth = 1, flattened = 0;
    while (cursor) {
        read.bounds.visitRaw(baseDepth + depth);
        auto id = read.idFor(*cursor);
        require(id.has_value(), "private native registry capacity");
        RawNode row { cursor, cursor->parentNode(), static_cast<unsigned>(cursor->nodeType()), {}, {}, false, {} };
        bool descend = true;
        auto* input = dynamicDowncast<HTMLInputElement>(*cursor);
        if (input && input->isSecureField()) { row.secure = true; descend = false; }
        else if (skipControls && (is<HTMLInputElement>(*cursor) || is<HTMLTextAreaElement>(*cursor)
            || is<HTMLSelectElement>(*cursor))) descend = false;
        else if (auto* text = dynamicDowncast<Text>(*cursor)) {
            auto length = text->length(); // O(1), before data/String copying.
            read.bounds.chargePrivate(length);
            if (flattenedUnits) {
                require(length <= N::maxFieldUnits - flattened, "flattened native field limit");
                flattened += length;
            }
            require(scalarText(text->data()), "non-scalar private text");
            row.text = text->data();
        } else if (auto* element = dynamicDowncast<Element>(*cursor)) {
            if (!is<HTMLElement>(*element)) {
                // Native identity/type only: no foreign attrs/style/children.
                // Flattening getters cannot run across this incomplete marker.
                row.complete = row.styleComplete = false;
                row.presentation.omitted = true;
                descend = false;
            } else {
                if (applyOmission && !read.graphical) row.presentation = presentation(*element, read.bounds);
                if (applyOmission && !read.graphical && row.presentation.omitted) {
                    row.complete = false;
                    descend = false;
                } else row.styleComplete = attributes(*element, row.attributes, read.bounds);
            }
            if (flattenedUnits && is<HTMLBRElement>(*element)) {
                require(flattened < N::maxFieldUnits, "flattened BR limit");
                ++flattened;
            }
            // Public label literal text excludes executable/inert containers.
            if (skipControls && (element->localName() == "script"_s || element->localName() == "style"_s
                || element->localName() == "template"_s)) descend = false;
        }
        out.push_back(std::move(row));
        if (descend && cursor->firstChild()) { cursor = cursor->firstChild(); ++depth; continue; }
        while (cursor && cursor.get() != &root && !cursor->nextSibling()) { cursor = cursor->parentNode(); --depth; }
        if (!cursor || cursor.get() == &root) break;
        cursor = cursor->nextSibling();
    }
    if (flattenedUnits) *flattenedUnits = flattened;
}
bool Session::subtreeComplete(const std::vector<RawNode>& rows)
{
    return std::all_of(rows.begin(), rows.end(), [](const auto& row) { return row.complete; });
}
bool Session::subtreeStyleComplete(const std::vector<RawNode>& rows)
{
    return std::all_of(rows.begin(), rows.end(), [](const auto& row) { return row.styleComplete; });
}
Session::Capture Session::PreparedRead::capture(HTMLFormControlElement& control, const Presentation& decision)
{
    auto& owner = session;
    require(valid() && control.isConnected() && &control.document() == exact.document.get(), "foreign control");
    bounds.control();
    Capture result;
    result.node = &control;
    auto id = idFor(control);
    require(id.has_value(), "native control ID limit");
    auto& out = result.observed;
    out.node = *id;
    result.presentation = decision;
    // Absolute first branch, before control.type(), flags/attrs/name/label/value,
    // selection, text length, innerTextElement or any descendant traversal.
    auto* input = dynamicDowncast<HTMLInputElement>(control);
    if (input && input->isSecureField()) {
        out.kind = F::FormKind::secure_readonly;
        out.omitted = true; // Safe conservative marker, with no hint/style read.
        result.focused = control.document().focusedElement(); // Nonsecret pointer only.
        out.focused = result.focused.get() == &control;
        out.disabled = control.isDisabledFormControl();
        owner.copy(control.type(), out.native_type, N::TextSection::forms, bounds);
        out.complete = true;
        result.privateComplete = true;
        return result;
    }
    owner.copy(control.type(), out.native_type, N::TextSection::forms, bounds);
    out.omitted = decision.omitted;
    if (decision.omitted) {
        out.kind = F::FormKind::unsupported; // monostate is honest for uncaptured values.
        out.complete = true;
        result.privateComplete = true;
        return result;
    }
    result.focused = control.document().focusedElement();
    out.focused = result.focused.get() == &control;
    out.disabled = control.isDisabledFormControl();
    out.read_only = control.isReadOnly();
    out.focusable = control.isFocusable();
    result.editorFlags = owner.editorFlags(exact);
    result.styleComplete = owner.attributes(control, result.attributes, bounds);
    const auto& nativeID = NativeAttributeRead::nativeID(control, bounds);
    bounds.chargePrivate(nativeID.length());
    require(scalarText(nativeID), "non-scalar native control ID");
    result.nativeID = nativeID;
    owner.rawSubtree(*this, control, result.lightSubtree, false);
    result.styleComplete = result.styleComplete && owner.subtreeStyleComplete(result.lightSubtree);
    // Bounded native aria-label fallback. Associated native labels are attached
    // later from the SAME whole-document prepared read, without recapturing.
    static const AtomString labelName("aria-label"_s);
    owner.copy(NativeAttributeRead::literal(control, labelName, bounds), out.label, N::TextSection::forms, bounds);
    F::FormCapabilities supported = 0;
    bool complete = result.styleComplete && owner.subtreeComplete(result.lightSubtree);
    if (input && input->isCheckbox()) {
        out.kind = F::FormKind::checkbox;
        out.state = F::FormCheckState { input->checked(), input->indeterminate() };
        require(bounds.remaining(N::TextSection::private_capture) >= N::maxFieldUnits, "checkbox evidence capacity");
        auto value = input->value(); // value attribute was bounded before sanitization.
        bounds.chargePrivate(value->length());
        require(scalarText(value.get()), "checkbox private value");
        result.nativeValue = value.get();
        supported = F::form_capability(F::FormCapability::set_checked);
    } else if (auto* select = dynamicDowncast<HTMLSelectElement>(control)) {
        out.kind = select->multiple() ? F::FormKind::select_many : F::FormKind::select_one;
        result.selectSize = select->size();
        F::FormSelectState state { select->multiple(), select->usesMenuList(), {} };
        // length()/item() may build listItems() by traversing ALL optgroups,
        // including TUI-omitted ones. Bound that native search/allocation input
        // without reading attrs/text/values below exclusion before either call.
        size_t selectDepth = 0, preflightOptions = 0;
        for (RefPtr<Node> ancestor = select; ancestor; ancestor = ancestor->parentOrShadowHostNode()) bounds.visitRaw(++selectDepth);
        RefPtr<Node> cursor = select->firstChild();
        size_t depth = 1;
        bool collectionBounded = true;
        while (cursor) {
            bounds.visitRaw(selectDepth + depth);
            auto* nestedInput = dynamicDowncast<HTMLInputElement>(*cursor);
            if ((nestedInput && nestedInput->isSecureField())
                || (is<Element>(*cursor) && !is<HTMLElement>(*cursor))) {
                // No descent or field read across an unprebound native search
                // space. Keep the select public but never call lazy listItems.
                collectionBounded = false;
                break;
            }
            if (is<HTMLOptionElement>(*cursor)) { bounds.option(); ++preflightOptions; }
            if (cursor->firstChild()) { cursor = cursor->firstChild(); ++depth; continue; }
            while (cursor && cursor.get() != select && !cursor->nextSibling()) { cursor = cursor->parentNode(); --depth; }
            if (!cursor || cursor.get() == select) break;
            cursor = cursor->nextSibling();
        }
        if (!collectionBounded) complete = false;
        else {
            auto count = select->length();
            require(count <= preflightOptions && count <= N::maxOptions, "native select count changed after preflight");
            for (unsigned i = 0; i < count; ++i) {
                bounds.evidence();
                RefPtr<HTMLOptionElement> option = select->item(i);
                require(option && option->ownerSelectElement() == select, "native option membership");
                OptionState exactOption;
                exactOption.node = option;
                // Ancestor hints/style are captured before getter/read authority.
                std::vector<RefPtr<Element>> ancestors;
                for (RefPtr<Element> ancestor = option; ancestor && ancestor.get() != select; ancestor = ancestor->parentElement()) {
                    bounds.checkDepth(ancestors.size() + 1);
                    bounds.evidence();
                    ancestors.push_back(ancestor);
                }
                bool inherited = false;
                for (auto it = ancestors.rbegin(); it != ancestors.rend(); ++it) {
                    auto sampled = owner.presentation(**it, bounds, inherited);
                    if (graphical) sampled.omitted = inherited || !sampled.styleKnown || sampled.inert
                        || sampled.display == static_cast<unsigned>(DisplayType::None)
                        || sampled.visibility != static_cast<unsigned>(Visibility::Visible);
                    inherited = sampled.omitted;
                    if (it + 1 == ancestors.rend()) exactOption.presentation = sampled;
                }
                F::FormOption row;
                auto optionID = idFor(*option);
                require(optionID.has_value(), "native option ID limit");
                row.node = *optionID;
                row.selected = option->selected();
                row.disabled = option->isDisabledFormControl();
                row.omitted = exactOption.presentation.omitted;
                if (row.omitted) {
                    // Excluded option: no attributes, text, label or submitted value
                    // are captured. This intentional baseline gap disables the WHOLE
                    // select descriptor, never a partially actionable live menu.
                    complete = false;
                    result.options.push_back(std::move(exactOption));
                    state.options.push_back(std::move(row));
                    continue;
                }
                bool optionStyle = owner.attributes(*option, exactOption.attributes, bounds);
                size_t flattened = 0;
                owner.rawSubtree(*this, *option, exactOption.subtree, false, &flattened);
                optionStyle = optionStyle && owner.subtreeStyleComplete(exactOption.subtree);
                result.styleComplete = result.styleComplete && optionStyle;
                complete = complete && optionStyle;
                if (!owner.subtreeComplete(exactOption.subtree)
                    || std::any_of(exactOption.subtree.begin(), exactOption.subtree.end(), [](const auto& row) { return row.secure; })) {
                    // No displayLabel/value call after a pruned preflight. Empty
                    // label/value is explicit unavailable data on a cap-free owner.
                    complete = false;
                    result.options.push_back(std::move(exactOption));
                    state.options.push_back(std::move(row));
                    continue;
                }
                // Both potentially allocating option getters are prebound by ALL
                // root attrs and raw descendants. Reserve worst field space first.
                require(bounds.remaining(N::TextSection::forms) >= N::maxFieldUnits
                    && bounds.remaining(N::TextSection::private_capture) >= N::maxFieldUnits,
                    "option getter preallocation capacity");
                owner.copy(option->displayLabel(), row.label, N::TextSection::forms, bounds);
                auto submitted = option->value();
                bounds.chargePrivate(submitted.length());
                require(scalarText(submitted), "native submitted option value");
                exactOption.submittedValue = std::move(submitted);
                result.options.push_back(std::move(exactOption));
                state.options.push_back(std::move(row));
            }
        } // Exact native collection was bounded before length()/item().
        out.state = std::move(state);
        if (!select->multiple() && owner.hooks.openNativeUserPopup)
            supported = F::form_capability(F::FormCapability::open_popup);
        else if (select->multiple() && !select->usesMenuList())
            supported = F::form_capability(F::FormCapability::set_option);
    } else if (auto* text = dynamicDowncast<HTMLTextFormControlElement>(control); text && text->isTextField()) {
        bool known = is<HTMLTextAreaElement>(control) || (input && (input->isText() || input->isNumberField()
            || input->isSearchField() || input->isEmailField() || input->isTelephoneField() || input->isURLField()));
        if (known) {
            out.kind = is<HTMLTextAreaElement>(control) ? F::FormKind::textarea
                : input->isNumberField() ? F::FormKind::number : F::FormKind::text;
            RefPtr inner = text->innerTextElement(); // Existing subtree only, no creation.
            require(!!inner, "native inner editor unavailable");
            result.innerRoot = inner;
            bool innerStyle = owner.attributes(*inner, result.innerAttributes, bounds);
            size_t flattened = 0;
            owner.rawSubtree(*this, *inner, result.innerEditor, false, &flattened, false);
            result.styleComplete = result.styleComplete && innerStyle && owner.subtreeStyleComplete(result.innerEditor);
            complete = complete && result.styleComplete;
            if (!owner.subtreeComplete(result.innerEditor)
                || std::any_of(result.innerEditor.begin(), result.innerEditor.end(), [](const auto& row) { return row.secure; })) {
                complete = false;
                out.state = F::FormTextState {}; // Explicit unavailable, no guessed live value.
            } else {
                require(bounds.remaining(N::TextSection::forms) >= 2 * N::maxFieldUnits
                    && bounds.remaining(N::TextSection::private_capture) >= 2 * N::maxFieldUnits,
                    "text getter preallocation capacity");
                // Textarea value can flatten; input value can sanitize valueAttr.
                // The relevant native subtree and attrs are now already bounded.
                auto value = text->value();
                bounds.chargePrivate(value->length());
                require(scalarText(value.get()), "native canonical value");
                result.nativeValue = value.get();
                auto editing = text->innerTextValue();
                bounds.chargePrivate(editing.length());
                require(scalarText(editing), "native editing value");
                result.editingValue = editing;
                F::FormTextState state;
                owner.copy(result.nativeValue, state.value, N::TextSection::forms, bounds);
                owner.copy(result.editingValue, state.editing_text, N::TextSection::forms, bounds);
                F::FormControlRange range { text->selectionStart(), text->selectionEnd(), nativeDirection(text->selectionDirection()) };
                (void)F::form_byte_selection(state.editing_text, range);
                state.selection = range;
                out.state = std::move(state);
                supported = F::form_capability(F::FormCapability::replace_text);
            } // Flattening getters require complete native editor evidence.
        }
    }
    out.complete = result.privateComplete = complete;
    if (!complete) if (auto* text = std::get_if<F::FormTextState>(&out.state)) text->selection.reset();
    if (complete && supported && !out.disabled && !out.read_only && out.focusable && decision.renderer)
        out.capabilities = supported | F::form_capability(F::FormCapability::finish);
    require(valid(), "native context changed while reading control");
    return result;
}
bool Session::sameCapture(const Capture& a, const Capture& b) const
{
    return a.privateComplete == b.privateComplete && a.styleComplete == b.styleComplete && a.node == b.node && a.innerRoot == b.innerRoot
        && a.focused == b.focused && a.presentation == b.presentation && a.attributes == b.attributes
        && a.options == b.options && a.lightSubtree == b.lightSubtree && a.innerEditor == b.innerEditor
        && a.innerAttributes == b.innerAttributes
        && a.labels == b.labels && a.nativeValue == b.nativeValue && a.editingValue == b.editingValue && a.nativeID == b.nativeID
        && a.selectSize == b.selectSize && a.editorFlags == b.editorFlags
        && F::form_control_state_matches(a.observed, b.observed);
}
bool Session::matchesCommitted(const PreparedRead& read) const
{
    if (!boundContext || !sameDocument(*boundContext, read.exact) || publishedControls.size() != read.controls.size()) return false;
    for (size_t i = 0; i < read.controls.size(); ++i)
        if (!sameCapture(publishedControls[i], read.controls[i])) return false;
    return true;
}
const Session::Capture* Session::captured(uint64_t id) const
{
    for (const auto& capture : publishedControls) if (capture.observed.node == id) return &capture;
    return nullptr;
}
bool Session::actionable(const Capture& capture) const
{
    return capture.privateComplete && capture.observed.capabilities && capture.node && capture.node->isConnected()
        && capture.focused == capture.node && capture.observed.focused && capture.presentation.renderer
        && !capture.observed.omitted && !capture.observed.disabled && !capture.observed.read_only;
}
uint32_t Session::editorFlags(const Context& context) const
{
    require(static_cast<bool>(hooks.inputMethodEnabled), "authoritative input-method state accessor missing");
    auto enabled = hooks.inputMethodEnabled();
    require(enabled.has_value(), "authoritative input-method state unavailable");
    auto& editor = context.frame->editor();
    return (editor.canEdit() ? 1U : 0U) | (editor.hasComposition() ? 2U : 0U)
        | (editor.canUndo() ? 4U : 0U) | (editor.canRedo() ? 8U : 0U) | (*enabled ? 16U : 0U);
}
bool Session::leaseWillSurvive(const PreparedRead& read) const
{
    if (!activeLease || !hooks.foreground || !hooks.foreground() || !sameDocument(activeLease->context, read.exact)) return false;
    for (const auto& value : read.controls)
        if (value.observed.node == activeLease->wire.node)
            return actionable(value) && sameCapture(activeLease->baseline, value);
    return false;
}
Session::PreparedForms Session::prepareCommit(PreparedRead&& read, F::FormVersion version,
    std::optional<uint64_t> issueLease, bool noActions)
{
    require(read.valid(), "native context changed before preparation");
    PreparedForms out;
    out.context = read.exact;
    out.context.version = version;
    if (!noActions && !issueLease && leaseWillSurvive(read)) out.lease = activeLease;
    if (issueLease && !noActions) {
        auto found = std::find_if(read.controls.begin(), read.controls.end(), [&](const auto& v) { return v.observed.node == *issueLease; });
        require(found != read.controls.end() && actionable(*found) && hooks.foreground && hooks.foreground(), "new lease readback focus");
        auto next = leaseIDs.reserve();
        if (!next) { retired = true; admission = false; }
        require(next.has_value(), "native lease counter retired");
        out.lease = Lease { { version, *issueLease, *next }, out.context, *found };
    }
    for (auto& capture : read.controls) {
        capture.observed.lease.reset();
        if (noActions) capture.observed.capabilities = 0;
        if (out.lease && capture.observed.node == out.lease->wire.node) capture.observed.lease = out.lease->wire;
    }
    out.registry = std::move(read.registry);
    out.controls = std::move(read.controls);
    return out;
}
void Session::commit(PreparedForms&& prepared) noexcept
{
    registry.swap(prepared.registry);
    publishedControls.swap(prepared.controls);
    activeLease.swap(prepared.lease);
    std::optional<Context> next(std::move(prepared.context));
    boundContext.swap(next); // No allocation/native callback in either commit.
    admission = true;
}
} // namespace BIB::FormsV2Combined
