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
    fixture::visual_sizes(session.application,adapter,"fltk",[&]{
        const auto size=session.application.view().client_size;
        adapter.window().size(int(size.width),int(size.height));sync();
    },[&](const std::string& name){
        Fl::flush();
        fixture::check(Fl::focus()==nullptr,"Native focus was not cleared");
        adapter.window().make_current();
        const std::unique_ptr<unsigned char[]> image(fl_read_image(nullptr,0,0,adapter.window().w(),adapter.window().h()));
        fixture::check(bool(image),"Native capture failed");
        fixture::capture(image.get(),unsigned(adapter.window().w()),unsigned(adapter.window().h()),name.c_str());
    });
    adapter.policy().send(gui::WidgetEvent{{"entries.options",1},gui::ChooseOption{"heading"}});sync();
    fixture::check(adapter.service_active(),"Native service not started");
    session.application.handle(gui::CloseEvent{});sync();
    fixture::check(!adapter.window().shown()&&!adapter.service_active(),"Native close did not release service/window");
    fixture::check(adapter.error().empty(),"Native callback failed");
    // Generic kind coverage protects the maintained flat-control adapter patch.
    unsigned toggles=0;
    gui::fltk::Adapter generic([&](const gui::Event& event){
        if(const auto* widget=std::get_if<gui::WidgetEvent>(&event))
            if(const auto* value=std::get_if<gui::SetChecked>(&widget->input))
                if(value->value)++toggles;
    });
    gui::Snapshot declaration;declaration.client_size={320,120};
    gui::Widget toggle;toggle.spec.key.id="fixture.toggle";toggle.spec.kind=gui::Kind::toggle;
    toggle.state.label="Enable option";toggle.state.bounds={16,16,288,32};
    declaration.widgets.push_back(toggle);generic.present(declaration);generic.show();generic.sync();Fl::check();
    auto* native_toggle=dynamic_cast<Fl_Check_Button*>(generic.native_widget(toggle.spec.key));
    fixture::check(native_toggle,"Missing generic native toggle");
    native_toggle->value(1);native_toggle->do_callback();
    fixture::check(toggles==1,"Flat toggle changed native callback meaning");
    fixture::check(generic.focus(toggle.spec.key),"Generic toggle focus failed");
    generic.focus(std::nullopt);fixture::check(Fl::focus()==nullptr,"Generic clear focus failed");
    generic.close();
    std::cout<<"FLTK real controls, shared extension, declarations, capture and close passed\n";
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
