#pragma once

#include <cstdint>
#include <memory>
#include <span>

namespace foundation::appended {
class Registry;

/* One trusted foundation-guest-v1 instance. Registry must outlive the Module,
 * belongs to this instance only, and is closed on shutdown or terminal failure.
 * Calls are synchronous and serialized by the caller. Construction validates
 * bytes and required signatures before querying the ABI; it runs no start
 * function. Invalid modules and runtime traps throw std::runtime_error.
 * The runtime is private: no supplier types or native pointers form the ABI.
 * Keep the Module and Registry alive until every public invocation returns;
 * callbacks may request shutdown but must not destroy their active owners. */
class Module {
public:
    Module(std::span<const std::uint8_t> bytes, Registry& registry);
    ~Module();
    Module(const Module&) = delete;
    Module& operator=(const Module&) = delete;
    Module(Module&&) = delete;
    Module& operator=(Module&&) = delete;

    /* Exactly one attempt. Supplies an encoded context from registry generation
     * and limits before enabling application services. Nonzero results close
     * the instance and release interpreter resources immediately. Initialization
     * uses its fixed 128-byte context independently of the gateway message cap.
     * Input buffers are copied and released within each call; dispatch may be
     * empty without requesting a zero-byte guest allocation. */
    std::uint32_t initialize();
    std::uint32_t dispatch(std::span<const std::uint8_t> bytes);
    std::uint32_t step(std::uint32_t budget_units);
    void shutdown(std::uint32_t reason = 0) noexcept;

    /* Native scheduling guards. All guest exports, including allocation/free,
     * belong to one invocation. Recursive public entry rejects before teardown;
     * shutdown requested during an invocation is deferred until it returns. */
    bool invocation_active() const noexcept;
    bool initializing() const noexcept;
    bool initialized() const noexcept;
    bool closed() const noexcept;
    bool uses_registry(const Registry&) const noexcept;

private:
    struct Impl;
    std::unique_ptr<Impl> impl_;
};
} // namespace foundation::appended
