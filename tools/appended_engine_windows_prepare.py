#!/usr/bin/env python3
"""Explicit POSIX Windows source preparation; never a Linux/SDK build fallback.

The byte writer, Windows R/S/B constructor and bounded metadata controller are
implemented separately from admission. Original supplier projection/proof data,
dependency source declarations and the POSIX controller runtime still require
their released semantic admissions. Missing code is reported before any output
or program launch; a candidate document or caller boolean cannot supply it.
"""
from __future__ import annotations

import argparse
import copy
from functools import wraps
import importlib
import math
import os
from pathlib import Path
import re
import stat
import sys
import time

import appended_engine_manifest as manifest
import appended_engine_native_actions_contract as actions
import appended_engine_native_inputs as native_source
import appended_engine_windows_contract as contract
import appended_engine_windows_handoff as handoff
import process_tree
from dependency_archive import PathInventory

CONTRACT_SHA256 = 'ef065be8c502211ea748dbfc1732b6ca02b9210ee78ed74901f2b6ca6869d5d8'
KIND = 'foundation-native-engine-windows-posix-prepare-selection-v1'
SOURCE_KIND = 'foundation-native-engine-windows-prepared-source-metadata-v1'
PREPARED_KIND = 'foundation-native-engine-windows-prepared-inputs-v1'
SCOPE = 'windows-posix-source-metadata-preparation-only'
IDENTITY_PATH = 'native-inputs/toolchain-identity.json'
NATIVE_INPUTS_PATH = 'native-inputs/native-windows-inputs.json'
DEPENDENCY_PATH = 'native-inputs/dependency-producer-receipt.json'
MAX_DOCUMENT = handoff.MAX_DOCUMENT
MAX_FILE = 8 * 1024 * 1024 * 1024
MAX_BYTES = 32 * 1024 * 1024 * 1024
MAX_FILES = 65536
MAX_OUTPUT_FILES = 524288
MAX_DEPTH = 64
LIMITS = {'prepare_seconds': 86400, 'generator_seconds': 86400, 'cleanup_seconds': 300,
    'maximum_processes': 1024, 'maximum_output_bytes': 64 * 1024 * 1024 * 1024,
    'maximum_log_bytes': 64 * 1024 * 1024}
METADATA_REFS = ('source_projection', 'native_inputs', 'dependency_producer_receipt',
                 'typed_toolchain_identity', 'metadata_controller_runtime')
NATIVE_HELPERS = tuple(sorted(set(manifest.HELPERS) | {
    'tools/appended_engine_document_contract.py', 'tools/appended_engine_editor_contract.py',
    'tools/appended_engine_native_actions_contract.py'}))
FALSE_FACTS = ('build', 'production_eligible', 'engine_execution',
               'native_runtime_qualified', 'kernel_rebuild')
MissingInputs = contract.MissingInputs
encoded = contract.encoded
_PREPARATIONS = {}
_UNCERTAIN = []
_RUNTIMES = {}
_RESOURCES = {}
_BOUND_RUNS = {}
_OUTPUTS = {}
# The shared owners release exact implementations separately. Neither symbols
# nor caller status fields may activate a controller against drifting source.
RUNTIME_SEAM_SHA256 = '973fdddefa5a4cccc0190fdc4c4f6f1ba6afd693b17d70d928e428c4060eb706'
PROCESS_TREE_SEAM_SHA256 = '521fa923a4396afeda67b05efabb0c21f1161895fbe72f172d4d7dfc69c1496f'
SDK_ENVIRONMENT_SHA256 = 'f69fd947603ee6cb7ecd6633a9565aab8aa7336e3e96569ef219109763f26b9e'


def _missing(role, path, reason):
    return MissingInputs([{'role': role, 'path': os.fspath(path), 'reason': reason}])


def _replay():
    return importlib.import_module('appended_engine_windows_source_replay')


def _absolute(value):
    path = handoff._absolute(value)
    if os.name != 'posix':
        raise ValueError('Windows source preparation requires a qualified POSIX producer')
    return path


def _reference(value, label):
    contract.fields(value, ('path', 'sha256'), label)
    _absolute(value['path'])
    contract.pin(value['sha256'], label)
    return copy.deepcopy(value)


def _metadata(reference, role, *, document=True):
    reference = _reference(reference, role)
    try:
        raw = handoff._read(reference['path'])
    except FileNotFoundError as error:
        raise _missing(role, reference['path'], 'explicit original metadata is absent') from error
    if handoff.digest(raw) != reference['sha256']:
        raise ValueError('Original Windows preparation metadata pin differs: ' + role)
    return raw, handoff._document(raw) if document else None


def validate_selection(value):
    contract.fields(value, ('schema_version', 'kind', 'target', 'source_catalogue',
        'repository_root', 'source_projection', 'bindings', 'native_inputs',
        'dependency_producer_receipt', 'typed_toolchain_identity',
        'metadata_controller_runtime', 'phase_limits'), 'Windows POSIX preparation selection')
    if (type(value['schema_version']) is not int or value['schema_version'] != 1 or
            value['kind'] != KIND or value['target'] != contract.TARGET or
            value['source_catalogue'] != contract.CATALOGUE):
        raise ValueError('Windows preparation target/current source catalogue differs')
    _absolute(value['repository_root'])
    for role in METADATA_REFS:
        _reference(value[role], role)
    _replay().validate_bindings(value['bindings'], relative=False)
    contract.fields(value['phase_limits'], LIMITS, 'Windows preparation finite limits')
    for name, maximum in LIMITS.items():
        if type(value['phase_limits'][name]) is not int or not 1 <= value['phase_limits'][name] <= maximum:
            raise ValueError('Windows preparation limit is outside its finite bound: ' + name)
    return copy.deepcopy(value)


def _source_api(module, expected, role):
    if expected is None:
        raise _missing(role, module.__name__, 'the exact source implementation has not been released')
    contract.pin(expected, role)
    if handoff.digest(handoff._read(str(Path(module.__file__).absolute()))) != expected:
        raise ValueError('Released controller source identity differs: ' + role)
    return module


def _runtime_api():
    return _source_api(native_source, RUNTIME_SEAM_SHA256,
                       'posix-metadata-controller-runtime-admission')


def _process_api():
    return _source_api(process_tree, PROCESS_TREE_SEAM_SHA256,
                       'posix-metadata-controller-resource-adapter')


def _require_clean_controller_environment():
    module = importlib.import_module('sdk_environment')
    _source_api(module, SDK_ENVIRONMENT_SHA256, 'posix-metadata-controller-environment')
    module.require_clean()


def _observe_current_python():
    """Implementation-owned observations, never supplied by runtime metadata."""
    return {'path': sys.executable, 'version': tuple(sys.version_info[:3]),
        'implementation': sys.implementation.name, 'prefix': sys.prefix,
        'base_prefix': sys.base_prefix}


def _handle(cls, registry, owner):
    token = object.__new__(cls)
    registry[token] = owner
    return token


def _runtime(value):
    owner = _RUNTIMES.get(value) if type(value) is _ControllerRuntime else None
    if owner is None:
        raise _missing('posix-metadata-controller-runtime-admission', 'runtime',
                       'an actual live issued Python runtime owner is required')
    owner.live()
    return owner


class _ControllerRuntime:
    __slots__ = ()

    def __new__(cls):
        raise TypeError('Controller runtimes are issued only by original input admission')

    def python_reference(self):
        owner = _runtime(self)
        return {key: owner.program[key] for key in ('path', 'sha256')}

    def recheck(self):
        _runtime(self).recheck()

    def environment(self, workspace):
        return _runtime(self).environment(workspace)

    def protected_paths(self):
        owner = _runtime(self)
        paths = set(owner.inputs.protected_paths)
        for item in owner.inventories.values():
            root = Path(item['root'])
            paths.add(root)
            paths.update(root / name for name in item['directories'])
        return tuple(sorted(paths))

    def close(self):
        owner = _RUNTIMES.get(self)
        if owner is not None:
            if any(bound.runtime is owner and bound.phase in ('running', 'uncertain')
                   for bound in _BOUND_RUNS.values()):
                raise process_tree.ProcessTreeError('Metadata writers remain; retain the actual runtime capture')
            owner.close()
            _RUNTIMES.pop(self, None)


