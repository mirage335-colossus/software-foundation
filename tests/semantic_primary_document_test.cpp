// Focused semantic composition routing regression.
// Real TerminalAdapter/Owner/Driver/Forms/Broker, existing mock C table and
// metadata-only view binding. Actual Module coverage is the separate7-case run.
#include "semantic_native_fixture.hpp"

namespace {
const gui::Widget* visible(const Fixture& f,std::string_view id) {
    const auto* w=gui::find_widget(f.app->view(),{std::string(id),1});
    return w && w->state.visible && w->state.enabled ? w : nullptr;
}
void tab(Fixture& f,bool compiled) {
    f.app->handle(gui::WidgetEvent{{compiled?"foundation.semantic.compiled":"foundation.semantic.document",1},gui::Activate{}});
}
void show_html(Fixture& f) {
    tab(f,false);f.until([&]{return f.app->body_ready();},"HTML switch did not wait for actual fresh paired publication");
}
void compiled_feature_and_html_share_one_owner() {
    Fixture f(true,EngineStartupPrimary::compiled);
    check(visible(f,"compiled.increment") && !f.queries,"compiled page entered HTML before its inactive hold settled");
    const auto before=f.calls;
    f.app->handle(gui::WidgetEvent{{"compiled.increment",1},gui::Activate{}});
    check(f.calls==before && visible(f,"compiled.count")->state.text=="Count: 0","compiled callback entered provider or synchronously changed feature");
    f.tick();check(visible(f,"compiled.count")->state.text=="Count: 1","shared compiled feature did not publish normally");
    f.native_value="PRIVATE_HTML_VALUE";show_html(f);
    check(f.driver->owner()==f.owner && exported_text(f.app->view()).find("PRIVATE_HTML_VALUE")!=std::string::npos,"HTML did not use the same real Owner/Driver");
    const auto calls=f.calls;tab(f,true);
    check(f.calls==calls && exported_text(f.app->view()).find("PRIVATE_HTML_VALUE")==std::string::npos,"tab callback exported stale native data or entered provider");
    f.until([&]{return visible(f,"compiled.increment")!=nullptr;},"compiled page crossed unfinished4083 hold");
    check(exported_text(f.adapter.terminal.snapshot()).find("PRIVATE_HTML_VALUE")==std::string::npos,"inactive HTML data remained in actual combined Snapshot");
    const auto queries=f.queries;for(unsigned n=0;n!=5;++n)f.tick();
    check(f.queries==queries,"hidden semantic pane was rearmed after its hold");
}
void exact_combined_retry(bool after) {
    Fixture f(true,EngineStartupPrimary::compiled);
    f.adapter.fail_before=!after;f.adapter.fail_after=after;
    f.app->handle(gui::WidgetEvent{{"compiled.increment",1},gui::Activate{}});
    bool threw=false;try{f.tick();}catch(const std::runtime_error&){threw=true;}
    check(threw && f.app->presentation_pending(),"failed combined scene was not retained");
    const auto failed=f.adapter.attempts.back();const auto calls=f.calls;
    tab(f,false);check(f.calls==calls,"navigation crossed failed actual publication debt");
    f.app->retry_presentation();
    check(f.adapter.attempts.back().revision==failed.revision && exported_text(f.adapter.attempts.back())==exported_text(failed),"retry changed the exact failed combined candidate");
    check(visible(f,"compiled.count")->state.text=="Count: 1","retry replayed the accepted compiled action");
}
void presentation_debt_prevents_graceful_close() {
    Fixture f(true,EngineStartupPrimary::compiled);
    f.adapter.fail_before=true;f.app->handle(gui::WidgetEvent{{"compiled.increment",1},gui::Activate{}});
    try{f.tick();}catch(const std::runtime_error&){}
    check(f.app->presentation_pending(),"close discriminator has no actual failed candidate");
    f.app->shutdown();f.driver->request_close();
    // Test-only direct Driver turns establish native detach independently of
    // the deliberately failed GUI scene; they are never a production fallback.
    for(unsigned n=0;n!=24 && f.driver->state()!=NativeEngineState::detached;++n)f.driver->tick(f.now+=1ms);
    check(f.driver->state()==NativeEngineState::detached,"close discriminator failed to establish actual Driver detach");
    check(!f.app->shutdown_complete(),"Driver detach hid unresolved combined presentation debt");
    f.app->retry_presentation();check(f.app->shutdown_complete(),"exact successful retry did not settle local close debt");
}
void low_binary_control_then_html_resets_terminal_pan() {
    Fixture f(true,EngineStartupPrimary::binary,true);f.tick();
    check(f.binary_binding && !f.binary_binding->model->pending(),"binary source was ACKed before/without actual publication");
    check(f.adapter.terminal.focus(gui::WidgetKey{"binary.increment",1}),"actual terminal could not focus low source control");
    const auto text=terminal_text(f.adapter.terminal);
    check(f.adapter.terminal.viewport_origin().y>0 && text.find("Count: 0")!=std::string::npos,"logical source canvas did not reveal low control in actual cells");
    show_html(f);const auto html=terminal_text(f.adapter.terminal);
    check(f.adapter.terminal.viewport_origin()==gui::Point{0,0} && html.find("Paired body observation")!=std::string::npos,"compiled global pan hid reflowed HTML rows");
    check(f.app->view().client_size==gui::Size{448,256},"HTML used a logical/minimum canvas instead of actual56x16 cells");
}
void real_offer_freezes_driver_and_retains_close_debt() {
    Fixture f(true,EngineStartupPrimary::binary);f.tick();
    f.binary_binding->ask_service();check(!f.app->next_service(),"GUI request bypassed actual combined safe publication");
    std::optional<gui::ServiceRequest> request;
    for(unsigned n=0;n!=12&&!request;++n){f.tick();request=f.app->next_service();}
    check(request.has_value(),"actual settled hold did not offer binary GUI request");
    const auto calls=f.calls;f.tick();check(f.calls==calls,"ordinary Driver advanced during external UI offer");
    check(!f.app->complete_service({request->id+1,gui::ServiceStatus::cancelled,{},{}}),"foreign service result consumed offer");
    f.app->foreground(false);f.app->shutdown();f.tick();
    check(f.calls==calls && !f.app->shutdown_complete(),"close/foreground bypassed actual external UI debt");
    check(f.app->complete_service({request->id,gui::ServiceStatus::cancelled,"obsolete","obsolete"}),"matching external UI completion was lost during close");
    f.until([&]{return f.app->shutdown_complete();},"known external completion did not resume existing close drain");
    check(f.binding_probe.service_exports==0,"closed guest received a synthetic obsolete service completion/ACK");
}
Bytes owner_call(Fixture& f,unsigned operation,Span body={}) {
    const auto id=f.owner->identity();Bytes input(72+body.size());std::copy_n("FKB1",4,input.begin());
    put(input,4,1,2);put(input,6,operation,2);put(input,8,input.size(),4);
    put(input,16,id.worker_epoch,8);put(input,24,id.application_instance,8);put(input,32,id.document_sequence,8);put(input,40,id.service_generation,8);
    put(input,64,body.size(),4);std::copy(body.begin(),body.end(),input.begin()+72);
    Bytes output(4096);const auto count=f.owner->dispatch(operation,input,output);
    check(count>=80 && static_cast<std::size_t>(count)<=output.size(),"real Owner counterfactual receipt malformed");output.resize(count);return output;
}
void pending_effect_before_handle_drops_stale_compiled_intent() {
    Fixture f(true,EngineStartupPrimary::compiled);show_html(f);f.discover();tab(f,true);
    f.until([&]{return visible(f,"compiled.increment")!=nullptr;},"compiled hold did not settle");
    Envelope envelope;envelope.generation=f.current.service_generation;envelope.sequence=2;envelope.interface_handle=f.route;envelope.operation=1;
    Bytes encoded;check(encode_envelope(envelope,encode_u32(41),encoded)==CodecStatus::ok,"counterfactual service encoding failed");
    const auto submitted=owner_call(f,FOUNDATION_ENGINE_SUBMIT,encoded);
    check(get(submitted,72,4)==0 && get(submitted,76,4)==0,"counterfactual actual Owner submit failed");
    (void)owner_call(f,FOUNDATION_ENGINE_PUMP_ONE);
    check(f.owner->native_effect() && !f.owner->native_effect()->entered,"counterfactual did not create actual pending effect before handle");
    const auto calls=f.calls;f.app->handle(gui::WidgetEvent{{"compiled.increment",1},gui::Activate{}});
    check(f.calls==calls,"effect-rejected callback entered provider");
    f.until([&]{return f.effects==1 && !f.owner->native_effect();},"actual pending effect did not settle through real safe publication");
    for(unsigned n=0;n!=8;++n)f.tick();
    check(visible(f,"compiled.count") && visible(f,"compiled.count")->state.text=="Count: 0","stale compiled intent survived a pending native effect");
}
void pending_effect_after_handle_retires_already_retained_intent() {
    Fixture f(true,EngineStartupPrimary::compiled);show_html(f);f.discover();tab(f,true);
    f.until([&]{return visible(f,"compiled.increment")!=nullptr;},"compiled hold did not settle");
    f.app->handle(gui::WidgetEvent{{"compiled.increment",1},gui::Activate{}});
    check(visible(f,"compiled.count")->state.text=="Count: 0","compiled action ran inside its admission callback");
    Envelope envelope;envelope.generation=f.current.service_generation;envelope.sequence=2;envelope.interface_handle=f.route;envelope.operation=1;
    Bytes encoded;check(encode_envelope(envelope,encode_u32(41),encoded)==CodecStatus::ok,"retained-intent service encoding failed");
    const auto submitted=owner_call(f,FOUNDATION_ENGINE_SUBMIT,encoded);
    check(get(submitted,72,4)==0 && get(submitted,76,4)==0,"retained-intent actual Owner submit failed");
    (void)owner_call(f,FOUNDATION_ENGINE_PUMP_ONE);
    check(f.owner->native_effect() && !f.owner->native_effect()->entered,"retained-intent setup omitted actual pending effect");
    f.until([&]{return f.effects==1 && !f.owner->native_effect();},"retained-intent actual effect did not settle safely");
    for(unsigned n=0;n!=8;++n)f.tick();
    check(visible(f,"compiled.count") && visible(f,"compiled.count")->state.text=="Count: 0","intent retained before an effect survived its tick barrier");
}
void native_effect_redacts_both_source_pages() {
    Fixture f(true,EngineStartupPrimary::compiled);show_html(f);f.discover();
    f.open();f.adapter.terminal.input("PRIVATE_COMPOSITION_DRAFT");
    // Existing C-table fixture emits/ACKs the actual native service. Its real
    // Registry callback checks cleared source state and actual terminal cells.
    f.send(2,f.route,1,encode_u32(41));
    f.until([&]{return f.effects==1;},"real native service did not pass the single safe presenter");
    check(exported_text(f.adapter.terminal.snapshot()).find("PRIVATE_COMPOSITION_DRAFT")==std::string::npos,"whole-scene native mask exported old draft");
}
}
int main(int argc,char**argv){
    const std::array<std::pair<const char*,void(*)()>,9> cases{{
        {"compiled-html",compiled_feature_and_html_share_one_owner},{"retry-before",[]{exact_combined_retry(false);}},
        {"retry-after",[]{exact_combined_retry(true);}},{"close-publication",presentation_debt_prevents_graceful_close},
        {"low-control-html",low_binary_control_then_html_resets_terminal_pan},{"offered-close",real_offer_freezes_driver_and_retains_close_debt},
        {"native-effect",native_effect_redacts_both_source_pages},{"effect-before-handle",pending_effect_before_handle_drops_stale_compiled_intent},
        {"effect-after-handle",pending_effect_after_handle_retires_already_retained_intent}}};
    if(argc!=3||std::string_view(argv[1])!="--case")return 2;
    for(const auto&[name,test]:cases)if(std::string_view(argv[2])==name){try{test();std::cout<<"PASS "<<name<<" "<<assertions<<" assertions,0 skipped\n";return 0;}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
    return 2;
}
