"""In-memory native binding fixtures only. Never load WinDLL or launch a process."""
import copy
import ctypes
import hashlib
import io
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import appended_engine_windows_publication as publication
import process_tree


class _Stream(io.BytesIO):
    def __init__(self, node): super().__init__(); self.node = node
    def write(self, raw): self.node['data'].extend(raw); return len(raw)


class FakeNative:
    """A private finite object/handle model, not filesystem qualification."""
    def __init__(self):
        self.nodes, self.handles, self.events = {}, {}, []
        self.next_id, self.next_handle = 1, 1
        self.short_write = None; self.flush_error = False; self.rename_error = None
        self.add('C:/', True); self.add('C:/work', True)

    def add(self, path, directory=False, data=b''):
        node = {'path': path, 'directory': directory, 'data': bytearray(data),
            'identity': [7, '%032x' % self.next_id], 'links': 1, 'version': [1, 1, 1], 'attributes': 16 if directory else 128}
        self.next_id += 1; self.nodes[path.casefold()] = node; return node

    def handle(self, node):
        value = self.next_handle; self.next_handle += 1; self.handles[value] = node; return value

    def open_root(self, root): return self.handle(self.nodes[root.casefold()])

    def open_child(self, parent, name, *, create=False, directory=False, writable=False, metadata_only=False):
        base = self.handles[parent]['path']; path = base + ('' if base.endswith('/') else '/') + name
        key = path.casefold()
        if create:
            if key in self.nodes: raise FileExistsError(path)
            node = self.add(path, directory); self.events.append(('create', path))
        else:
            if key not in self.nodes: raise FileNotFoundError(path)
            node = self.nodes[key]
        return self.handle(node)

    def state(self, handle):
        node = self.handles[handle]
        if node.get('reparse') or not node['directory'] and node['links'] != 1:
            raise publication.PublicationError('reparse/linked fixture object')
        return {name: copy.deepcopy(value) for name, value in node.items() if name not in ('data', 'reparse')} | {'bytes': len(node['data'])}

    def verify_private(self, handle): self.events.append(('private', self.handles[handle]['path']))
    def filesystem(self, handle): return {'name': 'NTFS', 'volume_serial': 7}
    def names(self, handle):
        root = self.handles[handle]['path'].rstrip('/') + '/'
        return sorted(node['path'][len(root):] for node in self.nodes.values()
            if node['path'].startswith(root) and '/' not in node['path'][len(root):])
    def write(self, handle, raw):
        count = min(len(raw), self.short_write) if self.short_write is not None else len(raw)
        self.handles[handle]['data'].extend(raw[:count]); return count
    def flush(self, handle):
        self.events.append(('flush', self.handles[handle]['path']))
        if self.flush_error: raise OSError('injected flush failure')
    def read(self, handle, maximum):
        data = bytes(self.handles[handle]['data'])
        if len(data) > maximum: raise publication.PublicationError('file bound')
        return data
    def close(self, handle): self.events.append(('close', self.handles[handle]['path'])); del self.handles[handle]
    def stream(self, handle):
        stream = _Stream(self.handles[handle]); stream.descriptor = id(stream); stream.native_handle = handle
        return stream
    def stream_state(self, stream):
        if stream.closed: raise publication.OwnershipUncertain('fixture stream closed')
        return {'descriptor': stream.descriptor, 'handle': stream.native_handle,
            'identity': copy.deepcopy(stream.node['identity']), 'path': stream.node['path']}
    def rename_new(self, handle, parent, name):
        node = self.handles[handle]; base = self.handles[parent]['path'].rstrip('/')
        path = base + '/' + name
        if path.casefold() in self.nodes: raise FileExistsError(path)
        del self.nodes[node['path'].casefold()]; node['path'] = path; self.nodes[path.casefold()] = node
        self.events.append(('rename', path))
        if self.rename_error: raise self.rename_error
    def remove(self, handle):
        node = self.handles[handle]; del self.nodes[node['path'].casefold()]; self.close(handle)


def workspace(native=None, **limits):
    native = native or FakeNative()
    return publication.Workspace._create(native, 'C:/work/new', (), limits), native


def owner(code=0, finish_error=None, close_error=None):
    process = mock.Mock(returncode=code); process.poll.return_value = code
    result = process_tree.ProcessTree(process, mock.Mock())
    result.finish = mock.Mock(return_value=code, side_effect=finish_error)
    def close():
        if close_error: raise close_error
        result.closed = True
    result.close = mock.Mock(side_effect=close)
    return result


def runtime():
    return {'python_path': 'C:/python/python.exe', 'python_sha256': '1' * 64, 'python_version': '3.9.20',
        'system': 'Windows', 'machine': 'x86_64', 'pointer_bits': 64,
        'windows_version': [10, 0, 20348], 'system_root': 'C:/Windows'}


def evidence(directory):
    sources = {name: '1' * 64 for name in publication.SOURCE_FILES}
    sources['tools/appended_engine_windows_contract.py'] = publication.CONTRACT_SHA256
    def save(name, value, raw=False):
        path = directory / name; data = value if raw else publication.encoded(value); path.write_bytes(data)
        return {'path': str(path), 'sha256': hashlib.sha256(data).hexdigest()}
    inventory = ['diagnostic_windows_engine_publication.NativePublication.' + name for name in publication.CASE_NAMES]
    run = {'schema_version': 1, 'system': 'Windows', 'status': 'passed', 'inventory': inventory,
        'excluded': {}, 'results': {name: {'status': 'passed'} for name in inventory}}
    common = {'scope': publication.SCOPE, 'policy': publication.POLICY, 'source_identity': sources,
        'runtime_identity': runtime(), 'filesystem': {'name': 'NTFS', 'volume_serial': 7}}
    observed = {'schema_version': 1, 'kind': 'foundation-windows-publication-observations-v1', **common,
        'cases': {name: {'operation': name, 'observed': {'fixture_native_observation': 1}} for name in publication.CASE_NAMES}}
    observed_ref = save('observations.json', observed)
    console = b'WINDOWS_PUBLICATION_OBSERVATIONS_SHA256=' + observed_ref['sha256'].encode() + b'\n'
    report = {'schema_version': 1, 'kind': 'foundation-windows-publication-qualification-v1', **common,
        'run_report': save('run.json', run), 'observations': observed_ref, 'console': save('console.log', console, True)}
    return save('qualification.json', report), report, sources, run, observed


