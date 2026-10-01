#include "adapter.hpp"
#include "probe.hpp"
#include "host/contract.hpp"
#include "tests/fixture.hpp"
#include <iostream>

int main(){try{
    foundation::host::Session<foundation::ui::Application,gui::rev::Adapter> session;
    auto& adapter=session.adapter;adapter.show();
    auto sync=[&]{session.tick();adapter.pump();session.tick();fixture::check(adapter.error().empty(),"Native callback failed");};sync();
    fixture::feature(session.application,
        [&](std::string text){gui::rev::Probe::edit_text(adapter,{"entries.editor",1},std::move(text));},
        [&](std::string id){gui::rev::Probe::activate(adapter,{std::move(id),1});},
        [&](std::string id){gui::rev::Probe::select_record(adapter,{"entries.list",1},std::move(id));},sync);
    fixture::parity(session.application.view());
    fixture::unavailable_service(adapter);
    fixture::visual_sizes(session.application,adapter,"rev",sync,[&](const std::string& name){
        const auto image=adapter.capture();fixture::check(image.width()>0&&image.height()>0,"Native capture failed");
        fixture::capture(image.pixels().data(),image.width(),image.height(),name.c_str());
    });
    gui::rev::Probe::select_option(adapter,{"entries.options",1},"heading");sync();
    fixture::check(adapter.service_active(),"Native service not started");
    gui::rev::Probe::complete_prompt(adapter,"New heading");sync();
    fixture::check(fixture::widget(session.application.view(),"entries.heading").state.text=="New heading","Prompt result lost");
    session.application.handle(gui::CloseEvent{});fixture::check(adapter.closed(),"Native close failed");
    std::cout<<"Rev native callbacks, shared extension, declarations, capture, services and close passed\n";
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
