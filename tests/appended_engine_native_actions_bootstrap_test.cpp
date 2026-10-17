// SPDX-License-Identifier: CC0-1.0
// Actual rich4083 Guard/Once fixture. Fake metadata/callbacks, no WebCore or native actions.
#include "EnginePrivate.hpp"
#include "BibCopiedDocumentCatalog.hpp"
#include "BibEngineProviderPreflight.h"
#include "BibNativeProviderOnce.hpp"
#include <algorithm>
#include <array>
#include <atomic>
#include <cstring>
#include <iostream>
#include <latch>
#include <new>
#include <stdexcept>
#include <string>
#include <string_view>
#include <thread>

namespace P = bib::provider_candidate;
namespace D = P::document_catalog;
namespace {
constexpr std::uint64_t application = UINT64_C(0x4649585455524501);
constexpr std::uint64_t worker = UINT64_C(0x4649585455524502);
constexpr BibEngineLimitsV1 limits{sizeof(BibEngineLimitsV1),1048576,236,1048576,
    1048576,8,64,0,67108864,134217728};
struct Fixture {
    std::string_view mode;
    std::thread::id owner;
    std::atomic<unsigned> attempts{}, reservations{}, binds{}, ownerProbes{}, preflights{}, wrongPreflight{};
    std::atomic<unsigned> enters{}, leaves{}, otherHost{}, installs{}, starts{}, advances{}, currents{}, wrongHost{};
    std::atomic<unsigned> validations{}, editorCalls{}, otherBackend{};
    std::latch builderPaused{1}, releaseBuilder{1}, gatePaused{1}, releaseGate{1};
    std::atomic<std::int32_t> recursive{99};
};
Fixture* f;
constinit P::NativeProviderOnce once;
thread_local bool pauseGate;

void check(bool value, const char* message) {
    if (!value) throw std::runtime_error(message);
}
bool owner() noexcept { return f->owner == std::this_thread::get_id(); }
void untouchedHost() { check(!f->enters && !f->leaves && !f->otherHost && !f->installs && !f->starts && !f->advances && !f->currents
    && !f->validations && !f->editorCalls && !f->otherBackend, "getter/preflight invoked Host or engine"); }
std::int32_t preflight(void*, const BibEngineStartV1* start) noexcept {
    ++f->preflights;
    if (!owner()) { ++f->wrongPreflight; return BIB_ENGINE_WRONG_THREAD; }
    return start ? P::validateActualStart(*start) : BIB_ENGINE_INVALID;
}
std::int32_t install(void*,const BibEngineHostV1*,const BibEngineStartV1*,std::uint64_t) { ++f->installs; return 0; }
std::int32_t start(void*,const BibEngineHostV1*,const BibEngineStartV1*,std::uint64_t) { ++f->starts; return 0; }
std::int32_t advance(void*,const BibEngineAdvanceV1*) { ++f->advances; return 0; }
std::int32_t current(void*,std::uint64_t,BibEngineDocumentV1* out) { ++f->currents; *out={application,11,7}; return 0; }
std::int32_t command(void*,const BibEngineCommandV1*,BibEngineReplyBufferV1*,BibEngineCommandResultV1*) { ++f->otherBackend; return BIB_ENGINE_UNSUPPORTED; }
std::int32_t query(void*,const BibEngineQueryV1*,BibEngineReplyBufferV1*,BibEngineQueryResultV1*) { ++f->otherBackend; return BIB_ENGINE_UNSUPPORTED; }
std::int32_t deliver(void*,const BibEngineDocumentV1*,const BibEngineBytesV1*) { ++f->otherBackend; return BIB_ENGINE_UNSUPPORTED; }
std::uint32_t ack(void*,const BibEngineDocumentV1*) { ++f->otherBackend; return 14; }
std::int32_t dispose(void*,std::uint64_t,std::uint64_t) { ++f->otherBackend; return BIB_ENGINE_UNSUPPORTED; }
std::int32_t validate(void*,std::uint64_t,const BibEngineDocumentV1*,std::uint32_t,std::uint32_t,std::uint64_t,const BibEngineBytesV1*) { ++f->validations; return BIB_ENGINE_INVALID; }
std::int32_t validateReply(void*,std::uint64_t,const BibEngineDocumentV1*,std::uint32_t,std::uint32_t,std::uint64_t,const BibEngineBytesV1*,const BibEngineBytesV1*) { ++f->validations; return BIB_ENGINE_INVALID; }
std::int32_t retire(void*,std::uint64_t,const BibEngineCommandV1*) { ++f->validations; return 0; }
std::int32_t editorProject(void*,std::uint64_t,const BibEngineQueryV1*,BibEngineReplyBufferV1*,BibEngineQueryResultV1*) {
    ++f->editorCalls; return BIB_ENGINE_UNSUPPORTED;
}
std::int32_t editorApply(void*,std::uint64_t,const BibEngineCommandV1*,BibEngineReplyBufferV1*,BibEngineCommandResultV1*) {
    ++f->editorCalls; return BIB_ENGINE_UNSUPPORTED;
}

BibEngineBuildV1 build() {
    BibEngineBuildV1 b{};
    b.size=sizeof(b); b.layout_revision=1; b.target_system=BIB_ENGINE_TARGET_LINUX;
#if !defined(__linux__) || !defined(__x86_64__) || defined(__aarch64__) || defined(_WIN32)
#error "This bounded fake-native helper fixture requires the real Linux x86_64 target"
#endif
    b.target_processor=BIB_ENGINE_CPU_X86_64;
    b.pointer_bits=64; b.lifetime=1; b.maximum_starts=1;
    b.fixed_viewport_width=800; b.fixed_viewport_height=600; b.capabilities=4083;
    std::copy(D::actions_contract.begin(),D::actions_contract.end(),b.contract_header_sha256);
    std::fill_n(b.build_identity_sha256,32,0xf1); // Explicit fake fixture only.
    std::fill_n(b.source_recipe_sha256,32,0xf2);
    return b;
}

std::int32_t factory() {
    ++f->attempts;
    if (f->mode=="known-unsupported") return BIB_ENGINE_UNSUPPORTED;
    if (f->mode=="known-invalid") return BIB_ENGINE_INVALID;
    if (f->mode=="known-limit") throw std::bad_alloc{};
    if (f->mode=="uncertain-throw") throw std::runtime_error("injected pre-bind uncertainty");
    if (f->mode=="binding-before-owner-written") {
        f->builderPaused.count_down(); f->releaseBuilder.wait();
    }
    f->owner=std::this_thread::get_id();
    if (f->mode=="concurrent-binding") {
        f->builderPaused.count_down(); f->releaseBuilder.wait();
    }
    f->reservations.fetch_add(2);
    if (f->mode=="same-thread-recursive-getter") {
        BibEngineProviderV1 nested{};
        f->recursive=bib_engine_get_provider_v1(1,1,sizeof(nested),&nested);
    }
    P::EnginePrivateV1 engine{sizeof(P::EnginePrivateV1),P::private_interface_version,build(),limits,application,f,
        D::actions_commands.data(),static_cast<std::uint32_t>(D::actions_commands.size()),
        D::actions_queries.data(),static_cast<std::uint32_t>(D::actions_queries.size()),
        preflight,start,advance,current,command,query,deliver,ack,dispose,install};
    P::EngineDocumentPrivateV1 document{sizeof(P::EngineDocumentPrivateV1),P::document_private_interface_version,
        P::document_physical_profile,0,worker,D::base_header,D::extension_header,D::contract,D::catalog,
        D::physical_catalog,validate,validateReply,retire};
    P::EngineEditorPrivateV1 editor{sizeof(P::EngineEditorPrivateV1),P::editor_private_interface_version,0,0,worker,
        D::editor_header,D::editor_contract,D::editor_catalog,D::editor_schema,
        validate,validateReply,editorProject,editorApply,editorApply};
    P::EngineDocumentActionsPrivateV1 actions{sizeof(P::EngineDocumentActionsPrivateV1),
        P::document_actions_private_interface_version,P::document_actions_profile,0,worker,
        D::actions_header,D::actions_contract,D::actions_catalog,D::actions_schema,D::actions_ack_schema,
        validate,validateReply,retire};
    ++f->binds;
    const auto status=P::bind_engine_document_actions_private(engine,document,editor,actions);
    if (!status && f->mode=="uncertain-after-bind")
        throw std::runtime_error("injected post-bind uncertainty; permanent fixture context retained");
    return status;
}

BibEngineProviderV1 get() {
    BibEngineProviderV1 table{};
    check(bib_engine_get_provider_v1(1,1,sizeof(table),&table)==0,"eligible getter rejected");
    check(table.abi_major==1 && table.abi_minor==1 && table.build.capabilities==4083,"wrong rich native table");
    check(!std::memcmp(table.build.contract_header_sha256,D::actions_contract.data(),32)
        && table.limits.maximum_command_bytes==1048576 && table.limits.maximum_query_bytes==236
        && table.limits.maximum_reply_bytes==1048576,"rich composite or limits changed");
    untouchedHost();
    return table;
}
BibEngineHostV1 host() {
    BibEngineHostV1 h{}; h.size=sizeof(h); h.abi_major=1; h.abi_minor=0; h.context=f;
    h.wake=[](void*) { ++f->otherHost; };
    h.replace_timer_ms=[](void*,double,std::uint32_t) { ++f->otherHost; };
    h.damage=[](void*,const BibEngineDamageV1*) { ++f->otherHost; };
    h.persistence=[](void*,const BibEngineBytesV1*) { ++f->otherHost; };
    h.enter_engine=[](void*) -> std::uint32_t { ++f->enters; if (!owner()) ++f->wrongHost; return 0; };
    h.leave_engine=[](void*) { ++f->leaves; if (!owner()) ++f->wrongHost; };
    h.begin_service_document=[](void*,const BibEngineDocumentV1*) -> std::uint64_t { ++f->otherHost; return 1; };
    h.close_service_document=[](void*,std::uint64_t) { ++f->otherHost; };
    h.submit_service=[](void*,std::uint64_t,const BibEngineBytesV1*,std::uint32_t) -> std::uint32_t { ++f->otherHost; return 1; };
    h.cancel_service=[](void*,std::uint64_t,std::uint64_t) -> std::uint32_t { ++f->otherHost; return 1; };
    h.stage_service_ack=[](void*,std::uint64_t,std::uint64_t) -> std::uint32_t { ++f->otherHost; return 1; };
    h.begin_resource_epoch=[](void*,const BibEngineDocumentV1*,BibEngineResourceEpochV1*) -> std::int32_t { ++f->otherHost; return 1; };
    h.retire_resource_epoch=[](void*,std::uint64_t) { ++f->otherHost; };
    return h;
}
BibEngineStartV1 configuration() {
    static const std::string url="app://"+std::string(64,'a')+"/web/index.html";
    BibEngineStartV1 c{}; c.size=sizeof(c); c.raster_output=1; c.required_capabilities=4083;
    c.limits=limits; c.entry_url={reinterpret_cast<const std::uint8_t*>(url.data()),static_cast<std::uint32_t>(url.size()),0};
    std::fill_n(c.application_package_sha256,32,0xaa);
    return c;
}
BibEngineStartResultV1 started(const BibEngineProviderV1& table) {
    const auto h=host(); const auto c=configuration();
    BibEngineStartResultV1 result{sizeof(result),0,0};
    check(table.start(&h,&c,&result)==0,"owner START rejected");
    check(result.phase==BIB_ENGINE_START_READY && result.application_instance==application,"START did not publish READY");
    check(f->installs==1 && f->starts==1 && f->enters==1 && f->leaves==1 && !f->otherHost && !f->wrongHost,"START callback counts wrong");
    return result;
}
void rejected(std::uint32_t major,std::uint32_t minor,std::uint32_t capacity,std::int32_t expected) {
    alignas(BibEngineProviderV1) std::array<std::uint8_t,sizeof(BibEngineProviderV1)+32> bytes; bytes.fill(0xa5);
    const auto before=bytes;
    auto* out=reinterpret_cast<BibEngineProviderV1*>(bytes.data()+16);
    check(bib_engine_get_provider_v1(major,minor,capacity,out)==expected,"getter wrong rejection");
    check(bytes==before,"rejected getter wrote output/canaries");
}
void badGetters() {
    check(bib_engine_get_provider_v1(1,1,sizeof(BibEngineProviderV1),nullptr)==BIB_ENGINE_INVALID,"null getter accepted");
    rejected(2,1,sizeof(BibEngineProviderV1),BIB_ENGINE_INVALID);
    rejected(1,1,sizeof(BibEngineProviderV1)-1,BIB_ENGINE_INVALID);
    rejected(1,0,sizeof(BibEngineProviderV1),BIB_ENGINE_UNSUPPORTED);
    check(!f->attempts && !f->reservations && !f->binds && !f->ownerProbes,"rejected getter registered metadata");
    untouchedHost();
}
}

