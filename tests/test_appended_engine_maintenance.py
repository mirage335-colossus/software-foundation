"""Small offline producer contracts; fake objects/SDK are never real engines."""
import contextlib
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(ROOT / 'tests'))
import appended_engine_maintenance as maintenance
import appended_engine_manifest as manifest
from dependency_archive import digest, encoded
import test_appended_engine_sdk as integrity_fixture


def write(root, name, raw, mode=0o644):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    for parent in path.parents:
        if parent == root.parent:
            break
        parent.chmod(0o755)
    path.write_bytes(raw)
    path.chmod(mode)
    return path


def header(name, size):
    return (name.ljust(16) + '0'.ljust(12) + '0'.ljust(6) + '0'.ljust(6)
            + '100644'.ljust(8) + str(size).ljust(10) + '`\n').encode('ascii')


def regular(members, *, offsets=None):
    # Index offsets are filled independently from serialized byte positions.
    symbols = [b'symbol' + str(i).encode() + b'\0' for i in range(len(members))]
    index_size = 4 + 4 * len(members) + sum(map(len, symbols))
    start = 8 + 60 + index_size + (index_size & 1)
    observed, content = [], b''
    for name, raw in members:
        observed.append(start + len(content))
        content += header(name + '/', len(raw)) + raw + (b'\n' if len(raw) & 1 else b'')
    index = len(members).to_bytes(4, 'big')
    index += b''.join(value.to_bytes(4, 'big') for value in (observed if offsets is None else offsets))
    index += b''.join(symbols)
    return b'!<arch>\n' + header('/', len(index)) + index + (b'\n' if len(index) & 1 else b'') + content


def thin(members):
    names, offsets = b'', []
    for name, raw in members:
        offsets.append(len(names)); names += name.encode('ascii') + b'/\n'
    return (b'!<thin>\n' + header('//', len(names)) + names + (b'\n' if len(names) & 1 else b'')
            + b''.join(header('/' + str(offset), len(raw)) for offset, (_, raw) in zip(offsets, members)))


class MaintenanceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='foundation-engine-maintenance-')
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name).resolve()

    def test_maintenance_ledger_above_32_mib_parses_without_raising_default_manifest_limit(self):
        prefix = b'{"commands":{"synthetic":{"argv":["compiler","-c","one.cpp"],"cwd":"/fixture"}}}'
        # A ledger-shaped object with JSON whitespace exercises real byte length
        # while keeping the parsed result tiny. Raw+decoded large allocations
        # stay below 100 MiB; there is no 65 MiB parsed-string duplicate.
        raw = bytearray(b' ') * (32 * 1024 * 1024 + 1)
        raw[:len(prefix)] = prefix
        self.assertEqual(manifest.MAX_MANIFEST, 32 * 1024 * 1024)
        self.assertEqual(maintenance.MAX_DOCUMENT, 64 * 1024 * 1024)
        self.assertGreater(len(raw), manifest.MAX_MANIFEST)
        self.assertLessEqual(len(raw), maintenance.MAX_DOCUMENT)
        with self.assertRaisesRegex(ValueError, 'engine manifest exceeds size limit'):
            manifest.json_bytes(raw)
        self.assertEqual(maintenance.document(raw), {'commands': {'synthetic': {
            'argv': ['compiler', '-c', 'one.cpp'], 'cwd': '/fixture'}}})

    def test_maintenance_document_above_64_mib_is_rejected_before_json_parse(self):
        raw = b' ' * (64 * 1024 * 1024 + 1)
        with mock.patch.object(maintenance.json, 'loads', side_effect=AssertionError('oversize input parsed')) as parse:
            with self.assertRaisesRegex(ValueError, 'Maintenance document exceeds 64 MiB'):
                maintenance.document(raw)
        parse.assert_not_called()

    def test_maintenance_document_preserves_duplicate_nonfinite_and_utf8_grammar(self):
        invalid = (b'{"a":1,"a":2}', b'{"a":1,"\\u0061":2}', b'{"nested":{"a":1,"a":2}}',
                   b'{"value":NaN}', b'{"value":Infinity}', b'{"value":-Infinity}', b'{"text":"\xff"}')
        for raw in invalid:
            with self.subTest(raw=raw):
                for parser in (maintenance.document, manifest.json_bytes):
                    with self.assertRaises(ValueError):
                        parser(raw)
        valid = b'{"text":"\xc3\xa9","values":[0,true,false,null]}'
        self.assertEqual(maintenance.document(valid), {'text': '\u00e9', 'values': [0, True, False, None]})
        self.assertEqual(maintenance.document(valid), manifest.json_bytes(valid))

    def fixture(self, *, recipe_triple='wasm32-unknown-emscripten', sdk_triple=None):
        helper = integrity_fixture.EngineIntegrityTests(methodName='runTest')
        helper.base = self.base
        original = helper.make_fixture('retained')
        sources, recipe = original['sources'], original['recipe']
        recipe['target']['triple'] = recipe_triple
        sdk_triple = recipe_triple if sdk_triple is None else sdk_triple
        sdk, reuse = self.base / 'sdk', self.base / 'baseline'
        sdk.mkdir(); reuse.mkdir()
        config = maintenance.profile()
        def retain(name, raw, role='source', mode=0o644):
            write(sources, name, raw, mode)
            recipe['inputs'][name] = {'sha256': hashlib.sha256(raw).hexdigest(), 'role': role, 'mode': mode}
        for name in maintenance.REQUIRED_HELPERS:
            retain(name, (ROOT / name).read_bytes(), 'helper')
        for name in config['python_entrypoints']:
            write(sdk, name, b'# inert fixture Python, never execute\n')
        launcher_markers = {
            'config': ('upstream/emscripten/tools/config.py', b"os.environ['EMSDK_PYTHON'] = sys.executable\n"),
            'shared': ('upstream/emscripten/tools/shared.py', b"FILE_PACKAGER = exe_path_from_root('tools/file_packager')\n"),
            'file_packager': ('upstream/emscripten/tools/file_packager', b'exec "$_EM_PY" -E "$0.py" "$@"\n'),
            'emxx': ('upstream/emscripten/em++', b'exec "$_EM_PY" -B -E "$0.py" "$@"\n')}
        for name, raw in launcher_markers.values():
            write(sdk, name, raw, 0o755 if name.endswith(('em++', 'file_packager')) else 0o644)
        for name in ('emar', 'emranlib'):
            write(sdk, 'upstream/emscripten/' + name, b'#!/bin/sh\nexit 91\n', 0o755)
        write(sdk, 'node/bin/node', b'#!/bin/sh\nexit 92\n', 0o755)
        (sdk / 'upstream/bin').mkdir()
        (sdk / 'upstream/bin').chmod(0o755)
        write(sdk, 'cache/syslib.a', b'inert prepared cache\n')
        sdk_data = {'schema_version': 1, 'recipe_id': '4' * 64,
            'target': {'system': 'Emscripten', 'processor': 'wasm32', 'triple': sdk_triple,
                       'cxx_compiler': 'upstream/emscripten/em++', 'sysroot': 'cache'},
            'files': manifest.tree_inventory(sdk, 'sdk.json')['files']}
        write(sdk, 'sdk.json', encoded(sdk_data))
        sdk_hash = digest(sdk / 'sdk.json')
        recipe['toolchain']['paired_sdk_sha256'] = sdk_hash
        projected = {}
        objects = []
        source_paths = {}
        for index, name in enumerate(config['wrapper_objects'] + config['engine_objects']):
            if name == 'main.cpp':
                path = 'source/wrapper/src/embedder/main.cpp'
            else:
                path = 'source/selected/' + name
            retain(path, ('// inert ' + name + '\n').encode())
            source_paths[name] = path
            projected[path] = {'sha256': recipe['inputs'][path]['sha256']}
        for name in ('source/wrapper/src/embedder/embedder.cmake', 'source/copied-provider/runtime/embedder.cmake'):
            retain(name, b'# retained recovery sibling marker\n', 'config')
            projected[name] = {'sha256': recipe['inputs'][name]['sha256']}
        retain(config['metadata_generator'], b'# inert fixture generator, never run\n', 'helper')
        retain('provenance/prelink.json', b'{"fixture": true}\n', 'config')
        retain('provenance/source-projection.json', encoded({'files': projected}), 'config')
        def ref(root, name):
            where = {'sources': sources, 'sdk': sdk, 'reuse': reuse}[root]
            return {'root': root, 'path': name, 'sha256': digest(where / name)}
        original_command = {'argv': ['/fixture/compiler', '-o', str(reuse / 'objects/original.o'), '-c', 'original.cpp'],
                            'cwd': str(reuse)}
        command_hash = hashlib.sha256(encoded(original_command)).hexdigest()
        command_records = {command_hash: original_command}
        write(reuse, 'commands.json', encoded({'schema_version': 1,
            'kind': 'foundation-engine-original-commands-v1', 'commands': {command_hash: original_command}}))
        write(reuse, 'original-receipt.json', b'{"scope":"fixture-not-cold-build"}\n')
        for index, name in enumerate(config['wrapper_objects'] + config['engine_objects']):
            use_eh = index < 12
            objects.append({'id': name, 'source': ref('sources', source_paths[name]),
                'arguments': ['-std=c++23', '-fexceptions' if use_eh else '-fno-exceptions'],
                'dependencies': [ref('sources', source_paths[name])],
                'original_command_sha256': command_hash,
                'unified_members': [ref('sources', source_paths[name])] if name.startswith('UnifiedSource-') else [],
                'exceptions': use_eh})
        archives = []
        replacements = []
        owner_index = 0
        for name, count in config['archive_members'].items():
            members, thin_members = [], []
            for ordinal in range(count):
                owner = (config['engine_objects'][ordinal] if name == 'WebCore' and ordinal < 5
                         else 'RunLoopGeneric.cpp' if name == 'WTF' and ordinal == 0 else None)
                member_name = owner + '.o' if owner else name + '-' + str(ordinal) + '.o'
                raw = (member_name + '\n').encode()
                path = 'objects/' + member_name
                write(reuse, path, raw)
                record = {'argv': ['/fixture/compiler', '-o', str(reuse / path), '-c', '/fixture/original/' + (owner or member_name[:-2])],
                          'cwd': str(reuse)}
                identity = hashlib.sha256(encoded(record)).hexdigest()
                command_records[identity] = record
                members.append({'ordinal': ordinal, 'name': '../' + path,
                    'input': ref('reuse', path), 'bytes': len(raw), 'compile_command_sha256': identity})
                thin_members.append(('../' + path, raw))
            archive_path = 'lib/lib' + name + '.a'
            write(reuse, archive_path, thin(thin_members))
            archives.append({'name': name, 'input': ref('reuse', archive_path), 'members': members})
            if name == 'WebCore':
                for ordinal, owner in enumerate(config['engine_objects'][:5]):
                    replacements.append({'archive': name, 'ordinal': ordinal, 'object_id': owner,
                        'old_sha256': members[ordinal]['input']['sha256']})
            elif name == 'WTF':
                replacements.append({'archive': name, 'ordinal': 0, 'object_id': 'RunLoopGeneric.cpp',
                    'old_sha256': members[0]['input']['sha256']})
        for replacement in replacements:
            old = next(a for a in archives if a['name'] == replacement['archive'])['members'][replacement['ordinal']]
            next(obj for obj in objects if obj['id'] == replacement['object_id'])['original_command_sha256'] = old['compile_command_sha256']
        write(reuse, 'commands.json', encoded({'schema_version': 1,
            'kind': 'foundation-engine-original-commands-v1', 'commands': command_records}))
        dependencies = []
        for name in sorted(set(config['link_archive_names']) - set(config['archive_members'])):
            write(reuse, 'dependencies/' + name, b'inert dependency ' + name.encode())
            dependencies.append(ref('reuse', 'dependencies/' + name))
        for name in ('pre.js', 'host.js'):
            retain('source/' + name, b'// inert fixture ' + name.encode())
        data = []
        for index in range(32):
            name = 'data/item' + str(index)
            retain(name, b'data\n', 'data')
            data.append({'input': ref('sources', name), 'virtual_path': '/exact-original/' + str(index)})
        executable = str(Path(sys.executable).resolve())
        host = {'path': executable, 'sha256': digest(executable), 'version': sys.version,
                'provenance': 'synthetic fixture external host prerequisite', 'recovery_limit': 'not retained'}
        proof = {'schema_version': 1, 'kind': maintenance.REUSE_KIND, 'profile': config['name'],
            'target': recipe['target'], 'paired_sdk_sha256': sdk_hash,
            'baseline': {'origin': 'inert fixture, not a build', 'original_receipt': ref('reuse', 'original-receipt.json'),
                'source_identity': 'fixture-original-sources', 'configuration_identity': 'fixture-original-config',
                'recorded_scopes': ['fixture only'], 'command_records': ref('reuse', 'commands.json'),
                'original_root': str(reuse)},
            'inventory': manifest.tree_inventory(reuse, 'reuse-proof.json'),
            'host_tools': {key: copy.deepcopy(host) for key in ('python', 'cmake', 'ninja')},
            'sdk_tools': {key: {'path': 'upstream/emscripten/' + name,
                'sha256': digest(sdk / ('upstream/emscripten/' + name))}
                for key, name in (('emxx', 'em++'), ('emar', 'emar'), ('emranlib', 'emranlib'))},
            'python_launch': {key: {'path': name, 'sha256': digest(sdk / name)}
                              for key, (name, _) in launcher_markers.items()},
            'objects': objects, 'archives': archives, 'replacements': replacements,
            'link': {'flags': ['-fexceptions', '--no-entry', '-lexports.js',
                *('-s' + name + '=' + value for name, value in config['link_settings'].items())],
                'archives': config['link_archive_names'], 'dependencies': dependencies,
                'pre_js': ref('sources', 'source/pre.js'), 'host_library': ref('sources', 'source/host.js'), 'data': data},
            'metadata': {'generator': ref('sources', config['metadata_generator']),
                'prelink_plan': ref('sources', 'provenance/prelink.json'),
                'contract_header': ref('sources', recipe['provider']['header'])},
            'private_cache': {'root': 'cache', 'files': ['cache/syslib.a']},
            'emscripten_config': {'LLVM_ROOT': 'upstream/bin', 'BINARYEN_ROOT': 'upstream', 'NODE_JS': 'node/bin/node'},
            'recovery_limits': ['fake engine and external host tools; no runtime qualification']}
        write(reuse, 'reuse-proof.json', encoded(proof))
        write(sources, 'recipe.json', encoded(recipe))
        source_hash = digest(sources / 'recipe.json')
        source_manifest = {'schema_version': 1, 'kind': 'foundation-appended-engine-sources',
            'producer_version': 1, 'recipe_id': source_hash, **manifest.tree_inventory(sources, 'sources.json')}
        write(sources, 'sources.json', encoded(source_manifest))
        selection = {'profile': config['name'], 'sources': str(sources), 'recipe_sha256': source_hash,
            'sources_sha256': digest(sources / 'sources.json'),
            'projection': str(sources / 'provenance/source-projection.json'),
            'projection_sha256': digest(sources / 'provenance/source-projection.json'),
            'sdk': str(sdk), 'sdk_manifest_sha256': sdk_hash, 'reuse_root': str(reuse),
            'reuse_proof': str(reuse / 'reuse-proof.json'), 'reuse_proof_sha256': digest(reuse / 'reuse-proof.json')}
        return selection, proof

    def test_complete_plan_is_passive_and_pins_actual_thin_order(self):
        selection, proof = self.fixture()
        with mock.patch('subprocess.Popen', side_effect=AssertionError('no plan programs')), \
                mock.patch.object(maintenance.process_tree, 'launch', side_effect=AssertionError('no launch')):
            result = maintenance.make_plan(selection, self.base / 'plan')
            plan, inspection = maintenance.verify_plan(Path(result['plan']), result['plan_sha256'])
        self.assertFalse(result['production_eligible'])
        self.assertEqual(sum(map(lambda a: len(a['members']), proof['archives'])), 2076)
        self.assertEqual(len(proof['replacements']), 6)
        self.assertEqual(proof['link']['archives'][3], proof['link']['archives'][19])
        self.assertEqual(plan['scope'], maintenance.SCOPE)
        self.assertEqual(inspection.proof['host_tools']['python']['recovery_limit'], 'not retained')

    def identity_fixture(self, *, inspection=None, record_root='reuse'):
        """Ordinary copied headers; historical identities are synthetic evidence."""
        if inspection is None:
            roots = {name: self.base / ('identity-' + name) for name in ('sources', 'reuse', 'sdk')}
            for root in roots.values():
                root.mkdir()
                root.chmod(0o755)
            inspection = maintenance.Inspection(
                selection={'projection_sha256': 'a' * 64}, recipe={}, projection={'files': {}},
                proof={}, roots=roots, inventories={name: {} for name in roots}, profile={})
        raw = b'#pragma once\n#include "Sibling.h"\nstruct FixtureIdentity {};\n'
        groups = [
            ('include canonical/Shared.h', ['include aliases/one/Shared.h', 'include aliases/two/Shared.h']),
            ('include canonical/Unrelated.h', ['include aliases/other/Unrelated.h']),
        ]
        classes, receipt_files = [], {}
        for index, (canonical, aliases) in enumerate(groups):
            refs = []
            original_identity = [91, 201 + index, 0o100644, 1, len(raw), 1001, 1002]
            for name in (canonical, *aliases):
                path = write(inspection.roots['reuse'], name, raw)
                inspection.inventories['reuse'][name] = digest(path)
                refs.append({'root': 'reuse', 'path': name, 'sha256': digest(path)})
                receipt_files[name] = {'source_identity': original_identity.copy(),
                                       'sha256': digest(path), 'bytes': len(raw)}
            classes.append({'original_identity': original_identity,
                            'canonical': refs[0], 'aliases': refs[1:]})
        # Equal content outside the declared identity classes must stay distinct.
        unclassified = write(inspection.roots['reuse'], 'include ignored/Shared.h', raw)
        inspection.inventories['reuse']['include ignored/Shared.h'] = digest(unclassified)
        receipt_files['include ignored/Shared.h'] = {'source_identity':
            [91, 203, 0o100644, 1, len(raw), 1001, 1002], 'sha256': digest(unclassified), 'bytes': len(raw)}
        for index, (name, content) in enumerate((
                ('include canonical/Sibling.h', b'// physical canonical sibling\n'),
                ('include aliases/one/Sibling.h', b'// requested logical sibling\n'))):
            path = write(inspection.roots['reuse'], name, content)
            inspection.inventories['reuse'][name] = digest(path)
            receipt_files[name] = {'source_identity': [91, 204 + index, 0o100644, 1, len(content), 1001, 1002],
                                   'sha256': digest(path), 'bytes': len(content)}
        receipt = {'schema_version': 1, 'kind': 'closed-unpublished-baseline-copy-v1',
                   'status': 'closed-exact-readback-passed-unpublished', 'files': receipt_files}
        generated = write(inspection.roots['reuse'], 'provenance/original-command-ledger.json', b'{}\n')
        inspection.inventories['reuse']['provenance/original-command-ledger.json'] = digest(generated)
        receipt_files['provenance/original-command-ledger.json'] = {
            'source_identity': None, 'sha256': digest(generated), 'bytes': generated.stat().st_size}
        receipt_path = write(inspection.roots['reuse'], 'provenance/copy-receipt.json', encoded(receipt))
        inspection.inventories['reuse']['provenance/copy-receipt.json'] = digest(receipt_path)
        record = {'schema_version': 1, 'kind': 'foundation-copied259-header-identity-v1',
                  'projection_sha256': inspection.selection['projection_sha256'],
                  'evidence_sha256': {'discovery': 'b' * 64, 'copy_set': 'c' * 64,
                                      'copy_receipt': digest(receipt_path)},
                  'classes': classes, 'postimages': []}
        self.retain_identity_record(inspection, record, root=record_root)
        return inspection, record

    def retain_identity_record(self, inspection, record, *, root=None, raw=None):
        current = inspection.proof.get('header_identity', {})
        root = root or current.get('root', 'reuse')
        name = 'provenance/header-identity.json'
        path = write(inspection.roots[root], name, encoded(record) if raw is None else raw)
        inspection.inventories[root][name] = digest(path)
        inspection.proof['header_identity'] = {'root': root, 'path': name, 'sha256': digest(path)}
        return path

    def identity_mappings(self, overlay):
        result = {}
        def visit(entry, parent=None):
            name = Path(entry['name'])
            path = name if name.is_absolute() else parent / name
            if entry['type'] == 'directory':
                for child in entry['contents']:
                    visit(child, path)
            else:
                self.assertEqual(entry['type'], 'file')
                self.assertNotIn(str(path), result)
                result[str(path)] = entry['external-contents']
        for entry in overlay['roots']:
            visit(entry)
        return result

    def test_header_identity_is_optional_and_does_not_collapse_equal_content_classes(self):
        self.assertIsNone(maintenance._header_identity(SimpleNamespace(proof={})))
        inspected, record = self.identity_fixture()
        with mock.patch('subprocess.Popen', side_effect=AssertionError('no header-view programs')):
            view = maintenance._header_identity(inspected)
        self.assertEqual({key: value for key, value in view['overlay'].items() if key != 'roots'},
                         {'version': 0, 'case-sensitive': True, 'use-external-names': False,
                          'overlay-relative': False, 'fallthrough': True})
        expected = {str(inspected.roots['reuse'] / alias['path']):
                    str(inspected.roots['reuse'] / group['canonical']['path'])
                    for group in record['classes'] for alias in group['aliases']}
        self.assertEqual(self.identity_mappings(view['overlay']), expected)
        self.assertEqual(view['mapping_count'], 3)
        self.assertEqual(view['record_ref'], inspected.proof['header_identity'])
        dependencies = {inspected.roots['reuse'] / ref['path']
                        for group in record['classes'] for ref in [group['canonical'], *group['aliases']]}
        dependencies.add(inspected.roots['reuse'] / inspected.proof['header_identity']['path'])
        dependencies.add(inspected.roots['reuse'] / 'provenance/copy-receipt.json')
        self.assertEqual(set(map(Path, view['dependencies'])), dependencies)
        # Sibling spellings and unrelated equal bytes are not implicit remaps.
        for path in ('include ignored/Shared.h', 'include aliases/one/Sibling.h', 'include canonical/Sibling.h',
                     'provenance/original-command-ledger.json'):
            self.assertNotIn(str(inspected.roots['reuse'] / path), expected)
        ids = [(inspected.roots['reuse'] / ref['path']).stat().st_ino
               for group in record['classes'] for ref in [group['canonical'], *group['aliases']]]
        self.assertEqual(len(set(ids)), len(ids))

    def test_header_identity_rejects_unreviewed_fields_evidence_and_original_identity(self):
        inspected, original = self.identity_fixture()
        cases = []
        for key, value in (('schema_version', True), ('kind', 'other'), ('projection_sha256', 'f' * 64),
                           ('postimages', [{'preimage': 'unreviewed'}]), ('classes', []), ('extra', True)):
            changed = copy.deepcopy(original)
            changed[key] = value
            cases.append((key, changed))
        for label, evidence in (('missing evidence', {'discovery': 'b' * 64, 'copy_set': 'c' * 64}),
                                ('extra evidence', dict(original['evidence_sha256'], unknown='e' * 64)),
                                ('invalid evidence', dict(original['evidence_sha256'], copy_receipt='not-a-pin'))):
            changed = copy.deepcopy(original)
            changed['evidence_sha256'] = evidence
            cases.append((label, changed))
        invalid_identities = [[91, 201]]
        for index, value in ((0, True), (0, -1), (4, 1)):
            identity = copy.deepcopy(original['classes'][0]['original_identity'])
            identity[index] = value
            invalid_identities.append(identity)
        for identity in invalid_identities:
            changed = copy.deepcopy(original)
            changed['classes'][0]['original_identity'] = identity
            cases.append(('original identity ' + repr(identity), changed))
        for label, changed in cases:
            self.retain_identity_record(inspected, changed)
            with self.subTest(case=label), self.assertRaises(ValueError):
                maintenance._header_identity(inspected)
        duplicate = encoded(original).replace(b'{', b'{"schema_version":1,', 1)
        self.retain_identity_record(inspected, original, raw=duplicate)
        with self.assertRaises(ValueError):
            maintenance._header_identity(inspected)

    def test_header_identity_rejects_duplicate_paths_identity_classes_and_alias_chains(self):
        inspected, original = self.identity_fixture()
        cases = []
        for label, mutate in (
                ('duplicate alias', lambda value: value['classes'][0]['aliases'].append(
                    copy.deepcopy(value['classes'][0]['aliases'][0]))),
                ('canonical alias cycle', lambda value: value['classes'][0]['aliases'].append(
                    copy.deepcopy(value['classes'][0]['canonical']))),
                ('cross-class path', lambda value: value['classes'][1]['aliases'].append(
                    copy.deepcopy(value['classes'][0]['canonical']))),
                ('duplicate original identity', lambda value: value['classes'][1].update(
                    original_identity=copy.deepcopy(value['classes'][0]['original_identity']))),
                ('contradictory original snapshot', lambda value: value['classes'][1].update(
                    original_identity=[*value['classes'][0]['original_identity'][:5], 2001, 2002])),
                ('empty aliases', lambda value: value['classes'][0].update(aliases=[])),
                ('unknown class field', lambda value: value['classes'][0].update(extra=True))):
            changed = copy.deepcopy(original)
            mutate(changed)
            cases.append((label, changed))
        for label, changed in cases:
            self.retain_identity_record(inspected, changed)
            with self.subTest(case=label), self.assertRaises(ValueError):
                maintenance._header_identity(inspected)

    def test_header_identity_rejects_foreign_uninventoried_and_unequal_alias_targets(self):
        inspected, original = self.identity_fixture()
        for role in ('canonical', 'alias'):
            for root in ('sources', 'sdk'):
                changed = copy.deepcopy(original)
                group = changed['classes'][0]
                reference = group['canonical'] if role == 'canonical' else group['aliases'][0]
                target = write(inspected.roots[root], reference['path'],
                               (inspected.roots['reuse'] / reference['path']).read_bytes())
                inspected.inventories[root][reference['path']] = digest(target)
                reference['root'] = root
                self.retain_identity_record(inspected, changed)
                with self.subTest(role=role, root=root), self.assertRaises(ValueError):
                    maintenance._header_identity(inspected)
        changed = copy.deepcopy(original)
        changed['classes'][0]['aliases'][0]['path'] = 'not-in-inventory.h'
        self.retain_identity_record(inspected, changed)
        with self.assertRaises(ValueError):
            maintenance._header_identity(inspected)
        # Repin every changed input so rejection distinguishes byte inequality
        # within one identity class from stale references or size differences.
        changed = copy.deepcopy(original)
        alias = changed['classes'][0]['aliases'][0]
        original_bytes = (inspected.roots['reuse'] / alias['path']).read_bytes()
        path = write(inspected.roots['reuse'], alias['path'], b'X' + original_bytes[1:])
        alias['sha256'] = inspected.inventories['reuse'][alias['path']] = digest(path)
        receipt_path = inspected.roots['reuse'] / 'provenance/copy-receipt.json'
        receipt = json.loads(receipt_path.read_bytes())
        receipt['files'][alias['path']]['sha256'] = digest(path)
        write(inspected.roots['reuse'], 'provenance/copy-receipt.json', encoded(receipt))
        inspected.inventories['reuse']['provenance/copy-receipt.json'] = digest(receipt_path)
        changed['evidence_sha256']['copy_receipt'] = digest(receipt_path)
        self.retain_identity_record(inspected, changed)
        with self.assertRaises(ValueError):
            maintenance._header_identity(inspected)

    def test_header_identity_requires_copy_receipt_identity_join_and_complete_class_membership(self):
        inspected, original = self.identity_fixture()
        cases = []
        changed = copy.deepcopy(original)
        changed['classes'][0]['canonical'] = {'root': 'reuse', 'path': 'include ignored/Shared.h',
            'sha256': inspected.inventories['reuse']['include ignored/Shared.h']}
        cases.append(('equal hash wrong historical file', changed))
        changed = copy.deepcopy(original)
        changed['classes'][0]['aliases'].pop()
        cases.append(('omitted copied alias', changed))
        changed = copy.deepcopy(original)
        changed['classes'].pop()
        cases.append(('omitted multi-path identity class', changed))
        changed = copy.deepcopy(original)
        changed['evidence_sha256']['copy_receipt'] = 'f' * 64
        cases.append(('missing inventoried receipt', changed))
        for label, changed in cases:
            self.retain_identity_record(inspected, changed)
            with self.subTest(case=label), self.assertRaises(ValueError):
                maintenance._header_identity(inspected)
        self.retain_identity_record(inspected, original)
        receipt_path = inspected.roots['reuse'] / 'provenance/copy-receipt.json'
        duplicate = write(inspected.roots['reuse'], 'provenance/ambiguous-receipt.json', receipt_path.read_bytes())
        inspected.inventories['reuse']['provenance/ambiguous-receipt.json'] = digest(duplicate)
        with self.assertRaises(ValueError):
            maintenance._header_identity(inspected)
        del inspected.inventories['reuse']['provenance/ambiguous-receipt.json']
        duplicate.unlink()
        receipt = json.loads(receipt_path.read_bytes())
        receipt['files'][original['classes'][0]['canonical']['path']]['source_identity'][1] = 999
        write(inspected.roots['reuse'], 'provenance/copy-receipt.json', encoded(receipt))
        inspected.inventories['reuse']['provenance/copy-receipt.json'] = digest(receipt_path)
        changed = copy.deepcopy(original)
        changed['evidence_sha256']['copy_receipt'] = digest(receipt_path)
        self.retain_identity_record(inspected, changed)
        with self.assertRaises(ValueError):
            maintenance._header_identity(inspected)

    def test_header_identity_pins_record_bytes_rejects_alias_filesystem_links_and_engine_postimages(self):
        inspected, record = self.identity_fixture()
        record_path = inspected.roots['reuse'] / inspected.proof['header_identity']['path']
        record_path.write_bytes(record_path.read_bytes() + b' ')
        with self.assertRaises(ValueError):
            maintenance._header_identity(inspected)
        self.retain_identity_record(inspected, record)
        for suffix in ('.h', '.hpp', '.hh', '.hxx', '.inc', '.inl'):
            name = 'source/engine/nested/Modified' + suffix
            inspected.projection['files'] = {name: {'sha256': 'e' * 64}}
            with self.subTest(suffix=suffix), self.assertRaises(ValueError):
                maintenance._header_identity(inspected)
        inspected.projection['files'] = {}
        alias = inspected.roots['reuse'] / record['classes'][0]['aliases'][0]['path']
        canonical = inspected.roots['reuse'] / record['classes'][0]['canonical']['path']
        alias.unlink()
        alias.symlink_to(canonical)
        with self.assertRaises(ValueError):
            maintenance._header_identity(inspected)
        alias.unlink()
        os.link(canonical, alias)
        with self.assertRaises(ValueError):
            maintenance._header_identity(inspected)

    def test_header_identity_rejects_invalid_authority_identity_even_with_matching_record_repins(self):
        inspected, original = self.identity_fixture()
        receipt_path = inspected.roots['reuse'] / 'provenance/copy-receipt.json'
        original_receipt = json.loads(receipt_path.read_bytes())
        for label in ('boolean schema', 'missing generated identity', 'boolean physical identity'):
            receipt, record = copy.deepcopy(original_receipt), copy.deepcopy(original)
            if label == 'boolean schema':
                receipt['schema_version'] = True
            elif label == 'missing generated identity':
                del receipt['files']['provenance/original-command-ledger.json']['source_identity']
            else:
                group = record['classes'][0]
                group['original_identity'][0] = True
                for ref in [group['canonical'], *group['aliases']]:
                    receipt['files'][ref['path']]['source_identity'] = group['original_identity'].copy()
            write(inspected.roots['reuse'], 'provenance/copy-receipt.json', encoded(receipt))
            inspected.inventories['reuse']['provenance/copy-receipt.json'] = digest(receipt_path)
            record['evidence_sha256']['copy_receipt'] = digest(receipt_path)
            self.retain_identity_record(inspected, record)
            with self.subTest(case=label), self.assertRaises(ValueError):
                maintenance._header_identity(inspected)

    def test_header_identity_generated_metadata_without_original_identity_cannot_authorize_alias(self):
        inspected, record = self.identity_fixture()
        group = record['classes'][0]
        name = 'provenance/original-command-ledger.json'
        # Equal bytes/size cannot turn generated metadata into an original alias.
        raw = (inspected.roots['reuse'] / group['canonical']['path']).read_bytes()
        generated = write(inspected.roots['reuse'], name, raw)
        inspected.inventories['reuse'][name] = digest(generated)
        receipt_path = inspected.roots['reuse'] / 'provenance/copy-receipt.json'
        receipt = json.loads(receipt_path.read_bytes())
        receipt['files'][name].update(sha256=digest(generated), bytes=len(raw))
        write(inspected.roots['reuse'], 'provenance/copy-receipt.json', encoded(receipt))
        inspected.inventories['reuse']['provenance/copy-receipt.json'] = digest(receipt_path)
        record['evidence_sha256']['copy_receipt'] = digest(receipt_path)
        group['aliases'].append({'root': 'reuse', 'path': name, 'sha256': digest(generated)})
        self.retain_identity_record(inspected, record)
        with self.assertRaises(ValueError):
            maintenance._header_identity(inspected)

    def test_header_identity_record_can_be_retained_in_sources_but_not_sdk(self):
        inspected, record = self.identity_fixture(record_root='sources')
        view = maintenance._header_identity(inspected)
        self.assertEqual(view['record_ref']['root'], 'sources')
        self.assertIn(inspected.roots['sources'] / 'provenance/header-identity.json',
                      list(map(Path, view['dependencies'])))
        self.retain_identity_record(inspected, record, root='sdk')
        with self.assertRaises(ValueError):
            maintenance._header_identity(inspected)

    def test_header_identity_internal_graph_view_preserves_explicit_alias_paths_and_dependencies(self):
        selection, _ = self.fixture()
        inspected, record = self.identity_fixture(inspection=maintenance.inspect_inputs(selection))
        output = self.base / 'identity-graph'
        (output / 'cmake').mkdir(parents=True)
        (output / 'private').mkdir()
        plan_path = write(self.base, 'identity-plan.json', b'{}\n')
        with mock.patch('subprocess.Popen', side_effect=AssertionError('no graph programs')):
            maintenance._validate_proof(inspected)
            prepared = maintenance._write_header_identity(inspected, output)
            _, fragment, commands = maintenance._graph(inspected, {}, plan_path, digest(plan_path), output)
        view_path = output / 'private/header-identity-vfs.json'
        expected = maintenance._header_identity(inspected)
        self.assertEqual(json.loads(view_path.read_bytes()), expected['overlay'])
        self.assertEqual(Path(prepared['path']), view_path)
        self.assertEqual(prepared['sha256'], digest(view_path))
        mappings = self.identity_mappings(expected['overlay'])
        self.assertEqual(mappings[str(inspected.roots['reuse'] / 'include aliases/one/Shared.h')],
                         str(inspected.roots['reuse'] / 'include canonical/Shared.h'))
        for obj in inspected.proof['objects']:
            argv = commands['objects'][obj['id']]
            self.assertEqual(argv[1:3], ['-ivfsoverlay', str(view_path)])
            self.assertEqual(argv[3:3 + len(obj['arguments'])], obj['arguments'])
        self.assertNotIn('-ivfsoverlay', commands['link'])
        graph = fragment.read_text()
        for index in range(len(inspected.proof['objects'])):
            edge = graph.split('set(ENGINE_OBJECT_o' + str(index) + '_DEPENDS', 1)[1].split(')\n', 1)[0]
            for path in [view_path, *map(Path, expected['dependencies'])]:
                self.assertIn(maintenance._cmake_value(path), edge)

    def test_header_identity_plan_admission_is_passive_and_rejects_repinned_invalid_record(self):
        selection, _ = self.fixture()
        inspected, record = self.identity_fixture(inspection=maintenance.inspect_inputs(selection))
        inspected.proof['inventory'] = manifest.tree_inventory(inspected.roots['reuse'], 'reuse-proof.json')
        proof_path = write(inspected.roots['reuse'], 'reuse-proof.json', encoded(inspected.proof))
        selection['reuse_proof_sha256'] = digest(proof_path)
        with mock.patch('subprocess.Popen', side_effect=AssertionError('no plan programs')), \
                mock.patch.object(maintenance.process_tree, 'launch', side_effect=AssertionError('no launch')):
            admitted = maintenance.make_plan(selection, self.base / 'valid-header-plan')
        self.assertFalse(admitted['production_eligible'])
        record['postimages'] = [{'unreviewed': 'header replacement'}]
        self.retain_identity_record(inspected, record)
        inspected.proof['inventory'] = manifest.tree_inventory(inspected.roots['reuse'], 'reuse-proof.json')
        proof_path = write(inspected.roots['reuse'], 'reuse-proof.json', encoded(inspected.proof))
        selection['reuse_proof_sha256'] = digest(proof_path)
        output = self.base / 'invalid-header-plan'
        with mock.patch('subprocess.Popen', side_effect=AssertionError('no plan programs')), \
                mock.patch.object(maintenance.process_tree, 'launch', side_effect=AssertionError('no launch')):
            with self.assertRaises(ValueError):
                maintenance.make_plan(selection, output)
        self.assertFalse(output.exists())

    def test_header_identity_build_rechecks_private_view_before_second_supervised_phase(self):
        selection, _ = self.fixture()
        inspected, _ = self.identity_fixture(inspection=maintenance.inspect_inputs(selection))
        inspected.proof['inventory'] = manifest.tree_inventory(inspected.roots['reuse'], 'reuse-proof.json')
        proof_path = write(inspected.roots['reuse'], 'reuse-proof.json', encoded(inspected.proof))
        selection['reuse_proof_sha256'] = digest(proof_path)
        planned = maintenance.make_plan(selection, self.base / 'identity-build-plan')
        output = self.base / 'identity-build'
        phases = []
        def configure_changes_private_view(argv, *unused):
            phases.append(argv)
            path = output / 'private/header-identity-vfs.json'
            self.assertTrue(path.is_file())
            self.assertEqual(json.loads(path.read_bytes()), maintenance._header_identity(inspected)['overlay'])
            path.write_bytes(path.read_bytes() + b' ')
            return {'returncode': 0, 'writers_finished': True}
        with mock.patch.object(maintenance, '_supervise', side_effect=configure_changes_private_view):
            with self.assertRaisesRegex(ValueError, 'Input hash mismatch: .*header-identity-vfs.json'):
                maintenance.build(Path(planned['plan']), planned['plan_sha256'], output)
        self.assertEqual(len(phases), 1)
        self.assertFalse((output / 'maintenance-build.json').exists())
        self.assertEqual(json.loads((output / 'maintenance-failure.json').read_bytes())['status'], 'incomplete')

    def test_user_overlay_options_remain_outside_closed_grammar(self):
        for args in (['-ivfsoverlay', '{reuse}/view.json'], ['-ivfsoverlay{reuse}/view.json'],
                     ['-ivfsoverlay'], ['-vfsoverlay', '{reuse}/view.json'],
                     ['-Xclang', '-ivfsoverlay', '-Xclang', '{reuse}/view.json']):
            for link in (False, True):
                with self.subTest(arguments=args, link=link), self.assertRaises(ValueError):
                    maintenance._arguments(args, link=link)

    def test_source_pin_rejection_precedes_any_output_or_program(self):
        selection, _ = self.fixture()
        selection['recipe_sha256'] = '9' * 64
        with mock.patch('subprocess.Popen', side_effect=AssertionError('no program')), self.assertRaises(ValueError):
            maintenance.make_plan(selection, self.base / 'absent-plan')
        self.assertFalse((self.base / 'absent-plan').exists())

    def test_actual_declared_wasm32_emscripten_triple_is_preserved_without_programs(self):
        selection, _ = self.fixture(recipe_triple='wasm32-emscripten')
        recipe_path = Path(selection['sources']) / 'recipe.json'
        sdk_path = Path(selection['sdk']) / 'sdk.json'
        recipe_before, sdk_before = recipe_path.read_bytes(), sdk_path.read_bytes()
        with mock.patch('subprocess.Popen', side_effect=AssertionError('no SDK programs')), \
                mock.patch.object(maintenance.process_tree, 'launch', side_effect=AssertionError('no launch')):
            result = maintenance.make_plan(selection, self.base / 'actual-spelling-plan')
            _, inspected = maintenance.verify_plan(Path(result['plan']), result['plan_sha256'])
        self.assertEqual(inspected.recipe['target']['triple'], 'wasm32-emscripten')
        self.assertEqual(inspected.proof['target']['triple'], 'wasm32-emscripten')
        self.assertEqual(recipe_path.read_bytes(), recipe_before)
        self.assertEqual(sdk_path.read_bytes(), sdk_before)

    def test_documented_triple_alias_mismatch_is_rejected_before_programs(self):
        selection, _ = self.fixture(recipe_triple='wasm32-unknown-emscripten', sdk_triple='wasm32-emscripten')
        output = self.base / 'mismatched-alias-plan'
        with mock.patch('subprocess.Popen', side_effect=AssertionError('no SDK programs')), \
                mock.patch.object(maintenance.process_tree, 'launch', side_effect=AssertionError('no launch')):
            with self.assertRaisesRegex(ValueError, 'target triple differs'):
                maintenance.make_plan(selection, output)
        self.assertFalse(output.exists())

    def test_unsupported_triple_is_rejected_even_when_sdk_declaration_matches(self):
        selection, _ = self.fixture(recipe_triple='wasm32-custom-emscripten')
        output = self.base / 'unsupported-triple-plan'
        with mock.patch('subprocess.Popen', side_effect=AssertionError('no SDK programs')), \
                mock.patch.object(maintenance.process_tree, 'launch', side_effect=AssertionError('no launch')):
            with self.assertRaisesRegex(ValueError, 'Source recipe is not the exact copied259 browser profile'):
                maintenance.make_plan(selection, output)
        self.assertFalse(output.exists())

    def test_proof_cannot_relabel_thin_order_or_compile_wrong_source(self):
        selection, _ = self.fixture()
        inspected = maintenance.inspect_inputs(selection)
        cases = []
        wrong = copy.deepcopy(inspected)
        wrong.proof['archives'][0]['members'][0]['name'] = 'unrelated.o'
        cases.append(wrong)
        wrong = copy.deepcopy(inspected)
        wrong.proof['objects'][0]['source'] = wrong.proof['archives'][0]['members'][0]['input']
        cases.append(wrong)
        wrong = copy.deepcopy(inspected)
        wrong.proof['objects'][0]['original_command_sha256'] = '8' * 64
        cases.append(wrong)
        wrong = copy.deepcopy(inspected)
        wrong.proof['link']['archives'][3], wrong.proof['link']['archives'][4] = wrong.proof['link']['archives'][4], wrong.proof['link']['archives'][3]
        cases.append(wrong)
        wrong = copy.deepcopy(inspected)
        wrong.proof['link']['flags'].append('-sENVIRONMENT=web')
        cases.append(wrong)
        wrong = copy.deepcopy(inspected)
        wrong.proof['objects'][0]['arguments'].append('-fno-exceptions')
        cases.append(wrong)
        wrong = copy.deepcopy(inspected)
        replacement = next(r for r in wrong.proof['replacements'] if r['archive'] == 'WebCore')
        replacement['ordinal'] = 10
        replacement['old_sha256'] = next(a for a in wrong.proof['archives'] if a['name'] == 'WebCore')['members'][10]['input']['sha256']
        cases.append(wrong)
        for value in cases:
            with self.subTest(value=value.proof['objects'][0]['id']), self.assertRaises(ValueError):
                maintenance._validate_proof(value)

    def test_plan_tamper_and_unknown_options_are_rejected(self):
        path = write(self.base, 'plan.json', b'{}\n')
        with mock.patch.object(maintenance, 'inspect_inputs', side_effect=AssertionError('early pin')):
            with self.assertRaises(ValueError):
                maintenance.verify_plan(path, '7' * 64)
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            maintenance.main(['build', '--plan', str(path), '--plan-sha256', '7' * 64,
                '--output', str(self.base / 'output'), '--target', 'all'])

    def test_candidate_build_stays_ineligible_and_uses_only_two_supervised_phases(self):
        selection, proof = self.fixture()
        planned = maintenance.make_plan(selection, self.base / 'plan')
        output = self.base / 'candidate'
        phases = []
        def fake_supervise(argv, cwd, log, environment, timeout):
            phases.append(argv)
            self.assertEqual(cwd, output)
            self.assertEqual(environment['EM_FROZEN_CACHE'], '1')
            self.assertEqual(environment['EMSDK_PYTHON'], str(output / 'private/sdk-python'))
            if '--build' in argv:
                for obj in proof['objects']:
                    write(output, 'objects/' + obj['id'] + '.o', b'fake object\n')
                write(output, 'evidence/artifact-inspection.json', encoded({'production_eligible': False, 'fixture': True}))
            return {'returncode': 0, 'writers_finished': True}
        with mock.patch.object(maintenance, '_supervise', side_effect=fake_supervise):
            result = maintenance.build(Path(planned['plan']), planned['plan_sha256'], output)
        self.assertEqual(len(phases), 2)
        self.assertIn('foundation-neutral-engine', phases[1])
        self.assertEqual(result['status'], 'passed')
        self.assertFalse(result['production_eligible'])
        self.assertEqual(len(result['objects']), 24)
        self.assertFalse((output / 'engine-sdk.json').exists())

    def test_changed_configure_input_stops_before_build_program(self):
        selection, _ = self.fixture()
        planned = maintenance.make_plan(selection, self.base / 'plan')
        output = self.base / 'candidate'
        phases = []
        def configure_changes_input(argv, *args):
            phases.append(argv)
            (Path(selection['reuse_root']) / 'objects/JavaScriptCore-0.o').write_bytes(b'changed\n')
            return {'returncode': 0, 'writers_finished': True}
        with mock.patch.object(maintenance, '_supervise', side_effect=configure_changes_input):
            with self.assertRaises(ValueError):
                maintenance.build(Path(planned['plan']), planned['plan_sha256'], output)
        self.assertEqual(len(phases), 1)
        self.assertFalse((output / 'maintenance-build.json').exists())
        self.assertEqual(json.loads((output / 'maintenance-failure.json').read_bytes())['status'], 'incomplete')

    def test_regular_archive_actual_bytes_order_index_and_duplicate_rejection(self):
        path = write(self.base, 'sample.a', regular([('first.o', b'abc'), ('second.o', b'xy')]))
        expected = [{'name': name, 'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}
                    for name, raw in [('first.o', b'abc'), ('second.o', b'xy')]]
        self.assertEqual(maintenance.read_regular_archive(path), expected)
        for raw in (regular([('x.o', b'a'), ('x.o', b'b')]), regular([('x.o', b'a')], offsets=[9]),
                    b'!<thin>\n', regular([('../bad.o', b'a')]), regular([('x.o', b'a')])[:-1]):
            path.write_bytes(raw)
            with self.subTest(raw=raw[:16]), self.assertRaises(ValueError):
                maintenance.read_regular_archive(path)

    def test_regular_archive_llvm_index_alignment_and_malformed_symbol_counts(self):
        def archive(names, *, count=1, width=4):
            size = width * (count + 1) + len(names)
            offset = 8 + 60 + size + (size & 1)
            index = count.to_bytes(width, 'big') + offset.to_bytes(width, 'big') * count + names
            return (b'!<arch>\n' + header('/SYM64/' if width == 8 else '/', size) + index
                    + (b'\n' if size & 1 else b'') + header('one.o/', 3) + b'abc\n')
        path = self.base / 'index.a'
        expected = [{'name': 'one.o', 'sha256': hashlib.sha256(b'abc').hexdigest(), 'bytes': 3}]
        for width in (4, 8):
            for names, count in ((b'xy\0\0', 1), (b'xy\0', 1), (b'x\0', 1),
                                 (b'a\0b\0', 2), (b'', 0)):
                with self.subTest(width=width, names=names, count=count):
                    path.write_bytes(archive(names, count=count, width=width))
                    self.assertEqual(expected, maintenance.read_regular_archive(path))
            for names, count in ((b'xy\0\0\0', 1), (b'x\0\0', 1), (b'\0', 1),
                                 (b'xy', 1), (b'\0', 0), (b'a\0b\0', 1), (b'a\0', 2)):
                with self.subTest(width=width, names=names, count=count):
                    path.write_bytes(archive(names, count=count, width=width))
                    with self.assertRaisesRegex(ValueError, 'archive symbol names'):
                        maintenance.read_regular_archive(path)

    def test_thin_archive_reads_serialized_not_invented_member_order(self):
        path = write(self.base, 'thin.a', thin([('../objects/z.o', b'123'), ('../objects/a.o', b'1')]))
        self.assertEqual(maintenance.read_thin_archive(path),
                         [{'name': '../objects/z.o', 'bytes': 3}, {'name': '../objects/a.o', 'bytes': 1}])
        path.write_bytes(path.read_bytes()[:-2])
        with self.assertRaises(ValueError):
            maintenance.read_thin_archive(path)

    def test_auxiliary_and_response_options_cannot_escape_fixed_recipes(self):
        for arg in ('-o', '-fsyntax-only', '@response', '-MJ/foreign.json', '-fplugin=/foreign.so',
                    '--serialize-diagnostics=/foreign.dia', '-Xclang', '--embed-file=/foreign'):
            with self.subTest(arg=arg), self.assertRaises(ValueError):
                maintenance._arguments([arg])

    def test_foreign_filename_inputs_and_transform_are_rejected_before_plan_or_graph(self):
        selection, original = self.fixture()
        # Independent reproductions from the frozen review plus other operand
        # encodings. These files need not exist: they are outside the grammar.
        cases = [
            (False, ['-include', '/foreign/unpinned.h']),
            (False, ['-I{sources}/../foreign']),
            (False, ['/foreign/extra.cpp']),
            (True, ['--post-js=/foreign/append.js']),
            (True, ['--js-transform=python3 /foreign/transform.py']),
            (True, ['-Wl,--version-script=/foreign/link.script']),
            (False, ['--sysroot=/foreign']),
            (False, ['-isystem', '/foreign']),
            (False, ['-DAPP_HEADER="/foreign/header.h"']),
            (True, ['{reuse}/objects/extra.o']),
            (True, ['-Xlinker', '/foreign/script']),
            (True, ['--post-js', '{sources}/source/pre.js']),
        ]
        for number, (link, arguments) in enumerate(cases):
            changed = copy.deepcopy(original)
            if link:
                changed['link']['flags'].extend(arguments)
            else:
                changed['objects'][0]['arguments'].extend(arguments)
            write(Path(selection['reuse_root']), 'reuse-proof.json', encoded(changed))
            selection['reuse_proof_sha256'] = digest(selection['reuse_proof'])
            output = self.base / ('rejected-plan-' + str(number))
            with self.subTest(arguments=arguments), \
                    mock.patch('subprocess.Popen', side_effect=AssertionError('no programs')), \
                    mock.patch.object(maintenance, '_graph', side_effect=AssertionError('no graph')):
                with self.assertRaises(ValueError):
                    maintenance.make_plan(selection, output)
            self.assertFalse(output.exists())
        with self.assertRaises(ValueError):
            maintenance._expand('-I{sources}/../foreign', {'sources': Path(selection['sources'])}, self.base / 'output')

    def test_admitted_include_directories_bind_their_inventory_to_actual_graph_dependencies(self):
        selection, _ = self.fixture()
        inspected = maintenance.inspect_inputs(selection)
        arguments = ['-std=c++23', '-fexceptions', '-I{sources}/source/selected',
                     '-isystem', '{sdk}/upstream/emscripten', '-I{generated}']
        dependencies = maintenance._arguments(arguments, inspection=inspected)
        selected_file = str(Path(selection['sources']) / 'source/selected/BibEngineWasmShim.cpp')
        sdk_file = str(Path(selection['sdk']) / 'upstream/emscripten/tools/config.py')
        self.assertIn(selected_file, dependencies)
        self.assertIn(sdk_file, dependencies)
        self.assertIn(str(Path(selection['sources']) / 'source/selected'), dependencies)
        inspected.proof['objects'][0]['arguments'] = arguments
        output = self.base / 'graph-inputs'
        (output / 'cmake').mkdir(parents=True)
        path = write(self.base, 'dummy-plan.json', b'{}\n')
        _, fragment, _ = maintenance._graph(inspected, {}, path, digest(path), output)
        graph = fragment.read_text()
        self.assertIn(maintenance._cmake_value(selected_file), graph)
        self.assertIn(maintenance._cmake_value(sdk_file), graph)
        self.assertIn('-I' + str(output / 'copied-generated'), graph)

    def test_official_negative_aliases_and_unapproved_settings_cannot_override_factory_policy(self):
        fixed = maintenance.profile()['link_settings']
        self.assertEqual({name: fixed[name] for name in ('ENVIRONMENT', 'MODULARIZE', 'INVOKE_RUN', 'EXIT_RUNTIME')},
                         {'ENVIRONMENT': 'worker', 'MODULARIZE': '1', 'INVOKE_RUN': '0', 'EXIT_RUNTIME': '0'})
        base = ['--no-entry', '-fexceptions', '-lexports.js', *('-s' + name + '=' + value for name, value in fixed.items())]
        maintenance._arguments(base, link=True)
        for added in (['-sNO_MODULARIZE=1'], ['-sNO_INVOKE_RUN=0'], ['-sNO_EXIT_RUNTIME=0'],
                      ['-s', 'NO_MODULARIZE=1'], ['-sENVIRONMENT=web'],
                      ['-sEXPORTED_FUNCTIONS=_main'], ['-sUSE_PTHREADS=1'],
                      ['-sSHARED_MEMORY=1'], ['-sPRE_JS_FILES=/foreign/file.js'],
                      ['-sJS_TRANSFORM=python3 /foreign/transform.py'], ['-sWASM_ASYNC_COMPILATION=0']):
            with self.subTest(added=added):
                with self.assertRaises(ValueError):
                    maintenance._arguments([*base, *added], link=True)
                with self.assertRaises(ValueError):
                    maintenance._settings([*base, *added])

    def test_raw_wasm_export_preservation_is_required_exactly_once(self):
        config = maintenance.profile()
        valid = ['--no-entry', '-fexceptions', '-lexports.js',
                 *('-s' + name + '=' + value for name, value in config['link_settings'].items())]
        maintenance._arguments(valid, link=True)
        for invalid in ([arg for arg in valid if arg != '-lexports.js'],
                        [*valid, '-lexports.js'], [*valid, '-lexports'],
                        [*valid, '-l', 'exports.js']):
            with self.subTest(arguments=invalid), self.assertRaises(ValueError):
                maintenance._arguments(invalid, link=True)

    def test_raw_export_library_is_link_only_even_in_a_corrupt_compile_profile(self):
        config = copy.deepcopy(maintenance.profile())
        config['compile_literals'].append('-lexports.js')
        with self.assertRaisesRegex(ValueError, 'link-only'):
            maintenance._arguments(['-lexports.js'], inspection=SimpleNamespace(profile=config))

    def test_actual_graph_link_preserves_raw_export_names_once(self):
        selection, _ = self.fixture()
        inspected = maintenance.inspect_inputs(selection)
        output = self.base / 'export-graph'
        (output / 'cmake').mkdir(parents=True)
        _, _, commands = maintenance._graph(inspected, {}, self.base / 'plan.json', '1' * 64, output)
        self.assertEqual(commands['link'].count('-lexports.js'), 1)
        self.assertTrue(all('-lexports.js' not in command for command in commands['objects'].values()))

    def test_exact_retained_helper_closure_can_inspect_factory_in_isolation(self):
        isolated = self.base / 'isolated-retained'
        for name in maintenance.REQUIRED_HELPERS:
            write(isolated, name, (ROOT / name).read_bytes())
        self.assertTrue((isolated / 'tools/browser_bundle.py').is_file())
        program = '''import json, pathlib, sys
root = pathlib.Path(sys.argv[1])
sys.path.insert(0, str(root / 'tools'))
import appended_engine_maintenance
import appended_engine_consumer as consumer
facts = consumer.scan_factory(b'export default function createFoundationRetainedEngine() {}')
import browser_bundle
assert pathlib.Path(browser_bundle.__file__).is_relative_to(root)
assert all('software-foundation/tools' not in entry for entry in sys.path[1:])
print(json.dumps(facts, sort_keys=True))
'''
        result = subprocess.run([str(Path(sys.executable).resolve()), '-I', '-B', '-c', program, str(isolated)],
                                cwd=self.base, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {'module_dependencies': [], 'default_export': True, 'import_meta_url': False})
        self.assertFalse((isolated / 'tools/__pycache__').exists())

    def test_supervisor_success_finishes_and_closes_before_log_receipt(self):
        calls = []
        owner = SimpleNamespace(wait=lambda timeout: calls.append('wait') or 0,
            finish=lambda: calls.append('finish') or 0, close=lambda: calls.append('close'),
            terminate=lambda: calls.append('terminate'))
        with mock.patch.object(maintenance.process_tree, 'launch', side_effect=lambda *a, **k: calls.append('launch') or owner):
            result = maintenance._supervise(['/fixed/tool'], self.base, self.base / 'log', {}, 2)
        self.assertEqual(calls, ['launch', 'wait', 'finish', 'close'])
        self.assertTrue(result['writers_finished'])

    def test_supervisor_failure_never_returns_completed_evidence(self):
        for failure in ('nonzero', 'timeout', 'finish', 'close'):
            calls = []
            def wait(timeout):
                calls.append('wait')
                if failure == 'timeout':
                    raise subprocess.TimeoutExpired('fixture', timeout)
                return 3 if failure == 'nonzero' else 0
            def finish():
                calls.append('finish')
                if failure == 'finish':
                    raise ValueError('uncertain writers')
            def close():
                calls.append('close')
                if failure == 'close':
                    raise ValueError('uncertain close')
            owner = SimpleNamespace(wait=wait, finish=finish, close=close,
                                    terminate=lambda: calls.append('terminate'))
            with self.subTest(failure=failure), mock.patch.object(maintenance.process_tree, 'launch', return_value=owner):
                with self.assertRaises((ValueError, subprocess.TimeoutExpired)):
                    maintenance._supervise(['/fixed/tool'], self.base, self.base / ('log-' + failure), {}, 2)
            self.assertIn('close', calls)
            if failure in ('timeout', 'finish'):
                self.assertIn('terminate', calls)

    def test_recursive_python_BE_survives_sdk_normalization_and_descendant_E(self):
        synthetic = self.base / 'fake SDK with spaces'
        synthetic.mkdir()
        parent = write(synthetic, 'em++.py', b'''import os, sys, subprocess, json
import marker
os.environ['EMSDK_PYTHON'] = sys.executable
subprocess.check_call([os.path.join(os.path.dirname(__file__), 'file_packager'), *sys.argv[1:]])
''')
        child = write(synthetic, 'file_packager.py', b'''import sys, json
import marker
print(json.dumps({'executable':sys.executable,'B':sys.flags.dont_write_bytecode,
'dont':sys.dont_write_bytecode,'E':sys.flags.ignore_environment,'args':sys.argv[1:],'marker':marker.VALUE}))
''')
        write(synthetic, 'marker.py', b'VALUE = 17\n')
        packager = write(synthetic, 'file_packager', b'#!/bin/sh\nexec "$EMSDK_PYTHON" -E "$0.py" "$@"\n', 0o755)
        hostile = self.base / 'hostile'
        sentinel = self.base / 'sitecustomize-ran'
        write(hostile, 'sitecustomize.py', ('open(' + repr(str(sentinel)) + ',"w").write("bad")\n').encode())
        launcher = maintenance.python_launcher(Path(sys.executable).resolve(), [parent, child], self.base / 'sdk-python')
        environment = dict(os.environ, EMSDK_PYTHON=str(launcher), PYTHONPATH=str(hostile), PYTHONDONTWRITEBYTECODE='0')
        result = subprocess.run([str(launcher), '-B', '-E', str(parent), 'argument with spaces', '-unchanged'],
            cwd=self.base, env=environment, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        value = json.loads(result.stdout)
        self.assertEqual(value, {'executable': str(launcher), 'B': 1, 'dont': True, 'E': 1,
            'args': ['argument with spaces', '-unchanged'], 'marker': 17})
        self.assertFalse((synthetic / '__pycache__').exists())
        self.assertFalse((hostile / '__pycache__').exists())
        self.assertFalse(sentinel.exists())
        for arguments in (['-c', 'pass'], ['-m', 'os'], ['-I', str(parent)], [str(synthetic / 'unselected.py')]):
            bad = subprocess.run([str(launcher), *arguments], env=environment,
                                 capture_output=True, text=True, timeout=10)
            self.assertNotEqual(bad.returncode, 0)

    def test_internal_step_refuses_unowned_or_overlapping_output(self):
        root = self.base / 'input'
        root.mkdir()
        plan = {'kind': maintenance.PLAN_KIND, 'production_eligible': False, 'reuse': {},
                'selection': {'sources': str(root), 'sdk': str(self.base / 'sdk'), 'reuse_root': str(self.base / 'reuse')}}
        path = write(self.base, 'plan.json', encoded(plan))
        args = SimpleNamespace(plan=path, plan_sha256=digest(path), build_root=root, action='artifacts')
        with self.assertRaisesRegex(ValueError, 'overlaps'):
            maintenance._step(args)

    def test_maintained_graph_uses_only_explicit_nodes_and_declares_readback(self):
        value = (ROOT / maintenance.GRAPH_PATH).read_text()
        self.assertIn('LANGUAGES NONE', value)
        self.assertIn('foundation-neutral-engine', value)
        self.assertIn('ENGINE_ARCHIVE_${_name}_REPORT', value)
        self.assertNotIn('add_subdirectory(', value)
        self.assertNotIn('find_package(', value)
        for invalid in ('semi;colon', 'line\nbreak'):
            with self.assertRaises(ValueError):
                maintenance._cmake_value(invalid)

    def test_tiny_actual_cmake_graph_has_no_default_build_and_rebuilds_missing_readback(self):
        # This invokes only an inert two-object fixture. No engine, SDK driver,
        # compiler, archive implementation or vendor graph participates.
        cmake, ninja = shutil.which('cmake'), shutil.which('ninja')
        if not cmake or not ninja:
            self.skipTest('documented CMake/Ninja host prerequisites unavailable')
        output = self.base / 'tiny-graph'
        output.mkdir()
        script = write(output, 'fake.py', b'''import sys
from pathlib import Path
mode, log, *outputs = sys.argv[1:]
with open(log, 'a') as stream: stream.write(mode + '\\n')
for name in outputs:
    p = Path(name); p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(str(p.with_suffix('.o')) + ':\\n' if name.endswith('.d') else 'inert fixture\\n')
''')
        log = output / 'actions'
        python = str(Path(sys.executable).resolve())
        def command(mode, *paths):
            return [python, '-BE', str(script), mode, str(log), *map(str, paths)]
        settings = {'FOUNDATION_ENGINE_GRAPH_VERSION': ['1'], 'ENGINE_OBJECT_IDS': ['one', 'two'],
                    'ENGINE_ARCHIVE_NAMES': ['Tiny']}
        header_file, build_file = output / 'header', output / 'provider-build'
        settings.update(ENGINE_HEADER=[header_file], ENGINE_PROVIDER_BUILD=[build_file],
            ENGINE_METADATA_COMMAND=command('metadata', header_file, build_file), ENGINE_METADATA_DEPENDS=[script])
        for name in ('one', 'two'):
            obj, dep = output / (name + '.o'), output / (name + '.d')
            settings['ENGINE_OBJECT_' + name + '_OUTPUT'] = [obj]
            settings['ENGINE_OBJECT_' + name + '_DEPFILE'] = [dep]
            settings['ENGINE_OBJECT_' + name + '_COMMAND'] = command('compile-' + name, obj, dep)
            settings['ENGINE_OBJECT_' + name + '_DEPENDS'] = [script]
        archive, report = output / 'tiny.a', output / 'readback.json'
        settings.update(ENGINE_ARCHIVE_Tiny_OUTPUT=[archive], ENGINE_ARCHIVE_Tiny_REPORT=[report],
            ENGINE_ARCHIVE_Tiny_COMMAND=command('archive', archive), ENGINE_ARCHIVE_Tiny_INDEX=command('index'),
            ENGINE_ARCHIVE_Tiny_READBACK=command('readback', report),
            ENGINE_ARCHIVE_Tiny_DEPENDS=[output / 'one.o', output / 'two.o'])
        factory, wasm, linkmap, inspected = [output / name for name in ('factory.mjs', 'engine.wasm', 'link.map', 'inspected.json')]
        settings.update(ENGINE_FACTORY=[factory], ENGINE_WASM=[wasm], ENGINE_MAP=[linkmap],
            ENGINE_LINK_COMMAND=command('link', factory, wasm, linkmap), ENGINE_LINK_DEPENDS=[script],
            ENGINE_INSPECTION=[inspected], ENGINE_INSPECT_COMMAND=command('inspect', inspected), ENGINE_INSPECT_DEPENDS=[script])
        fragment = write(output, 'input.cmake', ''.join('set(' + name + ''.join('\n ' + maintenance._cmake_value(value)
            for value in values) + ')\n' for name, values in settings.items()).encode())
        build = output / 'build'
        def run(arguments):
            value = subprocess.run(arguments, cwd=output, capture_output=True, text=True, timeout=20)
            self.assertEqual(value.returncode, 0, value.stdout + value.stderr)
        run([cmake, '-S', str(ROOT / Path(maintenance.GRAPH_PATH).parent), '-B', str(build), '-G', 'Ninja',
             '-DCMAKE_MAKE_PROGRAM=' + ninja, '-DFOUNDATION_ENGINE_PLAN=' + str(fragment)])
        run([cmake, '--build', str(build)])
        self.assertFalse(log.exists())
        run([cmake, '--build', str(build), '--target', 'foundation-neutral-engine', '--parallel', '2'])
        original = log.read_text().splitlines()
        self.assertEqual(sorted(original), sorted(['metadata', 'compile-one', 'compile-two', 'archive', 'index', 'readback', 'link', 'inspect']))
        run([cmake, '--build', str(build), '--target', 'foundation-neutral-engine'])
        self.assertEqual(log.read_text().splitlines(), original)
        report.unlink()
        run([cmake, '--build', str(build), '--target', 'foundation-neutral-engine'])
        self.assertEqual(log.read_text().splitlines()[len(original):], ['archive', 'index', 'readback', 'link', 'inspect'])


if __name__ == '__main__':
    unittest.main()
