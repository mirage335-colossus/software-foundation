#!/usr/bin/env python3
"""Inert source/fake-I/O checks only. Never launches a child or reads /proc."""
import importlib.util
import io
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SPEC = importlib.util.spec_from_file_location('process_owner_observation_fixture', ROOT / 'tools/process_tree.py')
p = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(p)


def encoded(value):
    return (json.dumps(value, sort_keys=True) + '\n').encode()


def final(**changes):
    value = dict(schema_version=1, primary_returncode=0, descendants_outlived=False,
                 terminated=False, error=None, reaped=1)
    value.update(changes)
    return value


def startup():
    return dict(kind='supervisor-startup', schema_version=1, facts=dict(
        pid=100, parent_pid=10, executable='/runtime/python', executable_realpath='/runtime/python-real',
        version_info=[3, 9, 25], implementation='cpython', prefix='/base', base_prefix='/base',
        exec_prefix='/base', base_exec_prefix='/base', sys_path=['', 'relative', '/missing'],
        platlibdir='lib', flags=[[name, 1] for name in p._STARTUP_FLAGS],
        helper_path='/helper.py', dont_write_bytecode=True))


def sample(request_id=1, records=None, **changes):
    value = dict(kind='process-sample', schema_version=1, request_id=request_id,
                 records=[[200, 2000, 100, 1000]] if records is None else records,
                 complete=False, unknown_coverage=True, error=None)
    value.update(changes)
    return value


class FakeSupervisor:
    def __init__(self, returncode=None):
        self.pid = 100
        self.returncode = returncode
        self.wait_calls = []

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        self.wait_calls.append(timeout)
        return self.returncode


class FakePipe:
    def __init__(self, chunks=(), *, eof=False):
        self.chunks = list(chunks)
        self.eof = eof
        self.writes, self.closed = [], []
        self.on_write = None

    def read(self, fd, count):
        if fd != 1:
            raise AssertionError('unexpected fake read fd')
        if self.chunks:
            chunk = self.chunks.pop(0)
            if isinstance(chunk, BaseException):
                raise chunk
            if len(chunk) > count:
                self.chunks.insert(0, chunk[count:])
                chunk = chunk[:count]
            return chunk
        if self.eof:
            return b''
        raise BlockingIOError()

    def write(self, fd, raw):
        self.writes.append((fd, raw))
        if self.on_write:
            return self.on_write(fd, raw)
        return len(raw)

    def patches(self):
        return mock.patch.multiple(p.os, read=self.read, write=self.write,
                                   close=self.closed.append, set_blocking=lambda *_: None,
                                   create=True)


def owner(supervisor=None, *, isolated=False):
    return p._LinuxProcess(supervisor or FakeSupervisor(), 1, ['inert-target'], 2,
        startup_deadline=20 if isolated else None, expected_parent=10, expected_helper='/helper.py')


