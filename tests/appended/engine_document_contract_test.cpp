#include <foundation/appended/engine_provider.h>

#include <array>
#include <cstddef>
#include <cstdint>
#include <type_traits>

// Capture the base table layout before including the additive source contract.
// These comparisons stay valid across native and Wasm pointer widths.
namespace base_layout {
constexpr std::array sizes{sizeof(BibEngineHostV1),sizeof(BibEngineProviderV1),sizeof(BibEngineCommandV1),
    sizeof(BibEngineQueryV1),sizeof(BibEngineCommandResultV1),sizeof(BibEngineQueryResultV1)};
constexpr std::array alignments{alignof(BibEngineHostV1),alignof(BibEngineProviderV1),alignof(BibEngineCommandV1),
    alignof(BibEngineQueryV1),alignof(BibEngineCommandResultV1),alignof(BibEngineQueryResultV1)};
constexpr std::array offsets{offsetof(BibEngineHostV1,context),offsetof(BibEngineHostV1,retire_resource_epoch),
    offsetof(BibEngineProviderV1,build),offsetof(BibEngineProviderV1,start),offsetof(BibEngineProviderV1,command),
    offsetof(BibEngineProviderV1,query),offsetof(BibEngineProviderV1,dispose_retired_service_document)};
using Command = decltype(BibEngineProviderV1{}.command);
using Query = decltype(BibEngineProviderV1{}.query);
using BeginDocument = decltype(BibEngineHostV1{}.begin_service_document);
}

#include <foundation/appended/engine_provider_document_v2.h>
#include "shared/engine_document_profile.hpp"
#include "shared/engine_document_work.hpp"

#include <algorithm>
#include <iostream>
#include <limits>
#include <span>
#include <stdexcept>
#include <string>
#include <string_view>
#include <vector>

static_assert(BIB_ENGINE_ABI_MAJOR == 1 && BIB_ENGINE_ABI_MINOR == 0);
static_assert(BIB_ENGINE_DOCUMENT_V2_ABI_MAJOR == 1 && BIB_ENGINE_DOCUMENT_V2_ABI_MINOR == 1);
static_assert(BIB_ENGINE_DOCUMENT_V2_HOST_ABI_MAJOR == 1 && BIB_ENGINE_DOCUMENT_V2_HOST_ABI_MINOR == 0);
static_assert(BIB_ENGINE_COMMAND_KEY == 1 && BIB_ENGINE_COMMAND_COMPOSITION == 2 && BIB_ENGINE_COMMAND_FOCUS == 3 &&
    BIB_ENGINE_COMMAND_SEMANTIC_ACTION == 4 && BIB_ENGINE_COMMAND_POINTER == 5);
static_assert(BIB_ENGINE_QUERY_SEMANTIC_SNAPSHOT == 1 && BIB_ENGINE_QUERY_EDITOR_FLAGS == 2);
static_assert(BIB_ENGINE_CAP_SEMANTIC_SNAPSHOT_V2 == 512 && BIB_ENGINE_CAP_FORM_ACTION_V2 == 1024);
static_assert(BIB_ENGINE_QUERY_DOCUMENT_FORMS_V2 == 3 && BIB_ENGINE_COMMAND_FORM_ACTION_V2 == 6 &&
    BIB_ENGINE_COMMAND_ACK_FORM_ACTION_V2 == 7);
static_assert(BIB_ENGINE_DOCUMENT_V2_QUERY_BYTES == 48 && BIB_ENGINE_DOCUMENT_V2_MAX_ACTION_BYTES == 6246 &&
    BIB_ENGINE_DOCUMENT_V2_REPLY_CAPACITY == 1048576);
static_assert(BIB_ENGINE_DOCUMENT_V2_ACK_REQUEST_BYTES == 8 && BIB_ENGINE_DOCUMENT_V2_ACK_REPLY_CAPACITY == 16 &&
    BIB_ENGINE_DOCUMENT_V2_ACK_RESULT_BYTES == 16);
static_assert(BIB_ENGINE_DOCUMENT_V2_ACK_SEQUENCE_OFFSET == 0 && BIB_ENGINE_DOCUMENT_V2_ACK_CODE_OFFSET == 8 &&
    BIB_ENGINE_DOCUMENT_V2_ACK_RESERVED_OFFSET == 12);
static_assert(BIB_ENGINE_DOCUMENT_V2_ACK_RETIRED == 0 && BIB_ENGINE_DOCUMENT_V2_ACK_ALREADY_RETIRED == 1 &&
    BIB_ENGINE_DOCUMENT_V2_ACK_STALE == 2);
