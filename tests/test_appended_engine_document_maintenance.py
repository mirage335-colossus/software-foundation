"""Tiny, offline document-maintenance fixtures; no SDK or build is consulted."""
import copy
import hashlib
import io
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import appended_engine_document_maintenance as maintenance
import appended_engine_document_contract as contract
from dependency_archive import encoded


PIN = '1' * 64
OTHER = '2' * 64


def reference(path, *, root='sources', pin=PIN):
    return {'root': root, 'path': path, 'sha256': pin}


def facts():
    signatures = {
        'bib_engine_get_provider_v1': (['i32'] * 4, ['i32']),
        'bib_engine_wasm_bridge_v1': ([], ['i32']),
        'bib_engine_wasm_dispatch_v1': (['i32'] * 5, ['i32']),
        'bib_engine_wasm_document_facts_v1': (['i32'] * 2, ['i32']),
        'bib_engine_wasm_document_configure_v1': (['i32'] * 2, ['i32']),
        'malloc': (['i32'], ['i32']), 'free': (['i32'], []),
    }
    return {'start': None, 'memories': [{'shared': False, 'memory64': False, 'maximum': 65536}],
        'imports': [], 'exports': [{'name': name, 'kind': 'function',
            'details': {'parameters': parameters, 'results': results}}
            for name, (parameters, results) in signatures.items()]}


def regular_archive(symbols, entries, width, *, wrong_offset=False):
    """Inert regular-archive bytes; no ar, compiler or object parser runs."""
    def member(name, content):
        header = (name.ljust(16) + '0'.ljust(12) + '0'.ljust(6) + '0'.ljust(6)
            + '644'.ljust(8) + str(len(content)).ljust(10) + '`\n').encode('ascii')
        return header + content + (b'\n' if len(content) & 1 else b'')
    index_size = width * (entries + 1) + len(symbols)
    offset = 8 + 60 + index_size + (index_size & 1) + int(wrong_offset)
    content = entries.to_bytes(width, 'big') + offset.to_bytes(width, 'big') * entries + symbols
    return b'!<arch>\n' + member('/SYM64/' if width == 8 else '/', content) + member('member.o/', b'inert bytes')


