#include "native_engine_loader.hpp"

#if defined(_WIN32)
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <cstring>

namespace foundation::appended::native_engine_loader_detail {
void check_node(const std::filesystem::path& path, bool directory, std::uint32_t mode, bool compare_mode) {
    (void)mode; (void)compare_mode; // Compiled plan is Windows logical-mode authority.
    const DWORD attributes = ::GetFileAttributesW(path.c_str());
    if (attributes == INVALID_FILE_ATTRIBUTES ||
        (attributes & (FILE_ATTRIBUTE_REPARSE_POINT | FILE_ATTRIBUTE_DEVICE)) ||
        ((attributes & FILE_ATTRIBUTE_DIRECTORY) != 0) != directory)
        throw NativeEngineLoadError("native engine maintenance required: linked/reparse or wrong retained path type");
    if (!directory) {
        const HANDLE file = ::CreateFileW(path.c_str(), FILE_READ_ATTRIBUTES, FILE_SHARE_READ,
            nullptr, OPEN_EXISTING, FILE_FLAG_OPEN_REPARSE_POINT, nullptr);
        if (file == INVALID_HANDLE_VALUE)
            throw NativeEngineLoadError("native engine maintenance required: retained file attributes unavailable");
        BY_HANDLE_FILE_INFORMATION state{};
        const bool ordinary = ::GetFileInformationByHandle(file, &state) && state.nNumberOfLinks == 1 &&
            !(state.dwFileAttributes & (FILE_ATTRIBUTE_REPARSE_POINT | FILE_ATTRIBUTE_DEVICE | FILE_ATTRIBUTE_DIRECTORY));
        ::CloseHandle(file); // Attribute handle only; never an engine HMODULE.
        if (!ordinary) throw NativeEngineLoadError("native engine maintenance required: retained file is not ordinary and singly linked");
    }
}
decltype(&bib_engine_get_provider_v1) acquire_factory(const std::filesystem::path& path) {
    const HMODULE handle = ::LoadLibraryExW(path.c_str(), nullptr,
        LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR | LOAD_LIBRARY_SEARCH_SYSTEM32);
    if (!handle) throw NativeEngineLoadError("native engine maintenance required: cannot load explicit retained provider DLL");
    // Intentionally no FreeLibrary on any path, including a missing/bad getter.
    const FARPROC address = ::GetProcAddress(handle, "bib_engine_get_provider_v1");
    if (!address) throw NativeEngineLoadError("native engine maintenance required: retained provider lacks bib_engine_get_provider_v1; DLL remains process-lived");
    decltype(&bib_engine_get_provider_v1) factory{};
    static_assert(sizeof(factory) == sizeof(address));
    std::memcpy(&factory, &address, sizeof(factory));
    return factory;
}
} // namespace foundation::appended::native_engine_loader_detail
#endif
