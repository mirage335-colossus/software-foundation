// SPDX-License-Identifier: CC0-1.0
// Real main/source with test-only physical-boundary overlays. No real engine,
// SDK, payload image, TTY, Module/VM, DSO or production provider is exercised.
#include "fixtures/appended_engine_terminal/state.hpp"
#define main appended_engine_terminal_entry_for_test
#include "../gui/hosts/appended_engine_terminal_main.cpp"
#undef main

#include <iostream>
#include <sstream>
#include <string>
#include <vector>

#if defined(FOUNDATION_APPENDED_BINARY_CAPABILITY) && FOUNDATION_APPENDED_BINARY_CAPABILITY
namespace foundation::appended {
std::unique_ptr<EngineModuleBinding> make_engine_module_binding(std::span<const std::uint8_t>,std::span<const NativeServiceRegistration>,std::uint64_t){
    ++terminal_main_fixture::state.factories;return std::make_unique<EngineModuleBinding>();
}
std::unique_ptr<EngineModuleBinding> make_engine_binary_view_module_binding(std::span<const std::uint8_t>,std::span<const NativeServiceRegistration>,std::uint64_t){
    ++terminal_main_fixture::state.factories;
    throw std::logic_error("binary-primary view is not modeled by terminal entry fixture");
}
}
#endif
namespace {
int invoke(std::vector<std::string> values){
    auto& s=terminal_main_fixture::state;s.argv0=values.front();std::vector<char*> args;
    for(auto& item:values)args.push_back(item.data());
    return appended_engine_terminal_entry_for_test(static_cast<int>(args.size()),args.data());
}
void absent(unsigned value,const char* text){terminal_main_fixture::require(value==0,text);}
}
int main(int argc,char** argv){
    namespace t=terminal_main_fixture;auto& s=t::state;
    try{
        t::require(argc==2,"select exactly one fresh-process case");s.scenario=argv[1];
        std::vector<std::string> args{"terminal-fixture","--engine-runtime-root","/fixture/runtime"};
        int wanted=0;
#if defined(FOUNDATION_APPENDED_ENGINE_NATIVE_DOCUMENT_ACTIONS_PROFILE) && FOUNDATION_APPENDED_ENGINE_NATIVE_DOCUMENT_ACTIONS_PROFILE
        if(t::is("default-runtime"))args={"terminal-fixture"};
        else if(t::is("default-runtime-failure")){args={"terminal-fixture"};wanted=1;}
        else if(t::is("actions-cli-missing")){args={"terminal-fixture","--engine-runtime-root"};wanted=1;}
        else if(s.scenario.starts_with("actions-plan-")){
            s.actions_mismatch=std::stoi(s.scenario.substr(13));t::require(s.actions_mismatch>=0&&s.actions_mismatch<=96,"invalid actions plan case");s.actions_rejected=true;wanted=1;
        }else if(s.scenario.starts_with("actions-facts-")){
            const auto index=std::stoi(s.scenario.substr(14));t::require(index>=0&&index<=90,"invalid actions facts case");t::alter_actions(s.actions_profile,index);s.actions_rejected=true;wanted=1;
        }else if(t::is("actions-browser")){
            s.actions_profile.target_system=BIB_ENGINE_TARGET_BROWSER_WASM;s.actions_profile.target_processor=BIB_ENGINE_CPU_WASM32;s.actions_profile.pointer_bits=32;s.actions_rejected=true;wanted=1;
        }else if(t::is("actions-legacy-document")||t::is("actions-legacy-editor")||t::is("actions-legacy-document-dirty")||t::is("actions-legacy-editor-dirty")){
            s.actions_rejected=true;wanted=1;
        }else if(t::is("actions-linux-arm64"))s.actions_profile.target_processor=BIB_ENGINE_CPU_AARCH64;
        else if(t::is("actions-windows"))s.actions_profile.target_system=BIB_ENGINE_TARGET_WINDOWS;
        else
#endif
        if(s.scenario.starts_with("profile-")){s.mismatch=std::stoi(s.scenario.substr(8));t::require(s.mismatch>=0&&s.mismatch<=36,"invalid profile case");wanted=1;}
        else if(t::is("help"))args={"terminal-fixture","--help"};
        else if(t::is("cli-missing")){args={"terminal-fixture"};wanted=1;}
        else if(t::is("cli-relative")){args[2]="relative/runtime";wanted=1;}
        else if(t::is("cli-normalized")){args[2]="/fixture/../runtime";wanted=1;}
        else if(t::is("cli-flag")){args[1]="--runtime";wanted=1;}
        else if(t::is("cli-extra")){args.push_back("extra");wanted=1;}
        else if(t::is("physical-profile")){s.profile.kind=foundation::appended::engine_document::ProfileKind::physical;s.profile.name=foundation::appended::engine_document::kPhysicalProfileName;s.profile.provider_capabilities=2003;s.profile.physical_catalog_sha256=foundation::appended::engine_document::kPhysicalCatalogSha256;wanted=1;}
        else if(t::is("browser-profile")){s.profile.target_system=BIB_ENGINE_TARGET_BROWSER_WASM;s.profile.target_processor=BIB_ENGINE_CPU_WASM32;s.profile.pointer_bits=32;wanted=1;}
        else if(t::is("invalid-profile")){s.profile.provider_abi_minor=0;wanted=1;}
        else if(t::is("binary-payload")){
            s.binary=true;
#if !defined(FOUNDATION_APPENDED_BINARY_CAPABILITY) || !FOUNDATION_APPENDED_BINARY_CAPABILITY
            wanted=1;
#endif
        }else if(t::is("unconfigured-start")){s.configured=false;wanted=1;}
        else if(t::is("unadopted-start")){s.adopt_identity=false;wanted=1;}
        else if(t::is("missing-payload")||t::is("corrupt-payload")||t::is("invalid-startup")||t::is("plan-root")||t::is("verify-failure")||t::is("load-failure")||t::is("bind-failure")||t::is("start-terminal")||t::is("start-blocked")||t::is("start-bound")||t::is("runner-terminal")||t::is("runner-blocked")||t::is("close-terminal")||t::is("close-blocked")||t::is("unfinished-close")||t::is("tty-failure")||t::is("tty-nonstd")||t::is("tty-return-failure"))wanted=1;
        else t::require(t::is("graceful")||t::is("start-waiting")||t::is("runner-hooks"),"unknown fixture case");
        s.expire_close=[] {terminal_main_fixture::require(prepared!=nullptr,"missing scoped binding");prepared->close_deadline=Clock::now()-std::chrono::milliseconds(1);};
        s.on_facade_tick=[] {terminal_main_fixture::require(prepared&&!prepared->wake.pending.load(std::memory_order_acquire),"tick did not clear atomic wake before facade");terminal_main_fixture::state.wake_cleared=true;};
        std::ostringstream output,errors;auto* cout_old=std::cout.rdbuf(output.rdbuf());auto* cerr_old=std::cerr.rdbuf(errors.rdbuf());
        const auto result=invoke(args);std::cout.rdbuf(cout_old);std::cerr.rdbuf(cerr_old);
        t::require(result==wanted,"unexpected main result");t::require(prepared==nullptr,"injection escaped runner scope");
        if(t::is("runner-hooks")){
            auto* native=static_cast<foundation::appended::NativeEngineDriver*>(s.bound_driver);
            auto* token=static_cast<WakeToken*>(native->wake.context);token->pending.store(false,std::memory_order_release);
            const auto ticks=s.driver_ticks,facade_ticks=s.facade_ticks;
            std::thread late_wake([&]{native->wake.post_owner_wake(native->wake.context);});late_wake.join();
            t::require(token->pending.load(std::memory_order_acquire)&&s.driver_ticks==ticks&&s.facade_ticks==facade_ticks,"Driver wake retained dead scoped wrapper or pumped after injection");
        }
        if(t::is("default-runtime-failure")||t::is("actions-cli-missing")){absent(s.self,"default resolution or CLI failure read payload");absent(s.plans,"default resolution or CLI failure created plan");}
        else if(t::is("help")||s.scenario.starts_with("cli-")){absent(s.self,"CLI/help read payload");absent(s.plans,"CLI/help created plan");}
        else {t::require(s.self==1,"native payload not read exactly once");t::require(!s.events.empty()&&s.events.front()=="payload","load_self did not precede admission");}
        if(t::is("default-runtime")||t::is("default-runtime-failure"))t::require(s.resolves==1,"default entry did not resolve installed runtime exactly once");
        else absent(s.resolves,"explicit runtime override or CLI/help resolved installed runtime");
        if(s.plans)t::require(s.plan_root==(t::is("default-runtime")?"/fixture/installed/runtime":"/fixture/runtime"),"generated plan received the wrong runtime root");
        if(t::is("help"))t::require(output.str().find("--engine-runtime-root")!=std::string::npos,"missing help interface");
        if(t::is("missing-payload")||t::is("corrupt-payload"))absent(s.plans,"invalid payload reached generated plan");
        if(s.mismatch>=0||t::is("physical-profile")||t::is("browser-profile")||t::is("invalid-profile")||t::is("plan-root"))absent(s.owners,"invalid plan/profile constructed Owner");
        if(s.actions_rejected){absent(s.owners,"invalid actions plan/profile constructed Owner");absent(s.verify,"invalid actions plan/profile verified native closure");absent(s.load,"invalid actions plan/profile loaded provider");}
        if(t::is("invalid-startup")){t::require(s.owners==1,"startup was not checked by Owner");absent(s.verify,"invalid startup reached native closure");}
        if(t::is("verify-failure"))absent(s.load,"verification failure loaded provider");
        if(t::is("load-failure"))absent(s.bind,"failed load bound Driver");
        if(t::is("bind-failure"))absent(s.start,"failed bind started provider");
        if(s.load)t::require(s.owners==1&&s.verify==1&&s.events[2]=="owner"&&s.events[3]=="verify"&&s.events[4]=="load","Owner/verify/load ordering changed");
        if(s.start)t::require(s.start==1&&s.bind==1,"native provider bound/started repeatedly");
        if(t::is("unconfigured-start")||t::is("unadopted-start")||t::is("start-terminal")||t::is("start-blocked")||t::is("start-bound"))absent(s.runner,"invalid start reached terminal runner");
        if(t::is("tty-failure")||t::is("tty-nonstd")||t::is("tty-return-failure")){absent(s.facades,"TTY failure constructed App");t::require(s.close_requests==1&&s.driver_ticks==1,"TTY failure bypassed bounded ordinary close");}
        if(t::is("runner-terminal")||t::is("runner-blocked")||t::is("start-terminal")||t::is("start-blocked")){absent(s.close_requests,"terminal state attempted provider cleanup");absent(s.driver_ticks,"terminal state advanced provider");}
        if(t::is("unfinished-close"))t::require(s.driver_ticks==0&&s.close_requests==1,"expired close deadline pumped or forced cleanup");
        if(t::is("runner-hooks"))t::require(s.cells==1&&s.foreground==1&&s.retry==1&&s.qualify==1&&s.handled==1&&s.service_reads==1&&s.service_completions==1&&s.wake_cleared,"scoped wrapper failed hooks");
        if(t::is("binary-payload")){
#if defined(FOUNDATION_APPENDED_BINARY_CAPABILITY) && FOUNDATION_APPENDED_BINARY_CAPABILITY
            t::require(s.factories==1&&s.start==1,"both did not inject actual fixture module factory");
#else
            absent(s.verify,"web binary reached verifier");absent(s.load,"web binary loaded provider");absent(s.factories,"web unexpectedly referenced module factory");
#endif
        }
        std::cout<<"PASS "<<s.scenario<<" (mock boundaries only)\n";return 0;
    }catch(const std::exception& error){std::cerr<<"FAIL "<<s.scenario<<": "<<error.what()<<'\n';return 1;}
}
