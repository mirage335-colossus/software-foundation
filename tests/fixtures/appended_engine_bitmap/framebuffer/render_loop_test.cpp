// SPDX-License-Identifier: CC0-1.0
// Actual framebuffer main/loop; only Session, output, startup/provider/facade
// seams are synthetic. No display, file output, provider or real close runs.
#include "state.hpp"
#define main foundation_bitmap_framebuffer_embedded_main
#include "../../../../gui/hosts/appended_engine_framebuffer_main.cpp"
#undef main

int main(int argc,char** argv) {
    namespace t=bitmap_framebuffer_fixture;
    if(argc!=2)return 2;
    t::scenario=argv[1];
    if(t::scenario!="success"&&t::scenario!="error-frame"&&t::scenario!="error-detached")return 2;
    try {
        foundation::host::native_bitmap_entry::Factory factory;
        factory.mode=foundation::host::NativeSurfaceMode::none;
        foundation::host::native_bitmap_entry::Invocation invocation;
        invocation.read_only=true;invocation.output=bitmap_entry_fixture::output_path();
        const auto result=render(std::move(factory),invocation);
        const bool success=t::scenario=="success";
        t::require(result==(success?0:1),"framebuffer loop swallowed a failure or rejected success");
        t::require(t::sessions==1&&t::shutdowns==1&&t::ticks==1,"framebuffer loop changed first-frame/close order");
        t::require(t::outputs==(success?2u:1u)&&t::artifacts==(success?1u:0u),
            "framebuffer saved an artifact after failure or skipped successful retained image");
        t::require(bitmap_entry_fixture::invariant_failure.empty(),"render-loop boundary assertion was swallowed");
        return 0;
    } catch(const std::exception& error) { std::cerr<<error.what()<<'\n';return 1; }
}
