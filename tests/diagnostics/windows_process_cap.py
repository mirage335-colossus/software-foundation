"""Opt-in native Windows process-cap diagnostic (qualification unrun).

Opt in on native Windows x64 with -B and
a fresh FOUNDATION_PROCESS_CAP_DIAGNOSTIC_ROOT. Uses only isolated Python child
fixtures, never an SDK/compiler/provider. All files and uncertain owners remain
for inspection. This is not an executable producer or publication qualification.
"""
import sys
if not sys.dont_write_bytecode:
    raise RuntimeError('Start this opt-in diagnostic with -B before any helper import')

import ctypes
import hashlib
import json
import os
from pathlib import Path
import platform
import struct
import time
import unittest

ROOT = Path(__file__).resolve().parents[2]
EXPECTED_HELPER_SHA256 = '521fa923a4396afeda67b05efabb0c21f1161895fbe72f172d4d7dfc69c1496f'
if hashlib.sha256((ROOT / 'tools/process_tree.py').read_bytes()).hexdigest() != EXPECTED_HELPER_SHA256:
    raise RuntimeError('Shared helper differs from the exact cap candidate; refuse its import')
sys.path.insert(0, str(ROOT / 'tools'))
import process_tree

_BASE = None
_OWNERS, _STREAMS, _RETAINED, _CASES = [], [], [], {}


class BasicLimits(ctypes.Structure):
    _fields_ = [('process_time', ctypes.c_int64), ('job_time', ctypes.c_int64),
        ('flags', ctypes.c_uint32), ('min_working_set', ctypes.c_size_t),
        ('max_working_set', ctypes.c_size_t), ('active_limit', ctypes.c_uint32),
        ('affinity', ctypes.c_size_t), ('priority', ctypes.c_uint32), ('scheduling', ctypes.c_uint32)]


class IoCounters(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint64) for name in
        ('read_ops', 'write_ops', 'other_ops', 'read_bytes', 'write_bytes', 'other_bytes')]


class ExtendedLimits(ctypes.Structure):
    _fields_ = [('basic', BasicLimits), ('io', IoCounters), ('process_memory', ctypes.c_size_t),
        ('job_memory', ctypes.c_size_t), ('peak_process_memory', ctypes.c_size_t), ('peak_job_memory', ctypes.c_size_t)]


PARENT = r'''
import json,pathlib,subprocess,sys,time
folder = pathlib.Path(sys.argv[1]); count = int(sys.argv[2])
(folder/'ready').write_bytes(b'ready')
deadline = time.monotonic()+10
while not (folder/'go').is_file():
    if time.monotonic() >= deadline: raise RuntimeError('fixture release deadline')
    time.sleep(0.01)
observed = []
for index in range(count):
    marker = folder/('entered-'+str(index))
    body = 'import pathlib,sys;pathlib.Path(sys.argv[1]).write_bytes(b"entered");print("entered",flush=True)'
    child = None
    try:
        child = subprocess.Popen([sys.executable,'-I','-B','-S','-c',body,str(marker)],
            stdout=sys.stdout,stderr=sys.stderr)
        code = child.wait(timeout=5)
        observed.append({'outcome':'body-ran' if marker.is_file() else 'terminated-before-body',
            'returncode':code,'pid':child.pid})
    except OSError as error:
        observed.append({'outcome':'creation-denied','winerror':getattr(error,'winerror',None),
            'errno':error.errno})
    finally:
        if child is not None:
            if child.poll() is None:
                child.kill(); child.wait(timeout=5)
            # CPython's retained Popen process handle is a diagnostic-owned
            # reference. Closing it matters after overflow termination. This
            # exact fixture runtime is bound in original host/CI evidence.
            child._handle.Close()
(folder/'child-observations.json').write_text(json.dumps(observed),encoding='utf-8')
'''


def setUpModule():
    global _BASE
    if os.name != 'nt' or platform.system() != 'Windows' or platform.machine().casefold() not in ('amd64', 'x86_64') or struct.calcsize('P') != 8:
        raise RuntimeError('This opt-in candidate diagnostic requires native Windows x64')
    if not sys.dont_write_bytecode or sys.implementation.name != 'cpython':
        raise RuntimeError('Select actual CPython with startup -B for the original fixture')
    if hashlib.sha256((ROOT / 'tools/process_tree.py').read_bytes()).hexdigest() != EXPECTED_HELPER_SHA256:
        raise RuntimeError('Shared helper is not the exact released cap candidate; do not probe the old helper')
    if (ctypes.sizeof(BasicLimits), BasicLimits.active_limit.offset, ctypes.sizeof(ExtendedLimits)) != (64, 40, 144):
        raise RuntimeError('Windows x64 Job limit ABI differs')
    selected = os.environ.get('FOUNDATION_PROCESS_CAP_DIAGNOSTIC_ROOT')
    if not selected:
        raise RuntimeError('Select one fresh FOUNDATION_PROCESS_CAP_DIAGNOSTIC_ROOT')
    _BASE = Path(selected)
    if not _BASE.is_absolute() or '..' in _BASE.parts:
        raise RuntimeError('Diagnostic root must be explicitly absolute')
    _BASE.mkdir()  # fresh only; no reuse/replacement or recursive cleanup


