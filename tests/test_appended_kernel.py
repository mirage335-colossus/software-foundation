"""Initial boundary production and the actual native console composition root."""
import hashlib
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import appended_container as container
import appended_kernel as kernel
import source_identity



def elf_fixture(*, alignment=4096, writable=False):
    """One independently laid out ELF64 load ending in the middle of a page."""
    value = bytearray(768)
    value[:16] = b'\x7fELF\x02\x01\x01' + bytes(9)
    struct.pack_into('<HHIQQQIHHHHHH', value, 16,
                     2, 62, 1, 0x400100, 64, 0, 0, 64, 56, 1, 0, 0, 0)
    struct.pack_into('<IIQQQQQQ', value, 64,
                     1, 6 if writable else 4, 0, 0x400000, 0x400000, len(value), len(value), alignment)
    value[128:144] = b'SFKERN01' + bytes(8)
    value[-1] = 0xa5
    return bytes(value)


def pe_fixture(*, signed=False, writable=False):
    value = bytearray(1024)
    value[:2] = b'MZ'
    struct.pack_into('<I', value, 60, 64)
    value[64:68] = b'PE\0\0'
    struct.pack_into('<HHIIIHH', value, 68, 0x8664, 1, 0, 0, 0, 240, 2)
    struct.pack_into('<H', value, 88, 0x20b)
    struct.pack_into('<I', value, 88 + 108, 16)
    if signed:
        struct.pack_into('<II', value, 88 + 112 + 32, 900, 80)
    section = 88 + 240
    value[section:section + 8] = b'.rdata\0\0'
    struct.pack_into('<II', value, section + 16, 512, 512)
    struct.pack_into('<I', value, section + 36, 0xc0000040 if writable else 0x40000040)
    value[640:656] = b'SFKERN01' + bytes(8)
    return bytes(value)


def _u32(value):
    encoded = bytearray()
    while True:
        byte = value & 127
        value >>= 7
        encoded.append(byte | (128 if value else 0))
        if not value:
            return bytes(encoded)


def _section(kind, value):
    return bytes([kind]) + _u32(len(value)) + value


def module_fixture(initialization_status=0):
    # Conservative core wasm32 with the exact ABI exports. No compiler or web
    # runtime is needed to independently exercise actual loader initialization.
    signatures = [b'\x60\x00\x01\x7f', b'\x60\x01\x7f\x01\x7f',
                  b'\x60\x02\x7f\x7f\x00', b'\x60\x02\x7f\x7f\x01\x7f',
                  b'\x60\x01\x7f\x00']
    value = b'\0asm\x01\0\0\0'
    value += _section(1, _u32(len(signatures)) + b''.join(signatures))
    value += _section(3, b'\x07\x00\x01\x02\x03\x03\x01\x04')
    value += _section(5, b'\x01\x01\x01\x01')
    exports = [(b'memory', 2, 0)] + [
        (('foundation_app_' + name + '_v1').encode(), 0, index)
        for index, name in enumerate(('abi', 'alloc', 'free', 'init', 'dispatch', 'step', 'shutdown'))]
    value += _section(7, _u32(len(exports)) + b''.join(
        _u32(len(name)) + name + bytes([kind]) + _u32(index) for name, kind, index in exports))
    bodies = [b'\x00\x41\x80\x80\x04\x0b', b'\x00\x41\x80\x08\x0b',
              b'\x00\x0b', b'\x00\x41' + bytes([initialization_status]) + b'\x0b',
              b'\x00\x41\x00\x0b', b'\x00\x41\x00\x0b', b'\x00\x0b']
    value += _section(10, _u32(len(bodies)) + b''.join(_u32(len(body)) + body for body in bodies))
    return value


