#include "foundation/appended/module.hpp"
#include "foundation/appended/registry.hpp"

#include "wasm3.h"

#include <algorithm>
#include <array>
#include <cstring>
#include <limits>
#include <map>
#include <stdexcept>
#include <string>
#include <string_view>
#include <vector>

namespace foundation::appended {
namespace {
constexpr std::size_t max_module_bytes = 4 * 1024 * 1024;
constexpr std::uint32_t max_memory_pages = 256;
constexpr std::uint32_t max_table_elements = 8192;
constexpr std::uint64_t invocation_gas = 10000000;
constexpr std::uint32_t init_context_bytes = 128;
constexpr std::uint32_t max_function_locals = 1024;
constexpr std::uint32_t max_total_locals = 1048576;

[[noreturn]] void invalid(std::string_view message) {
    throw std::runtime_error("foundation-guest-v1: " + std::string(message));
}

/* This check runs on the actual supplied bytes, independently of a packaging
 * manifest. It enforces the format/feature contract; wasm3's enabled validator
 * checks instruction types and indexes when every body is compiled below. */
struct Reader {
    std::span<const std::uint8_t> bytes;
    std::size_t cursor{0};
    bool empty() const noexcept { return cursor == bytes.size(); }
    std::uint8_t byte() {
        if (empty()) invalid("truncated module");
        return bytes[cursor++];
    }
    std::span<const std::uint8_t> take(std::size_t count) {
        if (count > bytes.size() - cursor) invalid("truncated section");
        auto result = bytes.subspan(cursor, count);
        cursor += count;
        return result;
    }
    std::uint32_t u32() {
        std::uint32_t value = 0;
        for (unsigned shift = 0; shift < 35; shift += 7) {
            const auto next = byte();
            if (shift == 28 && (next & 0xf0u)) invalid("u32 LEB overflow");
            value |= std::uint32_t(next & 0x7fu) << shift;
            if (!(next & 0x80u)) {
                if (shift && next == 0) invalid("nonminimal u32 LEB");
                return value;
            }
        }
        invalid("unterminated u32 LEB");
    }
    void signed_leb(unsigned bits) {
        const auto count = (bits + 6) / 7;
        std::uint8_t previous = 0;
        for (unsigned n = 0; n < count; ++n) {
            const auto next = byte();
            if (n + 1 == count) {
                const auto used = bits - 7 * n;
                const auto mask = std::uint8_t(0x7fu & ~((1u << used) - 1));
                const bool negative = next & (1u << (used - 1));
                if ((next & 0x80u) || (next & mask) != (negative ? mask : 0))
                    invalid("signed LEB overflow");
            }
            if (!(next & 0x80u)) {
                if (n && ((next == 0 && !(previous & 0x40u)) ||
                          (next == 0x7f && (previous & 0x40u)))) invalid("nonminimal signed LEB");
                return;
            }
            previous = next;
        }
        invalid("unterminated signed LEB");
    }
    std::string name() {
        const auto value = take(count(1024));
        if (!valid_utf8(value) || std::find(value.begin(), value.end(), 0) != value.end())
            invalid("invalid name encoding");
        return {reinterpret_cast<const char*>(value.data()), value.size()};
    }
    std::uint32_t count(std::uint32_t maximum) {
        const auto value = u32();
        if (value > maximum) invalid("section count exceeds profile limit");
        return value;
    }
    void done() { if (!empty()) invalid("trailing section bytes"); }
};

bool scalar(std::uint8_t type) noexcept { return type >= 0x7c && type <= 0x7f; }
struct Signature {
    std::vector<std::uint8_t> args;
    std::vector<std::uint8_t> results;
};
void constant(Reader& reader, bool offset = false) {
    const auto opcode = reader.byte();
    if (opcode == 0x41) reader.signed_leb(32);
    else if (!offset && opcode == 0x42) reader.signed_leb(64);
    else if (!offset && opcode == 0x43) reader.take(4);
    else if (!offset && opcode == 0x44) reader.take(8);
    else invalid("unsupported constant expression");
    if (reader.byte() != 0x0b) invalid("constant expression has no end");
}
void instructions(Reader& reader) {
    while (!reader.empty()) {
        const auto opcode = reader.byte();
        if (opcode == 0x02 || opcode == 0x03 || opcode == 0x04) {
            const auto block = reader.byte();
            if (block != 0x40 && !scalar(block)) invalid("multi-value block type");
        } else if (opcode == 0x0c || opcode == 0x0d || opcode == 0x10 ||
                   (opcode >= 0x20 && opcode <= 0x24)) {
            reader.u32();
        } else if (opcode == 0x0e) {
            const auto count = reader.count(65536);
            for (std::uint32_t n = 0; n < count; ++n) reader.u32();
            reader.u32();
        } else if (opcode == 0x11) {
            reader.u32();
            if (reader.byte() != 0) invalid("non-MVP indirect call");
        } else if (opcode >= 0x28 && opcode <= 0x3e) {
            reader.u32(); reader.u32();
        } else if (opcode == 0x3f || opcode == 0x40) {
            if (reader.byte() != 0) invalid("non-MVP memory instruction");
        } else if (opcode == 0x41) reader.signed_leb(32);
        else if (opcode == 0x42) reader.signed_leb(64);
        else if (opcode == 0x43) reader.take(4);
        else if (opcode == 0x44) reader.take(8);
        else if (opcode == 0x00 || opcode == 0x01 || opcode == 0x05 ||
                 opcode == 0x0b || opcode == 0x0f || opcode == 0x1a ||
                 opcode == 0x1b || (opcode >= 0x45 && opcode <= 0xbf)) {}
        else invalid("instruction outside MVP scalar profile");
    }
}
void limits(Reader& reader, std::uint32_t maximum) {
    if (reader.u32() != 1) invalid("finite unshared limits required");
    const auto initial = reader.u32();
    const auto limit = reader.u32();
    if (initial > limit || limit > maximum) invalid("limits exceed profile");
}

bool preflight(std::span<const std::uint8_t> bytes) {
    if (bytes.size() < 8 || bytes.size() > max_module_bytes) invalid("module size");
    constexpr std::array<std::uint8_t, 8> header{0, 97, 115, 109, 1, 0, 0, 0};
    if (!std::equal(header.begin(), header.end(), bytes.begin())) invalid("module header");
    Reader module{bytes.subspan(8)};
    std::uint8_t previous = 0;
    std::vector<Signature> types;
    std::vector<std::uint32_t> functions;
    std::map<std::string, std::pair<std::uint8_t, std::uint32_t>> exports;
    std::uint32_t imports = 0, memories = 0, bodies = 0, total_locals = 0;
    while (!module.empty()) {
        const auto id = module.byte();
        Reader section{module.take(module.u32())};
        if (id == 0) { section.name(); continue; }
        if (id <= previous || id > 11 || id == 8) invalid("section order, start or unsupported section");
        previous = id;
        const auto count = section.count(id == 5 ? 1 : 65536);
        if ((id == 3 || id == 10) && count > 16384) invalid("too many functions");
        if (id == 1) {
            if (count > 4096) invalid("too many function types");
            for (std::uint32_t n = 0; n < count; ++n) {
                if (section.byte() != 0x60) invalid("function type required");
                Signature type;
                for (auto left = section.count(64); left; --left) {
                    const auto value = section.byte();
                    if (!scalar(value)) invalid("non-scalar parameter");
                    type.args.push_back(value);
                }
                for (auto left = section.count(1); left; --left) {
                    const auto value = section.byte();
                    if (!scalar(value)) invalid("non-scalar result");
                    type.results.push_back(value);
                }
                types.push_back(std::move(type));
            }
        } else if (id == 2) {
            imports = count;
            if (count > 1) invalid("at most one kernel import required");
            if (!count) { section.done(); continue; }
            if (section.name() != FOUNDATION_APPENDED_IMPORT_MODULE ||
                section.name() != FOUNDATION_APPENDED_IMPORT_NAME || section.byte() != 0)
                invalid("foreign import");
            const auto type = section.u32();
            if (type >= types.size() || types[type].args != std::vector<std::uint8_t>(4, 0x7f) ||
                types[type].results != std::vector<std::uint8_t>(1, 0x7f)) invalid("kernel import signature");
            functions.push_back(type);
        } else if (id == 3) {
            for (std::uint32_t n = 0; n < count; ++n) functions.push_back(section.u32());
        } else if (id == 4) {
            if (count > 1) invalid("multiple tables");
            if (count) {
                if (section.byte() != 0x70) invalid("non-MVP table");
                limits(section, max_table_elements);
            }
        } else if (id == 5) {
            memories = count;
            if (count != 1) invalid("one defined memory required");
            limits(section, max_memory_pages);
        } else if (id == 6) {
            for (std::uint32_t n = 0; n < count; ++n) {
                if (!scalar(section.byte()) || section.byte() > 1) invalid("global type");
                constant(section);
            }
        } else if (id == 7) {
            for (std::uint32_t n = 0; n < count; ++n) {
                auto name = section.name();
                const auto kind = section.byte();
                const auto index = section.u32();
                if (!exports.emplace(std::move(name), std::pair{kind, index}).second)
                    invalid("duplicate export");
            }
        } else if (id == 9) {
            for (std::uint32_t n = 0; n < count; ++n) {
                if (section.u32() != 0) invalid("non-MVP element segment");
                constant(section, true);
                for (auto left = section.count(max_table_elements); left; --left) section.u32();
            }
        } else if (id == 10) {
            bodies = count;
            if (std::size_t(count) + imports != functions.size()) invalid("function body count");
            for (std::uint32_t n = 0; n < count; ++n) {
                Reader body{section.take(section.u32())};
                const auto type = functions[imports + n];
                if (type >= types.size()) invalid("function type index");
                auto locals = static_cast<std::uint32_t>(types[type].args.size());
                for (auto left = body.count(max_function_locals); left; --left) {
                    const auto number = body.count(max_function_locals);
                    if (number > max_function_locals - locals || number > max_total_locals - total_locals ||
                        !scalar(body.byte())) invalid("local declaration");
                    locals += number;
                    total_locals += number;
                }
                if (body.empty() || body.bytes.back() != 0x0b) invalid("function has no end");
                instructions(body);
            }
        } else if (id == 11) {
            for (std::uint32_t n = 0; n < count; ++n) {
                if (section.u32() != 0) invalid("non-MVP data segment");
                constant(section, true);
                section.take(section.u32());
            }
        }
        section.done();
    }
    if (memories != 1 || functions.size() > 16384 ||
        bodies + imports != functions.size() || exports.size() != 8)
        invalid("incomplete ABI module");
    const auto memory = exports.find("memory");
    if (memory == exports.end() || memory->second != std::pair<std::uint8_t, std::uint32_t>{2, 0})
        invalid("memory export");
    struct Required { const char* name; unsigned args; unsigned results; };
    constexpr Required required[]{
        {"foundation_app_abi_v1", 0, 1}, {"foundation_app_alloc_v1", 1, 1},
        {"foundation_app_free_v1", 2, 0}, {"foundation_app_init_v1", 2, 1},
        {"foundation_app_dispatch_v1", 2, 1}, {"foundation_app_step_v1", 1, 1},
        {"foundation_app_shutdown_v1", 1, 0}};
    for (const auto& expected : required) {
        const auto found = exports.find(expected.name);
        if (found == exports.end() || found->second.first != 0 || found->second.second < imports ||
            found->second.second >= functions.size()) invalid("required function export");
        const auto type = functions[found->second.second];
        if (type >= types.size() || types[type].args != std::vector<std::uint8_t>(expected.args, 0x7f) ||
            types[type].results != std::vector<std::uint8_t>(expected.results, 0x7f)) invalid("export signature");
    }
    return imports != 0;
}

Bytes execution_copy(std::span<const std::uint8_t> input) {
    Bytes result(input.begin(), input.begin() + 8);
    Reader reader{input.subspan(8)};
    while (!reader.empty()) {
        const auto start = reader.cursor;
        const auto kind = reader.byte();
        const auto payload = reader.take(reader.u32());
        if (kind == 0) {
            Reader custom{payload};
            /* A custom payload is opaque in this profile. wasm3 parses debug
             * name subsections, so omit that optional metadata only in its
             * private execution copy. Original payload/container bytes remain
             * unchanged; the complete input has already passed preflight. */
            if (custom.name() == "name") continue;
        }
        const auto section = reader.bytes.subspan(start, reader.cursor - start);
        result.insert(result.end(), section.begin(), section.end());
    }
    return result;
}

void checked(M3Result result) {
    if (result) throw std::runtime_error("appended runtime: " + std::string(result));
}
} // namespace

struct Module::Impl {
    Registry& registry;
    Bytes bytes;
    IM3Environment environment{};
    IM3Runtime runtime{};
    IM3Module module{};
    std::array<IM3Function, 7> functions{};
    bool attempted{false}, initialized{false}, closed{false}, services{false};
    bool forbidden_import{false}, stopping{false};
    bool active{false}, in_initialization{false}, shutdown_requested{false};
    std::uint32_t shutdown_reason{0};
    struct Entry {
        Impl& self;
        explicit Entry(Impl& instance, bool initialization = false) : self(instance) {
            self.active = true; self.in_initialization = initialization;
        }
        ~Entry() {
            self.active = false; self.in_initialization = false;
            if (self.shutdown_requested && !self.closed) self.shutdown_now(self.shutdown_reason);
        }
    };
    void shutdown_now(std::uint32_t reason) noexcept {
        if (closed) return;
        active = true; stopping = true; shutdown_requested = false;
        if (initialized) {
            try {
                services = true;
                const std::array arguments{reason};
                invoke(6, arguments);
            } catch (...) {}
        }
        fail(); active = false; in_initialization = false;
    }

