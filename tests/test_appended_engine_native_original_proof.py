"""Inert fixed-original-proof consumer checks; never original observations.

Tiny synthetic source/runtime/package bytes are admitted only under explicitly
patched unit constants. No collector, runner, SDK, archive parser or tool runs.
"""
import copy
import builtins
from contextlib import ExitStack, contextmanager
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import types
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'tools/appended_engine_native_original_proof.py'
PIN = '1' * 64


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True,
                       allow_nan=False) + '\n').encode('ascii')


@contextmanager
def no_programs():
    with ExitStack() as stack:
        for name in ('subprocess.run', 'subprocess.Popen', 'subprocess.check_output', 'os.system'):
            stack.enter_context(mock.patch(name, side_effect=AssertionError('program execution forbidden')))
        yield


def load_consumer():
    module = types.ModuleType('_unit_native_original_proof')
    module.__file__ = str(SOURCE)
    exec(compile(SOURCE.read_bytes(), str(SOURCE), 'exec'), module.__dict__)
    return module


class SyntheticProof:
    """Complete tiny v4 receipt graph, with no real original facts or tools."""
    def __init__(self, root, api):
        self.root, self.api = Path(root), api
        self.root.chmod(0o755)
        self.meta = self.root / 'staged'
        self.input_root = self.root / 'original-input'
        self.body = self.input_root / 'body'
        self.opaque = self.root / 'opaque-output'
        self.source = self.root / 'source'
        self.runtime = self.root / 'runtime'
        self.keyring = self.root / 'keyring'
        self.workspace = self.root / 'historical-workspace'
        self.historical_metadata = self.root / 'historical-metadata-output'
        self.known_sources = {}
        self.source_files = {}
        for role, name in (('collector', 'collector.py'), ('runner', 'runner.py'), ('process_tree', 'process_tree.py')):
            raw = ('SYNTHETIC inert source for ' + role + '; never execute\n').encode('ascii')
            path = self.file(self.source / name, raw)
            self.known_sources[role] = {'sha256': digest(raw), 'bytes': len(raw)}
            self.source_files[role] = {'path': name, 'sha256': digest(raw), 'bytes': len(raw), 'mode': 0o644}
        self.programs = {}
        for role in ('controller', 'gpgv', 'dpkg_deb'):
            raw = ('SYNTHETIC non-executable program bytes ' + role + '\n').encode('ascii')
            path = self.file(self.runtime / 'bin' / role, raw, 0o755)
            self.programs[role] = {'path': str(path), 'sha256': digest(raw), 'version': 'SYNTHETIC-v1'}
        self.file(self.runtime / 'lib/runtime.data', b'SYNTHETIC complete runtime leaf\n')
        self.keyring_path = self.file(self.keyring / 'keyring.gpg', b'\xff\x00SYNTHETIC-binary-keyring\xfe')
        self.file(self.meta / 'keyring.gpg', self.keyring_path.read_bytes())
        inrelease = b'SYNTHETIC InRelease; deliberately not OpenPGP\n'
        release = b'SYNTHETIC Release; deliberately not Debian metadata\n'
        packages = b'SYNTHETIC Packages; deliberately not an index\n'
        self.file(self.meta / 'InRelease', inrelease)
        self.file(self.meta / 'Release', release)
        self.file(self.body / 'Packages', packages)
        self.fixed_inputs = {'InRelease': (digest(inrelease), len(inrelease)),
                             'Release': (digest(release), len(release)),
                             'Packages': (digest(packages), len(packages))}
        self.packages = copy.deepcopy(api.PACKAGES)
        for name, package in self.packages.items():
            raw = ('SYNTHETIC DEB opaque bytes ' + name + '\n').encode('ascii')
            self.file(self.body / Path(package['filename']).name, raw)
            package.update(sha256=digest(raw), bytes=len(raw))
            self.file(self.opaque / (name + '.tar'), ('SYNTHETIC non-TAR ' + name + '\n').encode('ascii'))
            self.file(self.meta / 'stanzas' / (name + '.paragraph'),
                      ('SYNTHETIC opaque stanza ' + name + '\n').encode('ascii'))
        self.file(self.meta / 'raw/gpgv.stdout', release)
        self.file(self.meta / 'raw/gpgv.stderr', b'SYNTHETIC opaque status; no interpretation\n')
        for role in ('gpgv', *self.packages):
            self.file(self.meta / 'raw' / ('worker-' + role + '.log'), b'SYNTHETIC supervisory log\n')
            if role != 'gpgv':
                self.file(self.meta / 'raw' / (role + '.stderr'), b'')
        self.file(self.meta / 'collector.stderr', b'')
        self.inventories = {
            'source': self.inventory(self.source, self.meta / 'authority/source-inventory.json'),
            'runtime': self.inventory(self.runtime, self.meta / 'authority/runtime-inventory.json'),
            'keyring': self.inventory(self.keyring, self.meta / 'authority/keyring-inventory.json'),
            'body': self.inventory(self.body, self.meta / 'body-inventory.json'),
            'opaque': self.inventory(self.opaque, self.meta / 'opaque-inventory.json')}
        self.source_closure = {'schema_version': 1,
            'kind': 'foundation-native-fixed-trixie-original-source-closure-v1',
            'scope': 'fixed-original-producer-source-only',
            'inventory': self.root_record('source', self.meta / 'authority'), 'files': self.source_files}
        environment = {'PATH': str(self.runtime / 'bin'), 'LANG': 'C.UTF-8', 'LC_ALL': 'C.UTF-8',
                       'TZ': 'UTC', 'SOURCE_DATE_EPOCH': '1'}
        self.policy = {'schema_version': 1, 'kind': 'foundation-native-fixed-trixie-original-launch-policy-v1',
            'scope': 'fixed-original-producer-launch-authority-only', 'source_closure_sha256': PIN,
            'programs': self.programs, 'keyring': self.blob('keyring', 'keyring.gpg', self.meta / 'authority'),
            'runtime_inventories': {role: self.root_record('runtime', self.meta / 'authority') for role in self.programs},
            'selection': {name: {'members': ['usr/lib/' + name + '/empty.rb', 'usr/bin/' + name],
                                  'link_origins': ['usr/bin/' + name + '-alias']} for name in self.packages},
            'environment': environment, 'limits': copy.deepcopy(api.LIMITS)}
        self.invocation = {'schema_version': 1, 'kind': 'foundation-native-fixed-trixie-original-invocation-v1',
            'producer': {}, 'input_root': str(self.input_root), 'metadata_output': str(self.historical_metadata),
            'opaque_output': str(self.opaque), 'workspace': str(self.workspace)}
        self.packets, children = {}, {}
        collector = str(self.source / 'collector.py')
        for role in ('gpgv', *self.packages):
            if role == 'gpgv':
                argv = [self.programs['gpgv']['path'], '--homedir', str(self.workspace / 'gnupg'),
                    '--keyring', str(self.keyring_path), '--status-fd=2', '--output', '-',
                    str(self.input_root / 'metadata/InRelease')]
                stdout = self.ref(self.meta / 'raw/gpgv.stdout')
                stdout_path = self.historical_metadata / 'raw/gpgv.stdout'
            else:
                argv = [self.programs['dpkg_deb']['path'], '--fsys-tarfile',
                    str(self.body / Path(self.packages[role]['filename']).name)]
                stdout = self.blob('opaque', role + '.tar')
                stdout_path = self.opaque / (role + '.tar')
            self.packets[role] = {'schema_version': 1, 'kind': 'foundation-native-fixed-trixie-worker-packet-v1',
                'role': role, 'producer': {}, 'argv': argv, 'environment': copy.deepcopy(environment),
                'cwd': str(self.workspace), 'stdout_path': str(stdout_path),
                'stderr_path': str(self.historical_metadata / 'raw' / (role + '.stderr')),
                'deadline_seconds': api.LIMITS['gpgv_seconds' if role == 'gpgv' else 'dpkg_seconds']}
            children[role] = {'argv': argv, 'environment': copy.deepcopy(environment), 'cwd': str(self.workspace),
                'returncode': 0, 'stdout': stdout, 'stderr': self.ref(self.meta / 'raw' / (role + '.stderr')),
                'ownership': self.ownership(), 'worker': {'packet': {},
                    'argv': [self.programs['controller']['path'], '-I', '-B', collector, '--fixed-worker',
                             role, '--packet', str(self.historical_metadata / ('worker-' + role + '.json'))],
                    'log': self.ref(self.meta / 'raw' / ('worker-' + role + '.log')),
                    'completion': self.completion(), 'ownership': self.ownership()}}
        self.proof = {'schema_version': 1, 'kind': 'foundation-native-fixed-trixie-original-proof-v1',
            'scope': 'fixed-three-package-original-regular-members-only', 'producer': {},
            'inputs': {'inrelease': self.ref(self.meta / 'InRelease'), 'retained_release': self.ref(self.meta / 'Release'),
                'keyring': self.ref(self.meta / 'keyring.gpg'), 'index': self.blob('body', 'Packages')},
            'authentication': {'gpgv': children['gpgv'], 'decoded_release': self.ref(self.meta / 'raw/gpgv.stdout'),
                'signing_fingerprints': list(api.SIGNERS), 'index_entry': {'path': 'main/binary-amd64/Packages',
                    'sha256': digest(packages), 'bytes': len(packages)}},
            'packages': {}, 'production_eligible': False, 'native_engine_execution': False, 'kernel_rebuild': False}
        for name, package in self.packages.items():
            self.proof['packages'][name] = {key: package[key] for key in ('name', 'source_package', 'version', 'architecture')}
            self.proof['packages'][name].update(archive=self.blob('body', Path(package['filename']).name),
                stanza=self.ref(self.meta / 'stanzas' / (name + '.paragraph')), reader=children[name],
                members={'usr/lib/' + name + '/empty.rb': {'sha256': digest(b''), 'size': 0, 'mode': 0o644},
                         'usr/bin/' + name: {'sha256': digest(b'SYNTHETIC selected member'), 'size': 25, 'mode': 0o755}},
                link_origins={'usr/bin/' + name + '-alias': {'type': 'symlink', 'target': name}})
        self.launch = {'schema_version': 1, 'kind': 'foundation-native-fixed-trixie-original-launch-v1',
            'scope': 'original-post-closure-producer-launch-only', 'producer': {}, 'invocation': {},
            'command': {'argv': [self.programs['controller']['path'], '-I', '-B', collector, '--collect-fixed',
                        '--invocation', str(self.input_root / 'metadata/invocation.json')],
                'environment': copy.deepcopy(environment), 'cwd': str(self.workspace), 'returncode': 0,
                'stdout': {}, 'stderr': self.ref(self.meta / 'collector.stderr'), 'ownership': self.ownership()},
            'completion': self.completion(), 'proof': {}, 'production_eligible': False,
            'native_engine_execution': False, 'kernel_rebuild': False}
        self.reseal()

    @staticmethod
    def ownership():
        return {'closed': True, 'descendants_closed': True, 'logs_closed': True}

    @staticmethod
    def completion():
        return {'finish_returncode': 0, 'fault': None, 'terminated': False, 'outliving': False}

    def file(self, path, raw, mode=0o644):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        for parent in (path.parent, *path.parent.parents):
            if parent == self.root.parent:
                break
            if parent == self.root or self.root in parent.parents:
                parent.chmod(0o755)
        path.write_bytes(raw)
        path.chmod(mode)
        return path

    def write(self, path, value):
        return self.file(path, canonical(value))

    def ref(self, path, base=None):
        path, base = Path(path), Path(base or self.meta)
        return {'path': path.relative_to(base).as_posix(), 'sha256': digest(path.read_bytes())}

    def inventory(self, root, path):
        files, modes, directories = {}, {}, []
        for leaf in sorted(root.rglob('*')):
            name = leaf.relative_to(root).as_posix()
            modes[name] = stat.S_IMODE(leaf.stat().st_mode)
            if leaf.is_dir():
                directories.append(name)
            else:
                files[name] = digest(leaf.read_bytes())
        self.write(path, {'files': files, 'directories': directories, 'modes': modes})
        return {'root': str(root), 'path': Path(path)}

    def root_record(self, name, base=None):
        record = self.inventories[name]
        return {'root': record['root'], 'inventory': self.ref(record['path'], base)}

    def blob(self, name, member, base=None):
        record = self.root_record(name, base)
        path = Path(record['root']) / member
        return dict(record, member=member, sha256=digest(path.read_bytes()), bytes=path.stat().st_size)

    def reseal(self):
        self.write(self.meta / 'authority/source-closure.json', self.source_closure)
        self.source_ref = self.ref(self.meta / 'authority/source-closure.json')
        self.policy['source_closure_sha256'] = self.source_ref['sha256']
        self.write(self.meta / 'authority/launch-policy.json', self.policy)
        self.policy_ref = self.ref(self.meta / 'authority/launch-policy.json')
        producer = {'source_closure': self.source_ref, 'launch_policy': self.policy_ref}
        self.invocation['producer'] = copy.deepcopy(producer)
        self.write(self.meta / 'invocation.json', self.invocation)
        for role, packet in self.packets.items():
            packet['producer'] = copy.deepcopy(producer)
            self.write(self.meta / ('worker-' + role + '.json'), packet)
            child = (self.proof['authentication']['gpgv'] if role == 'gpgv'
                     else self.proof['packages'][role]['reader'])
            child['worker']['packet'] = self.ref(self.meta / ('worker-' + role + '.json'))
        self.proof['producer'] = copy.deepcopy(producer)
        self.write(self.meta / 'proof.json', self.proof)
        proof_ref = dict(self.ref(self.meta / 'proof.json'), bytes=(self.meta / 'proof.json').stat().st_size,
                         kind=self.proof['kind'])
        # Collector uses proof_sha256, not the REF spelling sha256.
        self.write(self.meta / 'collector.stdout', {'proof_sha256': proof_ref['sha256'],
            'bytes': proof_ref['bytes'], 'kind': proof_ref['kind']})
        self.launch.update(producer=copy.deepcopy(producer), invocation=self.ref(self.meta / 'invocation.json'), proof=proof_ref)
        self.launch['command']['stdout'] = self.ref(self.meta / 'collector.stdout')
        self.write(self.meta / 'launch.json', self.launch)
        self.launch_ref = self.ref(self.meta / 'launch.json')

    def constants(self):
        return {'KNOWN_SOURCES': self.known_sources, 'FIXED_INPUTS': self.fixed_inputs, 'PACKAGES': self.packages}

    def rebind_proof_raw(self, raw):
        self.file(self.meta / 'proof.json', raw)
        self.launch['proof'] = {'path': 'proof.json', 'sha256': digest(raw), 'bytes': len(raw),
                                'kind': 'foundation-native-fixed-trixie-original-proof-v1'}
        self.write(self.meta / 'collector.stdout', {'proof_sha256': digest(raw), 'bytes': len(raw),
            'kind': 'foundation-native-fixed-trixie-original-proof-v1'})
        self.launch['command']['stdout'] = self.ref(self.meta / 'collector.stdout')
        self.write(self.meta / 'launch.json', self.launch)
        self.launch_ref = self.ref(self.meta / 'launch.json')


