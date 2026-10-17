#pragma once

#include <foundation/appended/provider_abi.h>
#include <foundation/appended/registry.hpp>
#include <functional>
#include <memory>

namespace foundation::appended {
class Module;
struct ProviderLimits {
    std::uint32_t max_providers{FOUNDATION_PROVIDER_MAX_PROVIDERS};
    std::uint32_t max_payload_bytes{FOUNDATION_PROVIDER_MAX_PAYLOAD_BYTES};
    std::uint32_t max_retained_calls{FOUNDATION_PROVIDER_MAX_RETAINED_CALLS};
    std::uint32_t max_retained_bytes{FOUNDATION_PROVIDER_MAX_RETAINED_BYTES};
};
struct ProviderDescriptor {
    ServiceDescriptor contract;
    std::uint32_t max_request_bytes{0};
};
struct ProviderDiscovery {
    ServiceStatus status{ServiceStatus::not_found};
    std::uint64_t handle{0};
    ProviderDescriptor descriptor;
};
struct ProviderRequest {
    std::uint64_t generation{0}, sequence{0}, provider{0};
    std::uint32_t operation{0};
    Bytes payload;
};
struct ProviderOutcome {
    ServiceStatus status{ServiceStatus::unavailable};
    Bytes payload;
};

/* Construct after Module, before initialize; destroy before Module. Registry must
 * be exactly the one used by Module and outlive both. Native callbacks retain
 * shared closed state after this object dies, never a dangling bridge pointer.
 * All operations use the same serialized owner as Module and Registry. Owners
 * must remain alive through every callback and the entire public invocation;
 * shutdown can be requested recursively, destruction cannot.
 *
 * Service callbacks only copy registrations/responses. invoke never enters the
 * guest while a Registry or Module invocation is active. A web owner queues it
 * until its engine callback returns, then delivers completion after invoke ends.
 * Provider functions respond synchronously during one dispatch; no deferred jobs
 * or fake native service callbacks are installed for application contracts. */
class ModuleProviders {
public:
    /* Supply the owner's shared outbound event sequence source when mixing view
     * and provider events. Values must strictly increase; gaps are permitted.
     * Without one, this bridge owns a private sequence source
     * and must be the only producer of events for its Module. */
    using EventSequence = std::function<std::optional<std::uint64_t>()>;
    ModuleProviders(Module&, Registry&, EventSequence events = {}, ProviderLimits limits = {});
    ~ModuleProviders();
    ModuleProviders(const ModuleProviders&) = delete;
    ModuleProviders& operator=(const ModuleProviders&) = delete;

    ServiceStatus activate();
    ProviderDiscovery discover(const DiscoveryQuery&) const;
    ProviderOutcome invoke(const ProviderRequest&);
    ServiceStatus acknowledge(std::uint64_t through_sequence) noexcept;
    void close() noexcept;
    bool closed() const noexcept;
    std::uint64_t service_handle() const noexcept;
    std::size_t provider_count() const noexcept;
    std::size_t retained_call_count() const noexcept;
    static const SchemaId& schema() noexcept;
private:
    struct State;
    Module& module_;
    Registry& registry_;
    std::shared_ptr<State> state_;
};
} // namespace foundation::appended