    explicit Impl(Registry& value) : registry(value) {}
    ~Impl() { release_runtime(); }
    void release_runtime() noexcept {
        if (runtime) m3_FreeRuntime(runtime);
        if (environment) m3_FreeEnvironment(environment);
        runtime = nullptr; environment = nullptr; module = nullptr;
        functions.fill(nullptr);
        Bytes{}.swap(bytes);
    }
    std::span<std::uint8_t> memory() {
        std::size_t size = 0;
        auto* data = m3_GetMemory(module, &size, 0);
        if (!data || size > std::size_t(max_memory_pages) * 65536) invalid("runtime memory");
        return {data, size};
    }
    static const void* gateway(IM3Runtime runtime, IM3ImportContext, std::uint64_t* stack, void*) noexcept {
        auto& self = *static_cast<Impl*>(m3_GetUserData(runtime));
        const auto request = static_cast<std::uint32_t>(stack[1]);
        const auto length = static_cast<std::uint32_t>(stack[2]);
        const auto reply = static_cast<std::uint32_t>(stack[3]);
        const auto capacity = static_cast<std::uint32_t>(stack[4]);
        auto status = TransportStatus::internal_error;
        if (self.services && !self.closed) {
            std::size_t size = 0;
            auto* data = m3_GetMemory(self.module, &size, 0);
            if (data && size <= std::size_t(max_memory_pages) * 65536) {
                bool allowed = true;
                if (self.stopping) {
                    Envelope envelope;
                    std::span<const std::uint8_t> payload;
                    allowed = request <= size && length <= size - request &&
                        decode_envelope({data + request, length}, envelope, payload) == CodecStatus::ok &&
                        envelope.interface_handle == FOUNDATION_APPENDED_BOOTSTRAP_HANDLE &&
                        (envelope.operation == FOUNDATION_APPENDED_CONTROL_RESULT_RELEASE ||
                         envelope.operation == FOUNDATION_APPENDED_CONTROL_ACKNOWLEDGE);
                }
                if (allowed) status = self.registry.call({data, size}, request, length, reply, capacity);
            }
        } else self.forbidden_import = true;
        stack[0] = static_cast<std::uint32_t>(status);
        return m3Err_none;
    }
    void load(std::span<const std::uint8_t> input) {
        const bool imports_gateway = preflight(input);
        bytes = execution_copy(input);
        environment = m3_NewEnvironment();
        if (!environment) invalid("environment allocation");
        runtime = m3_NewRuntime(environment, 256 * 1024, this);
        if (!runtime) invalid("runtime allocation");
        checked(m3_SetResourceLimit(runtime, c_m3Limit_MemoryBytes, std::uint64_t(max_memory_pages) * 65536));
        checked(m3_SetResourceLimit(runtime, c_m3Limit_TableElements, max_table_elements));
        checked(m3_SetResourceLimit(runtime, c_m3Limit_GasUnits, invocation_gas));
        checked(m3_ParseModule(environment, &module, bytes.data(), static_cast<std::uint32_t>(bytes.size())));
        /* m3_LoadModule owns the parsed module on either outcome. */
        checked(m3_LoadModule(runtime, module));
        if (imports_gateway)
            checked(m3_LinkRawFunction(module, FOUNDATION_APPENDED_IMPORT_MODULE,
                                      FOUNDATION_APPENDED_IMPORT_NAME, "i(iiii)", gateway));
        checked(m3_CompileModule(module));
        constexpr const char* names[]{"foundation_app_abi_v1", "foundation_app_alloc_v1",
            "foundation_app_free_v1", "foundation_app_init_v1", "foundation_app_dispatch_v1",
            "foundation_app_step_v1", "foundation_app_shutdown_v1"};
        for (std::size_t n = 0; n < functions.size(); ++n)
            checked(m3_FindFunctionIn(&functions[n], module, names[n]));
        if (invoke(0, {}) != FOUNDATION_APPENDED_ABI_VERSION) invalid("ABI version");
    }
    std::uint32_t invoke(std::size_t index, std::span<const std::uint32_t> args) {
        checked(m3_SetResourceLimit(runtime, c_m3Limit_GasUnits, invocation_gas));
        const void* pointers[2]{};
        for (std::size_t n = 0; n < args.size(); ++n) pointers[n] = &args[n];
        checked(m3_Call(functions[index], static_cast<std::uint32_t>(args.size()), pointers));
        if (forbidden_import) invalid("service import during ABI query or allocation");
        std::uint32_t result = 0;
        if (index != 2 && index != 6) checked(m3_GetResultsV(functions[index], &result));
        return result;
    }
    std::uint32_t buffer_call(std::size_t index, std::span<const std::uint8_t> input) {
        if (index == 3) {
            if (input.size() != init_context_bytes) invalid("initialization context size");
        } else if (input.size() > registry.limits().max_message_bytes) invalid("input exceeds message limit");
        const auto size = static_cast<std::uint32_t>(input.size());
        const auto allocated_bytes = std::max(size, std::uint32_t{1});
        const std::array allocation{allocated_bytes};
        services = false;
        const auto offset = invoke(1, allocation);
        auto lease = memory();
        if (!offset || offset % 16 || offset > lease.size() || allocated_bytes > lease.size() - offset)
            invalid("guest allocation");
        if (size) std::memcpy(lease.data() + offset, input.data(), size);
        services = true;
        const std::array arguments{offset, size};
        const auto result = invoke(index, arguments);
        services = false;
        const std::array release{offset, allocated_bytes};
        invoke(2, release);
        return result;
    }
    void fail() noexcept {
        services = false; closed = true; initialized = false;
        registry.close();
        release_runtime();
    }
};

Module::Module(std::span<const std::uint8_t> bytes, Registry& registry)
    : impl_(std::make_unique<Impl>(registry)) {
    try {
        if (registry.closed()) invalid("registry is closed");
        impl_->load(bytes);
    } catch (...) { impl_->fail(); throw; }
}
Module::~Module() { shutdown(); }
std::uint32_t Module::initialize() {
    auto& self = *impl_;
    if (self.active) invalid("recursive module invocation");
    if (self.attempted || self.closed) invalid("initialization already attempted");
    Impl::Entry entry(self, true);
    self.attempted = true;
    try {
        Bytes context;
        if (encode_init_context(self.registry.generation(), self.registry.limits(), context) != CodecStatus::ok)
            invalid("initialization context");
        const auto result = self.buffer_call(3, context);
        if (result > FOUNDATION_APPENDED_APP_EXHAUSTED) invalid("reserved initialization status");
        if (result) self.fail();
        else self.initialized = true;
        return result;
    } catch (...) { self.fail(); throw; }
}
std::uint32_t Module::dispatch(std::span<const std::uint8_t> input) {
    auto& self = *impl_;
    if (self.active) invalid("recursive module invocation");
    if (!self.initialized || self.closed) invalid("instance is not initialized");
    Impl::Entry entry(self);
    try {
        const auto result = self.buffer_call(4, input);
        if (result > FOUNDATION_APPENDED_APP_EXHAUSTED) invalid("reserved dispatch status");
        if (result) self.fail();
        return result;
    } catch (...) { self.fail(); throw; }
}
std::uint32_t Module::step(std::uint32_t budget_units) {
    auto& self = *impl_;
    if (self.active) invalid("recursive module invocation");
    if (!self.initialized || self.closed) invalid("instance is not initialized");
    Impl::Entry entry(self);
    try {
        self.services = true;
        const std::array arguments{budget_units};
        const auto result = self.invoke(5, arguments);
        self.services = false;
        if (result > FOUNDATION_APPENDED_STEP_EXHAUSTED) invalid("reserved step status");
        if (result >= FOUNDATION_APPENDED_STEP_FAILED) self.fail();
        return result;
    } catch (...) { self.fail(); throw; }
}
void Module::shutdown(std::uint32_t reason) noexcept {
    auto& self = *impl_;
    if (self.closed) return;
    if (self.active) {
        self.shutdown_requested = true; self.shutdown_reason = reason; return;
    }
    self.shutdown_now(reason);
}
bool Module::invocation_active() const noexcept { return impl_->active; }
bool Module::initializing() const noexcept { return impl_->active && impl_->in_initialization; }
bool Module::initialized() const noexcept { return impl_->initialized && !impl_->closed; }
bool Module::closed() const noexcept { return impl_->closed; }
bool Module::uses_registry(const Registry& value) const noexcept { return &impl_->registry == &value; }
} // namespace foundation::appended
