// NEW successor facade: one Session, no second registry/DOM/select policy.
#pragma once
#include "NativeFormsV2Combined.hpp"
#include <WebCore/ContainerNodeInlines.h>
#include <WebCore/HTMLInputElement.h>
#include <WebCore/HTMLElement.h>
#include <WebCore/RenderStyle.h>

namespace BIB::FormsV2Combined {
enum class Audience { graphical, terminal };
class SharedGuard final {
    friend class Publisher;
public:
    using Capture = Session::Capture;
    using AttributeState = Session::AttributeState;
    using RawNode = Session::RawNode;
    using ReadBudget = N::ReadBudget;
    struct RowInput {
        uint64_t node { 0 };
        RefPtr<WebCore::HTMLElement> element;
        std::vector<AttributeState> attributes;
        std::vector<RawNode> subtree;
        bool omitted { false };
        bool operator==(const RowInput&) const = default;
    };
    explicit SharedGuard(Session& owner) : session(owner) { }
    ~SharedGuard() { if (session.trustedPopupFacade == this) session.trustedPopupFacade = nullptr; }
    SharedGuard(const SharedGuard&) = delete;
    SharedGuard& operator=(const SharedGuard&) = delete;
    std::optional<Context> current()
    {
        if (!session.thread()) return std::nullopt;
        if (!trusted) return session.current(); // Whole paired refresh, external idle only.
        if (session.trustedPopupFacade != this || session.phase != Session::Phase::action
            || !session.exactCurrent(*trusted, serial)) return std::nullopt;
        return trusted; // Private action-scoped access, never the refresh hook.
    }
    bool sameDocument(const Context& a, const Context& b) const { return session.sameDocument(a, b); }
    uint64_t lifetimeSerial() const noexcept { return session.invalidationSerial; }
    bool isCurrent(const Context& expected, uint64_t expectedSerial)
    {
        auto actual = current();
        return actual && expectedSerial == session.invalidationSerial && sameDocument(expected, *actual);
    }
    std::optional<uint64_t> idFor(WebCore::Node& node)
    {
        auto context = current();
        if (!context || !node.isConnected() || &node.document() != context->document.get()) return std::nullopt;
        return session.knownID(node); // No eager registry mutation outside paired commit.
    }
    RefPtr<WebCore::Node> resolve(uint64_t id)
    {
        auto context = current();
        auto node = session.resolve(id);
        if (!context || !node || !node->isConnected() || &node->document() != context->document.get()) return nullptr;
        return node;
    }
    std::optional<Capture> capture(WebCore::HTMLFormControlElement& control, Audience audience = Audience::graphical)
    {
        auto context = current();
        auto before = session.invalidationSerial;
        if (!context) return std::nullopt;
        // External callers receive the already FULL-refreshed SAME capture;
        // there is no recapture of one control after whole publication commit.
        if (!trusted && audience == Audience::terminal) {
            auto id = session.knownID(control);
            auto* captured = id ? session.captured(*id) : nullptr;
            if (!captured || !session.exactCurrent(*context, before)) return std::nullopt;
            return *captured;
        }
        if (!session.captureForFacade) return std::nullopt;
        // Publisher owns the staged extra-ID/full-TUI paired transaction. This
        // facade cannot eagerly mutate registry state or borrow stale labels.
        return session.captureForFacade(control, audience == Audience::graphical);
    }

    bool same(const Capture& a, const Capture& b) const { return session.sameCapture(a, b); }
    bool nativeSelectEligible(const Capture& captured, Audience audience, bool requireFocused = true) const
    {
        auto* select = captured.node ? dynamicDowncast<WebCore::HTMLSelectElement>(*captured.node) : nullptr;
        const auto& observed = captured.observed;
        if (!captured.privateComplete || !select || observed.kind != F::FormKind::select_one
            || select->multiple() || !select->isConnected() || !select->renderer()
            || observed.disabled || observed.read_only || !observed.complete || !observed.focusable
            || (requireFocused && (!observed.focused || captured.focused.get() != select))) return false;
        return audience == Audience::graphical || !captured.presentation.terminalOmit;
    }
    ReadBudget makeReadBudget() const { return {}; }
    F::FormLimits limits() const noexcept { return {}; }
    bool copyString(const String& value, std::string& output, ReadBudget& budget)
    {
        return session.copy(value, output, N::TextSection::private_capture, budget);
    }
    std::optional<RowInput> rowInput(WebCore::HTMLElement& element, ReadBudget& budget)
    {
        auto context = current();
        if (!context) return std::nullopt;
        auto before = session.invalidationSerial;
        if (auto* input = dynamicDowncast<WebCore::HTMLInputElement>(element); input && input->isSecureField()) return std::nullopt;
        try {
            auto phase = session.phase;
            struct Exit { Session::Phase& out; Session::Phase value; ~Exit() { out = value; } } exit { session.phase, phase };
            session.phase = trusted ? Session::Phase::actionCapture : Session::Phase::capture;
            auto read = session.beginRead(*context, budget, false);
            auto id = read->idFor(element);
            if (!id) return std::nullopt;
            budget.option(); budget.evidence();
            RowInput result;
            result.node = *id; result.element = &element;
            auto decision = session.presentation(element, budget);
            result.omitted = decision.omitted; // Presentation only; GUI policy may ignore TUI hint.
            // GUI row evidence ignores terminal hints, retaining native row data.
            bool complete = session.attributes(element, result.attributes, budget);
            session.rawSubtree(*read, element, result.subtree, false, nullptr, false);
            if (!complete || !session.subtreeComplete(result.subtree) || !session.subtreeStyleComplete(result.subtree)) return std::nullopt;
            if (!read->valid() || before != session.invalidationSerial) return std::nullopt;
            return result;
        } catch (...) { return std::nullopt; }
    }
private:
    SharedGuard(Session& owner, const Context& context) : session(owner), trusted(context), serial(owner.invalidationSerial)
    {
        session.trustedPopupFacade = this;
    }
    Session& session;
    std::optional<Context> trusted;
    uint64_t serial { 0 };
};
} // namespace BIB::FormsV2Combined
