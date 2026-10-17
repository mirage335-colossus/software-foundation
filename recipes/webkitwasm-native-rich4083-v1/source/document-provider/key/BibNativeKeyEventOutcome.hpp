// SPDX-License-Identifier: CC0-1.0
#pragma once

#include <cstdint>
#include <type_traits>

namespace WebCore {

class Element;
class EventHandler;
class PlatformKeyboardEvent;

// Private dispatch-point scalars, never a post-lock editor authority/token.
// No Event, Node, Frame or owner pointer escapes in either output record.
struct KeyEventDispatchOutcome {
    enum class Flag : std::uint8_t { Unobserved, No, Yes };
    enum class Route : std::uint8_t { NotReached, DOMDispatch, EditorOnly, LegacyTargetHelper };
    enum class Frame : std::uint8_t { Unobserved, SameFrameAndDocument, FocusedFrameMismatch, DocumentReplaced, PageUnavailable };
    enum class Target : std::uint8_t { Unobserved, OriginalTarget, SameFrameRetarget, Unavailable };
    enum class Focus : std::uint8_t { Unobserved, Unchanged, SameFrameRetarget, Cleared };
    enum class Exit : std::uint8_t {
        Incomplete, FullscreenExit, FullscreenRejected, NonLocalMainFrame,
        PanScrollSwallowed, NoInitialTarget, StandaloneHelperReturned,
        RawKeyDownReturned, InputMethodHandled, KeyDownReturned,
        NoTargetAfterKeyDown, EmptyKeyPress, EditorOnlyKeyPress, KeyPressReturned
    };
    struct Stage {
        Route route { Route::NotReached };
        Flag defaultPrevented { Flag::Unobserved };
        Flag defaultHandled { Flag::Unobserved };
        Frame frame { Frame::Unobserved };
        Target target { Target::Unobserved };
        Focus focus { Focus::Unobserved };
    };
    Stage keydown, keypress, standalone;
    Exit exit { Exit::Incomplete };
    bool accessKeyMatched { false };
    bool inputMethodHandled { false };
    Flag requiresKeyPressEvent { Flag::Unobserved };
    bool targetRefetched { false };
    Flag refetchedTargetChanged { Flag::Unobserved };
    bool normalHandled { false };
    bool complete { false }; // Set only after the existing outer keyEvent work.
};

struct KeyEventDispatchObservation {
    bool defaultPrevented { false };
    bool defaultHandled { false };
    bool complete { false };
};

namespace BibKeyObservationDetail {

// Only live synchronous stack scopes are linked. This private storage performs
// no native read, allocation or callback. Each Value is a fixed scalar record.
template<class Owner, class Event, class Value>
class ScopedObservation final {
    static_assert(std::is_trivially_copyable_v<Value>);
    static_assert(std::is_nothrow_default_constructible_v<Value>);
public:
    class Invocation;
    class Request final {
    public:
        Request(Owner& owner, const Event& event, Value& value) noexcept
            : m_owner(&owner), m_event(&event), m_value(&value), m_previous(s_request)
        {
            value = { };
            s_request = this;
        }
        ~Request() { s_request = m_previous; }
        Request(const Request&) = delete;
        Request& operator=(const Request&) = delete;
        Request(Request&&) = delete;
        Request& operator=(Request&&) = delete;
    private:
        friend class Invocation;
        Owner* m_owner;
        const Event* m_event;
        Value* m_value;
        Request* m_previous;
        bool m_claimed { false };
    };

    class Invocation final {
    public:
        Invocation(Owner& owner, const Event& event) noexcept
            : m_owner(&owner), m_event(&event), m_previous(s_invocation)
        {
            if (auto* request = s_request; request && !request->m_claimed
                && request->m_owner == &owner && request->m_event == &event) {
                request->m_claimed = true;
                m_value = request->m_value;
            }
            // Push even an unobserved call. Nested ordinary dispatch must not
            // see the outer invocation, even for the same owner/event address.
            s_invocation = this;
        }
        ~Invocation() { s_invocation = m_previous; }
        Invocation(const Invocation&) = delete;
        Invocation& operator=(const Invocation&) = delete;
        Invocation(Invocation&&) = delete;
        Invocation& operator=(Invocation&&) = delete;
        Value* value() const noexcept { return m_value; }
    private:
        friend class ScopedObservation;
        Owner* m_owner;
        const Event* m_event;
        Value* m_value { nullptr };
        Invocation* m_previous;
    };

    static Value* current(Owner& owner, const Event& event) noexcept
    {
        auto* invocation = s_invocation;
        return invocation && invocation->m_owner == &owner
            && invocation->m_event == &event ? invocation->m_value : nullptr;
    }
private:
    inline static thread_local Request* s_request { nullptr };
    inline static thread_local Invocation* s_invocation { nullptr };
};

using HandlerObservation = ScopedObservation<EventHandler, PlatformKeyboardEvent, KeyEventDispatchOutcome>;
using ElementObservation = ScopedObservation<Element, PlatformKeyboardEvent, KeyEventDispatchObservation>;

} // namespace BibKeyObservationDetail

// Defined in the existing owning CPPs. Each wraps exactly one unchanged public
// member call. No class definition or old member declaration is changed.
bool dispatchKeyEventWithNativeOutcome(EventHandler&, const PlatformKeyboardEvent&, KeyEventDispatchOutcome&);
bool dispatchElementKeyEventWithNativeObservation(Element&, const PlatformKeyboardEvent&, KeyEventDispatchObservation&);

} // namespace WebCore