class DocumentMaintenanceTests(unittest.TestCase):
    def test_metadata_interfaces_require_exact_roles_and_hashes_for_each_profile(self):
        for selected in ('pixel', 'physical', 'editor'):
            recipe = {'inputs': {name: {'role': 'interface', 'sha256': pin}
                for name, pin in maintenance.metadata_interface_paths(selected).values()}}
            maintenance._validate_metadata_interfaces(recipe, selected)
            for name in recipe['inputs']:
                for mutation in ('role', 'hash', 'missing', 'malformed'):
                    changed = copy.deepcopy(recipe)
                    if mutation == 'role': changed['inputs'][name]['role'] = 'source'
                    elif mutation == 'hash': changed['inputs'][name]['sha256'] = PIN
                    elif mutation == 'missing': del changed['inputs'][name]
                    else: changed['inputs'][name] = None
                    with self.subTest(profile=selected, name=name, mutation=mutation), \
                         self.assertRaisesRegex(ValueError, 'exact interface role/hash'):
                        maintenance._validate_metadata_interfaces(changed, selected)

    def test_editor_wrong_role_rejects_before_source_sdk_or_reuse_walks(self):
        with tempfile.TemporaryDirectory(prefix='document-interface-admission-') as temporary:
            root = Path(temporary).resolve()
            for name in ('sources', 'sdk', 'reuse'):
                (root / name).mkdir()
            selection = {key: PIN for key in maintenance.SELECTION_FIELDS}
            selection.update(document_profile='editor', profile=maintenance.profile('editor')['name'],
                sources=str(root / 'sources'), sdk=str(root / 'sdk'), reuse_root=str(root / 'reuse'),
                projection=str(root / 'sources/provenance/source-projection.json'),
                reuse_proof=str(root / 'reuse/reuse-proof.json'))
            recipe = {'inputs': {name: {'role': 'interface', 'sha256': pin}
                for name, pin in maintenance.metadata_interface_paths('editor').values()}}
            editor_paths = [name for key, (name, _) in maintenance.metadata_interface_paths('editor').items()
                            if key.startswith('editor_')]
            for name in editor_paths:
                changed = copy.deepcopy(recipe)
                changed['inputs'][name]['role'] = 'source'
                raw = encoded(changed)
                (root / 'sources/recipe.json').write_bytes(raw)
                selection['recipe_sha256'] = hashlib.sha256(raw).hexdigest()
                with self.subTest(name=name), \
                     mock.patch.object(maintenance.manifest, 'verify_sources',
                        side_effect=AssertionError('Source walk reached')) as sources, \
                     mock.patch.object(maintenance, 'verify_sdk',
                        side_effect=AssertionError('SDK walk reached')) as sdk, \
                     mock.patch.object(maintenance, 'inventory',
                        side_effect=AssertionError('Reuse walk reached')) as reuse, \
                     self.assertRaisesRegex(ValueError, 'exact interface role/hash: ' + name):
                    maintenance.inspect_inputs(selection)
                sources.assert_not_called()
                sdk.assert_not_called()
                reuse.assert_not_called()

    def opaque_fixture(self):
        receipt = reference('provenance/original-engine-build.json', root='reuse')
        baseline = {'original_receipt': receipt, 'origin': 'Original limited fixture scope',
            'recorded_scopes': ['Opaque artifact fixture, no runtime eligibility']}
        members = [{'ordinal': i, 'name': name + '.o', 'input': reference(name + '.o', root='reuse',
            pin=PIN if i == 0 else OTHER), 'bytes': i + 1, 'compile_command_sha256': PIN if i == 0 else OTHER}
            for i, name in enumerate(('Owner', 'Opaque', 'Second'))]
        archives = [{'name': 'WebCore', 'input': reference('libWebCore.a', root='reuse'), 'members': members}]
        target = {'system': 'Emscripten', 'processor': 'wasm32', 'pointer_bits': 32, 'triple': 'wasm32-emscripten'}
        predecessor = {'schema_version': 1, 'kind': 'foundation-copied259-baseline-reuse-v1',
            'baseline': copy.deepcopy(baseline), 'archives': copy.deepcopy(archives),
            'inventory': {'files': {name: OTHER for name in maintenance.OPAQUE_BASELINE_METADATA_NAMES}},
            'target': target, 'paired_sdk_sha256': PIN}
        inspection = SimpleNamespace(recipe={'target': target}, selection={'sdk_manifest_sha256': PIN},
            proof={'baseline': dict(baseline, compile_contexts=reference('contexts.json', root='reuse')),
                'archives': archives, 'replacements': [{'archive': 'WebCore', 'ordinal': 0}]})
        value = {'kind': maintenance.OPAQUE_BASELINE_KIND,
            'predecessor_proof': reference('predecessor.json', root='reuse', pin=maintenance.OPAQUE_BASELINE_PROOF_SHA256),
            'original_receipt': receipt, 'target': target, 'paired_sdk_sha256': PIN,
            'members': [{'archive': 'WebCore', **member} for member in members[1:]]}
        return value, inspection, predecessor

    def test_opaque_authority_preserves_exact_artifact_tuples_and_original_limitations(self):
        value, inspection, predecessor = self.opaque_fixture()
        with mock.patch.object(maintenance, 'checked_document', return_value=predecessor):
            self.assertEqual(maintenance._opaque_baseline(value, inspection, lambda ref: Path('/fixture/input')),
                {name: OTHER for name in maintenance.OPAQUE_BASELINE_METADATA_NAMES})
        for mutation in ('order', 'member-hash', 'command', 'size', 'omit', 'receipt', 'SDK', 'target',
                         'predecessor', 'archive-layout', 'scope'):
            changed, current = copy.deepcopy(value), copy.deepcopy(inspection)
            if mutation == 'order': changed['members'].reverse()
            elif mutation == 'member-hash': changed['members'][0]['input']['sha256'] = PIN
            elif mutation == 'command': changed['members'][0]['compile_command_sha256'] = PIN
            elif mutation == 'size': changed['members'][0]['bytes'] += 1
            elif mutation == 'omit': changed['members'].pop()
            elif mutation == 'receipt': changed['original_receipt'] = reference('other.json')
            elif mutation == 'SDK': changed['paired_sdk_sha256'] = OTHER
            elif mutation == 'target': changed['target']['pointer_bits'] = 64
            elif mutation == 'predecessor': changed['predecessor_proof']['sha256'] = PIN
            elif mutation == 'archive-layout': current.proof['archives'][0]['members'].reverse()
            else: current.proof['baseline']['recorded_scopes'] = ['Invented runtime pass']
            with self.subTest(mutation=mutation), \
                 mock.patch.object(maintenance, 'checked_document', return_value=predecessor), \
                 self.assertRaises(ValueError):
                maintenance._opaque_baseline(changed, current, lambda ref: Path('/fixture/input'))

    def test_context_authority_modes_are_explicit_and_never_fallback(self):
        for invalid in (None, [], 'infer-the-mode'):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                maintenance._compile_contexts(invalid, {}, None, None, None)
        value = {'schema_version': 1, 'kind': maintenance.SELECTED_CONTEXT_KIND,
            'contexts': {PIN: {}}, 'search_closures': {}, 'opaque_baseline': {}}
        inspection = SimpleNamespace(profile={'engine_objects': ['Owner.cpp']},
            proof={'objects': [{'id': 'New.cpp'}, {'id': 'Owner.cpp'}]})
        commands = {PIN: {}, OTHER: {}}
        with mock.patch.object(maintenance, '_object_provenance', return_value=PIN), \
             mock.patch.object(maintenance, '_opaque_baseline') as opaque, \
             mock.patch.object(maintenance, '_context_record') as record:
            self.assertTrue(maintenance._compile_contexts(value, commands, inspection, None, None))
            self.assertEqual(record.call_count, 1)
            opaque.assert_called_once()
            for mutation in ('missing', 'extra', 'unknown', 'missing-opaque'):
                changed = copy.deepcopy(value)
                if mutation == 'missing': changed['contexts'] = {}
                elif mutation == 'extra': changed['contexts'][OTHER] = {}
                elif mutation == 'unknown': changed['kind'] = 'infer-from-absent-contexts'
                else: changed.pop('opaque_baseline')
                with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                    maintenance._compile_contexts(changed, commands, inspection, None, None)
            full = {'schema_version': 1, 'kind': 'foundation-engine-original-compile-contexts-v1',
                'contexts': {PIN: {}, OTHER: {}}, 'search_closures': {}}
            self.assertFalse(maintenance._compile_contexts(full, commands, inspection, None, None))
            full['contexts'].pop(OTHER)
            with self.assertRaises(ValueError):
                maintenance._compile_contexts(full, commands, inspection, None, None)

    def test_selected_contexts_still_enforce_global_headers_namespace_and_sdk(self):
        original = {'include/Owner.cpp': {'sha256': PIN}, 'include/a.h': {'sha256': OTHER}}
        sdk = {'include/std.h': PIN}
        arguments = ['-I{reuse}/include', '-O3']
        namespace = {'{reuse}/' + name: item['sha256'] for name, item in original.items()}
        namespace.update({'{sdk}/' + name: pin for name, pin in sdk.items()})
        closure = {'schema_version': 1, 'kind': 'foundation-engine-original-include-search-v1',
            'directories': ['{reuse}/include'], 'original_inventory_sha256': hashlib.sha256(encoded(original)).hexdigest(),
            'sdk_manifest_sha256': PIN, 'namespace_sha256': hashlib.sha256(encoded(namespace)).hexdigest(),
            'headers_sha256': hashlib.sha256(encoded({k: v for k, v in namespace.items() if not k.endswith('.cpp')})).hexdigest()}
        key = hashlib.sha256(encoded(closure)).hexdigest()
        context = {'source': {'original_path': '/old/include/Owner.cpp',
            'input': reference('include/Owner.cpp', root='reuse')}, 'headers': [], 'macros': [],
            'generated_metadata': [], 'sdk_manifest_sha256': PIN, 'arguments': arguments,
            'closure_mode': 'include-search-v1', 'unified_members': [], 'search_closure_sha256': key}
        value = {'schema_version': 1, 'kind': maintenance.SELECTED_CONTEXT_KIND,
            'contexts': {PIN: context}, 'search_closures': {key: closure}, 'opaque_baseline': {}}
        commands = {PIN: {'cwd': '/old', 'argv': ['/sdk/upstream/emscripten/em++', '-I/old/include',
            '-O3', '-o', 'Owner.o', '-c', '/old/include/Owner.cpp']}, OTHER: {}}
        inspection = SimpleNamespace(profile={'engine_objects': ['Owner.cpp'],
            'owner_postimages': {'Owner.cpp': ['engine/Owner.cpp']}},
            proof={'objects': [{'id': 'Owner.cpp'}], 'baseline': {'original_bindings':
                {'reuse': '/old', 'sdk': '/sdk', 'sources': '/new'}}},
            selection={'sdk_manifest_sha256': PIN},
            inventories={'reuse': {n: i['sha256'] for n, i in original.items()}, 'sdk': sdk})
        view = {'original_files': original, 'postimages': {}}
        with mock.patch.object(maintenance, '_object_provenance', return_value=PIN), \
             mock.patch.object(maintenance, '_opaque_baseline'):
            maintenance._compile_contexts(value, commands, inspection, lambda ref: Path('/fixture/source'), view)
            for mutation in ('header-postimage', 'header-bytes', 'shadow', 'sdk'):
                current, changed_view = copy.deepcopy(inspection), copy.deepcopy(view)
                if mutation == 'header-postimage': changed_view['postimages']['reuse', 'include/a.h'] = reference('engine/a.h')
                elif mutation == 'header-bytes': current.inventories['reuse']['include/a.h'] = PIN
                elif mutation == 'shadow': current.inventories['reuse']['include/extra.h'] = OTHER
                else: current.selection['sdk_manifest_sha256'] = OTHER
                with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                    maintenance._compile_contexts(value, commands, current, lambda ref: Path('/fixture/source'), changed_view)

    def test_opaque_mode_admits_only_unchanged_preexisting_baseline_metadata(self):
        original = {'provenance/baseline-rules.ninja': {'sha256': PIN}}
        namespace = {'{reuse}/provenance/baseline-rules.ninja': PIN}
        closure = {'schema_version': 1, 'kind': 'foundation-engine-original-include-search-v1',
            'directories': [], 'original_inventory_sha256': hashlib.sha256(encoded(original)).hexdigest(),
            'sdk_manifest_sha256': PIN, 'namespace_sha256': hashlib.sha256(encoded(namespace)).hexdigest(),
            'headers_sha256': hashlib.sha256(encoded(namespace)).hexdigest()}
        key = hashlib.sha256(encoded(closure)).hexdigest()
        inspection = SimpleNamespace(selection={'sdk_manifest_sha256': PIN},
            inventories={'reuse': {'provenance/baseline-rules.ninja': PIN,
                'provenance/original-engine-build.json': OTHER}, 'sdk': {}},
            profile={'owner_postimages': {}})
        view = {'original_files': original, 'postimages': {},
            'opaque_baseline_metadata': {'provenance/original-engine-build.json': OTHER}}
        maintenance._search_closure(key, [], inspection, view, {key: closure}, set())
        for mutation in ('changed-old-metadata', 'new-name', 'untrusted-full-mode'):
            current, changed_view = copy.deepcopy(inspection), copy.deepcopy(view)
            if mutation == 'changed-old-metadata': current.inventories['reuse']['provenance/original-engine-build.json'] = PIN
            elif mutation == 'new-name': current.inventories['reuse']['provenance/new-note.json'] = OTHER
            else: changed_view.pop('opaque_baseline_metadata')
            with self.subTest(mutation=mutation), self.assertRaisesRegex(ValueError, 'New filename'):
                maintenance._search_closure(key, [], current, changed_view, {key: closure}, set())

    def test_physical_original_and_logical_predecessor_are_distinct_authorities(self):
        before = reference('cold/Owner.cpp', root='reuse', pin=PIN)
        after = reference('selected/Owner.cpp', pin=OTHER)
        original = {'cold/Owner.cpp': {'sha256': PIN}}
        projected = {'selected/Owner.cpp': {'preimage_sha256': '3' * 64, 'sha256': OTHER}}
        maintenance._physical_postimage(before, after, original, projected)
        for mutation in ('original', 'successor', 'missing-path'):
            a, b = copy.deepcopy(original), copy.deepcopy(projected)
            if mutation == 'original': a['cold/Owner.cpp']['sha256'] = OTHER
            elif mutation == 'successor': b['selected/Owner.cpp']['sha256'] = PIN
            else: b.clear()
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                maintenance._physical_postimage(before, after, a, b)

    def test_regular_archive_accepts_exact_names_and_one_required_llvm_index_pad(self):
        with tempfile.TemporaryDirectory(prefix='document-archive-fixture-') as temporary:
            path = Path(temporary) / 'input.a'
            for width in (4, 8):
                for symbols, count in ((b'abc\0', 1), (b'ab\0', 1), (b'ab\0\0', 1),
                                       (b'a\0bc\0', 2), (b'a\0bc\0\0', 2), (b'', 0)):
                    with self.subTest(width=width, symbols=symbols):
                        path.write_bytes(regular_archive(symbols, count, width))
                        result = maintenance.read_regular_archive(path)
                        self.assertEqual(result, [{'name': 'member.o', 'bytes': 11,
                            'sha256': hashlib.sha256(b'inert bytes').hexdigest()}])

    def test_regular_archive_rejects_extra_empty_missing_or_unneeded_symbol_padding(self):
        with tempfile.TemporaryDirectory(prefix='document-archive-fixture-') as temporary:
            path = Path(temporary) / 'input.a'
            for width in (4, 8):
                for symbols, count in ((b'abc', 1), (b'\0', 1), (b'one\0', 2),
                        (b'a\0b\0', 1), (b'ab\0\0\0', 1), (b'abc\0\0', 1),
                        (b'\0', 0), (b'\0\0', 0), (b'foreign', 0)):
                    with self.subTest(width=width, symbols=symbols, count=count), \
                         self.assertRaisesRegex(ValueError, 'symbol names'):
                        path.write_bytes(regular_archive(symbols, count, width))
                        maintenance.read_regular_archive(path)

    def test_regular_archive_still_requires_actual_indexed_member_header_offsets(self):
        with tempfile.TemporaryDirectory(prefix='document-archive-fixture-') as temporary:
            path = Path(temporary) / 'input.a'
            for width in (4, 8):
                with self.subTest(width=width), self.assertRaisesRegex(ValueError, 'missing member header'):
                    path.write_bytes(regular_archive(b'ab\0\0', 1, width, wrong_offset=True))
                    maintenance.read_regular_archive(path)

    def test_explicit_document_selector_and_distinct_plan_contract(self):
        self.assertEqual(maintenance.profile_path('pixel'),
            'recipes/webkitwasm-document-v2/maintenance-profile-pixel.json')
        self.assertEqual(maintenance.profile_path('physical'),
            'recipes/webkitwasm-document-v2/maintenance-profile-physical.json')
        for value in ('copied259', '', None, True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                maintenance.profile_path(value)
        self.assertEqual(maintenance.PLAN_KIND, 'foundation-document-v2-maintenance-plan-v1')
        self.assertIn('document_profile', maintenance.SELECTION_FIELDS)

    def test_document_json_rejects_duplicate_and_nonfinite_values(self):
        for raw in (b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":"\xff"}'):
            with self.subTest(raw=raw), self.assertRaises((ValueError, UnicodeError)):
                maintenance.document(raw)

    def test_original_arguments_relocate_only_known_include_operands(self):
        bindings = {'sources': '/original/source', 'sdk': '/original/sdk', 'reuse': '/original/build'}
        record = {'cwd': '/original/build', 'argv': ['/original/sdk/upstream/emscripten/em++',
            '-I/original/source/include', '-isystem', '/original/sdk/include', '-fno-exceptions',
            '-MD', '-MT', 'out.o', '-MF', 'out.d', '-o', 'out.o', '-c', '/original/source/main.cpp']}
        self.assertEqual(maintenance._original_arguments(record, bindings),
            ['-I{sources}/include', '-isystem', '{sdk}/include', '-fno-exceptions'])
        with self.assertRaisesRegex(ValueError, 'one exact admitted root'):
            maintenance._relocate_original('/outside/include', record['cwd'], bindings)

    def test_depfile_continuations_escaped_paths_and_literal_dollars(self):
        self.assertEqual(maintenance._depfile_inputs(b'out.o: /a/main.cpp \\\n /a/space\\ header.h /a/cash$$.h\n'),
            ['/a/main.cpp', '/a/space header.h', '/a/cash$.h'])

    def test_depfile_rejects_missing_rules_variables_and_multiple_targets(self):
        for raw in (b'no rule', b'a.o b.o: /a.cpp', b'a.o: $(INPUT)', b'a.o: /a.cpp\nb.o: /b.cpp',
                    b'a.o: /a.cpp # ignored.h', b'a.o: /a.cpp\\'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                maintenance._depfile_inputs(raw)

    def test_original_context_cannot_claim_an_mmd_depfile_as_complete_headers(self):
        context = dict.fromkeys(('source', 'headers', 'macros', 'generated_metadata',
            'sdk_manifest_sha256', 'arguments', 'depfile', 'unified_members'))
        context['closure_mode'] = 'depfile-v1'
        with self.assertRaisesRegex(ValueError, 'including system headers'):
            maintenance._context_record(context, {'argv': ['compiler', '-MMD', '-MF', 'file.d']},
                None, None, {}, {}, set())

    def test_shared_search_closure_binds_namespace_sdk_and_known_cpp_owners(self):
        original = {'include/a.h': {'sha256': PIN}, 'include/Owner.cpp': {'sha256': OTHER},
                    'src/local.h': {'sha256': PIN}}
        sdk = {'include/std.h': PIN}
        arguments = ['-I{reuse}/include', '-isystem', '{sdk}/include']
        namespace = {'{reuse}/include/a.h': PIN, '{reuse}/include/Owner.cpp': OTHER,
                     '{reuse}/src/local.h': PIN, '{sdk}/include/std.h': PIN}
        headers = {name: pin for name, pin in namespace.items() if not name.endswith('.cpp')}
        record = {'schema_version': 1, 'kind': 'foundation-engine-original-include-search-v1',
            'directories': ['{reuse}/include', '{sdk}/include'],
            'original_inventory_sha256': hashlib.sha256(encoded(original)).hexdigest(),
            'sdk_manifest_sha256': PIN, 'namespace_sha256': hashlib.sha256(encoded(namespace)).hexdigest(),
            'headers_sha256': hashlib.sha256(encoded(headers)).hexdigest()}
        identity = hashlib.sha256(encoded(record)).hexdigest()
        inspection = SimpleNamespace(selection={'sdk_manifest_sha256': PIN},
            inventories={'reuse': {name: item['sha256'] for name, item in original.items()}, 'sdk': sdk},
            profile={'owner_postimages': {'Owner.cpp': ['engine/Owner.cpp']}})
        view = {'original_files': original,
            'postimages': {('reuse', 'include/Owner.cpp'): reference('engine/Owner.cpp')}}
        validated = set()
        maintenance._search_closure(identity, arguments, inspection, view, {identity: record}, validated)
        self.assertEqual(validated, {identity})
        for mutation in ('header-postimage', 'extra-name', 'different-sdk', 'wrong-argv',
                         'source-local-bytes', 'source-local-postimage', 'source-local-extra'):
            changed_view, changed_inspection = copy.deepcopy(view), copy.deepcopy(inspection)
            changed_arguments = list(arguments)
            if mutation == 'header-postimage':
                changed_view['postimages']['reuse', 'include/a.h'] = reference('engine/a.h')
            elif mutation == 'extra-name': changed_inspection.inventories['reuse']['include/shadow.h'] = OTHER
            elif mutation == 'different-sdk': changed_inspection.selection['sdk_manifest_sha256'] = OTHER
            elif mutation == 'wrong-argv': changed_arguments.append('-I{reuse}/other')
            elif mutation == 'source-local-bytes': changed_inspection.inventories['reuse']['src/local.h'] = OTHER
            elif mutation == 'source-local-postimage':
                changed_view['postimages']['reuse', 'src/local.h'] = reference('engine/local.h')
            else: changed_inspection.inventories['reuse']['src/optional.h'] = OTHER
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                maintenance._search_closure(identity, changed_arguments, changed_inspection,
                    changed_view, {identity: record}, set())

    def test_search_context_source_must_match_original_compile_before_return(self):
        value = {'source': {'original_path': '/old/wrong.cpp', 'input': reference('wrong.cpp', root='reuse')},
            'headers': [], 'macros': [], 'generated_metadata': [], 'sdk_manifest_sha256': PIN,
            'arguments': ['-O3'], 'closure_mode': 'include-search-v1', 'unified_members': [],
            'search_closure_sha256': PIN}
        command = {'cwd': '/old', 'argv': ['/sdk/upstream/emscripten/em++', '-O3',
            '-o', 'object.o', '-c', '/old/UnifiedSource-foo.cpp']}
        inspection = SimpleNamespace(selection={'sdk_manifest_sha256': PIN}, inventories={'sdk': {}},
            proof={'baseline': {'original_bindings': {'reuse': '/old', 'sdk': '/sdk', 'sources': '/new'}}})
        with self.assertRaisesRegex(ValueError, 'source differs from its exact compile'):
            maintenance._context_record(value, command, inspection, lambda ref: Path('/fixture/wrong.cpp'),
                {'original_files': {'wrong.cpp': {'sha256': PIN}}}, {}, set())

    def test_original_unified_members_follow_actual_ordered_include_search(self):
        with tempfile.TemporaryDirectory(prefix='document-unified-tiny-') as temporary:
            source = Path(temporary) / 'UnifiedSource-test.cpp'
            source.write_bytes(b'#include "dom/One.cpp"\n#include "dom/Two.cpp"\n')
            value = {'source': {'original_path': '/old/build/UnifiedSource-test.cpp',
                'input': reference('build/UnifiedSource-test.cpp', root='reuse')},
                'arguments': ['-I{reuse}/Source/WebCore'], 'unified_members': [
                    {'original_path': '/old/Source/WebCore/dom/' + name,
                     'input': reference('Source/WebCore/dom/' + name, root='reuse')}
                    for name in ('One.cpp', 'Two.cpp')]}
            inspection = SimpleNamespace(proof={'baseline': {'original_bindings':
                {'reuse': '/old', 'sdk': '/sdk', 'sources': '/new-source'}}})
            original = {'Source/WebCore/dom/One.cpp': {}, 'Source/WebCore/dom/Two.cpp': {}}
            maintenance._original_unified_members(value, {'cwd': '/old/build'}, inspection,
                lambda ref: source, original)
            value['unified_members'].reverse()
            with self.assertRaisesRegex(ValueError, 'include-search selection'):
                maintenance._original_unified_members(value, {'cwd': '/old/build'}, inspection,
                    lambda ref: source, original)

    def test_new_source_requires_bounded_derived_donor(self):
        commands = {PIN: {'cwd': '/original/build', 'argv': ['compiler', '-fno-exceptions',
            '-o', 'main.o', '-c', '/original/source/main.cpp']}}
        obj = {'id': 'New.cpp', 'source': reference('new/New.cpp'),
            'arguments': ['-fno-exceptions', '-DBIB_ENGINE_PROVIDER_DOCUMENT_V2=1', '-fexceptions'],
            'provenance': {'kind': 'derived-command-v1', 'donor_command_sha256': PIN,
                'profile_sha256': OTHER,
                'source_replacement': {'before': '/original/source/main.cpp', 'after': reference('new/New.cpp')},
                'remove': [], 'append': ['-DBIB_ENGINE_PROVIDER_DOCUMENT_V2=1', '-fexceptions']}}
        inspection = SimpleNamespace(profile={'document_profile': 'pixel', 'derived_commands': {
            'New.cpp': {'donor_source': 'main.cpp', 'remove': [],
                'append': ['-DBIB_ENGINE_PROVIDER_DOCUMENT_V2=1', '-fexceptions']}}},
            proof={'baseline': {'original_bindings': {
                'sources': '/original/source', 'sdk': '/original/sdk', 'reuse': '/original/build'}}})
        with mock.patch.object(maintenance, 'digest', return_value=OTHER):
            self.assertEqual(maintenance._object_provenance(obj, commands, inspection), PIN)
            for mutation in ('profile', 'source', 'append', 'argv'):
                changed = copy.deepcopy(obj)
                if mutation == 'profile':
                    changed['provenance']['profile_sha256'] = PIN
                elif mutation == 'source':
                    changed['provenance']['source_replacement']['before'] = '/original/source/fake.cpp'
                elif mutation == 'append':
                    changed['provenance']['append'].append('-include')
                else:
                    changed['arguments'].append('-O3')
                with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                    maintenance._object_provenance(changed, commands, inspection)

    def test_a_new_object_cannot_claim_original_command_provenance(self):
        obj = {'id': 'New.cpp', 'source': reference('New.cpp'), 'arguments': ['-O3'],
            'provenance': {'kind': 'original-command-v1', 'command_sha256': PIN}}
        commands = {PIN: {'cwd': '/original/build', 'argv': ['compiler', '-O3',
            '-o', 'main.o', '-c', '/original/source/main.cpp']}}
        inspection = SimpleNamespace(profile={'derived_commands': {'New.cpp': {}}},
            proof={'baseline': {'original_bindings': {'sources': '/original/source',
                'sdk': '/original/sdk', 'reuse': '/original/build'}}})
        with self.assertRaisesRegex(ValueError, 'explicit derived'):
            maintenance._object_provenance(obj, commands, inspection)

    def test_untouched_object_reuse_rejects_changed_header_and_selected_postimage(self):
        source = {'original_path': '/original/source/a.cpp', 'input': reference('original/a.cpp', root='reuse')}
        header = {'original_path': '/original/source/a.h', 'input': reference('original/a.h', root='reuse')}
        context = {'source': source, 'headers': [header], 'generated_metadata': [], 'arguments': ['-O3'],
            'unified_members': []}
        inspection = SimpleNamespace(inventories={'sources': {'a.cpp': PIN, 'a.h': PIN}},
            proof={'baseline': {'original_bindings': {'sources': '/original/source',
                'sdk': '/original/sdk', 'reuse': '/original/build'}}})
        with mock.patch.object(maintenance, '_arguments', return_value=[]):
            maintenance._reusable_context(context, {'cwd': '/original/build'}, inspection)
            inspection.inventories['sources']['a.h'] = OTHER
            with self.assertRaisesRegex(ValueError, 'context changed'):
                maintenance._reusable_context(context, {'cwd': '/original/build'}, inspection)
            inspection.inventories['sources']['a.h'] = PIN
            with self.assertRaisesRegex(ValueError, 'context changed'):
                maintenance._reusable_context(context, {'cwd': '/original/build'}, inspection,
                    {('sources', 'a.h'): reference('new/a.h', pin=OTHER)})

    def test_compile_context_binds_all_current_inputs_and_metadata(self):
        metadata = {'generator': reference('generate.py'), 'template': reference('template.in')}
        obj = {'source': reference('New.cpp'), 'dependencies': [reference('a.h')],
            'unified_members': [], 'arguments': ['-O3', '-DTEST=1']}
        obj['compile_context'] = {'source': obj['source'], 'headers': obj['dependencies'],
            'arguments': obj['arguments'], 'macros': ['-DTEST=1'],
            'generated_metadata': [metadata[key] for key in sorted(metadata)], 'sdk_manifest_sha256': PIN}
        inspection = SimpleNamespace(proof={'metadata': metadata}, selection={'sdk_manifest_sha256': PIN})
        maintenance._current_context(obj, inspection)
        for key in ('source', 'headers', 'arguments', 'macros', 'generated_metadata', 'sdk_manifest_sha256'):
            changed = copy.deepcopy(obj)
            changed['compile_context'][key] = []
            with self.subTest(key=key), self.assertRaises(ValueError):
                maintenance._current_context(changed, inspection)

    def test_owner_postimages_require_projected_source_bytes_and_physical_mapping(self):
        selected = reference('engine/Selected.cpp')
        obj = {'id': 'Unified.cpp', 'source': reference('engine/Unified.cpp'),
            'unified_members': [selected]}
        inspection = SimpleNamespace(profile={'owner_postimages': {'Unified.cpp': [selected['path']]}},
            projection={'files': {selected['path']: {'sha256': PIN}}})
        view = {'postimages': {('reuse', 'original/Selected.cpp'): selected}}
        maintenance._owner_postimages(obj, inspection, view)
        for mutation in ('root', 'sha', 'mapping'):
            changed = copy.deepcopy(obj)
            if mutation == 'root': changed['unified_members'][0]['root'] = 'reuse'
            elif mutation == 'sha': changed['unified_members'][0]['sha256'] = OTHER
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                maintenance._owner_postimages(changed, inspection,
                    {'postimages': {}} if mutation == 'mapping' else view)

    def test_alias_groups_require_exact_per_path_pre_and_postimages(self):
        files = {'engine/a.h': {'preimage_sha256': PIN, 'sha256': OTHER},
                 'engine/private/a.h': {'preimage_sha256': PIN, 'sha256': OTHER}}
        group = {'canonical': 'engine/a.h', 'paths': sorted(files),
            'preimages': dict.fromkeys(files, PIN), 'postimages': dict.fromkeys(files, OTHER)}
        maintenance._validate_alias_groups([group], files)
        for mutation in ('canonical', 'preimage', 'postimage', 'overlap'):
            changed = copy.deepcopy(group)
            if mutation == 'canonical': changed['canonical'] = 'unproven/a.h'
            elif mutation == 'preimage': changed['preimages']['engine/a.h'] = OTHER
            elif mutation == 'postimage': changed['postimages']['engine/a.h'] = PIN
            groups = [changed, changed] if mutation == 'overlap' else [changed]
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                maintenance._validate_alias_groups(groups, files)

    def test_physical_receipt_authority_and_every_alias_postimage_are_required(self):
        with tempfile.TemporaryDirectory(prefix='document-alias-tiny-') as temporary:
            base = Path(temporary).resolve()
            roots = {name: base / name for name in ('sources', 'reuse')}
            inventories = {name: {} for name in roots}
            for path in roots.values(): path.mkdir()

            def write(root, path, value):
                raw = value if type(value) is bytes else encoded(value)
                destination = roots[root] / path
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(raw)
                pin = hashlib.sha256(raw).hexdigest()
                inventories[root][path] = pin
                return reference(path, root=root, pin=pin)

            canonical = write('reuse', 'original/a.h', b'old')
            alias = write('reuse', 'original/private/a.h', b'old')
            unrelated = write('reuse', 'original/unrelated.h', b'old')
            first = write('sources', 'engine/a.h', b'new')
            second = write('sources', 'engine/private/a.h', b'new')
            identity = [1, 2, 33188, 1, 3, 4, 5]
            receipt = {'schema_version': 1, 'kind': 'closed-unpublished-baseline-copy-v1',
                'status': 'closed-exact-readback-passed-unpublished', 'files': {
                    ref['path']: {'sha256': ref['sha256'], 'bytes': 3,
                        'source_identity': identity if ref is not unrelated else [1, 3, 33188, 1, 3, 4, 5]}
                    for ref in (canonical, alias, unrelated)}}
            copy_set = {'kind': 'foundation-original-baseline-prospective-copy-set-v1', 'entries': [
                {'destination': ref['path'], 'sha256': ref['sha256'],
                 'expected_resolved_path': canonical['path'] if ref is not unrelated else unrelated['path']}
                for ref in (canonical, alias, unrelated)]}
            evidence = {'discovery': write('reuse', 'discovery.json', {}),
                'copy_set': write('reuse', 'copy-set.json', copy_set),
                'copy_receipt': write('reuse', 'copy-receipt.json', receipt)}
            record = {'schema_version': 1, 'kind': 'foundation-document-v2-header-identity-v1',
                'projection_sha256': PIN, 'evidence': evidence,
                'classes': [{'original_identity': identity, 'canonical': canonical, 'aliases': [alias]}],
                'postimages': [{'input': canonical, 'output': first}, {'input': alias, 'output': second}]}
            files = {ref['path']: {'preimage_sha256': canonical['sha256'], 'sha256': ref['sha256']}
                     for ref in (first, second)}
            groups = [{'canonical': first['path'], 'paths': sorted(files),
                'preimages': dict.fromkeys(files, canonical['sha256']),
                'postimages': dict.fromkeys(files, first['sha256'])}]
            inspection = SimpleNamespace(roots=roots, inventories=inventories,
                selection={'projection_sha256': PIN},
                projection={'files': files, 'physical_alias_groups': groups, 'declared_source_aliases': []},
                profile={'declared_source_aliases': []},
                proof={'header_identity': write('sources', 'identity.json', record)})
            view = maintenance._header_identity(inspection)
            self.assertEqual(view['mapping_count'], 3)
            self.assertEqual({item['external-contents'] for item in view['overlay']['roots']},
                {str(roots['sources'] / first['path'])})
            self.assertNotIn(str(roots['reuse'] / unrelated['path']),
                {item['name'] for item in view['overlay']['roots']})
            self.assertIn(str(roots['sources'] / second['path']),
                {item['name'] for item in view['overlay']['roots']})
            for mutation in ('missing-postimage', 'wrong-canonical', 'missing-class'):
                changed = copy.deepcopy(record)
                if mutation == 'missing-postimage': changed['postimages'].pop()
                elif mutation == 'wrong-canonical':
                    changed['classes'][0]['canonical'], changed['classes'][0]['aliases'][0] = alias, canonical
                else: changed['classes'] = []
                inspection.proof['header_identity'] = write('sources', 'identity.json', changed)
                with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                    maintenance._header_identity(inspection)
            different = write('reuse', alias['path'], b'BAD')
            receipt['files'][alias['path']]['sha256'] = different['sha256']
            next(item for item in copy_set['entries'] if item['destination'] == alias['path'])['sha256'] = different['sha256']
            changed = copy.deepcopy(record)
            changed['evidence']['copy_receipt'] = write('reuse', 'copy-receipt.json', receipt)
            changed['evidence']['copy_set'] = write('reuse', 'copy-set.json', copy_set)
            changed['classes'][0]['aliases'] = [different]
            changed['postimages'] = []
            inspection.projection['physical_alias_groups'] = []
            inspection.proof['header_identity'] = write('sources', 'identity.json', changed)
            with self.assertRaisesRegex(ValueError, 'identical preimage bytes'):
                maintenance._header_identity(inspection)

    def test_declared_source_layout_aliases_need_exact_profile_and_projection(self):
        with tempfile.TemporaryDirectory(prefix='document-layout-tiny-') as temporary:
            root = Path(temporary).resolve()
            for name in ('canonical.h', 'alias.h'): (root / name).write_bytes(b'new')
            pin = hashlib.sha256(b'new').hexdigest()
            files = {name: {'preimage_sha256': PIN, 'sha256': pin} for name in ('canonical.h', 'alias.h')}
            group = {'canonical': 'canonical.h', 'paths': sorted(files),
                'preimages': dict.fromkeys(files, PIN), 'postimages': dict.fromkeys(files, pin)}
            inspection = SimpleNamespace(roots={'sources': root},
                projection={'declared_source_aliases': [group], 'files': files},
                profile={'declared_source_aliases': [group]})
            view = maintenance._source_aliases(inspection)
            self.assertEqual(view['mappings'], {str(root / 'alias.h'): str(root / 'canonical.h')})
            inspection.profile = {'declared_source_aliases': []}
            with self.assertRaisesRegex(ValueError, 'explicit maintained layout'):
                maintenance._source_aliases(inspection)

    def test_untrusted_filename_options_and_overlay_flags_are_rejected(self):
        inspection = SimpleNamespace(profile={'compile_literals': ['-O3', '-DBIB_ENGINE_PROVIDER_DOCUMENT_V2=1']})
        maintenance._arguments(['-O3', '-DBIB_ENGINE_PROVIDER_DOCUMENT_V2=1'], inspection=inspection)
        for arg in ('-ivfsoverlay', '-include', '-iquote', '@response', '-fplugin=evil.so', 'file.cpp'):
            with self.subTest(arg=arg), self.assertRaisesRegex(ValueError, 'reviewed document-v2 grammar'):
                maintenance._arguments([arg], inspection=inspection)

    def test_pixel_and_physical_links_preserve_raw_exports_exactly_once(self):
        for name in ('pixel', 'physical'):
            selected = maintenance.profile(name)
            self.assertEqual(selected['link_literals'].count('-lexports.js'), 1)
            self.assertNotIn('-lexports.js', selected['compile_literals'])
            arguments = selected['link_literals'] + ['-s' + key + '=' + value
                for key, value in selected['link_settings'].items()]
            with self.subTest(document_profile=name):
                self.assertEqual(maintenance._arguments(arguments, link=True,
                    inspection=SimpleNamespace(profile=selected)), [])
                for changed in ([arg for arg in arguments if arg != '-lexports.js'],
                                arguments + ['-lexports.js']):
                    with self.assertRaisesRegex(ValueError, 'exactly one literal -lexports.js'):
                        maintenance._arguments(changed, link=True,
                            inspection=SimpleNamespace(profile=selected))

    def test_raw_export_library_cannot_be_a_compile_argument_or_link_alias(self):
        selected = maintenance.profile('pixel')
        selected['compile_literals'].append('-lexports.js')
        with self.assertRaisesRegex(ValueError, 'link-only'):
            maintenance._arguments(['-lexports.js'], inspection=SimpleNamespace(profile=selected))
        arguments = selected['link_literals'] + ['-s' + key + '=' + value
            for key, value in selected['link_settings'].items()]
        for alias in ('-l', 'exports.js', '-lexports.js=1', '-Wl,-lexports.js'):
            with self.subTest(alias=alias), self.assertRaisesRegex(ValueError, 'reviewed document-v2 grammar'):
                maintenance._arguments(arguments + [alias], link=True,
                    inspection=SimpleNamespace(profile=selected))

    def test_document_profiles_reject_missing_duplicate_or_compile_export_library(self):
        for name in ('pixel', 'physical'):
            original = maintenance.profile(name)
            for mutation in ('missing', 'duplicate', 'compile'):
                changed = copy.deepcopy(original)
                if mutation == 'missing': changed['link_literals'].remove('-lexports.js')
                elif mutation == 'duplicate': changed['link_literals'].append('-lexports.js')
                else: changed['compile_literals'].append('-lexports.js')
                with self.subTest(document_profile=name, mutation=mutation), \
                     mock.patch.object(maintenance, 'checked_document', return_value=changed), \
                     self.assertRaisesRegex(ValueError, 'metadata/exports/definition policy'):
                    maintenance.profile(name)

    def test_actual_document_exports_require_exact_function_signatures(self):
        maintenance.validate_artifact_facts(facts())
        for name in ('bib_engine_wasm_document_facts_v1', 'bib_engine_wasm_document_configure_v1',
                     'bib_engine_get_provider_v1'):
            changed = facts()
            next(item for item in changed['exports'] if item['name'] == name)['details']['parameters'] = []
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'mistyped actual document export'):
                maintenance.validate_artifact_facts(changed)

    def test_artifact_inspection_rejects_start_shared_memory_and_diagnostic_entries(self):
        for kind in ('start', 'shared', 'diagnostic'):
            changed = facts()
            if kind == 'start': changed['start'] = 0
            elif kind == 'shared': changed['memories'][0]['shared'] = True
            else: changed['exports'].append({'name': 'bib_eval', 'kind': 'function', 'details': {}})
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                maintenance.validate_artifact_facts(changed)

    def test_document_provider_build_uses_composite_contract_and_exact_13_fields(self):
        recipe = {'inputs': [], 'target': {}, 'toolchain': {}, 'options': {}}
        selection = {'document_profile': 'pixel', 'recipe_sha256': PIN}
        build = {'schema_version': 1, 'kind': contract.BUILD_KIND,
            'target': {}, 'toolchain': {}, 'options': {}, 'source_recipe_sha256': PIN,
            'source_inputs_sha256': hashlib.sha256(encoded([])).hexdigest(),
            'contract_header_sha256': contract.CONTRACT_SHA256, 'binding': contract.BINDING,
            'configuration': contract.expected_configuration(document_profile='pixel'),
            'capabilities': '1795', 'bridge_abi': 65536,
            'provider_contract': contract.provider_contract(document_profile='pixel')}
        maintenance.validate_provider_build(build, selection, recipe)
        for key, value in (('contract_header_sha256', contract.BASE_HEADER_SHA256),
                           ('bridge_abi', True), ('kind', 'foundation-neutral-engine-provider-build-v1')):
            changed = dict(build, **{key: value})
            with self.subTest(key=key), self.assertRaises(ValueError):
                maintenance.validate_provider_build(changed, selection, recipe)
        with self.assertRaisesRegex(ValueError, 'fields'):
            maintenance.validate_provider_build(dict(build, production_eligible=True), selection, recipe)

    def test_graph_links_only_the_explicit_direct_list_and_document_metadata(self):
        with tempfile.TemporaryDirectory(prefix='document-maintenance-tiny-') as temporary:
            root = Path(temporary).resolve()
            (root / 'cmake').mkdir()
            metadata = {name: reference(name) for name in ('generator', 'template', 'prelink_plan',
                'contract_header', 'document_header', 'document_contract', 'document_catalog',
                'document_schema', 'action_ack', 'physical_catalog')}
            proof = {'host_tools': {'python': {'path': '/fixture/python'}},
                'sdk_tools': {'emxx': {'path': 'emxx'}}, 'metadata': metadata,
                'objects': [{'id': name, 'arguments': ['-O3'], 'source': reference(name),
                    'dependencies': [], 'unified_members': []} for name in ('Direct.cpp', 'Owner.cpp')],
                'replacements': [], 'archives': [], 'link': {'dependencies': [], 'archives': [],
                    'flags': [], 'data': [], 'pre_js': reference('pre.js'), 'host_library': reference('host.js')}}
            inspection = SimpleNamespace(proof=proof, roots={'sources': root / 'sources', 'sdk': root / 'sdk'},
                inventories={}, selection={'document_profile': 'physical'}, profile={'direct_objects': ['Direct.cpp']})
            with mock.patch.object(maintenance, '_tool', return_value=Path('/fixture/python')), \
                 mock.patch.object(maintenance, 'ref_path', side_effect=lambda ref, roots, inv: root / ref['path']), \
                 mock.patch.object(maintenance, '_arguments', return_value=[]), \
                 mock.patch.object(maintenance, '_header_identity', return_value=None):
                _, fragment, commands = maintenance._graph(inspection, {}, root / 'plan.json', PIN, root)
            self.assertIn('--document-profile', commands['metadata'])
            self.assertIn('--physical-catalog', commands['metadata'])
            self.assertIn(str(root / 'objects/Direct.cpp.o'), commands['link'])
            self.assertNotIn(str(root / 'objects/Owner.cpp.o'), commands['link'])
            self.assertIn('BibCopiedDocumentMetadata.generated.h', fragment.read_text())

    def test_cli_requires_document_profile_before_planning(self):
        with mock.patch.object(maintenance, 'make_plan') as planner, \
             mock.patch('sys.stderr', new_callable=io.StringIO):
            with self.assertRaises(SystemExit):
                maintenance.main(['plan'])
        planner.assert_not_called()


class EditorMaintenanceTests(unittest.TestCase):
    def test_editor_is_explicit_and_legacy_contract_stays_closed(self):
        self.assertEqual(maintenance.profile_selector('editor'), 'editor')
        with self.assertRaises(ValueError):
            contract.document_selector('editor')
        for value in ('2035', 3, True, None, 'physical-editor'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                maintenance.profile_selector(value)
        self.assertNotIn('tools/appended_engine_editor_contract.py', maintenance.required_helpers('pixel'))
        self.assertNotIn('tools/appended_engine_editor_contract.py', maintenance.required_helpers('physical'))
        self.assertIn('tools/appended_engine_editor_contract.py', maintenance.required_helpers('editor'))

    def test_editor_profile_has_exact_sources_owners_macro_and_exports(self):
        selected = maintenance.profile('editor')
        self.assertEqual((len(selected['direct_objects']), len(selected['engine_objects'])), (35, 16))
        self.assertEqual(selected['capabilities'], '2035')
        self.assertEqual(selected['physical_input_capabilities'], 208)
        self.assertIn('-DBIB_ENGINE_PROVIDER_EDITOR_V1=1', selected['compile_literals'])
        self.assertIn('_bib_engine_wasm_editor_facts_v1', selected['link_settings']['EXPORTED_FUNCTIONS'])
        self.assertNotIn('_bib_engine_wasm_document_facts_v1', selected['link_settings']['EXPORTED_FUNCTIONS'])
        for owner in ('UnifiedSource-be65d27a-9.cpp', 'UnifiedSource-767013ce-4.cpp'):
            self.assertIn(owner, selected['owner_postimages'])
        for paths in selected['owner_postimages'].values():
            self.assertTrue(all(path.endswith('.cpp') for path in paths))
        self.assertNotIn('native_editor_controller.cpp', ' '.join(selected['source_bindings'].values()))
        for mutation in ('caps', 'macro', 'getter', 'duplicate'):
            changed = copy.deepcopy(selected)
            if mutation == 'caps': changed['capabilities'] = '2003'
            elif mutation == 'macro': changed['compile_literals'].remove('-DBIB_ENGINE_PROVIDER_EDITOR_V1=1')
            elif mutation == 'getter': changed['link_settings']['EXPORTED_FUNCTIONS'] = changed['link_settings']['EXPORTED_FUNCTIONS'].replace('wasm_editor_', 'wasm_document_')
            else: changed['direct_objects'].append(changed['direct_objects'][0])
            with self.subTest(mutation=mutation), mock.patch.object(maintenance, 'checked_document', return_value=changed), self.assertRaises(ValueError):
                maintenance.profile('editor')

    def test_rich_ui_union_preserves_archive_owners_and_bounded_donor_policy(self):
        direct = {
            'BibEngineUiOwner.cpp': 'ui/BibEngineUiOwner.cpp',
            'BibNativePopupOwner.cpp': 'popup/BibNativePopupOwner.cpp',
            'NativePopupController.cpp': 'popup/NativePopupController.cpp',
            'BibClipboardStore.cpp': 'clipboard/BibClipboardStore.cpp',
        }
        owners = {
            'UnifiedSource-950a39b6-13.cpp': 'html/HTMLSelectElement.cpp',
            'UnifiedSource-c57e08af-3.cpp': 'loader/EmptyClients.cpp',
            'UnifiedSource-f34946be-3.cpp': 'editing/Editor.cpp',
            'UnifiedSource-be65d27a-6.cpp': 'dom/DataTransfer.cpp',
            'PasteboardEmscripten.cpp': 'platform/emscripten/PasteboardEmscripten.cpp',
        }
        archives = {'JavaScriptCore': 185, 'PAL': 24, 'Skia': 775, 'WTF': 168, 'WebCore': 924}
        shared = ['-I{sources}/source/document-provider' + suffix
                  for suffix in ('', '/ui', '/popup', '/clipboard')]
        definitions = ['-DBIB_ENGINE_HTML_POPUP_V1=1', '-DBIB_INTERNAL_RICH_CLIPBOARD=1']
        key_include = '-I{sources}/source/document-provider/key'
        for profile, direct_count, owner_count, total, opaque in (
                ('physical', 31, 14, 45, 2062), ('editor', 35, 16, 51, 2060)):
            selected = maintenance.profile(profile)
            with self.subTest(document_profile=profile):
                self.assertEqual((len(selected['direct_objects']), len(selected['engine_objects'])),
                                 (direct_count, owner_count))
                self.assertEqual(len(selected['direct_objects'] + selected['engine_objects']), total)
                self.assertEqual(selected['direct_objects'][-4:], list(direct))
                self.assertEqual(selected['engine_objects'][-5:], list(owners))
                self.assertEqual(selected['archive_members'], archives)
                self.assertEqual(list(selected['archive_members']), list(archives))
                self.assertEqual(sum(selected['archive_members'].values()), 2076)
                self.assertEqual(sum(selected['archive_members'].values()) - owner_count, opaque)
                self.assertEqual(set(direct) & set(selected['exceptions']), {'BibNativePopupOwner.cpp'})
                for definition in definitions:
                    self.assertEqual(selected['compile_literals'].count(definition), 1)
                for name, suffix in direct.items():
                    rule = selected['derived_commands'][name]
                    donor = 'BibAppResources.cpp' if name == 'BibNativePopupOwner.cpp' else 'main.cpp'
                    self.assertEqual(rule, selected['derived_commands'][donor])
                    self.assertEqual(rule['donor_source'], 'main.cpp')
                    self.assertEqual(rule['remove'], [])
                    self.assertEqual(rule['append'].count('-fexceptions'), int(name == 'BibNativePopupOwner.cpp'))
                    self.assertEqual(maintenance._exception_policy(['-fno-exceptions'] + rule['append']),
                                     name == 'BibNativePopupOwner.cpp')
                    self.assertEqual(rule['append'].count(key_include), 1)
                    self.assertEqual(selected['source_bindings'][name], 'source/document-provider/' + suffix)
                    for token in shared + definitions:
                        self.assertEqual(rule['append'].count(token), 1)
                for name, suffix in owners.items():
                    self.assertNotIn(name, selected['exceptions'])
                    self.assertEqual(selected['derived_commands'][name],
                                     {'donor_source': name, 'remove': [], 'append': shared + definitions})
                    postimage = 'source/engine/Source/WebCore/' + suffix
                    self.assertEqual(selected['owner_postimages'][name], [postimage])
                    self.assertEqual(selected['source_bindings'][name],
                                     'source/engine/unified/' + name if name.startswith('UnifiedSource-') else postimage)

    def test_editor_artifact_requires_editor_getter_and_full_signature(self):
        current = facts()
        for row in current['exports']:
            row['name'] = row['name'].replace('wasm_document_', 'wasm_editor_')
        maintenance.validate_artifact_facts(current, 'editor')
        with self.assertRaises(ValueError):
            maintenance.validate_artifact_facts(facts(), 'editor')
        changed = copy.deepcopy(current)
        next(x for x in changed['exports'] if x['name'] == 'bib_engine_wasm_editor_facts_v1')['details']['parameters'].pop()
        with self.assertRaises(ValueError):
            maintenance.validate_artifact_facts(changed, 'editor')
        maintenance.validate_artifact_facts(facts(), 'physical')

    def test_editor_interface_mapping_keeps_document_and_editor_contracts_distinct(self):
        editor = maintenance.profile_contract('editor')
        value = maintenance.metadata_interface_paths('editor')
        self.assertEqual(len(value), 11)
        self.assertEqual(value['document_contract'][1], contract.CONTRACT_SHA256)
        self.assertEqual(value['editor_contract'][1], editor.CONTRACT_SHA256)
        self.assertNotEqual(value['editor_contract'][1], value['document_contract'][1])
        self.assertEqual(value['physical_catalog'][1], contract.PHYSICAL_CATALOG_SHA256)
        for old in ('pixel', 'physical'):
            self.assertFalse(any(key.startswith('editor_') for key in maintenance.metadata_interface_paths(old)))

    def test_editor_build_accepts_only_exact_13field_editor_contract(self):
        editor = maintenance.profile_contract('editor')
        recipe = {'inputs': [], 'target': {}, 'toolchain': {}, 'options': {}}
        selection = {'document_profile': 'editor', 'recipe_sha256': PIN}
        value = {'schema_version': 1, 'kind': editor.BUILD_KIND, 'target': {}, 'toolchain': {},
            'options': {}, 'source_recipe_sha256': PIN, 'source_inputs_sha256': hashlib.sha256(encoded([])).hexdigest(),
            'contract_header_sha256': editor.CONTRACT_SHA256, 'binding': editor.BINDING,
            'configuration': editor.expected_configuration(editor_profile='editor'), 'capabilities': '2035',
            'bridge_abi': 65536, 'provider_contract': editor.provider_contract(editor_profile='editor')}
        maintenance.validate_provider_build(value, selection, recipe)
        for key, bad in (('kind', contract.BUILD_KIND), ('contract_header_sha256', contract.CONTRACT_SHA256),
                         ('configuration', contract.expected_configuration(document_profile='physical')),
                         ('provider_contract', contract.provider_contract(document_profile='physical'))):
            with self.subTest(key=key), self.assertRaises(ValueError):
                maintenance.validate_provider_build(dict(value, **{key: bad}), selection, recipe)
        with self.assertRaises(ValueError):
            maintenance.validate_provider_build(dict(value, eligible=True), selection, recipe)


class GuardRepairEntryPoints(unittest.TestCase):
    def cli(self):
        values = {name: ('editor' if name == 'document_profile' else PIN if name.endswith('sha256') else '/inert/' + name)
                  for name in maintenance.SELECTION_FIELDS}
        argv = ['plan']
        for name, value in values.items(): argv.extend(('--' + name.replace('_', '-'), value))
        return argv + ['--output', '/inert/output']

    def test_cli_explicit_guard_optin_and_unchanged_old_donor_call(self):
        for optin in (False, True):
            argv = self.cli() + ['--successful-donor', '/inert/donor.json', '--successful-donor-sha256', PIN]
            if optin: argv.append('--successful-donor-guard-repair')
            with mock.patch.object(maintenance, 'make_plan', return_value={'inert': True}) as planner, \
                 mock.patch('sys.stdout', new_callable=io.StringIO):
                self.assertEqual(0, maintenance.main(argv))
            self.assertEqual({'path': '/inert/donor.json', 'sha256': PIN}, planner.call_args.kwargs['successful_donor'])
            self.assertEqual({'successful_donor', 'successful_donor_guard_repair'} if optin else {'successful_donor'},
                             set(planner.call_args.kwargs))
            if optin: self.assertIs(True, planner.call_args.kwargs['successful_donor_guard_repair'])

    def test_cli_guard_optin_rejects_missing_donor_partial_lane_and_unpaired_pin(self):
        for extra in ([], ['--completed-work', '/inert/partial.json', '--completed-work-sha256', PIN],
                      ['--successful-donor', '/inert/donor.json']):
            with self.subTest(extra=extra), mock.patch.object(maintenance, 'make_plan') as planner, \
                 mock.patch('sys.stderr', new_callable=io.StringIO):
                with self.assertRaises(SystemExit): maintenance.main(self.cli() + extra + ['--successful-donor-guard-repair'])
            planner.assert_not_called()

    def test_api_guard_optin_requires_explicit_donor_boolean_and_editor_before_inspection(self):
        for kwargs, profile in (({'successful_donor_guard_repair': True}, 'editor'),
                                ({'successful_donor_guard_repair': 1, 'successful_donor': {}}, 'editor'),
                                ({'successful_donor_guard_repair': True, 'successful_donor': {}}, 'physical'),
                                ({'successful_donor_guard_repair': True, 'successful_donor': {}, 'completed_work': {}}, 'editor')):
            with self.subTest(kwargs=kwargs, profile=profile), mock.patch.object(maintenance, 'inspect_inputs') as inspect:
                with self.assertRaises(ValueError):
                    maintenance.make_plan({'document_profile': profile}, Path('/inert/output'), **kwargs)
            inspect.assert_not_called()

    def test_plan_creation_and_readback_keep_schema_and_infer_exact_lane(self):
        # All input walks/admission are mocked. Only tiny prospective JSON is
        # written inside this fixture's TemporaryDirectory; no SDK/program runs.
        with tempfile.TemporaryDirectory(prefix='inert-guard-repair-plan-') as temporary:
            root = Path(temporary).resolve()
            selected = {'document_profile': 'editor'}
            inspected = SimpleNamespace(selection=selected, proof={'inert': True}, projection={}, roots={}, inventories={})
            for optin in (False, True):
                admitted = {'reference': {'path': '/inert/donor.json', 'sha256': PIN}, 'objects': []}
                output = root / ('guard-plan' if optin else 'old-plan')
                with mock.patch.object(maintenance, 'inspect_inputs', return_value=inspected), \
                     mock.patch.object(maintenance, '_completed_work', return_value=admitted) as admission, \
                     mock.patch.object(maintenance, '_completed_input_directories', return_value=()), \
                     mock.patch.object(maintenance, 'ref_path'), mock.patch.object(maintenance, 'digest', return_value=PIN):
                    result = maintenance.make_plan(selected, output, successful_donor=admitted['reference'],
                        successful_donor_guard_repair=optin)
                    self.assertEqual({'_successful': True, '_guard_repair': optin}, admission.call_args.kwargs)
                    plan, _ = maintenance.verify_plan(Path(result['plan']),
                        hashlib.sha256(Path(result['plan']).read_bytes()).hexdigest())
                    self.assertEqual({'_successful': True, '_guard_repair': optin}, admission.call_args.kwargs)
                self.assertEqual(maintenance.GUARD_REPAIR_PLAN_KIND if optin else maintenance.SUCCESSFUL_PLAN_KIND, plan['kind'])
                self.assertEqual({'schema_version', 'kind', 'scope', 'selection', 'profile_sha256', 'producer_inputs',
                                  'reuse', 'projection', 'production_eligible', 'successful_donor'}, set(plan))
                self.assertIn(maintenance.SUCCESSFUL_HELPER, plan['producer_inputs'])
                self.assertIs(False, plan['production_eligible'])

    def test_plan_reader_rejects_crosslane_restamp_and_changed_helpers(self):
        admitted = {'reference': {'path': '/inert/new-descriptor.json', 'sha256': PIN}, 'objects': []}
        selected = {'document_profile': 'editor'}
        inspected = SimpleNamespace(proof={}, projection={})
        plan = {'schema_version': 1, 'kind': maintenance.GUARD_REPAIR_PLAN_KIND, 'scope': maintenance.SCOPE,
            'selection': selected, 'profile_sha256': PIN, 'producer_inputs': {name: PIN for name in
                maintenance.required_helpers('editor') + (maintenance.SUCCESSFUL_HELPER,)}, 'reuse': {},
            'projection': {}, 'production_eligible': False, 'successful_donor': admitted}
        def admit(reference, inspection, *, _successful=False, _guard_repair=False):
            if not _successful or not _guard_repair: raise ValueError('explicit descriptor lane differs')
            return admitted
        with mock.patch.object(maintenance, 'checked_document', side_effect=lambda *args: plan), \
             mock.patch.object(maintenance, 'digest', return_value=PIN), \
             mock.patch.object(maintenance, 'inspect_inputs', return_value=inspected), \
             mock.patch.object(maintenance, '_completed_work', side_effect=admit):
            maintenance.verify_plan(Path('/inert/plan.json'), PIN)
            plan['kind'] = maintenance.SUCCESSFUL_PLAN_KIND
            with self.assertRaisesRegex(ValueError, 'lane differs'): maintenance.verify_plan(Path('/inert/plan.json'), PIN)
            plan['kind'] = maintenance.GUARD_REPAIR_PLAN_KIND
            plan['producer_inputs'].pop(maintenance.SUCCESSFUL_HELPER)
            with self.assertRaisesRegex(ValueError, 'producer/profile'): maintenance.verify_plan(Path('/inert/plan.json'), PIN)

    def test_graph_exact51_partition_threefresh_fiveimports_no_repack_one_link(self):
        import appended_engine_successful_donor as donor
        fresh = ('NativeDocumentV2Publisher.cpp', 'BibEngineDocumentWasmShim.cpp', 'ProviderGuard.cpp')
        direct = list(fresh) + ['Direct%02d.cpp' % i for i in range(32)]
        engine = ['Engine%02d.cpp' % i for i in range(16)]
        selected = direct + engine
        names = list(donor.ARCHIVE_COUNTS)
        with tempfile.TemporaryDirectory(prefix='inert-guard-repair-graph-') as temporary:
            root = Path(temporary).resolve(); (root / 'cmake').mkdir()
            metadata = {name: reference(name) for name in ('generator', 'template', 'prelink_plan',
                *maintenance.metadata_interface_paths('editor'))}
            proof = {'host_tools': {'python': {'path': '/inert/python'}},
                'sdk_tools': {name: {'path': name} for name in ('emxx', 'emranlib')}, 'metadata': metadata,
                'objects': [{'id': name, 'arguments': [], 'source': reference(name), 'dependencies': [], 'unified_members': []}
                            for name in selected], 'replacements': [],
                'archives': [{'name': name, 'members': []} for name in names],
                'link': {'dependencies': [], 'archives': names, 'flags': [], 'data': [],
                         'pre_js': reference('pre.js'), 'host_library': reference('host.js')}}
            imported = [name for name in selected if name not in fresh]
            work = {'objects': [{'id': name, 'object': {'path': '/inert/' + name + '.o'},
                                'depfile': {'path': '/inert/' + name + '.o.d'}} for name in imported],
                    'archives': [{'name': name, 'archive': {'path': '/inert/lib' + name + '.a'},
                                  'report': {'path': '/inert/archive-' + name + '.json'}} for name in names]}
            plan = {'kind': maintenance.GUARD_REPAIR_PLAN_KIND, 'successful_donor': work}
            inspected = SimpleNamespace(proof=proof, roots={'sources': root / 'sources', 'sdk': root / 'sdk'},
                inventories={}, selection={'document_profile': 'editor'}, profile={'direct_objects': direct})
            with mock.patch.object(maintenance, '_tool', return_value=Path('/inert/python')), \
                 mock.patch.object(maintenance, 'ref_path', side_effect=lambda ref, roots, inv: root / ref['path']), \
                 mock.patch.object(maintenance, '_arguments', return_value=[]), \
                 mock.patch.object(maintenance, '_header_identity', return_value=None):
                _, fragment, commands = maintenance._graph(inspected, plan, root / 'plan.json', PIN, root)
            self.assertEqual(list(fresh), list(commands['objects']))
            self.assertEqual(imported, list(commands['imports']))
            self.assertEqual((51, 48, 3, 5), (len(selected), len(commands['imports']), len(commands['objects']), len(commands['archive_imports'])))
            self.assertTrue(all(cmd[-1] == name and cmd[-3] == 'import' for name, cmd in commands['imports'].items()))
            self.assertTrue(all(cmd[-1] == name and cmd[-3] == 'import-archive' for name, cmd in commands['archive_imports'].items()))
            self.assertEqual(1, sum(token.endswith('foundation-retained-engine.mjs') for token in commands['link']))
            self.assertEqual(5, len([token for token in commands['link'] if '/archives/lib' in token]))
            graph = fragment.read_text()
            self.assertIn(maintenance.SUCCESSFUL_HELPER, graph)
            self.assertTrue(all('repack' not in cmd for cmd in commands['archive_imports'].values()))

    def test_internal_guard_plan_routes_imports_but_refuses_repack_before_tool(self):
        output = Path('/inert/fresh-output')
        plan = {'kind': maintenance.GUARD_REPAIR_PLAN_KIND, 'production_eligible': False, 'reuse': {},
                'selection': {'sources': '/inert/sources', 'sdk': '/inert/sdk', 'reuse_root': '/inert/reuse'}}
        owner = {'schema_version': 1, 'plan_sha256': PIN, 'output': str(output), 'producer_sha256': PIN}
        args = SimpleNamespace(plan=Path('/inert/plans/plan.json'), plan_sha256=PIN, build_root=output,
                               action='import', object='Imported.cpp', archive='WebCore')
        with mock.patch.object(maintenance, 'checked_document', side_effect=lambda p, *pins: plan if p == args.plan else owner), \
             mock.patch.object(maintenance, 'ordinary', side_effect=lambda p, *a, **kw: Path(p)), \
             mock.patch.object(maintenance, 'digest', return_value=PIN), \
             mock.patch.object(maintenance, '_copy_completed_object', return_value='object') as obj, \
             mock.patch.object(maintenance, '_copy_successful_archive', return_value='archive') as archive, \
             mock.patch.object(maintenance.os, 'execv') as execute:
            self.assertEqual('object', maintenance._step(args)); obj.assert_called_once_with(plan, 'Imported.cpp', output)
            args.action = 'import-archive'
            self.assertEqual('archive', maintenance._step(args)); archive.assert_called_once_with(plan, 'WebCore', output)
            for action in ('archive', 'repack'):
                args.action = action
                with self.subTest(action=action), self.assertRaisesRegex(ValueError, 'zero repacks'): maintenance._step(args)
            execute.assert_not_called()




class CompositionRepairEntryPoints(unittest.TestCase):
    cli = GuardRepairEntryPoints.cli

    def test_explicit_composition_flag_and_preinspection_rejections(self):
        args=self.cli()+['--successful-donor','/inert/donor.json','--successful-donor-sha256',PIN,'--successful-donor-composition-repair']
        with mock.patch.object(maintenance,'make_plan',return_value={}) as planner,mock.patch('sys.stdout',new_callable=io.StringIO):
            self.assertEqual(maintenance.main(args),0)
        self.assertEqual(planner.call_args.kwargs,dict(successful_donor={'path':'/inert/donor.json','sha256':PIN},successful_donor_composition_repair=True))
        for extra in (['--successful-donor-composition-repair'],
                      ['--successful-donor-composition-repair','--completed-work','/inert/failed','--completed-work-sha256',PIN],
                      ['--successful-donor-composition-repair','--successful-donor','/inert/donor'],
                      ['--successful-donor-composition-repair','--successful-donor','/inert/donor','--successful-donor-sha256',PIN,'--successful-donor-guard-repair']):
            with mock.patch.object(maintenance,'make_plan') as planner,mock.patch('sys.stderr',new_callable=io.StringIO):
                with self.assertRaises(SystemExit):maintenance.main(self.cli()+extra)
            planner.assert_not_called()
        for value in (1,False,True):
            kwargs=dict(successful_donor_composition_repair=value)
            if value is False:kwargs.update(successful_donor_composition_repair=True,successful_donor_guard_repair=True,successful_donor={})
            with mock.patch.object(maintenance,'inspect_inputs') as inspect:
                with self.assertRaises(ValueError):maintenance.make_plan({'document_profile':'editor'},Path('/inert/output'),**kwargs)
            inspect.assert_not_called()
        with mock.patch.object(maintenance,'inspect_inputs') as inspect:
            with self.assertRaises(ValueError):maintenance.make_plan({'document_profile':'physical'},Path('/inert/output'),successful_donor={},successful_donor_composition_repair=True)
        inspect.assert_not_called()

    def test_new_plan_creation_readback_schema_and_crosslane(self):
        selected={'document_profile':'editor'};admitted={'reference':{'path':'/inert/composition.json','sha256':PIN},'objects':[]}
        inspected=SimpleNamespace(selection=selected,proof={},projection={},roots={},inventories={})
        with tempfile.TemporaryDirectory(prefix='inert-composition-plan-') as temporary:
            with mock.patch.object(maintenance,'inspect_inputs',return_value=inspected),mock.patch.object(maintenance,'_completed_input_directories',return_value=()),mock.patch.object(maintenance,'ref_path'),mock.patch.object(maintenance,'digest',return_value=PIN),mock.patch.object(maintenance,'_completed_work',return_value=admitted) as admission:
                result=maintenance.make_plan(selected,Path(temporary)/'plan',successful_donor=admitted['reference'],successful_donor_composition_repair=True)
                self.assertEqual(admission.call_args.kwargs,{'_successful':True,'_guard_repair':False,'_composition_repair':True})
                plan,_=maintenance.verify_plan(Path(result['plan']),hashlib.sha256(Path(result['plan']).read_bytes()).hexdigest())
                self.assertEqual(admission.call_args.kwargs,{'_successful':True,'_guard_repair':False,'_composition_repair':True})
            self.assertEqual(plan['kind'],'foundation-document-v2-maintenance-successful-donor-composition-repair-plan-v1')
            self.assertEqual(set(plan),{'schema_version','kind','scope','selection','profile_sha256','producer_inputs','reuse','projection','production_eligible','successful_donor'})
            def admit(ref,inspection,**flags):
                if flags!={'_successful':True,'_guard_repair':False,'_composition_repair':True}:raise ValueError('crossed composition lane')
                return admitted
            with mock.patch.object(maintenance,'checked_document',return_value=plan),mock.patch.object(maintenance,'digest',return_value=PIN),mock.patch.object(maintenance,'inspect_inputs',return_value=inspected),mock.patch.object(maintenance,'_completed_work',side_effect=admit):
                maintenance.verify_plan(Path('/inert/plan'),PIN)
                for kind in (maintenance.SUCCESSFUL_PLAN_KIND,maintenance.GUARD_REPAIR_PLAN_KIND):
                    plan['kind']=kind
                    with self.assertRaises(ValueError):maintenance.verify_plan(Path('/inert/plan'),PIN)


    def test_graph_exact51_partition_fivefresh_fiveimports_no_repack_one_link(self):
            import appended_engine_successful_donor as donor
            fresh = ('NativeDocumentV2Publisher.cpp', 'BibEngineDocumentWasmShim.cpp', 'ProviderGuard.cpp', 'BibNativeEditorBackend.cpp', 'main.cpp')
            direct = list(fresh) + ['Direct%02d.cpp' % i for i in range(30)]
            engine = ['Engine%02d.cpp' % i for i in range(16)]
            selected = direct + engine
            names = list(donor.ARCHIVE_COUNTS)
            with tempfile.TemporaryDirectory(prefix='inert-guard-repair-graph-') as temporary:
                root = Path(temporary).resolve(); (root / 'cmake').mkdir()
                metadata = {name: reference(name) for name in ('generator', 'template', 'prelink_plan',
                    *maintenance.metadata_interface_paths('editor'))}
                proof = {'host_tools': {'python': {'path': '/inert/python'}},
                    'sdk_tools': {name: {'path': name} for name in ('emxx', 'emranlib')}, 'metadata': metadata,
                    'objects': [{'id': name, 'arguments': [], 'source': reference(name), 'dependencies': [], 'unified_members': []}
                                for name in selected], 'replacements': [],
                    'archives': [{'name': name, 'members': []} for name in names],
                    'link': {'dependencies': [], 'archives': names, 'flags': [], 'data': [],
                             'pre_js': reference('pre.js'), 'host_library': reference('host.js')}}
                imported = [name for name in selected if name not in fresh]
                work = {'objects': [{'id': name, 'object': {'path': '/inert/' + name + '.o'},
                                    'depfile': {'path': '/inert/' + name + '.o.d'}} for name in imported],
                        'archives': [{'name': name, 'archive': {'path': '/inert/lib' + name + '.a'},
                                      'report': {'path': '/inert/archive-' + name + '.json'}} for name in names]}
                plan = {'kind': maintenance.COMPOSITION_REPAIR_PLAN_KIND, 'successful_donor': work}
                inspected = SimpleNamespace(proof=proof, roots={'sources': root / 'sources', 'sdk': root / 'sdk'},
                    inventories={}, selection={'document_profile': 'editor'}, profile={'direct_objects': direct})
                with mock.patch.object(maintenance, '_tool', return_value=Path('/inert/python')), \
                     mock.patch.object(maintenance, 'ref_path', side_effect=lambda ref, roots, inv: root / ref['path']), \
                     mock.patch.object(maintenance, '_arguments', return_value=[]), \
                     mock.patch.object(maintenance, '_header_identity', return_value=None):
                    _, fragment, commands = maintenance._graph(inspected, plan, root / 'plan.json', PIN, root)
                self.assertEqual(list(fresh), list(commands['objects']))
                self.assertEqual(imported, list(commands['imports']))
                self.assertEqual((51, 46, 5, 5), (len(selected), len(commands['imports']), len(commands['objects']), len(commands['archive_imports'])))
                self.assertTrue(all(cmd[-1] == name and cmd[-3] == 'import' for name, cmd in commands['imports'].items()))
                self.assertTrue(all(cmd[-1] == name and cmd[-3] == 'import-archive' for name, cmd in commands['archive_imports'].items()))
                self.assertEqual(1, sum(token.endswith('foundation-retained-engine.mjs') for token in commands['link']))
                self.assertEqual(5, len([token for token in commands['link'] if '/archives/lib' in token]))
                graph = fragment.read_text()
                self.assertIn(maintenance.SUCCESSFUL_HELPER, graph)
                self.assertTrue(all('repack' not in cmd for cmd in commands['archive_imports'].values()))

    def test_internal_composition_plan_routes_imports_but_refuses_repack_before_tool(self):
            output = Path('/inert/fresh-output')
            plan = {'kind': maintenance.COMPOSITION_REPAIR_PLAN_KIND, 'production_eligible': False, 'reuse': {},
                    'selection': {'sources': '/inert/sources', 'sdk': '/inert/sdk', 'reuse_root': '/inert/reuse'}}
            owner = {'schema_version': 1, 'plan_sha256': PIN, 'output': str(output), 'producer_sha256': PIN}
            args = SimpleNamespace(plan=Path('/inert/plans/plan.json'), plan_sha256=PIN, build_root=output,
                                   action='import', object='Imported.cpp', archive='WebCore')
            with mock.patch.object(maintenance, 'checked_document', side_effect=lambda p, *pins: plan if p == args.plan else owner), \
                 mock.patch.object(maintenance, 'ordinary', side_effect=lambda p, *a, **kw: Path(p)), \
                 mock.patch.object(maintenance, 'digest', return_value=PIN), \
                 mock.patch.object(maintenance, '_copy_completed_object', return_value='object') as obj, \
                 mock.patch.object(maintenance, '_copy_successful_archive', return_value='archive') as archive, \
                 mock.patch.object(maintenance.os, 'execv') as execute:
                self.assertEqual('object', maintenance._step(args)); obj.assert_called_once_with(plan, 'Imported.cpp', output)
                args.action = 'import-archive'
                self.assertEqual('archive', maintenance._step(args)); archive.assert_called_once_with(plan, 'WebCore', output)
                for action in ('archive', 'repack'):
                    args.action = action
                    with self.subTest(action=action), self.assertRaisesRegex(ValueError, 'zero repacks'): maintenance._step(args)
                execute.assert_not_called()

class CompositionContextTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory(prefix='inert-composition-context-');self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name).resolve();self.roots={k:self.root/k for k in ('sources','sdk','reuse')}
        self.inventories={k:{} for k in self.roots}
        for p in self.roots.values():p.mkdir()
        self.fresh=('NativeDocumentV2Publisher.cpp','BibEngineDocumentWasmShim.cpp','ProviderGuard.cpp','BibNativeEditorBackend.cpp','main.cpp')
        self.headers=('source/wrapper/src/embedder/BibPageClients.h','source/wrapper/src/embedder/BibUndoHistory.h','source/wrapper/src/embedder/BibEngineProviderCompositionUndo.h')
        oldns={};newns={};before=[];after=[]
        def write(root,path,raw):
            target=self.roots[root]/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
            pin=hashlib.sha256(raw).hexdigest();self.inventories[root][path]=pin;return {'root':root,'path':path,'sha256':pin}
        sdk=write('sdk','include/base.h',b'unchanged SDK header')
        oldns['{sdk}/include/base.h']=newns['{sdk}/include/base.h']=sdk['sha256']
        refs={}
        for path in self.headers:
            ref=write('sources',path,('newheader:'+path).encode());refs[path]=ref;newns['{sources}/'+path]=ref['sha256']
            if path!=self.headers[-1]:oldns['{sources}/'+path]=hashlib.sha256(('oldheader:'+path).encode()).hexdigest()
        selected=list(self.fresh)+['Imported%02d.cpp'%i for i in range(46)]
        for name in selected:
            path='units/'+name;oldraw=('oldbody:'+name).encode();newraw=('newbody:'+name).encode() if name in self.fresh and name!='BibEngineDocumentWasmShim.cpp' else oldraw
            current=write('sources',path,newraw);prior=dict(current,sha256=hashlib.sha256(oldraw).hexdigest());oldns['{sources}/'+path]=prior['sha256'];newns['{sources}/'+path]=current['sha256']
            deps=[prior,dict(sdk)];newdeps=[current,dict(sdk)]
            if name=='main.cpp':
                for header in self.headers[:-1]:deps.append(dict(refs[header],sha256=oldns['{sources}/'+header]));newdeps.append(dict(refs[header]))
            common=dict(id=name,arguments=['-I{sources}/units','-fno-rtti'],exceptions=True,unified_members=[])
            before.append(dict(common,source=prior,dependencies=deps));after.append(dict(common,source=current,dependencies=newdeps))
        self.old={'reuse':{'objects':before}};self.inspected=SimpleNamespace(proof={'objects':after},roots=self.roots,inventories=self.inventories)
        shared=dict(directories=['{sources}/units','{sources}/source/wrapper/src/embedder','{sdk}/include'],physical_headers_sha256=hashlib.sha256(b'fixed physical headers').hexdigest(),vfs={'version':0,'roots':[]})
        self.previous=dict(shared,namespace=oldns);self.current=dict(shared,namespace=newns)

    def admit(self):
        maintenance._composition_context_matches(self.previous,self.current)
        maintenance._successful_context_delta(self.inspected,self.old,self.previous,self.current,composition_repair=True)

    def test_exact_body_header_namespace_and_all51_owner_join_positive(self):
        self.admit()
        self.assertEqual(len(self.inspected.proof['objects']),51)
        self.assertEqual(set(self.current['namespace'])-set(self.previous['namespace']),{'{sources}/'+self.headers[-1]})
        with self.assertRaises(ValueError):maintenance._completed_context_matches(self.previous,self.current)
        with self.assertRaises(ValueError):maintenance._successful_context_delta(self.inspected,self.old,self.previous,self.current)
        with self.assertRaises(ValueError):maintenance._successful_context_delta(self.inspected,self.old,self.previous,self.current,guard_repair=True)

    def test_namespace_add_remove_sdk_physical_vfs_and_undeclared_body_drift_reject(self):
        original=copy.deepcopy(self.current)
        for change in ('extra','remove','sdk','physical','vfs','directory','imported-body','unchanged-header'):
            self.current=copy.deepcopy(original)
            if change=='extra':self.current['namespace']['{sources}/new-extra.h']='a'*64
            elif change=='remove':self.current['namespace'].pop('{sources}/units/Imported00.cpp')
            elif change=='sdk':self.current['namespace']['{sdk}/include/base.h']='a'*64
            elif change=='physical':self.current['physical_headers_sha256']='a'*64
            elif change=='vfs':self.current['vfs']={'version':1}
            elif change=='directory':self.current['directories']=[]
            elif change=='imported-body':self.current['namespace']['{sources}/units/Imported00.cpp']='a'*64
            else:self.current['namespace']['{sources}/'+self.headers[0]]=self.previous['namespace']['{sources}/'+self.headers[0]]
            with self.subTest(change=change),self.assertRaises(ValueError):self.admit()

    def test_abridged_recipe_dependencies_are_not_a_header_census(self):
        for table in (self.old['reuse']['objects'], self.inspected.proof['objects']):
            for obj in table:
                obj['dependencies'] = [obj['dependencies'][1]]
        self.admit()
        self.assertTrue(all(len(obj['dependencies']) == 1 for obj in self.old['reuse']['objects']))

    def test_invented_private_or_other_header_proof_references_reject(self):
        original = copy.deepcopy(self.inspected.proof['objects'])
        for owner, path in ((name, self.headers[-1]) for name in self.fresh):
            self.inspected.proof['objects'] = copy.deepcopy(original)
            obj = next(obj for obj in self.inspected.proof['objects'] if obj['id'] == owner)
            obj['dependencies'].append(reference(path, pin=self.current['namespace']['{sources}/' + path]))
            with self.subTest(owner=owner), self.assertRaises(ValueError):
                self.admit()
        self.inspected.proof['objects'] = copy.deepcopy(original)
        obj = next(obj for obj in self.inspected.proof['objects'] if obj['id'] == 'BibNativeEditorBackend.cpp')
        obj['dependencies'].append(reference(self.headers[0], pin=self.current['namespace']['{sources}/' + self.headers[0]]))
        with self.assertRaises(ValueError):
            self.admit()

    def test_fresh_options_unified_source_coordinates_shim_and_dependency_order_remain_strict(self):
        original=copy.deepcopy(self.inspected.proof['objects'])
        for change in ('flags','unified','coordinate','shim','order','extra-sdk','missing-body-delta'):
            self.inspected.proof['objects']=copy.deepcopy(original);objects={x['id']:x for x in self.inspected.proof['objects']};backend=objects['BibNativeEditorBackend.cpp']
            if change=='flags':backend['arguments'].append('-DUNDECLARED=1')
            elif change=='unified':backend['unified_members']=[backend['source']]
            elif change=='coordinate':backend['source']=dict(backend['source'],path='units/elsewhere.cpp')
            elif change=='shim':objects['BibEngineDocumentWasmShim.cpp']['source']=dict(objects['BibEngineDocumentWasmShim.cpp']['source'],sha256='a'*64)
            elif change=='order':backend['dependencies'][0:2]=backend['dependencies'][0:2][::-1]
            elif change=='extra-sdk':backend['dependencies'].append(dict(backend['dependencies'][1]))
            else:backend['source']=copy.deepcopy(self.old['reuse']['objects'][3]['source'])
            with self.subTest(change=change),self.assertRaises(ValueError):self.admit()

    def test_current_header_hash_must_join_namespace_and_actual_inventory(self):
        main=next(x for x in self.inspected.proof['objects'] if x['id']=='main.cpp')
        header=main['dependencies'][-1];before=header['sha256'];header['sha256']='a'*64
        with self.assertRaises(ValueError):self.admit()
        header['sha256']=before
        self.inventories['sources'][self.headers[-1]]='a'*64
        with self.assertRaisesRegex(ValueError,'Reference not bound'):self.admit()



class CompositionPriorHeaderTests(unittest.TestCase):
    """Real recipe lists are abridged; only parsed original depfiles own headers."""
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='inert-prior-header-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.bindings = {key: self.root / key for key in ('sources', 'sdk', 'reuse', 'build')}
        for path in self.bindings.values():
            path.mkdir()
        self.fresh = maintenance._successful_module().COMPOSITION_REPAIR_COMPILED_IDS
        self.headers = maintenance.COMPOSITION_REPAIR_HEADERS
        self.records, self.commands, self.rows = {}, {'objects': {}}, []
        self.sidecar = {'dependencies': {}, 'header_context': {'namespace': {}}}
        self.freeze = {'files': {}}
        self.old = {'reuse': {'objects': []}}
        self.header_keys = []
        for header in self.headers[:-1]:
            path = self.bindings['sources'] / header
            self.write(path, ('old:' + header).encode())
            fact = self.fact(path)
            self.header_keys.append(str(path))
            self.sidecar['dependencies'][str(path)] = {'input': reference(header, pin=fact['sha256']),
                'fact': fact, 'origin': 'retained'}
            self.sidecar['header_context']['namespace']['{sources}/' + header] = fact['sha256']
            self.freeze['files'][str(path)] = copy.deepcopy(fact)
        for name in (*self.fresh, *('Imported%02d.cpp' % i for i in range(46))):
            relative = 'units/' + name
            source = self.bindings['sources'] / relative
            self.old['reuse']['objects'].append({'id': name, 'source': reference(relative),
                'dependencies': [reference('build/cmakeconfig.h', root='reuse')]})
            if name in self.fresh:
                self.commands['objects'][name] = ['-c', str(source)]
                keys = [str(source)] + (self.header_keys if name == 'main.cpp' else [])
                self.depfile(name, keys)
            else:
                self.rows.append({'id': name, 'object': {'bytes': 1}, 'depfile': {'bytes': 1},
                    'command_script': None, 'dependency_keys': [str(source)]})

    def write(self, path, raw):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)

    def fact(self, path):
        state = path.stat()
        return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'bytes': state.st_size, 'mode': state.st_mode & 0o777, 'identity': maintenance._identity7(state)}

    def depfile(self, name, keys, *, target=None):
        target = target or str(self.bindings['build'] / ('objects/' + name + '.o'))
        path = self.bindings['build'] / ('objects/' + name + '.o.d')
        self.write(path, (target + ': ' + ' '.join(keys) + '\n').encode())
        self.records['objects/' + name + '.o.d'] = self.fact(path)

    def admit(self):
        with mock.patch.object(maintenance._successful_module(), '_metadata', return_value=({}, self.records)) as metadata:
            maintenance._composition_prior_headers({}, self.bindings, self.old, self.sidecar,
                self.freeze, self.rows, self.commands)
            metadata.assert_called_once_with({}, self.bindings, self.old, maintenance, composition_repair=True)

    def test_51_complete_owner_union_from_exact_five_original_depfiles(self):
        with mock.patch.object(maintenance, '_completed_fact', wraps=maintenance._completed_fact) as read:
            self.admit()
        self.assertEqual(7, read.call_count)  # Five indexed depfiles and two exact old headers.
        self.assertTrue(all(len(obj['dependencies']) == 1 for obj in self.old['reuse']['objects']))

    def test_main_only_old_headers_and_private_absence_across_all51(self):
        records = copy.deepcopy(self.records)
        rows = copy.deepcopy(self.rows)
        for change in ('backend-old', 'main-missing', 'imported-old', 'private-before'):
            self.records = copy.deepcopy(records)
            self.rows = copy.deepcopy(rows)
            self.depfile('main.cpp', [str(self.bindings['sources'] / 'units/main.cpp'), *self.header_keys])
            self.depfile('BibNativeEditorBackend.cpp', [str(self.bindings['sources'] / 'units/BibNativeEditorBackend.cpp')])
            if change == 'backend-old':
                self.depfile('BibNativeEditorBackend.cpp', [str(self.bindings['sources'] / 'units/BibNativeEditorBackend.cpp'), self.header_keys[0]])
            elif change == 'main-missing':
                self.depfile('main.cpp', [str(self.bindings['sources'] / 'units/main.cpp'), self.header_keys[0]])
            elif change == 'imported-old':
                self.rows[0]['dependency_keys'].append(self.header_keys[0])
            else:
                self.rows[0]['dependency_keys'].append(str(self.bindings['sources'] / self.headers[-1]))
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.admit()

    def test_depfile_source_target_bytes_and_total_read_budget_reject(self):
        records = copy.deepcopy(self.records)
        name = self.fresh[0]
        source = str(self.bindings['sources'] / ('units/' + name))
        for change in ('target', 'source', 'hash', 'budget'):
            self.records = copy.deepcopy(records)
            self.depfile(name, [source])
            if change == 'target':
                self.depfile(name, [source], target='/elsewhere/other.o')
            elif change == 'source':
                self.depfile(name, ['/elsewhere/other.cpp'])
            elif change == 'hash':
                self.records['objects/' + name + '.o.d']['sha256'] = PIN
            else:
                self.records['objects/' + name + '.o.d']['bytes'] = 256 * 1024 * 1024
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.admit()

    def test_header_sidecar_namespace_freeze_and_physical_facts_reject(self):
        original = copy.deepcopy(self.sidecar)
        for change in ('hash', 'namespace', 'path', 'freeze', 'origin', 'missing'):
            self.sidecar = copy.deepcopy(original)
            key = self.header_keys[0]
            item = self.sidecar['dependencies'][key]
            if change == 'hash': item['input']['sha256'] = PIN
            elif change == 'namespace': self.sidecar['header_context']['namespace']['{sources}/' + self.headers[0]] = PIN
            elif change == 'path': item['fact']['path'] = '/elsewhere/BibPageClients.h'
            elif change == 'freeze': item['fact']['identity'][1] += 1
            elif change == 'origin': item['origin'] = 'private-cache'
            else: del self.sidecar['dependencies'][key]
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.admit()

    def test_relative_original_depfile_paths_use_exact_original_cwd(self):
        import os
        cwd = self.bindings['build'] / 'cmake/build'
        for name in self.fresh:
            keys = [str(self.bindings['sources'] / ('units/' + name))]
            if name == 'main.cpp': keys.extend(self.header_keys)
            self.depfile(name, [os.path.relpath(key, cwd) for key in keys])
        self.admit()


