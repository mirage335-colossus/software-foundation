"""Pure current-checkout preparation preserves independently pinned kernels.

Binary receipts below are synthetic schema fixtures, never compiler evidence.
All operation paths forbid process, network, compiler and SDK entry points.
"""
from contextlib import ExitStack, contextmanager
import copy
import io
import json
import os
from pathlib import Path
import shutil
import socket
import stat
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import Mock, patch
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(ROOT / 'tests'))
import appended
import appended_checkout as checkout
import appended_compile as compiler
import appended_container as container
import appended_policy as policy
import appended_project as project
import appended_release as release
import appended_wasm as wasm
import artifact
import build
import dependency_archive as archive
import source_identity
import test_appended_wasm as wasm_fixture


def document(path, value):
    path.write_bytes(container.canonical_json(value))


def pinned(path, base, **extra):
    return {'path': path.relative_to(base).as_posix(), 'sha256': archive.digest(path), **extra}


def tree_bytes(root):
    return {path.relative_to(root).as_posix(): (path.read_bytes(), stat.S_IMODE(path.stat().st_mode))
            for path in sorted(root.rglob('*')) if path.is_file() and not path.is_symlink()}


@contextmanager
def pure_operation():
    """Fail at the attempted effect rather than trusting a zero tool exit."""
    with ExitStack() as stack:
        for name in ('run', 'Popen', 'check_output', 'check_call', 'call'):
            stack.enter_context(patch.object(subprocess, name,
                side_effect=AssertionError('checkout invoked process: ' + name)))
        for module, name in ((os, 'system'), (os, 'popen'), (socket, 'socket'),
                             (socket, 'create_connection'), (urllib.request, 'urlopen'),
                             (urllib.request, 'urlretrieve'), (compiler, 'load_sdk'),
                             (compiler, 'compile_guest'), (compiler, '_run')):
            stack.enter_context(patch.object(module, name,
                side_effect=AssertionError('checkout entered forbidden effect: ' + name)))
        yield


class CheckoutTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='checkout fixture with spaces ')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.source = self.root / 'project'
        self.group = self.root / 'selected'
        self.group.mkdir()
        for name in ('src', 'src-web-appended', 'src-bin-appended', 'tools',
                     'include/foundation/appended'):
            (self.source / name).mkdir(parents=True, exist_ok=True)
        (self.source / 'src/kernel.cpp').write_text('unchanged retained kernel\n', encoding='utf-8')
        (self.source / 'src-web-appended/index.html').write_text('<p>original</p>', encoding='utf-8')
        (self.source / 'src-bin-appended/main.c').write_text('int application_source(void) { return 7; }\n', encoding='utf-8')
        (self.source / '.gitignore').write_text('src-web-appended/ignored-resource.txt\n', encoding='utf-8')
        for name in ('appended_compile.py', 'appended_wasm.py'):
            shutil.copy2(ROOT / 'tools' / name, self.source / 'tools' / name)
        shutil.copytree(ROOT / 'sdk/appended', self.source / 'sdk/appended')
        for name in ('abi.h', 'provider_abi.h'):
            shutil.copy2(ROOT / 'include/foundation/appended' / name,
                         self.source / 'include/foundation/appended' / name)
        self.application = {'id': 'checkout.example', 'name': 'Checkout fixture', 'version': '2.0.0'}
        self.configuration = project.default_document()
        self.configuration['application'] = dict(self.application)
        self.configure('web')
        self.original_source = self.group / 'original-source.tar.gz'
        self.original_manifest = source_identity.archive_source(self.source, self.original_source)
        self.prefix = b'<!doctype html><html><head></head><body><p>retained</p>' + container.HTML_MARKER
        self.descriptor = {'schema_version': 1, 'kind': 'foundation-kernel', 'carrier': 'html',
            'profile': 'both', 'append_format': 1, 'abi': {'major': 1, 'minor': 0},
            'capabilities': sorted([container.STARTUP_CAPABILITY, 'fixture.capability']), 'services': ['fixture.service'],
            'executable': {'length': len(self.prefix), 'sha256': container.digest(self.prefix)},
            'boundary_offset': None,
            'provenance': {'producer': 'original', 'qualification': 'unqualified-development'},
            'kernel_inputs': policy.kernel_source_tree(self.source)}
        self.descriptor_path = self.group / 'kernel.json'
        document(self.descriptor_path, self.descriptor)
        old_payload = container.build_package({'web/index.html': b'<p>original</p>'}, self.application,
            web_entry='web/index.html', identities={'source_tree': self.original_manifest['tree_sha256']})
        self.old_payload = self.group / 'original.sfapp'
        self.old_payload.write_bytes(container.encode_package(old_payload))
        self.base = self.group / 'kernel.tar.gz'
        self.members = {'bin/application.html': (self.prefix, 0o755),
            'lib/runtime.so': (b'retained runtime\0\xff', 0o640),
            'share/build-info.txt': (b'ORIGINAL PRODUCER AND SOURCE\n', 0o644)}
        self.directories = {'bin': 0o755, 'lib': 0o750, 'share': 0o755, 'empty': 0o700}
        release._write_archive(self.base, self.members, self.directories)
        self.inventory = self.group / 'kernel.inventory.json'
        inventory = artifact.describe(self.base)
        inventory['modes'] = release._mode_inventory(self.members)
        document(self.inventory, inventory)
        self.recovery = self.group / 'recovery-input.bin'
        self.recovery.write_bytes(b'independently retained reconstruction inputs')
        self.evidence = self.group / 'original-evidence.json'
        document(self.evidence, {'original': 'not current qualification'})
        (self.group / 'unselected.bin').write_bytes(b'preserve complete group, including this member')
        (self.group / 'README.md').write_bytes(b'Unselected documentation stays in the original group only.\n')
        entry = {'id': 'retained-html', 'archive': pinned(self.base, self.group),
            'inventory': pinned(self.inventory, self.group), 'descriptor': pinned(self.descriptor_path, self.group),
            'runtime_member': 'bin/application.html', 'output': 'checkout-html.tar.gz',
            'original_source': pinned(self.original_source, self.group,
                                      tree_sha256=self.original_manifest['tree_sha256']),
            'recovery': [pinned(self.recovery, self.group)], 'evidence': [pinned(self.evidence, self.group)]}
        self.selection = {'schema_version': 1, 'kind': 'foundation-appended-selection',
            'application': dict(self.application),
            'source': pinned(self.original_source, self.group, tree_sha256=self.original_manifest['tree_sha256']),
            'payload': pinned(self.old_payload, self.group), 'kernels': [entry]}
        self.selection_path = self.group / 'selection.json'
        document(self.selection_path, self.selection)
        self.request_path = self.root / 'checkout-request.json'
        self.request = {'schema_version': 1, 'kind': 'foundation-appended-checkout-request',
            'selection': pinned(self.selection_path, self.root), 'binary': None}
        self.save_request()
        self.output = self.root / 'checkout'

    def configure(self, mode, *, primary=None):
        web, binary = mode in ('web', 'both'), mode in ('binary', 'both')
        self.configuration['appended']['web'].update(enabled=web, entry='index.html')
        self.configuration['appended']['binary']['enabled'] = binary
        self.configuration['startup']['primary'] = primary or ('web' if web else 'binary' if binary else 'compiled')
        document(self.source / project.CONFIG_NAME, self.configuration)

    def save_request(self):
        document(self.request_path, self.request)

    def save_descriptor(self):
        document(self.descriptor_path, self.descriptor)
        self.selection['kernels'][0]['descriptor'] = pinned(self.descriptor_path, self.group)
        document(self.selection_path, self.selection)
        self.request['selection'] = pinned(self.selection_path, self.root)
        self.save_request()

    def retained_closure_bytes(self, group=None):
        group = group or self.group
        names = {self.selection_path.name, self.selection['source']['path']}
        if self.selection['payload'] is not None: names.add(self.selection['payload']['path'])
        for entry in self.selection['kernels']:
            names.update(entry[name]['path'] for name in ('archive', 'inventory', 'descriptor', 'original_source'))
            names.update(reference['path'] for name in ('recovery', 'evidence') for reference in entry[name])
        return {name: ((group / name).read_bytes(), stat.S_IMODE((group / name).stat().st_mode))
                for name in sorted(names)}

    def binary_inputs(self, *, language='c'):
        self.module = self.group / 'current.wasm'
        self.module.write_bytes(wasm_fixture.module())
        self.proof_path = self.group / 'compile-receipt.json'
        # Exact compile_guest schema; deliberately synthetic original provenance.
        self.proof = {'schema_version': 1, 'profile': compiler.PROFILE, 'language': language,
            'sources': compiler._tree(self.source / 'src-bin-appended', source=True),
            'bindings': {name: archive.digest(path) for name, path in sorted(
                compiler._binding_sources(self.source, language).items())},
            'sdk_descriptor_sha256': 'a' * 64, 'sdk_inventory_sha256': 'b' * 64,
            'compiler_helper_sha256': archive.digest(self.source / 'tools/appended_compile.py'),
            'validator_sha256': archive.digest(self.source / 'tools/appended_wasm.py'),
            'host': {'system': 'synthetic-fixture-host', 'machine': 'fixture-machine'},
            'commands': [['/not-executed/clang', '-c', '$WORK/source/main.c', '-o', '$WORK/main.o'],
                         ['/not-executed/wasm-ld', '$WORK/main.o', '-o', '$WORK/application.wasm']],
            'module': {'sha256': archive.digest(self.module), 'bytes': self.module.stat().st_size},
            'audit': wasm.validate_module(self.module.read_bytes())}
        self.save_proof()

    def save_proof(self):
        document(self.proof_path, self.proof)
        self.request['binary'] = {'module': pinned(self.module, self.root),
                                  'proof': pinned(self.proof_path, self.root)}
        self.save_request()

    def prepare(self, *, output=None, before_publish=None):
        with pure_operation():
            return checkout.prepare_checkout(self.source, self.request_path, output or self.output,
                                              before_publish=before_publish)

    def rejects(self, *, output=None, before_publish=None, absent=True):
        target = output or self.output
        with self.assertRaises((ValueError, OSError)):
            self.prepare(output=target, before_publish=before_publish)
        if absent:
            self.assertFalse(target.exists())
        elif target.exists():
            self.assertFalse((target / 'checkout.json').exists())

    def completed(self, result):
        self.assertEqual(result['candidate_directory'], 'candidate')
        self.assertEqual(result['qualification'], 'incomplete')
        self.assertIs(result['publication_eligible'], False)
        candidate = self.output / result['candidate_directory']
        self.assertEqual(result['candidate_sha256'], archive.digest(candidate / 'candidate.json'))
        self.assertEqual(result['composition_sha256'], archive.digest(candidate / 'composition.json'))
        self.assertEqual(result['selection_sha256'], archive.digest(self.output / 'selection.json'))
        source = source_identity.verify_source_archive(self.output / 'current-source.tar.gz')
        self.assertEqual(result['source_tree_sha256'], source['tree_sha256'])
        self.assertEqual(result['source_policy']['tree_sha256'], source['tree_sha256'])
        marker = json.loads((self.output / 'checkout.json').read_bytes())
        self.assertEqual(marker['candidate'], result)
        self.assertIs(marker['publication_eligible'], False)
        self.assertEqual(marker['qualification'], 'incomplete')
        with pure_operation():
            release.verify_candidate(candidate, result['candidate_sha256'])
        return candidate, source, marker

    def test_current_web_edit_preserves_pinned_closure_and_original_input_group(self):
        (self.source / 'src-web-appended/index.html').write_bytes(b'<h1>current checkout</h1>')
        before = tree_bytes(self.group)
        result = self.prepare()
        candidate, source, marker = self.completed(result)
        self.assertNotEqual(source['tree_sha256'], self.original_manifest['tree_sha256'])
        self.assertEqual(tree_bytes(self.group), before)
        self.assertEqual(tree_bytes(self.output / 'retained'), self.retained_closure_bytes())
        self.assertEqual(marker['retained_selection_sha256'], self.request['selection']['sha256'])
        self.assertTrue(all(row['current']['eligible'] for row in marker['kernel_eligibility']))
        package = container.parse_artifact((self.output / 'application.sfapp').read_bytes()).package
        self.assertEqual(package.file_bytes('web/index.html'), b'<h1>current checkout</h1>')
        self.assertEqual(package.index['identities']['source_tree'], source['tree_sha256'])
        self.assertEqual(container.validate_rich_startup(package)['primary'], 'web')
        _, observed, directories = release._members(candidate / 'artifacts/checkout-html.tar.gz')
        self.assertEqual(directories, self.directories)
        for name, original in self.members.items():
            if name != 'bin/application.html':
                self.assertEqual(observed[name], original)
        runtime, mode = observed['bin/application.html']
        self.assertEqual(mode, 0o755)
        self.assertEqual(container.parse_artifact(runtime, self.descriptor).prefix, self.prefix)
        self.assertEqual(container.parse_artifact(runtime, self.descriptor).package.data, package.data)

    def test_current_product_identity_is_packed_without_relabelling_original_source(self):
        self.configuration['application'].update(name='Current product', version='3.0.0')
        self.configure('web')
        before = tree_bytes(self.group)
        self.completed(self.prepare())
        selection = json.loads((self.output / 'selection.json').read_bytes())
        self.assertEqual(selection['application'], self.configuration['application'])
        self.assertEqual(tree_bytes(self.output / 'retained'), self.retained_closure_bytes())
        self.assertEqual(tree_bytes(self.group), before)
        self.assertEqual(selection['kernels'][0]['original_source']['sha256'], archive.digest(self.original_source))

    def test_neither_mode_creates_no_payload_and_retains_pristine_prefix(self):
        self.configure('neither')
        candidate, _, marker = self.completed(self.prepare())
        self.assertFalse((self.output / 'application.sfapp').exists())
        self.assertIsNone(json.loads((self.output / 'selection.json').read_bytes())['payload'])
        self.assertIsNone(marker['binary'])
        _, files, _ = release._members(candidate / 'artifacts/checkout-html.tar.gz')
        self.assertEqual(files['bin/application.html'], (self.prefix, 0o755))

    def test_binary_only_requires_current_proof_and_preserves_actual_module_bytes(self):
        self.configure('binary'); self.binary_inputs()
        before = self.module.read_bytes()
        _, source, marker = self.completed(self.prepare())
        package = container.parse_artifact((self.output / 'application.sfapp').read_bytes()).package
        self.assertEqual(package.mode, 'binary')
        self.assertEqual(package.file_bytes('binary/application.wasm'), before)
        self.assertEqual(marker['binary']['module_sha256'], container.digest(before))
        self.assertEqual(package.index['identities']['source_tree'], source['tree_sha256'])
        self.assertEqual((self.output / 'binary-proof/compile-receipt.json').read_bytes(), self.proof_path.read_bytes())

    def test_both_reuses_same_proved_module_after_current_web_edit(self):
        self.configure('both'); self.binary_inputs()
        before_module, before_proof = self.module.read_bytes(), self.proof_path.read_bytes()
        (self.source / 'src-web-appended/index.html').write_bytes(b'<p>web-only successor</p>')
        self.completed(self.prepare())
        package = container.parse_artifact((self.output / 'application.sfapp').read_bytes()).package
        self.assertEqual(package.mode, 'both')
        self.assertEqual(package.file_bytes('binary/application.wasm'), before_module)
        self.assertEqual(package.file_bytes('web/index.html'), b'<p>web-only successor</p>')
        self.assertEqual(self.proof_path.read_bytes(), before_proof)
        self.assertEqual(self.module.read_bytes(), before_module)

    def test_binary_requires_both_independently_pinned_module_and_actual_receipt(self):
        self.configure('binary')
        self.rejects()
        self.binary_inputs()
        original = copy.deepcopy(self.request['binary'])
        for bad in ({'module': original['module']}, {'proof': original['proof']},
                    {**original, 'guess': True}, {'module': original['module'], 'proof': None}):
            with self.subTest(binary=bad):
                self.request['binary'] = bad; self.save_request(); self.rejects()

    def test_disabled_binary_refuses_even_valid_module_receipt(self):
        self.binary_inputs()
        self.rejects()

    def test_binary_proof_schema_and_all_correlations_are_checked(self):
        self.configure('binary'); self.binary_inputs()
        original = copy.deepcopy(self.proof)
        mutations = {
            'unknown': lambda p: p.update(guess=True),
            'missing': lambda p: p.pop('sources'),
            'schema-bool': lambda p: p.update(schema_version=True),
            'profile': lambda p: p.update(profile='foreign-profile'),
            'language': lambda p: p.update(language='javascript'),
            'sources-hash': lambda p: p['sources']['main.c'].update(sha256='0' * 64),
            'sources-extra': lambda p: p['sources'].update(unlisted={'sha256': '0' * 64, 'executable': False}),
            'sources-mode': lambda p: p['sources']['main.c'].update(executable=True),
            'bindings': lambda p: p['bindings'].update({'guest.c': '0' * 64}),
            'wrong-language-bindings': lambda p: p.update(language='rust'),
            'helper': lambda p: p.update(compiler_helper_sha256='0' * 64),
            'validator': lambda p: p.update(validator_sha256='0' * 64),
            'module-hash': lambda p: p['module'].update(sha256='0' * 64),
            'module-length': lambda p: p['module'].update(bytes=p['module']['bytes'] + 1),
            'module-length-bool': lambda p: p['module'].update(bytes=True),
            'audit': lambda p: p['audit'].update(sha256='0' * 64),
            'commands': lambda p: p.update(commands=[]),
            'command-nul': lambda p: p.update(commands=[['bad\0argument']]),
            'host': lambda p: p['host'].update(system=''),
            'sdk-pin': lambda p: p.update(sdk_inventory_sha256='not-a-pin'),
        }
        for name, mutate in mutations.items():
            with self.subTest(correlation=name):
                self.proof = copy.deepcopy(original); mutate(self.proof); self.save_proof(); self.rejects()

    def test_stale_complete_binary_root_and_binding_changes_reject_without_build(self):
        self.configure('both'); self.binary_inputs()
        for name in ('src-bin-appended/main.c', 'src-bin-appended/extra.h', 'sdk/appended/guest.c',
                     'tools/appended_compile.py', 'tools/appended_wasm.py'):
            with self.subTest(input=name):
                path = self.source / name
                before = path.read_bytes() if path.exists() else None
                path.write_bytes((before or b'') + b'\nchanged input\n')
                self.rejects()
                if before is None: path.unlink()
                else: path.write_bytes(before)
        path = self.source / 'src-bin-appended/main.c'
        before, mode = path.read_bytes(), stat.S_IMODE(path.stat().st_mode)
        path.chmod(mode ^ 0o111)
        if bool(path.stat().st_mode & 0o111) != bool(mode & 0o111):
            self.rejects()
        path.chmod(mode)
        path.unlink()
        self.rejects(); path.write_bytes(before); path.chmod(mode)

    def test_actual_wasm_validation_cannot_be_replaced_by_forged_proof_audit(self):
        self.configure('binary'); self.binary_inputs()
        self.module.write_bytes(b'\0asm\1\0\0\0')
        self.proof['module'] = {'sha256': archive.digest(self.module), 'bytes': self.module.stat().st_size}
        self.save_proof(); self.rejects()

    def test_independent_selection_module_and_proof_pins_are_not_recomputed(self):
        self.configure('binary'); self.binary_inputs()
        for path in (self.selection_path, self.module, self.proof_path):
            with self.subTest(path=path.name):
                before = path.read_bytes(); path.write_bytes(before + b'\n')
                self.rejects(); path.write_bytes(before)

    def test_rich_checkout_preserves_configured_primary_with_compatible_retained_kernel(self):
        self.descriptor['capabilities'] = sorted(set(self.descriptor['capabilities']) | {
            container.GUI_COMPOSITION_CAPABILITY, 'foundation.view.v1'})
        self.descriptor['services'] = sorted(set(self.descriptor['services']) | {'foundation.view'})
        self.save_descriptor()
        for mode, primary in (('web', 'compiled'), ('both', 'web'),
                              ('both', 'compiled'), ('both', 'binary')):
            with self.subTest(mode=mode, primary=primary):
                self.configure(mode, primary=primary)
                if mode == 'both':
                    self.binary_inputs()
                self.output = self.root / (mode + '-' + primary)
                before = tree_bytes(self.group)
                candidate, _, marker = self.completed(self.prepare())
                self.assertEqual(tree_bytes(self.group), before)
                self.assertTrue(all(row['current']['eligible'] for row in marker['kernel_eligibility']))
                package = container.parse_artifact((self.output / 'application.sfapp').read_bytes()).package
                self.assertEqual(container.validate_rich_startup(package), {
                    'kind': 'foundation-appended-startup', 'primary': primary,
                    'schema_version': 1 if primary == 'web' else 2})
                required = package.index['requires']
                self.assertIn(container.STARTUP_CAPABILITY, required['capabilities'])
                if primary != 'web':
                    self.assertIn(container.GUI_COMPOSITION_CAPABILITY, required['capabilities'])
                    self.assertIn(container.COMPOSITION_STARTUP_PATH,
                                  [entry['path'] for entry in package.index['files']])
                    self.assertNotIn(container.STARTUP_PATH,
                                     [entry['path'] for entry in package.index['files']])
                if primary == 'binary':
                    self.assertEqual(package.file_bytes('binary/application.wasm'), self.module.read_bytes())
                    self.assertIn('foundation.view', required['services'])
                    self.assertIn('foundation.view.v1', required['capabilities'])
                _, files, _ = release._members(candidate / 'artifacts/checkout-html.tar.gz')
                artifact = container.parse_artifact(files['bin/application.html'][0], self.descriptor,
                                                    expected_mode=mode)
                self.assertEqual(artifact.prefix, self.prefix)
                self.assertEqual(artifact.package.data, package.data)

    def test_rich_composition_still_requires_actual_retained_kernel_capability(self):
        for primary in ('compiled', 'binary'):
            with self.subTest(primary=primary):
                self.configure('both', primary=primary); self.binary_inputs()
                self.descriptor['services'] = sorted(set(self.descriptor['services']) | {'foundation.view'})
                self.descriptor['capabilities'] = sorted(set(self.descriptor['capabilities']) | {'foundation.view.v1'})
                self.save_descriptor()
                with self.assertRaisesRegex(ValueError, 'foundation.gui-composition.v1'):
                    self.prepare()
                self.assertFalse(self.output.exists())

    def test_binary_primary_still_requires_actual_view_service_and_capability(self):
        self.configure('both', primary='binary'); self.binary_inputs()
        for missing in ('service', 'capability'):
            with self.subTest(missing=missing):
                self.descriptor['services'] = ['fixture.service'] + (
                    [] if missing == 'service' else ['foundation.view'])
                self.descriptor['capabilities'] = sorted({container.STARTUP_CAPABILITY,
                    container.GUI_COMPOSITION_CAPABILITY, 'fixture.capability'} | (
                        set() if missing == 'capability' else {'foundation.view.v1'}))
                self.save_descriptor()
                with self.assertRaisesRegex(ValueError, 'foundation.view'):
                    self.prepare()
                self.assertFalse(self.output.exists())

    def test_compiled_primary_cannot_satisfy_secondary_view_requirements(self):
        self.configure('both', primary='compiled'); self.binary_inputs()
        self.request['requires'] = {'abi': {'major': 1, 'minor': 0},
            'services': ['foundation.view'], 'capabilities': []}
        self.save_request()
        with self.assertRaisesRegex(ValueError, 'secondary views are unsupported'):
            self.prepare()
        self.assertFalse(self.output.exists())

    def test_requires_is_strict_and_cannot_claim_unavailable_service(self):
        for requires in ({'abi': {'major': True, 'minor': 0}, 'services': [], 'capabilities': []},
                         {'abi': {'major': 1, 'minor': 0}, 'services': [], 'capabilities': [], 'guess': True},
                         {'abi': {'major': 1, 'minor': 0}, 'services': ['missing.service'], 'capabilities': []},
                         {'abi': {'major': 1, 'minor': 0}, 'services': ['foundation.view'], 'capabilities': []}):
            with self.subTest(requires=requires):
                self.request['requires'] = requires; self.save_request(); self.rejects()

    def test_supported_explicit_requirements_reach_actual_package(self):
        requires = {'abi': {'major': 1, 'minor': 0}, 'services': ['fixture.service'],
                    'capabilities': ['fixture.capability']}
        self.request['requires'] = requires; self.save_request()
        self.completed(self.prepare())
        package = container.parse_artifact((self.output / 'application.sfapp').read_bytes()).package
        self.assertEqual(package.index['requires'], {**requires,
            'capabilities': sorted(['fixture.capability', container.STARTUP_CAPABILITY])})
        self.assertEqual(json.loads((self.output / 'request.json').read_bytes())['requires'], requires)

    def test_request_rejects_unknown_missing_duplicate_and_bool_schema(self):
        original = copy.deepcopy(self.request)
        for mutate in (lambda p: p.update(guess=True), lambda p: p.pop('binary'),
                       lambda p: p.update(schema_version=True), lambda p: p.update(kind='foreign')):
            self.request = copy.deepcopy(original); mutate(self.request); self.save_request(); self.rejects()
        text = container.canonical_json(original).decode()
        self.request_path.write_text(text.replace('"schema_version":1', '"schema_version":1,"schema_version":1'), encoding='utf-8')
        self.rejects()

    def test_request_paths_use_canonical_portable_spelling_relative_to_request(self):
        for name in ('../selected/selection.json', './selected/selection.json', 'selected//selection.json',
                     str(self.selection_path), 'C:/selection.json', 'selected\\selection.json',
                     'selected/CON', 'selected/missing.json'):
            with self.subTest(path=name):
                self.request['selection']['path'] = name; self.save_request(); self.rejects()

    def test_request_path_is_resolved_from_its_parent_not_process_cwd(self):
        original = Path.cwd()
        try:
            os.chdir(self.group)
            self.completed(self.prepare())
        finally:
            os.chdir(original)

    def test_no_clobber_preserves_existing_output_and_foreign_publication_race(self):
        self.output.mkdir(); sentinel = self.output / 'foreign'; sentinel.write_bytes(b'keep')
        before = tree_bytes(self.output)
        self.rejects(absent=False)
        self.assertEqual(tree_bytes(self.output), before)
        second = self.root / 'raced-output'
        def occupy():
            second.mkdir(); (second / 'foreign').write_bytes(b'new owner')
        self.rejects(output=second, before_publish=occupy, absent=False)
        self.assertEqual((second / 'foreign').read_bytes(), b'new owner')

    def test_outputs_cannot_enter_source_or_retained_inputs(self):
        for output in (self.source / 'ordinary-output', self.group / 'nested-output'):
            with self.subTest(output=output): self.rejects(output=output)

    def test_existing_ignored_build_output_is_allowed_without_self_capture(self):
        (self.source / 'build').mkdir()
        self.output = self.source / 'build/checkout'
        _, source, _ = self.completed(self.prepare())
        self.assertFalse(any(name == 'build' or name.startswith('build/') for name in source['files']))

    def test_acquired_group_inside_existing_ignored_build_is_deliberately_supported(self):
        retained = self.source / 'build/acquired'
        retained.parent.mkdir()
        shutil.copytree(self.group, retained)
        before = tree_bytes(retained)
        self.request['selection'] = pinned(retained / 'selection.json', self.root); self.save_request()
        _, source, _ = self.completed(self.prepare())
        self.assertEqual(tree_bytes(retained), before)
        self.assertEqual(tree_bytes(self.output / 'retained'), self.retained_closure_bytes(retained))
        self.assertFalse(any(name.startswith('build/') for name in source['files']))

    def test_unsafe_acquired_group_overlap_rejects_before_capture_or_private_copy(self):
        roots = (self.source, self.root, self.source / 'ordinary-retained', self.source / '.git/retained')
        for ordinal, group in enumerate(roots):
            with self.subTest(group=group):
                group.mkdir(parents=True, exist_ok=True)
                selection = group / 'relocated-selection.json'
                selection.write_bytes(self.selection_path.read_bytes())
                private = group / '.env.private'; private.write_bytes(b'never copied')
                git = group / '.git'; git.mkdir(exist_ok=True); (git / 'HEAD').write_bytes(b'private git state')
                self.request['selection'] = pinned(selection, self.root); self.save_request()
                with tempfile.TemporaryDirectory(prefix='checkout external output ') as external:
                    target = Path(external) / ('rejected-' + str(ordinal))
                    with patch.object(checkout, '_capture', side_effect=AssertionError('unsafe group entered capture')):
                        self.rejects(output=target)
                    self.assertEqual(list(Path(external).iterdir()), [])
                self.assertEqual(private.read_bytes(), b'never copied')
                self.assertEqual((git / 'HEAD').read_bytes(), b'private git state')

    def test_unreferenced_private_large_linked_and_special_siblings_are_never_enumerated_or_read(self):
        forbidden = []
        for name in ('.env', '.env.local', '.git/HEAD', '.GIT/config', 'nested/.env.local', 'nested/.git/HEAD'):
            path = self.group / name; path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'private retained sibling'); forbidden.append(path)
        large = self.group / 'unreferenced-large.bin'
        with large.open('wb') as stream: stream.truncate(release.MAX_INPUT + 1)
        forbidden.append(large)
        secret = self.root / 'unreferenced-foreign-secret'; secret.write_bytes(b'never read')
        link = self.group / 'unreferenced-link'; link.symlink_to(secret)
        forbidden.extend((secret, link))
        if hasattr(os, 'mkfifo'):
            fifo = self.group / 'unreferenced-fifo'; os.mkfifo(fifo); forbidden.append(fifo)
        forbidden.extend((self.group / 'README.md', self.group / 'unselected.bin'))
        exact = self.retained_closure_bytes()
        opened = Path.open
        scandir = os.scandir
        def guarded_open(path, *args, **kwargs):
            if Path(path).absolute() in forbidden:
                raise AssertionError('unreferenced retained sibling opened: ' + str(path))
            return opened(path, *args, **kwargs)
        def guarded_scandir(path):
            if isinstance(path, (str, bytes, os.PathLike)) and Path(os.fsdecode(path)).absolute() == self.group:
                raise AssertionError('unreferenced retained group enumerated')
            return scandir(path)
        with patch.object(Path, 'open', guarded_open), patch.object(os, 'scandir', side_effect=guarded_scandir):
            self.completed(self.prepare())
        self.assertEqual(tree_bytes(self.output / 'retained'), exact)
        self.assertEqual((self.group / '.env').read_bytes(), b'private retained sibling')
        self.assertEqual(secret.read_bytes(), b'never read')
        self.assertTrue(link.is_symlink())
        self.assertEqual(large.stat().st_size, release.MAX_INPUT + 1)
        self.assertFalse((self.output / 'retained/README.md').exists())

    def test_unreferenced_sibling_creation_does_not_invalidate_selected_closure(self):
        note = self.group / 'unrelated-writer-note.txt'
        exact = self.retained_closure_bytes()
        def unrelated_write():
            note.write_bytes(b'unrelated local work is outside the selected closure')
        self.completed(self.prepare(before_publish=unrelated_write))
        self.assertEqual(tree_bytes(self.output / 'retained'), exact)
        self.assertEqual(note.read_bytes(), b'unrelated local work is outside the selected closure')
        self.assertFalse((self.output / 'retained/unrelated-writer-note.txt').exists())

    def test_retained_reference_case_alias_cannot_enter_mirrored_closure(self):
        alias = self.group / 'KERNEL.JSON'; alias.write_bytes(self.descriptor_path.read_bytes())
        self.selection['kernels'][0]['recovery'].append(pinned(alias, self.group))
        document(self.selection_path, self.selection)
        self.request['selection'] = pinned(self.selection_path, self.root); self.save_request()
        self.rejects()

    def test_unique_retained_input_bytes_obey_aggregate_budget_before_release(self):
        source_bytes = sum((self.source / name).stat().st_size
                           for name in source_identity.source_files_without_git(self.source))
        with tarfile.open(self.original_source, 'r:*') as source:
            tar_bytes = sum(member.size for member in source)
        extra = self.group / 'additional-evidence.bin'
        extra.write_bytes(b'e' * (2 * max(source_bytes, tar_bytes) + 1024))
        self.selection['kernels'][0]['evidence'].append(pinned(extra, self.group))
        document(self.selection_path, self.selection)
        self.request['selection'] = pinned(self.selection_path, self.root); self.save_request()
        exact = self.retained_closure_bytes()
        cap = max(source_bytes, tar_bytes, max(len(data) for data, _ in exact.values())) + 1
        self.assertGreaterEqual(cap, tar_bytes)
        self.assertLess(cap, sum(len(data) for data, _ in exact.values()))
        original = release.Inputs.read
        reads = []
        def counted_read(inputs, item, **kwargs):
            if inputs.base == self.group: reads.append(item['path'])
            return original(inputs, item, **kwargs)
        with patch.object(checkout, 'MAX_BYTES', cap), \
                patch.object(release.Inputs, 'read', counted_read), \
                patch.object(release, 'prepare_release', side_effect=AssertionError('aggregate byte debt reached release')):
            self.rejects()
        self.assertIn(extra.name, reads)
        self.assertEqual(self.retained_closure_bytes(), exact)

    def test_unique_retained_input_count_obeys_budget_before_release(self):
        source_count = len(list(source_identity.source_files_without_git(self.source)))
        self.assertLess(source_count + 1, 128)
        for index in range(source_count + 1):
            extra = self.group / ('extra-evidence-' + str(index) + '.txt'); extra.write_bytes(b'bounded')
            self.selection['kernels'][0]['evidence'].append(pinned(extra, self.group))
        document(self.selection_path, self.selection)
        self.request['selection'] = pinned(self.selection_path, self.root); self.save_request()
        exact = self.retained_closure_bytes()
        self.assertGreater(len(exact), source_count)
        with patch.object(checkout, 'MAX_FILES', source_count), \
                patch.object(release, 'prepare_release', side_effect=AssertionError('unique file debt reached release')):
            self.rejects()
        self.assertEqual(self.retained_closure_bytes(), exact)

    def test_repeated_exact_references_reuse_one_original_snapshot(self):
        reference = pinned(self.original_source, self.group)
        self.selection['kernels'][0]['evidence'] = [dict(reference) for _ in range(128)]
        document(self.selection_path, self.selection)
        self.request['selection'] = pinned(self.selection_path, self.root); self.save_request()
        exact = self.retained_closure_bytes()
        original = release.Inputs.read
        reads = []
        def counted_read(inputs, item, **kwargs):
            if inputs.base == self.group: reads.append(item['path'])
            return original(inputs, item, **kwargs)
        with patch.object(release.Inputs, 'read', counted_read):
            self.completed(self.prepare())
        expected_paths = set(exact) - {self.selection_path.name}
        self.assertEqual(set(reads), expected_paths)
        self.assertEqual(len(reads), len(expected_paths))
        self.assertEqual(reads.count(reference['path']), 1)
        selected = json.loads((self.output / 'selection.json').read_bytes())
        self.assertEqual(selected['kernels'][0]['evidence'],
                         [{**reference, 'path': 'retained/' + reference['path']}] * 128)
        self.assertEqual(tree_bytes(self.output / 'retained'), exact)

    def test_repeated_reference_occurrences_obey_composition_consumption_budget(self):
        reference = pinned(self.original_source, self.group)
        self.selection['kernels'][0]['evidence'] = [dict(reference) for _ in range(128)]
        document(self.selection_path, self.selection)
        self.request['selection'] = pinned(self.selection_path, self.root); self.save_request()
        exact = self.retained_closure_bytes()
        unique_bytes = sum(len(data) for data, _ in exact.values())
        source_bytes = sum((self.source / name).stat().st_size
                           for name in source_identity.source_files_without_git(self.source))
        with tarfile.open(self.original_source, 'r:*') as source:
            tar_bytes = sum(member.size for member in source)
        cap = max(unique_bytes, source_bytes, tar_bytes) + 1
        self.assertGreaterEqual(cap, tar_bytes)
        self.assertLess(cap, unique_bytes + 127 * self.original_source.stat().st_size)
        with patch.object(checkout, 'MAX_BYTES', cap), \
                patch.object(release, 'prepare_release', side_effect=AssertionError('repeated consumption debt reached release')):
            with self.assertRaisesRegex(ValueError, 'composition consumption'):
                self.prepare()
        self.assertFalse(self.output.exists())
        self.assertEqual(self.retained_closure_bytes(), exact)

    def test_validly_hashed_retained_source_git_alias_rejects_before_release_restore(self):
        with tarfile.open(self.original_source, 'r:*') as source:
            members = {member.name: (source.extractfile(member).read(), member.mode)
                       for member in source if member.isfile()}
        original_members = dict(members)
        manifest = copy.deepcopy(self.original_manifest)
        alias = b'private case-insensitive Git metadata'
        manifest['files']['.GIT/HEAD'] = container.digest(alias)
        manifest['files'] = dict(sorted(manifest['files'].items()))
        manifest['tree_sha256'] = container.digest(archive.encoded(
            {'files': manifest['files'], 'executables': manifest['executables']}))
        members['.GIT/HEAD'] = (alias, 0o644)
        members['source.json'] = (archive.encoded(manifest), 0o644)
        archive_path = self.group / 'aliased-source.tar.gz'
        release._write_archive(archive_path, members, {})
        original = copy.deepcopy(self.selection)
        for scope in ('source', 'original_source'):
            with self.subTest(scope=scope):
                self.selection = copy.deepcopy(original)
                reference = pinned(archive_path, self.group, tree_sha256=manifest['tree_sha256'])
                if scope == 'source': self.selection['source'] = reference
                else: self.selection['kernels'][0]['original_source'] = reference
                document(self.selection_path, self.selection)
                self.request['selection'] = pinned(self.selection_path, self.root); self.save_request()
                with patch.object(release, 'prepare_release', side_effect=AssertionError('Git alias reached source restore')):
                    with self.assertRaisesRegex(ValueError, '[Gg]it|metadata'):
                        self.prepare()
                self.assertFalse(self.output.exists())
        # Empty directory headers do not affect the file manifest/tree. They
        # must still be rejected before a restored tree could detect Git.
        empty_archive = self.group / 'empty-git-directory-source.tar.gz'
        release._write_archive(empty_archive, original_members, {'.GIT': 0o755})
        for scope in ('source', 'original_source'):
            with self.subTest(scope=scope, kind='empty-directory'):
                self.selection = copy.deepcopy(original)
                reference = pinned(empty_archive, self.group,
                                   tree_sha256=self.original_manifest['tree_sha256'])
                if scope == 'source': self.selection['source'] = reference
                else: self.selection['kernels'][0]['original_source'] = reference
                document(self.selection_path, self.selection)
                self.request['selection'] = pinned(self.selection_path, self.root); self.save_request()
                with patch.object(release, 'prepare_release', side_effect=AssertionError('Empty Git alias reached source restore')):
                    with self.assertRaisesRegex(ValueError, '[Gg]it|metadata'):
                        self.prepare()
                self.assertFalse(self.output.exists())

    def test_source_staging_parent_cannot_enter_unexcluded_project_namespace(self):
        # Even an excluded leaf cannot authorize a scratch staging directory
        # under an otherwise selected parent: that would capture the operation.
        self.rejects(output=self.source / '.agent-work')

    def test_selected_web_binary_and_sdk_insulation_fail_before_packing(self):
        cases = (('web', 'src-web-appended/index.html', b'<script>navigator.serial.requestPort()</script>'),
                 ('binary', 'src-bin-appended/main.c', b'EM_JS(void, foreign, (), {});'),
                 ('web', 'sdk/appended/guest.c', b'EM_ASM({ foreign(); });'))
        for mode, name, contents in cases:
            with self.subTest(scope=name):
                self.configure(mode)
                if mode == 'binary': self.binary_inputs()
                else: self.request['binary'] = None; self.save_request()
                path = self.source / name; before = path.read_bytes(); path.write_bytes(contents)
                if mode == 'binary':
                    self.proof['sources'] = compiler._tree(self.source / 'src-bin-appended', source=True)
                    self.save_proof()
                with patch.object(container, '_pack', side_effect=AssertionError('insulation failure reached pack')):
                    self.rejects()
                path.write_bytes(before)

    def test_disabled_payload_insulation_scope_is_not_interpreted(self):
        path = self.source / 'src-bin-appended/disabled.js'
        path.write_bytes(b'EM_JS(void, not_selected, (), {});')
        with patch.object(policy, 'binary_violations', wraps=policy.binary_violations) as checker:
            _, source, marker = self.completed(self.prepare())
        self.assertIn(path.relative_to(self.source).as_posix(), source['files'])
        self.assertIs(marker['insulation']['ok'], True)
        self.assertFalse(any(call.args[1].startswith('src-bin-appended/') for call in checker.call_args_list))

    def test_fixed_source_exclusions_ignore_git_rules_and_never_call_git(self):
        (self.source / '.git').mkdir()
        (self.source / '.git/HEAD').write_text('not a git repository', encoding='utf-8')
        (self.source / 'src-web-appended/ignored-resource.txt').write_bytes(b'include despite .gitignore')
        for name in ('build/ignored.bin', '.agent-work/private.bin', '.env', '.env.local',
                     'src/__pycache__/ignored.pyc', 'src/ignored.pyc'):
            path = self.source / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(b'excluded')
        # Windows may use a checked source.json only for executable-mode
        # authority; on every host its bytes remain outside source identity.
        paths = {name: self.source / name for name in source_identity.source_files_without_git(self.source)}
        document(self.source / 'source.json', source_identity.describe_paths(paths))
        _, source, _ = self.completed(self.prepare())
        self.assertIn('src-web-appended/ignored-resource.txt', source['files'])
        self.assertIn('.gitignore', source['files'])
        self.assertFalse(any(source_identity.ignored_source_path(name) for name in source['files']))
        package = container.parse_artifact((self.output / 'application.sfapp').read_bytes()).package
        self.assertEqual(package.file_bytes('web/ignored-resource.txt'), b'include despite .gitignore')

    def test_source_git_case_alias_fails_before_source_archive_or_git_detection(self):
        for name in ('.GIT', '.GiT'):
            with self.subTest(alias=name):
                alias = self.source / name; alias.mkdir(); (alias / 'HEAD').write_bytes(b'private alias')
                with patch.object(source_identity, 'archive_source', side_effect=AssertionError('Git alias reached archive')):
                    self.rejects()
                shutil.rmtree(alias)

    def test_unrelated_kernel_byte_change_requires_maintenance_and_no_candidate(self):
        (self.source / 'src/kernel.cpp').write_bytes(b'changed kernel implementation')
        self.rejects()

    def test_selected_source_symlinks_and_special_entries_are_rejected(self):
        for root in (self.source,):
            for kind in ('file-link', 'directory-link', 'fifo'):
                with self.subTest(root=root.name, kind=kind):
                    path = root / 'unsupported-entry'
                    if kind == 'file-link': path.symlink_to(self.evidence)
                    elif kind == 'directory-link': path.symlink_to(self.source / 'src', target_is_directory=True)
                    elif hasattr(os, 'mkfifo'): os.mkfifo(path)
                    else:
                        # A directory as a pinned file is also nonregular on
                        # hosts without FIFO creation. No FIFO pass is claimed.
                        path.mkdir()
                        self.request['selection']['path'] = path.relative_to(self.root).as_posix()
                        self.save_request()
                    try: self.rejects()
                    finally:
                        if path.is_dir() and not path.is_symlink(): path.rmdir()
                        else: path.unlink()
                        self.request['selection'] = pinned(self.selection_path, self.root); self.save_request()

    def test_first_publication_recheck_detects_bytes_inventory_modes_and_inode_replacement(self):
        cases = ('source-bytes', 'source-added', 'source-mode', 'source-inode', 'group-bytes', 'request')
        for ordinal, change in enumerate(cases):
            with self.subTest(change=change):
                target = self.source / 'src-web-appended/index.html'
                before, mode = target.read_bytes(), target.stat().st_mode
                evidence = self.evidence.read_bytes(); request = self.request_path.read_bytes()
                def mutate():
                    if change == 'source-bytes': target.write_bytes(before + b'changed')
                    elif change == 'source-added': (self.source / 'src-web-appended/late.txt').write_bytes(b'late')
                    elif change == 'source-mode': target.chmod(stat.S_IMODE(mode) ^ 0o111)
                    elif change == 'source-inode':
                        replacement = self.source / 'src-web-appended/replacement.tmp'
                        replacement.write_bytes(before); replacement.replace(target)
                    elif change == 'group-bytes': self.evidence.write_bytes(evidence + b'changed')
                    else: self.request_path.write_bytes(request + b'\n')
                self.rejects(output=self.root / ('mutation-' + str(ordinal)), before_publish=mutate)
                target.write_bytes(before); target.chmod(stat.S_IMODE(mode)); self.evidence.write_bytes(evidence)
                self.request_path.write_bytes(request)
                for path in (self.source / 'src-web-appended/late.txt', self.group / 'late.bin'):
                    if path.exists(): path.unlink()

    def test_marker_is_last_and_second_phase_change_preserves_unmarked_partial_output(self):
        calls = []
        def mutate_second():
            calls.append(self.output.exists())
            self.assertFalse((self.output / 'checkout.json').exists())
            if len(calls) == 2:
                self.assertTrue((self.output / 'candidate/candidate.json').is_file())
                (self.source / 'src-web-appended/late.txt').write_bytes(b'changed after output reservation')
                (self.output / 'foreign-note').write_bytes(b'preserve for inspection')
        self.rejects(before_publish=mutate_second, absent=False)
        self.assertEqual(calls, [False, True])
        self.assertTrue((self.output / 'candidate').is_dir())
        self.assertEqual((self.output / 'foreign-note').read_bytes(), b'preserve for inspection')
        self.assertFalse((self.output / 'checkout.json').exists())

    def test_directory_swap_cannot_chmod_foreign_target_or_publish_marker(self):
        foreign = self.root / 'foreign-directory'; foreign.mkdir(); foreign.chmod(0o700)
        sentinel = foreign / 'foreign-data'; sentinel.write_bytes(b'untouched')
        before_mode = stat.S_IMODE(foreign.stat().st_mode)
        original = checkout._directory_mode
        swapped = []
        def swap_before_mode(path, identity, mode):
            if path == self.output / 'retained' and not swapped:
                path.rename(self.output / 'saved-retained')
                path.symlink_to(foreign, target_is_directory=True)
                swapped.append(True)
            return original(path, identity, mode)
        with patch.object(checkout, '_directory_mode', side_effect=swap_before_mode):
            self.rejects(absent=False)
        self.assertEqual(swapped, [True])
        self.assertEqual(stat.S_IMODE(foreign.stat().st_mode), before_mode)
        self.assertEqual(sentinel.read_bytes(), b'untouched')
        self.assertFalse((self.output / 'checkout.json').exists())

    def test_valid_outer_publication_callback_occurs_twice_before_marker(self):
        phases = []
        def observe():
            phases.append(self.output.exists())
            self.assertFalse((self.output / 'checkout.json').exists())
        self.completed(self.prepare(before_publish=observe))
        self.assertEqual(phases, [False, True])

    def test_cli_requires_named_options_without_positional_action(self):
        captured = io.StringIO()
        with pure_operation(), patch.object(sys, 'stdout', captured):
            self.assertEqual(checkout.main(['--project-root', str(self.source), '--request', str(self.request_path),
                                            '--output', str(self.output)]), 0)
        self.completed(json.loads(captured.getvalue()))
        with patch.object(sys, 'stderr', io.StringIO()), self.assertRaises(SystemExit) as failure:
            checkout.main(['prepare-checkout', '--project-root', str(self.source), '--request', str(self.request_path),
                           '--output', str(self.root / 'wrong-cli')])
        self.assertEqual(failure.exception.code, 2)
        self.assertFalse((self.root / 'wrong-cli').exists())


