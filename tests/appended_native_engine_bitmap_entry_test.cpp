// SPDX-License-Identifier: CC0-1.0
// Actual entry, native Surface/factory and real source validators; all physical
// startup/provider/facade/window boundaries are explicit fixture values.
#include "fixtures/appended_engine_bitmap/state.hpp"
#include "../gui/hosts/appended_engine_native_entry.hpp"

#include <iostream>
#include <sstream>
#include <string>
#include <thread>
#include <vector>

#if defined(FOUNDATION_APPENDED_BINARY_CAPABILITY) && FOUNDATION_APPENDED_BINARY_CAPABILITY
namespace foundation::appended {
std::unique_ptr<EngineModuleBinding> make_engine_module_binding(std::span<const std::uint8_t>,
        std::span<const NativeServiceRegistration>,std::uint64_t) {
    ++bitmap_entry_fixture::state.factories;return std::make_unique<EngineModuleBinding>();
}
}
#endif

namespace {
namespace t=bitmap_entry_fixture;
namespace entry=foundation::host::native_bitmap_entry;
using foundation::host::NativeSurfaceMode;
using foundation::host::NativeSurfaceSession;
using foundation::appended::NativeEngineDriver;
using foundation::appended::NativeEngineState;

void zero(unsigned value,const char* message) { t::require(value==0,message); }
bool named(std::initializer_list<std::string_view> names) {
    return std::find(names.begin(),names.end(),t::state.scenario)!=names.end();
}
void publisher_forwarding() {
    unsigned pairs{},editors{},retirements{},services{};
    foundation::host::NativeSurfacePublisher publisher;
    publisher.capabilities.supported=8255;publisher.capabilities.mouse_input_version=1;publisher.generation=912;
    publisher.present_pair=[&](gui::Snapshot snapshot,const foundation::gui_surface::Presentation& surface) {
        ++pairs;t::require(snapshot.revision==11&&surface.identity.context==12,"port changed bitmap/surface publication");
        return foundation::gui_surface::CommitResult{foundation::gui_surface::Status::busy,{}};
    };
    publisher.present_editor_pair=[&](gui::Snapshot snapshot,const foundation::gui_surface::Presentation& surface,
            std::optional<foundation::gui_editor::EditorPublication> publication,
            std::optional<foundation::gui_editor::CompositionFact> composition) {
        ++editors;t::require(snapshot.revision==21&&surface.identity.context==12&&publication&&publication->basis&&
            publication->basis->token==22&&composition&&composition->transaction==23,"port changed editor publication");
        return foundation::gui_surface::CommitResult{foundation::gui_surface::Status::closed,{}};
    };
    publisher.present_editor_retirement=[&](gui::Snapshot snapshot,foundation::gui_editor::EditorPublication publication) {
        ++retirements;t::require(snapshot.revision==31&&publication.settlement&&publication.settlement->id==32,
            "port changed retirement publication");
        return foundation::gui_surface::CommitResult{foundation::gui_surface::Status::unavailable,{}};
    };
    publisher.set_owned_service_active=[&](bool value) {++services;return value;};
    entry::NativeEngineEditorPort port(publisher);
    t::require(port.capabilities()==publisher.capabilities&&port.generation()==912,"port changed publisher capabilities/generation");
    foundation::gui_surface::Presentation surface;surface.identity.context=12;
    gui::Snapshot snapshot;snapshot.revision=11;
    t::require(port.present_pair(snapshot,surface).status==foundation::gui_surface::Status::busy,"port rewrote bitmap receipt");
    snapshot.revision=21;foundation::gui_editor::EditorPublication publication;
    publication.basis=foundation::gui_editor::Basis{};publication.basis->token=22;
    foundation::gui_editor::CompositionFact composition;composition.transaction=23;
    t::require(port.present_editor_pair(snapshot,surface,publication,composition).status==foundation::gui_surface::Status::closed,
        "port rewrote editor receipt");
    snapshot.revision=31;publication={};publication.settlement=foundation::gui_editor::Settlement{};publication.settlement->id=32;
    t::require(port.present_editor_retirement(snapshot,publication).status==foundation::gui_surface::Status::unavailable,
        "port rewrote retirement receipt");
    port.set_owned_service_active(true);bool closed_rejected{};
    try{port.set_owned_service_active(false);}catch(const std::logic_error&){closed_rejected=true;}
    t::require(closed_rejected&&pairs==1&&editors==1&&retirements==1&&services==2,"port skipped, repeated or hid publisher closure");
    for(unsigned field=0;field<5;++field) {
        auto incomplete=publisher;
        if(field==0)incomplete.generation=0;
        if(field==1)incomplete.present_pair={};
        if(field==2)incomplete.present_editor_pair={};
        if(field==3)incomplete.present_editor_retirement={};
        if(field==4)incomplete.set_owned_service_active={};
        bool rejected{};try{entry::NativeEngineEditorPort invalid(std::move(incomplete));}catch(const std::invalid_argument&){rejected=true;}
        t::require(rejected,"port admitted an incomplete publication handle");
    }
}
int run_backend(entry::Factory factory,const entry::Invocation& invocation) {
    auto& s=t::state;++s.runner;t::event("runner");
    t::require(s.start==1&&s.bind==1&&s.configures==1,"runner preceded unique prepared Driver startup");
    const auto expected_root=t::is("default-runtime")?t::installed_root():
        named({"utf8-root","utf8-both"})?t::unicode_runtime_root():t::runtime_root();
    t::require(invocation.runtime_root==expected_root,"runner received another runtime root");
    t::require(invocation.read_only==s.expected_read_only,"runner changed read-only selection");
    t::require(bool(invocation.output)==named({"output-required","utf8-output","utf8-both"}),"runner changed framebuffer output selection");
    if(invocation.output)t::require(*invocation.output==(named({"utf8-output","utf8-both"})?t::unicode_output_path():t::output_path()),"runner changed output path");
    t::require(factory.window.width==800&&factory.window.height==600&&factory.window.scale==1&&
        factory.window.title==std::string("Bitmap entry fixture")+(s.expected_read_only?" (view only)":""),
        "root did not preserve neutral title/fixed viewport");
    t::require(factory.mode==(s.expected_read_only?NativeSurfaceMode::none:NativeSurfaceMode::editor_v1),
        "root selected a different native surface mode");
    t::require(factory.application&&!factory.prepare_peer,"root omitted App factory or installed a backend-owned peer");
    t::require(bool(factory.editor.terminal.notify)==!s.expected_read_only,"root changed editor terminal hook selection");
    if(!s.expected_read_only){
        t::require(factory.editor.terminal.context==s.bound_owner,"terminal hook substituted Owner");
        s.terminal_notify=[hook=factory.editor.terminal]{hook.notify(hook.context);};
    }
    if(t::is("runner-failure"))throw std::runtime_error("synthetic backend setup failure");
    if(t::is("runner-nonstd"))throw 19;
    if(t::is("runner-return-failure"))return 1;
    if(t::is("runner-no-app"))return 0;
    const auto original_application=std::move(factory.application);
    factory.application=[original_application](foundation::host::NativeSurfaceAdapter& adapter) {
        ++t::state.application_attempts;return original_application(adapter);
    };
    if(t::is("unsupported-editor"))factory.mode=NativeSurfaceMode::none;
    const auto mode=factory.mode;
    factory.prepare_peer=[mode](gui::Adapter& backend,const foundation::host::NativeSurfaceWindow&,
            foundation::host::NativeSurfaceIngress) {
        foundation::host::NativeSurfacePeer peer;
        if(mode==NativeSurfaceMode::editor_v1){peer.capabilities.supported=8255;peer.capabilities.mouse_input_version=1;}
        peer.ready=[] { return !t::is("peer-not-ready"); };
        peer.present=[&backend](gui::Snapshot value) {
            const auto revision=value.revision;++t::state.renders;backend.present(std::move(value));
            return foundation::host::NativeRenderReceipt{revision};
        };
        peer.editor=[](const foundation::host::NativeEditorPresentation&) {};
        peer.suspend=[] {};
        return peer;
    };
    NativeSurfaceSession<entry::PreparedApplication,t::Adapter> session(std::move(factory));
    auto& app=session.application;
    auto* driver=static_cast<NativeEngineDriver*>(s.bound_driver);
    t::require(driver&&s.facades==1,"actual App factory did not construct exactly one facade");
    if(t::is("runner-after-app-failure"))throw std::runtime_error("synthetic post-App runner failure");
    if(t::is("runner-after-app-nonstd"))throw 23;
    if(t::is("runner-after-app-return-failure"))return 1;
    if(t::is("runner-unresolved"))return 0;
    if(t::is("runner-detached-without-shutdown")){
        driver->state(NativeEngineState::detached);
        t::require(!app.runner_state().close_complete,"detached Driver fabricated unrequested App close");
        return 0;
    }
    if(t::is("runner-hooks")) {
        publisher_forwarding();
        const auto ticks=s.driver_ticks,facade_ticks=s.facade_ticks;
        const auto connections=s.connections;
        app.drawable_pixels(801,0);app.foreground(false);app.handle(gui::CloseEvent{});
        app.request_frame();app.retry_presentation();bool presented{};app.qualify([&]{presented=true;});
        t::require(presented&&app.frame_ready()&&app.input_epoch()==17&&!app.presentation_pending(),"root changed generic facade forwarding");
        const auto reads=s.service_reads,completions=s.service_completions;
        t::require(!app.next_service()&&!app.complete_service({})&&s.service_reads==reads+1&&s.service_completions==completions+1,
            "root omitted generic service forwarding");
        foundation::gui_surface::Capabilities caps;caps.supported=8255;caps.mouse_input_version=1;
        app.surface_connected(caps);
        foundation::gui_surface::AcceptedEvent input;input.event.sequence=31;app.surface_input(std::move(input));
        foundation::gui_surface::Revocation revoked;revoked.reason=foundation::gui_surface::RevocationReason::service;
        app.surface_revoked(std::move(revoked));
        foundation::gui_editor::Packet packet;packet.session=41;packet.basis.token=42;packet.observation.id=43;
        foundation::gui_editor::Revocation revoke;revoke.incarnation=51;
        t::require(app.editor_submit(std::move(packet))==73&&app.editor_revoke(std::move(revoke))==74,
            "root changed owned editor submission results");
        const auto completion=app.editor_take(75);app.editor_resync();
        t::require(completion&&completion->ticket==75,"root changed exact editor completion");
        t::require(s.driver_ticks==ticks&&s.facade_ticks==facade_ticks,"callback forwarding synchronously advanced provider work");
        t::require(s.connections==connections+1&&s.surface_events==1&&s.surface_revocations==1&&
            s.editor_submits==1&&s.editor_revokes==1&&s.editor_takes==1&&s.editor_resyncs==1,
            "root missed or repeated a neutral callback");
        auto* token=static_cast<entry::WakeToken*>(driver->wake.context);
        t::require(token&&driver->wake.post_owner_wake&&s.facade_wake,"root omitted process-held scheduling hooks");
        token->pending.store(false,std::memory_order_release);
        std::thread producer([]{t::state.facade_wake();});producer.join();
        t::require(token->pending.load(std::memory_order_acquire)&&s.driver_ticks==ticks&&s.facade_ticks==facade_ticks,
            "facade worker wake entered the scoped application");
        const auto awake=app.runner_state();
        t::require(awake.deadline&&*awake.deadline<=entry::Clock::now(),"facade wake did not select a later owner turn");
        session.tick();
        t::require(!token->pending.load(std::memory_order_acquire)&&s.wake_cleared,"owner turn did not clear wake before facade work");
        const auto before=s.driver_ticks;
        std::thread native([&]{driver->wake.post_owner_wake(driver->wake.context);});native.join();
        t::require(token->pending.load(std::memory_order_acquire)&&s.driver_ticks==before,
            "native worker wake pumped Driver or lost its live token");
        session.tick();
    }
    if(t::is("runner-terminal")||t::is("runner-blocked")) {
        driver->state(t::is("runner-terminal")?NativeEngineState::process_exit_required:NativeEngineState::blocked);
        const auto status=app.runner_state();
        t::require(status.close_requested&&!status.close_complete&&status.exit_code==1,"terminal runner fabricated successful close");
        return 1;
    }
    app.shutdown();
    const auto closing=app.runner_state();
    t::require(closing.close_requested&&!closing.close_complete&&closing.deadline&&
        *closing.deadline<=entry::Clock::now()+std::chrono::seconds(10),"wrapper lost facade close intent/budget");
    if(t::is("close-timeout")) {
        t::require(closing.exit_code==1,"facade close timeout did not select failure");return 1;
    }
    session.tick();
    if(t::is("close-terminal")||t::is("close-blocked"))return 1;
    if(t::is("runner-detached-metadata-debt")||t::is("runner-detached-metadata-drained")){
        t::require(driver->state()==NativeEngineState::detached&&!app.runner_state().close_complete,
            "detached Driver fabricated metadata retirement completion");
        if(t::is("runner-detached-metadata-debt"))return 0; // Deliberate premature runner success.
        const auto ticks=s.driver_ticks;
        session.tick();
        t::require(s.driver_ticks==ticks&&s.metadata_settles==1,"App-only metadata settle reentered detached Driver");
    }
    const auto done=app.runner_state();
    t::require(done.close_complete&&done.exit_code==0,"normal facade close did not detach");
    return 0;
}
int invoke(std::vector<std::string> values,entry::EntryOptions options) {
    std::vector<char*> args;for(auto& value:values)args.push_back(value.data());
    return entry::run(static_cast<int>(args.size()),args.data(),options,run_backend);
}
struct OutputCapture {
    std::ostringstream out,err;
    std::streambuf* old_out=std::cout.rdbuf(out.rdbuf());
    std::streambuf* old_err=std::cerr.rdbuf(err.rdbuf());
    ~OutputCapture(){std::cout.rdbuf(old_out);std::cerr.rdbuf(old_err);}
};
}

