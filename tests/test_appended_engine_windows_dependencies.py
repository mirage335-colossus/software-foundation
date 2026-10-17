"""Inert controller fixtures; no retained bodies, native programs or subprocesses."""
import ast
import contextlib
import copy
import gzip
import hashlib
import io
import json
from pathlib import Path
import struct
import sys
import tempfile
import tarfile
import types
import unittest
from unittest import mock
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import appended_engine_windows_dependencies as dependency_entry
controller = dependency_entry._legacy()
import appended_engine_windows_dependency_proof as proof
from test_appended_engine_windows_dependency_proof import identity, receipts as proof_receipts, command, reference


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def receipts():
    value, expected = proof_receipts()
    for bindings in (value['bindings'], expected['bindings']):
        bindings['producer']['helpers'] += [reference('C:/source/' + name)
                                            for name in controller.ARCHIVE_HELPER_SOURCES]
    return value, expected


def limits():
    return {key: (4 if key == 'maximum_jobs' else
                  4096 if key in ('maximum_output_bytes', 'maximum_log_bytes') else 8)
            for key in controller.LIMIT_BOUNDS}


def selection():
    profile, _review, _refs = controller._recipe_metadata()
    h = identity()
    return {'schema_version': 1, 'kind': controller.SELECTION_KIND,
        'target': copy.deepcopy(proof.TARGET),
        'toolchain_identity': reference('C:/records/toolchain-identity.json'),
        'inventories': {role: reference('C:/records/' + role + '-inventory.json')
                        for role in proof.INVENTORIES},
        'sources': {supplier: {
            'archive': {'path': 'C:/archives/' + profile['components'][supplier]['archive'],
                        'sha256': profile['components'][supplier]['sha256']},
            'replay': reference('C:/records/' + supplier + '-replay.json')}
            for supplier in proof.SOURCES},
        'output': 'C:/output', 'limits': limits(),
        'publication': {'qualification': reference('C:/records/publication-qualification.json'),
            'source_identity': {name: digest(name.encode()) for name in controller.PUBLICATION_SOURCES},
            'runtime_identity': {'python_path': h['programs']['python']['path'],
                'python_sha256': h['programs']['python']['sha256'],
                'python_version': h['programs']['python']['version'], 'system': 'Windows',
                'machine': 'x86_64', 'pointer_bits': 64, 'windows_version': [10, 0, 22621],
                'system_root': 'C:/Windows'}}}


def native_inputs(h, receipt):
    return {'schema_version': 1, 'kind': 'foundation-native-engine-windows-inputs',
        'target': 'windows-x86_64', 'build_type': 'Release', 'crt': 'static-mt',
        'cpu_baseline': 'x86_64-sse2', 'os_floor_declaration': 'windows-10-1809-unqualified',
        'engine_cxx_standard': 23, 'dependency_prefix': receipt['prefix']['root'],
        'toolchain': {'compiler': {k: h['programs']['compiler'][k] for k in ('path', 'sha256')},
            'linker': {k: h['programs']['linker'][k] for k in ('path', 'sha256')},
            'builtins': copy.deepcopy(h['builtins']), 'compiler_version': '19.1.7',
            **{role: {'root': h['inventories'][role]['root'],
                       'inventory': reference('C:/records/' + role + '-inventory.json')}
               for role in ('msvc_stl', 'windows_sdk')}},
        'dependency_inventory': reference('C:/records/dependency-inventory.json'), 'woff2': 'OFF',
        'libraries': {target: {key: item[key] for key in ('path', 'sha256', 'includes', 'definitions', 'links')}
                      for target, item in receipt['libraries'].items()}}


def source_bundle():
    h = identity()
    d, expected = receipts()
    # The frozen proof fixtures deliberately use independent declaration values.
    # This controller fixture joins D's selected CMake to H without changing that
    # separate proof suite or claiming an observed native version.
    h['programs']['cmake'] = copy.deepcopy(d['commands'][0]['program'])
    hpin = digest(proof.encoded(h))
    d['bindings']['toolchain_identity_sha256'] = hpin
    d['postflight']['toolchain_identity_sha256'] = hpin
    expected['bindings']['toolchain_identity_sha256'] = hpin
    d['bindings']['controller']['runtime_subject_sha256'] = h['inventories']['host_generators']['subject_sha256']
    expected['bindings']['controller'] = copy.deepcopy(d['bindings']['controller'])
    profile = controller._recipe_metadata()[0]
    for supplier, source in d['bindings']['sources'].items():
        component = profile['components'][supplier]
        source['version'] = component['version']
        source['archive'] = {'path': 'C:/archives/' + component['archive'], **{
            key: component[key] for key in ('sha256', 'bytes', 'format', 'strip_prefix')}}
    expected['bindings']['sources'] = copy.deepcopy(d['bindings']['sources'])
    return h, d, expected, native_inputs(h, d)


