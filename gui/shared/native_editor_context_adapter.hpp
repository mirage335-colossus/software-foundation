// SPDX-License-Identifier: CC0-1.0
#pragma once
#include "native_editor_controller.hpp"
#include <functional>
#include <memory>
#include <optional>

namespace foundation::ui::native_editor {
struct ContextRequest {
    enum class Kind { projection, observation, revoke };
    Kind kind = Kind::projection;
    // Correlation for this transport stage; distinct from the browser head.
    std::uint64_t ticket{}, head_ticket{}, mapping_id{};
    std::optional<NativeRequest> request;
    std::optional<Revocation> revocation;
    std::optional<NativeRevocationRequest> retirement;
};
using ContextRequestKind = ContextRequest::Kind;
// Transport mailbox and checked publication around the typed owner. submit and
// queue_revoke retain bounded values only, even during a browser callback.
// Async owner phases never enter a Backend; advance is the optional synchronous
// mock compatibility path. Injected lifetime owners must outlive this endpoint.
class NativeEditorContextAdapter final {
public:
    using Publish = std::function<bool(const EditorPublication&)>;
    using BeforeHead = std::function<bool()>;
    NativeEditorContextAdapter(Publish, EditorTerminalHook);
    NativeEditorContextAdapter(Backend&, Publish, EditorTerminalHook);
    ~NativeEditorContextAdapter();
    NativeEditorContextAdapter(const NativeEditorContextAdapter&) = delete;
    NativeEditorContextAdapter& operator=(const NativeEditorContextAdapter&) = delete;
    bool install_projection(NativeProjection);
    std::optional<std::uint64_t> submit(Packet);
    std::optional<std::uint64_t> queue_revoke(Revocation);
    // All methods below are owner phases, outside ingress/publication callbacks.
    // prepare offers each stage once. A busy owner that did not accept it must
    // defer that exact ticket; a sent/uncertain operation must never be deferred.
    // Explicit resync retires old ownership before focused rediscovery.
    bool request_projection();
    // Read-only revalidation of the current mapping. Identical checked native
    // facts (apart from presentation revision) preserve token and composition;
    // changed/unavailable facts retire old ownership before rediscovery.
    bool request_refresh();
    // Trusted redaction: withhold any in-flight known receipt until exact owned
    // retirement is checked. This does not rewrite its actual native outcome.
    bool request_retirement();
    std::optional<ContextRequest> prepare(BeforeHead = {});
    bool defer(std::uint64_t ticket);
    // True means the correlated offered callback was consumed, even when it
    // exposed a terminal result. False never authorizes replay of a sent effect.
    bool supply_projection(std::uint64_t ticket, std::optional<NativeProjection>,
        std::optional<RetirementReadback> = {});
    bool complete(std::uint64_t ticket, NativeResult);
    // Trusted Owner evidence only: the admitted provider operation is known
    // never to have entered. This is neither frontend cancellation nor defer.
    bool cancel_unentered(std::uint64_t ticket);
    bool notify_transport_failure(std::uint64_t ticket) noexcept;
    // Synchronous compatibility for injected pure mock Backends only.
    bool advance();
    std::optional<EditorCompletion> take_completion(std::uint64_t ticket);
    const EditorPublication* publication() const noexcept;
    // Checked geometry/readback matching publication(). During Publish this
    // exposes the staged checked projection, before either cache is committed.
    const NativeProjection* projection() const noexcept;
    bool available() const noexcept;
    bool terminal() const noexcept;
    bool pending() const noexcept;
    // Independent of retained browser completions: true until the requested
    // native cleanup and its checked null publication have both settled.
    bool retirement_pending() const noexcept;
    // Composition guards every physical/dispatcher/publication callback with
    // these methods; neither invokes a Backend. Nested callbacks are allowed.
    void enter_callback();
    void leave_callback() noexcept;
    void notify_terminal() noexcept;
    void close() noexcept;
private:
    struct Impl;
    std::unique_ptr<Impl> impl_;
};
}
