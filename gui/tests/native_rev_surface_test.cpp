#include "host/rev_runner.hpp"
#include "WinEvent.hpp"
#include <iostream>
#include <stdexcept>
namespace fake {
struct Window {std::shared_ptr<gui::rev::NativeSurfaceHooks> hooks;RevSurfaceFacts facts{1000,800,1000,800,1,true,true,true};RevSurfaceContext context;unsigned suspends{},captures{},draws{};bool wrong{},captured{};};
Window* current{};
void event(RevSurfaceEvent value){current->hooks->event(value);}
}
namespace gui::rev {
struct Adapter::Impl {fake::Window state;};
Adapter::Adapter(EventSink sink):RetainedAdapter(std::move(sink)),impl_(std::make_unique<Impl>()){fake::current=&impl_->state;}
Adapter::~Adapter()=default;
void Adapter::present(Snapshot value){RetainedAdapter::present(std::move(value));}
Size Adapter::measure_text(const TextMeasureRequest& value)const{return framebuffer_detail::measure(value);}
bool Adapter::focus(std::optional<WidgetKey> value){return RetainedAdapter::focus(std::move(value));}
bool Adapter::focus_next(bool value){return RetainedAdapter::focus_next(value);}
void Adapter::text_selection(const WidgetKey& key,TextSelection value){RetainedAdapter::text_selection(key,value);}
TextSelection Adapter::text_selection(const WidgetKey& key)const{return RetainedAdapter::text_selection(key);}
void Adapter::scroll(const WidgetKey& key,Point value){RetainedAdapter::scroll(key,value);}
Point Adapter::scroll_offset(const WidgetKey& key)const{return RetainedAdapter::scroll_offset(key);}
bool Adapter::open_popup(const WidgetKey& key){return RetainedAdapter::open_popup(key);}
void Adapter::close_popup(const WidgetKey& key){RetainedAdapter::close_popup(key);}
void Adapter::invalidate(const WidgetKey& key,PixelRect value){RetainedAdapter::invalidate(key,value);}
void Adapter::close(){RetainedAdapter::close();}
void Adapter::show(){}void Adapter::sync(){}bool Adapter::pump(){return !closed();}
const std::string& Adapter::error()const{static const std::string empty;return empty;}
bool Adapter::service_active()const{return false;}bool Adapter::service(ServiceRequest,std::function<void(ServiceResult)>){return false;}
BitmapImage Adapter::capture(){++impl_->state.draws;return BitmapImage(unsigned(impl_->state.facts.render_width)+(impl_->state.wrong?1:0),unsigned(impl_->state.facts.render_height),PixelFormat::rgb24);}
void Adapter::native_surface(std::shared_ptr<NativeSurfaceHooks> value,bool){impl_->state.hooks=std::move(value);}
void Adapter::native_surface_window(std::string,int,int){}
RevSurfaceFacts Adapter::native_surface_facts()const{return impl_->state.facts;}
void Adapter::native_surface_context(const RevSurfaceContext& value){impl_->state.context=value;}
void Adapter::native_surface_suspend(bool){++impl_->state.suspends;impl_->state.context.enabled=false;}
bool Adapter::native_surface_capture(bool value){impl_->state.captured=value;++impl_->state.captures;return true;}
}
namespace H=foundation::host;namespace S=foundation::gui_surface;namespace E=foundation::gui_editor;
unsigned checks{};void check(bool value,const char* why){++checks;if(!value)throw std::runtime_error(why);}
gui::Snapshot view(std::uint64_t revision){gui::Snapshot v;v.revision=revision;v.client_size={800,600};gui::Widget w;w.spec.key={"surface",1};w.spec.kind=gui::Kind::bitmap;w.state.bounds={0,0,800,600};v.widgets.push_back(w);return v;}
struct Fixture {
 gui::FramebufferAdapter canvas;std::vector<S::Input> inputs;std::vector<H::NativeEditorObservation> edits;unsigned revokes{},drawable{},foreground{};
 H::NativeRevSurfacePeer owner;H::NativeSurfacePeer peer;
 Fixture():owner(canvas,{"test",800,600,1},ingress(),H::NativeSurfaceMode::editor_v1),peer(owner.peer()){}
 H::NativeSurfaceIngress ingress(){return {[this](S::Input v){inputs.push_back(std::move(v));return S::AcceptResult{S::Status::ok,{}};},[this](H::NativeEditorObservation v)->std::optional<std::uint64_t>{edits.push_back(std::move(v));return edits.size();},{},[this](S::RevocationReason){++revokes;},[this](std::int64_t,std::int64_t){++drawable;},[this](bool){++foreground;}};}
 H::NativeEditorPresentation publication(std::uint64_t revision=7) {
  H::NativeEditorPresentation p;p.admission=H::NativeEditorAdmission::active;S::Presentation s;s.identity={{"surface",1},revision,3,4,5};s.bounds=s.clip={0,0,800,600};s.keys.fallback=S::Capture::capture;
  S::EditorContext context;context.editable=true;context.revision=1;context.surrounding="ab";context.selection={1,1};context.caret={10,20,1,20};s.editor=context;p.surface=s;p.context=context;
  E::Basis b{9,s.identity,1,"ab",{1,1},false,0};E::EditorPublication pub;pub.basis=b;p.publication=pub;p.passage_basis=b;return p;
 }
 void activate(){check(peer.present(view(7)).snapshot_revision==7,"receipt did not use Snapshot revision");peer.editor(publication());peer.activate();}
};
void validate_observations(const std::vector<H::NativeEditorObservation>& values,E::Basis basis) {
 H::NativeEditorEndpoint endpoint;endpoint.submit=[](E::Packet)->std::optional<std::uint64_t>{return {};};endpoint.revoke=[](E::Revocation)->std::optional<std::uint64_t>{return {};};endpoint.take=[](std::uint64_t)->std::optional<E::EditorCompletion>{return {};};endpoint.resync=[]{};endpoint.terminal={nullptr,[](void*)noexcept{}};
 H::NativeEditorCapture capture(endpoint);E::EditorPublication pub;pub.basis=basis;check(capture.install(pub,basis.identity),"collector initial Basis rejected");
 for(const auto& value:values)check(capture.observe(value).has_value(),"actual peer observation violates Core collector contract");
}
struct LoopSession {
 struct Adapter {bool stopped{};bool closed()const{return stopped;}} adapter;
 H::RunnerState state;unsigned ticks{},shutdowns{},complete_after{3};int exit_after_tick{},exit_during_shutdown{};bool in_pump{},complete_during_shutdown{};
 struct App {LoopSession& owner;void shutdown(){check(!owner.in_pump,"App shutdown entered native callback");++owner.shutdowns;owner.state.close_requested=true;owner.state.exit_code=owner.exit_during_shutdown;owner.state.close_complete=owner.complete_during_shutdown;}} application{*this};
 H::RunnerState runner_state()const{return state;}
 void tick(){++ticks;if(exit_after_tick)state.exit_code=exit_after_tick;if(state.close_requested && ticks>=complete_after)state.close_complete=true;}
};
struct LoopPeer {
 LoopSession& session;bool requested{},stopped{};unsigned pumps{},request_after{};int exit_after_pump{};std::string failure{};
 bool close_requested()const{return requested;}bool closed()const{return stopped;}const std::string& error()const{return failure;}
 bool pump(){session.in_pump=true;++pumps;if(request_after && pumps==request_after)requested=true;if(exit_after_pump)session.state.exit_code=exit_after_pump;session.in_pump=false;return !stopped;}
};
void runner_lifecycle() {
 using Clock=std::chrono::steady_clock;
 auto run=[](LoopSession& session,LoopPeer& peer){auto now=Clock::time_point{};return H::rev_surface_runner_detail::loop(session,peer,[&]{return now;},[&](auto until){now=until+std::chrono::seconds(1);});};
 {LoopSession s;LoopPeer p{s};p.requested=true;check(run(s,p)==0&&s.shutdowns==1&&s.ticks==3&&p.pumps==2&&!p.stopped,"native close did not drain known head with renderer alive");}
 {LoopSession s;LoopPeer p{s};p.requested=true;s.exit_during_shutdown=13;check(run(s,p)==13&&s.shutdowns==1&&s.ticks==0&&p.pumps==0,"synchronous shutdown exit advanced work");}
 {LoopSession s;LoopPeer p{s};p.requested=true;s.complete_during_shutdown=true;check(run(s,p)==0&&s.shutdowns==1&&s.ticks==0&&p.pumps==0,"synchronous shutdown completion advanced work");}
 {LoopSession s;LoopPeer p{s};s.state.exit_code=7;check(run(s,p)==7&&s.ticks==0&&p.pumps==0&&s.shutdowns==0,"entry exit code was ignored");}
 {LoopSession s;LoopPeer p{s};s.exit_after_tick=5;check(run(s,p)==5&&s.ticks==1&&p.pumps==0,"post-tick exit code was ignored");}
 {LoopSession s;LoopPeer p{s};p.exit_after_pump=9;check(run(s,p)==9&&s.ticks==1&&p.pumps==1,"post-pump exit code was ignored");}
 {LoopSession s;LoopPeer p{s};p.requested=true;s.complete_after=100000;check(run(s,p)==1&&!s.state.close_complete&&s.shutdowns==1&&s.ticks<100,"unknown close was falsely completed or unbounded");}
 {LoopSession s;LoopPeer p{s};s.state.close_requested=true;s.complete_after=2;check(run(s,p)==0&&s.shutdowns==1&&s.ticks==2,"App close request did not drain");}
 {LoopSession s;LoopPeer p{s};p.request_after=1;s.complete_after=3;check(run(s,p)==0&&s.shutdowns==1&&s.ticks==3,"native callback close request was not queued to owner");}
 {LoopSession s;LoopPeer p{s};s.state.close_complete=true;check(run(s,p)==0&&!s.ticks&&!s.shutdowns,"already complete state advanced work");}
}
int main(){try {
 runner_lifecycle();
 {
  Fixture f;check(f.canvas.snapshot().revision==0,"stage mutated App canvas");check(fake::current->draws==1,"staging did not use renderer");check(f.peer.ready(),"staged peer not ready");check(f.peer.capabilities.supported==8255,"capability mask");
  f.activate();check(f.canvas.snapshot().revision==7,"App Snapshot not installed");check(f.drawable==1&&f.foreground==1,"actual facts missing");
  check(fake::current->context.caret_x==12&&fake::current->context.caret_y==50,"caret letterbox transform mismatch");
  auto before=f.inputs.size();f.peer.activate();check(f.inputs.size()==before,"same context focus echoed");
  RevSurfaceEvent key;key.kind=RevSurfaceEvent::Kind::key;key.down=true;key.key="x";key.code="KeyX";fake::event(key);check(f.edits.size()==1&&f.inputs.size()==before,"key duplicated into physical ingress");check(f.edits.back().before.value=="ab"&&!f.edits.back().after,"key guessed text");
  RevSurfaceEvent commit;commit.kind=RevSurfaceEvent::Kind::commit;commit.text="X";commit.selection_start=commit.selection_end=1;fake::event(commit);check(f.edits.size()==2&&f.edits.back().after->value=="aXb","actual committed insertion");
  auto paused=f.publication();paused.admission=H::NativeEditorAdmission::paused;paused.context.reset();paused.surface.reset();auto resets=fake::current->suspends;f.peer.editor(paused);check(fake::current->suspends==resets,"pause reset IME");
  commit.text="Y";fake::event(commit);check(f.edits.size()==3&&f.edits.back().before.value=="aXb"&&f.edits.back().after->value=="aXYb","paused continuation lost");
  f.peer.activate();check(f.inputs.size()==before,"paused focus echo");
  auto resumed=f.publication();resumed.draft=f.edits.back().after;resumed.preserve_passage=true;f.peer.editor(resumed);f.peer.activate();check(f.inputs.size()==before+1,"actual resume focus not refreshed");
  key.down=false;fake::event(key);check(f.edits.size()==4,"owned editor up lost");
  RevSurfaceEvent select;select.kind=RevSurfaceEvent::Kind::selection;select.selection_start=0;select.selection_end=2;fake::event(select);check(f.edits.back().authority==E::Authority::range&&f.edits.back().after->selection==S::ByteRange{0,2},"selection authority/readback");
  f.peer.suspend();before=f.edits.size();fake::event(commit);check(f.edits.size()==before,"retired text ingress");f.peer.editor(resumed);key.down=false;fake::event(key);check(f.edits.size()==before,"orphan key up retargeted");
  validate_observations(f.edits,*f.publication().publication->basis);
  f.peer.close();check(!f.peer.ready(),"closed peer ready");
 }
 {
  Fixture f;f.activate();auto key=RevSurfaceEvent{};key.down=true;key.key="z";key.code="KeyZ";fake::event(key);f.peer.suspend();f.peer.editor(f.publication());auto count=f.edits.size();key.down=false;fake::event(key);check(f.edits.size()==count,"retired held up retargeted");
  auto context=f.publication();context.publication.reset();context.admission=H::NativeEditorAdmission::withdrawn;context.context.reset();f.peer.editor(context);count=f.edits.size();RevSurfaceEvent text;text.kind=RevSurfaceEvent::Kind::commit;text.text="bad";fake::event(text);check(f.edits.size()==count,"withdrawn frontend committed");
 }
 {
  Fixture f;f.activate();RevSurfaceEvent begin;begin.kind=RevSurfaceEvent::Kind::preedit_begin;begin.transaction=21;fake::event(begin);
  auto update=begin;update.kind=RevSurfaceEvent::Kind::preedit_update;update.text="\xf0\x9f\x98\x80";update.selection_start=update.selection_end=2;fake::event(update);check(f.edits.back().after->value=="a\xf0\x9f\x98\x80" "b","preedit scalar projection");
  auto cancel=begin;cancel.kind=RevSurfaceEvent::Kind::preedit_cancel;fake::event(cancel);check(f.edits.back().after->value=="ab"&&std::get<E::CompositionData>(f.edits.back().data).text.empty(),"composition cancellation guessed result");
  validate_observations(f.edits,*f.publication().publication->basis);
 }
 {
  Fixture f;f.activate();RevSurfaceEvent mouse;mouse.kind=RevSurfaceEvent::Kind::mouse;mouse.mouse_phase=1;mouse.button=0;mouse.buttons=1;mouse.clicks=1;mouse.x=125;mouse.y=150;fake::event(mouse);
  const auto input=std::get<S::MouseTransition>(f.inputs.back());check(input.x==100&&input.y==100&&input.capture_token&&fake::current->captured,"mouse inverse transform/capture");
  mouse.mouse_phase=2;mouse.buttons=0;mouse.clicks=0;fake::event(mouse);check(fake::current->captured,"native release ran inside input callback");
  mouse.mouse_phase=1;mouse.buttons=1;mouse.clicks=1;fake::event(mouse);const auto successor=std::get<S::MouseTransition>(f.inputs.back()).capture_token;
  f.owner.pump();check(fake::current->captured&&successor!=input.capture_token,"old deferred release cancelled successor gesture");
  mouse.mouse_phase=2;mouse.buttons=0;mouse.clicks=0;fake::event(mouse);f.owner.pump();check(!fake::current->captured,"mouse capture not released on owner turn");
  fake::current->facts.width=0;fake::current->facts.active=false;fake::current->hooks->lifecycle(fake::current->facts,true);check(f.revokes&&f.drawable==2,"actual resize did not retire old transform");
 }
 {
  Fixture f;f.activate();fake::current->wrong=true;bool rejected=false;try{f.peer.present(view(42));}catch(const std::runtime_error&){rejected=true;}check(rejected,"wrong actual drawable acknowledged");
 }
 {
  Fixture f;f.activate();bool completed=false;gui::ServiceRequest request;request.id=1;request.kind=gui::ServiceKind::prompt;request.title="test";request.value="";request.byte_limit=64;
  check(f.canvas.service(request,[&](gui::ServiceResult value){completed=value.status==gui::ServiceStatus::success&&value.value=="actual";}),"generic service rejected");
  f.owner.pump();auto count=f.edits.size();
  RevSurfaceEvent composing;composing.kind=RevSurfaceEvent::Kind::preedit_begin;composing.transaction=5;fake::event(composing);
  composing.kind=RevSurfaceEvent::Kind::key;composing.down=true;composing.key="Enter";fake::event(composing);check(f.canvas.prompt().has_value()&&!completed,"candidate Enter submitted prompt");
  composing.kind=RevSurfaceEvent::Kind::preedit_cancel;composing.transaction=5;fake::event(composing);
  RevSurfaceEvent value;value.kind=RevSurfaceEvent::Kind::commit;value.text="actual";fake::event(value);check(f.edits.size()==count&&f.canvas.prompt()->value=="actual","prompt did not reuse generic text path");
  value={};value.kind=RevSurfaceEvent::Kind::key;value.down=true;value.key="Enter";fake::event(value);f.owner.pump();check(completed&&!f.canvas.prompt(),"prompt completion failed");
  value.kind=RevSurfaceEvent::Kind::commit;value.text="late";fake::event(value);check(f.edits.size()==count,"prompt close restored retired editor authority");
 }
 {
  Fixture f;f.activate();RevSurfaceEvent close;close.kind=RevSurfaceEvent::Kind::close;fake::event(close);
  check(f.owner.close_requested()&&f.peer.ready()&&!f.canvas.closed(),"native close destroyed renderer before ordinary drain");
  auto size=f.edits.size();RevSurfaceEvent value;value.kind=RevSurfaceEvent::Kind::commit;value.text="late";fake::event(value);check(f.edits.size()==size,"native closing admitted new editor input");
 }
 std::cout<<"Rev actual peer with explicit fake window transport: "<<checks<<" assertions, no OS/GL runtime\n";return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
