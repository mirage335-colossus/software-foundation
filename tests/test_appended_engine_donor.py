"""Inert retained-object provenance fixtures; no SDK or compiler is executed."""
import copy
import hashlib
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(ROOT / 'tests'))
import appended_engine_donor as donor
import appended_engine_maintenance as maintenance
import test_appended_engine_maintenance as baseline
from dependency_archive import digest, encoded


class DonorFixture:
    """Synthetic historical declarations are fixtures, never real build evidence."""
    def __init__(self, case):
        helper = baseline.MaintenanceTests(methodName='runTest')
        helper.setUp()
        case.addCleanup(helper.doCleanups)
        self.base = helper.base
        selection, proof = helper.fixture()
        self.sources = Path(selection['sources'])
        self.reuse = Path(selection['reuse_root'])
        self.recipe = maintenance.checked_document(self.sources / 'recipe.json')
        for name in ('source/include-common/used.h', 'source/include-common/alias.h',
                     'observed-inputs/absolute.h'):
            self.retain_source(name, b'// inert dependency fixture\n')
        baseline.write(self.reuse, 'headers/reused.h', b'// inert reused header\n')
        for obj in proof['objects']:
            obj['arguments'] += ['-I{sources}/source/include-common', '-isystem', '{reuse}/headers']
        self.seal_sources(selection)
        proof['inventory'] = maintenance.manifest.tree_inventory(self.reuse, 'reuse-proof.json')
        baseline.write(self.reuse, 'reuse-proof.json', encoded(proof))
        selection['reuse_proof_sha256'] = digest(self.reuse / 'reuse-proof.json')
        self.inspection = maintenance.inspect_inputs(selection)
        self.build = self.base / 'historical-build'
        self.old_roots = {'sources': self.base / 'historical-sources',
                          'reuse': self.base / 'historical-reuse',
                          'sdk': self.inspection.roots['sdk']}
        self.old_profile = copy.deepcopy(self.inspection.profile)
        self.old_profile['link_literals'].remove('-lexports.js')
        self.old_recipe = copy.deepcopy(self.recipe)
        self.old_recipe['inputs'].pop('tools/appended_engine_donor.py')
        self.old_manifest = maintenance.checked_document(self.sources / 'sources.json')
        self.old_manifest['files'].pop('tools/appended_engine_donor.py')
        self.old_manifest['modes'].pop('tools/appended_engine_donor.py')
        self.old_helper = (self.sources / maintenance.SELF_PATH).read_bytes()
        self.old_sdk = maintenance.checked_document(self.inspection.roots['sdk'] / 'sdk.json')
        old_selection = copy.deepcopy(selection)
        old_selection.update(sources=str(self.old_roots['sources']),
            reuse_root=str(self.old_roots['reuse']),
            reuse_proof=str(self.old_roots['reuse'] / 'reuse-proof.json'),
            projection=str(self.old_roots['sources'] / 'provenance/source-projection.json'))
        old_proof = copy.deepcopy(self.inspection.proof)
        old_proof['link']['flags'].remove('-lexports.js')
        self.old = {'schema_version': 1, 'kind': maintenance.PLAN_KIND, 'scope': maintenance.SCOPE,
            'selection': old_selection, 'profile_sha256': '', 'producer_inputs': {},
            'reuse': old_proof, 'projection': copy.deepcopy(self.inspection.projection),
            'production_eligible': False}
        self.old_view = self.view(self.old_roots)
        self.current_view = self.view(self.inspection.roots)
        self.commands = {'metadata': ['inert-fixture-metadata-not-executed'], 'objects': {},
                         'link': ['inert-fixture-link-not-executed']}
        self.depfiles, self.object_bytes = {}, {}
        for obj in old_proof['objects']:
            target = self.build / ('objects/' + obj['id'] + '.o')
            self.commands['objects'][obj['id']] = [
                str(self.old_roots['sdk'] / old_proof['sdk_tools']['emxx']['path']),
                '-ivfsoverlay', str(self.build / 'private/header-identity-vfs.json'),
                *(maintenance._expand(arg, self.old_roots, self.build) for arg in obj['arguments']),
                '-MD', '-MT', str(target), '-MF', str(target) + '.d', '-o', str(target),
                '-c', str(self.old_roots['sources'] / obj['source']['path'])]
            names = [str(self.old_roots['sources'] / obj['source']['path']),
                # An absolute include is a positive dependency outside the
                # selected source/include-search top-level namespace.
                str(self.old_roots['sources'] / 'observed-inputs/absolute.h'),
                str(self.old_roots['reuse'] / 'headers/reused.h'),
                str(self.build / 'private/cache/syslib.a')]
            self.depfiles[obj['id']] = (str(target) + ': ' + ' '.join(names) + '\n').encode()
            self.object_bytes[obj['id']] = ('inert object ' + obj['id'] + '\n').encode()
        self.ninja_header = '# ninja log v6'
        self.completed = [str(self.build / ('objects/' + obj['id'] + '.o'))
                          for obj in old_proof['objects']]
        self.completed += [str(self.build / name) for name in (
            'copied-generated/BibCopiedMetadata.generated.h', 'copied-generated/provider-build.json',
            'artifacts/foundation-retained-engine.mjs', 'artifacts/foundation-retained-engine.wasm',
            'evidence/engine-link.map')]
        for archive in old_proof['archives']:
            self.completed += [str(self.build / ('archives/lib' + archive['name'] + '.a')),
                               str(self.build / ('evidence/archive-' + archive['name'] + '.json'))]
        self.build_log = (b'FAILED: evidence/artifact-inspection.json\n'
                          b'Actual factory lacks required copied exports\n')
        self.closure = self.closed(False)
        self.postverify = self.closed(True)
        self.freeze = {'schema_version': 1, 'status': donor.STATUS, 'production_eligible': False,
            'runtime_not_run': True, 'cause': 'Synthetic fixture only, no engine executed',
            'utc': '2000-01-01T00:00:00Z', 'compiled_objects': 24, 'archive_readbacks': 5,
            'files': []}
        self.originals = {'plan': self.base / 'historical-plan/plan.json',
            'owner': self.build / 'maintenance-owner.json',
            'commands': self.build / 'evidence/commands.json',
            'source_recipe': self.old_roots['sources'] / 'recipe.json',
            'source_manifest': self.old_roots['sources'] / 'sources.json',
            'sdk_manifest': self.old_roots['sdk'] / 'sdk.json',
            'helper': self.old_roots['sources'] / maintenance.SELF_PATH,
            'profile': self.old_roots['sources'] / maintenance.PROFILE_PATH,
            'vfs': self.build / 'private/header-identity-vfs.json',
            'config': self.build / 'private/emscripten-config.py',
            'launcher': self.build / 'private/sdk-python',
            'ninja_log': self.build / 'cmake/build/.ninja_log',
            'build_log': self.build / 'logs/build.log',
            'closure': self.base / 'historical-review/RESULT.json',
            'postverify': self.base / 'historical-postverify/RESULT.json',
            'freeze': self.base / 'historical-review/FAILURE-FREEZE.json'}
        self.record = {'schema_version': 1, 'kind': donor.KIND, 'scope': maintenance.SCOPE,
            'profile': selection['profile'], 'evidence': {},
            'environment_policy': 'original-sanitized-construction-values-unrecorded-v1',
            'objects': [{'id': obj['id']} for obj in old_proof['objects'] if obj['id'] != donor.SHIM]}
        self.raw_overrides = {}
        self.save()

    @staticmethod
    def closed(passed):
        code = 0 if passed else 1
        return {'status': 'passed' if passed else 'failed', 'closed': True, 'returncode': code,
            'deadline_exceeded': False, 'seconds': 1.0,
            'supervisor_report': {'descendants_outlived': False, 'error': None,
                'primary_returncode': code, 'terminated': False}}

    @staticmethod
    def view(roots):
        return {'version': 0, 'case-sensitive': True, 'use-external-names': False,
            'overlay-relative': False, 'fallthrough': True, 'roots': [{'type': 'file',
                'name': str(roots['sources'] / 'source/include-common/alias.h'),
                'external-contents': str(roots['sources'] / 'source/include-common/used.h')}]}

    def retain_source(self, name, raw):
        baseline.write(self.sources, name, raw)
        self.recipe['inputs'][name] = {'sha256': hashlib.sha256(raw).hexdigest(),
                                       'role': 'source', 'mode': 0o644}

    def seal_sources(self, selection=None):
        selection = self.inspection.selection if selection is None else selection
        baseline.write(self.sources, 'recipe.json', encoded(self.recipe))
        source_manifest = {'schema_version': 1, 'kind': 'foundation-appended-engine-sources',
            'producer_version': 1, 'recipe_id': digest(self.sources / 'recipe.json'),
            **maintenance.manifest.tree_inventory(self.sources, 'sources.json')}
        baseline.write(self.sources, 'sources.json', encoded(source_manifest))
        selection.update(recipe_sha256=source_manifest['recipe_id'],
                         sources_sha256=digest(self.sources / 'sources.json'))
        if hasattr(self, 'inspection'):
            self.inspection.inventories['sources'] = source_manifest['files']
            self.inspection.recipe.clear()
            self.inspection.recipe.update(copy.deepcopy(self.recipe))

    def ref(self, name, raw):
        path = baseline.write(self.reuse, 'completed-donor/' + name, raw)
        return {'root': 'reuse', 'path': path.relative_to(self.reuse).as_posix(), 'sha256': digest(path)}

    def save(self):
        for name, raw in ((maintenance.SELF_PATH, self.old_helper),
                          (maintenance.PROFILE_PATH, encoded(self.old_profile))):
            pin = hashlib.sha256(raw).hexdigest()
            self.old_recipe['inputs'][name]['sha256'] = pin
            self.old_manifest['files'][name] = pin
        recipe_raw = encoded(self.old_recipe)
        self.old_manifest['recipe_id'] = hashlib.sha256(recipe_raw).hexdigest()
        self.old_manifest['files']['recipe.json'] = self.old_manifest['recipe_id']
        manifest_raw = encoded(self.old_manifest)
        self.old['selection'].update(recipe_sha256=self.old_manifest['recipe_id'],
            sources_sha256=hashlib.sha256(manifest_raw).hexdigest(),
            sdk_manifest_sha256=hashlib.sha256(encoded(self.old_sdk)).hexdigest())
        self.old['profile_sha256'] = hashlib.sha256(encoded(self.old_profile)).hexdigest()
        self.old['producer_inputs'] = {name: self.old_manifest['files'][name]
            for name in maintenance.REQUIRED_HELPERS if name != 'tools/appended_engine_donor.py'}
        plan_raw = encoded(self.old)
        owner = {'schema_version': 1, 'plan_sha256': hashlib.sha256(plan_raw).hexdigest(),
            'output': str(self.build), 'producer_sha256': hashlib.sha256(self.old_helper).hexdigest()}
        config = ''.join(key + ' = ' + repr(str(self.old_roots['sdk'] / name)) + '\n'
            for key, name in sorted(self.old['reuse']['emscripten_config'].items()))
        config += 'CACHE = ' + repr(str(self.build / 'private/cache')) + '\nFROZEN_CACHE = True\n'
        launcher = self.build / 'private/sdk-python'
        launcher.parent.mkdir(parents=True, exist_ok=True)
        maintenance.python_launcher(self.old['reuse']['host_tools']['python']['path'],
            [self.old_roots['sdk'] / name for name in self.old_profile['python_entrypoints']], launcher)
        ninja_log = self.ninja_header + '\n' + ''.join('0\t1\t1\t' + name + '\tabc123\n'
                                                for name in self.completed)
        raw = {'plan': plan_raw, 'owner': encoded(owner), 'commands': encoded(self.commands),
            'source_recipe': recipe_raw, 'source_manifest': manifest_raw,
            'sdk_manifest': encoded(self.old_sdk), 'helper': self.old_helper,
            'profile': encoded(self.old_profile), 'vfs': encoded(self.old_view),
            'config': config.encode(), 'launcher': launcher.read_bytes(),
            'ninja_log': ninja_log.encode(), 'build_log': self.build_log,
            'closure': encoded(self.closure), 'postverify': encoded(self.postverify)}
        raw.update(self.raw_overrides)
        frozen = []
        for key in ('commands', 'ninja_log', 'build_log', 'closure', 'postverify'):
            frozen.append(self.frozen(self.originals[key], raw[key]))
        for obj in self.old['reuse']['objects']:
            name = obj['id']
            target = self.build / ('objects/' + name + '.o')
            frozen += [self.frozen(target, self.object_bytes[name]),
                       self.frozen(Path(str(target) + '.d'), self.depfiles[name])]
        self.freeze['files'] = frozen
        raw['freeze'] = encoded(self.freeze)
        self.record['evidence'] = {key: {'input': self.ref('evidence/' + key, raw[key]),
            'original_path': str(self.originals[key])} for key in donor.EVIDENCE}
        for item in self.record['objects']:
            name = item['id']
            item.update(object=self.ref('objects/' + name + '.o', self.object_bytes[name]),
                        depfile=self.ref('objects/' + name + '.o.d', self.depfiles[name]))
        reference = self.ref('record.json', encoded(self.record))
        self.inspection.proof['completed_objects'] = reference
        inventory = maintenance.manifest.tree_inventory(self.reuse, 'reuse-proof.json')
        self.inspection.proof['inventory'] = inventory
        self.inspection.inventories['reuse'] = inventory['files']
        baseline.write(self.reuse, 'reuse-proof.json', encoded(self.inspection.proof))
        self.inspection.selection['reuse_proof_sha256'] = digest(self.reuse / 'reuse-proof.json')

    @staticmethod
    def frozen(path, raw):
        return {'path': str(path), 'sha256': hashlib.sha256(raw).hexdigest(),
                'bytes': len(raw), 'mode': 0o644}

    def validate(self):
        with mock.patch.object(maintenance, '_header_identity',
                               return_value={'overlay': self.current_view}), \
             mock.patch('subprocess.Popen', side_effect=AssertionError('No programs in donor validation')):
            return donor.validate(self.inspection, api=maintenance)

    def graph_scope(self, label='first'):
        output = self.base / ('new-output-' + label)
        for name in ('cmake', 'evidence', 'objects'):
            (output / name).mkdir(parents=True)
        plan_dir = self.base / ('new-plan-' + label)
        plan_dir.mkdir()
        plan = {'schema_version': 1, 'kind': maintenance.PLAN_KIND, 'scope': maintenance.SCOPE,
            'selection': self.inspection.selection, 'reuse': self.inspection.proof,
            'profile_sha256': digest(ROOT / maintenance.PROFILE_PATH),
            'producer_inputs': {name: digest(ROOT / name) for name in maintenance.REQUIRED_HELPERS},
            'projection': self.inspection.projection, 'production_eligible': False}
        plan_path = baseline.write(plan_dir, 'plan.json', encoded(plan))
        plan_hash = digest(plan_path)
        baseline.write(output, 'maintenance-owner.json', encoded({'schema_version': 1,
            'plan_sha256': plan_hash, 'output': str(output),
            'producer_sha256': digest(ROOT / maintenance.SELF_PATH)}))
        with mock.patch.object(maintenance, '_header_identity',
                               return_value={'overlay': self.current_view, 'dependencies': []}), \
             mock.patch('subprocess.Popen', side_effect=AssertionError('No graph programs')):
            _, fragment, commands = maintenance._graph(self.inspection, plan, plan_path, plan_hash, output)
        return output, plan_path, plan_hash, fragment, commands