namespace bib::provider_candidate {
std::int32_t ensureNativeDocumentProviderBound() noexcept {
    return once.ensure(factory,[]() noexcept { ++f->ownerProbes; return owner(); });
}
}
extern "C" void bib_native_fixture_gate_pause_v1() noexcept {
    if (pauseGate) { f->gatePaused.count_down(); f->releaseGate.wait(); }
}

int main(int argc,char** argv) {
    try {
        check(argc==2,"exactly one fresh-process case required");
        f=new Fixture; f->mode=argv[1]; const auto mode=f->mode;
        if (mode=="null-output" || mode=="wrong-major" || mode=="short-capacity" || mode=="minor0") badGetters();
        else if (mode=="rejected-then-accepted") { badGetters(); (void)get(); check(f->attempts==1 && f->binds==1 && f->reservations==2,"metadata registration count wrong"); }
        else if (mode=="higher-max-minor") { BibEngineProviderV1 t{}; check(bib_engine_get_provider_v1(1,UINT32_MAX,sizeof(t),&t)==0 && t.abi_minor==1,"maximum minor negotiation wrong"); untouchedHost(); }
        else if (mode=="repeated-owner-getter") { const auto a=get(),b=get(); check(!std::memcmp(&a,&b,sizeof(a)) && f->attempts==1 && f->binds==1 && f->reservations==2,"repeated getter rebuilt or changed table"); }
        else if (mode=="ready-foreign-getter") { (void)get(); std::thread t([] { rejected(1,1,sizeof(BibEngineProviderV1),BIB_ENGINE_WRONG_THREAD); }); t.join(); check(f->attempts==1,"foreign getter rebuilt"); untouchedHost(); }
        else if (mode=="concurrent-binding" || mode=="binding-before-owner-written") {
            std::atomic<std::int32_t> code{99};
            std::thread winner([&] { BibEngineProviderV1 table{}; code=bib_engine_get_provider_v1(1,1,sizeof(table),&table); });
            f->builderPaused.wait(); rejected(1,1,sizeof(BibEngineProviderV1),BIB_ENGINE_REENTRANT);
            check(!f->ownerProbes && !f->reservations,"binding observer read unpublished owner/IDs");
            f->releaseBuilder.count_down(); winner.join();
            check(code==0 && f->attempts==1 && f->binds==1 && f->reservations==2,"concurrent binding lacked one winner"); untouchedHost();
        } else if (mode=="same-thread-recursive-getter") { (void)get(); check(f->recursive==BIB_ENGINE_REENTRANT && f->attempts==1,"recursive getter rebound"); }
        else if (mode=="known-unsupported" || mode=="known-invalid" || mode=="known-limit" || mode=="uncertain-throw" || mode=="uncertain-after-bind") {
            const auto expected=mode=="known-unsupported"?BIB_ENGINE_UNSUPPORTED:mode=="known-invalid"?BIB_ENGINE_INVALID:mode=="known-limit"?BIB_ENGINE_LIMIT:BIB_ENGINE_PROCESS_EXIT_REQUIRED;
            rejected(1,1,sizeof(BibEngineProviderV1),expected); rejected(1,1,sizeof(BibEngineProviderV1),expected);
            check(f->attempts==1 && f->binds==(mode=="uncertain-after-bind"?1u:0u),"failed registration retried or lost retained context"); untouchedHost();
        } else if (mode=="wrong-thread-start-then-owner") {
            const auto table=get(); const auto h=host(); const auto c=configuration(); BibEngineStartResultV1 out{sizeof(out),99,99}; std::int32_t code{};
            std::thread t([&] { code=table.start(&h,&c,&out); }); t.join();
            check(code==BIB_ENGINE_WRONG_THREAD && out.phase==0 && !out.application_instance && f->wrongPreflight==1,"foreign START committed state"); untouchedHost(); (void)started(table);
        } else if (mode=="malformed-start-then-owner") {
            const auto table=get(); auto h=host(); auto c=configuration(); BibEngineStartResultV1 out{sizeof(out),99,99};
            check(table.start(nullptr,&c,&out)==BIB_ENGINE_INVALID && out.phase==0 && !out.application_instance,"null Host retained");
            check(table.start(&h,nullptr,&out)==BIB_ENGINE_INVALID && out.phase==0 && !out.application_instance,"null START retained");
            auto bad=c; bad.size=0; check(table.start(&h,&bad,&out)==BIB_ENGINE_INVALID,"short START accepted");
            BibEngineStartResultV1 shortOut{0,99,99}; const auto before=shortOut;
            check(table.start(&h,&c,&shortOut)==BIB_ENGINE_INVALID && !std::memcmp(&shortOut,&before,sizeof(before)),"short output overwritten");
            untouchedHost(); (void)started(table);
        } else if (mode=="repeated-start" || mode=="foreign-start-after-ready") {
            const auto table=get(); (void)started(table); const auto h=host(); const auto c=configuration(); BibEngineStartResultV1 out{sizeof(out),0,0}; std::int32_t code{};
            if (mode=="repeated-start") { code=table.start(&h,&c,&out); check(code==BIB_ENGINE_CLOSED && out.application_instance==application,"repeated START changed lifetime"); }
            else { std::thread t([&] { code=table.start(&h,&c,&out); }); t.join(); check(code==BIB_ENGINE_WRONG_THREAD,"foreign ready START accepted"); }
            check(f->starts==1 && f->installs==1 && f->enters==1 && f->leaves==1,"START replayed callbacks");
        } else if (mode=="initial-phase-gate-race") {
            const auto table=get(); std::int32_t code{}; const BibEngineAdvanceV1 tick{sizeof(tick),0,application};
            std::thread foreign([&] { pauseGate=true; code=table.advance(&tick); });
            f->gatePaused.wait(); (void)started(table); f->releaseGate.count_down(); foreign.join();
            check(code==BIB_ENGINE_WRONG_THREAD && !f->advances && f->enters==1 && f->leaves==1 && !f->wrongHost,"foreign advance crossed START owner commitment");
            check(table.advance(&tick)==0 && f->advances==1,"rejected foreign gate retained busy");
        } else throw std::runtime_error("unknown case");
        std::cout << "PASS " << mode << " attempts=" << f->attempts << " binds=" << f->binds << '\n';
        return 0;
    } catch (const std::exception& error) { std::cerr << "FAIL " << (argc>1?argv[1]:"argument") << ": " << error.what() << '\n'; return 1; }
}
