// SPDX-License-Identifier: CC0-1.0
// Real Owner, Driver, bitmap App and Surface Policy with a synthetic C provider.
// No engine, SDK, DSO, native window or physical IME qualification is claimed.
#include "../gui/shared/native_engine_bitmap_composition.hpp"
#include "../gui/shared/appended_engine_input_codec.hpp"
#include "../gui/shared/native_editor_codec.hpp"
#include "appended_document_actions_fixture.hpp"

#include <gui/retained_adapter.hpp>
#include <algorithm>
#include <array>
#include <atomic>
#include <chrono>
#include <functional>
#include <iostream>
#include <memory>
#include <optional>
#include <stdexcept>
#include <string>
#include <string_view>
#include <thread>
#include <utility>
#include <vector>

namespace {
using namespace foundation;
using namespace appended;
using ui::NativeEngineBitmapComposition;
namespace facts = document_actions_fixture;
namespace actions = appended::engine_document_actions;
namespace physical = appended::engine_input;
namespace ne = ui::native_editor;
namespace codec = ne::codec;
using Clock = std::chrono::steady_clock;
using Span = std::span<const std::uint8_t>;
using namespace std::chrono_literals;
std::size_t assertions{};
void check(bool condition, const char* reason) {
    ++assertions;
    if (!condition) throw std::runtime_error(reason);
}
template<class Function> void rejects(Function function, const char* reason) {
    bool rejected{};
    try { function(); } catch (const std::invalid_argument&) { rejected = true; }
    check(rejected, reason);
}
std::array<std::uint8_t, 3> pixel(const gui::Snapshot& snapshot) {
    check(snapshot.widgets.size() == 1 && snapshot.widgets.front().spec.kind == gui::Kind::bitmap,
          "composition did not expose exactly one ordinary bitmap");
    std::array<std::uint8_t, 3> result{}; bool painted{};
    snapshot.widgets.front().state.bitmap.source.paint({800,600,{0,0,1,1},gui::PixelFormat::rgb24},
        [&](unsigned x, unsigned y, gui::PixelBlock block) {
            check(!x && !y && block.bytes.size() >= 3, "copied bitmap damage changed");
            std::copy_n(block.bytes.begin(),3,result.begin()); painted = true;
        });
    check(painted,"copied bitmap source did not paint"); return result;
}
struct Adapter final : gui::RetainedAdapter {
    bool fail_next{}, paired{};
    unsigned attempts{}, failures{};
    std::function<void()> during_present;
    std::function<void(std::uint64_t)> legacy;
    void present(gui::Snapshot next) override {
        ++attempts;
        if (std::exchange(fail_next,false)) { ++failures; throw std::runtime_error("injected bitmap presentation failure"); }
        const auto revision = next.revision;
        gui::RetainedAdapter::present(std::move(next));
        if (!paired && legacy) legacy(revision);
        if (during_present) during_present();
    }
};
struct Port final : ui::EngineEditorPort {
    Adapter& adapter;
    gui_surface::Capabilities caps;
    gui_surface::Policy policy;
    std::optional<gui_surface::Presentation> surface;
    std::optional<ne::EditorPublication> editor;
    bool service{};
    unsigned pair_count{}, retirement_count{};
    static gui_surface::Capabilities selected() {
        gui_surface::Capabilities value; value.supported = actions::kSurfaceCapabilities;
        value.mouse_input_version = 1; return value;
    }
    explicit Port(Adapter& target) : adapter(target), caps(selected()), policy(caps,501) {
        adapter.legacy = [this](std::uint64_t revision) {
            (void)policy.legacy_present(revision); surface.reset(); editor.reset();
        };
    }
    ~Port() override { adapter.legacy = {}; }
    const gui_surface::Capabilities& capabilities() const noexcept override { return caps; }
    std::uint64_t generation() const noexcept override { return 501; }
    void install(gui::Snapshot snapshot) {
        adapter.paired = true;
        try { adapter.present(std::move(snapshot)); }
        catch (...) { adapter.paired = false; throw; }
        adapter.paired = false;
    }
    gui_surface::CommitResult present_pair(gui::Snapshot snapshot, const gui_surface::Presentation& next) override {
        return present_editor_pair(std::move(snapshot),next,{},{});
    }
    gui_surface::CommitResult present_editor_pair(gui::Snapshot snapshot, const gui_surface::Presentation& next,
        std::optional<ne::EditorPublication> publication, std::optional<ne::CompositionFact> composition) override {
        check(snapshot.revision == next.identity.presentation_revision && snapshot.widgets.size() == 1 &&
              snapshot.widgets.front().spec.key.id == next.identity.owner.id &&
              snapshot.widgets.front().spec.key.generation == next.identity.owner.generation,
              "native editor pair split its actual bitmap owner/revision");
        check(!publication || publication->composition == composition,"editor composition split from publication");
        auto ordinary = next; ordinary.editor.reset();
        ordinary.required &= ~(gui_surface::feature(gui_surface::Feature::committed_text) |
            gui_surface::feature(gui_surface::Feature::composition) |
            gui_surface::feature(gui_surface::Feature::surrounding_text) |
            gui_surface::feature(gui_surface::Feature::selection));
        auto prepared = policy.prepare(ordinary);
        if (prepared.status != gui_surface::Status::ok) return {prepared.status,{}};
        install(std::move(snapshot));
        auto result = policy.commit(std::move(prepared.prepared),next.identity.presentation_revision);
        if (result.status == gui_surface::Status::ok) {
            surface = next; editor = std::move(publication); ++pair_count;
        }
        return result;
    }
    gui_surface::CommitResult present_editor_retirement(gui::Snapshot snapshot, ne::EditorPublication publication) override {
        check(snapshot.widgets.empty() && !publication.basis && publication.retirement &&
              publication.retirement->readback_attested,"retirement omitted checked null readback");
        const auto revision = snapshot.revision; install(std::move(snapshot));
        auto result = policy.legacy_present(revision);
        if (result.status == gui_surface::Status::ok) {
            surface.reset(); editor = std::move(publication); ++retirement_count;
        }
        return result;
    }
    void set_owned_service_active(bool value) override {
        service = value;
        if (value && policy.accepted()) {
            (void)policy.legacy_present(adapter.snapshot().revision); surface.reset(); editor.reset();
        }
    }
    bool editable() const noexcept { return !service && surface && surface->available && editor && editor->basis; }
};

struct Fixture;
Fixture* active{};
struct Fixture {
    static constexpr std::uint64_t instance = UINT64_C(0x8000000000000044);
    static constexpr std::string_view service_name = "org.example.bitmap.native";
    const actions::EngineDocumentActionsProfileFacts profile = facts::profile();
    std::shared_ptr<EngineOwner> owner;
    NativeEngineDriver* driver{};
    Adapter adapter;
    Port* port{};
    std::unique_ptr<NativeEngineBitmapComposition> app;
    BibEngineHostV1 host{};
    BibEngineDocumentV1 document{instance,1,0};
    BibEngineResourceEpochV1 resource{};
    Clock::time_point now{1000s};
    std::optional<ne::NativeProjection> projection;
    std::uint64_t frame_revision{}, sample{700}, service_handle{}, pending_ack{}, held_ticket{}, next_native_token{904};
    std::uint8_t red{41};
    unsigned calls{}, starts{}, advances{}, queries{}, commands{}, retirements{}, disposals{}, effects{}, deliveries{}, native_observations{};
    std::atomic<unsigned> posts{}, synchronous_rejections{};
    bool inside{}, in_adapter{}, synchronous_post{}, fail_advance{}, unknown_revoke{}, emit_next{true}, hold_effect{};
    std::optional<ne::Packet> expected_head;
    std::shared_ptr<int> capture = std::make_shared<int>(7);

