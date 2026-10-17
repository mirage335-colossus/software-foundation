"""Independent binary fixtures for the portable final-module audit."""

import hashlib
from pathlib import Path
import sys
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import appended_wasm as wasm


HEADER = b"\0asm\1\0\0\0"
EXPORT_NAMES = (
    "foundation_app_abi_v1", "foundation_app_alloc_v1", "foundation_app_free_v1",
    "foundation_app_init_v1", "foundation_app_dispatch_v1", "foundation_app_step_v1",
    "foundation_app_shutdown_v1",
)


def uint(value):
    result = bytearray()
    while value >= 128:
        result.append(128 | (value & 127))
        value >>= 7
    result.append(value)
    return bytes(result)


def sint(value):
    result = bytearray()
    while True:
        part = value & 127
        value >>= 7
        if (value == 0 and part < 64) or (value == -1 and part >= 64):
            return bytes(result + bytes([part]))
        result.append(part | 128)


def name(value):
    data = value.encode("utf-8") if isinstance(value, str) else value
    return uint(len(data)) + data


def vector(items):
    return uint(len(items)) + b"".join(items)


def section(number, data):
    return bytes([number]) + uint(len(data)) + data


def code_section(bodies):
    return vector([uint(len(body)) + body for body in bodies])


def fixtures(import_call=False):
    # Types and bodies are encoded independently of the validator's ABI constants.
    types = [b"\x60\x00\x01\x7f", b"\x60\x01\x7f\x01\x7f",
             b"\x60\x02\x7f\x7f\x00", b"\x60\x02\x7f\x7f\x01\x7f",
             b"\x60\x01\x7f\x00", b"\x60\x04\x7f\x7f\x7f\x7f\x01\x7f"]
    bodies = [b"\x00\x41\x00\x0b", b"\x00\x20\x00\x0b", b"\x00\x0b",
              b"\x00\x41\x00\x0b", b"\x00\x41\x00\x0b",
              b"\x00\x20\x00\x0b", b"\x00\x0b"]
    shift = int(import_call)
    exports = [name(item) + b"\x00" + uint(index + shift)
               for index, item in enumerate(EXPORT_NAMES)]
    exports.append(name("memory") + b"\x02\x00")
    sections = {1: vector(types), 3: vector([bytes([x]) for x in (0, 1, 2, 3, 3, 1, 4)]),
                5: b"\x01\x01\x01\x10", 7: vector(exports), 10: code_section(bodies)}
    if import_call:
        sections[2] = b"\x01" + name("foundation.kernel.v1") + name("call") + b"\x00\x05"
    return sections, bodies, types, exports


def module(sections=None, bodies=None, import_call=False):
    if sections is None:
        sections, default_bodies, _, _ = fixtures(import_call)
        if bodies is None:
            bodies = default_bodies
    if bodies is not None:
        sections = dict(sections)
        sections[10] = code_section(bodies)
    return HEADER + b"".join(section(key, value) for key, value in sorted(sections.items()))