class _RuntimeCapture:
    def __init__(self, api, reference, raw, deadline):
        self.reference, self.raw = copy.deepcopy(reference), raw
        self.deadline = min(time.monotonic() + LIMITS['prepare_seconds'],
                            math.inf if deadline is None else deadline)
        self.closed = self.failed = False
        self.inputs = api.InputSet()
        self.inputs.deadline = self.deadline
        self.inputs.file(Path(reference['path']), reference['sha256'],
                         'metadata-controller-wrapper', maximum=MAX_DOCUMENT)
        if self.inputs.bytes(Path(reference['path'])) != raw:
            raise ValueError('Controller wrapper differs from its original captured bytes')
        value = handoff._document(raw)
        contract.fields(value, ('schema_version', 'kind', 'python', 'inventories',
                               'runtime_facts', 'supervisor'), 'POSIX metadata Python runtime')
        if (type(value['schema_version']) is not int or value['schema_version'] != 1 or
                value['kind'] != 'foundation-posix-metadata-python-runtime-v1'):
            raise ValueError('Original POSIX metadata Python runtime kind differs')
        specs = value['inventories']
        if type(specs) is not dict or not 1 <= len(specs) <= 64:
            raise ValueError('Explicit finite complete Python inventories are required')
        base = Path(reference['path']).parent
        self.inventories = {}
        for name, item in sorted(specs.items()):
            if '/' in manifest.path_name(name):
                raise ValueError('Python inventory names must be one component')
            self.inventories[name] = self.inputs.inventory(item, base, 'metadata-python-' + name)
        self.program = api._program(value['python'], self.inventories, self.inputs,
                                    'metadata-controller-python')
        api._version(self.program['version'], (3, 9, 0), 'Python')
        facts = self.inputs.document(value['runtime_facts'], base, 'metadata-python-runtime-facts')
        self.facts = api._interpreter_runtime_facts(facts, self.program, self.inventories,
            (('json/__init__.py',), ('hashlib.py',), ('pathlib.py', 'pathlib/__init__.py')),
            required_inventory=None, external=True)
        self.supervisor = _reference(value['supervisor'], 'metadata-controller-supervisor')
        if self.supervisor['path'] != str(Path(process_tree.__file__).absolute()):
            raise ValueError('Selected supervisor differs from the actual process owner source')
        self.inputs.file(Path(self.supervisor['path']), self.supervisor['sha256'],
                         'metadata-controller-supervisor', maximum=MAX_DOCUMENT)
        self.current = self.observe()
        _require_clean_controller_environment()
        self.recheck()

    def live(self):
        if self.closed or self.failed:
            raise ValueError('Controller runtime is failed or closed')
        if time.monotonic() >= self.deadline:
            raise ValueError('Controller runtime exceeded its original deadline')

    def observe(self):
        self.live()
        observed = _observe_current_python()
        contract.fields(observed, ('path', 'version', 'implementation', 'prefix', 'base_prefix'),
                        'actual controller Python observation')
        match = re.fullmatch(r'(\d+)\.(\d+)(?:\.(\d+))?(?:[-+][A-Za-z0-9._-]+)?',
                             self.program['version'])
        version = tuple(int(part or 0) for part in match.groups()) if match else None
        if (_absolute(observed['path']) != Path(self.program['path']) or
                type(observed['version']) is not tuple or observed['version'] != version or
                type(observed['implementation']) is not str or not observed['implementation']):
            raise ValueError('Selected Python differs from the actual supervisor interpreter')
        names = self.facts['runtime_inventories']
        for key in ('prefix', 'base_prefix'):
            prefix = _absolute(observed[key])
            if not any(prefix == Path(self.inventories[name]['root']) or
                Path(self.inventories[name]['root']) in prefix.parents and
                prefix.relative_to(self.inventories[name]['root']).as_posix() in self.inventories[name]['directories']
                for name in names):
                raise ValueError('Actual Python prefix lies outside its complete retained runtime')
        return copy.deepcopy(observed)

    def recheck(self):
        self.live()
        try:
            self.inputs.recheck()
            if self.observe() != self.current:
                raise ValueError('Actual controller Python changed during its owned lifetime')
            _require_clean_controller_environment()
            self.live()
        except BaseException:
            self.failed = True
            raise

    def environment(self, workspace):
        self.recheck()
        root = _absolute(os.fspath(workspace))
        # The bound runner separately proves this is its actual private root.
        # No ambient PATH/PYTHONPATH/HOME/loader state enters either child.
        return {'LANG': 'C', 'LC_ALL': 'C', 'TZ': 'UTC',
                'TMPDIR': str(root), 'TEMP': str(root), 'TMP': str(root)}

    def close(self):
        self.closed = True


def _controller_runtime_admission(reference, raw, *, deadline=None):
    api = _runtime_api()
    reference = _reference(reference, 'metadata-controller-runtime')
    if deadline is not None and (type(deadline) not in (int, float) or
            not math.isfinite(deadline) or deadline <= time.monotonic()):
        raise ValueError('Controller runtime requires a live finite original deadline')
    if type(raw) is not bytes or len(raw) > MAX_DOCUMENT or handoff.digest(raw) != reference['sha256']:
        raise ValueError('Controller runtime requires original independently pinned bytes')
    owner = _RuntimeCapture(api, reference, raw, deadline)
    return _handle(_ControllerRuntime, _RUNTIMES, owner)


def _isolated_startup_admission(runtime):
    runtime.live()
    if not sys.platform.startswith('linux'):
        raise _missing('posix-metadata-controller-isolated-startup-layout', runtime.program['path'],
                       'the released isolated supervisor protocol supports Linux only')
    for name in runtime.facts['search_paths']:
        if _runtime_location(runtime, _absolute(name)) != 'directory':
            raise ValueError('Original isolated Python search roots require complete captured directories')


def _runtime_location(runtime, path):
    """Classify a path only inside original complete captured inventories."""
    absent = False
    for name in runtime.facts['runtime_inventories']:
        item = runtime.inventories[name]
        root = Path(item['root'])
        if path == root:
            return 'directory'
        if root not in path.parents:
            continue
        relative = path.relative_to(root).as_posix()
        if relative in item['files']:
            return 'file'
        if relative in item['directories']:
            return 'directory'
        if path.parent == root or path.parent.relative_to(root).as_posix() in item['directories']:
            absent = True
    return 'absent' if absent else None


def _validate_supervisor_startup(runtime, observation):
    """Join the actual pending owner's child observation before its single GO.

    This function returns no authority. The real process owner additionally
    requires the same observation object it issued, preventing copied facts
    from releasing another pending child.
    """
    runtime.live()
    expected_flags = tuple((name, 1) for name in ('isolated', 'ignore_environment',
        'no_user_site', 'no_site', 'dont_write_bytecode'))
    if (type(observation.pid) is not int or observation.pid <= 0 or
            type(observation.parent_pid) is not int or observation.parent_pid != os.getpid() or
            _absolute(observation.executable) != Path(runtime.program['path']) or
            _absolute(observation.executable_realpath) != Path(runtime.program['path']) or
            type(observation.version_info) is not tuple or
            any(type(part) is not int for part in observation.version_info) or
            observation.version_info != runtime.current['version'] or
            observation.implementation != runtime.current['implementation'] or
            _absolute(observation.helper_path) != Path(runtime.supervisor['path']) or
            type(observation.flags) is not tuple or
            any(type(pair) is not tuple or len(pair) != 2 or type(pair[1]) is not int
                for pair in observation.flags) or
            observation.flags != expected_flags or observation.dont_write_bytecode is not True):
        raise ValueError('Actual isolated supervisor differs from its admitted Python/source/flags')
    prefixes = tuple(_absolute(getattr(observation, name))
        for name in ('prefix', 'base_prefix', 'exec_prefix', 'base_exec_prefix'))
    if any(_runtime_location(runtime, path) != 'directory' for path in prefixes):
        raise ValueError('Actual isolated Python prefix is outside its complete retained runtime')
    platlibdir = manifest.path_name(observation.platlibdir)
    if '/' in platlibdir:
        raise ValueError('Actual Python platform library directory must be one component')
    paths = observation.sys_path
    if type(paths) is not tuple or not paths or any(type(value) is not str for value in paths):
        raise ValueError('Actual isolated Python requires a complete ordered search-path observation')
    directories, seen = [], set()
    zip_name = 'python' + ''.join(str(part) for part in runtime.current['version'][:2]) + '.zip'
    zip_parents = {prefix / name for prefix in prefixes for name in ('lib', platlibdir)}
    for value in paths:
        path = _absolute(value)
        if str(path) != value or value in seen:
            raise ValueError('Actual isolated Python search paths contain aliases or duplicates')
        seen.add(value)
        location = _runtime_location(runtime, path)
        if location == 'directory':
            directories.append(value)
        elif (path.name == zip_name and path.parent in zip_parents and
                location in ('file', 'absent') and
                _runtime_location(runtime, path.parent) == 'directory'):
            # CPython includes this standard zip candidate even when absent.
            # A complete captured parent inventory proves that absence; an
            # existing ordinary zip is independently pinned by that inventory.
            continue
        else:
            raise ValueError('Actual isolated Python search path lacks original retained authority')
    if sorted(directories) != runtime.facts['search_paths']:
        raise ValueError('Actual isolated Python search roots differ from original runtime facts')
    runtime.live()


def _resource(value):
    owner = _RESOURCES.get(value) if type(value) is _MetadataResources else None
    if owner is None or owner.closed:
        raise _missing('posix-metadata-controller-resource-adapter', 'resources',
                       'an actual live issued metadata resource owner is required')
    _runtime(owner.runtime)
    return owner


class _MetadataResources:
    __slots__ = ()

    def __new__(cls):
        raise TypeError('Metadata resources are issued only by controller admission')

    def for_workspace(self, output_owner, *, generated_root, temporary_root,
                      protected_paths, argv, limits, deadline):
        owner = _resource(self)
        bound = _BoundRun(owner, output_owner, generated_root, temporary_root,
                          protected_paths, argv, limits, deadline)
        token = _handle(_BoundMetadataRun, _BOUND_RUNS, bound)
        owner.bindings.add(token)
        return token

    def close(self):
        owner = _RESOURCES.get(self)
        if owner is None:
            return
        for token in owner.bindings:
            bound = _BOUND_RUNS.get(token)
            if bound is not None and bound.phase in ('running', 'uncertain'):
                raise process_tree.ProcessTreeError('Metadata writers are not closed; retain resource ownership')
        for token in owner.bindings:
            _BOUND_RUNS.pop(token, None)
        owner.closed = True
        _RESOURCES.pop(self, None)


class _ResourceOwner:
    def __init__(self, runtime, api):
        self.runtime, self.api, self.closed = runtime, api, False
        self.bindings = set()


def _controller_resource_admission(reference, raw, *, controller=None):
    api = _process_api()
    if controller is None:
        raise _missing('posix-metadata-controller-resource-adapter', reference['path'],
                       'an actual original runtime owner is required before resource admission')
    runtime = _runtime(controller)
    if runtime.reference != reference or runtime.raw != raw:
        raise ValueError('Metadata resource/runtime original inputs differ')
    runtime.recheck()
    _isolated_startup_admission(runtime)
    return _handle(_MetadataResources, _RESOURCES, _ResourceOwner(controller, api))


def _workspace_owner(output):
    owner = _OUTPUTS.get(output) if type(output) is _PosixOutput else None
    if (owner is None or type(owner) is not _PreparationOwner or owner.output is not output or
            owner.failed or owner.closed or not any(item[1] is owner for item in _PREPARATIONS.values())):
        raise ValueError('Metadata resources require the actual registered preparation workspace')
    owner.check()
    return owner


