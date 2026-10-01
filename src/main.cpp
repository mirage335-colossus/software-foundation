#include "foundation/store.hpp"
#include "foundation/version.hpp"

#include <exception>
#include <iostream>
#include <string_view>

int main(int argc, char** argv) {
    try {
        if (argc == 2 && std::string_view(argv[1]) == "--version") {
            std::cout << "software-foundation " << FOUNDATION_VERSION << '\n';
            return std::cout.flush() ? 0 : 1;
        }
        if (argc == 2 && std::string_view(argv[1]) == "--self-check") {
            foundation::Store store(1);
            const auto id = store.add("example");
            return store.get(id)->text == "example" && store.erase(id) ? 0 : 1;
        }
        if (argc == 1 || (argc == 2 && std::string_view(argv[1]) == "--help")) {
            std::cout << "Usage: foundation-cli [--version|--self-check|--help]\n"
                         "       foundation-cli -- TEXT [TEXT ...]\n"
                         "Print a bounded collection, one record per line.\n";
            return std::cout.flush() ? 0 : 1;
        }
        if (std::string_view(argv[1]) != "--" || argc < 3) {
            std::cerr << "Use --help for usage.\n";
            return 2;
        }
        foundation::Store store;
        // Validate the complete request before emitting any records.
        for (int i = 2; i < argc; ++i) store.add(argv[i]);
        for (const auto& row : store.snapshot()) {
            std::cout << row.id << '\t' << row.text << '\n';
        }
        if (!std::cout.flush()) return 1;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
    return 0;
}