class CaptureLog:
    """Public-protocol wrapper; never inspects the caller's capture cache."""
    def __init__(self, inner, *, simulated_sizes=None):
        self.inner, self.simulated_sizes = inner, simulated_sizes or {}
        self.files, self.inventories, self.deadlines = [], [], 0

    def file(self, path, pin, role, *, maximum):
        self.files.append((str(path), pin, role, maximum))
        size = self.simulated_sizes.get(str(path))
        if size is not None and size > maximum:
            raise ValueError('SYNTHETIC size exceeds preflight remaining budget')
        result = self.inner.file(path, pin, role, maximum=maximum)
        if size is not None:
            result = dict(result, bytes=size)
        return result

    def bytes(self, path, *, maximum):
        return self.inner.bytes(path, maximum=maximum)

    def inventory(self, record, base, role):
        self.inventories.append(record['root'])
        return self.inner.inventory(record, base, role)

    def recheck(self):
        return self.inner.recheck()

    def check_deadline(self):
        self.deadlines += 1
        return self.inner.check_deadline()


class OriginalProofCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with no_programs():
            cls.api = load_consumer()
            previous, sys.dont_write_bytecode = sys.dont_write_bytecode, True
            old_path = list(sys.path)
            sys.path.insert(0, str(ROOT / 'tools'))
            try:
                import appended_engine_native_inputs
                cls.input_type = appended_engine_native_inputs.InputSet
            finally:
                sys.dont_write_bytecode, sys.path[:] = previous, old_path

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='synthetic-original-proof-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(no_programs())

    def fixture(self):
        return SyntheticProof(self.root, self.api)

    def consume(self, fixture, *, capture=None, source_pin=None, policy_pin=None):
        capture = capture or self.input_type()
        with mock.patch.multiple(self.api, **fixture.constants()):
            return self.api._diagnostic_original_proof(fixture.launch_ref, fixture.meta, capture,
                approved_source_closure_sha256=source_pin or fixture.source_ref['sha256'],
                approved_launch_policy_sha256=policy_pin or fixture.policy_ref['sha256'])

    def contradictory(self, fixture):
        with self.assertRaises(ValueError) as failure:
            self.consume(fixture)
        self.assertNotIsInstance(failure.exception, self.api.MissingInputs)


