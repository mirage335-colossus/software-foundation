#include "../gui/shared/appended_engine_abi.h"
#include "../gui/shared/appended_engine_owner.hpp"

#include <algorithm>
#include <array>
#include <iostream>
#include <stdexcept>
#include <string>
#include <string_view>

using namespace foundation::appended;
namespace {
void require(bool value, const char* reason) {
    if (!value) throw std::runtime_error(reason);
}
void put(Bytes& bytes, std::size_t offset, std::uint64_t value, unsigned count) {
    for (unsigned i = 0; i < count; ++i) bytes[offset + i] = static_cast<std::uint8_t>(value >> (8 * i));
}
std::uint64_t get(std::span<const std::uint8_t> bytes, std::size_t offset, unsigned count) {
    require(offset <= bytes.size() && count <= bytes.size() - offset, "web test reply range");
    std::uint64_t value{};
    for (unsigned i = 0; i < count; ++i) value |= std::uint64_t(bytes[offset + i]) << (8 * i);
    return value;
}
Package package() {
    Package value;
    value.application = {"org.example.web-only", "VM-free owner test", "1.0.0"};
    value.web = {true, "web/index.html", {}};
    value.capabilities = {"foundation.startup.v1"};
    value.package_sha256 = std::string(64, '1');
    const std::string startup = "{\"kind\":\"foundation-appended-startup\",\"primary\":\"web\",\"schema_version\":1}";
    value.files = {{"web/.foundation/startup-v1.json", "web", "application/json", std::string(64, '2'),
        Bytes(startup.begin(), startup.end())}, {"web/index.html", "web", "text/html", std::string(64, '3'), {}}};
    return value;
}
struct Reply { EngineIdentity identity; std::uint64_t transfer; Bytes bytes; };
Reply call(EngineOwner& owner, std::uint32_t operation, EngineIdentity identity, Bytes payload = {}, std::uint64_t transfer = 0) {
    Bytes input(72 + payload.size());
    input[0] = 'F'; input[1] = 'K'; input[2] = 'B'; input[3] = '1';
    put(input, 4, 1, 2); put(input, 6, operation, 2); put(input, 8, input.size(), 4);
    put(input, 16, identity.worker_epoch, 8); put(input, 24, identity.application_instance, 8);
    put(input, 32, identity.document_sequence, 8); put(input, 40, identity.service_generation, 8);
    put(input, 48, transfer, 8); put(input, 64, payload.size(), 4);
    std::copy(payload.begin(), payload.end(), input.begin() + 72);
    Bytes output(FOUNDATION_ENGINE_MAX_BODY_BYTES + 80);
    const auto written = owner.dispatch(operation, input, output);
    require(written >= 80 && std::size_t(written) <= output.size(), "web-only typed dispatch failed");
    output.resize(static_cast<std::size_t>(written));
    require(get(output, 6, 2) == (operation | FOUNDATION_ENGINE_REPLY_KIND) &&
        get(output, 8, 4) == output.size() && get(output, 72, 4) == FOUNDATION_ENGINE_OK,
        "web-only owner refused a valid operation");
    return {{get(output, 16, 8), get(output, 24, 8), get(output, 32, 8), get(output, 40, 8)}, get(output, 48, 8), std::move(output)};
}
Bytes request(EngineIdentity identity, std::uint64_t sequence, std::uint64_t handle, std::uint32_t operation, Bytes payload) {
    Envelope envelope;
    envelope.generation = identity.service_generation; envelope.sequence = sequence;
    envelope.interface_handle = handle; envelope.operation = operation;
    Bytes bytes;
    require(encode_envelope(envelope, payload, bytes) == CodecStatus::ok, "web-only service fixture encoding");
    return bytes;
}
void accept(EngineOwner& owner, std::uint32_t result_operation, const Reply& pending) {
    call(owner, FOUNDATION_ENGINE_TURN_ENTER, pending.identity, {}, pending.transfer);
    call(owner, FOUNDATION_ENGINE_TURN_LEAVE, pending.identity, {}, pending.transfer);
    call(owner, result_operation, pending.identity, encode_u32(FOUNDATION_ENGINE_ACCEPTED), pending.transfer);
}
void acknowledge(EngineOwner& owner, EngineIdentity identity, std::uint64_t sequence) {
    const auto staged = call(owner, FOUNDATION_ENGINE_STAGE_ACK, identity, encode_u64(sequence));
    require(get(staged.bytes, 76, 4) == FOUNDATION_APPENDED_SERVICE_UNAVAILABLE, "web-only ACK was not staged");
    call(owner, FOUNDATION_ENGINE_PUMP_ONE, identity);
    const auto receipt = call(owner, FOUNDATION_ENGINE_PEEK_ACK_RECEIPT, identity);
    require(receipt.bytes.size() == 92 && get(receipt.bytes, 80, 8) == sequence &&
        get(receipt.bytes, 88, 4) == FOUNDATION_APPENDED_SERVICE_OK, "web-only actual ACK receipt changed");
    accept(owner, FOUNDATION_ENGINE_ACK_RECEIPT_RESULT, receipt);
}
void run() {
    unsigned effects{}, factory_calls{};
    constexpr std::string_view name = "org.example.web-only.counter";
    EngineOwnerConfiguration config;
    config.worker_epoch = 17; config.application_instance = 23;
    config.native_services.push_back({{std::string(name), 1, 0, SchemaId{1}, 4},
        [&](std::uint32_t operation, auto input, auto output) -> ServiceReply {
            require(operation == 1 && input.size() == 4 && output.size() >= 4, "web-only native owner request");
            ++effects;
            const auto value = encode_u32(static_cast<std::uint32_t>(get(input, 0, 4)) + 1);
            std::copy(value.begin(), value.end(), output.begin());
            return {ServiceStatus::ok, 4};
        }});
    // This neutral hook has no interpreter implementation or actual factory
    // reference. A web-only Package must not invoke it even if supplied.
    config.module_factory = [&](auto, auto, auto) -> std::unique_ptr<EngineModuleBinding> {
        ++factory_calls; return {};
    };
    EngineOwner owner(package(), config);
    EngineIdentity identity{17, 23, 0, 0};
    call(owner, FOUNDATION_ENGINE_CONFIGURE, identity);
    identity.document_sequence = 1;
    identity = call(owner, FOUNDATION_ENGINE_BEGIN_DOCUMENT, identity).identity;
    require(identity.service_generation && !owner.has_module() && !factory_calls,
        "web-only configuration constructed an optional binary owner");
    const auto major = encode_u32(1), minor = encode_u32(0);
    const std::array<FieldView, 4> fields{{{1, FieldType::utf8, true,
        {reinterpret_cast<const std::uint8_t*>(name.data()), name.size()}},
        {2, FieldType::u32, true, major}, {3, FieldType::u32, true, minor}, {4, FieldType::u32, true, minor}}};
    Bytes query;
    require(encode_record(fields, query) == CodecStatus::ok, "web-only native discovery record");
    call(owner, FOUNDATION_ENGINE_SUBMIT, identity, request(identity, 1, 0, FOUNDATION_APPENDED_CONTROL_DISCOVER, query));
    call(owner, FOUNDATION_ENGINE_PUMP_ONE, identity);
    const auto discovered = call(owner, FOUNDATION_ENGINE_PEEK_DELIVERY, identity);
    Envelope envelope; std::span<const std::uint8_t> payload;
    require(decode_envelope(std::span(discovered.bytes).subspan(80), envelope, payload) == CodecStatus::ok &&
        envelope.service_status == FOUNDATION_APPENDED_SERVICE_OK, "web-only actual native discovery completion");
    std::vector<FieldView> descriptor;
    std::uint64_t handle{};
    require(decode_record(payload, descriptor) == CodecStatus::ok && descriptor.size() == 6 && read_u64(descriptor[0], handle) && handle,
        "web-only native Registry did not issue an opaque service route");
    accept(owner, FOUNDATION_ENGINE_DELIVERY_RESULT, discovered); acknowledge(owner, identity, 1);
    call(owner, FOUNDATION_ENGINE_SUBMIT, identity, request(identity, 2, handle, 1, encode_u32(41)));
    require(!effects, "web-only admission executed the native owner synchronously");
    call(owner, FOUNDATION_ENGINE_PUMP_ONE, identity);
    const auto completed = call(owner, FOUNDATION_ENGINE_PEEK_DELIVERY, identity);
    require(effects == 1 && call(owner, FOUNDATION_ENGINE_PEEK_DELIVERY, identity).bytes == completed.bytes &&
        decode_envelope(std::span(completed.bytes).subspan(80), envelope, payload) == CodecStatus::ok &&
        envelope.service_status == FOUNDATION_APPENDED_SERVICE_OK && payload.size() == 4 && get(payload, 0, 4) == 42,
        "web-only native outcome was not retained exactly once");
    accept(owner, FOUNDATION_ENGINE_DELIVERY_RESULT, completed); acknowledge(owner, identity, 2);
    call(owner, FOUNDATION_ENGINE_CLOSE, identity);
    require(owner.closed() && !factory_calls && effects == 1, "web-only owner did not close without an interpreter");
    auto binary = package();
    binary.binary = {true, "binary/application.wasm", "foundation-guest-v1"};
    binary.files.insert(binary.files.begin(), {"binary/application.wasm", "binary", "application/wasm", std::string(64, '4'), {}});
    try { EngineOwner unsupported(std::move(binary), {}); }
    catch (const std::invalid_argument& error) {
        require(std::string_view(error.what()).find("kernel maintenance required") != std::string_view::npos,
            "VM-free binary admission did not state the missing retained capability");
        return;
    }
    throw std::runtime_error("VM-free kernel accepted a binary Package without its actual optional factory");
}
} // namespace
int main() {
    try { run(); std::cout << "VM-free appended engine owner checks passed\n"; return 0; }
    catch (const std::exception& error) { std::cerr << error.what() << '\n'; return 1; }
}
