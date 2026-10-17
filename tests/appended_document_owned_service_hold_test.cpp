// Source-authored focused debt cases. Not yet compiled or executed.
#define main foundation_original_document_application_fixture_main
#include "../gui/tests/appended_engine_document_application_test.cpp"
#undef main
namespace {
void owned_hold_requires_actual_safe_publication() {
    Fixture f(false,false,true); f.native_value="PRIVATE_HOLD_VALUE";
    f.finish_query(f.take()); f.app->tick();
    check(f.app->body_ready(),"initial actual4083 publication missing");
    const auto installed=f.adapter.terminal.snapshot().revision,attempts=f.adapter.attempts.size();
    f.adapter.fail_before=true; f.app->set_owned_service_active(true);
    try { f.app->tick(); } catch(const std::runtime_error&) {}
    check(f.adapter.attempts.size()>attempts && !f.adapter.fail_before &&
        f.adapter.terminal.snapshot().revision==installed &&
        !f.app->owned_service_ready() && f.app->presentation_pending(),"failed safe publication was called ready or installed");
    check(!f.peek(),"failed safe publication admitted new document work");
    const auto failed=f.adapter.attempts.back().revision;
    f.app->retry_presentation(); f.app->tick();
    check(f.app->owned_service_ready() && f.adapter.attempts.back().revision==failed,"exact safe candidate was not retained");
    redacted(f.adapter.terminal.snapshot(),f.native_value);
    f.app->foreground(true); f.app->tick();
    check(f.app->owned_service_ready() && !f.peek(),"true OS foreground accidentally released internal hold");
    f.app->set_owned_service_active(false); f.refresh();
    check(f.app->body_ready(),"hold release did not require/accept a fresh actual query");
}
void outstanding_query_blocks_hold_readiness() {
    Fixture f(false,false,true); const auto query=f.take();
    f.claim(query); f.app->set_owned_service_active(true); f.app->tick();
    check(!f.app->owned_service_ready(),"admitted query was ignored by readiness");
    f.result(query,query_reply(query,f.revision),0,0,false,f.revision);
    for(unsigned n=0;n!=5;++n)f.app->tick();
    check(f.app->owned_service_ready() && !f.peek(),"retained query did not settle without a new effect/query");
}
void accepted_apply_requires_original_ack_before_ready() {
    Fixture f(true,false,true); f.open(); const auto action=f.apply("PRIVATE_APPLY_VALUE"); f.claim(action);
    f.app->set_owned_service_active(true); f.app->tick();
    check(!f.app->owned_service_ready(),"admitted Apply was dropped by the hold");
    ++f.revision; f.result(action,form_reply(action,0,0,f.revision,"PRIVATE_APPLY_VALUE",f.revision+87),0,1,true);
    f.app->tick(); check(!f.app->owned_service_ready(),"consumed Apply became ready before its actual ACK");
    const auto ack=f.finish_ack(action);
    check(ack.work.target==action.work.target && get(ack.work.payload,0,8)==action.work.request_sequence,"hold changed original ACK identity");
    for(unsigned n=0;n!=5;++n)f.app->tick();
    check(f.app->owned_service_ready() && !f.peek(),"original ACK/publication debt did not drain under hold");
    redacted(f.adapter.terminal.snapshot(),"PRIVATE_APPLY_VALUE");
}
void native_effect_blocks_hold_readiness() {
    Fixture f(true,true,true); f.discover();
    const std::array<std::uint8_t,4> request{1,2,3,4}; f.submit_service(2,f.route,1,request);
    f.app->set_owned_service_active(true); f.app->tick();
    check(!f.app->owned_service_ready() && f.owner->native_effect(),"real pending Registry effect was ignored");
    ok(call(*f.owner,FOUNDATION_ENGINE_PUMP_ONE,f.id));
    check(f.collect_service(2)==Bytes(request.begin(),request.end()),"actual native service outcome changed");
    for(unsigned n=0;n!=5;++n)f.app->tick();
    check(f.effects==1 && f.app->owned_service_ready(),"effect was replayed or not settled before readiness");
}
}
int main(int argc,char**argv){
    const std::array<std::pair<const char*,void(*)()>,4> tests{{
        {"publication",owned_hold_requires_actual_safe_publication},{"query",outstanding_query_blocks_hold_readiness},
        {"apply-ack",accepted_apply_requires_original_ack_before_ready},{"native-effect",native_effect_blocks_hold_readiness}}};
    if(argc!=3||std::string_view(argv[1])!="--case")return 2;
    for(const auto&[name,test]:tests)if(std::string_view(argv[2])==name){try{test();std::cout<<"PASS "<<name<<" "<<assertions<<" assertions,0 skipped\n";return 0;}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
    return 2;
}