class Observations(unittest.TestCase):
    def setUp(self):
        self.clock = mock.patch.object(p.time, 'monotonic', return_value=10.)
        self.clock.start()
        self.addCleanup(self.clock.stop)

    def test_pipe_fixture_supplies_api_absent_on_other_hosts(self):
        with mock.patch.dict(p.os.__dict__):
            p.os.__dict__.pop('set_blocking', None)
            with FakePipe().patches():
                p.os.set_blocking(1, False)
            self.assertFalse(hasattr(p.os, 'set_blocking'))

    def test_strict_limits_and_deadlines(self):
        for value in (True, False, 0, -1, 1025, 1.0, None):
            with self.subTest(value=value), self.assertRaises(p.ProcessTreeError):
                p._sample_limit(value)
        for value in (True, float('inf'), float('nan'), 10, '20', 10 ** 1000):
            with self.subTest(value=str(value)[:30]), self.assertRaises(p.ProcessTreeError):
                p._deadline(value)
        self.assertEqual(p._sample_limit(1024), 1024)

    def test_startup_record_raw_paths_nested_immutable(self):
        pipe, process = FakePipe([encoded(startup())]), owner(isolated=True)
        with pipe.patches():
            observed = process.observe_supervisor_startup(deadline=19)
        self.assertIsInstance(observed, p.SupervisorStartup)
        self.assertEqual(observed.version_info, (3, 9, 25))
        self.assertEqual(observed.sys_path, ('', 'relative', '/missing'))
        self.assertEqual(observed.flags, tuple((n, 1) for n in p._STARTUP_FLAGS))
        self.assertIs(observed.dont_write_bytecode, True)
        with self.assertRaises(AttributeError):
            observed.pid = 101

    def test_startup_rejects_independent_bytecode_bool_and_flag_type(self):
        for field in ('dont_write_bytecode', 'flag', 'parent', 'helper', 'version'):
            frame = startup()
            if field == 'dont_write_bytecode':
                frame['facts']['dont_write_bytecode'] = 1
            elif field == 'flag':
                frame['facts']['flags'][0][1] = True
            elif field == 'parent':
                frame['facts']['parent_pid'] = 11
            elif field == 'helper':
                frame['facts']['helper_path'] = '/foreign.py'
            else:
                frame['facts']['version_info'][0] = True
            with self.subTest(field=field):
                pipe, process = FakePipe([encoded(frame)]), owner(isolated=True)
                with pipe.patches(), self.assertRaises(p.ProcessTreeError):
                    process.observe_supervisor_startup(deadline=19)

    def test_go_exact_object_once_and_failure_consumes_eligibility(self):
        for fail in (False, True):
            pipe, process = FakePipe([encoded(startup())]), owner(isolated=True)
            with pipe.patches():
                observed = process.observe_supervisor_startup(deadline=19)
                with self.assertRaises(p.ProcessTreeError):
                    process.release_supervisor_startup(observed._replace())
                if fail:
                    pipe.on_write = lambda *_: (_ for _ in ()).throw(BrokenPipeError())
                    with self.assertRaises(p.ProcessTreeError):
                        process.release_supervisor_startup(observed)
                else:
                    process.release_supervisor_startup(observed)
                with self.assertRaises(p.ProcessTreeError):
                    process.release_supervisor_startup(observed)
            self.assertEqual(pipe.writes, [(2, b'G')])

    def test_go_revoked_expired_and_sampling_before_go_never_write(self):
        pipe, process = FakePipe([encoded(startup())]), owner(isolated=True)
        with pipe.patches():
            observed = process.observe_supervisor_startup(deadline=19)
            with self.assertRaises(p.ProcessTreeError):
                process.sample_processes(maximum_processes=3, deadline=19)
            with mock.patch.object(p.time, 'monotonic', return_value=21), self.assertRaises(p.ProcessTreeError):
                process.release_supervisor_startup(observed)
            process._revoked = True
            with self.assertRaises(p.ProcessTreeError):
                process.release_supervisor_startup(observed)
        self.assertFalse(pipe.writes)

    def test_joined_clean_pre_go_cancellation_can_report_actual_empty(self):
        process = owner(FakeSupervisor(0), isolated=True)
        process._revoked = True
        pipe = FakePipe([encoded(startup()) + encoded(final(primary_returncode=-15, terminated=True))], eof=True)
        with pipe.patches():
            tree = p.ProcessTree(process)
            self.assertEqual(tree.sample_processes(maximum_processes=1, deadline=19),
                             p.ObservedProcessSample((), True, False))
        self.assertFalse(process._released)
        self.assertEqual(process.returncode, -15)
        self.assertFalse(pipe.writes)

    def test_sample_request_effective_deadline_and_live_coverage(self):
        pipe, process = FakePipe(), owner()
        def respond(_fd, raw):
            request = json.loads(raw[1:])
            self.assertEqual(request['deadline'], 15)
            self.assertEqual(request['maximum_processes'], 3)
            pipe.chunks.append(encoded(sample()))
            return len(raw)
        pipe.on_write = respond
        with pipe.patches():
            result = process.sample_processes(maximum_processes=3, deadline=90)
        self.assertEqual(result, p.ObservedProcessSample(((200, 2000, 100, 1000),), False, True))

    def test_final_arrives_instead_of_requested_sample(self):
        pipe, process = FakePipe(), owner()
        def finish(_fd, raw):
            pipe.chunks.append(encoded(final(primary_returncode=4)))
            pipe.eof = True
            process.supervisor.returncode = 0
            return len(raw)
        pipe.on_write = finish
        with pipe.patches():
            result = process.sample_processes(maximum_processes=3, deadline=19)
        self.assertEqual(result, p.ObservedProcessSample((), True, False))
        self.assertEqual(process.returncode, 4)

    def test_sample_error_does_not_replace_authoritative_final_receipt(self):
        pipe, process = FakePipe(), owner()
        def fail(_fd, raw):
            pipe.chunks.append(encoded(sample(records=[], error='inaccessible identity')))
            return len(raw)
        pipe.on_write = fail
        with pipe.patches(), self.assertRaisesRegex(p.ProcessTreeError, 'inaccessible'):
            process.sample_processes(maximum_processes=3, deadline=19)
        self.assertIsNone(process.failure)
        pipe.chunks.append(encoded(final()))
        pipe.eof = True
        process.supervisor.returncode = 0
        with pipe.patches():
            self.assertEqual(process.wait(timeout=1), 0)
            self.assertTrue(process.sample_processes(maximum_processes=3, deadline=19).complete)

    def test_every_frame_byte_boundary(self):
        raw = encoded(sample())
        for split in range(1, len(raw)):
            process = owner()
            process._protocol = True
            process._pending = (1, 2)
            pipe = FakePipe([raw[:split], BlockingIOError(), raw[split:]])
            with pipe.patches():
                process._drain()
                self.assertNotIn(1, process._responses)
                process._drain()
                self.assertIn(1, process._responses)

    def test_sample_and_final_coalesced_and_current_closure_after_nonzero_or_termination(self):
        for changes in ({}, {'primary_returncode': 7}, {'terminated': True}, {'descendants_outlived': True}):
            process = owner(FakeSupervisor(0))
            process._protocol = True
            process._pending = (1, 3)
            pipe = FakePipe([encoded(sample()) + encoded(final(**changes))], eof=True)
            with pipe.patches():
                process.wait(timeout=1)
                process.report['error'] = 'caller mutation'
                self.assertEqual(process._completed_sample(), p.ObservedProcessSample((), True, False))
            self.assertEqual(pipe.closed, [1, 2])

    def test_finish_keeps_outlived_failure_after_complete_sample(self):
        process = owner(FakeSupervisor(0))
        process._protocol = True
        pipe = FakePipe([encoded(final(descendants_outlived=True))], eof=True)
        with pipe.patches():
            process.wait(timeout=1)
            tree = p.ProcessTree(process)
            self.assertTrue(tree.sample_processes(maximum_processes=1, deadline=19).complete)
            with self.assertRaisesRegex(p.ProcessTreeError, 'outlived'):
                tree.finish()

    def test_public_report_cannot_mint_completed_sample(self):
        process = owner()
        process.report = final()
        with self.assertRaises(p.ProcessTreeError):
            process._completed_sample()

    def test_legacy_wait_cannot_mint_weak_or_no_eof_sample_proof(self):
        cases = [(encoded(final(schema_version=True)), [], True),
                 (encoded(final())[:-1], [], True),
                 (encoded(final()), [b'trailing'], True),
                 (encoded(final()), [], False)]
        for raw, trailing, eof in cases:
            with self.subTest(raw=raw, trailing=trailing, eof=eof):
                process = owner(FakeSupervisor(0))
                pipe = FakePipe([raw] + trailing, eof=eof)
                with pipe.patches():
                    self.assertEqual(process.wait(timeout=1), 0)  # Legacy compatibility.
                    with self.assertRaises(p.ProcessTreeError):
                        process.sample_processes(maximum_processes=1, deadline=19)
                self.assertIsNone(process._validated_final)
        process = owner(FakeSupervisor(0))
        with FakePipe([encoded(final())], eof=True).patches():
            self.assertEqual(process.wait(timeout=1), 0)
            self.assertTrue(process.sample_processes(maximum_processes=1, deadline=19).complete)

    def test_legacy_final_proof_uses_original_bytes_not_public_alias(self):
        process = owner(FakeSupervisor(0))
        pipe = FakePipe([encoded(final(error='original cleanup uncertainty'))], eof=True)
        original_read = pipe.read
        def mutate_during_probe(fd, count):
            if count == 1:
                process.report['error'] = None
            return original_read(fd, count)
        with pipe.patches(), mock.patch.object(p.os, 'read', side_effect=mutate_during_probe):
            self.assertEqual(process.wait(timeout=1), 0)
            with self.assertRaisesRegex(p.ProcessTreeError, 'cleanup remained uncertain'):
                process.sample_processes(maximum_processes=1, deadline=19)

    def test_wait_post_collect_timeout_keeps_final_for_later_cleanup(self):
        for protocol in (False, True):
            clock = [10.]
            process = owner(FakeSupervisor(0))
            process._protocol = protocol
            pipe = FakePipe([encoded(final())], eof=True)
            original_read = pipe.read
            def late(fd, count):
                raw = original_read(fd, count)
                clock[0] = 12.
                return raw
            with pipe.patches(), mock.patch.object(p.os, 'read', side_effect=late), \
                 mock.patch.object(p.time, 'monotonic', side_effect=lambda: clock[0]):
                with self.assertRaises(p.subprocess.TimeoutExpired):
                    process.wait(timeout=1)
                self.assertIsNotNone(process._validated_final)
                self.assertEqual(process.wait(timeout=1), 0)

    def test_wait_lock_uses_entry_deadline_and_poll_is_nonblocking(self):
        clock = [10.]
        process = owner()
        attempts, releases = [], []
        class BusyReader:
            def acquire(self, **kwargs):
                attempts.append(kwargs)
                if kwargs.get('blocking') is False:
                    return False
                clock[0] = 12.
                return True
            def release(self):
                releases.append(True)
        process._lock = BusyReader()
        with mock.patch.object(p.time, 'monotonic', side_effect=lambda: clock[0]):
            self.assertIsNone(process.poll())
            with self.assertRaises(p.subprocess.TimeoutExpired):
                process.wait(timeout=1)
        self.assertEqual(attempts, [{'blocking': False}, {'timeout': 1.}])
        self.assertEqual(releases, [True])
        self.assertFalse(process.supervisor.wait_calls)

    def test_post_drain_deadline_before_publication(self):
        clock = [10.]
        process = owner(isolated=True)
        pipe = FakePipe([encoded(startup())])
        original_read = pipe.read
        def late_startup(fd, count):
            raw = original_read(fd, count)
            clock[0] = 21.
            return raw
        with pipe.patches(), mock.patch.object(p.os, 'read', side_effect=late_startup), \
             mock.patch.object(p.time, 'monotonic', side_effect=lambda: clock[0]):
            with self.assertRaises(p.ProcessTreeError):
                process.observe_supervisor_startup(deadline=19)
        self.assertIsNotNone(process._startup)  # Actual parsed frame retained.
        clock[0] = 10.
        process, pipe = owner(), FakePipe()
        def send(_fd, raw):
            pipe.chunks.append(encoded(sample()))
            return len(raw)
        pipe.on_write = send
        original_read = pipe.read
        def late_sample(fd, count):
            raw = original_read(fd, count)
            clock[0] = 16.
            return raw
        with pipe.patches(), mock.patch.object(p.os, 'read', side_effect=late_sample), \
             mock.patch.object(p.time, 'monotonic', side_effect=lambda: clock[0]):
            with self.assertRaises(p.ProcessTreeError):
                process.sample_processes(maximum_processes=2, deadline=90)
        self.assertIsNone(process._validated_final)

    def test_invalid_final_and_trailing_data_never_complete(self):
        for raw in (encoded(final(error='unknown')), encoded(final()) + encoded(sample()),
                    encoded(final()) + encoded(final()), encoded(final()) + b'junk',
                    encoded(final())[:-1], encoded(final(schema_version=True))):
            process = owner(FakeSupervisor(0))
            process._protocol = True
            pipe = FakePipe([raw], eof=True)
            with pipe.patches():
                try:
                    process.wait(timeout=1)
                except p.ProcessTreeError:
                    pass
                with self.assertRaises(p.ProcessTreeError):
                    process._completed_sample()

    def test_all_prefix_truncations_of_final_are_uncertain(self):
        raw = encoded(final())
        for end in range(len(raw)):
            process = owner(FakeSupervisor(0))
            process._protocol = True
            with FakePipe([raw[:end]], eof=True).patches(), self.assertRaises(p.ProcessTreeError):
                process.wait(timeout=1)

    def test_late_sample_after_timeout_is_drained_before_final(self):
        process = owner()
        pipe = FakePipe()
        with pipe.patches(), mock.patch.object(p, '_remaining', side_effect=p.ProcessTreeError('fake timeout')):
            with self.assertRaises(p.ProcessTreeError):
                process.sample_processes(maximum_processes=2, deadline=19)
        # A real request was not sent in this forced entry-time timeout. Model
        # an already outstanding request and a reply split across later reads.
        process._protocol = True
        process._pending = (1, 2)
        process._sample_failure = 'sample deadline exhausted'
        raw = encoded(sample())
        pipe.chunks = [raw[:30], BlockingIOError()]
        with pipe.patches():
            process._drain()
        pipe.chunks = [raw[30:] + encoded(final())]
        pipe.eof = True
        process.supervisor.returncode = 0
        with pipe.patches():
            self.assertEqual(process.wait(timeout=1), 0)
            self.assertTrue(process.sample_processes(maximum_processes=2, deadline=19).complete)

    def test_wait_drains_large_sample_while_supervisor_is_live(self):
        records = [[1000 + n, 3000 + n, 100, 1000] for n in range(1024)]
        process = owner()
        process._protocol = True
        process._pending = (1, 1024)
        raw = encoded(sample(records=records))
        pipe = FakePipe([raw])
        original_read = pipe.read
        appended = [False]
        def read(fd, count):
            result = original_read(fd, count)
            if not pipe.chunks and not appended[0]:
                appended[0] = True
                pipe.chunks.append(encoded(final()))
                pipe.eof = True
                process.supervisor.returncode = 0
                pipe.read = original_read
            return result
        # The supervisor fake can only exit once its observation is drained.
        with pipe.patches(), mock.patch.object(p.os, 'read', side_effect=read):
            self.assertEqual(process.wait(timeout=1), 0)
        self.assertFalse(process.supervisor.wait_calls)

    def test_oversize_frame_not_resynchronized(self):
        process = owner(FakeSupervisor(0))
        process._protocol = True
        pipe = FakePipe([b'x' * (p._SAMPLE_BYTES + 1) + encoded(final())], eof=True)
        with pipe.patches(), self.assertRaises(p.ProcessTreeError):
            process.wait(timeout=1)
        self.assertIsNone(process._validated_final)

    def test_cancel_can_write_while_reader_lock_is_held(self):
        process, pipe = owner(), FakePipe()
        class CannotAcquire:
            def __enter__(self):
                raise AssertionError('termination waited behind sample lock')
        process._lock = CannotAcquire()
        with pipe.patches():
            process.terminate()
        self.assertEqual(pipe.writes, [(2, b'T')])

    def test_closed_or_nonlinux_owner_rejects_without_io(self):
        tree = p.ProcessTree(owner())
        tree.closed = True
        with self.assertRaises(p.ProcessTreeError):
            tree.sample_processes(maximum_processes=1, deadline=19)
        with self.assertRaises(p.ProcessTreeError):
            p.ProcessTree(object()).observe_supervisor_startup(deadline=19)

    def test_close_between_outer_check_and_observation_never_returns_record(self):
        tree = p.ProcessTree(owner(FakeSupervisor(0)))
        # Capture the same process returned after the outer open-owner check,
        # then close the actual owner before its serialized method enters.
        process = tree._linux_observer()
        pipe = FakePipe([encoded(final())], eof=True)
        with pipe.patches():
            tree.close()
            self.assertTrue(tree.closed)
            with self.assertRaisesRegex(p.ProcessTreeError, 'already closed'):
                process.sample_processes(maximum_processes=1, deadline=19)

    def test_actual_linux_owner_cannot_be_rebound_to_another_tree(self):
        tree = p.ProcessTree(owner(FakeSupervisor(0)))
        with self.assertRaisesRegex(p.ProcessTreeError, 'already belongs'):
            p.ProcessTree(tree.process)
        self.assertIs(tree.process._owner_tree, tree)
        with FakePipe([encoded(final())], eof=True).patches():
            tree.close()
            with self.assertRaisesRegex(p.ProcessTreeError, 'already closed'):
                tree.process.sample_processes(maximum_processes=1, deadline=19)