class CompositionContextConstructionTests(unittest.TestCase):
    """Fresh owners must retain their original dependency search coordinates."""
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='inert-composition-context-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.bindings = {key: self.root / key for key in ('sources', 'sdk', 'reuse', 'build')}
        self.inventories = {key: {} for key in ('sources', 'sdk', 'reuse')}
        for path in self.bindings.values(): path.mkdir()
        self.sidecar, self.freeze, self.dependencies = {'dependencies': {}}, {'files': {}}, {}
        self.objects = [{'id': name, 'arguments': []} for name in
            (*maintenance._successful_module().COMPOSITION_REPAIR_COMPILED_IDS,
             *('Imported%02d.cpp' % i for i in range(46))) ]
        for obj in self.objects:
            self.dependencies[obj['id']] = {self.add('sources', 'units/' + obj['id'])}
        self.leaves = ('build/skia/effects', 'build/wtf/unix')
        for leaf in self.leaves:
            self.dependencies['main.cpp'].add(self.add('reuse', leaf + '/MainOnly.h'))
        for relative in ('upstream/lib/clang/24/include', 'cache/sysroot/include'):
            (self.bindings['sdk'] / relative).mkdir(parents=True)
        self.inspection = SimpleNamespace(roots={key: self.bindings[key] for key in self.inventories},
            inventories=self.inventories, proof={'objects': self.objects,
                'private_cache': {'root': 'cache', 'files': []}})
        self.view = {'original_files': {}, 'overlay': {'version': 0, 'case-sensitive': True,
            'use-external-names': False, 'overlay-relative': False, 'fallthrough': True, 'roots': []}}

    def add(self, root, relative):
        path = self.bindings[root] / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(relative.encode())
        pin = hashlib.sha256(path.read_bytes()).hexdigest()
        state = path.stat()
        fact = {'path': str(path), 'sha256': pin, 'bytes': state.st_size,
            'mode': state.st_mode & 0o777, 'identity': maintenance._identity7(state)}
        self.inventories[root][relative] = pin
        self.freeze['files'][str(path)] = copy.deepcopy(fact)
        self.sidecar['dependencies'][str(path)] = {'fact': fact,
            'input': reference(relative, root=root, pin=pin), 'origin': 'retained'}
        return str(path)

    def construct(self):
        with mock.patch.object(maintenance, '_header_identity', return_value=self.view), \
                mock.patch.object(maintenance, '_completed_fact', side_effect=AssertionError('extra body read')):
            return maintenance._composition_header_context(self.inspection, self.bindings,
                self.sidecar, self.freeze, self.dependencies, getattr(self, 'generated', None))

    def test_fresh_main_only_leaf_directories_survive_import46_pruning(self):
        result = self.construct()
        expected = {'{sources}/units', '{sdk}/upstream/lib/clang/24/include',
            '{sdk}/cache/sysroot/include', *('{reuse}/' + leaf for leaf in self.leaves)}
        self.assertEqual(sorted(expected), result['directories'])
        for leaf in self.leaves:
            self.assertIn('{reuse}/' + leaf + '/MainOnly.h', result['namespace'])
        imported = [obj for obj in self.objects if obj['id'].startswith('Imported')]
        refs = [self.sidecar['dependencies'][key]['input'] for obj in imported
            for key in self.dependencies[obj['id']]]
        with mock.patch.object(maintenance, '_header_identity', return_value=self.view):
            pruned = maintenance._completed_header_context(self.inspection, refs, imported)
        self.assertEqual(expected - {'{reuse}/' + leaf for leaf in self.leaves}, set(pruned['directories']))
        self.assertEqual(46, len(imported))

    def test_original_coordinates_allow_current_fresh_source_hash(self):
        self.inventories['sources']['units/main.cpp'] = OTHER
        self.assertEqual(OTHER, self.construct()['namespace']['{sources}/units/main.cpp'])

    def test_full_owner_original_fact_relocation_and_current_namespace_required(self):
        key = next(iter(self.dependencies['main.cpp']))
        original = copy.deepcopy((self.dependencies, self.sidecar, self.freeze, self.inventories))
        for change in ('owner', 'missing', 'origin', 'fact-path', 'pin', 'freeze', 'relocation', 'namespace'):
            self.dependencies, self.sidecar, self.freeze, inventories = copy.deepcopy(original)
            self.inventories.clear(); self.inventories.update(inventories)
            item = self.sidecar['dependencies'][key]
            if change == 'owner': del self.dependencies['main.cpp']
            elif change == 'missing': del self.sidecar['dependencies'][key]
            elif change == 'origin': item['origin'] = 'generated'
            elif change == 'fact-path': item['fact']['path'] = '/other/path'
            elif change == 'pin': item['input']['sha256'] = OTHER
            elif change == 'freeze': self.freeze['files'][key]['identity'][1] += 1
            elif change == 'relocation': item['input']['root'] = 'sdk'
            else: del self.inventories[item['input']['root']][item['input']['path']]
            with self.subTest(change=change), self.assertRaises(ValueError): self.construct()

    def test_private_cache_metadata_requires_the_exact_frozen_sdk_seed(self):
        relative = 'cache/sysroot/include/Private.h'
        sdk_key = self.add('sdk', relative)
        item = copy.deepcopy(self.sidecar['dependencies'].pop(sdk_key))
        original_key = str(self.bindings['build'] / 'private/cache/sysroot/include/Private.h')
        item['fact']['path'] = original_key; item['origin'] = 'private-cache'
        self.sidecar['dependencies'][original_key] = item
        self.dependencies['main.cpp'].add(original_key)
        seed = self.inspection.proof['private_cache']['files']
        seed.append(relative)
        self.assertIn('{sdk}/' + relative, self.construct()['namespace'])
        original = copy.deepcopy((self.sidecar, self.freeze, seed))
        for change in ('missing-seed', 'seed-hash', 'relocation', 'root'):
            self.sidecar, self.freeze, files = copy.deepcopy(original)
            seed.clear(); seed.extend(files)
            if change == 'missing-seed': seed.remove(relative)
            elif change == 'seed-hash': self.freeze['files'][sdk_key]['sha256'] = OTHER
            elif change == 'relocation': self.sidecar['dependencies'][original_key]['input']['path'] = 'cache/other.h'
            else: self.sidecar['dependencies'][original_key]['input']['root'] = 'reuse'
            with self.subTest(change=change), self.assertRaises(ValueError): self.construct()

    def add_fresh_only_partition(self):
        publisher, shim = 'NativeDocumentV2Publisher.cpp', 'BibEngineDocumentWasmShim.cpp'
        rows = [('sources', 'source/document-provider/native/NativeDocumentV2Publisher.cpp', publisher),
            ('sources', 'source/document-provider/runtime/BibEngineDocumentWasmShim.cpp', shim),
            ('sources', 'source/document-provider/runtime/BibEngineDocumentWasmShim.h', shim)]
        rows += [('reuse', 'build/webcore/WebCore/PrivateHeaders/WebCore/' + name, publisher)
                 for name in ('HTMLBodyElement.h', 'HTMLButtonElement.h', 'TextEvent.h')]
        self.sidecar['header_context'] = dict(directories=[], namespace={})
        for root, relative, owner in rows:
            key = self.add(root, relative)
            item = self.sidecar['dependencies'].pop(key)
            self.sidecar['header_context']['namespace']['{' + root + '}/' + relative] = item['fact']['sha256']
            self.dependencies[owner].add(key)
        path = self.bindings['build'] / 'document-generated/BibCopiedDocumentMetadata.generated.h'
        path.parent.mkdir(parents=True); path.write_bytes(b'original generated metadata')
        state = path.stat()
        self.generated = dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            bytes=state.st_size, mode=state.st_mode & 0o777, identity=maintenance._identity7(state))
        self.dependencies[shim].add(str(path))
        return rows

    def test_seven_fresh_only_inputs_join_frozen_namespace_without_body_reads(self):
        rows = self.add_fresh_only_partition()
        main = 'source/document-provider/native/NativeDocumentV2Publisher.cpp'
        self.inventories['sources'][main] = OTHER
        result = self.construct()
        self.assertEqual(OTHER, result['namespace']['{sources}/' + main])
        for root, relative, _ in rows:
            self.assertIn('{' + root + '}/' + relative, result['namespace'])
        self.assertFalse(any('BibCopiedDocumentMetadata.generated.h' in name for name in result['namespace']))
        self.assertFalse(any('{generated}' in name for name in result['directories']))

    def test_missing_partition_coordinate_owner_and_frozen_authorities_remain_strict(self):
        self.add_fresh_only_partition()
        original = copy.deepcopy((self.sidecar, self.freeze, self.dependencies, self.generated, self.inventories))
        key = str(self.bindings['sources'] / 'source/document-provider/native/NativeDocumentV2Publisher.cpp')
        generated_key = self.generated['path']
        for change in ('unknown', 'partial', 'sidecar-injection', 'imported-owner', 'wrong-owner',
                       'missing-freeze', 'wrong-fact-path', 'namespace-pin', 'current-namespace',
                       'generated-path', 'generated-pin', 'generated-owner', 'generated-frozen',
                       'generated-search', 'generated-namespace'):
            self.sidecar, self.freeze, self.dependencies, self.generated, inventory = copy.deepcopy(original)
            self.inventories.clear(); self.inventories.update(inventory)
            if change == 'unknown': self.dependencies['main.cpp'].add(str(self.bindings['sources'] / 'unknown.h'))
            elif change == 'partial': self.dependencies['BibEngineDocumentWasmShim.cpp'].remove(generated_key)
            elif change == 'sidecar-injection': self.sidecar['dependencies'][key] = {}
            elif change == 'imported-owner': self.dependencies['Imported00.cpp'].add(key)
            elif change == 'wrong-owner': self.dependencies['main.cpp'].add(key)
            elif change == 'missing-freeze': del self.freeze['files'][key]
            elif change == 'wrong-fact-path': self.freeze['files'][key]['path'] = '/other/source.cpp'
            elif change == 'namespace-pin': self.sidecar['header_context']['namespace']['{sources}/source/document-provider/native/NativeDocumentV2Publisher.cpp'] = OTHER
            elif change == 'current-namespace': del self.inventories['sources']['source/document-provider/native/NativeDocumentV2Publisher.cpp']
            elif change == 'generated-path': self.generated['path'] = '/other/generated.h'
            elif change == 'generated-pin': self.generated['sha256'] = 'not-a-pin'
            elif change == 'generated-owner': self.dependencies['main.cpp'].add(generated_key)
            elif change == 'generated-frozen': self.freeze['files'][generated_key] = copy.deepcopy(self.generated)
            elif change == 'generated-search': self.sidecar['header_context']['directories'].append('{generated}')
            else: self.sidecar['header_context']['namespace']['{generated}/unexpected.h'] = PIN
            with self.subTest(change=change), self.assertRaises(ValueError): self.construct()

