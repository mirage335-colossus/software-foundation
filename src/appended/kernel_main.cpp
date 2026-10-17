#include "foundation/appended/container.hpp"
#include "foundation/appended/module.hpp"
#include "foundation/appended/providers.hpp"
#include "foundation/appended/registry.hpp"
#include "foundation/appended/startup.hpp"
#include "platform/windows_arguments.hpp"

#include <algorithm>
#include <array>
#include <charconv>
#include <cstdint>
#include <filesystem>
#include <iostream>
#include <optional>
#include <span>
#include <stdexcept>
#include <string>
#include <string_view>
#include <vector>

namespace {
namespace appended = foundation::appended;

std::string_view mode(const std::optional<appended::Package>& package) {
    if (!package) return "neither";
    if (package->web.present) return package->binary.present ? "both" : "web";
    return package->binary.present ? "binary" : "neither";
}

unsigned int hex_digit(char value) {
    if (value >= '0' && value <= '9') return static_cast<unsigned int>(value - '0');
    if (value >= 'a' && value <= 'f') return static_cast<unsigned int>(value - 'a' + 10);
    if (value >= 'A' && value <= 'F') return static_cast<unsigned int>(value - 'A' + 10);
    throw std::invalid_argument("input needs an even number of hexadecimal digits");
}

appended::Bytes parse_hex(std::string_view value) {
    if (value.size() % 2 != 0)
        throw std::invalid_argument("input needs an even number of hexadecimal digits");
    if (value.size() / 2 > FOUNDATION_APPENDED_MAX_MESSAGE_BYTES)
        throw std::invalid_argument("dispatch input exceeds the ABI message limit");
    appended::Bytes result;
    result.reserve(value.size() / 2);
    for (std::size_t i = 0; i != value.size(); i += 2)
        result.push_back(static_cast<std::uint8_t>((hex_digit(value[i]) << 4) | hex_digit(value[i + 1])));
    return result;
}

void print_hex(std::span<const std::uint8_t> bytes) {
    static constexpr char digits[] = "0123456789abcdef";
    for (const auto value : bytes)
        std::cout << digits[value >> 4] << digits[value & 15];
}

struct Options {
    bool inspect{false}, help{false};
    std::optional<std::string_view> expected;
    std::optional<appended::Bytes> dispatch;
    std::optional<std::string_view> provider;
    std::optional<std::uint32_t> provider_operation;
    std::optional<appended::Bytes> provider_payload;
};

Options parse_options(int argc, const char* const* argv) {
    Options result;
    for (int i = 1; i != argc; ++i) {
        const std::string_view argument(argv[i]);
        if (argument == "--inspect" && !result.inspect) result.inspect = true;
        else if (argument == "--help" && !result.help) result.help = true;
        else if (argument == "--expect-mode" && !result.expected && i + 1 < argc) {
            const std::string_view expected(argv[++i]);
            if (expected != "neither" && expected != "web" && expected != "binary" && expected != "both")
                throw std::invalid_argument("--expect-mode needs neither, web, binary or both");
            result.expected = expected;
        } else if ((argument == "--dispatch" || argument == "--dispatch-hex") && !result.dispatch && i + 1 < argc) {
            const std::string_view input(argv[++i]);
            if (argument == "--dispatch-hex") result.dispatch = parse_hex(input);
            else {
                if (input.size() > FOUNDATION_APPENDED_MAX_MESSAGE_BYTES)
                    throw std::invalid_argument("dispatch input exceeds the ABI message limit");
                result.dispatch.emplace(input.begin(), input.end());
            }
        } else if (argument == "--provider" && !result.provider && i + 1 < argc) {
            result.provider = argv[++i];
            if (result.provider->empty() || result.provider->starts_with('-'))
                throw std::invalid_argument("--provider needs a contract name");
        } else if (argument == "--provider-operation" && !result.provider_operation && i + 1 < argc) {
            const std::string_view value(argv[++i]);
            std::uint32_t operation = 0;
            const auto parsed = std::from_chars(value.data(), value.data() + value.size(), operation);
            if (parsed.ec != std::errc{} || parsed.ptr != value.data() + value.size() || operation == 0)
                throw std::invalid_argument("--provider-operation needs a positive uint32 value");
            result.provider_operation = operation;
        } else if (argument == "--provider-payload-hex" && !result.provider_payload && i + 1 < argc) {
            result.provider_payload = parse_hex(argv[++i]);
        } else throw std::invalid_argument("invalid arguments; use --help for usage");
    }
    if ((result.provider_operation || result.provider_payload) && !result.provider)
        throw std::invalid_argument("provider operation and payload require --provider");
    if ((result.dispatch || result.provider) && (result.inspect || result.help))
        throw std::invalid_argument("application calls cannot be combined with --inspect or --help");
    if (result.dispatch && result.provider)
        throw std::invalid_argument("dispatch and provider calls must be separate invocations");
    return result;
}

void register_diagnostics(appended::Registry& registry, std::uint64_t& calls) {
    appended::ServiceDescriptor descriptor;
    descriptor.name = "foundation.diagnostics";
    descriptor.max_reply_bytes = 65536;
    descriptor.schema = {0xae, 0xd2, 0xa3, 0x5d, 0x3c, 0xb1, 0x62, 0x5b,
        0x2a, 0xb4, 0x00, 0x32, 0xc8, 0x53, 0xbd, 0x98,
        0xa1, 0x3a, 0xc3, 0xcb, 0x57, 0x05, 0x42, 0x7b,
        0x4a, 0x3c, 0x82, 0x09, 0xe0, 0xc0, 0x58, 0x10};
    const auto result = registry.register_service(std::move(descriptor), [&calls](std::uint32_t operation,
        std::span<const std::uint8_t> request, std::span<std::uint8_t> response) -> appended::ServiceReply {
        if (operation != 1) return {appended::ServiceStatus::unknown_operation, 0};
        if (request.size() > response.size()) return {appended::ServiceStatus::limit_exceeded, 0};
        std::copy(request.begin(), request.end(), response.begin());
        ++calls;
        std::cout << "diagnostics\t";
        print_hex(request);
        std::cout << '\n';
        return {appended::ServiceStatus::ok, static_cast<std::uint32_t>(request.size())};
    });
    if (result.status != appended::ServiceStatus::ok)
        throw std::runtime_error("could not register the native diagnostics service");
}

int run(int argc, const char* const* argv) {
    try {
        const auto options = parse_options(argc, argv);
        const auto boundary = appended::self_pristine_length();
        const auto package = appended::load_self();
        if (options.expected && *options.expected != mode(package))
            throw std::runtime_error("expected appended mode " + std::string(*options.expected) +
                                     ", found " + std::string(mode(package)));
        if (options.help) {
            std::cout << "Usage: foundation-appended-kernel [--inspect] [--expect-mode MODE]\n"
                         "       foundation-appended-kernel [--expect-mode MODE] [--dispatch TEXT|--dispatch-hex HEX]\n"
                         "       foundation-appended-kernel --provider NAME [--provider-operation N] [--provider-payload-hex HEX]\n"
                         "MODE is neither, web, binary or both. This console kernel implements the binary profile.\n";
            return std::cout.flush() ? 0 : 1;
        }
        if (options.inspect) {
            if (package) std::cout << package->index_json << '\n';
            else std::cout << "{\"mode\":\"neither\",\"sealed\":true,\"kernel_length\":" << boundary << "}\n";
            return std::cout.flush() ? 0 : 1;
        }
        if (!package) {
            if (options.dispatch || options.provider) throw std::runtime_error("there is no appended binary application to call");
            std::cout << "Foundation binary kernel: no appended application\n";
            return std::cout.flush() ? 0 : 1;
        }
        if (package->web.present)
            throw std::runtime_error("rich web engine capability is unavailable in this binary kernel");
        if (package->abi_major != FOUNDATION_APPENDED_ABI_MAJOR || package->abi_minor > FOUNDATION_APPENDED_ABI_MINOR)
            throw std::runtime_error("the composition requires an unsupported application ABI version");
        if (!package->binary.present || !package->binary.entry)
            throw std::runtime_error("the composition contains no binary entry point");
        if (!package->binary.profile || *package->binary.profile != "foundation-guest-v1")
            throw std::runtime_error("unsupported appended binary profile");
        const auto* binary = package->find_file(*package->binary.entry);
        if (binary == nullptr) throw std::runtime_error("the binary entry point is missing");

        std::cout << "application\t" << package->application.id << '\t' << package->application.name
                  << '\t' << package->application.version << '\n';
        appended::Registry registry(1);
        std::uint64_t calls = 0;
        register_diagnostics(registry, calls);
        appended::Module module(binary->data, registry);
        appended::ModuleProviders providers(module, registry);
        // Provider readiness precedes guest initialization; no guest callback is
        // permitted to compete for a second host loop.
        for (const auto& service : package->services) {
            if (service == FOUNDATION_APPENDED_BOOTSTRAP_NAME) continue;
            if (registry.discover({service, 1, 0, 0, std::nullopt}).status != appended::ServiceStatus::ok)
                throw std::runtime_error("required application service is unavailable: " + service);
        }
        for (const auto& capability : package->capabilities)
            if (capability != "foundation.providers.v1")
                throw std::runtime_error("required kernel capability is unavailable: " + capability);
        if (module.initialize() != FOUNDATION_APPENDED_APP_OK)
            throw std::runtime_error("binary application initialization failed");
        if (providers.activate() != appended::ServiceStatus::ok)
            throw std::runtime_error("binary application provider activation failed");
        std::cout << "binary\tinitialized\n";
        if (options.dispatch && module.dispatch(*options.dispatch) != FOUNDATION_APPENDED_APP_OK)
            throw std::runtime_error("binary application dispatch failed");
        if (options.provider) {
            const auto found = providers.discover({std::string(*options.provider), 1, 0, 0, std::nullopt});
            if (found.status != appended::ServiceStatus::ok)
                throw std::runtime_error("application provider is unavailable: " + std::string(*options.provider));
            const auto result = providers.invoke({registry.generation(), 1, found.handle,
                options.provider_operation.value_or(1), options.provider_payload.value_or(appended::Bytes{})});
            std::cout << "provider\t" << *options.provider << '\t' << static_cast<std::uint32_t>(result.status) << '\t';
            print_hex(result.payload); std::cout << '\n';
            if (providers.acknowledge(1) != appended::ServiceStatus::ok)
                throw std::runtime_error("application provider result acknowledgment failed");
            if (result.status != appended::ServiceStatus::ok)
                throw std::runtime_error("application provider call failed");
        }
        constexpr std::uint32_t budget = 10000;
        bool idle = false;
        for (unsigned int slice = 0; slice != 64; ++slice) {
            const auto result = module.step(budget);
            if (result == FOUNDATION_APPENDED_STEP_IDLE) { idle = true; break; }
            if (result != FOUNDATION_APPENDED_STEP_MORE)
                throw std::runtime_error("binary application step failed");
        }
        if (!idle) throw std::runtime_error("binary application exceeded the bounded console scheduling budget");
        providers.close();
        module.shutdown();
        std::cout << "service_calls\t" << calls << '\n';
        return std::cout.flush() ? 0 : 1;
    } catch (const std::exception& error) {
        std::cerr << "appended kernel: " << error.what() << '\n';
        return 1;
    }
}
} // namespace

#ifdef _WIN32
int wmain(int argc, wchar_t** argv) {
    try {
        std::vector<std::string> arguments;
        arguments.reserve(static_cast<std::size_t>(argc));
        for (int i = 0; i != argc; ++i) arguments.push_back(foundation::platform::utf8_argument(argv[i]));
        std::vector<const char*> pointers;
        pointers.reserve(arguments.size());
        for (const auto& value : arguments) pointers.push_back(value.c_str());
        return run(argc, pointers.data());
    } catch (const std::exception& error) {
        std::cerr << "appended kernel: " << error.what() << '\n';
        return 1;
    }
}
#else
int main(int argc, char** argv) { return run(argc, argv); }
#endif