def proc_stat(pid, parent, start):
    fields = [b'S', str(parent).encode()] + [b'0'] * 17 + [str(start).encode()]
    return str(pid).encode() + b' (fixture ) name) ' + b' '.join(fields) + b'\n'


class FakeProc:
    def __init__(self):
        self.data, self.task_ids, self.reads = {}, {}, []
        for pid, parent, start, tids in ((10, 1, 100, (10,)), (100, 10, 1000, (100,)),
                                         (200, 100, 2000, (200, 201)), (300, 200, 3000, (300,))):
            self.task_ids['/proc/%d/task' % pid] = tids
            for tid in tids:
                base = '/proc/%d' % pid if tid == pid else '/proc/%d/task/%d' % (pid, tid)
                self.data[base + '/stat'] = proc_stat(tid, parent, start + (tid != pid))
                self.data[base + '/status'] = ('Pid:\t%d\nTgid:\t%d\nPPid:\t%d\n' % (tid, pid, parent)).encode()
                self.data['/proc/%d/task/%d/children' % (pid, tid)] = b''
        self.data['/proc/100/task/100/children'] = b'200\n'
        self.data['/proc/200/task/201/children'] = b'300\n'

    def open(self, path, mode, *, buffering):
        if buffering != 0:
            raise AssertionError('proc fixture must use unbuffered FileIO')
        self.assert_read(path, mode)
        return io.BytesIO(self.data[path])

    def assert_read(self, path, mode):
        if mode != 'rb' or not path.startswith('/proc/'):
            raise AssertionError('unexpected fake metadata access')
        self.reads.append(path)

    def scandir(self, path):
        class Entries:
            def __enter__(inner):
                return iter(SimpleNamespace(name=str(tid)) for tid in self.task_ids[path])
            def __exit__(inner, *_):
                pass
        return Entries()

    def patches(self):
        return mock.patch.multiple(p, open=self.open, create=True)


