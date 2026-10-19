"""Successful donor admission and continuation accounting, using inert fixtures.

Every authority/product in these tests is fabricated or created under an owned
TemporaryDirectory. No retained input, SDK, engine program or real archive is
read. The actual maintained producer and successful-donor helper are tested.
"""
import ast
from contextlib import ExitStack
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import stat
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / 'fixtures/appended_engine_successful_donor'
CONTRACT = json.loads((FIXTURES / 'fixture_contract.json').read_text())
SOURCE = ROOT / 'tools/appended_engine_document_maintenance.py'
HELPER = ROOT / 'tools/appended_engine_successful_donor.py'

def load_shape():
    tree = ast.parse(SOURCE.read_text())
    nodes = [node for node in tree.body if
             isinstance(node, ast.FunctionDef) and node.name == "_completed_shape" or
             isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and
                 target.id == "COMPLETED_DIRECT" for target in node.targets)]
    if len(nodes) != 2:
        raise AssertionError("failed-work shape and whitelist definitions missing")
    namespace = {}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(SOURCE), "exec"), namespace)
    return namespace

def fixture(*, composition_repair=False):
    # The literal old nine-name whitelist and two excluded compilation identities
    # come from fixture_contract, independently of the implementation constants.
    direct = CONTRACT["legacy_direct_ids"] + CONTRACT["compiled_ids"] + [
        "ProviderGuard.cpp" if i == 0 else "Direct%02d.cpp" % i for i in range(24)]
    if composition_repair:
        direct = [{"Direct01.cpp": "BibNativeEditorBackend.cpp", "Direct02.cpp": "main.cpp"}.get(name, name) for name in direct]
    engine = ["Engine%02d.cpp" % i for i in range(16)]
    archives = [{"name": name, "members": ["m%04d.o" % i for i in range(count)]}
        for name, count in zip(CONTRACT["archive_order"], CONTRACT["archive_member_counts"])]
    replacements = [{"archive": "WebCore", "ordinal": i, "object_id": name}
                    for i, name in enumerate(engine)]
    selected = direct + engine
    proof = {"objects": [{"id": name} for name in selected],
             "archives": archives, "replacements": replacements}
    inspection = SimpleNamespace(proof=proof, profile={"direct_objects": direct,
                                                     "engine_objects": engine})
    old = {"reuse": {"archives": deepcopy(archives), "replacements": deepcopy(replacements)}}
    rows = [{"id": name} for name in CONTRACT["legacy_direct_ids"] + engine]
    return inspection, old, rows, selected


shape_fixture = fixture  # Preserve the alias used by the original separate suites.


class LegacyShape(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.namespace = load_shape()

    def shape(self, inspection, old, rows):
        return self.namespace["_completed_shape"](inspection, old, rows)

    def test_exact_literal_nine_direct_whitelist_is_unchanged(self):
        self.assertEqual(set(CONTRACT["legacy_direct_ids"]), self.namespace["COMPLETED_DIRECT"])

    def test_failed_work_one_and_twentyfive_remain_admissible(self):
        inspection, old, rows, selected = fixture()
        self.assertEqual(selected, self.shape(inspection, old, rows[:1]))
        self.assertEqual(25, len(rows))
        self.assertEqual(selected, self.shape(inspection, old, rows))

    def test_failed_work_empty_rejects(self):
        inspection, old, _, _ = fixture()
        with self.assertRaises(ValueError): self.shape(inspection, old, [])

    def test_failed_work_twenty_six_rejects(self):
        inspection, old, rows, _ = fixture()
        rows.insert(9, {"id": CONTRACT["compiled_ids"][0]})
        with self.assertRaises(ValueError): self.shape(inspection, old, rows)

    def test_failed_work_publisher_and_shim_remain_forbidden(self):
        for name in CONTRACT["compiled_ids"]:
            with self.subTest(name=name):
                inspection, old, _, _ = fixture()
                with self.assertRaises(ValueError): self.shape(inspection, old, [{"id": name}])

    def test_failed_work_duplicate_unknown_and_reordered_reject(self):
        inspection, old, rows, _ = fixture()
        for changed in ([rows[0], rows[0]], [{"id": "Unknown.cpp"}], rows[::-1]):
            with self.subTest(rows=changed[:2]):
                with self.assertRaises(ValueError): self.shape(inspection, old, changed)

    def test_archive_member_count_and_original_order_cannot_change(self):
        inspection, old, rows, _ = fixture()
        inspection.proof["archives"][0]["members"].pop()
        with self.assertRaises(ValueError): self.shape(inspection, old, rows)
        inspection, old, rows, _ = fixture()
        old["reuse"]["archives"][0]["members"][0:2] = ["m0001.o", "m0000.o"]
        with self.assertRaises(ValueError): self.shape(inspection, old, rows)

    def test_replacement_cardinality_and_identity_cannot_change(self):
        inspection, old, rows, _ = fixture()
        inspection.proof["replacements"].pop()
        with self.assertRaises(ValueError): self.shape(inspection, old, rows)
        inspection, old, rows, _ = fixture()
        inspection.proof["replacements"][0]["object_id"] = "Unknown.cpp"
        with self.assertRaises(ValueError): self.shape(inspection, old, rows)

    def test_selected_union_must_stay_exact_ordered_fiftyone(self):
        inspection, old, rows, _ = fixture()
        inspection.proof["objects"][0:2] = inspection.proof["objects"][0:2][::-1]
        with self.assertRaises(ValueError): self.shape(inspection, old, rows)


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True,
                       allow_nan=False) + '\n').encode('ascii')

def digest(value):
    return hashlib.sha256(value if isinstance(value, bytes) else value.encode()).hexdigest()

