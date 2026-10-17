#include "shared/appended_engine_application.hpp"
#include "shared/appended_engine_input_codec.hpp"
#include "shared/appended_engine_abi.h"
#include "../../src/appended/sha256.hpp"

#include <gui/retained_adapter.hpp>
#include <algorithm>
#include <array>
#include <iostream>
#include <stdexcept>

namespace {
using namespace foundation;
using namespace appended;
namespace input = appended::engine_input;
using Span = std::span<const std::uint8_t>;
void check(bool value, const char* message) { if (!value) throw std::runtime_error(message); }
Span bytes(std::string_view value) { return {reinterpret_cast<const std::uint8_t*>(value.data()), value.size()}; }
void put(std::span<std::uint8_t> output, std::size_t offset, std::uint64_t value, unsigned width) {
    for (unsigned i = 0; i < width; ++i) output[offset + i] = static_cast<std::uint8_t>(value >> (i * 8));
}
std::uint64_t get(Span value, std::size_t offset, unsigned width) {
    std::uint64_t result{};
    for (unsigned i = 0; i < width; ++i) result |= std::uint64_t(value[offset + i]) << (i * 8);
    return result;
}
Bytes request(std::uint32_t operation, EngineIdentity id, Span body = {}, std::uint64_t transfer = 0) {
    Bytes result(72 + body.size());
    std::copy_n("FKB1", 4, result.begin());
    put(result, 4, 1, 2); put(result, 6, operation, 2); put(result, 8, result.size(), 4);
    put(result, 16, id.worker_epoch, 8); put(result, 24, id.application_instance, 8);
    put(result, 32, id.document_sequence, 8); put(result, 40, id.service_generation, 8);
    put(result, 48, transfer, 8); put(result, 64, body.size(), 4);
    std::copy(body.begin(), body.end(), result.begin() + 72); return result;
}
Bytes dispatch(EngineOwner& owner, std::uint32_t operation, EngineIdentity id, Span body = {}, std::uint64_t transfer = 0) {
    const auto record = request(operation, id, body, transfer);
    Bytes result(512);
    const auto count = owner.dispatch(operation, record, result);
    check(count >= 80, "input application owner transport failed");
    result.resize(static_cast<std::size_t>(count)); return result;
}
void accept(EngineOwner& owner, std::uint32_t operation, EngineIdentity id, Span body = {}, std::uint64_t transfer = 0) {
    const auto result = dispatch(owner, operation, id, body, transfer);
    if (get(result,72,4) != FOUNDATION_ENGINE_OK || get(result,76,4) != 0)
        throw std::runtime_error("fixture operation " + std::to_string(operation) + " rejected: control=" +
                                 std::to_string(get(result,72,4)) + " service=" + std::to_string(get(result,76,4)));
}
Package package() {
    const std::string startup = "{\"kind\":\"foundation-appended-startup\",\"primary\":\"web\",\"schema_version\":1}";
    const std::string html = "<!doctype html><title>Input fixture</title>";
    const auto file = [](std::string_view path, std::string_view mime, std::size_t offset, std::string_view text) {
        return "{\"component\":\"web\",\"length\":" + std::to_string(text.size()) +
            ",\"media_type\":\"" + std::string(mime) + "\",\"offset\":" + std::to_string(offset) +
            ",\"path\":\"" + std::string(path) + "\",\"sha256\":\"" + detail::hex_digest(detail::sha256(bytes(text))) + "\"}";
    };
    const auto index = "{\"application\":{\"id\":\"org.example.input\",\"name\":\"Input fixture\",\"version\":\"1.0.0\"},"
        "\"components\":{\"binary\":{\"entry\":null,\"present\":false,\"profile\":null},\"web\":{\"entry\":\"web/index.html\",\"present\":true}},"
        "\"files\":[" + file("web/.foundation/startup-v1.json", "application/json", 0, startup) + "," +
        file("web/index.html", "text/html", startup.size(), html) + "],\"identities\":{},\"kind\":\"foundation-appended-package\","
        "\"requires\":{\"abi\":{\"major\":1,\"minor\":0},\"capabilities\":[\"foundation.startup.v1\"],\"services\":[]},\"schema_version\":1}";
    Bytes data(startup.begin(), startup.end()); data.insert(data.end(), html.begin(), html.end());
    const auto offset = data.size(); data.insert(data.end(), index.begin(), index.end());
    return read_package(data, offset, index.size());
}
input::EngineSurfaceProfileFacts test_profile() {
    // Explicit test-only pins qualify no retained engine or production profile.
    input::EngineSurfaceProfileFacts facts;
    facts.enabled = true; facts.name = input::kInputProfileName;
    facts.contract_sha256 = input::kProviderContractSha256;
    facts.build_sha256.fill(1); facts.source_recipe_sha256.fill(2); facts.catalog_sha256 = input::kInputCatalogSha256;
    facts.provider_capabilities = input::kProviderCapabilities; facts.surface_capabilities = input::kSurfaceCapabilities;
    facts.surface_protocol_version = 1; facts.mouse_input_version = 1; facts.raw_key_mapping_revision = 1;
    facts.viewport_width = 800; facts.viewport_height = 600; facts.display_scale = 1; facts.commands = input::kCommands;
    return facts;
}
Bytes frame(std::uint64_t base) {
    Bytes data(48 + 800 * 600 * 4);
    put(data, 0, 1, 4); put(data, 4, 800, 4); put(data, 8, 600, 4); put(data, 12, 3200, 4);
    put(data, 24, 800, 4); put(data, 28, 600, 4); put(data, 32, base, 8); put(data, 40, base + 1, 8);
    for (std::size_t i = 48; i < data.size(); i += 4) data[i + 3] = 255;
    return data;
}
struct FakeAdapter final : gui::RetainedAdapter {
    bool paired = false;
    std::function<void(std::uint64_t)> legacy;
    void present(gui::Snapshot value) override {
        const auto revision = value.revision;
        gui::RetainedAdapter::present(std::move(value));
        if (!paired && legacy) legacy(revision);
    }
};
struct FakePort final : ui::EngineSurfacePort {
    FakeAdapter& adapter;
    gui_surface::Capabilities caps;
    gui_surface::Policy policy;
    std::vector<gui_surface::Presentation> publications;
    bool service = false, fail = false;
    static gui_surface::Capabilities capabilities_value() { gui_surface::Capabilities value; value.supported=8225; value.mouse_input_version=1; return value; }
    explicit FakePort(FakeAdapter& value) : adapter(value), caps(capabilities_value()), policy(caps,77) {
        adapter.legacy = [this](std::uint64_t revision) { if (policy.accepted()) (void)policy.legacy_present(revision); };
    }
    ~FakePort() override { adapter.legacy = {}; }
    bool available() const noexcept { return policy.accepted() && policy.accepted()->available && !service; }
    const gui_surface::Capabilities& capabilities() const noexcept override { return caps; }
    std::uint64_t generation() const noexcept override { return 77; }
    gui_surface::CommitResult present_pair(gui::Snapshot snapshot, const gui_surface::Presentation& value) override {
        check(snapshot.revision == value.identity.presentation_revision, "unpaired rich snapshot revision");
        check(snapshot.widgets.size() == 1 && snapshot.widgets.front().spec.key.id == value.identity.owner.id &&
              snapshot.widgets.front().spec.key.generation == value.identity.owner.generation,
              "surface owner is not the live bitmap");
        check(value.bounds == gui_surface::Rect{0,0,800,600} && value.clip == value.bounds && value.display_scale == 1,
              "surface geometry does not match fixed viewport");
        if (fail) return {gui_surface::Status::stale_preparation,{}};
        auto preparation = policy.prepare(value);
        if (preparation.status != gui_surface::Status::ok) return {preparation.status,{}};
        adapter.paired = true;
        try { adapter.present(std::move(snapshot)); } catch (...) { adapter.paired=false; throw; }
        adapter.paired = false;
        auto committed = policy.commit(std::move(preparation.prepared), value.identity.presentation_revision);
        if (committed.status == gui_surface::Status::ok) publications.push_back(value);
        return committed;
    }
    void set_owned_service_active(bool active) override {
        service = active;
        if (active && policy.accepted()) (void)policy.legacy_present(adapter.snapshot().revision);
    }
};
struct Fixture {
    FakeAdapter adapter;
    input::EngineSurfaceProfileFacts facts = test_profile();
    std::shared_ptr<EngineOwner> owner;
    FakePort* port{};
    std::unique_ptr<ui::AppendedEngineApplication> app;
    unsigned native_effects{};
    bool hold_on_entry{};
    std::uint64_t held_ticket{}, expected_native_context{};
    static constexpr std::string_view service_name = "org.example.input.native";
    explicit Fixture(bool native = false) {
        EngineOwnerConfiguration configuration; configuration.worker_epoch = 11; configuration.input_profile = facts;
        if (native) configuration.native_services.push_back({{std::string(service_name),1,0,SchemaId{7},4},
            [this](std::uint32_t operation, Span value, std::span<std::uint8_t> output) -> ServiceReply {
                const auto effect = owner->native_effect();
                check(operation==1 && value.size()==4 && output.size()>=4 && port && port->service && !port->available() &&
                      effect && effect->entered && effect->target==owner->identity() &&
                      effect->input_context==expected_native_context,
                      "actual Registry handler entered before App publication and provider retirement");
                if (hold_on_entry) {
                    check(owner->hold_native_effect(effect->ticket), "actual native handler could not hold UI suspension");
                    held_ticket=effect->ticket;
                }
                ++native_effects;
                std::copy(value.begin(),value.end(),output.begin()); return {ServiceStatus::ok,4};
            }});
        owner = std::make_shared<EngineOwner>(package(), configuration);
        accept(*owner, FOUNDATION_ENGINE_CONFIGURE, {11,0,0,0});
        accept(*owner, FOUNDATION_ENGINE_TURN_ENTER, {11,0,0,0});
        accept(*owner, FOUNDATION_ENGINE_BEGIN_DOCUMENT, {11,17,1,0});
        accept(*owner, FOUNDATION_ENGINE_TURN_LEAVE, {11,0,0,0});
        accept(*owner, FOUNDATION_ENGINE_FRAME_COMMIT, owner->identity(), frame(0));
        auto owned = std::make_unique<FakePort>(adapter); port = owned.get();
        app = std::make_unique<ui::AppendedEngineApplication>(adapter, owner, std::move(owned), facts);
        app->surface_connected(port->caps); app->tick();
    }
    std::optional<input::Command> peek() {
        const auto result = dispatch(*owner, FOUNDATION_ENGINE_PEEK_INPUT, owner->identity());
        if (get(result,72,4) == FOUNDATION_ENGINE_EMPTY) return {};
        check(get(result,72,4) == FOUNDATION_ENGINE_OK, "input peek rejected");
        input::Command command;
        check(input::decode_command(Span(result).subspan(80), command) == input::Status::ok, "invalid staged command bytes");
        return command;
    }
    input::Command consume() {
        const auto result = dispatch(*owner, FOUNDATION_ENGINE_PEEK_INPUT, owner->identity());
        check(get(result,72,4) == FOUNDATION_ENGINE_OK, "missing staged command");
        const EngineIdentity target{get(result,16,8),get(result,24,8),get(result,32,8),get(result,40,8)};
        const auto transfer = get(result,48,8);
        input::Command command;
        check(input::decode_command(Span(result).subspan(80), command) == input::Status::ok, "invalid command record");
        const auto again = dispatch(*owner, FOUNDATION_ENGINE_PEEK_INPUT, owner->identity());
        check(again == result, "peek reminted immutable command");
        accept(*owner, FOUNDATION_ENGINE_TURN_ENTER, target, {}, transfer);
        accept(*owner, FOUNDATION_ENGINE_TURN_LEAVE, target, {}, transfer);
        Bytes outcome;
        check(input::encode_command_result({0,1,command.request_sequence,0,0}, outcome) == input::Status::ok,
              "fixture command result invalid");
        accept(*owner, FOUNDATION_ENGINE_COMMAND_RESULT, target, outcome, transfer);
        return command;
    }
    void bind() {
        check(!port->publications.empty() && !port->publications.back().available,
              "input authority published before bind consumption");
        const auto command = consume(); input::Focus focus;
        check(command.operation == 3 && input::decode_focus(command.payload, focus) == input::Status::ok && focus.action == 1,
              "first input command is not context bind metadata");
        app->tick(); check(port->publications.back().available, "consumed bind did not publish input authority");
    }
    void send(gui_surface::Input value) {
        static std::uint64_t sequence = 1;
        app->surface_input({{port->publications.back().identity, sequence++, std::move(value)}, gui_surface::Capture::capture, {}});
    }
};
void bind_and_frozen_frame_identity() {
    Fixture f; check(f.peek().has_value(), "connection did not stage bind"); f.bind();
    const auto old = f.port->publications.back().identity;
    auto stale = old; ++stale.presentation_revision;
    f.app->surface_input({{stale,1,gui_surface::KeyTransition{gui_surface::KeyPhase::down,"x","KeyX"}},gui_surface::Capture::capture,{}});
    f.app->tick(); check(!f.peek(), "stale GUI identity entered owner mailbox");
    f.send(gui_surface::FocusChange{true,true,gui_surface::FocusCause::direct}); f.app->tick(); f.consume(); f.app->tick();
    f.send(gui_surface::KeyTransition{gui_surface::KeyPhase::down,"z","KeyY",0,31,false});
    accept(*f.owner, FOUNDATION_ENGINE_FRAME_COMMIT, f.owner->identity(), frame(1));
    f.app->tick();
    const auto command = f.consume(); input::Key key;
    check(input::decode_key(command.payload,key) == input::Status::ok && key.key == "z" && key.code == "KeyY" && key.modifiers == 31 &&
          key.input_context == old.context && f.port->publications.back().identity.context == old.context &&
          f.port->publications.back().identity.presentation_revision > old.presentation_revision,
          "compatible frame dropped or rebased frozen accepted input");
}
void chord_context_and_retirement() {
    Fixture f; f.bind();
    constexpr std::uint64_t token = (std::uint64_t{1} << 63) + 17;
    auto mouse = [&](gui_surface::MousePhase phase, unsigned button, unsigned buttons, gui_surface::ContextOrigin origin = gui_surface::ContextOrigin::pointer) {
        gui_surface::MouseTransition value; value.phase=phase; value.capture_token=token; value.button=button; value.buttons=buttons;
        value.x = origin == gui_surface::ContextOrigin::pointer ? 12.5 : 0;
        value.y = origin == gui_surface::ContextOrigin::pointer ? 21.25 : 0; value.context_origin=origin;
        f.send(value); f.app->tick(); const auto command=f.consume(); input::Mouse decoded;
        check(input::decode_mouse(command.payload,decoded)==input::Status::ok && decoded.capture_token==token && decoded.buttons==buttons,
              "mouse chord or context changed u64 authority"); f.app->tick();
    };
    mouse(gui_surface::MousePhase::down,0,1); mouse(gui_surface::MousePhase::down,2,3);
    mouse(gui_surface::MousePhase::context,0,3); mouse(gui_surface::MousePhase::context,0,3,gui_surface::ContextOrigin::keyboard);
    mouse(gui_surface::MousePhase::up,0,2); mouse(gui_surface::MousePhase::up,2,0);
    const auto old=f.port->publications.back().identity;
    f.app->set_owned_service_active(true); f.app->tick();
    check(f.port->service && !f.port->available(), "native service did not suspend paired authority");
    const auto retirement=f.consume(); input::Focus retired;
    check(input::decode_focus(retirement.payload,retired)==input::Status::ok && retired.action==2 && retired.expected_context==old.context,
          "service did not stage exact context retirement");
    f.app->tick(); f.app->set_owned_service_active(false); f.app->tick(); f.consume(); f.app->tick();
    check(f.port->publications.back().available && f.port->publications.back().identity.context > old.context,
          "service resumed retired input context");
    gui_surface::Revocation delayed; delayed.identity=old;
    f.app->surface_revoked(std::move(delayed)); f.app->tick();
    check(!f.peek() && f.port->publications.back().available, "delayed revocation retired successor context");
}
Bytes service_request(EngineIdentity target, std::uint64_t sequence, std::uint64_t handle,
                      std::uint32_t operation, Span payload) {
    Envelope header; header.generation=target.service_generation; header.sequence=sequence;
    header.interface_handle=handle; header.operation=operation;
    Bytes result; check(encode_envelope(header,payload,result)==CodecStatus::ok,"service fixture envelope invalid"); return result;
}
Bytes collect_service(Fixture& f, std::uint64_t sequence) {
    const auto target=f.owner->identity();
    const auto delivery=dispatch(*f.owner,FOUNDATION_ENGINE_PEEK_DELIVERY,target);
    check(get(delivery,72,4)==FOUNDATION_ENGINE_OK,"actual service completion missing");
    Envelope header; Span payload;
    check(decode_envelope(Span(delivery).subspan(80),header,payload)==CodecStatus::ok &&
          header.sequence==sequence && header.service_status==0,"actual service completion identity/status changed");
    Bytes result(payload.begin(),payload.end());
    const auto accepted=encode_u32(FOUNDATION_ENGINE_ACCEPTED);
    accept(*f.owner,FOUNDATION_ENGINE_DELIVERY_RESULT,target,accepted,get(delivery,48,8));
    const auto ack=dispatch(*f.owner,FOUNDATION_ENGINE_STAGE_ACK,target,encode_u64(sequence));
    check(get(ack,72,4)==FOUNDATION_ENGINE_OK && get(ack,76,4)==static_cast<std::uint32_t>(ServiceStatus::unavailable),
          "actual service ACK did not stage");
    accept(*f.owner,FOUNDATION_ENGINE_PUMP_ONE,target);
    const auto receipt=dispatch(*f.owner,FOUNDATION_ENGINE_PEEK_ACK_RECEIPT,target);
    check(get(receipt,72,4)==FOUNDATION_ENGINE_OK && get(receipt,80,8)==sequence,"actual service ACK receipt missing");
    accept(*f.owner,FOUNDATION_ENGINE_ACK_RECEIPT_RESULT,target,accepted,get(receipt,48,8));
    return result;
}
void automatic_native_effect_and_ui_hold() {
    Fixture f(true); f.bind();
    auto run = [&](std::uint64_t sequence, std::uint64_t handle, std::uint32_t operation, const Bytes& payload) {
        const auto target=f.owner->identity(); const auto old=f.port->publications.back().identity;
        const auto effects=f.native_effects; f.expected_native_context=old.context;
        accept(*f.owner,FOUNDATION_ENGINE_SUBMIT,target,service_request(target,sequence,handle,operation,payload));
        const auto gate=dispatch(*f.owner,FOUNDATION_ENGINE_PUMP_ONE,target);
        check(get(gate,72,4)==FOUNDATION_ENGINE_CONFLICT && get(gate,76,4)==static_cast<std::uint32_t>(ServiceStatus::unavailable) &&
              f.native_effects==effects && f.owner->native_effect(),"native effect bypassed App suspension handshake");
        f.app->tick();
        check(f.port->service && !f.port->available(),"App did not automatically suspend actual pending native effect");
        const auto command=f.consume(); input::Focus retire;
        check(command.operation==3 && input::decode_focus(command.payload,retire)==input::Status::ok &&
              retire.action==2 && retire.expected_context==old.context,"native effect did not consume exact provider retirement");
        f.app->tick();
        accept(*f.owner,FOUNDATION_ENGINE_PUMP_ONE,target);
        const auto completion=collect_service(f,sequence);
        f.app->tick();
        if (f.hold_on_entry) {
            check(f.held_ticket && f.owner->native_effect() && f.port->service && !f.port->available() && !f.peek(),
                  "known reply released a trusted native UI hold");
            // A renderer notification cannot release this independently owned hold.
            f.app->set_owned_service_active(false); f.app->tick();
            check(f.port->service && !f.port->available(),"frontend-like false cleared owner UI hold");
            check(f.owner->release_native_effect(f.held_ticket),"trusted actual UI closure did not release hold");
            f.app->tick();
        }
        check(!f.port->service && !f.port->available(),"known completion failed to stage a fresh unavailable context");
        const auto bind=f.consume(); input::Focus context;
        check(input::decode_focus(bind.payload,context)==input::Status::ok && context.action==1 && context.input_context>old.context,
              "native completion restored a retired context");
        f.app->tick(); check(f.port->available(),"fresh acknowledged native context did not reopen admission");
        return completion;
    };
    const auto major=encode_u32(1),minor=encode_u32(0);
    const std::array<FieldView,4> fields{{{1,FieldType::utf8,true,bytes(Fixture::service_name)},
        {2,FieldType::u32,true,major},{3,FieldType::u32,true,minor},{4,FieldType::u32,true,minor}}};
    Bytes query; check(encode_record(fields,query)==CodecStatus::ok,"discovery fixture invalid");
    const auto descriptor=run(1,0,FOUNDATION_APPENDED_CONTROL_DISCOVER,query);
    std::vector<FieldView> decoded; std::uint64_t handle{};
    check(decode_record(descriptor,decoded)==CodecStatus::ok && !decoded.empty() && read_u64(decoded.front(),handle) && handle,
          "actual Registry discovery did not issue a service route");
    f.hold_on_entry=true;
    check(run(2,handle,1,encode_u32(41))==encode_u32(41) && f.native_effects==1,
          "actual Registry handler did not execute exactly once");
}

void callbacks_queue_and_overflow() {
    Fixture f; f.bind();
    accept(*f.owner, FOUNDATION_ENGINE_TURN_ENTER, f.owner->identity());
    f.send(gui_surface::FocusChange{true,true,gui_surface::FocusCause::direct}); f.app->tick();
    check(f.owner->callback_depth()==1, "surface callback changed native turn depth");
    accept(*f.owner, FOUNDATION_ENGINE_TURN_LEAVE, f.owner->identity());
    check(!f.peek(), "surface callback staged native command inside turn");
    f.app->tick(); f.consume(); f.app->tick();
    for (unsigned i=0;i<65;++i) f.send(gui_surface::KeyTransition{gui_surface::KeyPhase::down,"x","KeyX"});
    f.app->tick(); const auto command=f.consume(); input::Focus focus;
    check(command.operation==3 && input::decode_focus(command.payload,focus)==input::Status::ok && focus.action==2 &&
          !f.port->available(),
          "ordinary queue overflow consumed reserved retirement or replayed accepted work");
    Fixture bytes; bytes.bind();
    gui_surface::KeyTransition oversized{gui_surface::KeyPhase::down,"x","KeyX"};
    oversized.key.reserve(1024*1024); bytes.send(std::move(oversized)); bytes.app->tick();
    const auto barrier=bytes.consume();
    check(barrier.operation==3 && input::decode_focus(barrier.payload,focus)==input::Status::ok && focus.action==2 && !bytes.port->available(),
          "owned string allocation exceeded byte budget without retiring admission");
    Fixture unrelated; unrelated.bind();
    unrelated.send(gui_surface::FocusChange{true,true,gui_surface::FocusCause::direct});
    unrelated.app->tick(); unrelated.consume(); unrelated.app->tick();
    gui_surface::AcceptedEvent event{{unrelated.port->publications.back().identity,1000000,
        gui_surface::KeyTransition{gui_surface::KeyPhase::down,"x","KeyX"}},gui_surface::Capture::capture,{}};
    event.revoked.identity=event.event.identity; ++event.revoked.identity->context;
    event.revoked.identity->owner.id.reserve(1024*1024);
    unrelated.app->surface_input(std::move(event)); unrelated.app->tick();
    check(unrelated.consume().operation==1,"irrelevant revocation retained a large allocation or retired current input");
}
}
int main() {
    try {
        bind_and_frozen_frame_identity(); chord_context_and_retirement(); callbacks_queue_and_overflow();
        automatic_native_effect_and_ui_hold();
        std::cout << "Rich App paired bind, frozen identity, mouse context, bounded queue and native-effect UI hold passed\n";
    } catch (const std::exception& error) { std::cerr << error.what() << '\n'; return 1; }
}