class ProcMetadata(unittest.TestCase):
    def setUp(self):
        self.fs = FakeProc()
        self.observation = p._ProcObservation(3, 100, lambda: False)
        self.patches = [mock.patch.object(p.time, 'monotonic', return_value=10),
                        mock.patch.object(p, 'open', self.fs.open, create=True),
                        mock.patch.object(p.os, 'scandir', self.fs.scandir)]
        for patch in self.patches:
            patch.start()
            self.addCleanup(patch.stop)

    def test_nonleader_children_and_detached_adoptee(self):
        records = self.observation.sample(100, 10)
        self.assertEqual(records, ((200, 2000, 100, 1000), (300, 3000, 200, 2000)))
        self.assertIn('/proc/200/task/201/children', self.fs.reads)
        self.fs.data['/proc/100/task/100/children'] = b'200 300'
        self.fs.data['/proc/200/task/201/children'] = b''
        self.fs.data['/proc/300/stat'] = proc_stat(300, 100, 3000)
        self.fs.data['/proc/300/status'] = b'Pid: 300\nTgid: 300\nPPid: 100\n'
        self.assertEqual(self.observation.sample(100, 10)[1], (300, 3000, 100, 1000))

    def test_live_empty_is_only_unknown_coverage_at_interface(self):
        self.fs.data['/proc/100/task/100/children'] = b''
        self.assertEqual(self.observation.sample(100, 10), ())
        process = owner()
        process._pending = (1, 1)
        process._accept_sample(sample(records=[]))
        self.assertEqual(process._responses[1][0], p.ObservedProcessSample((), False, True))

    def test_inaccessible_or_missing_task_never_empty(self):
        del self.fs.task_ids['/proc/200/task']
        with self.assertRaises(KeyError):
            self.observation.sample(100, 10)

    def test_metadata_race_and_parent_mismatch(self):
        self.fs.data['/proc/300/status'] = b'Pid: 300\nTgid: 300\nPPid: 100\n'
        with self.assertRaises(p.ProcessTreeError):
            self.observation.sample(100, 10)

    def test_pid_reuse_between_stat_reads(self):
        original = self.fs.open
        seen = [False]
        def reused(path, mode, *, buffering):
            stream = original(path, mode, buffering=buffering)
            if path == '/proc/200/stat' and not seen[0]:
                seen[0] = True
                self.fs.data[path] = proc_stat(200, 100, 9999)
            return stream
        with mock.patch.object(p, 'open', reused), self.assertRaises(p.ProcessTreeError):
            self.observation.sample(100, 10)

    def test_pid_reuse_after_normalization_before_enqueue(self):
        original = self.observation.normalize
        changed = [False]
        def reused(child):
            result = original(child)
            if child == 200 and not changed[0]:
                changed[0] = True
                self.fs.data['/proc/200/stat'] = proc_stat(200, 100, 9999)
            return result
        with mock.patch.object(self.observation, 'normalize', side_effect=reused), self.assertRaises(p.ProcessTreeError):
            self.observation.sample(100, 10)

    def test_threshold_task_and_byte_budgets(self):
        self.observation.maximum = 1
        with self.assertRaisesRegex(p.ProcessTreeError, 'threshold'):
            self.observation.sample(100, 10)
        self.observation.maximum = 3
        with mock.patch.object(p, '_TASK_ENTRIES', 1), self.assertRaisesRegex(p.ProcessTreeError, 'task budget'):
            self.observation.sample(100, 10)
        self.fs.data['/proc/100/stat'] = b'x' * (p._PROC_BYTES + 1)
        with self.assertRaisesRegex(p.ProcessTreeError, 'byte boundary'):
            self.observation.read('/proc/100/stat')
        self.observation.bytes = p._SAMPLE_TOTAL_BYTES
        with self.assertRaisesRegex(p.ProcessTreeError, 'budget'):
            self.observation.read('/proc/100/stat')

    def test_per_read_boundary_never_probes_beyond_64k(self):
        requests = []
        class Counted(io.BytesIO):
            def read(inner, count):
                requests.append(count)
                return super().read(count)
        for size, succeeds in ((p._PROC_BYTES - 1, True), (p._PROC_BYTES, False), (p._PROC_BYTES + 1, False)):
            self.observation.bytes = 0
            with mock.patch.object(p, 'open', side_effect=lambda *_, **kw: Counted(b'x' * size)):
                if succeeds:
                    self.assertEqual(len(self.observation.read('/proc/fixture')), size)
                else:
                    with self.assertRaises(p.ProcessTreeError):
                        self.observation.read('/proc/fixture')
            self.assertLessEqual(self.observation.bytes, p._PROC_BYTES)
        self.assertEqual(requests, [p._PROC_BYTES, 1, p._PROC_BYTES, p._PROC_BYTES])

    def test_unbuffered_short_reads_continue_until_actual_zero(self):
        requests, observed_buffering = [], []
        class Short(io.BytesIO):
            def read(inner, count):
                requests.append(count)
                return super().read(min(2, count))
        def open_short(_path, _mode, *, buffering):
            observed_buffering.append(buffering)
            return Short(b'abcdefg')
        with mock.patch.object(p, 'open', side_effect=open_short):
            self.assertEqual(self.observation.read('/proc/inert'), b'abcdefg')
        self.assertEqual(observed_buffering, [0])
        self.assertEqual(self.observation.bytes, 7)
        self.assertEqual(requests, [p._PROC_BYTES, p._PROC_BYTES - 2, p._PROC_BYTES - 4,
                                    p._PROC_BYTES - 6, p._PROC_BYTES - 7])

    def test_cancellation_checkpoints_stop_before_full_scan(self):
        calls = [0]
        def cancel():
            calls[0] += 1
            return calls[0] >= 8
        self.observation.cancelled = cancel
        with self.assertRaisesRegex(p.ProcessTreeError, 'cancelled'):
            self.observation.sample(100, 10)
        self.assertLess(len(self.fs.reads), 10)