def load_helper():
    spec = importlib.util.spec_from_file_location('fixture_successful_donor', HELPER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def fields(value, names, label):
    if type(value) is not dict or set(value) != set(names):
        raise ValueError('invalid fake-reader ' + label)

class Reader:
    """Policy-unit boundary, deliberately not an actual hash/physical reader."""
    fields = staticmethod(fields)
    encoded = staticmethod(encoded)
    document = staticmethod(json.loads)

    def __init__(self):
        self.documents = {}
        self.facts = {}
        self.raw = {}
        self.fact_reads = []
        self.authority_calls = []
        self.original = ({'freeze': 'unmodified'}, {'packet': 'unmodified'},
                         {'actual_session': 6290}, {'objects': 'unmodified'})

    def _completed_reference(self, reference):
        fields(reference, ('path', 'sha256'), 'reference')
        key = (reference['path'], reference['sha256'])
        if key not in self.documents:
            raise ValueError('unknown reference')
        return self.documents[key]

    def _completed_fact(self, fact):
        fields(fact, ('path', 'sha256', 'bytes', 'mode', 'identity'), 'fact')
        if self.facts.get(fact['path']) != fact:
            raise ValueError('fact differs from fixture trusted-reader record')
        self.fact_reads.append(fact['path'])
        return self.raw.get(fact['path'], b'invented physical bytes')

    def _completed_authority(self, value, bindings, old):
        # The old authority validator is independently retained by the producer.
        # Preserve the exact descriptor; never restamp its failure into success.
        self.authority_calls.append(deepcopy(value))
        return self.original

class Donor:
    def __init__(self, helper, *, composition_repair=False):
        self.helper = helper
        self.api = Reader()
        self.bindings = {key: Path('/invented/' + key) for key in ('sources', 'sdk', 'reuse', 'build')}
        self.inspection, old, _, self.selected = shape_fixture(composition_repair=composition_repair)
        archives = []
        for name, count in zip(CONTRACT['archive_order'], CONTRACT['archive_member_counts']):
            archives.append({'name': name, 'members': [
                {'ordinal': i, 'input': {'path': 'opaque/' + name + '%04d.o' % i,
                                        'sha256': digest(name + str(i))}, 'bytes': i + 1}
                for i in range(count)]})
        self.inspection.proof['archives'] = archives
        self.old = {'selection': {'recipe_sha256': '1' * 64, 'sources_sha256': '2' * 64,
                                 'sdk_manifest_sha256': '3' * 64},
                    'reuse': {'objects': [{'id': name} for name in self.selected],
                              'archives': deepcopy(archives),
                              'replacements': deepcopy(self.inspection.proof['replacements'])}}
        self.records = {}
        names = [part for name in self.selected for part in ('objects/' + name + '.o', 'objects/' + name + '.o.d')]
        names += ['archives/lib' + name + '.a' for name in CONTRACT['archive_order']]
        names += ['artifacts/foundation-retained-engine.mjs', 'artifacts/foundation-retained-engine.wasm',
                  'document-generated/BibCopiedDocumentMetadata.generated.h',
                  'document-generated/provider-build.json', 'evidence/engine-link.map']
        for i, name in enumerate(names):
            self.records[name] = self.fact(str(self.bindings['build'] / name), i + 1)
        self.build_objects = [{'id': name, 'sha256': self.records['objects/' + name + '.o']['sha256'],
                               'bytes': self.records['objects/' + name + '.o']['bytes']}
                              for name in self.selected]
        replacements = {(row['archive'], row['ordinal']): row['object_id']
                        for row in self.inspection.proof['replacements']}
        objects = {row['id']: row for row in self.build_objects}
        self.reports = []
        for archive in archives:
            members = []
            for item in archive['members']:
                owner = replacements.get((archive['name'], item['ordinal']))
                if owner is not None:
                    product = objects[owner]
                    members.append({'name': owner + '.o', 'sha256': product['sha256'], 'bytes': product['bytes']})
                else:
                    members.append({'name': Path(item['input']['path']).name,
                                    'sha256': item['input']['sha256'], 'bytes': item['bytes']})
            self.reports.append({'name': archive['name'], 'members': members,
                                 'sha256': self.records['archives/lib' + archive['name'] + '.a']['sha256']})
        self.build = {'schema_version': 1, 'kind': 'foundation-document-v2-maintenance-build-v1',
                      'status': 'passed', 'production_eligible': False,
                      'plan_sha256': helper.ORIGINAL_PLAN_SHA256,
                      'source_recipe_sha256': '1' * 64, 'sources_sha256': '2' * 64,
                      'paired_sdk_sha256': '3' * 64, 'objects': self.build_objects,
                      'commands': {'path': 'evidence/commands.json', 'sha256': '4' * 64},
                      'inspection': {'archives': self.reports}}
        natural = {'schema_version': 1, 'primary_returncode': 0, 'descendants_outlived': False,
                   'terminated': False, 'reaped': 1, 'error': None}
        self.worker = {'kind': 'private-passive-j1-readback-result-v1', 'status': 'passed',
                       'original_outer6290_status': 'failed-preserved',
                       'root_closed_wrapper_sha256': helper.ROOT_FAILURE_SHA256,
                       'packet_sha256': '5' * 64, 'SDK_programs_compiler_archive_link_runtime': False,
                       'runtime_not_run': True,
                       'verification': {'actual_archive_reports': 5, 'actual_objects': 51,
                           'artifact_records': self.records, 'inspection_sha256': digest(encoded(self.build['inspection'])),
                           'maintenance_build_sha256': helper.MAINTENANCE_BUILD_SHA256,
                           'opaque_unchanged_members': 2060, 'runtime_not_run': True, 'static_byte_readback': 'passed'}}
        self.result = {'status': 'passed', 'returncode': 0, 'closed': True, 'writers_joined': True,
                       'verified': True, 'production_eligible': False, 'new_build_or_runtime': False,
                       'runtime_not_run': True, 'original_outer6290_status': 'failed-preserved',
                       'input_identity_namespace_postflight': 'passed', 'supervisor_report': deepcopy(natural)}
        self.original = {'status': 'failed', 'returncode': 0, 'closed': True, 'writers_joined': True,
                         'production_eligible': False, 'runtime_not_run': True,
                         'input_identity_namespace_postflight': 'passed', 'supervisor_report': deepcopy(natural)}
        self.failure = {'kind': 'root-closed-build51-execution-and-readback-defect-v1', 'actual_session': 6290,
                        'actual_caller_returncode': 1, 'inner_returncode': 0, 'original_outer_status': 'failed-preserved',
                        'closed': True, 'writers_joined': True, 'production_eligible': False, 'runtime_not_run': True,
                        'input_identity_namespace_postflight': 'passed', 'qualified_report': deepcopy(natural)}
        self.root = {'kind': 'root-closed-passive-j1-candidate-readback-accepted-v1', 'actual_session': 81951,
                     'actual_caller_returncode': 0, 'closed': True, 'writers_joined': True,
                     'original6290_outer_status': 'failed-preserved', 'input_identity_namespace_postflight': 'passed',
                     'static_byte_readback': 'passed', 'all_artifact_physical_identities_root_rechecked': True,
                     'production_eligible': False, 'runtime_not_run': True, 'new_compile_archive_link_runtime': False,
                     'actual_objects': 51, 'actual_archive_reports': 5, 'opaque_unchanged_members': 2060,
                     'verified_artifact_records': 112, 'qualified_report': deepcopy(natural)}
        ref = lambda path, sha: {'path': path, 'sha256': sha}
        self.value = {'schema_version': 1, 'kind': helper.DONOR_KIND, 'document_profile': 'editor',
                      'original_bindings': {k: str(v) for k, v in self.bindings.items()},
                      'objects': [{'id': name, 'object': self.records['objects/' + name + '.o'],
                                   'depfile': self.records['objects/' + name + '.o.d']}
                                  for name in self.selected if name not in CONTRACT['compiled_ids']],
                      'archives': []}
        refs = {'original_plan': ('/invented/plan.json', helper.ORIGINAL_PLAN_SHA256),
                'original_commands': ('/invented/build/evidence/commands.json', '4' * 64),
                'root_failure': ('/invented/authority/failure.json', helper.ROOT_FAILURE_SHA256),
                'candidate_result': ('/invented/authority/original.json', '6' * 64),
                'root_acceptance': ('/invented/authority/acceptance.json', helper.ROOT_ACCEPTANCE_SHA256),
                'passive_worker': ('/invented/passive/output/result.json', helper.PASSIVE_WORKER_SHA256),
                'passive_result': ('/invented/passive/owner.json', '7' * 64),
                'maintenance_build': ('/invented/build/maintenance-build.json', helper.MAINTENANCE_BUILD_SHA256)}
        for key, (path, sha) in refs.items(): self.value[key] = ref(path, sha)
        for key in ['original_input_freeze', 'original_build_packet', 'root_launch', 'root_handle',
                    'original_private', 'ninja_log', 'dependency_sidecar']:
            self.value[key] = ref('/invented/authority/' + key + '.json', digest(key))
        self.packet_ref = ref('/invented/passive/PACKET.json', '5' * 64)
        for name in CONTRACT['archive_order']:
            report = self.reports[CONTRACT['archive_order'].index(name)]
            fact = self.fact('/invented/build/evidence/archive-' + name + '.json', 200 + len(self.value['archives']))
            self.api.raw[fact['path']] = encoded(report)
            self.value['archives'].append({'name': name, 'archive': self.records['archives/lib' + name + '.a'], 'report': fact})
        docs = {'root_acceptance': self.root, 'root_failure': self.failure, 'passive_worker': self.worker,
                'passive_result': self.result, 'candidate_result': self.original, 'maintenance_build': self.build}
        for key, payload in docs.items():
            reference = self.value[key]
            self.api.documents[(reference['path'], reference['sha256'])] = payload
        self.root['references'] = [self.attested(self.value[key], 300 + i)
                                   for i, key in enumerate(['passive_worker', 'passive_result'])]
        self.root['references'].append(self.attested(self.packet_ref, 302))
        self.failure['references'] = [self.attested(self.value[key], 310 + i)
                                      for i, key in enumerate(['candidate_result', 'maintenance_build'])]
        self.refresh()

    def fact(self, path, index):
        result = {'path': path, 'sha256': digest(path), 'bytes': index + 7, 'mode': 0o644,
                  'identity': [41, 1000 + index, 0o100644, 1, index + 7, 71, 72]}
        self.api.facts[path] = deepcopy(result)
        return result

    def attested(self, reference, index):
        result = self.fact(reference['path'], index)
        result['sha256'] = reference['sha256']
        self.api.facts[result['path']] = deepcopy(result)
        return {k: deepcopy(v) for k, v in result.items() if k != 'mode'}

    def refresh(self):
        self.worker['verification']['inspection_sha256'] = digest(encoded(self.build['inspection']))
        self.result['passive_readback'] = deepcopy(self.worker)
        for row, report in zip(self.value['archives'], self.reports):
            self.api.raw[row['report']['path']] = encoded(report)

    def admit(self):
        self.refresh()
        return self.helper.authority(self.value, self.bindings, self.old, self.api)

    def archives(self):
        self.refresh()
        return self.helper.archive_rows(self.value, self.inspection, self.old, self.bindings, self.api)

class SuccessfulDonor(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.helper = load_helper()

    def new(self): return Donor(self.helper)

    def test_literal_kinds_compilation_pair_and_original_four_authorities(self):
        self.assertEqual(('NativeDocumentV2Publisher.cpp', 'BibEngineDocumentWasmShim.cpp'), self.helper.COMPILED_IDS)
        self.assertEqual('foundation-document-v2-successful-donor-v1', self.helper.DONOR_KIND)
        self.assertEqual('foundation-document-v2-maintenance-successful-donor-plan-v1', self.helper.PLAN_KIND)
        self.assertEqual('foundation-document-v2-maintenance-successful-donor-build-v1', self.helper.BUILD_KIND)
        f = self.new(); original = deepcopy(f.value)
        self.assertIs(f.api.original, f.admit())
        self.assertEqual(original, f.value)
        self.assertEqual([original], f.api.authority_calls)
        self.assertEqual('failed', f.original['status'])

    def test_ordered_five_archives_and_full_member_tables(self):
        f = self.new(); rows = f.archives()
        self.assertEqual(CONTRACT['archive_order'], [row['name'] for row in rows])
        self.assertEqual(f.value['archives'], rows)
        self.assertEqual(2076, sum(len(row['members']) for row in f.reports))
        self.assertEqual(49, len(f.value['objects']))
        self.assertFalse(any(name.endswith(('.o', '.o.d')) for name in f.api.fact_reads))

    def test_historical_reference_pin_and_descriptor_negatives(self):
        for key in ['root_acceptance', 'root_failure', 'passive_worker', 'maintenance_build', 'original_plan']:
            f = self.new(); f.value[key]['sha256'] = 'a' * 64
            with self.subTest(key=key), self.assertRaises(ValueError): f.admit()
        for key, value in [('schema_version', True), ('document_profile', 'web'), ('kind', 'completed-work')]:
            f = self.new(); f.value[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): f.admit()
        f = self.new(); f.value['extra'] = False
        with self.assertRaises(ValueError): f.admit()

    def test_original_failure_is_never_restamped_or_unclosed(self):
        mutations = [('original_outer_status', 'passed'), ('inner_returncode', False),
                     ('actual_caller_returncode', 0), ('closed', False), ('writers_joined', False),
                     ('runtime_not_run', False), ('production_eligible', True)]
        for key, value in mutations:
            f = self.new(); f.failure[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): f.admit()
        f = self.new(); f.original['status'] = 'passed'
        with self.assertRaises(ValueError): f.admit()

    def test_qualified_owner_reports_require_exact_natural_plain_integers(self):
        for target in ['root', 'failure']:
            for key, value in [('schema_version', True), ('primary_returncode', False),
                               ('terminated', True), ('descendants_outlived', True), ('reaped', 0), ('error', 'unknown')]:
                f = self.new(); getattr(f, target)['qualified_report'][key] = value
                with self.subTest(target=target, key=key), self.assertRaises(ValueError): f.admit()

    def test_passive_root_count_and_no_runtime_conjunction(self):
        for key, value in [('actual_objects', 50), ('actual_archive_reports', True),
                           ('verified_artifact_records', 111), ('opaque_unchanged_members', 2059),
                           ('all_artifact_physical_identities_root_rechecked', False),
                           ('new_compile_archive_link_runtime', True), ('static_byte_readback', 'not-run')]:
            f = self.new(); f.root[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): f.admit()

    def test_passive_owner_worker_and_maintenance_joins(self):
        for key, value in [('verified', False), ('returncode', False), ('new_build_or_runtime', True),
                           ('original_outer6290_status', 'passed'), ('closed', False)]:
            f = self.new(); f.result[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): f.admit()
        for key in ['source_recipe_sha256', 'sources_sha256', 'paired_sdk_sha256', 'plan_sha256']:
            f = self.new(); f.build[key] = 'a' * 64
            with self.subTest(key=key), self.assertRaises(ValueError): f.admit()

    def test_attested_metadata_identity_mode_and_references(self):
        for mutation in ['duplicate', 'missing', 'identity', 'bytes', 'extra']:
            f = self.new(); row = f.root['references'][0]
            if mutation == 'duplicate': f.root['references'].append(deepcopy(row))
            elif mutation == 'missing': f.root['references'].pop(0)
            elif mutation == 'identity': row['identity'][1] += 1
            elif mutation == 'bytes': row['bytes'] += 1
            else: row['mode'] = 0o644
            with self.subTest(mutation=mutation), self.assertRaises(ValueError): f.admit()

    def test_imports_must_be_exact_ordered_fortynine(self):
        for change in ['missing', 'duplicate', 'reverse', 'publisher', 'shim', 'unknown']:
            f = self.new()
            if change == 'missing': f.value['objects'].pop()
            elif change == 'duplicate': f.value['objects'][1] = deepcopy(f.value['objects'][0])
            elif change == 'reverse': f.value['objects'].reverse()
            else: f.value['objects'][0]['id'] = {'publisher': CONTRACT['compiled_ids'][0], 'shim': CONTRACT['compiled_ids'][1], 'unknown': 'Unknown.cpp'}[change]
            with self.subTest(change=change), self.assertRaises(ValueError): f.admit()

    def test_product_namespace_physical_facts_and_object_depfile_join(self):
        for change in ['missing', 'extra', 'hardlink', 'bool-size', 'zero-sha', 'mismatched-dep']:
            f = self.new(); name = 'objects/' + f.selected[0] + '.o'
            if change == 'missing': del f.records[name]
            elif change == 'extra': f.records['unrelated'] = deepcopy(f.records[name])
            elif change == 'hardlink': f.records[name]['identity'][3] = 2
            elif change == 'bool-size': f.records[name]['bytes'] = True
            elif change == 'zero-sha': f.records[name]['sha256'] = '0' * 64
            else: f.value['objects'][0]['depfile'] = deepcopy(f.value['objects'][1]['depfile'])
            with self.subTest(change=change), self.assertRaises(ValueError): f.admit()

    def test_archive_rows_report_and_full_order_changes_reject(self):
        for change in ['missing', 'reverse', 'duplicate', 'fact', 'member-order', 'member-hash', 'member-size', 'report-name']:
            f = self.new()
            if change == 'missing': f.value['archives'].pop()
            elif change == 'reverse': f.value['archives'].reverse()
            elif change == 'duplicate': f.value['archives'][1] = deepcopy(f.value['archives'][0])
            elif change == 'fact': f.value['archives'][0]['archive'] = deepcopy(f.value['archives'][1]['archive'])
            elif change == 'member-order': f.reports[0]['members'][0:2] = f.reports[0]['members'][0:2][::-1]
            elif change == 'member-hash': f.reports[0]['members'][0]['sha256'] = 'a' * 64
            elif change == 'member-size': f.reports[0]['members'][0]['bytes'] += 1
            else: f.reports[0]['name'] = 'Wrong'
            with self.subTest(change=change), self.assertRaises(ValueError): f.archives()

    def test_archive_proof_replacement_and_member_identity_changes_reject(self):
        f = self.new(); f.inspection.proof['archives'][0]['members'][20]['input']['sha256'] = 'a' * 64
        with self.assertRaises(ValueError): f.archives()
        f = self.new(); f.inspection.proof['replacements'][0]['object_id'] = CONTRACT['compiled_ids'][0]
        with self.assertRaises(ValueError): f.archives()

    def test_successful_shape_exact_fortynine_reuses_whole_union_checks(self):
        namespace = load_shape()
        namespace['_successful_module'] = lambda: self.helper
        call = namespace['_completed_shape']
        f = self.new()
        self.assertEqual(f.selected, call(f.inspection, f.old, f.value['objects'], successful=True))
        for changed in [f.value['objects'][:-1], f.value['objects'][::-1],
                        f.value['objects'] + [{'id': CONTRACT['compiled_ids'][0]}]]:
            with self.assertRaises(ValueError): call(f.inspection, f.old, changed, successful=True)


def load_receipt_functions():
    tree = ast.parse(SOURCE.read_text())
    wanted = {'_identity7', '_completed_build_receipt', '_successful_build_receipt', '_native_capability_build_receipt', '_native_control_keypress_build_receipt'}
    nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in wanted]
    if {node.name for node in nodes} != wanted:
        raise AssertionError('actual receipt implementations missing')
    namespace = {'NATIVE_CONTROL_KEYPRESS_REPAIR_PLAN_KIND': 'foundation-document-v2-maintenance-successful-donor-native-control-keypress-repair-plan-v1',
                 'NATIVE_CONTROL_KEYPRESS_REPAIR_BUILD_KIND': 'foundation-document-v2-maintenance-successful-donor-native-control-keypress-repair-build-v1',
                 'NATIVE_CAPABILITY_REPAIR_PLAN_KIND': 'foundation-document-v2-maintenance-successful-donor-native-capability-repair-plan-v1',
                 'NATIVE_CAPABILITY_REPAIR_BUILD_KIND': 'foundation-document-v2-maintenance-successful-donor-native-capability-repair-build-v1',
                 'SUCCESSFUL_PLAN_KIND': 'foundation-document-v2-maintenance-successful-donor-plan-v1',
                 'GUARD_REPAIR_PLAN_KIND': 'foundation-document-v2-maintenance-successful-donor-guard-repair-plan-v1',
                 'GUARD_REPAIR_BUILD_KIND': 'foundation-document-v2-maintenance-successful-donor-guard-repair-build-v1',
                 'COMPOSITION_REPAIR_PLAN_KIND': 'foundation-document-v2-maintenance-successful-donor-composition-repair-plan-v1',
                 'COMPOSITION_REPAIR_BUILD_KIND': 'foundation-document-v2-maintenance-successful-donor-composition-repair-build-v1',
                 'RESUME_BUILD_KIND': 'foundation-document-v2-maintenance-resume-build-v1',
                 'SUCCESSFUL_BUILD_KIND': 'foundation-document-v2-maintenance-successful-donor-build-v1',
                 '_successful_module': load_helper,
                 'checked_document': lambda p: json.loads(Path(p).read_bytes()),
                 'ordinary': lambda p: Path(p),
                 'digest': lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(SOURCE), 'exec'), namespace)
    return namespace

