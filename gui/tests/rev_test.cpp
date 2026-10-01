#include "adapter.hpp"
#include "probe.hpp"
#include "host/contract.hpp"
#include "tests/fixture.hpp"
#include <iostream>
#include <cmath>

int main(){try{
    foundation::host::Session<foundation::ui::Application,gui::rev::Adapter> session;
    auto& adapter=session.adapter;adapter.show();
    auto sync=[&]{session.tick();adapter.pump();session.tick();fixture::check(adapter.error().empty(),"Native callback failed");};sync();
    // Native scale belongs to the host. Verify physical storage and logical
    // widget rectangles before the shared unit-scale comparison scenarios.
    const auto native_scale=session.application.view().display_scale;
    fixture::check(std::isfinite(native_scale)&&native_scale>0,"Invalid native display scale");
    {
        const auto& view=session.application.view();
        const auto image=adapter.capture();
        fixture::check(image.width()==unsigned(std::ceil(view.client_size.width*native_scale))&&
            image.height()==unsigned(std::ceil(view.client_size.height*native_scale)),
            "Native physical capture differs from scaled logical viewport");
        for(const auto& widget:view.widgets) {
            if(!widget.state.visible)continue;
            const auto actual=gui::rev::Probe::bounds(adapter,widget.spec.key);
            const auto expected=widget.state.bounds;
            fixture::check(std::abs(actual.x-expected.x)<0.01&&std::abs(actual.y-expected.y)<0.01&&
                std::abs(actual.width-expected.width)<0.01&&std::abs(actual.height-expected.height)<0.01,
                "Native scale changed logical widget geometry");
        }
        std::cout<<"Rev native scale "<<native_scale<<" logical "<<view.client_size.width<<'x'
            <<view.client_size.height<<" physical "<<image.width()<<'x'<<image.height()<<'\n';
    }
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
