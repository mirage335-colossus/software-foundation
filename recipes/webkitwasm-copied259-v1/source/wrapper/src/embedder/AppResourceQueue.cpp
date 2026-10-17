// SPDX-License-Identifier: CC0-1.0
#include "AppResourceQueue.hpp"
#include <algorithm>
#include <limits>
#include <stdexcept>
#include <utility>

namespace foundation::appended::candidate {
namespace {
bool valid_mime(std::string_view mime) {
    const auto slash = mime.find('/');
    return slash != std::string_view::npos && slash && slash + 1 < mime.size() &&
        mime.find('/', slash + 1) == std::string_view::npos && mime.size() <= 127 &&
        std::all_of(mime.begin(), mime.end(), [](char c) {
            return (c >= 'a' && c <= 'z') || (c >= '0' && c <= '9') || c == '.' || c == '+' || c == '-' || c == '/';
        });
}
struct Lease {
    const BibAppResourceHostV1& hooks;
    std::uint64_t value{};
    ~Lease() { if (value) hooks.release(hooks.context, value); }
};
}
AppResourceBudget::AppResourceBudget(std::uint64_t response, std::uint32_t inflight, std::uint64_t retained)
    : limits_{response, inflight, retained} {
    if (!valid_app_resource_limits(limits_))
        throw std::invalid_argument("invalid app resource session limits");
}
std::uint64_t AppResourceBudget::acquire_ticket() noexcept {
    if (!owner_thread() || !next_ticket_ || inflight() >= limits_.max_inflight) return 0;
    inflight_.fetch_add(1, std::memory_order_acq_rel);
    const auto result = next_ticket_;
    next_ticket_ = result == std::numeric_limits<std::uint64_t>::max() ? 0 : result + 1;
    return result;
}
void AppResourceBudget::release_ticket() noexcept { inflight_.fetch_sub(1, std::memory_order_acq_rel); }
bool AppResourceBudget::reserve_body(std::uint64_t bytes) noexcept {
    if (!owner_thread() || bytes > limits_.max_response_bytes) return false;
    auto prior = retained_.load(std::memory_order_acquire);
    do {
        if (prior > limits_.max_retained_bytes || bytes > limits_.max_retained_bytes - prior) return false;
    } while (!retained_.compare_exchange_weak(prior, prior + bytes, std::memory_order_acq_rel, std::memory_order_acquire));
    return true;
}
void AppResourceBudget::release_body(std::uint64_t bytes) noexcept { retained_.fetch_sub(bytes, std::memory_order_acq_rel); }
AppResourceQueue::Held::~Held() {
    std::vector<std::uint8_t>().swap(reply.body);
    if (budget) budget->release_body(charge);
}
AppResourceQueue::Pending::~Pending() { if (budget) budget->release_ticket(); }
AppResourceQueue::AppResourceQueue(const BibAppResourceHostV1& hooks, std::shared_ptr<AppResourceBudget> budget)
    : hooks_(hooks), budget_(std::move(budget)) {
    if (!budget_ || !budget_->owner_thread() || hooks_.size != sizeof(hooks_) ||
        hooks_.version != BIB_APP_RESOURCE_HOST_VERSION || !hooks_.document_epoch ||
        !hooks_.resolve || !hooks_.release || hooks_.reserved ||
        hooks_.max_response_bytes != budget_->limits().max_response_bytes ||
        hooks_.max_inflight != budget_->limits().max_inflight ||
        hooks_.max_retained_bytes != budget_->limits().max_retained_bytes)
        throw std::invalid_argument("invalid app resource hooks or non-session budget");
}
AppResourceQueue::~AppResourceQueue() { pending_.clear(); }
std::uint64_t AppResourceQueue::prepare(std::uint64_t epoch, std::string_view method, std::string_view url) {
    if (!owner_thread() || closed_ || epoch != hooks_.document_epoch || method.size() > 16 || url.size() > 4096) return 0;
    // Reserve the global slot before calling the host. A rejected response or
    // exception releases it; copied Provider bodies carry a separate charge.
    auto pending = std::make_unique<Pending>();
    const auto ticket = budget_->acquire_ticket();
    if (!ticket) return 0;
    pending->budget = budget_;
    BibAppResourceRequestV1 request{sizeof(request), BIB_APP_RESOURCE_HOST_VERSION, epoch,
        reinterpret_cast<const std::uint8_t*>(method.data()), static_cast<std::uint32_t>(method.size()),
        reinterpret_cast<const std::uint8_t*>(url.data()), static_cast<std::uint32_t>(url.size())};
    BibAppResourceResponseV1 response{};
    const auto result = hooks_.resolve(hooks_.context, &request, &response);
    Lease lease{hooks_, response.lease};
    if (result || response.size != sizeof(response) || response.version != BIB_APP_RESOURCE_HOST_VERSION ||
        response.status < 200 || response.status > 599 || response.status / 100 == 3 ||
        response.body_length > hooks_.max_response_bytes || response.content_length > hooks_.max_response_bytes ||
        response.mime_length > 127 || (!response.mime && response.mime_length) ||
        (!response.body && response.body_length) || (method == "HEAD" && response.body_length) ||
        (method == "GET" && response.body_length != response.content_length)) return 0;
    const std::string_view mime(response.mime ? reinterpret_cast<const char*>(response.mime) : "", response.mime_length);
    if (!valid_mime(mime)) return 0;
    auto held = std::make_shared<Held>();
    if (!budget_->reserve_body(response.body_length)) return 0;
    // Everything below may allocate. Bind the charge first, so all exception
    // paths free/cancel reservations and release the host lease exactly once.
    held->budget = budget_;
    held->charge = response.body_length;
    held->reply.status = response.status;
    held->reply.content_length = response.content_length;
    held->reply.mime = mime;
    if (response.body_length) held->reply.body.assign(response.body, response.body + response.body_length);
    pending->held = std::move(held);
    pending_.emplace(ticket, std::move(pending));
    return ticket;
}
bool AppResourceQueue::begin(std::uint64_t ticket, AppResourceSink& sink) {
    if (!owner_thread() || closed_) return false;
    const auto it = pending_.find(ticket);
    if (it == pending_.end() || it->second->stage != Pending::Stage::ready) return false;
    auto held = it->second->held;
    it->second->stage = Pending::Stage::waiting;
    sink.response(ticket, held->reply);
    return true;
}
bool AppResourceQueue::continue_response(std::uint64_t ticket, AppResourceSink& sink) {
    if (!owner_thread() || closed_) return false;
    const auto it = pending_.find(ticket);
    if (it == pending_.end() || it->second->stage != Pending::Stage::waiting) return false;
    auto held = it->second->held;
    it->second->stage = Pending::Stage::delivering;
    if (!held->reply.body.empty()) sink.data(ticket, held->reply.body);
    const auto current = pending_.find(ticket);
    if (closed_ || current == pending_.end() || current->second->held != held) return true;
    pending_.erase(current);
    sink.finished(ticket);
    return true;
}
bool AppResourceQueue::cancel(std::uint64_t ticket) noexcept {
    return owner_thread() && pending_.erase(ticket) != 0;
}
void AppResourceQueue::close(std::uint64_t epoch) noexcept {
    if (!owner_thread() || epoch != hooks_.document_epoch) return;
    closed_ = true;
    pending_.clear();
}
bool AppResourceQueue::contains(std::uint64_t ticket) const noexcept {
    return owner_thread() && !closed_ && pending_.contains(ticket);
}
std::shared_ptr<const AppResourceReply> AppResourceQueue::retain_reply(std::uint64_t ticket) const noexcept {
    if (!owner_thread() || closed_) return {};
    const auto it = pending_.find(ticket);
    if (it == pending_.end()) return {};
    return {it->second->held, &it->second->held->reply};
}
}
