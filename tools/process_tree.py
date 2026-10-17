#!/usr/bin/env python3
"""Supervise one command and finish its inherited output writers before evidence.

Linux uses a private child-subreaper process, including nested sessions and groups.
Commands must not transfer writable handles or ask another service to keep writing;
such workloads require a qualified container/service supervisor. This is lifetime
supervision of cooperating programs, not hostile-process confinement. Other POSIX
systems fail closed until an equivalent descendant owner is supplied.
Windows starts suspended and assigns a no-breakaway, kill-on-close Job Object
before resuming the initial thread; assignment failure never runs child code.
Windows termination pins verified Job member handles before requesting exit and
joins them under one deadline; changed cumulative assignments fail closed.
Normal completion checks signaled member handles and a fresh complete Job list
before waiting for accounting retirement; a running descendant fails immediately.
An explicit Windows maximum_active_processes limits this Job before any child
runs, including the primary; it is not a per-user quota or available capacity.
The default leaves the active-process limit unset; other hosts reject an explicit cap.
Native qualification is required for each supported platform and environment.
"""
import ctypes
from collections import namedtuple
from contextlib import contextmanager
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time


class ProcessTreeError(RuntimeError):
    pass


ObservedProcessSample = namedtuple('ObservedProcessSample', 'records complete unknown_coverage')
SupervisorStartup = namedtuple('SupervisorStartup',
    'pid parent_pid executable executable_realpath version_info implementation prefix base_prefix '
    'exec_prefix base_exec_prefix sys_path platlibdir flags helper_path dont_write_bytecode')
_STARTUP_FLAGS = ('isolated', 'ignore_environment', 'no_user_site', 'no_site', 'dont_write_bytecode')
_STARTUP_BYTES = 64 * 1024
_SAMPLE_BYTES = 256 * 1024
_PROC_BYTES = 64 * 1024
_SAMPLE_TOTAL_BYTES = 32 * 1024 * 1024
_TASK_ENTRIES = 16384
_REQUEST_BYTES = 256


def _finite_deadline(value):
    try:
        finite = type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        finite = False
    if not finite:
        raise ProcessTreeError('deadline must be a finite monotonic number')
    return value


def _deadline(value):
    _finite_deadline(value)
    if value <= time.monotonic():
        raise ProcessTreeError('observation deadline exhausted; retain output ownership')
    return value


def _sample_limit(value):
    if type(value) is not int or not 1 <= value <= 1024:
        raise ProcessTreeError('maximum_processes must be an integer in 1..1024')
    return value


def _number(token, *, maximum=2 ** 64 - 1, zero=False):
    if (not token or len(token) > 20 or any(c < 48 or c > 57 for c in token)):
        raise ProcessTreeError('invalid bounded proc identity')
    value = int(token)
    if value > maximum or value < (0 if zero else 1):
        raise ProcessTreeError('proc identity outside its bounded range')
    return value


class _ProcObservation:
    """Finite repeated metadata observations; never an atomic process census."""
    def __init__(self, maximum, deadline, cancelled):
        self.maximum, self.deadline, self.cancelled = maximum, deadline, cancelled
        self.bytes = self.entries = 0

    def checkpoint(self):
        if self.cancelled():
            raise ProcessTreeError('process observation cancelled')
        _remaining(self.deadline)

    def read(self, path):
        parts, consumed = [], 0
        self.checkpoint()
        # FileIO avoids BufferedReader prefetch beyond the actual I/O allowance.
        # A short native read is not EOF: only an actual zero-byte read is.
        with open(path, 'rb', buffering=0) as source:
            while True:
                self.checkpoint()
                allowance = min(_PROC_BYTES - consumed, _SAMPLE_TOTAL_BYTES - self.bytes)
                if allowance <= 0:
                    raise ProcessTreeError('metadata at byte boundary cannot establish bounded EOF budget')
                raw = source.read(allowance)
                if type(raw) is not bytes or len(raw) > allowance:
                    raise ProcessTreeError('invalid bounded metadata read')
                self.bytes += len(raw)
                consumed += len(raw)
                self.checkpoint()
                if not raw:
                    return b''.join(parts)
                parts.append(raw)

    def stat(self, raw, expected):
        # comm may contain whitespace and closing parentheses. The final ')' is
        # followed by the fixed stat fields, whose starttime is field 22.
        end = raw.rfind(b')')
        first = raw.find(b' (')
        if first <= 0 or end <= first:
            raise ProcessTreeError('malformed proc stat')
        pid = _number(raw[:first], maximum=2 ** 31 - 1)
        fields = raw[end + 1:].split()
        if pid != expected or len(fields) < 20 or len(fields[0]) != 1:
            raise ProcessTreeError('proc stat identity mismatch')
        return (_number(fields[1], maximum=2 ** 31 - 1, zero=True), _number(fields[19]))

    def identity(self, tgid, tid=None):
        tid = tgid if tid is None else tid
        base = '/proc/' + str(tgid) + ('/task/' + str(tid) if tid != tgid else '')
        before = self.stat(self.read(base + '/stat'), tid)
        status = self.read(base + '/status')
        values = {}
        for line in status.splitlines():
            self.checkpoint()
            key, sep, value = line.partition(b':')
            if key in (b'Pid', b'Tgid', b'PPid'):
                if not sep or key in values:
                    raise ProcessTreeError('ambiguous proc status identity')
                values[key] = _number(value.strip(), maximum=2 ** 31 - 1, zero=key == b'PPid')
        after = self.stat(self.read(base + '/stat'), tid)
        if (set(values) != {b'Pid', b'Tgid', b'PPid'} or values[b'Pid'] != tid
                or values[b'Tgid'] != tgid or values[b'PPid'] != before[0] or before != after):
            raise ProcessTreeError('changed proc task identity')
        return (tid, tgid, before[0], before[1])

    def normalize(self, child):
        raw = self.read('/proc/' + str(child) + '/status')
        found = [line.partition(b':')[2].strip() for line in raw.splitlines()
                 if line.partition(b':')[0] == b'Tgid']
        if len(found) != 1:
            raise ProcessTreeError('child TGID unavailable')
        tgid = _number(found[0], maximum=2 ** 31 - 1)
        task = self.identity(tgid, child)
        leader = self.identity(tgid)
        if (self.identity(tgid, child) != task or task[2] != leader[2]
                or (tgid == child and task != leader)):
            raise ProcessTreeError('normalized child identity changed')
        return tgid, leader, task

    def tasks(self, tgid):
        values = []
        self.checkpoint()
        with os.scandir('/proc/' + str(tgid) + '/task') as entries:
            for entry in entries:
                self.checkpoint()
                self.entries += 1
                if self.entries > _TASK_ENTRIES:
                    raise ProcessTreeError('process observation task budget exhausted')
                try:
                    token = entry.name.encode('ascii')
                except UnicodeError as error:
                    raise ProcessTreeError('invalid proc task entry') from error
                values.append(_number(token, maximum=2 ** 31 - 1))
        values.sort()
        if not values or tgid not in values or len(set(values)) != len(values):
            raise ProcessTreeError('leader task directory unavailable or changed')
        return tuple(values)

    def walk(self, supervisor, controller):
        root = self.identity(supervisor)
        controller_identity = self.identity(controller)
        pending = [(supervisor, root, None)]
        queued = {supervisor}
        selected, signatures = {}, []
        while pending:
            self.checkpoint()
            tgid, expected, parent = pending.pop()
            before = self.identity(tgid)
            if before != expected:
                raise ProcessTreeError('process identity changed during observation')
            if parent is not None:
                parent_id = self.identity(parent[0])
                if parent_id != parent or before[2] != parent[0]:
                    raise ProcessTreeError('process parent edge changed during observation')
                selected[tgid] = (tgid, before[3], parent[0], parent[3])
            tids = self.tasks(tgid)
            task_facts = []
            children = {}
            for tid in tids:
                self.checkpoint()
                initial = self.identity(tgid, tid)
                raw = self.read('/proc/' + str(tgid) + '/task/' + str(tid) + '/children')
                for token in raw.split():
                    self.checkpoint()
                    child, child_identity, child_task = self.normalize(_number(token, maximum=2 ** 31 - 1))
                    if child in children or child in queued or child == controller:
                        raise ProcessTreeError('ambiguous or racing child membership')
                    children[child] = (child_identity, child_task)
                    if len(selected) + len(pending) + len(children) > self.maximum:
                        raise ProcessTreeError('observed process threshold exceeded')
                if self.identity(tgid, tid) != initial:
                    raise ProcessTreeError('task identity changed around children read')
                task_facts.append(initial)
            if self.tasks(tgid) != tids or self.identity(tgid) != before:
                raise ProcessTreeError('task membership changed during observation')
            signatures.append((before, tuple(task_facts)))
            for child in sorted(children):
                identity = self.identity(child)
                discovered, discovered_task = children[child]
                if (identity != discovered or identity[2] != tgid
                        or self.identity(child, discovered_task[0]) != discovered_task):
                    raise ProcessTreeError('child reparented during observation')
                queued.add(child)
                pending.append((child, identity, before))
        if self.identity(supervisor) != root or self.identity(controller) != controller_identity:
            raise ProcessTreeError('supervisor/controller identity changed')
        return tuple(sorted(selected.values())), tuple(sorted(signatures))

    def sample(self, supervisor, controller):
        first = self.walk(supervisor, controller)
        second = self.walk(supervisor, controller)
        if first != second:
            raise ProcessTreeError('process observations changed between bounded passes')
        self.checkpoint()
        return first[0]


