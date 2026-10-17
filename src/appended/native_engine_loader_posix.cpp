#include "native_engine_loader.hpp"

#if defined(__linux__)
#include <dlfcn.h>
#include <sys/stat.h>
#include <cstring>

namespace foundation::appended::native_engine_loader_detail {
void check_node(const std::filesystem::path& path, bool directory, std::uint32_t mode, bool compare_mode) {
    struct stat state{};
    if (::lstat(path.c_str(), &state) != 0 ||
        (directory ? !S_ISDIR(state.st_mode) : !S_ISREG(state.st_mode) || state.st_nlink != 1) ||
        (compare_mode && (state.st_mode & 07777) != mode))
        throw NativeEngineLoadError("native engine maintenance required: retained path/type/mode mismatch: " + path.string());
}
decltype(&bib_engine_get_provider_v1) acquire_factory(const std::filesystem::path& path) {
    // The producer qualifies DT_NEEDED/RUNPATH and the private runtime closure.
    // RTLD_LOCAL controls symbol visibility; it does not establish isolation.
    void* handle = ::dlopen(path.c_str(), RTLD_NOW | RTLD_LOCAL);
    if (!handle) throw NativeEngineLoadError("native engine maintenance required: cannot load explicit retained provider: " + path.string());
    // Intentionally no dlclose on any path, including a missing/bad getter.
    ::dlerror();
    void* address = ::dlsym(handle, "bib_engine_get_provider_v1");
    if (::dlerror() || !address)
        throw NativeEngineLoadError("native engine maintenance required: retained provider lacks bib_engine_get_provider_v1; library remains process-lived");
    decltype(&bib_engine_get_provider_v1) factory{};
    static_assert(sizeof(factory) == sizeof(address));
    std::memcpy(&factory, &address, sizeof(factory));
    return factory;
}
} // namespace foundation::appended::native_engine_loader_detail
#endif