class DonorTests(unittest.TestCase):
    def setUp(self):
        self.fixture = DonorFixture(self)

    def test_complete_original_context_admits_only_23_metadata_independent_objects(self):
        f = self.fixture
        value = f.validate()
        self.assertEqual(len(value['objects']), 23)
        self.assertNotIn(donor.SHIM, value['objects'])
        self.assertEqual(list(value['objects']), [obj['id'] for obj in f.old['reuse']['objects']
                                                 if obj['id'] != donor.SHIM])
        for name, item in value['objects'].items():
            self.assertEqual(item['object'].read_bytes(), f.object_bytes[name])
            self.assertEqual(item['provenance']['original_argv'], f.commands['objects'][name])
            self.assertEqual(item['provenance']['environment_policy'], f.record['environment_policy'])
            self.assertEqual(item['provenance']['failed_predecessor_status'], donor.STATUS)

    def test_no_donor_is_an_explicit_ordinary_build(self):
        self.fixture.inspection.proof.pop('completed_objects')
        self.assertIsNone(self.fixture.validate())

    def test_original_ninja_v5_completion_ledger_remains_accepted(self):
        f = self.fixture
        f.ninja_header = '# ninja log v5'
        f.save()
        self.assertEqual(len(f.validate()['objects']), 23)

    def test_unknown_ninja_v7_completion_ledger_is_rejected(self):
        f = self.fixture
        f.ninja_header = '# ninja log v7'
        f.save()
        with self.assertRaisesRegex(ValueError, 'Unsupported donor completion ledger'):
            f.validate()

    def test_explicit_null_donor_cannot_select_the_ordinary_build_route(self):
        self.fixture.inspection.proof['completed_objects'] = None
        with self.assertRaisesRegex(ValueError, 'Invalid completed-object donor reference fields'):
            self.fixture.validate()

    def test_shim_cannot_be_imported_even_with_complete_frozen_object(self):
        f = self.fixture
        f.record['objects'].append({'id': donor.SHIM})
        f.save()
        with self.assertRaisesRegex(ValueError, 'exact 23'):
            f.validate()

    def test_missing_or_reordered_donor_is_rejected(self):
        f = self.fixture
        f.record['objects'].reverse()
        f.save()
        with self.assertRaisesRegex(ValueError, 'exact 23'):
            f.validate()

    def test_re_pinned_actual_compiler_argv_change_is_rejected(self):
        f = self.fixture
        f.commands['objects'][f.record['objects'][0]['id']].insert(1, '-DUNRECORDED=1')
        f.save()
        with self.assertRaisesRegex(ValueError, 'actual compiler argv'):
            f.validate()

    def test_changed_current_compile_recipe_cannot_reuse_old_object(self):
        f = self.fixture
        f.inspection.proof['objects'][0]['arguments'].append('-DNDEBUG')
        f.save()
        with self.assertRaisesRegex(ValueError, 'context differs beyond'):
            f.validate()

    def test_changed_observed_header_is_rejected_after_current_source_resealing(self):
        f = self.fixture
        f.retain_source('observed-inputs/absolute.h', b'// changed header\n')
        f.seal_sources()
        with self.assertRaisesRegex(ValueError, 'observed source/header dependency changed'):
            f.validate()

    def test_new_include_shadow_file_is_rejected_without_changing_positive_depfile(self):
        f = self.fixture
        f.retain_source('source/include-common/new-shadow.h', b'// new namespace entry\n')
        f.seal_sources()
        with self.assertRaisesRegex(ValueError, 'complete include-search namespace changed'):
            f.validate()

    def test_changed_sdk_namespace_cannot_keep_old_donor(self):
        f = self.fixture
        sdk = f.inspection.roots['sdk']
        baseline.write(sdk, 'new-shadow.h', b'// changed SDK namespace\n')
        current = maintenance.checked_document(sdk / 'sdk.json')
        current['files']['new-shadow.h'] = digest(sdk / 'new-shadow.h')
        baseline.write(sdk, 'sdk.json', encoded(current))
        pin = digest(sdk / 'sdk.json')
        f.inspection.inventories['sdk'] = current['files']
        f.inspection.selection['sdk_manifest_sha256'] = pin
        f.inspection.proof['paired_sdk_sha256'] = pin
        f.recipe['toolchain']['paired_sdk_sha256'] = pin
        f.seal_sources()
        with self.assertRaisesRegex(ValueError, 'complete paired SDK namespace differs'):
            f.validate()

    def test_changed_vfs_semantics_are_rejected_even_for_equal_header_bytes(self):
        f = self.fixture
        f.old_view['use-external-names'] = True
        f.save()
        with self.assertRaisesRegex(ValueError, 'VFS alias semantics differ'):
            f.validate()

    def test_re_pinned_original_closure_with_outliving_descendants_is_rejected(self):
        f = self.fixture
        f.closure['supervisor_report']['descendants_outlived'] = True
        f.save()
        with self.assertRaisesRegex(ValueError, 'did not close cleanly'):
            f.validate()

    def test_re_pinned_postverify_failure_is_rejected(self):
        f = self.fixture
        f.postverify['returncode'] = 1
        f.save()
        with self.assertRaisesRegex(ValueError, 'did not close cleanly'):
            f.validate()

    def test_re_pinned_helper_environment_construction_change_is_rejected(self):
        f = self.fixture
        old = b"keep = ('LANG', 'LC_ALL', 'TZ', 'SYSTEMROOT', 'WINDIR')"
        self.assertIn(old, f.old_helper)
        f.old_helper = f.old_helper.replace(old,
            b"keep = ('LANG', 'LC_ALL', 'TZ', 'SYSTEMROOT', 'WINDIR', 'CXXFLAGS')", 1)
        f.save()
        with self.assertRaisesRegex(ValueError, 'environment/launcher/expansion/VFS construction changed'):
            f.validate()

    def test_unknown_historical_environment_policy_is_not_an_equivalence_claim(self):
        f = self.fixture
        f.record['environment_policy'] = 'assumed-identical'
        f.save()
        with self.assertRaisesRegex(ValueError, 'limited donor environment provenance'):
            f.validate()

    def test_re_pinned_depfile_make_expansion_is_rejected(self):
        f = self.fixture
        name = f.record['objects'][0]['id']
        f.depfiles[name] = f.depfiles[name].replace(b': ', b': $(UNTRUSTED) ', 1)
        f.save()
        with self.assertRaisesRegex(ValueError, 'Make expansion'):
            f.validate()

    def test_re_pinned_depfile_with_wrong_target_is_rejected(self):
        f = self.fixture
        name = f.record['objects'][0]['id']
        f.depfiles[name] = f.depfiles[name].replace(name.encode() + b'.o:', b'wrong.o:', 1)
        f.save()
        with self.assertRaisesRegex(ValueError, 'target differs'):
            f.validate()

    def test_missing_archive_readback_completion_is_not_a_full_closed_graph(self):
        f = self.fixture
        f.completed.remove(str(f.build / 'evidence/archive-WebCore.json'))
        f.save()
        with self.assertRaisesRegex(ValueError, 'exact completed metadata/archive/link graph'):
            f.validate()

    def test_build_failure_before_final_export_scan_is_not_an_admitted_donor(self):
        f = self.fixture
        f.build_log = b'FAILED: objects/anything.o\ncompiler failure\n'
        f.save()
        with self.assertRaisesRegex(ValueError, 'specific final raw-export inspection'):
            f.validate()

    def test_graph_emits_23_checked_imports_and_only_one_real_compile_command(self):
        f = self.fixture
        output, _, _, fragment, commands = f.graph_scope()
        imported, compiled = [], []
        for name, argv in commands['objects'].items():
            if '--action' in argv and argv[argv.index('--action') + 1] == 'donor':
                imported.append(name)
                self.assertIn('--admission-sha256', argv)
            else:
                compiled.append(name)
                self.assertEqual(argv[0], str(f.inspection.roots['sdk'] /
                    f.inspection.proof['sdk_tools']['emxx']['path']))
        self.assertEqual(len(imported), 23)
        self.assertEqual(compiled, [donor.SHIM])
        self.assertIn('ENGINE_OBJECT_o0_COMMAND', fragment.read_text())
        admission = maintenance.checked_document(output / 'evidence/completed-object-admission.json')
        self.assertEqual(set(admission['objects']), set(imported))

    def test_internal_import_copies_an_ordinary_object_and_writes_fresh_readback(self):
        f = self.fixture
        output, plan_path, plan_hash, _, _ = f.graph_scope()
        name = f.record['objects'][0]['id']
        admission = output / 'evidence/completed-object-admission.json'
        args = SimpleNamespace(plan=plan_path, plan_sha256=plan_hash, build_root=output,
            action='donor', object=name, admission_sha256=digest(admission))
        with mock.patch('subprocess.Popen', side_effect=AssertionError('No import programs')):
            report = maintenance._step(args)
        source = f.reuse / f.record['objects'][0]['object']['path']
        target = output / ('objects/' + name + '.o')
        self.assertEqual(target.read_bytes(), source.read_bytes())
        self.assertNotEqual((target.stat().st_dev, target.stat().st_ino),
                            (source.stat().st_dev, source.stat().st_ino))
        self.assertEqual(target.stat().st_mode & 0o777, 0o644)
        dep_target, dependencies = donor.depfile(Path(str(target) + '.d').read_bytes())
        self.assertEqual(dep_target, str(target))
        self.assertEqual(dependencies, [str(source)])
        self.assertIs(report['compiler_executed'], False)
        self.assertEqual(report['sha256'], digest(source))
        self.assertEqual(report, maintenance.checked_document(output / ('evidence/donor-' + name + '.json')))

    def test_internal_import_rejects_changed_admission_or_object_pin_before_output(self):
        f = self.fixture
        name = f.record['objects'][0]['id']
        for mutation in ('admission', 'object-pin'):
            output, plan_path, plan_hash, _, _ = f.graph_scope(mutation)
            admission = output / 'evidence/completed-object-admission.json'
            args = SimpleNamespace(plan=plan_path, plan_sha256=plan_hash, build_root=output,
                action='donor', object=name, admission_sha256=digest(admission))
            if mutation == 'admission':
                admission.write_bytes(admission.read_bytes() + b'\n')
            else:
                (f.reuse / f.record['objects'][0]['object']['path']).write_bytes(b'changed donor object')
            with self.subTest(mutation=mutation), \
                 mock.patch('subprocess.Popen', side_effect=AssertionError('No import programs')), \
                 self.assertRaises(ValueError):
                maintenance._step(args)
            self.assertFalse((output / ('objects/' + name + '.o')).exists())
            self.assertFalse((output / ('evidence/donor-' + name + '.json')).exists())


class DependencyGrammarTests(unittest.TestCase):
    def test_exact_single_rule_preserves_escaped_paths_and_literal_dollar(self):
        raw = b'/tmp/object.o: /tmp/source\\ file.cpp ' + bytes((92, 10)) + b' /tmp/header$$literal.h\n'
        target, names = donor.depfile(raw)
        self.assertEqual(target, '/tmp/object.o')
        self.assertEqual(names, ['/tmp/source file.cpp', '/tmp/header$literal.h'])

    def test_make_expansions_multiple_targets_and_comments_are_rejected(self):
        for raw in (b'/tmp/a.o: $(shell echo broken)\n', b'/tmp/a.o /tmp/b.o: /tmp/a.cpp\n',
                    b'/tmp/a.o: /tmp/a.cpp # comment\n', b'/tmp/a.o: /tmp/a.cpp\n/tmp/b.o: /tmp/b.cpp\n',
                    b'/tmp/a.o: /tmp/a.cpp /tmp/a.cpp\n', b'/tmp/a.o: relative.cpp\n'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                donor.depfile(raw)


if __name__ == '__main__':
    unittest.main()
