// TEST ONLY: the common native payload reader boundary, not an alternate loader.
#pragma once
#include "shared/native_engine_loader.hpp"
namespace foundation::appended {
inline std::filesystem::path self_relative_path(const std::filesystem::path& hint) {
    auto& s=bitmap_entry_fixture::state;++s.resolves;
    bitmap_entry_fixture::require(hint==std::filesystem::path("../share/software-foundation/engine-native"),"entry lost compiled executable-relative runtime hint");
    bitmap_entry_fixture::require(s.self==0&&s.plans==0&&s.owners==0&&s.verify==0&&s.load==0,"default runtime resolution ran after payload or provider admission");
    if(bitmap_entry_fixture::is("default-runtime-failure"))throw ContainerError("synthetic unavailable installed runtime");
    return bitmap_entry_fixture::installed_root();
}
inline std::optional<Package> load_self() {
    auto& s=bitmap_entry_fixture::state;++s.self;bitmap_entry_fixture::event("payload");
    if(bitmap_entry_fixture::is("missing-payload"))return {};
    if(bitmap_entry_fixture::is("corrupt-payload"))throw ContainerError("synthetic native payload corruption");
    Package result;result.binary=s.binary;return result;
}
}
