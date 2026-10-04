#include "host/framebuffer.hpp"
#include <iostream>
void check(bool value,const char* message){if(!value)throw std::runtime_error(message);}
int main(){try{
    std::vector<gui::Event> events;
    gui::FramebufferAdapter adapter([&](const gui::Event& event){events.push_back(event);});
    gui::Snapshot view;view.client_size={200,120};
    gui::Widget action;action.spec.key={"test.action",1};action.spec.kind=gui::Kind::button;
    action.state.label="Run";action.state.bounds={5,5,80,30};view.widgets.push_back(action);
    gui::Widget menu;menu.spec.key={"test.menu",1};menu.spec.kind=gui::Kind::menu;
    menu.state.label="Options";menu.state.bounds={5,45,80,30};menu.state.options={{"first","First","",true},{"disabled","Disabled","",false},{"second","Second","",true}};view.widgets.push_back(menu);
    adapter.present(view);foundation::host::Bezel keys(3);
    check(keys.labels(adapter)==std::vector<std::string>{"Previous","Next","Run"},"Initial projected labels differ");
    check(keys.activate(adapter,2)&&keys.labels(adapter)[2]=="First","Next action not selected");
    keys.activate(adapter,2);check(keys.labels(adapter)[2]=="Second","Disabled action was projected");
    keys.activate(adapter,3);check(std::get<gui::ChooseOption>(std::get<gui::WidgetEvent>(events.back()).input).id=="second","Wrong declared option dispatched");
    adapter.open_popup({"test.menu",1});check(keys.labels(adapter)[2]=="Choose","Popup did not own bezel keys");
    const auto popup_before=events.size();keys.activate(adapter,3);check(events.size()==popup_before+1&&std::holds_alternative<gui::ChooseOption>(std::get<gui::WidgetEvent>(events.back()).input),"Popup key dispatched background action");
    view.widgets[1].state.enabled=false;adapter.present(view);check(keys.labels(adapter)[2]=="Run","Disabled target remained selected");
    const auto before=events.size();keys.activate(adapter,3);check(events.size()==before+1&&std::holds_alternative<gui::Activate>(std::get<gui::WidgetEvent>(events.back()).input),"Button did not dispatch through shared policy");
    bool cancelled=false;adapter.service({7,gui::ServiceKind::prompt,"Value","",10},[&](gui::ServiceResult result){cancelled=result.status==gui::ServiceStatus::cancelled;});
    check(keys.labels(adapter)==std::vector<std::string>{"Cancel","Accept",""},"Prompt exposes background actions");
    check(!keys.activate(adapter,3)&&!cancelled,"Inactive modal key dispatched");keys.activate(adapter,1);check(cancelled,"Prompt cancel missing");
    foundation::host::Bezel five(5);check(five.labels(adapter).size()==5,"Five-key projection absent");
    adapter.close();check(!five.activate(adapter,3)&&five.labels(adapter)==std::vector<std::string>(5),"Closed adapter accepted bezel input");
    bool rejected=false;try{foundation::host::Bezel invalid(4);}catch(const std::invalid_argument&){rejected=true;}check(rejected,"Unsupported key count accepted");
    std::cout<<"Three/five keys project declared eligible actions, modality and close correctly\n";
}catch(const std::exception& error){std::cerr<<error.what()<<'\n';return 1;}}