static_assert(BIB_ENGINE_DOCUMENT_V2_MAX_ORDINARY_SEQUENCE == UINT64_MAX - 1 &&
    BIB_ENGINE_DOCUMENT_V2_MAX_ACK_SEQUENCE == UINT64_MAX);
static_assert(base_layout::sizes == std::array{sizeof(BibEngineHostV1),sizeof(BibEngineProviderV1),sizeof(BibEngineCommandV1),
    sizeof(BibEngineQueryV1),sizeof(BibEngineCommandResultV1),sizeof(BibEngineQueryResultV1)});
static_assert(base_layout::alignments == std::array{alignof(BibEngineHostV1),alignof(BibEngineProviderV1),alignof(BibEngineCommandV1),
    alignof(BibEngineQueryV1),alignof(BibEngineCommandResultV1),alignof(BibEngineQueryResultV1)});
static_assert(base_layout::offsets == std::array{offsetof(BibEngineHostV1,context),offsetof(BibEngineHostV1,retire_resource_epoch),
    offsetof(BibEngineProviderV1,build),offsetof(BibEngineProviderV1,start),offsetof(BibEngineProviderV1,command),
    offsetof(BibEngineProviderV1,query),offsetof(BibEngineProviderV1,dispose_retired_service_document)});
static_assert(std::is_same_v<base_layout::Command,decltype(BibEngineProviderV1{}.command)> &&
    std::is_same_v<base_layout::Query,decltype(BibEngineProviderV1{}.query)> &&
    std::is_same_v<base_layout::BeginDocument,decltype(BibEngineHostV1{}.begin_service_document)>);
static_assert(std::is_standard_layout_v<BibEngineHostV1> && std::is_trivially_copyable_v<BibEngineHostV1> &&
    std::is_standard_layout_v<BibEngineProviderV1> && std::is_trivially_copyable_v<BibEngineProviderV1>);

