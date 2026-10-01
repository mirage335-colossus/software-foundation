#include "host/browser.hpp"
#include "shared/application.hpp"
#include "host/qualification.hpp"
#include <iostream>

int main(int argc, char** argv) {
    try {
        if (foundation::host::smoke_requested(argc, argv)) {
            foundation::host::Browser<foundation::ui::Application> runtime("qualification");
            std::uint64_t sequence = 0;
            runtime.application().qualify([&] {
                using namespace gui::web_detail;
                const auto response = Parser(runtime.receive(encode(Json::Object{
                    {"epoch", "qualification"}, {"seq", std::to_string(++sequence)},
                    {"operation", Json::Object{{"type", "poll"}}}}))).parse();
                if (!response.at("error").str().empty() || response.at("ack").str() != std::to_string(sequence) ||
                    response.at("snapshot").at("revision").str() != std::to_string(runtime.adapter.snapshot().revision))
                    throw std::runtime_error("Browser transport lost presentation");
            });
            return foundation::host::finish_smoke(runtime.application(), runtime.adapter);
        }
        if (argc > 2) throw std::invalid_argument("Usage: foundation-gui-web [SESSION|--smoke-test|--self-check]");
        foundation::host::Browser<foundation::ui::Application> runtime(argc > 1 ? argv[1] : "stdio-session");
        std::cout << runtime.initial() << '\n' << std::flush;
        std::string line; char byte; bool oversized = false;
        while (std::cin.get(byte)) {
            if (byte == '\n') {
                std::cout << runtime.receive(oversized ? std::string_view{} : std::string_view{line}) << '\n' << std::flush;
                line.clear(); oversized = false;
            } else if (line.size() < 1024 * 1024) line += byte;
            else oversized = true;
        }
    } catch (const std::exception& error) { std::cerr << error.what() << '\n'; return 1; }
}
