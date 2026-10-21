// SPDX-License-Identifier: CC0-1.0
// Real generic Browser/session ownership with value-only application fixtures.
// No HTML engine, provider, kernel, SDK or browser process runs.
#include "host/browser_surface_composition.hpp"
#include <iostream>
#include <functional>
#include <stdexcept>
#include <vector>
#include <atomic>
#include <condition_variable>
#include <thread>
#include <mutex>
namespace {
using namespace foundation;
namespace D=foundation::gui_document;
using Json=gui::web_detail::Json;
std::size_t assertions{};
void check(bool value,const char* message){++assertions;if(!value)throw std::runtime_error(message);}
template<class F>void rejected(F&& f,const char* message){++assertions;try{f();}catch(const std::exception&){return;}throw std::runtime_error(message);}
struct Probe{int submits{},takes{},states{},terminals{},destructed{},shutdowns{},service_calls{},retries{};bool wrong_ticket{},future_publication{},throw_submit{},construct_inert{},destroy_inert{},throw_service{},fail_retry{};std::function<void()> during_retry;};
Probe* probe{};
gui::Snapshot snapshot(){gui::Snapshot s;s.revision=1;s.title="Generic document host";s.client_size={100,100};return s;}
struct Plain{
    gui::Adapter& adapter;Probe& p;
    explicit Plain(gui::Adapter& a):adapter(a),p(*probe){adapter.present(snapshot());}
    ~Plain(){++p.destructed;}
    void handle(gui::Event){} void tick(){} void shutdown(){++p.shutdowns;} void retry_presentation(){++p.retries;if(p.during_retry)p.during_retry();if(p.fail_retry){auto next=snapshot();next.revision=2;gui::Widget w;w.spec.key={"broken",1};w.spec.kind=gui::Kind::bitmap;w.state.bounds={0,0,100,100};w.state.bitmap={"broken",1,gui::BitmapSource([](const gui::BitmapRequest&,const gui::BitmapSink&){throw std::runtime_error("Fixture retry paint failure");})};next.widgets.push_back(std::move(w));adapter.present(std::move(next));}}
    std::optional<gui::ServiceRequest> next_service(){++p.service_calls;if(p.throw_service)throw std::runtime_error("Fixture initial service failure");return {};} bool complete_service(gui::ServiceResult){return false;}
    void qualify(const std::function<void()>& f){f();}
};
struct Document:Plain{
    D::State live;std::optional<D::Completion> completion;
    explicit Document(gui::Adapter& a):Plain(a){
        live.available=true;
        auto& actual=dynamic_cast<host::BrowserSurfaceAdapter&>(adapter);
        const auto before=p.states;const auto result=actual.document_submit(D::Observe{});
        p.construct_inert=p.states==before&&p.submits==0&&result.admission==D::Admission::unavailable;
    }
    ~Document(){auto& actual=dynamic_cast<host::BrowserSurfaceAdapter&>(adapter);const auto before=p.submits;const auto result=actual.document_submit(D::Observe{});p.destroy_inert=p.submits==before&&!actual.document_endpoint_bound()&&result.admission==D::Admission::closed;}
    D::Submission document_submit(D::Intent){++p.submits;if(p.throw_submit)throw std::runtime_error("Fixture submit failure");live.pending=D::Ticket{53};live.phase=D::Phase::waiting_take;completion=D::Completion{{p.wrong_ticket?54u:53u},D::Outcome::completed,{},{},""};return {D::Admission::accepted,D::Ticket{53}};}
    std::optional<D::Completion> document_take(D::Ticket ticket){++p.takes;if(!completion||(ticket.value!=53&&ticket!=completion->ticket))return {};auto result=std::move(completion);completion.reset();live.pending.reset();live.phase=D::Phase::idle;return result;}
    D::State document_state()const{++p.states;auto result=live;if(p.future_publication)result.publication_revision=2;return result;}
    D::TerminalHook document_terminal()noexcept{return {&p,[](void* context)noexcept{++static_cast<Probe*>(context)->terminals;}};}
};
struct Partial:Plain{using Plain::Plain;D::Submission document_submit(D::Intent){return {};}};
struct Borrowed:Document{using Document::Document;D::Submission document_submit(const D::Intent&){return {};}};
struct WrongTerminal:Document{using Document::Document;D::TerminalHook document_terminal(){return {};}};
static_assert(host::BrowserSurfaceApplication<Plain>);
static_assert(host::BrowserSurfaceApplication<Document>);
static_assert(!host::BrowserSurfaceApplication<Partial>);
static_assert(!host::BrowserSurfaceApplication<Borrowed>);
static_assert(!host::BrowserSurfaceApplication<WrongTerminal>);
std::string message(std::uint64_t sequence,Json operation){return gui::web_detail::encode(Json::Object{{"epoch","generic-document"},{"seq",std::to_string(sequence)},{"operation",std::move(operation)}});}
host::BrowserSurfaceComposition document_composition(){return host::BrowserSurfaceComposition{0,host::surface_web::Profile::legacy,{}, {},true};}
Json submit(){return Json::Object{{"type","documentSubmit"},{"version",1},{"intent",Json::Object{{"kind","observe"}}}};}
void absent_legacy(){Probe p;probe=&p;host::Browser<Plain,host::BrowserSurfaceComposition> runtime("generic-document",host::BrowserSurfaceComposition{});const auto initial=gui::web_detail::Parser(runtime.initial()).parse();check(std::get<Json::Object>(initial.value).count("document")==0,"Legacy application acquired a document capability");check(!runtime.adapter.document_endpoint_bound(),"Absent document hooks were bound");}
void route_and_lifetime(){
    Probe p;probe=&p;
    {host::Browser<Document,host::BrowserSurfaceComposition> runtime("generic-document",document_composition());
        const auto initial=gui::web_detail::Parser(runtime.initial()).parse();check(initial.at("document").at("publicationRevision").str()=="0"&&p.construct_inert,"Construction entered an unarmed application");
        const auto request=message(1,submit());const auto submitted_text=runtime.receive(request);const auto submitted=gui::web_detail::Parser(submitted_text).parse();check(submitted.at("documentReply").at("ticket").str()=="53"&&p.submits==1,"Document submit did not use the typed app hook");
        runtime.app().live.available=false;const auto states=p.states,services=p.service_calls;check(runtime.receive(request)==submitted_text,"Duplicate GUI envelope changed its original response bytes");check(p.states==states&&p.submits==1&&p.service_calls==services,"Duplicate GUI envelope resampled metadata/service or repeated submission");runtime.app().live.available=true;
        const auto take=message(2,Json::Object{{"type","documentTake"},{"version",1},{"ticket","53"}});
        const auto taken_text=runtime.receive(take);const auto taken=gui::web_detail::Parser(taken_text).parse();check(taken.at("documentReply").at("completion").at("outcome").str()=="completed"&&p.takes==1,"Known Take completion was lost");
        check(taken.at("document").at("publicationRevision").str()=="0"&&std::holds_alternative<std::nullptr_t>(taken.at("document").at("pending").value),"Take invented a publication revision or retained pending metadata");
        runtime.app().live.phase=D::Phase::queued;check(runtime.receive(take)==taken_text,"Duplicate Take changed its original response bytes");check(p.takes==1,"Duplicate GUI Take repeated local consumption");
        const auto polled=gui::web_detail::Parser(runtime.receive(message(3,Json::Object{{"type","poll"}}))).parse();check(std::holds_alternative<std::nullptr_t>(polled.at("documentReply").value),"Poll relabeled an older document reply as its own GUI acknowledgment");
    }
    check(p.shutdowns==1&&p.destructed==1&&p.destroy_inert,"Document hooks survived application disarm/destruction");check(p.terminals==0,"Ordinary destruction fabricated terminal failure");
}
void submit_before_retry_and_take_progress(){
    Probe p;probe=&p;host::Browser<Document,host::BrowserSurfaceComposition> runtime("generic-document",document_composition());
    (void)runtime.initial();const auto retries=p.retries;
    p.during_retry=[&]{check(p.submits==1&&p.takes==0,"Document retry crossed an unadmitted submit");runtime.app().live.available=false;};
    const auto request=message(1,submit());const auto submitted_text=runtime.receive(request);
    const auto submitted=gui::web_detail::Parser(submitted_text).parse();
    check(submitted.at("error").str().empty()&&submitted.at("documentReply").at("ticket").str()=="53"&&p.submits==1&&p.retries==retries,
        "Document submit advanced work before its typed reservation");
    check(runtime.receive(request)==submitted_text&&p.submits==1&&p.retries==retries,"Duplicate document submit advanced work or repeated reservation");
    const auto taken=gui::web_detail::Parser(runtime.receive(message(2,Json::Object{{"type","documentTake"},{"version",1},{"ticket","53"}}))).parse();
    check(taken.at("error").str().empty()&&taken.at("documentReply").at("completion").at("outcome").str()=="completed"&&
        !taken.at("document").at("available").boolean()&&p.takes==1&&p.retries==retries+1,
        "Document metadata Take lost retry progress or its owned completion");
    p.during_retry={};
}
void accept_later_edit(Document& app){
    auto frame=snapshot();frame.revision=2;app.adapter.present(std::move(frame));
    auto native=std::make_shared<ui::NativeFormsDocumentObservation>();native->publication={1,1,1};native->forms.version=native->publication;native->body.request_id=71;native->body.epoch=1;
    app.live.publication_revision=2;app.live.observation=D::Observation{71};app.live.document=std::move(native);D::DraftView draft;draft.id={72};draft.kind=appended::FormKind::textarea;draft.phase=appended::FormDraftPhase::editing;draft.text="Later accepted edit";app.live.draft=std::move(draft);app.live.phase=D::Phase::idle;
}
void duplicate_completion_after_accepted_edit(){
    for(const unsigned variant:{0u,1u,2u,3u}){
        Probe p;probe=&p;host::Browser<Document,host::BrowserSurfaceComposition> runtime("generic-document",document_composition());(void)runtime.initial();(void)runtime.receive(message(1,submit()));const auto original=*runtime.app().completion;
        const auto first=gui::web_detail::Parser(runtime.receive(message(2,Json::Object{{"type","documentTake"},{"version",1},{"ticket","53"}}))).parse();
        accept_later_edit(runtime.app());const auto later=gui::web_detail::Parser(runtime.receive(message(3,Json::Object{{"type","poll"}}))).parse();
        auto repeated=original;
        if(variant==1){repeated.observation=runtime.app().live.observation;repeated.draft=runtime.app().live.draft;repeated.detail="Changed whole payload";}
        if(variant==2)repeated.ticket={54};
        if(variant==3)repeated.outcome=D::Outcome::unknown;
        runtime.app().completion=repeated;
        const auto request=message(4,Json::Object{{"type","documentTake"},{"version",1},{"ticket",variant==2?"54":"53"}});
        if(variant==0){const auto again=gui::web_detail::Parser(runtime.receive(request)).parse();check(gui::web_detail::encode(again.at("documentReply").at("completion"))==gui::web_detail::encode(first.at("documentReply").at("completion")),"Exact validated completion was not redelivered with a new GUI envelope");check(gui::web_detail::encode(again.at("document"))==gui::web_detail::encode(later.at("document")),"Duplicate old completion replaced newer accepted State");check(!runtime.adapter.failed()&&p.terminals==0&&p.takes==2,"Exact completion redelivery poisoned or bypassed the typed hook");}
        else{try{(void)runtime.receive(request);}catch(const std::exception&){}check(runtime.adapter.failed()&&p.terminals==1,"Changed, unseen old or unknown completion used the last-validated cache");}
    }
}
void fail_once(){
    Probe p;probe=&p;host::Browser<Document,host::BrowserSurfaceComposition> runtime("generic-document",document_composition());(void)runtime.initial();
    rejected([&]{runtime.receive(message(1,Json::Object{{"type","documentPublicationAck"},{"version",1}}));},"Public publication ACK was accepted");
    check(runtime.adapter.failed()&&p.terminals==1&&p.submits==0&&p.takes==0,"Malformed document request did not poison before reservation");
    rejected([&]{runtime.receive(message(2,submit()));},"Terminal adapter admitted later intent");check(p.terminals==1,"Duplicate failure notified twice");runtime.adapter.close();check(!runtime.adapter.document_endpoint_bound(),"Failed close did not detach document hooks");
}
void first_failure_without_initial(){
    Probe p;probe=&p;host::Browser<Document,host::BrowserSurfaceComposition> runtime("generic-document",document_composition());
    rejected([&]{runtime.receive("{}");},"Malformed first receive was accepted");
    check(runtime.adapter.failed()&&p.terminals==1&&p.submits==0&&p.takes==0,"First malformed request dropped terminal poison before initial state");
}
void initial_supplier_failure(){
    Probe p;probe=&p;p.throw_service=true;host::Browser<Document,host::BrowserSurfaceComposition> runtime("generic-document",document_composition());
    try{(void)runtime.initial();}catch(const std::exception&){}
    check(runtime.adapter.failed()&&p.terminals==1&&p.service_calls==1,"Initial supplier failure dropped terminal poison before state sampling");
}
void prefix_retry_failure(){
    Probe p;probe=&p;p.fail_retry=true;host::Browser<Document,host::BrowserSurfaceComposition> runtime("generic-document",document_composition());
    rejected([&]{runtime.initial();},"Prefix presentation retry failure was hidden");
    check(runtime.adapter.failed()&&p.terminals==1,"Prefix retry publication failure dropped terminal poison");
}
void crossed_and_future(){
    for(const bool crossed:{true,false}){Probe p;probe=&p;p.wrong_ticket=crossed;p.future_publication=!crossed;host::Browser<Document,host::BrowserSurfaceComposition> runtime("generic-document",document_composition());
        if(crossed){
            (void)runtime.initial();(void)runtime.receive(message(1,submit()));
            const auto response=gui::web_detail::Parser(runtime.receive(message(2,Json::Object{{"type","documentTake"},{"version",1},{"ticket","53"}}))).parse();
            // Supplier receive reports caught endpoint errors on the wire. The
            // terminal response must carry no crossed completion or live authority.
            check(response.at("error").str()=="Mismatched document completion ticket"&&response.at("ack").str()=="2"&&
                response.at("snapshot").at("closed").boolean()&&response.at("document").at("phase").str()=="terminal"&&!response.at("document").at("available").boolean()&&
                std::holds_alternative<std::nullptr_t>(response.at("documentReply").value)&&std::holds_alternative<std::nullptr_t>(response.at("service").value)&&std::holds_alternative<std::nullptr_t>(response.at("transfer").value)&&p.takes==1,
                "Crossed completion ticket did not produce its terminal wire error");
            const auto submits=p.submits,takes=p.takes,states=p.states,services=p.service_calls;
            rejected([&]{runtime.receive(message(3,submit()));},"Crossed completion failure admitted later ingress");
            check(p.submits==submits&&p.takes==takes&&p.states==states&&p.service_calls==services&&p.terminals==1,"Terminal crossed completion repeated application work");
        }
        else rejected([&]{runtime.initial();},"Future document publication accepted before GUI commit");
        check(runtime.adapter.failed()&&p.terminals==1,"Invalid document output failed without terminal notification");
    }
}
void explicit_opt_in(){
    Probe p;probe=&p;
    {host::Browser<Document,host::BrowserSurfaceComposition> runtime("generic-document",host::BrowserSurfaceComposition{});const auto initial=gui::web_detail::Parser(runtime.initial()).parse();check(!runtime.adapter.document_endpoint_bound()&&std::get<Json::Object>(initial.value).count("document")==0,"Exact App methods silently enabled document capability");}
    rejected([&]{host::Browser<Plain,host::BrowserSurfaceComposition> runtime("generic-document",document_composition());},"Opted-in composition without complete App hooks was accepted");
}
void terminal_binding(){
    struct State{std::mutex mutex;std::condition_variable cv;bool entered{},release{};std::atomic<unsigned> calls{};} state;
    auto binding=std::make_shared<host::BrowserDocumentTerminalBinding>();
    binding->notify();check(state.calls==0,"Unarmed terminal binding entered an App");
    binding->bind({&state,[](void* raw)noexcept{auto& s=*static_cast<State*>(raw);++s.calls;std::unique_lock lock(s.mutex);s.entered=true;s.cv.notify_all();s.cv.wait(lock,[&]{return s.release;});}});
    std::thread notification([&]{binding->notify();});
    {std::unique_lock lock(state.mutex);state.cv.wait(lock,[&]{return state.entered;});}
    std::atomic<bool> detached{};std::thread detacher([&]{binding->detach();detached=true;});
    check(!detached,"Detach completed while terminal callback was in flight");
    {std::lock_guard lock(state.mutex);state.release=true;}state.cv.notify_all();notification.join();detacher.join();
    binding->notify();check(detached&&state.calls==1,"Terminal detach/duplicate notification entered retired context");
    rejected([&]{binding->bind({&state,[](void*)noexcept{}});},"Detached terminal binding was rearmed");
}
void partial_descriptor(){host::BrowserDocumentEndpoint partial;partial.submit=[](D::Intent){return D::Submission{};};rejected([&]{host::BrowserSurfaceAdapter adapter(1,{}, {},0,host::surface_web::Profile::legacy,{},partial);},"Partial explicit document endpoint accepted");}
}
int main(){try{absent_legacy();explicit_opt_in();route_and_lifetime();submit_before_retry_and_take_progress();duplicate_completion_after_accepted_edit();fail_once();first_failure_without_initial();initial_supplier_failure();prefix_retry_failure();crossed_and_future();terminal_binding();partial_descriptor();std::cout<<assertions<<" generic document composition assertions passed\n";return 0;}catch(const std::exception& error){std::cerr<<error.what()<<'\n';return 1;}}