    explicit Fixture(bool interactive = false, bool construct = true, bool native_service = false) {
        check(!active,"one mock native binding per fresh process"); active = this;
        auto config = facts::configuration(); config.application_instance = 0;
        if (native_service) config.native_services.push_back({{std::string(service_name),1,0,SchemaId{7},4},
            [this](std::uint32_t operation, Span input, std::span<std::uint8_t> output) -> ServiceReply {
                check(operation == 1 && input.size() == 4 && output.size() >= 4 &&
                      adapter.snapshot().widgets.empty() && (!port || (port->service && !port->editable())),
                      "Registry effect entered before actual bitmap/editor redaction");
                check(!in_adapter,"Registry effect entered an Adapter callback");
                if (hold_effect) {
                    const auto effect = owner->native_effect();
                    check(effect && effect->entered && owner->hold_native_effect(effect->ticket),
                          "actual entered native effect could not retain its trusted UI hold");
                    held_ticket = effect->ticket;
                }
                ++effects;
                std::copy(input.begin(),input.end(),output.begin()); return {ServiceStatus::ok,4};
            }});
        owner = std::make_shared<EngineOwner>(facts::package(),std::move(config));
        NativeEngineOptions options; options.maximum_steps_per_tick = 4;
        options.limits.maximum_command_bytes = BIB_ENGINE_EDITOR_MAX_WIRE_BYTES;
        options.limits.maximum_query_bytes = engine_editor::kQueryRequestMaximum;
        options.limits.maximum_reply_bytes = actions::kReplyCapacity;
        NativeEngineExpectation expected; expected.document_actions_profile = profile;
        expected.target_system = profile.target_system; expected.target_processor = profile.target_processor;
        expected.pointer_bits = profile.pointer_bits; expected.contract_header_sha256 = profile.contract_sha256;
        expected.build_identity_sha256 = profile.build_sha256; expected.source_recipe_sha256 = profile.source_recipe_sha256;
        BibEngineProviderV1 table{}; table.size = sizeof(table); table.abi_major = 1; table.abi_minor = 1;
        auto& build = table.build; build.size = sizeof(build); build.layout_revision = BIB_ENGINE_LAYOUT_V1;
        build.target_system = profile.target_system; build.target_processor = profile.target_processor;
        build.pointer_bits = profile.pointer_bits; build.lifetime = BIB_ENGINE_LIFETIME_PROCESS; build.maximum_starts = 1;
        build.fixed_viewport_width = 800; build.fixed_viewport_height = 600; build.capabilities = profile.provider_capabilities;
        std::copy(profile.contract_sha256.begin(),profile.contract_sha256.end(),build.contract_header_sha256);
        std::copy(profile.build_sha256.begin(),profile.build_sha256.end(),build.build_identity_sha256);
        std::copy(profile.source_recipe_sha256.begin(),profile.source_recipe_sha256.end(),build.source_recipe_sha256);
        table.limits = options.limits; table.start = start; table.advance = advance; table.current_document = current;
        table.query = query; table.command = command; table.deliver_services = deliver;
        table.collect_service_ack = collect; table.dispose_retired_service_document = dispose;
        driver = &NativeEngineDriver::bind_once(NativeEngineProvider::checked(table,expected),owner,options,
            {this,[](void* context) noexcept {
                auto& fixture = *static_cast<Fixture*>(context); if (fixture.app) fixture.app->wake();
            }});
        driver->start_once(now);
        check(starts == 1 && owner->configured() && driver->state() == NativeEngineState::ready && !owner->has_module(),
              "synthetic4083 did not start the actual VM-free Owner/Driver");
        if (construct) create(interactive);
    }
    ~Fixture() { app.reset(); active = nullptr; }
    void create(bool interactive) {
        const auto before = calls;
        auto post = [this, keep = capture] {
            (void)keep; posts.fetch_add(1);
            if (synchronous_post && app) {
                const auto entered = calls;
                try { app->tick(now); } catch (const std::logic_error&) { synchronous_rejections.fetch_add(1); }
                check(calls == entered,"synchronous wake callback entered the provider");
            }
        };
        if (interactive) {
            auto owned = std::make_unique<Port>(adapter); port = owned.get();
            app = std::make_unique<NativeEngineBitmapComposition>(adapter,owner,*driver,profile,
                ui::BoundEngineEditorPort{std::move(owned)},std::move(post));
        } else app = std::make_unique<NativeEngineBitmapComposition>(adapter,owner,*driver,profile,
            ui::ReadOnlyEngineBitmap{},std::move(post));
        check(calls == before,"facade construction entered or restarted its provider");
    }
    template<class Function> std::int32_t turn(Function function) {
        ++calls;
        check(!inside && !in_adapter,"provider reentered a callback or another native turn");
        inside = true;
        const auto admission = host.enter_engine(host.context);
        if (admission) { inside = false; return BIB_ENGINE_REENTRANT; }
        try {
            const auto status = function(); host.leave_engine(host.context); inside = false; return status;
        } catch (...) { host.leave_engine(host.context); inside = false; throw; }
    }
    void damage() {
        Bytes pixels(800 * 600 * 4);
        for (std::size_t offset = 0; offset < pixels.size(); offset += 4) {
            pixels[offset] = red; pixels[offset + 1] = 23; pixels[offset + 2] = 45; pixels[offset + 3] = 255;
        }
        BibEngineDamageV1 value{sizeof(value),1,document,++frame_revision,0,0,800,600,3200,
            static_cast<std::uint32_t>(pixels.size()),pixels.data()};
        host.damage(host.context,&value); std::fill(pixels.begin(),pixels.end(),0xee);
    }
    void tick() { app->tick(now += 1ms); }
    template<class Done> void until(Done done, const char* reason) {
        for (unsigned step = 0; step < 48 && !done(); ++step) tick();
        if (!done()) std::cerr << "diagnostic: native=" << static_cast<unsigned>(driver->state())
            << " calls=" << calls << " advance=" << advances << " query=" << queries << " command=" << commands
            << " retire=" << retirements << " frame=" << app->frame_ready() << " debt=" << app->presentation_pending() << '\n';
        check(done(),reason);
    }
    void show() {
        app->drawable_pixels(800,600);
        if (port) app->surface_connected(port->capabilities());
        until([&] { return app->frame_ready() && (!port || port->editable()); },"native bitmap/editor did not settle its actual frame");
    }
    void close() {
        const auto before = calls; app->shutdown(); check(calls == before,"shutdown entered the provider synchronously");
        until([&] { return app->native_state() == NativeEngineState::detached; },"normal bitmap close did not drain real retirement");
        until([&] { return app->close_complete(); },"native detach did not finish actual local App close metadata");
    }
    static std::int32_t BIB_ENGINE_CALL start(const BibEngineHostV1* callbacks, const BibEngineStartV1* input,
        BibEngineStartResultV1* result) {
        auto& f = *active; ++f.starts; f.host = *callbacks;
        check(input && input->raster_output == 1 && input->required_capabilities == actions::kProviderCapabilities,
              "START changed independent4083/raster admission");
        const auto status = f.turn([&] {
            f.resource.size = sizeof(f.resource);
            check(f.host.begin_resource_epoch(f.host.context,&f.document,&f.resource) == BIB_ENGINE_OK,
                  "actual resource epoch was not issued");
            f.document.service_generation = f.host.begin_service_document(f.host.context,&f.document);
            check(f.document.service_generation,"actual service generation was not issued");
            f.damage(); return BIB_ENGINE_OK;
        });
        *result = {sizeof(*result),BIB_ENGINE_START_READY,instance}; return status;
    }
    static std::int32_t BIB_ENGINE_CALL current(std::uint64_t application, BibEngineDocumentV1* result) {
        auto& f = *active;
        return f.turn([&] { check(application == instance,"current document changed application"); *result = f.document; return BIB_ENGINE_OK; });
    }
    static std::int32_t BIB_ENGINE_CALL advance(const BibEngineAdvanceV1* input) {
        auto& f = *active; ++f.advances;
        return f.turn([&] {
            if (f.fail_advance) return BIB_ENGINE_PROCESS_EXIT_REQUIRED;
            check(input && input->application_instance == instance,"advance changed actual application");
            if (std::exchange(f.emit_next,false)) f.damage();
            return BIB_ENGINE_OK;
        });
    }
    static void copy(BibEngineReplyBufferV1* output, const Bytes& value) {
        check(output && output->bytes && value.size() <= output->capacity,"canonical mock reply exceeded caller storage");
        std::copy(value.begin(),value.end(),output->bytes);
    }
    static std::int32_t BIB_ENGINE_CALL query(const BibEngineQueryV1* input, BibEngineReplyBufferV1* output,
        BibEngineQueryResultV1* result) {
        auto& f = *active; ++f.queries;
        check(input && input->kind == BIB_ENGINE_QUERY_EDITOR_PROJECTION_V1,"bitmap presenter entered a second semantic controller");
        codec::ProjectionQuery request;
        check(codec::decode_projection_query({input->payload.data,input->payload.length},request),"query4 omitted canonical editor request");
        return f.turn([&] {
            ne::NativeProjection projection;
            if (f.projection && f.projection->identity.context == request.identity.context) projection = *f.projection;
            else {
                projection.editor_revision = 901; projection.surrounding = "A😀B"; projection.selection = {1,5};
                projection.mapping_id = 902; projection.frame_id = 903; projection.readback_attested = true;
                projection.caret = {12,24,1,18}; projection.input_purpose = "text";
                projection.retire = ne::NativeRetireMaterial{f.next_native_token++,902,request.identity.context,0};
            }
            projection.identity = request.identity; f.projection = projection;
            codec::ProjectionReply reply; reply.state = codec::ProjectionReply::State::available;
            reply.observation_revision = ++f.sample; reply.target = request.target; reply.projection = projection;
            reply.identity = request.identity; reply.readback_attested = true;
            Bytes bytes; check(codec::encode_projection_reply(reply,bytes),"canonical native projection could not encode"); copy(output,bytes);
            *result = {sizeof(*result),static_cast<std::uint32_t>(bytes.size()),input->expected,reply.observation_revision};
            return BIB_ENGINE_OK;
        });
    }
    static std::int32_t BIB_ENGINE_CALL command(const BibEngineCommandV1* input, BibEngineReplyBufferV1* output,
        BibEngineCommandResultV1* result) {
        auto& f = *active; ++f.commands;
        check(input && input->request_sequence,"native command omitted Owner correlation");
        if (input->operation <= 5) return f.turn([&] {
            check(input->operation == 3,"minimal fixture received unexpected key/mouse input");
            physical::Focus focus;
            check(physical::decode_focus({input->payload.data,input->payload.length},focus) == physical::Status::ok,
                  "physical bind/retire was not canonical FOCUS3");
            *result = {sizeof(*result),1,input->request_sequence,0,0}; return BIB_ENGINE_OK;
        });
        if (input->operation == BIB_ENGINE_COMMAND_EDITOR_OBSERVATION_V1) {
            codec::NativeRequestEnvelope request;
            check(codec::decode_native_request({input->payload.data,input->payload.length},request) && f.expected_head &&
                  request.request.packet == *f.expected_head && request.target.request_sequence == input->request_sequence &&
                  f.projection && request.request.resolved.retire == f.projection->retire &&
                  request.request.resolved.mapping_id == f.projection->mapping_id &&
                  request.request.resolved.editor_revision == f.projection->editor_revision &&
                  request.request.resolved.surrounding == f.projection->surrounding,
                  "native8 changed the genuine accepted head or its actual checked projection");
            return f.turn([&] {
                auto projection = request.request.resolved;
                ++projection.editor_revision; projection.surrounding = "AXB";
                projection.selection = {2,2}; projection.caret = {40,24,1,18};
                ne::NativeResult reply; reply.outcome = ne::Outcome::applied; reply.continuity = ne::Continuity::same;
                reply.availability = ne::NativeAvailability::available; reply.observation_revision = ++f.sample;
                reply.readback_identity = projection.identity; reply.readback_attested = true;
                reply.retire = projection.retire; reply.projection = projection;
                Bytes bytes; check(codec::encode_native_result({request.target,reply},bytes),
                                   "genuine native8 applied readback could not encode");
                copy(output,bytes);
                *result = {sizeof(*result),1,input->request_sequence,static_cast<std::uint32_t>(bytes.size()),0};
                f.projection = std::move(projection); ++f.native_observations; return BIB_ENGINE_OK;
            });
        }
        check(input->operation == BIB_ENGINE_COMMAND_EDITOR_REVOKE_V1,"minimal fixture received an unexpected editor operation");
        codec::RevocationEnvelope request;
        check(codec::decode_revocation({input->payload.data,input->payload.length},request) && f.projection &&
              request.request.material == f.projection->retire,"native9 changed actual provider retirement material");
        return f.turn([&] {
            ne::NativeResult reply; reply.outcome = f.unknown_revoke ? ne::Outcome::unknown : ne::Outcome::applied;
            reply.continuity = ne::Continuity::replaced; reply.availability = ne::NativeAvailability::unavailable;
            reply.observation_revision = ++f.sample; reply.readback_identity = request.request.identity;
            reply.readback_attested = true; reply.retired = request.request.material;
            Bytes bytes; check(codec::encode_native_result({request.target,reply},bytes),"canonical native9 result could not encode");
            copy(output,bytes); *result = {sizeof(*result),1,input->request_sequence,static_cast<std::uint32_t>(bytes.size()),0};
            ++f.retirements; f.projection.reset(); return BIB_ENGINE_OK;
        });
    }
    static std::int32_t BIB_ENGINE_CALL deliver(const BibEngineDocumentV1* target, const BibEngineBytesV1* input) {
        auto& f = *active; ++f.deliveries;
        return f.turn([&] {
            Envelope envelope; Span payload;
            check(target && target->service_generation == f.document.service_generation && input &&
                  decode_envelope({input->data,input->length},envelope,payload) == CodecStatus::ok &&
                  envelope.service_status == FOUNDATION_APPENDED_SERVICE_OK,"actual native completion changed status/identity");
            if (envelope.sequence == 1) {
                std::vector<FieldView> fields;
                check(decode_record(payload,fields) == CodecStatus::ok && !fields.empty() &&
                      read_u64(fields.front(),f.service_handle) && f.service_handle,"native discovery did not issue actual opaque route");
            }
            f.pending_ack = envelope.sequence; return BIB_ENGINE_OK;
        });
    }
    static std::uint32_t BIB_ENGINE_CALL collect(const BibEngineDocumentV1* target) {
        auto& f = *active; std::uint32_t status = FOUNDATION_APPENDED_SERVICE_UNAVAILABLE;
        const auto result = f.turn([&] {
            if (f.pending_ack) {
                status = f.host.stage_service_ack(f.host.context,target->service_generation,f.pending_ack);
                if (status == FOUNDATION_APPENDED_SERVICE_OK) f.pending_ack = 0;
            }
            return BIB_ENGINE_OK;
        });
        return result == BIB_ENGINE_OK ? status : FOUNDATION_APPENDED_SERVICE_UNAVAILABLE;
    }
    static std::int32_t BIB_ENGINE_CALL dispose(std::uint64_t application, std::uint64_t generation) {
        auto& f = *active; ++f.disposals;
        return f.turn([&] {
            check(application == instance && generation == f.document.service_generation,"disposal changed actual retired identity");
            f.host.retire_resource_epoch(f.host.context,f.resource.resource_epoch); return BIB_ENGINE_OK;
        });
    }
    void submit(std::uint64_t sequence, std::uint64_t handle, std::uint32_t operation, Span payload, bool notify = true) {
        Envelope envelope; envelope.generation = document.service_generation; envelope.sequence = sequence;
        envelope.interface_handle = handle; envelope.operation = operation;
        Bytes bytes; check(encode_envelope(envelope,payload,bytes) == CodecStatus::ok,"native fixture service packet could not encode");
        facts::ok(facts::call(*owner,FOUNDATION_ENGINE_SUBMIT,owner->identity(),bytes));
        if (notify) app->wake();
    }
    void discover() {
        const auto major = encode_u32(1), minor = encode_u32(0);
        const std::array<FieldView,4> fields{{
            {1,FieldType::utf8,true,{reinterpret_cast<const std::uint8_t*>(service_name.data()),service_name.size()}},
            {2,FieldType::u32,true,major},{3,FieldType::u32,true,minor},{4,FieldType::u32,true,minor}}};
        Bytes payload; check(encode_record(fields,payload) == CodecStatus::ok,"native discovery request could not encode");
        submit(1,0,FOUNDATION_APPENDED_CONTROL_DISCOVER,payload);
        until([&] { return service_handle && !pending_ack; },"native discovery/ACK did not settle");
    }
};

void readonly_frames() {
    Fixture f;
    check(!f.app->frame_ready(),"facade claimed a drawable frame before actual native extent");
    f.show(); const auto old = f.app->view();
    check(pixel(old) == std::array<std::uint8_t,3>{41,23,45},"readonly4083 changed copied frame bytes");
    check(!f.queries && !f.commands && f.starts == 1,"readonly4083 created an editor/controller or restarted native runtime");
    f.red = 73; f.emit_next = true; const auto before = f.calls; f.app->request_frame();
    check(f.calls == before,"frame demand entered native provider before owner turn");
    f.until([&] { return f.app->frame_ready() && pixel(f.app->view())[0] == 73; },"later actual native frame did not publish");
    check(pixel(old)[0] == 41,"later native frame mutated retained GUI pixels");
    check(!f.app->next_service() && !f.app->complete_service({}),"native facade exposed a second GUI service owner");
    f.close();
}
void owner_agreement() {
    Fixture f(false,false);
    auto other = std::make_shared<EngineOwner>(facts::package(),facts::configuration());
    const auto before = f.calls;
    rejects([&] { NativeEngineBitmapComposition invalid(f.adapter,other,*f.driver,f.profile,ui::ReadOnlyEngineBitmap{}); },
            "facade admitted a different Owner from its actual Driver");
    auto corrupt = f.profile; corrupt.build_sha256.front() ^= 1;
    rejects([&] { NativeEngineBitmapComposition invalid(f.adapter,f.owner,*f.driver,corrupt,ui::ReadOnlyEngineBitmap{}); },
            "facade admitted mismatched immutable4083 facts");
    rejects([&] { NativeEngineBitmapComposition invalid(f.adapter,f.owner,*f.driver,f.profile,ui::BoundEngineEditorPort{}); },
            "interactive4083 admitted a missing physical editor port");
    check(f.calls == before,"rejected admission entered or replayed native START");
    f.create(false); f.show(); f.close();
}
void presentation_retry() {
    Fixture f; f.show(); const auto original = f.app->view();
    f.red = 83; f.emit_next = true; f.adapter.fail_next = true; f.app->request_frame();
    bool failed{};
    for (unsigned step = 0; step < 12 && !failed; ++step) try { f.tick(); } catch (const std::runtime_error&) { failed = true; }
    check(failed && f.adapter.failures == 1 && f.app->presentation_pending(),"fixture did not retain actual failed presentation debt");
    const auto before = f.calls, advances = f.advances; unsigned qualified{};
    f.app->retry_presentation(); f.app->qualify([&] { ++qualified; });
    check(f.calls == before && f.advances == advances && qualified == 1,"presentation retry/qualification entered the provider");
    check(pixel(f.app->view())[0] == 83 && pixel(original)[0] == 41,"retry lost current/retained owned frame"); f.close();
}
void wake_barriers() {
    Fixture f; f.show(); f.tick();
    const auto prior_posts = f.posts.load(); f.synchronous_post = true; const auto before = f.calls;
    std::thread worker([&] { f.app->wake(); f.app->wake(); }); worker.join();
    check(f.calls == before,"worker/synchronous post entered the actual Driver");
    const auto posts = f.posts.load(); check(posts > prior_posts,"worker wake did not schedule owner work");
    f.app->wake(); check(f.posts.load() == posts,"pending native wake was not coalesced");
    f.synchronous_post = false; f.tick(); f.close();
}
void callback_facts() {
    Fixture f; f.show(); bool queued{};
    f.adapter.during_present = [&] {
        if (std::exchange(queued,true)) return;
        f.in_adapter = true; const auto before = f.calls;
        f.app->drawable_pixels(0,0); f.app->foreground(false); f.app->tick(f.now);
        check(f.calls == before,"new lifecycle fact or nested tick entered native provider during publication"); f.in_adapter = false;
    };
    f.red = 92; f.emit_next = true; f.app->request_frame();
    f.until([&] { return queued && !f.app->frame_ready(); },"new callback lifecycle version was overwritten by older publication");
    f.adapter.during_present = {}; const auto before = f.advances;
    f.app->retry_presentation(); check(f.advances == before,"background/invalid drawable retry advanced native engine");
    f.app->drawable_pixels(1200,900); f.app->foreground(true); f.red = 93; f.emit_next = true; f.app->request_frame();
    f.until([&] { return f.app->frame_ready(); },"restored native drawable facts did not rearm normal publication");
    check(f.app->view().client_size == gui::Size{800,600},"native extent changed fixed admitted provider viewport"); f.close();
}
void ordinary_turns() {
    Fixture f(false,true,true); f.show(); f.discover();
    // Exhaust the finite immediate-deadline hint with ordinary full cycles.
    // Subsequent explicitly supplied owner-loop turns must still run all phases.
    for (unsigned turn = 0; turn < 20; ++turn) f.tick();
    const auto due = f.app->deadline();
    check(!due || *due > f.now,"idle continuation hint never exhausted to a future/no deadline");
    check(!f.owner->native_effect(),"post-budget fixture already had a native effect ticket");
    // Simulate a trusted Owner producer without adding a new facade wake hint.
    // One normal turn must discover/redact this real pending native effect;
    // later normal turns may then run its actual Registry handler exactly once.
    f.submit(2,f.service_handle,1,encode_u32(41),false);
    f.tick();
    const auto admitted = f.owner->native_effect();
    check(admitted && admitted->ticket && !admitted->entered && !f.effects && f.adapter.snapshot().widgets.empty(),
          "ordinary turn after exhausted hint skipped Driver work or its App redaction settlement");
    f.until([&] { return f.effects == 1 && f.deliveries >= 2; },
            "ordinary turns after exhausted immediate hint did not finish real staged native work");
    check(f.effects == 1,"ordinary continuation replayed an actual native effect"); f.close();
}
void independent_holds() {
    Fixture f; f.show();
    f.app->set_owned_service_active(true); f.app->foreground(false); f.app->drawable_pixels(0,0); f.tick();
    check(!f.app->frame_ready() && f.adapter.snapshot().widgets.empty(),"combined native holds did not redact the actual frame");
    f.app->set_owned_service_active(false);
    for (unsigned turn = 0; turn < 12; ++turn) f.tick();
    check(!f.app->frame_ready() && f.adapter.snapshot().widgets.empty(),
          "releasing manual hold restored pixels while background/invalid extent still held them");
    f.app->foreground(true);
    for (unsigned turn = 0; turn < 12; ++turn) f.tick();
    check(!f.app->frame_ready() && f.adapter.snapshot().widgets.empty(),
          "foreground restoration bypassed the independent invalid-extent hold");
    f.red = 101; f.emit_next = true; f.app->drawable_pixels(800,600); f.app->request_frame();
    f.until([&] { return f.app->frame_ready() && pixel(f.app->view())[0] == 101; },
            "releasing all three holds did not wait for/publish an actual new native frame");
    f.app->set_owned_service_active(true); f.app->foreground(false); f.tick();
    f.app->foreground(true);
    for (unsigned turn = 0; turn < 12; ++turn) f.tick();
    check(!f.app->frame_ready() && f.adapter.snapshot().widgets.empty(),
          "releasing foreground hold bypassed the independent manual service hold");
    f.red = 102; f.emit_next = true; f.app->set_owned_service_active(false); f.app->request_frame();
    f.until([&] { return f.app->frame_ready() && pixel(f.app->view())[0] == 102; },
            "manual hold release did not restore only through a later actual frame"); f.close();
}
void interactive_close() {
    Fixture f(true); f.show(); check(f.queries && f.commands && f.port->editable(),"bound4083 did not use sole actual editor presenter");
    const auto before = f.calls; f.app->shutdown();
    check(f.calls == before,"editor close exported native cleanup from callback");
    f.until([&] { return f.app->native_state() == NativeEngineState::detached; },"close omitted App stage/settle for native9 retirement");
    check(f.retirements == 1 && !f.app->close_timed_out(),"normal editor close omitted/replayed native9 or claimed timeout");
    f.until([&] { return f.app->close_complete(); },"normal editor close did not finish its actual local App metadata");
}
void unknown_retention() {
    Fixture f(true); f.show(); f.unknown_revoke = true; f.app->shutdown();
    f.until([&] { return f.app->native_state() == NativeEngineState::process_exit_required; },"unknown native9 did not become process terminal");
    check(!f.app->close_complete(),"unknown native9 falsely completed local/native close");
    const auto before = f.calls; const std::weak_ptr<int> retained = f.capture;
    f.app->retry_presentation(); f.app->qualify({}); f.app->shutdown(); f.app.reset(); f.capture.reset();
    check(f.calls == before && !retained.expired(),"terminal facade destruction entered cleanup or dropped complete retained captures");
}
void close_timeout() {
    Fixture f(false,true,true); f.show(); f.discover(); f.hold_effect = true;
    f.submit(2,f.service_handle,1,encode_u32(41));
    f.until([&] { return f.effects == 1 && f.held_ticket; },"close fixture did not retain an actual native UI hold");
    const auto held = f.held_ticket; const auto id = f.owner->identity();
    f.app->shutdown(); f.tick();
    check(f.app->native_state() == NativeEngineState::closing && !f.owner->closed(),
          "close invented release of an actually held native effect");
    check(f.app->deadline().has_value(),"unresolved close omitted its bounded scheduling deadline");
    f.now += 11s; f.app->tick(f.now);
    check(f.app->close_timed_out() && f.app->native_state() != NativeEngineState::detached && !f.owner->closed(),
          "unresolved close ignored its bounded ten-second deadline");
    check(!f.app->close_complete(),"timed-out held native effect falsely completed close");
    check(id.application_instance == f.owner->identity().application_instance,"close timeout changed native application ownership");
    const auto before = f.calls; const std::weak_ptr<int> retained = f.capture;
    f.app.reset(); f.capture.reset();
    check(f.calls == before && !retained.expired(),"close timeout destroyed unresolved native captures or entered cleanup");
    check(f.owner->native_effect() && f.owner->native_effect()->ticket == held,
          "close timeout erased the actual held effect identity");
}
void registry_gate() {
    Fixture f(false,true,true); f.show(); f.discover();
    f.adapter.fail_next = true; f.submit(2,f.service_handle,1,encode_u32(41));
    bool failed{};
    for (unsigned step = 0; step < 16 && !failed; ++step) try { f.tick(); } catch (const std::runtime_error&) { failed = true; }
    check(failed && f.adapter.failures == 1 && f.app->presentation_pending() && !f.effects,
          "failed redaction publication admitted native Registry effect or lost real publication debt");
    const auto before = f.calls; f.app->retry_presentation(); check(!f.effects && f.calls == before,"redaction retry executed native effect/provider");
    f.until([&] { return f.effects == 1 && f.deliveries >= 2; },"checked redaction did not release one actual native effect");
    check(f.effects == 1,"native service effect replayed"); f.close();
}
void completed_head_close() {
    Fixture f(true); f.show();
    check(f.port->editor && f.port->editor->basis,"completed-head fixture has no actual checked editor Basis");
    const auto original_basis = *f.port->editor->basis;
    ne::Packet packet; packet.session = 1601; packet.basis = original_basis;
    packet.observation.id = 1701; packet.observation.kind = ne::Kind::text;
    packet.observation.authority = ne::Authority::range;
    packet.observation.before = {"A😀B",1,3,ne::Direction::forward,{1,5},6};
    packet.observation.after = ne::TextObservation{"AXB",2,2,ne::Direction::none,{2,2},3};
    packet.observation.data = ne::TextData{"insertText","X",{1,5},{}};
    check(ne::valid_observation(packet.observation),"completed-head fixture observation is not canonical");
    f.expected_head = packet;
    const auto entered = f.calls;
    const auto head = f.app->editor_submit(packet);
    check(head && f.calls == entered && !f.app->editor_take(*head),
          "real facade editor_submit entered native work or fabricated an immediate receipt");
    const ne::Settlement expected{packet.session,packet.observation.id,packet.basis.token,packet.observation.predecessor};
    f.until([&] {
        return f.native_observations == 1 && f.port->editor && f.port->editor->settlement == std::optional{expected};
    },"real native8 head did not complete and publish its actual paired settlement");
    check(f.port->editor->basis && f.port->editor->basis->surrounding == "AXB" &&
          f.port->editor->basis->selection == gui_surface::ByteRange{2,2} &&
          f.port->surface && f.port->surface->identity.presentation_revision == f.adapter.snapshot().revision,
          "known native8 result did not join the actual bitmap/Basis/settlement publication");
    const auto completed_editor = *f.port->editor;
    const auto completed_surface = f.port->surface;
    const auto completed_revision = f.adapter.snapshot().revision;
    const auto completed_calls = f.calls;
    f.app->retry_presentation(); f.app->retry_presentation();
    check(f.calls == completed_calls && f.port->editor == std::optional{completed_editor} &&
          f.port->surface == completed_surface && f.adapter.snapshot().revision == completed_revision,
          "untaken genuine completed head lost its exact paired publication or repeated native work");
    const auto native_before_close = f.native_observations;
    const std::weak_ptr<int> callback_lifetime = f.capture;
    f.capture.reset();
    check(!callback_lifetime.expired(),"completed-head facade lost its actual scheduling capture before close");
    f.app->shutdown();
    check(f.calls == completed_calls,"shutdown exported native work before its ordinary owner turn");
    ne::Packet successor; successor.session = packet.session; successor.basis = *completed_editor.basis;
    successor.observation.id = packet.observation.id + 1; successor.observation.predecessor = packet.observation.id;
    successor.observation.kind = ne::Kind::text; successor.observation.authority = ne::Authority::range;
    successor.observation.before = {"AXB",2,2,ne::Direction::none,{2,2},3};
    successor.observation.after = ne::TextObservation{"AXZB",3,3,ne::Direction::none,{3,3},4};
    successor.observation.data = ne::TextData{"insertText","Z",{2,2},{}};
    check(ne::valid_observation(successor.observation) && !f.app->editor_submit(successor) &&
          !f.app->close_complete() && f.calls == completed_calls,
          "closing admitted a valid fresh editor successor, completed early or entered provider from ingress");
    for (unsigned turn = 0; turn < 48 && f.app->native_state() != NativeEngineState::detached &&
         f.app->native_state() != NativeEngineState::process_exit_required; ++turn) f.tick();
    std::cout << "HEAD_CLOSE before_revision=" << completed_revision
              << " after_revision=" << f.adapter.snapshot().revision
              << " native8=" << f.native_observations << " native9=" << f.retirements
              << " owner_closed=" << f.owner->closed()
              << " driver_state=" << static_cast<unsigned>(f.app->native_state())
              << " published_settlement=" << bool(f.port->editor && f.port->editor->settlement)
              << " published_basis=" << bool(f.port->editor && f.port->editor->basis)
              << " published_retirement=" << bool(f.port->editor && f.port->editor->retirement) << '\n';
    check(f.native_observations == native_before_close && f.retirements == 1 && f.owner->closed() &&
          f.app->native_state() == NativeEngineState::detached && !f.app->close_complete(),
          "held completed head did not reach one real known native9 and actual Owner close");
    const auto publication_at_take = f.port->editor;
    check(publication_at_take && publication_at_take->settlement == std::optional{expected} &&
          publication_at_take->retirement && publication_at_take->retirement->authority_retired &&
          publication_at_take->retirement->readback_attested && publication_at_take->retirement->observation_revision,
          "native detach erased the actual checked retirement/settlement before original head Take");
    const auto calls_at_take = f.calls;
    const auto completion = f.app->editor_take(*head);
    std::cout << "HEAD_CLOSE take=" << bool(completion)
              << " take_receipt=" << bool(completion && completion->result.receipt)
              << " callback_capture_live=" << !callback_lifetime.expired() << '\n';
    check(completion && completion->ticket == *head && completion->result.admission == ne::Admission::completed &&
          completion->result.receipt,"actual close lost the genuine already-completed head metadata Take");
    const auto& receipt = *completion->result.receipt;
    check(receipt.outcome == ne::Outcome::applied && receipt.session == packet.session &&
          receipt.id == packet.observation.id && receipt.submitted_token == packet.basis.token &&
          receipt.predecessor == packet.observation.predecessor && publication_at_take &&
          publication_at_take->settlement == std::optional{expected} && receipt.basis == publication_at_take->basis &&
          receipt.retirement == publication_at_take->retirement && !f.app->editor_take(*head) && f.calls == calls_at_take,
          "close changed the known native outcome/correlation, split current publication or replayed Take/native work");
    if (receipt.basis) check(receipt.basis == completed_editor.basis,
                             "close replaced completed Basis without checked retirement publication");
    else check(receipt.retirement && receipt.retirement->authority_retired &&
               receipt.retirement->readback_attested && receipt.retirement->observation_revision,
               "close withdrew a completed Basis without actual checked native9 retirement proof");
    f.until([&] { return f.app->close_complete(); },"detached local App metadata did not finish after actual original head Take");
    check(f.calls == calls_at_take && f.app->native_state() == NativeEngineState::detached,
          "detached App metadata close reentered Driver/provider or changed actual native state");
    const auto closed_calls = f.calls;
    f.app.reset();
    check(f.calls == closed_calls && callback_lifetime.expired(),
          "honestly drained/taken completed-head close repeated native work or retained unnecessary facade captures");
}
} // namespace

int main(int argc, char** argv) {
    try {
        check(argc == 2,"one fresh-process native bitmap scenario required"); const std::string_view scenario(argv[1]);
        if (scenario == "readonly-frames") readonly_frames();
        else if (scenario == "owner-agreement") owner_agreement();
        else if (scenario == "presentation-retry") presentation_retry();
        else if (scenario == "wake-barriers") wake_barriers();
        else if (scenario == "callback-facts") callback_facts();
        else if (scenario == "ordinary-turns") ordinary_turns();
        else if (scenario == "independent-holds") independent_holds();
        else if (scenario == "interactive-close") interactive_close();
        else if (scenario == "unknown-retention") unknown_retention();
        else if (scenario == "close-timeout") close_timeout();
        else if (scenario == "registry-gate") registry_gate();
        else if (scenario == "completed-head-close") completed_head_close();
        else throw std::runtime_error("unknown native bitmap composition scenario");
        std::cout << "PASS " << scenario << ": " << assertions << " assertions; actual Owner/Driver/App/Policy, mock C provider, no engine/SDK/DSO\n";
        return 0;
    } catch (const std::exception& error) { std::cerr << "FAIL: " << error.what() << '\n'; return 1; }
}