def _frame_write(fd, payload, maximum, deadline, cancelled):
    data = (json.dumps(payload, sort_keys=True, separators=(',', ':')) + '\n').encode('utf-8')
    if len(data) > maximum:
        raise ProcessTreeError('private observation frame exceeds byte budget')
    os.set_blocking(fd, False)
    try:
        offset = 0
        while offset < len(data):
            if cancelled():
                raise ProcessTreeError('private observation write cancelled')
            _remaining(deadline)
            try:
                count = os.write(fd, data[offset:])
                if not count:
                    raise ProcessTreeError('private observation write made no progress')
                offset += count
            except BlockingIOError:
                time.sleep(min(0.001, _remaining(deadline)))
    finally:
        os.set_blocking(fd, True)


class _SupervisorControl:
    def __init__(self, fd):
        self.fd, self.buffer = fd, bytearray()

    def receive(self):
        try:
            raw = os.read(self.fd, _REQUEST_BYTES + 1)
        except BlockingIOError:
            raw = None
        if raw == b'':
            return 'stop'
        if raw:
            self.buffer.extend(raw)
        if b'T' in self.buffer:
            return 'stop'
        if not self.buffer:
            return None
        if self.buffer[0] in (ord('T'), ord('G')):
            result = 'stop' if self.buffer[0] == ord('T') else 'go'
            del self.buffer[:1]
            return result
        if self.buffer[0] != ord('S') or len(self.buffer) > _REQUEST_BYTES:
            return 'stop'
        end = self.buffer.find(b'\n')
        if end < 0:
            return None
        raw = bytes(self.buffer[1:end])
        del self.buffer[:end + 1]
        try:
            request = json.loads(raw)
            if (type(request) is not dict or set(request) != {'request_id', 'maximum_processes', 'deadline'}
                    or type(request['request_id']) is not int or not 1 <= request['request_id'] <= 2 ** 31 - 1):
                raise ValueError('invalid request')
            _sample_limit(request['maximum_processes'])
            _finite_deadline(request['deadline'])
        except (ValueError, ProcessTreeError):
            return 'stop'
        return request


def _startup_facts():
    return SupervisorStartup(os.getpid(), os.getppid(), sys.executable, os.path.realpath(sys.executable),
        tuple(sys.version_info[:3]), sys.implementation.name, sys.prefix, sys.base_prefix,
        sys.exec_prefix, sys.base_exec_prefix, tuple(sys.path), sys.platlibdir,
        tuple((name, getattr(sys.flags, name)) for name in _STARTUP_FLAGS),
        str(Path(__file__).resolve()), sys.dont_write_bytecode)


def _remaining(deadline):
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise ProcessTreeError('descendant exit deadline exhausted; retain output ownership')
    return remaining


def _direct_children():
    """The private supervisor has one thread and is its children's only reaper."""
    text = Path('/proc/self/task/' + str(os.getpid()) + '/children').read_text()
    values = text.split()
    if any(not value.isdecimal() or int(value) <= 0 for value in values):
        raise ProcessTreeError('invalid private supervisor child inventory')
    return [int(value) for value in values]