class OriginalAuthority(OriginalProofCase):
    def test_module_loading_imports_only_stdlib_never_any_producer_or_application_helper(self):
        raw = SOURCE.read_bytes()
        imported = []
        original = builtins.__import__
        def admitted(name, *args, **kwargs):
            imported.append(name)
            if name.split('.')[0] not in ('hashlib', 'json', 'pathlib', 're'):
                raise AssertionError('non-stdlib consumer dependency: ' + name)
            return original(name, *args, **kwargs)
        module = types.ModuleType('_isolated_original_proof_import_test')
        module.__file__ = str(SOURCE)
        with mock.patch('builtins.__import__', side_effect=admitted):
            exec(compile(raw, str(SOURCE), 'exec'), module.__dict__)
        self.assertTrue(callable(module._diagnostic_original_proof))
        self.assertEqual(set(imported), {'hashlib', 'json', 'pathlib', 're'})

    def test_absent_independent_authorities_fail_before_any_capture(self):
        for source, policy, expected in ((None, PIN, ('diagnostic-original-source-authority',)),
                (PIN, None, ('diagnostic-original-launch-authority',)),
                (None, None, ('diagnostic-original-source-authority', 'diagnostic-original-launch-authority'))):
            capture = mock.Mock()
            with self.subTest(source=source, policy=policy), self.assertRaises(self.api.MissingInputs) as failure:
                self.api._diagnostic_original_proof({'path': 'unread.json', 'sha256': PIN}, self.root, capture,
                    approved_source_closure_sha256=source, approved_launch_policy_sha256=policy)
            self.assertEqual(failure.exception.roles, expected)
            capture.file.assert_not_called()
            capture.bytes.assert_not_called()
            capture.inventory.assert_not_called()

    def test_wrong_independent_source_and_launch_pins_remain_named_missing_authority(self):
        fixture = self.fixture()
        for key, role in (('source_pin', 'diagnostic-original-source-authority'),
                          ('policy_pin', 'diagnostic-original-launch-authority')):
            with self.subTest(key=key), self.assertRaises(self.api.MissingInputs) as failure:
                self.consume(fixture, **{key: PIN})
            self.assertIn(role, failure.exception.roles)
            self.assertEqual(set(failure.exception.as_dict()), {'missing'})

    def test_unpatched_real_source_constants_do_not_admit_synthetic_original_authority(self):
        fixture = self.fixture()
        with mock.patch.multiple(self.api, FIXED_INPUTS=fixture.fixed_inputs, PACKAGES=fixture.packages), \
                self.assertRaises(ValueError):
            self.api._diagnostic_original_proof(fixture.launch_ref, fixture.meta, self.input_type(),
                approved_source_closure_sha256=fixture.source_ref['sha256'],
                approved_launch_policy_sha256=fixture.policy_ref['sha256'])

    def test_source_closure_requires_exact_three_known_roles_hash_lengths_and_inventory(self):
        mutations = {
            'source-bytes': lambda f: f.source_closure['files']['collector'].update(bytes=True),
            'source-string-bytes': lambda f: f.source_closure['files']['collector'].update(bytes='1'),
            'source-mode': lambda f: f.source_closure['files']['runner'].update(mode=0o666),
            'extra-source': lambda f: f.source_closure['files'].update(extra=f.source_closure['files']['runner'])}
        for name, mutate in mutations.items():
            fixture = self.fixture()
            mutate(fixture)
            fixture.reseal()
            with self.subTest(mutation=name):
                self.contradictory(fixture)

    def test_well_shaped_unknown_source_is_named_missing_compatible_implementation(self):
        fixture = self.fixture()
        fixture.source_closure['files']['collector']['sha256'] = PIN
        fixture.reseal()
        with self.assertRaises(self.api.MissingInputs) as failure:
            self.consume(fixture)
        self.assertIn('diagnostic-original-source-authority', failure.exception.roles)

    def test_unknown_source_policy_kinds_are_missing_authority_but_recognized_wrong_versions_contradict(self):
        for document, role in (('source_closure', 'diagnostic-original-source-authority'),
                               ('policy', 'diagnostic-original-launch-authority')):
            fixture = self.fixture()
            getattr(fixture, document)['kind'] = 'unrecognized-original-authority-kind'
            fixture.reseal()
            with self.subTest(document=document, kind='unknown'), self.assertRaises(self.api.MissingInputs) as failure:
                self.consume(fixture)
            self.assertEqual(failure.exception.roles, (role,))
            fixture = self.fixture()
            getattr(fixture, document)['schema_version'] = True
            fixture.reseal()
            with self.subTest(document=document, kind='recognized-wrong-version'):
                self.contradictory(fixture)

    def test_policy_rejects_old_creation_limit_wrong_environment_and_extra_program(self):
        mutations = {
            'old-limit': lambda f: f.policy['limits'].update(child_creations=12),
            'bool-limit': lambda f: f.policy['limits'].update(child_creations=True),
            'extra-limit': lambda f: f.policy['limits'].update(unbounded=1),
            'ambient-path': lambda f: f.policy['environment'].update(PATH='/ambient/bin'),
            'extra-env': lambda f: f.policy['environment'].update(LD_LIBRARY_PATH='/ambient'),
            'epoch': lambda f: f.policy['environment'].update(SOURCE_DATE_EPOCH='01'),
            'extra-program': lambda f: f.policy['programs'].update(shell=f.programs['controller'])}
        for name, mutate in mutations.items():
            fixture = self.fixture()
            mutate(fixture)
            fixture.reseal()
            with self.subTest(mutation=name):
                self.contradictory(fixture)


