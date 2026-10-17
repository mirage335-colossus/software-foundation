// Source-authored only; this new fixture has not been compiled or run.
#include "shared/appended_engine_module.hpp"
#include "shared/appended_binary_view_model.hpp"
#include "appended_application_guest_fixture.hpp"
#include <iostream>
#include <utility>

using namespace foundation::appended;
using namespace foundation::appended::binding_fixture;
namespace {
std::unique_ptr<EngineModuleBinding> make_binding(const Script& script) {
    auto bytes=wasm(script);
    auto binding=make_engine_binary_view_module_binding(bytes,{},7);
    std::fill(bytes.begin(),bytes.end(),0xff); // The single Module must own its image.
    return binding;
}
Bytes service_event(std::uint64_t sequence,std::uint64_t id,std::uint32_t status,
                    std::string_view value,std::string_view error) {
    return envelope(FOUNDATION_APPENDED_MESSAGE_EVENT,sequence,2,
        record({integer(1,id),enumeration(2,status),text(3,value),text(4,error)},true));
}
gui::ServiceResult result(std::uint64_t id,gui::ServiceStatus status,std::string value={},std::string error={}) {
    gui::ServiceResult value_result; value_result.id=id; value_result.status=status;
    value_result.value=std::move(value); value_result.error=std::move(error); return value_result;
}
Bytes click(const std::shared_ptr<const EngineModuleView>& view,std::uint64_t revision) {
    gui::Event event=gui::WidgetEvent{{"apply",1},gui::Activate{}};
    check(view->normalize_event(event,EngineModuleView::EventFacts{}),"fixture live click did not normalize");
    return EngineModuleView::encode_event(event,revision);
}
void initialization_and_exact_publication_ack() {
    auto binding=make_binding(Script{{call(1,1,replacement(0,{}),ServiceStatus::ok,1)}, {}});
    auto view=binding->view();
    check(binding->supports_view() && view && view->pending() && view->snapshot().revision==1,
          "foundation.view was not registered before the actual guest initialized");
    check(!binding->acknowledge_view(0) && view->pending(),"zero ACK cleared initial pending publication");
    const auto premature=EngineModuleView::encode_event(gui::WidgetEvent{{"apply",1},gui::Activate{}},1);
    check(!binding->stage_view_event(1,premature),"unpublished binary view accepted input");
    check(binding->acknowledge_view(1) && !view->pending() && !binding->acknowledge_view(1),
          "exact publication ACK was not single-use");
    check(!binding->stage_view_event(9001,premature),"composed revision substituted for module-local revision");
    binding->close();
    check(view->closed() && view->snapshot().revision==1 && !binding->acknowledge_view(1),
          "closed binding lost owned snapshot or accepted publication");
}
void providers_view_and_service_share_one_module_allocator() {
    ViewState provided,activated,completed;provided.title="provider";activated.title="view";completed.title="service";
    Script script{{call(1,FOUNDATION_PROVIDER_REGISTER,provider_registration(),ServiceStatus::ok,1,2),
                   call(2,1,replacement(0,{}),ServiceStatus::ok,1),call(3,2,service_request())}, {
        {provider_event(1,10,41),{provider_response(4,10,42,1),call(5,1,replacement(1,provided),ServiceStatus::ok,2)}},
        {input_event(2,2,"apply",1,1),{call(6,1,replacement(2,activated),ServiceStatus::ok,3)}},
        {service_event(3,99,2,"",""),{call(7,1,replacement(3,completed),ServiceStatus::ok,4)}}}};
    auto binding=make_binding(script);auto view=binding->view();
    check(binding->acknowledge_view(1),"initial source revision ACK failed");
    auto hooks=binding->services();const auto found=hooks.discover(provider_query());
    check(found.status==ServiceStatus::ok && hooks.generation==7,"actual provider registration missing");
    ProviderRequest request{7,10,found.handle,1,encode_u32(41)};
    check_provider_result(hooks.invoke(request),42,1);
    check(view->snapshot().revision==2 && view->snapshot().title=="provider" && view->pending(),
          "provider did not mutate the same Module view");
    check(hooks.acknowledge(10)==ServiceStatus::ok && binding->acknowledge_view(2),"independent provider/view ACK failed");
    auto event=click(view,2);
    check(binding->stage_view_event(2,event),"live module-local view event not staged");
    std::fill(event.begin(),event.end(),0);
    check(view->snapshot().revision==2,"staging reentered guest before tick");
    binding->tick_view();
    check(view->snapshot().revision==3 && view->snapshot().title=="view" && view->pending(),
          "view dispatch did not use the shared second event sequence/owned bytes");
    check(!binding->acknowledge_view(2) && binding->acknowledge_view(3),"wrong local publication ACK accepted");
    auto request_wrapper=binding->begin_view_service();
    check(request_wrapper && request_wrapper->request.id==99,"actual generic host request missing");
    auto cancelled=result(99,gui::ServiceStatus::cancelled,"remove value","remove error");
    auto payload=EngineModuleView::encode_service_result(cancelled);
    check(binding->stage_view_service_result(payload),"host completion not staged");
    std::fill(payload.begin(),payload.end(),0xff);
    binding->tick_view();
    check(view->snapshot().revision==4 && view->snapshot().title=="service" && !binding->current_view_service(),
          "service dispatch was not normalized or did not use the shared third event sequence");
}
void begin_current_and_owned_completion() {
    const auto second=record({integer(1,100),enumeration(2,3),text(3,"second"),enumeration(5,8)});
    ViewState one,two;one.title="first completed";two.title="second completed";
    Script script{{call(1,1,replacement(0,{}),ServiceStatus::ok,1),call(2,2,service_request()),call(3,2,second)}, {
        {service_event(1,99,1,"hello",""),{call(4,1,replacement(1,one),ServiceStatus::ok,2)}},
        {service_event(2,100,1,"next",""),{call(5,1,replacement(2,two),ServiceStatus::ok,3)}}}};
    auto binding=make_binding(script);check(binding->acknowledge_view(1),"initial ACK failed");
    auto first=binding->begin_view_service();
    check(first && first->request.id==99 && !binding->begin_view_service(),"begin consumed an already active request");
    check(binding->current_view_service()==first && binding->current_view_service()==first,"current query advanced request queue");
    auto wrong=result(100,gui::ServiceStatus::success,"bad");
    check(!binding->stage_view_service_result(EngineModuleView::encode_service_result(wrong)) &&
          binding->current_view_service()==first,"foreign service result consumed request");
    auto right=result(99,gui::ServiceStatus::success,"hello");
    check(binding->stage_view_service_result(EngineModuleView::encode_service_result(right)) &&
          !binding->stage_view_service_result(EngineModuleView::encode_service_result(right)),"duplicate queued result accepted");
    check(binding->current_view_service()==first,"staging consumed request before ordinary tick");
    binding->tick_view();
    check(!binding->current_view_service() && first->request.id==99 && first->request.value=="seed",
          "completed wrapper was not retired or retained request borrowed queue storage");
    check(binding->acknowledge_view(2),"first completion publication ACK failed");
    auto next=binding->begin_view_service();check(next && next->request.id==100,"explicit successor begin lost queued request");
    auto next_result=result(100,gui::ServiceStatus::success,"next");
    check(binding->stage_view_service_result(EngineModuleView::encode_service_result(next_result)),"successor result not staged");
    binding->tick_view();
    check(binding->view()->snapshot().revision==3 && !binding->current_view_service() && !binding->begin_view_service(),
          "host result was duplicated or successor current wrapper not cleared");
}
void per_request_limit_is_normalized_before_dispatch() {
    ViewState bounded;bounded.title="bounded";
    Script script{{call(1,1,replacement(0,{}),ServiceStatus::ok,1),call(2,2,service_request())}, {
        {service_event(1,99,3,"","Text exceeds the byte limit"),
            {call(3,1,replacement(1,bounded),ServiceStatus::ok,2)}}}};
    auto binding=make_binding(script);check(binding->acknowledge_view(1),"initial ACK failed");
    check(binding->begin_view_service()->request.byte_limit==8,"fixture request byte limit changed");
    auto oversized=result(99,gui::ServiceStatus::success,"123456789");
    check(binding->stage_view_service_result(EngineModuleView::encode_service_result(oversized)),"bounded raw result rejected before queue normalization");
    binding->tick_view();
    check(!binding->view()->closed() && binding->view()->snapshot().revision==2 && binding->view()->snapshot().title=="bounded",
          "leaf dispatched pre-normalized staged bytes instead of actual queue-normalized result");
}
void accepted_view_work_failure_is_terminal() {
    auto binding=make_binding(Script{{call(1,1,replacement(0,{}),ServiceStatus::ok,1)}, {}});
    auto view=binding->view();check(binding->acknowledge_view(1),"initial ACK failed");
    auto event=click(view,1);check(binding->stage_view_event(1,event),"fixture event not accepted");
    bool failed=false;try{binding->tick_view();}catch(const std::exception&){failed=true;}
    check(failed && view->closed() && !binding->stage_view_event(1,event) && !binding->acknowledge_view(1),
          "guest trap after accepted work left a retryable live view");
    binding->tick_view();binding->close();binding->close();
}
void consumed_service_failure_is_terminal() {
    auto binding=make_binding(Script{{call(1,1,replacement(0,{}),ServiceStatus::ok,1),call(2,2,service_request())}, {}});
    auto held=binding->begin_view_service();check(held && held->request.id==99,"fixture service missing");
    auto value=result(99,gui::ServiceStatus::success,"hello");const auto payload=EngineModuleView::encode_service_result(value);
    check(binding->stage_view_service_result(payload),"fixture completion not accepted");
    bool failed=false;try{binding->tick_view();}catch(const std::exception&){failed=true;}
    check(failed && binding->view()->closed() && !binding->current_view_service() && !binding->begin_view_service() &&
          !binding->stage_view_service_result(payload) && held->request.id==99,
          "consumed service dispatch failure requeued work or lost retained request value");
}
void provider_only_factory_has_no_view_lane() {
    auto bytes=wasm(Script{});auto binding=make_engine_module_binding(bytes,{},7);
    check(!binding->supports_view() && !binding->view() && !binding->acknowledge_view(1) &&
          !binding->begin_view_service() && !binding->current_view_service(),"provider-only factory acquired binary GUI capability");
    auto hooks=binding->services();
    check(hooks.generation==7 && hooks.discover(provider_query()).status==ServiceStatus::not_found,
          "provider-only default behavior changed");
    const auto a=hooks.sequence(),b=hooks.sequence();check(a && b && *a==1 && *b==2,"host sequence allocator changed");
    binding->tick_view();binding->close();
}
} // namespace
int main() {
    const std::array<std::pair<const char*,void(*)()>,7> cases{{
        {"initialization_and_exact_publication_ack",initialization_and_exact_publication_ack},
        {"providers_view_and_service_share_one_module_allocator",providers_view_and_service_share_one_module_allocator},
        {"begin_current_and_owned_completion",begin_current_and_owned_completion},
        {"per_request_limit_is_normalized_before_dispatch",per_request_limit_is_normalized_before_dispatch},
        {"accepted_view_work_failure_is_terminal",accepted_view_work_failure_is_terminal},
        {"consumed_service_failure_is_terminal",consumed_service_failure_is_terminal},
        {"provider_only_factory_has_no_view_lane",provider_only_factory_has_no_view_lane}
    }};
    try{for(const auto&[name,run]:cases){run();std::cout<<name<<"\n";}}
    catch(const std::exception&error){std::cerr<<error.what()<<"\n";return 1;}
}
