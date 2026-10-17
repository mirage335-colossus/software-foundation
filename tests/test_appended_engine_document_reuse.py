#!/usr/bin/env python3
"""Tiny inert metadata fixtures; no retained SDK, compiler or engine execution."""
import ast
import copy
import importlib.util
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / 'recipes/webkitwasm-document-v2/prepare_reuse.py'
SPEC = importlib.util.spec_from_file_location('_test_document_reuse_metadata', PATH)
reuse = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = reuse
SPEC.loader.exec_module(reuse)


class Fixture:
    def __init__(self, driver):
        self.driver = driver
        self.original_root = '/historical/wrapper'
        self.sdk_hash = 'd' * 64
        self.bindings = {'reuse': self.original_root, 'sdk': '/historical/sdk',
                         'sources': '/historical/sources'}
        self.commands = {}
        self.owner = self.command('Source/UnifiedSource-owner.cpp', 'build/UnifiedSource-owner.cpp.o')
        # The opaque body and donor body are deliberately absent from receipt.
        self.opaque = self.command('not-retained/Opaque.cpp', 'build/Opaque.cpp.o')
        self.donor = self.command('not-retained/main.cpp', 'build/main.cpp.o')
        self.files = {'Source/UnifiedSource-owner.cpp': self.file(1, '1'),
            'Source/Body.cpp': self.file(2, '4'), 'build/cmakeconfig.h': self.file(3, '5'),
            'build/UnifiedSource-owner.cpp.o': self.file(4, 'a'),
            'build/Opaque.cpp.o': self.file(5, 'b'), 'build/libWebCore.a': self.file(6, 'c')}
        self.receipt = {'schema_version': 1, 'kind': 'closed-unpublished-baseline-copy-v1',
            'status': 'closed-exact-readback-passed-unpublished', 'files': self.files}
        self.inventory = {'files': {name: value['sha256'] for name, value in self.files.items()},
            'directories': ['Source', 'build'],
            'modes': {**{name: 0o644 for name in self.files}, 'Source': 0o755, 'build': 0o755}}
        self.config = {'document_profile': 'pixel', 'direct_objects': ['New.cpp'],
            'engine_objects': ['UnifiedSource-owner.cpp'], 'archive_members': {'WebCore': 2},
            'exceptions': ['New.cpp'], 'source_bindings': {
                'New.cpp': 'source/New.cpp', 'UnifiedSource-owner.cpp': 'source/UnifiedSource-owner.cpp'},
            'owner_postimages': {'UnifiedSource-owner.cpp': ['source/Body.cpp']},
            'derived_commands': {'New.cpp': {'donor_source': 'main.cpp', 'remove': [],
                                            'append': ['-DNEWDOC=1', '-fexceptions']}},
            'compile_literals': ['-DOLD=1', '-DNEWDOC=1', '-fno-exceptions', '-fexceptions'],
            'link_literals': ['-fno-exceptions', '-fexceptions', '--no-entry', '-lexports.js'],
            'link_settings': {'ENVIRONMENT': 'worker'}}
        self.source_files = {'source/New.cpp': '6' * 64,
            'source/UnifiedSource-owner.cpp': '2' * 64, 'source/Body.cpp': '3' * 64,
            'metadata.py': 'e' * 64}
        self.projection = {'files': {
            'source/New.cpp': {'preimage_sha256': None, 'sha256': '6' * 64},
            'source/UnifiedSource-owner.cpp': {'preimage_sha256': '8' * 64, 'sha256': '2' * 64},
            # Logical retained preimage intentionally differs from cold copy.
            'source/Body.cpp': {'preimage_sha256': '7' * 64, 'sha256': '3' * 64}},
            'physical_alias_groups': []}
        self.authority = {'original_root': self.original_root, 'original_bindings': self.bindings,
            'unified_sources': {'Source/UnifiedSource-owner.cpp': {
                'sha256': '1' * 64, 'literal_includes': ['Body.cpp'], 'members': ['Source/Body.cpp']}},
            'postimages': [{'original_path': 'Source/Body.cpp', 'source_path': 'source/Body.cpp'}],
            'configuration': {'root': 'reuse', 'path': 'build/cmakeconfig.h', 'sha256': '5' * 64},
            '_reuse_files': self.inventory['files'], '_sdk_sha256': self.sdk_hash}
        self.sdk_files = {'upstream/emscripten/em++': '9' * 64, 'include/stdint.h': 'f' * 64}
        self.copy_set = {'entries': [{'destination': name, 'expected_resolved_path': name,
                                     'sha256': value['sha256']} for name, value in self.files.items()]}
        self.old = {'target': {'system': 'Emscripten', 'processor': 'wasm32', 'pointer_bits': 32,
                               'triple': 'wasm32-emscripten'}, 'paired_sdk_sha256': self.sdk_hash,
            'inventory': self.inventory, 'baseline': {'original_receipt': {
                'root': 'reuse', 'path': 'original-build.json', 'sha256': 'e' * 64}},
            'archives': [{'name': 'WebCore', 'input': {'root': 'reuse', 'path': 'build/libWebCore.a',
                'sha256': 'c' * 64}, 'members': [self.member(0, 'UnifiedSource-owner.cpp', 'a', self.owner),
                                              self.member(1, 'Opaque.cpp', 'b', self.opaque)]}]}

    @staticmethod
    def file(ino, value):
        return {'sha256': value * 64, 'bytes': 1, 'mode': 0o644,
                'source_identity': [1, ino, 0o100644, 1, 1, 10, 10]}

    def command(self, name, output):
        record = {'argv': ['/historical/sdk/upstream/emscripten/em++', '-DOLD=1',
            '-I/historical/wrapper/Source', '-fno-exceptions', '-c', self.original_root + '/' + name,
            '-o', output], 'cwd': self.original_root}
        identity = reuse.digest(reuse.encoded(record))
        self.commands[identity] = record
        return identity

    @staticmethod
    def member(ordinal, name, value, command):
        return {'ordinal': ordinal, 'name': name + '.o', 'bytes': 1,
            'input': {'root': 'reuse', 'path': 'build/' + name + '.o', 'sha256': value * 64},
            'compile_command_sha256': command}

    def contexts(self):
        return reuse.make_contexts({self.owner: self.commands[self.owner]}, self.receipt,
            self.authority, self.sdk_files, self.sdk_hash, self.driver)

    def header(self):
        return reuse.make_header_identity(self.receipt, self.copy_set, self.authority,
            self.projection, 'f' * 64, self.source_files, self.inventory['files'], {})


class MetadataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.assembly, cls.driver, _ = reuse._helpers(ROOT)

    def setUp(self):
        self.fixture = Fixture(self.driver)

    def test_selected_link_preserves_raw_exports_exactly_once(self):
        config = self.fixture.config
        arguments = config['link_literals'] + ['-s' + key + '=' + value
            for key, value in config['link_settings'].items()]
        self.assertIsNone(reuse.validate_arguments(arguments, config, self.driver, link=True))
        for changed in ([arg for arg in arguments if arg != '-lexports.js'],
                        arguments + ['-lexports.js']):
            with self.subTest(arguments=changed), \
                 self.assertRaisesRegex(ValueError, 'exactly one literal -lexports.js'):
                reuse.validate_arguments(changed, config, self.driver, link=True)

    def test_selected_export_library_is_link_only_even_if_compile_profile_lists_it(self):
        config = self.fixture.config
        config['compile_literals'].append('-lexports.js')
        with self.assertRaisesRegex(ValueError, 'link-only'):
            reuse.validate_arguments(['-lexports.js'], config, self.driver)

    def test_selected_export_library_aliases_are_not_admitted(self):
        config = self.fixture.config
        arguments = config['link_literals'] + ['-s' + key + '=' + value
            for key, value in config['link_settings'].items()]
        for alias in ('-l', 'exports.js', '-lexports.js=1', '-Wl,-lexports.js'):
            with self.subTest(alias=alias), self.assertRaisesRegex(ValueError, 'closed document grammar'):
                reuse.validate_arguments(arguments + [alias], config, self.driver, link=True)

    def test_selected_context_uses_exact_source_macro_and_ordered_unified_member(self):
        f = self.fixture
        value = f.contexts()
        self.assertEqual(set(value['contexts']), {f.owner})
        context = value['contexts'][f.owner]
        self.assertEqual(context['source']['input']['path'], 'Source/UnifiedSource-owner.cpp')
        self.assertEqual(context['unified_members'], [{'original_path': '/historical/wrapper/Source/Body.cpp',
            'input': {'root': 'reuse', 'path': 'Source/Body.cpp', 'sha256': '4' * 64}}])
        self.assertEqual(context['macros'], ['-DOLD=1'])
        self.assertEqual(context['headers'], [])
        self.assertEqual(context['closure_mode'], 'include-search-v1')
        closure = value['search_closures'][context['search_closure_sha256']]
        self.assertEqual(closure['directories'], ['{reuse}/Source'])
        self.assertEqual(reuse.digest(reuse.encoded(closure)), context['search_closure_sha256'])

    def test_changed_sdk_header_changes_shared_namespace_identity(self):
        f = self.fixture
        before = f.contexts()['search_closures']
        f.sdk_files['include/stdint.h'] = 'e' * 64
        after = f.contexts()['search_closures']
        self.assertNotEqual(set(before), set(after))

    def test_changed_macro_with_old_command_identity_fails(self):
        f = self.fixture
        f.commands[f.owner]['argv'][1] = '-DOLD=2'
        with self.assertRaisesRegex(ValueError, 'command hash'):
            f.contexts()

    def test_wrong_unified_primary_pin_fails(self):
        f = self.fixture
        f.authority['unified_sources']['Source/UnifiedSource-owner.cpp']['sha256'] = 'f' * 64
        with self.assertRaisesRegex(ValueError, 'copied original primary'):
            f.contexts()

    def test_unretained_unified_body_is_explicit_prerequisite(self):
        f = self.fixture
        f.authority['unified_sources']['Source/UnifiedSource-owner.cpp']['members'] = ['Source/Absent.cpp']
        with self.assertRaises(reuse.PrerequisiteError) as caught:
            f.contexts()
        self.assertEqual(caught.exception.report['missing_selected_unified_member']['retained_path'], 'Source/Absent.cpp')

    def test_unused_unified_observation_is_rejected(self):
        f = self.fixture
        f.authority['unified_sources']['Source/Unused.cpp'] = {}
        with self.assertRaisesRegex(ValueError, 'unused or unbound'):
            f.contexts()

    def test_unified_first_include_search_match_cannot_be_substituted(self):
        f = self.fixture
        f.files['Other/Body.cpp'] = Fixture.file(20, '4')
        f.authority['unified_sources']['Source/UnifiedSource-owner.cpp']['members'] = ['Other/Body.cpp']
        with self.assertRaisesRegex(ValueError, 'first include-search match'):
            f.contexts()

    def test_selected_donor_flags_need_no_historical_donor_body(self):
        f = self.fixture
        objects = reuse.make_objects(f.config, 'a' * 64, f.commands, f.contexts(), f.source_files,
            f.projection, f.header(), f.authority,
            {'generator': {'root': 'sources', 'path': 'metadata.py', 'sha256': 'e' * 64}}, self.driver)
        self.assertEqual([o['id'] for o in objects], ['New.cpp', 'UnifiedSource-owner.cpp'])
        self.assertEqual(objects[0]['provenance']['donor_command_sha256'], f.donor)
        self.assertTrue(objects[0]['exceptions'])
        self.assertFalse(objects[1]['exceptions'])
        self.assertEqual(objects[1]['unified_members'], [{'root': 'sources', 'path': 'source/Body.cpp',
                                                       'sha256': '3' * 64}])
        self.assertNotIn('not-retained/main.cpp', f.receipt['files'])

    def test_engine_owner_requires_exact_projected_body(self):
        f = self.fixture
        header = f.header(); header['postimages'] = []
        with self.assertRaisesRegex(ValueError, r'projected C\+\+ postimage'):
            reuse.make_objects(f.config, 'a' * 64, f.commands, f.contexts(), f.source_files,
                f.projection, header, f.authority, {}, self.driver)

    def test_physical_preimage_and_retained_logical_preimage_are_distinct(self):
        f = self.fixture
        header = f.header()
        self.assertEqual(header['postimages'][0]['input']['sha256'], '4' * 64)
        self.assertEqual(f.projection['files']['source/Body.cpp']['preimage_sha256'], '7' * 64)
        reuse.validate_header_mappings(header, f.projection, f.config, self.driver.document_contract)

    def test_physical_postimage_cannot_change_unselected_header(self):
        f = self.fixture
        header = f.header()
        f.config['owner_postimages']['UnifiedSource-owner.cpp'] = []
        with self.assertRaisesRegex(ValueError, 'explicitly selected engine'):
            reuse.validate_header_mappings(header, f.projection, f.config, self.driver.document_contract)

    def test_original_physical_alias_class_requires_all_postimages(self):
        f = self.fixture
        f.files['Source/Alias.cpp'] = copy.deepcopy(f.files['Source/Body.cpp'])
        f.inventory['files']['Source/Alias.cpp'] = '4' * 64
        f.copy_set['entries'].append({'destination': 'Source/Alias.cpp',
            'expected_resolved_path': 'Source/Body.cpp', 'sha256': '4' * 64})
        header = f.header()
        self.assertEqual(len(header['classes']), 1)
        with self.assertRaisesRegex(ValueError, 'every canonical and alias'):
            reuse.validate_header_mappings(header, f.projection, f.config, self.driver.document_contract)

    def test_opaque_member_retains_object_identity_without_body_claim(self):
        f = self.fixture
        opaque, replacements = reuse.opaque_baseline(f.old, f.commands, f.config, f.original_root,
            reuse.TRUSTED_OPAQUE_PROOF_SHA256, self.driver)
        self.assertEqual(opaque['members'], [{'archive': 'WebCore', **f.old['archives'][0]['members'][1]}])
        self.assertEqual(replacements, [{'archive': 'WebCore', 'ordinal': 0,
            'object_id': 'UnifiedSource-owner.cpp', 'old_sha256': 'a' * 64}])
        self.assertEqual(opaque['predecessor_proof']['path'], reuse.PREDECESSOR)
        self.assertNotIn('not-retained/Opaque.cpp', f.files)

    def test_opaque_mode_rejects_an_unadmitted_predecessor_pin(self):
        f = self.fixture
        with self.assertRaisesRegex(ValueError, 'explicitly admitted'):
            reuse.opaque_baseline(f.old, f.commands, f.config, f.original_root, 'f' * 64, self.driver)

    def test_opaque_member_hash_cannot_be_replaced(self):
        f = self.fixture
        f.old['archives'][0]['members'][1]['input']['sha256'] = 'f' * 64
        with self.assertRaisesRegex(ValueError, 'tuple/order/identity'):
            reuse.opaque_baseline(f.old, f.commands, f.config, f.original_root,
                                 reuse.TRUSTED_OPAQUE_PROOF_SHA256, self.driver)

    def test_opaque_member_order_cannot_be_replaced(self):
        f = self.fixture
        f.old['archives'][0]['members'].reverse()
        with self.assertRaisesRegex(ValueError, 'tuple/order/identity'):
            reuse.opaque_baseline(f.old, f.commands, f.config, f.original_root,
                                 reuse.TRUSTED_OPAQUE_PROOF_SHA256, self.driver)

    def test_original_object_output_must_identify_actual_member(self):
        f = self.fixture
        record = f.commands.pop(f.opaque)
        record['argv'][record['argv'].index('-o') + 1] = 'build/Wrong.cpp.o'
        new_pin = reuse.digest(reuse.encoded(record)); f.commands[new_pin] = record
        f.old['archives'][0]['members'][1]['compile_command_sha256'] = new_pin
        with self.assertRaisesRegex(ValueError, 'exact archive member reference'):
            reuse.opaque_baseline(f.old, f.commands, f.config, f.original_root,
                                 reuse.TRUSTED_OPAQUE_PROOF_SHA256, self.driver)

    def test_grammar_rejects_response_files_and_host_include_paths(self):
        for tokens in (['@response'], ['-I/etc'], ['-isystem', '/etc'], ['--compiler=/bin/false']):
            with self.subTest(tokens=tokens), self.assertRaises(ValueError):
                reuse.validate_arguments(tokens, self.fixture.config, self.driver)

    def test_inventory_metadata_cannot_overwrite_original_path_or_mode(self):
        f = self.fixture
        with self.assertRaisesRegex(ValueError, 'collides'):
            reuse._inventory(f.inventory, {'Source/Body.cpp': b'changed'}, {}, self.driver.manifest)
        replacement = copy.deepcopy(f.files['Source/Body.cpp']); replacement['mode'] = 0o755
        with self.assertRaisesRegex(ValueError, 'changes original'):
            reuse._inventory(f.inventory, {}, {'Source/Body.cpp': replacement}, self.driver.manifest)

    def test_new_metadata_inventory_preserves_empty_directories(self):
        f = self.fixture
        f.inventory['directories'].append('empty-search'); f.inventory['directories'].sort()
        f.inventory['modes']['empty-search'] = 0o755
        value = reuse._inventory(f.inventory, {reuse.PREFIX + 'contexts.json': b'{}\n'}, {}, self.driver.manifest)
        self.assertIn('empty-search', value['directories'])
        self.assertEqual(value['modes']['empty-search'], 0o755)