class CompositionDependencyOwnersTests(unittest.TestCase):
    def fixture(self):
        units=('NativeDocumentV2Publisher.cpp','BibEngineDocumentWasmShim.cpp','ProviderGuard.cpp','BibNativeEditorBackend.cpp','main.cpp')
        keys=('source/wrapper/src/embedder/BibPageClients.h','source/wrapper/src/embedder/BibUndoHistory.h','source/wrapper/src/embedder/BibEngineProviderCompositionUndo.h')
        aliases={key:{'/bound/source/'+key,'/bound/vfs/'+Path(key).name} for key in keys}
        deps={name:{'/bound/source/'+name} for name in units}
        deps['main.cpp'].update('/bound/source/'+key for key in keys)
        deps['BibNativeEditorBackend.cpp'].add('/bound/vfs/BibEngineProviderCompositionUndo.h')
        return deps,aliases

    def test_exact_alias_owner_sets_pure_positive(self):
        deps,aliases=self.fixture()
        with mock.patch.object(Path,'open',side_effect=AssertionError('ownership validator opened path')):
            self.assertIsNone(maintenance.validate_composition_dependency_owners(deps,aliases))
            maintenance.validate_composition_dependency_owners({k:frozenset(v) for k,v in deps.items()},aliases)

    def test_wrong_owner_missing_keys_and_alias_overlap_reject(self):
        for change in ('extra-owner','missing-backend','extra-mainheader','unit','header','overlap'):
            deps,aliases=self.fixture();private='source/wrapper/src/embedder/BibEngineProviderCompositionUndo.h'
            if change=='extra-owner':deps['ProviderGuard.cpp'].add(next(iter(aliases[private])))
            elif change=='missing-backend':deps['BibNativeEditorBackend.cpp']={'/bound/source/backend.cpp'}
            elif change=='extra-mainheader':deps['BibNativeEditorBackend.cpp'].add('/bound/source/source/wrapper/src/embedder/BibUndoHistory.h')
            elif change=='unit':deps['Other.cpp']={'/bound/source/Other.cpp'}
            elif change=='header':aliases['extra.h']={'/bound/source/extra.h'}
            else:aliases[private].update(aliases['source/wrapper/src/embedder/BibUndoHistory.h'])
            with self.subTest(change=change),self.assertRaises(ValueError):maintenance.validate_composition_dependency_owners(deps,aliases)

    def test_strict_set_types_and_canonical_paths_reject(self):
        for invalid in ('/bound/path',[],(),set(),{'relative/path'},{'/bound/../path'},{'/bound//path'},{'/bound/./path'},{'/bound/path\x00bad'},{True}):
            deps,aliases=self.fixture();deps['ProviderGuard.cpp']=invalid
            with self.subTest(invalid=invalid),self.assertRaises(ValueError):maintenance.validate_composition_dependency_owners(deps,aliases)


if __name__ == '__main__':
    unittest.main()