class OriginalPositive(OriginalProofCase):
    def test_existing_generated_runtime_inventory_document_role_remains_metadata(self):
        fixture = self.fixture()
        capture = self.input_type()
        record = fixture.root_record('runtime', fixture.meta / 'authority')
        capture.inventory(record, fixture.meta / 'authority', 'diagnostic-body-runtime-controller')
        inventory_path = str(fixture.meta / 'authority/runtime-inventory.json')
        document = next(item for item in capture.records if item['path'] == inventory_path)
        self.assertIn('diagnostic-body-runtime-controller-inventory', document['roles'])
        result = self.consume(fixture, capture=capture)
        self.assertEqual(set(result['packages']), set(fixture.packages))
        document = next(item for item in capture.records if item['path'] == inventory_path)
        self.assertIn('diagnostic-provenance-body-inventory', document['roles'])
        for item in capture.records:
            if str(fixture.runtime) + '/' in item['path']:
                self.assertTrue(all(not any(marker in role for marker in ('provenance', 'inventory', 'inspection'))
                                    for role in item['roles']))

    def test_complete_synthetic_graph_returns_exact4_normalized_keys_and_empty_member(self):
        fixture = self.fixture()
        result = self.consume(fixture)
        self.assertEqual(set(result), {'launch', 'proof', 'packages', 'external_inventories'})
        self.assertEqual(result['launch'], {'path': str(fixture.meta / 'launch.json'),
                                          'sha256': fixture.launch_ref['sha256']})
        self.assertEqual(result['proof'], dict(fixture.launch['proof'], path=str(fixture.meta / 'proof.json')))
        self.assertEqual(set(result['packages']), {'gperf', 'ruby3.3', 'libruby3.3'})
        for name, package in result['packages'].items():
            self.assertEqual(set(package), {'name', 'source_package', 'version', 'architecture', 'members', 'link_origins'})
            self.assertEqual(package['members']['usr/lib/' + name + '/empty.rb'],
                             {'sha256': digest(b''), 'size': 0, 'mode': 0o644})
            self.assertEqual(package['link_origins']['usr/bin/' + name + '-alias'], {'type': 'symlink', 'target': name})
        roots = [item['root'] for item in result['external_inventories']]
        self.assertEqual(set(roots), {str(fixture.source), str(fixture.runtime), str(fixture.keyring),
                                     str(fixture.body), str(fixture.opaque)})
        self.assertEqual(len(roots), 5, 'three runtime aliases must deduplicate identical complete roots')

    def test_staged_metadata_uses_original_argv_strings_without_reopening_old_paths(self):
        fixture = self.fixture()
        capture = CaptureLog(self.input_type())
        self.consume(fixture, capture=capture)
        forbidden = (str(fixture.input_root / 'metadata'), str(fixture.historical_metadata), str(fixture.workspace))
        self.assertFalse((fixture.input_root / 'metadata').exists())
        self.assertFalse(fixture.historical_metadata.exists())
        self.assertFalse(fixture.workspace.exists())
        self.assertTrue(capture.files)
        self.assertTrue(all(not any(path == old or path.startswith(old + '/') for old in forbidden)
                            for path, *_ in capture.files))
        self.assertGreater(capture.deadlines, 10)

    def test_binary_keyring_and_opaque_invalid_archives_are_hashed_without_parsing(self):
        fixture = self.fixture()
        with mock.patch('tarfile.open', side_effect=AssertionError('TAR parsing forbidden')), \
                mock.patch('zipfile.ZipFile', side_effect=AssertionError('archive parsing forbidden')):
            result = self.consume(fixture)
        self.assertEqual(set(result['packages']), set(fixture.packages))
        self.assertEqual((fixture.meta / 'keyring.gpg').read_bytes(), b'\xff\x00SYNTHETIC-binary-keyring\xfe')

    def test_consumer_writes_no_files_and_rechecks_caller_before_returning(self):
        fixture = self.fixture()
        snapshot = {path.relative_to(self.root).as_posix(): digest(path.read_bytes())
                    for path in self.root.rglob('*') if path.is_file()}
        capture = self.input_type()
        with mock.patch.object(capture, 'recheck', wraps=capture.recheck) as recheck:
            self.consume(fixture, capture=capture)
        recheck.assert_called_once_with()
        self.assertEqual(snapshot, {path.relative_to(self.root).as_posix(): digest(path.read_bytes())
                                   for path in self.root.rglob('*') if path.is_file()})

    def test_source_files_may_be0755_without_making_published_metadata_executable(self):
        fixture = self.fixture()
        (fixture.source / 'collector.py').chmod(0o755)
        fixture.source_closure['files']['collector']['mode'] = 0o755
        fixture.inventories['source'] = fixture.inventory(fixture.source, fixture.meta / 'authority/source-inventory.json')
        fixture.source_closure['inventory'] = fixture.root_record('source', fixture.meta / 'authority')
        fixture.reseal()
        result = self.consume(fixture)
        self.assertEqual(set(result), {'launch', 'proof', 'packages', 'external_inventories'})

    def test_case_distinct_source_ids_and_literal_link_target_are_data_not_opened_paths(self):
        fixture = self.fixture()
        selection = fixture.policy['selection']['gperf']
        selection['members'] += ['usr/lib/Case.rb', 'usr/lib/case.rb']
        facts = fixture.proof['packages']['gperf']['members']
        for name in ('usr/lib/Case.rb', 'usr/lib/case.rb'):
            facts[name] = {'sha256': digest(b''), 'size': 0, 'mode': 0o644}
        fixture.proof['packages']['gperf']['link_origins']['usr/bin/gperf-alias']['target'] = '../../never-opened-target'
        fixture.reseal()
        capture = CaptureLog(self.input_type())
        result = self.consume(fixture, capture=capture)
        self.assertIn('usr/lib/Case.rb', result['packages']['gperf']['members'])
        self.assertIn('usr/lib/case.rb', result['packages']['gperf']['members'])
        self.assertTrue(all('never-opened-target' not in path for path, *_ in capture.files))