def _controller_limits(value):
    contract.fields(value, LIMITS, 'metadata controller limits')
    for key, maximum in LIMITS.items():
        item = value[key]
        if key.endswith('_seconds'):
            valid = type(item) in (int, float) and math.isfinite(item) and 0 < item <= maximum
        else:
            valid = type(item) is int and 0 < item <= maximum
        if not valid:
            raise ValueError('Metadata controller limit is outside its finite bound: ' + key)
    return copy.deepcopy(value)


class _BoundMetadataRun:
    __slots__ = ()

    def __new__(cls):
        raise TypeError('Metadata runs are issued only by owned workspace binding')

    def run(self, argv, cwd, log, environment, limits):
        owner = _BOUND_RUNS.get(self)
        if owner is None:
            raise ValueError('An actual issued bound metadata run is required')
        return owner.run(argv, cwd, log, environment, limits)

    def adopt_closed_log(self, output, relative, maximum):
        owner = _BOUND_RUNS.get(self)
        if (owner is None or owner.phase != 'closed' or output is not owner.output or
                relative != owner.log_name or owner.closed_log_identity is None):
            raise ValueError('Only the actual closed metadata run may supply its original log')
        return output.adopt_closed_log(relative, maximum,
                                       _expected_identity=owner.closed_log_identity)


class _BoundRun:
    def __init__(self, resources, output, generated, temporary, protected, argv, limits, deadline):
        self.resources, self.output = resources, output
        self.preparation = _workspace_owner(output)
        self.runtime = _runtime(resources.runtime)
        self.generated = _absolute(os.fspath(generated))
        self.temporary = _absolute(os.fspath(temporary))
        self.limits = _controller_limits(limits)
        self.deadline = min(deadline, self.runtime.deadline,
                            time.monotonic() + self.limits['generator_seconds'])
        self.argv, self.phase = copy.deepcopy(argv), 'bound'
        self.owner = self.stream = None
        self.log_close_attempted = False
        self.log_identity = self.log_name = None
        self.closed_log_identity = None
        self.maximum_observed_processes = 0
        self.final_process_closure_observed = False
        for path in (self.generated, self.temporary):
            if (output.root not in path.parents or
                    path.relative_to(output.root).as_posix() not in output.private_directories):
                raise ValueError('Metadata output/temp require actual owned private directories')
        if self.generated == self.temporary:
            raise ValueError('Metadata generated and temporary roots must be distinct')
        self.protected = tuple(_absolute(os.fspath(path)) for path in protected)
        for path in (*self.protected, *self.runtime.inputs.protected_paths):
            if path == output.root or path in output.root.parents or output.root in path.parents:
                raise ValueError('Metadata workspace overlaps a protected source/runtime input')
        expected = _generator_arguments(self.preparation.retained_root,
            self.preparation.references['recipe'], self.preparation.references['sources'],
            self.preparation.references['provider_build'], self.generated,
            resources.runtime.python_reference())
        if self.argv != expected:
            raise ValueError('Metadata resource command differs from the fixed original generator')
        self.output.recheck()

    def _wall(self):
        if time.monotonic() >= self.deadline:
            raise ValueError('Metadata controller exceeded its original wall threshold')

    def _workspace_sample(self):
        self._wall()
        self.output.recheck(deadline=self.deadline)
        total = entries = 0
        pending = [(os.dup(self.output.anchor.fd), '')]
        try:
            while pending:
                descriptor, prefix = pending.pop()
                try:
                    for name in handoff._names(descriptor):
                        self._wall()
                        manifest.path_name(name)
                        relative = prefix + ('/' if prefix else '') + name
                        entries += 1
                        if entries > MAX_OUTPUT_FILES or len(relative.split('/')) > MAX_DEPTH:
                            raise ValueError('Metadata workspace entry/depth threshold exceeded')
                        state = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
                        if stat.S_ISDIR(state.st_mode):
                            expected = self.output.private_directories.get(relative)
                            mode = 0o700 if expected is not None else 0o755
                            expected = expected or self.output.directories.get(relative)
                            if (expected is None or handoff._identity(state)[:2] != expected or
                                    stat.S_IMODE(state.st_mode) != mode):
                                raise ValueError('Metadata workspace contains an unowned directory')
                            child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor)
                            if handoff._identity(os.fstat(child))[:2] != expected:
                                os.close(child)
                                raise ValueError('Metadata workspace directory changed during observation')
                            pending.append((child, relative))
                        elif stat.S_ISREG(state.st_mode):
                            known = self.output.files.get(relative)
                            if known is not None:
                                if handoff._identity(state) != known['identity']:
                                    raise ValueError('Protected preparation output changed during metadata generation')
                            elif relative == self.log_name and self.log_identity is not None:
                                if handoff._identity(state)[:2] != self.log_identity[:2]:
                                    raise ValueError('Metadata log path changed during execution')
                            elif prefix == self.generated.relative_to(self.output.root).as_posix():
                                if (name != handoff.HEADER and not re.fullmatch(r'\.native-metadata-[0-9a-f]{32}', name) or
                                        stat.S_IMODE(state.st_mode) not in (0o600, 0o644) or
                                        state.st_nlink not in (1, 2) or state.st_size > MAX_DOCUMENT):
                                    raise ValueError('Metadata generator wrote an unknown output channel')
                            else:
                                raise ValueError('Metadata workspace contains an unowned file')
                            total += state.st_size
                            if total > self.limits['maximum_output_bytes']:
                                raise ValueError('Metadata workspace monitored output threshold exceeded')
                        else:
                            raise ValueError('Metadata workspace contains a symlink or special file')
                finally:
                    os.close(descriptor)
        finally:
            for descriptor, unused in pending:
                os.close(descriptor)
        self._wall()
        return total, entries

    def _sample(self, *, processes=True):
        self._workspace_sample()
        if self.stream is not None:
            state = os.fstat(self.stream.fileno())
            if (self.stream.closed or handoff._identity(state)[:2] != self.log_identity[:2] or
                    state.st_size > self.limits['maximum_log_bytes']):
                raise ValueError('Metadata original log identity/monitored threshold differs')
        if processes and self.owner is not None:
            snapshot = self.owner.sample_processes(maximum_processes=self.limits['maximum_processes'],
                                                    deadline=self.deadline)
            records = snapshot.records
            if (type(records) is not tuple or len(records) > self.limits['maximum_processes'] or
                    type(snapshot.complete) is not bool or type(snapshot.unknown_coverage) is not bool or
                    snapshot.complete == snapshot.unknown_coverage or snapshot.complete and records):
                raise ValueError('Metadata descendant observation is invalid or exceeds its threshold')
            seen = set()
            for record in records:
                if (type(record) is not tuple or len(record) != 4 or
                        any(type(item) is not int or item <= 0 for item in record) or record[0] in seen):
                    raise ValueError('Metadata descendant identity observation is malformed')
                seen.add(record[0])
            self.maximum_observed_processes = max(self.maximum_observed_processes, len(records))
            self.final_process_closure_observed = snapshot.complete
        self._wall()

    def run(self, argv, cwd, log, environment, limits):
        if self.phase != 'bound' or self.resources.closed:
            raise ValueError('Metadata run is closed, failed or already consumed')
        if (argv != self.argv or _controller_limits(limits) != self.limits or
                _absolute(os.fspath(cwd)) != self.preparation.retained_root or
                environment != self.resources.runtime.environment(self.temporary)):
            raise ValueError('Metadata run arguments differ from their actual workspace binding')
        log = _absolute(os.fspath(log))
        if self.output.root not in log.parents:
            raise ValueError('Metadata log is outside its actual workspace')
        self.log_name = log.relative_to(self.output.root).as_posix()
        if self.log_name not in self.output.reserved:
            raise ValueError('Metadata log must be the actual reserved exclusive output')
        joined = closed = uncertain = close_attempted = False
        self.phase = 'running'
        try:
            self.runtime.recheck()
            self._sample()
            directory, base = self.output._directory(self.log_name)
            try:
                descriptor = os.open(base, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                                     0o600, dir_fd=directory)
                try:
                    os.fchmod(descriptor, 0o644)
                    self.log_identity = handoff._identity(os.fstat(descriptor))
                    self.stream = os.fdopen(descriptor, 'wb')
                except BaseException:
                    os.close(descriptor)
                    raise
            finally:
                os.close(directory)
            self._sample()
            self.owner = self.resources.api.launch(argv, Path(cwd), self.stream, env=environment,
                                                   isolated_python_supervisor=True)
            observation = self.owner.observe_supervisor_startup(deadline=self.deadline)
            _validate_supervisor_startup(self.runtime, observation)
            self._sample(processes=False)
            # Never replace this with the validator's result or a serialized
            # expectation: only the exact pending owner's observation may GO.
            self.owner.release_supervisor_startup(observation)
            while self.owner.poll() is None:
                self._sample()
                time.sleep(0.05)
            code = self.owner.finish()
            joined = True
            if code != 0:
                # The actual owner has joined its writers. A failing primary
                # cannot produce metadata, but needs no successful-run sample
                # and must not be terminated a second time during cleanup.
                raise ValueError('Original metadata generator exited ' + str(code))
            self._sample()  # Final live observation; ECHILD, not PID disappearance, proves closure.
            if not self.final_process_closure_observed:
                raise process_tree.ProcessTreeError('Metadata final descendant closure observation is missing')
            close_attempted = True
            self.owner.close()
            closed = True
            self.stream.flush()
            os.fsync(self.stream.fileno())
            self._sample(processes=False)
            self.closed_log_identity = handoff._identity(os.fstat(self.stream.fileno()))
            self.log_close_attempted = True
            self.stream.close()
            self.stream = None
            self._workspace_sample()
            self.runtime.recheck()
            self.phase = 'closed'
            return {'argv': list(argv), 'returncode': code, 'process_owner_closed': True,
                'resource_policy': 'monitored-process-output-log-thresholds; cooperating-writers',
                'maximum_observed_processes': self.maximum_observed_processes,
                'live_process_census_complete': False, 'unknown_live_coverage': True,
                'final_process_closure_observed': self.final_process_closure_observed,
                'process_limit_enforced': False,
                'hard_quota_claim': False}
        except BaseException as error:
            if self.log_close_attempted and self.stream is not None:
                uncertain = True
                raise process_tree.ProcessTreeError('Metadata log close uncertain; retain the original stream and owners') from error
            if self.owner is not None and not closed:
                if close_attempted:
                    uncertain = True
                    raise process_tree.ProcessTreeError('Metadata close uncertain; retain all input/output owners') from error
                else:
                    try:
                        if not joined:
                            self.owner.terminate(timeout=self.limits['cleanup_seconds'])
                        close_attempted = True
                        self.owner.close()
                        closed = True
                    except BaseException as cleanup:
                        uncertain = True
                        raise process_tree.ProcessTreeError('Metadata cleanup uncertain; retain all input/output owners') from cleanup
            elif self.owner is None and isinstance(error, process_tree.ProcessTreeError):
                uncertain = True
            raise
        finally:
            if uncertain:
                self.phase = 'uncertain'
                _UNCERTAIN.append(self)
            else:
                self.phase = 'closed' if self.phase == 'closed' else 'failed'
                if self.stream is not None:
                    try:
                        self.log_close_attempted = True
                        self.stream.close()
                        self.stream = None
                    except BaseException as error:
                        self.phase = 'uncertain'
                        _UNCERTAIN.append(self)
                        raise process_tree.ProcessTreeError('Metadata log close uncertain; retain all owners') from error


