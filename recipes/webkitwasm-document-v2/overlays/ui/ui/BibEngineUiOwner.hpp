// SPDX-License-Identifier: CC0-1.0
// Private common browser/Wasm and native engine UI owner. No public ABI.
#pragma once
#include <cstdint>
namespace WebCore { class ChromeClient; class Page; class LocalFrame; class Document; }
namespace BIB {
// Inert Bridge-state observation; does not enter a turn or touch the VM.
bool foundationServicesInOwnerEngineTurn() noexcept;
namespace EngineUI {
struct Identity { std::uint64_t runtime_generation{},worker{},application{}; friend bool operator==(const Identity&,const Identity&)=default; };
struct Rect { std::int32_t x{},y{},width{},height{}; };
struct Snapshot {
    Identity owner{};
    const WebCore::ChromeClient* chrome{};
    WebCore::Page* page{};
    WebCore::LocalFrame* main_frame{};
    WebCore::Document* document{};
    std::uint64_t page_identifier{},document_sequence{},service_generation{},resource_epoch{},input_context{},authority_revision{},modal_epoch{};
    std::uint32_t viewport_width{},viewport_height{};
    bool raster{},modal{};
};
struct OwnerHooks {
    void* context{};
    bool (*on_owner)(void*) noexcept{};
    // Optional notification only; faulted() is always the authoritative sticky flag.
    void (*fault)(void*) noexcept{};
    // Optional when no editor exists: metadata-only cached editor authority invalidation.
    // No Publisher invalidation during its popup action; no DOM/Host/VM/ACK.
    void (*modal_changed)(void*) noexcept{};
};
struct RuntimeHooks {
    void* context{};
    bool (*in_native_turn)(void*) noexcept{}; // Existing Bridge + actual VM lock.
    bool (*read_current)(void*,Snapshot&) noexcept{}; // Borrow only, no Host entry.
    void (*damage)(void*,Rect) noexcept{}; // Local dirty flags only.
};
// One retained process lifetime. Hook contexts live until process exit, including
// after retireOwner; retirement denies borrowing and never unloads the context.
// No reset, replacement or DSO constructor.
bool bindOwner(Identity,OwnerHooks) noexcept;
bool attachRuntime(const WebCore::ChromeClient&,RuntimeHooks) noexcept;
bool onOwner() noexcept;
bool attached() noexcept;
bool inNativeTurn() noexcept; // Existing Bridge/API-lock state, even during pending document.
bool borrowCurrent(Snapshot&) noexcept;
bool matches(const Snapshot&) noexcept;
Identity identity() noexcept; // Exact owner only; no DOM lookup.
const WebCore::ChromeClient* registeredChrome() noexcept;
bool setInputContext(std::uint64_t) noexcept; // Actual committed physical metadata.
std::uint64_t inputContext() noexcept;
bool setModal(std::uint64_t epoch,bool active) noexcept;
bool modal() noexcept;
std::uint64_t modalEpoch() noexcept;
void retireDocumentAuthority() noexcept; // Metadata only; clipboard owner persists.
// One idempotently registered private value-store cleanup, no DOM/Host callbacks.
bool registerRetirementHook(void*,void (*)(void*) noexcept) noexcept;
void retireOwner() noexcept;
void markDamage(Rect) noexcept;
void requestWake() noexcept;
bool takeWakeRequest() noexcept; // Only normal post-native owner scheduling.
void fault() noexcept;
bool faulted() noexcept; // Inert atomic query, safe before binding/from any thread.
} // namespace EngineUI
} // namespace BIB
