"""Small synthetic source capsules; no SDK/program/archive body is inspected."""
import ast
import copy
from contextlib import redirect_stderr, redirect_stdout
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import appended_engine_windows_handoff as handoff
import appended_engine_native_actions_contract as actions
import appended_engine_windows_contract as contract


def pin(raw):
    return hashlib.sha256(raw).hexdigest()


def inventory(files):
    directories = sorted({parent.as_posix() for name in files
        for parent in Path(name).parents if parent.as_posix() != '.'})
    return {'files': {name: pin(raw) for name, raw in files.items()},
        'directories': directories,
        'modes': {**{name: 0o644 for name in files}, **{name: 0o755 for name in directories}}}


def reference(path):
    return {'path': path, 'sha256': pin(path.encode())}


def native_inputs():
    prefix = 'C:/retained/deps'
    return {'schema_version': 1, 'kind': 'foundation-native-engine-windows-inputs',
        'target': 'windows-x86_64', 'build_type': 'Release', 'crt': 'static-mt',
        'cpu_baseline': 'x86_64-sse2', 'os_floor_declaration': 'windows-10-1809-unqualified',
        'engine_cxx_standard': 23, 'dependency_prefix': prefix, 'woff2': 'OFF',
        'toolchain': {'compiler': reference('C:/retained/llvm/clang-cl.exe'),
            'linker': reference('C:/retained/llvm/lld-link.exe'),
            'builtins': reference('C:/retained/llvm/builtins.lib'), 'compiler_version': '19.1.7',
            'msvc_stl': {'root': 'C:/retained/msvc', 'inventory': reference('C:/records/msvc.json')},
            'windows_sdk': {'root': 'C:/retained/sdk', 'inventory': reference('C:/records/sdk.json')}},
        'dependency_inventory': reference('C:/records/deps.json'),
        'libraries': {name: {**reference(prefix + '/lib/' + name.replace('::', '_') + '.lib'),
            'includes': [prefix + '/include'], 'definitions': ['STATIC_BUILD=1'],
            'links': ['ws2_32', 'WebP::sharpyuv'] if name == 'WebP::libwebp' else ['ws2_32']}
            for name in sorted(contract.LIBRARIES)}}


