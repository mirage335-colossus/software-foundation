#include <foundation/store.hpp>
#include <foundation/version.hpp>
#include <string_view>

int main() {
    foundation::Store store;
    const auto id = store.add("External consumer");
    return store.get(id)->text == "External consumer" &&
        std::string_view(FOUNDATION_VERSION) == "0.1.0" ? 0 : 1;
}