class _PreparationTicket:
    """Opaque issued handle; constructor/type/caller fields cannot mint authority."""
    __slots__ = ()

    def __new__(cls):
        raise TypeError('Preparation tickets are issued only by checked inspection')


def _issue(kind, owner):
    value = object.__new__(_PreparationTicket)
    _PREPARATIONS[value] = (kind, owner)
    owner.tickets.add(value)
    return value


def _checked(value, kind='checked', phase=None):
    entry = _PREPARATIONS.get(value) if type(value) is _PreparationTicket else None
    if entry is None or entry[0] != kind:
        raise _missing('windows-source-checked-preparation', 'inspect_prepare',
            'an actual live issued source/proof/controller inspection is required')
    owner = entry[1]
    if owner.failed or owner.closed or (phase is not None and owner.phase != phase):
        raise ValueError('Windows preparation authority is failed, closed or consumed')
    try:
        owner.check()
    except BaseException:
        owner.fail()
        raise
    return owner


def inspect_prepare(selection_path, selection_sha256):
    started = time.monotonic()
    handoff._qualified_posix()
    selection_path = _absolute(os.fspath(selection_path))
    raw, _ = _metadata({'path': str(selection_path), 'sha256': selection_sha256},
                       'windows-source-preparation-selection', document=False)
    selected = validate_selection(handoff._document(raw))
    # The existing producer source is independently frozen. Never feature-
    # detect a drifting shared helper and quietly acquire new admission behavior.
    if handoff.digest(handoff._read(str(Path(contract.__file__).absolute()))) != CONTRACT_SHA256:
        raise ValueError('Windows preparation source contract differs from its released identity')
    documents, missing = {}, []
    for role in METADATA_REFS:
        try:
            documents[role] = _metadata(selected[role], role)
        except MissingInputs as error:
            missing.extend(error.missing)
    if missing:
        raise MissingInputs(missing)
    contract.validate_inputs(documents['native_inputs'][1])
    _replay().validate_projection_metadata(documents['source_projection'][1])
    root = Path(selected['repository_root'])
    catalogue = {}
    for role, reference in contract.CATALOGUE.items():
        catalogue[role], _ = _metadata({'path': str(root / reference['path']),
            'sha256': reference['sha256']}, 'current-source-' + role, document=False)
    _replay().catalogue_metadata(catalogue['source_map'], catalogue['provenance'], catalogue['graph'])
    try:
        proof = importlib.import_module('appended_engine_windows_dependency_proof')
        proof.validate_source_declarations(documents['typed_toolchain_identity'][0],
            selected['typed_toolchain_identity']['sha256'], documents['dependency_producer_receipt'][0],
            selected['dependency_producer_receipt']['sha256'], documents['native_inputs'][1])
    except ModuleNotFoundError as error:
        if error.name != 'appended_engine_windows_dependency_proof':
            raise
        missing.extend(_missing('windows-dependency-source-declaration-join',
            'tools/appended_engine_windows_dependency_proof.py',
            'the reviewed H/D/native-input declaration join is not available').missing)
    except MissingInputs as error:
        missing.extend(error.missing)
    try:
        _replay().require_original_proof_seam()
    except MissingInputs as error:
        missing.extend(error.missing)
    controller = resources = None
    try:
        try:
            controller = _controller_runtime_admission(selected['metadata_controller_runtime'],
                documents['metadata_controller_runtime'][0],
                deadline=started + selected['phase_limits']['prepare_seconds'])
        except MissingInputs as error:
            missing.extend(error.missing)
        try:
            resources = _controller_resource_admission(selected['metadata_controller_runtime'],
                documents['metadata_controller_runtime'][0], controller=controller)
        except MissingInputs as error:
            missing.extend(error.missing)
        if missing:
            raise MissingInputs(missing)
        owner = _PreparationOwner(selected, documents, catalogue, controller, resources,
            deadline=started + selected['phase_limits']['prepare_seconds'])
    except BaseException:
        # No preparation owner has acquired these actual admissions yet. Stop
        # at the first uncertain close so its dependent runtime remains held.
        try:
            for resource in (resources, controller):
                if resource is not None:
                    resource.close()
        except BaseException as cleanup:
            _UNCERTAIN.append((resources, controller))
            raise process_tree.ProcessTreeError(
                'Preparation admission cleanup uncertain; retain the actual runtime/resource owners') from cleanup
        raise
    try:
        owner.capture_selected(str(selection_path), selection_sha256, raw)
        return _issue('checked', owner)
    except BaseException:
        owner.fail()
        raise


def _metadata_documents(input_records, identity_sha256, suppliers, patches, licenses):
    """Pure candidate R/S/B construction, never source/provenance admission."""
    if type(input_records) is not dict or not 1 <= len(input_records) <= MAX_FILES:
        raise ValueError('Windows metadata requires a finite complete input record map')
    for name, item in input_records.items():
        manifest.path_name(name)
        manifest.fields(item, ('sha256', 'role', 'mode'), 'Windows candidate input record')
        contract.pin(item['sha256'], 'Windows candidate input')
        if (type(item['role']) is not str or item['role'] not in manifest.ROLES or
                type(item['mode']) is not int or item['mode'] not in (0o644, 0o755)):
            raise ValueError('Windows candidate input role or mode differs')
    contract.pin(identity_sha256, 'original typed Windows toolchain identity')
    if input_records.get(IDENTITY_PATH) != {'sha256': identity_sha256, 'role': 'config', 'mode': 0o644}:
        raise ValueError('Original canonical Windows identity must be retained as config0644')
    for name in (NATIVE_INPUTS_PATH, DEPENDENCY_PATH, handoff.GENERATOR, handoff.TEMPLATE, handoff.CONFIG):
        if name not in input_records:
            raise ValueError('Windows metadata omits a required original source role: ' + name)
    for name, role in ((NATIVE_INPUTS_PATH, 'config'), (DEPENDENCY_PATH, 'data'),
            (handoff.GENERATOR, 'helper'), (handoff.TEMPLATE, 'config'), (handoff.CONFIG, 'config'),
            *((name, 'helper') for name in NATIVE_HELPERS)):
        item = input_records.get(name)
        if item is None or item.get('role') != role or item.get('mode') != 0o644:
            raise ValueError('Windows metadata fixed source helper/config role or mode differs: ' + name)
    for role, name in actions.INTERFACE_PATHS.items():
        if input_records.get(name) != {'sha256': actions._pins()[role], 'role': 'interface', 'mode': 0o644}:
            raise ValueError('Windows metadata must retain every exact rich4083 interface: ' + role)
    if (type(suppliers) is not dict or set(suppliers) != {'wrapper', 'engine'} or
            any(type(item) is not dict for item in suppliers.values()) or
            suppliers['wrapper'].get('commit') != '68c618544e1f8af18ebce346281a6a49766aa194' or
            suppliers['engine'].get('commit') != native_source.ENGINE_COMMIT):
        raise ValueError('Windows metadata supplier commits differ from the reviewed source contract')
    if (type(patches) is not list or len(patches) != 1 or type(patches[0]) is not dict or
            type(patches[0].get('preimages')) is not dict or patches[0].get('tree') != 'engine' or
            input_records.get(patches[0].get('path'), {}).get('sha256') != native_source.SUPPLIER_PATCH or
            len(patches[0].get('preimages', {})) != 68 or
            sum(value is None for value in patches[0]['preimages'].values()) != 23):
        raise ValueError('Windows metadata requires the original one supplier forward patch45/23')
    forbidden = {'recipe.json', 'sources.json', 'provider-build.json', handoff.HEADER}
    if any(name in forbidden or Path(name).name in ('provider-build.json', handoff.HEADER)
           for name in input_records):
        raise ValueError('R may not retain its own identity, B or generated header')
    recipe = {'schema_version': 1, 'producer_version': 1, 'kind': 'foundation-appended-engine-recipe',
        'target': copy.deepcopy(contract.TARGET),
        'toolchain': {'cxx_standard': 23, 'identity_sha256': identity_sha256,
            'runtime_policy': 'private-native', 'paired_sdk_sha256': None,
            'target_baseline': 'windows-10-1809-unqualified'},
        'options': {'script_enabled': True, 'rendering': 'cpu', 'thread_model': 'native'},
        'provider': {'format': 'native-shared', 'binding': 'c-abi', 'abi_major': 1, 'abi_minor': 1,
            'header': 'include/foundation/appended/engine_provider.h', 'header_sha256': actions.BASE_HEADER_SHA256},
        'suppliers': copy.deepcopy(suppliers), 'inputs': copy.deepcopy(input_records),
        'patches': copy.deepcopy(patches), 'licenses': copy.deepcopy(licenses)}
    manifest.recipe_contract(recipe)
    raw_recipe = encoded(recipe)
    recipe_sha256 = handoff.digest(raw_recipe)
    files = {name: record['sha256'] for name, record in input_records.items()}
    files['recipe.json'] = recipe_sha256
    directories = sorted({part.as_posix() for name in files for part in Path(name).parents if part.as_posix() != '.'})
    modes = {name: 0o755 for name in directories}
    modes.update({name: record['mode'] for name, record in input_records.items()})
    modes['recipe.json'] = 0o644
    sources = {'schema_version': 1, 'producer_version': 1, 'kind': 'foundation-appended-engine-sources',
        'recipe_id': recipe_sha256, 'files': files, 'directories': directories, 'modes': modes}
    manifest.source_contract(sources, recipe, recipe_sha256)
    build = handoff._expected_build(recipe, recipe_sha256)
    raw_sources, raw_build = encoded(sources), encoded(build)
    if max(len(raw_recipe), len(raw_sources), len(raw_build)) > MAX_DOCUMENT:
        raise ValueError('Windows source metadata exceeds its finite document bound')
    return {'recipe': raw_recipe, 'sources': raw_sources, 'provider_build': raw_build,
        'recipe_sha256': recipe_sha256, 'sources_sha256': handoff.digest(raw_sources),
        'provider_build_sha256': handoff.digest(raw_build), 'source_proof_admitted': False}


