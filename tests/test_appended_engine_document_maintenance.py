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


if __name__ == '__main__':
    unittest.main()
