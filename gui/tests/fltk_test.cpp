#include "adapter.hpp"
#include "host/contract.hpp"
#include "tests/fixture.hpp"
#include <iostream>

int main(){try{
    foundation::host::Session<foundation::ui::Application,gui::fltk::Adapter> session;
    auto& adapter=session.adapter;adapter.show();
    auto sync=[&]{session.tick();Fl::check();Fl::flush();};sync();
    fixture::feature(session.application,
        [&](std::string text){auto* editor=dynamic_cast<Fl_Text_Editor*>(adapter.native_widget({"entries.editor",1}));fixture::check(editor,"Missing native editor");editor->buffer()->text(text.c_str());editor->do_callback();},
        [&](std::string id){auto* button=dynamic_cast<Fl_Button*>(adapter.native_widget({id,1}));if(!button||!button->active())throw std::runtime_error("Missing active native button: "+id+"; shared enabled="+std::to_string(fixture::widget(session.application.view(),id).state.enabled));button->do_callback();},
        [&](std::string){fixture::check(adapter.focus(gui::WidgetKey{"entries.list",1}),"Native list focus failed");const auto old=Fl::e_keysym;Fl::e_keysym=FL_Down;fixture::check(adapter.native_widget({"entries.list",1})->handle(FL_KEYDOWN)==1,"Native list key rejected");Fl::e_keysym=old;},sync);
    adapter.window().size(800,640);sync();
    fixture::parity(session.application.view());
    fixture::unavailable_service(adapter);
    adapter.window().make_current();
    const std::unique_ptr<unsigned char[]> image(fl_read_image(nullptr,0,0,adapter.window().w(),adapter.window().h()));
    fixture::check(bool(image),"Native capture failed");
    fixture::capture(image.get(),unsigned(adapter.window().w()),unsigned(adapter.window().h()),"fltk");
    adapter.policy().send(gui::WidgetEvent{{"entries.options",1},gui::ChooseOption{"heading"}});sync();
    fixture::check(adapter.service_active(),"Native service not started");
    session.application.handle(gui::CloseEvent{});sync();
    fixture::check(!adapter.window().shown()&&!adapter.service_active(),"Native close did not release service/window");
    fixture::check(adapter.error().empty(),"Native callback failed");
    std::cout<<"FLTK real controls, shared extension, declarations, capture and close passed\n";
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
