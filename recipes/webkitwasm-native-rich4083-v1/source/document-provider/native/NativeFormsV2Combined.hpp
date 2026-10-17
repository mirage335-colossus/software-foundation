// NEW successor overlay: source candidate, not compiled/linked/runtime qualified.
#pragma once
#include "../portable/NativeDocumentV2Types.hpp"
#include <WebCore/Document.h>
#include <WebCore/HTMLFormControlElement.h>
#include <WebCore/HTMLOptionElement.h>
#include <WebCore/HTMLSelectElement.h>
#include <WebCore/LocalFrame.h>
#include <WebCore/Node.h>
#include <wtf/WeakPtr.h>
#include <functional>
#include <memory>
#include <optional>
#include <vector>

namespace BIB::FormsV2Combined {
namespace F = foundation::appended;
namespace N = BIB::NativeDocumentV2;
// Native-private bounded reads. Callers decide omission first; all helpers reject
// secure inputs BEFORE touching raw storage. No QName text/synchronization.
namespace NativeAttributeRead {
const AtomString& literal(WebCore::Element&, const AtomString&, N::ReadBudget&);
const AtomString& qualified(WebCore::Element&, const WebCore::QualifiedName&, N::ReadBudget&);
const AtomString& nativeID(WebCore::Element&, N::ReadBudget&, bool reserveNativeRepeat = false);
bool authorOmittedForAssociation(WebCore::Element&, N::ReadBudget&);
void prechargeNativeForScans(WebCore::Element&, N::ReadBudget&, bool explicitFor);
}
class Publisher;
class SharedGuard;
struct Context {
    F::FormVersion version;
    uint64_t documentSequence { 0 }, resourceEpoch { 0 };
    RefPtr<WebCore::Document> document;
    RefPtr<WebCore::LocalFrame> frame;
};
// All callbacks are native composition callbacks, never page-callable objects.
struct Hooks {
    std::function<bool()> onEngineThread;
    std::function<bool()> foreground;
    // Actual embedding EditorClient state, not the wrapping prototype counter.
    // nullopt/missing means unknown and rejects a current v2 publication.
    std::function<std::optional<bool>()> inputMethodEnabled;
    // Called only with an ephemeral trusted facade over THIS Session. Ordinary
    // external facades remain busy during the action, including author reentry.
    std::function<bool(WebCore::HTMLSelectElement&, SharedGuard&)> openNativeUserPopup;
};
struct Presentation {
    bool omitted { false }, terminalOmit { false }, styleKnown { false };
    unsigned display { 0 }, visibility { 0 }, collapse { 0 }, wrap { 0 };
    bool inert { false }, renderer { false };
    bool operator==(const Presentation&) const = default;
};

class Session final {
    friend class Publisher;
    friend class SharedGuard;
public:
    explicit Session(Hooks);
    ~Session() = default;
    Session(const Session&) = delete;
    Session& operator=(const Session&) = delete;
    // Revokes admission synchronously. Historical publication bytes belong to
    // Publisher and remain immutable. No node/lease high-water mark is reset.
    void invalidate() noexcept;
    struct ScalarStyleProperty {
        unsigned property { 0 }, shorthandIndex { 0 }, kind { 0 }, unit { 0 }, identifier { 0 };
        uint64_t numberBits { 0 };
        bool shorthand { false }, important { false }, implicit { false }, implicitInitial { false };
        bool semanticColor { false }, colorFunctionSerialization { false };
        bool operator==(const ScalarStyleProperty&) const = default;
    };
    struct InlineStyleState {
        unsigned parserMode { 0 };
        bool present { false }, mutableProperties { false }, complete { true };
        std::vector<ScalarStyleProperty> properties;
        bool operator==(const InlineStyleState&) const = default;
    };
    struct AttributeState {
        String prefix, name, nameSpace, value;
        // Explicit PRIVATE evidence marker (all four strings empty), never a
        // synthetic DOM attr/public metadata row. Raw attrs remain separate.
        std::optional<InlineStyleState> inlineStyle;
        bool operator==(const AttributeState&) const = default;
    };
    struct RawNode {
        RefPtr<WebCore::Node> node, parent;
        unsigned kind { 0 };
        String text;
        std::vector<AttributeState> attributes;
        bool secure { false };
        Presentation presentation;
        bool complete { true }, styleComplete { true };
        bool operator==(const RawNode&) const = default;
    };
    struct OptionState {
        RefPtr<WebCore::HTMLOptionElement> node;
        String submittedValue;
        std::vector<AttributeState> attributes;
        std::vector<RawNode> subtree;
        Presentation presentation;
        bool operator==(const OptionState&) const = default;
    };
    struct LabelState {
        RefPtr<WebCore::HTMLElement> node, target;
        std::vector<AttributeState> attributes;
        std::vector<RawNode> subtree;
        String text;
        bool associationComplete { false };
        bool privateComplete { true }, styleComplete { true };
        bool onlyMatchingID { false };
        String forAttribute;
        bool operator==(const LabelState&) const = default;
    };
    struct Capture {
        F::FormControl observed;
        RefPtr<WebCore::HTMLFormControlElement> node;
        RefPtr<WebCore::Node> innerRoot;
        RefPtr<WebCore::Element> focused;
        Presentation presentation;
        std::vector<AttributeState> attributes;
        std::vector<OptionState> options;
        std::vector<RawNode> lightSubtree, innerEditor;
        std::vector<AttributeState> innerAttributes;
        std::vector<LabelState> labels;
        String nativeValue, editingValue, nativeID;
        unsigned selectSize { 0 };
        uint32_t editorFlags { 0 };
        bool privateComplete { false }, styleComplete { true };
    };
    // Phase-scoped staged access to THIS registry. Construction is private;
    // neither current() nor a refresh hook is called by any prepared method.
    class PreparedRead final {
        friend class Session;
        friend class Publisher;
        friend class SharedGuard;
    public:
        std::optional<uint64_t> idFor(WebCore::Node&);
        std::optional<uint64_t> knownID(WebCore::Node&) const;
        Capture capture(WebCore::HTMLFormControlElement&, const Presentation&);
        bool valid() const;
        N::ReadBudget& budget() noexcept { return bounds; }
        const Context& context() const noexcept { return exact; }
    private:
        PreparedRead(Session&, Context, N::ReadBudget&, bool allowNew);
        Session& session;
        Context exact;
        uint64_t serial;
        N::ReadBudget& bounds;
        bool allowNew;
        bool graphical { false };
        struct Entry { uint64_t id; WeakPtr<WebCore::Node, WebCore::WeakPtrImplWithEventTargetData> node; };
        std::vector<Entry> registry;
        std::vector<Capture> controls;
    };

private:
    struct Lease { F::FormLease wire; Context context; Capture baseline; };
    struct PreparedForms {
        Context context;
        std::vector<PreparedRead::Entry> registry;
        std::vector<Capture> controls;
        std::optional<Lease> lease;
    };
    enum class Phase { idle, capture, action, actionCapture };
    std::optional<Context> current(); // external refresh only; never capture-internal
    bool thread() const;
    bool exactCurrent(const Context&, uint64_t serial) const;
    bool sameDocument(const Context&, const Context&) const;
    std::unique_ptr<PreparedRead> beginRead(const Context&, N::ReadBudget&, bool allowNew = true);
    PreparedForms prepareCommit(PreparedRead&&, F::FormVersion, std::optional<uint64_t> issueLease, bool noActions);
    void commit(PreparedForms&&) noexcept;
    bool matchesCommitted(const PreparedRead&) const;
    bool leaseWillSurvive(const PreparedRead&) const;
    const Capture* captured(uint64_t) const;
    std::optional<uint64_t> knownID(WebCore::Node&) const;
    RefPtr<WebCore::Node> resolve(uint64_t) const;
    bool sameCapture(const Capture&, const Capture&) const;
    bool actionable(const Capture&) const;
    uint32_t editorFlags(const Context&) const;
    bool attributes(WebCore::Element&, std::vector<AttributeState>&, N::ReadBudget&);
    InlineStyleState inlineStyle(WebCore::Element&, N::ReadBudget&);
    static bool subtreeComplete(const std::vector<RawNode>&);
    static bool subtreeStyleComplete(const std::vector<RawNode>&);
    void rawSubtree(PreparedRead&, WebCore::ContainerNode&, std::vector<RawNode>&,
        bool skipControls, size_t* flattenedUnits = nullptr, bool applyOmission = true);
    Presentation presentation(WebCore::Element&, N::ReadBudget&, bool inheritedOmit = false);
    bool copy(const String&, std::string&, N::TextSection, N::ReadBudget&) const;
    void attachLabels(PreparedRead&, const std::vector<LabelState>&, uint32_t& degradation);

    Hooks hooks;
    std::function<std::optional<Context>()> refreshPaired; // installed by ONE Publisher
    std::function<std::optional<Capture>(WebCore::HTMLFormControlElement&, bool)> captureForFacade;
    std::optional<Context> boundContext;
    std::vector<PreparedRead::Entry> registry;
    std::vector<Capture> publishedControls;
    std::optional<Lease> activeLease;
    N::Counter nodeIDs, leaseIDs;
    uint64_t invalidationSerial { 0 };
    bool retired { false }, admission { false };
    Phase phase { Phase::idle };
    const SharedGuard* trustedPopupFacade { nullptr };
    static constexpr size_t maxLiveHandles = 65536;
};
} // namespace BIB::FormsV2Combined