class WindowsPublicationTests(unittest.TestCase):
    def tearDown(self): publication._RETAINED.clear()

    def test_fixed_x64_layouts_do_not_use_host_long_or_wchar(self):
        expected = publication.abi_layout()
        self.assertEqual(expected['OBJECT_ATTRIBUTES'], 48)
        self.assertEqual(ctypes.sizeof(publication.U32), 4)
        self.assertEqual(ctypes.sizeof(publication.U16), 2)
        self.assertEqual(publication.IO_STATUS_BLOCK.Information.offset, 8)
        self.assertEqual(publication.FILE_RENAME_INFORMATION.FileName.offset, 20)

    def test_unicode_and_rename_buffers_keep_byte_lengths_and_no_replace(self):
        storage, value = publication._utf16('a\U0001f600')
        self.assertEqual(value.Length, 6); self.assertEqual(value.MaximumLength, 8)
        raw = publication._rename_buffer(123, 'hello.txt')
        header = publication.FILE_RENAME_INFORMATION.from_buffer(raw)
        self.assertEqual(header.Flags, 0); self.assertEqual(header.RootDirectory, 123)
        self.assertEqual(header.FileNameLength, 18)
        self.assertEqual(bytes(raw)[20:38].decode('utf-16-le'), 'hello.txt')
        with self.assertRaises(ValueError): publication._utf16('x\0y')

    def test_directory_buffer_complete_chain_and_malformed_offsets(self):
        raw = struct.pack('<III', 0, 0, 8) + 'name'.encode('utf-16-le')
        self.assertEqual(publication._directory_names(raw), ['name'])
        for bad in (b'', raw[:11], struct.pack('<III', 1, 0, 8) + raw[12:], struct.pack('<III', 0, 0, 7) + raw[12:]):
            with self.subTest(bad=bad), self.assertRaises(ValueError): publication._directory_names(bad)

    def test_child_paths_reject_traversal_devices_ads_and_lists(self):
        for path in ('../file', 'NUL', 'a:stream', '/absolute', 'a\\b', 'a//b', 'a;code'):
            with self.subTest(path=path), self.assertRaises(ValueError): publication._relative(path)

    def test_public_workspace_never_loads_native_binding_on_linux(self):
        with mock.patch.object(publication, '_Native') as binding:
            with self.assertRaises(ValueError): publication.Workspace.create_new('C:/work/new', protected_paths=(), limits={}, qualification=True)
        binding.assert_not_called()

    def test_public_constructor_does_not_accept_a_qualified_boolean(self):
        with mock.patch.object(publication, '_native_host'), mock.patch.object(publication, '_Native') as binding:
            with self.assertRaises(ValueError): publication.Workspace.create_new('C:/work/new', protected_paths=(), limits={}, qualification=True)
        binding.assert_not_called()
        with self.assertRaises(ValueError): publication.Workspace()

    def test_overlap_checks_precede_mutation(self):
        native = FakeNative()
        for protected in ('C:/work/new', 'C:/work', 'C:/work/new/retained.bin'):
            with self.subTest(protected=protected), self.assertRaisesRegex(ValueError, 'overlaps'):
                publication.Workspace._create(native, 'C:/work/new', [protected], {})
        self.assertFalse(any(event[0] == 'create' for event in native.events))

    def test_existing_empty_directory_and_case_alias_never_replaced(self):
        native = FakeNative(); existing = native.add('C:/work/NEW', True)
        with self.assertRaises(FileExistsError): workspace(native)
        self.assertIs(native.nodes['c:/work/new'], existing)

    def test_atomic_file_is_complete_and_read_back(self):
        work, native = workspace(); native.short_write = 2
        row = work.publish_bytes_new('result.json', b'complete')
        self.assertEqual(row, {'path': 'result.json', 'sha256': hashlib.sha256(b'complete').hexdigest(), 'bytes': 8})
        events = [event[0] for event in native.events]
        self.assertLess(events.index('flush'), events.index('rename'))
        self.assertEqual(bytes(native.nodes['c:/work/new/result.json']['data']), b'complete')

    def test_collision_preserves_existing_bytes_and_owned_pending(self):
        work, native = workspace(); old = native.add('C:/work/new/result', False, b'old')
        with self.assertRaises(FileExistsError): work.publish_bytes_new('result', b'new')
        self.assertEqual(bytes(old['data']), b'old')
        pending = work._retained_pending[0][0]
        self.assertIn(pending.casefold(), {node['path'].split('/new/')[1].casefold() for node in native.nodes.values() if '/new/' in node['path']})
        work.remove_owned_pending(pending)
        self.assertEqual(bytes(old['data']), b'old')

    def test_zero_write_and_flush_error_never_publish_final_name(self):
        for setting in ('short_write', 'flush_error'):
            work, native = workspace(); setattr(native, setting, 0 if setting == 'short_write' else True)
            with self.subTest(setting=setting), self.assertRaises((ValueError, OSError)):
                work.publish_bytes_new('result', b'new')
            self.assertNotIn('c:/work/new/result', native.nodes)
            self.assertTrue(work.failed)

    def test_unreturned_created_handle_keeps_workspace_uncertain(self):
        work, native = workspace(); original = native.open_child
        def unconfirmed(*args, **kwargs):
            handle = original(*args, **kwargs)
            native._unknown_handles = [handle]
            raise publication.OwnershipUncertain('injected create result loss')
        with mock.patch.object(native, 'open_child', side_effect=unconfirmed):
            with self.assertRaises(publication.OwnershipUncertain): work.publish_bytes_new('result', b'bytes')
        self.assertTrue(work.uncertain)
        self.assertIn(native._unknown_handles[0], native.handles)
        with self.assertRaises(publication.OwnershipUncertain): work.close_joined()

    def test_creation_security_cleanup_failure_retains_native_handle(self):
        native = publication._Native.__new__(publication._Native); native.events = []
        native._private_sd = lambda: publication.PVOID(456)
        def create(handle, access, attributes, status, *args):
            ctypes.cast(handle, ctypes.POINTER(publication.HANDLE)).contents.value = 123
            ctypes.cast(status, ctypes.POINTER(publication.IO_STATUS_BLOCK)).contents.Information = 2
            return 0
        native.n = SimpleNamespace(NtCreateFile=create)
        native.k = SimpleNamespace(LocalFree=lambda descriptor: 456)
        with self.assertRaises(publication.OwnershipUncertain): native.open_child(9, 'new', create=True)
        self.assertEqual(native._unknown_handles, [123])
        self.assertEqual(native._unknown_security_descriptors[0].value, 456)

    def test_unexpected_pending_retains_ctypes_operation_storage(self):
        native = publication._Native.__new__(publication._Native); native.events = []
        native._private_sd = lambda: publication.PVOID(456)
        def pending(handle, *args):
            ctypes.cast(handle, ctypes.POINTER(publication.HANDLE)).contents.value = 123
            return 0x103
        native.n = SimpleNamespace(NtCreateFile=pending)
        native.k = SimpleNamespace(LocalFree=mock.Mock())
        with self.assertRaises(publication.OwnershipUncertain): native.open_child(9, 'new', create=True)
        native.k.LocalFree.assert_not_called()
        self.assertEqual(native._unknown_handles, [123])
        self.assertEqual(len(native._unknown_operations), 1)

    def test_pending_identity_change_before_rename_retains_ownership(self):
        work, native = workspace(); original = native.write
        def changed(handle, raw):
            count = original(handle, raw)
            native.handles[handle]['identity'] = [7, 'changed']
            return count
        with mock.patch.object(native, 'write', side_effect=changed):
            with self.assertRaises(publication.OwnershipUncertain): work.publish_bytes_new('result', b'bytes')
        self.assertTrue(work.uncertain); self.assertNotIn('c:/work/new/result', native.nodes)

    def test_uncertain_rename_retains_committed_bytes_and_all_ownership(self):
        work, native = workspace(); native.rename_error = OSError('after committed rename')
        with self.assertRaises(OSError): work.publish_bytes_new('result', b'complete')
        self.assertEqual(bytes(native.nodes['c:/work/new/result']['data']), b'complete')
        self.assertTrue(work.uncertain)
        with self.assertRaises(publication.OwnershipUncertain): work.close_joined()
        self.assertFalse(work.closed)

    def test_changed_ancestor_identity_prevents_later_publication(self):
        work, native = workspace(); native.nodes['c:/work']['identity'][1] = 'changed'
        with self.assertRaises(publication.OwnershipUncertain): work.publish_bytes_new('result', b'x')
        self.assertNotIn('c:/work/new/result', native.nodes)

    def test_cleanup_refuses_changed_pending_identity(self):
        work, native = workspace(); native.flush_error = True
        with self.assertRaises(OSError): work.publish_bytes_new('result', b'new')
        pending, handle, _identity = work._retained_pending[0]
        native.handles[handle]['identity'] = [7, 'foreign']
        with self.assertRaises(publication.OwnershipUncertain): work.remove_owned_pending(pending)
        self.assertIn(handle, native.handles)

    def test_job_owner_finishes_and_closes_once_before_log_publication(self):
        work, native = workspace(); work.mkdir_new('logs'); log = work.open_log_new('logs/build.log')
        log.stream.write(b'original stdout'); work.mark_running(log)
        owned = owner(); work.bind_owner(log, owned)
        joined = work.mark_joined(log, {'phase': 'build', 'returncode': 0})
        self.assertIs(joined.as_dict()['process_tree_closed'], True)
        owned.finish.assert_called_once(); owned.close.assert_called_once()
        row = work.seal_log(log)
        self.assertEqual(row['bytes'], 15); self.assertTrue(log.stream.closed)
        self.assertEqual(log._state, 'sealed')

    def test_launch_uses_exact_owned_stream_and_internally_binds_owner(self):
        for cap in (None, 3):
            with self.subTest(maximum_active_processes=cap):
                work, _native = workspace(); log = work.open_log_new('build.log'); work.mark_running(log)
                owned = owner(); argv, env = ['C:/python/python.exe', '-B'], {'SystemRoot': 'C:/Windows'}
                with mock.patch.object(process_tree, 'launch', return_value=owned) as launch:
                    self.assertIs(work.launch(log, argv, 'C:/work/new', env=env,
                        maximum_active_processes=cap), owned)
                expected = {'env': env}
                if cap is not None:
                    expected['maximum_active_processes'] = cap
                launch.assert_called_once_with(argv, 'C:/work/new', log.stream, **expected)
                self.assertIs(log._owner, owned)
                work.mark_joined(log, {'phase': 'build'}); work.seal_log(log)

    def test_native_binding_rejects_unrelated_job_owner(self):
        work, native = workspace(); log = work.open_log_new('build.log'); work.mark_running(log)
        with mock.patch.object(publication, '_Native', type(native)):
            with self.assertRaisesRegex(ValueError, 'Workspace.launch'): work.bind_owner(log, owner())
        self.assertIsNone(log._owner)

    def test_original_owned_log_stream_is_read_only_before_launch(self):
        work, _native = workspace(); log = work.open_log_new('build.log'); original = log.stream
        with self.assertRaises(AttributeError): log.stream = io.BytesIO()
        self.assertIs(log.stream, original)

    def test_raw_descriptor_or_stream_target_reuse_prevents_launch(self):
        for mutation in ('descriptor', 'handle', 'target', 'primary'):
            work, native = workspace(); log = work.open_log_new('build.log'); work.mark_running(log)
            foreign = native.add('C:/work/new/foreign', False, b'foreign')
            if mutation == 'descriptor': log.stream.descriptor += 1
            elif mutation == 'handle': log.stream.native_handle += 1
            elif mutation == 'target': log.stream.node = foreign
            else: native.handles[log._handle] = foreign
            with mock.patch.object(process_tree, 'launch') as launch:
                with self.subTest(mutation=mutation), self.assertRaises(publication.OwnershipUncertain):
                    work.launch(log, ['program'], 'C:/work/new', env={})
            launch.assert_not_called(); self.assertTrue(work.uncertain)

    def test_joined_stream_descriptor_target_change_prevents_log_sealing(self):
        work, native = workspace(); log = work.open_log_new('build.log'); work.mark_running(log)
        work.bind_owner(log, owner()); work.mark_joined(log, {'phase': 'build'})
        log.stream.node = native.add('C:/work/new/foreign', False, b'foreign')
        with self.assertRaises(publication.OwnershipUncertain): work.seal_log(log)
        self.assertNotIn('c:/work/new/build.log', native.nodes)
        self.assertFalse(log.stream.closed); self.assertTrue(work.uncertain)

    def test_launch_failure_retains_log_and_workspace_without_retry(self):
        work, _native = workspace(); log = work.open_log_new('build.log'); work.mark_running(log)
        with mock.patch.object(process_tree, 'launch', side_effect=process_tree.ProcessTreeError('unconfirmed launch')) as launch:
            with self.assertRaises(process_tree.ProcessTreeError): work.launch(log, ['program'], 'C:/work/new', env={})
        self.assertEqual(launch.call_count, 1); self.assertTrue(work.uncertain)
        self.assertFalse(log.stream.closed)

    def test_log_stream_creation_failure_retains_primary_pending_identity(self):
        work, native = workspace()
        with mock.patch.object(native, 'stream', side_effect=OSError('stream construction failed')):
            with self.assertRaises(OSError): work.open_log_new('build.log')
        pending, handle, identity = work._retained_pending[0]
        self.assertTrue(work.uncertain); self.assertEqual(native.handles[handle]['identity'], identity)
        self.assertTrue(pending.startswith('.build.log.pending-'))

    def test_partial_native_stream_creation_retains_duplicate_or_descriptor(self):
        for step in ('open_osfhandle', 'setmode', 'fdopen'):
            native = publication._Native.__new__(publication._Native)
            def duplicate(process, handle, target, result, *args):
                ctypes.cast(result, ctypes.POINTER(publication.HANDLE)).contents.value = 789
                return 1
            native.k = SimpleNamespace(GetCurrentProcess=lambda: 42, DuplicateHandle=duplicate)
            bridge = SimpleNamespace(open_osfhandle=mock.Mock(return_value=99,
                side_effect=OSError('conversion failed') if step == 'open_osfhandle' else None),
                setmode=mock.Mock(return_value=0, side_effect=OSError('binary mode failed') if step == 'setmode' else None))
            with mock.patch.dict(sys.modules, {'msvcrt': bridge}), mock.patch.object(os, 'O_BINARY', 0, create=True), \
                    mock.patch.object(os, 'fdopen', side_effect=OSError('fdopen failed')):
                with self.subTest(step=step), self.assertRaises(OSError): native.stream(123)
            if step == 'open_osfhandle': self.assertEqual(native._unknown_handles, [789])
            else: self.assertEqual(native._unknown_stream_descriptors, [99])

    def test_native_stream_identity_queries_current_crt_handle_without_closing_it(self):
        native = publication._Native.__new__(publication._Native)
        native.state = mock.Mock(return_value={'directory': False, 'identity': [7, 'a' * 32], 'path': 'C:/work/pending'})
        stream = SimpleNamespace(closed=False, fileno=lambda: 99)
        bridge = SimpleNamespace(get_osfhandle=mock.Mock(return_value=123))
        with mock.patch.dict(sys.modules, {'msvcrt': bridge}):
            result = native.stream_state(stream)
        self.assertEqual(result, {'descriptor': 99, 'handle': 123, 'identity': [7, 'a' * 32], 'path': 'C:/work/pending'})
        bridge.get_osfhandle.assert_called_once_with(99); native.state.assert_called_once_with(123)

    def test_boolean_receipt_cannot_close_unbound_running_log(self):
        work, _native = workspace(); log = work.open_log_new('build.log'); work.mark_running(log)
        with self.assertRaises(publication.OwnershipUncertain): work.mark_joined(log, {'phase': 'build', 'process_tree_closed': True})
        with self.assertRaises(ValueError): work.seal_log(log)

    def test_no_output_inspection_or_commit_while_job_writes(self):
        work, _native = workspace(); log = work.open_log_new('build.log'); work.mark_running(log)
        with self.assertRaises(ValueError): work.inspect_outputs()
        with self.assertRaises(ValueError): work.commit_receipt_new('receipt.json', b'{}')
        self.assertEqual(work.usage()['bytes'], 0)

    def test_running_usage_reads_anchored_log_size_and_enforces_bound(self):
        work, _native = workspace(maximum_log_bytes=3)
        log = work.open_log_new('build.log'); work.mark_running(log)
        log.stream.write(b'abc')
        self.assertEqual(work.usage(log=log)['log_bytes'], 3)
        log.stream.write(b'd')
        with self.assertRaisesRegex(ValueError, 'Log byte bound'): work.usage(log=log)
        self.assertFalse(work.uncertain)

    def test_uncertain_job_finish_or_close_retains_log_and_workspace(self):
        for which in ('finish_error', 'close_error'):
            work, _native = workspace(); log = work.open_log_new('build.log'); work.mark_running(log)
            work.bind_owner(log, owner(**{which: process_tree.ProcessTreeError('cannot prove close')}))
            with self.subTest(which=which), self.assertRaises(process_tree.ProcessTreeError): work.mark_joined(log, {'phase': 'build'})
            self.assertTrue(work.uncertain); self.assertFalse(log.stream.closed)

    def test_known_nonzero_can_seal_failure_log_but_cannot_commit_success(self):
        work, _native = workspace(); log = work.open_log_new('build.log'); work.mark_running(log)
        work.bind_owner(log, owner(7)); joined = work.mark_joined(log, {'phase': 'install'})
        self.assertEqual(joined.as_dict()['returncode'], 7)
        work.seal_log(log)
        with self.assertRaises(ValueError): work.commit_receipt_new('receipt.json', b'{}')

    def test_failed_resource_phase_uses_already_joined_token_without_rejoining(self):
        work, _native = workspace(); log = work.open_log_new('build.log'); work.mark_running(log)
        owned = owner(); work.bind_owner(log, owned); joined = work.mark_joined(log, {'phase': 'probe'})
        result = work.mark_failed_joined(joined, 'output limit')
        self.assertEqual(result['status'], 'failed'); owned.finish.assert_called_once()
        work.seal_log(log)
        with self.assertRaises(ValueError): work.commit_receipt_new('receipt.json', b'{}')

    def test_complete_inventory_reads_bytes_and_rejects_physical_alias(self):
        work, native = workspace(); work.mkdir_new('files'); row = work.publish_bytes_new('files/data', b'hello')
        result = work.inspect_outputs(); self.assertEqual(result['bytes'], 5)
        self.assertEqual(result['directories'], ['files']); self.assertEqual(result['files']['files/data']['sha256'], row['sha256'])
        alias = native.add('C:/work/new/files/alias', False, b'hello')
        alias['identity'] = copy.deepcopy(native.nodes['c:/work/new/files/data']['identity'])
        with self.assertRaisesRegex(ValueError, 'Physical output alias'): work.inspect_outputs()

    def test_output_byte_limit_and_singly_linked_rule_are_enforced(self):
        work, native = workspace(maximum_output_bytes=3); native.add('C:/work/new/data', False, b'four')
        with self.assertRaisesRegex(ValueError, 'byte bound'): work.inspect_outputs()
        native.nodes['c:/work/new/data']['links'] = 2
        with self.assertRaisesRegex(ValueError, 'linked'): work.inspect_outputs()

    def test_failed_nested_inspection_closes_all_known_read_handles(self):
        work, native = workspace(); native.add('C:/work/new/a', True)
        native.add('C:/work/new/a/data', False, b'valid')
        bad = native.add('C:/work/new/zbad', False, b'bad'); bad['links'] = 2
        owned = set(native.handles)
        with self.assertRaises(ValueError): work.inspect_outputs()
        self.assertEqual(set(native.handles), owned)
        with self.assertRaises(ValueError): work.usage()
        self.assertEqual(set(native.handles), owned)

    def test_inspection_close_uncertainty_retains_exact_reader(self):
        work, native = workspace(); native.add('C:/work/new/data', False, b'valid')
        original = native.close
        def failed_close(handle):
            if native.handles[handle]['path'].endswith('/data'): raise OSError('reader close lost')
            original(handle)
        with mock.patch.object(native, 'close', side_effect=failed_close):
            with self.assertRaises(OSError): work.inspect_outputs()
        self.assertTrue(work.uncertain)
        self.assertEqual(len(work._retained_readers), 1)
        self.assertIn(work._retained_readers[0], native.handles)

    def test_native_runtime_qualification_needs_original_complete_joined_cases(self):
        with tempfile.TemporaryDirectory() as temporary:
            ref, report, sources, _run, _observed = evidence(Path(temporary).resolve())
            checked = publication.admit_qualification(ref, source_identity=sources, runtime_identity=runtime())
            self.assertIs(checked.as_dict()['production_eligible'], False)
            self.assertIs(checked.as_dict()['power_loss_guarantee'], False)
            report['source_identity'].clear()
            self.assertEqual(len(checked.as_dict()['source_identity']), 4)

    def test_qualification_runtime_source_and_contract_mismatches_reject(self):
        with tempfile.TemporaryDirectory() as temporary:
            ref, _report, sources, _run, _observed = evidence(Path(temporary).resolve())
            for subject in ('runtime', 'source'):
                changed = runtime() if subject == 'runtime' else copy.deepcopy(sources)
                if subject == 'runtime': changed['python_version'] = '3.12.9'
                else: changed['tools/process_tree.py'] = '2' * 64
                with self.subTest(subject=subject), self.assertRaises(ValueError):
                    publication.admit_qualification(ref, source_identity=changed if subject == 'source' else sources,
                        runtime_identity=changed if subject == 'runtime' else runtime())

    def test_qualification_skipped_missing_or_only_status_evidence_rejects(self):
        for mutation in ('skip', 'missing', 'observations', 'console'):
            with tempfile.TemporaryDirectory() as temporary:
                directory = Path(temporary).resolve(); ref, report, sources, run, observed = evidence(directory)
                if mutation == 'skip': run['excluded'] = {run['inventory'][0]: 'skip'}
                elif mutation == 'missing': run['inventory'].pop()
                elif mutation == 'observations': observed['cases'][publication.CASE_NAMES[0]]['observed'] = {}
                else: (directory / 'console.log').write_bytes(b'passed')
                if mutation in ('skip', 'missing'):
                    path = directory / 'run.json'; path.write_bytes(publication.encoded(run)); report['run_report']['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
                elif mutation == 'observations':
                    path = directory / 'observations.json'; path.write_bytes(publication.encoded(observed)); report['observations']['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
                else: report['console']['sha256'] = hashlib.sha256(b'passed').hexdigest()
                path = directory / 'qualification.json'; path.write_bytes(publication.encoded(report)); ref['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
                with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                    publication.admit_qualification(ref, source_identity=sources, runtime_identity=runtime())

    def test_malformed_native_case_types_fail_as_admission_errors(self):
        for mutation in ('inventory', 'results', 'version', 'version_bound', 'baseline'):
            with tempfile.TemporaryDirectory() as temporary:
                directory = Path(temporary).resolve(); ref, report, sources, run, _observed = evidence(directory)
                selected_runtime = runtime()
                if mutation == 'inventory': run['inventory'][0] = {'unhashable': True}
                elif mutation == 'results': run['results'] = []
                elif mutation == 'version': selected_runtime['python_version'] = []
                elif mutation == 'baseline': selected_runtime['python_version'] = '3.8.20'
                else: selected_runtime['windows_version'][2] = 2 ** 32
                if mutation in ('inventory', 'results'):
                    data = publication.encoded(run); (directory / 'run.json').write_bytes(data)
                    report['run_report']['sha256'] = hashlib.sha256(data).hexdigest()
                else: report['runtime_identity'] = selected_runtime
                data = publication.encoded(report); (directory / 'qualification.json').write_bytes(data)
                ref['sha256'] = hashlib.sha256(data).hexdigest()
                with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                    publication.admit_qualification(ref, source_identity=sources, runtime_identity=selected_runtime)

    def test_public_factory_protects_original_authority_and_actual_program(self):
        sources = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in publication.SOURCE_FILES}
        facts = {'runtime_identity': runtime(), 'source_identity': sources, 'filesystem': {'name': 'NTFS', 'volume_serial': 7},
            'reference': {'path': 'C:/authority/qualification.json'}, 'originals': {
                name: {'path': 'C:/authority/' + name} for name in ('cases.json', 'observations.json', 'console.log')}}
        qualification = publication.Qualification(publication.encoded(facts), publication._TOKEN)
        native = FakeNative(); native.runtime_identity = runtime
        with mock.patch.object(publication, '_native_host'), mock.patch.object(publication, '_Native', return_value=native), \
                mock.patch.object(publication.Workspace, '_create', return_value='private fixture') as create:
            self.assertEqual(publication.Workspace.create_new('C:/output', protected_paths=['C:/input'], limits={}, qualification=qualification), 'private fixture')
        protected = set(create.call_args.args[2])
        self.assertTrue({'C:/input', 'C:/authority/qualification.json', 'C:/authority/cases.json',
            'C:/authority/observations.json', 'C:/authority/console.log', 'C:/python/python.exe', 'C:/Windows'} <= protected)


class InputFakeNative(FakeNative):
    """Private in-memory handle model; none of its facts qualify a native OS."""
    def __init__(self):
        super().__init__()
        self.opens, self.reads = [], []
        self.enumerations, self.after_names = [], None
        self.short_read, self.read_error, self.after_read, self.close_error = None, None, None, None

    def open_root(self, root):
        self.opens.append((root, True, False))
        return super().open_root(root)

    def open_child(self, parent, name, *, create=False, directory=False, writable=False, metadata_only=False, input_file=False):
        self.opens.append((name, directory, input_file))
        if create or writable: raise AssertionError('input fixture must never mutate')
        return super().open_child(parent, name, directory=directory, metadata_only=metadata_only)

    def state(self, handle, *, _raw=False):
        node = self.handles[handle]
        row = {name: copy.deepcopy(node[name]) for name in ('path', 'directory', 'identity', 'links', 'version', 'attributes')}
        row['bytes'] = len(node['data'])
        if _raw:
            row.update(_basic_attributes=node.get('basic_attributes', node['attributes']),
                _reparse_tag=int(node.get('reparse', False)), _delete_pending=bool(node.get('delete_pending', False)))
            return row
        return super().state(handle)

    def read_at(self, handle, offset, count):
        self.reads.append((handle, offset, count))
        if self.read_error: raise self.read_error
        amount = min(count, self.short_read) if self.short_read is not None else count
        raw = bytes(self.handles[handle]['data'][offset:offset + amount])
        if self.after_read: self.after_read(self.handles[handle])
        return raw

    def names(self, handle, *, deadline=None, maximum_entries=None):
        self.enumerations.append((handle, deadline, maximum_entries))
        names = super().names(handle)
        if self.after_names: self.after_names(self.handles[handle], names)
        if maximum_entries is not None and len(names) > maximum_entries:
            raise publication.PublicationError('inert enumeration bound')
        return names

    def close(self, handle):
        if self.close_error == handle: raise OSError('inert close uncertainty')
        super().close(handle)


def input_limits(**changes):
    result = {'seconds': 30, 'maximum_archive_bytes': 1024 * 1024,
        'maximum_expanded_bytes': 4 * 1024 * 1024, 'maximum_members': 32,
        'maximum_member_bytes': 1024 * 1024, 'maximum_patch_bytes': 1024 * 1024}
    result.update(changes)
    return result


def input_pin(raw=b'body', **changes):
    result = {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw), 'mode': 0o644}
    result.update(changes)
    return result


def inputs(native=None, **limits):
    native = native or InputFakeNative()
    return publication.AnchoredInputs._open(native, 'C:/work', limits=input_limits(**limits)), native


def input_evidence(directory):
    """Original-record grammar fixture with intentionally nonnative subjects."""
    sources = {name: '1' * 64 for name in publication.INPUT_SOURCE_FILES}
    sources['tools/appended_engine_windows_contract.py'] = publication.INPUT_CONTRACT_SHA256
    def save(name, value, raw=False):
        path = directory / name; data = value if raw else publication.encoded(value); path.write_bytes(data)
        return {'path': str(path), 'sha256': hashlib.sha256(data).hexdigest()}
    prefix = 'diagnostic_windows_engine_source_reader.NativeSourceReader.'
    inventory = [prefix + name for name in publication.INPUT_CASE_NAMES]
    run = {'schema_version': 1, 'system': 'Windows', 'status': 'passed', 'inventory': inventory,
        'excluded': {}, 'results': {name: {'status': 'passed'} for name in inventory}}
    common = {'scope': publication.INPUT_SCOPE, 'policy': publication.INPUT_POLICY, 'source_identity': sources,
        'runtime_identity': runtime(), 'filesystem': {'name': 'NTFS', 'volume_serial': 7}}
    observed = {'schema_version': 1, 'kind': 'foundation-windows-source-reader-observations-v1', **common,
        'cases': {name: {'operation': name, 'observed': {'inert_structure_fixture_only': 1}} for name in publication.INPUT_CASE_NAMES}}
    observation = save('input-observations.json', observed)
    report = {'schema_version': 1, 'kind': 'foundation-windows-source-reader-qualification-v1', **common,
        'run_report': save('input-cases.json', run), 'observations': observation,
        'console': save('input-console.log', b'WINDOWS_SOURCE_READER_OBSERVATIONS_SHA256=' + observation['sha256'].encode(), True)}
    return save('input-qualification.json', report), report, sources, run, observed, save


class WindowsInputReaderTests(unittest.TestCase):
    def tearDown(self):
        publication._RETAINED.clear()
        publication._INPUT_ISSUED.clear()

    def test_input_native_open_uses_documented_access_share_and_existing_disposition(self):
        native = publication._Native.__new__(publication._Native); native.events = []
        seen = []
        def opened(handle, access, attrs, status, allocation, attributes, share, disposition, options, *unused):
            ctypes.cast(handle, ctypes.POINTER(publication.HANDLE)).contents.value = 123
            ctypes.cast(status, ctypes.POINTER(publication.IO_STATUS_BLOCK)).contents.Information = 1
            obj = ctypes.cast(attrs, ctypes.POINTER(publication.OBJECT_ATTRIBUTES)).contents
            seen.append((access, obj.RootDirectory, obj.Attributes, share, disposition, options))
            return 0
        native.n = SimpleNamespace(NtCreateFile=opened)
        self.assertEqual(native.open_child(9, 'archive.tar', input_file=True), 123)
        self.assertEqual(seen, [(0x80100000, 9, 0x1040, 1, 1, 0x200060)])
        for flags in ({'create': True}, {'directory': True}, {'writable': True}, {'metadata_only': True}):
            with self.subTest(flags=flags), self.assertRaises(ValueError): native.open_child(9, 'archive.tar', input_file=True, **flags)
        self.assertEqual(len(seen), 1)
        self.assertEqual(native.open_child(9, 'output-readback'), 123)
        self.assertEqual(seen[-1], (0x120081, 9, 0x1040, 7, 1, 0x200020))

    def test_native_read_chunk_checks_seek_result_and_read_count(self):
        native = publication._Native.__new__(publication._Native)
        def seek(handle, offset, result, whence):
            ctypes.cast(result, ctypes.POINTER(publication.I64)).contents.value = offset
            return 1
        def read(handle, buffer, count, result, unused):
            ctypes.memmove(buffer, b'ab', 2)
            ctypes.cast(result, ctypes.POINTER(publication.U32)).contents.value = 2
            return 1
        native.k = SimpleNamespace(SetFilePointerEx=seek, ReadFile=read)
        self.assertEqual(native.read_at(9, 2, 4), b'ab')
        for offset, count in ((True, 1), (-1, 1), (2 ** 63, 1), (0, True), (0, 1024 * 1024 + 1)):
            with self.subTest(offset=offset, count=count), self.assertRaises(ValueError): native.read_at(9, offset, count)
        native.k.SetFilePointerEx = lambda *unused: 1
        with self.assertRaises(publication.OwnershipUncertain): native.read_at(9, 2, 4)
        native.k.SetFilePointerEx = seek
        def impossible_count(handle, buffer, count, result, unused):
            ctypes.cast(result, ctypes.POINTER(publication.U32)).contents.value = count + 1
            return 1
        native.k.ReadFile = impossible_count
        with self.assertRaises(publication.OwnershipUncertain): native.read_at(9, 2, 4)

    def test_native_unexpected_pending_read_retains_buffer_and_owner(self):
        native = publication._Native.__new__(publication._Native)
        def seek(handle, offset, result, whence):
            ctypes.cast(result, ctypes.POINTER(publication.I64)).contents.value = offset
            return 1
        native.k = SimpleNamespace(SetFilePointerEx=seek, ReadFile=lambda *unused: 0)
        with mock.patch.object(publication.ct, 'get_last_error', return_value=997, create=True):
            with self.assertRaises(publication.OwnershipUncertain): native.read_at(9, 0, 3)
        record = native._unknown_operations[0]
        self.assertEqual(record['handle'], 9); self.assertEqual(len(record['storage'][0]), 3)

    def test_raw_native_observation_preserves_rejected_identity_without_admitting_it(self):
        native = publication._Native.__new__(publication._Native); native.events = []
        native.final_path = lambda handle: 'C:/work/meta'
        def info(handle, number, buffer, size):
            if number == 0: ctypes.cast(buffer, ctypes.POINTER(publication.FILE_BASIC_INFO)).contents.FileAttributes = 128
            elif number == 1:
                row = ctypes.cast(buffer, ctypes.POINTER(publication.FILE_STANDARD_INFO)).contents
                row.EndOfFile, row.NumberOfLinks = 4, 2
            elif number == 9: ctypes.cast(buffer, ctypes.POINTER(publication.FILE_ATTRIBUTE_TAG_INFO)).contents.FileAttributes = 128
            else:
                row = ctypes.cast(buffer, ctypes.POINTER(publication.FILE_ID_INFO)).contents
                row.VolumeSerialNumber = 7; row.FileId[0] = 1
            return 1
        native.k = SimpleNamespace(GetFileType=lambda handle: 1, GetFileInformationByHandleEx=info)
        with self.assertRaises(ValueError): native.state(9)
        raw = native.state(9, _raw=True)
        self.assertEqual(raw['identity'], [7, '01' + '00' * 15]); self.assertEqual(raw['links'], 2)
        self.assertEqual(raw['_reparse_tag'], 0)

    def test_metadata_is_pinned_and_all_handles_held_without_mutation(self):
        native = InputFakeNative(); native.add('C:/work/meta.json', data=b'body')
        reader, native = inputs(native)
        self.assertEqual(reader.read('meta.json', expected=input_pin(), maximum=8), b'body')
        self.assertTrue(native.handles); self.assertIn(('meta.json', False, True), native.opens)
        reader.check(); reader.close()
        self.assertTrue(reader.closed); self.assertFalse(reader.uncertain); self.assertEqual(native.handles, {})
        self.assertFalse(any(row[0] in ('create', 'write', 'rename', 'flush', 'private') for row in native.events if isinstance(row, tuple)))
        with self.assertRaises(ValueError): reader.close()

    def test_invalid_active_paths_never_open_selected_input(self):
        for path in ('../x', '/x', 'C:/x', 'C:x', 'a\\b', 'NUL', 'a:stream', 'a//b', 'a/./b'):
            reader, native = inputs(); before = list(native.opens)
            with self.subTest(path=path), self.assertRaises(ValueError): reader.read(path, expected=input_pin(), maximum=8)
            self.assertEqual(native.opens, before); reader.close()

    def test_exact_pin_types_and_logical_mode_reject_before_leaf_open(self):
        for pin in (input_pin(mode=0o755), input_pin(mode=True), input_pin(bytes=True), input_pin(bytes=-1), input_pin(sha256='wrong'), input_pin(sha256='0' * 64)):
            reader, native = inputs(); before = list(native.opens)
            with self.subTest(pin=pin), self.assertRaises(ValueError): reader.read('x', expected=pin, maximum=8)
            self.assertEqual(native.opens, before); reader.close()

    def test_pin_and_eof_mismatches_allow_only_known_owned_close(self):
        for pin in (input_pin(sha256='2' * 64), input_pin(bytes=3)):
            native = InputFakeNative(); native.add('C:/work/meta', data=b'body'); reader, _ = inputs(native)
            with self.subTest(pin=pin), self.assertRaises(ValueError): reader.read('meta', expected=pin, maximum=8)
            if pin['sha256'] == '2' * 64: self.assertTrue(native.reads)
            self.assertFalse(reader.uncertain); reader.close(); self.assertEqual(native.handles, {})

    def test_sha_only_metadata_observes_eof_without_claiming_declared_size(self):
        native = InputFakeNative(); native.add('C:/work/meta', data=b'body'); reader, _ = inputs(native)
        expected = {'sha256': input_pin()['sha256'], 'mode': 0o644}
        self.assertEqual(reader.read('meta', expected=expected, maximum=8), b'body')
        self.assertEqual(set(reader._files['meta']['expected']), {'sha256', 'mode'})
        self.assertEqual(reader._files['meta']['bytes'], 4); self.assertEqual(reader._captured_bytes, 4)
        reader.check(); reader.close()

    def test_sha_only_metadata_oversize_hash_and_change_fail_without_stat_or_extra_pass(self):
        for failure in ('maximum', 'aggregate', 'hash', 'change'):
            native = InputFakeNative(); native.add('C:/work/meta', data=b'body')
            reader, _ = inputs(native, **({'maximum_expanded_bytes': 3} if failure == 'aggregate' else {}))
            expected = {'sha256': '2' * 64 if failure == 'hash' else input_pin()['sha256'], 'mode': 0o644}
            if failure == 'change': native.after_read = lambda node: node['version'].__setitem__(1, 2)
            with self.subTest(failure=failure), self.assertRaises(ValueError):
                reader.read('meta', expected=expected, maximum=3 if failure == 'maximum' else 8)
            if failure in ('maximum', 'aggregate'): self.assertEqual(native.reads, [])
            if failure == 'hash': self.assertTrue(native.reads)
            self.assertFalse(reader.uncertain); reader.close(); self.assertEqual(native.handles, {})

    def test_archive_still_requires_independent_size_declaration(self):
        reader, native = inputs(); before = list(native.opens)
        with self.assertRaises(ValueError): reader.open_archive('archive', expected={'sha256': input_pin()['sha256'], 'mode': 0o644})
        self.assertEqual(native.opens, before); reader.close()

    def test_hardlink_or_nonordinary_rejection_retains_identity_for_close(self):
        for mutation in ('links', 'reparse', 'delete_pending', 'basic_attributes'):
            native = InputFakeNative(); node = native.add('C:/work/meta', data=b'body')
            node[mutation] = 2 if mutation == 'links' else True if mutation != 'basic_attributes' else 0
            reader, _ = inputs(native)
            with self.subTest(mutation=mutation), self.assertRaises(ValueError): reader.read('meta', expected=input_pin(), maximum=8)
            self.assertFalse(reader.uncertain); reader.close(); self.assertEqual(native.handles, {})

    def test_fresh_case_alias_or_wrong_kind_rejection_closes_the_known_opened_object(self):
        for name, directory in (('META', False), ('directory', True)):
            native = InputFakeNative(); native.add('C:/work/meta', data=b'body')
            if directory: native.add('C:/work/directory', directory=True)
            reader, _ = inputs(native)
            with self.subTest(name=name), self.assertRaises(ValueError): reader.read(name, expected=input_pin(), maximum=8)
            self.assertFalse(reader.uncertain); reader.close(); self.assertEqual(native.handles, {})

    def test_archive_capture_does_not_eagerly_hash_or_read(self):
        native = InputFakeNative(); native.add('C:/work/archive', data=b'body'); reader, _ = inputs(native)
        # Wrong SHA is deliberately left to the complete compressed-byte core check.
        view = reader.open_archive('archive', expected=input_pin(sha256='2' * 64))
        self.assertEqual(native.reads, []); reader.check(); self.assertEqual(native.reads, [])
        self.assertEqual(view.read(), b'body'); reader.close()

    def test_archive_view_collects_short_native_reads_and_has_independent_cursors(self):
        native = InputFakeNative(); native.short_read = 2; native.add('C:/work/archive', data=b'abcdef')
        reader, _ = inputs(native); pin = input_pin(b'abcdef')
        first = reader.open_archive('archive', expected=pin); second = reader.open_archive('archive', expected=pin)
        self.assertEqual(first.read(5), b'abcde'); self.assertEqual(second.read(2), b'ab')
        self.assertEqual(first.tell(), 5); self.assertEqual(first.read(), b'f'); self.assertEqual(first.read(1), b'')
        self.assertEqual(second.seek(-2, 2), 4); self.assertEqual(second.read(), b'ef')
        self.assertEqual(second.seek(-1, 1), 5); self.assertEqual(second.read(0), b'')
        self.assertTrue(first.readable()); self.assertTrue(first.seekable()); self.assertFalse(hasattr(first, 'fileno'))
        first.close(); self.assertTrue(first.closed); self.assertTrue(native.handles)
        self.assertEqual(second.seek(0), 0); self.assertEqual(second.read(), b'abcdef')
        reader.close(); self.assertTrue(second.closed)

    def test_seek_rejects_invalid_bounds_without_native_io(self):
        native = InputFakeNative(); native.add('C:/work/archive', data=b'body'); reader, _ = inputs(native)
        view = reader.open_archive('archive', expected=input_pin())
        for offset, whence in ((-1, 0), (5, 0), (True, 0), (0, True), (0, 3), (2 ** 64, 1)):
            with self.subTest(offset=offset, whence=whence), self.assertRaises((ValueError, OSError)): view.seek(offset, whence)
        self.assertEqual(native.reads, []); reader.close()

    def test_zero_before_pinned_eof_stops_capture(self):
        native = InputFakeNative(); native.short_read = 0; native.add('C:/work/archive', data=b'body')
        reader, _ = inputs(native); view = reader.open_archive('archive', expected=input_pin())
        with self.assertRaises(ValueError): view.read()
        with self.assertRaises(ValueError): reader.check()
        reader.close(); self.assertFalse(reader.uncertain)

    def test_state_version_change_rejects_bytes_but_can_close_same_object(self):
        native = InputFakeNative(); node = native.add('C:/work/archive', data=b'body'); reader, _ = inputs(native)
        view = reader.open_archive('archive', expected=input_pin())
        native.after_read = lambda node: node['version'].__setitem__(1, 2)
        with self.assertRaises(ValueError): view.read()
        self.assertFalse(reader.uncertain); reader.close(); self.assertEqual(native.handles, {})

    def test_numeric_file_handle_reuse_never_closes_foreign_target(self):
        native = InputFakeNative(); native.add('C:/work/archive', data=b'body'); reader, _ = inputs(native)
        reader.open_archive('archive', expected=input_pin()); record = reader._files['archive']
        foreign = native.add('C:/work/foreign', data=b'other'); native.handles[record['handle']] = foreign
        with self.assertRaises(publication.OwnershipUncertain): reader.check()
        with self.assertRaises(publication.OwnershipUncertain): reader.close()
        self.assertIn(record['handle'], native.handles); self.assertTrue(reader.uncertain)

    def test_ancestor_identity_change_retains_all_remaining_handles(self):
        reader, native = inputs(); native.nodes['c:/work']['identity'][1] = 'f' * 32
        with self.assertRaises(publication.OwnershipUncertain): reader.check()
        self.assertTrue(reader.uncertain); self.assertTrue(native.handles)

    def test_close_error_retains_owner_and_stops_later_closes(self):
        native = InputFakeNative(); native.add('C:/work/archive', data=b'body'); reader, _ = inputs(native)
        reader.open_archive('archive', expected=input_pin()); native.close_error = reader._files['archive']['handle']
        before = set(native.handles)
        with self.assertRaises(publication.OwnershipUncertain): reader.close()
        self.assertEqual(set(native.handles), before); self.assertIn(reader, publication._RETAINED)

    def test_missing_initial_root_closes_only_known_acquired_ancestors(self):
        native = InputFakeNative()
        with self.assertRaises(FileNotFoundError): publication.AnchoredInputs._open(native, 'C:/missing', limits=input_limits())
        self.assertEqual(native.handles, {}); self.assertEqual(publication._RETAINED, [])

    def test_distinct_bytes_count_and_repeated_selection_are_not_refunded(self):
        native = InputFakeNative(); native.add('C:/work/a', data=b'body'); native.add('C:/work/b', data=b'body')
        reader, _ = inputs(native, maximum_members=1, maximum_expanded_bytes=4)
        self.assertEqual(reader.read('a', expected=input_pin(), maximum=4), b'body')
        read_count = len(native.reads)
        self.assertEqual(reader.read('a', expected=input_pin(), maximum=4), b'body')
        self.assertEqual(len(native.reads), read_count); before = list(native.opens)
        with self.assertRaises(ValueError): reader.read('b', expected=input_pin(), maximum=4)
        self.assertEqual(native.opens, before); self.assertEqual(reader._captured_bytes, 4); reader.close()

    def test_case_alias_different_pin_and_role_rejected_without_second_open(self):
        for path, pin, role in (('A', input_pin(), 'metadata'), ('a', input_pin(sha256='2' * 64), 'metadata'), ('a', input_pin(), 'archive')):
            native = InputFakeNative(); native.add('C:/work/a', data=b'body'); reader, _ = inputs(native)
            reader.read('a', expected=input_pin(), maximum=4); before = list(native.opens)
            with self.subTest(path=path, role=role), self.assertRaises(ValueError):
                if role == 'archive': reader.open_archive(path, expected=pin)
                else: reader.read(path, expected=pin, maximum=4)
            self.assertEqual(native.opens, before); reader.close()

    def test_nonextending_deadline_and_explicit_close_after_expiry(self):
        now = [0.0]
        native = InputFakeNative(); native.add('C:/work/archive', data=b'body')
        with mock.patch.object(publication.time, 'monotonic', side_effect=lambda: now[0]):
            reader = publication.AnchoredInputs._open(native, 'C:/work', limits=input_limits(seconds=10), deadline=3.0)
            view = reader.open_archive('archive', expected=input_pin()); self.assertEqual(reader._deadline, 3.0)
            now[0] = 2.0; self.assertEqual(view.read(1), b'b'); self.assertEqual(reader._deadline, 3.0)
            now[0] = 3.0
            with self.assertRaises(ValueError): reader.check()
            reader.close(); self.assertEqual(native.handles, {})

    def test_limits_deadline_and_archive_maximum_are_exact(self):
        for change in ({'seconds': True}, {'maximum_members': 1000001}, {'maximum_archive_bytes': 8 * 1024 ** 3 + 1}, {'extra': 1}):
            native = InputFakeNative()
            with self.subTest(change=change), self.assertRaises(ValueError): publication.AnchoredInputs._open(native, 'C:/work', limits=input_limits(**change))
            self.assertEqual(native.handles, {})
        native = InputFakeNative()
        with self.assertRaises(ValueError): publication.AnchoredInputs._open(native, 'C:/work', limits=input_limits(), deadline=float('inf'))
        with self.assertRaises(ValueError): publication.AnchoredInputs._open(native, 'C:/work', limits=input_limits(), deadline=-1)
        self.assertEqual(native.handles, {})
        reader, native = inputs(maximum_archive_bytes=3)
        with self.assertRaises(ValueError): reader.open_archive('archive', expected=input_pin())
        self.assertEqual(native.reads, []); reader.close()

    def test_public_input_constructor_and_unissued_tokens_never_initialize_native(self):
        with self.assertRaises(ValueError): publication.InputQualification(True)
        impostor = object.__new__(publication.InputQualification)
        with self.assertRaises(ValueError): impostor.as_dict()
        with self.assertRaises(ValueError): publication.AnchoredInputs()
        for qualifier in ({'qualified': True}, impostor, publication.Qualification(b'{}', publication._TOKEN)):
            with mock.patch.object(publication, '_native_host'), mock.patch.object(publication, '_Native') as native:
                with self.subTest(qualifier=qualifier), self.assertRaises(ValueError):
                    publication.AnchoredInputs.open_existing('C:/work', qualification=qualifier, limits=input_limits())
                native.assert_not_called()

    def test_public_input_native_guard_precedes_native_initialization(self):
        with mock.patch.object(publication.os, 'name', 'posix'), mock.patch.object(publication, '_Native') as native:
            with self.assertRaisesRegex(ValueError, 'Native Windows x64'):
                publication.AnchoredInputs.open_existing('C:/work', qualification=None, limits=input_limits())
        native.assert_not_called()

    def test_original_input_inventory_issues_only_opaque_immutable_token(self):
        with tempfile.TemporaryDirectory() as directory:
            ref, report, sources, run, observed, save = input_evidence(Path(directory))
            qualifier = publication.admit_input_qualification(ref, source_identity=sources, runtime_identity=runtime())
            self.assertIs(type(qualifier), publication.InputQualification)
            result = qualifier.as_dict(); result['filesystem']['volume_serial'] = 99
            self.assertEqual(qualifier.as_dict()['filesystem']['volume_serial'], 7)
            self.assertFalse(hasattr(qualifier, '__dict__'))
            self.assertEqual(set(qualifier.as_dict()['source_identity']), set(publication.INPUT_SOURCE_FILES))

    def test_original_input_inventory_rejects_missing_or_excluded_cases(self):
        for mutation in ('missing', 'excluded', 'publication_scope', 'empty_observation', 'console'):
            with tempfile.TemporaryDirectory() as directory:
                ref, report, sources, run, observed, save = input_evidence(Path(directory))
                if mutation == 'missing': run['inventory'].pop(); report['run_report'] = save('input-cases.json', run)
                elif mutation == 'excluded': run['excluded'][run['inventory'][0]] = 'fixture'; report['run_report'] = save('input-cases.json', run)
                elif mutation == 'publication_scope': report['scope'] = publication.SCOPE
                elif mutation == 'empty_observation':
                    observed['cases'][publication.INPUT_CASE_NAMES[0]]['observed'] = {}
                    report['observations'] = save('input-observations.json', observed)
                else: report['console'] = save('input-console.log', b'not-an-original-marker', True)
                ref = save('input-qualification.json', report)
                with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                    publication.admit_input_qualification(ref, source_identity=sources, runtime_identity=runtime())
        self.assertEqual(publication._INPUT_ISSUED, {})

    def test_input_subject_observes_actual_source_and_runtime_without_issuance(self):
        native = SimpleNamespace(runtime_identity=mock.Mock(return_value=runtime()))
        with mock.patch.object(publication, '_ordinary_bytes', side_effect=lambda path, maximum: str(path).encode()) as source:
            subject = publication._input_subject(native)
        self.assertEqual(set(subject), {'source_identity', 'runtime_identity'})
        self.assertEqual(set(subject['source_identity']), set(publication.INPUT_SOURCE_FILES))
        self.assertEqual(source.call_count, 4); native.runtime_identity.assert_called_once()
        self.assertEqual(publication._INPUT_ISSUED, {})

    def test_public_input_open_rechecks_actual_subject_and_volume(self):
        with tempfile.TemporaryDirectory() as directory:
            ref, report, sources, run, observed, save = input_evidence(Path(directory))
            qualifier = publication.admit_input_qualification(ref, source_identity=sources, runtime_identity=runtime())
            for field in ('source_identity', 'runtime_identity'):
                subject = {'source_identity': sources, 'runtime_identity': runtime()}; subject[field] = {}
                with mock.patch.object(publication, '_native_host'), mock.patch.object(publication, '_Native'), \
                        mock.patch.object(publication, '_input_subject', return_value=subject), mock.patch.object(publication.AnchoredInputs, '_open') as opened:
                    with self.subTest(field=field), self.assertRaises(ValueError):
                        publication.AnchoredInputs.open_existing('C:/work', qualification=qualifier, limits=input_limits())
                    opened.assert_not_called()
            native = InputFakeNative()
            with self.assertRaisesRegex(ValueError, 'volume'):
                publication.AnchoredInputs._open(native, 'C:/work', limits=input_limits(), filesystem={'name': 'NTFS', 'volume_serial': 8})
            self.assertEqual(native.handles, {})

    def test_synthetic_zip_tar_use_borrowed_stream_without_fileno_or_reopen(self):
        import tarfile
        import zipfile
        fixtures = []
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_STORED) as archive: archive.writestr('member', b'body')
        fixtures.append(('zip', stream.getvalue()))
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode='w') as archive:
            info = tarfile.TarInfo('member'); info.size = 4; archive.addfile(info, io.BytesIO(b'body'))
        fixtures.append(('tar', stream.getvalue()))
        for kind, raw in fixtures:
            native = InputFakeNative(); native.add('C:/work/archive', data=raw); reader, _ = inputs(native)
            view = reader.open_archive('archive', expected=input_pin(raw))
            self.assertEqual(hashlib.sha256(view.read()).hexdigest(), input_pin(raw)['sha256']); view.seek(0)
            if kind == 'zip':
                with zipfile.ZipFile(view) as archive: self.assertEqual(archive.read('member'), b'body')
            else:
                with tarfile.open(fileobj=view, mode='r:') as archive: self.assertEqual(archive.extractfile('member').read(), b'body')
            reader.check(); reader.close()

    def test_empty_zip_optional_negative_zip64_probe_uses_filelike_oserror(self):
        import zipfile
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w'): pass
        raw = stream.getvalue(); self.assertEqual(len(raw), 22)
        native = InputFakeNative(); native.add('C:/work/archive', data=raw); reader, _ = inputs(native)
        view = reader.open_archive('archive', expected=input_pin(raw))
        with zipfile.ZipFile(view) as archive: self.assertEqual(archive.namelist(), [])
        reader.check(); reader.close()

    def test_complete_tree_is_structural_and_observations_do_not_fabricate_pins(self):
        native = InputFakeNative(); native.add('C:/work/include', directory=True)
        native.add('C:/work/empty', directory=True); native.add('C:/work/include/a.h', data=b'body')
        reader, _ = inputs(native)
        declared = {'include/a.h': {'sha256': input_pin()['sha256'], 'mode': 0o755}}
        tree = reader.capture_tree('', files=declared, directories=['include', 'empty'])
        self.assertEqual(native.reads, []); self.assertEqual(reader._captured_bytes, 4)
        self.assertEqual(len(native.enumerations), 6)  # Complete preflight and final pass.
        snapshot = tree.as_dict()
        self.assertEqual(set(snapshot), {'root', 'files', 'directories', 'observed'})
        self.assertEqual(snapshot['root'], ''); self.assertEqual(snapshot['files'], declared)
        self.assertNotIn('bytes', snapshot['files']['include/a.h'])
        self.assertEqual(snapshot['observed']['files']['include/a.h']['bytes'], 4)
        self.assertEqual(snapshot['observed']['files']['include/a.h']['attributes'], 128)
        self.assertEqual(set(snapshot['observed']['directories']), {'', 'empty', 'include'})
        snapshot['files']['include/a.h']['mode'] = 0
        self.assertEqual(tree.as_dict()['files'], declared)
        first, second = tree.open_file('include/a.h'), tree.open_file('include/a.h')
        self.assertEqual(first.read(1), b'b'); self.assertEqual(second.read(), b'body')
        self.assertEqual(first.tell(), 1); reader.check(); reader.close()
        self.assertEqual(tree.as_dict()['files'], declared)  # Passive after closure.
        self.assertTrue(first.closed); self.assertEqual(native.handles, {})

    def test_subtree_capture_does_not_include_unselected_siblings(self):
        native = InputFakeNative(); native.add('C:/work/sibling', data=b'unselected')
        native.add('C:/work/source', directory=True); native.add('C:/work/source/a', data=b'body')
        reader, _ = inputs(native)
        tree = reader.capture_tree('source', files={'a': input_pin()}, directories=[])
        self.assertEqual(tree.as_dict()['root'], 'source'); self.assertNotIn('sibling', reader._files)
        self.assertEqual(tree.open_file('a').read(), b'body'); reader.check(); reader.close()

    def test_invalid_tree_manifests_reject_before_new_native_open(self):
        for relative, files, directories in (
                ('.', {}, []), ('..', {}, []), ('', [], []), ('', {}, ()),
                ('', {'a/b': input_pin()}, []), ('', {}, ['a/b']),
                ('', {'a': input_pin()}, ['a']), ('', {'A': input_pin()}, ['a']),
                ('', {}, ['a', 'a']), ('', {'../a': input_pin()}, []),
                ('', {'a': input_pin(mode=True)}, []), ('', {'a': input_pin(mode=0o600)}, [])):
            reader, native = inputs(); before = list(native.opens)
            with self.subTest(relative=relative, files=files, directories=directories), self.assertRaises(ValueError):
                reader.capture_tree(relative, files=files, directories=directories)
            self.assertEqual(native.opens, before); reader.close()

    def test_tree_rejects_missing_extra_case_alias_and_wrong_kind_members(self):
        for failure in ('missing', 'extra', 'alias', 'kind', 'hardlink', 'reparse'):
            native = InputFakeNative()
            if failure != 'missing':
                node = native.add('C:/work/A' if failure == 'alias' else 'C:/work/a',
                    directory=failure == 'kind', data=b'body')
                if failure == 'hardlink': node['links'] = 2
                if failure == 'reparse': node['reparse'] = True
            if failure == 'extra': native.add('C:/work/extra', data=b'new')
            reader, _ = inputs(native)
            with self.subTest(failure=failure), self.assertRaises(ValueError):
                reader.capture_tree('', files={'a': input_pin()}, directories=[])
            self.assertEqual(native.reads, []); self.assertFalse(reader.uncertain)
            reader.close(); self.assertEqual(native.handles, {})

    def test_tree_boundary_check_rejects_late_unselected_or_missing_names(self):
        for failure in ('late', 'missing', 'alias'):
            native = InputFakeNative(); native.add('C:/work/a', data=b'body'); reader, _ = inputs(native)
            reader.capture_tree('', files={'a': input_pin()}, directories=[])
            if failure == 'late': native.add('C:/work/late.h', data=b'new include')
            elif failure == 'missing': del native.nodes['c:/work/a']
            else: native.nodes['c:/work/a']['path'] = 'C:/work/A'
            with self.subTest(failure=failure), self.assertRaises(ValueError): reader.check()
            self.assertEqual(native.reads, [])
            if failure == 'alias': self.assertTrue(reader.uncertain)
            else: reader.close(); self.assertEqual(native.handles, {})

    def test_tree_second_enumeration_catches_change_during_capture(self):
        native = InputFakeNative(); native.add('C:/work/a', data=b'body'); reader, _ = inputs(native)
        def mutate(node, names):
            if node['path'] == 'C:/work' and len(native.enumerations) == 1:
                native.add('C:/work/late', data=b'late')
        native.after_names = mutate
        with self.assertRaisesRegex(ValueError, 'membership'):
            reader.capture_tree('', files={'a': input_pin()}, directories=[])
        self.assertFalse(reader._trees[0]._complete); self.assertEqual(native.reads, [])
        reader.close(); self.assertEqual(native.handles, {})

    def test_tree_joins_metadata_or_archive_in_either_order_without_second_charge(self):
        for role in ('metadata', 'archive'):
            for first in ('tree', 'direct'):
                for declared_bytes in (False, True):
                    native = InputFakeNative(); native.add('C:/work/a', data=b'body'); reader, _ = inputs(native)
                    tree_pin = input_pin()
                    if not declared_bytes: tree_pin.pop('bytes')
                    direct_pin = input_pin()
                    if role == 'metadata': direct_pin.pop('bytes')
                    def direct():
                        if role == 'archive': return reader.open_archive('a', expected=direct_pin)
                        return reader.read('a', expected=direct_pin, maximum=8)
                    with self.subTest(role=role, first=first, declared_bytes=declared_bytes):
                        if first == 'direct': direct()
                        tree = reader.capture_tree('', files={'a': tree_pin}, directories=[])
                        direct()
                        self.assertEqual(reader._captured_bytes, 4); self.assertEqual(len(reader._files), 1)
                        self.assertEqual(len(reader._charged), 1); self.assertEqual(reader._files['a']['role'], role)
                        self.assertEqual(tree.as_dict()['files']['a'], tree_pin)
                        # No tree hash and no archive hash; metadata hashes once.
                        self.assertEqual(len(native.reads), 0 if role == 'archive' else 1)
                        reader.check(); reader.close()

    def test_tree_join_preserves_direct_role_restriction_and_conflicting_pins(self):
        for failure in ('hash', 'mode', 'size', 'direct_role'):
            native = InputFakeNative(); native.add('C:/work/a', data=b'body'); reader, _ = inputs(native)
            reader.read('a', expected=input_pin(), maximum=8)
            row = input_pin(**({'sha256': '2' * 64} if failure == 'hash' else
                {'mode': 0o755} if failure == 'mode' else {'bytes': 5} if failure == 'size' else {}))
            if failure == 'direct_role': reader.capture_tree('', files={'a': row}, directories=[])
            with self.subTest(failure=failure), self.assertRaises(ValueError):
                if failure == 'direct_role': reader.open_archive('a', expected=input_pin())
                else: reader.capture_tree('', files={'a': row}, directories=[])
            reader.close(); self.assertFalse(native.handles)

    def test_tree_declared_size_and_aggregate_limits_precede_body_read(self):
        for change, manifest in (({'maximum_members': 1}, {'a': input_pin(), 'b': input_pin()}),
                ({'maximum_expanded_bytes': 3}, {'a': {'sha256': input_pin()['sha256'], 'mode': 0o644}}),
                ({}, {'a': input_pin(bytes=5)})):
            native = InputFakeNative(); native.add('C:/work/a', data=b'body'); reader, _ = inputs(native, **change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                reader.capture_tree('', files=manifest, directories=[])
            self.assertEqual(native.reads, []); reader.close()

    def test_tree_physical_archive_eof_is_not_an_expanded_member_limit(self):
        for first in ('tree', 'archive'):
            native = InputFakeNative(); native.add('C:/work/archive', data=b'body')
            reader, _ = inputs(native, maximum_member_bytes=3, maximum_archive_bytes=4)
            if first == 'archive': reader.open_archive('archive', expected=input_pin())
            tree = reader.capture_tree('', files={'archive': {'sha256': input_pin()['sha256'], 'mode': 0o644}}, directories=[])
            view = reader.open_archive('archive', expected=input_pin())
            with self.subTest(first=first):
                self.assertEqual(native.reads, []); self.assertEqual(reader._captured_bytes, 4)
                self.assertEqual(tree.as_dict()['observed']['files']['archive']['bytes'], 4)
                self.assertEqual(view.read(), b'body'); reader.check(); reader.close()

    def test_tree_check_observes_physical_drift_and_retains_uncertain_owner(self):
        for failure in ('file', 'directory', 'volume', 'unknown'):
            native = InputFakeNative(); native.add('C:/work/d', directory=True)
            native.add('C:/work/d/a', data=b'body'); reader, _ = inputs(native)
            reader.capture_tree('', files={'d/a': input_pin()}, directories=['d'])
            if failure == 'file': native.nodes['c:/work/d/a']['identity'][1] = 'f' * 32
            elif failure == 'directory': native.nodes['c:/work/d']['identity'][1] = 'f' * 32
            elif failure == 'volume': native.nodes['c:/work/d/a']['identity'][0] = 8
            else: native.after_names = lambda *unused: (_ for _ in ()).throw(publication.OwnershipUncertain('unknown native query'))
            with self.subTest(failure=failure), self.assertRaises(publication.OwnershipUncertain): reader.check()
            self.assertTrue(reader.uncertain); self.assertTrue(native.handles)
            with self.assertRaises(publication.OwnershipUncertain): reader.close()

    def test_tree_repeated_capture_is_same_borrow_and_cannot_change_manifest(self):
        native = InputFakeNative(); native.add('C:/work/a', data=b'body'); reader, _ = inputs(native)
        tree = reader.capture_tree('', files={'a': input_pin()}, directories=[])
        before = list(native.opens)
        self.assertIs(reader.capture_tree('', files={'a': input_pin()}, directories=[]), tree)
        self.assertEqual(native.opens, before); self.assertEqual(reader._captured_bytes, 4)
        with self.assertRaisesRegex(ValueError, 'different manifest'):
            reader.capture_tree('', files={'a': {'sha256': input_pin()['sha256'], 'mode': 0o644}}, directories=[])
        reader.close()

    def test_direct_leaves_and_disjoint_tree_share_one_aggregate_member_bound(self):
        for first in ('direct', 'tree'):
            native = InputFakeNative(); native.add('C:/work/a', data=b'body')
            native.add('C:/work/empty', directory=True)
            reader, _ = inputs(native, maximum_members=1)
            if first == 'direct': reader.read('a', expected=input_pin(), maximum=8)
            else: reader.capture_tree('empty', files={}, directories=[])
            before = list(native.opens)
            with self.subTest(first=first), self.assertRaisesRegex(ValueError, 'aggregate'):
                if first == 'direct': reader.capture_tree('empty', files={}, directories=[])
                else: reader.read('a', expected=input_pin(), maximum=8)
            self.assertEqual(native.opens, before); reader.close(); self.assertFalse(native.handles)

    def test_tree_boundary_lifetime_does_not_reset_after_body_work(self):
        now = [0.0]; native = InputFakeNative(); native.add('C:/work/a', data=b'body')
        with mock.patch.object(publication.time, 'monotonic', side_effect=lambda: now[0]):
            reader = publication.AnchoredInputs._open(native, 'C:/work', limits=input_limits(seconds=20), deadline=15.0)
            tree = reader.capture_tree('', files={'a': input_pin()}, directories=[])
            now[0] = 2.0; self.assertEqual(tree.open_file('a').read(), b'body')
            reads = list(native.reads); opens = list(native.opens)
            now[0] = 12.0; reader.check()  # Caller may have ended its shorter work budget.
            self.assertEqual(reader._deadline, 15.0); self.assertEqual(native.reads, reads)
            self.assertEqual(native.opens, opens)
            self.assertTrue(all(deadline == 15.0 for _, deadline, _ in native.enumerations))
            now[0] = 15.0
            with self.assertRaisesRegex(ValueError, 'deadline'): reader.check()
            reader.close(); self.assertFalse(native.handles)

    def test_native_enumerator_obeys_explicit_bounds_deadline_and_complete_pages(self):
        native = publication._Native.__new__(publication._Native)
        raw = struct.pack('<III', 0, 0, 2) + b'a\0'; calls = []
        def page(handle, event, apc, context, status, buffer, size, kind, single, name, restart):
            calls.append(restart)
            if len(calls) > 1: return ctypes.c_int32(0x80000006).value
            ctypes.memmove(buffer, raw, len(raw))
            ctypes.cast(status, ctypes.POINTER(publication.IO_STATUS_BLOCK)).contents.Information = len(raw)
            return 0
        native.n = SimpleNamespace(NtQueryDirectoryFile=page)
        with mock.patch.object(publication.time, 'monotonic', return_value=1.0):
            self.assertEqual(native.names(9, deadline=2.0, maximum_entries=1), ['a'])
        self.assertEqual(calls, [1, 0])
        for kwargs in ({'deadline': True}, {'deadline': float('inf')}, {'maximum_entries': True}, {'maximum_entries': 0}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError): native.names(9, **kwargs)
        calls.clear()
        with mock.patch.object(publication.time, 'monotonic', return_value=2.0), self.assertRaisesRegex(ValueError, 'deadline'):
            native.names(9, deadline=2.0, maximum_entries=1)
        self.assertEqual(calls, [])
        calls.clear()
        with mock.patch.object(publication.time, 'monotonic', side_effect=[0.0, 0.0, 2.0]), self.assertRaisesRegex(ValueError, 'deadline'):
            native.names(9, deadline=2.0, maximum_entries=1)
        self.assertEqual(calls, [1, 0])

    def test_native_enumerator_rejects_entry_overflow_without_truncated_success(self):
        native = publication._Native.__new__(publication._Native)
        raw = struct.pack('<III', 16, 0, 2) + b'a\0\0\0' + struct.pack('<III', 0, 0, 2) + b'b\0'
        def page(handle, event, apc, context, status, buffer, *unused):
            ctypes.memmove(buffer, raw, len(raw))
            ctypes.cast(status, ctypes.POINTER(publication.IO_STATUS_BLOCK)).contents.Information = len(raw)
            return 0
        native.n = SimpleNamespace(NtQueryDirectoryFile=page)
        with self.assertRaisesRegex(ValueError, 'entry bound'): native.names(9, maximum_entries=1)



if __name__ == '__main__': unittest.main()