def _owned_mutation(method):
    @wraps(method)
    def checked(self, *arguments, **keywords):
        self._live()
        try:
            return method(self, *arguments, **keywords)
        except BaseException:
            # Preserve failed private evidence, but never resume it as a clean
            # output after a partial write, path race or uncertain mutation.
            self.failed = True
            raise
    return checked


class _PosixOutput:
    """Owned stable private root; all saved files are new and inode checked."""
    def __init__(self, root, *, maximum_bytes=MAX_BYTES):
        handoff._qualified_posix()
        if type(maximum_bytes) is not int or not 1 <= maximum_bytes <= MAX_BYTES:
            raise ValueError('Windows source output requires a finite positive byte bound')
        self.root = _absolute(os.fspath(root))
        self.parent = handoff._Anchor(self.root.parent)
        self.maximum_bytes, self.bytes, self.files = maximum_bytes, 0, {}
        self.directories, self.registry, self.retired = {}, PathInventory(), set()
        self.private_directories, self.reserved = {}, set()
        self.failed = self.closed = False
        self.anchor = None
        try:
            os.mkdir(self.root.name, 0o700, dir_fd=self.parent.fd)
            self.anchor = handoff._Anchor(self.root)
            state = os.fstat(self.anchor.fd)
            if state.st_uid != os.geteuid() or stat.S_IMODE(state.st_mode) != 0o700:
                raise ValueError('Windows source output must be fresh caller-owned private0700')
        except BaseException:
            if self.anchor is not None:
                self.anchor.close()
            self.parent.close()
            raise
        _OUTPUTS[self] = None

    def _live(self):
        if self.failed or self.closed:
            raise ValueError('Windows source output has failed; preserve evidence and use a fresh root')
        self.anchor.check()

    def _directory(self, relative):
        name = manifest.path_name(relative)
        parts = name.split('/')
        if len(parts) > MAX_DEPTH:
            raise ValueError('Windows source output path exceeds finite depth bound')
        descriptor = os.dup(self.anchor.fd)
        try:
            prefix = ''
            for part in parts[:-1]:
                prefix = prefix + ('/' if prefix else '') + part
                created = False
                try:
                    os.mkdir(part, 0o755, dir_fd=descriptor)
                    created = True
                except FileExistsError:
                    pass
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor)
                try:
                    state = manifest.plain_state(os.fstat(child), True)
                    physical = handoff._identity(state)[:2]
                    if not created and (self.directories.get(prefix) != physical or
                                        stat.S_IMODE(state.st_mode) != 0o755):
                        raise ValueError('Windows source output encountered an unowned or changed directory')
                    if created:
                        os.fchmod(child, 0o755)
                        self.directories[prefix] = physical
                except BaseException:
                    os.close(child)
                    raise
                os.close(descriptor)
                descriptor = child
            return descriptor, parts[-1]
        except BaseException:
            os.close(descriptor)
            raise

    @_owned_mutation
    def save(self, relative, raw, mode=0o644, *, _replace_owned=False):
        previous = self.files.get(relative) if _replace_owned else None
        prior_bytes = previous['bytes'] if previous is not None else 0
        if (type(raw) is not bytes or len(raw) > MAX_FILE or type(mode) is not int or
                mode not in (0o644, 0o755) or len(self.files) - bool(previous) >= MAX_OUTPUT_FILES or
                self.bytes - prior_bytes + len(raw) > self.maximum_bytes):
            raise ValueError('Windows source output exceeds finite byte/file/mode bound')
        if _replace_owned and previous is None:
            raise ValueError('Only a captured owned source output may be replaced')
        self.anchor.check()
        if previous is None and relative not in self.retired:
            self.registry.add(manifest.path_name(relative), False)
        directory, base = self._directory(relative)
        try:
            if previous is not None:
                state = manifest.plain_state(os.stat(base, dir_fd=directory, follow_symlinks=False), False)
                if handoff._identity(state) != previous['identity']:
                    raise ValueError('Owned source changed before exact patch/overlay replacement')
                os.unlink(base, dir_fd=directory)
            descriptor = os.open(base, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                                 0o600, dir_fd=directory)
            try:
                view = memoryview(raw)
                while view:
                    count = os.write(descriptor, view)
                    if count <= 0:
                        raise ValueError('Incomplete Windows source metadata write')
                    view = view[count:]
                os.fchmod(descriptor, mode)
                os.fsync(descriptor)
                identity = handoff._identity(os.fstat(descriptor))
            finally:
                os.close(descriptor)
            if handoff._identity(os.stat(base, dir_fd=directory, follow_symlinks=False)) != identity:
                raise ValueError('Windows source output changed before publication')
            os.fsync(directory)
            self.files[relative] = {'sha256': handoff.digest(raw), 'mode': mode, 'bytes': len(raw),
                                    'identity': identity}
            self.bytes += len(raw) - prior_bytes
            self.retired.discard(relative)
            self.anchor.check()
            return {'path': str(self.root / relative), 'sha256': handoff.digest(raw)}
        finally:
            os.close(directory)

    def read_owned(self, relative, maximum=256 * 1024 * 1024):
        self._live()
        item = self.files.get(relative)
        if item is None:
            raise ValueError('Owned source input is absent')
        directory, base = self._directory(relative)
        try:
            state = manifest.plain_state(os.stat(base, dir_fd=directory, follow_symlinks=False), False)
            if handoff._identity(state) != item['identity']:
                raise ValueError('Owned source changed before bounded patch read')
            raw = handoff._read_fd(directory, base, maximum, expected=state)
            if handoff.digest(raw) != item['sha256']:
                raise ValueError('Owned source bytes differ before patch/overlay')
            self.anchor.check()
            return raw
        finally:
            os.close(directory)

    @_owned_mutation
    def remove_owned(self, relative):
        item = self.files.get(relative)
        if item is None:
            raise ValueError('Owned source deletion is absent')
        directory, base = self._directory(relative)
        try:
            state = manifest.plain_state(os.stat(base, dir_fd=directory, follow_symlinks=False), False)
            if handoff._identity(state) != item['identity']:
                raise ValueError('Owned source changed before exact deletion')
            os.unlink(base, dir_fd=directory)
            os.fsync(directory)
            self.bytes -= item['bytes']
            del self.files[relative]
            self.retired.add(relative)
            self.anchor.check()
        finally:
            os.close(directory)

    @_owned_mutation
    def copy(self, relative, source, sha256, mode=0o644):
        """Bounded anchored streaming copy; source hash/identity rechecked."""
        source = _absolute(os.fspath(source))
        contract.pin(sha256, 'captured source copy')
        self.anchor.check()
        if relative not in self.retired:
            self.registry.add(manifest.path_name(relative), False)
        incoming = handoff._Anchor(source.parent)
        directory = None
        try:
            directory, base = self._directory(relative)
            state = manifest.plain_state(os.stat(source.name, dir_fd=incoming.fd, follow_symlinks=False), False)
            if (state.st_size > MAX_FILE or self.bytes + state.st_size > self.maximum_bytes or
                    len(self.files) >= MAX_OUTPUT_FILES or type(mode) is not int or mode not in (0o644, 0o755)):
                raise ValueError('Windows source copy exceeds finite bounds')
            descriptor = os.open(base, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                                 0o600, dir_fd=directory)
            try:
                actual = handoff._read_fd(incoming.fd, source.name, MAX_FILE, descriptor, state)
                if actual != sha256:
                    raise ValueError('Windows copied source differs from independent pin')
                os.fchmod(descriptor, mode)
                os.fsync(descriptor)
                identity = handoff._identity(os.fstat(descriptor))
            finally:
                os.close(descriptor)
            if handoff._identity(os.stat(base, dir_fd=directory, follow_symlinks=False)) != identity:
                raise ValueError('Windows source copy identity changed')
            incoming.check()
            self.anchor.check()
            self.files[relative] = {'sha256': actual, 'mode': mode, 'bytes': state.st_size, 'identity': identity}
            self.bytes += state.st_size
            self.retired.discard(relative)
            os.fsync(directory)
            return {'path': str(self.root / relative), 'sha256': actual}
        finally:
            if directory is not None:
                os.close(directory)
            incoming.close()

    def recheck(self, *, deadline=None):
        self._live()
        for name, item in self.files.items():
            if deadline is not None and time.monotonic() >= deadline:
                raise ValueError('Owned output checking exceeded its original deadline')
            directory, base = self._directory(name)
            try:
                state = manifest.plain_state(os.stat(base, dir_fd=directory, follow_symlinks=False), False)
                if handoff._identity(state) != item['identity']:
                    raise ValueError('Owned Windows source output changed before completion')
            finally:
                os.close(directory)
        for name, physical in self.private_directories.items():
            if deadline is not None and time.monotonic() >= deadline:
                raise ValueError('Owned output checking exceeded its original deadline')
            directory, base = self._directory(name)
            try:
                state = manifest.plain_state(os.stat(base, dir_fd=directory, follow_symlinks=False), True)
                if handoff._identity(state)[:2] != physical or stat.S_IMODE(state.st_mode) != 0o700:
                    raise ValueError('Private generated output directory identity/mode changed')
            finally:
                os.close(directory)

    @_owned_mutation
    def private_directory(self, relative):
        self.registry.add(manifest.path_name(relative), True)
        directory, base = self._directory(relative)
        try:
            os.mkdir(base, 0o700, dir_fd=directory)
            child = os.open(base, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
            try:
                state = manifest.plain_state(os.fstat(child), True)
                if stat.S_IMODE(state.st_mode) != 0o700 or state.st_uid != os.geteuid():
                    raise ValueError('Generated output requires fresh caller-owned private0700')
                self.private_directories[relative] = handoff._identity(state)[:2]
                os.fsync(child)
            finally:
                os.close(child)
            os.fsync(directory)
            return self.root / relative
        finally:
            os.close(directory)

    @_owned_mutation
    def reserve_log(self, relative):
        self.registry.add(manifest.path_name(relative), False)
        directory, base = self._directory(relative)
        try:
            try:
                os.stat(base, dir_fd=directory, follow_symlinks=False)
            except FileNotFoundError:
                pass
            else:
                raise ValueError('Metadata log path already exists')
            self.reserved.add(relative)
            return self.root / relative
        finally:
            os.close(directory)

    @_owned_mutation
    def adopt_closed_log(self, relative, maximum, *, _expected_identity=None):
        if relative not in self.reserved:
            raise ValueError('Only an explicitly reserved controller log may be captured')
        directory, base = self._directory(relative)
        try:
            if (_expected_identity is not None and handoff._identity(os.stat(base, dir_fd=directory,
                    follow_symlinks=False)) != _expected_identity):
                raise ValueError('Original closed controller log changed before adoption')
            raw, identity = handoff._read_fd(directory, base, maximum, snapshot=True)
            if ((_expected_identity is not None and identity != _expected_identity) or
                    stat.S_IMODE(identity[2]) != 0o644 or len(self.files) >= MAX_OUTPUT_FILES or
                    self.bytes + len(raw) > self.maximum_bytes):
                raise ValueError('Closed controller log exceeds original mode/byte/file bound')
            self.files[relative] = {'sha256': handoff.digest(raw), 'mode': 0o644,
                'bytes': len(raw), 'identity': identity}
            self.bytes += len(raw)
            self.reserved.remove(relative)
            return raw
        finally:
            os.close(directory)

    def close(self):
        if self.closed:
            return
        errors = []
        for resource in (self.anchor, self.parent):
            try:
                resource.close()
            except BaseException as error:
                errors.append(error)
        if errors:
            raise errors[0]
        self.closed = True
        _OUTPUTS.pop(self, None)


def _materialize_candidate(projection, archive_streams, patch_bytes, overlay_bytes,
                           overlays, limits, output):
    """Write an unchecked private source candidate; never mint replay admission."""
    if type(output) is not _PosixOutput:
        raise ValueError('Source materialization requires a fresh owned POSIX output')
    output._live()
    try:
        return _materialize_candidate_data(projection, archive_streams, patch_bytes,
                                           overlay_bytes, overlays, limits, output)
    except BaseException:
        # A late stream pin, deadline or complete inventory failure invalidates
        # the whole operation, even if each individual saved file was complete.
        output.failed = True
        raise


def _materialize_candidate_data(projection, archive_streams, patch_bytes, overlay_bytes,
                                overlays, limits, output, *, checked_inventory=None):
    replay = _replay()
    started = time.monotonic()
    if (type(archive_streams) is not dict or type(patch_bytes) is not list or
            type(overlay_bytes) is not dict or type(overlays) is not dict):
        raise ValueError('Source materialization requires captured metadata and byte containers')
    projection, limits = copy.deepcopy(projection), copy.deepcopy(limits)
    archive_streams, patch_bytes = dict(archive_streams), list(patch_bytes)
    overlay_bytes, overlays = dict(overlay_bytes), copy.deepcopy(overlays)
    expected = (replay.replay_projection(projection, archive_streams, patch_bytes,
        overlay_bytes, overlays, limits) if checked_inventory is None else copy.deepcopy(checked_inventory))
    projected = (projection['projection']['files'] if checked_inventory is None else projection['_files'])
    targets = {}
    for destination, item in projected.items():
        normalized = projection['projection']['normalizations'][item['archive']]
        member = (normalized.get(item['member'], item['member']) if checked_inventory is None
                  else item['regular_member'])
        targets.setdefault((item['archive'], member), []).append((destination, item))
    budget = replay._Budget(limits)
    budget.deadline = min(budget.deadline, started + limits['seconds'])
    budget.check()
    for key, archive in sorted(projection['archives'].items()):
        source = replay._BoundedStream(archive_streams[key], archive['bytes'], budget)
        if checked_inventory is None:
            replay._stream_pin(source, archive, budget)
        else:
            source.seek(0)
        for raw_name, kind, mode, size, link, stream in replay._archive_entries(source, archive['format'], budget):
            budget.member(size)
            name = native_source._member_name(raw_name, archive['strip_prefix'])
            selected = targets.get((key, name), ())
            if not selected or kind != 'file':
                continue
            actual, body = replay._read_member(stream, size, True, budget)
            for destination, item in selected:
                if len(body) != item['bytes'] or actual != item['sha256']:
                    raise ValueError('Supplier source changed during private materialization')
                output.save('assembled/' + destination, body, item['mode'])
        if checked_inventory is None:
            replay._stream_pin(source, archive, budget)
        else:
            budget.check()
    for item, raw in zip(projection['patches'], patch_bytes):
        budget.check()
        prefix = 'assembled/source/' + item['tree'] + '/'
        originals, original_bytes = {}, 0
        for name, image in item['preimages'].items():
            budget.check()
            if image is not None:
                originals[name] = output.read_owned(prefix + name,
                    maximum=256 * 1024 * 1024 - original_bytes)
                original_bytes += len(originals[name])
        patched = native_source.apply_unified_patch(originals, raw, item['preimages'], item['postimages'])
        budget.check()
        for name, image in item['postimages'].items():
            budget.check()
            destination = prefix + name
            previous = output.files.get(destination)
            if image is None:
                output.remove_owned(destination)
            else:
                output.save(destination, patched[name], previous['mode'] if previous else 0o644,
                            _replace_owned=previous is not None)
    for name, item in sorted(overlays.items()):
        budget.check()
        destination = 'assembled/' + name
        output.save(destination, overlay_bytes[name], item['mode'],
                    _replace_owned=destination in output.files)
    inventory = {name: expected[name] for name in ('files', 'directories', 'modes')}
    budget.check()
    handoff._scan(output.root / 'assembled', inventory)
    budget.check()
    output.recheck()
    budget.check()
    return {**inventory, 'original_proof_admitted': False, 'preparation_complete': False}


def _generator_arguments(source_root, recipe_ref, sources_ref, build_ref, generated_root, python):
    source_root = _absolute(os.fspath(source_root))
    generated_root = _absolute(os.fspath(generated_root))
    python = _reference(python, 'admitted POSIX Python runtime')['path']
    for name, value in (('recipe', recipe_ref), ('sources', sources_ref), ('provider build', build_ref)):
        _reference(value, name)
    if (recipe_ref['path'] != str(source_root / 'recipe.json') or
            sources_ref['path'] != str(source_root / 'sources.json') or
            source_root in Path(build_ref['path']).parents or generated_root == source_root or
            source_root in generated_root.parents or generated_root in source_root.parents):
        raise ValueError('Windows metadata generator source/build/output roles overlap or differ')
    return [python, '-I', '-S', '-B', str(source_root / handoff.GENERATOR), '--source-root', str(source_root),
        '--recipe-sha256', recipe_ref['sha256'], '--source-manifest-sha256', sources_ref['sha256'],
        '--provider-build', build_ref['path'], '--provider-build-sha256', build_ref['sha256'],
        '--output-root', str(generated_root)]


def _run_controller(argv, cwd, log, environment, limits):
    """Internal wall/log/closure runner; never a complete controller admission.

The original interpreter/control/runtime and complete output/process resource
adapter remain a named missing admission in the public operation. This helper's
success cannot assert those missing semantics or create a preparation seal.
"""
    started, owner, closed = time.monotonic(), None, False
    try:
        with Path(log).open('xb') as stream:
            os.fchmod(stream.fileno(), 0o644)
            owner = process_tree.launch(argv, Path(cwd), stream, env=environment)
            while owner.poll() is None:
                if time.monotonic() - started >= limits['generator_seconds']:
                    raise ValueError('Windows metadata generator wall bound exceeded')
                if os.fstat(stream.fileno()).st_size > limits['maximum_log_bytes']:
                    raise ValueError('Windows metadata generator log bound exceeded')
                time.sleep(0.05)
            code = owner.finish()
            if (code != 0 or time.monotonic() - started >= limits['generator_seconds'] or
                    os.fstat(stream.fileno()).st_size > limits['maximum_log_bytes']):
                raise ValueError('Windows metadata generator failed or exceeded its finite bounds')
            owner.close()
            closed = True
            stream.flush()
            os.fsync(stream.fileno())
        if time.monotonic() - started >= limits['generator_seconds']:
            raise ValueError('Windows metadata generator closure exceeded its wall bound')
        return {'argv': list(argv), 'returncode': code, 'process_owner_closed': True,
                'controller_admitted': False, 'resource_limits_complete': False}
    except BaseException:
        if owner is not None and not closed:
            try:
                owner.terminate(timeout=limits['cleanup_seconds'])
                owner.close()
                closed = True
            except BaseException:
                _UNCERTAIN.append((owner, str(log), str(cwd)))
                raise process_tree.ProcessTreeError('Windows metadata cleanup uncertain; retain output ownership')
        raise


def _check_generated_metadata(raw, retained_read, original_header_path):
    """Use the existing exact generator/ABI joins without admitting provenance."""
    contract.fields(raw, handoff.REFS, 'Windows generated source metadata roles')
    original_header_path = _absolute(os.fspath(original_header_path))
    receipt = handoff._document(raw['metadata_receipt'])
    if type(receipt) is not dict or receipt.get('header') != str(original_header_path):
        raise ValueError('Original generated header path differs from its exact receipt')
    facts, retained, assembled = handoff._joined(raw, retained_read)
    return {'metadata': facts, 'retained_inventory': retained,
            'assembled_inventory': assembled, 'source_proof_admitted': False,
            'controller_admitted': False}


def _run_admitted_controller(controller, resources, argv, cwd, log, limits, *, temporary_root):
    """Only private original runtime/resource admissions can supply this runner.

    Their source producers remain explicit missing-code gates above. A returned
    status from the limited `_run_controller` helper cannot replace them.
    """
    controller.recheck()
    result = resources.run(argv, cwd, log, controller.environment(temporary_root), copy.deepcopy(limits))
    controller.recheck()
    return result


class _PreparationOwner:
    """Private capture/writer lifetime retained only by issued opaque tickets."""
    def __init__(self, selected, documents, catalogue, controller, resources, *, deadline):
        self.selected, self.documents = copy.deepcopy(selected), copy.deepcopy(documents)
        self.catalogue_raw = dict(catalogue)
        self.controller, self.resources, self.deadline = controller, resources, deadline
        self.capture = self.output = self.source_checked = None
        self.closed = self.failed = False
        self.phase, self.tickets = 'checked', set()
        self.specs, self.references = {}, {}
        self._closed_resources = set()

    def check_wall(self):
        if self.closed or self.failed:
            raise ValueError('Windows preparation is failed or closed')
        if time.monotonic() >= self.deadline:
            raise ValueError('Windows preparation exceeded its original wall bound')

    def check(self):
        self.check_wall()
        if self.capture is not None:
            self.capture.check()
        if self.output is not None:
            self.output.recheck(deadline=self.deadline)
        self.check_wall()

    def _add(self, name, sha256, mode, role, *, raw=None, source=None):
        manifest.path_name(name)
        item = {'sha256': sha256, 'mode': mode, 'role': role, 'raw': raw, 'source': source}
        previous = self.specs.get(name)
        if previous is not None and previous != item:
            raise ValueError('Retained Windows source roles collide: ' + name)
        self.specs[name] = item

    def _raw(self, name, raw, mode, role):
        self._add(name, handoff.digest(raw), mode, role, raw=raw)

    def capture_selected(self, selection_path, selection_sha256, selection_raw):
        replay = _replay()
        limit = self.selected['phase_limits']
        source_limits = {'seconds': min(limit['prepare_seconds'], self.deadline - time.monotonic()),
            'maximum_archive_bytes': MAX_FILE,
            'maximum_expanded_bytes': min(MAX_BYTES, limit['maximum_output_bytes']),
            'maximum_members': min(MAX_OUTPUT_FILES, replay.MAX_MEMBERS),
            'maximum_member_bytes': replay.MAX_MEMBER, 'maximum_patch_bytes': MAX_DOCUMENT}
        projection = self.documents['source_projection'][1]
        self.capture = replay._CapturedSource(projection, self.selected['bindings'], source_limits,
            resolve=lambda name: Path(name), deadline=self.deadline, relative=False)
        # Retain one physical capture, including metadata originally inspected
        # before supplier reads. Independent pins bind both reads to exact bytes.
        self.capture.capture_extra(selection_path, selection_sha256, len(selection_raw), 0o644, maximum=MAX_DOCUMENT)
        for role, (raw, unused) in self.documents.items():
            self.capture.capture_extra(self.selected[role]['path'], self.selected[role]['sha256'],
                                       len(raw), 0o644, maximum=MAX_DOCUMENT)
        root = Path(self.selected['repository_root'])
        for role, ref in contract.CATALOGUE.items():
            self.capture.capture_extra(root / ref['path'], ref['sha256'], len(self.catalogue_raw[role]),
                                       0o644, maximum=MAX_DOCUMENT)
        self.catalogue = replay.catalogue_metadata(*(self.catalogue_raw[role]
            for role in ('source_map', 'provenance', 'graph')))
        self.source_checked, self.source_facts = self.capture.checked()
        native_source._forward_patch_contract(self.source_checked.as_dict(), self.catalogue['source_map']['inputs'])
        self.overlays = {}
        for name, item in self.catalogue['source_map']['inputs'].items():
            body = self.capture.capture_extra(root / item['tracked_path'], item['sha256'], item['bytes'], item['mode'])
            role = {'provenance': 'data', 'patch': 'data'}.get(item['role'], item['role'])
            self._raw(name, body, item['mode'], role)
            if name in self.catalogue['overlays']:
                self.overlays[name] = body
        for name, item in self.catalogue['provenance']['retained_input_mapping'].items():
            original = self.specs[item['tracked_source']]
            self._raw(name, original['raw'], original['mode'], item['role'])
        missing = [name for name in NATIVE_HELPERS if name not in self.specs]
        if missing:
            raise MissingInputs([{'role': 'windows-source-helper-pin-closure', 'path': name,
                'reason': 'current catalogue/alias closure omits an independently pinned retained helper'} for name in missing])
        self.retained_bindings = {'archives': {}, 'provenance': {}, 'original_proof': {}, 'patches': [], 'notices': []}
        tables = (('archives', 'source', 'archive'), ('provenance', 'data', 'json'),
                  ('original_proof', 'data', 'bin'))
        for table, role, extension in tables:
            records = self.capture.original_proof if table == 'original_proof' else self.capture.records[table]
            for key, record in records.items():
                name = 'original-source/' + table + '/' + key + '.' + extension
                ref = {field: record[field] for field in ('sha256', 'bytes', 'mode')}
                ref['path'] = name
                self.retained_bindings[table][key] = ref
                if table == 'archives':
                    self._add(name, record['sha256'], 0o644, role,
                              source=self.selected['bindings'][table][key]['path'])
                else:
                    self._raw(name, record['raw'], 0o644, role)
        for table, role, extension in (('patches', 'patch', 'patch'), ('notices', 'license', 'txt')):
            for index, record in enumerate(self.capture.records[table]):
                name = 'original-source/' + table + '/' + str(index) + '.' + extension
                self.retained_bindings[table].append({'path': name,
                    **{field: record[field] for field in ('sha256', 'bytes', 'mode')}})
                self._raw(name, record['raw'], 0o644, role)
        for role, name, kind in (('source_projection', 'native-inputs/source-projection.json', 'config'),
                ('typed_toolchain_identity', IDENTITY_PATH, 'config'), ('native_inputs', NATIVE_INPUTS_PATH, 'config'),
                ('dependency_producer_receipt', DEPENDENCY_PATH, 'data')):
            self._raw(name, self.documents[role][0], 0o644, kind)
        self.check()

    def start(self, root):
        root = _absolute(os.fspath(root))
        for item in self.capture._inputs.values():
            if root == item['path'] or root in item['path'].parents:
                raise ValueError('Preparation output overlaps a captured input')
        protected = self.controller.protected_paths()
        for path in protected:
            path = _absolute(os.fspath(path))
            if root == path or root in path.parents or path in root.parents:
                raise ValueError('Preparation output overlaps the admitted controller runtime')
        # Qualified anchors reject symlinks; physical parent identities also
        # reject an alternate mount/path spelling of an admitted runtime root.
        runtime_directories = {handoff._identity(state)[:2] for path in protected
            for state in (os.stat(path, follow_symlinks=False),) if stat.S_ISDIR(state.st_mode)}
        for parent in (root.parent, *root.parent.parents):
            if handoff._identity(os.stat(parent, follow_symlinks=False))[:2] in runtime_directories:
                raise ValueError('Preparation output parent aliases an admitted runtime directory')
        self.output = _PosixOutput(root, maximum_bytes=min(MAX_BYTES,
            self.selected['phase_limits']['maximum_output_bytes']))
        _OUTPUTS[self.output] = self
        self.retained_root, self.assembled_root = root / 'retained', root / 'assembled'

    def prepare(self):
        self.check()
        for name, item in sorted(self.specs.items()):
            self.check_wall()
            if item['source'] is not None:
                self.output.copy('retained/' + name, item['source'], item['sha256'], item['mode'])
            else:
                self.output.save('retained/' + name, item['raw'], item['mode'])
        projection = self.source_checked.as_dict()
        expected = _replay()._checked_inventory(self.source_checked, self.catalogue['overlays'],
                                                deadline=self.deadline)
        try:
            _materialize_candidate_data(projection, self.capture.streams, self.capture.patch_bytes,
                self.overlays, self.catalogue['overlays'], self.capture.remaining_limits(), self.output,
                checked_inventory=expected)
        except BaseException:
            self.output.failed = True
            raise
        records = {name: {field: item[field] for field in ('sha256', 'role', 'mode')}
                   for name, item in self.specs.items()}
        suppliers = {key: dict(item, archive=self.retained_bindings['archives'][item['archive']]['path'])
                     for key, item in projection['suppliers'].items()}
        patches = [{**{key: item[key] for key in ('tree', 'preimages', 'postimages')}, 'path': bound['path']}
                   for item, bound in zip(projection['patches'], self.retained_bindings['patches'])]
        metadata = _metadata_documents(records, self.selected['typed_toolchain_identity']['sha256'],
            suppliers, patches, [item['path'] for item in self.retained_bindings['notices']])
        self.references['recipe'] = self.output.save('retained/recipe.json', metadata['recipe'])
        self.references['sources'] = self.output.save('retained/sources.json', metadata['sources'])
        self.references['provider_build'] = self.output.save('metadata/provider-build.json', metadata['provider_build'])
        self.references['assembled_inventory'] = self.output.save('metadata/assembled-inventory.json', encoded(expected))
        self.references['native_inputs'] = {'path': str(self.retained_root / NATIVE_INPUTS_PATH),
                                           'sha256': self.selected['native_inputs']['sha256']}
        self.retained_inventory = handoff._retained_inventory(handoff._document(metadata['sources']), metadata['sources_sha256'])
        self.assembled_inventory = expected
        self.scan_sources()

    def scan_sources(self):
        self.check()
        handoff._scan(self.retained_root, self.retained_inventory)
        handoff._scan(self.assembled_root, self.assembled_inventory)
        expected_top = {'retained', 'assembled', 'metadata'}
        if hasattr(self, 'generated_root'):
            expected_top.update(('generated', 'temporary', 'logs'))
            handoff._scan(self.temporary_root, {'files': {}, 'directories': [], 'modes': {}})
        if set(handoff._names(self.output.anchor.fd)) != expected_top:
            raise ValueError('Preparation workspace contains unowned output')
        for prefix in ('metadata', 'logs'):
            files = {name[len(prefix) + 1:]: item for name, item in self.output.files.items()
                     if name.startswith(prefix + '/')}
            if not files:
                continue
            directories = _replay()._parents(files)
            handoff._scan(self.output.root / prefix, {'files': {name: item['sha256'] for name, item in files.items()},
                'directories': directories, 'modes': {**{name: item['mode'] for name, item in files.items()},
                    **{name: 0o755 for name in directories}}})
        self.check()

    def generate(self):
        self.check()
        self.controller.recheck()
        self.generated_root = self.output.private_directory('generated')
        self.temporary_root = self.output.private_directory('temporary')
        log = self.output.reserve_log('logs/metadata-generator.log')
        argv = _generator_arguments(self.retained_root, self.references['recipe'], self.references['sources'],
            self.references['provider_build'], self.generated_root, self.controller.python_reference())
        self.check()
        limits = {**self.selected['phase_limits'], 'maximum_output_bytes': self.output.maximum_bytes,
             'generator_seconds': min(self.selected['phase_limits']['generator_seconds'],
                                      self.deadline - time.monotonic())}
        bound = self.resources.for_workspace(self.output, generated_root=self.generated_root,
            temporary_root=self.temporary_root, protected_paths=[item['path'] for item in self.capture._inputs.values()],
            argv=argv, limits=limits, deadline=self.deadline)
        _run_admitted_controller(self.controller, bound, argv, self.retained_root, log, limits,
                                temporary_root=self.temporary_root)
        receipt = bound.adopt_closed_log(self.output, 'logs/metadata-generator.log',
            min(MAX_DOCUMENT, self.selected['phase_limits']['maximum_log_bytes']))
        handoff._document(receipt)  # Entire closed original stream, never a selected JSON line.
        header_path = self.generated_root / handoff.HEADER
        header, identity = handoff._read(str(header_path), snapshot=True)
        if stat.S_IMODE(identity[2]) != 0o644:
            raise ValueError('Original generated header mode differs')
        self.header_identity = identity
        self.generated_inventory = {'files': {handoff.HEADER: handoff.digest(header)},
            'directories': [], 'modes': {handoff.HEADER: 0o644}}
        self.references['metadata_header'] = {'path': str(header_path), 'sha256': handoff.digest(header)}
        self.references['metadata_receipt'] = self.output.save('metadata/metadata-receipt.json', receipt)
        raw = {role: (header if role == 'metadata_header' else self.output.read_owned(
            str(Path(ref['path']).relative_to(self.output.root)), MAX_DOCUMENT)) for role, ref in self.references.items()}
        self.generated_facts = _check_generated_metadata(raw,
            lambda name: self.output.read_owned('retained/' + name, MAX_DOCUMENT), header_path)
        self.controller.recheck()
        self.scan_sources()
        self.scan_generated()

    def scan_generated(self):
        self.check()
        header, identity = handoff._read(str(self.generated_root / handoff.HEADER), snapshot=True)
        if identity != self.header_identity or handoff.digest(header) != self.references['metadata_header']['sha256']:
            raise ValueError('Original generated header changed')
        handoff._scan(self.generated_root, self.generated_inventory)
        if self.output.bytes + len(header) > self.output.maximum_bytes:
            raise ValueError('Complete generated output exceeds original byte bound')
        self.check()

    def summary(self):
        return {'schema_version': 1, 'kind': PREPARED_KIND, 'scope': SCOPE,
            'target': copy.deepcopy(contract.TARGET), 'source_catalogue': copy.deepcopy(contract.CATALOGUE),
            'phase': self.phase, 'source_proof_admitted': True,
            'references': copy.deepcopy(self.references), **{name: False for name in FALSE_FACTS}}

    def replay_selection(self):
        return {'schema_version': 1, 'kind': _replay().SELECTION_KIND,
            'target': copy.deepcopy(contract.TARGET), 'source_catalogue': copy.deepcopy(contract.CATALOGUE),
            'retained': {'root': str(self.retained_root),
                'recipe_sha256': self.references['recipe']['sha256'],
                'sources_sha256': self.references['sources']['sha256']},
            'assembled': {'root': str(self.assembled_root),
                'inventory': copy.deepcopy(self.references['assembled_inventory'])},
            'source_projection': {'path': 'native-inputs/source-projection.json',
                'sha256': self.selected['source_projection']['sha256']},
            'typed_toolchain_identity': {'path': IDENTITY_PATH,
                'sha256': self.selected['typed_toolchain_identity']['sha256']},
            'bindings': copy.deepcopy(self.retained_bindings), 'limits': dict(self.capture.limits)}

    def close(self):
        if self.closed:
            return
        errors, validation = [], None
        for name, resource in (('resources', self.resources), ('controller', self.controller),
                               ('output', self.output), ('capture', self.capture)):
            if errors and name in ('controller', 'output'):
                # Runtime/resource errors can mean a live command still owns
                # every input/output. Preserve that graph rather than closing
                # the anchors merely because cleanup reached a finally block.
                break
            if resource is not None and name not in self._closed_resources:
                try:
                    if name == 'controller' and not self.failed:
                        try:
                            resource.recheck()
                        except BaseException as error:
                            self.failed = True
                            validation = error
                    resource.close()
                    self._closed_resources.add(name)
                except BaseException as error:
                    errors.append(error)
        for ticket in self.tickets:
            _PREPARATIONS.pop(ticket, None)
        self.tickets.clear()
        if errors:
            self.failed = True
            _UNCERTAIN.append(self)
            raise process_tree.ProcessTreeError('Preparation resource closure uncertain; retain output ownership') from errors[0]
        self.closed = True
        if validation is not None:
            raise validation
        if not self.failed and time.monotonic() >= self.deadline:
            raise ValueError('Preparation closure exceeded its original wall bound')

    def fail(self):
        if self.failed:
            return
        self.failed = True
        for ticket in self.tickets:
            _PREPARATIONS.pop(ticket, None)
        self.tickets.clear()
        if self.output is not None:
            self.output.failed = True
        if isinstance(sys.exc_info()[1], process_tree.ProcessTreeError):
            _UNCERTAIN.append(self)
            return
        self.close()


def prepare_sources(checked_preparation, fresh_private_root):
    owner = _checked(checked_preparation, phase='checked')
    owner.phase = 'materializing'
    try:
        owner.start(fresh_private_root)
        owner.prepare()
        owner.check()
    except BaseException:
        owner.fail()
        raise
    owner.phase = 'sources_ready'
    return _issue('sources', owner)


def generate_metadata(checked_preparation, prepared_source_metadata):
    owner = _checked(checked_preparation, phase='sources_ready')
    if _checked(prepared_source_metadata, kind='sources', phase='sources_ready') is not owner:
        raise ValueError('Prepared source authority belongs to another inspection')
    owner.phase = 'generating'
    try:
        owner.generate()
        owner.check()
    except BaseException:
        owner.fail()
        raise
    owner.phase = 'metadata_ready'
    return _issue('metadata', owner)


def handoff_selection(prepared):
    owner = _checked(prepared, kind='metadata', phase='metadata_ready')
    try:
        owner.scan_sources()
        owner.scan_generated()
        value = {'schema_version': 1, 'kind': handoff.SELECTION_KIND,
            'target': copy.deepcopy(contract.TARGET), 'source_catalogue': copy.deepcopy(contract.CATALOGUE),
            'retained_root': str(owner.retained_root), 'assembled_root': str(owner.assembled_root),
            **copy.deepcopy(owner.references)}
        contract.fields(value, ('schema_version', 'kind', 'target', 'source_catalogue',
            'retained_root', 'assembled_root', *handoff.REFS), 'Windows handoff selection')
        owner.close()
    except BaseException:
        owner.fail()
        raise
    owner.phase = 'closed'
    return value


def cli(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='action', required=True)
    for action in ('check', 'prepare'):
        command = commands.add_parser(action)
        command.add_argument('--selection', required=True)
        command.add_argument('--selection-sha256', required=True)
        if action == 'prepare':
            command.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    checked = None
    try:
        checked = inspect_prepare(args.selection, args.selection_sha256)
        if args.action == 'check':
            owner = _checked(checked)
            result = owner.summary()
            owner.close()
        else:
            prepared = generate_metadata(checked, prepare_sources(checked, args.output))
            owner = _checked(prepared, kind='metadata', phase='metadata_ready')
            result = {**owner.summary(), 'source_replay_selection': owner.replay_selection()}
            result['handoff_selection'] = handoff_selection(prepared)
        print(encoded(result).decode('ascii'), end='')
        return 0
    except MissingInputs as error:
        print(encoded(error.as_dict()).decode('ascii'), end='')
        return 2
    except (ValueError, OSError) as error:
        print('Windows source preparation: ' + str(error), file=sys.stderr)
        return 1
    finally:
        entry = _PREPARATIONS.get(checked) if type(checked) is _PreparationTicket else None
        if entry is not None and not entry[1].failed:
            entry[1].close()


if __name__ == '__main__':
    raise SystemExit(cli())
