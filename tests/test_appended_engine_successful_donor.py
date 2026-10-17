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

def fixture():
    # The literal old nine-name whitelist and two excluded compilation identities
    # come from fixture_contract, independently of the implementation constants.
    direct = CONTRACT["legacy_direct_ids"] + CONTRACT["compiled_ids"] + [
        "Direct%02d.cpp" % i for i in range(24)]
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
    def __init__(self, helper):
        self.helper = helper
        self.api = Reader()
        self.bindings = {key: Path('/invented/' + key) for key in ('sources', 'sdk', 'reuse', 'build')}
        self.inspection, old, _, self.selected = shape_fixture()
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
    wanted = {'_identity7', '_completed_build_receipt', '_successful_build_receipt'}
    nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in wanted]
    if {node.name for node in nodes} != wanted:
        raise AssertionError('actual receipt implementations missing')
    namespace = {'RESUME_BUILD_KIND': 'foundation-document-v2-maintenance-resume-build-v1',
                 'SUCCESSFUL_BUILD_KIND': 'foundation-document-v2-maintenance-successful-donor-build-v1',
                 '_successful_module': load_helper,
                 'checked_document': lambda p: json.loads(Path(p).read_bytes()),
                 'ordinary': lambda p: Path(p),
                 'digest': lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(SOURCE), 'exec'), namespace)
    return namespace

class ReceiptFixture:
    def __init__(self, root, namespace):
        self.root = root
        self.namespace = namespace
        _, _, _, selected = shape_fixture()
        self.selected = selected
        imported = [name for name in selected if name not in CONTRACT['compiled_ids']]
        self.commands = {'objects': {name: ['fake-compiler', name] for name in CONTRACT['compiled_ids']},
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
            rows.append(original)
            record = {'kind': 'foundation-document-v2-object-import-v1', 'production_eligible': False,
                      'id': name, 'origin': 'imported', 'compiler_invoked': False, 'hardlinked': False,
                      'sha256': obj['sha256'], 'bytes': obj['bytes'], 'object': original['object'],
                      'original_depfile': original['depfile'], 'original_command_sha256': original['command_sha256'],
                      'original_argv': original['original_argv'], 'original_cwd': original['original_cwd'],
                      'ninja_record': original['ninja_record'], 'ninja_command': original['ninja_command'],
                      'command_script': None}
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
        self.plan = {'reuse': {'objects': [{'id': name} for name in selected],
                               'archives': [{'name': name} for name in CONTRACT['archive_order']]},
                     'successful_donor': {'reference': {'path': '/invented/donor.json', 'sha256': 'b' * 64},
                                          'objects': rows, 'archives': archives}}

    def save(self, name, value):
        p = self.root / name; p.parent.mkdir(exist_ok=True, parents=True); p.write_bytes(encoded(value))

    def record(self, name): return json.loads((self.root / name).read_bytes())

    def apply(self):
        self.namespace['_successful_build_receipt'](self.result, self.plan, self.root, self.commands)
        return self.result

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
                              ['Direct%02d.cpp' % i for i in range(24)],
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
        def archives(value, inspection, old, bindings, api):
            self.archive_calls.append(value['objects'])
            return []
        selected = SimpleNamespace(DONOR_KIND='foundation-document-v2-successful-donor-v1',
            COMPILED_IDS=('NativeDocumentV2Publisher.cpp','BibEngineDocumentWasmShim.cpp'),
            authority=lambda value, bindings, old, api: self.m._completed_authority(value, bindings, old),
            archive_rows=archives)
        self.stack.enter_context(mock.patch.object(self.m, '_successful_module', return_value=selected))
        self.stack.enter_context(mock.patch.object(self.m, '_header_identity', side_effect=lambda inspection: self.f.view))

    def admit(self):
        reference = support.save(self.f.root / 'records/successful.json', self.f.value)
        return self.m._completed_work(reference, self.f.inspection, _successful=True)

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
        expected = [row['id'] for row in self.f.proof['objects'] if row['id'] not in CONTRACT['compiled_ids']]
        self.assertEqual(49, len(admitted['objects']))
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


if __name__ == "__main__":
    unittest.main()
