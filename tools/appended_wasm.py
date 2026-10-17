#!/usr/bin/env python3
"""Bounded, fail-closed validation of the ``foundation-guest-v1`` profile.

This is a validator, not a byte-pattern feature detector. It checks the complete
core module, instruction immediates, indices and operand/control stack types.
The supported language is core Wasm version 1 (MVP scalar instructions), mutable
defined globals and at most one MVP funcref table. Proposal instructions, typed
block signatures, imported memories/tables/globals, start functions, passive
segments and WASI are excluded. All integer encodings must be minimal LEB128.
Names must be valid UTF-8 without NUL. Custom section payloads are opaque data,
not instructions.

The profile deliberately requires statically in-bounds active data/element
segments, a finite memory maximum of 256 pages, and the scalar application ABI.
Resource limits below are part of the accepted profile, not a general-purpose
Wasm engine's limits. Compiler helpers must audit their final linked bytes here.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass


PROFILE = "foundation-guest-v1"
MAX_MODULE_BYTES = 4 * 1024 * 1024
MAX_MEMORY_PAGES = 256
MAX_TABLE_ELEMENTS = 8192
MAX_VECTOR_ITEMS = 65536
MAX_FUNCTIONS = 16384
MAX_TYPES = 4096
MAX_EXPORTS = 4096
MAX_NAME_BYTES = 1024
MAX_LOCALS = 1024
MAX_TOTAL_LOCALS = 1024 * 1024
MAX_CONTROL_DEPTH = 512
MAX_OPERAND_STACK = 1024
SCALAR_TYPES = {0x7F: "i32", 0x7E: "i64", 0x7D: "f32", 0x7C: "f64"}
REQUIRED_EXPORTS = {
    "foundation_app_abi_v1": ((), ("i32",)),
    "foundation_app_alloc_v1": (("i32",), ("i32",)),
    "foundation_app_free_v1": (("i32", "i32"), ()),
    "foundation_app_init_v1": (("i32", "i32"), ("i32",)),
    "foundation_app_dispatch_v1": (("i32", "i32"), ("i32",)),
    "foundation_app_step_v1": (("i32",), ("i32",)),
    "foundation_app_shutdown_v1": (("i32",), ()),
}
IMPORT_SIGNATURE = (("i32",) * 4, ("i32",))


class WasmError(ValueError):
    """The bytes are malformed or outside the portable guest profile."""


class _Reader:
    def __init__(self, data: bytes, context: str = "module", base: int = 0):
        self.data = data
        self.pos = 0
        self.context = context
        self.base = base

    def fail(self, message: str):
        raise WasmError(f"{self.context} at byte {self.base + self.pos}: {message}")

    def take(self, count: int) -> bytes:
        if count < 0 or count > len(self.data) - self.pos:
            self.fail("truncated bytes or invalid length")
        result = self.data[self.pos:self.pos + count]
        self.pos += count
        return result

    def byte(self) -> int:
        if self.pos >= len(self.data):
            self.fail("unexpected end of bytes")
        result = self.data[self.pos]
        self.pos += 1
        return result

    def leb(self, bits: int = 32, signed: bool = False) -> int:
        start = self.pos
        result = 0
        shift = 0
        for _ in range((bits + 6) // 7):
            value = self.byte()
            result |= (value & 0x7F) << shift
            shift += 7
            if not value & 0x80:
                if signed and value & 0x40:
                    result -= 1 << shift
                lower = -(1 << (bits - 1)) if signed else 0
                upper = (1 << (bits - 1)) - 1 if signed else (1 << bits) - 1
                if not lower <= result <= upper:
                    self.fail("LEB integer exceeds its declared width")
                encoded = bytearray()
                remaining = result
                while True:
                    part = remaining & 0x7F
                    remaining >>= 7
                    done = (remaining == 0 and (not signed or not part & 0x40)) or (
                        signed and remaining == -1 and bool(part & 0x40))
                    encoded.append(part if done else part | 0x80)
                    if done:
                        break
                if self.data[start:self.pos] != bytes(encoded):
                    self.fail("noncanonical LEB integer")
                return result
        self.fail("unterminated or oversized LEB integer")

    def count(self, limit: int = MAX_VECTOR_ITEMS) -> int:
        count = self.leb()
        if count > limit:
            self.fail(f"vector exceeds profile limit {limit}")
        return count

    def name(self) -> str:
        count = self.count(MAX_NAME_BYTES)
        try:
            result = self.take(count).decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            self.fail("invalid UTF-8 name")
        if "\x00" in result:
            self.fail("NUL is excluded from profile names")
        return result

    def scalar(self) -> str:
        value = self.byte()
        if value not in SCALAR_TYPES:
            self.fail("unsupported non-scalar value type")
        return SCALAR_TYPES[value]

    def done(self):
        if self.pos != len(self.data):
            self.fail("trailing bytes")


@dataclass
class _Control:
    kind: str
    height: int
    results: tuple
    unreachable: bool = False
    has_else: bool = False

    @property
    def label(self):
        return () if self.kind == "loop" else self.results


class _Module:
    def __init__(self):
        self.types = []
        self.functions = []
        self.defined_functions = []
        self.imports = []
        self.globals = []
        self.memory = None
        self.table = None
        self.exports = {}
        self.total_locals = 0
        self.code_count = 0

    @staticmethod
    def index(reader: _Reader, collection, label: str):
        index = reader.leb()
        if index >= len(collection):
            reader.fail(f"{label} index out of range")
        return index

    @staticmethod
    def limits(reader: _Reader, memory: bool):
        flags = reader.leb()
        if flags not in (0, 1) or (memory and flags != 1):
            reader.fail("memory must have finite unshared wasm32 limits" if memory
                        else "unsupported table limits")
        if not memory and flags != 1:
            reader.fail("table must have finite limits")
        lower = reader.leb()
        upper = reader.leb() if flags == 1 else None
        cap = MAX_MEMORY_PAGES if memory else MAX_TABLE_ELEMENTS
        if lower > cap or (upper is not None and (upper < lower or upper > cap)):
            reader.fail("limits exceed the profile bound or maximum is below minimum")
        return {"minimum_pages" if memory else "minimum_elements": lower,
                "maximum_pages" if memory else "maximum_elements": upper}

    @staticmethod
    def constant(reader: _Reader, expected: str):
        opcode = reader.byte()
        if opcode == 0x41:
            actual, value = "i32", reader.leb(32, True)
        elif opcode == 0x42:
            actual, value = "i64", reader.leb(64, True)
        elif opcode in (0x43, 0x44):
            actual = "f32" if opcode == 0x43 else "f64"
            value = reader.take(4 if opcode == 0x43 else 8)
        else:
            reader.fail("initializer must contain one MVP scalar constant")
        if actual != expected or reader.byte() != 0x0B:
            reader.fail("initializer type mismatch or missing end")
        return value

    def section(self, number: int, r: _Reader):
        if number == 1:
            for _ in range(r.count(MAX_TYPES)):
                if r.byte() != 0x60:
                    r.fail("type must be an MVP function type")
                parameters = tuple(r.scalar() for _ in range(r.count(64)))
                results = tuple(r.scalar() for _ in range(r.count(1)))
                self.types.append((parameters, results))
        elif number == 2:
            for _ in range(r.count(1)):
                module, name, kind = r.name(), r.name(), r.byte()
                if (module, name, kind) != ("foundation.kernel.v1", "call", 0):
                    r.fail("only the foundation.kernel.v1.call function import is allowed")
                type_index = self.index(r, self.types, "import type")
                if self.types[type_index] != IMPORT_SIGNATURE:
                    r.fail("kernel call import signature must be (i32,i32,i32,i32)->i32")
                self.functions.append(type_index)
                self.imports.append({"module": module, "name": name,
                                     "parameters": list(IMPORT_SIGNATURE[0]), "results": ["i32"]})
        elif number == 3:
            for _ in range(r.count(MAX_FUNCTIONS)):
                index = self.index(r, self.types, "function type")
                self.defined_functions.append(index)
                self.functions.append(index)
            if len(self.functions) > MAX_FUNCTIONS:
                r.fail("too many total functions")
        elif number == 4:
            for _ in range(r.count(1)):
                if r.byte() != 0x70:
                    r.fail("only an MVP funcref table is supported")
                self.table = self.limits(r, False)
        elif number == 5:
            for _ in range(r.count(1)):
                self.memory = self.limits(r, True)
        elif number == 6:
            for _ in range(r.count()):
                scalar, mutable = r.scalar(), r.byte()
                if mutable not in (0, 1):
                    r.fail("invalid global mutability")
                self.constant(r, scalar)
                self.globals.append((scalar, mutable))
        elif number == 7:
            for _ in range(r.count(MAX_EXPORTS)):
                name, kind = r.name(), r.byte()
                if name in self.exports:
                    r.fail("duplicate export name")
                if kind == 0:
                    index = self.index(r, self.functions, "export function")
                    parameters, results = self.types[self.functions[index]]
                    value = {"kind": "function", "index": index,
                             "parameters": list(parameters), "results": list(results)}
                elif kind in (1, 2):
                    index = r.leb()
                    if index != 0 or (self.table if kind == 1 else self.memory) is None:
                        r.fail("export table/memory index out of range")
                    value = {"kind": "table" if kind == 1 else "memory", "index": index}
                elif kind == 3:
                    index = self.index(r, self.globals, "export global")
                    value = {"kind": "global", "index": index,
                             "type": self.globals[index][0], "mutable": bool(self.globals[index][1])}
                else:
                    r.fail("unsupported export kind")
                self.exports[name] = value
        elif number == 8:
            r.fail("start sections are forbidden; use explicit application initialization")
        elif number == 9:
            for _ in range(r.count()):
                if r.leb() != 0 or self.table is None:
                    r.fail("element segment requires the single defined MVP table")
                offset = self.constant(r, "i32") & 0xFFFFFFFF
                count = r.count()
                if offset > self.table["minimum_elements"] or count > self.table["minimum_elements"] - offset:
                    r.fail("active element segment exceeds initial table")
                for _ in range(count):
                    self.index(r, self.functions, "element function")
        elif number == 10:
            count = r.count(MAX_FUNCTIONS)
            if count != len(self.defined_functions):
                r.fail("function and code section counts differ")
            self.code_count = count
            for index in range(count):
                size = r.leb()
                base = r.base + r.pos
                body = _Reader(r.take(size), f"function {index}", base)
                self.body(body, self.types[self.defined_functions[index]])
                body.done()
        elif number == 11:
            for _ in range(r.count()):
                if r.leb() != 0 or self.memory is None:
                    r.fail("data segment requires the single defined MVP memory")
                offset = self.constant(r, "i32") & 0xFFFFFFFF
                size = r.leb()
                capacity = self.memory["minimum_pages"] * 65536
                if offset > capacity or size > capacity - offset:
                    r.fail("active data segment exceeds initial memory")
                r.take(size)
        else:
            r.fail("unknown or unsupported section")
        r.done()

    def body(self, r: _Reader, signature):
        parameters, results = signature
        locals_ = list(parameters)
        for _ in range(r.count(MAX_LOCALS)):
            count, scalar = r.count(MAX_LOCALS), r.scalar()
            if count > MAX_LOCALS - len(locals_):
                r.fail("too many function locals")
            self.total_locals += count
            if self.total_locals > MAX_TOTAL_LOCALS:
                r.fail("total locals exceed profile bound")
            locals_.extend([scalar] * count)
        stack = []
        controls = [_Control("function", 0, results)]

        def pop(expected=None):
            frame = controls[-1]
            if len(stack) == frame.height and frame.unreachable:
                return expected
            if len(stack) <= frame.height:
                r.fail("operand stack underflow")
            actual = stack.pop()
            if expected is not None and actual is not None and actual != expected:
                r.fail(f"operand type mismatch: expected {expected}, found {actual}")
            return actual

        def push(scalar):
            if len(stack) >= MAX_OPERAND_STACK:
                r.fail("operand stack exceeds profile bound")
            stack.append(scalar)

        def pop_types(types):
            for scalar in reversed(types):
                pop(scalar)

        def unreachable():
            del stack[controls[-1].height:]
            controls[-1].unreachable = True

        def label():
            depth = r.leb()
            if depth >= len(controls):
                r.fail("branch depth out of range")
            return controls[-1 - depth].label

        def unary(before, after):
            pop(before)
            push(after)

        def binary(before, after):
            pop(before)
            pop(before)
            push(after)

        while controls:
            opcode = r.byte()
            if opcode == 0x00:
                unreachable()
            elif opcode == 0x01:
                pass
            elif opcode in (0x02, 0x03, 0x04):
                if opcode == 0x04:
                    pop("i32")
                block_type = r.byte()
                if block_type == 0x40:
                    block_results = ()
                elif block_type in SCALAR_TYPES:
                    block_results = (SCALAR_TYPES[block_type],)
                else:
                    r.fail("unsupported block signature (multi-value/type-index blocks excluded)")
                if len(controls) >= MAX_CONTROL_DEPTH:
                    r.fail("control nesting exceeds profile bound")
                controls.append(_Control({2: "block", 3: "loop", 4: "if"}[opcode], len(stack), block_results))
            elif opcode == 0x05:
                frame = controls[-1]
                if frame.kind != "if" or frame.has_else:
                    r.fail("else outside if or duplicate else")
                pop_types(frame.results)
                if len(stack) != frame.height:
                    r.fail("unexpected values at else")
                frame.unreachable = False
                frame.has_else = True
            elif opcode == 0x0B:
                frame = controls[-1]
                pop_types(frame.results)
                if len(stack) != frame.height:
                    r.fail("unexpected values at end")
                if frame.kind == "if" and frame.results and not frame.has_else:
                    r.fail("result-producing if requires else")
                controls.pop()
                for scalar in frame.results:
                    push(scalar)
            elif opcode == 0x0C:
                pop_types(label())
                unreachable()
            elif opcode == 0x0D:
                types = label()
                pop("i32")
                pop_types(types)
                for scalar in types:
                    push(scalar)
            elif opcode == 0x0E:
                labels = [label() for _ in range(r.count())]
                default = label()
                if any(len(types) != len(default) for types in labels):
                    r.fail("br_table label types have different arities")
                pop("i32")
                # Each target must match the actual operands. An unreachable
                # bottom value may match different scalar target types.
                for index in range(len(default) - 1, -1, -1):
                    actual = pop()
                    if actual is not None and any(
                        actual != types[index] for types in labels + [default]
                    ):
                        r.fail("br_table label types differ from the operand")
                unreachable()
            elif opcode == 0x0F:
                pop_types(results)
                unreachable()
            elif opcode == 0x10:
                index = self.index(r, self.functions, "call function")
                arguments, returns = self.types[self.functions[index]]
                pop_types(arguments)
                for scalar in returns:
                    push(scalar)
            elif opcode == 0x11:
                index = self.index(r, self.types, "indirect call type")
                if r.byte() != 0 or self.table is None:
                    r.fail("call_indirect requires the single MVP table and zero reserved byte")
                arguments, returns = self.types[index]
                pop("i32")
                pop_types(arguments)
                for scalar in returns:
                    push(scalar)
            elif opcode == 0x1A:
                pop()
            elif opcode == 0x1B:
                pop("i32")
                second, first = pop(), pop()
                if first is not None and second is not None and first != second:
                    r.fail("select operand types differ")
                push(first if first is not None else second)
            elif opcode in (0x20, 0x21, 0x22):
                scalar = locals_[self.index(r, locals_, "local")]
                if opcode != 0x20:
                    pop(scalar)
                if opcode != 0x21:
                    push(scalar)
            elif opcode in (0x23, 0x24):
                scalar, mutable = self.globals[self.index(r, self.globals, "global")]
                if opcode == 0x23:
                    push(scalar)
                else:
                    if not mutable:
                        r.fail("global.set targets immutable global")
                    pop(scalar)
            elif 0x28 <= opcode <= 0x3E:
                if self.memory is None:
                    r.fail("memory instruction without memory")
                scalar, alignment = _MEMORY_OPS[opcode - 0x28]
                if r.leb() > alignment:
                    r.fail("memory alignment exceeds natural alignment")
                r.leb()  # wasm32 offset, even in unreachable code
                if opcode >= 0x36:
                    pop(scalar)
                    pop("i32")
                else:
                    pop("i32")
                    push(scalar)
            elif opcode in (0x3F, 0x40):
                if self.memory is None or r.byte() != 0:
                    r.fail("memory.size/grow requires memory and zero reserved byte")
                if opcode == 0x40:
                    pop("i32")
                push("i32")
            elif opcode in (0x41, 0x42):
                r.leb(32 if opcode == 0x41 else 64, True)
                push("i32" if opcode == 0x41 else "i64")
            elif opcode in (0x43, 0x44):
                r.take(4 if opcode == 0x43 else 8)
                push("f32" if opcode == 0x43 else "f64")
            elif opcode in _NUMERIC_OPS:
                before, after, count = _NUMERIC_OPS[opcode]
                (unary if count == 1 else binary)(before, after)
            else:
                r.fail(f"unknown or unsupported instruction 0x{opcode:02x}")
        r.done()

    def finish(self):
        if self.code_count != len(self.defined_functions):
            raise WasmError("function definitions require a matching code section")
        memory_exports = [name for name, value in self.exports.items() if value["kind"] == "memory"]
        if self.memory is None or memory_exports != ["memory"]:
            raise WasmError("profile requires one defined memory exported exactly once as 'memory'")
        if set(self.exports) != set(REQUIRED_EXPORTS) | {"memory"}:
            raise WasmError("profile requires exactly the seven application exports and memory")
        for name, expected in REQUIRED_EXPORTS.items():
            actual = self.exports.get(name)
            if actual is None or actual["kind"] != "function" or (
                tuple(actual["parameters"]), tuple(actual["results"])) != expected:
                raise WasmError(f"missing or incorrect required scalar export {name}")


# (value type, natural alignment exponent), in opcode order 0x28..0x3e.
_MEMORY_OPS = (
    ("i32", 2), ("i64", 3), ("f32", 2), ("f64", 3),
    ("i32", 0), ("i32", 0), ("i32", 1), ("i32", 1),
    ("i64", 0), ("i64", 0), ("i64", 1), ("i64", 1), ("i64", 2), ("i64", 2),
    ("i32", 2), ("i64", 3), ("f32", 2), ("f64", 3),
    ("i32", 0), ("i32", 1), ("i64", 0), ("i64", 1), ("i64", 2),
)
_NUMERIC_OPS = {}
for _lower, _upper, _before, _after, _count in (
    (0x45, 0x45, "i32", "i32", 1), (0x46, 0x4F, "i32", "i32", 2),
    (0x50, 0x50, "i64", "i32", 1), (0x51, 0x5A, "i64", "i32", 2),
    (0x5B, 0x60, "f32", "i32", 2), (0x61, 0x66, "f64", "i32", 2),
    (0x67, 0x69, "i32", "i32", 1), (0x6A, 0x78, "i32", "i32", 2),
    (0x79, 0x7B, "i64", "i64", 1), (0x7C, 0x8A, "i64", "i64", 2),
    (0x8B, 0x91, "f32", "f32", 1), (0x92, 0x98, "f32", "f32", 2),
    (0x99, 0x9F, "f64", "f64", 1), (0xA0, 0xA6, "f64", "f64", 2),
    (0xA7, 0xA7, "i64", "i32", 1), (0xA8, 0xA9, "f32", "i32", 1),
    (0xAA, 0xAB, "f64", "i32", 1), (0xAC, 0xAD, "i32", "i64", 1),
    (0xAE, 0xAF, "f32", "i64", 1), (0xB0, 0xB1, "f64", "i64", 1),
    (0xB2, 0xB3, "i32", "f32", 1), (0xB4, 0xB5, "i64", "f32", 1),
    (0xB6, 0xB6, "f64", "f32", 1), (0xB7, 0xB8, "i32", "f64", 1),
    (0xB9, 0xBA, "i64", "f64", 1), (0xBB, 0xBB, "f32", "f64", 1),
    (0xBC, 0xBC, "f32", "i32", 1), (0xBD, 0xBD, "f64", "i64", 1),
    (0xBE, 0xBE, "i32", "f32", 1), (0xBF, 0xBF, "i64", "f64", 1),
):
    for _opcode in range(_lower, _upper + 1):
        _NUMERIC_OPS[_opcode] = (_before, _after, _count)


def validate_module(data: bytes) -> dict:
    """Return a deterministic audit summary, or raise :class:`WasmError`.

    This call performs no execution and needs no installed compiler or runtime.
    The returned SHA256 always identifies the exact audited final module bytes.
    """
    if not isinstance(data, (bytes, bytearray, memoryview)):
        raise WasmError("module must be bytes")
    if (data.nbytes if isinstance(data, memoryview) else len(data)) > MAX_MODULE_BYTES:
        raise WasmError("module exceeds profile byte limit")
    data = bytes(data)
    reader = _Reader(data)
    if reader.take(8) != b"\x00asm\x01\x00\x00\x00":
        reader.fail("expected core Wasm version 1 magic and version")
    module = _Module()
    previous = 0
    while reader.pos < len(data):
        number = reader.byte()
        size = reader.leb()
        base = reader.pos
        section = _Reader(reader.take(size), f"section {number}", base)
        if number == 0:
            section.name()
            # Custom bytes (including producer/debug data) have no execution semantics.
            section.take(len(section.data) - section.pos)
            section.done()
            continue
        if number > 11:
            section.fail("unknown or unsupported section")
        if number <= previous:
            section.fail("duplicate or out-of-order section")
        previous = number
        module.section(number, section)
    module.finish()
    return {"profile": PROFILE, "sha256": hashlib.sha256(data).hexdigest(),
            "size_bytes": len(data), "memory": module.memory, "table": module.table,
            "type_count": len(module.types), "function_count": len(module.functions),
            "defined_function_count": len(module.defined_functions),
            "global_count": len(module.globals), "imports": module.imports,
            "exports": module.exports}