class CheckoutRouteTests(unittest.TestCase):
    def test_dispatch_imports_only_checkout_and_preserves_exact_options_without_action(self):
        options = ['--project-root', '/inert/source with spaces', '--request', '/inert/request.json',
                   '--output', '/inert/output with spaces']
        helper = Mock(); helper.main.return_value = 23
        with pure_operation(), patch.object(appended.importlib, 'import_module', return_value=helper) as imported:
            self.assertEqual(appended.main(['prepare-checkout', *options]), 23)
        imported.assert_called_once_with('appended_checkout')
        helper.main.assert_called_once_with(options)

    def test_supported_build_dispatch_precedes_native_toolchain_selection(self):
        options = ['--project-root', '/inert/project', '--request', '/inert/request', '--output', '/inert/output']
        helper = Mock(); helper.main.return_value = 19
        with ExitStack() as stack:
            stack.enter_context(pure_operation())
            for name in ('execute', 'run', 'native_rust_identity', 'host_programs', 'sdk_identity'):
                stack.enter_context(patch.object(build, name, side_effect=AssertionError('native path: ' + name)))
            imported = stack.enter_context(patch.object(appended.importlib, 'import_module', return_value=helper))
            self.assertEqual(build.main(['appended', 'prepare-checkout', *options]), 19)
        imported.assert_called_once_with('appended_checkout')
        helper.main.assert_called_once_with(options)

    def test_actual_workflow_keeps_frozen_default_and_separate_pure_checkout_guard(self):
        text = (ROOT / '.github/workflows/appended-compose.yml').read_text(encoding='utf-8')
        frozen = text.split('- name: Compose frozen unqualified candidate without native tools', 1)[1].split('- name:', 1)[0]
        current = text.split('- name: Pack current checkout and compose against retained kernels without native tools', 1)[1].split('- name:', 1)[0]
        choice = text.split('payload_source:', 1)[1].split('source_repository:', 1)[0]
        self.assertIn('default: frozen-group', choice)
        self.assertIn("if: inputs.payload_source == 'frozen-group'", frozen)
        self.assertIn('./build.sh appended prepare-release', frozen)
        self.assertIn("if: inputs.payload_source == 'checkout'", current)
        self.assertIn('./build.sh appended prepare-checkout --project-root .', current)
        self.assertIn("set(binary) != {'module', 'proof'}", current)
        self.assertIn("set(reference) != {'path', 'sha256'}", current)
        self.assertIn("'retained/' + resource_path(reference['path'])", current)
        self.assertIn("'sha256': os.environ['SELECTION_SHA256']", current)
        self.assertIn('CHECKOUT_REQUIRES: ${{ inputs.checkout_requires }}', current)
        self.assertIn("json.loads(os.environ['CHECKOUT_BINARY'], object_pairs_hook=object_pairs)", current)
        self.assertIn("json.loads(os.environ['CHECKOUT_REQUIRES'], object_pairs_hook=object_pairs)", current)
        self.assertIn('if requires is not None:', current)
        self.assertIn("request['requires'] = requires", current)
        requires_input = text.split('checkout_requires:', 1)[1].split('permissions:', 1)[0]
        self.assertIn('required: false', requires_input)
        self.assertIn("default: 'null'", requires_input)
        self.assertNotIn('hashlib', current)
        self.assertIn('contents: read', text)
        self.assertNotIn('contents: write', text)
        for line in text.splitlines():
            command = line.strip()
            self.assertFalse(command.startswith(('cmake ', 'ninja ', 'make ', 'cargo ', 'rustc ', 'clang ',
                                                 './build.sh build ', './build.sh engine-maintenance ')), command)


if __name__ == '__main__':
    unittest.main()
