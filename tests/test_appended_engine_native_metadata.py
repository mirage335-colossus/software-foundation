"""Native metadata source-integrity fixtures; no compiler/SDK/engine executes.

The tiny source recipes below are synthetic unit inputs, not actual native
recipes, dependencies, provider binaries or runtime evidence. Generation always
reports production_eligible=False. Fixture is reusable by separately authorized
header syntax checks; this suite never launches such checks itself.
"""
import copy
from contextlib import contextmanager, redirect_stdout
import hashlib
import json
import io
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / 'recipes/webkitwasm-native-v1/runtime/generate_native_metadata.py'
TEMPLATE = GENERATOR.with_name('native-provider-metadata.h.in')
CONFIG = ROOT / 'recipes/webkitwasm-native-v1/prelink-config.json'


def load(path):
    module = types.ModuleType('_native_metadata_test_module')
    module.__file__ = str(path)
    exec(compile(path.read_bytes(), str(path), 'exec'), module.__dict__)
    return module


adapter = load(GENERATOR)
contract = load(ROOT / 'tools/appended_engine_document_contract.py')


class Fixture:
    """Small sealed synthetic source group, disjoint original B and output."""
    def __init__(self, base, processor='x86_64'):
        self.base = Path(base)
        self.root = self.base / 'sources'
        self.output = self.base / 'generated'
        self.build_file = self.base / 'original/provider-build.json'
        for path in (self.root, self.output, self.build_file.parent):
            path.mkdir(mode=0o700, parents=True)
            path.chmod(0o700)
        self.roles = {}
        for name in adapter.HELPERS:
            self.write(name, (ROOT / name).read_bytes(), 'helper')
        self.write(adapter.GENERATOR, GENERATOR.read_bytes(), 'helper')
        self.write(adapter.TEMPLATE, TEMPLATE.read_bytes(), 'config')
        self.write(adapter.CONFIG, CONFIG.read_bytes(), 'config')
        for name, _ in adapter.PINS.values():
            self.write(name, (ROOT / 'recipes/webkitwasm-native-v1/source/foundation' / name).read_bytes(), 'interface')
        self.write('supplier/wrapper.tar', b'synthetic inert wrapper source archive\n', 'source')
        self.write('supplier/engine.tar', b'synthetic inert engine source archive\n', 'source')
        self.write('licenses/NOTICE', b'Synthetic test fixture only, not a supplier license closure.\n', 'license')
        self.recipe = {'schema_version': 1, 'kind': 'foundation-appended-engine-recipe',
            'producer_version': 1, 'target': {'system': 'Linux', 'processor': processor,
                'triple': processor + '-linux-gnu', 'pointer_bits': 64},
            'toolchain': {'cxx_standard': 23, 'identity_sha256': adapter.digest(b'synthetic native toolchain'),
                'runtime_policy': 'private-native', 'paired_sdk_sha256': None, 'target_baseline': 'synthetic only'},
            'options': {'script_enabled': True, 'rendering': 'cpu', 'thread_model': 'native'},
            'provider': {'format': 'native-shared', 'binding': 'c-abi', 'abi_major': 1, 'abi_minor': 1,
                'header': adapter.PINS['base'][0], 'header_sha256': adapter.PINS['base'][1]},
            'suppliers': {label: {'repository': 'https://example.invalid/' + label,
                'commit': '1' * 40, 'archive': 'supplier/' + label + '.tar'} for label in ('wrapper', 'engine')},
            'inputs': {}, 'patches': [], 'licenses': ['licenses/NOTICE']}
        self.seal()

    def write(self, name, raw, role):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        for parent in path.parents:
            if parent == self.root:
                break
            parent.chmod(0o755)
        path.write_bytes(raw)
        path.chmod(0o644)
        self.roles[name] = role

    def seal(self):
        self.recipe['inputs'] = {name: {'sha256': adapter.digest((self.root / name).read_bytes()),
            'role': role, 'mode': 0o644} for name, role in self.roles.items()}
        raw_recipe = adapter.encoded(self.recipe)
        (self.root / 'recipe.json').write_bytes(raw_recipe)
        (self.root / 'recipe.json').chmod(0o644)
        directories = sorted(path.relative_to(self.root).as_posix() for path in self.root.rglob('*') if path.is_dir())
        files = {name: item['sha256'] for name, item in self.recipe['inputs'].items()}
        files['recipe.json'] = adapter.digest(raw_recipe)
        source = {'schema_version': 1, 'kind': 'foundation-appended-engine-sources', 'producer_version': 1,
            'recipe_id': adapter.digest(raw_recipe), 'files': files, 'directories': directories,
            'modes': {**{name: 0o644 for name in files}, **{name: 0o755 for name in directories}}}
        raw_sources = adapter.encoded(source)
        (self.root / 'sources.json').write_bytes(raw_sources)
        (self.root / 'sources.json').chmod(0o644)
        operations = contract.provider_contract(document_profile='pixel')
        operations['target'] = {'system': 1, 'processor': 1 if self.recipe['target']['processor'] == 'x86_64' else 2, 'pointer_bits': 64}
        self.build = {'schema_version': 1, 'kind': 'foundation-neutral-engine-provider-native-document-v2-build-v1',
            'target': copy.deepcopy(self.recipe['target']), 'toolchain': copy.deepcopy(self.recipe['toolchain']),
            'options': copy.deepcopy(self.recipe['options']), 'source_recipe_sha256': adapter.digest(raw_recipe),
            'source_inputs_sha256': adapter.digest(adapter.encoded(self.recipe['inputs'])),
            'contract_header_sha256': contract.CONTRACT_SHA256, 'binding': 'private-native',
            'configuration': {'kind': 'native-dso-private-runtime-v1', 'document_profile': contract.PROFILE_NAMES['pixel'],
                'getter': 'bib_engine_get_provider_v1', 'getter_maximum_minor': 1, 'inert_registration': True,
                'public_exports': ['bib_engine_get_provider_v1'], 'rendering': 'cpu', 'script_enabled': True, 'thread_model': 'native'},
            'capabilities': '1795', 'provider_contract': operations, 'provider_limits': {
                'size': 48, 'maximum_command_bytes': 65536, 'maximum_query_bytes': 65536,
                'maximum_reply_bytes': 1048576, 'maximum_service_message_bytes': 1048576,
                'maximum_retired_documents': 8, 'maximum_inflight_resources': 64, 'reserved': 0,
                'maximum_resource_response_bytes': 67108864, 'maximum_retained_resource_bytes': 134217728}}
        self.args = types.SimpleNamespace(source_root=self.root, output_root=self.output,
            recipe_sha256=adapter.digest(raw_recipe), source_manifest_sha256=adapter.digest(raw_sources),
            provider_build=self.build_file, provider_build_sha256='')
        self.save_build()
        self.module = load(self.root / adapter.GENERATOR)

    def save_build(self, raw=None):
        raw = adapter.encoded(self.build) if raw is None else raw
        self.build_file.write_bytes(raw)
        self.build_file.chmod(0o644)
        self.args.provider_build_sha256 = adapter.digest(raw)

    def generate(self):
        return self.module.generate(self.args)


class NativeMetadataTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='native-metadata-unit-')
        self.addCleanup(self.temporary.cleanup)
        self.f = Fixture(self.temporary.name)

    def rejected(self, fragment=None):
        with self.assertRaises((ValueError, OSError)) as caught:
            self.f.generate()
        if fragment:
            self.assertIn(fragment, str(caught.exception))
        self.assertEqual(list(self.f.output.iterdir()), [])

    @contextmanager
    def stale_retained_listing(self):
        original_open, original_listdir = os.open, os.listdir
        observed = {'retained': None, 'fresh_opens': 0, 'retained_lists': 0, 'fresh_lists': 0}
        def open_entry(path, *args, **kwargs):
            descriptor = original_open(path, *args, **kwargs)
            if path == self.f.output:
                observed['retained'] = descriptor
            elif path == '.' and kwargs.get('dir_fd') == observed['retained']:
                observed['fresh_opens'] += 1
            return descriptor
        def list_entries(path):
            if path == observed['retained']:
                observed['retained_lists'] += 1
                return []  # A reused open directory description keeps its initial snapshot.
            if isinstance(path, int) and observed['retained'] is not None:
                observed['fresh_lists'] += 1
            return original_listdir(path)
        with mock.patch.object(self.f.module.os, 'open', side_effect=open_entry):
            with mock.patch.object(self.f.module.os, 'listdir', side_effect=list_entries):
                # Capability checks must follow the patched function identities.
                with mock.patch.object(self.f.module.os, 'supports_dir_fd', {os.open, os.stat, os.link, os.unlink}):
                    with mock.patch.object(self.f.module.os, 'supports_fd', {os.listdir}):
                        yield observed

    def test_native64_header_only_and_digest_joins(self):
        result = self.f.generate()
        self.assertFalse(result['production_eligible'])
        self.assertFalse(result['engine_execution'])
        self.assertEqual(result['scope'], 'native-provider-metadata-source-integrity-only')
        self.assertEqual([path.name for path in self.f.output.iterdir()], [adapter.HEADER])
        header = (self.f.output / adapter.HEADER).read_text()
        self.assertNotIn('@', header)
        self.assertNotIn('DESIGN TEMPLATE', header)
        self.assertNotIn('std::string', header)
        self.assertNotIn('worker_epoch', header)
        self.assertIn('namespace foundation::appended::native_provider_metadata', header)
        self.assertIn('targetProcessor = 1;', header)
        self.assertIn('rawDigestMatches(build.contract_header_sha256, contractSha256)', header)
        self.assertIn('rawDigestMatches(build.build_identity_sha256, buildIdentitySha256)', header)
        self.assertIn('rawDigestMatches(build.source_recipe_sha256, sourceRecipeSha256)', header)
        self.assertIn('sizeof(BibEngineLimitsV1), 65536, 65536, 1048576', header)
        self.assertEqual(result['header_sha256'], adapter.digest(header.encode()))

    def test_aarch64_is_explicit(self):
        self.f.recipe['target'].update(processor='aarch64', triple='aarch64-linux-gnu')
        self.f.seal()
        self.f.generate()
        self.assertIn('targetProcessor = 2;', (self.f.output / adapter.HEADER).read_text())

    def test_recipe_pin(self):
        self.f.args.recipe_sha256 = '1' * 64
        self.rejected('pin differs')

    def test_source_manifest_pin(self):
        self.f.args.source_manifest_sha256 = '1' * 64
        self.rejected('pin differs')

    def test_provider_build_pin(self):
        self.f.args.provider_build_sha256 = '1' * 64
        self.rejected('provider-build pin differs')

    def test_zero_pin(self):
        self.f.args.recipe_sha256 = '0' * 64
        self.rejected('nonzero exact SHA256')

    def test_source_candidate_is_not_recipe(self):
        raw = adapter.encoded({'kind': 'foundation-native-source-inputs-v1', 'files': {}})
        (self.f.root / 'recipe.json').write_bytes(raw)
        self.f.args.recipe_sha256 = adapter.digest(raw)
        self.rejected('actual complete retained native recipe')

    def test_windows_not_admitted_by_initial_generator(self):
        self.f.recipe['target'].update(system='Windows', triple='x86_64-pc-windows-msvc')
        self.f.seal()
        self.rejected('Linux64')

    def test_wasm_target_rejects(self):
        self.f.recipe['target'].update(system='Emscripten', processor='wasm32', triple='wasm32-unknown-emscripten', pointer_bits=32)
        self.f.seal()
        self.rejected()

    def test_cxx23_native_toolchain_required(self):
        self.f.recipe['toolchain']['cxx_standard'] = 20
        self.f.seal()
        self.rejected('C++23')

    def test_paired_wasm_sdk_rejects(self):
        self.f.recipe['toolchain']['paired_sdk_sha256'] = '1' * 64
        self.f.seal()
        self.rejected('Emscripten pairing')

    def test_minor0_recipe_rejects(self):
        self.f.recipe['provider']['abi_minor'] = 0
        self.f.seal()
        self.rejected('ABI1.1')

    def test_missing_generator_role(self):
        self.f.roles[adapter.GENERATOR] = 'source'
        self.f.seal()
        self.rejected('input/role missing')

    def test_execute_exact_retained_generator(self):
        self.f.module.__file__ = str(GENERATOR)
        self.rejected('exact recipe-retained')

    def test_unpinned_source_mutation(self):
        (self.f.root / 'licenses/NOTICE').write_bytes(b'mutated')
        self.rejected('hash differs')

    def test_extra_source_entry(self):
        (self.f.root / 'extra').write_bytes(b'unlisted')
        self.rejected('Unlisted retained')

    def test_symlink_source_file(self):
        path = self.f.root / 'licenses/NOTICE'
        path.unlink()
        path.symlink_to(self.f.build_file)
        self.rejected('ordinary unlinked')

    def test_hardlinked_source_file(self):
        path = self.f.root / 'licenses/NOTICE'
        os.link(path, self.f.base / 'foreign-notice')
        self.rejected('ordinary unlinked')

    def test_interface_hash_not_just_recipe_hash(self):
        name = adapter.PINS['extension'][0]
        self.f.write(name, b'mutated interface\n', 'interface')
        self.f.seal()
        self.rejected('interface differs')

    def test_generated_header_cannot_enter_recipe(self):
        self.f.write('source/native/' + adapter.HEADER, b'circular generated output\n', 'config')
        self.f.seal()
        self.rejected('Generated/circular output')

    def test_prelink_config_extra_identity_rejects(self):
        value = json.loads(CONFIG.read_bytes())
        value['provider_build_sha256'] = '1' * 64
        self.f.write(adapter.CONFIG, adapter.encoded(value), 'config')
        self.f.seal()
        self.rejected('Prelink config differs')

    def test_prelink_retention_fixed(self):
        value = json.loads(CONFIG.read_bytes())
        value['service_retention']['max_retained_calls'] = 65
        self.f.write(adapter.CONFIG, adapter.encoded(value), 'config')
        self.f.seal()
        self.rejected('Prelink config differs')

    def test_prelink_bool_not_integer(self):
        value = json.loads(CONFIG.read_bytes())
        value['schema_version'] = True
        self.f.write(adapter.CONFIG, adapter.encoded(value), 'config')
        self.f.seal()
        self.rejected('Prelink config differs')

    def test_original_provider_build_must_be_canonical(self):
        self.f.save_build(json.dumps(self.f.build).encode())
        self.rejected('canonical provider-build')

    def test_provider_build_extra_field(self):
        self.f.build['bridge_abi'] = 65536
        self.f.save_build()
        self.rejected('closed native provider-build')

    def test_provider_build_source_input_join(self):
        self.f.build['source_inputs_sha256'] = '1' * 64
        self.f.save_build()
        self.rejected('source/target/native configuration')

    def test_provider_build_base_digest_is_not_document_contract(self):
        self.f.build['contract_header_sha256'] = contract.BASE_HEADER_SHA256
        self.f.save_build()
        self.rejected('source/target/native configuration')

    def test_provider_build_limits_and_exports_closed(self):
        self.f.build['configuration']['public_exports'].append('diagnostic')
        self.f.save_build()
        self.rejected('source/target/native configuration')

    def test_duplicate_provider_build_field(self):
        raw = adapter.encoded(self.f.build).replace(b'"schema_version": 1,', b'"schema_version": 1, "schema_version": 1,')
        self.f.save_build(raw)
        self.rejected('Duplicate JSON field')

    def test_invalid_unicode(self):
        self.f.build['target']['triple'] = '\ud800'
        self.f.save_build()
        self.rejected('Unicode')

    def test_unresolved_template(self):
        self.f.write(adapter.TEMPLATE, TEMPLATE.read_bytes() + b'@MISSING@\n', 'config')
        self.f.seal()
        self.rejected('Unresolved')

    def test_private_helpers_ignore_ambient_module(self):
        poison = types.ModuleType('dependency_archive')
        with mock.patch.dict(sys.modules, {'dependency_archive': poison}):
            self.assertFalse(self.f.generate()['production_eligible'])
            self.assertIs(sys.modules['dependency_archive'], poison)

    def test_new_helper_import_must_be_in_closed_import_set(self):
        name = 'tools/appended_engine_manifest.py'
        self.f.write(name, (ROOT / name).read_bytes() + b'\nimport subprocess\n', 'helper')
        self.f.seal()
        self.rejected('Unpinned retained helper import')

    def test_private_output_permissions(self):
        self.f.output.chmod(0o755)
        self.rejected('private mode0700')

    def test_existing_output_preserved(self):
        path = self.f.output / adapter.HEADER
        path.write_bytes(b'foreign existing header')
        with self.assertRaisesRegex(ValueError, 'fresh and empty'):
            self.f.generate()
        self.assertEqual(path.read_bytes(), b'foreign existing header')

    def test_publication_refreshes_stale_retained_directory_listing(self):
        with self.stale_retained_listing() as observed:
            result = self.f.generate()
        self.assertFalse(result['production_eligible'])
        self.assertEqual(observed['retained_lists'], 0)
        self.assertEqual(observed['fresh_opens'], 2)
        self.assertEqual(observed['fresh_lists'], 2)
        self.assertEqual([path.name for path in self.f.output.iterdir()], [adapter.HEADER])

    def test_refreshed_listing_rejects_and_preserves_foreign_file(self):
        original_fsync = os.fsync
        foreign = self.f.output / '.foreign'
        def introduce_foreign(descriptor):
            foreign.write_bytes(b'foreign file must survive publication rejection')
            return original_fsync(descriptor)
        with self.stale_retained_listing() as observed:
            with mock.patch.object(self.f.module.os, 'fsync', side_effect=introduce_foreign):
                with self.assertRaisesRegex(ValueError, 'Private output state changed'):
                    self.f.generate()
        self.assertEqual(observed['retained_lists'], 0)
        self.assertEqual(observed['fresh_opens'], 2)
        self.assertEqual(observed['fresh_lists'], 2)
        self.assertEqual([path.name for path in self.f.output.iterdir()], ['.foreign'])
        self.assertEqual(foreign.read_bytes(), b'foreign file must survive publication rejection')

    def test_refreshed_directory_identity_mismatch_rejects(self):
        descriptor = os.open(self.f.output, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            state = os.fstat(descriptor)
            with self.assertRaisesRegex(ValueError, 'descriptor identity changed'):
                self.f.module.directory_entries(descriptor, (state.st_dev, state.st_ino + 1))
        finally:
            os.close(descriptor)

    def test_output_inside_sources_rejects(self):
        self.f.args.output_root = self.f.root
        with self.assertRaisesRegex(ValueError, 'disjoint'):
            self.f.generate()

    def test_provider_build_inside_output_rejects(self):
        self.f.args.provider_build = self.f.output / 'provider-build.json'
        self.f.args.provider_build.write_bytes(adapter.encoded(self.f.build))
        with self.assertRaisesRegex(ValueError, 'disjoint'):
            self.f.generate()

    def test_unqualified_filesystem_fails_closed(self):
        with mock.patch.object(self.f.module.os, 'supports_dir_fd', set()):
            self.rejected('qualified POSIX')

    def test_postflight_detects_source_mutation(self):
        original = self.f.module.load_helpers
        def change(*args):
            result = original(*args)
            (self.f.root / 'licenses/NOTICE').write_bytes(b'changed after first source verification')
            return result
        with mock.patch.object(self.f.module, 'load_helpers', side_effect=change):
            self.rejected('hash differs')

    def test_atomic_link_failure_leaves_no_header_or_temp(self):
        with mock.patch.object(self.f.module.os, 'link', side_effect=OSError('injected publication failure')):
            # qualified_posix uses the same function object for capability checks.
            with mock.patch.object(self.f.module.os, 'supports_dir_fd', {os.open, os.stat, self.f.module.os.link, os.unlink}):
                self.rejected('injected publication failure')

    def test_atomic_race_preserves_foreign_header(self):
        original = os.link
        def race(*args, **kwargs):
            (self.f.output / adapter.HEADER).write_bytes(b'foreign publication won race')
            return original(*args, **kwargs)
        with mock.patch.object(self.f.module.os, 'link', side_effect=race):
            with mock.patch.object(self.f.module.os, 'supports_dir_fd', {os.open, os.stat, self.f.module.os.link, os.unlink}):
                with self.assertRaises(FileExistsError):
                    self.f.generate()
        self.assertEqual([path.name for path in self.f.output.iterdir()], [adapter.HEADER])
        self.assertEqual((self.f.output / adapter.HEADER).read_bytes(), b'foreign publication won race')

    def test_exact_cli_reports_only_source_integrity(self):
        args = self.f.args
        output = io.StringIO()
        with redirect_stdout(output):
            result = self.f.module.main(['--source-root', str(args.source_root),
                '--recipe-sha256', args.recipe_sha256, '--source-manifest-sha256', args.source_manifest_sha256,
                '--provider-build', str(args.provider_build), '--provider-build-sha256', args.provider_build_sha256,
                '--output-root', str(args.output_root)])
        self.assertEqual(result, 0)
        self.assertFalse(json.loads(output.getvalue())['production_eligible'])
        self.assertEqual(len(output.getvalue().splitlines()), 1)


if __name__ == '__main__':
    unittest.main()