class ReceiptFixture:
    def __init__(self, root, namespace, *, guard_repair=False, composition_repair=False, native_capability_repair=False, control_keypress_repair=False):
        self.root = root
        self.namespace = namespace
        self.native_capability_repair = native_capability_repair
        self.control_keypress_repair = control_keypress_repair
        _, _, _, selected = shape_fixture(composition_repair=composition_repair)
        if native_capability_repair or control_keypress_repair:
            selected = [{'Direct03.cpp': 'NativeFormsV2Combined.cpp', 'Direct04.cpp': 'NativeDocumentV2Types.cpp', 'Direct05.cpp': 'BibNativePopupOwner.cpp'}.get(name, name) for name in selected]
        if control_keypress_repair:
            selected = ["BibDocumentPhysicalProvider.cpp" if name == "Direct06.cpp" else name for name in selected]
        self.selected = selected
        compiled = CONTRACT['compiled_ids'] + (['ProviderGuard.cpp', 'BibNativeEditorBackend.cpp', 'main.cpp'] if composition_repair else ['ProviderGuard.cpp'] if guard_repair else [])
        if native_capability_repair or control_keypress_repair:
            compiled = ['NativeDocumentV2Publisher.cpp', 'NativeFormsV2Combined.cpp', 'NativeDocumentV2Types.cpp', 'BibEngineDocumentWasmShim.cpp', 'BibNativePopupOwner.cpp']
        if control_keypress_repair:
            compiled.append("BibDocumentPhysicalProvider.cpp")
        imported = [name for name in selected if name not in compiled]
        self.commands = {'objects': {name: ['fake-compiler', name] for name in compiled},
                         'imports': {name: ['fake-copy', name] for name in imported},
                         'archive_imports': {name: ['fake-copy', name] for name in CONTRACT['archive_order']}}
        rows = []
        self.result = {'objects': []}
        for index, name in enumerate(selected):
            raw = ('owned fake object ' + name).encode()
            obj = {'id': name, 'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}
            self.result['objects'].append(obj)
            if name not in imported: continue
            original = {'id': name, 'object': {'path': '/invented/donor/' + name + '.o'},
                        'depfile': {'path': '/invented/donor/' + name + '.o.d'},
                        'command_sha256': str(index + 1).zfill(64), 'original_argv': ['old-compiler', name],
                        'original_cwd': '/invented/donor', 'ninja_record': ['0', '1', '2', name, 'abc'],
                        'ninja_command': 'invented source-bound command', 'command_script': None}
            if native_capability_repair or control_keypress_repair:
                original['donor_provenance'] = dict(**({'kind': 'foundation-document-v2-native-control-keypress-object-provenance-v1'} if control_keypress_repair else {}), compile_origin='p5-compiled' if name in ('ProviderGuard.cpp', 'BibNativeEditorBackend.cpp', 'main.cpp') else 'legacy-imported',
                    compile_bindings={'build': '/invented/p5' if name in ('ProviderGuard.cpp', 'BibNativeEditorBackend.cpp', 'main.cpp') else '/invented/legacy'})
            rows.append(original)
            record = {'kind': 'foundation-document-v2-object-import-v1', 'production_eligible': False,
                      'id': name, 'origin': 'imported', 'compiler_invoked': False, 'hardlinked': False,
                      'sha256': obj['sha256'], 'bytes': obj['bytes'], 'object': original['object'],
                      'original_depfile': original['depfile'], 'original_command_sha256': original['command_sha256'],
                      'original_argv': original['original_argv'], 'original_cwd': original['original_cwd'],
                      'ninja_record': original['ninja_record'], 'ninja_command': original['ninja_command'],
                      'command_script': None}
            if native_capability_repair or control_keypress_repair:
                record['donor_provenance'] = deepcopy(original['donor_provenance'])
            self.save('evidence/import-' + name + '.json', record)
        archives = []
        for name in CONTRACT['archive_order']:
            target = self.root / ('archives/lib' + name + '.a')
            target.parent.mkdir(exist_ok=True)
            raw = ('not a real archive: ' + name).encode(); target.write_bytes(raw)
            digest = hashlib.sha256(raw).hexdigest()
            original = {'path': '/invented/donor/lib' + name + '.a', 'sha256': digest,
                        'bytes': len(raw), 'mode': 0o644, 'identity': [999, 888, 0o100644, 1, len(raw), 7, 8]}
            report = {'path': '/invented/donor/archive-' + name + '.json', 'sha256': 'a' * 64,
                      'bytes': 10, 'mode': 0o644, 'identity': [999, 777, 0o100644, 1, 10, 7, 8]}
            archives.append({'name': name, 'archive': original, 'report': report})
            self.save('evidence/import-archive-' + name + '.json',
                      {'kind': 'foundation-document-v2-archive-import-v1', 'name': name,
                       'origin': 'imported', 'archive': original, 'original_report': report,
                       'destination': str(target), 'hardlinked': False, 'archive_program_invoked': False,
                       'production_eligible': False, 'sha256': digest, 'bytes': len(raw)})
        self.plan = {'kind': ('foundation-document-v2-maintenance-successful-donor-native-control-keypress-repair-plan-v1' if control_keypress_repair else 'foundation-document-v2-maintenance-successful-donor-native-capability-repair-plan-v1' if native_capability_repair else 'foundation-document-v2-maintenance-successful-donor-composition-repair-plan-v1' if composition_repair else 'foundation-document-v2-maintenance-successful-donor-guard-repair-plan-v1' if guard_repair
                              else 'foundation-document-v2-maintenance-successful-donor-plan-v1'),
                     'reuse': {'objects': [{'id': name} for name in selected],
                               'archives': [{'name': name} for name in CONTRACT['archive_order']]},
                     'successful_donor': {'reference': {'path': '/invented/donor.json', 'sha256': 'b' * 64},
                                          'objects': rows, 'archives': archives}}
        if native_capability_repair or control_keypress_repair:
            for name in (load_helper().native_control_keypress_artifact_names if control_keypress_repair else load_helper().native_capability_artifact_names)(selected, CONTRACT['archive_order']):
                path = self.root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                if not path.exists():
                    raw = ('owned fake object ' + name[8:-2]).encode() if name.startswith('objects/') and name.endswith('.o') else b'inert candidate evidence, no executable artifact'
                    path.write_bytes(raw)

    def save(self, name, value):
        p = self.root / name; p.parent.mkdir(exist_ok=True, parents=True); p.write_bytes(encoded(value))

    def record(self, name): return json.loads((self.root / name).read_bytes())

    def apply(self):
        name = '_native_control_keypress_build_receipt' if self.control_keypress_repair else '_native_capability_build_receipt' if self.native_capability_repair else '_successful_build_receipt'
        self.namespace[name](self.result, self.plan, self.root, self.commands)
        return self.result


class NativeControlKeypressAccounting(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.namespace = load_receipt_functions()

    def fixture(self):
        temp = tempfile.TemporaryDirectory(prefix='inert-control-keypress-accounting-')
        self.addCleanup(temp.cleanup)
        return ReceiptFixture(Path(temp.name), self.namespace, control_keypress_repair=True)

    def test_real_receipt_counts_kind_provenance_and_complete_namespace(self):
        f = self.fixture(); result = f.apply()
        self.assertEqual(result['kind'], self.namespace['NATIVE_CONTROL_KEYPRESS_REPAIR_BUILD_KIND'])
        self.assertEqual((51, 45, 6, 5, 0), tuple(result['accounting'][k] for k in
            ('selected', 'imported', 'compiled', 'archive_imported', 'archive_repacked')))
        self.assertEqual(167, result['expected_artifact_records'])
        self.assertEqual([name for name in f.selected if name in load_helper().NATIVE_CONTROL_KEYPRESS_REPAIR_COMPILED_IDS], result['accounting']['compiled_ids'])
        self.assertNotIn('completed_work', result)

    def test_real_receipt_refuses_partition_provenance_and_archive_mutations(self):
        for change in ('extra-compile', 'missing-import', 'old-kind', 'origin', 'archive-program', 'archive-order'):
            f = self.fixture()
            if change == 'extra-compile': f.commands['objects']['Extra.cpp'] = []
            elif change == 'missing-import': f.commands['imports'].pop(next(iter(f.commands['imports'])))
            elif change == 'old-kind': f.plan['kind'] = self.namespace['NATIVE_CAPABILITY_REPAIR_PLAN_KIND']
            elif change == 'origin':
                n = f.plan['successful_donor']['objects'][0]['id']; p = 'evidence/import-' + n + '.json'
                record = f.record(p); record['donor_provenance']['kind'] = 'foundation-document-v2-native-capability-object-provenance-v1'; f.save(p, record)
            elif change == 'archive-program':
                p = 'evidence/import-archive-WebCore.json'; record = f.record(p); record['archive_program_invoked'] = True; f.save(p, record)
            else: f.plan['successful_donor']['archives'].reverse()
            with self.subTest(change=change), self.assertRaises(ValueError): f.apply()


class Accounting(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.namespace = load_receipt_functions()

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='fake-successful-donor-accounting-')
        self.addCleanup(self.temporary.cleanup)
        self.f = ReceiptFixture(Path(self.temporary.name), self.namespace)

    def test_exact_ordered_fiftyone_partition_and_five_imports(self):
        result = self.f.apply()
        self.assertEqual('foundation-document-v2-maintenance-successful-donor-build-v1', result['kind'])
        self.assertNotIn('completed_work', result)
        self.assertEqual(self.f.plan['successful_donor']['reference'], result['successful_donor'])
        self.assertEqual({'selected': 51, 'imported': 49, 'compiled': 2,
            'imported_ids': [n for n in self.f.selected if n not in CONTRACT['compiled_ids']],
            'compiled_ids': CONTRACT['compiled_ids'], 'archive_imported': 5, 'archive_repacked': 0,
            'imported_archive_names': CONTRACT['archive_order']}, result['accounting'])
        self.assertEqual(self.f.selected, [row['id'] for row in result['objects']])
        self.assertEqual(CONTRACT['archive_order'], [row['name'] for row in result['archive_imports']])
        for row in result['objects']:
            self.assertEqual('compiled' if row['id'] in CONTRACT['compiled_ids'] else 'imported', row['origin'])

    def test_missing_duplicate_reordered_and_empty_result_objects_reject(self):
        original = deepcopy(self.f.result['objects'])
        for changed in [[], original[:-1], [original[0]] + original[:-1], original[::-1]]:
            self.f.result = {'objects': deepcopy(changed)}
            with self.subTest(count=len(changed)), self.assertRaises(ValueError): self.f.apply()

    def test_missing_extra_or_misclassified_command_sets_reject(self):
        self.f.commands['objects']['Unexpected.cpp'] = []
        with self.assertRaises(ValueError): self.f.apply()
        del self.f.commands['objects']['Unexpected.cpp']
        del self.f.commands['imports'][self.f.selected[0]]
        with self.assertRaises(ValueError): self.f.apply()

    def test_object_original_command_and_depfile_evidence_cannot_change(self):
        name = self.f.selected[0]
        relative = 'evidence/import-' + name + '.json'
        original = self.f.record(relative)
        for key, value in [('compiler_invoked', True), ('hardlinked', True),
                           ('original_cwd', '/wrong'), ('original_depfile', {'path': '/wrong'}),
                           ('original_argv', ['replacement compiler'])]:
            changed = dict(original, **{key: value}); self.f.save(relative, changed)
            with self.subTest(key=key), self.assertRaises(ValueError): self.f.apply()
        self.f.save(relative, original)

    def test_archive_copy_provenance_and_no_tool_flags_reject_changes(self):
        relative = 'evidence/import-archive-WebCore.json'
        original = self.f.record(relative)
        for key, value in [('archive_program_invoked', True), ('hardlinked', True),
                           ('origin', 'compiled'), ('bytes', True), ('destination', '/wrong')]:
            self.f.save(relative, dict(original, **{key: value}))
            with self.subTest(key=key), self.assertRaises(ValueError): self.f.apply()
        self.f.save(relative, original)

    def test_archive_names_command_namespace_and_donor_order_reject(self):
        del self.f.commands['archive_imports']['WebCore']
        with self.assertRaises(ValueError): self.f.apply()
        self.f.commands['archive_imports']['WebCore'] = []
        self.f.plan['successful_donor']['archives'].reverse()
        with self.assertRaises(ValueError): self.f.apply()


_spec = importlib.util.spec_from_file_location('successful_donor_tail_fixture', FIXTURES / 'tail_fixture.py')
support = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(support)
support.encoded = encoded


def load_maintenance():
    # These are named source-module imports only; none executes SDK/tool children.
    sys.path.insert(0, str(ROOT / 'tools'))
    spec = importlib.util.spec_from_file_location('counterparty_actual_maintenance', SOURCE)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module

class CommonValidator(unittest.TestCase):
    guard_repair = False
    @classmethod
    def setUpClass(cls):
        cls.m = load_maintenance()
        support.m = cls.m

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='inert-successful-common-validator-')
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        self.stack = ExitStack(); self.addCleanup(self.stack.close)
        self.config = {'name': 'webkitwasm-copied2035-ndv2-v1',
            'direct_objects': CONTRACT['legacy_direct_ids'] + CONTRACT['compiled_ids'] +
                              ['ProviderGuard.cpp' if i == 0 else 'Direct%02d.cpp' % i for i in range(24)],
            'engine_objects': ['Engine%02d.cpp' % i for i in range(16)],
            'archive_members': dict(zip(CONTRACT['archive_order'], CONTRACT['archive_member_counts'])),
            'python_entrypoints': ['upstream/emscripten/fake_entry.py']}
        fake_checkout = root / 'fake-checkout'; fake_checkout.mkdir()
        profile = fake_checkout / self.m.profile_path('editor')
        profile.parent.mkdir(parents=True); profile.write_bytes(support.encoded(self.config))
        helper = fake_checkout / self.m.SELF_PATH
        helper.parent.mkdir(parents=True); helper.write_text(support.BASELINE_SOURCE)
        self.stack.enter_context(mock.patch.object(self.m, 'ROOT', fake_checkout))
        self.stack.enter_context(mock.patch.object(self.m, 'profile', return_value=self.config))
        self.f = support.Fixture(root)
        self.f.value['kind'] = 'foundation-document-v2-successful-donor-v1'
        for name in ('root_acceptance','passive_worker','passive_result','maintenance_build'):
            self.f.value[name] = dict(self.f.value['candidate_result'])
        self.f.value['archives'] = []
        self.archive_calls = []
        def archives(value, inspection, old, bindings, api, **kwargs):
            self.archive_calls.append(value['objects'])
            return []
        selected = SimpleNamespace(DONOR_KIND='foundation-document-v2-successful-donor-v1',
            COMPILED_IDS=('NativeDocumentV2Publisher.cpp','BibEngineDocumentWasmShim.cpp'),
            GUARD_REPAIR_DONOR_KIND='foundation-document-v2-successful-donor-guard-repair-v1',
            GUARD_REPAIR_COMPILED_IDS=('NativeDocumentV2Publisher.cpp','BibEngineDocumentWasmShim.cpp','ProviderGuard.cpp'),
            authority=lambda value, bindings, old, api, **kwargs: self.m._completed_authority(value, bindings, old),
            archive_rows=archives)
        self.stack.enter_context(mock.patch.object(self.m, '_successful_module', return_value=selected))
        self.stack.enter_context(mock.patch.object(self.m, '_header_identity', side_effect=lambda inspection: self.f.view))
        if self.guard_repair:
            self.f.value['kind'] = selected.GUARD_REPAIR_DONOR_KIND
            self.f.value['objects'] = [row for row in self.f.rows if row['id'] != 'ProviderGuard.cpp']

    def admit(self):
        reference = support.save(self.f.root / 'records/successful.json', self.f.value)
        return self.m._completed_work(reference, self.f.inspection, _successful=True, _guard_repair=self.guard_repair)

    def change_current(self, path, raw):
        name = str(path.relative_to(self.f.current['sources']))
        path.parent.mkdir(exist_ok=True, parents=True); path.write_bytes(raw)
        self.f.inventories['sources'][name] = hashlib.sha256(raw).hexdigest()
        return self.f.inventories['sources'][name]

    def test_unchanged_fortynine_allow_only_publisher_and_unincluded_generated_delta(self):
        name = CONTRACT['compiled_ids'][0]
        obj = next(row for row in self.f.proof['objects'] if row['id'] == name)
        obj['source']['sha256'] = self.change_current(self.f.current['sources'] / obj['source']['path'], b'changed Publisher implementation only\n')
        # This is an owned prospective output, never an imported dependency.
        generated = self.f.root / 'fresh-generated/BibCopiedDocumentMetadata.generated.h'
        generated.parent.mkdir(); generated.write_bytes(b'fresh construction metadata\n')
        admitted = self.admit()
        compiled = CONTRACT['compiled_ids'] + (['ProviderGuard.cpp'] if self.guard_repair else [])
        expected = [row['id'] for row in self.f.proof['objects'] if row['id'] not in compiled]
        self.assertEqual(48 if self.guard_repair else 49, len(admitted['objects']))
        self.assertEqual(expected, [row['id'] for row in admitted['objects']])
        self.assertEqual(1, len(self.archive_calls))

    def test_included_generated_metadata_header_rejects_before_archive_gate(self):
        row = self.f.rows[0]; path = self.f.bindings['build'] / 'document-generated/BibCopiedDocumentMetadata.generated.h'
        generated = support.write(path, b'included generated metadata\n')
        self.f.sidecar['dependencies'][str(path)] = {'fact': generated,
            'input': {'root': 'generated', 'path': path.name, 'sha256': generated['sha256']}, 'origin': 'generated'}
        row['dependency_keys'] = sorted(row['dependency_keys'] + [str(path)])
        target = row['object']['path']
        row['depfile'] = support.write(Path(row['depfile']['path']),
            (target + ': ' + ' '.join(row['dependency_keys']) + '\n').encode())
        self.f.value['dependency_sidecar'] = support.save(self.f.root / 'records/dependencies.json', self.f.sidecar)
        with self.assertRaisesRegex(ValueError, 'Generated/unknown'): self.admit()
        self.assertFalse(self.archive_calls)

    def test_imported_source_options_exception_and_rtti_changes_reject(self):
        for change in ('source', 'options', 'exceptions', 'rtti'):
            with self.subTest(change=change):
                obj = self.f.proof['objects'][0]; before = deepcopy(obj)
                if change == 'source': obj['source'] = dict(obj['source'], sha256='a' * 64)
                elif change == 'options': obj['arguments'] = obj['arguments'] + ['-DNEW_OPTION=1']
                elif change == 'exceptions': obj['exceptions'] = not obj['exceptions']
                else: obj['arguments'] = [a for a in obj['arguments'] if a != '-fno-rtti'] + ['-frtti']
                with self.assertRaisesRegex(ValueError, 'source/command/context'): self.admit()
                obj.clear(); obj.update(before)
        self.assertFalse(self.archive_calls)

    def test_same_named_logical_header_byte_change_rejects(self):
        self.change_current(self.f.current['sources'] / 'units/header.h', b'changed logical header\n')
        with self.assertRaises(ValueError): self.admit()
        self.assertFalse(self.archive_calls)

    def test_added_and_removed_search_namespace_names_reject(self):
        path = self.f.current['sources'] / 'units/previously-absent-shadow.h'
        self.change_current(path, b'new negative-presence shadow\n')
        with self.assertRaisesRegex(ValueError, 'namespace/physical-header/VFS'): self.admit()
        del self.f.inventories['sources']['units/previously-absent-shadow.h']; path.unlink()
        del self.f.inventories['sources']['units/BibEngineDocumentWasmShim.cpp']
        with self.assertRaisesRegex(ValueError, 'namespace/physical-header/VFS'): self.admit()

    def test_original_physical_headers_and_vfs_options_are_not_waived(self):
        self.f.view['original_files']['header.h']['sha256'] = 'a' * 64
        with self.assertRaisesRegex(ValueError, 'namespace/physical-header/VFS'): self.admit()
        self.f.view['original_files']['header.h']['sha256'] = '1' * 64
        self.f.view['overlay']['fallthrough'] = False
        with self.assertRaisesRegex(ValueError, 'VFS policy'): self.admit()

    def test_virtual_header_mapping_change_rejects(self):
        self.f.view['overlay']['roots'].append({'type': 'file',
            'name': str(self.f.current['sources'] / 'virtual/header.h'),
            'external-contents': str(self.f.current['sources'] / 'units/header.h')})
        with self.assertRaisesRegex(ValueError, 'namespace/physical-header/VFS'): self.admit()

    def test_sdk_identity_and_tool_context_must_match_original(self):
        self.f.inspection.selection['sdk_manifest_sha256'] = 'a' * 64
        with self.assertRaisesRegex(ValueError, 'plan/SDK'): self.admit()
        self.f.inspection.selection['sdk_manifest_sha256'] = self.f.selection['sdk_manifest_sha256']
        self.f.proof['host_tools']['ninja']['version'] = 'unqualified'
        with self.assertRaises(ValueError): self.admit()

    def test_unrelated_translation_unit_delta_is_not_a_publisher_waiver(self):
        self.change_current(self.f.current['sources'] / 'units/Direct23.cpp', b'unrelated changed TU\n')
        with self.assertRaises(ValueError): self.admit()
        self.assertFalse(self.archive_calls)


class GuardRepairDonor(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.helper = load_helper()

    def fixture(self):
        f = Donor(self.helper)
        f.value['kind'] = 'foundation-document-v2-successful-donor-guard-repair-v1'
        f.value['objects'] = [row for row in f.value['objects'] if row['id'] != 'ProviderGuard.cpp']
        return f

    def test_explicit_kinds_and_fresh_triple(self):
        self.assertEqual('foundation-document-v2-successful-donor-guard-repair-v1', self.helper.GUARD_REPAIR_DONOR_KIND)
        self.assertEqual('foundation-document-v2-maintenance-successful-donor-guard-repair-plan-v1', self.helper.GUARD_REPAIR_PLAN_KIND)
        self.assertEqual('foundation-document-v2-maintenance-successful-donor-guard-repair-build-v1', self.helper.GUARD_REPAIR_BUILD_KIND)
        self.assertEqual(('NativeDocumentV2Publisher.cpp', 'BibEngineDocumentWasmShim.cpp', 'ProviderGuard.cpp'),
                         self.helper.GUARD_REPAIR_COMPILED_IDS)
        f = self.fixture()
        self.assertIs(f.api.original, self.helper.authority(f.value, f.bindings, f.old, f.api, guard_repair=True))
        self.assertEqual(48, len(f.value['objects']))
        self.assertEqual(f.value['archives'], self.helper.archive_rows(f.value, f.inspection, f.old, f.bindings, f.api, guard_repair=True))
        self.assertEqual(16, len(f.inspection.proof['replacements']))

    def test_kind_optin_and_partition_finite_crosslane_grid(self):
        for new_kind in (False, True):
            for optin in (False, True):
                for three_fresh in (False, True):
                    with self.subTest(new_kind=new_kind, optin=optin, three_fresh=three_fresh):
                        f = self.fixture() if three_fresh else Donor(self.helper)
                        f.value['kind'] = self.helper.GUARD_REPAIR_DONOR_KIND if new_kind else self.helper.DONOR_KIND
                        if new_kind == optin == three_fresh:
                            self.helper.authority(f.value, f.bindings, f.old, f.api, guard_repair=optin)
                        else:
                            with self.assertRaises(ValueError):
                                self.helper.authority(f.value, f.bindings, f.old, f.api, guard_repair=optin)

    def test_exact48_rejects_missing_duplicate_reordered_and_extra(self):
        original = self.fixture().value['objects']
        for rows in (original[:-1], original[::-1], original + [original[0]], original + [{'id': 'ProviderGuard.cpp'}]):
            f = self.fixture(); f.value['objects'] = deepcopy(rows)
            with self.subTest(count=len(rows)), self.assertRaises(ValueError):
                self.helper.authority(f.value, f.bindings, f.old, f.api, guard_repair=True)

    def test_original_build_and_donor_pins_cannot_be_new_candidate_receipts(self):
        f = self.fixture(); f.build['kind'] = self.helper.GUARD_REPAIR_BUILD_KIND
        with self.assertRaises(ValueError):
            self.helper.authority(f.value, f.bindings, f.old, f.api, guard_repair=True)
        f = self.fixture(); f.value['maintenance_build']['sha256'] = 'a' * 64
        with self.assertRaises(ValueError):
            self.helper.authority(f.value, f.bindings, f.old, f.api, guard_repair=True)

    def test_shape_exact48_and_direct_guard_without_archive_mapping(self):
        namespace = load_shape(); namespace['_successful_module'] = lambda: self.helper
        call = namespace['_completed_shape']; f = self.fixture()
        self.assertEqual(f.selected, call(f.inspection, f.old, f.value['objects'], successful=True, guard_repair=True))
        for successful, guard_repair in ((True, False), (False, True)):
            with self.assertRaises(ValueError): call(f.inspection, f.old, f.value['objects'], successful=successful, guard_repair=guard_repair)
        f.inspection.proof['replacements'][0]['object_id'] = 'ProviderGuard.cpp'
        with self.assertRaises(ValueError): call(f.inspection, f.old, f.value['objects'], successful=True, guard_repair=True)


class GuardRepairAccounting(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.namespace = load_receipt_functions()

    def fixture(self, guard_repair=True):
        temporary = tempfile.TemporaryDirectory(prefix='inert-guard-repair-accounting-')
        self.addCleanup(temporary.cleanup)
        return ReceiptFixture(Path(temporary.name), self.namespace, guard_repair=guard_repair)

    def test_exact48_threefresh_fivecopies_and_distinct_build_kind(self):
        f = self.fixture(); result = f.apply()
        self.assertEqual('foundation-document-v2-maintenance-successful-donor-guard-repair-build-v1', result['kind'])
        self.assertEqual((51, 48, 3, 5, 0), tuple(result['accounting'][key] for key in
            ('selected', 'imported', 'compiled', 'archive_imported', 'archive_repacked')))
        fresh = {'NativeDocumentV2Publisher.cpp', 'BibEngineDocumentWasmShim.cpp', 'ProviderGuard.cpp'}
        self.assertEqual([n for n in f.selected if n in fresh], result['accounting']['compiled_ids'])
        self.assertEqual([n for n in f.selected if n not in fresh], result['accounting']['imported_ids'])
        self.assertEqual(CONTRACT['archive_order'], [row['name'] for row in result['archive_imports']])

    def test_old_new_plan_and_partition_cannot_cross_lanes(self):
        for partition in (False, True):
            f = self.fixture(partition)
            f.plan['kind'] = ('foundation-document-v2-maintenance-successful-donor-plan-v1' if partition else
                              'foundation-document-v2-maintenance-successful-donor-guard-repair-plan-v1')
            with self.assertRaises(ValueError): f.apply()
        f = self.fixture(); f.plan['kind'] = 'foundation-document-v2-maintenance-plan-v1'
        with self.assertRaises(ValueError): f.apply()

    def test_reordered_imports_or_extra_compiler_reject(self):
        f = self.fixture(); f.plan['successful_donor']['objects'].reverse()
        with self.assertRaises(ValueError): f.apply()
        f = self.fixture(); f.commands['objects'][f.selected[0]] = ['unexpected compiler']
        with self.assertRaises(ValueError): f.apply()


class GuardRepairCommonValidator(CommonValidator):
    guard_repair = True

    def test_guard_and_publisher_source_delta_admitted_with_unchanged_shim(self):
        for name in ('ProviderGuard.cpp', 'NativeDocumentV2Publisher.cpp'):
            obj = next(row for row in self.f.proof['objects'] if row['id'] == name)
            obj['source']['sha256'] = self.change_current(self.f.current['sources'] / obj['source']['path'],
                                                         ('changed direct ' + name).encode())
        admitted = self.admit()
        self.assertEqual(48, len(admitted['objects']))
        self.assertNotIn('ProviderGuard.cpp', [row['id'] for row in admitted['objects']])
        self.assertEqual(16, len(self.f.proof['replacements']))

    def test_shim_delta_is_forbidden_even_though_fresh(self):
        obj = next(row for row in self.f.proof['objects'] if row['id'] == 'BibEngineDocumentWasmShim.cpp')
        obj['source']['sha256'] = self.change_current(self.f.current['sources'] / obj['source']['path'], b'changed shim')
        with self.assertRaisesRegex(ValueError, 'Shim'): self.admit()
        self.assertFalse(self.archive_calls)

    def test_guard_options_headers_unified_members_and_coordinates_reject(self):
        obj = next(row for row in self.f.proof['objects'] if row['id'] == 'ProviderGuard.cpp')
        before = deepcopy(obj)
        for key, changed in (('arguments', obj['arguments'] + ['-DNEW=1']),
                             ('exceptions', not obj['exceptions']),
                             ('dependencies', []), ('unified_members', [obj['source']]),
                             ('source', dict(obj['source'], path='units/elsewhere.cpp'))):
            obj[key] = changed
            with self.subTest(key=key), self.assertRaises(ValueError): self.admit()
            obj.clear(); obj.update(deepcopy(before))
        self.assertFalse(self.archive_calls)

    def test_guard_as_imported_actual_dependency_cannot_change(self):
        guard = next(row for row in self.f.proof['objects'] if row['id'] == 'ProviderGuard.cpp')
        old_path = self.f.bindings['sources'] / guard['source']['path']
        item = {'fact': support.fact(old_path), 'input': deepcopy(guard['source']), 'origin': 'retained'}
        self.f.sidecar['dependencies'][str(old_path)] = item
        row = self.f.value['objects'][0]
        row['dependency_keys'] = sorted(row['dependency_keys'] + [str(old_path)])
        row['depfile'] = support.write(Path(row['depfile']['path']),
            (row['object']['path'] + ': ' + ' '.join(row['dependency_keys']) + '\n').encode())
        self.f.value['dependency_sidecar'] = support.save(self.f.root / 'records/dependencies.json', self.f.sidecar)
        guard['source']['sha256'] = self.change_current(self.f.current['sources'] / guard['source']['path'], b'changed guard')
        with self.assertRaisesRegex(ValueError, 'Reference not bound'): self.admit()
        self.assertFalse(self.archive_calls)




class CompositionRepairDonor(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.helper = load_helper()

    def fixture(self):
        f = Donor(self.helper, composition_repair=True)
        f.value['kind'] = 'foundation-document-v2-successful-donor-composition-repair-v1'
        fresh = {'NativeDocumentV2Publisher.cpp', 'BibEngineDocumentWasmShim.cpp', 'ProviderGuard.cpp', 'BibNativeEditorBackend.cpp', 'main.cpp'}
        f.value['objects'] = [row for row in f.value['objects'] if row['id'] not in fresh]
        return f

    def test_exact_fivefresh_kinds_original112_and_archives(self):
        h = self.helper
        self.assertEqual(h.COMPOSITION_REPAIR_COMPILED_IDS,
            ('NativeDocumentV2Publisher.cpp', 'BibEngineDocumentWasmShim.cpp', 'ProviderGuard.cpp', 'BibNativeEditorBackend.cpp', 'main.cpp'))
        self.assertEqual(h.COMPOSITION_REPAIR_DONOR_KIND, 'foundation-document-v2-successful-donor-composition-repair-v1')
        self.assertEqual(h.COMPOSITION_REPAIR_PLAN_KIND, 'foundation-document-v2-maintenance-successful-donor-composition-repair-plan-v1')
        self.assertEqual(h.COMPOSITION_REPAIR_BUILD_KIND, 'foundation-document-v2-maintenance-successful-donor-composition-repair-build-v1')
        f = self.fixture()
        self.assertIs(f.api.original, h.authority(f.value, f.bindings, f.old, f.api, composition_repair=True))
        self.assertEqual(len(f.records),112)
        self.assertEqual(len(f.value['objects']),46)
        self.assertEqual(f.value['archives'], h.archive_rows(f.value, f.inspection, f.old, f.bindings, f.api, composition_repair=True))

    def test_all_three_descriptor_lanes_reject_crossings(self):
        for kind in (self.helper.DONOR_KIND,self.helper.GUARD_REPAIR_DONOR_KIND,self.helper.COMPOSITION_REPAIR_DONOR_KIND):
            for flags in ({},{'guard_repair':True},{'composition_repair':True}):
                f=self.fixture();f.value['kind']=kind
                if kind==self.helper.COMPOSITION_REPAIR_DONOR_KIND and flags=={'composition_repair':True}:
                    self.helper.authority(f.value,f.bindings,f.old,f.api,**flags)
                else:
                    with self.subTest(kind=kind,flags=flags),self.assertRaises(ValueError):
                        self.helper.authority(f.value,f.bindings,f.old,f.api,**flags)
        for flags in ({'composition_repair':1},{'composition_repair':True,'guard_repair':True}):
            f=self.fixture()
            with self.assertRaises(ValueError):self.helper.authority(f.value,f.bindings,f.old,f.api,**flags)

    def test_exact46_import_order_missing_extra_and_historical_pins_reject(self):
        for change in ('missing','reverse','duplicate','main','pin','ancestor-kind','boolschema'):
            f=self.fixture()
            if change=='missing':f.value['objects'].pop()
            elif change=='reverse':f.value['objects'].reverse()
            elif change=='duplicate':f.value['objects'].append(deepcopy(f.value['objects'][0]))
            elif change=='main':f.value['objects'].append({'id':'main.cpp'})
            elif change=='pin':f.value['original_plan']['sha256']='a'*64
            elif change=='ancestor-kind':f.build['kind']=self.helper.COMPOSITION_REPAIR_BUILD_KIND
            else:f.value['schema_version']=True
            with self.subTest(change=change),self.assertRaises(ValueError):
                self.helper.authority(f.value,f.bindings,f.old,f.api,composition_repair=True)

    def test_shape_requires_exact_direct_five_and_ordered46(self):
        f=self.fixture();n=load_shape();n['_successful_module']=lambda:self.helper
        self.assertEqual(f.selected,n['_completed_shape'](f.inspection,f.old,f.value['objects'],successful=True,composition_repair=True))
        for flags in ({'successful':True},{'successful':True,'guard_repair':True},
                      {'composition_repair':True},{'successful':True,'guard_repair':True,'composition_repair':True}):
            with self.subTest(flags=flags),self.assertRaises(ValueError):n['_completed_shape'](f.inspection,f.old,f.value['objects'],**flags)
        f.value['objects'].reverse()
        with self.assertRaises(ValueError):n['_completed_shape'](f.inspection,f.old,f.value['objects'],successful=True,composition_repair=True)

    def test_fresh_backend_or_main_cannot_be_archive_member(self):
        for name in ('BibNativeEditorBackend.cpp','main.cpp'):
            f=self.fixture();f.inspection.proof['replacements'][0]['object_id']=name
            f.old['reuse']['replacements'][0]['object_id']=name
            with self.subTest(name=name),self.assertRaises(ValueError):
                self.helper.archive_rows(f.value,f.inspection,f.old,f.bindings,f.api,composition_repair=True)


class CompositionRepairAccounting(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.namespace=load_receipt_functions()

    def fixture(self):
        temporary=tempfile.TemporaryDirectory(prefix='inert-composition-accounting-');self.addCleanup(temporary.cleanup)
        return ReceiptFixture(Path(temporary.name),self.namespace,composition_repair=True)

    def test_new46_five_compiled_five_imported_archives(self):
        f=self.fixture();result=f.apply()
        self.assertEqual(result['kind'],'foundation-document-v2-maintenance-successful-donor-composition-repair-build-v1')
        self.assertEqual(tuple(result['accounting'][k] for k in ('selected','imported','compiled','archive_imported','archive_repacked')),(51,46,5,5,0))
        fresh=['NativeDocumentV2Publisher.cpp','BibEngineDocumentWasmShim.cpp','ProviderGuard.cpp','BibNativeEditorBackend.cpp','main.cpp']
        self.assertEqual(result['accounting']['compiled_ids'],fresh)
        self.assertEqual(result['accounting']['imported_ids'],[x for x in f.selected if x not in fresh])
        self.assertEqual(51+5+2*46+3*5+5,168)

    def test_old_plan_or_reordered_imports_extra_compile_and_archive_tamper_reject(self):
        for change in ('old2','old3','order','compiler','archive'):
            f=self.fixture()
            if change=='old2':f.plan['kind']=self.namespace['SUCCESSFUL_PLAN_KIND']
            elif change=='old3':f.plan['kind']=self.namespace['GUARD_REPAIR_PLAN_KIND']
            elif change=='order':f.plan['successful_donor']['objects'].reverse()
            elif change=='compiler':f.commands['objects']['Other.cpp']=[]
            else:
                name='evidence/import-archive-WebCore.json';value=f.record(name);value['archive_program_invoked']=True;f.save(name,value)
            with self.subTest(change=change),self.assertRaises(ValueError):f.apply()



class NativeCapabilityShapeContextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.h = load_helper()
        cls.m = load_maintenance()

    def fixture(self):
        inspection, old, _, selected = shape_fixture(composition_repair=True)
        rename = {'Direct03.cpp': 'NativeFormsV2Combined.cpp', 'Direct04.cpp': 'NativeDocumentV2Types.cpp', 'Direct05.cpp': 'BibNativePopupOwner.cpp'}
        selected = [rename.get(name, name) for name in selected]
        inspection.profile['direct_objects'] = [rename.get(name, name) for name in inspection.profile['direct_objects']]
        objects = []
        for name in selected:
            source = dict(root='sources', path='units/' + name, sha256='1' * 64)
            objects.append(dict(id=name, source=source, arguments=['-fno-rtti'], exceptions=False,
                unified_members=[], dependencies=[source, dict(root='reuse', path='config.h', sha256='2' * 64)]))
        old['reuse']['objects'] = deepcopy(objects)
        inspection.proof['objects'] = deepcopy(objects)
        for key in ('host_tools', 'sdk_tools', 'python_launch', 'emscripten_config', 'private_cache', 'metadata', 'link'):
            old['reuse'][key] = inspection.proof[key] = {key: 'unchanged'}
        # The independent original fixture uses literal archive sizes and engine IDs.
        old['reuse']['archives'] = deepcopy(inspection.proof['archives'])
        rows = [dict(id=name, origin='p5-compiled' if name in ('ProviderGuard.cpp', 'BibNativeEditorBackend.cpp', 'main.cpp')
                     else 'legacy-imported') for name in selected if name not in
                ('NativeDocumentV2Publisher.cpp', 'NativeFormsV2Combined.cpp', 'NativeDocumentV2Types.cpp', 'BibEngineDocumentWasmShim.cpp', 'BibNativePopupOwner.cpp')]
        namespace = {'{sources}/units/' + name: '1' * 64 for name in selected}
        namespace['{reuse}/config.h'] = '2' * 64
        shared = dict(directories=['{sources}/units', '{reuse}'], physical_headers_sha256='3' * 64, vfs={})
        previous, current = dict(shared, namespace=deepcopy(namespace)), dict(shared, namespace=deepcopy(namespace))
        for row in inspection.proof['objects']:
            if row['id'] in ('NativeDocumentV2Publisher.cpp', 'NativeFormsV2Combined.cpp', 'NativeDocumentV2Types.cpp', 'BibNativePopupOwner.cpp'):
                prior = row['source']; row['source'] = dict(prior, sha256='4' * 64)
                row['dependencies'][0] = row['source']
                current['namespace']['{sources}/' + prior['path']] = '4' * 64
        return inspection, old, rows, selected, previous, current

    def test_exact_five_fresh_fortysix_imports_and_168_namespace(self):
        i, old, rows, selected, previous, current = self.fixture()
        self.assertEqual(selected, self.h.native_capability_shape(i, old, rows, self.m))
        self.h.native_capability_context_delta(i, old, previous, current, self.m)
        self.assertEqual((43, 3), tuple(sum(row['origin'] == origin for row in rows) for origin in ('legacy-imported', 'p5-compiled')))
        names = self.h.native_capability_artifact_names(selected, list(CONTRACT['archive_order']))
        self.assertEqual(168, len(names))
        self.assertIn('objects/BibEngineDocumentWasmShim.cpp.o.d', names)
        self.assertNotIn('evidence/import-BibEngineDocumentWasmShim.cpp.json', names)
        self.assertIn('objects/BibNativePopupOwner.cpp.o.d', names)
        self.assertNotIn('evidence/import-BibNativePopupOwner.cpp.json', names)
        self.assertIn('evidence/import-main.cpp.original.d', names)

    def test_partition_origin_missing_duplicate_reorder_and_extra_fields_reject(self):
        for change in ('missing', 'duplicate', 'reverse', 'extra', 'origin', 'shim-import', 'unknown'):
            i, old, rows, _, _, _ = self.fixture()
            if change == 'missing': rows.pop()
            elif change == 'duplicate': rows[1] = deepcopy(rows[0])
            elif change == 'reverse': rows.reverse()
            elif change == 'extra': rows[0]['trusted'] = True
            elif change == 'origin': next(r for r in rows if r['id'] == 'main.cpp')['origin'] = 'legacy-imported'
            else: rows[0]['id'] = 'BibEngineDocumentWasmShim.cpp' if change == 'shim-import' else 'Unknown.cpp'
            with self.subTest(change=change), self.assertRaises(ValueError): self.h.native_capability_shape(i, old, rows, self.m)

    def test_archive_engine_membership_and_fresh_direct_boundary_cannot_change(self):
        for change in ('member-count', 'replacement', 'direct', 'order'):
            i, old, rows, _, _, _ = self.fixture()
            if change == 'member-count': i.proof['archives'][0]['members'].pop()
            elif change == 'replacement': i.proof['replacements'][0]['object_id'] = 'main.cpp'
            elif change == 'direct': i.profile['direct_objects'].remove('NativeFormsV2Combined.cpp')
            else: i.proof['objects'].reverse()
            with self.subTest(change=change), self.assertRaises(ValueError): self.h.native_capability_shape(i, old, rows, self.m)

    def test_no_header_namespace_physical_vfs_or_undeclared_source_waiver(self):
        for change in ('header', 'added', 'removed', 'physical', 'vfs', 'shim', 'imported', 'missing-native'):
            i, old, _, _, previous, current = self.fixture()
            if change == 'header': current['namespace']['{reuse}/config.h'] = '5' * 64
            elif change == 'added': current['namespace']['{sources}/new.h'] = '5' * 64
            elif change == 'removed': current['namespace'].pop(next(iter(current['namespace'])))
            elif change == 'physical': current['physical_headers_sha256'] = '5' * 64
            elif change == 'vfs': current['vfs'] = {'changed': True}
            elif change in ('shim', 'imported'):
                name = 'BibEngineDocumentWasmShim.cpp' if change == 'shim' else 'main.cpp'
                row = next(r for r in i.proof['objects'] if r['id'] == name); row['source']['sha256'] = '5' * 64
            else:
                row = next(r for r in i.proof['objects'] if r['id'] == 'NativeDocumentV2Types.cpp')
                row['source']['sha256'] = '1' * 64
            with self.subTest(change=change), self.assertRaises(ValueError): self.h.native_capability_context_delta(i, old, previous, current, self.m)


    def test_arguments_unified_dependency_and_tool_metadata_changes_reject(self):
        for change in ('arguments', 'unified_members', 'exceptions', 'dependencies', 'source-path',
                       'host_tools', 'sdk_tools', 'private_cache', 'metadata', 'link'):
            i, old, _, _, previous, current = self.fixture()
            row = i.proof['objects'][0]
            if change in ('arguments', 'unified_members', 'dependencies'): row[change] = ['forged']
            elif change == 'exceptions': row[change] = True
            elif change == 'source-path': row['source'] = dict(row['source'], path='different.cpp')
            else: i.proof[change] = {'changed': True}
            with self.subTest(change=change), self.assertRaises(ValueError): self.h.native_capability_context_delta(i, old, previous, current, self.m)


class NativeControlKeypressShapeContextTests(unittest.TestCase):
    """F6 is a separate six-fresh lane over the same exact P5 baseline."""
    @classmethod
    def setUpClass(cls):
        cls.h = load_helper()
        cls.m = load_maintenance()

    def fixture(self):
        i, old, _, selected, previous, current = NativeCapabilityShapeContextTests.fixture(self)
        old_name, new_name = 'Direct06.cpp', 'BibDocumentPhysicalProvider.cpp'
        self.assertIn(old_name, selected)
        selected = [new_name if name == old_name else name for name in selected]
        i.profile['direct_objects'] = [new_name if name == old_name else name for name in i.profile['direct_objects']]
        for object_set in (old['reuse']['objects'], i.proof['objects']):
            row = next(row for row in object_set if row['id'] == old_name)
            row['id'] = new_name
            row['source'] = dict(row['source'], path='units/' + new_name)
            row['dependencies'][0] = row['source']
        new_source = next(row for row in i.proof['objects'] if row['id'] == new_name)
        prior_source = next(row for row in old['reuse']['objects'] if row['id'] == new_name)['source']
        new_source['source'] = dict(new_source['source'], sha256='5' * 64)
        new_source['dependencies'][0] = new_source['source']
        previous['namespace'].pop('{sources}/units/' + old_name)
        current['namespace'].pop('{sources}/units/' + old_name)
        previous['namespace']['{sources}/units/' + new_name] = prior_source['sha256']
        current['namespace']['{sources}/units/' + new_name] = '5' * 64
        fresh = set(self.h.NATIVE_CONTROL_KEYPRESS_REPAIR_COMPILED_IDS)
        rows = [dict(id=name, origin='p5-compiled' if name in ('ProviderGuard.cpp', 'BibNativeEditorBackend.cpp', 'main.cpp')
                     else 'legacy-imported') for name in selected if name not in fresh]
        return i, old, rows, selected, previous, current

    def test_exact_six_fresh_45_imports_and_167_artifacts(self):
        i, old, rows, selected, previous, current = self.fixture()
        self.assertEqual(selected, self.h.native_control_keypress_shape(i, old, rows, self.m))
        self.h.native_control_keypress_context_delta(i, old, previous, current, self.m)
        self.assertEqual((42, 3), tuple(sum(row['origin'] == origin for row in rows)
            for origin in ('legacy-imported', 'p5-compiled')))
        names = self.h.native_control_keypress_artifact_names(selected, list(CONTRACT['archive_order']))
        self.assertEqual(167, len(names))
        self.assertIn('objects/BibDocumentPhysicalProvider.cpp.o.d', names)
        self.assertNotIn('evidence/import-BibDocumentPhysicalProvider.cpp.json', names)
        self.assertIn('evidence/import-BibNativeEditorBackend.cpp.original.d', names)

    def test_each_historical_five_lane_refuses_f6_partition_and_f6_refuses_old_five(self):
        i, old, rows, _, _, _ = self.fixture()
        with self.assertRaises(ValueError): self.h.native_capability_shape(i, old, rows, self.m)
        old_fixture = NativeCapabilityShapeContextTests.fixture(self)
        oi, oo, old_rows, selected, _, _ = old_fixture
        with self.assertRaises(ValueError): self.h.native_control_keypress_shape(oi, oo, old_rows, self.m)

    def test_order_origin_and_exact_unit_set_are_closed(self):
        for change in ('order', 'origin', 'missing-provider', 'wrong-provider', 'extra-provider', 'shim',
                       'member-count', 'replacement-owner', 'direct-boundary', 'selected-order'):
            i, old, rows, _, _, _ = self.fixture()
            if change == 'order': rows.reverse()
            elif change == 'origin': next(row for row in rows if row['id'] == 'main.cpp')['origin'] = 'legacy-imported'
            elif change == 'missing-provider': i.profile['direct_objects'].remove('BibDocumentPhysicalProvider.cpp')
            elif change == 'wrong-provider': rows.append(dict(id='BibDocumentPhysicalProvider.cpp', origin='legacy-imported'))
            elif change == 'extra-provider': rows.append(dict(id='Bogus.cpp', origin='legacy-imported'))
            elif change == 'shim': rows.append(dict(id='BibEngineDocumentWasmShim.cpp', origin='p5-compiled'))
            elif change == 'member-count': i.proof['archives'][0]['members'].pop()
            elif change == 'replacement-owner': i.proof['replacements'][0]['object_id'] = 'main.cpp'
            elif change == 'direct-boundary': i.profile['direct_objects'].remove('BibDocumentPhysicalProvider.cpp')
            else: i.proof['objects'].reverse()
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.h.native_control_keypress_shape(i, old, rows, self.m)

    def test_source_delta_allows_five_named_bodies_and_rejects_unmodified_or_unselected(self):
        i, old, _, _, previous, current = self.fixture()
        changed = {name for name, pin in previous['namespace'].items() if current['namespace'].get(name) != pin}
        self.assertEqual(5, len(changed))
        self.h.native_control_keypress_context_delta(i, old, previous, current, self.m)
        # An allowed source must differ from its exact predecessor; changing it
        # to an arbitrary third hash is admitted here and pinned by donor capture.
        i, old, _, _, previous, current = self.fixture()
        name = 'BibDocumentPhysicalProvider.cpp'
        row = next(row for row in i.proof['objects'] if row['id'] == name)
        before = next(prior for prior in old['reuse']['objects'] if prior['id'] == name)['source']
        row['source'] = dict(row['source'], sha256=before['sha256'])
        row['dependencies'][0] = row['source']
        current['namespace']['{sources}/' + row['source']['path']] = before['sha256']
        with self.assertRaises(ValueError): self.h.native_control_keypress_context_delta(i, old, previous, current, self.m)
        for name in ('BibEngineDocumentWasmShim.cpp', 'main.cpp'):
            ii, oo, _, _, pp, cc = self.fixture()
            row = next(row for row in ii.proof['objects'] if row['id'] == name)
            row['source'] = dict(row['source'], sha256='6' * 64)
            row['dependencies'][0] = row['source']
            cc['namespace']['{sources}/' + row['source']['path']] = '6' * 64
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.h.native_control_keypress_context_delta(ii, oo, pp, cc, self.m)

    def test_f6_source_context_rejects_header_namespace_vfs_physical_and_policy_changes(self):
        for change in ('header', 'added', 'removed', 'physical', 'vfs', 'arguments', 'unified_members',
                       'exceptions', 'dependencies', 'source-path', 'host_tools', 'sdk_tools',
                       'private_cache', 'metadata', 'link'):
            i, old, _, _, previous, current = self.fixture()
            if change == 'header': current['namespace']['{reuse}/config.h'] = '5' * 64
            elif change == 'added': current['namespace']['{sources}/new.h'] = '5' * 64
            elif change == 'removed': current['namespace'].pop(next(iter(current['namespace'])))
            elif change == 'physical': current['physical_headers_sha256'] = '5' * 64
            elif change == 'vfs': current['vfs'] = {'changed': True}
            elif change in ('arguments', 'unified_members', 'dependencies'):
                i.proof['objects'][0][change] = ['forged']
            elif change == 'exceptions': i.proof['objects'][0][change] = True
            elif change == 'source-path': i.proof['objects'][0]['source'] = dict(i.proof['objects'][0]['source'], path='units/elsewhere.cpp')
            else: i.proof[change] = {'changed': True}
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.h.native_control_keypress_context_delta(i, old, previous, current, self.m)

    def test_f6_metadata_kind_is_separate_and_keeps_p5_pins(self):
        fixture = NativeCapabilityP5MetadataFixture(self.h, self.m)
        fixture.value['kind'] = self.h.NATIVE_CONTROL_KEYPRESS_REPAIR_DONOR_KIND
        self.h._p5_metadata(fixture.value, fixture.inspection, fixture.api, control_keypress=True)
        with self.assertRaises(ValueError): self.h._p5_metadata(fixture.value, fixture.inspection, fixture.api)
        fixture.value['p5_plan']['sha256'] = '0' * 64
        with self.assertRaises(ValueError): self.h._p5_metadata(fixture.value, fixture.inspection, fixture.api, control_keypress=True)



class NativeCapabilityP5MetadataFixture:
    """Fabricated trusted-reader documents; never reads a retained product/SDK."""
    def __init__(self, h, m):
        self.h, self.m = h, m
        self.api = Reader()
        self.api.SCOPE, self.api.ROOT = m.SCOPE, Path('/invented/repository')
        self.api.profile_path = lambda selected: 'profile-' + selected + '.json'
        self.api.digest = lambda path: '9' * 64
        self.api._completed_binding = m._completed_binding
        self.bindings = {key: Path('/invented/p5-' + key) for key in ('sources', 'sdk', 'reuse', 'build')}
        i, old, rows, selected, _, _ = NativeCapabilityShapeContextTests.fixture(SimpleNamespace(h=h, m=m))
        self.inspection = i; self.selected = selected
        i.selection = dict(document_profile='editor', sdk_manifest_sha256='8' * 64)
        i.roots = {'sdk': self.bindings['sdk']}
        self.docs = {}
        self.value = dict(schema_version=1, kind=h.NATIVE_CAPABILITY_REPAIR_DONOR_KIND,
            document_profile='editor', p5_bindings={k: str(v) for k, v in self.bindings.items()},
            legacy_donor={'path': '/invented/legacy/descriptor.json', 'sha256': '747858f13c1878d7829aab79f933e75100f706a76b5f69f4eb0d2a670510b54e'},
            objects=rows, archives=[], p5_private={}, p5_ninja_log={}, p5_compiled=[])
        paths = {name: '/invented/authority/' + name + '.json' for name in h.P5_PINS}
        paths['p5_plan'] = '/invented/p5-plan/plan.json'
        paths['p5_maintenance_build'] = str(self.bindings['build'] / 'maintenance-build.json')
        paths['p5_commands'] = str(self.bindings['build'] / 'evidence/commands.json')
        for name, pin in h.P5_PINS.items(): self.value[name] = {'path': paths[name], 'sha256': pin}
        self.api.documents[(self.value['legacy_donor']['path'], self.value['legacy_donor']['sha256'])] = {}
        self.records = {}
        fresh = {'NativeDocumentV2Publisher.cpp', 'BibEngineDocumentWasmShim.cpp', 'ProviderGuard.cpp', 'BibNativeEditorBackend.cpp', 'main.cpp'}
        names = list(CONTRACT['archive_order'])
        product_names = {'artifacts/foundation-retained-engine.mjs', 'artifacts/foundation-retained-engine.wasm',
            'document-generated/BibCopiedDocumentMetadata.generated.h', 'document-generated/provider-build.json', 'evidence/engine-link.map'}
        for name in selected:
            product_names.add('objects/' + name + '.o')
            if name in fresh: product_names.add('objects/' + name + '.o.d')
            else: product_names.update(('evidence/import-' + name + '.json', 'evidence/import-' + name + '.original.d'))
        for name in names: product_names.update(('archives/lib' + name + '.a', 'evidence/archive-' + name + '.json', 'evidence/import-archive-' + name + '.json'))
        for index, name in enumerate(sorted(product_names)):
            self.records[name] = self.fact(str(self.bindings['build'] / name), index + 1)
        natural = dict(schema_version=1, primary_returncode=0, descendants_outlived=False, terminated=False, reaped=1, error=None)
        accounting = dict(selected=51, compiled=5, imported=46, archive_imported=5, archive_repacked=0,
            compiled_ids=[n for n in selected if n in fresh], imported_ids=[n for n in selected if n not in fresh], imported_archive_names=names)
        selection = dict(document_profile='editor', sources=str(self.bindings['sources']), sdk=str(self.bindings['sdk']),
            reuse_root=str(self.bindings['reuse']), sdk_manifest_sha256='8' * 64, recipe_sha256='6' * 64, sources_sha256='7' * 64)
        old.update(schema_version=1, kind=h.COMPOSITION_REPAIR_PLAN_KIND, production_eligible=False, scope=m.SCOPE,
            selection=selection, profile_sha256='9' * 64, producer_inputs={'tools/frozen.py': 'a' * 64}, successful_donor={'reference': self.value['legacy_donor']})
        build = dict(schema_version=1, kind=h.COMPOSITION_REPAIR_BUILD_KIND, status='passed', production_eligible=False,
            accounting=deepcopy(accounting), plan_sha256=h.P5_PINS['p5_plan'], source_recipe_sha256='6' * 64,
            sources_sha256='7' * 64, paired_sdk_sha256='8' * 64,
            commands={'path': 'evidence/commands.json', 'sha256': h.P5_PINS['p5_commands']},
            objects=[dict(id=n, sha256=self.records['objects/' + n + '.o']['sha256'], bytes=self.records['objects/' + n + '.o']['bytes']) for n in selected],
            inspection={'inert': 'inspection'})
        result = dict(status='passed', returncode=0, closed=True, verified=True, writers_joined=True, runtime_not_run=True,
            production_eligible=False, static_byte_readback='passed', input_identity_namespace_postflight='passed',
            supervisor_report=deepcopy(natural), actual_objects=51, actual_archive_reports=5, opaque_unchanged_members=2060,
            artifact_records=self.records, successful_donor={'accounting': deepcopy(accounting)},
            maintenance_build_sha256=h.P5_PINS['p5_maintenance_build'], inspection_sha256=digest(encoded(build['inspection'])))
        build['successful_donor'] = self.value['legacy_donor']
        result['successful_donor'].update(successful_donor=self.value['legacy_donor'], independent_copies=True, original_dependencies_retained=True)
        root = dict(schema_version=1, kind='root-closed-successful-donor-composition-repair-candidate-accepted-v1', status='passed',
            actual_session=4865, caller_observed_exit=0, closed=True, writers_joined=True, inputs_unchanged=True,
            runtime_not_run=True, production_eligible=False, input_identity_namespace_postflight='passed',
            all_artifact_physical_identities_root_rechecked=True, verified_artifact_records=168, qualified_report=deepcopy(natural), records={})
        ref_fields = {'closed': 'p5_closed_result', 'commands': 'p5_commands', 'maintenance_build': 'p5_maintenance_build', 'plan': 'p5_plan', 'donor_descriptor': 'legacy_donor'}
        for index, (name, key) in enumerate(ref_fields.items()):
            fact = self.fact(self.value[key]['path'], 200 + index, self.value[key]['sha256'])
            root['records'][name] = self.flat(fact)
        root['records']['inspection'] = self.flat(self.fact('/invented/inspection.json', 209, result['inspection_sha256']))
        root['artifact_records_sha256'] = digest((json.dumps(self.records, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False) + '\n').encode('ascii'))
        packet = dict(kind='editor-rich-ui-successful-donor-composition-repair-build-launch-v1', selection=selection,
            producer_inputs=old['producer_inputs'], plan=self.value['p5_plan']['path'], plan_sha256=h.P5_PINS['p5_plan'],
            freeze=self.value['p5_input_freeze']['path'], freeze_sha256=h.P5_PINS['p5_input_freeze'],
            preparation_acceptance=self.value['p5_preparation_acceptance'], output=str(self.bindings['build']),
            policy=dict(cold_fallback=False, header_odr_waiver=False, production_eligible=False, runtime=False, timestamp_seeding=False))
        packet['argv'] = ['./build.sh', 'engine-maintenance', 'document-build', '--plan', packet['plan'], '--plan-sha256', packet['plan_sha256'], '--output', packet['output'], '--jobs', '1', '--timeout-seconds', '2700']
        freeze = dict(schema_version=1, kind='editor-rich-ui-input-freeze-v1', actual_plan_or_build=False,
            roots={k: str(v) for k, v in self.bindings.items() if k != 'build'}, files={}, directories={})
        for path, pin in [(self.bindings['sources'] / 'recipe.json', '6' * 64),
                          (self.bindings['sources'] / 'sources.json', '7' * 64),
                          (self.bindings['sources'] / 'tools/frozen.py', 'a' * 64), (self.bindings['sdk'] / 'sdk.json', '8' * 64)]:
            freeze['files'][str(path)] = dict(sha256=pin)
        preparation = dict(status='passed', closed=True, writers_joined=True, caller_observed_exit=0,
            input_identity_namespace_postflight='passed', production_eligible=False)
        vfs = self.fact(str(self.bindings['build'] / 'private/header-identity-vfs.json'), 220)
        self.value['p5_private'] = dict(vfs=vfs, configuration={}, launcher={})
        gate = dict(kind='root-P5-actual-VFS-five-depfile-gate-v1', status='passed', actual_session=4865,
            five_depfile_ownership='passed', result_sha256=h.P5_PINS['p5_closed_result'], packet_sha256=h.P5_PINS['p5_build_packet'],
            production_eligible=False, actual_VFS=vfs, depfile_records={'objects/' + n + '.o.d': self.records['objects/' + n + '.o.d'] for n in fresh})
        commands = dict(objects={n: [] for n in fresh}, imports={n: [] for n in selected if n not in fresh},
            archive_imports={n: [] for n in names}, metadata=[], link=[])
        self.docs.update(zip(h.P5_PINS, (root, result, old, build, commands, packet, freeze, preparation, gate)))
        for name, document in self.docs.items():
            ref = self.value[name]; self.api.documents[(ref['path'], ref['sha256'])] = document

    def fact(self, path, index, pin=None):
        value = dict(path=path, sha256=pin or digest(path), bytes=index + 10, mode=0o644,
            identity=[31, index + 100, 0o100644, 1, index + 10, 1000, 1001])
        self.api.facts[path] = deepcopy(value)
        return value

    @staticmethod
    def flat(fact):
        i = fact['identity']
        return dict(path=fact['path'], sha256=fact['sha256'], bytes=fact['bytes'], dev=i[0], ino=i[1],
            mode=fact['mode'], nlink=i[3], mtime_ns=i[5], ctime_ns=i[6])

    def check(self): return self.h._p5_metadata(self.value, self.inspection, self.api)


class NativeCapabilityP5MetadataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.h, cls.m = load_helper(), load_maintenance()

    def fixture(self): return NativeCapabilityP5MetadataFixture(self.h, self.m)

    def test_complete_pinned_p5_chain_preserves_168_original_products(self):
        f = self.fixture(); docs, bindings, records = f.check()
        self.assertEqual(168, len(records))
        self.assertEqual(f.bindings, bindings)
        self.assertIs(f.docs['p5_plan'], docs['p5_plan'])
        self.assertEqual('passed', f.docs['p5_closed_result']['status'])

    def test_p5_root_index_requires_the_original_newline(self):
        f = self.fixture()
        # This is the original Root receipt writer's format, including its final
        # newline; the producer must admit that authority rather than restamp it.
        compact = json.dumps(f.records, sort_keys=True, separators=(',', ':'),
                             ensure_ascii=True, allow_nan=False).encode('ascii')
        root = f.docs['p5_root_acceptance']
        self.assertEqual(digest(compact + b'\n'), root['artifact_records_sha256'])
        f.check()
        root['artifact_records_sha256'] = digest(compact)
        with self.assertRaisesRegex(ValueError, 'P5 product index differs'):
            f.check()

    def test_wrong_descriptor_kind_profile_fields_and_pins_reject(self):
        for change in ('schema', 'kind', 'profile', 'extra', *self.h.P5_PINS):
            f = self.fixture()
            if change == 'schema': f.value['schema_version'] = True
            elif change == 'kind': f.value['kind'] = self.h.COMPOSITION_REPAIR_DONOR_KIND
            elif change == 'profile': f.value['document_profile'] = 'physical'
            elif change == 'extra': f.value['eligible'] = True
            else: f.value[change]['sha256'] = 'f' * 64
            with self.subTest(change=change), self.assertRaises(ValueError): f.check()

    def test_root_caller_status_natural_and_physical_reference_negatives(self):
        for change in ('closed', 'session', 'caller', 'runtime', 'natural', 'physical', 'artifact-hash', 'artifact-extra', 'hardlink'):
            f = self.fixture(); root = f.docs['p5_root_acceptance']
            if change == 'closed': root['closed'] = False
            elif change == 'session': root['actual_session'] = True
            elif change == 'caller': f.docs['p5_closed_result']['returncode'] = False
            elif change == 'runtime': root['runtime_not_run'] = False
            elif change == 'natural': root['qualified_report']['terminated'] = True
            elif change == 'physical': root['records']['plan']['ino'] += 1
            elif change == 'artifact-hash': root['artifact_records_sha256'] = 'f' * 64
            elif change == 'artifact-extra': f.records['unrelated'] = deepcopy(next(iter(f.records.values())))
            else:
                fact = next(iter(f.records.values())); fact['identity'][3] = 2
                root['artifact_records_sha256'] = digest((json.dumps(f.records, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False) + '\n').encode('ascii'))
            with self.subTest(change=change), self.assertRaises(ValueError): f.check()

    def test_source_sdk_freeze_packet_build_command_and_gate_joins_reject(self):
        for change in ('SDK', 'freeze', 'launch', 'policy', 'recipe', 'commands', 'count-bool', 'VFS', 'depfile', 'legacy'):
            f = self.fixture()
            if change == 'SDK': f.inspection.selection['sdk_manifest_sha256'] = 'f' * 64
            elif change == 'freeze': f.docs['p5_input_freeze']['files'].clear()
            elif change == 'launch': f.docs['p5_build_packet']['argv'][-1] = '9999'
            elif change == 'policy': f.docs['p5_build_packet']['policy']['cold_fallback'] = True
            elif change == 'recipe': f.docs['p5_maintenance_build']['source_recipe_sha256'] = 'f' * 64
            elif change == 'commands': f.docs['p5_commands']['objects']['extra.cpp'] = []
            elif change == 'count-bool': f.docs['p5_maintenance_build']['accounting']['archive_repacked'] = False
            elif change == 'VFS': f.value['p5_private']['vfs'] = {}
            elif change == 'depfile': f.docs['p5_vfs_dependency_gate']['depfile_records'].clear()
            else: f.value['legacy_donor'] = dict(f.value['legacy_donor'], sha256='f' * 64)
            with self.subTest(change=change), self.assertRaises(ValueError): f.check()


class NativeCapabilityP5CompiledFixture(NativeCapabilityP5MetadataFixture):
    def __init__(self, h, m):
        super().__init__(h, m)
        old = self.docs['p5_plan']; proof = old['reuse']; freeze = self.docs['p5_input_freeze']
        self.old_inspection = SimpleNamespace(proof=proof, roots={k: v for k, v in self.bindings.items() if k != 'build'},
            inventories={'sources': {}, 'sdk': {}, 'reuse': {}})
        self.api._completed_arguments = m._completed_arguments
        self.api._depfile_inputs = m._depfile_inputs
        self.api._completed_ninja_command = m._completed_ninja_command
        original_fact_reader = self.api._completed_fact
        self.api._completed_fact = lambda fact, **kwargs: original_fact_reader(fact)
        self.api.ordinary = lambda path, *args, **kwargs: Path(path)
        self.api.checked_read = lambda path, pin: self.api.raw[str(path)]
        def reference(ref, roots, inventories):
            if inventories[ref['root']].get(ref['path']) != ref['sha256']: raise ValueError('fixture inventory mismatch')
            return roots[ref['root']] / ref['path']
        self.api.ref_path = reference
        proof['host_tools'] = {'cmake': {'path': '/invented/cmake', 'version': 'cmake version 3.31.6'},
                               'ninja': {'path': '/invented/ninja', 'version': '1.12.1'}}
        proof['private_cache'] = dict(root='cache', files=['cache/sysroot/include/cache.h'])
        for index, obj in enumerate(proof['objects']):
            obj['arguments'] = ['-fno-rtti']
            source = obj['source']; path = self.bindings['sources'] / source['path']
            fact = self.fact(str(path), 300 + index, source['sha256'])
            freeze['files'][str(path)] = fact
            self.old_inspection.inventories['sources'][source['path']] = source['sha256']
        common = self.bindings['sources'] / 'units/common.h'
        common_fact = self.fact(str(common), 360)
        freeze['files'][str(common)] = common_fact
        self.old_inspection.inventories['sources']['units/common.h'] = common_fact['sha256']
        sdk_path = self.bindings['sdk'] / 'cache/sysroot/include/cache.h'
        sdk_fact = self.fact(str(sdk_path), 361)
        freeze['files'][str(sdk_path)] = sdk_fact
        self.old_inspection.inventories['sdk']['cache/sysroot/include/cache.h'] = sdk_fact['sha256']
        cache_path = self.bindings['build'] / 'private/cache/sysroot/include/cache.h'
        self.api.raw[str(cache_path)] = b'inert cache seed'
        cwd = str(self.bindings['build'] / 'cmake/build')
        graph_source = str(self.bindings['sources'] / Path(m.GRAPH_PATH).parent)
        log = ['# ninja log v6']
        commands = self.docs['p5_commands']['objects']
        self.dependencies = {}
        for name in [r['id'] for r in proof['objects'] if r['id'] in h.COMPOSITION_REPAIR_COMPILED_IDS]:
            obj = next(r for r in proof['objects'] if r['id'] == name)
            target = str(self.bindings['build'] / ('objects/' + name + '.o')); depfile = target + '.d'
            argv = [str(self.bindings['sdk'] / 'upstream/emscripten/em++'), '-ivfsoverlay',
                str(self.bindings['build'] / 'private/header-identity-vfs.json'), '-fno-rtti',
                '-MD', '-MT', target, '-MF', depfile, '-o', target,
                '-c', str(self.bindings['sources'] / obj['source']['path'])]
            commands[name] = argv
            transformed = str(self.bindings['build'] / ('cmake/build/CMakeFiles/d/' + hashlib.sha256(depfile.encode()).hexdigest() + '.d'))
            transform = ['/invented/cmake', '-E', 'cmake_transform_depfile', 'Ninja', 'gccdepfile',
                graph_source, graph_source, cwd, cwd, depfile, transformed]
            command = ' '.join(['cd', cwd, '&&', *argv, '&&', *transform])
            record = ['0', '1', str(self.records['objects/' + name + '.o']['identity'][5]), target, m._completed_ninja_hash(command)]
            self.value['p5_compiled'].append(dict(id=name, ninja_record=record, ninja_command=command, command_script=None))
            log.append('\t'.join(record))
            keys = [str(self.bindings['sources'] / obj['source']['path']), str(common), str(cache_path)]
            if name == 'BibEngineDocumentWasmShim.cpp': keys.append(str(self.bindings['build'] / 'document-generated/BibCopiedDocumentMetadata.generated.h'))
            self.dependencies[name] = keys
            self.set_dependencies(name, keys)
        log_fact = self.fact(str(self.bindings['build'] / 'cmake/build/.ninja_log'), 370)
        self.value['p5_ninja_log'] = log_fact
        self.api.raw[log_fact['path']] = ('\n'.join(log) + '\n').encode()

    def set_dependencies(self, name, keys):
        target = str(self.bindings['build'] / ('objects/' + name + '.o'))
        self.api.raw[target + '.d'] = (target + ': ' + ' '.join(keys) + '\n').encode()

    def compiled(self):
        return self.h._p5_compiled_rows(self.value, self.old_inspection, self.bindings,
            self.docs['p5_input_freeze'], self.records, self.docs['p5_commands'], self.api)


class NativeCapabilityP5CompiledTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.h, cls.m = load_helper(), load_maintenance()

    def fixture(self): return NativeCapabilityP5CompiledFixture(self.h, self.m)

    def test_three_imports_retain_actual_p5_compiler_depfile_and_ninja(self):
        f = self.fixture(); admitted, refs = f.compiled()
        self.assertEqual({'ProviderGuard.cpp', 'BibNativeEditorBackend.cpp', 'main.cpp'}, {r['id'] for r in admitted})
        self.assertTrue(all(r['original_cwd'] == str(f.bindings['build'] / 'cmake/build') for r in admitted))
        self.assertTrue(all(r['object'] == f.records['objects/' + r['id'] + '.o'] for r in admitted))
        self.assertTrue(any(ref['path'] == 'cache/sysroot/include/cache.h' for ref in refs))
        self.assertFalse(any('generated' in ref['path'] for ref in refs))
        self.assertEqual(5, sum(path.endswith('.o.d') for path in f.api.fact_reads))

    def test_missing_or_extra_compiler_evidence_and_wrong_ninja_coordinates_reject(self):
        for change in ('missing', 'reverse', 'extra', 'mtime', 'hash', 'argv-source', 'overlay', 'output'):
            f = self.fixture(); rows = f.value['p5_compiled']
            if change == 'missing': rows.pop()
            elif change == 'reverse': rows.reverse()
            elif change == 'extra': rows[0]['eligible'] = True
            elif change == 'mtime': rows[0]['ninja_record'][2] = '999'
            elif change == 'hash': rows[0]['ninja_record'][4] = 'bad'
            else:
                argv = f.docs['p5_commands']['objects'][rows[0]['id']]
                flag = {'argv-source': '-c', 'overlay': '-ivfsoverlay', 'output': '-o'}[change]
                argv[argv.index(flag) + 1] = '/invented/wrong'
            with self.subTest(change=change), self.assertRaises(ValueError): f.compiled()

    def test_generated_unknown_source_missing_and_cache_unseeded_dependencies_reject(self):
        name = 'main.cpp'
        for change in ('generated', 'outside', 'source-missing', 'cache', 'variable', 'shim-missing'):
            f = self.fixture(); owner = 'BibEngineDocumentWasmShim.cpp' if change == 'shim-missing' else name
            keys = list(f.dependencies[owner])
            if change == 'generated': keys.append(str(f.bindings['build'] / 'document-generated/BibCopiedDocumentMetadata.generated.h'))
            elif change == 'outside': keys.append('/invented/unowned/header.h')
            elif change == 'source-missing': keys.pop(0)
            elif change == 'cache': keys.append(str(f.bindings['build'] / 'private/cache/unseeded.h'))
            elif change == 'shim-missing': keys.pop()
            else: keys.append('$(EXPAND)')
            f.set_dependencies(owner, keys)
            with self.subTest(change=change), self.assertRaises(ValueError): f.compiled()

    def test_frozen_dependency_identity_and_inventory_hash_are_required(self):
        for change in ('missing-fact', 'fact-inode', 'inventory'):
            f = self.fixture(); path = str(f.bindings['sources'] / 'units/common.h')
            if change == 'missing-fact': del f.docs['p5_input_freeze']['files'][path]
            elif change == 'fact-inode': f.docs['p5_input_freeze']['files'][path]['identity'][1] += 1
            else: f.old_inspection.inventories['sources']['units/common.h'] = 'f' * 64
            with self.subTest(change=change), self.assertRaises(ValueError): f.compiled()


class NativeCapabilityReceiptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.namespace = load_receipt_functions()
        cls.namespace['ordinary'] = load_maintenance().ordinary

    def fixture(self):
        temporary = tempfile.TemporaryDirectory(prefix='inert-native-capability-receipt-')
        self.addCleanup(temporary.cleanup)
        return ReceiptFixture(Path(temporary.name), self.namespace, composition_repair=True, native_capability_repair=True)

    def test_exact_five_fresh_fortysix_imports_168_evidence_and_real_origins(self):
        f = self.fixture(); result = f.apply()
        self.assertEqual('foundation-document-v2-maintenance-successful-donor-native-capability-repair-build-v1', result['kind'])
        self.assertEqual((51, 46, 5, 5, 0), tuple(result['accounting'][key] for key in
            ('selected', 'imported', 'compiled', 'archive_imported', 'archive_repacked')))
        self.assertEqual(168, result['expected_artifact_records'])
        self.assertEqual((43, 3), tuple(sum(row['donor_provenance']['compile_origin'] == origin for row in f.plan['successful_donor']['objects']) for origin in ('legacy-imported', 'p5-compiled')))
        self.assertEqual(['NativeDocumentV2Publisher.cpp', 'BibEngineDocumentWasmShim.cpp', 'NativeFormsV2Combined.cpp', 'NativeDocumentV2Types.cpp', 'BibNativePopupOwner.cpp'], result['accounting']['compiled_ids'])

    def test_crosslane_kind_and_old_compilation_partition_reject(self):
        for change in ('legacy', 'composition', 'three', 'five', 'missing-import', 'extra-compiler'):
            f = self.fixture()
            if change == 'legacy': f.plan['kind'] = self.namespace['SUCCESSFUL_PLAN_KIND']
            elif change == 'composition': f.plan['kind'] = self.namespace['COMPOSITION_REPAIR_PLAN_KIND']
            elif change == 'three': del f.commands['objects']['NativeDocumentV2Types.cpp']
            elif change == 'five': f.commands['objects']['main.cpp'] = ['compiler', 'main.cpp']
            elif change == 'missing-import': f.plan['successful_donor']['objects'].pop()
            else: f.commands['objects']['Unrelated.cpp'] = ['compiler', 'Unrelated.cpp']
            with self.subTest(change=change), self.assertRaises(ValueError): f.apply()

    def test_lost_or_rebound_compilation_provenance_rejects(self):
        for change in ('missing', 'origin', 'binding'):
            f = self.fixture(); name = 'evidence/import-main.cpp.json'; record = f.record(name)
            if change == 'missing': record.pop('donor_provenance')
            elif change == 'origin': record['donor_provenance']['compile_origin'] = 'legacy-imported'
            else: record['donor_provenance']['compile_bindings']['build'] = '/invented/forged'
            f.save(name, record)
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, 'provenance'): f.apply()

    def test_missing_artifact_archive_tool_or_hardlink_never_passes(self):
        for change in ('missing', 'archive-tool', 'hardlink'):
            f = self.fixture()
            if change == 'missing': (f.root / 'objects/BibEngineDocumentWasmShim.cpp.o.d').unlink()
            else:
                name = 'evidence/import-archive-WebCore.json'; record = f.record(name)
                record['archive_program_invoked' if change == 'archive-tool' else 'hardlinked'] = True
                f.save(name, record)
            with self.subTest(change=change), self.assertRaises((ValueError, OSError)): f.apply()


class NativeCapabilityAdmissionFixture(NativeCapabilityP5CompiledFixture):
    """The real new admission, with a fabricated already-qualified legacy reader.

    The existing exact legacy reader is exercised by its unchanged suites. This
    fixture supplies its boundary result and complete independent virtual paths;
    no real source, donor, SDK, compiler or retained file is opened.
    """
    def __init__(self, h, m):
        super().__init__(h, m)
        old = self.docs['p5_plan']; proof = old['reuse']; freeze = self.docs['p5_input_freeze']
        self.api.Inspection = m.Inspection
        self.api.REFERENCE_FIELDS = m.REFERENCE_FIELDS
        self.api._completed_context_matches = m._completed_context_matches
        self.api._completed_normalize_vfs = m._completed_normalize_vfs
        projection = {'path': '/invented/p5-projection.json', 'sha256': 'b' * 64}
        old['selection'].update(projection=projection['path'], projection_sha256=projection['sha256'])
        self.api.documents[(projection['path'], projection['sha256'])] = {}
        proof['inventory'] = {'files': {'config.h': '2' * 64}}
        for name, payload, pin in (('sources.json', {'files': self.old_inspection.inventories['sources']}, '7' * 64),
                                   ('recipe.json', {'inert': 'frozen P5 recipe'}, '6' * 64)):
            fact = self.fact(str(self.bindings['sources'] / name), 390 + len(name), pin)
            freeze['files'][fact['path']] = fact; self.api.raw[fact['path']] = encoded(payload)
        vfs = dict(version=0, **{'case-sensitive': True, 'use-external-names': False,
            'overlay-relative': False, 'fallthrough': True, 'roots': []})
        normalized = m._completed_normalize_vfs(vfs, self.bindings)
        self.api._completed_private_context = mock.Mock(return_value=normalized)
        self.api._header_identity = mock.Mock(return_value={'overlay': vfs})
        self.value['p5_private']['configuration'] = {'sha256': 'c' * 64}
        self.value['p5_private']['launcher'] = {'sha256': 'd' * 64}
        self.docs['p5_maintenance_build']['private_configuration'] = dict(config_sha256='c' * 64, launcher_sha256='d' * 64)
        i, _, _, _, previous, current = NativeCapabilityShapeContextTests.fixture(SimpleNamespace(h=h, m=m))
        self.inspection.proof = i.proof
        for key in ('host_tools', 'sdk_tools', 'python_launch', 'emscripten_config', 'private_cache', 'metadata', 'link'):
            self.inspection.proof[key] = deepcopy(proof[key])
        self.inspection.roots = dict(sources=Path('/invented/new-sources'), sdk=self.bindings['sdk'], reuse=Path('/invented/new-reuse'))
        self.inspection.inventories = deepcopy(self.old_inspection.inventories)
        self.inspection.inventories['reuse']['config.h'] = '2' * 64
        for obj in self.inspection.proof['objects']:
            self.inspection.inventories['sources'][obj['source']['path']] = obj['source']['sha256']
        self.api._completed_header_context = mock.Mock(side_effect=lambda context, refs, objects:
            current if context is self.inspection else previous)
        legacy_bindings = {key: '/invented/legacy-' + key for key in ('sources', 'sdk', 'reuse', 'build')}
        rows, sidecar = [], {'dependencies': {}}
        fresh = {'NativeDocumentV2Publisher.cpp', 'BibEngineDocumentWasmShim.cpp', 'ProviderGuard.cpp', 'BibNativeEditorBackend.cpp', 'main.cpp'}
        for index, name in enumerate(self.selected):
            if name in fresh: continue
            product = self.records['objects/' + name + '.o']
            original = self.fact('/invented/legacy-build/objects/' + name + '.o', 500 + index, product['sha256'])
            original['bytes'] = original['identity'][4] = product['bytes']; self.api.facts[original['path']] = deepcopy(original)
            depfile = self.fact('/invented/legacy-build/objects/' + name + '.o.d', 600 + index)
            key = '/invented/legacy-sources/units/' + name
            source = next(row['source'] for row in proof['objects'] if row['id'] == name)
            sidecar['dependencies'][key] = {'input': source}
            row = dict(id=name, object=original, depfile=depfile, command_script=None,
                command_sha256=digest(name), original_argv=['legacy-compiler', name], original_cwd='/invented/legacy-build/cmake/build',
                ninja_record=['0', '1', '1000', original['path'], 'abc'], ninja_command='retained original command', dependency_keys=[key])
            rows.append(row)
            receipt = dict(kind='foundation-document-v2-object-import-v1', object=original, original_depfile=depfile,
                original_argv=row['original_argv'], original_cwd=row['original_cwd'], original_command_sha256=row['command_sha256'],
                ninja_record=row['ninja_record'], ninja_command=row['ninja_command'], command_script=None, compiler_invoked=False,
                hardlinked=False, origin='imported', id=name, production_eligible=False, destination=product['path'],
                sha256=product['sha256'], bytes=product['bytes'], depfile_sha256=depfile['sha256'],
                retained_depfile=self.records['evidence/import-' + name + '.original.d']['path'])
            self.api.raw[self.records['evidence/import-' + name + '.json']['path']] = encoded(receipt)
            raw = ('inert true original depfile ' + name).encode()
            self.api.raw[depfile['path']] = raw
            self.api.raw[self.records['evidence/import-' + name + '.original.d']['path']] = raw
        self.sidecar_ref = {'path': '/invented/legacy/dependencies.json', 'sha256': 'e' * 64}
        self.api.documents[(self.sidecar_ref['path'], self.sidecar_ref['sha256'])] = sidecar
        self.legacy = dict(objects=rows, original_bindings=legacy_bindings, dependency_sidecar=self.sidecar_ref,
            metadata_directories=['/invented/legacy'], archives=[])
        self.api.documents[(self.value['legacy_donor']['path'], self.value['legacy_donor']['sha256'])] = {'objects': rows}
        for index, name in enumerate(CONTRACT['archive_order']):
            product = self.records['archives/lib' + name + '.a']; report = self.records['evidence/archive-' + name + '.json']
            original = self.fact('/invented/legacy-build/archives/lib' + name + '.a', 700 + index, product['sha256'])
            original['bytes'] = original['identity'][4] = product['bytes']; self.api.facts[original['path']] = deepcopy(original)
            old_report = self.fact('/invented/legacy-build/evidence/archive-' + name + '.json', 710 + index)
            raw = encoded({'name': name, 'members': [], 'sha256': product['sha256']})
            self.api.raw[old_report['path']] = self.api.raw[report['path']] = raw
            self.value['archives'].append(dict(name=name, archive=product, report=report))
            self.legacy['archives'].append(dict(name=name, archive=original, report=old_report))
        self.api._completed_work = mock.Mock(return_value=self.legacy)
        self.reference = {'path': '/invented/new-donor.json', 'sha256': 'f' * 64}
        self.api.documents[(self.reference['path'], self.reference['sha256'])] = self.value
        # This fixture extends source/build metadata after the initial fake Root
        # was made. Refresh its independent trusted-reader inspection hash only.
        pin = digest(encoded(self.docs['p5_maintenance_build']['inspection']))
        self.docs['p5_closed_result']['inspection_sha256'] = pin

    def admit(self): return self.h.native_capability_admission(self.reference, self.inspection, self.api)


class NativeCapabilityAdmissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.h, cls.m = load_helper(), load_maintenance()

    def fixture(self): return NativeCapabilityAdmissionFixture(self.h, self.m)

    def test_real_new_admission_keeps43_original_histories_and_three_p5_histories(self):
        f = self.fixture(); admitted = f.admit()
        self.assertEqual(46, len(admitted['objects']))
        self.assertEqual(5, len(admitted['archives']))
        self.assertEqual(f.reference, admitted['reference'])
        self.assertEqual((43, 3), tuple(sum(row['donor_provenance']['compile_origin'] == origin for row in admitted['objects']) for origin in ('legacy-imported', 'p5-compiled')))
        f.api._completed_work.assert_called_once()
        self.assertEqual({'_successful': True, '_composition_repair': True}, f.api._completed_work.call_args.kwargs)
        frozen = f.api._completed_work.call_args.args[1]
        self.assertEqual(str(f.bindings['sources']), frozen.selection['sources'])
        self.assertNotEqual(f.inspection.roots['sources'], frozen.roots['sources'])
        for row in admitted['objects']:
            provenance = row['donor_provenance']
            if provenance['compile_origin'] == 'p5-compiled':
                self.assertIsNone(provenance['p5_import_receipt'])
                self.assertEqual(str(f.bindings['build'] / 'cmake/build'), row['original_cwd'])
            else:
                self.assertIsNotNone(provenance['p5_import_receipt'])
                self.assertEqual('/invented/legacy-build/cmake/build', row['original_cwd'])
        self.assertEqual(set(map(str, f.bindings.values())), set(admitted['additional_input_directories']))

    def test_changed_current_import_dependency_rejects_even_if_old_histories_match(self):
        f = self.fixture(); f.inspection.inventories['sources']['units/main.cpp'] = 'f' * 64
        with self.assertRaisesRegex(ValueError, 'inventory'): f.admit()

    def test_p5_import_receipt_cannot_restamp_compilation_or_rebind_original_context(self):
        for key, bad in (('compiler_invoked', True), ('hardlinked', True), ('original_cwd', '/invented/wrong'),
                         ('origin', 'compiled'), ('ninja_command', 'new compiler command'),
                         ('retained_depfile', '/invented/forged.d'), ('depfile_sha256', '0' * 64), ('kind', 'compiled')):
            f = self.fixture(); name = next(r['id'] for r in f.value['objects'] if r['origin'] == 'legacy-imported')
            path = f.records['evidence/import-' + name + '.json']['path']; record = json.loads(f.api.raw[path]); record[key] = bad
            f.api.raw[path] = encoded(record)
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'provenance'): f.admit()

    def test_original_depfile_archive_report_and_private_identity_must_match(self):
        for change in ('depfile', 'archive', 'private'):
            f = self.fixture()
            if change == 'depfile':
                name = next(r['id'] for r in f.value['objects'] if r['origin'] == 'legacy-imported')
                f.api.raw[f.records['evidence/import-' + name + '.original.d']['path']] = b'forged original dependency bytes'
            elif change == 'archive': f.api.raw[f.value['archives'][0]['report']['path']] = b'forged archive report'
            else: f.value['p5_private']['configuration']['sha256'] = 'f' * 64
            with self.subTest(change=change), self.assertRaises(ValueError): f.admit()

if __name__ == "__main__":
    unittest.main()
