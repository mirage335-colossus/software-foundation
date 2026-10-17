// SPDX-License-Identifier: CC0-1.0
#pragma once
#include "BibAppResourceHost.h"
#include <atomic>
#include <cstdint>
#include <map>
#include <memory>
#include <span>
#include <string>
#include <string_view>
#include <thread>
#include <vector>

namespace foundation::appended::candidate {
struct AppResourceLimits {
    std::uint64_t max_response_bytes{64ULL * 1024 * 1024};
    std::uint32_t max_inflight{64};
    std::uint64_t max_retained_bytes{128ULL * 1024 * 1024};
};
[[nodiscard]] constexpr bool valid_app_resource_limits(AppResourceLimits limits) noexcept {
    return limits.max_inflight && limits.max_inflight <= 4096 && limits.max_response_bytes &&
        limits.max_response_bytes <= 64ULL * 1024 * 1024 &&
        limits.max_retained_bytes >= limits.max_response_bytes &&
        limits.max_retained_bytes <= 256ULL * 1024 * 1024;
}
// One instance per engine session, shared by every active/pending/successor
// queue. Only retained-byte release may run on workers. Reservations and ticket
// allocation belong to the construction thread; counters remain atomic because
// a Provider may release its last body concurrently with the next admission.
class AppResourceBudget final {
public:
    AppResourceBudget(std::uint64_t max_response_bytes, std::uint32_t max_inflight,
        std::uint64_t max_retained_bytes);
    explicit AppResourceBudget(AppResourceLimits limits)
        : AppResourceBudget(limits.max_response_bytes, limits.max_inflight, limits.max_retained_bytes) { }
    AppResourceBudget(const AppResourceBudget&) = delete;
    AppResourceBudget& operator=(const AppResourceBudget&) = delete;
    [[nodiscard]] const AppResourceLimits& limits() const noexcept { return limits_; }
    [[nodiscard]] std::uint64_t retained_bytes() const noexcept { return retained_.load(std::memory_order_acquire); }
    [[nodiscard]] std::uint32_t inflight() const noexcept { return inflight_.load(std::memory_order_acquire); }
    [[nodiscard]] bool owner_thread() const noexcept { return std::this_thread::get_id() == thread_; }
private:
    friend class AppResourceQueue;
    [[nodiscard]] std::uint64_t acquire_ticket() noexcept;
    void release_ticket() noexcept;
    [[nodiscard]] bool reserve_body(std::uint64_t) noexcept;
    void release_body(std::uint64_t) noexcept;
    const AppResourceLimits limits_;
    const std::thread::id thread_{std::this_thread::get_id()};
    std::atomic<std::uint64_t> retained_{};
    std::atomic<std::uint32_t> inflight_{};
    std::uint64_t next_ticket_{1}; // 0 means exhausted; never wraps/reuses.
};
struct AppResourceReply {
    std::uint32_t status{};
    std::uint64_t content_length{};
    std::string mime;
    std::vector<std::uint8_t> body;
};
class AppResourceSink {
public:
    virtual ~AppResourceSink() = default;
    // Borrowed until callback returns. Headers/data may synchronously cancel or
    // close this queue; response continuation may be deferred.
    virtual void response(std::uint64_t ticket, const AppResourceReply&) = 0;
    virtual void data(std::uint64_t ticket, std::span<const std::uint8_t>) = 0;
    virtual void finished(std::uint64_t ticket) = 0;
};
class AppResourceQueue final {
public:
    // No implicit per-queue budget: callers must retain/share the session one.
    AppResourceQueue(const BibAppResourceHostV1&, std::shared_ptr<AppResourceBudget>);
    ~AppResourceQueue();
    AppResourceQueue(const AppResourceQueue&) = delete;
    AppResourceQueue& operator=(const AppResourceQueue&) = delete;
    [[nodiscard]] std::uint64_t prepare(std::uint64_t epoch, std::string_view method, std::string_view resolved_url);
    bool begin(std::uint64_t ticket, AppResourceSink&);
    bool continue_response(std::uint64_t ticket, AppResourceSink&);
    bool cancel(std::uint64_t ticket) noexcept;
    void close(std::uint64_t epoch) noexcept;
    [[nodiscard]] bool contains(std::uint64_t ticket) const noexcept;
    [[nodiscard]] std::size_t count() const noexcept { return owner_thread() ? pending_.size() : 0; }
    [[nodiscard]] std::uint64_t retained_bytes() const noexcept { return budget_->retained_bytes(); }
    [[nodiscard]] std::shared_ptr<const AppResourceReply> retain_reply(std::uint64_t ticket) const noexcept;
    [[nodiscard]] std::uint64_t epoch() const noexcept { return hooks_.document_epoch; }
private:
    struct Held {
        AppResourceReply reply;
        std::shared_ptr<AppResourceBudget> budget;
        std::uint64_t charge{};
        ~Held(); // Frees body allocation BEFORE making its reservation reusable.
    };
    struct Pending {
        std::shared_ptr<Held> held;
        std::shared_ptr<AppResourceBudget> budget;
        enum class Stage { ready, waiting, delivering } stage{Stage::ready};
        ~Pending();
    };
    [[nodiscard]] bool owner_thread() const noexcept { return std::this_thread::get_id() == thread_; }
    const BibAppResourceHostV1 hooks_;
    const std::thread::id thread_{std::this_thread::get_id()};
    const std::shared_ptr<AppResourceBudget> budget_;
    std::map<std::uint64_t, std::unique_ptr<Pending>> pending_;
    bool closed_{false};
};
}
