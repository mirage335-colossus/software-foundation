#include "foundation/appended/module.hpp"
#include "foundation/appended/registry.hpp"

#include <algorithm>
#include <array>
#include <fstream>
#include <iostream>
#include <iterator>
#include <stdexcept>
#include <string_view>

using namespace foundation::appended;
namespace {
void require(bool result, const char* text) {
    if (!result) throw std::runtime_error(text);
}
template<class Function> void rejects(Function function) {
    try { function(); }
    catch (const std::runtime_error&) { return; }
    throw std::runtime_error("expected module rejection");
}
void uleb(Bytes& output, std::uint32_t value) {
    do {
        auto next = static_cast<std::uint8_t>(value & 127u);
        value >>= 7;
        output.push_back(static_cast<std::uint8_t>(next | (value ? 128u : 0u)));
    } while (value);
}
void constant(Bytes& output, std::int32_t value) {
    output.push_back(0x41);
    bool more;
    do {
        auto next = static_cast<std::uint8_t>(value & 127);
        value >>= 7;
        more = !((value == 0 && !(next & 64)) || (value == -1 && (next & 64)));
        output.push_back(static_cast<std::uint8_t>(next | (more ? 128u : 0u)));
    } while (more);
}
void append(Bytes& target, const Bytes& input) { target.insert(target.end(), input.begin(), input.end()); }
void name(Bytes& target, std::string_view input) {
    uleb(target, static_cast<std::uint32_t>(input.size()));
    target.insert(target.end(), input.begin(), input.end());
}
void section(Bytes& module, std::uint8_t kind, const Bytes& input) {
    module.push_back(kind); uleb(module, static_cast<std::uint32_t>(input.size())); append(module, input);
}
struct Options {
    bool start{false}, wrong_signature{false}, forbidden_opcode{false};
    bool allocator_import{false}, grow{false}, recursive{false}, infinite{false}, dispatch_trap{false};
    bool shutdown_service{false};
    bool no_init_call{false};
    bool opaque_names{false};
    std::uint32_t allocation{1024};
    std::uint32_t free_locals{0}, free_blocks{0}, aliases{0};
};
Bytes fixture(const Bytes& request, Options options = {}) {
    Bytes module{0, 97, 115, 109, 1, 0, 0, 0};
    // Gateway, abi, alloc/step, free, init/dispatch, shutdown.
    section(module, 1, {6, 0x60,4,0x7f,0x7f,0x7f,0x7f,1,0x7f,
        0x60,0,1,0x7f, 0x60,1,0x7f,1,0x7f,
        0x60,2,0x7f,0x7f,0, 0x60,2,0x7f,0x7f,1,0x7f, 0x60,1,0x7f,0});
    Bytes imports{1}; name(imports, FOUNDATION_APPENDED_IMPORT_MODULE);
    name(imports, FOUNDATION_APPENDED_IMPORT_NAME); imports.push_back(0); imports.push_back(0);
    section(module, 2, imports);
    section(module, 3, {7, static_cast<std::uint8_t>(options.wrong_signature ? 2 : 1), 2,3,4,4,2,5});
    section(module, 5, {1,1,1,4});
    Bytes exports{8}; name(exports, "memory"); exports.push_back(2); exports.push_back(0);
    constexpr std::array names{"foundation_app_abi_v1", "foundation_app_alloc_v1",
        "foundation_app_free_v1", "foundation_app_init_v1", "foundation_app_dispatch_v1",
        "foundation_app_step_v1", "foundation_app_shutdown_v1"};
    for (std::size_t n = 0; n < names.size(); ++n) {
        name(exports, names[n]); exports.push_back(0); uleb(exports, static_cast<std::uint32_t>(n + 1));
    }
    section(module, 7, exports);
    if (options.start) section(module, 8, {7});
    std::array<Bytes, 7> code;
    constant(code[0], FOUNDATION_APPENDED_ABI_VERSION);
    if (options.allocator_import) {
        for (unsigned n = 0; n < 4; ++n) constant(code[1], 0);
        code[1].insert(code[1].end(), {0x10,0,0x1a});
    }
    if (options.grow) {
        constant(code[1], 1); code[1].insert(code[1].end(), {0x40,0,0x1a});
    }
    constant(code[1], static_cast<std::int32_t>(options.allocation));
    // Match SDK semantics: allocation of zero bytes returns zero.
    code[1].insert(code[1].begin(), {0x20,0,0x45,0x04,0x7f,0x41,0,0x05});
    code[1].push_back(0x0b);
    if (options.forbidden_opcode) code[2].push_back(0xc0);
    for (std::uint32_t n = 0; n < options.aliases; ++n) code[2].insert(code[2].end(), {0x20,0});
    if (options.aliases) code[2].insert(code[2].end(), {0x02,0x40,0x0b});
    for (std::uint32_t n = 0; n < options.aliases; ++n) code[2].push_back(0x1a);
    for (std::uint32_t n = 0; n < options.free_blocks; ++n)
        code[2].insert(code[2].end(), {0x02,0x40});
    for (std::uint32_t n = 0; n < options.free_blocks; ++n) code[2].push_back(0x0b);
    if (options.grow) {
        constant(code[3], 1); code[3].insert(code[3].end(), {0x40,0,0x1a});
    }
    if (options.no_init_call) constant(code[3], 0);
    else {
        constant(code[3], 256); constant(code[3], static_cast<std::int32_t>(request.size()));
        constant(code[3], 512); constant(code[3], 256); code[3].insert(code[3].end(), {0x10,0});
    }
    if (options.dispatch_trap) code[4].push_back(0x00);
    constant(code[4], 0);
    if (options.recursive) code[5].insert(code[5].end(), {0x20,0,0x10,6});
    else if (options.infinite) {
        code[5].insert(code[5].end(), {0x03,0x40,0x0c,0,0x0b}); constant(code[5], 0);
    } else constant(code[5], 0);
    if (options.shutdown_service) {
        constant(code[6], 768); constant(code[6], static_cast<std::int32_t>(request.size()));
        constant(code[6], 512); constant(code[6], 256);
        code[6].insert(code[6].end(), {0x10,0,0x1a});
    }
    Bytes bodies{7};
    for (std::size_t n = 0; n < code.size(); ++n) {
        Bytes body;
        if (n == 2 && options.free_locals) {
            body.push_back(1); uleb(body, options.free_locals); body.push_back(0x7f);
        } else body.push_back(0);
        append(body, code[n]); body.push_back(0x0b);
        uleb(bodies, static_cast<std::uint32_t>(body.size())); append(bodies, body);
    }
    section(module, 10, bodies);
    Bytes data{static_cast<std::uint8_t>(options.shutdown_service ? 2 : 1),0};
    constant(data, 256); data.push_back(0x0b);
    uleb(data, static_cast<std::uint32_t>(request.size())); append(data, request);
    if (options.shutdown_service) {
        auto second = request; second[FOUNDATION_APPENDED_OFFSET_SEQUENCE] = 2;
        data.push_back(0); constant(data, 768); data.push_back(0x0b);
        uleb(data, static_cast<std::uint32_t>(second.size())); append(data, second);
    }
    section(module, 11, data);
    if (options.opaque_names) section(module, 0, {4,'n','a','m','e',0xff});
    return module;
}
Bytes request(std::uint64_t generation, std::uint64_t handle) {
    Envelope envelope; envelope.generation = generation; envelope.sequence = 1;
    envelope.interface_handle = handle; envelope.operation = 1;
    Bytes result; require(encode_envelope(envelope, {}, result) == CodecStatus::ok, "fixture envelope");
    return result;
}
DiscoveryResult add(Registry& registry, unsigned& calls) {
    ServiceDescriptor descriptor; descriptor.name = "fixture.echo"; descriptor.max_reply_bytes = 1;
    descriptor.schema[0] = 1;
    auto result = registry.register_service(std::move(descriptor), [&calls](std::uint32_t operation,
        std::span<const std::uint8_t>, std::span<std::uint8_t> reply) {
        require(operation == 1, "service operation"); ++calls; reply[0] = 7;
        return ServiceReply{ServiceStatus::ok, 1};
    });
    require(result.status == ServiceStatus::ok, "fixture registration"); return result;
}
void successful(bool grow) {
    Registry registry(7); unsigned calls = 0;
    const auto service = add(registry, calls);
    Options options; options.grow = grow; options.shutdown_service = true;
    if (grow) options.allocation = 65536;
    auto bytes = fixture(request(7, service.handle), options);
    Module module(bytes, registry);
    std::fill(bytes.begin(), bytes.end(), 0xff); // The instance owns its source bytes.
    require(calls == 0, "load invoked application service");
    require(module.initialize() == 0 && calls == 1, "guest did not invoke host service");
    rejects([&] { module.initialize(); });
    require(module.dispatch({}) == 0 && module.step(100) == 0, "guest dispatch or step");
    module.shutdown(); require(registry.closed(), "shutdown retained registry");
    require(calls == 1, "shutdown started new service work");
    rejects([&] { module.step(1); });
}
} // namespace

