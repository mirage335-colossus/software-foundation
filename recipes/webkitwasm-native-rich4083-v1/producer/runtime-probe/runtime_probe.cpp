// Link-only diagnostic. The producer inspects this DSO without loading it.
// Strings, allocation and exceptions stay wholly behind the single C entry.
#include <cstdint>
#include <memory>
#include <stdexcept>
#include <string>

namespace {
struct Payload final {
    explicit Payload(std::uint32_t seed)
        : text(64u + (seed & 1023u), static_cast<char>('a' + (seed % 26u))),
          bytes(std::make_unique<char[]>(text.size() + 1u)) {
        text.copy(bytes.get(), text.size());
        bytes[text.size()] = '\0';
    }
    std::string text;
    std::unique_ptr<char[]> bytes;
};
}

extern "C" __attribute__((visibility("default")))
std::int32_t bib_native_runtime_probe_v1(std::uint32_t seed) noexcept {
    try {
        Payload payload(seed);
        if ((seed & 1u) != 0u) {
            // Unwinding must destroy both allocated members before the catch.
            throw std::runtime_error(payload.text);
        }
        return static_cast<std::int32_t>(payload.text.size()
            + static_cast<unsigned char>(payload.bytes[seed % payload.text.size()]));
    } catch (const std::runtime_error& error) {
        return -static_cast<std::int32_t>(std::char_traits<char>::length(error.what()));
    } catch (...) {
        // No exception or C++ ownership is permitted through the C entry.
        return -1;
    }
}