def tearDownModule():
    if _BASE is None: return
    if _RETAINED or any(not owner.closed for owner in _OWNERS) or any(not stream.closed for stream in _STREAMS):
        raise process_tree.ProcessTreeError('Diagnostic writers/streams remain uncertain; preserve complete fixture tree')
    if hashlib.sha256((ROOT / 'tools/process_tree.py').read_bytes()).hexdigest() != EXPECTED_HELPER_SHA256:
        raise RuntimeError('Helper source changed during original native diagnostic')
    value = {'schema_version': 1, 'kind': 'windows-process-cap-observations-v1',
        'source_identity': {'tools/process_tree.py': EXPECTED_HELPER_SHA256,
            'tests/diagnostics/windows_process_cap.py': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},
        'runtime': {'python_path': sys.executable, 'python_version': platform.python_version(),
            'implementation': sys.implementation.name, 'system': platform.system(),
            'machine': platform.machine(), 'pointer_bits': struct.calcsize('P') * 8},
        'scope': 'exact-owned-job-active-process-limit-only', 'cases': _CASES,
        'per_user_quota': False, 'available_capacity_claim': False, 'release_qualification': False}
    raw = (json.dumps(value, sort_keys=True, indent=2) + '\n').encode('utf-8')
    path = _BASE / 'observations.json'
    with path.open('xb') as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    print('WINDOWS_PROCESS_CAP_OBSERVATIONS_SHA256=' + hashlib.sha256(raw).hexdigest(), flush=True)
    print('WINDOWS_PROCESS_CAP_OBSERVATIONS_PATH=' + str(path), flush=True)


class WindowsProcessCap(unittest.TestCase):
    def exercise(self, cap, attempts):
        folder = _BASE / self._testMethodName; folder.mkdir()
        stream = (folder / 'console.log').open('xb'); _STREAMS.append(stream)
        owner = None
        try:
            command = [sys.executable, '-I', '-B', '-S', '-c', PARENT, str(folder), str(attempts)]
            owner = process_tree.launch(command, folder, stream, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'),
                maximum_active_processes=cap)
            _OWNERS.append(owner)
            deadline = time.monotonic() + 10
            while not (folder / 'ready').is_file():
                if owner.poll() is not None or time.monotonic() >= deadline:
                    raise RuntimeError('Primary fixture did not reach its pre-attempt barrier')
                time.sleep(0.01)
            limits = ExtendedLimits()
            # Query the exact retained Job, never NULL/the caller's ambient Job.
            self.assertTrue(owner.job.api.QueryInformationJobObject(owner.job.handle, 9,
                ctypes.byref(limits), ctypes.sizeof(limits), None))
            self.assertEqual(limits.basic.flags & 0x2008, 0x2008)
            self.assertEqual(limits.basic.flags & 0x1800, 0)
            self.assertEqual(limits.basic.active_limit, cap)
            self.assertEqual(owner.job.process_ids(), [owner.process.pid])
            (folder / 'go').write_bytes(b'go')
            code = owner.wait(timeout=20)
            self.assertEqual(owner.finish(), code)
            total, active = owner.job.total(), owner.job.active()
            self.assertEqual(owner.job.process_ids(), [])
            owner.close(); stream.close()
            self.assertTrue(owner.closed); self.assertTrue(stream.closed)
            self.assertEqual(code, 0); self.assertEqual(active, 0)
            observed = json.loads((folder / 'child-observations.json').read_text(encoding='utf-8'))
            self.assertEqual(len(observed), attempts)
            facts = {'configured_limit': cap, 'queried_flags': limits.basic.flags,
                'attempts': observed, 'cumulative_total': total, 'active_after_finish': active,
                'process_tree_closed': owner.closed, 'stream_closed': stream.closed,
                'log_sha256': hashlib.sha256((folder / 'console.log').read_bytes()).hexdigest()}
            return folder, observed, facts
        except BaseException:
            if owner is None:
                _RETAINED.append((owner, stream, folder)); raise
            try:
                if not owner.closed: owner.terminate(timeout=5); owner.close()
                if not owner.closed: raise process_tree.ProcessTreeError('Owner closure unconfirmed')
                stream.close()
            except BaseException:
                _RETAINED.append((owner, stream, folder)); raise
            raise

    def test_primary_counts_toward_cap_and_child_body_is_blocked(self):
        folder, observed, facts = self.exercise(1, 1)
        self.assertIn(observed[0]['outcome'], ('creation-denied', 'terminated-before-body'))
        if 'returncode' in observed[0]: self.assertNotEqual(observed[0]['returncode'], 0)
        self.assertFalse((folder / 'entered-0').exists())
        _CASES[self._testMethodName] = facts

    def test_two_process_control_permits_same_child_body(self):
        folder, observed, facts = self.exercise(2, 1)
        self.assertEqual(observed[0]['outcome'], 'body-ran'); self.assertEqual(observed[0]['returncode'], 0)
        self.assertEqual((folder / 'entered-0').read_bytes(), b'entered')
        _CASES[self._testMethodName] = facts

    def test_cap_is_simultaneous_instead_of_cumulative(self):
        folder, observed, facts = self.exercise(2, 2)
        self.assertTrue(all(row['outcome'] == 'body-ran' and row['returncode'] == 0 for row in observed))
        self.assertGreaterEqual(facts['cumulative_total'], 3)
        self.assertTrue(all((folder / ('entered-' + str(index))).read_bytes() == b'entered' for index in range(2)))
        _CASES[self._testMethodName] = facts


if __name__ == '__main__': unittest.main()