def _linux_supervise(parent, report_fd, control_fd, argv, *, startup_deadline=None):
    """Run only in a dedicated process, never inside the calling Python harness.

    Reaping all children to ECHILD proves no descendant can still create writers.
    During cleanup, killing direct children makes their descendants direct adopted
    children of this subreaper. Repeat until the kernel reports no children. PID
    identity cannot be reused between inventory and kill: this single-threaded
    process performs no wait/reap between those operations.
    """
    stopping = False
    primary = None
    code = None
    outlived = False
    error = None
    reaped = 0
    def stop(_signum, _frame):
        nonlocal stopping
        stopping = True
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGCHLD, signal.SIG_DFL)
    os.set_blocking(control_fd, False)
    control = _SupervisorControl(control_fd)
    def cancelled():
        nonlocal stopping
        event = control.receive()
        if event is not None or control.buffer:
            stopping = True
        return stopping
    def requested():
        nonlocal stopping
        event = control.receive()
        if event is None:
            return False
        if not isinstance(event, dict):
            return True
        deadline = min(event['deadline'], time.monotonic() + 5)
        response = {'kind': 'process-sample', 'schema_version': 1,
                    'request_id': event['request_id'], 'records': [],
                    'complete': False, 'unknown_coverage': True, 'error': None}
        try:
            response['records'] = _ProcObservation(event['maximum_processes'], deadline, cancelled).sample(os.getpid(), parent)
        except BaseException as failure:
            response['error'] = 'process observation failed: ' + str(failure)[:1024]
        # A timed-out scan still has a small bounded diagnostic to drain. Its
        # write receives no renewed scan budget and remains cancellation-aware.
        if not stopping and time.monotonic() < deadline:
            try:
                _frame_write(report_fd, response, _SAMPLE_BYTES, deadline, cancelled)
            except ProcessTreeError:
                # A partial frame remains uncertainty at the collector. Do not
                # relabel sampling expiry/cancellation as cleanup failure.
                pass
        return stopping
    try:
        api = ctypes.CDLL(None, use_errno=True)
        api.prctl.argtypes = [ctypes.c_int, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong]
        api.prctl.restype = ctypes.c_int
        if api.prctl(36, 1, 0, 0, 0) != 0:  # PR_SET_CHILD_SUBREAPER
            raise ProcessTreeError('private Linux child-subreaper setup failed')
        if api.prctl(1, signal.SIGTERM, 0, 0, 0) != 0:  # PR_SET_PDEATHSIG
            raise ProcessTreeError('private Linux parent-death notification failed')
        if os.getppid() != parent:
            raise ProcessTreeError('command owner exited before launch')
        _direct_children()  # Require the cleanup primitive before any command code.
        if startup_deadline is not None:
            _deadline(startup_deadline)
            _frame_write(report_fd, {'kind': 'supervisor-startup', 'schema_version': 1,
                                    'facts': _startup_facts()._asdict()},
                         _STARTUP_BYTES, startup_deadline, cancelled)
            while not stopping:
                _remaining(startup_deadline)
                event = control.receive()
                if event == 'go':
                    # A queued T/EOF/second GO is already a revocation. There
                    # is no target creation between these control checkpoints.
                    if cancelled():
                        break
                    _remaining(startup_deadline)
                    break
                if event is not None or control.buffer:
                    stopping = True
                    break
                time.sleep(min(0.001, _remaining(startup_deadline)))
        if stopping or requested():
            stopping = True
            code = -signal.SIGTERM
        else:
            if startup_deadline is not None:
                _remaining(startup_deadline)
            child = subprocess.Popen(argv, stdin=subprocess.DEVNULL, close_fds=True)
            primary = child.pid
    except BaseException as failure:
        error = 'supervisor launch failed: ' + str(failure)[:1024]
        stopping = True
    # Even a failed inspection keeps this owner alive while children remain. The
    # caller times out and retains ownership instead of claiming uncertain cleanup.
    while True:
        empty = False
        try:
            stopping = stopping or requested()
            while True:
                try:
                    pid, status = os.waitpid(-1, os.WNOHANG)
                except ChildProcessError:
                    empty = True
                    break
                if not pid:
                    break
                reaped += 1
                if pid == primary:
                    code = os.waitstatus_to_exitcode(status)
                    child.returncode = code
            if empty:
                break
            if code is not None and not stopping:
                outlived = True
            if stopping or outlived:
                for pid in _direct_children():
                    try:
                        os.kill(pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
        except BaseException as failure:
            error = 'descendant cleanup inspection failed: ' + str(failure)[:1024]
            stopping = True
        time.sleep(0.01)
    report = {'schema_version': 1, 'primary_returncode': code, 'descendants_outlived': outlived,
              'terminated': stopping, 'error': error, 'reaped': reaped}
    data = (json.dumps(report, sort_keys=True) + '\n').encode()
    if len(data) > 4096:
        report['error'] = 'supervisor failure exceeded the bounded diagnostic size'
        data = (json.dumps(report, sort_keys=True) + '\n').encode()
    # The pipe is private, has one small final record, and is not inherited by the
    # command. A lost receipt remains uncertain to the caller, even after cleanup.
    try:
        os.write(report_fd, data)
    finally:
        os.close(report_fd)
        os.close(control_fd)


class _LinuxProcess:
    """Popen-compatible observation of a privately supervised primary command."""
    def __init__(self, supervisor, report_fd, argv, control_fd=None, *, startup_deadline=None,
                 expected_parent=None, expected_helper=None):
        self.supervisor, self.report_fd, self.args = supervisor, report_fd, argv
        self.control_fd = control_fd
        self.pid = supervisor.pid
        self.returncode = None
        self.report = None
        self.failure = None
        self._lock = threading.RLock()
        self._protocol = startup_deadline is not None
        self._startup_deadline = startup_deadline
        self._expected_parent = expected_parent
        self._expected_helper = expected_helper
        self._startup = None
        self._release_attempted = False
        self._released = False
        self._revoked = False
        self._buffer = bytearray()
        self._eof = False
        self._final = None
        self._validated_final = None
        self._request_id = 0
        self._pending = None
        self._responses = {}
        self._sample_failure = None
        self._owner_tree = None

    def _observer_open(self):
        if self._owner_tree is not None and self._owner_tree.closed:
            raise ProcessTreeError('process owner already closed')

    @contextmanager
    def _reading(self, deadline):
        if not self._lock.acquire(timeout=_remaining(deadline)):
            raise ProcessTreeError('private observation reader busy beyond deadline; retain output ownership')
        try:
            _remaining(deadline)
            yield
        finally:
            self._lock.release()

    def _close_pipes(self):
        for name in ('report_fd', 'control_fd'):
            fd = getattr(self, name)
            if fd is not None:
                os.close(fd)
                setattr(self, name, None)

    def _accept_final(self, report):
        required = {'schema_version', 'primary_returncode', 'descendants_outlived', 'terminated', 'error', 'reaped'}
        if (type(report) is not dict or set(report) != required or type(report['schema_version']) is not int
                or report['schema_version'] != 1 or type(report['descendants_outlived']) is not bool
                or type(report['terminated']) is not bool or type(report['reaped']) is not int or report['reaped'] < 0
                or (report['error'] is not None and type(report['error']) is not str)
                or (report['primary_returncode'] is not None and type(report['primary_returncode']) is not int)
                or (report['primary_returncode'] is None and not report['error'])):
            raise ValueError('invalid private supervisor receipt')
        # This immutable snapshot is produced only by the actual collector. The
        # public legacy report dictionary is never completion evidence.
        self._final = tuple(report[name] for name in sorted(required))
        self.report = dict(report)
        self.returncode = report['primary_returncode'] if report['primary_returncode'] is not None else 125

    def _accept_startup(self, frame):
        if (self._startup_deadline is None or self._startup is not None or type(frame) is not dict
                or set(frame) != {'kind', 'schema_version', 'facts'} or type(frame['schema_version']) is not int
                or frame['schema_version'] != 1 or type(frame['facts']) is not dict
                or set(frame['facts']) != set(SupervisorStartup._fields)):
            raise ValueError('invalid private supervisor startup frame')
        facts = dict(frame['facts'])
        for name in ('pid', 'parent_pid'):
            if type(facts[name]) is not int or facts[name] <= 0:
                raise ValueError('invalid supervisor startup process identity')
        if (facts['pid'] != self.pid or facts['parent_pid'] != self._expected_parent
                or facts['helper_path'] != self._expected_helper):
            raise ValueError('foreign supervisor startup identity')
        for name in ('executable', 'executable_realpath', 'implementation', 'prefix', 'base_prefix',
                     'exec_prefix', 'base_exec_prefix', 'platlibdir', 'helper_path'):
            if type(facts[name]) is not str:
                raise ValueError('invalid supervisor startup string')
        version = facts['version_info']
        if type(version) is not list or len(version) != 3 or any(type(v) is not int or v < 0 for v in version):
            raise ValueError('invalid supervisor version observation')
        paths = facts['sys_path']
        if type(paths) is not list or any(type(v) is not str for v in paths):
            raise ValueError('invalid supervisor path observation')
        flags = facts['flags']
        if (type(flags) is not list or len(flags) != len(_STARTUP_FLAGS)
                or any(type(pair) is not list or len(pair) != 2 or pair[0] != name
                       or type(pair[1]) is not int or pair[1] != 1 for pair, name in zip(flags, _STARTUP_FLAGS))
                or facts['dont_write_bytecode'] is not True):
            raise ValueError('supervisor did not observe requested isolation flags')
        facts['version_info'], facts['sys_path'] = tuple(version), tuple(paths)
        facts['flags'] = tuple(tuple(pair) for pair in flags)
        self._startup = SupervisorStartup(**facts)

    def _accept_sample(self, frame):
        required = {'kind', 'schema_version', 'request_id', 'records', 'complete', 'unknown_coverage', 'error'}
        if (type(frame) is not dict or set(frame) != required or type(frame['schema_version']) is not int
                or frame['schema_version'] != 1 or self._pending is None
                or type(frame['request_id']) is not int or frame['request_id'] != self._pending[0]
                or frame['request_id'] in self._responses or frame['complete'] is not False
                or frame['unknown_coverage'] is not True
                or (frame['error'] is not None and type(frame['error']) is not str)
                or type(frame['records']) is not list or len(frame['records']) > self._pending[1]):
            raise ValueError('invalid private process sample frame')
        records, seen = [], set()
        for record in frame['records']:
            if (type(record) is not list or len(record) != 4 or any(type(v) is not int or v <= 0 for v in record)
                    or record[0] in seen or record[0] in (self.pid, self._expected_parent)
                    or record[0] > 2 ** 31 - 1 or record[2] > 2 ** 31 - 1
                    or record[1] > 2 ** 64 - 1 or record[3] > 2 ** 64 - 1):
                raise ValueError('invalid private sample identity')
            seen.add(record[0])
            records.append(tuple(record))
        if frame['error'] is not None and records:
            raise ValueError('failed process sample contains partial records')
        self._responses[frame['request_id']] = (ObservedProcessSample(tuple(records), False, True), frame['error'])

    def _drain(self):
        if self.report_fd is None or self._eof:
            return
        os.set_blocking(self.report_fd, False)
        # Each turn is finite even if a broken helper keeps sending bytes.
        for _ in range(66):
            try:
                raw = os.read(self.report_fd, 4096)
            except BlockingIOError:
                break
            if not raw:
                self._eof = True
                if self._buffer:
                    self.failure = 'private supervisor truncated its receipt; retain output ownership'
                break
            if self.failure is not None:
                continue  # Drain for cleanup without resynchronizing corrupt framing.
            self._buffer.extend(raw)
            while b'\n' in self._buffer:
                end = self._buffer.index(b'\n') + 1
                if end > _SAMPLE_BYTES:
                    self.failure = 'private supervisor frame exceeds byte budget; retain output ownership'
                    self._buffer.clear()
                    break
                frame_raw = bytes(self._buffer[:end])
                del self._buffer[:end]
                try:
                    frame = json.loads(frame_raw)
                    kind = frame.get('kind') if type(frame) is dict else None
                    if self._final is not None:
                        raise ValueError('data after private final receipt')
                    if kind == 'supervisor-startup':
                        if len(frame_raw) > _STARTUP_BYTES:
                            raise ValueError('startup frame exceeds byte budget')
                        self._accept_startup(frame)
                    elif kind == 'process-sample':
                        self._accept_sample(frame)
                    else:
                        if len(frame_raw) > 4096:
                            raise ValueError('final receipt exceeds byte budget')
                        self._accept_final(frame)
                except (ValueError, TypeError, KeyError, RecursionError):
                    self.failure = 'private supervisor completion uncertain; retain output ownership'
                    self._buffer.clear()
                    break
            if len(self._buffer) > _SAMPLE_BYTES or (self._final is not None and self._buffer):
                self.failure = 'private supervisor framing uncertain; retain output ownership'
                self._buffer.clear()

    def _collect_protocol(self):
        self._drain()
        if self.supervisor.returncode is None:
            return None
        if not self._eof:
            if self.report_fd is None:
                raise ProcessTreeError('private final receipt lacks actual EOF evidence; retain output ownership')
            return None
        try:
            if self.failure is not None or self.supervisor.returncode != 0 or self._final is None:
                raise ProcessTreeError(self.failure or 'private supervisor completion uncertain; retain output ownership')
            self._validated_final = self._final
            return self.returncode
        finally:
            self._close_pipes()

    def _completed_sample(self):
        if self._validated_final is None:
            raise ProcessTreeError('private supervisor completion was not validated')
        # The actual ECHILD final path also proves current emptiness after a
        # nonzero target or controlled termination. Existing finish failures and
        # return codes remain independent from this current-closure observation.
        report = dict(zip(sorted({'schema_version', 'primary_returncode', 'descendants_outlived',
                                  'terminated', 'error', 'reaped'}), self._validated_final))
        if report['error'] is not None:
            raise ProcessTreeError('private supervisor cleanup remained uncertain')
        return ObservedProcessSample((), True, False)

    def observe_supervisor_startup(self, *, deadline):
        deadline = _deadline(deadline)
        if self._startup_deadline is None:
            raise ProcessTreeError('no pending isolated supervisor startup')
        deadline = min(deadline, self._startup_deadline)
        with self._reading(deadline):
            self._observer_open()
            if self._startup_deadline is None or self._revoked or self._release_attempted:
                raise ProcessTreeError('no pending isolated supervisor startup')
            deadline = min(deadline, self._startup_deadline)
            while True:
                _remaining(deadline)
                self._drain()
                if self.failure is not None:
                    raise ProcessTreeError(self.failure)
                if self.supervisor.poll() is not None or self._final is not None:
                    raise ProcessTreeError('isolated supervisor exited before release')
                if self._startup is not None:
                    _remaining(deadline)
                    return self._startup
                time.sleep(min(0.001, _remaining(deadline)))

    def release_supervisor_startup(self, observation):
        if self._startup_deadline is None:
            raise ProcessTreeError('no pending isolated supervisor startup')
        with self._reading(self._startup_deadline):
            self._observer_open()
            if (self._startup_deadline is None or self._revoked or self._release_attempted
                    or self._startup is None or observation is not self._startup):
                raise ProcessTreeError('startup release requires this pending owner observation')
            _remaining(self._startup_deadline)
            self._drain()
            if self.failure is not None or self.supervisor.poll() is not None or self._final is not None:
                raise ProcessTreeError('startup owner no longer pending release')
            _remaining(self._startup_deadline)
            self._release_attempted = True  # An uncertain write must never be retried.
            try:
                if os.write(self.control_fd, b'G') != 1:
                    raise ProcessTreeError('startup GO write uncertain; retain output ownership')
            except OSError as error:
                self._revoked = True
                raise ProcessTreeError('startup GO write failed; retain output ownership') from error
            self._released = True

    def sample_processes(self, *, maximum_processes, deadline):
        entered = time.monotonic()
        maximum_processes = _sample_limit(maximum_processes)
        deadline = min(_deadline(deadline), entered + 5)
        with self._reading(deadline):
            self._observer_open()
            self._protocol = True
            if self.poll() is not None:
                _remaining(deadline)
                return self._completed_sample()
            if self._startup_deadline is not None and not self._released:
                raise ProcessTreeError('isolated supervisor must be released before sampling')
            if self._sample_failure is not None:
                raise ProcessTreeError(self._sample_failure)
            if self.failure is not None or self._pending is not None:
                raise ProcessTreeError(self.failure or 'a process sample request is already pending')
            if self._request_id >= 2 ** 31 - 1:
                raise ProcessTreeError('private sample request identity exhausted')
            self._request_id += 1
            self._pending = (self._request_id, maximum_processes)
            raw = b'S' + (json.dumps({'request_id': self._request_id, 'maximum_processes': maximum_processes,
                                     'deadline': deadline}, separators=(',', ':')) + '\n').encode('ascii')
            try:
                if len(raw) > _REQUEST_BYTES or os.write(self.control_fd, raw) != len(raw):
                    raise ProcessTreeError('private sample request write uncertain')
                while True:
                    _remaining(deadline)
                    self._drain()
                    if self.failure is not None:
                        raise ProcessTreeError(self.failure)
                    if self._request_id in self._responses:
                        result, error = self._responses.pop(self._request_id)
                        self._pending = None
                        if error is not None:
                            raise ProcessTreeError(error)
                        _remaining(deadline)
                        return result
                    if self.supervisor.poll() is not None:
                        if self._collect_protocol() is not None:
                            _remaining(deadline)
                            return self._completed_sample()
                    time.sleep(min(0.001, _remaining(deadline)))
            except BaseException as error:
                self._sample_failure = 'private process sample failed; retain output ownership: ' + str(error)
                raise

    def _collect(self):
        if self.failure is not None:
            raise ProcessTreeError(self.failure)
        if self.report is not None:
            return self.returncode
        try:
            raw = os.read(self.report_fd, 8193)
            if len(raw) > 8192 or self.supervisor.returncode != 0:
                raise ValueError('private supervisor failed or excessive receipt')
            report = json.loads(raw)
            required = {'schema_version', 'primary_returncode', 'descendants_outlived', 'terminated', 'error', 'reaped'}
            if (not isinstance(report, dict) or set(report) != required or report['schema_version'] != 1
                    or type(report['descendants_outlived']) is not bool or type(report['terminated']) is not bool
                    or type(report['reaped']) is not int or report['reaped'] < 0
                    or (report['error'] is not None and not isinstance(report['error'], str))
                    or (report['primary_returncode'] is not None and type(report['primary_returncode']) is not int)):
                raise ValueError('invalid private supervisor receipt')
            if report['primary_returncode'] is None and not report['error']:
                raise ValueError('primary completion missing from supervisor receipt')
            self.report = report
            self.returncode = report['primary_returncode'] if report['primary_returncode'] is not None else 125
            # Preserve the legacy wait result, but mint NEW closure evidence
            # only from strict original bytes and an actual additional EOF
            # read. Supervisor exit alone cannot hide unread trailing data.
            try:
                os.set_blocking(self.report_fd, False)
                self._eof = os.read(self.report_fd, 1) == b''
                if self._eof and len(raw) <= 4096 and raw.endswith(b'\n') and raw.count(b'\n') == 1:
                    self._accept_final(json.loads(raw))
                    self._validated_final = self._final
            except (OSError, ValueError):
                self._final = self._validated_final = None
        except (OSError, ValueError) as failure:
            self.failure = 'private supervisor completion uncertain; retain output ownership'
            raise ProcessTreeError(self.failure) from failure
        finally:
            if self.report_fd is not None:
                os.close(self.report_fd)
                self.report_fd = None
            if self.control_fd is not None:
                os.close(self.control_fd)
                self.control_fd = None
        return self.returncode

    def poll(self):
        if not self._lock.acquire(blocking=False):
            return None
        try:
            if self._protocol:
                self._drain()
                return None if self.supervisor.poll() is None else self._collect_protocol()
            return None if self.supervisor.poll() is None else self._collect()
        finally:
            self._lock.release()

    def wait(self, timeout=None):
        deadline = None if timeout is None else time.monotonic() + timeout
        acquired = (self._lock.acquire() if deadline is None else
                    self._lock.acquire(timeout=max(0, deadline - time.monotonic())))
        if not acquired:
            raise subprocess.TimeoutExpired(self.args, timeout)
        try:
            if deadline is not None and time.monotonic() > deadline:
                raise subprocess.TimeoutExpired(self.args, timeout)
            if not self._protocol:
                self.supervisor.wait(timeout=None if deadline is None else max(0, deadline - time.monotonic()))
                result = self._collect()
                if deadline is not None and time.monotonic() > deadline:
                    raise subprocess.TimeoutExpired(self.args, timeout)
                return result
            while True:
                self._drain()
                if self.supervisor.poll() is not None:
                    result = self._collect_protocol()
                    if result is not None:
                        if deadline is not None and time.monotonic() > deadline:
                            raise subprocess.TimeoutExpired(self.args, timeout)
                        return result
                if deadline is not None and time.monotonic() >= deadline:
                    raise subprocess.TimeoutExpired(self.args, timeout)
                time.sleep(0.001 if deadline is None else min(0.001, max(0, deadline - time.monotonic())))
        finally:
            self._lock.release()

    def terminate(self):
        # This one-byte cancellation must not wait behind a serialized reader
        # holding its lock during a scan. PIPE_BUF atomicity separates it from
        # the single bounded sample request; no second report consumer appears.
        self._revoked = True
        if self.supervisor.poll() is None:
            try:
                os.write(self.control_fd, b'T')
            except BrokenPipeError:
                pass


def _linux_launch(argv, cwd, stream, *, env=None, isolated_python_supervisor=False, startup_deadline=None):
    helper = str(Path(__file__).resolve())
    parent = os.getpid()
    arguments = [sys.executable, '-B', helper, '--supervise-linux', str(parent)]
    if isolated_python_supervisor:
        arguments = [sys.executable, '-I', '-S', '-B', helper, '--supervise-linux-isolated', str(parent)]
    incoming, outgoing = os.pipe()
    try:
        control_incoming, control_outgoing = os.pipe()
    except BaseException:
        os.close(incoming)
        os.close(outgoing)
        raise
    try:
        arguments.extend([str(outgoing), str(control_incoming)])
        if isolated_python_supervisor:
            arguments.append(repr(startup_deadline))
        process = subprocess.Popen([*arguments, *argv],
                                   cwd=cwd, stdin=subprocess.DEVNULL, stdout=stream,
                                   stderr=subprocess.STDOUT, start_new_session=True, pass_fds=(outgoing,control_incoming), env=env)
    except BaseException:
        os.close(incoming)
        os.close(control_outgoing)
        raise
    finally:
        os.close(outgoing)
        os.close(control_incoming)
    return ProcessTree(_LinuxProcess(process, incoming, argv, control_outgoing,
        startup_deadline=startup_deadline if isolated_python_supervisor else None,
        expected_parent=parent, expected_helper=helper))


def _validate_maximum_active_processes(value):
    if value is not None and (type(value) is not int or not 1 <= value <= 65536):
        raise ProcessTreeError('maximum_active_processes must be an integer in 1..65536 or None')
    return value


class _WindowsJob:
    """Native handle owner; constructed only on Windows."""
    def __init__(self, *, maximum_active_processes=None):
        maximum_active_processes = _validate_maximum_active_processes(maximum_active_processes)
        from ctypes import wintypes as w
        self.api = ctypes.WinDLL('kernel32', use_last_error=True)
        self.handle = None
        self.completion_observation = None
        self.w = w
        class BasicLimits(ctypes.Structure):
            _fields_ = [('process_time', ctypes.c_longlong), ('job_time', ctypes.c_longlong),
                        ('flags', w.DWORD), ('min_working_set', ctypes.c_size_t),
                        ('max_working_set', ctypes.c_size_t), ('active_limit', w.DWORD),
                        ('affinity', ctypes.c_size_t), ('priority', w.DWORD), ('scheduling', w.DWORD)]
        class IoCounters(ctypes.Structure):
            _fields_ = [(name, ctypes.c_ulonglong) for name in
                        ('read_ops', 'write_ops', 'other_ops', 'read_bytes', 'write_bytes', 'other_bytes')]
        class ExtendedLimits(ctypes.Structure):
            _fields_ = [('basic', BasicLimits), ('io', IoCounters),
                        ('process_memory', ctypes.c_size_t), ('job_memory', ctypes.c_size_t),
                        ('peak_process_memory', ctypes.c_size_t), ('peak_job_memory', ctypes.c_size_t)]
        class Accounting(ctypes.Structure):
            _fields_ = [('user_time', ctypes.c_longlong), ('kernel_time', ctypes.c_longlong),
                        ('period_user', ctypes.c_longlong), ('period_kernel', ctypes.c_longlong),
                        ('page_faults', w.DWORD), ('total', w.DWORD), ('active', w.DWORD),
                        ('terminated', w.DWORD)]
        class ThreadEntry(ctypes.Structure):
            _fields_ = [('size', w.DWORD), ('usage', w.DWORD), ('thread', w.DWORD),
                        ('owner', w.DWORD), ('base_priority', w.LONG), ('delta_priority', w.LONG),
                        ('flags', w.DWORD)]
        self.Accounting, self.ThreadEntry = Accounting, ThreadEntry
        signatures = {
            'CreateJobObjectW': ([ctypes.c_void_p, w.LPCWSTR], w.HANDLE),
            'SetInformationJobObject': ([w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD], w.BOOL),
            'QueryInformationJobObject': ([w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD, ctypes.c_void_p], w.BOOL),
            'AssignProcessToJobObject': ([w.HANDLE, w.HANDLE], w.BOOL),
            'TerminateJobObject': ([w.HANDLE, w.UINT], w.BOOL),
            'CloseHandle': ([w.HANDLE], w.BOOL),
            'CreateToolhelp32Snapshot': ([w.DWORD, w.DWORD], w.HANDLE),
            'Thread32First': ([w.HANDLE, ctypes.POINTER(ThreadEntry)], w.BOOL),
            'Thread32Next': ([w.HANDLE, ctypes.POINTER(ThreadEntry)], w.BOOL),
            'OpenThread': ([w.DWORD, w.BOOL, w.DWORD], w.HANDLE),
            'ResumeThread': ([w.HANDLE], w.DWORD),
            'OpenProcess': ([w.DWORD, w.BOOL, w.DWORD], w.HANDLE),
            'IsProcessInJob': ([w.HANDLE, w.HANDLE, ctypes.POINTER(w.BOOL)], w.BOOL),
            'WaitForSingleObject': ([w.HANDLE, w.DWORD], w.DWORD),
            'QueryFullProcessImageNameW': ([w.HANDLE, w.DWORD, w.LPWSTR, ctypes.POINTER(w.DWORD)], w.BOOL),
        }
        for name, (arguments, result) in signatures.items():
            function = getattr(self.api, name)
            function.argtypes, function.restype = arguments, result
        self.handle = self.api.CreateJobObjectW(None, None)
        if not self.handle:
            self.fail('create job')
        try:
            limits = ExtendedLimits()
            limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE; no breakaway flags.
            if maximum_active_processes is not None:
                limits.basic.flags |= 0x8  # JOB_OBJECT_LIMIT_ACTIVE_PROCESS.
                limits.basic.active_limit = maximum_active_processes
            if not self.api.SetInformationJobObject(self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
                self.fail('configure non-breakaway job')
            self.maximum_active_processes = maximum_active_processes
        except BaseException:
            self.close()
            raise

    def fail(self, operation):
        raise ProcessTreeError(operation + ' failed: ' + str(ctypes.WinError(ctypes.get_last_error())))

    def assign(self, process):
        if not self.api.AssignProcessToJobObject(self.handle, self.w.HANDLE(int(process._handle))):
            self.fail('assign suspended process to job')

    def resume(self, process):
        snapshot = self.api.CreateToolhelp32Snapshot(0x4, 0)  # TH32CS_SNAPTHREAD
        if snapshot == ctypes.c_void_p(-1).value:
            self.fail('inspect suspended process thread')
        matches = []
        try:
            entry = self.ThreadEntry()
            entry.size = ctypes.sizeof(entry)
            found = self.api.Thread32First(snapshot, ctypes.byref(entry))
            while found:
                if entry.owner == process.pid:
                    matches.append(entry.thread)
                entry.size = ctypes.sizeof(entry)
                found = self.api.Thread32Next(snapshot, ctypes.byref(entry))
            if ctypes.get_last_error() != 18:  # ERROR_NO_MORE_FILES
                self.fail('enumerate suspended process thread')
        finally:
            if not self.api.CloseHandle(snapshot):
                self.fail('close thread snapshot')
        if len(matches) != 1:
            raise ProcessTreeError('expected exactly one suspended initial thread')
        thread = self.api.OpenThread(0x2, False, matches[0])  # THREAD_SUSPEND_RESUME
        if not thread:
            self.fail('open suspended initial thread')
        try:
            count = self.api.ResumeThread(thread)
            if count == 0xffffffff:
                self.fail('resume initial thread')
            if count != 1:
                raise ProcessTreeError('unexpected initial thread suspension count')
        finally:
            if not self.api.CloseHandle(thread):
                self.fail('close initial thread handle')

    def accounting(self):
        accounting = self.Accounting()
        if not self.api.QueryInformationJobObject(self.handle, 1, ctypes.byref(accounting),
                                                  ctypes.sizeof(accounting), None):
            self.fail('inspect job membership')
        return accounting

    def active(self):
        return self.accounting().active

    def total(self):
        return self.accounting().total

    def process_ids(self):
        """Take a complete, bounded Job snapshot, including nested members."""
        capacity = 32
        for _ in range(8):
            class ProcessIds(ctypes.Structure):
                _fields_ = [('assigned', self.w.DWORD), ('count', self.w.DWORD),
                            ('ids', ctypes.c_size_t * capacity)]
            members = ProcessIds()
            ok = self.api.QueryInformationJobObject(self.handle, 3, ctypes.byref(members),
                                                    ctypes.sizeof(members), None)
            if not ok and ctypes.get_last_error() != 234:  # ERROR_MORE_DATA
                self.fail('inspect job process list')
            if members.count > capacity or members.count > members.assigned:
                raise ProcessTreeError('invalid job process list counts')
            if ok and members.count == members.assigned:
                result = list(members.ids[:members.count])
                if len(set(result)) != len(result) or any(not 0 < pid <= 0xffffffff for pid in result):
                    raise ProcessTreeError('invalid job process identifiers')
                return result
            capacity = max(capacity * 2, members.assigned)
            if capacity > 65536:
                break
        raise ProcessTreeError('job process inventory remains incomplete; retain output ownership')

    def observe_running_process(self, pid, handle, members, state):
        """Retain the first rejected handle observation, never a later substitute.

        These bounded diagnostics cannot grant completion. Query the image through
        the already pinned, verified member handle; do not log argv or environment.
        Accounting is explicitly a later observation, not an atomic snapshot.
        """
        if getattr(self, 'completion_observation', None) is not None:
            return
        observation = {'pid': pid, 'member_verified': True, 'wait_state': state,
                       'snapshot_count': len(members), 'snapshot_pids': members[:32],
                       'snapshot_truncated': len(members) > 32}
        self.completion_observation = observation
        image = ctypes.create_unicode_buffer(32768)
        size = self.w.DWORD(len(image))
        if self.api.QueryFullProcessImageNameW(handle, 0, image, ctypes.byref(size)):
            observation['image'] = image.value[:4096]
            observation['image_truncated'] = len(image.value) > 4096
        else:
            observation['image_query_error'] = ctypes.get_last_error()
        try:
            accounting = self.accounting()
            observation['accounting_after_observation'] = {
                key: int(getattr(accounting, key)) for key in ('active', 'total', 'terminated')}
        except (OSError, ProcessTreeError):
            observation['accounting_query_error'] = ctypes.get_last_error()

    def has_running_process(self):
        """Separate executable members from already-signaled process objects.

        Job accounting and process-handle completion are separate observations.
        Never give a running descendant a grace period to finish successfully.
        Open handles pin identity; membership rejects a reused foreign PID.
        """
        observed = {}
        try:
            pending = self.process_ids()
            for _ in range(8):
                disappeared = set()
                for pid in pending:
                    if pid in observed:
                        continue  # The retained signaled handle pins this identity.
                    # SYNCHRONIZE | PROCESS_QUERY_LIMITED_INFORMATION; no inheritance.
                    handle = self.api.OpenProcess(0x101000, False, pid)
                    if not handle:
                        error = ctypes.get_last_error()
                        if error == 87:  # Possibly retired since the snapshot.
                            disappeared.add(pid)
                            continue
                        raise ProcessTreeError('open job member failed: ' + str(error) +
                                               '; retain output ownership')
                    observed[pid] = handle
                    member = self.w.BOOL()
                    if not self.api.IsProcessInJob(handle, self.handle, ctypes.byref(member)):
                        self.fail('confirm job process identity')
                    if not member.value:
                        raise ProcessTreeError('job process identity changed; retain output ownership')
                    state = self.api.WaitForSingleObject(handle, 0)
                    if state == 0x102:  # WAIT_TIMEOUT: still executable now.
                        self.observe_running_process(pid, handle, pending, state)
                        return True
                    if state != 0:  # Only WAIT_OBJECT_0 establishes termination.
                        self.fail('inspect job process completion')
                # A member could have created another member before terminating.
                # Inspect every newly found process before permitting any sleep.
                pending = self.process_ids()
                if disappeared.intersection(pending):
                    raise ProcessTreeError('job member lookup remains ambiguous; retain output ownership')
                if all(pid in observed for pid in pending):
                    return False
            raise ProcessTreeError('job membership did not settle; retain output ownership')
        finally:
            failed = False
            for handle in observed.values():
                if not self.api.CloseHandle(handle):
                    failed = True
            if failed:
                self.fail('close job process observation')

    def terminate(self):
        if not self.api.TerminateJobObject(self.handle, 1):
            self.fail('terminate job')

    def terminate_and_wait(self, deadline, *, validate_live=None):
        """Pin identities before termination; accounting alone is not a join.

        A cumulative assignment change can hide a new child that disappeared from
        the active list before it was pinned. Reject that uncertainty, even when
        the final list and active count are empty. This is not a creation freeze.
        """
        observed, requested, failure = {}, False, None
        try:
            _remaining(deadline)
            total = self.total()
            for pid in self.process_ids():
                _remaining(deadline)
                handle = self.api.OpenProcess(0x101000, False, pid)
                if not handle:
                    # Even ERROR_INVALID_PARAMETER cannot prove completion of an
                    # observed identity that we never managed to pin.
                    raise ProcessTreeError('cannot pin observed job member; retain output ownership')
                observed[pid] = handle
                member = self.w.BOOL()
                if not self.api.IsProcessInJob(handle, self.handle, ctypes.byref(member)):
                    self.fail('confirm termination member identity')
                if not member.value:
                    raise ProcessTreeError('termination member identity changed; retain output ownership')
            if validate_live is not None:
                # Pin the entire snapshot before classifying any live member.
                # A caller-specific helper policy never uses the first-member
                # diagnostic as proof about the remainder of the Job.
                live = []
                for pid, handle in observed.items():
                    _remaining(deadline)
                    state = self.api.WaitForSingleObject(handle, 0)
                    if state == 0x102:
                        live.append((pid, handle))
                    elif state != 0:
                        self.fail('inspect helper process completion')
                # Preserve every live observation before any caller policy work;
                # a later natural exit cannot exempt an already observed member.
                for pid, handle in live:
                    _remaining(deadline)
                    image = ctypes.create_unicode_buffer(32768)
                    size = self.w.DWORD(len(image))
                    if not self.api.QueryFullProcessImageNameW(handle, 0, image, ctypes.byref(size)):
                        self.fail('identify live helper image')
                    if not 0 < size.value < len(image) or size.value != len(image.value):
                        raise ProcessTreeError('invalid live helper image identity; retain output ownership')
                    if validate_live(pid, image.value) is not True:
                        raise ProcessTreeError('live member is not an accepted command helper; retain output ownership')
                    _remaining(deadline)
            def reconcile():
                _remaining(deadline)
                members = self.process_ids()
                if any(pid not in observed for pid in members) or self.total() != total:
                    raise ProcessTreeError('job assignments changed during termination; retain output ownership')
            reconcile()
            requested = True
            self.terminate()
            for handle in observed.values():
                milliseconds = max(1, min(int(_remaining(deadline) * 1000), 0xfffffffe))
                state = self.api.WaitForSingleObject(handle, milliseconds)
                if state == 0x102:
                    raise ProcessTreeError('descendant exit deadline exhausted; retain output ownership')
                if state != 0:
                    self.fail('join terminated job member')
            reconcile()
        except BaseException as error:
            failure = error
            raise
        finally:
            cleanup_errors = []
            if not requested:
                # Capture failed, but still stop executable members. This is a
                # best-effort stop, never a substitute for the failed join proof.
                try:
                    self.terminate()
                except BaseException as error:
                    cleanup_errors.append('stop after failed capture: ' + str(error))
            for handle in observed.values():
                if not self.api.CloseHandle(handle):
                    cleanup_errors.append('close termination observation failed')
            if cleanup_errors:
                message = '; '.join(cleanup_errors) + '; retain output ownership'
                if failure is not None:
                    raise ProcessTreeError(str(failure) + '; ' + message) from failure
                raise ProcessTreeError(message)
        return total

    def close(self):
        if self.handle is not None:
            if not self.api.CloseHandle(self.handle):
                self.fail('close job')
            self.handle = None


class ProcessTree:
    def __init__(self, process, job=None):
        self.process, self.job = process, job
        self.closed = False
        self.termination_joined = False
        self.termination_failure = None
        if isinstance(process, _LinuxProcess):
            with process._lock:
                if process._owner_tree is not None:
                    raise ProcessTreeError('Linux process already belongs to its actual process owner')
                process._owner_tree = self

    def poll(self):
        return self.process.poll()

    def wait(self, timeout=None):
        return self.process.wait(timeout=timeout)

    def _linux_observer(self):
        if self.closed or not isinstance(self.process, _LinuxProcess):
            raise ProcessTreeError('an open actual Linux process owner is required')
        return self.process

    def observe_supervisor_startup(self, *, deadline):
        return self._linux_observer().observe_supervisor_startup(deadline=deadline)

    def release_supervisor_startup(self, observation):
        return self._linux_observer().release_supervisor_startup(observation)

    def sample_processes(self, *, maximum_processes, deadline):
        return self._linux_observer().sample_processes(maximum_processes=maximum_processes, deadline=deadline)

    def _live(self):
        if isinstance(self.process, _LinuxProcess):
            return self.process.poll() is None
        return bool(self.job.active())

    def terminate(self, timeout=5, *, validate_live=None):
        """Stop and join every member; optional helper validation precedes stopping.

        A caller-specific helper policy requires an already successful Windows
        parent and validates every live pinned identity. It does not alter finish.
        """
        if self.closed:
            return
        if self.termination_failure is not None:
            raise ProcessTreeError(self.termination_failure)
        if validate_live is not None:
            if (not callable(validate_live) or self.job is None or self.process.poll() != 0
                    or self.termination_joined):
                raise ProcessTreeError('helper completion requires a successful unjoined Windows command')
        if self.termination_joined:
            return
        deadline = time.monotonic() + timeout
        try:
            if isinstance(self.process, _LinuxProcess):
                self.process.terminate()
            elif self.job is not None:
                total = (self.job.terminate_and_wait(deadline) if validate_live is None else
                         self.job.terminate_and_wait(deadline, validate_live=validate_live))
            self.process.wait(timeout=_remaining(deadline))
            while self._live():
                time.sleep(min(0.01, _remaining(deadline)))
            _remaining(deadline)
            if self.job is not None and self.job.total() != total:
                raise ProcessTreeError('job assignments changed during termination; retain output ownership')
            self.termination_joined = True
        except BaseException as error:
            if self.job is not None:
                self.termination_failure = 'Windows termination remains unconfirmed: ' + str(error)
            raise

    def finish(self):
        """A successful parent with surviving writers is an incomplete command."""
        if self.closed:
            raise ProcessTreeError('process owner already closed')
        if self.termination_failure is not None:
            raise ProcessTreeError(self.termination_failure)
        if self.process.poll() is None:
            raise ProcessTreeError('parent has not exited')
        if isinstance(self.process, _LinuxProcess):
            report = self.process.report
            if report['error']:
                raise ProcessTreeError(report['error'])
            if report['descendants_outlived']:
                raise ProcessTreeError('descendants outlived the command; output completion was not valid')
        deadline = time.monotonic() + 5
        while self._live():
            if self.job is None or self.job.has_running_process():
                message = 'descendants outlived the command; output completion was not valid'
                observation = getattr(self.job, 'completion_observation', None)
                if isinstance(observation, dict):
                    message += '; windows_completion=' + json.dumps(observation, sort_keys=True)
                try:
                    self.terminate()
                except BaseException as error:
                    raise ProcessTreeError(message + '; descendant cleanup failed: ' + str(error)) from error
                raise ProcessTreeError(message)
            # All observed members have terminated. Wait only for accounting to
            # retire them, rechecking for any actual live member on every turn.
            if time.monotonic() >= deadline:
                raise ProcessTreeError('job retirement remains unconfirmed; retain output ownership')
            time.sleep(0.01)
        return self.process.returncode

    def close(self):
        if not self.closed:
            try:
                if self.termination_failure is not None:
                    raise ProcessTreeError(self.termination_failure)
                if self.job is not None or self.process.poll() is None or self._live():
                    # Windows must not skip a required join merely because its
                    # primary and aggregate counters already look completed.
                    self.terminate()
            finally:
                if self.job is not None:
                    self.job.close()
            if isinstance(self.process, _LinuxProcess):
                with self.process._lock:
                    self.closed = True
            else:
                self.closed = True


def launch(argv, cwd, stream, *, env=None, maximum_active_processes=None, isolated_python_supervisor=False):
    """Own descendants; an explicit Windows Job cap includes the primary."""
    # Capture once, before pipe creation or other fallible launch work.
    startup_deadline = time.monotonic() + 10 if isolated_python_supervisor is True else None
    if type(isolated_python_supervisor) is not bool:
        raise ProcessTreeError('isolated_python_supervisor must be a bool')
    linux = os.name == 'posix' and sys.platform.startswith('linux')
    if isolated_python_supervisor and not linux:
        raise ProcessTreeError('isolated_python_supervisor requires Linux')
    maximum_active_processes = _validate_maximum_active_processes(maximum_active_processes)
    if maximum_active_processes is not None and os.name != 'nt':
        raise ProcessTreeError('maximum_active_processes requires native Windows Job enforcement; no POSIX fallback')
    if linux:
        return _linux_launch(argv, cwd, stream, env=env,
            isolated_python_supervisor=isolated_python_supervisor, startup_deadline=startup_deadline)
    if os.name != 'nt':
        raise ProcessTreeError('no qualified process supervisor for this operating system')
    job = (_WindowsJob() if maximum_active_processes is None else
           _WindowsJob(maximum_active_processes=maximum_active_processes))
    process = None
    try:
        process = subprocess.Popen(argv, cwd=cwd, stdin=subprocess.DEVNULL,
                                   stdout=stream, stderr=subprocess.STDOUT,
                                   start_new_session=os.name == 'posix',
                                   creationflags=0x4 if job is not None else 0, env=env)
        if job is not None:
            job.assign(process)
            job.resume(process)
        return ProcessTree(process, job)
    except BaseException as original:
        # Assignment failure leaves the child suspended; no child code ran.
        cleanup_errors = []
        actions = []
        deadline = time.monotonic() + 5
        if process is not None:
            if job is not None:
                # Resume can fail after the initial thread already ran (for
                # example while closing its handle), so descendants need joining.
                actions.append(lambda: job.terminate_and_wait(deadline))
            actions.extend((lambda: process.kill() if process.poll() is None else None,
                            lambda: process.wait(timeout=_remaining(deadline))))
        if job is not None:
            actions.append(job.close)
        for action in actions:
            try:
                action()
            except BaseException as error:
                cleanup_errors.append(str(error))
        if cleanup_errors:
            raise ProcessTreeError('launch failed and writer cleanup is uncertain: '
                                   + '; '.join(cleanup_errors)) from original
        raise


if __name__ == '__main__':
    if len(sys.argv) < 6 or sys.argv[1] not in ('--supervise-linux', '--supervise-linux-isolated') or not sys.platform.startswith('linux'):
        raise SystemExit('private supervisor requires its complete internal invocation')
    if sys.argv[1] == '--supervise-linux-isolated':
        if len(sys.argv) < 7:
            raise SystemExit('private isolated supervisor requires its startup deadline')
        _linux_supervise(int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), sys.argv[6:], startup_deadline=float(sys.argv[5]))
    else:
        _linux_supervise(int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), sys.argv[5:])
