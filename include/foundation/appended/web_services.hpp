#pragma once

#include <foundation/appended/providers.hpp>

#include <cstddef>
#include <cstdint>
#include <functional>
#include <memory>
#include <optional>
#include <span>

namespace foundation::appended {

/* Deliberate native wrappers, reusable at composition time. Install the same
 * list into the guest Registry and the separate web Registry; never forward a
 * web callback through the guest's Registry or copy a Registry's ledger. The
 * handlers' captured owners must outlive every installed registration. */
struct NativeServiceRegistration {
    ServiceDescriptor descriptor;
    ServiceHandler handler;
};
/* Startup only. A failure may leave earlier registrations installed; the owner
 * must abandon that startup rather than retrying the list on that Registry. */
ServiceStatus install_native_services(Registry&, std::span<const NativeServiceRegistration>);

enum class WebServiceSource { automatic, native, module };

struct WebServiceLimits {
    std::uint32_t max_message_bytes{FOUNDATION_APPENDED_MAX_MESSAGE_BYTES};
    std::uint32_t max_retained_calls{64};
    std::uint32_t max_retained_bytes{4 * FOUNDATION_APPENDED_MAX_MESSAGE_BYTES};
    std::uint32_t max_service_handles{256};
};

struct WebModuleServices {
    std::uint64_t generation{0};
    /* Bind at the binary-capable composition root, using ModuleProviders or the
     * AppendedApplication composition API. Web-only kernels leave these empty;
     * the queue itself never references a Module or interpreter implementation.
     * These are scheduling hooks, never native Registry service callbacks. */
    std::function<ProviderDiscovery(const DiscoveryQuery&)> discover;
    std::function<ProviderOutcome(const ProviderRequest&)> invoke;
    /* Notification that this single host-call outcome has been copied. An
     * exclusive owner can directly acknowledge through it. A shared owner must
     * broker retirement with its other consumers and retain their outcomes. */
    std::function<ServiceStatus(std::uint64_t)> acknowledge;
    /* Required when other callers share this ModuleProviders host-call domain.
     * Without it, this queue is the bridge's exclusive host-call producer.
     * Also required when a retained Module generation outlives this document:
     * the owner keeps this sequence domain across replacement WebServices and
     * brokers acknowledgements for every consumer of that retained ledger.
     * This is separate from the Module owner's outbound event sequence. */
    std::function<std::optional<std::uint64_t>()> sequence;
};

/* One internal document/epoch, on one serialized owner. A replacement document
 * gets a fresh nonzero generation and a new WebServices object. Its native
 * Registry and native request/ACK counter are independent of the Module's guest
 * gateway. Web handles are opaque and distinct from both underlying namespaces.
 *
 * submit only copies and reserves; it never enters Registry or ModuleProviders.
 * Wrap each engine callback with CallbackScope. Pump after that scope returns,
 * then poll owned completions after pump returns; never deliver into the engine
 * synchronously from a native/guest service invocation. Nested callback scopes
 * are permitted; pump, completion delivery and ACK refuse while one is active.
 *
 * Requests use existing v1 REQUEST Envelopes and canonical bootstrap DISCOVER
 * TLV records (handle zero, operation DISCOVER). Discovery replies use the same
 * bootstrap descriptor record with a web-owned handle. Automatic discovery
 * selects the highest compatible minor across both sources; identical selected
 * versions in both sources are a conflict. Completions use kind COMPLETION with
 * the original generation/sequence/web handle/operation and zero correlation.
 * Ordinary calls resolve their opaque handle without a source choice. Explicit
 * source selection is optional.
 *
 * All admitted request/reply storage is bounded and reserved before effects.
 * Identical live resubmission replays; changed bytes/source conflict; old gaps
 * expire. cancel affects only queued calls and completes them as CLOSED.
 * acknowledge retires only a completed prefix, including unused lower gaps.
 * No uncertain effect is retried automatically. Internal backend outcomes may
 * be acknowledged after copying; web outcomes remain until explicit web ACK.
 *
 * All hook and native callback owners outlive this object. Keep this object
 * alive through every callback scope and entire public invocation; close may be
 * requested recursively but destruction may not. No engine pointer is retained.
 * This queue is an integration component, not an integrated WebCore adapter. */
class WebServices {
public:
    class CallbackScope {
    public:
        explicit CallbackScope(WebServices&);
        ~CallbackScope();
        CallbackScope(const CallbackScope&) = delete;
        CallbackScope& operator=(const CallbackScope&) = delete;
    private:
        WebServices& owner_;
    };

    WebServices(std::uint64_t document_generation,
                std::span<const NativeServiceRegistration> native_services = {},
                WebModuleServices module = {}, WebServiceLimits limits = {});
    ~WebServices();
    WebServices(const WebServices&) = delete;
    WebServices& operator=(const WebServices&) = delete;

    ServiceStatus submit(std::span<const std::uint8_t> request,
                         WebServiceSource source = WebServiceSource::automatic);
    ServiceStatus cancel(std::uint64_t generation, std::uint64_t sequence);
    ServiceStatus pump(std::size_t maximum_calls = 1);
    /* Returns each ready completion once; identical submit makes it ready again.
     * Allocation failure leaves delivery pending. Bytes never borrow VM storage. */
    std::optional<Bytes> take_completion();
    /* Trusted owner retirement only. A closed queue exposes its lowest retained
     * exact completion even after normal delivery; this never acknowledges it,
     * changes replay/delivery state or runs a handler. Active queues conflict;
     * callback/pump entry is unavailable; an empty closed queue is not_found.
     * A too-small output returns limit_exceeded. Output scalars are unchanged
     * unless ok; all bytes continue to belong to the queue until actual ACK. */
    ServiceStatus copy_closed_completion(std::span<std::uint8_t> output,
        std::uint64_t& sequence, std::uint32_t& written) const noexcept;
    ServiceStatus acknowledge(std::uint64_t generation, std::uint64_t through_sequence);
    void close() noexcept;
    bool closed() const noexcept;
    std::uint64_t generation() const noexcept;
    /* Reports calls still awaiting pump, including during callback scopes.
     * Running calls and retained completions do not count as queued work. */
    bool has_queued_calls() const noexcept;
    std::size_t retained_call_count() const noexcept;
    std::size_t retained_bytes() const noexcept;

private:
    struct Impl;
    std::unique_ptr<Impl> impl_;
};

} // namespace foundation::appended
