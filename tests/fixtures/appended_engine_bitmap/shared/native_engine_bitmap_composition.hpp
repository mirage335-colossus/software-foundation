// TEST ONLY: counted facade boundary; actual entry and neutral Surface stay real.
#pragma once
#include "shared/native_engine_loader.hpp"
#include "shared/engine_surface_port.hpp"
#include <foundation/gui/surface_editor.hpp>

namespace foundation::ui {
struct ReadOnlyEngineBitmap {};
class EngineEditorPort : public EngineSurfacePort {
public:
    virtual gui_surface::CommitResult present_editor_pair(gui::Snapshot,const gui_surface::Presentation&,
        std::optional<gui_editor::EditorPublication>,std::optional<gui_editor::CompositionFact>)=0;
    virtual gui_surface::CommitResult present_editor_retirement(gui::Snapshot,gui_editor::EditorPublication)=0;
};
struct BoundEngineEditorPort { std::unique_ptr<EngineEditorPort> port; };

// Metadata-only prerequisite for the selected entry. Actual shared policy is
// covered by its separate real-Owner fixture, not this counted facade mock.
class EnginePrimaryRegionApplication {
public:
    static gui::Size initial_client_size(const std::shared_ptr<appended::EngineOwner>& owner) {
        if (!owner || owner->startup_primary()!=appended::EngineStartupPrimary::web)
            throw std::logic_error("This entry fixture models only the original web-primary canvas");
        return {800,600};
    }
};
class NativeEngineBitmapComposition {
    appended::NativeEngineDriver& driver_;
    std::unique_ptr<EngineEditorPort> port_;
    bool close_queued_{},close_entered_{};
    bool metadata_pending_{bitmap_entry_fixture::is("runner-detached-metadata-debt")||
        bitmap_entry_fixture::is("runner-detached-metadata-drained")};
    std::optional<std::chrono::steady_clock::time_point> close_deadline_;
    void created(std::shared_ptr<appended::EngineOwner> owner,std::function<void()> post,const char* kind) {
        auto& s=bitmap_entry_fixture::state;++s.facades;bitmap_entry_fixture::event("facade");
        bitmap_entry_fixture::require(owner.get()==s.bound_owner&&&driver_==s.bound_driver&&driver_.owner()==owner,
            "facade substituted Owner or Driver");
        bitmap_entry_fixture::require(s.start==1&&s.configures==1,"facade preceded actual single startup");
        s.facade_kind=kind;s.facade_wake=std::move(post);
        if(bitmap_entry_fixture::is("facade-failure"))throw std::runtime_error("synthetic facade construction failure");
    }
public:
    NativeEngineBitmapComposition(gui::Adapter&,std::shared_ptr<appended::EngineOwner> owner,
        appended::NativeEngineDriver& driver,const appended::engine_document_actions::EngineDocumentActionsProfileFacts& facts,
        BoundEngineEditorPort port,std::function<void()> post={}) :driver_(driver),port_(std::move(port.port)) {
        auto& s=bitmap_entry_fixture::state;
        bitmap_entry_fixture::require(!s.expected_read_only&&port_&&port_->generation()!=0&&
            ((port_->capabilities().supported==8255&&port_->capabilities().mouse_input_version==1)||
             (port_->capabilities().supported==0&&port_->capabilities().mouse_input_version==0)),
            "interactive actions did not receive the actual checked native publisher");
        bitmap_entry_fixture::require(appended::engine_document_actions::document_actions_profile_agrees(facts,s.actions_profile),
            "interactive facade lost independent actions facts");
        created(std::move(owner),std::move(post),"actions-editor");
    }
    NativeEngineBitmapComposition(gui::Adapter&,std::shared_ptr<appended::EngineOwner> owner,
        appended::NativeEngineDriver& driver,const appended::engine_document_actions::EngineDocumentActionsProfileFacts& facts,
        ReadOnlyEngineBitmap,std::function<void()> post={}) :driver_(driver) {
        bitmap_entry_fixture::require(bitmap_entry_fixture::state.expected_read_only&&
            appended::engine_document_actions::document_actions_profile_agrees(facts,bitmap_entry_fixture::state.actions_profile),
            "read-only actions route changed mode or selected facts");
        created(std::move(owner),std::move(post),"actions-readonly");
    }
    NativeEngineBitmapComposition(gui::Adapter&,std::shared_ptr<appended::EngineOwner> owner,
        appended::NativeEngineDriver& driver,const appended::engine_document::EngineDocumentProfileFacts& facts,
        ReadOnlyEngineBitmap,std::function<void()> post={}) :driver_(driver) {
        bitmap_entry_fixture::require(bitmap_entry_fixture::state.expected_read_only&&
            appended::engine_document::document_profile_agrees(facts,bitmap_entry_fixture::state.profile),
            "pixel route changed selected facts or enabled input");
        created(std::move(owner),std::move(post),"pixel-readonly");
    }
    ~NativeEngineBitmapComposition() { ++bitmap_entry_fixture::state.facade_destroys; }
    void handle(gui::Event value) {
        bitmap_entry_fixture::require(std::holds_alternative<gui::CloseEvent>(value),"wrapper changed owned legacy event");
        ++bitmap_entry_fixture::state.handled;
    }
    void drawable_pixels(std::int64_t width,std::int64_t height) {
        bitmap_entry_fixture::require(width==801&&height==0,"wrapper changed measured drawable pixels");
        ++bitmap_entry_fixture::state.pixels;
    }
    void foreground(bool value) { bitmap_entry_fixture::require(!value,"wrapper invented foreground");++bitmap_entry_fixture::state.foreground; }
    void tick() {
        auto& s=bitmap_entry_fixture::state;++s.facade_ticks;if(s.on_facade_tick)s.on_facade_tick();
        if(close_timed_out()||native_state()==appended::NativeEngineState::blocked||
            native_state()==appended::NativeEngineState::process_exit_required)return;
        if(native_state()==appended::NativeEngineState::detached){
            if(close_queued_&&metadata_pending_&&bitmap_entry_fixture::is("runner-detached-metadata-drained")){
                metadata_pending_=false;++s.metadata_settles;
            }
            return; // Detached-provider metadata settlement must enter no Driver export.
        }
        if(close_queued_&&!close_entered_){close_entered_=true;driver_.request_close();}
        driver_.tick();
    }
    void shutdown() noexcept { ++bitmap_entry_fixture::state.shutdown;close_queued_=true;if(!close_deadline_)close_deadline_=std::chrono::steady_clock::now()+std::chrono::seconds(10); }
    void retry_presentation() { ++bitmap_entry_fixture::state.retry; }
    void qualify(const std::function<void()>& present) { ++bitmap_entry_fixture::state.qualify;if(present)present(); }
    std::optional<gui::ServiceRequest> next_service() { ++bitmap_entry_fixture::state.service_reads;return {}; }
    bool complete_service(gui::ServiceResult) { ++bitmap_entry_fixture::state.service_completions;return false; }
    void request_frame() noexcept { ++bitmap_entry_fixture::state.frame_requests; }
    bool frame_ready() const noexcept { return true; }
    std::uint64_t input_epoch() const noexcept { return 17; }
    bool presentation_pending() const noexcept { return false; }
    bool closed() const noexcept { return close_queued_||native_state()==appended::NativeEngineState::process_exit_required||native_state()==appended::NativeEngineState::blocked; }
    bool close_complete() const noexcept { return close_queued_&&close_entered_&&!metadata_pending_&&!close_timed_out()&&native_state()==appended::NativeEngineState::detached; }
    bool close_timed_out() const noexcept { return close_queued_&&bitmap_entry_fixture::is("close-timeout"); }
    appended::NativeEngineState native_state() const noexcept { return driver_.state(); }
    std::optional<std::chrono::steady_clock::time_point> deadline() const noexcept { return close_deadline_?close_deadline_:std::optional{std::chrono::steady_clock::now()+std::chrono::seconds(30)}; }
    void surface_connected(gui_surface::Capabilities value) { bitmap_entry_fixture::require(value.supported==8255||(bitmap_entry_fixture::state.expected_read_only&&value.supported==0),"wrapper changed capabilities");++bitmap_entry_fixture::state.connections; }
    void surface_input(gui_surface::AcceptedEvent value) { bitmap_entry_fixture::require(value.event.sequence==31,"wrapper changed accepted input");++bitmap_entry_fixture::state.surface_events; }
    void surface_revoked(gui_surface::Revocation value) { bitmap_entry_fixture::require(value.reason==gui_surface::RevocationReason::service,"wrapper changed revocation");++bitmap_entry_fixture::state.surface_revocations; }
    std::optional<std::uint64_t> editor_submit(gui_editor::Packet value) {
        bitmap_entry_fixture::require(value.session==41&&value.basis.token==42&&value.observation.id==43,"wrapper changed editor packet");
        ++bitmap_entry_fixture::state.editor_submits;return 73;
    }
    std::optional<std::uint64_t> editor_revoke(gui_editor::Revocation value) { bitmap_entry_fixture::require(value.incarnation==51,"wrapper changed editor revocation");++bitmap_entry_fixture::state.editor_revokes;return 74; }
    std::optional<gui_editor::EditorCompletion> editor_take(std::uint64_t value) { bitmap_entry_fixture::require(value==75,"wrapper changed editor ticket");++bitmap_entry_fixture::state.editor_takes;return gui_editor::EditorCompletion{75,{}}; }
    void editor_resync() { ++bitmap_entry_fixture::state.editor_resyncs; }
};
} // namespace foundation::ui
