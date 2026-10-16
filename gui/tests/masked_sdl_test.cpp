#include <SDL.h>
#include <cstring>
#include <new>
#include <stdexcept>
#include <string>

namespace {
std::string clipboard_value="clipboard sentinel";
unsigned clipboard_reads=0,clipboard_writes=0;
int fixture_set_clipboard(const char* value) {
    ++clipboard_writes;clipboard_value=value;return 0;
}
char* fixture_get_clipboard() {
    ++clipboard_reads;
    auto* value=static_cast<char*>(SDL_malloc(clipboard_value.size()+1));
    if(!value)throw std::bad_alloc();
    std::memcpy(value,clipboard_value.c_str(),clipboard_value.size()+1);return value;
}
}
// Exercise the actual generated runner helper without an OS clipboard or display.
#define SDL_SetClipboardText fixture_set_clipboard
#define SDL_GetClipboardText fixture_get_clipboard
#include "sdl_runner.hpp"
#undef SDL_GetClipboardText
#undef SDL_SetClipboardText

namespace {
void check(bool value,const char* message) {if(!value)throw std::runtime_error(message);}
}
int main(int,char**) {try {
    gui::Snapshot view;view.client_size={320,120};gui::Widget field;
    field.spec.key={"field",1};field.spec.kind=gui::Kind::text;field.spec.text_policy.masked=true;
    field.state.bounds={10,10,200,32};field.state.text="A\xc3\xa9\xf0\x9f\x94\x92Z";view.widgets={field};
    gui::FramebufferAdapter* target=nullptr;std::vector<std::string> edits;
    gui::FramebufferAdapter adapter([&](const gui::Event& event) {
        if(const auto* item=std::get_if<gui::WidgetEvent>(&event))if(const auto* edit=std::get_if<gui::EditText>(&item->input)) {
            edits.push_back(edit->value);view.widgets[0].state.text=edit->value;target->present(view);
        }
    });target=&adapter;adapter.present(view);adapter.focus(field.spec.key);adapter.text_selection(field.spec.key,{1,7});
    clipboard(adapter,SDLK_c);clipboard(adapter,SDLK_x);
    check(clipboard_writes==0&&clipboard_value=="clipboard sentinel"&&clipboard_reads==0,
        "SDL masked copy/cut accessed or replaced the clipboard");
    check(edits.empty()&&adapter.snapshot().widgets[0].state.text==field.state.text&&
        adapter.text_selection(field.spec.key)==gui::TextSelection{1,7},"SDL masked cut changed text or selection");
    clipboard_value="paste\xc3\xa9";clipboard(adapter,SDLK_v);
    check(clipboard_reads==1&&clipboard_writes==0&&edits.size()==1&&edits.back()=="A"+clipboard_value+"Z",
        "SDL masked paste was blocked or lost source UTF-8 byte selection");
    view.widgets[0].spec.key.generation=2;view.widgets[0].spec.text_policy.masked=false;
    adapter.present(view);adapter.focus(view.widgets[0].spec.key);
    adapter.text_selection(view.widgets[0].spec.key,{0,view.widgets[0].state.text.size()});
    const auto ordinary=view.widgets[0].state.text;clipboard(adapter,SDLK_c);
    check(clipboard_writes==1&&clipboard_value==ordinary&&edits.size()==1,"Ordinary SDL copy behavior changed");
    clipboard(adapter,SDLK_x);
    check(clipboard_writes==2&&clipboard_value==ordinary&&edits.size()==2&&edits.back().empty(),
        "Ordinary SDL cut behavior changed");
    std::cout<<"SDL masked copy/cut cannot export text; paste and ordinary clipboard behavior remain available\n";
    return 0;
}catch(const std::exception& failure){std::cerr<<failure.what()<<'\n';return 1;}}
