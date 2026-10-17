// SPDX-License-Identifier: CC0-1.0
#include "host/native_framebuffer_surface_peer.hpp"
#include <gui/retained_adapter.hpp>
#include <algorithm>
#include <array>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <iterator>
#include <stdexcept>
#include <string>
#include <thread>
#ifdef __linux__
#include <csignal>
#include <sys/resource.h>
#endif

namespace {
namespace H=foundation::host;
namespace S=foundation::gui_surface;
std::size_t checks{};
void check(bool value,const char* why) { ++checks; if (!value) throw std::runtime_error(why); }
template<class F> void rejects(F&& action,const char* why) {
    bool rejected=false;
    try { action(); } catch (const std::exception&) { rejected=true; }
    check(rejected,why);
}
gui::Snapshot bitmap(std::uint64_t revision=101) {
    gui::Snapshot view; view.revision=revision; view.client_size={2,1};
    gui::Widget widget; widget.spec.key={"image",1}; widget.spec.kind=gui::Kind::bitmap;
    widget.state.bounds={0,0,2,1}; widget.state.enabled=false;
    widget.state.bitmap.source_id="owned-image"; widget.state.bitmap.revision=1;
    widget.state.bitmap.source=gui::BitmapSource([](const gui::BitmapRequest& request,const gui::BitmapSink& sink) {
        if (request.width!=2 || request.height!=1 || request.format!=gui::PixelFormat::rgb24)
            throw std::logic_error("Unexpected actual bitmap request");
        const std::array<std::uint8_t,6> pixels{255,0,0,0,255,0};
        sink(0,0,{2,1,6,gui::PixelFormat::rgb24,pixels});
    });
    view.widgets.push_back(std::move(widget)); return view;
}
H::NativeSurfaceWindow window() { return {"Read-only framebuffer",2,1,1}; }
H::NativeSurfacePeer peer(gui::FramebufferAdapter& adapter,H::NativeFramebufferOutput output,H::NativeSurfaceIngress ingress={}) {
    return H::prepare_native_framebuffer_surface_peer(adapter,window(),std::move(ingress),std::move(output));
}
void actual_pixels_and_revisions() {
    gui::FramebufferAdapter adapter;
    std::vector<gui::Frame> frames;
    std::vector<std::uint64_t> revisions;
    unsigned ready_calls{},ingress{},activity{};
    std::int64_t width{},height{}; bool foreground{};
    H::NativeFramebufferOutput output{
        [&] { ++ready_calls; return true; },
        [&](const gui::Frame& frame,std::uint64_t revision) { frames.push_back(frame); revisions.push_back(revision); return H::NativeRenderReceipt{revision}; },{}};
    H::NativeSurfaceIngress unused;
    unused.legacy=[&](gui::Event) { ++ingress; };
    unused.drawable_pixels=[&](std::int64_t w,std::int64_t h) { width=w; height=h; };
    unused.foreground=[&](bool value) { foreground=value; ++activity; };
    auto surface=peer(adapter,std::move(output),std::move(unused));
    check(ready_calls==1 && surface.ready(),"Output was not prepared before application publication");
    check(activity==0,"Output activity reached an unarmed application");
    surface.activate(); check(activity==1 && foreground && width==2 && height==1,"Actual configured canvas/activity was not available before first App frame");
    check(surface.capabilities.supported==0 && surface.capabilities.mouse_input_version==0 && !surface.editor,"Bare framebuffer advertised physical/editor support");
    const auto first=surface.present(bitmap());
    check(first.snapshot_revision==101 && adapter.snapshot().revision==101,"Receipt did not join installed snapshot");
    check(frames.size()==1 && frames.front().width==2 && frames.front().height==1 && frames.front().stride_bytes==6,"Actual FramebufferAdapter did not render complete pixels");
    const std::vector<std::uint8_t> expected{255,0,0,0,255,0};
    check(*frames.front().pixels==expected,"Snapshot bitmap pixels did not reach the output");
    const auto second=surface.present(bitmap(102));
    check(second.snapshot_revision==102 && revisions==std::vector<std::uint64_t>{101,102},"Identical pixels lost the new Snapshot revision receipt");
    check(frames[1].revision==frames[0].revision && frames[1].pixels==frames[0].pixels,"Fixture did not preserve the pixel revision independently");
    check(ingress==0,"View-only peer fabricated ingress");
    surface.suspend(); check(surface.ready(),"Context suspension closed the view-only renderer");
    check(surface.present(bitmap(103)).snapshot_revision==103,"Context suspension blocked fresh output");
    surface.close(); check(!surface.ready(),"Closed peer stayed ready");
    rejects([&] { (void)surface.present(bitmap(104)); },"Closed peer presented again");
}
void output_receipts_and_failures() {
    for (unsigned mode=0;mode<3;++mode) {
        gui::FramebufferAdapter adapter; unsigned calls{};
        auto surface=peer(adapter,{[] { return true; },[&](const gui::Frame&,std::uint64_t revision) {
            ++calls;
            if (mode==2) throw std::runtime_error("Actual output failure");
            return H::NativeRenderReceipt{mode==0?0:revision-1};
        },{}});
        rejects([&] { (void)surface.present(bitmap()); },"Queued/wrong/failed output acquired a receipt");
        check(calls==1 && !surface.ready(),"Failed output did not fail closed");
        rejects([&] { (void)surface.present(bitmap(102)); },"Failed output was replayed");
        check(calls==1,"Failed output callback was invoked again");
    }
    gui::FramebufferAdapter adapter; unsigned calls{};
    auto surface=peer(adapter,{[] { return true; },[&](const gui::Frame&,std::uint64_t revision) { ++calls; return H::NativeRenderReceipt{revision}; },{}});
    rejects([&] { (void)surface.present(bitmap(0)); },"Zero Snapshot revision acquired a receipt");
    check(calls==0 && adapter.snapshot().revision==0,"Invalid Snapshot entered rendering/output");
    auto mismatch=bitmap(1); mismatch.client_size={3,1};
    rejects([&] { (void)surface.present(mismatch); },"Populated scene with a different canvas acquired an output receipt");
    check(calls==0 && adapter.snapshot().revision==0,"Populated canvas mismatch entered output");
}
void actual_blank_canvas(const std::filesystem::path& directory) {
    gui::FramebufferAdapter adapter;
    gui::Frame rendered; unsigned outputs{};
    const auto path=directory/"blank-actual-canvas.ppm";
    auto output=H::native_framebuffer_ppm_output(path);
    auto surface=H::prepare_native_framebuffer_surface_peer(adapter,{"Configured output",800,600,1},{},{
        output.ready,[&](const gui::Frame& frame,std::uint64_t revision) {
            rendered=frame; ++outputs; return output.present(frame,revision);
        },output.suspend});
    gui::Snapshot empty; empty.revision=601; empty.title="Safe blank"; empty.palette.background={17,18,19};
    check(empty.client_size.width==640 && empty.client_size.height==480,"Fixture lost default empty Snapshot geometry");
    check(surface.present(empty).snapshot_revision==601 && outputs==1,"Empty initial Snapshot did not acquire its actual output receipt");
    const auto& installed=adapter.snapshot();
    check(installed.revision==601 && installed.title=="Safe blank" && installed.widgets.empty()
        && installed.client_size.width==800 && installed.client_size.height==600,
        "Empty publication did not preserve metadata while installing actual canvas");
    check(rendered.width==800 && rendered.height==600 && rendered.stride_bytes==2400
        && rendered.pixels && rendered.pixels->size()==800*600*3,"Empty publication did not render the complete actual canvas");
    bool complete=true;
    for (std::size_t i=0;i<rendered.pixels->size();++i)
        if ((*rendered.pixels)[i]!=std::array<std::uint8_t,3>{17,18,19}[i%3]) { complete=false; break; }
    check(complete,"Empty publication left pixels outside the cleared canvas");
    check(empty.client_size.width==640 && empty.client_size.height==480,"Renderer mutated the caller's original empty metadata");
    std::ifstream input(path,std::ios::binary);
    const std::vector<unsigned char> bytes(std::istreambuf_iterator<char>(input),{});
    const std::string header="P6\n800 600\n255\n";
    check(bytes.size()==header.size()+rendered.pixels->size()
        && std::equal(header.begin(),header.end(),bytes.begin())
        && std::equal(rendered.pixels->begin(),rendered.pixels->end(),bytes.begin()+header.size()),
        "Empty actual canvas did not complete its full PPM output before receipt");
    surface.close(); check(!output.ready(),"Blank canvas output remained live after close");
}
void mutation_and_owner_guards() {
    gui::FramebufferAdapter adapter; H::NativeSurfacePeer surface;
    unsigned mutations{},recursions{};
    surface=peer(adapter,{[] { return true; },[&](const gui::Frame&,std::uint64_t revision) {
        rejects([&] { adapter.present(bitmap(999)); },"Output mutated the installed adapter"); ++mutations;
        rejects([&] { (void)surface.present(bitmap(998)); },"Recursive output acquired a receipt"); ++recursions;
        return H::NativeRenderReceipt{revision};
    },{}});
    check(surface.present(bitmap()).snapshot_revision==101 && mutations==1 && recursions==1,"Valid guarded output failed");
    bool other_ready=true,rejected=false;
    std::thread foreign([&] { other_ready=surface.ready(); try { (void)surface.present(bitmap(103)); } catch (...) { rejected=true; } });
    foreign.join(); check(!other_ready && rejected,"Foreign thread entered framebuffer output");
    check(surface.ready(),"Foreign rejection poisoned the actual owner");
}
void preparation_validation() {
    H::NativeFramebufferOutput output{[] { return true; },[](const gui::Frame&,std::uint64_t revision) { return H::NativeRenderReceipt{revision}; },{}};
    gui::RetainedAdapter wrong;
    rejects([&] { (void)H::prepare_native_framebuffer_surface_peer(wrong,window(),{},output); },"A stand-in adapter was admitted");
    gui::FramebufferAdapter adapter;
    auto invalid=window(); invalid.width=0;
    rejects([&] { (void)H::prepare_native_framebuffer_surface_peer(adapter,invalid,{},output); },"Invalid staged extent was admitted");
    rejects([&] { (void)peer(adapter,{}); },"Missing synchronous output was admitted");
    rejects([&] { (void)peer(adapter,{[] { return false; },output.present,{}}); },"Unready output was admitted before App construction");
    adapter.close(); rejects([&] { (void)peer(adapter,output); },"Closed concrete adapter was admitted");
}
void ppm_output(const std::filesystem::path& directory) {
    const auto path=directory/"actual.ppm";
    auto output=H::native_framebuffer_ppm_output(path);
    check(output.ready() && std::filesystem::exists(path),"Actual PPM output was not opened before App creation");
    gui::FramebufferAdapter adapter; auto surface=peer(adapter,output);
    check(surface.present(bitmap(501)).snapshot_revision==501,"Actual PPM write did not acknowledge its Snapshot");
    const auto read=[&] {
        std::ifstream input(path,std::ios::binary);
        return std::vector<unsigned char>(std::istreambuf_iterator<char>(input),{});
    };
    const std::vector<unsigned char> expected{'P','6','\n','2',' ','1','\n','2','5','5','\n',255,0,0,0,255,0};
    check(read()==expected,"PPM header/pixels were not complete and closed before receipt");
    check(surface.present(bitmap(502)).snapshot_revision==502 && read()==expected,"Repeated PPM output did not complete identical pixels/new Snapshot");
    surface.suspend(); check(output.ready(),"Transient context suspension closed PPM output");
    surface.close(); check(!output.ready(),"PPM output remained ready after session close");
    rejects([&] { (void)H::native_framebuffer_ppm_output(directory/"missing"/"output.ppm"); },"Failed actual output open was admitted");
#ifdef __linux__
    struct FileLimit {
        rlimit original{};
        using Handler=void (*)(int);
        Handler handler{};
        FileLimit() {
            if (getrlimit(RLIMIT_FSIZE,&original)) throw std::runtime_error("Cannot inspect fixture file-size limit");
            handler=std::signal(SIGXFSZ,SIG_IGN);
            auto bounded=original; bounded.rlim_cur=8;
            if (setrlimit(RLIMIT_FSIZE,&bounded)) {
                std::signal(SIGXFSZ,handler); throw std::runtime_error("Cannot bound fixture output file");
            }
        }
        ~FileLimit() { (void)setrlimit(RLIMIT_FSIZE,&original); std::signal(SIGXFSZ,handler); }
    };
    {
        auto full=H::native_framebuffer_ppm_output(directory/"bounded-write.ppm");
        FileLimit limit;
        { // Close every file writer before restoring the process-local limit.
            gui::FramebufferAdapter bad; auto broken=peer(bad,full);
            rejects([&] { (void)broken.present(bitmap()); },"Actual flush failure acquired a receipt");
            check(!broken.ready(),"Actual flush failure did not fail the peer closed");
            broken.close();
        }
        full.suspend();
    }
#endif
}
#ifdef FOUNDATION_FRAMEBUFFER_SESSION_FIXTURE
struct ProbeApp {
    std::int64_t width{},height{}; bool active{};
    void drawable_pixels(std::int64_t w,std::int64_t h) { width=w; height=h; }
    void foreground(bool value) { active=value; }
    explicit ProbeApp(H::NativeSurfaceAdapter&) {}
    void handle(gui::Event) {}
    void tick() {}
    void shutdown() {}
    void retry_presentation() {}
    std::optional<gui::ServiceRequest> next_service() { return {}; }
    bool complete_service(gui::ServiceResult) { return false; }
    void qualify(std::function<void()> present) { present(); }
};
void actual_session_weak_lifetime() {
    H::NativeSurfacePublisher publisher;
    unsigned outputs{},stops{},prepared{};
    H::NativeSurfaceSessionFactory<ProbeApp> factory;
    factory.window=window(); factory.mode=H::NativeSurfaceMode::none;
    factory.prepare_peer=[&](gui::Adapter& adapter,const H::NativeSurfaceWindow& value,H::NativeSurfaceIngress ingress) {
        ++prepared;
        return H::prepare_native_framebuffer_surface_peer(adapter,value,std::move(ingress),{
            [] { return true; },[&](const gui::Frame&,std::uint64_t revision) { ++outputs; return H::NativeRenderReceipt{revision}; },[&] { ++stops; }});
    };
    factory.application=[&](H::NativeSurfaceAdapter& adapter) {
        check(prepared==1,"Application was constructed before its concrete output peer");
        publisher=adapter.publisher();
        adapter.present(bitmap());
        return std::make_unique<ProbeApp>(adapter);
    };
    {
        H::NativeSurfaceSession<ProbeApp,gui::FramebufferAdapter,H::AdapterServices> session(std::move(factory));
        check(outputs==1 && publisher.bound(),"Initial App publication was not rendered through actual generic session");
        check(session.application.width==2 && session.application.height==1 && session.application.active,"Output extent/activity was not activated through actual session ingress");
        check(session.surface().capabilities().supported==0 && !session.surface().editor_endpoint_bound()
            && !session.surface().editor_capture() && !session.surface().accepted() && !session.surface().input_admitted(),
            "Read-only session acquired input/editor authority");
        check(publisher.set_owned_service_active(true),"Read-only service suspension was rejected");
        check(outputs==2 && !session.surface().snapshot().widgets.front().state.visible,
            "Normal service did not render its safe redaction through the same framebuffer");
        check(publisher.set_owned_service_active(false),"Read-only service restoration was rejected");
        session.surface().present(bitmap(102));
        check(outputs==3 && session.surface().snapshot().revision==102 && !session.surface().failed(),
            "Service/context suspension permanently closed framebuffer output");
        session.shutdown(); session.shutdown();
        check(stops==1,"Actual output was not suspended exactly once before shutdown");
    }
    check(!publisher.set_owned_service_active(false),"Expired publisher retained its dead native session");
    const auto before=outputs;
    (void)publisher.present_pair(bitmap(102),{});
    (void)publisher.present_editor_retirement(bitmap(103),{});
    check(outputs==before,"Expired publication callback entered a destroyed framebuffer peer");
    H::NativeSurfaceSessionFactory<ProbeApp> initial;
    initial.window=window(); initial.mode=H::NativeSurfaceMode::none;
    initial.prepare_peer=[](gui::Adapter& adapter,const H::NativeSurfaceWindow& value,H::NativeSurfaceIngress ingress) {
        return H::prepare_native_framebuffer_surface_peer(adapter,value,std::move(ingress),{
            [] { return true; },[](const gui::Frame&,std::uint64_t revision) { return H::NativeRenderReceipt{revision}; },{}});
    };
    initial.application=[](H::NativeSurfaceAdapter& adapter) { return std::make_unique<ProbeApp>(adapter); };
    H::NativeSurfaceSession<ProbeApp,gui::FramebufferAdapter,H::AdapterServices> bootstrap(std::move(initial));
    check(bootstrap.surface().snapshot().revision==0 && bootstrap.application.width==2
        && bootstrap.application.height==1 && bootstrap.application.active,
        "Read-only bootstrap depended on a first App frame to discover its configured output canvas");
}
#endif
} // namespace
int main(int argc,char** argv) {
    try {
        if (argc!=2) throw std::invalid_argument("Fixture requires its owned output directory");
        actual_pixels_and_revisions(); output_receipts_and_failures(); actual_blank_canvas(argv[1]); mutation_and_owner_guards(); preparation_validation();
        ppm_output(argv[1]);
#ifdef FOUNDATION_FRAMEBUFFER_SESSION_FIXTURE
        actual_session_weak_lifetime();
#endif
        std::cout << "framebuffer peer checks=" << checks << " failures=0 skips=0\n";
    } catch (const std::exception& error) { std::cerr << "FAIL after " << checks << " checks: " << error.what() << '\n'; return 1; }
}