namespace {
using namespace foundation::appended;
namespace profile = foundation::appended::engine_document;
void require(bool value, const char* message) {
    if (!value) throw std::runtime_error(message);
}
std::string hex(const profile::Digest& value) {
    constexpr char digits[] = "0123456789abcdef";
    std::string result;
    for (const auto byte : value) { result += digits[byte >> 4]; result += digits[byte & 15]; }
    return result;
}
bool nonzero(const profile::Digest& value) {
    return std::any_of(value.begin(),value.end(),[](auto byte) { return byte != 0; });
}
profile::EngineDocumentProfileFacts pixel_profile() {
    profile::EngineDocumentProfileFacts result;
    result.enabled = true; result.kind = profile::ProfileKind::pixel; result.name = profile::kPixelProfileName;
    result.provider_abi_major = 1; result.provider_abi_minor = 1; result.host_abi_major = 1; result.host_abi_minor = 0;
    result.target_system = BIB_ENGINE_TARGET_LINUX; result.target_processor = BIB_ENGINE_CPU_X86_64; result.pointer_bits = 64;
    result.lifetime = BIB_ENGINE_LIFETIME_PROCESS; result.maximum_starts = 1;
    result.viewport_width = 800; result.viewport_height = 600; result.provider_capabilities = 1795;
    result.base_header_sha256 = profile::kBaseHeaderSha256; result.extension_header_sha256 = profile::kExtensionHeaderSha256;
    result.contract_sha256 = profile::kContractSha256; result.catalog_sha256 = profile::kCatalogSha256;
    result.build_sha256[0] = 1; result.source_recipe_sha256[31] = 2;
    result.queries = profile::kQueries; result.commands = profile::kCommands; result.query_count = 1; result.command_count = 2;
    return result;
}
void source_contract_facts() {
    static_assert(profile::kPixelCapabilities == 1795 && profile::kPhysicalCapabilities == 2003);
    static_assert(profile::kQueryCopiedReplyCapacity == 1048672 && profile::kFormCopiedReplyCapacity == 1048680 &&
        profile::kAckCopiedReplyCapacity == 120);
    static_assert(static_cast<std::uint32_t>(profile::ProfileKind::disabled) == 0 &&
        static_cast<std::uint32_t>(profile::ProfileKind::pixel) == 1 && static_cast<std::uint32_t>(profile::ProfileKind::physical) == 2);
    require(hex(profile::kBaseHeaderSha256) == "a8e89da85d34b29a4d1bc454495791fa604b81e3477e48ce8ca902e4333a9c0d" &&
        hex(profile::kSchema) == BIB_ENGINE_DOCUMENT_V2_SCHEMA_SHA256_HEX &&
        hex(profile::kAckSchema) == BIB_ENGINE_DOCUMENT_V2_ACK_SCHEMA_SHA256_HEX,
        "Document profile lost its canonical base or wire-schema identity");
    for (const auto* digest : {&profile::kBaseHeaderSha256,&profile::kExtensionHeaderSha256,&profile::kContractSha256,
            &profile::kCatalogSha256,&profile::kPhysicalCatalogSha256,&profile::kSchema,&profile::kAckSchema})
        require(nonzero(*digest),"Source contract supplied an unpinned zero digest");
    require(profile::kBaseHeaderSha256 != profile::kExtensionHeaderSha256 &&
        profile::kExtensionHeaderSha256 != profile::kContractSha256 && profile::kContractSha256 != profile::kCatalogSha256 &&
        profile::kSchema != profile::kAckSchema,"Distinct source/wire identity domains collapsed into one digest");
    require(profile::kPixelProfileName == "foundation-engine-copied1795-ndv2-v1" &&
        profile::kPhysicalProfileName == "foundation-engine-copied2003-ndv2-v1","Named document profiles changed identity");
    require(profile::kQueries.size() == 1 && profile::kQueries[0] == profile::OperationFacts{3,48,1048576,512,profile::kSchema} &&
        profile::kCommands.size() == 2 && profile::kCommands[0] == profile::OperationFacts{6,6246,1048576,1024,profile::kSchema} &&
        profile::kCommands[1] == profile::OperationFacts{7,8,16,1024,profile::kAckSchema},
        "Operation catalog IDs, capacities, capabilities or schemas disagree");
}
void profile_admission() {
    const profile::EngineDocumentProfileFacts disabled;
    require(!disabled.enabled && disabled.kind == profile::ProfileKind::disabled &&
        !profile::document_profile_valid(disabled) && !profile::document_profile_agrees(disabled,disabled),
        "Default source facts enabled or admitted an engine profile");
    const auto valid = pixel_profile();
    require(profile::document_profile_valid(valid) && profile::document_profile_agrees(valid,valid),"Exact pixel facts rejected");
    const auto reject = [&](auto change, const char* message) {
        auto altered = valid; change(altered);
        require(!profile::document_profile_valid(altered) && !profile::document_profile_agrees(altered,valid),message);
    };
    reject([](auto& f) { f.enabled = false; },"Disabled facts admitted");
    reject([](auto& f) { f.kind = static_cast<profile::ProfileKind>(99); },"Unknown profile kind admitted");
    reject([](auto& f) { f.name = "foundation-engine-copied259-v1"; },"Legacy profile name admitted as document v2");
    reject([](auto& f) { f.provider_abi_major = 2; },"Unknown provider major admitted");
    reject([](auto& f) { f.provider_abi_minor = 0; },"Document profile downgraded to provider minor zero");
    reject([](auto& f) { f.provider_abi_minor = 2; },"Unknown provider minor admitted");
    reject([](auto& f) { f.host_abi_major = 2; },"Unknown host major admitted");
    reject([](auto& f) { f.host_abi_minor = 1; },"Document extension changed the base host callback minor");
    reject([](auto& f) { f.target_system = 99; },"Unknown target system admitted");
    reject([](auto& f) { f.target_processor = 99; },"Unknown target processor admitted");
    reject([](auto& f) { f.pointer_bits = 32; },"Native target admitted with wrong pointer width");
    reject([](auto& f) { f.target_system = BIB_ENGINE_TARGET_WINDOWS; f.target_processor = BIB_ENGINE_CPU_AARCH64; },
        "Unsupported Windows processor tuple admitted");
    reject([](auto& f) { f.target_system = BIB_ENGINE_TARGET_BROWSER_WASM; },"Browser target admitted native CPU/width facts");
    reject([](auto& f) { f.lifetime = 2; },"Unsupported provider lifetime admitted");
    reject([](auto& f) { f.maximum_starts = 2; },"Provider restart promise invented");
    reject([](auto& f) { f.viewport_width = 801; },"Unknown viewport width admitted");
    reject([](auto& f) { f.viewport_height = 601; },"Unknown viewport height admitted");
    for (const auto mask : {UINT64_C(0),UINT64_C(259),UINT64_C(467),UINT64_C(1795) | (UINT64_C(1) << 63)})
        reject([mask](auto& f) { f.provider_capabilities = mask; },"Missing, legacy or unknown capability mask admitted");
    reject([](auto& f) { f.base_header_sha256[0] ^= 1; },"Unknown canonical base pin admitted");
    reject([](auto& f) { f.extension_header_sha256[0] ^= 1; },"Unknown extension pin admitted");
    reject([](auto& f) { f.contract_sha256 = f.base_header_sha256; },"Composite contract silently downgraded to a header pin");
    reject([](auto& f) { f.catalog_sha256[0] ^= 1; },"Unknown operation catalog pin admitted");
    reject([](auto& f) { f.build_sha256.fill(0); },"Zero provider build pin admitted");
    reject([](auto& f) { f.source_recipe_sha256.fill(0); },"Zero source recipe pin admitted");
    reject([](auto& f) { f.physical_catalog_sha256 = profile::kPhysicalCatalogSha256; },"Pixel profile acquired an extra physical catalog");
    reject([](auto& f) { f.query_count = 0; },"Missing query facts admitted");
    reject([](auto& f) { f.query_count = 2; },"Unknown extra query facts admitted");
    reject([](auto& f) { f.command_count = 1; },"Missing ACK command facts admitted");
    reject([](auto& f) { f.command_count = 3; },"Unknown extra command facts admitted");
    reject([](auto& f) { f.queries[0].operation = 1; },"Legacy query operation admitted");
    reject([](auto& f) { ++f.queries[0].maximum_input_bytes; },"Wrong query input capacity admitted");
    reject([](auto& f) { --f.queries[0].required_reply_capacity; },"Insufficient query reply capacity admitted");
    reject([](auto& f) { f.queries[0].capability = 4; },"Wrong query capability admitted");
    reject([](auto& f) { f.queries[0].schema_sha256[0] ^= 1; },"Unknown query schema admitted");
    reject([](auto& f) { std::swap(f.commands[0],f.commands[1]); },"Reordered command facts admitted");
    for (std::size_t index = 0; index < 2; ++index) {
        reject([index](auto& f) { ++f.commands[index].operation; },"Unknown command operation admitted");
        reject([index](auto& f) { ++f.commands[index].maximum_input_bytes; },"Wrong command input capacity admitted");
        reject([index](auto& f) { --f.commands[index].required_reply_capacity; },"Insufficient command reply capacity admitted");
        reject([index](auto& f) { f.commands[index].capability = 0; },"Missing command capability admitted");
        reject([index](auto& f) { f.commands[index].schema_sha256[0] ^= 1; },"Unknown command schema admitted");
    }
    for (const auto target : std::array<std::array<std::uint32_t,3>,4>{{
            {1,1,64},{1,2,64},{2,1,64},{3,3,32}}}) {
        auto actual = valid; actual.target_system = target[0]; actual.target_processor = target[1]; actual.pointer_bits = target[2];
        require(profile::document_profile_valid(actual),"Declared target vocabulary rejected valid facts");
    }
    auto physical = valid; physical.kind = profile::ProfileKind::physical; physical.name = profile::kPhysicalProfileName;
    physical.provider_capabilities = 2003; physical.physical_catalog_sha256 = profile::kPhysicalCatalogSha256;
    require(profile::document_profile_valid(physical) && profile::document_profile_agrees(physical,physical) &&
        !profile::document_profile_agrees(physical,valid),"Exact physical facts or profile distinction lost");
    auto missing = physical; missing.physical_catalog_sha256.fill(0);
    require(!profile::document_profile_valid(missing),"Physical profile admitted without its physical catalog pin");
    missing = physical; missing.physical_catalog_sha256[0] ^= 1;
    require(!profile::document_profile_valid(missing),"Physical profile admitted with an unknown physical catalog pin");
    for (unsigned variant = 0; variant < 3; ++variant) {
        auto changed = valid;
        if (variant == 0) changed.build_sha256[1] = 3;
        if (variant == 1) changed.source_recipe_sha256[1] = 3;
        if (variant == 2) changed.target_processor = BIB_ENGINE_CPU_AARCH64;
        require(profile::document_profile_valid(changed) && !profile::document_profile_agrees(changed,valid),
            "Individually valid but different retained facts agreed");
    }
}
void ack_wire_codec() {
    constexpr std::uint64_t original = UINT64_C(0x0123456789abcdef);
    constexpr std::array<std::uint8_t,8> little{0xef,0xcd,0xab,0x89,0x67,0x45,0x23,0x01};
    constexpr auto encoded = encode_engine_document_action_ack(original);
    static_assert(encoded && *encoded == little);
    static_assert(!encode_engine_document_action_ack(0) && !encode_engine_document_action_ack(UINT64_MAX));
    const auto maximum = encode_engine_document_action_ack(UINT64_MAX - 1);
    require(maximum && (*maximum)[0] == 0xfe && std::all_of(maximum->begin() + 1,maximum->end(),
        [](auto byte) { return byte == 0xff; }),"Maximum ordinary action ACK wrapped or narrowed");
    const auto first = encode_engine_document_action_ack(1);
    require(first && (*first)[0] == 1 && std::all_of(first->begin() + 1,first->end(),
        [](auto byte) { return byte == 0; }),"First action ACK encoding changed byte order");
    std::array<std::uint8_t,16> wire{}; std::copy(little.begin(),little.end(),wire.begin());
    for (std::uint32_t code = 0; code <= 2; ++code) {
        wire[8] = static_cast<std::uint8_t>(code);
        const auto decoded = decode_engine_document_action_ack(wire);
        require(decoded && decoded->original_action_sequence == original &&
            decoded->code == static_cast<EngineDocumentAckCode>(code),"ACK reply lost its exact original sequence or code");
    }
    wire[8] = 2;
    require(decode_engine_document_action_ack(wire)->code == EngineDocumentAckCode::stale,
        "STALE metadata became proof of action retirement");
    for (std::size_t length = 0; length < wire.size(); ++length)
        require(!decode_engine_document_action_ack(std::span(wire).first(length)),"Truncated ACK reply accepted");
    std::vector<std::uint8_t> extra(wire.begin(),wire.end()); extra.push_back(0);
    require(!decode_engine_document_action_ack(extra),"ACK reply with trailing bytes accepted");
    for (std::size_t index = 12; index < 16; ++index) {
        auto malformed = wire; malformed[index] = 1;
        require(!decode_engine_document_action_ack(malformed),"Nonzero ACK reserved byte accepted");
    }
    for (std::size_t index = 8; index < 12; ++index) {
        auto malformed = wire; malformed[index] = index == 8 ? 3 : 1;
        require(!decode_engine_document_action_ack(malformed),"Unknown ACK code accepted");
    }
    auto zero = wire; std::fill(zero.begin(),zero.begin() + 8,0);
    require(!decode_engine_document_action_ack(zero),"ACK for action sequence zero accepted");
    auto reserved_sequence = wire; std::fill(reserved_sequence.begin(),reserved_sequence.begin() + 8,0xff);
    require(!decode_engine_document_action_ack(reserved_sequence),"Final reserved ACK sequence accepted as an original action");
    reserved_sequence[0] = 0xfe;
    const auto last = decode_engine_document_action_ack(reserved_sequence);
    require(last && last->original_action_sequence == UINT64_MAX - 1,"Maximum original ACK result narrowed");
    for (std::size_t index = 0; index < 8; ++index) {
        auto changed = wire; changed[index] ^= 0x80;
        const auto decoded = decode_engine_document_action_ack(changed);
        require(decoded && decoded->original_action_sequence != original,
            "ACK decoder discarded part of the original action identity");
    }
}
EngineDocumentWork query_work() {
    EngineDocumentWork work;
    work.target = {UINT64_MAX,UINT64_MAX - 1,UINT64_MAX - 2,UINT64_MAX - 3};
    work.request_sequence = 10; work.kind = EngineDocumentWorkKind::snapshot_query; work.operation = 3;
    work.required_reply_capacity = 1048576; work.schema_sha256 = profile::kSchema; work.payload.resize(48);
    return work;
}
void owned_work_shapes() {
    require(!valid_engine_document_work_shape(EngineDocumentWork{}),"Default work acquired valid target authority");
    auto query = query_work();
    require(valid_engine_document_work_shape(query),"Full-width logical target or exact query shape rejected");
    const auto reject = [&](auto change, const char* message) {
        auto altered = query; change(altered); require(!valid_engine_document_work_shape(altered),message);
    };
    reject([](auto& w) { w.target.worker_epoch = 0; },"Zero worker epoch admitted");
    reject([](auto& w) { w.target.application_instance = 0; },"Zero application instance admitted");
    reject([](auto& w) { w.target.document_sequence = 0; },"Zero document sequence admitted");
    reject([](auto& w) { w.target.service_generation = 0; },"Zero service generation admitted");
    reject([](auto& w) { w.request_sequence = 0; },"Zero request sequence admitted");
    reject([](auto& w) { w.request_sequence = UINT64_MAX; },"Query consumed the final reserved ACK sequence");
    reject([](auto& w) { w.kind = static_cast<EngineDocumentWorkKind>(99); },"Unknown work kind admitted");
    reject([](auto& w) { w.operation = 1; },"Legacy query operation admitted");
    reject([](auto& w) { w.schema_sha256[0] ^= 1; },"Wrong query schema admitted");
    reject([](auto& w) { --w.required_reply_capacity; },"Insufficient query reply reservation admitted");
    reject([](auto& w) { w.payload.pop_back(); },"Short query payload admitted");
    reject([](auto& w) { w.payload.push_back(0); },"Oversized query payload admitted");
    query.request_sequence = UINT64_MAX - 1;
    require(valid_engine_document_work_shape(query),"Maximum ordinary query sequence rejected");
    auto action = query; action.kind = EngineDocumentWorkKind::form_action; action.operation = 6;
    // Shape checks deliberately do not grant canonical NDV2 or live DOM authority.
    for (const std::size_t length : {81U,6246U}) {
        action.payload.resize(length); require(valid_engine_document_work_shape(action),"Bounded action shape rejected");
    }
    for (const std::size_t length : {80U,6247U}) {
        action.payload.resize(length); require(!valid_engine_document_work_shape(action),"Out-of-bounds action shape admitted");
    }
    action.payload.resize(81); action.request_sequence = UINT64_MAX;
    require(!valid_engine_document_work_shape(action),"Form action consumed the final reserved ACK sequence");
    auto ack = query; ack.kind = EngineDocumentWorkKind::action_ack; ack.operation = 7;
    ack.schema_sha256 = profile::kAckSchema; ack.required_reply_capacity = 16; ack.request_sequence = UINT64_MAX;
    const auto original = encode_engine_document_action_ack(UINT64_MAX - 1);
    ack.payload.assign(original->begin(),original->end());
    require(valid_engine_document_work_shape(ack),"Final fresh ACK command rejected for the maximum ordinary action");
    auto altered = ack; altered.request_sequence = UINT64_MAX - 1;
    require(!valid_engine_document_work_shape(altered),"ACK sequence did not exceed its original action");
    --altered.request_sequence;
    require(!valid_engine_document_work_shape(altered),"Decreasing ACK request sequence admitted");
    for (unsigned variant = 0; variant < 6; ++variant) {
        altered = ack;
        if (variant == 0) altered.operation = 6;
        if (variant == 1) altered.schema_sha256 = profile::kSchema;
        if (variant == 2) altered.required_reply_capacity = 15;
        if (variant == 3) altered.payload.pop_back();
        if (variant == 4) altered.payload.assign(8,0);
        if (variant == 5) altered.payload.assign(8,0xff);
        require(!valid_engine_document_work_shape(altered),"Malformed ACK work shape admitted");
    }
    EngineDocumentDispatch dispatch{17,23,ack}; ack.payload[0] ^= 1;
    require(dispatch.work.payload[0] == 0xfe && dispatch.work.target == query.target &&
        dispatch.ticket == 17 && dispatch.transfer == 23,"Dispatch retained borrowed work bytes or changed target/ticket fields");
    EngineDocumentAdmission admission;
    EngineDocumentCompletion completion;
    require(admission.code == EngineDocumentAdmissionCode::unavailable && admission.ticket == 0 &&
        completion.outcome == EngineDocumentOutcome::unknown && completion.provider_status == BIB_ENGINE_PROCESS_EXIT_REQUIRED &&
        completion.provider_disposition == 0 && !completion.handled && completion.bytes.empty(),
        "Default admission/completion invented success or confused provider status/disposition domains");
    completion.target = dispatch.work.target; completion.bytes = dispatch.work.payload;
    const auto copied = completion; completion.bytes[0] = 0;
    require(copied.bytes[0] == 0xfe && copied.target == dispatch.work.target,"Completion copy borrowed byte storage or narrowed identity");
}
} // namespace

int main() {
    try {
        source_contract_facts(); profile_admission(); ack_wire_codec(); owned_work_shapes();
        std::cout << "Engine document source contract, profile facts, work shapes and ACK codec passed\n";
    } catch (const std::exception& error) { std::cerr << error.what() << '\n'; return 1; }
}
