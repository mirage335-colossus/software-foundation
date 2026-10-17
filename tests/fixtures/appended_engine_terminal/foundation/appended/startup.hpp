// TEST ONLY: the common native payload reader boundary, not an alternate loader.
#pragma once
#include "shared/native_engine_loader.hpp"
namespace foundation::appended {
inline std::filesystem::path self_relative_path(const std::filesystem::path& hint) {
    auto& s=terminal_main_fixture::state;++s.resolves;
    terminal_main_fixture::require(hint==std::filesystem::path("../share/software-foundation/engine-native"),"entry lost compiled executable-relative runtime hint");
    terminal_main_fixture::require(s.self==0&&s.plans==0&&s.owners==0&&s.verify==0&&s.load==0,"default runtime resolution ran after payload or provider admission");
    if(terminal_main_fixture::is("default-runtime-failure"))throw ContainerError("synthetic unavailable installed runtime");
    return "/fixture/installed/runtime";
}
inline std::optional<Package> load_self() {
    auto& s=terminal_main_fixture::state;++s.self;terminal_main_fixture::event("payload");
    if(terminal_main_fixture::is("missing-payload"))return {};
    if(terminal_main_fixture::is("corrupt-payload"))throw ContainerError("synthetic native payload corruption");
    return Package{s.binary};
}
}
