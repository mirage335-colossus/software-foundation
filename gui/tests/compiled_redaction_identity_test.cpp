// Maintained shared GUI boundary regression for compiled source redaction.
// Synthetic snapshots exercise resumable privacy behavior used by rich web and
// portable C/C++/Rust applications through the generic MemoryAdapter contract;
// this does not execute either application or qualify its runtime.
#include "shared/engine_region_composition.hpp"
#include <gui/memory_adapter.hpp>
#include <iostream>
#include <stdexcept>
using foundation::ui::EngineRegionComposition;
namespace {
unsigned checks=0;
void check(bool v,const char* why){++checks;if(!v)throw std::runtime_error(why);}
template<class F> void reused(F f,const char* expected){bool caught=false;try{f();}catch(const std::invalid_argument& e){if(std::string_view(e.what())!=expected)throw std::runtime_error(std::string("Expected ")+expected+"; observed "+e.what());caught=true;}check(caught,expected);}
gui::Snapshot compiled(){
 gui::Snapshot s;s.revision=1;s.title="Lifetime fixture";s.client_size={1000,600};
 s.pages.push_back({"private.page","PRIVATE_PAGE"});s.active_page="private.page";s.page_bar={0,0,200,20};
 gui::Widget group;group.spec.key={"compiled.group",7};group.spec.kind=gui::Kind::group;group.spec.page="private.page";
 group.state.bounds={0,20,200,580};group.state.content_size={200,580};group.state.content_clip=gui::Rect{0,0,200,580};s.widgets.push_back(group);
 gui::Widget text;text.spec.key={"compiled.text",4};text.spec.kind=gui::Kind::text;text.spec.parent=group.spec.key.id;text.spec.page=group.spec.page;
 text.state.bounds={0,20,180,30};text.state.text="PRIVATE_TEXT";text.state.label="PRIVATE_LABEL";text.state.help="PRIVATE_HELP";text.state.accessible_name="PRIVATE_ACCESS";text.state.placeholder="PRIVATE_PLACEHOLDER";text.state.display_text="PRIVATE_DISPLAY";
 text.state.bitmap={"PRIVATE_UNUSED",1,gui::solid_bitmap(1,2,3)};s.widgets.push_back(text);
 gui::Widget choice;choice.spec.key={"compiled.choice",2};choice.spec.kind=gui::Kind::choice;choice.spec.parent=group.spec.key.id;choice.spec.page=group.spec.page;
 choice.state.bounds={0,60,180,30};choice.state.options.push_back({"private.option","PRIVATE_OPTION","PRIVATE_VALUE"});choice.state.selected="private.option";s.widgets.push_back(choice);
 gui::Widget list;list.spec.key={"compiled.list",1};list.spec.kind=gui::Kind::list;list.spec.parent=group.spec.key.id;list.spec.page=group.spec.page;
 list.state.bounds={0,100,180,100};gui::Record record;record.id="private.record";record.accessible_text="PRIVATE_RECORD";record.cells.push_back({"PRIVATE_CELL",{0,0,100,20},{},gui::TextWrap::none});list.state.records.push_back(record);s.widgets.push_back(list);
 s.commands.push_back({{"compiled.command",5},true,group.spec.key});gui::KeyBinding key;key.target={"compiled.command",5};key.focus=text.spec.key;s.key_bindings.push_back(key);s.modal_root=group.spec.key;
 gui::validate_snapshot(s);return s;
}
gui::Widget frame(std::uint64_t generation){gui::Widget w;w.spec.key={"engine.frame",generation};w.spec.kind=gui::Kind::bitmap;w.state.bounds={200,0,800,600};w.state.bitmap={"real.fixture.frame",generation,gui::solid_bitmap(10,20,30)};return w;}
gui::Snapshot compose(const EngineRegionComposition& region,const gui::Snapshot& current,std::uint64_t generation,std::uint64_t revision){auto f=frame(generation);auto s=region.compose(current,&f);s.revision=revision;return s;}
void safe(const gui::Snapshot& s){
 check(!gui::find_widget(s,{"engine.frame",1})&&!gui::find_widget(s,{"engine.frame",2}),"Retired rich frame survived redaction");
 check(s.widgets.size()==4&&s.commands.size()==1&&!s.commands[0].enabled,"Compiled declarations or disabled command lost");
 check(!s.active_page&&!s.modal_root&&s.key_bindings.empty(),"Redaction retained input authority");
 for(const auto& p:s.pages)check(p.label.empty()&&!p.visible&&!p.enabled,"Redaction leaked page content");
 for(const auto& w:s.widgets){const auto& t=w.state;
  check(!t.visible&&!t.enabled&&t.label.empty()&&t.text.empty()&&t.help.empty()&&t.accessible_name.empty()&&t.placeholder.empty()&&t.display_text.empty()&&!t.selected&&t.options.empty()&&t.actions.empty()&&t.records.empty()&&t.bitmap.source_id.empty()&&!t.bitmap.revision,"Redaction leaked compiled state or paint callable");
 }
}
}
int main(){try{
 auto source=compiled();EngineRegionComposition region(source,{200,0,800,600});gui::Snapshot current;current.revision=1;
 auto visible=compose(region,current,1,1);
 {gui::MemoryAdapter old;auto original=visible;original.commands.clear();original.key_bindings.clear();old.present(original);auto erased=original;EngineRegionComposition::clear_content(erased);erased.revision=2;old.present(erased);
  auto original_rearm=compose(region,erased,2,3);original_rearm.commands.clear();original_rearm.key_bindings.clear();
  reused([&]{old.present(original_rearm);},"Widget generation was reused");}
 unsigned events=0;gui::MemoryAdapter adapter([&](gui::Event){++events;});adapter.present(visible);
 check(adapter.focus({gui::WidgetKey{"compiled.text",4}}),"Initial compiled focus missing");
 auto masked=visible;EngineRegionComposition::redact_content(masked);masked.revision=2;gui::validate_snapshot(masked);safe(masked);adapter.present(masked);
 check(!adapter.focused(),"Redaction retained focus");
 check(adapter.send(gui::WidgetEvent{{"compiled.text",4},gui::EditText{"AFTER","PRIVATE_TEXT"}})==gui::Delivery::ignored&&!events,"Redaction admitted compiled edit");
 check(adapter.send(gui::WidgetEvent{{"compiled.command",5},gui::Activate{gui::WidgetKey{"compiled.text",4}}})==gui::Delivery::ignored&&!events,"Redaction admitted command");
 auto restored=compose(region,masked,2,3);adapter.present(restored);
 check(adapter.snapshot().widgets.size()==5&&gui::find_widget(adapter.snapshot(),{"compiled.text",4})->state.text=="PRIVATE_TEXT","Rearm lost original source keys/content");
 check(adapter.send(gui::WidgetEvent{{"compiled.text",3},gui::EditText{"BAD","PRIVATE_TEXT"}})==gui::Delivery::ignored&&!events,"Stale source key was accepted");
 check(adapter.send(gui::WidgetEvent{{"engine.frame",1},gui::PointerInput{}})==gui::Delivery::ignored&&!events,"Retired rich frame key was accepted");
 check(adapter.send(gui::WidgetEvent{{"compiled.text",4},gui::EditText{"AFTER","PRIVATE_TEXT"}})==gui::Delivery::delivered&&events==1,"Rearmed source key no longer routes ordinary events");
 for(unsigned cycle=0;cycle<2;++cycle){auto next=adapter.snapshot();EngineRegionComposition::redact_content(next);next.revision+=1;adapter.present(next);safe(next);adapter.present(compose(region,next,cycle+3,next.revision+1));}
 auto before_removal=adapter.snapshot();auto removed=before_removal;
 std::erase_if(removed.widgets,[](const auto& w){return w.spec.key.id=="compiled.text";});removed.key_bindings.clear();++removed.revision;adapter.present(removed);
 auto reused_source=before_removal;reused_source.revision=removed.revision+1;
 reused([&]{adapter.present(reused_source);},"Widget generation was reused");
 for(auto& w:reused_source.widgets)if(w.spec.key.id=="compiled.text")w.spec.key.generation=5;
 for(auto& binding:reused_source.key_bindings)if(binding.focus&&binding.focus->id=="compiled.text")binding.focus->generation=5;
 adapter.present(reused_source);
 check(adapter.send(gui::WidgetEvent{{"compiled.text",4},gui::EditText{"BAD","PRIVATE_TEXT"}})==gui::Delivery::ignored&&events==1,"Genuinely retired compiled source key was accepted");
 check(adapter.send(gui::WidgetEvent{{"compiled.text",5},gui::EditText{"NEW","PRIVATE_TEXT"}})==gui::Delivery::delivered&&events==2,"Fresh source generation did not route");
 // A typed binary source may also carry a compiled bitmap. Exercise the
 // generic redaction operation on its actual GUI representation without
 // claiming the separate binary decoding/admission boundary.
 {auto bitmap_scene=source;gui::Widget thumbnail;thumbnail.spec.key={"compiled.thumbnail",1};thumbnail.spec.kind=gui::Kind::bitmap;
  thumbnail.spec.parent="compiled.group";thumbnail.spec.page="private.page";thumbnail.state.bounds={0,220,100,60};
  unsigned paints=0;thumbnail.state.bitmap={"PRIVATE_BITMAP",1,gui::BitmapSource([&](const gui::BitmapRequest&,const gui::BitmapSink&){++paints;})};thumbnail.state.actions.push_back({"private.action","PRIVATE_ACTION",""});bitmap_scene.widgets.push_back(thumbnail);
  gui::MemoryAdapter bitmap_adapter;bitmap_adapter.present(bitmap_scene);auto hidden=bitmap_scene;EngineRegionComposition::redact_content(hidden);++hidden.revision;bitmap_adapter.present(hidden);
  const auto* w=gui::find_widget(hidden,{"compiled.thumbnail",1});check(w&&w->state.bitmap.source_id.empty()&&!w->state.bitmap.revision&&w->state.actions.empty()&&!w->state.visible&&!w->state.enabled,"Compiled bitmap callback/action survived redaction");
  const auto before_paint=paints;w->state.bitmap.source.paint(gui::full_bitmap_request(1,1),[](unsigned,unsigned,gui::PixelBlock){});check(paints==before_paint,"Redacted compiled bitmap invoked retained callable");
  bitmap_scene.revision=hidden.revision+1;bitmap_adapter.present(bitmap_scene);check(gui::find_widget(bitmap_adapter.snapshot(),{"compiled.thumbnail",1})->state.bitmap.source_id=="PRIVATE_BITMAP","Compiled bitmap lifetime was retired by suspension");}
 auto terminal=adapter.snapshot();EngineRegionComposition::clear_content(terminal);++terminal.revision;gui::validate_snapshot(terminal);adapter.present(terminal);
 check(terminal.widgets.empty()&&terminal.commands.empty()&&terminal.key_bindings.empty()&&!terminal.modal_root,"Terminal erasure retained declarations");
 reused([&]{adapter.present(compose(region,terminal,9,terminal.revision+1));},"Command generation was reused");
 std::cout<<"passed "<<checks<<" checks; actual MemoryAdapter redaction/rearm and stale identity contracts\n";return 0;
}catch(const std::exception& e){std::cerr<<"after "<<checks<<" checks: "<<e.what()<<'\n';return 1;}}
