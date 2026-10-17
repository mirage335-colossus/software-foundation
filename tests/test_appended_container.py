"""Reference vectors and observable filesystem safety for pure composition."""
import copy
import contextlib
import io
import importlib.util
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import appended_container as c

APP = {'id': 'org.example.fixture', 'name': 'Fixture', 'version': '1.0.0'}


def elf_fixture():
    content = bytearray(4096)
    content[:16] = b'\x7fELF\x02\x01\x01' + bytes(9)
    struct.pack_into('<HHIQQQIHHHHHH', content, 16, 2, 62, 1, 256, 64, 0, 0, 64, 56, 1, 0, 0, 0)
    struct.pack_into('<IIQQQQQQ', content, 64, 1, 5, 0, 0x400000, 0, 4096, 4096, 4096)
    content[256:272] = c.STAMP_MAGIC + struct.pack('<Q', len(content))
    return bytes(content), 256


def pe_fixture(plus=False):
    content = bytearray(1024)
    content[:2] = b'MZ'
    struct.pack_into('<I', content, 60, 128)
    content[128:132] = b'PE\0\0'
    optional_size = 240 if plus else 224
    struct.pack_into('<HHIIIHH', content, 132, 0x8664 if plus else 0x14c, 1, 0, 0, 0, optional_size, 2)
    struct.pack_into('<H', content, 152, 0x20b if plus else 0x10b)
    directory = 112 if plus else 96
    struct.pack_into('<I', content, 152 + directory - 4, 16)
    struct.pack_into('<II', content, 152 + optional_size + 16, 512, 512)
    struct.pack_into('<I', content, 152 + optional_size + 36, 0x40000000)
    content[800:816] = c.STAMP_MAGIC + struct.pack('<Q', len(content))
    return bytes(content), 800


def descriptor(prefix, boundary, carrier='elf', profile='web'):
    return {'schema_version': 1, 'kind': 'foundation-kernel', 'carrier': carrier, 'profile': profile,
            'append_format': 1, 'abi': {'major': 1, 'minor': 0}, 'capabilities': [], 'services': [],
            'executable': {'length': len(prefix), 'sha256': c.digest(prefix)}, 'boundary_offset': boundary,
            'provenance': {'scope': 'reference-fixture'}}


def web_package(text=b'<h1>Application</h1>'):
    return c.build_package({'web/index.html': text, 'web/style.css': b'h1{color:red}'}, APP,
                           web_entry='web/index.html')


def rewritten_package(package, change):
    index = copy.deepcopy(package.index)
    change(index)
    encoded = c.canonical_json(index)
    data = package.data[:package.index_offset] + encoded
    # Independent field construction deliberately rehashes structural attacks.
    trailer = struct.pack('<8sIIQQQQQ32s32s32s40s', b'SFAPND01', 1, 192, 0, len(data),
                          package.index_offset, len(encoded), 0,
                          bytes.fromhex(c.digest(b'')), bytes.fromhex(c.digest(data)),
                          bytes.fromhex(c.digest(encoded)), bytes(40))
    return data + trailer


class ContainerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.base, self.boundary = elf_fixture()
        self.desc = descriptor(self.base, self.boundary)
        self.package = web_package()
        self.source = self.root / 'kernel'
        self.source.write_bytes(self.base)
        self.source.chmod(0o755)
        self.manifest = self.root / 'kernel.json'
        self.manifest.write_bytes(c.canonical_json(self.desc))
        self.pin = c.digest(self.manifest.read_bytes())
        self.payload = self.root / 'application.sfapp'
        self.payload.write_bytes(c.encode_package(self.package))

    def compose(self, output='composed', source=None, payload=True, **kwargs):
        return c.compose(source or self.source, self.manifest, self.pin,
                         self.payload if payload else None, self.root / output, **kwargs)

    def test_golden_canonical_bytes_and_hash_boundaries(self):
        package = c.build_package({'web/index.html': b'X'}, APP, web_entry='web/index.html')
        expected_index = (b'{"application":{"id":"org.example.fixture","name":"Fixture","version":"1.0.0"},'
                          b'"components":{"binary":{"entry":null,"present":false,"profile":null},'
                          b'"web":{"entry":"web/index.html","present":true}},"files":[{"component":"web",'
                          b'"length":1,"media_type":"text/html","offset":0,"path":"web/index.html",'
                          b'"sha256":"4b68ab3847feda7d6c62c1fbcbeebfa35eab7351ed5e78f4ddadea5df64b8015"}],'
                          b'"identities":{},"kind":"foundation-appended-package","requires":{"abi":{"major":1,"minor":0},'
                          b'"capabilities":[],"services":[]},"schema_version":1}')
        self.assertEqual(package.data, b'X' + expected_index)
        self.assertEqual(package.payload_id, c.digest(expected_index))
        transport = c.encode_package(package)
        self.assertEqual(len(transport) - len(package.data), 192)
        self.assertEqual(transport[-192:-184], b'SFAPND01')
        self.assertEqual(struct.unpack_from('<QQQQQ', transport, len(transport) - 176),
                         (0, len(package.data), 1, len(expected_index), 0))
        self.assertEqual(c.parse_artifact(transport).package.data, package.data)

    def test_canonical_order_is_independent_of_input_mapping(self):
        first = c.build_package({'web/z.txt': b'z', 'web/index.html': b'i'}, APP, web_entry='web/index.html')
        second = c.build_package({'web/index.html': b'i', 'web/z.txt': b'z'}, dict(reversed(list(APP.items()))), web_entry='web/index.html')
        self.assertEqual(c.encode_package(first), c.encode_package(second))

    def test_compose_replace_strip_no_stacking_and_preserve_execute_mode(self):
        self.compose(expected_mode='web')
        first = (self.root / 'composed').read_bytes()
        self.assertEqual(first[:len(self.base)], self.base)
        self.assertEqual((self.root / 'composed').stat().st_mode & 0o777, 0o755)
        replacement = web_package(b'<!doctype html><h1>Replacement</h1>')
        self.payload.write_bytes(c.encode_package(replacement))
        self.compose('replaced', source=self.root / 'composed')
        second = (self.root / 'replaced').read_bytes()
        self.assertEqual(second, self.base + replacement.data + c.trailer_bytes(self.base, replacement, 'elf'))
        c.strip(self.root / 'replaced', self.manifest, self.pin, self.root / 'stripped', expected_mode='web')
        self.assertEqual((self.root / 'stripped').read_bytes(), self.base)
        self.assertEqual(self.source.read_bytes(), self.base)

    def test_neither_is_pristine_and_required_presence_is_external(self):
        self.compose(payload=False, expected_mode='neither')
        self.assertEqual((self.root / 'composed').read_bytes(), self.base)
        with self.assertRaisesRegex(ValueError, 'required mode'):
            c.parse_artifact(self.base, self.desc, expected_mode='web')
        with self.assertRaisesRegex(ValueError, 'pristine kernel'):
            c.build_package({}, APP)

    def test_descriptor_pin_complete_base_hash_and_stamp_are_required(self):
        with self.assertRaisesRegex(ValueError, 'descriptor differs'):
            c.compose(self.source, self.manifest, '0' * 64, self.payload, self.root / 'bad')
        changed = bytearray(self.base)
        changed[1000] ^= 1
        with self.assertRaisesRegex(ValueError, 'prefix differs'):
            c.compose_bytes(bytes(changed), self.desc, self.package)
        changed = bytearray(self.base)
        changed[self.boundary + 8:self.boundary + 16] = struct.pack('<Q', len(changed) - 1)
        desc = descriptor(bytes(changed), self.boundary)
        with self.assertRaisesRegex(ValueError, 'pristine-length metadata'):
            c.compose_bytes(bytes(changed), desc, self.package)

    def test_reference_profile_cannot_invent_missing_capabilities(self):
        for change, message in (({'profile': 'minimal'}, 'profile lacks'),
                                ({'abi': {'major': 2, 'minor': 0}}, 'ABI is incompatible')):
            with self.subTest(change=change):
                desc = dict(self.desc, **change)
                with self.assertRaisesRegex(ValueError, message):
                    c.compose_bytes(self.base, desc, self.package)
        required = copy.deepcopy(self.package.index['requires'])
        required['services'] = ['device.uart']
        package = c.build_package({'web/index.html': b'i'}, APP, web_entry='web/index.html', requires=required)
        with self.assertRaisesRegex(ValueError, 'missing required services: device.uart'):
            c.compose_bytes(self.base, self.desc, package)

    def test_every_fixed_trailer_field_checked(self):
        encoded = c.encode_package(self.package)
        for label, offset, replacement in (
                ('magic', 0, b'BADMAGIC'), ('version', 8, struct.pack('<I', 2)),
                ('size', 12, struct.pack('<I', 191)), ('prefix', 16, struct.pack('<Q', 1)),
                ('package', 24, struct.pack('<Q', (1 << 64) - 1)),
                ('index offset', 32, struct.pack('<Q', 0)), ('index size', 40, struct.pack('<Q', 0)),
                ('carrier', 48, struct.pack('<Q', 99)), ('kernel hash', 56, bytes(32)),
                ('package hash', 88, bytes(32)), ('index hash', 120, bytes(32)),
                ('reserved', 152, b'\x01')):
            with self.subTest(label=label):
                changed = bytearray(encoded)
                start = len(changed) - 192 + offset
                changed[start:start + len(replacement)] = replacement
                with self.assertRaises(ValueError):
                    c.parse_artifact(bytes(changed))

    def test_complete_trailer_loss_and_embedded_fake_magic_never_fallback(self):
        native = c.compose_bytes(self.base, self.desc, self.package)
        for removed in (1, 191, 192, 193, len(native) - len(self.base) - 1):
            with self.subTest(removed=removed), self.assertRaises(ValueError):
                c.parse_artifact(native[:-removed], self.desc)
        package = web_package(b'<p>SFAPND01<!--SFAPPEND01--></p>')
        self.assertEqual(c.parse_artifact(c.compose_bytes(self.base, self.desc, package), self.desc).mode, 'web')

    def test_structural_attacks_rehashed_to_avoid_checksum_masking(self):
        mutations = (
            lambda i: i['files'][0].update(offset=1),
            lambda i: i['files'][1].update(offset=0),
            lambda i: i['files'][0].update(length=True),
            lambda i: i['files'][0].update(length=-1),
            lambda i: i['files'].reverse(),
            lambda i: i['files'].append(copy.deepcopy(i['files'][0])),
            lambda i: i['components']['web'].update(present=False, entry=None),
            lambda i: i['components']['web'].update(entry='web/missing.html'),
            lambda i: i['components']['binary'].update(profile='foundation-guest-v1'),
            lambda i: i.update(extra='field'),
            lambda i: i['files'][0].update(extra=1),
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                with self.assertRaises(ValueError):
                    c.parse_artifact(rewritten_package(self.package, mutation))

    def test_duplicate_noncanonical_json_and_floats_fail(self):
        for raw in (b'{"x":1,"x":2}', b'{ "x":1}', b'{"x":1.0}', b'{"x":NaN}', b'{"x":-0}',
                    b'{"z":0,"a":0}', b'{"x":"\\u0061"}', b'{"x":"\\ud800"}'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                c.parse_json(raw)
        self.assertEqual(c.parse_json(b'{"x":1}'), {'x': 1})

    def test_unsafe_resource_names_and_aliases(self):
        for name in ('/a', '../a', 'a/../b', 'a//b', 'C:a', 'a\\b', 'a%20b', 'a?b', 'a#b',
                     'a\x00b', 'a\x7fb', 'a<b', 'a>b', 'a"b', 'a|b', 'a*b', 'caf\xe9.txt', 'a.', 'a ', 'NUL.txt', 'x/CON', '.', ''):
            with self.subTest(name=name), self.assertRaises(ValueError):
                c.resource_path(name)
        for resources in ({'web/index.html': b'i', 'web/INDEX.html': b'j'},
                          {'web/index.html': b'i', 'web/a': b'a', 'web/A/b': b'b'}):
            with self.subTest(resources=resources), self.assertRaisesRegex(ValueError, 'alias'):
                c.build_package(resources, APP, web_entry='web/index.html')

    def test_project_semver_build_identity_and_utf8_name(self):
        app = dict(APP, version='1.0.0-rc.1+build.5', name='Application ' + '\u03bb' * 20)
        package = c.build_package({'web/index.html': b'i'}, app, web_entry='web/index.html')
        self.assertEqual(c.parse_artifact(c.encode_package(package)).package.index['application'], app)
        with self.assertRaisesRegex(ValueError, 'application name'):
            c.build_package({'web/index.html': b'i'}, dict(app, name='\u03bb' * 129), web_entry='web/index.html')

    def test_zero_length_files_cover_no_unexplained_data(self):
        package = c.build_package({'web/empty.txt': b'', 'web/index.html': b'i'}, APP, web_entry='web/index.html')
        parsed = c.parse_artifact(c.encode_package(package))
        self.assertEqual(parsed.package.file_bytes('web/empty.txt'), b'')
        self.assertEqual(parsed.package.file_bytes('web/index.html'), b'i')

    def test_corrupt_file_hash_even_when_outer_hashes_are_recomputed(self):
        encoded = rewritten_package(self.package, lambda i: i['files'][0].update(sha256='0' * 64))
        with self.assertRaisesRegex(ValueError, 'File SHA-256 mismatch'):
            c.parse_artifact(encoded)

    def test_elf_requires_initial_padding_and_valid_load_table(self):
        unpadded = self.base[:-1]
        desc = descriptor(unpadded, self.boundary)
        changed = bytearray(unpadded)
        struct.pack_into('<Q', changed, 64 + 32, len(changed))
        changed[self.boundary + 8:self.boundary + 16] = struct.pack('<Q', len(changed))
        desc['executable']['sha256'] = c.digest(bytes(changed))
        with self.assertRaisesRegex(ValueError, 'padding'):
            c.compose_bytes(bytes(changed), desc, self.package)
        changed = bytearray(self.base)
        struct.pack_into('<Q', changed, 32, (1 << 64) - 1)
        with self.assertRaisesRegex(ValueError, 'program-header'):
            c.compose_bytes(bytes(changed), descriptor(bytes(changed), self.boundary), self.package)

    def test_unsigned_pe32_and_pe32plus_reject_any_security_directory(self):
        for plus in (False, True):
            with self.subTest(plus=plus):
                prefix, boundary = pe_fixture(plus)
                desc = descriptor(prefix, boundary, 'pe')
                self.assertEqual(c.parse_artifact(c.compose_bytes(prefix, desc, self.package), desc).mode, 'web')
                directory = 112 if plus else 96
                for certificate in ((900, 8), (900, 0), (0, 8)):
                    changed = bytearray(prefix)
                    struct.pack_into('<II', changed, 152 + directory + 32, *certificate)
                    with self.assertRaisesRegex(ValueError, 'Signed PE'):
                        c.compose_bytes(bytes(changed), descriptor(bytes(changed), boundary, 'pe'), self.package)

    def test_html_exact_framing_and_same_logical_hash_as_native(self):
        prefix = b'<!doctype html><html><head><meta charset="utf-8"></head><body><!--SFAPPEND01-->'
        desc = descriptor(prefix, None, 'html')
        package = web_package(b'</script></body><!--SFAPPEND01-->')
        html = c.compose_bytes(prefix, desc, package)
        parsed = c.parse_artifact(html, desc)
        native = c.parse_artifact(c.compose_bytes(self.base, self.desc, package), self.desc)
        self.assertEqual(parsed.package.data, native.package.data)
        self.assertEqual(parsed.package.package_sha256, native.package.package_sha256)
        self.assertEqual(c.compose_bytes(html, desc), prefix)
        self.assertEqual(c.parse_artifact(html).mode, 'web')
        for invalid in (html + b' ', html[:-1], html.replace(c.HTML_OPEN, c.HTML_OPEN + b' '),
                        html + html[len(prefix):], html.replace(c.HTML_CLOSE, b'\n' + c.HTML_CLOSE)):
            with self.subTest(invalid=invalid[-30:]), self.assertRaises(ValueError):
                c.parse_artifact(invalid, desc)

    def test_html_shell_parser_state_and_owned_block_are_validated(self):
        for prefix in (
                b'<!doctype html><html><head><script><!--SFAPPEND01-->',
                b'<!doctype html><html><head></head><body><div><!--SFAPPEND01-->',
                b"<!doctype html><html><head></head><body><script id='foundation-appended-v1' type='application/octet-stream'>AA==</script><!--SFAPPEND01-->",
                b'<!doctype html><html><head></head><body><textarea><!--SFAPPEND01-->',
                b'<!doctype html><html><head></head><body><noscript><!--SFAPPEND01-->'):
            with self.subTest(prefix=prefix), self.assertRaises(ValueError):
                c.compose_bytes(prefix, descriptor(prefix, None, 'html'), self.package)

    def test_unpinned_carriers_still_require_valid_native_structure(self):
        prefix = b'not an ELF executable'
        with self.assertRaisesRegex(ValueError, 'ELF kernel header'):
            c.parse_artifact(prefix + self.package.data + c.trailer_bytes(prefix, self.package, 'elf'))
        prefix, _ = pe_fixture()
        signed = bytearray(prefix)
        struct.pack_into('<II', signed, 152 + 96 + 32, 900, 8)
        signed = bytes(signed)
        with self.assertRaisesRegex(ValueError, 'Signed PE'):
            c.parse_artifact(signed + self.package.data + c.trailer_bytes(signed, self.package, 'pe'))

    def test_embedded_html_magic_in_package_does_not_choose_html_parser(self):
        package = web_package(c.HTML_OPEN + b'payload')
        self.assertEqual(c.parse_artifact(c.encode_package(package)).carrier, 'package')

    def test_unpinned_verification_truthfully_reports_no_authentication(self):
        report = c.verify(self.payload)
        self.assertFalse(report['independently_pinned_kernel'])
        self.assertFalse(report['independently_pinned_artifact'])
        self.compose()
        report = c.verify(self.root / 'composed', self.manifest, self.pin)
        self.assertTrue(report['independently_pinned_kernel'])
        with self.assertRaisesRegex(ValueError, 'pinned SHA-256'):
            c.verify(self.payload, expected_sha256='0' * 64)

    def test_existing_symlink_hardlink_and_racing_destination_not_clobbered(self):
        output = self.root / 'output'
        output.write_bytes(b'original')
        with self.assertRaises(ValueError):
            self.compose('output')
        self.assertEqual(output.read_bytes(), b'original')
        output.unlink()
        output.symlink_to(self.source)
        with self.assertRaises(ValueError):
            self.compose('output')
        self.assertEqual(self.source.read_bytes(), self.base)
        output.unlink()
        os.link(self.source, output)
        with self.assertRaises(ValueError):
            self.compose('output')
        output.unlink()
        original_link = os.link
        def racing_link(source, target, **kwargs):
            Path(target).write_bytes(b'racing writer')
            return original_link(source, target, **kwargs)
        with patch.object(c.os, 'link', side_effect=racing_link), self.assertRaises(FileExistsError):
            self.compose('output')
        self.assertEqual(output.read_bytes(), b'racing writer')
        self.assertEqual(list(self.root.glob('.sfappend-*')), [])

    def test_changed_sources_rechecked_before_publication_and_owned_temp_cleaned(self):
        original_recheck = c._recheck
        def mutate_then_recheck(snapshot):
            if snapshot.path == self.source:
                changed = bytearray(self.source.read_bytes())
                changed[1000] ^= 1
                self.source.write_bytes(changed)
            original_recheck(snapshot)
        with patch.object(c, '_recheck', side_effect=mutate_then_recheck), self.assertRaisesRegex(ValueError, 'changed before'):
            self.compose('output')
        self.assertFalse((self.root / 'output').exists())
        self.assertEqual(list(self.root.glob('.sfappend-*')), [])

    def test_replaced_input_identity_even_identical_bytes_is_rejected(self):
        original_recheck = c._recheck
        def replace_then_recheck(snapshot):
            if snapshot.path == self.source:
                moved = self.root / 'replacement'
                moved.write_bytes(self.source.read_bytes())
                moved.chmod(0o755)
                moved.replace(self.source)
            original_recheck(snapshot)
        with patch.object(c, '_recheck', side_effect=replace_then_recheck), self.assertRaisesRegex(ValueError, 'changed before'):
            self.compose('output')
        self.assertFalse((self.root / 'output').exists())

    def test_symlink_input_and_linked_output_parent_rejected(self):
        linked = self.root / 'linked'
        linked.symlink_to(self.source)
        with self.assertRaisesRegex(ValueError, 'Linked input'):
            self.compose(source=linked)
        parent = self.root / 'linked-dir'
        parent.symlink_to(self.root, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'Linked input'):
            c.compose(self.source, self.manifest, self.pin, self.payload, parent / 'output')

    def test_pack_web_tree_and_changes_to_inventory(self):
        web = self.root / 'web'
        web.mkdir()
        (web / 'index.html').write_bytes(b'<h1>local</h1>')
        (web / 'empty').mkdir()
        output = self.root / 'packed'
        report = c.pack(web, None, output, application=APP)
        self.assertEqual(report['mode'], 'web')
        self.assertEqual(c.verify(output)['package_sha256'], report['package_sha256'])
        original_recheck = c._recheck
        def add_file(snapshot):
            if isinstance(snapshot, c._TreeSnapshot):
                (web / 'new.css').write_bytes(b'body{}')
            original_recheck(snapshot)
        with patch.object(c, '_recheck', side_effect=add_file), self.assertRaisesRegex(ValueError, 'inventory changed'):
            c.pack(web, None, self.root / 'changed-pack', application=APP)
        self.assertFalse((self.root / 'changed-pack').exists())

    def test_traversal_errors_fail_closed_without_partial_package(self):
        web = self.root / 'web'
        web.mkdir()
        (web / 'index.html').write_bytes(b'<h1>local</h1>')
        blocked = web / 'unreadable'
        blocked.mkdir()
        scandir = os.scandir
        def deny_child(path):
            if Path(path) == blocked:
                raise PermissionError('fixture unreadable subtree')
            return scandir(path)
        with patch.object(c.os, 'scandir', side_effect=deny_child), self.assertRaisesRegex(ValueError, 'traversal failed'):
            c.pack(web, None, self.root / 'partial', application=APP)
        self.assertFalse((self.root / 'partial').exists())

    def test_boundary_stamp_cannot_live_in_writable_native_data(self):
        changed = bytearray(self.base)
        struct.pack_into('<I', changed, 64 + 4, 7)
        with self.assertRaisesRegex(ValueError, 'immutable native data'):
            c.compose_bytes(bytes(changed), descriptor(bytes(changed), self.boundary), self.package)
        prefix, boundary = pe_fixture()
        changed = bytearray(prefix)
        struct.pack_into('<I', changed, 152 + 224 + 36, 0xc0000000)
        with self.assertRaisesRegex(ValueError, 'immutable native data'):
            c.compose_bytes(bytes(changed), descriptor(bytes(changed), boundary, 'pe'), self.package)

    def test_cli_pack_uses_config_identity_and_rechecks_it_before_publication(self):
        import appended_project
        web = self.root / 'web'
        web.mkdir()
        (web / 'index.html').write_bytes(b'<h1>CLI</h1>')
        config = appended_project.default_document()
        config['appended']['web'] = {'enabled': True, 'source': 'web', 'entry': 'index.html'}
        config['application']['version'] = '1.2.3+build.4'
        config_path = self.root / appended_project.CONFIG_NAME
        config_path.write_text(json.dumps(config))
        output = self.root / 'cli.sfapp'
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(c.main(['pack', '--project-root', str(self.root), '--output', str(output)]), 0)
        parsed = c.parse_artifact(output.read_bytes())
        self.assertEqual(parsed.package.index['application']['version'], '1.2.3+build.4')
        self.assertEqual(parsed.package.index['identities']['project-config'], c.digest(config_path.read_bytes()))
        original_recheck = c._recheck
        def mutate_config(snapshot):
            if snapshot.path == config_path:
                config_path.write_bytes(snapshot.content + b' ')
            original_recheck(snapshot)
        with patch.object(c, '_recheck', side_effect=mutate_config), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(c.main(['pack', '--project-root', str(self.root), '--output', str(self.root / 'changed.sfapp')]), 1)
        self.assertFalse((self.root / 'changed.sfapp').exists())

    def _cli_binary_project(self):
        import appended_project
        source = self.root / 'src-bin-appended'
        source.mkdir()
        (source / 'application.c').write_bytes(b'int application(void) { return 0; }\n')
        config = appended_project.default_document()
        config['appended']['binary']['enabled'] = True
        config_path = self.root / appended_project.CONFIG_NAME
        config_path.write_text(json.dumps(config))
        spec = importlib.util.spec_from_file_location('appended_requirement_vectors', ROOT / 'tests/test_appended_wasm.py')
        vectors = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(vectors)
        prepared = self.root / 'prepared.wasm'
        prepared.write_bytes(vectors.module())
        return prepared, config_path

    def _cli(self, arguments):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = c.main(arguments)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_cli_pack_explicit_requirements_are_canonical_and_preserve_inputs(self):
        prepared, config = self._cli_binary_project()
        originals = {path: path.read_bytes() for path in (prepared, config, self.source, self.manifest)}
        flags = ['--require-service', 'org.example.provider', '--require-service', 'foundation.view',
                 '--require-capability', 'foundation.view.v1', '--require-capability', 'org.example.provider',
                 '--require-abi-minor', '65535']
        first, second = self.root / 'requirements.sfapp', self.root / 'same-requirements.sfapp'
        with patch.object(subprocess, 'run', side_effect=AssertionError('forbidden process')), \
             patch.object(subprocess, 'Popen', side_effect=AssertionError('forbidden process')):
            code, _, error = self._cli(['pack', '--project-root', str(self.root), '--binary-module', str(prepared),
                                        '--output', str(first), *flags])
            self.assertEqual(code, 0, error)
            # A different option order must freeze the exact same package.
            reverse_flags = ['--require-abi-minor', '65535', '--require-capability', 'org.example.provider',
                             '--require-capability', 'foundation.view.v1', '--require-service', 'foundation.view',
                             '--require-service', 'org.example.provider']
            code, _, error = self._cli(['pack', '--project-root', str(self.root), '--binary-module', str(prepared),
                                        '--output', str(second), *reverse_flags])
            self.assertEqual(code, 0, error)
        self.assertEqual(first.read_bytes(), second.read_bytes())
        package = c.parse_artifact(first.read_bytes()).package
        self.assertEqual(package.index['requires'], {'abi': {'major': 1, 'minor': 65535},
                         'services': ['foundation.view', 'org.example.provider'],
                         'capabilities': ['foundation.view.v1', 'org.example.provider']})
        self.assertEqual(package.file_bytes('binary/application.wasm'), originals[prepared])
        compatible = dict(self.desc, profile='binary', abi={'major': 1, 'minor': 65535},
                          services=package.index['requires']['services'],
                          capabilities=package.index['requires']['capabilities'])
        compatible_path = self.root / 'compatible-kernel.json'
        compatible_path.write_bytes(c.canonical_json(compatible))
        with patch.object(subprocess, 'run', side_effect=AssertionError('forbidden process')), \
             patch.object(subprocess, 'Popen', side_effect=AssertionError('forbidden process')):
            code, _, error = self._cli(['compose', '--input', str(self.source), '--kernel-descriptor', str(compatible_path),
                                       '--kernel-descriptor-sha256', c.digest(compatible_path.read_bytes()),
                                       '--package', str(first), '--output', str(self.root / 'compatible'),
                                       '--expected-mode', 'binary'])
            self.assertEqual(code, 0, error)
        self.assertEqual(c.parse_artifact((self.root / 'compatible').read_bytes(), compatible).package.index['requires'],
                         package.index['requires'])
        self.assertEqual({path: path.read_bytes() for path in originals}, originals)

    def test_cli_required_kernel_mismatches_reject_before_output_creation(self):
        prepared, config = self._cli_binary_project()
        output = self.root / 'requires.sfapp'
        code, _, error = self._cli(['pack', '--project-root', str(self.root), '--binary-module', str(prepared),
                                   '--output', str(output), '--require-service', 'foundation.view',
                                   '--require-capability', 'foundation.view.v1', '--require-abi-minor', '2'])
        self.assertEqual(code, 0, error)
        compatible = dict(self.desc, profile='binary', abi={'major': 1, 'minor': 2},
                          services=['foundation.view'], capabilities=['foundation.view.v1'])
        originals = {path: path.read_bytes() for path in (prepared, config, self.source, output)}
        for label, change, message in (('service', {'services': []}, 'missing required services'),
                                       ('capability', {'capabilities': []}, 'missing required capabilities'),
                                       ('minor', {'abi': {'major': 1, 'minor': 1}}, 'ABI is incompatible')):
            descriptor_path = self.root / (label + '-kernel.json')
            descriptor_path.write_bytes(c.canonical_json(dict(compatible, **change)))
            destination = self.root / (label + '-output')
            with self.subTest(label=label), patch.object(c, '_write_new', side_effect=AssertionError('output attempted')), \
                 patch.object(subprocess, 'Popen', side_effect=AssertionError('forbidden process')):
                code, _, error = self._cli(['compose', '--input', str(self.source), '--kernel-descriptor', str(descriptor_path),
                                           '--kernel-descriptor-sha256', c.digest(descriptor_path.read_bytes()),
                                           '--package', str(output), '--output', str(destination)])
                self.assertEqual(code, 1)
                self.assertIn(message, error)
                self.assertFalse(destination.exists())
        self.assertEqual({path: path.read_bytes() for path in originals}, originals)
        self.assertEqual(list(self.root.glob('.sfappend-*')), [])

    def test_cli_invalid_requirements_fail_before_configuration_or_source_reads(self):
        import appended_project
        invalid = [(['--require-service', name], 'services')
                   for name in ('', 'bad name', 'bad/name', 'bad\nname', '\u03bb', 'a' * 129)]
        invalid.extend((['--require-capability', name], 'capabilities')
                       for name in ('', '.bad', 'bad:name', 'a' * 129))
        invalid.extend(((['--require-service', 'foundation.view', '--require-service', 'foundation.view'], 'Duplicate required service'),
                        (['--require-capability', 'foundation.view.v1', '--require-capability', 'foundation.view.v1'], 'Duplicate required capability'),
                        (['--require-abi-minor', '-1'], 'ABI minor'), (['--require-abi-minor', '65536'], 'ABI minor')))
        invalid.append(([flag for n in range(4097) for flag in ('--require-service', 'provider' + str(n))], 'services'))
        for flags, message in invalid:
            with self.subTest(flags=flags[:4]), patch.object(appended_project, 'load_project', side_effect=AssertionError('config inspected')):
                code, _, error = self._cli(['pack', '--project-root', str(self.root / 'absent'),
                                           '--output', str(self.root / 'invalid.sfapp'), *flags])
                self.assertEqual(code, 1)
                self.assertIn(message, error)
                self.assertFalse((self.root / 'invalid.sfapp').exists())
        with patch.object(appended_project, 'load_project', side_effect=AssertionError('config inspected')), \
             contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
            c.main(['pack', '--output', str(self.root / 'invalid.sfapp'), '--require-abi-minor', '1.5'])
        self.assertEqual(raised.exception.code, 2)

    def test_cli_requirement_defaults_and_maximum_service_count(self):
        prepared, _ = self._cli_binary_project()
        output = self.root / 'default.sfapp'
        base_args = ['pack', '--project-root', str(self.root), '--binary-module', str(prepared)]
        code, _, error = self._cli([*base_args, '--output', str(output)])
        self.assertEqual(code, 0, error)
        self.assertEqual(c.parse_artifact(output.read_bytes()).package.index['requires'],
                         {'abi': {'major': 1, 'minor': 0}, 'services': [], 'capabilities': []})
        explicit = self.root / 'explicit-default.sfapp'
        code, _, error = self._cli([*base_args, '--output', str(explicit), '--require-abi-minor', '0'])
        self.assertEqual(code, 0, error)
        self.assertEqual(explicit.read_bytes(), output.read_bytes())
        flags = [flag for n in range(4096) for flag in ('--require-service', 'provider' + str(n))]
        maximum = self.root / 'maximum.sfapp'
        code, _, error = self._cli([*base_args, '--output', str(maximum), *flags,
                                   '--require-capability', 'a' * 128])
        self.assertEqual(code, 0, error)
        index = c.parse_artifact(maximum.read_bytes()).package.index
        self.assertEqual(len(index['requires']['services']), 4096)
        self.assertEqual(index['requires']['capabilities'], ['a' * 128])

    def test_four_modes_component_removal_and_carrier_package_identity(self):
        # The Wasm suite's independent full scalar-ABI vector is intentionally
        # reused as prepared bytes, without invoking a compiler or runtime.
        spec = importlib.util.spec_from_file_location('appended_wasm_vectors', ROOT / 'tests/test_appended_wasm.py')
        vectors = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(vectors)
        module = vectors.module()
        binary = c.build_package({'binary/application.wasm': module}, APP,
                                 binary_entry='binary/application.wasm', binary_profile=c.BINARY_PROFILE)
        both = c.build_package({'binary/application.wasm': module, 'web/index.html': b'<h1>both</h1>'}, APP,
                               web_entry='web/index.html', binary_entry='binary/application.wasm',
                               binary_profile=c.BINARY_PROFILE)
        desc = dict(self.desc, profile='both')
        artifact = self.base
        for package, mode in ((self.package, 'web'), (both, 'both'), (binary, 'binary'), (None, 'neither')):
            artifact = c.compose_bytes(artifact, desc, package, expected_mode=mode)
            parsed = c.parse_artifact(artifact, desc, expected_mode=mode)
            self.assertEqual(parsed.prefix, self.base)
            if mode in ('binary', 'both'):
                self.assertEqual(parsed.package.file_bytes('binary/application.wasm'), module)
            if mode == 'binary':
                self.assertFalse(any(e['path'].startswith('web/') for e in parsed.package.index['files']))
        self.assertEqual(artifact, self.base)
        pe, boundary = pe_fixture()
        html = b'<!doctype html><html><head></head><body><!--SFAPPEND01-->'
        for prefix, manifest in ((self.base, desc), (pe, descriptor(pe, boundary, 'pe', 'both')),
                                 (html, descriptor(html, None, 'html', 'both'))):
            parsed = c.parse_artifact(c.compose_bytes(prefix, manifest, both), manifest)
            self.assertEqual(parsed.package.package_sha256, both.package_sha256)
            self.assertEqual(parsed.package.payload_id, both.payload_id)
            self.assertEqual(parsed.package.data, both.data)

    def test_stamp_virtual_page_cannot_be_shadowed_by_writable_load(self):
        # Independent ELF program-header vectors: no executable probe is used.
        # The second load need not own the stamp's file bytes to change the
        # effective permissions of its virtual page.
        for writable_offset, writable_size, writable_virtual, writable_memory in (
                (0, 4096, 0x400000, 4096),
                (0, 16, 0x400800, 16),
                (4096, 0, 0x400100, 16)):
            prefix = bytearray(self.base)
            struct.pack_into('<H', prefix, 56, 2)
            struct.pack_into('<IIQQQQQQ', prefix, 120, 1, 6, writable_offset,
                             writable_virtual, writable_virtual, writable_size,
                             writable_memory, 4096)
            desc = descriptor(bytes(prefix), self.boundary)
            with self.subTest(mapping=(writable_offset, writable_virtual)):
                with self.assertRaisesRegex(ValueError, 'Writable ELF load overlaps'):
                    c.compose_bytes(bytes(prefix), desc, self.package)
        # An unrelated virtual private mapping of the same file bytes does not
        # make the authoritative constant writable.
        prefix = bytearray(self.base)
        struct.pack_into('<H', prefix, 56, 2)
        struct.pack_into('<IIQQQQQQ', prefix, 120, 1, 6, 0, 0x500000, 0x500000,
                         4096, 4096, 4096)
        desc = descriptor(bytes(prefix), self.boundary)
        self.assertEqual(c.parse_artifact(c.compose_bytes(bytes(prefix), desc, self.package), desc).mode, 'web')

    def test_binary_packing_cannot_accept_unvalidated_wasm(self):
        with self.assertRaises(ValueError):
            c.build_package({'binary/application.wasm': b'\0asm\x01\0\0\0'}, APP,
                            binary_entry='binary/application.wasm', binary_profile=c.BINARY_PROFILE)
        with self.assertRaisesRegex(ValueError, 'profile'):
            c.build_package({'binary/application.wasm': b'fake'}, APP,
                            binary_entry='binary/application.wasm', binary_profile='native-dll')

    def _rich_project(self, *, both=False, primary='web'):
        import appended_project
        binary, config_path = self._cli_binary_project() if both else (None, self.root / appended_project.CONFIG_NAME)
        config = json.loads(config_path.read_bytes()) if both else appended_project.default_document()
        web = self.root / 'src-web-appended'
        web.mkdir()
        (web / 'index.html').write_bytes(b'<h1>Retained application</h1>')
        config['application'] = dict(APP)
        config['appended']['web'] = {'enabled': True, 'source': web.name, 'entry': 'index.html'}
        config['startup']['primary'] = primary
        config_path.write_bytes(c.canonical_json(config))
        return web, binary, config_path

    def _startup_package(self, metadata=None, *, path=c.STARTUP_PATH, requires=None, extra=None):
        files = {'web/index.html': b'<h1>Retained application</h1>'}
        if path is not None:
            files[path] = (b'{"kind":"foundation-appended-startup","primary":"web","schema_version":1}'
                           if metadata is None else metadata)
        files.update(extra or {})
        return c.build_package(files, APP, web_entry='web/index.html', requires=requires or {
            'abi': {'major': 1, 'minor': 0}, 'services': [], 'capabilities': ['foundation.startup.v1']})

    def test_rich_pack_is_explicit_deterministic_and_reappends_without_rebuilding(self):
        web, binary, config = self._rich_project(both=True)
        first, same = self.root / 'rich.sfapp', self.root / 'same-rich.sfapp'
        requires = {'abi': {'major': 1, 'minor': 0}, 'services': ['org.example.provider'],
                    'capabilities': ['org.example.capability']}
        original_requires = copy.deepcopy(requires)
        originals = {path: path.read_bytes() for path in (binary, config, self.source, self.manifest)}
        with patch.object(subprocess, 'run', side_effect=AssertionError('forbidden process')), \
             patch.object(subprocess, 'Popen', side_effect=AssertionError('forbidden process')):
            report = c.pack_project(self.root, binary, first, rich_startup=True, requires=requires)
            c.pack_project(self.root, binary, same, rich_startup=True, requires=requires)
            self.assertEqual(first.read_bytes(), same.read_bytes())
            frozen_output = first.read_bytes()
            with self.assertRaisesRegex(ValueError, 'destination must be new'):
                c.pack_project(self.root, binary, first, rich_startup=True, requires=requires)
            self.assertEqual(first.read_bytes(), frozen_output)
            self.assertEqual(report['mode'], 'both')
            package = c.parse_artifact(first.read_bytes()).package
            self.assertEqual(c.validate_rich_startup(package), {
                'kind': 'foundation-appended-startup', 'primary': 'web', 'schema_version': 1})
            self.assertEqual(package.file_bytes(c.STARTUP_PATH),
                             b'{"kind":"foundation-appended-startup","primary":"web","schema_version":1}')
            startup = next(entry for entry in package.index['files'] if entry['path'] == c.STARTUP_PATH)
            self.assertEqual((startup['component'], startup['media_type']), ('web', 'application/json'))
            self.assertEqual(package.index['requires']['capabilities'],
                             ['foundation.startup.v1', 'org.example.capability'])
            rich_descriptor = dict(self.desc, profile='both', services=['org.example.provider'],
                                   capabilities=package.index['requires']['capabilities'])
            manifest = self.root / 'rich-kernel.json'
            manifest.write_bytes(c.canonical_json(rich_descriptor))
            pin = c.digest(manifest.read_bytes())
            composed, replaced = self.root / 'rich-composed', self.root / 'rich-replaced'
            c.compose(self.source, manifest, pin, first, composed)
            (web / 'index.html').write_bytes(b'<h1>Changed application</h1>')
            newer = self.root / 'new-rich.sfapp'
            c.pack_project(self.root, binary, newer, rich_startup=True, requires=requires)
            c.compose(composed, manifest, pin, newer, replaced)
        parsed = c.parse_artifact(replaced.read_bytes(), rich_descriptor)
        self.assertEqual(parsed.prefix, self.base)
        self.assertEqual(replaced.stat().st_size, len(self.base) + len(newer.read_bytes()))
        self.assertEqual(parsed.package.file_bytes('binary/application.wasm'), originals[binary])
        self.assertEqual(parsed.package.file_bytes('web/index.html'), b'<h1>Changed application</h1>')
        self.assertEqual(c.validate_rich_startup(parsed.package)['primary'], 'web')
        self.assertEqual(requires, original_requires)
        self.assertEqual({path: path.read_bytes() for path in originals}, originals)

    def test_rich_cli_requires_explicit_supported_primary_before_source_collection(self):
        web, binary, config_path = self._rich_project(both=True, primary='compiled')
        original = config_path.read_bytes()
        for primary in ('compiled', 'binary'):
            config = json.loads(original)
            config['startup']['primary'] = primary
            config_path.write_bytes(c.canonical_json(config))
            output = self.root / (primary + '.sfapp')
            with self.subTest(primary=primary):
                code, _, error = self._cli(['pack', '--project-root', str(self.root), '--binary-module', str(binary),
                                           '--rich-startup', '--output', str(output)])
                self.assertEqual(code, 0, error)
                package = c.parse_artifact(output.read_bytes()).package
                self.assertEqual(c.validate_rich_startup(package), {
                    'kind': 'foundation-appended-startup', 'primary': primary, 'schema_version': 2})
                self.assertIn(c.COMPOSITION_STARTUP_PATH, [entry['path'] for entry in package.index['files']])
                self.assertNotIn(c.STARTUP_PATH, [entry['path'] for entry in package.index['files']])
                required = package.index['requires']
                self.assertIn(c.STARTUP_CAPABILITY, required['capabilities'])
                self.assertIn(c.GUI_COMPOSITION_CAPABILITY, required['capabilities'])
                if primary == 'binary':
                    self.assertTrue(package.index['components']['binary']['present'])
                    self.assertIn('foundation.view', required['services'])
                    self.assertIn('foundation.view.v1', required['capabilities'])
                # Isolate the new missing capability without executing a kernel.
                old_descriptor = {'profile': 'both', 'abi': {'major': 1, 'minor': 0},
                    'services': list(required['services']),
                    'capabilities': [name for name in required['capabilities'] if name != c.GUI_COMPOSITION_CAPABILITY]}
                with self.assertRaisesRegex(ValueError, 'foundation.gui-composition.v1'):
                    c._compatible(package, old_descriptor)
        config = json.loads(original)
        config['startup']['primary'] = 'web'
        config_path.write_bytes(c.canonical_json(config))
        output = self.root / 'explicit-web.sfapp'
        code, _, error = self._cli(['pack', '--project-root', str(self.root), '--binary-module', str(binary),
                                   '--rich-startup', '--output', str(output)])
        self.assertEqual(code, 0, error)
        self.assertEqual(c.validate_rich_startup(c.parse_artifact(output.read_bytes()).package)['primary'], 'web')
        legacy = self.root / 'explicit-web-legacy.sfapp'
        c.pack_project(self.root, binary, legacy)
        self.assertNotIn(c.STARTUP_PATH, [entry['path'] for entry in c.parse_artifact(legacy.read_bytes()).package.index['files']])

    def test_rich_namespace_rejects_files_directories_and_case_aliases_before_output(self):
        web, _, _ = self._rich_project()
        for name, directory in (('.foundation', False), ('.foundation', True), ('.FOUNDATION', True),
                                ('.FoUnDaTiOn', False)):
            reserved = web / name
            if directory:
                reserved.mkdir()
            else:
                reserved.write_bytes(b'user supplied')
            destination = self.root / ('namespace-' + name + '-' + str(directory))
            with self.subTest(name=name, directory=directory), \
                 patch.object(c, '_write_new', side_effect=AssertionError('output attempted')):
                with self.assertRaisesRegex(ValueError, 'reserves the web/.foundation namespace'):
                    c.pack_project(self.root, None, destination, rich_startup=True)
            self.assertFalse(destination.exists())
            reserved.rmdir() if directory else reserved.unlink()
        (web / '.foundationx').mkdir()
        (web / '.foundationx/ordinary.txt').write_bytes(b'not reserved')
        c.pack_project(self.root, None, self.root / 'allowed', rich_startup=True)
        self.assertEqual(c.validate_rich_startup(c.parse_artifact((self.root / 'allowed').read_bytes()).package)['primary'], 'web')
        with patch.object(c, '_write_new', side_effect=AssertionError('output attempted')), \
             self.assertRaisesRegex(ValueError, 'missing required capabilities'):
            c.compose(self.source, self.manifest, self.pin, self.root / 'allowed', self.root / 'incapable-kernel')
        self.assertFalse((self.root / 'incapable-kernel').exists())

    def test_rich_metadata_admission_rejects_missing_alias_unknown_and_noncanonical_records(self):
        canonical = {'kind': 'foundation-appended-startup', 'primary': 'web', 'schema_version': 1}
        malformed = [b'{}', b'{', c.canonical_json(dict(canonical, schema_version=True)),
                     c.canonical_json(dict(canonical, schema_version=2)), c.canonical_json(dict(canonical, extra='ignored')),
                     c.canonical_json(dict(canonical, primary='compiled')), c.canonical_json(dict(canonical, primary='binary')),
                     c.canonical_json(dict(canonical, kind='foreign-startup')),
                     c.canonical_json(canonical) + b'\n',
                     b'{"kind":"foundation-appended-startup","primary":"web","schema_version":1,"schema_version":1}']
        for metadata in malformed:
            with self.subTest(metadata=metadata), self.assertRaises(ValueError):
                c.validate_rich_startup(self._startup_package(metadata))
        for package in (self._startup_package(path=None),
                        self._startup_package(path='web/.FOUNDATION/startup-v1.json'),
                        self._startup_package(extra={'web/.foundation/other.json': b'{}'}),
                        self._startup_package(requires={'abi': {'major': 1, 'minor': 0}, 'services': [], 'capabilities': []})):
            with self.subTest(paths=[entry['path'] for entry in package.index['files']]), self.assertRaises(ValueError):
                c.validate_rich_startup(package)
        wrong_media = c.parse_artifact(rewritten_package(self._startup_package(), lambda index:
            next(entry for entry in index['files'] if entry['path'] == c.STARTUP_PATH).__setitem__('media_type', 'text/plain'))).package
        with self.assertRaisesRegex(ValueError, 'application/json'):
            c.validate_rich_startup(wrong_media)
        oversized = self._startup_package(b'x' * (c.MAX_STARTUP + 1))
        original_parse = c.parse_json
        def no_startup_decode(data, label='JSON'):
            self.assertNotEqual(label, 'startup metadata', 'oversized metadata was decoded')
            return original_parse(data, label)
        with patch.object(c, 'parse_json', side_effect=no_startup_decode), self.assertRaisesRegex(ValueError, '4 KiB'):
            c.validate_rich_startup(oversized)

    def test_rich_admission_uses_actual_package_bytes_and_rejects_view_requirements(self):
        package = self._startup_package()
        package.index['requires']['capabilities'] = []
        with self.assertRaisesRegex(ValueError, 'index differs from its actual'):
            c.validate_rich_startup(package)
        with self.assertRaisesRegex(ValueError, 'actual verified Package'):
            c.validate_rich_startup({'index': self._startup_package().index})
        web, binary, _ = self._rich_project(both=True)
        for field in ('services', 'capabilities'):
            for name in ('foundation.view', 'foundation.view.v1'):
                required = {'abi': {'major': 1, 'minor': 0}, 'services': [], 'capabilities': ['foundation.startup.v1']}
                required[field] = sorted(set(required[field]) | {name})
                with self.subTest(field=field, name=name):
                    with self.assertRaisesRegex(ValueError, 'secondary views are unsupported'):
                        c.validate_rich_startup(self._startup_package(requires=required))
                    with patch.object(c, '_tree_inventory', side_effect=AssertionError('source traversed')), \
                         patch.object(c, '_audit_module', side_effect=AssertionError('module audited')), \
                         patch.object(c, '_write_new', side_effect=AssertionError('output attempted')), \
                         self.assertRaisesRegex(ValueError, 'secondary views are unsupported'):
                        c.pack_project(self.root, binary, self.root / 'view-rejected', rich_startup=True, requires=required)
        self.assertFalse((self.root / 'view-rejected').exists())

    def test_rich_generation_counts_toward_file_byte_and_capability_limits(self):
        web, _, _ = self._rich_project()
        with patch.object(c, 'MAX_FILES', 1), self.assertRaisesRegex(ValueError, 'bounded nonempty file inventory'):
            c.pack_project(self.root, None, self.root / 'too-many', rich_startup=True)
        required = {'abi': {'major': 1, 'minor': 0}, 'services': [],
                    'capabilities': ['capability' + str(n).zfill(4) for n in range(4096)]}
        with patch.object(c, '_tree_inventory', side_effect=AssertionError('source traversed')), \
             self.assertRaisesRegex(ValueError, 'capabilities'):
            c.pack_project(self.root, None, self.root / 'too-many-capabilities', rich_startup=True, requires=required)
        with patch.object(c, 'MAX_PACKAGE', 80), self.assertRaisesRegex(ValueError, 'bounded ordinary input'):
            c.pack_project(self.root, None, self.root / 'too-many-bytes', rich_startup=True)
        for name in ('too-many', 'too-many-capabilities', 'too-many-bytes'):
            self.assertFalse((self.root / name).exists())

    def test_pack_rechecks_web_root_identity_and_bounds_collection_before_allocation(self):
        web, _, _ = self._rich_project()
        replacement = self.root / 'preexisting-web'
        replacement.mkdir()
        os.link(web / 'index.html', replacement / 'index.html')
        saved_file = (web / 'index.html').stat()
        original_recheck = c._recheck
        def replace_root(snapshot):
            if isinstance(snapshot, c._TreeSnapshot):
                web.rename(self.root / 'old-web')
                replacement.rename(web)
                self.assertEqual((web / 'index.html').stat().st_ino, saved_file.st_ino)
            original_recheck(snapshot)
        with patch.object(c, '_recheck', side_effect=replace_root), self.assertRaisesRegex(ValueError, 'inventory changed'):
            c.pack_project(self.root, None, self.root / 'replaced-root', rich_startup=True)
        self.assertFalse((self.root / 'replaced-root').exists())
        (web / 'index.html').write_bytes(b'x' * 6)
        (web / 'second.txt').write_bytes(b'y' * 6)
        original_snapshot, bounds = c._snapshot, []
        def observe_bound(path, limit=c.MAX_ARTIFACT):
            if Path(path).parent == web:
                bounds.append(limit)
            return original_snapshot(path, limit)
        with patch.object(c, 'MAX_PACKAGE', 10), patch.object(c, '_snapshot', side_effect=observe_bound), \
             self.assertRaisesRegex(ValueError, 'bounded ordinary input'):
            c.pack(web, None, self.root / 'bounded-collection', application=APP)
        self.assertEqual(bounds, [10, 4])
        self.assertFalse((self.root / 'bounded-collection').exists())

    def test_legacy_binary_literal_bytes_and_legacy_web_startup_remain_unchanged(self):
        module = bytes.fromhex(
            '0061736d010000000121066000017f60017f017f60027f7f0060027f7f017f60017f0060047f7f7f7f017f'
            '0308070001020303010405040101011007c1010815666f756e646174696f6e5f6170705f6162695f76310000'
            '17666f756e646174696f6e5f6170705f616c6c6f635f7631000116666f756e646174696f6e5f6170705f6672'
            '65655f7631000216666f756e646174696f6e5f6170705f696e69745f763100031a666f756e646174696f6e5f'
            '6170705f64697370617463685f7631000416666f756e646174696f6e5f6170705f737465705f763100051a66'
            '6f756e646174696f6e5f6170705f73687574646f776e5f76310006066d656d6f727902000a2007040041000b'
            '040020000b02000b040041000b040041000b040020000b02000b')
        expected_index = (
            b'{"application":{"id":"org.example.fixture","name":"Fixture","version":"1.0.0"},'
            b'"components":{"binary":{"entry":"binary/application.wasm","present":true,"profile":"foundation-guest-v1"},'
            b'"web":{"entry":null,"present":false}},"files":[{"component":"binary","length":289,"media_type":"application/wasm",'
            b'"offset":0,"path":"binary/application.wasm","sha256":"b44c949c1bab64b818355a1d03264dd182cead87d322758926df92edaaa67df0"}],'
            b'"identities":{},"kind":"foundation-appended-package","requires":{"abi":{"major":1,"minor":0},'
            b'"capabilities":[],"services":[]},"schema_version":1}')
        package = c.build_package({'binary/application.wasm': module}, APP,
                                  binary_entry='binary/application.wasm', binary_profile=c.BINARY_PROFILE)
        self.assertEqual(package.data, module + expected_index)
        self.assertEqual(c.digest(c.encode_package(package)), 'bdf672e036572545380685b975867377264203aa330f7f651746dfbced89060b')
        prepared, output = self.root / 'legacy.wasm', self.root / 'legacy-binary.sfapp'
        prepared.write_bytes(module)
        c.pack(None, prepared, output, application=APP)
        self.assertEqual(output.read_bytes(), c.encode_package(package))
        with self.assertRaisesRegex(ValueError, 'present web component'):
            c.validate_rich_startup(package)
        legacy_web = self._startup_package(path='web/.foundation/user.json', requires={
            'abi': {'major': 1, 'minor': 0}, 'services': [], 'capabilities': []})
        self.assertEqual(c.parse_artifact(c.encode_package(legacy_web)).package.data, legacy_web.data)
        with self.assertRaisesRegex(ValueError, 'missing required capability'):
            c.validate_rich_startup(legacy_web)

    def test_pure_composition_has_no_compiler_linker_install_process(self):
        with patch.object(subprocess, 'run', side_effect=AssertionError('forbidden process')), \
             patch.object(subprocess, 'Popen', side_effect=AssertionError('forbidden process')):
            self.compose()
            c.strip(self.root / 'composed', self.manifest, self.pin, self.root / 'stripped')
        self.assertEqual((self.root / 'stripped').read_bytes(), self.base)


if __name__ == '__main__':
    unittest.main()
