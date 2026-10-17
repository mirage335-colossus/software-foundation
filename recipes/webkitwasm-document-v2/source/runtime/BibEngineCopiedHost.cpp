// SPDX-License-Identifier: CC0-1.0
#include "BibEngineCopiedHost.h"
#include "appended_engine_abi.h"
#include <algorithm>
#include <bit>
#include <cmath>
#include <cstdlib>
#include <limits>
#include <new>
#include <string_view>

namespace bib::copied {
namespace {
using Span = std::span<const std::uint8_t>;
constexpr std::uint64_t maximum_response = 64ULL * 1024 * 1024;
constexpr std::uint64_t maximum_retained = 128ULL * 1024 * 1024;
constexpr std::uint32_t service_invalid = 1, service_unavailable = 2,
    service_invalid_handle = 7, service_limit = 8, service_closed = 10;
std::uint64_t get(Span bytes, std::size_t offset, unsigned count) noexcept {
    std::uint64_t value{};
    for (unsigned i = 0; i < count; ++i) value |= std::uint64_t(bytes[offset + i]) << (i * 8);
    return value;
}
void put(std::span<std::uint8_t> bytes, std::size_t offset, std::uint64_t value, unsigned count) noexcept {
    for (unsigned i = 0; i < count; ++i) bytes[offset + i] = static_cast<std::uint8_t>(value >> (i * 8));
}
bool same(const BibEngineDocumentV1& a, const BibEngineDocumentV1& b) noexcept {
    return a.application_instance == b.application_instance && a.document_sequence == b.document_sequence &&
        a.service_generation == b.service_generation;
}
bool prospective(const BibEngineDocumentV1& d) noexcept {
    return d.application_instance && d.document_sequence && !d.service_generation;
}
bool mime_valid(Span mime) noexcept {
    if (mime.empty() || mime.size() > 127) return false;
    const std::string_view value(reinterpret_cast<const char*>(mime.data()), mime.size());
    const auto slash = value.find('/');
    return slash && slash != std::string_view::npos && slash + 1 < value.size() &&
        value.find('/', slash + 1) == std::string_view::npos &&
        std::all_of(value.begin(), value.end(), [](char c) {
            return (c >= 'a' && c <= 'z') || (c >= '0' && c <= '9') || c == '-' || c == '+' || c == '.' || c == '/';
        });
}
bool scalar_utf8(Span bytes) noexcept {
    for (std::size_t i = 0; i < bytes.size();) {
        const auto c = bytes[i++];
        if (!c) return false;
        if (c < 0x80) continue;
        unsigned count{};
        std::uint32_t value{}, minimum{};
        if (c >= 0xc2 && c <= 0xdf) { count = 1; value = c & 0x1fu; minimum = 0x80; }
        else if (c >= 0xe0 && c <= 0xef) { count = 2; value = c & 0x0fu; minimum = 0x800; }
        else if (c >= 0xf0 && c <= 0xf4) { count = 3; value = c & 0x07u; minimum = 0x10000; }
        else return false;
        if (count > bytes.size() - i) return false;
        while (count--) {
            const auto tail = bytes[i++];
            if ((tail & 0xc0u) != 0x80u) return false;
            value = (value << 6) | (tail & 0x3fu);
        }
        if (value < minimum || value > 0x10ffff || (value >= 0xd800 && value <= 0xdfff)) return false;
    }
    return true;
}
std::int32_t provider_control(std::uint32_t control) noexcept {
    switch (control) {
    case FOUNDATION_ENGINE_OK: return BIB_ENGINE_OK;
    case FOUNDATION_ENGINE_EMPTY:
    case FOUNDATION_ENGINE_STALE: return BIB_ENGINE_STALE;
    case FOUNDATION_ENGINE_LIMIT: return BIB_ENGINE_LIMIT;
    case FOUNDATION_ENGINE_CLOSED: return BIB_ENGINE_CLOSED;
    case FOUNDATION_ENGINE_UNSUPPORTED: return BIB_ENGINE_UNSUPPORTED;
    case FOUNDATION_ENGINE_CONFLICT: return BIB_ENGINE_REENTRANT;
    default: return BIB_ENGINE_INVALID;
    }
}
} // namespace

CopiedHost::CopiedHost(Import transport, Fatal fatal, void* context) noexcept
    : import_(transport), fatal_(fatal), context_(context) {
    table_ = {sizeof(table_), BIB_ENGINE_ABI_MAJOR, BIB_ENGINE_ABI_MINOR, 0, this,
        c_wake, c_timer, c_damage, nullptr, c_enter, c_leave, c_begin, c_close,
        c_submit, c_cancel, c_ack, c_begin_epoch, c_retire_epoch};
    for (auto& value : epochs_) value.owner = this;
}

[[noreturn]] void CopiedHost::fail(const char* reason) noexcept {
    poisoned_.store(true, std::memory_order_relaxed);
    // No stack unwind, lease release, final TURN_LEAVE or recoverable return.
    if (fatal_) fatal_(context_, reason);
    std::abort();
}
bool CopiedHost::begin_dispatch(const Record& r) noexcept {
    if (poisoned() || !import_ || active_ || importing_ || depth_ || std::this_thread::get_id() != thread_ ||
        !r.worker || r.source || (worker_ && worker_ != r.worker)) return false;
    worker_ = r.worker;
    dispatch_ = {r.instance, r.document, r.generation};
    transfer_ = r.transfer;
    active_ = true;
    ack_ = {};
    return true;
}
bool CopiedHost::begin_metadata_dispatch(const Record& record) noexcept {
    if (!begin_dispatch(record)) return false;
    metadata_only_.store(true,std::memory_order_release);
    return true;
}
void CopiedHost::end_dispatch() noexcept {
    if (poisoned()) return;
    if (!active_ || importing_ || depth_ || std::this_thread::get_id() != thread_) fail("unbalanced copied host dispatch");
    metadata_only_.store(false,std::memory_order_release);
    active_ = false;
}
void CopiedHost::require_callback() noexcept {
    if (metadata_only_.load(std::memory_order_acquire) || poisoned() || !active_ || !depth_ || importing_ || std::this_thread::get_id() != thread_)
        fail("copied host callback outside guarded owner turn");
}
CopiedHost::Receipt CopiedHost::rpc(std::uint32_t op, const BibEngineDocumentV1& d,
    std::uint64_t transfer, std::uint32_t source, Span body, std::span<std::uint8_t> request,
    std::span<std::uint8_t> response, bool begin) noexcept {
    if (poisoned() || !active_ || importing_ || std::this_thread::get_id() != thread_) fail("invalid copied host import scope");
    const Record input{op, worker_, d.application_instance, d.document_sequence, d.service_generation, transfer, source, body};
    std::size_t written{};
    if (writeRecord(input, request, written) != Status::ok || written > UINT32_MAX || response.size() > UINT32_MAX)
        fail("copied host request bounds");
    std::int32_t result{};
    importing_ = true;
    try {
        result = import_(context_, op, request.data(), static_cast<std::uint32_t>(written), response.data(),
            static_cast<std::uint32_t>(response.size()));
    } catch (...) { fail("copied host import exception"); }
    importing_ = false;
    if (result < 0 || static_cast<std::uint32_t>(result) > response.size()) fail("copied host transport failure");
    Receipt receipt;
    if (readReceipt(op, Span(response.data(), static_cast<std::size_t>(result)), receipt.record,
            receipt.control, receipt.service) != Status::ok || receipt.service >= 14)
        fail("malformed or uncertain copied host receipt");
    const auto& r = receipt.record;
    const bool generation_matches = r.generation == d.service_generation ||
        (begin && receipt.control == FOUNDATION_ENGINE_OK && !receipt.service && !d.service_generation && r.generation);
    if (r.worker != worker_ || r.instance != d.application_instance || r.document != d.document_sequence ||
        !generation_matches || r.transfer != transfer || r.source != source ||
        (receipt.control != FOUNDATION_ENGINE_OK && !receipt.service &&
            op != FOUNDATION_ENGINE_BEGIN_DOCUMENT))
        fail("copied host receipt authority mismatch");
    return receipt;
}

std::uint32_t CopiedHost::enter_engine() noexcept {
    if (metadata_only_.load(std::memory_order_acquire) || poisoned() || !active_ || importing_ || std::this_thread::get_id() != thread_ || depth_ == 64)
        fail("invalid copied host engine entry");
    if (depth_) { ++depth_; return 0; }
    std::array<std::uint8_t, headerBytes> request{};
    std::array<std::uint8_t, receiptBytes> response{};
    const auto r = rpc(FOUNDATION_ENGINE_TURN_ENTER, dispatch_, transfer_, 0, {}, request, response);
    if (!r.record.body.empty()) fail("unexpected native turn receipt body");
    if (!r.control && !r.service) depth_ = 1;
    return r.service;
}
void CopiedHost::leave_engine() noexcept {
    if (metadata_only_.load(std::memory_order_acquire)) fail("metadata-only ACK attempted native leave");
    if (poisoned()) return;
    require_callback();
    if (--depth_) return;
    std::array<std::uint8_t, headerBytes> request{};
    std::array<std::uint8_t, receiptBytes> response{};
    // dispatch_ is immutable even after BEGIN adopts a new native instance.
    const auto r = rpc(FOUNDATION_ENGINE_TURN_LEAVE, dispatch_, transfer_, 0, {}, request, response);
    if (r.control || r.service || !r.record.body.empty()) fail("native turn leave refused");
}
void CopiedHost::adopt(const BibEngineDocumentV1& d) noexcept {
    if (!d.application_instance || !d.document_sequence ||
        (current_.application_instance && d.application_instance != current_.application_instance) ||
        d.document_sequence < highest_document_sequence_) fail("invalid copied document adoption");
    if (current_.document_sequence == d.document_sequence && current_.service_generation &&
        d.service_generation && d.service_generation != current_.service_generation) fail("copied document generation replacement");
    // A late resource callback cannot erase service authority already bound.
    if (current_.document_sequence == d.document_sequence && !d.service_generation && current_.service_generation) return;
    current_ = d;
    highest_document_sequence_ = d.document_sequence;
}
CopiedHost::Document* CopiedHost::document(std::uint64_t generation) noexcept {
    if (!generation) return nullptr;
    const auto found = std::find_if(documents_.begin(), documents_.end(), [&](const auto& d) {
        return d.identity.service_generation == generation;
    });
    return found == documents_.end() ? nullptr : &*found;
}
CopiedHost::Epoch* CopiedHost::epoch(std::uint64_t token) noexcept {
    if (!token) return nullptr;
    const auto found = std::find_if(epochs_.begin(), epochs_.end(), [&](const auto& e) { return e.token == token; });
    return found == epochs_.end() ? nullptr : &*found;
}
std::uint64_t CopiedHost::begin_document(const BibEngineDocumentV1* prospective_document) noexcept {
    require_callback();
    if (!prospective_document || !prospective(*prospective_document)) return 0;
    const auto slot = std::find_if(documents_.begin(), documents_.end(), [](const auto& d) { return !d.identity.service_generation; });
    if (slot == documents_.end()) return 0;
    std::array<std::uint8_t, headerBytes> request{};
    std::array<std::uint8_t, receiptBytes> response{};
    const auto r = rpc(FOUNDATION_ENGINE_BEGIN_DOCUMENT, *prospective_document, 0, 0, {}, request, response, true);
    if (!r.record.body.empty()) fail("unexpected service begin body");
    if (r.control || r.service) return 0;
    const auto generation = r.record.generation;
    if (!generation || document(generation)) fail("duplicate copied service generation");
    const BibEngineDocumentV1 adopted{r.record.instance, r.record.document, generation};
    *slot = {adopted, 0, false};
    // Kernel BEGIN retires its previous active queue atomically.
    for (auto& d : documents_) if (&d != &*slot && !d.closed && d.identity.service_generation) {
        d.closed = true;
        retire_document_resources(d.identity);
    }
    adopt(adopted);
    for (auto& e : epochs_) if (e.token && e.identity.application_instance == adopted.application_instance &&
        e.identity.document_sequence == adopted.document_sequence) e.identity = adopted;
    return generation;
}
void CopiedHost::close_document(std::uint64_t generation) noexcept {
    require_callback();
    auto* d = document(generation);
    if (!d || d->closed) return;
    std::array<std::uint8_t, headerBytes> request{};
    std::array<std::uint8_t, receiptBytes> response{};
    const auto r = rpc(FOUNDATION_ENGINE_CLOSE_DOCUMENT, d->identity, 0, 0, {}, request, response);
    if (r.control || r.service || !r.record.body.empty()) fail("service document close refused");
    d->closed = true;
    retire_document_resources(d->identity);
    // Mirror the copied browser endpoint's transport metadata: closing the
    // exact latest tuple keeps its instance but clears document authority.
    // Closing an older tuple must preserve any newer prospective reservation.
    if (same(current_, d->identity)) current_ = {current_.application_instance, 0, 0};
}
bool CopiedHost::forget_disposed_document(const BibEngineDocumentV1& identity) noexcept {
    if (poisoned() || !active_ || importing_ || depth_ || std::this_thread::get_id() != thread_) return false;
    auto* d = document(identity.service_generation);
    if (!d || !same(d->identity, identity) || !d->closed) return false;
    *d = {};
    return true;
}
std::uint32_t CopiedHost::service(std::uint32_t op, std::uint64_t generation, std::uint64_t sequence,
    const BibEngineBytesV1* bytes, std::uint32_t source) noexcept {
    require_callback();
    auto* d = document(generation);
    if (!d) return service_invalid_handle;
    // ACK readback remains legal on retained closed queues.
    if (d->closed && op != FOUNDATION_ENGINE_STAGE_ACK) return service_closed;
    if (source > 2 || (bytes && (bytes->reserved || (!bytes->data && bytes->length)))) return service_invalid;
    if (bytes && bytes->length > maxBodyBytes) return service_limit;
    if (!bytes && !sequence) return service_invalid;
    std::array<std::uint8_t, 8> sequence_body{};
    put(sequence_body, 0, sequence, 8);
    const Span body = bytes ? Span(bytes->data, bytes->length) : Span(sequence_body);
    std::array<std::uint8_t, receiptBytes> response{};
    Receipt r;
    try {
        std::vector<std::uint8_t> request(headerBytes + body.size());
        r = rpc(op, d->identity, 0, source, body, request, response);
    } catch (const std::bad_alloc&) { return service_limit; }
    catch (...) { fail("copied service request allocation failure"); }
    if (!r.record.body.empty()) fail("unexpected service callback body");
    if (op == FOUNDATION_ENGINE_STAGE_ACK) {
        if (ack_.count == UINT32_MAX) fail("ACK observation overflow");
        ++ack_.count;
        ack_.document = d->identity;
        ack_.through = sequence;
        ack_.status = r.service;
        ack_.control = r.control;
    }
    return r.service;
}

std::size_t CopiedHost::active_resource_contexts() const noexcept {
    return static_cast<std::size_t>(std::count_if(epochs_.begin(), epochs_.end(), [](const auto& e) { return e.token != 0; }));
}
std::size_t CopiedHost::outstanding_resource_leases() const noexcept {
    return static_cast<std::size_t>(std::count_if(leases_.begin(), leases_.end(), [](const auto& l) { return l.token != 0; }));
}
void CopiedHost::clear_retired(Epoch& e) noexcept {
    if (e.retired && !e.leases) { e = {}; e.owner = this; }
}
void CopiedHost::retire_document_resources(const BibEngineDocumentV1& identity) noexcept {
    // The actual kernel service CLOSE/BEGIN retires matching resource contexts
    // atomically and may already prune zero-lease contexts. Supplier destruction
    // can report its explicit retirement later: never send that known duplicate
    // to an epoch the kernel has already removed. Outstanding real leases keep
    // the local context pinned until their matching release succeeds.
    for (auto& e : epochs_) if (e.token && e.identity.application_instance == identity.application_instance &&
        e.identity.document_sequence == identity.document_sequence) {
        e.retired = true;
        clear_retired(e);
    }
}
std::int32_t CopiedHost::begin_epoch(const BibEngineDocumentV1* prospective_document, BibEngineResourceEpochV1* out) noexcept {
    require_callback();
    if (!out) return BIB_ENGINE_INVALID;
    *out = {};
    if (!prospective_document || !prospective(*prospective_document)) return BIB_ENGINE_INVALID;
    const auto slot = std::find_if(epochs_.begin(), epochs_.end(), [](const auto& e) { return !e.token; });
    if (slot == epochs_.end()) return BIB_ENGINE_LIMIT;
    std::array<std::uint8_t, headerBytes> request{};
    std::array<std::uint8_t, receiptBytes + 8> response{};
    const auto r = rpc(FOUNDATION_ENGINE_BEGIN_RESOURCE_EPOCH, *prospective_document, 0, 0, {}, request, response);
    if (r.control || r.service) {
        if (!r.record.body.empty()) fail("unexpected rejected epoch body");
        return r.control ? provider_control(r.control) : BIB_ENGINE_INVALID;
    }
    if (r.record.body.size() != 8) fail("malformed epoch token");
    const auto token = get(r.record.body, 0, 8);
    if (!token || epoch(token)) fail("duplicate copied resource epoch");
    *slot = {this, *prospective_document, token, 0, false};
    adopt(*prospective_document);
    *out = {sizeof(*out), 0, token, &*slot, c_resolve, c_release};
    return BIB_ENGINE_OK;
}
void CopiedHost::retire_epoch(std::uint64_t token) noexcept {
    require_callback();
    auto* e = epoch(token);
    if (!e || e->retired) return;
    std::array<std::uint8_t, 8> body{};
    put(body, 0, token, 8);
    std::array<std::uint8_t, headerBytes + 8> request{};
    std::array<std::uint8_t, receiptBytes> response{};
    const auto r = rpc(FOUNDATION_ENGINE_RETIRE_RESOURCE_EPOCH, e->identity, 0, 0, body, request, response);
    if (r.control || r.service || !r.record.body.empty()) fail("resource epoch retirement refused");
    e->retired = true;
    clear_retired(*e);
}
void CopiedHost::release_kernel(Epoch& e, std::uint64_t token) noexcept {
    if (!token || poisoned()) return;
    std::array<std::uint8_t, 8> body{};
    put(body, 0, token, 8);
    std::array<std::uint8_t, headerBytes + 8> request{};
    std::array<std::uint8_t, receiptBytes> response{};
    const auto r = rpc(FOUNDATION_ENGINE_RESOURCE_RELEASE, e.identity, 0, 0, body, request, response);
    if (r.control || r.service || !r.record.body.empty()) fail("resource lease release refused");
}
std::int32_t CopiedHost::resolve(Epoch& e, const BibEngineResourceRequestV1* input, BibEngineResourceResponseV1* out) noexcept {
    require_callback();
    if (!out) return BIB_ENGINE_INVALID;
    *out = {};
    if (!input || input->size != sizeof(*input) || input->reserved || input->method.reserved ||
        input->resolved_url.reserved || !input->method.data || !input->resolved_url.data ||
        !input->resolved_url.length || input->resolved_url.length > 4096) return BIB_ENGINE_INVALID;
    if (!e.token || e.retired || input->resource_epoch != e.token) return BIB_ENGINE_STALE;
    const std::string_view method(reinterpret_cast<const char*>(input->method.data), input->method.length);
    if ((method != "GET" && method != "HEAD") || !scalar_utf8(Span(input->resolved_url.data, input->resolved_url.length)))
        return BIB_ENGINE_INVALID;
    const auto slot = std::find_if(leases_.begin(), leases_.end(), [](const auto& l) { return !l.token; });
    if (slot == leases_.end() || !next_lease_) return BIB_ENGINE_LIMIT;
    std::array<std::uint8_t, 16 + 4096> body{};
    put(body, 0, e.token, 8); put(body, 8, method == "HEAD" ? 1u : 0u, 4); put(body, 12, input->resolved_url.length, 4);
    std::copy_n(input->resolved_url.data, input->resolved_url.length, body.begin() + 16);
    std::array<std::uint8_t, headerBytes + 16 + 4096> request{};
    std::array<std::uint8_t, receiptBytes + 32 + 127> response{};
    const auto r = rpc(FOUNDATION_ENGINE_RESOURCE_RESOLVE, e.identity, 0, 0,
        Span(body).first(16 + input->resolved_url.length), request, response);
    if (r.control || r.service) {
        if (!r.record.body.empty()) fail("unexpected rejected resource body");
        return r.control ? provider_control(r.control) : BIB_ENGINE_INVALID;
    }
    const auto metadata = r.record.body;
    if (metadata.size() < 32) fail("truncated copied resource metadata");
    const auto http = get(metadata, 0, 4), mime_length = get(metadata, 4, 4),
        body_length = get(metadata, 8, 8), content_length = get(metadata, 16, 8), kernel_lease = get(metadata, 24, 8);
    if (mime_length != metadata.size() - 32 || !mime_valid(metadata.subspan(32)) ||
        http < 200 || http > 599 || http / 100 == 3 ||
        (http == 200 && !kernel_lease) || (http != 200 && (kernel_lease || body_length || content_length)) ||
        (method == "HEAD" && body_length) || (method == "GET" && body_length != content_length))
        fail("invalid copied resource metadata");
    if (kernel_lease && std::any_of(leases_.begin(), leases_.end(), [&](const auto& held) {
        return held.token && held.kernel_token == kernel_lease;
    })) fail("duplicate live kernel resource lease");
    if (body_length > maximum_response || content_length > maximum_response || body_length > maximum_retained - retained_bytes_) {
        release_kernel(e, kernel_lease);
        return BIB_ENGINE_LIMIT;
    }
    // Allocation failures are known locally. The actual kernel lease is released
    // once; transport uncertainty instead traps before this cleanup can run.
    std::vector<std::uint8_t> copied_body;
    std::vector<std::uint8_t> read_response;
    try {
        copied_body.resize(static_cast<std::size_t>(body_length));
        if (body_length) read_response.resize(receiptBytes + static_cast<std::size_t>(std::min<std::uint64_t>(body_length, maxBodyBytes)));
    } catch (const std::bad_alloc&) { release_kernel(e, kernel_lease); return BIB_ENGINE_LIMIT; }
    catch (...) { release_kernel(e, kernel_lease); return BIB_ENGINE_LIMIT; }
    std::array<std::uint8_t, 20> read_body{};
    std::array<std::uint8_t, headerBytes + 20> read_request{};
    for (std::uint64_t offset = 0; offset < body_length;) {
        const auto count = static_cast<std::uint32_t>(std::min<std::uint64_t>(maxBodyBytes, body_length - offset));
        put(read_body, 0, kernel_lease, 8); put(read_body, 8, offset, 8); put(read_body, 16, count, 4);
        const auto read = rpc(FOUNDATION_ENGINE_RESOURCE_READ, e.identity, 0, 0, read_body, read_request, read_response);
        if (read.control || read.service || read.record.body.size() != count) fail("copied resource read refused or short");
        std::copy(read.record.body.begin(), read.record.body.end(), copied_body.begin() + static_cast<std::ptrdiff_t>(offset));
        offset += count;
    }
    slot->epoch = &e;
    slot->kernel_token = kernel_lease;
    slot->body = std::move(copied_body);
    slot->mime_length = static_cast<std::uint32_t>(mime_length);
    std::copy(metadata.begin() + 32, metadata.end(), slot->mime.begin());
    std::uint64_t local_lease{};
    if (kernel_lease) {
        local_lease = next_lease_;
        next_lease_ = local_lease == UINT64_MAX ? 0 : local_lease + 1;
        slot->token = local_lease;
        ++e.leases;
        retained_bytes_ += body_length;
    }
    // Error MIME is immutable and shared by this profile: no lease-less borrowed
    // span may depend on an unoccupied lease slot that the next resolve reuses.
    static constexpr std::uint8_t error_mime[]{'t','e','x','t','/','p','l','a','i','n'};
    if (!kernel_lease && !std::equal(metadata.begin() + 32, metadata.end(), std::begin(error_mime), std::end(error_mime)))
        fail("unexpected lease-less resource MIME");
    *out = {sizeof(*out), static_cast<std::uint32_t>(http), local_lease,
        {kernel_lease ? slot->mime.data() : error_mime, static_cast<std::uint32_t>(mime_length), 0},
        body_length ? slot->body.data() : nullptr, body_length, content_length};
    return BIB_ENGINE_OK;
}
void CopiedHost::release(Epoch& e, std::uint64_t token) noexcept {
    require_callback();
    if (!token) return;
    const auto found = std::find_if(leases_.begin(), leases_.end(), [&](const auto& l) { return l.token == token && l.epoch == &e; });
    if (found == leases_.end()) return;
    const auto kernel_token = found->kernel_token;
    const auto size = found->body.size();
    // Mark consumed before the import; an import reentry cannot double-release.
    found->token = 0;
    release_kernel(e, kernel_token);
    retained_bytes_ -= size;
    --e.leases;
    *found = {};
    clear_retired(e);
}

void CopiedHost::damage(const BibEngineDamageV1* input) noexcept {
    require_callback();
    if (!input || input->size != sizeof(*input) || input->format != 1 || !input->bytes ||
        input->x < 0 || input->y < 0 || input->width <= 0 || input->height <= 0 ||
        input->x > 800 || input->width > 800 - input->x || input->y > 600 || input->height > 600 - input->y ||
        input->stride_bytes != static_cast<std::uint32_t>(input->width) * 4 ||
        input->length != input->stride_bytes * static_cast<std::uint32_t>(input->height) ||
        !input->frame_revision || input->frame_revision <= producer_revision_) fail("invalid copied damage geometry or producer revision");
    auto* d = document(input->document.service_generation);
    // Resource reservation advances copied transport metadata before provisional
    // navigation commits. The old nonclosed service document may still paint;
    // only its exact committed map entry supplies raster authority.
    if (!d || d->closed || !same(d->identity, input->document) || d->frame == UINT64_MAX ||
        (!d->frame && (input->x || input->y || input->width != 800 || input->height != 600))) fail("invalid copied damage document or first frame");
    for (std::size_t i = 3; i < input->length; i += 4) if (input->bytes[i] != 255) fail("nonopaque copied damage");
    try {
        std::vector<std::uint8_t> body(48 + input->length);
        put(body, 0, 1, 4); put(body, 4, 800, 4); put(body, 8, 600, 4); put(body, 12, input->stride_bytes, 4);
        put(body, 16, static_cast<std::uint32_t>(input->x), 4); put(body, 20, static_cast<std::uint32_t>(input->y), 4);
        put(body, 24, static_cast<std::uint32_t>(input->width), 4); put(body, 28, static_cast<std::uint32_t>(input->height), 4);
        put(body, 32, d->frame, 8); put(body, 40, d->frame + 1, 8);
        std::copy_n(input->bytes, input->length, body.begin() + 48);
        std::vector<std::uint8_t> request(headerBytes + body.size());
        std::array<std::uint8_t, receiptBytes> response{};
        const auto r = rpc(FOUNDATION_ENGINE_FRAME_COMMIT, d->identity, 0, 0, body, request, response);
        if (r.control || r.service || !r.record.body.empty()) fail("copied frame commit refused");
    } catch (...) { fail("copied damage allocation failure"); }
    ++d->frame;
    producer_revision_ = input->frame_revision;
}
void CopiedHost::timer(double delay, std::uint32_t armed) noexcept {
    require_callback();
    if (!std::isfinite(delay) || delay < 0 || armed > 1) fail("invalid copied timer");
    const double clamped = armed ? std::min(delay, 86400000.0) : 0.0;
    std::array<std::uint8_t, 12> body{};
    put(body, 0, std::bit_cast<std::uint64_t>(clamped), 8); put(body, 8, armed, 4);
    importing_ = true;
    std::int32_t status{};
    try { status = import_(context_, FOUNDATION_RETAINED_ENGINE_HOST_TIMER, body.data(), static_cast<std::uint32_t>(body.size()), nullptr, 0); }
    catch (...) { fail("copied timer import exception"); }
    importing_ = false;
    if (status) fail("copied timer notification refused");
}
void CopiedHost::wake() noexcept {
    if (metadata_only_.load(std::memory_order_acquire) || poisoned() || !import_) fail("copied wake on terminal/metadata-only host");
    // No owner bookkeeping, reentry, pump or service dispatch: import only queues.
    std::int32_t status{};
    try { status = import_(context_, FOUNDATION_RETAINED_ENGINE_HOST_WAKE, nullptr, 0, nullptr, 0); }
    catch (...) { fail("copied wake import exception"); }
    if (status) fail("copied wake notification refused");
}

void BIB_ENGINE_CALL CopiedHost::c_wake(void* p) noexcept { static_cast<CopiedHost*>(p)->wake(); }
void BIB_ENGINE_CALL CopiedHost::c_timer(void* p, double delay, std::uint32_t armed) noexcept { static_cast<CopiedHost*>(p)->timer(delay, armed); }
void BIB_ENGINE_CALL CopiedHost::c_damage(void* p, const BibEngineDamageV1* d) noexcept { static_cast<CopiedHost*>(p)->damage(d); }
std::uint32_t BIB_ENGINE_CALL CopiedHost::c_enter(void* p) noexcept { return static_cast<CopiedHost*>(p)->enter_engine(); }
void BIB_ENGINE_CALL CopiedHost::c_leave(void* p) noexcept { static_cast<CopiedHost*>(p)->leave_engine(); }
std::uint64_t BIB_ENGINE_CALL CopiedHost::c_begin(void* p, const BibEngineDocumentV1* d) noexcept { return static_cast<CopiedHost*>(p)->begin_document(d); }
void BIB_ENGINE_CALL CopiedHost::c_close(void* p, std::uint64_t generation) noexcept { static_cast<CopiedHost*>(p)->close_document(generation); }
std::uint32_t BIB_ENGINE_CALL CopiedHost::c_submit(void* p, std::uint64_t generation, const BibEngineBytesV1* b, std::uint32_t source) noexcept {
    static_cast<CopiedHost*>(p)->require_callback();
    if (!b) return service_invalid;
    return static_cast<CopiedHost*>(p)->service(FOUNDATION_ENGINE_SUBMIT, generation, 0, b, source);
}
std::uint32_t BIB_ENGINE_CALL CopiedHost::c_cancel(void* p, std::uint64_t generation, std::uint64_t sequence) noexcept {
    return static_cast<CopiedHost*>(p)->service(FOUNDATION_ENGINE_CANCEL, generation, sequence, nullptr, 0);
}
std::uint32_t BIB_ENGINE_CALL CopiedHost::c_ack(void* p, std::uint64_t generation, std::uint64_t sequence) noexcept {
    return static_cast<CopiedHost*>(p)->service(FOUNDATION_ENGINE_STAGE_ACK, generation, sequence, nullptr, 0);
}
std::int32_t BIB_ENGINE_CALL CopiedHost::c_begin_epoch(void* p, const BibEngineDocumentV1* d, BibEngineResourceEpochV1* out) noexcept {
    return static_cast<CopiedHost*>(p)->begin_epoch(d, out);
}
void BIB_ENGINE_CALL CopiedHost::c_retire_epoch(void* p, std::uint64_t epoch_token) noexcept { static_cast<CopiedHost*>(p)->retire_epoch(epoch_token); }
std::int32_t BIB_ENGINE_CALL CopiedHost::c_resolve(void* p, const BibEngineResourceRequestV1* input, BibEngineResourceResponseV1* out) noexcept {
    auto& e = *static_cast<Epoch*>(p); return e.owner->resolve(e, input, out);
}
void BIB_ENGINE_CALL CopiedHost::c_release(void* p, std::uint64_t token) noexcept { auto& e = *static_cast<Epoch*>(p); e.owner->release(e, token); }
} // namespace bib::copied
