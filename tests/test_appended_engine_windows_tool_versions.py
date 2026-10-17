"""Windows version methods use fixed Source and inert original-byte fixtures."""
import copy
import ctypes
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import types
import unittest
from unittest.mock import patch

FAMILY = Path(__file__).resolve().parents[1] / 'tools/appended_engine_windows_dependency_support'


def load(name):
    p = FAMILY / name
    raw = p.read_bytes()
    value = types.ModuleType('_actual_source_fixture_' + p.stem)
    value.__file__ = str(p)
    exec(compile(raw, str(p), 'exec'), vars(value))
    return value


def forbidden(*args, **kwargs):
    raise AssertionError('Version method fixtures cannot launch programs or native libraries')


# The passive import itself is covered, as well as each individual method case.
with patch.object(subprocess, 'Popen', forbidden), \
        patch.object(ctypes, 'CDLL', forbidden), \
        patch.object(ctypes, 'WinDLL', forbidden, create=True):
    core = load('issuer.py')
    methods = core._methods()


def enc(value):
    return core.encoded(value)


def ref(path, number='1'):
    return {'path': path, 'sha256': number * 64}


def body(path, raw):
    return {'path': path, 'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw), 'mode': 0o644}


def case(role, raw_log):
    program = ref('C:/tools/' + core.PROGRAM_NAMES[role])
    command = {'program': program, 'argv': methods.argv(role, program['path']), 'cwd': 'C:/work',
        'environment': {'SystemRoot': 'C:/Windows', 'PATH': 'C:/tools', 'TEMP': 'C:/work/temp', 'TMP': 'C:/work/temp'}}
    collector = {'program': ref('C:/tools/python.exe', '9'), 'runtime_subject_sha256': 'a' * 64,
        'sources': [ref('C:/source/issuer.py', '6')], 'qualification': ref('C:/source/q.json', 'b')}
    runtime = {role: {'reference': body('C:/profiles/' + role + '.json', b'{}'),
                      'subject_sha256': 'd' * 64} for role in ('nmake', 'msbuild')}
    log = body('C:/work/logs/' + role + '.log', raw_log)
    job = {'owner': 'windows-job-v1', 'launch_intent_sha256': hashlib.sha256(enc(command)).hexdigest(),
        'image': program, 'launch_suspended': True, 'assigned_before_resume': True, 'breakaway_allowed': False,
        'kill_on_close': True, 'exit_code': 0, 'elapsed_milliseconds': 1, 'wall_limit_milliseconds': 100,
        'process_count': 1, 'process_limit': 8, 'peak_output_bytes': len(raw_log), 'output_limit_bytes': 65536,
        'active_processes_at_join': 0, 'streams_closed': True, 'join_completed': True, 'owner_closed': True}
    original = {'schema_version': 2, 'kind': core.O_KIND, 'target': core.TARGET, 'role': role,
        'method': methods.method_for(role), 'program': program, 'inventory_subject_sha256': 'c' * 64,
        'collector': collector, 'command': command, 'log': log, 'job': job,
        'output_subject_sha256': 'e' * 64, 'runtime_profiles': runtime}
    kwargs = {'role': role, 'program': program, 'inventory_subject_sha256': 'c' * 64,
        'collector': collector, 'command': command, 'log_raw': raw_log, 'log_reference': log,
        'runtime_profiles': runtime, 'method_inputs': None}
    return original, kwargs


class WindowsToolVersionTests(unittest.TestCase):
    def setUp(self):
        for guard in (patch.object(subprocess, 'Popen', forbidden),
                      patch.object(ctypes, 'CDLL', forbidden),
                      patch.object(ctypes, 'WinDLL', forbidden, create=True)):
            guard.start()
            self.addCleanup(guard.stop)

    def test_complete_source_dispatch_without_authority(self):
        self.assertEqual(core.missing_source(), [])
        self.assertIs(core._data_module('methods'), methods)
        self.assertFalse(core._ISSUED or core._LIVE or core._CLOSED)
        self.assertFalse(hasattr(core, '_OriginalInventoryReleases'))
        for fake in ({}, object.__new__(core.IssuedObservedVersions), core._fixture_result({})):
            with self.assertRaises(core.IssuerError):
                core.require_observed_versions(fake)

    def test_actual_new_console_methods_through_observation_wrapper(self):
        checker = core._data_module('observation_host')
        for role, raw, expected in (('compiler', b'19.1.7\n', '19.1.7'),
                                    ('linker', b'LLD 19.1.7\n', '19.1.7'),
                                    ('ninja', b'1.13.2\n', '1.13.2')):
            original, kwargs = case(role, raw); encoded = enc(original)
            value = checker.observation(encoded, hashlib.sha256(encoded).hexdigest(), **kwargs)
            self.assertEqual(value['version'], expected)
            changed = copy.deepcopy(original); changed['job']['image'] = ref('C:/tools/python.exe', '9')
            bad = enc(changed)
            with self.assertRaises(ValueError):
                checker.observation(bad, hashlib.sha256(bad).hexdigest(), **kwargs)
        self.assertFalse(core._ISSUED)

    def test_resource_subject_argv_and_exact_source_reuse(self):
        for role in ('archiver', 'resource_compiler', 'manifest_tool'):
            selected = {'path': 'C:/LLVM/bin/' + core.PROGRAM_NAMES[role], 'sha256': 'b' * 64, 'bytes': 512}
            argv = methods.resource_argv(role, 'C:/host/python.exe',
                'C:/source/resource/llvm_version_emitter.py', selected)
            self.assertEqual(argv, ['C:/host/python.exe', '-I', '-S',
                'C:/source/resource/llvm_version_emitter.py', '--role', role, '--program',
                selected['path'], '--sha256', selected['sha256'], '--bytes', '512'])
            self.assertEqual(methods.resource_refs(role)['codec']['path'], 'nmake_version.py')
            with self.assertRaises(ValueError):
                methods.argv(role, selected['path'])

    def test_public_method_exception_types_and_whole_output(self):
        with self.assertRaises(methods.MissingMethod):
            methods.source_refs('nmake')
        with self.assertRaises(methods.MissingMethod):
            methods.parse_resource_version('archiver', 'wrong', b'{}', None)
        with self.assertRaises(ValueError):
            methods.extract('compiler', methods.method_for('compiler'), b'19.1.7\nextra\n')
        self.assertEqual(methods.extract('ninja', methods.method_for('ninja'), b'1.13.2\r\n'), '1.13.2')


if __name__ == '__main__':
    sys.dont_write_bytecode = True
    unittest.main()