class SealingTests(unittest.TestCase):
    def test_elf_page_padding_and_stamp_are_part_of_final_hash(self):
        initial = elf_fixture()
        sealed, carrier, stamp = kernel.seal_bytes(initial)
        self.assertEqual((carrier, stamp, len(sealed)), ('elf', 128, 4096))
        self.assertEqual(sealed[:136], initial[:136])
        self.assertEqual(sealed[144:len(initial)], initial[144:])
        self.assertEqual(sealed[len(initial):], bytes(4096 - len(initial)))
        self.assertEqual(struct.unpack_from('<Q', sealed, 136)[0], 4096)
        container._native(sealed, 'elf')
        self.assertNotEqual(hashlib.sha256(initial).digest(), hashlib.sha256(sealed).digest())

    def test_large_load_alignment_is_honored_once(self):
        sealed, _, _ = kernel.seal_bytes(elf_fixture(alignment=65536))
        self.assertEqual(len(sealed), 65536)
        with self.assertRaisesRegex(kernel.KernelError, 'already sealed'):
            kernel.seal_bytes(sealed)

    def test_reject_legacy_ambiguous_or_writable_boundary(self):
        for initial in (b'legacy executable', elf_fixture() + b'SFKERN01' + bytes(8),
                        elf_fixture(writable=True), pe_fixture(writable=True)):
            with self.subTest(prefix=initial[:4], length=len(initial)):
                with self.assertRaises(kernel.KernelError):
                    kernel.seal_bytes(initial)
        with self.assertRaisesRegex(kernel.KernelError, 'carrier'):
            kernel.seal_bytes(elf_fixture(), 'pe')
        # A later writable load need not contain the stamp's file offset to
        # change protection on its virtual page. Keep the two tests independent
        # of section guesses and of the initial read-only file-range check.
        alias = bytearray(elf_fixture())
        alias[128:144] = bytes(16)
        alias[256:272] = b'SFKERN01' + bytes(8)
        struct.pack_into('<H', alias, 56, 2)
        struct.pack_into('<IIQQQQQQ', alias, 120,
                         1, 6, 512, 0x400200, 0x400200, 128, 128, 4096)
        with self.assertRaisesRegex(ValueError, '[Ww]ritable'):
            kernel.seal_bytes(bytes(alias))

    def test_signed_pe_is_not_rewritten_and_unsigned_pe_preserves_size(self):
        initial = pe_fixture(signed=True)
        with self.assertRaisesRegex(kernel.KernelError, 'signed PE'):
            kernel.seal_bytes(initial)
        sealed, carrier, stamp = kernel.seal_bytes(pe_fixture())
        self.assertEqual((carrier, stamp, len(sealed)), ('pe', 640, 1024))
        self.assertEqual(sealed[648:656], struct.pack('<Q', 1024))
        container._native(sealed, 'pe')

    def test_invalid_load_alignment_and_extents_fail_before_padding(self):
        with self.assertRaisesRegex(kernel.KernelError, 'alignment'):
            kernel.seal_bytes(elf_fixture(alignment=3))
        value = bytearray(elf_fixture())
        struct.pack_into('<Q', value, 64 + 32, len(value) + 1)
        with self.assertRaisesRegex(kernel.KernelError, 'bounds'):
            kernel.seal_bytes(bytes(value))

    def test_provenance_input_modes_and_new_destinations_are_preserved(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'source'
            source.mkdir()
            (source / 'main.cpp').write_text('int main() { return 0; }\n')
            raw, output, descriptor = root / 'raw', root / 'kernel', root / 'kernel.json'
            raw.write_bytes(elf_fixture())
            raw.chmod(0o751)
            provenance = {'original_source_archive_sha256': 'a' * 64, 'original_run': 17}
            actual = kernel.seal(raw, output, descriptor, source, provenance)
            self.assertEqual(raw.read_bytes(), elf_fixture())
            self.assertEqual(provenance, {'original_source_archive_sha256': 'a' * 64, 'original_run': 17})
            self.assertEqual(actual['provenance']['original_run'], 17)
            self.assertEqual(actual['provenance']['original_source_archive_sha256'], 'a' * 64)
            self.assertEqual(actual['provenance']['sealing']['qualification'], 'unqualified-development')
            self.assertEqual(actual['profile'], 'binary')
            self.assertEqual(actual['kernel_inputs']['projection'], 'foundation-appended-kernel-v2')
            self.assertEqual(descriptor.read_bytes(), container.canonical_json(actual))
            self.assertEqual(actual['executable']['sha256'], hashlib.sha256(output.read_bytes()).hexdigest())
            self.assertIsNone(container.parse_artifact(output.read_bytes(), actual).package)
            if os.name != 'nt':
                self.assertEqual(output.stat().st_mode & 0o777, 0o751)
            with self.assertRaisesRegex(kernel.KernelError, 'must be new'):
                kernel.seal(raw, output, root / 'second.json', source, provenance)
            self.assertFalse((root / 'second.json').exists())
            with self.assertRaisesRegex(kernel.KernelError, 'outside source inputs'):
                kernel.seal(raw, source / 'generated-kernel', root / 'second.json', source, provenance)
            self.assertFalse((source / 'generated-kernel').exists())
            terminal = kernel.seal(raw, root / 'terminal', root / 'terminal.json', source, provenance,
                                   services=['foundation.view'], capabilities=['foundation.view.v1'])
            self.assertEqual(terminal['services'], ['foundation.kernel', 'foundation.view'])
            self.assertEqual(terminal['capabilities'], ['foundation.view.v1'])
            self.assertNotIn('foundation.diagnostics', terminal['services'])

    def test_composed_kernel_cannot_be_used_as_initial_producer_input(self):
        sealed, _, _ = kernel.seal_bytes(elf_fixture())
        with self.assertRaisesRegex(kernel.KernelError, 'already sealed'):
            kernel.seal_bytes(sealed + b'appended application bytes')

    def test_same_bytes_new_inode_or_changed_mode_cannot_replace_the_producer_input(self):
        for replace_inode in (True, False):
            with self.subTest(replace_inode=replace_inode), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                source = root / 'source'
                source.mkdir()
                (source / 'main.cpp').write_text('// source fixture\n')
                raw, output, descriptor = root / 'raw', root / 'kernel', root / 'kernel.json'
                raw.write_bytes(elf_fixture())
                raw.chmod(0o644)
                original_identity = raw.stat().st_ino
                original_mode = raw.stat().st_mode & 0o777
                changed = False
                describe = source_identity.source_tree

                def replace_input(*args, **kwargs):
                    nonlocal changed
                    result = describe(*args, **kwargs)
                    if not changed:
                        changed = True
                        if replace_inode:
                            raw.rename(root / 'original-input')
                            raw.write_bytes(elf_fixture())
                            raw.chmod(original_mode)
                        else:
                            raw.chmod(0o444)
                    return result

                try:
                    with patch.object(source_identity, 'source_tree', side_effect=replace_input):
                        with self.assertRaisesRegex(ValueError, 'Input changed'):
                            kernel.seal(raw, output, descriptor, source, {})
                    self.assertEqual(raw.read_bytes(), elf_fixture())
                    if replace_inode:
                        self.assertNotEqual(raw.stat().st_ino, original_identity)
                        self.assertEqual(raw.stat().st_mode & 0o777, original_mode)
                    else:
                        self.assertEqual(raw.stat().st_ino, original_identity)
                        self.assertNotEqual(raw.stat().st_mode & 0o777, original_mode)
                    self.assertFalse(output.exists())
                    self.assertFalse(descriptor.exists())
                finally:
                    raw.chmod(0o644)

    def test_linked_or_retargeted_output_parent_cannot_publish_into_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'source'
            source.mkdir()
            (source / 'main.cpp').write_text('// source fixture\n')
            raw = root / 'raw'
            raw.write_bytes(elf_fixture())
            parent = root / 'outside-output'
            parent.mkdir()
            output, descriptor = parent / 'kernel', parent / 'kernel.json'
            changed = False
            describe = source_identity.source_tree

            def retarget_output(*args, **kwargs):
                nonlocal changed
                result = describe(*args, **kwargs)
                if not changed:
                    changed = True
                    parent.rename(root / 'original-output-directory')
                    parent.symlink_to(source, target_is_directory=True)
                return result

            with patch.object(source_identity, 'source_tree', side_effect=retarget_output):
                with self.assertRaisesRegex(ValueError, 'output parent changed'):
                    kernel.seal(raw, output, descriptor, source, {})
            self.assertFalse((source / 'kernel').exists())
            self.assertFalse((source / 'kernel.json').exists())
            self.assertFalse((root / 'original-output-directory' / 'kernel').exists())
            outside = root / 'another-outside-directory'
            outside.mkdir()
            alias = root / 'linked-parent'
            alias.symlink_to(outside, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, 'ordinary nonlinked'):
                kernel.seal(raw, alias / 'kernel', alias / 'kernel.json', source, {})
            self.assertFalse((outside / 'kernel').exists())

    def test_descriptor_consumer_size_limit_is_enforced_before_publication(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'source'
            source.mkdir()
            (source / 'main.cpp').write_text('// source fixture\n')
            raw = root / 'raw'
            raw.write_bytes(elf_fixture())
            baseline = kernel.seal(raw, root / 'baseline', root / 'baseline.json', source, {'build_log': ''})
            remaining = container.MAX_INDEX - len(container.canonical_json(baseline))
            accepted = kernel.seal(raw, root / 'exact', root / 'exact.json', source,
                                   {'build_log': 'x' * remaining})
            encoded = (root / 'exact.json').read_bytes()
            self.assertEqual(len(encoded), container.MAX_INDEX)
            self.assertEqual(container.load_kernel_descriptor(root / 'exact.json',
                             hashlib.sha256(encoded).hexdigest()), accepted)
            with self.assertRaisesRegex(kernel.KernelError, 'consumer 4 MiB limit'):
                kernel.seal(raw, root / 'oversize', root / 'oversize.json', source,
                            {'build_log': 'x' * (remaining + 1)})
            self.assertFalse((root / 'oversize').exists())
            self.assertFalse((root / 'oversize.json').exists())




if __name__ == '__main__':
    unittest.main()