class CompatibilityAndControl(unittest.TestCase):
    def test_control_partial_request_cancel_and_go_ordering(self):
        for raw in (b'TG', b'GT', b'S{"request_id":T'):
            pipe = FakePipe([raw])
            with pipe.patches():
                self.assertEqual(p._SupervisorControl(1).receive(), 'stop')
        pipe = FakePipe([b'G', BlockingIOError()])
        with pipe.patches():
            self.assertEqual(p._SupervisorControl(1).receive(), 'go')

    def test_control_rejects_oversize_and_strict_request(self):
        for raw in (b'S' + b'x' * 256, b'Q', b'S' + encoded(dict(request_id=True, maximum_processes=2, deadline=20))):
            with FakePipe([raw]).patches(), mock.patch.object(p.time, 'monotonic', return_value=10):
                self.assertEqual(p._SupervisorControl(1).receive(), 'stop')

    def test_frame_partial_write_and_cancellation_backpressure(self):
        pipe, writes = FakePipe(), [0]
        def short(_fd, raw):
            writes[0] += 1
            if writes[0] == 2:
                raise BlockingIOError()
            return min(3, len(raw))
        pipe.on_write = short
        with pipe.patches(), mock.patch.object(p.time, 'monotonic', return_value=10), mock.patch.object(p.time, 'sleep'):
            p._frame_write(2, {'kind': 'inert'}, 100, 20, lambda: False)
        self.assertGreater(writes[0], 3)
        with pipe.patches(), self.assertRaisesRegex(p.ProcessTreeError, 'cancelled'):
            p._frame_write(2, {}, 100, 20, lambda: True)
        calls = [False, True]
        pipe.on_write = lambda *_: (_ for _ in ()).throw(BlockingIOError())
        with pipe.patches(), mock.patch.object(p.time, 'monotonic', return_value=10), \
             mock.patch.object(p.time, 'sleep'), self.assertRaisesRegex(p.ProcessTreeError, 'cancelled'):
            p._frame_write(2, {}, 100, 20, lambda: calls.pop(0))
        self.assertEqual(calls, [])

    def test_launch_strict_bool_and_other_host_rejection_before_launch(self):
        for value in (1, 0, None, 'yes'):
            with self.subTest(value=value), mock.patch.object(p.subprocess, 'Popen') as launch:
                with self.assertRaises(p.ProcessTreeError):
                    p.launch(['fixture'], '/inert', object(), isolated_python_supervisor=value)
                launch.assert_not_called()
        with mock.patch.object(p.os, 'name', 'nt'), mock.patch.object(p.subprocess, 'Popen') as launch:
            with self.assertRaises(p.ProcessTreeError):
                p.launch(['fixture'], '/inert', object(), isolated_python_supervisor=True)
            launch.assert_not_called()

    def test_default_and_isolated_exact_argv(self):
        for isolated in (False, True):
            with mock.patch.object(p.os, 'pipe', side_effect=[(1, 3), (4, 2)]), \
                 mock.patch.object(p.os, 'close'), mock.patch.object(p.os, 'getpid', return_value=10), \
                 mock.patch.object(p.time, 'monotonic', return_value=10), \
                 mock.patch.object(p.subprocess, 'Popen', return_value=FakeSupervisor()) as launch:
                tree = p.launch(['fixture', 'arg'], '/inert', object(), isolated_python_supervisor=isolated)
            args = launch.call_args.args[0]
            helper = str((ROOT / 'tools/process_tree.py').resolve())
            expected = ([p.sys.executable, '-I', '-S', '-B', helper, '--supervise-linux-isolated',
                         '10', '3', '4', '20'] if isolated else
                        [p.sys.executable, '-B', helper, '--supervise-linux', '10', '3', '4'])
            # repr(float deadline) follows the actual numeric monotonic result.
            if isolated:
                self.assertEqual(float(args[-3]), 20)
                expected[-1] = args[-3]
            self.assertEqual(args, expected + ['fixture', 'arg'])
            self.assertEqual(tree.process._protocol, isolated)


    def test_original_supervisor_default_final_bytes_with_only_fakes(self):
        api = SimpleNamespace(prctl=mock.Mock(return_value=0))
        child = SimpleNamespace(pid=200, returncode=None)
        writes = []
        with mock.patch.object(p.ctypes, 'CDLL', return_value=api), \
             mock.patch.object(p.signal, 'signal'), mock.patch.object(p.os, 'set_blocking'), \
             mock.patch.object(p.os, 'getppid', return_value=10), mock.patch.object(p, '_direct_children', return_value=[]), \
             mock.patch.object(p.os, 'read', side_effect=BlockingIOError), \
             mock.patch.object(p.os, 'write', side_effect=lambda fd, raw: writes.append(raw) or len(raw)), \
             mock.patch.object(p.os, 'close'), mock.patch.object(p.time, 'sleep'), \
             mock.patch.object(p.subprocess, 'Popen', return_value=child), \
             mock.patch.object(p.os, 'waitpid', side_effect=[(200, 0), ChildProcessError()]):
            p._linux_supervise(10, 1, 2, ['inert'])
        self.assertEqual(writes, [encoded(final())])

    def test_actual_supervisor_gate_only_releases_after_go_with_fakes(self):
        for controls, released in (([BlockingIOError(), b'G', BlockingIOError(), BlockingIOError(), BlockingIOError()], True),
                                   ([b'TG'], False), ([b'GT'], False), ([b''], False), ([b'S'], False)):
            api = SimpleNamespace(prctl=mock.Mock(return_value=0))
            child = SimpleNamespace(pid=200, returncode=None)
            writes = []
            controls = iter(controls)
            def read(*_):
                value = next(controls, BlockingIOError())
                if isinstance(value, BaseException):
                    raise value
                return value
            frame = startup()
            facts = p.SupervisorStartup(**frame['facts'])
            statuses = [(200, 0), ChildProcessError()] if released else [ChildProcessError()]
            with mock.patch.object(p.ctypes, 'CDLL', return_value=api), \
                 mock.patch.object(p.signal, 'signal'), mock.patch.object(p.os, 'set_blocking'), \
                 mock.patch.object(p.os, 'getppid', return_value=10), \
                 mock.patch.object(p, '_direct_children', return_value=[]), \
                 mock.patch.object(p, '_startup_facts', return_value=facts), \
                 mock.patch.object(p.time, 'monotonic', return_value=10), mock.patch.object(p.time, 'sleep'), \
                 mock.patch.object(p.os, 'read', side_effect=read), \
                 mock.patch.object(p.os, 'write', side_effect=lambda fd, raw: writes.append(raw) or len(raw)), \
                 mock.patch.object(p.os, 'close'), mock.patch.object(p.os, 'waitpid', side_effect=statuses), \
                 mock.patch.object(p.subprocess, 'Popen', return_value=child) as launch:
                p._linux_supervise(10, 1, 2, ['inert'], startup_deadline=20)
            self.assertEqual(launch.call_count, int(released))
            if released:
                self.assertEqual(json.loads(writes[0]), frame)
                self.assertEqual(json.loads(writes[-1]), final())

    def test_supervisor_no_go_expiry_never_creates_target(self):
        api = SimpleNamespace(prctl=mock.Mock(return_value=0))
        facts = p.SupervisorStartup(**startup()['facts'])
        writes = []
        with mock.patch.object(p.ctypes, 'CDLL', return_value=api), mock.patch.object(p.signal, 'signal'), \
             mock.patch.object(p.os, 'set_blocking'), mock.patch.object(p.os, 'getppid', return_value=10), \
             mock.patch.object(p, '_direct_children', return_value=[]), \
             mock.patch.object(p, '_startup_facts', return_value=facts), \
             mock.patch.object(p, '_deadline', return_value=20), \
             mock.patch.object(p, '_remaining', side_effect=[10, 10, p.ProcessTreeError('fixed startup expiry')]), \
             mock.patch.object(p.os, 'read', side_effect=BlockingIOError), \
             mock.patch.object(p.os, 'write', side_effect=lambda fd, raw: writes.append(raw) or len(raw)), \
             mock.patch.object(p.os, 'close'), mock.patch.object(p.os, 'waitpid', side_effect=ChildProcessError), \
             mock.patch.object(p.subprocess, 'Popen') as launch:
            p._linux_supervise(10, 1, 2, ['inert'], startup_deadline=20)
        launch.assert_not_called()
        self.assertIn('fixed startup expiry', json.loads(writes[-1])['error'])

    def test_go_then_pretarget_sample_cannot_cross_startup_deadline(self):
        clock = [10.]
        api = SimpleNamespace(prctl=mock.Mock(return_value=0))
        facts = p.SupervisorStartup(**startup()['facts'])
        control = [None, 'go', None, dict(request_id=1, maximum_processes=1, deadline=30)]
        writes = []
        def scan(*_):
            clock[0] = 21.
            return ()
        with mock.patch.object(p.ctypes, 'CDLL', return_value=api), mock.patch.object(p.signal, 'signal'), \
             mock.patch.object(p.os, 'set_blocking'), mock.patch.object(p.os, 'getppid', return_value=10), \
             mock.patch.object(p, '_direct_children', return_value=[]), \
             mock.patch.object(p, '_startup_facts', return_value=facts), \
             mock.patch.object(p._SupervisorControl, 'receive', side_effect=lambda *_: control.pop(0) if control else None), \
             mock.patch.object(p._ProcObservation, 'sample', side_effect=scan), \
             mock.patch.object(p.os, 'write', side_effect=lambda fd, raw: writes.append(raw) or len(raw)), \
             mock.patch.object(p.os, 'getpid', return_value=100), mock.patch.object(p.os, 'close'), \
             mock.patch.object(p.os, 'waitpid', side_effect=ChildProcessError), \
             mock.patch.object(p.time, 'monotonic', side_effect=lambda: clock[0]), \
             mock.patch.object(p.subprocess, 'Popen') as launch:
            p._linux_supervise(10, 1, 2, ['inert'], startup_deadline=20)
        launch.assert_not_called()
        self.assertIn('deadline', json.loads(writes[-1])['error'])


if __name__ == '__main__':
    unittest.main()