class OriginalJoins(OriginalProofCase):
    def test_unknown_inventory_suffix_and_mixed_real_opaque_roles_are_not_metadata_exemptions(self):
        for roles in (('diagnostic-body-unreviewed-inventory',),
                      ('diagnostic-body-runtime-controller-inventory', 'diagnostic-body-runtime-controller')):
            fixture = self.fixture()
            capture = self.input_type()
            path = fixture.meta / 'authority/runtime-inventory.json'
            for role in roles:
                capture.file(path, digest(path.read_bytes()), role)
            with self.subTest(roles=roles), self.assertRaisesRegex(ValueError, 'opaque capture role'):
                self.consume(fixture, capture=capture)

    def test_closed_launch_and_proof_schema_and_false_flags_require_exact_types(self):
        mutations = {
            'launch-extra': lambda f: f.launch.update(verified=True),
            'proof-extra': lambda f: f.proof.update(ready=True),
            'launch-bool-version': lambda f: f.launch.update(schema_version=True),
            'proof-numeric-false': lambda f: f.proof.update(production_eligible=0),
            'launch-execution': lambda f: f.launch.update(native_engine_execution=True)}
        for name, mutate in mutations.items():
            fixture = self.fixture()
            mutate(fixture)
            fixture.reseal()
            with self.subTest(mutation=name):
                self.contradictory(fixture)

    def test_strict_json_rejects_duplicate_float_nonfinite_invalid_utf8_and_pointer_format(self):
        for raw in (b'{"schema_version":1,"schema_version":1}', b'{"schema_version":1.0}',
                    b'{"schema_version":NaN}', b'\xff'):
            fixture = self.fixture()
            fixture.rebind_proof_raw(raw)
            with self.subTest(raw=raw):
                self.contradictory(fixture)
        fixture = self.fixture()
        path = fixture.meta / 'collector.stdout'
        path.write_bytes(json.dumps(json.loads(path.read_bytes())).encode())
        fixture.launch['command']['stdout'] = fixture.ref(path)
        fixture.write(fixture.meta / 'launch.json', fixture.launch)
        fixture.launch_ref = fixture.ref(fixture.meta / 'launch.json')
        self.contradictory(fixture)

    def test_proof_pointer_and_launch_size_kind_hash_all_join_actual_bytes(self):
        for field, value in (('sha256', PIN), ('bytes', True), ('kind', 'wrong-proof')):
            fixture = self.fixture()
            fixture.launch['proof'][field] = value
            fixture.write(fixture.meta / 'launch.json', fixture.launch)
            fixture.launch_ref = fixture.ref(fixture.meta / 'launch.json')
            with self.subTest(field=field):
                self.contradictory(fixture)

    def test_collector_worker_and_child_argv_cannot_substitute_staged_paths_or_drop_isolation(self):
        mutations = {
            'collector-no-I': lambda f: f.launch['command']['argv'].remove('-I'),
            'collector-staged-invocation': lambda f: f.launch['command']['argv'].__setitem__(-1, str(f.meta / 'invocation.json')),
            'worker-staged-packet': lambda f: f.proof['authentication']['gpgv']['worker']['argv'].__setitem__(-1, str(f.meta / 'worker-gpgv.json')),
            'gpgv-extra': lambda f: f.proof['authentication']['gpgv']['argv'].append('--trust-anything'),
            'dpkg-other-package': lambda f: f.proof['packages']['gperf']['reader']['argv'].__setitem__(-1, '/foreign/archive.deb')}
        for name, mutate in mutations.items():
            fixture = self.fixture()
            mutate(fixture)
            fixture.reseal()
            with self.subTest(mutation=name):
                self.contradictory(fixture)

    def test_ownership_completion_and_returncodes_reject_open_or_numeric_flags(self):
        mutations = {
            'collector-open': lambda f: f.launch['command']['ownership'].update(logs_closed=False),
            'collector-return-bool': lambda f: f.launch['command'].update(returncode=False),
            'completion-numeric': lambda f: f.launch['completion'].update(terminated=0),
            'worker-outliving': lambda f: f.proof['authentication']['gpgv']['worker']['completion'].update(outliving=True),
            'child-open': lambda f: f.proof['packages']['ruby3.3']['reader']['ownership'].update(descendants_closed=False),
            'worker-open': lambda f: f.proof['packages']['gperf']['reader']['worker']['ownership'].update(closed=False)}
        for name, mutate in mutations.items():
            fixture = self.fixture()
            mutate(fixture)
            fixture.reseal()
            with self.subTest(mutation=name):
                self.contradictory(fixture)

    def test_worker_packet_exact_role_environment_paths_and_deadline_join_child(self):
        mutations = {
            'role': lambda f: f.packets['gperf'].update(role='ruby3.3'),
            'environment': lambda f: f.packets['gpgv']['environment'].update(PATH='/ambient'),
            'deadline': lambda f: f.packets['gpgv'].update(deadline_seconds=300),
            'stdout': lambda f: f.packets['gpgv'].update(stdout_path=str(f.meta / 'raw/gpgv.stdout')),
            'stderr': lambda f: f.packets['ruby3.3'].update(stderr_path='/foreign/stderr'),
            'cwd': lambda f: f.packets['libruby3.3'].update(cwd='/foreign/workspace')}
        for name, mutate in mutations.items():
            fixture = self.fixture()
            mutate(fixture)
            fixture.reseal()
            with self.subTest(mutation=name):
                self.contradictory(fixture)

    def test_package_index_signers_member_sets_facts_and_literal_links_remain_fixed(self):
        mutations = {
            'package-source': lambda f: f.proof['packages']['gperf'].update(source_package='not-gperf'),
            'version': lambda f: f.proof['packages']['ruby3.3'].update(version='future'),
            'index-hash': lambda f: f.proof['authentication']['index_entry'].update(sha256=PIN),
            'signer': lambda f: f.proof['authentication']['signing_fingerprints'].__setitem__(0, 'A' * 40),
            'missing-member': lambda f: f.proof['packages']['gperf']['members'].pop('usr/bin/gperf'),
            'extra-member': lambda f: f.proof['packages']['gperf']['members'].update(extra={'sha256': PIN, 'size': 0, 'mode': 0o644}),
            'empty-sha': lambda f: f.proof['packages']['gperf']['members']['usr/lib/gperf/empty.rb'].update(sha256=PIN),
            'bool-size': lambda f: f.proof['packages']['gperf']['members']['usr/bin/gperf'].update(size=True),
            'privileged-mode': lambda f: f.proof['packages']['gperf']['members']['usr/bin/gperf'].update(mode=0o4755),
            'oversized-member': lambda f: f.proof['packages']['gperf']['members']['usr/bin/gperf'].update(size=f.api.LIMITS['member_bytes'] + 1),
            'link-type': lambda f: f.proof['packages']['gperf']['link_origins']['usr/bin/gperf-alias'].update(type='regular')}
        for name, mutate in mutations.items():
            fixture = self.fixture()
            mutate(fixture)
            fixture.reseal()
            with self.subTest(mutation=name):
                self.contradictory(fixture)

    def test_actual_body_and_keyring_tampering_never_returns_partial_success(self):
        for name in ('Packages', Path(self.api.PACKAGES['gperf']['filename']).name):
            fixture = self.fixture()
            path = fixture.body / name
            path.write_bytes(path.read_bytes() + b'ALTERED')
            with self.subTest(body=name):
                self.contradictory(fixture)
        fixture = self.fixture()
        fixture.keyring_path.write_bytes(b'ALTERED')
        self.contradictory(fixture)

    def test_missing_proof_and_raw_stream_preserve_precise_missing_capture_roles(self):
        for relative, role in (('proof.json', 'diagnostic-provenance-proof'),
                ('raw/gpgv.stderr', 'diagnostic-provenance-gpgv-status-stderr')):
            fixture = self.fixture()
            (fixture.meta / relative).unlink()
            with self.subTest(relative=relative), self.assertRaises(ValueError) as failure:
                self.consume(fixture)
            self.assertEqual(failure.exception.roles, (role,))
            self.assertEqual(tuple(item['role'] for item in failure.exception.missing), (role,))

    def test_published_metadata0755_is_a_mode_contradiction(self):
        fixture = self.fixture()
        (fixture.meta / 'launch.json').chmod(0o755)
        self.contradictory(fixture)

    def test_opaque_body_cannot_acquire_metadata_role_even_from_callers_previous_capture(self):
        fixture = self.fixture()
        capture = self.input_type()
        path = fixture.body / 'Packages'
        capture.file(path, digest(path.read_bytes()), 'diagnostic-provenance-source-closure')
        with self.assertRaises(ValueError):
            self.consume(fixture, capture=capture)

    def test_caller_cached_opaque_source_or_keyring_leaf_cannot_become_route_metadata(self):
        for name in ('source', 'keyring'):
            fixture = self.fixture()
            path = fixture.source / 'collector.py' if name == 'source' else fixture.keyring_path
            capture = self.input_type()
            capture.file(path, digest(path.read_bytes()), 'diagnostic-body-runtime-controller')
            with self.subTest(leaf=name), self.assertRaises(ValueError):
                self.consume(fixture, capture=capture)

    def test_source_and_opaque_runtime_roots_must_be_disjoint(self):
        fixture = self.fixture()
        fixture.policy['runtime_inventories']['controller'] = fixture.root_record('source', fixture.meta / 'authority')
        fixture.reseal()
        self.contradictory(fixture)

    def test_global_selected_member_bytes_are_bounded_across_all_packages(self):
        fixture = self.fixture()
        for package in fixture.proof['packages'].values():
            for fact in package['members'].values():
                fact.update(size=self.api.LIMITS['member_bytes'])
        fixture.reseal()
        self.contradictory(fixture)

    def test_selected_member_ids_reject_traversal_backslash_and_duplicate_policy_names(self):
        for name in ('../escape', '/absolute', 'usr//double', 'usr/./dot', 'usr\\bad'):
            fixture = self.fixture()
            fixture.policy['selection']['gperf']['members'][0] = name
            fixture.reseal()
            with self.subTest(name=name):
                self.contradictory(fixture)
        fixture = self.fixture()
        fixture.policy['selection']['gperf']['members'].append('usr/bin/gperf')
        fixture.reseal()
        self.contradictory(fixture)

    def test_program_must_be_an_actual0755_leaf_inside_named_complete_runtime(self):
        fixture = self.fixture()
        Path(fixture.programs['controller']['path']).chmod(0o644)
        self.contradictory(fixture)
        fixture = self.fixture()
        fixture.policy['programs']['controller']['path'] = str(fixture.source / 'collector.py')
        fixture.reseal()
        self.contradictory(fixture)

    def test_runtime_budget_is_preflighted_even_when_leaf_was_already_captured(self):
        fixture = self.fixture()
        leaf = fixture.runtime / 'lib/runtime.data'
        inner = self.input_type()
        inner.file(leaf, digest(leaf.read_bytes()), 'diagnostic-body-runtime-controller')
        capture = CaptureLog(inner, simulated_sizes={str(leaf): self.api.LIMITS['unique_opaque_body_bytes']})
        with self.assertRaisesRegex(ValueError, 'SYNTHETIC size exceeds preflight remaining budget'):
            self.consume(fixture, capture=capture)
        self.assertNotIn(str(fixture.runtime), capture.inventories,
                         'complete runtime walker must not run before stricter leaf budget preflight')
        self.assertTrue(any(path == str(leaf) and maximum < self.api.LIMITS['unique_opaque_body_bytes']
                            for path, _, _, maximum in capture.files))

    def test_repeated_runtime_aliases_charge_the_same_canonical_leaf_once(self):
        fixture = self.fixture()
        leaf = fixture.runtime / 'lib/runtime.data'
        # The protocol double reports an admitted 600MiB leaf without allocating
        # it; a second charge would exceed the unchanged 1GiB route budget.
        capture = CaptureLog(self.input_type(), simulated_sizes={str(leaf): 600 * 1024 * 1024})
        result = self.consume(fixture, capture=capture)
        self.assertEqual(sum(item['root'] == str(fixture.runtime) for item in result['external_inventories']), 1)
        self.assertEqual(sum(root == str(fixture.runtime) for root in capture.inventories), 1)

    def test_raw_stream_per_role_cap_is_enforced_before_large_read(self):
        fixture = self.fixture()
        path = fixture.meta / 'collector.stdout'
        path.write_bytes(b' ' * (self.api.LIMITS['collector_pointer_bytes'] + 1))
        fixture.launch['command']['stdout'] = fixture.ref(path)
        fixture.write(fixture.meta / 'launch.json', fixture.launch)
        fixture.launch_ref = fixture.ref(fixture.meta / 'launch.json')
        self.contradictory(fixture)

    def test_active_deadline_failure_propagates_before_admission(self):
        fixture = self.fixture()
        capture = self.input_type()
        with mock.patch.object(capture, 'check_deadline', side_effect=ValueError('SYNTHETIC deadline')):
            with self.assertRaisesRegex(ValueError, 'SYNTHETIC deadline'):
                self.consume(fixture, capture=capture)

    def test_final_recheck_failure_cannot_return_normalized_success(self):
        fixture = self.fixture()
        capture = self.input_type()
        with mock.patch.object(capture, 'recheck', side_effect=ValueError('SYNTHETIC final input changed')):
            with self.assertRaisesRegex(ValueError, 'SYNTHETIC final input changed'):
                self.consume(fixture, capture=capture)
