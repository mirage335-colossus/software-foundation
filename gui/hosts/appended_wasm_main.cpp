#include "host/browser.hpp"
#include "shared/appended_application.hpp"
#include <memory>
#include <stdexcept>
#include <vector>

namespace {
std::vector<std::uint8_t> prepared_module;
// Injection keeps the browser entry independent of native executable discovery.
class PreparedApplication final : public foundation::ui::AppendedApplication {
public:
    explicit PreparedApplication(gui::Adapter& adapter)
        : AppendedApplication(adapter, prepared_module) {}
};
using Runtime = foundation::host::Browser<PreparedApplication>;
std::unique_ptr<Runtime> runtime;
std::string response, preparation_error;
std::uint64_t next_runtime = 1;
}

extern "C" {
// Private producer marker: this kernel links the module-provider bridge.
// It is separate from the portable application's seven scalar exports.
std::uint32_t gui_web_providers_v1() { return 0x00010000u; }
// The base-owned Worker copies the already verified component into kernel memory
// before creating a GUI session. A retained kernel never reads a URL or executes
// an HTML component to obtain binary application behavior.
const char* gui_web_prepare(const unsigned char* bytes, std::size_t length) {
    preparation_error.clear();
    if (runtime) preparation_error = "Cannot replace a live binary application";
    else if (!bytes || length < 8 || length > 4u * 1024u * 1024u)
        preparation_error = "Missing or oversized binary application";
    else {
        try { prepared_module.assign(bytes, bytes + length); }
        catch (const std::exception& error) { preparation_error = error.what(); }
    }
    if (!preparation_error.empty()) prepared_module.clear();
    return preparation_error.c_str();
}
void gui_web_destroy() { runtime.reset(); prepared_module.clear(); response.clear(); }
const char* gui_web_create(const char* epoch) {
    if (prepared_module.empty()) throw std::runtime_error("No binary application was prepared");
    runtime = std::make_unique<Runtime>(epoch && *epoch ? epoch : "appended-wasm-" + std::to_string(next_runtime++));
    response = runtime->initial(); return response.c_str();
}
const char* gui_web_receive(const char* message) {
    if (!runtime) throw std::runtime_error("Binary application session is not initialized");
    response = runtime->receive(message ? message : ""); return response.c_str();
}
}