class MetadataTests(unittest.TestCase):
    def test_exact_pending_recipe_and_all_fourteen_named_gaps(self):
        profile, review, refs = controller._recipe_metadata()
        self.assertEqual(set(profile['components']), set(proof.SOURCES))
        self.assertEqual(len(profile['libraries']), 20)
        self.assertEqual(refs['recipe']['sha256'], controller.PROFILE_PIN)
        self.assertEqual(len(controller._review_gaps(review)), 14)
        with self.assertRaises(controller.MissingInputs) as caught:
            controller._require_reviewed_recipe()
        self.assertEqual(len(caught.exception.missing), 16)
        roles = {item['role'] for item in caught.exception.missing}
        self.assertIn(controller.JOB_PROCESS_LIMIT_GAP, roles)
        self.assertIn(controller.PROBE_OBJECT_BINDING_GAP, roles)
        self.assertTrue(all(caught.exception.as_dict()[name] is False for name in controller.FALSE_FACTS))

    def test_recipe_status_flip_does_not_admit_review(self):
        original = controller._local_metadata
        def changed(path, pin):
            raw, ref = original(path, pin)
            value = json.loads(raw)
            if path == controller.SOURCE_REVIEW:
                value['sources']['icu']['status'] = 'passed'
            return proof.encoded(value), ref
        with mock.patch.object(controller, '_local_metadata', side_effect=changed), self.assertRaises(ValueError):
            controller._recipe_metadata()

    def test_recipe_supplier_pin_change_rejected(self):
        original = controller._local_metadata
        def changed(path, pin):
            raw, ref = original(path, pin)
            value = json.loads(raw)
            if path == controller.PROFILE:
                value['components']['icu']['version'] = '77.2'
            return proof.encoded(value), ref
        with mock.patch.object(controller, '_local_metadata', side_effect=changed), self.assertRaises(ValueError):
            controller._recipe_metadata()

    def test_selection_owned_and_closed(self):
        value = selection()
        checked = controller.validate_selection(value)
        checked['limits']['maximum_jobs'] = 1
        self.assertEqual(value['limits']['maximum_jobs'], 4)
        value['handoff'] = reference('C:/not-allowed/engine.json')
        with self.assertRaises(ValueError): controller.validate_selection(value)

    def test_selection_rejects_scalar_types_aliases_and_output_overlap(self):
        for mutation in (
                lambda value: value.update(schema_version=True),
                lambda value: value['target'].update(pointer_bits=True),
                lambda value: value['limits'].update(maximum_jobs=5),
                lambda value: value['sources']['curl'].update(archive=value['sources']['icu']['archive']),
                lambda value: value.update(output='C:/archives'),
                lambda value: value['inventories']['llvm'].update(path='c:/records/llvm.json'),
                lambda value: value['publication']['runtime_identity'].update(pointer_bits=True)):
            value = selection(); mutation(value)
            with self.subTest(value=value), self.assertRaises(ValueError):
                controller.validate_selection(value)

    def test_plan_reads_only_source_metadata_not_references(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'selection.json'
            raw = proof.encoded(selection()); path.write_bytes(raw)
            original = controller._host_read
            read_paths = []
            def read(selected, pin, maximum=controller.MAX_METADATA):
                read_paths.append(str(selected))
                self.assertFalse(str(selected).startswith('C:/'))
                return original(selected, pin, maximum)
            with mock.patch.object(controller, '_host_read', side_effect=read):
                with self.assertRaises(controller.MissingInputs) as caught:
                    controller.plan({'path': str(path), 'sha256': digest(raw)})
            self.assertEqual(len(caught.exception.missing), 16)
            self.assertEqual(len(read_paths), 4)
            self.assertEqual(list(Path(directory).iterdir()), [path])

    def test_inspection_rejects_wrong_original_supplier_sha(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'selection.json'
            value = selection(); value['sources']['icu']['archive']['sha256'] = '1' * 64
            raw = proof.encoded(value); path.write_bytes(raw)
            with self.assertRaisesRegex(ValueError, 'supplier archive pin'):
                controller.inspect_selection({'path': str(path), 'sha256': digest(raw)})

    def test_metadata_original_canonical_bytes_and_nonzero_pin(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'selection.json'; raw = b'{"kind":"wrong"}'
            path.write_bytes(raw)
            with self.assertRaisesRegex(ValueError, 'canonical'):
                controller.inspect_selection({'path': str(path), 'sha256': digest(raw)})
            with self.assertRaises(ValueError): controller._host_read(path, '0' * 64)

    def test_build_native_guard_precedes_any_read(self):
        with mock.patch.object(controller.os, 'name', 'posix'), mock.patch.object(controller, '_recipe_metadata') as read:
            with self.assertRaisesRegex(ValueError, 'Native Windows x64'):
                controller.build({'path': '/never-read', 'sha256': '1' * 64})
            read.assert_not_called()

    def test_native_build_and_native_admission_stop_before_plan_or_body_io(self):
        with mock.patch.object(controller, 'require_native_host'), mock.patch.object(controller, '_open_workspace') as create:
            for operation in (lambda: controller.build({'path': '/never-read', 'sha256': '1' * 64}),
                    lambda: controller.admit_dependency_producer(None, None, None, None)):
                with self.assertRaises(controller.MissingInputs): operation()
            create.assert_not_called()

    def test_source_declarations_closed_h_d_join_then_missing_review(self):
        h, d, _expected, native = source_bundle()
        hraw, draw = proof.encoded(h), proof.encoded(d)
        with self.assertRaises(controller.MissingInputs):
            controller.validate_source_declarations(hraw, digest(hraw), draw, digest(draw), native)
        d['extra'] = 'original_reports cannot create producer proof'
        draw = proof.encoded(d)
        with self.assertRaisesRegex(ValueError, 'fields'):
            controller.validate_source_declarations(hraw, digest(hraw), draw, digest(draw), native)

    def test_source_declarations_reject_original_pin_h_and_library_mismatch(self):
        h, d, _expected, native = source_bundle()
        hraw = proof.encoded(h)
        for mutate in (lambda value: value['bindings'].update(toolchain_identity_sha256='1' * 64),
                       lambda value: value['libraries']['PNG::PNG'].update(sha256='1' * 64)):
            value = copy.deepcopy(d); mutate(value); draw = proof.encoded(value)
            with self.assertRaises(ValueError):
                controller.validate_source_declarations(hraw, digest(hraw), draw, digest(draw), native)
        with self.assertRaisesRegex(ValueError, 'SHA256'):
            controller.validate_source_declarations(hraw, digest(hraw), proof.encoded(d), '1' * 64, native)

    def test_source_commands_join_exact_h_role_system_root_and_finite_path(self):
        h, original, _expected, native = source_bundle()
        hraw = proof.encoded(h)
        mutations = (
            lambda item: item['program'].update(path='C:/retained/host_generators/other/cmake.exe'),
            lambda item: item['program'].update(sha256='1' * 64),
            lambda item: item['program'].update(version='3.31.7'),
            lambda item: item['environment'].update(SystemRoot='C:/OtherWindows'),
            lambda item: item['environment'].update(PATH='C:/retained/host_generators/other'),
            lambda item: item['environment'].update(PATH='C:/retained/host_generators/bin;C:/retained/host_generators/bin'))
        for mutation in mutations:
            value = copy.deepcopy(original)
            for item in value['commands']:
                mutation(item)
                item['argv'][0] = item['program']['path']
                item['job']['image'] = {key: item['program'][key] for key in ('path', 'sha256')}
                declaration = {key: item[key] for key in proof.COMMAND_FIELDS}
                item['job']['launch_intent_sha256'] = digest(proof.encoded(declaration))
            raw = proof.encoded(value)
            with self.assertRaisesRegex(ValueError, 'H role|SystemRoot|H program parent'):
                controller.validate_source_declarations(hraw, digest(hraw), raw, digest(raw), native)

    def test_cli_missing_inputs_structured_stdout_and_no_save(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'selection.json'; raw = proof.encoded(selection()); path.write_bytes(raw)
            out, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                result = controller.cli(['plan', '--selection', str(path), '--selection-sha256', digest(raw)])
            self.assertEqual(result, 2); self.assertEqual(err.getvalue(), '')
            self.assertEqual(len(json.loads(out.getvalue())['missing']), 16)
            self.assertEqual(len(list(Path(directory).iterdir())), 1)

    def test_cli_bad_pin_and_non_native_build_are_errors(self):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(controller.cli(['plan', '--selection', '/absent', '--selection-sha256', 'bad']), 1)
            with mock.patch.object(controller.os, 'name', 'posix'):
                self.assertEqual(controller.cli(['build', '--plan', '/never-read', '--plan-sha256', '1' * 64]), 1)


class ProjectionTests(unittest.TestCase):
    def fixture(self):
        component = controller._recipe_metadata()[0]['components']['webp']
        return {'schema_version': 1, 'kind': 'foundation-native-engine-windows-dependency-source-replay-v1',
            'target': copy.deepcopy(proof.TARGET), 'supplier': 'webp', 'identity': component,
            'source_root': 'C:/source/webp', 'directories': ['include'],
            'files': {'LICENSE': {'sha256': digest(b'notice'), 'bytes': 6},
                      'include/webp.h': {'sha256': digest(b'header'), 'bytes': 6}},
            'notices': ['LICENSE'], 'transformations': []}

    def test_thirteen_source_projection_metadata_not_engine_replay(self):
        value = self.fixture()
        facts = controller._source_projection(value, 'webp', value['identity'])
        self.assertEqual(set(facts), {'source_subject_sha256', 'notice_subject_sha256'})
        self.assertNotEqual(facts['source_subject_sha256'], facts['notice_subject_sha256'])

    def test_inventory_subject_domain_does_not_inherit_h_d_byte_cap(self):
        value = self.fixture()
        for index in range(40):
            value['files']['member' + str(index) + '.h'] = {'sha256': digest(b'inert'), 'bytes': 5}
        subject = {'root': value['source_root'], 'files': value['files'],
                   'directories': value['directories']}
        expected = digest(controller.contract.encoded(subject))
        with mock.patch.object(proof, 'MAX_DOCUMENT', 1024):
            facts = controller._source_projection(value, 'webp', value['identity'])
            self.assertEqual(facts['source_subject_sha256'], expected)
            self.assertEqual(controller._subject(subject), expected)
            controller._inventory_equal(subject, copy.deepcopy(subject), 'complete source fixture')
            with self.assertRaises(ValueError): proof.encoded(subject)

    def test_source_projection_rejects_alias_missing_notice_parent_and_patch(self):
        for mutation in (lambda value: value.update(notices=[]),
                lambda value: value.update(directories=[]),
                lambda value: value.update(transformations=[{'status': 'passed'}]),
                lambda value: value['files'].update({'license': {'sha256': '1' * 64, 'bytes': 1}}),
                lambda value: value['files']['LICENSE'].update(bytes=True)):
            value = self.fixture(); mutation(value)
            with self.assertRaises(ValueError):
                controller._source_projection(value, 'webp', value['identity'])

    def archive(self, members):
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode='w:gz') as archive:
            for name, kind in members:
                info = tarfile.TarInfo(name)
                if kind == 'link':
                    info.type = tarfile.SYMTYPE; info.linkname = 'outside'
                    archive.addfile(info)
                elif kind == 'directory':
                    info.type = tarfile.DIRTYPE; archive.addfile(info)
                else:
                    body = b'inert source fixture'; info.size = len(body)
                    archive.addfile(info, io.BytesIO(body))
        raw = stream.getvalue()
        return raw, {'bytes': len(raw), 'sha256': digest(raw),
                     'strip_prefix': 'supplier', 'format': 'tar-gzip'}

    def test_archive_projection_compares_original_member_metadata_without_extraction(self):
        raw, component = self.archive([('supplier/include/a.h', 'file'),
                                       ('supplier/include', 'directory'), ('supplier/LICENSE', 'file')])
        result = controller._archive_projection(raw, component)
        self.assertEqual(set(result['files']), {'include/a.h', 'LICENSE'})
        self.assertEqual(result['directories'], ['include'])
        self.assertEqual(result['files']['LICENSE']['sha256'], digest(b'inert source fixture'))

    def test_archive_projection_rejects_links_case_aliases_escapes_and_wrong_bytes(self):
        for members in ([('supplier/link', 'link')],
                        [('supplier/A.h', 'file'), ('supplier/a.h', 'file')],
                        [('supplier/../escape', 'file')], [('foreign/a.h', 'file')]):
            raw, component = self.archive(members)
            with self.assertRaises(ValueError): controller._archive_projection(raw, component)
        raw, component = self.archive([('supplier/a.h', 'file')])
        component['sha256'] = '1' * 64
        with self.assertRaises(ValueError): controller._archive_projection(raw, component)

    def zip_archive(self, names):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, mode='w', compression=zipfile.ZIP_DEFLATED) as archive:
            for name in names:
                archive.writestr(name, b'inert source fixture')
        raw = stream.getvalue()
        return raw, {'bytes': len(raw), 'sha256': digest(raw),
                     'strip_prefix': 'supplier', 'format': 'zip'}

    def test_zip_raw_count_is_bounded_before_zipfile_allocates_index(self):
        import appended_engine_windows_source_replay as replay
        raw, component = self.zip_archive(['supplier/a.h', 'supplier/b.h', 'supplier/c.h'])
        raw = bytearray(raw)
        eocd = raw.rfind(b'PK\x05\x06')
        struct.pack_into('<HH', raw, eocd + 8, 1, 1)
        raw = bytes(raw); component.update(bytes=len(raw), sha256=digest(raw))
        with mock.patch.object(replay.zipfile, 'ZipFile', side_effect=AssertionError('index allocated')) as decoder:
            with self.assertRaises(ValueError): controller._archive_projection(raw, component)
        decoder.assert_not_called()

    def test_tar_raw_extended_header_bound_precedes_pax_parser(self):
        info = tarfile.TarInfo('supplier/PaxHeader')
        info.type = tarfile.XHDTYPE
        info.size = 1025
        raw = gzip.compress(info.tobuf())
        component = {'bytes': len(raw), 'sha256': digest(raw),
                     'strip_prefix': 'supplier', 'format': 'tar-gzip'}
        with mock.patch.object(controller, 'MAX_SOURCE_MEMBER_BYTES', 1024), \
                mock.patch.object(tarfile.TarInfo, '_proc_pax', side_effect=AssertionError('PAX allocated')) as parser:
            with self.assertRaises(ValueError): controller._archive_projection(raw, component)
        parser.assert_not_called()

    def test_zip_unknown_decoder_rejected_before_decompressor_creation(self):
        import appended_engine_windows_source_replay as replay
        raw, component = self.zip_archive(['supplier/a.h'])
        raw = bytearray(raw)
        local, central = raw.find(b'PK\x03\x04'), raw.find(b'PK\x01\x02')
        struct.pack_into('<H', raw, local + 8, zipfile.ZIP_LZMA)
        struct.pack_into('<H', raw, central + 10, zipfile.ZIP_LZMA)
        raw = bytes(raw); component.update(bytes=len(raw), sha256=digest(raw))
        with mock.patch.object(replay.zipfile, '_get_decompressor', side_effect=AssertionError('decoder allocated')) as decoder:
            with self.assertRaises(ValueError): controller._archive_projection(raw, component)
        decoder.assert_not_called()

    def test_zip_projection_uses_one_validated_decoder_instance(self):
        import appended_engine_windows_source_replay as replay
        raw, component = self.zip_archive(['supplier/a.h', 'supplier/LICENSE'])
        constructor = replay.zipfile.ZipFile
        with mock.patch.object(replay.zipfile, 'ZipFile', wraps=constructor) as decoder:
            result = controller._archive_projection(raw, component)
        self.assertEqual(decoder.call_count, 1)
        self.assertEqual(set(result['files']), {'a.h', 'LICENSE'})


class FakeOwner:
    def __init__(self, events, code=0, count=1, fail_join=False, fail_cleanup=False):
        self.events, self.code = events, code
        self.closed = False
        self.job = types.SimpleNamespace(active=lambda: count)
        self.fail_join, self.fail_cleanup = fail_join, fail_cleanup
    def poll(self): return self.code
    def finish(self):
        self.events.append('finish')
        if self.fail_join: raise RuntimeError('surviving writer')
        return self.code
    def close(self): self.events.append('owner-close'); self.closed = True
    def terminate(self, timeout):
        self.events.append('terminate')
        if self.fail_cleanup: raise RuntimeError('uncertain cleanup')


class FakeWorkspace:
    def __init__(self, events=None, output_bytes=0):
        self.events = [] if events is None else events
        self.output, self.output_bytes = 'C:/output', output_bytes
        self.files, self.failed, self.uncertain = {}, False, False
        self.directories = []
        self.launch_owner, self.launch_failure = None, None
    def mkdir_new(self, name): self.events.append('mkdir:' + name); self.directories.append(name)
    def open_log_new(self, name):
        self.events.append('log-open')
        return types.SimpleNamespace(stream=io.BytesIO(), path=name, owner=None)
    def mark_running(self, log): self.events.append('running')
    def check_anchors(self): self.events.append('anchors')
    def usage(self, log=None):
        return {'bytes': self.output_bytes, 'entries': 1,
                **({'log_bytes': len(log.stream.getvalue())} if log is not None else {})}
    def bind_owner(self, log, owner): log.owner = owner; self.events.append('bind')
    def launch(self, log, argv, cwd, *, env):
        self.events.append('launch')
        if self.launch_failure is not None:
            raise self.launch_failure
        owner = self.launch_owner or FakeOwner(self.events)
        self.bind_owner(log, owner)
        return owner
    def mark_joined(self, log, stage):
        self.events.append('join')
        code = log.owner.finish(); log.owner.close()
        return types.SimpleNamespace(as_dict=lambda: {**stage, 'returncode': code,
            'process_tree_closed': True, 'closure': 'actual-bound-job-finish-and-close'})
    def mark_failed_joined(self, joined, reason): self.events.append('failed-joined'); self.failed = True
    def seal_log(self, log):
        self.events.append('seal'); raw = log.stream.getvalue(); log.stream.close()
        return {'path': log.path, 'sha256': digest(raw), 'bytes': len(raw)}
    def inspect_outputs(self):
        self.events.append('inspect')
        return {'files': copy.deepcopy(self.files), 'directories': sorted(self.directories), 'bytes': sum(row['bytes'] for row in self.files.values())}
    def retain_uncertain(self, owner, log, reason): self.events.append('uncertain'); self.uncertain = True
    def publish_bytes_new(self, path, raw):
        self.events.append('publish:' + path)
        row = {'path': path, 'sha256': digest(raw), 'bytes': len(raw)}
        self.files[path] = {**row, 'kind': 'file'}
        return row
    def commit_receipt_new(self, path, raw): self.events.append('commit'); return self.publish_bytes_new(path, raw)
    def close_joined(self): self.events.append('workspace-close')


class OwnedStageTests(unittest.TestCase):
    def run_stage(self, workspace, owner=None, **kwargs):
        workspace.launch_owner = owner or FakeOwner(workspace.events)
        return controller._run_stage(workspace, command('webp', 'install'), limits(), **kwargs)

    def test_launch_intent_bind_join_close_seal_exact_order(self):
        workspace = FakeWorkspace()
        _joined, observed = self.run_stage(workspace)
        events = [event for event in workspace.events if event != 'anchors']
        self.assertEqual(events, ['log-open', 'running', 'launch', 'bind', 'join', 'finish', 'owner-close', 'seal', 'inspect'])
        self.assertEqual(observed['job']['exit_code'], 0)
        self.assertTrue(observed['logs']['combined']['path'].startswith('C:/output/logs/'))
        proof._job(observed['job'], {key: observed[key] for key in proof.COMMAND_FIELDS})

    def test_nonzero_exit_is_known_joined_failure(self):
        workspace = FakeWorkspace()
        with self.assertRaises(ValueError): self.run_stage(workspace, FakeOwner(workspace.events, code=7))
        self.assertTrue(workspace.failed); self.assertFalse(workspace.uncertain)
        self.assertEqual(workspace.events.count('finish'), 1)
        self.assertEqual(workspace.events.count('seal'), 1)

    def test_resource_limit_cleans_and_joins_without_success(self):
        workspace = FakeWorkspace()
        owner = FakeOwner(workspace.events, count=50)
        with self.assertRaisesRegex(ValueError, 'process-count'):
            self.run_stage(workspace, owner)
        self.assertIn('terminate', workspace.events)
        self.assertTrue(workspace.failed); self.assertFalse(workspace.uncertain)

    def test_launch_failure_without_owner_retains_intent(self):
        workspace = FakeWorkspace()
        workspace.launch_failure = RuntimeError('uncertain launch')
        with self.assertRaisesRegex(RuntimeError, 'uncertain launch'):
            controller._run_stage(workspace, command('webp', 'build'), limits())
        self.assertTrue(workspace.uncertain)
        self.assertNotIn('seal', workspace.events)

    def test_join_failure_never_retries_finish_or_seals(self):
        workspace = FakeWorkspace()
        with self.assertRaises(RuntimeError): self.run_stage(workspace, FakeOwner(workspace.events, fail_join=True))
        self.assertEqual(workspace.events.count('finish'), 1)
        self.assertNotIn('terminate', workspace.events)
        self.assertNotIn('seal', workspace.events)
        self.assertTrue(workspace.uncertain)

    def test_wall_deadline_includes_join_and_uses_known_failure(self):
        workspace = FakeWorkspace()
        times = iter([0, 0, 0, 9])
        with self.assertRaisesRegex(ValueError, 'deadline'):
            self.run_stage(workspace, monotonic=lambda: next(times))
        self.assertTrue(workspace.failed)

    def test_final_joined_output_growth_updates_peak_and_rechecks_limit(self):
        for size in (2048, limits()['maximum_output_bytes'] + 1):
            workspace = FakeWorkspace(output_bytes=0)
            workspace.files['late.bin'] = {'path': 'late.bin', 'kind': 'file',
                'sha256': digest(b'inert final growth'), 'bytes': size}
            if size <= limits()['maximum_output_bytes']:
                _joined, observation = self.run_stage(workspace)
                self.assertEqual(observation['job']['peak_output_bytes'], size)
            else:
                with self.assertRaisesRegex(ValueError, 'after join'):
                    self.run_stage(workspace)
                self.assertTrue(workspace.failed)
                self.assertFalse(workspace.uncertain)
            self.assertEqual(workspace.events.count('finish'), 1)
            self.assertEqual(workspace.events.count('seal'), 1)

    def test_finite_graph_rejects_missing_supplier_before_launch(self):
        workspace = FakeWorkspace(); workspace.launch = mock.Mock()
        with self.assertRaises(ValueError):
            controller._execute_commands(workspace, [command('webp', 'build')], limits())
        workspace.launch.assert_not_called(); self.assertEqual(workspace.events, [])


class ClosureAndPublicationTests(unittest.TestCase):
    def probe_fixture(self):
        _d, expected = receipts(); h = identity()
        declaration = command('__closure__', 'probe')
        declaration['program'] = copy.deepcopy(h['programs']['linker'])
        inputs = controller._probe_link_inputs(expected['libraries'], h, [])
        raw = b'inert executable fixture'; object_raw = b'inert original object fixture'
        output = {'path': 'C:/output/probe.exe', 'sha256': digest(raw)}
        objects = [{'path': 'C:/work/probe/main.obj', 'sha256': digest(object_raw)}]
        declaration['argv'] = [declaration['program']['path'], '/NODEFAULTLIB', '/MACHINE:X64',
            '/OPT:NOREF', '/OPT:NOICF', '/OUT:' + output['path'],
            *['/WHOLEARCHIVE:' + item['path'] for item in inputs[:20]],
            *[item['path'] for item in inputs[20:] + objects]]
        def read(path, pin):
            return object_raw if path == objects[0]['path'] else raw
        inspect = mock.Mock(return_value={'format': 'pe32plus', 'machine': 'x86_64',
                                         'dll': False, 'needed': ['kernel32.dll']})
        return declaration, expected['libraries'], h, output, read, inspect, objects, inputs

    def test_prefix_inspects_twenty_exact_bytes_and_provenance_excluded_subject(self):
        d, expected = receipts(); libraries = copy.deepcopy(expected['libraries'])
        raw = b'inert static archive fixture'
        for item in libraries.values(): item['sha256'] = digest(raw)
        metadata = {'schema_version': 1, 'kind': 'foundation-windows-retained-inventory-v1',
            'role': 'native_dependencies', 'target': copy.deepcopy(proof.TARGET),
            'version': 'fixture-v1', 'root': 'C:/output/prefix', 'files': {
            item['path'].split('/prefix/')[1]: {'sha256': digest(raw), 'bytes': len(raw)}
            for item in libraries.values()}, 'directories': ['lib'], 'provenance': reference('C:/later/provenance.json')}
        read = mock.Mock(return_value=raw)
        inspect = mock.Mock(return_value={'format': 'coff-archive', 'machine': 'x86_64', 'members': ['one']})
        subject, facts = controller._inspect_prefix(metadata, libraries, read, inspect)
        self.assertEqual(len(facts), 20); self.assertEqual(inspect.call_count, 20)
        metadata['provenance']['sha256'] = '1' * 64
        self.assertEqual(subject, controller._subject(metadata))
        libraries['PNG::PNG']['sha256'] = '1' * 64
        with self.assertRaises(ValueError): controller._inspect_prefix(metadata, libraries, read, inspect)

    def test_probe_closure_includes_exact_twenty_crt_builtins_and_selected_sdk(self):
        _d, expected = receipts(); h = identity()
        system = reference('C:/retained/windows_sdk/lib/ws2_32.lib')
        links = controller._probe_link_inputs(expected['libraries'], h, [system])
        self.assertEqual(len(links), 27)
        self.assertEqual(links[-1], system)
        with self.assertRaises(ValueError):
            controller._probe_link_inputs(expected['libraries'], h, [reference('C:/foreign/ws2_32.lib')])

    def test_probe_byte_inspection_never_runs_output_and_rejects_runtime_import(self):
        declaration, libraries, h, output, read, inspect, objects, inputs = self.probe_fixture()
        result = controller._verify_probe(declaration, libraries, h, [], output, read, inspect,
                                          reviewed_objects=objects)
        self.assertEqual(result['link_inputs'], inputs)
        inspect.return_value['needed'] = ['vcruntime140.dll']
        with self.assertRaisesRegex(ValueError, 'runtime'):
            controller._verify_probe(declaration, libraries, h, [], output, read, inspect,
                                     reviewed_objects=objects)

    def test_probe_requires_all_twenty_retained_archives_and_finite_linker_flags(self):
        declaration, libraries, h, output, read, inspect, objects, inputs = self.probe_fixture()
        mutations = (
            lambda item: item.update(argv=[argument.removeprefix('/WHOLEARCHIVE:') for argument in item['argv']]),
            lambda item: item['argv'].__setitem__(6, inputs[0]['path']),
            lambda item: item['argv'].append('/WHOLEARCHIVE:' + inputs[0]['path']),
            lambda item: item['argv'].append(inputs[0]['path']),
            lambda item: item['argv'].append('/WHOLEARCHIVE:C:/foreign/extra.lib'),
            lambda item: item['argv'].append('C:/foreign/extra.obj'),
            lambda item: item['argv'].append('/DEFAULTLIB:unreviewed.lib'),
            lambda item: item['argv'].append('/LIBPATH:C:/foreign'),
            lambda item: item['argv'].remove('/NODEFAULTLIB'),
            lambda item: item['argv'].remove('/OPT:NOREF'),
            lambda item: item['argv'].remove('/OPT:NOICF'),
            lambda item: item['argv'].remove('/MACHINE:X64'),
            lambda item: item['argv'].append('/link'))
        for mutation in mutations:
            value = copy.deepcopy(declaration); mutation(value)
            with self.assertRaises(ValueError):
                controller._verify_probe(value, libraries, h, [], output, read, inspect,
                                         reviewed_objects=objects)
        inspect.assert_not_called()
        driver = copy.deepcopy(declaration)
        driver['program'] = copy.deepcopy(h['programs']['compiler'])
        driver['argv'][0] = driver['program']['path']
        with self.assertRaises(ValueError):
            controller._verify_probe(driver, libraries, h, [], output, read, inspect,
                                     reviewed_objects=objects)

    def test_probe_object_refs_are_nonempty_unique_exact_pins(self):
        declaration, libraries, h, output, read, inspect, objects, _inputs = self.probe_fixture()
        for selected in ((), objects * 2,
                         [{'path': objects[0]['path'], 'sha256': '1' * 64}],
                         [{'path': 'C:/work/probe/main.lib', 'sha256': objects[0]['sha256']}]):
            with self.assertRaises(ValueError):
                controller._verify_probe(declaration, libraries, h, [], output, read, inspect,
                                         reviewed_objects=selected)
        inspect.assert_not_called()

    def test_assembly_checks_observations_against_separate_declarations(self):
        d, expected = receipts()
        inspections = {target: item['inspection'] for target, item in d['libraries'].items()}
        candidate = controller._assemble_receipt(expected['bindings'], expected['commands'], d['commands'],
            expected['prefix'], expected['libraries'], inspections, expected['probe'])
        self.assertEqual(proof.parse_document(candidate.raw), d)
        changed = copy.deepcopy(d['commands']); changed[0]['argv'].append('unreviewed-argument')
        with self.assertRaises(ValueError):
            controller._assemble_receipt(expected['bindings'], expected['commands'], changed,
                expected['prefix'], expected['libraries'], inspections, expected['probe'])
        missing = copy.deepcopy(expected['bindings'])
        missing['producer']['helpers'] = missing['producer']['helpers'][:-1]
        with self.assertRaisesRegex(ValueError, 'helper source closure'):
            controller._assemble_receipt(missing, expected['commands'], d['commands'],
                expected['prefix'], expected['libraries'], inspections, expected['probe'])

    def test_publication_acyclic_order_and_native_manifest_last(self):
        h, d, expected, native = source_bundle()
        inventory = {'schema_version': 1, 'kind': 'foundation-windows-retained-inventory-v1',
            'role': 'native_dependencies', 'target': copy.deepcopy(proof.TARGET),
            'root': d['prefix']['root'], 'version': 'fixture-v1', 'files': {
                item['path'].split('/prefix/')[1]: {'sha256': item['sha256'], 'bytes': 1}
                for item in d['libraries'].values()},
            'directories': ['include', 'lib'], 'provenance': reference('C:/future/provenance.json')}
        notice = reference('C:/output/prefix/NOTICE')
        inventory['files']['NOTICE'] = {'sha256': notice['sha256'], 'bytes': 1}
        subject = controller._subject(inventory)
        d['prefix']['inventory_subject_sha256'] = subject
        expected['prefix']['inventory_subject_sha256'] = subject
        for prefix in (d['prefix'], expected['prefix']):
            prefix['notice_subject_sha256'] = digest(proof.encoded({'NOTICE': inventory['files']['NOTICE']}))
            prefix['header_data_subject_sha256'] = digest(proof.encoded({
                'root': inventory['root'], 'files': {}, 'directories': inventory['directories']}))
        candidate = controller._assemble_receipt(expected['bindings'], expected['commands'], d['commands'],
            expected['prefix'], expected['libraries'], {target: item['inspection'] for target, item in d['libraries'].items()}, expected['probe'])
        workspace = FakeWorkspace()
        workspace.directories = ['prefix', 'prefix/include', 'prefix/lib']
        workspace.files = {'prefix/' + name: {'path': 'prefix/' + name, 'kind': 'file', **row}
                           for name, row in inventory['files'].items()}
        result = controller._publish_candidate(workspace, candidate, inventory, native, [notice])
        writes = [event for event in workspace.events if event.startswith('publish:')]
        self.assertEqual(writes, ['publish:metadata/dependency-receipt.json', 'publish:metadata/dependency-provenance.json',
            'publish:metadata/dependency-inventory.json', 'publish:metadata/native-inputs.json'])
        self.assertEqual(workspace.events[-1], 'workspace-close')
        self.assertTrue(all(result[name] is False for name in proof.FALSE_FACTS))
        self.assertNotIn('dependency_inventory', proof.parse_document(candidate.raw)['prefix'])
        failed = FakeWorkspace()
        failed.directories = ['prefix', 'prefix/include', 'prefix/lib']
        failed.files = {'prefix/' + name: {'path': 'prefix/' + name, 'kind': 'file', **row}
                        for name, row in inventory['files'].items()}
        publish = failed.publish_bytes_new
        def reject_provenance(path, raw):
            if path.endswith('dependency-provenance.json'):
                failed.failed = True
                raise ValueError('known publication failure')
            return publish(path, raw)
        failed.publish_bytes_new = reject_provenance
        with self.assertRaisesRegex(ValueError, 'publication failure'):
            controller._publish_candidate(failed, candidate, inventory, native, [notice])
        self.assertTrue(failed.failed)
        self.assertNotIn('publish:metadata/dependency-inventory.json', failed.events)
        self.assertNotIn('publish:metadata/native-inputs.json', failed.events)
        self.assertNotIn('workspace-close', failed.events)

    def test_publication_rejects_raw_receipt_before_mutation(self):
        workspace = FakeWorkspace()
        with self.assertRaises(ValueError): controller._publish_candidate(workspace, {}, {}, {}, [])
        self.assertEqual(workspace.events, [])


DEPENDENCY_ENTRY_SOURCE = ROOT / 'tools/appended_engine_windows_dependencies.py'
DEPENDENCY_ENTRY_RAW = DEPENDENCY_ENTRY_SOURCE.read_bytes()


def dependency_facade():
    selected = types.ModuleType('private_dependency_entry_fixture')
    selected.__file__ = str(DEPENDENCY_ENTRY_SOURCE)
    exec(compile(DEPENDENCY_ENTRY_RAW, str(DEPENDENCY_ENTRY_SOURCE), 'exec'), vars(selected))
    selected.sys = types.SimpleNamespace(modules={})
    return selected



class DependencyFacadeTests(unittest.TestCase):
    def test_import_has_no_project_import_or_module_execution(self):
        tree = ast.parse(DEPENDENCY_ENTRY_RAW, feature_version=(3, 9))
        imports = []
        for node in tree.body:
            if isinstance(node, ast.Import):
                imports.extend(alias.name.split('.')[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module.split('.')[0])
        self.assertEqual(set(imports), {'__future__', 'argparse', 'hashlib', 'os', 'pathlib',
            'stat', 'sys', 'threading', 'types'})
        selected = dependency_facade()
        self.assertEqual(selected._SOURCE_CACHE, {})
        self.assertEqual(selected._FAILED_RESERVATIONS, [])
        self.assertEqual(selected.sys.modules, {})
        self.assertIs(dependency_entry._legacy(), controller)
        self.assertIs(dependency_entry._recipe_metadata, controller._recipe_metadata)
        self.assertIs(controller._recipe_metadata.__globals__, vars(controller))
        self.assertIs(controller._archive_projection.__globals__, vars(controller))

    def _source(self, selected, directory, body):
        selected._FAMILY = Path(directory)
        target = selected._FAMILY / 'fixture.py'
        target.write_bytes(body)
        return ('fixture.py', hashlib.sha256(body).hexdigest(), len(body), 'owned_fixture')

    def test_exact_cache_reuses_owned_instance_and_rechecks_bytes(self):
        selected = dependency_facade()
        with tempfile.TemporaryDirectory() as directory:
            args = self._source(selected, directory, b'value = 7\n')
            first = selected._fixed_source(*args)
            self.assertIs(selected._fixed_source(*args), first)
            self.assertEqual(first.value, 7)
            (Path(directory) / 'fixture.py').write_bytes(b'value = 8\n')
            with self.assertRaises(selected.SourceBindingError):
                selected._fixed_source(*args)

    def test_cache_foreign_replacement_rejects_without_overwrite(self):
        selected = dependency_facade()
        with tempfile.TemporaryDirectory() as directory:
            args = self._source(selected, directory, b'value = 7\n')
            selected._fixed_source(*args)
            foreign = object()
            selected.sys.modules[args[3]] = foreign
            with self.assertRaises(selected.SourceBindingError):
                selected._fixed_source(*args)
            self.assertIs(selected.sys.modules[args[3]], foreign)

    def test_atomic_reservation_loser_never_executes_or_overwrites(self):
        selected = dependency_facade()
        foreign = object()
        class Namespace(dict):
            def setdefault(self, name, module):
                self[name] = foreign
                return foreign
        selected.sys.modules = Namespace()
        with tempfile.TemporaryDirectory() as directory:
            args = self._source(selected, directory, b'raise AssertionError("executed")\n')
            with self.assertRaises(selected.SourceBindingError):
                selected._fixed_source(*args)
            self.assertIs(selected.sys.modules[args[3]], foreign)
            self.assertEqual(selected._SOURCE_CACHE, {})

    def test_failed_reservation_remains_blocker(self):
        selected = dependency_facade()
        with tempfile.TemporaryDirectory() as directory:
            args = self._source(selected, directory, b'raise RuntimeError("fixture")\n')
            with self.assertRaises(RuntimeError):
                selected._fixed_source(*args)
            reserved = selected.sys.modules[args[3]]
            self.assertIs(selected._FAILED_RESERVATIONS[0], reserved)
            self.assertEqual(selected._SOURCE_CACHE, {})
            with self.assertRaises(selected.SourceBindingError):
                selected._fixed_source(*args)
            self.assertIs(selected.sys.modules[args[3]], reserved)

    def test_foreign_replacement_after_exec_is_retained(self):
        selected = dependency_facade()
        foreign = object()
        class Namespace(dict):
            def get(self, name, default=None):
                if name in self:
                    self[name] = foreign
                return super().get(name, default)
        selected.sys.modules = Namespace()
        with tempfile.TemporaryDirectory() as directory:
            args = self._source(selected, directory, b'value = 7\n')
            with self.assertRaises(selected.SourceBindingError):
                selected._fixed_source(*args)
            self.assertIs(selected.sys.modules[args[3]], foreign)
            self.assertEqual(selected._SOURCE_CACHE, {})

    def test_closed_role_rejects_before_lower_load(self):
        selected = dependency_facade()
        def forbidden(*args):
            self.fail('unexpected source load')
        selected._fixed_source = forbidden
        for role in ('issuer', '../producer', '', None, []):
            with self.assertRaises(selected.SourceBindingError):
                selected._module(role)

    def test_one_actual_controller_resolves_each_role(self):
        selected = dependency_facade()
        core = types.SimpleNamespace()
        calls, products = [], {}
        def resolve(role):
            calls.append(role)
            if role == 'controller':
                return core
            return products.setdefault(role, object())
        core._support_module = resolve
        selected._fixed_source = lambda *args: core
        self.assertIs(selected._module('controller'), core)
        first = selected._module('producer')
        self.assertIs(selected._module('producer'), first)
        self.assertEqual(calls, ['controller', 'controller', 'controller',
            'producer', 'controller', 'producer'])

    def test_unknown_attribute_does_not_load_legacy(self):
        selected = dependency_facade()
        selected._legacy = lambda: self.fail('unexpected legacy load')
        with self.assertRaises(AttributeError):
            selected.__getattr__('__path__')

    def test_native_cli_routes_only_exact_request_pair(self):
        selected = dependency_facade()
        calls = []
        producer = types.SimpleNamespace(cli=lambda argv: calls.append(argv) or 7)
        selected._module = lambda role: producer if role == 'producer' else self.fail(role)
        selected._legacy = lambda: self.fail('native request warmed legacy')
        for action in ('plan', 'build'):
            argv = [action, '--request', 'request.json', '--request-sha256', 'a' * 64]
            self.assertEqual(selected.cli(argv), 7)
            self.assertEqual(calls[-1], argv)

    def test_legacy_cli_preserves_both_old_flag_pairs(self):
        selected = dependency_facade()
        calls = []
        legacy = types.SimpleNamespace(cli=lambda argv: calls.append(argv) or 2)
        selected._module = lambda role: self.fail('legacy request warmed native Core')
        selected._legacy = lambda: legacy
        for action, flag in (('plan', 'selection'), ('build', 'plan')):
            argv = [action, '--' + flag, 'input.json', '--' + flag + '-sha256', 'b' * 64]
            self.assertEqual(selected.cli(argv), 2)
            self.assertEqual(calls[-1], argv)

    def test_cli_mismatched_or_missing_pins_reject_before_source_load(self):
        selected = dependency_facade()
        selected._module = lambda role: self.fail('invalid flags loaded Core')
        selected._legacy = lambda: self.fail('invalid flags loaded legacy')
        for argv in (['plan', '--request', 'x'], ['build', '--plan', 'x'],
                ['plan', '--request', 'x', '--selection-sha256', 'a' * 64],
                ['build', '--plan', 'x', '--request-sha256', 'a' * 64]):
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                selected.cli(argv)

    def test_public_admission_calls_preserve_one_actual_role_owner(self):
        selected = dependency_facade()
        calls = []
        def role(name):
            class Owner:
                def __getattr__(self, method):
                    return lambda *args, **kwargs: calls.append((name, method, args, kwargs)) or token
            return Owner()
        selected._module = role
        token = object()
        self.assertIs(selected.inventory_declaration(b'raw', 'pin', 'llvm',
            provenance_raw=b'prov', provenance_pin='provpin'), token)
        self.assertEqual(calls[-1], ('current_inputs', 'inventory_declaration',
            (b'raw', 'pin', 'llvm'), {'provenance_raw': b'prov', 'provenance_pin': 'provpin'}))
        for invoke, owner, method in (
                (lambda: selected.validate_toolchain_identity(b'h', 'pin', {'fact': 1}),
                    'current_inputs', 'validate_toolchain_identity'),
                (lambda: selected.engine_admission_declaration({'value': 1}, token),
                    'current_inputs', 'engine_admission_declaration'),
                (lambda: selected.admit_retained_dependency_with_probe({'path': 'x'}, overall_deadline=9),
                    'retained_dependency', 'admit_retained_dependency_with_probe'),
                (lambda: selected.require_retained_dependency_with_probe(token),
                    'retained_dependency', 'require_retained_dependency_with_probe'),
                (lambda: selected.require_dependency_with_probe(token),
                    'producer', 'require_dependency_with_probe'),
                (lambda: selected.admit_retained_originals({'path': 'x'}, deadline=9, limits={}),
                    'current_inputs', 'admit_retained_originals'),
                (lambda: selected.require_original_membership(token, []),
                    'current_inputs', 'require_original_membership')):
            self.assertIs(invoke(), token)
            self.assertEqual(calls[-1][:2], (owner, method))

    def test_core_requires_registered_actual_facade_before_execution(self):
        selected = dependency_facade()
        with tempfile.TemporaryDirectory() as directory:
            selected._FAMILY = Path(directory)
            raw = b'raise AssertionError("unowned Core executed")\n'
            (selected._FAMILY / 'controller.py').write_bytes(raw)
            with self.assertRaisesRegex(selected.SourceBindingError, 'actual dependency entry owner'):
                selected._fixed_source('controller.py', hashlib.sha256(raw).hexdigest(),
                    len(raw), selected._CONTROLLER_NAME)
            reserved = selected.sys.modules[selected._CONTROLLER_NAME]
            self.assertEqual(selected._FAILED_RESERVATIONS, [reserved])
            self.assertEqual(selected._SOURCE_CACHE, {})



if __name__ == '__main__':
    unittest.main()
