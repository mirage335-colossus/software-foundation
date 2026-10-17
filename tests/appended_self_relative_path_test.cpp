// Tests only the common OS self-path helper, never an engine or sealed kernel.
#include <foundation/appended/startup.hpp>

#include <filesystem>
#include <iostream>
#include <stdexcept>

namespace {
namespace fs = std::filesystem;
std::size_t assertions{};
void check(bool value, const char* message) {
    ++assertions;
    if (!value) throw std::runtime_error(message);
}
template<class Error> void rejected(const fs::path& hint) {
    bool failed{};
    try { (void)foundation::appended::self_relative_path(hint); }
    catch (const Error&) { failed = true; }
    check(failed, "invalid self-relative path hint was accepted");
}
}
int main(int argc, char** argv) {
    try {
        check(argc == 3, "usage: path-probe COMPILED-RELATIVE-HINT EXPECTED-INSTALLED-PATH");
        const fs::path hint = argv[1], expected = argv[2];
        const auto actual = foundation::appended::self_relative_path(hint);
        check(actual.is_absolute() && actual == actual.lexically_normal(), "self-relative path is not normalized and absolute");
        check(actual == expected, "self-relative path used the working directory, PATH entry or launcher location");
        check(foundation::appended::self_relative_path(hint) == actual, "self-relative path changed between calls");
        rejected<std::invalid_argument>({});
        rejected<std::invalid_argument>(expected);
        fs::path::string_type nul(1, static_cast<fs::path::value_type>('x'));
        nul.push_back(fs::path::value_type{});
        nul.push_back(static_cast<fs::path::value_type>('y'));
        rejected<std::invalid_argument>(fs::path(nul));
        rejected<std::runtime_error>(hint / "missing-installed-path");
        rejected<std::runtime_error>(hint / "dangling-installed-path");
#ifdef _WIN32
        rejected<std::invalid_argument>(fs::path(L"C:drive-relative"));
        rejected<std::invalid_argument>(fs::path(L"\\root-relative"));
#endif
        std::cout << "PASS self-relative-path assertions=" << assertions << '\n';
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "FAIL self-relative-path: " << error.what() << '\n';
        return 1;
    }
}
