// TEST ONLY: counter facade around the real main's scoped wrapper; no presenter.
#pragma once
#include "shared/native_engine_loader.hpp"
namespace foundation::ui {
class NativeEngineDocumentComposition {
    appended::NativeEngineDriver& driver_;
    bool close_queued_{};
public:
    NativeEngineDocumentComposition(gui::Adapter&,std::shared_ptr<appended::EngineOwner> owner,appended::NativeEngineDriver& driver,std::function<void()> wake)
        :driver_(driver){
        auto& s=terminal_main_fixture::state;++s.facades;terminal_main_fixture::event("facade");
        terminal_main_fixture::require(owner.get()==s.bound_owner&&&driver==s.bound_driver,"facade injected different Owner/Driver");s.facade_wake=std::move(wake);
    }
    void handle(gui::Event) {++terminal_main_fixture::state.handled;}
    void drawable_cells(std::int64_t columns,std::int64_t rows){
        ++terminal_main_fixture::state.cells;terminal_main_fixture::require(columns==81&&rows==0,"wrapper changed measured cells");
    }
    void foreground(bool value){++terminal_main_fixture::state.foreground;terminal_main_fixture::require(!value,"wrapper invented foreground");}
    void tick(){auto& s=terminal_main_fixture::state;++s.facade_ticks;if(s.on_facade_tick)s.on_facade_tick();if(close_queued_){driver_.request_close();driver_.tick();}}
    void shutdown() noexcept{++terminal_main_fixture::state.shutdown;close_queued_=true;}
    void retry_presentation(){++terminal_main_fixture::state.retry;}
    void qualify(const std::function<void()>& present){++terminal_main_fixture::state.qualify;if(present)present();}
    std::optional<gui::ServiceRequest> next_service(){++terminal_main_fixture::state.service_reads;return {};}
    bool complete_service(gui::ServiceResult){++terminal_main_fixture::state.service_completions;return false;}
    bool closed() const noexcept{return close_queued_||driver_.state()==appended::NativeEngineState::process_exit_required||driver_.state()==appended::NativeEngineState::blocked;}
    appended::NativeEngineState native_state()const noexcept{return driver_.state();}
    std::optional<std::chrono::steady_clock::time_point> deadline()const noexcept{return std::chrono::steady_clock::now()+std::chrono::seconds(30);}
};
}