class AppendedWasmTests(unittest.TestCase):
    def reject(self, data, message=None):
        with self.assertRaisesRegex(wasm.WasmError, message or "."):
            wasm.validate_module(data)

    def with_first_body(self, instructions, local_declarations=b"\x00"):
        sections, bodies, _, _ = fixtures()
        bodies[0] = local_declarations + instructions + b"\x0b"
        return module(sections, bodies)

    def test_golden_minimal_complete_module(self):
        data = module()
        audit = wasm.validate_module(data)
        self.assertEqual("foundation-guest-v1", audit["profile"])
        self.assertEqual(hashlib.sha256(data).hexdigest(), audit["sha256"])
        self.assertEqual(len(data), audit["size_bytes"])
        self.assertEqual(7, audit["function_count"])
        self.assertEqual(6, audit["type_count"])
        self.assertEqual([], audit["imports"])
        self.assertEqual({"minimum_pages": 1, "maximum_pages": 16}, audit["memory"])
        self.assertEqual({"kind": "function", "index": 0, "parameters": [], "results": ["i32"]},
                         audit["exports"]["foundation_app_abi_v1"])

    def test_golden_imported_function_shifts_actual_export_indices(self):
        audit = wasm.validate_module(module(import_call=True))
        self.assertEqual(8, audit["function_count"])
        self.assertEqual(1, audit["exports"]["foundation_app_abi_v1"]["index"])
        self.assertEqual(["i32"] * 4, audit["imports"][0]["parameters"])

    def test_magic_version_truncation_and_nonbytes(self):
        for data in (b"", HEADER[:7], b"\0asm\2\0\0\0", b"badmagic", "text"):
            with self.subTest(data=data):
                self.reject(data)

    def test_module_and_section_resource_limits(self):
        self.reject(b"\0" * (wasm.MAX_MODULE_BYTES + 1), "byte limit")
        self.reject(HEADER + b"\x01" + uint(100), "truncated")
        self.reject(HEADER + section(1, uint(wasm.MAX_TYPES + 1)), "vector")

    def test_multibyte_memoryview_bound_counts_bytes(self):
        with mock.patch.object(wasm, "MAX_MODULE_BYTES", 16):
            self.reject(memoryview(b"x" * 20).cast("I"), "byte limit")

    def test_section_order_duplicates_unknown_and_trailing(self):
        sections, _, _, _ = fixtures()
        for data in (module() + section(5, sections[5]),
                     HEADER + section(3, sections[3]) + section(1, sections[1]),
                     module() + section(12, b"\x00"), module() + section(255, b""),
                     module() + b"\x00", HEADER + section(1, b"\x00\x00")):
            with self.subTest(data=data[-20:]):
                self.reject(data)

    def test_custom_section_name_utf8_and_opaque_data(self):
        # Forbidden opcode bytes in custom/debug data have no instruction meaning.
        custom = section(0, name("debug") + bytes(range(256)))
        self.assertEqual(wasm.validate_module(module())["function_count"],
                         wasm.validate_module(HEADER + custom + module()[8:] + custom)["function_count"])
        self.reject(HEADER + section(0, name(b"\xff")) + module()[8:], "UTF-8")
        self.reject(HEADER + section(0, name("a\0b")) + module()[8:], "NUL")
        self.reject(HEADER + section(0, b"\x02a") + module()[8:], "truncated")

    def test_leb_canonicality_and_integer_widths(self):
        self.reject(HEADER + b"\x01\x80\x00", "noncanonical")
        for encoded in (b"\x80\x00", b"\xff\x7f", b"\x80\x80\x80\x80\x00",
                        b"\x80\x80\x80\x80\x08", b"\xff\xff\xff\xff\x0f",
                        b"\x80\x80\x80\x80\x80\x00"):
            with self.subTest(encoded=encoded):
                self.reject(self.with_first_body(b"\x41" + encoded))
        for value in (-2147483648, -65, -64, -1, 0, 63, 64, 2147483647):
            with self.subTest(value=value):
                wasm.validate_module(self.with_first_body(b"\x41" + sint(value)))
        for value in (-9223372036854775808, 9223372036854775807):
            wasm.validate_module(self.with_first_body(b"\x42" + sint(value) + b"\xa7"))
        self.reject(self.with_first_body(b"\x42" + b"\x80" * 9 + b"\x01\xa7"), "width")

    def test_final_immediate_bytes_are_not_forbidden_opcode_scans(self):
        wasm.validate_module(self.with_first_body(b"\x41" + sint(252)))
        wasm.validate_module(self.with_first_body(b"\x43\xfd\xfe\xfc\xc0\xbc"))
        sections, _, _, _ = fixtures()
        sections[11] = b"\x01\x00\x41\x00\x0b\x05\xfc\xfd\xfe\xc0\xd0"
        wasm.validate_module(module(sections))

    def test_start_and_foreign_imports_rejected(self):
        sections, _, _, _ = fixtures()
        sections[8] = b"\x00"
        self.reject(module(sections), "start")
        for namespace, field, kind in (("wasi_snapshot_preview1", "fd_write", 0),
                                        ("env", "call", 0), ("foundation.kernel.v1", "other", 0),
                                        ("foundation.kernel.v1", "call", 2)):
            sections, _, _, _ = fixtures()
            sections[2] = b"\x01" + name(namespace) + name(field) + bytes([kind]) + b"\x05"
            self.reject(module(sections), "only.*import")

    def test_import_signature_count_and_type_index(self):
        sections, _, _, _ = fixtures(True)
        sections[2] = sections[2][:-1] + b"\x00"
        self.reject(module(sections), "signature")
        sections[2] = sections[2][:-1] + b"\x06"
        self.reject(module(sections), "index")
        sections[2] = b"\x02" + sections[2][1:] * 2
        self.reject(module(sections), "vector")

    def test_memory_finite_unshared_single_and_bounded(self):
        for limits in (b"\x00\x01", b"\x02\x01", b"\x03\x01\x10", b"\x04\x01",
                       b"\x01\x10\x01", b"\x01\x00" + uint(257),
                       b"\x01" + uint(257) + uint(257)):
            sections, _, _, _ = fixtures()
            sections[5] = b"\x01" + limits
            with self.subTest(limits=limits):
                self.reject(module(sections))
        sections[5] = b"\x02\x01\x00\x01\x01\x00\x01"
        self.reject(module(sections), "vector")
        sections[5] = b"\x01\x01\x00" + uint(256)
        wasm.validate_module(module(sections))

    def test_memory_required_and_exported_once_as_memory(self):
        sections, _, _, exports = fixtures()
        del sections[5]
        self.reject(module(sections), "index")
        sections, _, _, exports = fixtures()
        for items in (exports[:-1], exports[:-1] + [name("heap") + b"\x02\x00"],
                      exports + [name("heap") + b"\x02\x00"]):
            sections[7] = vector(items)
            self.reject(module(sections), "memory")

    def test_required_exports_signatures_names_and_actual_indices(self):
        sections, _, _, exports = fixtures()
        for items in (exports[1:], exports + [exports[0]],
                      [name(EXPORT_NAMES[0]) + b"\x00\x01"] + exports[1:],
                      [name(EXPORT_NAMES[0]) + b"\x00\x07"] + exports[1:],
                      [name(EXPORT_NAMES[0]) + b"\x03\x00"] + exports[1:],
                      [name(b"\xff") + b"\x00\x00"] + exports[1:]):
            sections[7] = vector(items)
            self.reject(module(sections))

    def test_function_code_type_counts_and_body_lengths(self):
        sections, bodies, _, _ = fixtures()
        for replacement in (b"\x00", code_section(bodies[:-1]), b"\x07\xff"):
            sections[10] = replacement
            self.reject(module(sections))
        del sections[10]
        self.reject(module(sections), "matching code")
        sections, _, _, _ = fixtures()
        sections[3] = b"\x07\x06\x01\x02\x03\x03\x01\x04"
        self.reject(module(sections), "type.*index")
        self.reject(self.with_first_body(b"\x41\x00\x0b"), "trailing")
        sections, bodies, _, _ = fixtures()
        bodies[0] = b"\x00\x41\x00"
        self.reject(module(sections, bodies), "end")

    def test_scalar_types_single_result_and_mvp_block_types(self):
        for type_ in (b"\x60\x00\x02\x7f\x7f", b"\x60\x01\x70\x00", b"\x5f\x00"):
            sections, _, types, _ = fixtures()
            sections[1] = vector([type_] + types[1:])
            self.reject(module(sections))
        for blocktype in (b"\x00", b"\x70", b"\x7b", b"\xff\x7f"):
            self.reject(self.with_first_body(b"\x02" + blocktype + b"\x0b\x41\x00"), "block")

    def test_operand_types_stack_underflow_and_extra_values(self):
        for instructions in (b"\x6a", b"\x42\x00", b"\x41\x00\x41\x01",
                             b"\x41\x00\x42\x00\x6a", b"\x00\x42\x00\x45"):
            self.reject(self.with_first_body(instructions))
        wasm.validate_module(self.with_first_body(b"\x00\x6a"))
        wasm.validate_module(self.with_first_body(b"\x00\x1b"))

    def test_blocks_loops_if_else_and_unreachable_branching(self):
        for instructions in (b"\x02\x7f\x41\x01\x0b",
                             b"\x41\x01\x04\x7f\x41\x02\x05\x41\x03\x0b",
                             b"\x03\x40\x0c\x00\x0b\x41\x00",
                             b"\x02\x7f\x41\x01\x0c\x00\x0b",
                             b"\x41\x01\x41\x00\x0d\x00"):
            wasm.validate_module(self.with_first_body(instructions))
        for instructions in (b"\x05\x41\x00", b"\x0c\x01", b"\x41\x01\x04\x7f\x41\x02\x0b",
                             b"\x41\x01\x04\x40\x05\x05\x0b\x41\x00",
                             b"\x02\x40\x41\x00\x0b\x41\x00",
                             b"\x00\x02\x40\x1a\x0b"):
            self.reject(self.with_first_body(instructions))

    def test_br_table_label_types_and_depths(self):
        wasm.validate_module(self.with_first_body(b"\x02\x7f\x41\x09\x41\x00\x0e\x01\x00\x00\x0b"))
        self.reject(self.with_first_body(b"\x02\x40\x41\x00\x0e\x01\x00\x01\x0b\x41\x00"), "label types")
        self.reject(self.with_first_body(b"\x41\x00\x0e\x00\x01"), "depth")

    def test_unreachable_br_table_compares_operands_with_each_target(self):
        # Bottom operands can satisfy different scalar labels of equal arity.
        prefix = b"\x02\x7f\x02\x7d\x00"
        suffix = b"\x0e\x01\x00\x01\x0b\x1a\x41\x00\x0b"
        wasm.validate_module(self.with_first_body(prefix + suffix))
        # Explicitly pushed values retain their concrete type in unreachable code.
        self.reject(self.with_first_body(prefix + b"\x41\x00\x41\x00" + suffix), "operand")

    def test_calls_validate_function_and_parameter_types(self):
        wasm.validate_module(self.with_first_body(b"\x41\x03\x10\x01"))
        for instructions in (b"\x10\x01", b"\x42\x00\x10\x01", b"\x10\x07"):
            self.reject(self.with_first_body(instructions))
        sections, bodies, _, _ = fixtures(True)
        bodies[0] = b"\x00" + b"\x41\x00" * 4 + b"\x10\x00\x0b"
        wasm.validate_module(module(sections, bodies))

    def test_locals_bounds_types_and_budget(self):
        wasm.validate_module(self.with_first_body(b"\x41\x03\x21\x00\x20\x00", b"\x01\x01\x7f"))
        for instructions in (b"\x20\x00", b"\x41\x00\x21\x00", b"\x41\x00\x22\x00"):
            self.reject(self.with_first_body(instructions), "local.*index")
        self.reject(self.with_first_body(b"\x41\x00", b"\x01" + uint(wasm.MAX_LOCALS + 1) + b"\x7f"), "vector")
        self.reject(self.with_first_body(b"\x41\x00", b"\x01\x01\x70"), "scalar")
        self.reject(self.with_first_body(b"\x42\x00\x21\x00\x41\x00", b"\x01\x01\x7f"), "type")

    def test_function_frame_exact_independent_local_operand_boundaries(self):
        # The profile independently bounds indexed values and operand values.
        sections, bodies, _, _ = fixtures()
        bodies[2] = b"\x01" + uint(1022) + b"\x7f\x0b"  # two parameters
        wasm.validate_module(module(sections, bodies))
        bodies[2] = b"\x01" + uint(1023) + b"\x7f\x0b"
        self.reject(module(sections, bodies), "locals")
        declarations = b"\x01" + uint(1024) + b"\x7f"
        exact = b"\x41\x00" * 1024 + b"\x1a" * 1023
        wasm.validate_module(self.with_first_body(exact, declarations))
        over = b"\x41\x00" * 1025 + b"\x1a" * 1024
        self.reject(self.with_first_body(over, declarations), "stack exceeds")

    def test_deep_scalar_result_blocks_with_maximum_locals(self):
        declarations = b"\x01" + uint(1024) + b"\x7f"
        exact = b"\x02\x7f" * 511 + b"\x41\x00" + b"\x0b" * 511
        wasm.validate_module(self.with_first_body(exact, declarations))
        over = b"\x02\x7f" * 512 + b"\x41\x00" + b"\x0b" * 512
        self.reject(self.with_first_body(over, declarations), "nesting")

    def test_globals_mutability_initializer_and_index(self):
        sections, bodies, _, _ = fixtures()
        sections[6] = b"\x01\x7f\x01\x41\x00\x0b"
        bodies[0] = b"\x00\x41\x01\x24\x00\x23\x00\x0b"
        wasm.validate_module(module(sections, bodies))
        sections[6] = b"\x01\x7f\x00\x41\x00\x0b"
        self.reject(module(sections, bodies), "immutable")
        for initializer in (b"\x7f\x02\x41\x00\x0b", b"\x7f\x00\x42\x00\x0b",
                            b"\x7f\x00\x23\x00\x0b", b"\x7f\x00\x41\x00\x41\x00\x0b"):
            sections[6] = b"\x01" + initializer
            self.reject(module(sections, bodies))
        self.reject(self.with_first_body(b"\x23\x00"), "global.*index")

    def test_memory_operations_alignment_reserved_and_offsets(self):
        wasm.validate_module(self.with_first_body(b"\x41\x00\x41\x05\x36\x02\x00\x41\x00\x28\x02\x00"))
        wasm.validate_module(self.with_first_body(b"\x3f\x00"))
        wasm.validate_module(self.with_first_body(b"\x41\x01\x40\x00"))
        for instructions in (b"\x41\x00\x28\x03\x00", b"\x3f\x01", b"\x3f\x80\x00",
                             b"\x41\x00\x28\x02\xff\xff\xff\xff\x1f", b"\x41\x00\x36\x02\x00"):
            self.reject(self.with_first_body(instructions))

    def test_mvp_table_elements_and_indirect_call(self):
        sections, bodies, _, _ = fixtures()
        sections[4] = b"\x01\x70\x01\x02\x02"
        sections[9] = b"\x01\x00\x41\x01\x0b\x01\x01"
        bodies[0] = b"\x00\x41\x03\x41\x01\x11\x01\x00\x0b"
        wasm.validate_module(module(sections, bodies))
        for table in (b"\x01\x70\x00\x01", b"\x01\x6f\x01\x01\x01",
                      b"\x01\x70\x01\x01" + uint(8193)):
            sections[4] = table
            self.reject(module(sections, bodies))
        sections[4] = b"\x01\x70\x01\x02\x02"
        for elements in (b"\x01\x01\x41\x00\x0b\x00", b"\x01\x00\x41\x02\x0b\x01\x01",
                         b"\x01\x00\x41\x00\x0b\x01\x07"):
            sections[9] = elements
            self.reject(module(sections, bodies))
        self.reject(self.with_first_body(b"\x41\x00\x11\x00\x00"), "table")
        sections[9] = b"\x00"
        for instruction in (b"\x41\x00\x11\x00\x01", b"\x41\x00\x11\x06\x00",
                            b"\x41\x00\x11\x01\x00"):
            bodies[0] = b"\x00" + instruction + b"\x0b"
            self.reject(module(sections, bodies))

    def test_data_segments_are_active_bounded_and_fully_consumed(self):
        sections, _, _, _ = fixtures()
        sections[11] = b"\x01\x00\x41" + sint(65535) + b"\x0b\x01\xff"
        wasm.validate_module(module(sections))
        for data in (b"\x01\x01\x00", b"\x01\x00\x41" + sint(65535) + b"\x0b\x02ab",
                     b"\x01\x00\x41\x7f\x0b\x01a", b"\x01\x00\x42\x00\x0b\x00",
                     b"\x01\x00\x41\x00\x0b\x02a"):
            sections[11] = data
            self.reject(module(sections))

    def test_excluded_features_rejected_even_in_unreachable_code(self):
        for instruction in (b"\xfc\x00", b"\xfd\x00", b"\xfe\x00", b"\xc0", b"\xc4",
                            b"\xd0\x70", b"\x06\x40", b"\x12\x00", b"\x1c\x01\x7f", b"\xff"):
            with self.subTest(instruction=instruction):
                self.reject(self.with_first_body(b"\x00" + instruction), "unsupported instruction")

    def test_all_mvp_scalar_numeric_signatures(self):
        # Independent category ledger catches wrong opcodes/signatures and gaps.
        categories = (
            (0x45, 0x45, "i32", "i32", 1), (0x46, 0x4f, "i32", "i32", 2),
            (0x50, 0x50, "i64", "i32", 1), (0x51, 0x5a, "i64", "i32", 2),
            (0x5b, 0x60, "f32", "i32", 2), (0x61, 0x66, "f64", "i32", 2),
            (0x67, 0x69, "i32", "i32", 1), (0x6a, 0x78, "i32", "i32", 2),
            (0x79, 0x7b, "i64", "i64", 1), (0x7c, 0x8a, "i64", "i64", 2),
            (0x8b, 0x91, "f32", "f32", 1), (0x92, 0x98, "f32", "f32", 2),
            (0x99, 0x9f, "f64", "f64", 1), (0xa0, 0xa6, "f64", "f64", 2),
            (0xa7, 0xa7, "i64", "i32", 1), (0xa8, 0xa9, "f32", "i32", 1),
            (0xaa, 0xab, "f64", "i32", 1), (0xac, 0xad, "i32", "i64", 1),
            (0xae, 0xaf, "f32", "i64", 1), (0xb0, 0xb1, "f64", "i64", 1),
            (0xb2, 0xb3, "i32", "f32", 1), (0xb4, 0xb5, "i64", "f32", 1),
            (0xb6, 0xb6, "f64", "f32", 1), (0xb7, 0xb8, "i32", "f64", 1),
            (0xb9, 0xba, "i64", "f64", 1), (0xbb, 0xbb, "f32", "f64", 1),
            (0xbc, 0xbc, "f32", "i32", 1), (0xbd, 0xbd, "f64", "i64", 1),
            (0xbe, 0xbe, "i32", "f32", 1), (0xbf, 0xbf, "i64", "f64", 1),
        )
        constants = {"i32": b"\x41\x00", "i64": b"\x42\x00",
                     "f32": b"\x43\0\0\0\0", "f64": b"\x44" + b"\0" * 8}
        for lower, upper, before, after, count in categories:
            for opcode in range(lower, upper + 1):
                with self.subTest(opcode=opcode):
                    instructions = constants[before] * count + bytes([opcode])
                    if after != "i32":
                        instructions += b"\x1a\x41\x00"
                    wasm.validate_module(self.with_first_body(instructions))
                    wrong = "i64" if before == "i32" else "i32"
                    self.reject(self.with_first_body(constants[wrong] * count + bytes([opcode])))

    def test_control_nesting_and_stack_resource_limits(self):
        self.reject(self.with_first_body(b"\x02\x40" * wasm.MAX_CONTROL_DEPTH + b"\x0b" * wasm.MAX_CONTROL_DEPTH + b"\x41\x00"), "nesting")
        self.reject(self.with_first_body(b"\x41\x00" * (wasm.MAX_OPERAND_STACK + 1)), "stack exceeds")


if __name__ == "__main__":
    unittest.main()
