// SPDX-License-Identifier: CC0-1.0
// Native bitmap composition entry only. Preserve UTF-16 arguments before the
// CRT's narrow argument/code-page conversion, including console framebuffer use.
#ifdef _WIN32
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#include <shellapi.h>
#include "../../src/platform/windows_arguments.hpp"
#include <iostream>
#include <string>
#include <vector>
#ifdef FOUNDATION_GUI_SDL_ENTRY
#include <SDL.h>
#endif

int foundation_gui_main(int argc, char** argv);

namespace {
int invoke_native_bitmap() {
    try {
        int count{};
        struct WideArguments {
            wchar_t** values{};
            ~WideArguments() { if (values) LocalFree(values); }
        } original{CommandLineToArgvW(GetCommandLineW(), &count)};
        if (!original.values || count < 1)
            throw std::runtime_error("Could not read native command-line arguments");
        std::vector<std::string> values;
        values.reserve(static_cast<std::size_t>(count));
        for (int index = 0; index < count; ++index)
            values.push_back(foundation::platform::utf8_argument(original.values[index]));
        std::vector<char*> pointers;
        pointers.reserve(values.size() + 1);
        for (auto& value : values) pointers.push_back(value.data());
        pointers.push_back(nullptr);
#ifdef FOUNDATION_GUI_SDL_ENTRY
        SDL_SetMainReady();
#endif
        return foundation_gui_main(count, pointers.data());
    } catch (const std::exception& error) {
        std::cerr << "Native bitmap arguments: " << error.what() << '\n';
        return 1;
    }
}
} // namespace

#if defined(FOUNDATION_NATIVE_BITMAP_CONSOLE_ENTRY)
// The target renames only the application's main contract. This translation
// unit supplies the real CRT entry and still reads the original wide arguments.
#undef main
int main() { return invoke_native_bitmap(); }
#else
int WINAPI WinMain(HINSTANCE, HINSTANCE, LPSTR, int) {
    return invoke_native_bitmap();
}
#endif
#endif
