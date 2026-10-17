// SPDX-License-Identifier: CC0-1.0
#include "BibEngineUiOwner.hpp"
#include <atomic>
#include <limits>
namespace BIB::EngineUI {
namespace {
enum class Phase : unsigned { empty,publishing,bound,attached,retired };
struct Registry {
    std::atomic<Phase> phase{Phase::empty};
    std::atomic<bool> failed{};
    Identity id{};
    OwnerHooks owner{};
    RuntimeHooks runtime{};
    const WebCore::ChromeClient* chrome{};
    std::uint64_t input{},revision{1},modal_epoch{},modal_highwater{};
    bool is_modal{},wake{};
    void* retirement_context{};
    void (*retirement_hook)(void*) noexcept{};
};
constinit Registry registry;
bool increment() noexcept {
    if(registry.revision==std::numeric_limits<std::uint64_t>::max()) { fault(); return false; }
    ++registry.revision;return true;
}
bool valid(Identity id) noexcept {return id.runtime_generation&&id.worker&&id.application;}
}
bool onOwner() noexcept {
    const auto phase=registry.phase.load(std::memory_order_acquire);
    return phase>=Phase::bound && registry.owner.on_owner && registry.owner.on_owner(registry.owner.context);
}
bool bindOwner(Identity id,OwnerHooks hooks) noexcept {
    if(!valid(id)||!hooks.on_owner||!hooks.on_owner(hooks.context)) return false;
    auto expected=Phase::empty;
    if(!registry.phase.compare_exchange_strong(expected,Phase::publishing,std::memory_order_acq_rel))return false;
    registry.id=id;registry.owner=hooks;
    registry.phase.store(Phase::bound,std::memory_order_release);return true;
}
bool attachRuntime(const WebCore::ChromeClient& chrome,RuntimeHooks hooks) noexcept {
    if(!onOwner()||faulted()||registry.phase.load(std::memory_order_acquire)!=Phase::bound
        ||!hooks.in_native_turn||!hooks.read_current||!hooks.damage)return false;
    registry.chrome=&chrome;registry.runtime=hooks;
    registry.phase.store(Phase::attached,std::memory_order_release);return true;
}
bool attached() noexcept {return onOwner()&&!faulted()&&registry.phase.load(std::memory_order_acquire)==Phase::attached;}
bool inNativeTurn() noexcept {return attached()&&registry.runtime.in_native_turn(registry.runtime.context);}
bool borrowCurrent(Snapshot& output) noexcept {
    if(!inNativeTurn())return false;
    Snapshot candidate{};
    if(!registry.runtime.read_current(registry.runtime.context,candidate)||!candidate.page||!candidate.main_frame
        ||!candidate.document||!candidate.page_identifier||!candidate.document_sequence
        ||!candidate.service_generation||!candidate.resource_epoch||candidate.chrome!=registry.chrome
        ||candidate.owner.application!=registry.id.application)return false;
    candidate.owner=registry.id;candidate.input_context=registry.input;candidate.authority_revision=registry.revision;
    candidate.modal=registry.is_modal;candidate.modal_epoch=registry.modal_epoch;
    if(candidate.raster&&(!candidate.viewport_width||!candidate.viewport_height))return false;
    output=candidate;return true;
}
bool matches(const Snapshot& expected) noexcept {
    Snapshot now{};
    return borrowCurrent(now)&&now.owner==expected.owner&&now.chrome==expected.chrome&&now.page==expected.page
        &&now.main_frame==expected.main_frame&&now.document==expected.document&&now.page_identifier==expected.page_identifier
        &&now.document_sequence==expected.document_sequence&&now.service_generation==expected.service_generation
        &&now.resource_epoch==expected.resource_epoch&&now.input_context==expected.input_context
        &&now.authority_revision==expected.authority_revision&&now.modal_epoch==expected.modal_epoch&&now.modal==expected.modal
        &&now.raster==expected.raster&&now.viewport_width==expected.viewport_width&&now.viewport_height==expected.viewport_height;
}
Identity identity() noexcept {return onOwner()?registry.id:Identity{};}
const WebCore::ChromeClient* registeredChrome() noexcept {
    return registry.phase.load(std::memory_order_acquire)>=Phase::attached?registry.chrome:nullptr;
}
bool setInputContext(std::uint64_t context) noexcept {
    if(!onOwner()||faulted()||registry.phase.load(std::memory_order_acquire)==Phase::retired)return false;
    if(registry.input==context)return true;
    if(!increment())return false;
    registry.input=context;return true;
}
std::uint64_t inputContext() noexcept {return onOwner()?registry.input:0;}
bool setModal(std::uint64_t epoch,bool active) noexcept {
    if(!attached()||!epoch)return false;
    if(active) {
        if(registry.is_modal||epoch<=registry.modal_highwater)return false;
        if(!increment())return false;
        registry.modal_highwater=registry.modal_epoch=epoch;registry.is_modal=true;
    } else {
        if(!registry.is_modal)return registry.modal_epoch==epoch;
        if(registry.modal_epoch!=epoch||!increment())return false;
        registry.is_modal=false;
    }
    if(registry.owner.modal_changed)registry.owner.modal_changed(registry.owner.context);
    return !faulted();
}
bool modal() noexcept {return onOwner()&&registry.is_modal;}
std::uint64_t modalEpoch() noexcept {return onOwner()?registry.modal_epoch:0;}
void retireDocumentAuthority() noexcept {
    if(!onOwner()) {fault();return;}
    registry.input=0;
    if(!increment())return;
    const bool was_modal=registry.is_modal;registry.is_modal=false;
    if(was_modal&&registry.owner.modal_changed)registry.owner.modal_changed(registry.owner.context);
    registry.wake=true;
}
bool registerRetirementHook(void* context,void (*hook)(void*) noexcept) noexcept {
    if(!onOwner()||!hook||registry.phase.load(std::memory_order_acquire)==Phase::retired)return false;
    if(registry.retirement_hook)return registry.retirement_hook==hook&&registry.retirement_context==context;
    registry.retirement_context=context;registry.retirement_hook=hook;return true;
}
void retireOwner() noexcept {
    if(!onOwner()) {fault();return;}
    if(registry.phase.load(std::memory_order_acquire)==Phase::retired)return;
    retireDocumentAuthority();registry.phase.store(Phase::retired,std::memory_order_release);
    if(registry.retirement_hook)registry.retirement_hook(registry.retirement_context);
}
void markDamage(Rect rect) noexcept {
    if(!onOwner()) {fault();return;}
    if(registry.phase.load(std::memory_order_acquire)==Phase::attached&&rect.width>0&&rect.height>0)
        registry.runtime.damage(registry.runtime.context,rect);
}
void requestWake() noexcept {if(onOwner())registry.wake=true;else fault();}
bool takeWakeRequest() noexcept {if(!onOwner())return false;const bool value=registry.wake;registry.wake=false;return value;}
void fault() noexcept {
    const bool first=!registry.failed.exchange(true,std::memory_order_acq_rel);
    if(first&&onOwner()&&registry.owner.fault)registry.owner.fault(registry.owner.context);
}
bool faulted() noexcept {return registry.failed.load(std::memory_order_acquire);}
} // namespace BIB::EngineUI