int main(int argc,char** argv) {
    auto& s=t::state;
    try {
        t::require(argc==2,"select exactly one fresh-process case");s.scenario=argv[1];
        std::vector<std::string> args{"bitmap-fixture","--engine-runtime-root",t::runtime_root().generic_string()};
        entry::EntryOptions options{};int wanted=0;
        bool cli_rejection{},profile_rejection{};
        if(t::is("foreign-native-target")) {
#if FOUNDATION_APPENDED_ENGINE_NATIVE_DOCUMENT_ACTIONS_PROFILE
            auto& selected=s.actions_profile;
#else
            auto& selected=s.profile;
#endif
#if defined(_WIN32)
            selected.target_system=BIB_ENGINE_TARGET_LINUX;
#else
            selected.target_system=BIB_ENGINE_TARGET_WINDOWS;
#endif
            selected.target_processor=BIB_ENGINE_CPU_X86_64;selected.pointer_bits=64;
#if FOUNDATION_APPENDED_ENGINE_NATIVE_DOCUMENT_ACTIONS_PROFILE
            t::require(foundation::appended::engine_document_actions::document_actions_profile_valid(selected),"foreign target counterfactual invalidated actions facts");
#else
            t::require(foundation::appended::engine_document::document_profile_valid(selected),"foreign target counterfactual invalidated pixel facts");
#endif
            profile_rejection=true;
        } else
#if FOUNDATION_APPENDED_ENGINE_NATIVE_DOCUMENT_ACTIONS_PROFILE
        if(s.scenario.starts_with("actions-plan-")) {
            s.actions_mismatch=std::stoi(s.scenario.substr(13));t::require(s.actions_mismatch>=0&&s.actions_mismatch<=96,"invalid actions plan field");profile_rejection=true;
        } else if(s.scenario.starts_with("actions-facts-")) {
            const auto index=std::stoi(s.scenario.substr(14));t::require(index>=0&&index<=90,"invalid compiled actions field");t::alter_actions(s.actions_profile,index);profile_rejection=true;
        } else if(t::is("actions-browser")) {
            s.actions_profile.target_system=BIB_ENGINE_TARGET_BROWSER_WASM;s.actions_profile.target_processor=BIB_ENGINE_CPU_WASM32;s.actions_profile.pointer_bits=32;profile_rejection=true;
        } else if(named({"actions-legacy-document","actions-legacy-editor","actions-legacy-document-dirty","actions-legacy-editor-dirty", "actions-valid-build-divergence","actions-valid-recipe-divergence"}))profile_rejection=true;
        else
#else
        if(s.scenario.starts_with("profile-")) {
            s.mismatch=std::stoi(s.scenario.substr(8));t::require(s.mismatch>=0&&s.mismatch<=36,"invalid pixel plan field");profile_rejection=true;
        } else if(named({"pixel-legacy-actions","pixel-legacy-actions-dirty","pixel-legacy-editor","pixel-legacy-editor-dirty","pixel-valid-build-divergence","pixel-valid-recipe-divergence"}))profile_rejection=true;
        else if(t::is("physical-profile")) {
            s.profile.kind=foundation::appended::engine_document::ProfileKind::physical;s.profile.name=foundation::appended::engine_document::kPhysicalProfileName;s.profile.provider_capabilities=2003;s.profile.physical_catalog_sha256=foundation::appended::engine_document::kPhysicalCatalogSha256;profile_rejection=true;
        } else if(t::is("browser-profile")) {
            s.profile.target_system=BIB_ENGINE_TARGET_BROWSER_WASM;s.profile.target_processor=BIB_ENGINE_CPU_WASM32;s.profile.pointer_bits=32;profile_rejection=true;
        } else
#endif
        if(t::is("help"))args={"bitmap-fixture","--help"};
        else if(t::is("default-runtime")||t::is("default-runtime-failure"))args={"bitmap-fixture"};
        else if(t::is("cli-missing")){args.pop_back();cli_rejection=true;}
        else if(t::is("cli-relative")){args[2]="relative/runtime";cli_rejection=true;}
        else if(t::is("cli-normalized")){args[2]=(t::runtime_root().parent_path()/"../runtime").generic_string();cli_rejection=true;}
        else if(t::is("cli-flag")){args[1]="--runtime";cli_rejection=true;}
        else if(t::is("cli-extra")){args.push_back("extra");cli_rejection=true;}
        else if(t::is("cli-duplicate-root")){args.insert(args.end(),{"--engine-runtime-root",t::runtime_root().generic_string()});cli_rejection=true;}
        else if(t::is("cli-duplicate-view")){args.insert(args.end(),{"--view-only","--view-only"});cli_rejection=true;}
        else if(t::is("cli-empty")){args.clear();cli_rejection=true;}
        else if(t::is("cli-many")){args.insert(args.end(),6,"--view-only");cli_rejection=true;}
        else if(t::is("view-only"))args.push_back("--view-only");
        else if(t::is("read-only-default"))options.read_only=true;
        else if(t::is("output-required")){options.output_required=true;options.read_only=true;args.push_back(t::output_path().generic_string());}
        else if(t::is("output-missing")){options.output_required=true;cli_rejection=true;}
        else if(t::is("output-extra")){options.output_required=true;args.insert(args.end(),{t::output_path().generic_string(),t::output_path().generic_string()+".extra"});cli_rejection=true;}
        else if(named({"utf8-root","utf8-output","utf8-both"})){
            if(!t::is("utf8-output"))args[2]=t::utf8_bytes(t::unicode_runtime_root());
            if(!t::is("utf8-root")){
                options.output_required=true;options.read_only=true;
                args.push_back(t::utf8_bytes(t::unicode_output_path()));
            }
        }
        else if(s.scenario.starts_with("utf8-root-")||s.scenario.starts_with("utf8-output-")){
            const bool output=s.scenario.starts_with("utf8-output-");
            const auto kind=s.scenario.substr(output?12:10);std::string invalid;
            if(kind=="overlong")invalid="\xC0\xAF";
            else if(kind=="surrogate")invalid="\xED\xA0\x80";
            else if(kind=="truncated")invalid="\xF0\x9F\x92";
            else if(kind=="range")invalid="\xF4\x90\x80\x80";
            else if(kind=="continuation")invalid="\x80";
            else t::require(false,"unknown invalid UTF-8 selector");
            if(output){options.output_required=true;options.read_only=true;args.push_back("image-"+invalid+".ppm");}
            else args[2]=t::utf8_bytes(t::runtime_root())+"/"+invalid;
            cli_rejection=true;
        }
        else if(t::is("utf8-path-helper")){
            const auto valid=t::utf8_bytes(t::unicode_runtime_root());
            t::require(entry::argument_path(valid)==t::unicode_runtime_root(),"path helper changed UTF-8 scalar bytes");
            for(const auto& invalid:{std::string{},std::string("a\0b",3),std::string("\xED\xA0\x80")}){
                bool rejected{};try{(void)entry::argument_path(invalid);}catch(const std::invalid_argument&){rejected=true;}
                t::require(rejected,"path helper accepted empty, NUL or malformed UTF-8");
            }
            zero(s.self,"pure path helper entered native payload loading");
        }
        else if(t::is("binary-payload"))s.binary=true;
        else if(t::is("unconfigured-start"))s.configured=false;
        else if(t::is("unadopted-start"))s.adopt_identity=false;
        else t::require(named({"graceful","start-waiting","runner-hooks","missing-payload","corrupt-payload","invalid-startup","plan-root","verify-failure","load-failure","bind-failure","start-terminal","start-blocked","start-bound","runner-terminal","runner-blocked","close-terminal","close-blocked","close-timeout","runner-failure","runner-nonstd","runner-return-failure","runner-no-app","peer-not-ready","facade-failure","runner-after-app-failure","runner-after-app-nonstd","runner-after-app-return-failure","runner-unresolved","runner-detached-without-shutdown","runner-detached-metadata-debt","runner-detached-metadata-drained","unsupported-editor"}),"unknown bitmap entry case");
        if(profile_rejection||cli_rejection||named({"default-runtime-failure","missing-payload","corrupt-payload","invalid-startup","plan-root","verify-failure","load-failure","bind-failure","unconfigured-start","unadopted-start","start-terminal","start-blocked","start-bound","runner-terminal","runner-blocked","close-terminal","close-blocked","close-timeout","runner-failure","runner-nonstd","runner-return-failure","runner-no-app","peer-not-ready","facade-failure","runner-after-app-failure","runner-after-app-nonstd","runner-after-app-return-failure","runner-unresolved"}))wanted=1;
        if(t::is("runner-detached-without-shutdown")||t::is("runner-detached-metadata-debt"))wanted=1;
#if FOUNDATION_APPENDED_ENGINE_NATIVE_DOCUMENT_ACTIONS_PROFILE
        s.expected_read_only=options.read_only||t::is("view-only");
        if(t::is("unsupported-editor"))wanted=1;
#else
        s.expected_read_only=true;
        t::require(!t::is("unsupported-editor"),"unsupported-editor requires actions build");
#endif
#if !defined(FOUNDATION_APPENDED_BINARY_CAPABILITY) || !FOUNDATION_APPENDED_BINARY_CAPABILITY
        if(s.binary)wanted=1;
#endif
        s.on_facade_tick=[] {
            auto* driver=static_cast<NativeEngineDriver*>(t::state.bound_driver);
            auto* token=static_cast<entry::WakeToken*>(driver->wake.context);
            t::require(token&&!token->pending.load(std::memory_order_acquire),"facade tick observed uncleared root wake");t::state.wake_cleared=true;
        };
        int result{};std::string output,errors;
        {OutputCapture captured;result=invoke(std::move(args),options);output=captured.out.str();errors=captured.err.str();}
        if(!t::invariant_failure.empty())throw std::runtime_error("entry swallowed fixture invariant: "+t::invariant_failure);
        if(result!=wanted)throw std::runtime_error("unexpected entry result: "+errors.substr(0,2048));
        t::require(!s.forbidden_cleanup,"entry entered Driver after terminal/blocked state");
        if(t::is("help")||cli_rejection||t::is("default-runtime-failure")){zero(s.self,"CLI/default failure read payload");zero(s.plans,"CLI/default failure generated a plan");}
        else t::require(s.self==1&&!s.events.empty()&&s.events.front()=="payload","strict native payload read did not precede admission");
        if(t::is("default-runtime")||t::is("default-runtime-failure"))t::require(s.resolves==1,"default runtime did not call exact hint helper once");
        else zero(s.resolves,"explicit override/help/CLI unexpectedly used runtime hint helper");
        if(t::is("help"))t::require(output.find("--engine-runtime-root")!=std::string::npos,"entry lost help contract");
        if(named({"missing-payload","corrupt-payload"}))zero(s.plans,"invalid payload reached generated plan");
        if(profile_rejection||t::is("plan-root")){t::require(s.plans==1,"selected profile disagreement did not reach its generated plan");zero(s.owners,"invalid profile/plan constructed Owner");zero(s.verify,"invalid profile/plan reached verifier");zero(s.load,"invalid profile/plan loaded a provider");}
        if(t::is("invalid-startup")){t::require(s.owners==1,"startup bypassed Owner");zero(s.verify,"invalid startup reached verification");}
        if(t::is("verify-failure")){t::require(s.verify==1,"verification fault was not reached");zero(s.load,"failed verification loaded a provider");}
        if(t::is("load-failure")){t::require(s.load==1,"load fault was not reached");zero(s.bind,"failed load bound a provider");}
        if(t::is("bind-failure")){t::require(s.bind==1,"bind fault was not reached");zero(s.start,"failed bind started a provider");}
        if(s.load)t::require(s.owners==1&&s.verify==1&&s.events[2]=="owner"&&s.events[3]=="verify"&&s.events[4]=="load","Owner/verification/load ordering changed");
        if(s.start)t::require(s.start==1&&s.bind==1&&s.configures==1,"provider or Owner startup repeated");
        if(named({"unconfigured-start","unadopted-start","start-terminal","start-blocked","start-bound"})){t::require(s.start==1&&s.configures==1,"startup fault was not reached");zero(s.runner,"invalid startup reached runner");}
        if(named({"runner-failure","runner-nonstd","runner-return-failure","runner-no-app","peer-not-ready"})){t::require(s.runner==1,"runner fault was not reached");zero(s.facades,"pre-App failure constructed a facade");zero(s.application_attempts,"pre-App fault invoked App factory");t::require(s.close_requests==1&&s.driver_ticks==1,"pre-App failure bypassed bounded known-safe close");}
        if(named({"start-terminal","start-blocked","runner-terminal","runner-blocked"})){zero(s.close_requests,"terminal state attempted close exports");zero(s.driver_ticks,"terminal state advanced provider");}
        if(named({"facade-failure","runner-after-app-failure","runner-after-app-nonstd","runner-after-app-return-failure","runner-unresolved","close-timeout","unsupported-editor"})){t::require(s.runner==1&&s.application_attempts==1,"post-App fault did not attempt actual App construction");if(!t::is("unsupported-editor"))t::require(s.facades==1,"post-App fault missed facade construction");zero(s.close_requests,"post-App failure attempted forced close exports");zero(s.driver_ticks,"post-App failure attempted forced Driver ticks");}
        if(t::is("close-terminal")||t::is("close-blocked"))t::require(s.close_requests==1&&s.driver_ticks==1,"terminal close was retried after facade/window shutdown");
        if(t::is("runner-detached-without-shutdown")){
            t::require(s.facades==1&&s.facade_destroys==1&&s.metadata_settles==0,
                "premature detached return missed actual scoped App construction/destruction");
            zero(s.close_requests,"post-GUI detached return attempted provider close");
            zero(s.driver_ticks,"post-GUI detached return entered provider");
        }
        if(t::is("runner-detached-metadata-debt")||t::is("runner-detached-metadata-drained")){
            t::require(s.facades==1&&s.facade_destroys==1&&s.close_requests==1&&s.driver_ticks==1,
                "metadata close repeated provider work after detached return or GUI destruction");
            t::require(s.metadata_settles==(t::is("runner-detached-metadata-drained")?1u:0u),
                "App metadata debt was invented or silently cleared");
        }
        if(t::is("runner-hooks")) {
            t::require(s.pixels==1&&s.foreground==1&&s.handled==1&&s.frame_requests==1&&s.retry==1&&s.qualify==1&&s.wake_cleared,"wrapper missed queued bitmap hooks");
            auto* driver=static_cast<NativeEngineDriver*>(s.bound_driver);auto* token=static_cast<entry::WakeToken*>(driver->wake.context);
            token->pending.store(false,std::memory_order_release);const auto ticks=s.driver_ticks,facade_ticks=s.facade_ticks;
            std::thread late([&]{driver->wake.post_owner_wake(driver->wake.context);s.facade_wake();});late.join();
            t::require(token->pending.load(std::memory_order_acquire)&&s.driver_ticks==ticks&&s.facade_ticks==facade_ticks,"late wake captured dead scoped GUI or pumped work");
            if(s.terminal_notify){s.terminal_notify();t::require(s.terminal_notifications==1&&s.driver_ticks==ticks,"root terminal hook missed Owner or entered provider");}
        }
        if(s.binary) {
#if defined(FOUNDATION_APPENDED_BINARY_CAPABILITY) && FOUNDATION_APPENDED_BINARY_CAPABILITY
            t::require(s.factories==1&&s.start==1,"explicitboth lost counted binary factory");
#else
            zero(s.verify,"web-only binary reached verifier");zero(s.load,"web-only binary loaded provider");zero(s.factories,"web-only unexpectedly called module factory");
#endif
        }
        else zero(s.factories,"binary-free payload initialized a module");
        std::cout<<"PASS "<<s.scenario<<" (entry/factory with mock physical boundaries only)\n";return 0;
    } catch(const std::exception& error) { std::cerr<<"FAIL "<<s.scenario<<": "<<error.what()<<'\n';return 1; }
}