class Fixture:
    def __init__(self, root):
        self.root = root
        self.retained, self.assembled = root / 'retained-original', root / 'assembled-original'
        # Read only the frozen metadata generator source as data. These fixtures
        # never inspect the concurrently maintained real map/provenance or tree.
        generator_path = ROOT / contract.RECIPE / 'runtime/generate_native_actions_metadata.py'
        generator_ast = ast.parse(generator_path.read_text())
        fixed_pins = next(ast.literal_eval(item.value) for item in generator_ast.body
            if isinstance(item, ast.Assign) and any(isinstance(name, ast.Name) and name.id == 'PINS' for name in item.targets))
        self.interfaces = {name: {'retained_logical_path': record[0], 'sha256': record[1]}
                           for name, record in fixed_pins.items()}
        self.mapping = {item['retained_logical_path']: {'tracked_source': 'source/foundation/' + item['retained_logical_path'],
            'role': 'interface', 'sha256': item['sha256']} for item in self.interfaces.values()}
        aliases = {handoff.CONFIG: ('prelink-config.json', 'config'),
            handoff.GENERATOR: ('runtime/generate_native_actions_metadata.py', 'helper'),
            handoff.TEMPLATE: ('runtime/native-provider-actions-metadata.h.in', 'config')}
        aliases.update({name: ('helpers/' + name, 'helper') for name in (
            'tools/appended_engine_document_contract.py', 'tools/appended_engine_editor_contract.py',
            'tools/appended_engine_native_actions_contract.py', 'tools/appended_engine_manifest.py',
            'tools/appended_engine_sdk.py', 'tools/dependency_archive.py')})
        self.mapping.update({name: {'tracked_source': tracked, 'role': role, 'sha256': '1' * 64}
            for name, (tracked, role) in aliases.items()})
        self.files, entries = {}, {}
        def source(name, raw, role):
            self.files[name] = raw
            entries[name] = {'sha256': pin(raw), 'mode': 0o644, 'role': role,
                'bytes': len(raw), 'tracked_path': contract.RECIPE + '/' + name,
                'origin': {'kind': 'synthetic-test-source'}}
        for index in range(157):
            name = ('source/engine/unit' if index < 48 else 'source/document-provider/unit') + str(index) + '.cpp'
            source(name, ('// synthetic ' + str(index) + '\n').encode(), 'source')
        self.graph = b'set(_sources\n' + b'\n'.join(('"fixture' + str(i) + '.cpp"').encode() for i in range(32)) + b'\n)\n# document_forms\n'
        source('cmake/native-provider.cmake', self.graph, 'config')
        for name, item in self.mapping.items():
            tracked = item['tracked_source']
            if item['role'] == 'interface' or tracked.startswith('runtime/') or tracked == 'prelink-config.json':
                body = (ROOT / contract.RECIPE / tracked).read_bytes()
            else:
                body = ('# synthetic inert helper ' + tracked + '\n').encode()
            source(tracked, body, item['role'])
            item['sha256'] = pin(body)
            self.files[name] = body
        for item in self.interfaces.values():
            self.assert_pin(item)
        while len(entries) < 197:
            source('fixture-data/' + str(len(entries)) + '.txt', b'synthetic metadata\n', 'config')
        source_map = {'schema_version': 1, 'kind': 'foundation-native-engine-actions-source-inputs',
            'inputs': entries}
        provenance = {'source_graph': {'source_files': 157, 'engine_files': 48, 'direct_translation_units': 32},
            'retained_input_mapping': self.mapping, 'interface_pins': self.interfaces}
        self.files['native-inputs/canonical-source-map.json'] = handoff.encoded(source_map)
        self.files['native-inputs/provenance.json'] = handoff.encoded(provenance)
        self.catalogue = {'source_map': {'path': contract.RECIPE + '/source-imports.json',
            'sha256': pin(self.files['native-inputs/canonical-source-map.json'])},
            'provenance': {'path': contract.RECIPE + '/provenance.json', 'sha256': pin(self.files['native-inputs/provenance.json'])},
            'graph': {'path': contract.RECIPE + '/cmake/native-provider.cmake', 'sha256': pin(self.graph)}}
        self.files['supplier-archives/wrapper.txt'] = b'synthetic retained source record\n'
        self.files['supplier-archives/engine.txt'] = b'synthetic retained engine record\n'
        self.files['licenses/NOTICE'] = b'synthetic fixture notice\n'
        roles = {name: entries[name]['role'] if name in entries else 'data' for name in self.files}
        roles.update({name: item['role'] for name, item in self.mapping.items()})
        roles.update({'supplier-archives/wrapper.txt': 'source', 'supplier-archives/engine.txt': 'source', 'licenses/NOTICE': 'license'})
        self.recipe = {'schema_version': 1, 'producer_version': 1, 'kind': 'foundation-appended-engine-recipe',
            'target': contract.TARGET, 'toolchain': {'cxx_standard': 23, 'identity_sha256': pin(b'fixture-toolchain'),
                'runtime_policy': 'private-native', 'paired_sdk_sha256': None,
                'target_baseline': 'windows-10-1809-unqualified'},
            'options': {'script_enabled': True, 'rendering': 'cpu', 'thread_model': 'native'},
            'provider': {'format': 'native-shared', 'binding': 'c-abi', 'abi_major': 1, 'abi_minor': 1,
                'header': 'include/foundation/appended/engine_provider.h', 'header_sha256': actions.BASE_HEADER_SHA256},
            'suppliers': {name: {'repository': 'https://example.invalid/' + name, 'commit': '1' * 40,
                'archive': 'supplier-archives/' + name + '.txt'} for name in ('wrapper', 'engine')},
            'inputs': {name: {'sha256': pin(body), 'mode': 0o644, 'role': roles[name]}
                for name, body in self.files.items()}, 'patches': [], 'licenses': ['licenses/NOTICE']}
        self.files['recipe.json'] = handoff.encoded(self.recipe)
        recipe_pin = pin(self.files['recipe.json'])
        self.sources = {**inventory(self.files), 'schema_version': 1, 'producer_version': 1,
            'kind': 'foundation-appended-engine-sources', 'recipe_id': recipe_pin}
        self.files['sources.json'] = handoff.encoded(self.sources)
        for name, raw in self.files.items():
            self.write(self.retained / name, raw)
        assembled_files = {name: self.files[name] for name, item in entries.items()
                           if name.startswith('source/') and item['role'] == 'source'}
        assembled_files['source/engine/CMakeLists.txt'] = b'# synthetic complete supplier graph\n'
        for name, raw in assembled_files.items():
            self.write(self.assembled / name, raw)
        self.build = handoff._expected_build(self.recipe, recipe_pin)
        build_raw = handoff.encoded(self.build)
        # Independent rendering follows the retained source generator algorithm.
        generator_template = self.files[handoff.TEMPLATE].decode('ascii')
        literal = lambda value: ','.join('0x' + value[n:n + 2] for n in range(0, 64, 2))
        operation = lambda item: '{' + ','.join((str(item['operation']), str(item['maximum_input_bytes']),
            str(item['required_reply_capacity']), 'UINT64_C(' + item['capability'] + ')',
            '{' + literal(item['schema_sha256']) + '}')) + '}'
        values = {'TARGET_SYSTEM': '2', 'TARGET_PROCESSOR': '1',
            'SOURCE_RECIPE_SHA256_BYTES': literal(recipe_pin), 'BUILD_IDENTITY_SHA256_BYTES': literal(pin(build_raw)),
            'SOURCE_INPUTS_SHA256_BYTES': literal(self.build['source_inputs_sha256']),
            'TOOLCHAIN_IDENTITY_SHA256_BYTES': literal(self.recipe['toolchain']['identity_sha256']),
            'QUERIES': ',\n    '.join(operation(item) for item in self.build['provider_contract']['queries']),
            'COMMANDS': ',\n    '.join(operation(item) for item in self.build['provider_contract']['commands'])}
        values.update({name.upper() + '_SHA256_BYTES': literal(item['sha256']) for name, item in self.interfaces.items()})
        for key, value in values.items():
            generator_template = generator_template.replace('@' + key + '@', value)
        header_raw = generator_template.encode('ascii')
        header = root / 'original-metadata' / handoff.HEADER
        receipt = {'scope': 'native-document-actions-provider-metadata-source-integrity-only',
            'production_eligible': False, 'engine_execution': False, 'recipe_sha256': recipe_pin,
            'source_manifest_sha256': pin(self.files['sources.json']), 'provider_build_sha256': pin(build_raw),
            'source_inputs_sha256': self.build['source_inputs_sha256'], 'target': contract.TARGET,
            'engine_profile': actions.expected_engine_profile(kernel_target=contract.TARGET,
                actions_profile=actions.SELECTOR, build_sha256=pin(build_raw), source_recipe_sha256=recipe_pin),
            'header': str(header), 'header_sha256': pin(header_raw)}
        selected_raw = {'recipe': self.files['recipe.json'], 'sources': self.files['sources.json'],
            'provider_build': build_raw, 'metadata_header': header_raw,
            'metadata_receipt': handoff.encoded(receipt), 'assembled_inventory': handoff.encoded(inventory(assembled_files)),
            'native_inputs': handoff.encoded(native_inputs())}
        self.selection = {'schema_version': 1, 'kind': handoff.SELECTION_KIND, 'target': contract.TARGET,
            'source_catalogue': copy.deepcopy(self.catalogue), 'retained_root': str(self.retained), 'assembled_root': str(self.assembled)}
        for role, raw in selected_raw.items():
            path = self.retained / (role + '.json') if role in ('recipe', 'sources') else (
                header if role == 'metadata_header' else root / 'original-metadata' / (role + '.json'))
            self.write(path, raw)
            self.selection[role] = {'path': str(path), 'sha256': pin(raw)}
        self.selection_path = root / 'selection.json'
        self.save_selection()

    def assert_pin(self, item):
        assert pin(self.files[item['retained_logical_path']]) == item['sha256']

    def write(self, path, raw):
        path.parent.mkdir(parents=True, exist_ok=True)
        for directory in (path.parent, *path.parent.parents):
            if directory == self.root:
                break
            directory.chmod(0o755)
        path.write_bytes(raw)
        path.chmod(0o644)

    def save_selection(self):
        self.write(self.selection_path, handoff.encoded(self.selection))
        self.selection_pin = pin(self.selection_path.read_bytes())


class HandoffTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='windows-handoff-fixture-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.fixture = Fixture(self.root)
        self.catalogue = mock.patch.object(contract, 'CATALOGUE', self.fixture.catalogue)
        self.catalogue.start()
        self.addCleanup(self.catalogue.stop)
        self.output = self.root / 'capsule'

    def prepare(self):
        return handoff.create_handoff(self.fixture.selection_path, self.fixture.selection_pin, self.output)

    def test_complete_capsule_and_consumer_api(self):
        result = self.prepare()
        self.assertEqual(result['native_inputs'], native_inputs())
        self.assertEqual(result['target'], contract.TARGET)
        self.assertEqual(result['paths'], handoff.PATHS)
        self.assertEqual(result['protected_paths'], [str(self.output)])
        self.assertEqual(stat.S_IMODE(self.output.stat().st_mode), 0o700)
        for name in handoff.FALSE_FACTS:
            self.assertIs(result[name], False)
        self.assertIn('not-supplier-replay-proof', result['assembly_provenance'])
        self.assertEqual(handoff.verify_handoff(self.output, result['handoff_sha256']), result)

    def test_independent_selection_and_capsule_pins(self):
        with self.assertRaisesRegex(ValueError, 'selection pin'):
            handoff.create_handoff(self.fixture.selection_path, '1' * 64, self.output)
        result = self.prepare()
        with self.assertRaisesRegex(ValueError, 'manifest pin'):
            handoff.verify_handoff(self.output, '1' * 64)

    def test_missing_prepared_inputs_are_structured_no_source_producer(self):
        Path(self.fixture.selection['provider_build']['path']).unlink()
        with self.assertRaises(handoff.MissingInputs) as context:
            self.prepare()
        self.assertEqual(context.exception.missing[0]['role'], 'provider_build')
        self.assertFalse(self.output.exists())
        with redirect_stdout(io.StringIO()) as output:
            self.assertEqual(handoff.cli(['prepare', '--selection', str(self.fixture.selection_path),
                '--selection-sha256', self.fixture.selection_pin, '--output', str(self.output)]), 2)
        self.assertEqual(json.loads(output.getvalue())['missing'][0]['role'], 'provider_build')

    def test_payload_tampering_missing_extra_and_mode(self):
        result = self.prepare()
        original = self.output / 'assembled/source/engine/unit0.cpp'
        body = original.read_bytes()
        for change in ('tamper', 'extra', 'mode', 'missing'):
            with self.subTest(change=change):
                if change == 'tamper': original.write_bytes(body + b'changed')
                elif change == 'extra': (self.output / 'extra').write_bytes(b'extra')
                elif change == 'mode': original.chmod(0o755)
                else: original.unlink()
                with self.assertRaises((ValueError, OSError)):
                    handoff.verify_handoff(self.output, result['handoff_sha256'])
                if change == 'extra': (self.output / 'extra').unlink()
                else: self.fixture.write(original, body)

    def test_bad_header_or_receipt_provenance_fails_despite_new_selection_pin(self):
        for role in ('metadata_header', 'metadata_receipt', 'provider_build'):
            path = Path(self.fixture.selection[role]['path'])
            original = path.read_bytes()
            if role == 'metadata_header':
                body = original.replace(b'targetSystem = 2', b'targetSystem = 1')
            elif role == 'metadata_receipt':
                value = json.loads(original); value['scope'] = 'fabricated'; body = handoff.encoded(value)
            else:
                body = original + b'\n'
            path.write_bytes(body)
            self.fixture.selection[role]['sha256'] = pin(body)
            self.fixture.save_selection()
            with self.subTest(role=role), self.assertRaises(ValueError):
                self.prepare()
            path.write_bytes(original)
            self.fixture.selection[role]['sha256'] = pin(original)
            self.fixture.save_selection()

    def test_preparation_rejects_same_byte_header_at_a_different_original_path(self):
        original_header = Path(self.fixture.selection['metadata_header']['path'])
        other_header = self.root / 'other-original' / handoff.HEADER
        self.fixture.write(other_header, original_header.read_bytes())
        self.fixture.selection['metadata_header']['path'] = str(other_header)
        self.fixture.save_selection()
        with self.assertRaisesRegex(ValueError, 'receipt header path differs'):
            self.prepare()
        self.assertFalse(self.output.exists())

    def test_preparation_rejects_receipt_naming_a_nonexistent_original_header(self):
        receipt_path = Path(self.fixture.selection['metadata_receipt']['path'])
        receipt = json.loads(receipt_path.read_bytes())
        receipt['header'] = str(self.root / 'never-created' / handoff.HEADER)
        self.assertFalse(Path(receipt['header']).exists())
        receipt_raw = handoff.encoded(receipt)
        receipt_path.write_bytes(receipt_raw)
        self.fixture.selection['metadata_receipt']['sha256'] = pin(receipt_raw)
        self.fixture.save_selection()
        with self.assertRaisesRegex(ValueError, 'receipt header path differs'):
            self.prepare()
        self.assertFalse(self.output.exists())

    def test_manifest_in_place_change_during_payload_scan_is_rejected(self):
        result = self.prepare()
        path = self.output / 'handoff.json'
        original = path.read_bytes()
        physical = path.stat().st_ino
        scan = handoff._scan
        def mutate_manifest(root, expected, **options):
            checked = scan(root, expected, **options)
            if Path(root) == self.output:
                path.write_bytes(original + b'\n')
                self.assertEqual(path.stat().st_ino, physical)
            return checked
        with mock.patch.object(handoff, '_scan', side_effect=mutate_manifest):
            with self.assertRaisesRegex(ValueError, 'root manifest changed'):
                handoff.verify_handoff(self.output, result['handoff_sha256'])

    def test_same_byte_manifest_inode_replacement_during_payload_scan_is_rejected(self):
        result = self.prepare()
        path = self.output / 'handoff.json'
        original = path.read_bytes()
        physical = path.stat().st_ino
        scan = handoff._scan
        def replace_manifest(root, expected, **options):
            checked = scan(root, expected, **options)
            if Path(root) == self.output:
                replacement = self.output / 'replacement-manifest.json'
                self.fixture.write(replacement, original)
                self.assertNotEqual(replacement.stat().st_ino, physical)
                os.replace(replacement, path)
                self.assertEqual(pin(path.read_bytes()), result['handoff_sha256'])
            return checked
        with mock.patch.object(handoff, '_scan', side_effect=replace_manifest):
            with self.assertRaisesRegex(ValueError, 'root manifest changed'):
                handoff.verify_handoff(self.output, result['handoff_sha256'])

    def test_source_roots_alias_or_output_overlap_fails(self):
        self.fixture.selection['assembled_root'] = str(self.fixture.retained)
        self.fixture.save_selection()
        with self.assertRaisesRegex(ValueError, 'disjoint'):
            self.prepare()
        self.fixture.selection['assembled_root'] = str(self.fixture.assembled)
        self.fixture.save_selection()
        with self.assertRaisesRegex(ValueError, 'overlaps'):
            handoff.create_handoff(self.fixture.selection_path, self.fixture.selection_pin,
                self.fixture.assembled / 'new-output')

    def test_links_and_hardlinks_are_rejected(self):
        source = self.fixture.assembled / 'source/engine/unit0.cpp'
        raw = source.read_bytes()
        source.unlink()
        source.symlink_to(self.fixture.retained / 'source/engine/unit0.cpp')
        with self.assertRaises((ValueError, OSError)):
            self.prepare()
        source.unlink()
        os.link(self.fixture.retained / 'source/engine/unit0.cpp', source)
        with self.assertRaisesRegex(ValueError, 'singly linked'):
            self.prepare()
        source.unlink()
        self.fixture.write(source, raw)

    def test_existing_output_and_racing_publication_preserve_destination(self):
        self.output.mkdir()
        (self.output / 'sentinel').write_bytes(b'preserve')
        with self.assertRaises(FileExistsError):
            self.prepare()
        self.assertEqual((self.output / 'sentinel').read_bytes(), b'preserve')
        (self.output / 'sentinel').unlink()
        self.output.rmdir()
        original_publish = handoff._publish
        def race(parent, staged, output):
            self.output.mkdir()
            return original_publish(parent, staged, output)
        with mock.patch.object(handoff, '_publish', side_effect=race):
            with self.assertRaises(FileExistsError): self.prepare()
        self.assertEqual(list(self.output.iterdir()), [])

    def test_unavailable_publication_and_nonposix_fail_closed(self):
        with mock.patch.object(handoff.ctypes, 'CDLL', return_value=object()):
            with self.assertRaisesRegex(ValueError, 'unavailable'):
                self.prepare()
        self.assertFalse(self.output.exists())
        with mock.patch.object(handoff.os, 'name', 'nt'):
            with self.assertRaisesRegex(ValueError, 'POSIX'):
                self.prepare()

    def test_portable_paths_aliases_and_bounded_inventory(self):
        for name in ('NUL.txt', 'case/file', 'a:stream', 'x/../file'):
            value = inventory({'Case/file': b'a', name: b'b'})
            with self.subTest(name=name), self.assertRaises(ValueError):
                handoff._inventory_contract(value)
        with mock.patch.object(handoff, 'MAX_ENTRIES', 1):
            with self.assertRaisesRegex(ValueError, 'bound'):
                self.prepare()

    def test_cli_check_is_passive_json(self):
        result = self.prepare()
        with redirect_stdout(io.StringIO()) as output, redirect_stderr(io.StringIO()):
            self.assertEqual(handoff.cli(['check', '--root', str(self.output), '--sha256', result['handoff_sha256']]), 0)
        self.assertEqual(json.loads(output.getvalue())['provider_build_sha256'], result['provider_build_sha256'])

    def test_repinning_extra_empty_directories_or_metadata_mode_cannot_expand_layout(self):
        result = self.prepare()
        manifest_path = self.output / 'handoff.json'
        original = json.loads(manifest_path.read_bytes())
        for change in ('directory', 'mode'):
            changed = copy.deepcopy(original)
            if change == 'directory':
                (self.output / 'metadata/extra').mkdir(mode=0o755)
                changed['directories'].append('metadata/extra')
                changed['directories'].sort()
                changed['modes']['metadata/extra'] = 0o755
            else:
                (self.output / handoff.PATHS['provider_build']).chmod(0o755)
                changed['modes'][handoff.PATHS['provider_build']] = 0o755
            manifest_path.write_bytes(handoff.encoded(changed))
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, 'unknown payload'):
                handoff.verify_handoff(self.output, pin(manifest_path.read_bytes()))
            if change == 'directory':
                (self.output / 'metadata/extra').rmdir()
            else:
                (self.output / handoff.PATHS['provider_build']).chmod(0o644)
        manifest_path.write_bytes(handoff.encoded(original))
        self.assertEqual(handoff.verify_handoff(self.output, result['handoff_sha256'])['target'], contract.TARGET)

    def test_windows_walker_fixture_uses_logical_modes_and_omits_root_manifest(self):
        # POSIX simulation exercises the Windows walk algorithm only; it cannot
        # qualify actual Windows reparse attributes, ACLs or file visibility.
        root = self.root / 'windows-walk-fixture'
        self.fixture.write(root / 'plain.exe', b'not an executable')
        self.fixture.write(root / 'script.txt', b'logical executable source')
        self.fixture.write(root / 'handoff.json', b'fixed root manifest')
        value = inventory({'plain.exe': b'not an executable', 'script.txt': b'logical executable source'})
        value['modes']['script.txt'] = 0o755
        self.assertEqual(handoff._scan_windows(root, value, ('handoff.json',)), value)
        (root / 'unknown').write_bytes(b'unknown')
        with self.assertRaisesRegex(ValueError, 'Unknown'):
            handoff._scan_windows(root, value, ('handoff.json',))
        (root / 'unknown').unlink()
        with mock.patch.object(handoff, 'MAX_FILE', 2):
            with self.assertRaisesRegex(ValueError, 'byte bound'):
                handoff._scan_windows(root, value, ('handoff.json',))

    def test_renamed_anchor_and_changed_enumeration_identity_fail_closed(self):
        root = self.root / 'anchor-fixture'
        root.mkdir()
        anchor = handoff._Anchor(root)
        try:
            root.rename(self.root / 'anchor-moved')
            root.mkdir()
            with self.assertRaisesRegex(ValueError, 'identity changed'):
                anchor.check()
        finally:
            anchor.close()
        source = self.fixture.assembled / 'source/engine/unit0.cpp'
        before = source.stat()
        source.write_bytes(b'changed size before capture')
        directory = handoff._Anchor(source.parent)
        try:
            with self.assertRaisesRegex(ValueError, 'identity/mode changed'):
                handoff._read_fd(directory.fd, source.name, expected=before)
        finally:
            directory.close()

    def test_duplicate_deep_json_and_stale_catalogue_fail(self):
        with self.assertRaises(ValueError):
            handoff._document(b'{"duplicate":1,"duplicate":2}')
        with self.assertRaises(ValueError):
            handoff._document(b'[' * 2000 + b']' * 2000)
        self.fixture.selection['source_catalogue']['graph']['sha256'] = '1' * 64
        self.fixture.save_selection()
        with self.assertRaisesRegex(ValueError, 'catalogue'):
            self.prepare()

    def test_missing_assembled_tree_and_oversized_source_are_explicit_failures(self):
        self.fixture.assembled.rename(self.root / 'assembled-moved')
        with self.assertRaises(handoff.MissingInputs) as context:
            self.prepare()
        self.assertEqual(context.exception.missing[0]['role'], 'prepared-native-source-tree')
        (self.root / 'assembled-moved').rename(self.fixture.assembled)
        with mock.patch.object(handoff, 'MAX_FILE', 16):
            with self.assertRaisesRegex(ValueError, 'byte bound'):
                self.prepare()


if __name__ == '__main__':
    unittest.main()
