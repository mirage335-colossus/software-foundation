// SPDX-License-Identifier: CC0-1.0
// Private shared browser/Wasm and native HTML popup factory; no public ABI.
#pragma once
#include <cstdint>
#include <wtf/Forward.h>
namespace WebCore { class ChromeClient; class HTMLSelectElement; class PopupMenu; class PopupMenuClient; }
namespace BIB::NativeHTMLPopup {
// Stack-only creation permit; no Host/VM/getter/callback from construction.
// The implementation must use the registered exact DOM owner and typed weak
// select support. These raw pointers expire with this synchronous permit.
class NativeSelectPopupCreationPermit final {
public:
    explicit NativeSelectPopupCreationPermit(WebCore::HTMLSelectElement&) noexcept;
    ~NativeSelectPopupCreationPermit();
    NativeSelectPopupCreationPermit(const NativeSelectPopupCreationPermit&) = delete;
    NativeSelectPopupCreationPermit& operator=(const NativeSelectPopupCreationPermit&) = delete;
private:
    friend bool tryCreateNativeSelectPopup(const WebCore::ChromeClient&,
        WebCore::PopupMenuClient&, WTF::RefPtr<WebCore::PopupMenu>&) noexcept;
    NativeSelectPopupCreationPermit* previous_{};
    WebCore::HTMLSelectElement* select_{};
    const WebCore::PopupMenuClient* client_{};
    std::uint64_t serial_{};
    bool active_{};
};
// false: unhandled; preserve the exact old EmptyPopupMenu fallback.
// true+nonnull: exact registered native select popup.
// true+null: handled decline/fault; caller must not set visible/dereference null.
// No exception crosses the no-exception WebCore callers.
bool tryCreateNativeSelectPopup(const WebCore::ChromeClient&,
    WebCore::PopupMenuClient&, WTF::RefPtr<WebCore::PopupMenu>&) noexcept;
} // namespace BIB::NativeHTMLPopup
