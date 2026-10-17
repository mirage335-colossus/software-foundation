// SPDX-License-Identifier: CC0-1.0
#pragma once

// Synthetic transport fixtures only. No retained engine, SDK, DOM execution,
// semantic publication, artifact admission or runtime qualification is claimed.
#include "../gui/shared/appended_engine_owner.hpp"
#include "../gui/shared/appended_engine_abi.h"
#include "../gui/shared/engine_document_actions_profile.hpp"
#include "../gui/shared/engine_document_mailbox.hpp"

#include <algorithm>
#include <array>
#include <cstdint>
#include <iostream>
#include <memory>
#include <span>
#include <stdexcept>
#include <string>

namespace document_actions_fixture {
using namespace foundation::appended;
namespace doc = engine_document;
namespace actions = engine_document_actions;
namespace editor = engine_editor;
using Span = std::span<const std::uint8_t>;
inline std::size_t assertions{};
inline void check(bool value, const char* message) {
    ++assertions;
    if (!value) throw std::runtime_error(message);
}
inline void put(std::span<std::uint8_t> out, std::size_t at, std::uint64_t value, unsigned width) {
    check(width <= 8 && at <= out.size() && width <= out.size() - at, "fixture write bounds");
    for (unsigned i = 0; i < width; ++i) out[at + i] = static_cast<std::uint8_t>(value >> (8 * i));
}
inline std::uint64_t get(Span bytes, std::size_t at, unsigned width) {
    check(width <= 8 && at <= bytes.size() && width <= bytes.size() - at, "fixture read bounds");
    std::uint64_t value{};
    for (unsigned i = 0; i < width; ++i) value |= std::uint64_t(bytes[at + i]) << (8 * i);
    return value;
}
inline EngineDocumentTarget target(EngineIdentity id) {
    return {id.worker_epoch, id.application_instance, id.document_sequence, id.service_generation};
}
inline EngineIdentity identity(EngineDocumentTarget id) {
    return {id.worker_epoch, id.application_instance, id.document_sequence, id.service_generation};
}
inline Package package() {
    Package p;
    p.application = {"org.example.document-actions", "Document actions transport fixture", "1.0.0"};
    p.web = {true, "web/index.html", {}};
    p.capabilities = {"foundation.startup.v1"};
    p.package_sha256 = p.payload_id = p.kernel_sha256 = std::string(64, '1');
    const std::string startup = "{\"kind\":\"foundation-appended-startup\",\"primary\":\"web\",\"schema_version\":1}";
    p.files = {{"web/.foundation/startup-v1.json", "web", "application/json", std::string(64, '2'),
        Bytes(startup.begin(), startup.end())}, {"web/index.html", "web", "text/html", std::string(64, '3'), {}}};
    return p;
}
inline actions::EngineDocumentActionsProfileFacts profile() {
    actions::EngineDocumentActionsProfileFacts f;
    f.enabled = true; f.kind = actions::ProfileKind::document_actions; f.name = actions::kProfileName;
    f.provider_abi_major = 1; f.provider_abi_minor = 1; f.host_abi_major = 1;
#if defined(_WIN32) && (defined(_M_X64) || defined(__x86_64__))
    f.target_system = BIB_ENGINE_TARGET_WINDOWS; f.target_processor = BIB_ENGINE_CPU_X86_64;
#elif defined(__linux__) && defined(__aarch64__)
    f.target_system = BIB_ENGINE_TARGET_LINUX; f.target_processor = BIB_ENGINE_CPU_AARCH64;
#elif defined(__linux__) && defined(__x86_64__)
    f.target_system = BIB_ENGINE_TARGET_LINUX; f.target_processor = BIB_ENGINE_CPU_X86_64;
#else
    throw std::runtime_error("document-actions fixture requires a supported native 64-bit target");
#endif
    f.pointer_bits = sizeof(void*) * 8; f.lifetime = BIB_ENGINE_LIFETIME_PROCESS; f.maximum_starts = 1;
    f.viewport_width = 800; f.viewport_height = 600;
    f.provider_capabilities = actions::kProviderCapabilities; f.surface_capabilities = actions::kSurfaceCapabilities;
    f.surface_protocol_version = 2; f.editor_protocol_version = BIB_ENGINE_EDITOR_PROTOCOL_VERSION;
    f.base_header_sha256 = doc::kBaseHeaderSha256; f.document_header_sha256 = doc::kExtensionHeaderSha256;
    f.document_contract_sha256 = doc::kContractSha256; f.document_catalog_sha256 = doc::kCatalogSha256;
    f.physical_catalog_sha256 = doc::kPhysicalCatalogSha256;
    f.editor_header_sha256 = editor::kHeaderSha256; f.editor_contract_sha256 = editor::kContractSha256;
    f.editor_catalog_sha256 = editor::kCatalogSha256; f.editor_schema_sha256 = editor::kSchema;
    f.actions_header_sha256 = actions::kHeaderSha256; f.contract_sha256 = actions::kContractSha256;
    f.catalog_sha256 = actions::kCatalogSha256; f.schema_sha256 = actions::kSchema; f.ack_schema_sha256 = actions::kAckSchema;
    f.build_sha256.fill(0x51); f.source_recipe_sha256.fill(0x73); // Synthetic matching pins.
    f.queries = actions::kQueries; f.commands = actions::kCommands; f.query_count = 2; f.command_count = 9;
    return f;
}
inline doc::EngineDocumentProfileFacts legacy_profile() {
    const auto a = profile(); doc::EngineDocumentProfileFacts f;
    f.enabled = true; f.kind = doc::ProfileKind::physical; f.name = doc::kPhysicalProfileName;
    f.provider_abi_major = 1; f.provider_abi_minor = 1; f.host_abi_major = 1;
    f.target_system = a.target_system; f.target_processor = a.target_processor; f.pointer_bits = a.pointer_bits;
    f.lifetime = a.lifetime; f.maximum_starts = 1; f.viewport_width = 800; f.viewport_height = 600;
    f.provider_capabilities = doc::kPhysicalCapabilities;
    f.base_header_sha256 = doc::kBaseHeaderSha256; f.extension_header_sha256 = doc::kExtensionHeaderSha256;
    f.contract_sha256 = doc::kContractSha256; f.catalog_sha256 = doc::kCatalogSha256;
    f.physical_catalog_sha256 = doc::kPhysicalCatalogSha256; f.build_sha256 = a.build_sha256;
    f.source_recipe_sha256 = a.source_recipe_sha256;
    f.queries = doc::kQueries; f.commands = doc::kCommands; f.query_count = 1; f.command_count = 2;
    return f;
}
inline EngineOwnerConfiguration configuration() {
    EngineOwnerConfiguration c;
    c.worker_epoch = UINT64_C(0x8000000000000017);
    c.application_instance = UINT64_C(0x8000000000000044);
    c.document_actions_profile = profile();
    c.abandon_closed_document_outcomes = true;
    return c;
}
inline Bytes ndv2(EngineDocumentTarget id, std::uint64_t sequence, unsigned kind, std::uint64_t nested, std::size_t length) {
    Bytes bytes(length); check(length >= 48, "NDV2 fixture extent");
    std::copy_n("NDV2", 4, bytes.begin()); bytes[4] = 2; bytes[6] = static_cast<std::uint8_t>(kind);
    put(bytes, 8, id.application_instance, 8); put(bytes, 16, id.service_generation, 8);
    put(bytes, 24, id.document_sequence, 8); put(bytes, 32, sequence, 8); put(bytes, 40, nested, 8);
    return bytes;
}
inline Bytes dav1(EngineDocumentTarget id, std::uint64_t sequence, unsigned kind, std::size_t length) {
    Bytes bytes(length); check(length >= 64, "DAV1 fixture extent");
    std::copy_n("DAV1", 4, bytes.begin()); bytes[4] = 1; bytes[6] = static_cast<std::uint8_t>(kind);
    put(bytes, 8, length, 4); put(bytes, 16, id.worker_epoch, 8); put(bytes, 24, id.application_instance, 8);
    put(bytes, 32, id.document_sequence, 8); put(bytes, 40, id.service_generation, 8);
    put(bytes, 48, sequence, 8); put(bytes, 56, 73, 8);
    return bytes;
}
inline EngineDocumentWork work(EngineDocumentTarget id, std::uint64_t sequence, bool body = true) {
    EngineDocumentWork value;
    value.target = id; value.request_sequence = sequence;
    value.kind = body ? EngineDocumentWorkKind::body_action : EngineDocumentWorkKind::form_action;
    value.operation = body ? BIB_ENGINE_COMMAND_DOCUMENT_ACTION_V1 : BIB_ENGINE_COMMAND_FORM_ACTION_V2;
    value.required_reply_capacity = actions::kReplyCapacity; value.schema_sha256 = body ? actions::kSchema : doc::kSchema;
    if (body) {
        value.payload = dav1(id, sequence, 1, 128);
        put(value.payload, 64, id.application_instance, 8); put(value.payload, 72, id.service_generation, 8);
        put(value.payload, 80, 1, 8); put(value.payload, 96, 1, 8); // Focus(node1), displayed revision1.
    } else {
        value.payload = ndv2(id, sequence, 2, 0, 81);
        put(value.payload, 49, id.application_instance, 8); put(value.payload, 57, id.service_generation, 8);
        put(value.payload, 65, 1, 8); put(value.payload, 73, 1, 8);
    }
    return value;
}
inline Bytes completion(const EngineDocumentWork& value) {
    if (value.kind == EngineDocumentWorkKind::body_action) {
        auto bytes = dav1(value.target, value.request_sequence, 2, 72);
        bytes[64] = 2; bytes[65] = 6; // Canonical pre-effect unsupported semantic result.
        return bytes;
    }
    auto bytes = ndv2(value.target, value.request_sequence, 5, 0, 52);
    bytes[48] = 1; bytes[49] = 6; // Canonical form rejection; still consumed native command.
    return bytes;
}
inline Bytes ack_raw(std::uint64_t original, unsigned code = 0) {
    Bytes bytes(16); put(bytes, 0, original, 8); put(bytes, 8, code, 4); return bytes;
}
inline Bytes record(std::uint32_t operation, EngineIdentity id, Span body = {}, std::uint64_t transfer = 0) {
    Bytes bytes(72 + body.size()); std::copy_n("FKB1", 4, bytes.begin());
    put(bytes, 4, 1, 2); put(bytes, 6, operation, 2); put(bytes, 8, bytes.size(), 4);
    put(bytes, 16, id.worker_epoch, 8); put(bytes, 24, id.application_instance, 8);
    put(bytes, 32, id.document_sequence, 8); put(bytes, 40, id.service_generation, 8);
    put(bytes, 48, transfer, 8); put(bytes, 64, body.size(), 4); std::copy(body.begin(), body.end(), bytes.begin() + 72);
    return bytes;
}
struct Reply {
    EngineIdentity id;
    std::uint64_t transfer{};
    std::uint32_t control{}, service{};
    Bytes bytes;
    Span body() const { return Span(bytes).subspan(80); }
};
inline Reply call(EngineOwner& owner, std::uint32_t operation, EngineIdentity id, Span body = {},
        std::uint64_t transfer = 0, std::size_t capacity = 1048800) {
    const auto request = record(operation, id, body, transfer); Bytes bytes(capacity, 0xa5);
    const auto length = owner.dispatch(operation, request, bytes);
    check(length >= 80 && static_cast<std::size_t>(length) <= bytes.size(), "incomplete copied receipt");
    bytes.resize(static_cast<std::size_t>(length));
    check(get(bytes, 6, 2) == (operation | 0x8000) && get(bytes, 8, 4) == bytes.size() &&
        get(bytes, 64, 4) == bytes.size() - 72, "copied receipt framing");
    return {{get(bytes, 16, 8), get(bytes, 24, 8), get(bytes, 32, 8), get(bytes, 40, 8)}, get(bytes, 48, 8),
        static_cast<std::uint32_t>(get(bytes, 72, 4)), static_cast<std::uint32_t>(get(bytes, 76, 4)), std::move(bytes)};
}
inline void ok(const Reply& r) { check(!r.control && !r.service, "Owner rejected valid fixture operation"); }
inline Bytes claim_bytes(const EngineDocumentDispatch& d) {
    Bytes bytes(16); put(bytes, 0, static_cast<std::uint32_t>(d.work.kind), 4); put(bytes, 8, d.work.request_sequence, 8); return bytes;
}
inline Bytes result_bytes(const EngineDocumentDispatch& d, Span raw, std::int32_t status = 0,
        std::uint32_t disposition = 1, bool handled = false) {
    Bytes bytes(40 + raw.size()); put(bytes, 0, static_cast<std::uint32_t>(d.work.kind), 4);
    put(bytes, 8, d.work.request_sequence, 8); put(bytes, 16, static_cast<std::uint32_t>(status), 4);
    put(bytes, 20, disposition, 4); put(bytes, 24, raw.size(), 4); put(bytes, 28, handled, 4);
    std::copy(raw.begin(), raw.end(), bytes.begin() + 40); return bytes;
}
struct OwnerFixture {
    std::shared_ptr<EngineOwner> owner;
    EngineIdentity id{};
    explicit OwnerFixture(EngineOwnerConfiguration config = configuration()) {
        id = {config.worker_epoch, config.application_instance, 0, 0};
        owner = std::make_shared<EngineOwner>(package(), std::move(config));
        ok(call(*owner, 1, id)); id.document_sequence = UINT64_C(0x8000000000000001);
        const auto begun = call(*owner, 4, id); ok(begun); id = begun.id;
    }
    EngineDocumentWork next(bool body = true) {
        const auto sequence = owner->reserve_document_sequence(); check(bool(sequence), "ordinary reservation unavailable");
        return work(target(id), *sequence, body);
    }
    EngineDocumentAdmission stage(EngineDocumentWork value) {
        const auto a = owner->stage_document_work(std::move(value));
        check(a.code == EngineDocumentAdmissionCode::admitted && a.ticket, "valid ordinary work rejected"); return a;
    }
    EngineDocumentDispatch peek() {
        const auto r = call(*owner, 27, id); ok(r); check(r.transfer && r.body().size() >= 56, "document mailbox empty");
        EngineDocumentDispatch d; d.transfer = r.transfer; d.work.target = target(r.id);
        d.work.kind = static_cast<EngineDocumentWorkKind>(get(r.body(), 0, 4)); d.work.operation = static_cast<std::uint32_t>(get(r.body(), 4, 4));
        d.work.request_sequence = get(r.body(), 8, 8); std::copy_n(r.body().begin() + 16, 32, d.work.schema_sha256.begin());
        d.work.required_reply_capacity = static_cast<std::uint32_t>(get(r.body(), 48, 4));
        check(get(r.body(), 52, 4) == r.body().size() - 56, "mailbox payload length");
        d.work.payload.assign(r.body().begin() + 56, r.body().end()); return d;
    }
    void claim(const EngineDocumentDispatch& d) { ok(call(*owner, 29, identity(d.work.target), claim_bytes(d), d.transfer)); }
    void turn(const EngineDocumentDispatch& d) {
        ok(call(*owner, 2, identity(d.work.target), {}, d.transfer)); ok(call(*owner, 3, identity(d.work.target), {}, d.transfer));
    }
    void settle(const EngineDocumentDispatch& d, Span bytes) { ok(call(*owner, 28, identity(d.work.target), bytes, d.transfer)); }
    void finish(EngineDocumentAdmission a) {
        const auto d = peek(); claim(d); turn(d); settle(d, result_bytes(d, completion(d.work)));
        check(bool(owner->document_outcome(a.ticket)), "ordinary completion missing");
    }
    EngineDocumentAdmission ack(const EngineDocumentWork& original, bool body) {
        const auto a = body ? owner->stage_document_body_action_ack(original.target, original.request_sequence) :
            owner->stage_document_action_ack(original.target, original.request_sequence);
        check(a.code == EngineDocumentAdmissionCode::admitted && a.ticket, "metadata ACK rejected"); return a;
    }
    void finish_ack(EngineDocumentAdmission a, const EngineDocumentWork& original, bool body, unsigned code = 0) {
        const auto d = peek(); const auto kind = body ? EngineDocumentWorkKind::body_action_ack : EngineDocumentWorkKind::action_ack;
        check(d.work.kind == kind && d.work.operation == (body ? 11u : 7u) && d.work.target == original.target &&
            d.work.request_sequence > original.request_sequence && d.work.payload.size() == 8 &&
            get(d.work.payload, 0, 8) == original.request_sequence && d.work.required_reply_capacity == 16 &&
            d.work.schema_sha256 == (body ? actions::kAckSchema : doc::kAckSchema), "metadata ACK family/identity/schema/capacity changed");
        claim(d); check(call(*owner, 2, identity(d.work.target), {}, d.transfer).control != 0, "metadata ACK opened Host turn");
        settle(d, result_bytes(d, ack_raw(original.request_sequence, code)));
        check(bool(owner->document_outcome(a.ticket)), "ACK completion missing");
    }
};
} // namespace document_actions_fixture
