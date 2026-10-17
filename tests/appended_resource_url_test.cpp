#include <foundation/appended/resource_url.hpp>

#include <iostream>
#include <stdexcept>
#include <string>
#include <string_view>
#include <vector>

namespace {
using foundation::appended::ResourceUrlError;
using foundation::appended::normalize_app_resource_url;

constexpr std::string_view pin = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef";
std::size_t assertions = 0;

void require(bool condition, const std::string& message) {
    ++assertions;
    if (!condition) throw std::runtime_error(message);
}

std::string url(std::string_view path) {
    return "app://" + std::string(pin) + "/" + std::string(path);
}

void accepts(std::string_view source, std::string_view expected) {
    const auto result = normalize_app_resource_url(source, pin);
    require(static_cast<bool>(result), "rejected valid URL: " + std::string(source));
    require(result.error == ResourceUrlError::none, "successful result has an error");
    require(result.path == expected, "resource key differs for: " + std::string(source));
}

void rejects(std::string_view source) {
    const auto result = normalize_app_resource_url(source, pin);
    require(!result, "accepted invalid URL: " + std::string(source));
    require(result.error != ResourceUrlError::none, "failed result has no error");
    require(result.path.empty(), "failed result exposed a partial resource key");
}

void valid_resources() {
    accepts(url("web/index.html"), "web/index.html");
    accepts(url("web/pages/start%20page.html"), "web/pages/start page.html");
    accepts(url("web/%20leading.txt"), "web/ leading.txt");
    accepts(url("web/Case.Sensitive.css"), "web/Case.Sensitive.css");
    accepts(url("web/a%21%24%26%27%28%29%2B%2C%3B%3D%40%5B%5D.txt"), "web/a!$&'()+,;=@[].txt");
    accepts(url("web/a!$&'()+,;=@[].txt"), "web/a!$&'()+,;=@[].txt");
    accepts(url("web/%C3%A9.txt"), "web/\xc3\xa9.txt");
    accepts(url("web/%c3%a9.txt"), "web/\xc3\xa9.txt");
    accepts(url("web/%E2%82%AC.txt"), "web/\xe2\x82\xac.txt");
    accepts(url("web/%F0%9F%98%80.png"), "web/\xf0\x9f\x98\x80.png");
    accepts(url("web/e%CC%81.js"), "web/e\xcc\x81.js");
    accepts(url("web/\xc3\xa9.txt"), "web/\xc3\xa9.txt");
    accepts(url("web/conductor.txt"), "web/conductor.txt");
    accepts(url("web/com0.txt"), "web/com0.txt");
    accepts(url("web/com10.txt"), "web/com10.txt");
    accepts(url("web/a...b"), "web/a...b");
    accepts(url("web/a-b_~.js"), "web/a-b_~.js");
    // These are final WTF-resolved URLs. An HTML ../ reference within /web/
    // can legitimately produce them; no raw-source provenance is asserted.
    accepts(url("web/style.css"), "web/style.css");
    auto original = url("web/owned.txt");
    const auto owned = normalize_app_resource_url(original, pin);
    original.assign(original.size(), 'x');
    require(owned.path == "web/owned.txt", "result borrowed caller storage");
}

void suffix_policy() {
    accepts(url("web/index.html?cache=1#section"), "web/index.html");
    accepts(url("web/index.html#fragment?not-a-query"), "web/index.html");
    accepts(url("web/a?binary/application.wasm"), "web/a");
    accepts(url("web/a#../outside"), "web/a");
    accepts(url("web/a?ignored=%2F%25%GG#file:///tmp/secret"), "web/a");
    rejects(url("web/a%3Fb"));
    rejects(url("web/a%23b"));
    rejects(url("web/a?line\nbreak"));
    auto nul_query = url("web/a?x=");
    nul_query.push_back('\0');
    rejects(nul_query);
}

void authorities() {
    for (const auto prefix : {"", "app:/", "app:", "APP://", "https://", "file://", "//"})
        rejects(std::string(prefix) + std::string(pin) + "/web/a");
    rejects("web/a");
    rejects("app://" + std::string(pin));
    rejects("app://" + std::string(pin) + "?x=/web/a");
    rejects("app://" + std::string(pin) + "#x=/web/a");
    for (const auto host : {
        "", "short", "0123456789ABCDEF0123456789abcdef0123456789abcdef0123456789abcdef",
        "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdeg"})
        rejects("app://" + std::string(host) + "/web/a");
    rejects("app://" + std::string(pin) + "a/web/a");
    rejects("app://user@" + std::string(pin) + "/web/a");
    rejects("app://" + std::string(pin) + "@other/web/a");
    rejects("app://" + std::string(pin) + ":80/web/a");
    rejects("app://" + std::string(pin) + ".//web/a");
    rejects("app://%30" + std::string(pin.substr(1)) + "/web/a");
    const auto mismatch = normalize_app_resource_url("app://" + std::string(64, '0') + "/web/a", pin);
    require(mismatch.error == ResourceUrlError::origin_mismatch && mismatch.path.empty(), "origin mismatch classification");
    for (const auto expected : {"", "not-a-hash", "0123456789ABCDEF0123456789abcdef0123456789abcdef0123456789abcdef"}) {
        const auto result = normalize_app_resource_url(url("web/a"), expected);
        require(result.error == ResourceUrlError::invalid_authority && result.path.empty(), "invalid expected pin accepted");
    }
}

void bad_paths() {
    for (const auto path : {
        "", "web", "web/", "/web/a", "Web/a", "binary/application.wasm", "web/a/",
        "web//a", "web/./a", "web/../a", "web/a/.", "web/a/..", "web/a.", "web/a%20",
        "web/a b", "web/a:b", "web/a%3Ab", "web/a\\b", "web/a<b", "web/a>b", "web/a\"b",
        "web/a|b", "web/a*b", "web/CON", "web/con.html", "web/PrN.txt", "web/AUX", "web/nul.txt",
        "web/COM1", "web/cOm9.foo.bar", "web/LPT1", "web/lpt9.css", "web/con/a",
        "web/COM%C2%B9.txt", "web/CoM%C2%B2", "web/com%C2%B3.js",
        "web/LpT%C2%B9.txt", "web/lpt%C2%B2", "web/LPT%C2%B3.js",
        "web/a%3Cb", "web/a%3Eb", "web/a%22b", "web/a%7Cb", "web/a%2Ab"})
        rejects(url(path));
    const auto mixed_case = normalize_app_resource_url(url("web/Case.css"), pin);
    require(mixed_case.path != "web/case.css", "resource path was case folded");
}

void bad_encodings() {
    for (const auto path : {
        "web/%", "web/%0", "web/%GG", "web/%2f", "web/%2F", "web/%5c", "web/%5C",
        "web/%25", "web/%252e", "web/%252F", "web/%61", "web/%41", "web/%39", "web/%2d",
        "web/%2e", "web/%5F", "web/%7e", "web/%2e%2e/a", "web/%00", "web/%09",
        "web/%1F", "web/%7f", "web/%C2%80", "web/%C2%9F", "web/%80", "web/%C0%AF",
        "web/%E0%80%80", "web/%E2%82", "web/%ED%A0%80", "web/%F4%90%80%80", "web/%F5%80%80%80",
        "web/\x80", "web/\xc0\xaf", "web/\xed\xa0\x80", "web/\xf4\x90\x80\x80",
        "web/\xc2\x85", "web/\n", "web/\x7f"})
        rejects(url(path));
    auto with_nul = url("web/a");
    with_nul.push_back('\0');
    with_nul += "b";
    rejects(with_nul);
}

void bounds() {
    accepts(url("web/" + std::string(236, 'a')), "web/" + std::string(236, 'a'));
    const auto long_path = normalize_app_resource_url(url("web/" + std::string(237, 'a')), pin);
    require(long_path.error == ResourceUrlError::limit_exceeded && long_path.path.empty(), "241-byte resource key accepted");
    std::string deepest = "web";
    for (unsigned n = 0; n < 15; ++n) deepest += "/a";
    accepts(url(deepest), deepest);
    const auto depth = normalize_app_resource_url(url(deepest + "/a"), pin);
    require(depth.error == ResourceUrlError::limit_exceeded && depth.path.empty(), "17 path segments accepted");
    auto exact = url("web/a?");
    exact.append(4096 - exact.size(), 'q');
    accepts(exact, "web/a");
    const auto excess = normalize_app_resource_url(exact + "q", pin);
    require(excess.error == ResourceUrlError::limit_exceeded && excess.path.empty(), "oversized query ignored URL bound");
    std::string encoded = "web/", decoded = "web/";
    for (unsigned n = 0; n < 118; ++n) { encoded += "%C3%A9"; decoded += "\xc3\xa9"; }
    require(decoded.size() == 240, "UTF-8 boundary fixture size");
    accepts(url(encoded), decoded);
    const auto unicode_excess = normalize_app_resource_url(url(encoded + "%C3%A9"), pin);
    require(unicode_excess.error == ResourceUrlError::limit_exceeded && unicode_excess.path.empty(), "decoded UTF-8 bytes exceed bound");
}

} // namespace

int main() {
    try {
        valid_resources();
        suffix_policy();
        authorities();
        bad_paths();
        bad_encodings();
        bounds();
        std::cout << "resource URL helper: " << assertions << " assertions passed (no engine)\n";
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
