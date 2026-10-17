// TEST ONLY: old web-primary entry routes use the existing counter facade.
// This fake supplies no semantic primary implementation, presenter or UI debt.
#pragma once
#include "shared/native_engine_document_composition.hpp"
namespace foundation::ui {
class SemanticPrimaryDocumentApplication final : public NativeEngineDocumentComposition {
    static std::shared_ptr<appended::EngineOwner> web_owner(std::shared_ptr<appended::EngineOwner> owner) {
        terminal_main_fixture::require(owner && owner->startup_primary()==appended::EngineStartupPrimary::web,
            "terminal entry fixture only models web-primary startup");
        return owner;
    }
public:
    SemanticPrimaryDocumentApplication(gui::Adapter& adapter,std::shared_ptr<appended::EngineOwner> owner,
        appended::NativeEngineDriver& driver,std::function<void()> wake)
        :NativeEngineDocumentComposition(adapter,web_owner(std::move(owner)),driver,std::move(wake)) {}
    bool shutdown_complete() const noexcept { return native_state()==appended::NativeEngineState::detached; }
};
} // namespace foundation::ui