int main(int argc, char** argv) {
    try {
        if (argc == 2) {
            std::ifstream input(argv[1], std::ios::binary);
            if (!input) throw std::runtime_error("cannot read external profile fixture");
            const Bytes bytes{std::istreambuf_iterator<char>(input), std::istreambuf_iterator<char>()};
            Registry registry(7); Module module(bytes, registry);
            std::cout << "external module profile accepted\n";
            return 0;
        }
        successful(false); successful(true);
        {
            Limits limits; limits.max_message_bytes = FOUNDATION_APPENDED_ENVELOPE_BYTES;
            Registry registry(7, limits); Options options; options.no_init_call = true;
            Module module(fixture(request(7, 1), options), registry);
            require(module.initialize() == 0, "small message limit blocked initialization context");
            require(module.dispatch({}) == 0, "empty dispatch failed");
        }
        for (unsigned n = 0; n < 4; ++n) {
            Registry registry(7); Options options;
            if (n < 2) options.free_locals = n == 0 ? 1022 : 1023; // Plus two parameters.
            else options.free_blocks = n == 2 ? 511 : 512; // Plus the function frame.
            if (n % 2 == 0) { Module module(fixture(request(7, 1), options), registry); }
            else rejects([&] { Module module(fixture(request(7, 1), options), registry); });
        }
        for (const auto aliases : {255u, 256u, 1024u, 1025u}) {
            Registry registry(7); unsigned calls = 0; const auto service = add(registry, calls);
            Options options; options.aliases = aliases; options.opaque_names = true;
            if (aliases <= 1024) {
                Module module(fixture(request(7, service.handle), options), registry);
                require(module.initialize() == 0 && calls == 1, "alias capacity or opaque metadata");
            } else rejects([&] { Module module(fixture(request(7, service.handle), options), registry); });
        }
        for (unsigned n = 0; n < 3; ++n) {
            Registry registry(7); unsigned calls = 0; const auto service = add(registry, calls);
            Options options; options.start = n == 0; options.wrong_signature = n == 1; options.forbidden_opcode = n == 2;
            rejects([&] { Module module(fixture(request(7, service.handle), options), registry); });
            require(calls == 0 && registry.closed(), "invalid module had effects");
        }
        for (unsigned n = 0; n < 3; ++n) {
            Registry registry(7); unsigned calls = 0; const auto service = add(registry, calls);
            Options options;
            if (n == 0) options.allocation = 1025;
            if (n == 1) options.allocation = 65520;
            if (n == 2) options.allocator_import = true;
            Module module(fixture(request(7, service.handle), options), registry);
            rejects([&] { module.initialize(); });
            require(calls == 0 && registry.closed(), "invalid allocation had effects");
        }
        for (unsigned n = 0; n < 3; ++n) {
            Registry registry(7); unsigned calls = 0; const auto service = add(registry, calls);
            Options options; options.dispatch_trap = n == 0; options.recursive = n == 1; options.infinite = n == 2;
            Module module(fixture(request(7, service.handle), options), registry);
            require(module.initialize() == 0, "trap fixture initialization");
            rejects([&] { if (n == 0) module.dispatch({}); else module.step(100); });
            require(calls == 1 && registry.closed(), "trap did not close instance");
        }
        std::cout << "appended module native/interpreter contract passed\n";
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n'; return 1;
    }
}