class IOTests(unittest.TestCase):
    def test_strict_metadata_rejects_duplicate_nonfinite_and_invalid_unicode(self):
        for raw in (b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":1e999}', b'{"x":"\\ud800"}'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                reuse.document(raw)

    def test_named_metadata_budget_is_checked_before_content_open(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'large.json'; path.write_bytes(b'123456789')
            with mock.patch.object(reuse, 'MAX_DOCUMENT', 8), mock.patch.object(reuse.os, 'open') as opening:
                with self.assertRaisesRegex(ValueError, 'budget exceeded before reading'):
                    reuse.Reader().read(path, reuse.digest(b'123456789'))
                opening.assert_not_called()

    def test_named_input_is_counted_once_and_conflicting_pin_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'input.json'; path.write_bytes(b'{}\n')
            reader = reuse.Reader(); reader.read(path, reuse.digest(b'{}\n')); reader.read(path, reuse.digest(b'{}\n'))
            self.assertEqual(reader.total_bytes, 3)
            with self.assertRaisesRegex(ValueError, 'Conflicting independent pins'):
                reader.read(path, 'f' * 64)

    def test_changed_input_identity_stops_completion(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'input.json'; path.write_bytes(b'{}\n')
            reader = reuse.Reader(); reader.read(path, reuse.digest(b'{}\n')); path.write_bytes(b'{ }\n')
            with self.assertRaisesRegex(ValueError, 'changed before publication'):
                reader.recheck()

    def test_fragment_receipt_is_outside_metadata_inventory_and_last(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); protected = root / 'protected'; protected.mkdir()
            plan = {'protected_roots': (protected,), 'reader': reuse.Reader(),
                'assembly': SimpleNamespace(_recheck=lambda _plan: None), 'helper_snapshots': [],
                'outputs': {'reuse-proof.json': b'{}\n'},
                'summary': {'complete_reuse_root': False, 'production_eligible': False}}
            result = reuse.save(plan, root / 'fragment')
            self.assertFalse(result['complete_reuse_root'])
            self.assertTrue((root / 'fragment/ASSEMBLY.json').is_file())
            self.assertFalse((root / 'fragment/metadata-root/ASSEMBLY.json').exists())
            self.assertEqual(set(result['outputs']), {'reuse-proof.json'})

    def test_save_failure_leaves_no_complete_fragment_receipt(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); protected = root / 'protected'; protected.mkdir()
            plan = {'protected_roots': (protected,), 'reader': reuse.Reader(),
                'assembly': SimpleNamespace(_recheck=lambda _plan: None), 'helper_snapshots': [],
                'outputs': {'reuse-proof.json': b'{}\n'}, 'summary': {}}
            with mock.patch.object(reuse.os, 'fchmod', side_effect=OSError('inert save fixture')):
                with self.assertRaises(OSError):
                    reuse.save(plan, root / 'fragment')
            self.assertFalse((root / 'fragment/ASSEMBLY.json').exists())


class EditorReuseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.assembly, cls.driver, _ = reuse._helpers(ROOT)

    def test_editor_metadata_is_exact_owned_full_document_and_editor_set(self):
        driver = self.driver
        config = {'document_profile': 'editor',
            'metadata_generator': 'source/document-provider/runtime/generate_document_metadata.py'}
        names = [path for path, _ in driver.metadata_interface_paths('editor').values()] + [
            config['metadata_generator'], 'source/document-provider/runtime/engine-document-copied-metadata.h.in',
            'prelink-plan.json']
        source = {name: 'a' * 64 for name in names}
        value = reuse._metadata(config, source)
        self.assertEqual(len(value), 14)
        self.assertEqual(value['editor_schema']['path'], 'abi/appended/editor-v1/binary-schema.json')
        self.assertEqual(value['document_schema']['path'], 'abi/engine/document-v2/schema-definition.json')
        self.assertTrue(all(item['root'] == 'sources' and item['sha256'] == 'a' * 64 for item in value.values()))
        for key in ('editor_header', 'editor_contract', 'editor_catalog', 'editor_schema'):
            missing = dict(source); del missing[value[key]['path']]
            with self.subTest(key=key), self.assertRaises(ValueError):
                reuse._metadata(config, missing)

    def test_editor_cannot_add_an_unselected_core_header_postimage(self):
        f = Fixture(self.driver)
        f.config['document_profile'] = 'editor'
        f.authority['postimages'].append({'original_path': 'Source/Header.h', 'source_path': 'source/Header.h'})
        f.files['Source/Header.h'] = f.file(20, '5')
        f.inventory['files']['Source/Header.h'] = '5' * 64
        f.copy_set['entries'].append({'destination': 'Source/Header.h',
            'expected_resolved_path': 'Source/Header.h', 'sha256': '5' * 64})
        f.projection['files']['source/Header.h'] = {'preimage_sha256': '5' * 64, 'sha256': '6' * 64}
        f.source_files['source/Header.h'] = '6' * 64
        header = f.header()
        with self.assertRaises(ValueError):
            reuse.validate_header_mappings(header, f.projection, f.config, self.driver.document_contract)

    def test_editor_additional_owners_still_need_full_order_and_exact_original_output(self):
        f = Fixture(self.driver)
        f.config['document_profile'] = 'editor'
        context = f.contexts()
        self.assertEqual(len(context['contexts'][f.owner]['unified_members']), 1)
        f.authority['unified_sources']['Source/UnifiedSource-owner.cpp']['literal_includes'].append('Absent.cpp')
        with self.assertRaises(ValueError):
            f.contexts()


class PosthocMetadataTests(unittest.TestCase):
    @staticmethod
    def observations():
        # These are the three concrete separately pinned metadata shapes used
        # by the editor authority, reduced to tiny inert fixture documents.
        return [
            {'schema_version': 1, 'kind': 'foundation-document-v2-posthoc-source-observation-v1',
             'status': 'copied-readback-passed-posthoc-only'},
            {'schema_version': 1, 'kind': 'editor-cpp-exact-original-owner-proof-v1',
             'state': 'derived-named-original-metadata-and-closed-copy-unified-body-evidence-only'},
            {'schema_version': 1, 'kind': 'editor-unchanged-original-header-identity-join-v1',
             'state': 'original-metadata-identity-proof-only-no-header-body-read'}]

    @staticmethod
    def references(root, documents):
        refs, raws = [], []
        for ordinal, value in enumerate(documents):
            raw = reuse.encoded(value)
            path = root / ('observation-' + str(ordinal) + '.json')
            path.write_bytes(raw)
            refs.append({'path': str(path), 'sha256': reuse.digest(raw)})
            raws.append(raw)
        return refs, raws

    def test_all_three_editor_observation_kinds_keep_exact_pinned_bytes_and_order(self):
        with tempfile.TemporaryDirectory() as temporary:
            refs, raws = self.references(Path(temporary), self.observations())
            reader = reuse.Reader()
            outputs = reuse.posthoc_metadata(reader, refs, 'editor')
            self.assertEqual(list(outputs), [reuse.PREFIX + 'posthoc-observations-' + str(n) + '.json'
                                             for n in range(3)])
            self.assertEqual(list(outputs.values()), raws)
            self.assertEqual(reader.total_bytes, sum(map(len, raws)))
            with self.assertRaisesRegex(ValueError, 'exact identity/pin'):
                reuse.posthoc_metadata(reuse.Reader(), [dict(refs[1], sha256='a' * 64)], 'editor')

    def test_editor_observations_reject_wrong_kind_state_profile_or_schema(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for document in self.observations()[1:]:
                variants = [(dict(document, kind='unknown-editor-proof-v1'), 'editor'),
                    (dict(document, state='original-depfile-authority'), 'editor'),
                    (dict(document, schema_version=2), 'editor'),
                    (dict(document, schema_version=True), 'editor'),
                    (document, 'pixel'), (document, 'physical')]
                for value, profile in variants:
                    with self.subTest(kind=document['kind'], value=value, profile=profile):
                        refs, _ = self.references(root, [value])
                        with self.assertRaisesRegex(ValueError, 'masquerade'):
                            reuse.posthoc_metadata(reuse.Reader(), refs, profile)

    def test_generic_observation_keeps_existing_exact_kind_and_status_rule(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); generic = self.observations()[0]
            for profile in ('pixel', 'physical', 'editor'):
                refs, raws = self.references(root, [generic])
                self.assertEqual(list(reuse.posthoc_metadata(reuse.Reader(), refs, profile).values()), raws)
            refs, _ = self.references(root, [dict(generic, status='historical-original-authority')])
            with self.assertRaisesRegex(ValueError, 'masquerade'):
                reuse.posthoc_metadata(reuse.Reader(), refs, 'editor')

    def test_prepare_branch_executes_the_checked_loop_after_original_authority_checks(self):
        # Execute the actual prepare branch statement against tiny metadata.
        # This is deliberately not a claim that full real prepare() has run.
        tree = ast.parse(PATH.read_text())
        prepare = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'prepare')
        branch = next(n for n in prepare.body if isinstance(n, ast.Expr)
            and isinstance(n.value, ast.Call) and isinstance(n.value.func, ast.Attribute)
            and n.value.func.attr == 'update' and n.value.args
            and isinstance(n.value.args[0], ast.Call)
            and isinstance(n.value.args[0].func, ast.Name)
            and n.value.args[0].func.id == 'posthoc_metadata')
        for name in ('validate_authority', 'make_contexts'):
            calls = [n for n in ast.walk(prepare) if isinstance(n, ast.Call)
                     and isinstance(n.func, ast.Name) and n.func.id == name]
            self.assertTrue(calls and all(n.lineno < branch.lineno for n in calls))
        with tempfile.TemporaryDirectory() as temporary:
            refs, raws = self.references(Path(temporary), self.observations())
            scope = {'reader': reuse.Reader(), 'authority': {'posthoc_observations': refs},
                'selected': 'editor', 'outputs': {}, 'posthoc_metadata': reuse.posthoc_metadata}
            code = compile(ast.Module(body=[branch], type_ignores=[]), str(PATH), 'exec')
            exec(code, scope)
            self.assertEqual(list(scope['outputs'].values()), raws)
            changed = self.observations(); changed[1]['state'] = 'unqualified-original-build'
            refs, _ = self.references(Path(temporary), changed)
            scope.update(reader=reuse.Reader(), authority={'posthoc_observations': refs}, outputs={})
            with self.assertRaisesRegex(ValueError, 'masquerade'):
                exec(code, scope)
            self.assertEqual(scope['outputs'], {})


if __name__ == '__main__':
    unittest.main()
