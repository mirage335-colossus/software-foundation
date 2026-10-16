#include "adapter.hpp"
#include <FL/Fl_Secret_Input.H>
#include <iostream>
#include <stdexcept>
#include <cstring>
namespace {
void check(bool value,const char* message){if(!value)throw std::runtime_error(message);}
struct Events {int key=Fl::e_keysym,state=Fl::e_state,length=Fl::e_length;char* text=Fl::e_text;
    ~Events(){Fl::e_keysym=key;Fl::e_state=state;Fl::e_length=length;Fl::e_text=text;}};
struct Clipboard:Fl_Widget {std::string received;Clipboard():Fl_Widget(0,0,0,0){}void draw()override{}
    int handle(int event)override{if(event==FL_PASTE){received.assign(Fl::event_text(),std::size_t(Fl::event_length()));return 1;}return 0;}};
std::vector<unsigned char> pixels(gui::fltk::Adapter& adapter,Fl_Widget& native){
    Fl::flush();adapter.window().make_current();const std::unique_ptr<unsigned char[]> image(fl_read_image(nullptr,native.x()+2,native.y()+2,native.w()-4,native.h()-4));
    check(bool(image),"Native secret input capture unavailable");return {image.get(),image.get()+std::size_t(native.w()-4)*std::size_t(native.h()-4)*3};
}
}
int main(){try{
    gui::Snapshot view;view.client_size={500,280};gui::Widget secret;secret.spec.key={"secret",1};secret.spec.kind=gui::Kind::text;
    secret.spec.text_policy.masked=true;secret.spec.text_policy.submit=gui::SubmitKey::enter;secret.state.bounds={20,20,220,32};secret.state.text="abcde";view.widgets={secret};
    gui::fltk::Adapter* target=nullptr;std::vector<std::string> edits;std::vector<gui::WidgetEvent> input_events;
    gui::fltk::Adapter adapter([&](const gui::Event& event){
        if(const auto* item=std::get_if<gui::WidgetEvent>(&event))input_events.push_back(*item);
        if(const auto* item=std::get_if<gui::WidgetEvent>(&event))if(const auto* edit=std::get_if<gui::EditText>(&item->input)){
        check(target!=nullptr,"Native secret callback ran before construction");edits.push_back(edit->value);view.widgets[0].state.text=edit->value;target->present(view);
    }});target=&adapter;adapter.present(view);adapter.show();adapter.sync();Fl::check();Fl::handle(FL_FOCUS,&adapter.window());
    auto* native=dynamic_cast<Fl_Secret_Input*>(adapter.native_widget(secret.spec.key));check(native&&!dynamic_cast<Fl_Text_Editor*>(native),"Masked text did not use a native secret control");
    check(native->input_type()==FL_SECRET_INPUT&&std::string(native->value())=="abcde","Native masking replaced actual text or lost secret type");
    adapter.focus(std::nullopt);const auto first=pixels(adapter,*native);view.widgets[0].state.text="ZYXWV";adapter.present(view);adapter.sync();
    check(pixels(adapter,*native)==first,"Different same-length secrets rendered different plaintext glyphs");
    view.widgets[0].state.text="a\xc3\xa9\xf0\x9f\x94\x92z";adapter.present(view);adapter.sync();adapter.focus(secret.spec.key);adapter.text_selection(secret.spec.key,{7,1});
    check(native->mark()==7&&native->position()==1&&adapter.text_selection(secret.spec.key)==gui::TextSelection{7,1},"Native secret UTF-8 reverse byte selection changed");
    Events restore;const std::string pasted="paste\xc3\xa9";Fl::e_text=const_cast<char*>(pasted.c_str());Fl::e_length=int(pasted.size());Fl::e_state=0;
    native->handle(FL_PASTE);adapter.sync();check(edits.size()==1&&edits.back()=="a"+pasted+"z","Native masked paste delivered obscured/incorrect value");
    check(adapter.text_selection(secret.spec.key)==gui::TextSelection{1+pasted.size(),1+pasted.size()},"Native masked paste lost its actual byte caret");
    adapter.text_selection(secret.spec.key,{0,view.widgets[0].state.text.size()});Clipboard clipboard;
    Fl::copy("clipboard sentinel",18,1);Fl::e_state=FL_CTRL;Fl::e_keysym='c';Fl::e_text=const_cast<char*>("c");Fl::e_length=1;native->handle(FL_KEYDOWN);Fl::paste(clipboard,1);Fl::check();
    check(clipboard.received=="clipboard sentinel","Native masked copy exported its clear value");
    const auto before=view.widgets[0].state.text;Fl::e_keysym='x';native->handle(FL_KEYDOWN);adapter.sync();check(view.widgets[0].state.text==before,"Native masked cut changed the value");
    view.widgets[0].state.text.clear();adapter.present(view);adapter.sync();Fl::e_keysym='z';native->handle(FL_KEYDOWN);adapter.sync();
    check(std::string(native->value()).empty()&&view.widgets[0].state.text.empty(),"Cleared secret reappeared through native undo");
    // Declared shortcuts own their strokes before native secret undo/export or submission.
    const gui::WidgetKey undo_key{"undo",1},redo_key{"redo",1};
    view.commands={{undo_key,true,secret.spec.key},{redo_key,true,secret.spec.key}};
    view.key_bindings={{gui::ShortcutKey::z,undo_key,true,false,false,secret.spec.key},
        {gui::ShortcutKey::z,redo_key,true,true,false,secret.spec.key},
        {gui::ShortcutKey::y,redo_key,true,false,false,secret.spec.key},
        {gui::ShortcutKey::enter,undo_key,false,false,false,secret.spec.key},
        {gui::ShortcutKey::enter,redo_key,true,false,false,secret.spec.key}};
    adapter.present(view);adapter.sync();adapter.focus(secret.spec.key);
    struct Stroke {int key,state;gui::WidgetKey target;};
    for(const auto& stroke:{Stroke{'z',FL_CTRL,undo_key},Stroke{'z',FL_CTRL|FL_SHIFT,redo_key},
            Stroke{'y',FL_CTRL,redo_key},Stroke{FL_Enter,0,undo_key},Stroke{FL_KP_Enter,FL_CTRL,redo_key}}) {
        const auto count=input_events.size();Fl::e_keysym=stroke.key;Fl::e_state=stroke.state;
        Fl::e_text=const_cast<char*>("");Fl::e_length=0;native->handle(FL_KEYDOWN);adapter.sync();
        check(input_events.size()==count+1&&input_events.back().target==stroke.target,
            "Masked native field swallowed or duplicated a declared shortcut");
        const auto* activation=std::get_if<gui::Activate>(&input_events.back().input);
        check(activation&&activation->source==secret.spec.key&&view.widgets[0].state.text.empty(),
            "Masked shortcut submitted/edited text or lost its initiating field");
    }
    view.commands.clear();view.key_bindings.clear();
    view.widgets[0].state.text="secret";view.widgets[0].spec.key.generation=2;view.widgets[0].spec.text_policy.read_only=true;adapter.present(view);adapter.sync();
    native=dynamic_cast<Fl_Secret_Input*>(adapter.native_widget(view.widgets[0].spec.key));check(native,"New readonly secret control missing");
    Fl::e_state=0;Fl::e_text=const_cast<char*>("no");Fl::e_length=2;native->handle(FL_PASTE);adapter.sync();check(view.widgets[0].state.text=="secret","Readonly masked paste edited text");
    view.widgets[0].spec.key.generation=3;view.widgets[0].spec.text_policy.masked=false;view.widgets[0].spec.text_policy.read_only=false;view.widgets[0].state.text="ordinary";adapter.present(view);adapter.sync();
    check(dynamic_cast<Fl_Text_Editor*>(adapter.native_widget(view.widgets[0].spec.key))!=nullptr,"Fresh ordinary generation retained secret input");
    adapter.close();adapter.sync();check(adapter.error().empty(),"Native secret callback failed");
    std::cout<<"Native obscured glyphs, UTF-8 paste/selection, export suppression, cleared undo and generation replacement passed\n";
}catch(const std::exception& error){std::cerr<<error.what()<<'\n';return 1;}}
