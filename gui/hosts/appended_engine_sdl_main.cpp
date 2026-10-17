// SPDX-License-Identifier: CC0-1.0
#include "appended_engine_native_entry.hpp"
#include "sdl_runner.hpp"

int main(int argc, char** argv) {
    namespace entry = foundation::host::native_bitmap_entry;
    return entry::run(argc, argv, {}, [&](entry::Factory factory, const entry::Invocation&) {
        return foundation::host::run_sdl<entry::PreparedApplication>(1, argv, std::move(factory));
    });
}
