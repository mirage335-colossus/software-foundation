// A deliberately synthetic small DSO, never an eligible retained engine.
#include <foundation/appended/engine_provider_document_v2.h>
#include "engine_document_profile.hpp"

#include <algorithm>
#include <cstdlib>
#include <fstream>
#include <stdexcept>

#ifndef LOADER_FIXTURE_CASE
#define LOADER_FIXTURE_CASE 0
#endif
#ifndef LOADER_FIXTURE_PROFILE_KIND
#define LOADER_FIXTURE_PROFILE_KIND 1
#endif
#if LOADER_FIXTURE_PROFILE_KIND == 4
#include "engine_document_actions_profile.hpp"
#elif LOADER_FIXTURE_PROFILE_KIND != 1
#error "The loader fixture requires an explicit pixel1 or document-actions4 profile"
#endif
#if LOADER_FIXTURE_CASE >= 6 && LOADER_FIXTURE_PROFILE_KIND != 4
#error "Additional loader limit cases require the explicit document-actions4 profile"
#endif
namespace {
unsigned getters{}, starts{};
[[maybe_unused]] int32_t BIB_ENGINE_CALL start(const BibEngineHostV1*, const BibEngineStartV1*, BibEngineStartResultV1*) {
    ++starts; return BIB_ENGINE_UNSUPPORTED;
}
[[maybe_unused]] int32_t BIB_ENGINE_CALL advance(const BibEngineAdvanceV1*) { return BIB_ENGINE_UNSUPPORTED; }
[[maybe_unused]] int32_t BIB_ENGINE_CALL current(uint64_t, BibEngineDocumentV1*) { return BIB_ENGINE_UNSUPPORTED; }
[[maybe_unused]] int32_t BIB_ENGINE_CALL command(const BibEngineCommandV1*, BibEngineReplyBufferV1*, BibEngineCommandResultV1*) { return BIB_ENGINE_UNSUPPORTED; }
[[maybe_unused]] int32_t BIB_ENGINE_CALL query(const BibEngineQueryV1*, BibEngineReplyBufferV1*, BibEngineQueryResultV1*) { return BIB_ENGINE_UNSUPPORTED; }
[[maybe_unused]] int32_t BIB_ENGINE_CALL deliver(const BibEngineDocumentV1*, const BibEngineBytesV1*) { return BIB_ENGINE_UNSUPPORTED; }
[[maybe_unused]] uint32_t BIB_ENGINE_CALL ack(const BibEngineDocumentV1*) { return 0; }
[[maybe_unused]] int32_t BIB_ENGINE_CALL dispose(uint64_t, uint64_t) { return BIB_ENGINE_UNSUPPORTED; }
}
extern "C" BIB_ENGINE_EXPORT unsigned bib_loader_fixture_getters() { return getters; }
extern "C" BIB_ENGINE_EXPORT unsigned bib_loader_fixture_starts() { return starts; }

#if LOADER_FIXTURE_CASE != 1
extern "C" BIB_ENGINE_EXPORT int32_t BIB_ENGINE_CALL bib_engine_get_provider_v1(
        uint32_t major, uint32_t minor, uint32_t capacity, BibEngineProviderV1* output) {
    ++getters;
    if (major != 1 || minor != 1 || capacity != sizeof(BibEngineProviderV1) || !output)
        return BIB_ENGINE_INVALID;
#if LOADER_FIXTURE_CASE == 3
    return BIB_ENGINE_UNSUPPORTED;
#elif LOADER_FIXTURE_CASE == 4
    throw std::runtime_error("synthetic broken C ABI getter");
#else
    *output = {};
    output->size = sizeof(*output); output->abi_major = 1; output->abi_minor = 1;
    auto& build = output->build;
    build.size = sizeof(build); build.layout_revision = BIB_ENGINE_LAYOUT_V1;
#if defined(_WIN32)
    build.target_system = BIB_ENGINE_TARGET_WINDOWS;
#else
    build.target_system = BIB_ENGINE_TARGET_LINUX;
#endif
#if defined(__aarch64__)
    build.target_processor = BIB_ENGINE_CPU_AARCH64;
#else
    build.target_processor = BIB_ENGINE_CPU_X86_64;
#endif
    build.pointer_bits = sizeof(void*) * 8;
    build.lifetime = BIB_ENGINE_LIFETIME_PROCESS; build.maximum_starts = 1;
    build.fixed_viewport_width = 800; build.fixed_viewport_height = 600;
#if LOADER_FIXTURE_PROFILE_KIND == 4
    build.capabilities = foundation::appended::engine_document_actions::kProviderCapabilities;
    std::copy(foundation::appended::engine_document_actions::kContractSha256.begin(),
        foundation::appended::engine_document_actions::kContractSha256.end(), build.contract_header_sha256);
#else
    build.capabilities = foundation::appended::engine_document::kPixelCapabilities;
    std::copy(foundation::appended::engine_document::kContractSha256.begin(),
        foundation::appended::engine_document::kContractSha256.end(), build.contract_header_sha256);
#endif
    std::fill(std::begin(build.build_identity_sha256), std::end(build.build_identity_sha256), 0x41);
    std::fill(std::begin(build.source_recipe_sha256), std::end(build.source_recipe_sha256), 0x42);
#if LOADER_FIXTURE_PROFILE_KIND == 4
    output->limits = {sizeof(BibEngineLimitsV1), BIB_ENGINE_EDITOR_MAX_WIRE_BYTES,
        foundation::appended::engine_editor::kQueryRequestMaximum, BIB_ENGINE_DOCUMENT_ACTIONS_V1_REPLY_CAPACITY,
        65536, 8, 64, 0, 64ULL * 1024 * 1024, 128ULL * 1024 * 1024};
#else
    output->limits = {sizeof(BibEngineLimitsV1), 65536, 65536, BIB_ENGINE_DOCUMENT_V2_REPLY_CAPACITY,
        65536, 8, 64, 0, 64ULL * 1024 * 1024, 128ULL * 1024 * 1024};
#endif
    output->start = start; output->advance = advance; output->current_document = current;
    output->command = command; output->query = query; output->deliver_services = deliver;
    output->collect_service_ack = ack; output->dispose_retired_service_document = dispose;
#if LOADER_FIXTURE_CASE == 2
    output->abi_minor = 0; // A legacy table cannot silently satisfy new1795.
#elif LOADER_FIXTURE_CASE == 5
    if (const char* path = std::getenv("BIB_LOADER_FIXTURE_MUTATE_NOTICE"))
        std::ofstream(path, std::ios::binary | std::ios::app).put('!');
#elif LOADER_FIXTURE_CASE == 6
    --output->limits.maximum_command_bytes;
#elif LOADER_FIXTURE_CASE == 7
    --output->limits.maximum_query_bytes;
#elif LOADER_FIXTURE_CASE == 8
    --output->limits.maximum_reply_bytes;
#elif LOADER_FIXTURE_CASE == 9
    ++output->limits.maximum_command_bytes;
    ++output->limits.maximum_query_bytes;
    ++output->limits.maximum_reply_bytes;
#endif
    return BIB_ENGINE_OK;
#endif
}
#endif
