// SPDX-License-Identifier: CC0-1.0
// Dependency-free fake-private-backend tests. No engine or SDK qualification.
#include "EnginePrivate.hpp"
#include <array>
#include <cstring>
#include <iostream>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>

using namespace bib::provider_candidate;
#define CHECK(x) do { if (!(x)) throw std::runtime_error(std::string("failed: ") + #x + " line " + std::to_string(__LINE__)); } while (false)
namespace {
BibEngineProviderV1 provider{};
struct Fake {
    int enters=0, leaves=0, starts=0, effects=0, queries=0, advances=0;
    int preflight_status=0, start_status=0, command_status=0, query_status=0, advance_status=0;
    bool enter_ok=true, throw_command=false, throw_leave=false, malformed=false, reenter=false, wrong_query=false, wrong_sequence=false;
    std::uint32_t enter_status=0;
    int nested_enter=99, nested_leave=99, nested_backend=99, threaded=99;
    std::uint8_t* mutate=nullptr;
    std::uint8_t observed=0;
    BibEngineDocumentV1 document{44,1,0};
    const BibEngineHostV1* retained_host=nullptr;
    const BibEngineStartV1* retained_config=nullptr;
    static void BIB_ENGINE_CALL wake(void*) {}
    static void BIB_ENGINE_CALL timer(void*,double,std::uint32_t) {}
    static std::uint32_t BIB_ENGINE_CALL enter(void* context) {
        auto& f=*static_cast<Fake*>(context); ++f.enters;
        if(f.mutate) *f.mutate=91;
        if(f.reenter) { BibEngineDocumentV1 d{}; f.nested_enter=provider.current_document(44,&d); }
        return f.enter_ok?f.enter_status:2u;
    }
    static void BIB_ENGINE_CALL leave(void* context) {
        auto& f=*static_cast<Fake*>(context); ++f.leaves;
        if(f.reenter) { BibEngineDocumentV1 d{}; f.nested_leave=provider.current_document(44,&d); }
        if(f.throw_leave) throw std::runtime_error("broken host leave");
    }
    static std::int32_t preflight(void* p,const BibEngineStartV1*) { return static_cast<Fake*>(p)->preflight_status; }
    static std::int32_t start(void* p,const BibEngineHostV1* h,const BibEngineStartV1* c,std::uint64_t instance) {
        auto& f=*static_cast<Fake*>(p); CHECK(instance==44); ++f.starts; f.retained_host=h; f.retained_config=c;
        return f.start_status;
    }
    static std::int32_t advance(void* p,const BibEngineAdvanceV1*) { auto& f=*static_cast<Fake*>(p); ++f.advances; return f.advance_status; }
    static std::int32_t current(void* p,std::uint64_t,BibEngineDocumentV1* d) { *d=static_cast<Fake*>(p)->document; return 0; }
    static std::int32_t command(void* p,const BibEngineCommandV1* c,BibEngineReplyBufferV1* b,BibEngineCommandResultV1* r) {
        auto& f=*static_cast<Fake*>(p); ++f.effects;
        if(c->payload.length) f.observed=c->payload.data[0];
        if(f.reenter) {
            BibEngineDocumentV1 d{}; f.nested_backend=provider.current_document(44,&d);
            std::thread wrong([&]{f.threaded=provider.current_document(44,&d);}); wrong.join();
        }
        if(f.throw_command) throw std::runtime_error("private effect uncertainty");
        b->bytes[0]=7; r->bytes_written=f.malformed?b->capacity+1:1; r->handled=0;
        if(f.wrong_sequence)r->request_sequence=999;
        return f.command_status;
    }
    static std::int32_t query(void* p,const BibEngineQueryV1*,BibEngineReplyBufferV1* b,BibEngineQueryResultV1* r) {
        auto& f=*static_cast<Fake*>(p); ++f.queries; b->bytes[0]=8; r->bytes_written=f.malformed?b->capacity+1:1;
        r->document=f.document; if(f.wrong_query)++r->document.document_sequence; r->semantic_revision=3; return f.query_status;
    }
};
struct Fixture {
    Fake fake;
    Operation command{BIB_ENGINE_COMMAND_KEY,32,16,BIB_ENGINE_CAP_KEY_V1,{}};
    Operation query{BIB_ENGINE_QUERY_SEMANTIC_SNAPSHOT,32,16,BIB_ENGINE_CAP_SEMANTIC_SNAPSHOT_V1,{}};
    EnginePrivateV1 backend{};
    BibEngineHostV1 host{};
    BibEngineStartV1 config{};
    std::string url="app://"+std::string(64,'a')+"/web/index.html";
    std::array<std::uint8_t,3> persistence{1,2,3};
    Fixture() {
        command.schema.fill(31); query.schema.fill(32);
        backend.size=sizeof(backend); backend.version=private_interface_version; backend.application_instance=44;
        backend.build.size=sizeof(backend.build); backend.build.layout_revision=BIB_ENGINE_LAYOUT_V1;
#if defined(__EMSCRIPTEN__)
        backend.build.target_system=BIB_ENGINE_TARGET_BROWSER_WASM; backend.build.target_processor=BIB_ENGINE_CPU_WASM32; backend.build.pointer_bits=32;
#elif defined(_WIN32)
        backend.build.target_system=BIB_ENGINE_TARGET_WINDOWS; backend.build.target_processor=BIB_ENGINE_CPU_X86_64; backend.build.pointer_bits=64;
#elif defined(__aarch64__)
        backend.build.target_system=BIB_ENGINE_TARGET_LINUX; backend.build.target_processor=BIB_ENGINE_CPU_AARCH64; backend.build.pointer_bits=64;
#else
        backend.build.target_system=BIB_ENGINE_TARGET_LINUX; backend.build.target_processor=BIB_ENGINE_CPU_X86_64; backend.build.pointer_bits=64;
#endif
        backend.build.lifetime=BIB_ENGINE_LIFETIME_PROCESS; backend.build.maximum_starts=1;
        backend.build.capabilities=BIB_ENGINE_CAP_KEY_V1|BIB_ENGINE_CAP_SEMANTIC_SNAPSHOT_V1;
        std::memcpy(backend.build.contract_header_sha256,contract_header_sha256.data(),32);
        backend.build.build_identity_sha256[0]=1; backend.build.source_recipe_sha256[0]=2;
        backend.limits={sizeof(BibEngineLimitsV1),64,64,64,1024,4,8,0,1024,4096};
        backend.context=&fake; backend.commands=&command; backend.command_count=1; backend.queries=&query; backend.query_count=1;
        backend.preflight=Fake::preflight; backend.start=Fake::start; backend.advance=Fake::advance; backend.current_document=Fake::current;
        backend.command=Fake::command; backend.query=Fake::query;
        host.size=sizeof(host); host.abi_major=1; host.context=&fake; host.wake=Fake::wake; host.replace_timer_ms=Fake::timer;
        host.enter_engine=Fake::enter; host.leave_engine=Fake::leave;
        config.size=sizeof(config); config.required_capabilities=backend.build.capabilities; config.limits=backend.limits;
        config.entry_url={reinterpret_cast<const std::uint8_t*>(url.data()),static_cast<std::uint32_t>(url.size()),0};
        config.persist_seed={persistence.data(),3,0}; std::fill(std::begin(config.application_package_sha256),std::end(config.application_package_sha256),0xaa);
    }
    void bind() { CHECK(bind_engine_private(backend)==0); CHECK(bib_engine_get_provider_v1(1,0,sizeof(provider),&provider)==0); }
    BibEngineStartResultV1 start() { BibEngineStartResultV1 r{sizeof(r),99,99}; CHECK(provider.start(&host,&config,&r)==0); CHECK(r.phase==2&&r.application_instance==44); return r; }
};
struct Command {
    std::array<std::uint8_t,4> payload{4,5,6,7};
    std::array<std::uint8_t,64> output{};
    BibEngineCommandV1 request{};
    BibEngineReplyBufferV1 buffer{sizeof(buffer),64,output.data()};
    BibEngineCommandResultV1 result{sizeof(result),99,99,99,99};
    explicit Command(const Fixture& f) {
        request.size=sizeof(request); request.operation=1; request.expected=f.fake.document; request.request_sequence=1;
        std::memcpy(request.schema_sha256,f.command.schema.data(),32); request.payload={payload.data(),4,0};
    }
    int run() { result.size=sizeof(result); return provider.command(&request,&buffer,&result); }
};
void run(const std::string& name) {
    if(name=="unbound") { provider.size=17; CHECK(bib_engine_get_provider_v1(1,0,sizeof(provider),&provider)==BIB_ENGINE_UNSUPPORTED); CHECK(provider.size==17); return; }
    Fixture f;
    if(name=="bind-validation") {
        auto b=f.backend; b.build.target_processor=BIB_ENGINE_CPU_WASM32; CHECK(bind_engine_private(b)==BIB_ENGINE_INVALID);
        b=f.backend; b.build.pointer_bits=8; CHECK(bind_engine_private(b)==BIB_ENGINE_INVALID);
        b=f.backend; b.build.layout_revision=2; CHECK(bind_engine_private(b)==BIB_ENGINE_INVALID);
        b=f.backend; b.build.contract_header_sha256[0]^=1; CHECK(bind_engine_private(b)==BIB_ENGINE_INVALID);
        b=f.backend; b.build.reserved=1; CHECK(bind_engine_private(b)==BIB_ENGINE_INVALID);
        b=f.backend; ++b.build.size; CHECK(bind_engine_private(b)==BIB_ENGINE_INVALID);
        b=f.backend; ++b.limits.size; CHECK(bind_engine_private(b)==BIB_ENGINE_INVALID);
        b=f.backend; b.build.capabilities|=BIB_ENGINE_CAP_SERVICE_QUEUE; CHECK(bind_engine_private(b)==BIB_ENGINE_INVALID);
        b=f.backend; b.build.capabilities|=BIB_ENGINE_CAP_APP_BUNDLE; CHECK(bind_engine_private(b)==BIB_ENGINE_INVALID);
        b=f.backend; b.command=nullptr; CHECK(bind_engine_private(b)==BIB_ENGINE_INVALID);
        b=f.backend; b.build.capabilities|=UINT64_C(1)<<40; CHECK(bind_engine_private(b)==BIB_ENGINE_INVALID);
        f.command.required_reply_capacity=65; CHECK(bind_engine_private(f.backend)==BIB_ENGINE_INVALID); f.command.required_reply_capacity=16;
        f.command.schema.fill(0); CHECK(bind_engine_private(f.backend)==BIB_ENGINE_INVALID); f.command.schema.fill(31);
        f.bind(); CHECK(bind_engine_private(f.backend)==BIB_ENGINE_CLOSED); return;
    }
    f.bind();
    if(name=="prefix") {
        struct WithTail { BibEngineProviderV1 table; std::array<std::uint8_t,32> tail; } value{};
        std::memset(&value,0xa5,sizeof(value)); auto* out=&value.table;
        CHECK(bib_engine_get_provider_v1(2,0,sizeof(provider),out)==BIB_ENGINE_INVALID); CHECK(out->size==0xa5a5a5a5);
        CHECK(bib_engine_get_provider_v1(1,0,sizeof(provider)-1,out)==BIB_ENGINE_INVALID); CHECK(out->size==0xa5a5a5a5);
        CHECK(bib_engine_get_provider_v1(1,99,sizeof(value),out)==0); CHECK(out->abi_minor==0&&out->reserved==0);
        for(auto byte:value.tail) { CHECK(byte==0xa5); }
        return;
    }
    if(name=="startup-validation") {
        BibEngineStartResultV1 result{sizeof(result),99,99}; const auto good=f.config;
        f.config.size=4; CHECK(provider.start(&f.host,&f.config,&result)==BIB_ENGINE_INVALID); CHECK(result.phase==0&&result.application_instance==0);
        f.config=good; f.config.reserved0=1; CHECK(provider.start(&f.host,&f.config,&result)==BIB_ENGINE_INVALID);
        f.config=good; f.config.required_capabilities|=UINT64_C(1)<<63; CHECK(provider.start(&f.host,&f.config,&result)==BIB_ENGINE_INVALID);
        f.config=good; f.config.limits.maximum_reply_bytes=15; CHECK(provider.start(&f.host,&f.config,&result)==BIB_ENGINE_INVALID);
        f.config=good; f.config.entry_url.reserved=1; CHECK(provider.start(&f.host,&f.config,&result)==BIB_ENGINE_INVALID);
        f.config=good; f.config.application_package_sha256[1]=0; CHECK(provider.start(&f.host,&f.config,&result)==BIB_ENGINE_INVALID);
        f.config=good; f.url[0]='h'; CHECK(provider.start(&f.host,&f.config,&result)==BIB_ENGINE_INVALID); f.url[0]='a';
        f.config=good; f.host.reserved=1; CHECK(provider.start(&f.host,&f.config,&result)==BIB_ENGINE_INVALID); f.host.reserved=0;
        f.config=good; f.fake.preflight_status=BIB_ENGINE_INVALID; CHECK(provider.start(&f.host,&f.config,&result)==BIB_ENGINE_INVALID);
        CHECK(result.phase==0&&f.fake.starts==0&&f.fake.enters==0); f.fake.preflight_status=0; f.start(); return;
    }
    if(name=="startup-failure"||name=="enter-failure") {
        if(name=="startup-failure") f.fake.start_status=BIB_ENGINE_INVALID; else f.fake.enter_ok=false;
        BibEngineStartResultV1 result{sizeof(result),99,99};
        CHECK(provider.start(&f.host,&f.config,&result)==BIB_ENGINE_PROCESS_EXIT_REQUIRED); CHECK(result.phase==1&&result.application_instance==44);
        int enters=f.fake.enters; CHECK(provider.start(&f.host,&f.config,&result)==BIB_ENGINE_PROCESS_EXIT_REQUIRED); CHECK(f.fake.enters==enters); return;
    }
    f.start();
    if(name=="copied-start") {
        auto first=f.fake.retained_config->entry_url.data[0]; f.url[0]='x'; f.persistence[0]=99; f.host.enter_engine=nullptr; f.config.limits.maximum_command_bytes=1;
        CHECK(f.fake.retained_host->enter_engine==Fake::enter); CHECK(f.fake.retained_config->entry_url.data[0]==first);
        CHECK(f.fake.retained_config->persist_seed.data[0]==1); CHECK(f.fake.retained_config->limits.maximum_command_bytes==64);
        f.command.schema.fill(99); Command c(f); c.request.schema_sha256[0]=31; std::fill(std::begin(c.request.schema_sha256),std::end(c.request.schema_sha256),31);
        CHECK(c.run()==0); return;
    }
    Command c(f);
    if(name=="enter-status-rejection") {
        f.fake.enter_status=2; int enters=f.fake.enters, leaves=f.fake.leaves;
        CHECK(c.run()==BIB_ENGINE_REENTRANT&&f.fake.effects==0&&f.fake.enters==enters+1&&f.fake.leaves==leaves);
        f.fake.enter_status=14; CHECK(c.run()==BIB_ENGINE_REENTRANT&&f.fake.effects==0);
        f.fake.enter_status=0; CHECK(c.run()==0&&f.fake.effects==1&&c.result.disposition==1);return;
    }
    if(name=="command-validation") {
        auto original=c.request; int enters=f.fake.enters;
        c.request.size=4; CHECK(c.run()==BIB_ENGINE_INVALID); c.request=original;
        c.buffer.capacity=15; CHECK(c.run()==BIB_ENGINE_INVALID); CHECK(c.result.disposition==0&&c.result.bytes_written==0); c.buffer.capacity=64;
        c.request.schema_sha256[0]^=1; CHECK(c.run()==BIB_ENGINE_INVALID); c.request=original;
        c.request.payload.reserved=1; CHECK(c.run()==BIB_ENGINE_INVALID); c.request=original;
        c.request.request_sequence=0; CHECK(c.run()==BIB_ENGINE_STALE); c.request=original;
        CHECK(f.fake.enters==enters&&f.fake.effects==0);
        c.request.expected.document_sequence=2; CHECK(c.run()==BIB_ENGINE_STALE); CHECK(f.fake.effects==0); c.request=original;
        CHECK(c.run()==0&&c.result.disposition==1&&c.result.handled==0&&c.output[0]==7);
        CHECK(c.run()==BIB_ENGINE_STALE&&f.fake.effects==1); return;
    }
    if(name=="captured-reentry") {
        f.fake.reenter=true; f.fake.mutate=c.payload.data(); CHECK(c.run()==0); CHECK(f.fake.observed==4&&c.payload[0]==91);
        CHECK(f.fake.nested_enter==BIB_ENGINE_REENTRANT&&f.fake.nested_leave==BIB_ENGINE_REENTRANT&&f.fake.nested_backend==BIB_ENGINE_REENTRANT);
        CHECK(f.fake.threaded==BIB_ENGINE_WRONG_THREAD); return;
    }
    if(name=="wrong-thread") {
        int status=0, enters=f.fake.enters; std::thread thread([&]{BibEngineDocumentV1 d{};status=provider.current_document(44,&d);});thread.join();
        CHECK(status==BIB_ENGINE_WRONG_THREAD&&f.fake.enters==enters); return;
    }
    if(name=="command-error"||name=="command-malformed"||name=="command-throw"||name=="leave-throw"||name=="command-token"||name=="status-domain") {
        if(name=="command-error")f.fake.command_status=BIB_ENGINE_INVALID;
        if(name=="command-malformed")f.fake.malformed=true;
        if(name=="command-throw")f.fake.throw_command=true;
        if(name=="leave-throw")f.fake.throw_leave=true;
        if(name=="command-token")f.fake.wrong_sequence=true;
        if(name=="status-domain")f.fake.command_status=14;
        CHECK(c.run()!=0); CHECK(c.result.disposition==2&&c.result.bytes_written==0&&f.fake.effects==1);
        CHECK(c.result.request_sequence==1);
        CHECK(c.run()!=0&&f.fake.effects==1); return;
    }
    if(name=="sequence-max") {c.request.request_sequence=UINT64_MAX;CHECK(c.run()==0);c.request.request_sequence=1;CHECK(c.run()==BIB_ENGINE_STALE&&f.fake.effects==1);return;}
    if(name=="query"||name=="query-identity") {
        BibEngineQueryV1 request{}; request.size=sizeof(request); request.kind=1; request.expected=f.fake.document;
        std::memcpy(request.schema_sha256,f.query.schema.data(),32); BibEngineQueryResultV1 response{sizeof(response),99,{},0};
        if(name=="query-identity") {f.fake.wrong_query=true;CHECK(provider.query(&request,&c.buffer,&response)==BIB_ENGINE_INVALID&&response.bytes_written==0);return;}
        CHECK(provider.query(&request,&c.buffer,&response)==0); CHECK(response.bytes_written==1&&c.output[0]==8);
        f.fake.malformed=true; CHECK(provider.query(&request,&c.buffer,&response)==BIB_ENGINE_INVALID&&response.bytes_written==0); return;
    }
    if(name=="semantic-mode") {BibEngineAdvanceV1 a{sizeof(a),1,44};CHECK(provider.advance(&a)==BIB_ENGINE_INVALID&&f.fake.advances==0);a.render=0;CHECK(provider.advance(&a)==0&&f.fake.advances==1);return;}
    if(name=="exit-latch") {BibEngineAdvanceV1 a{sizeof(a),0,44};f.fake.advance_status=BIB_ENGINE_PROCESS_EXIT_REQUIRED;CHECK(provider.advance(&a)==BIB_ENGINE_PROCESS_EXIT_REQUIRED);int enters=f.fake.enters;f.fake.advance_status=0;CHECK(provider.advance(&a)==BIB_ENGINE_PROCESS_EXIT_REQUIRED&&f.fake.enters==enters&&f.fake.advances==1);return;}
    if(name=="outputs-alias") { c.buffer.bytes=reinterpret_cast<std::uint8_t*>(&c.result);CHECK(c.run()==BIB_ENGINE_INVALID&&f.fake.effects==0);return; }
    throw std::runtime_error("unknown test group");
}
}
int main(int argc,char** argv) {
    try { CHECK(argc==2);run(argv[1]);std::cout<<"PASS "<<argv[1]<<'\n';return 0; }
    catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}
}
