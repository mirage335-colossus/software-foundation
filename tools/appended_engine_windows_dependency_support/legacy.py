#!/usr/bin/env python3
"""Finite Windows20 dependency selection and original candidate admission.

The checked v1 recipe contains source identities, not reviewed Windows supplier
commands. Consequently every public plan/build/admission fails with named missing
reviews. This is an implementation prerequisite, not deferred qualification.
Metadata inspection never reads SDK, archive, interpreter or product bodies.
Native byte inspection and Workspace ownership are deliberately lazy operations.
No Linux build command, engine handoff or caller supplied ``passed`` fact is an
authority for this producer.
"""
from __future__ import annotations

import argparse
import copy
from dataclasses import dataclass
import hashlib
import io
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import platform
import stat
import struct
import sys
import time

import appended_engine_windows_contract as contract
import appended_engine_windows_dependency_proof as proof

ROOT = Path(__file__).resolve().parents[2]
RECIPE = 'recipes/webkitwasm-native-deps-windows-x86_64-v1'
PROFILE = RECIPE + '/profile.json'
SOURCE_REVIEW = RECIPE + '/source-review.json'
PROFILE_PIN = '14b73b412dab26015fdec17027e29526cfc35f1b9f377a675333257b75860ada'
SOURCE_REVIEW_PIN = '923f43e2a83f8484b6990185c3d05253cc1f5fcce62a55f2097a45acb284fa54'
SOURCE_METADATA = 'recipes/webkitwasm-native-deps-linux-x86_64-v1/profile.json'
SOURCE_METADATA_PIN = 'fe3df90a8567b811783e18906144bd2d44690207c68faa61322fe7b7fb303a53'
SELECTION_KIND = 'foundation-native-engine-windows-dependencies-selection-v1'
PLAN_KIND = 'foundation-native-engine-windows-dependencies-plan-v1'
SCOPE = 'windows-dependency-source-declarations-only'
IDENTITY_FIELDS = ('version', 'archive', 'sha256', 'bytes', 'format', 'strip_prefix')
RECIPE_FILES = ('profile.json', 'source-review.json', 'CMakeLists.txt',
                'cmake/components.cmake', 'initial-cache.cmake.in',
                'static-closure-probe.cpp', 'README.md')
MAX_METADATA = proof.MAX_DOCUMENT
MAX_SOURCE_FILES = 262144
MAX_SOURCE_BYTES = 8 * 1024**3
MAX_SOURCE_ARCHIVE_BYTES = 512 * 1024**2
MAX_SOURCE_MEMBER_BYTES = 256 * 1024**2
ARCHIVE_HELPER_SOURCES = (
    'tools/appended_engine_windows_source_replay.py',
    'tools/appended_engine_manifest.py', 'tools/appended_engine_native_inputs.py',
    'tools/appended_engine_windows_contract.py', 'tools/appended_engine_windows_handoff.py',
    'tools/appended_engine_native_actions_contract.py',
    'tools/appended_engine_document_contract.py', 'tools/appended_engine_editor_contract.py',
    'tools/dependency_archive.py')
_CANDIDATE_TOKEN = object()
FALSE_FACTS = ('executable_plan', 'build', 'production_eligible',
               'engine_execution', 'native_runtime_qualified', 'kernel_rebuild')
JOB_PROCESS_LIMIT_GAP = 'windows-dependency-pre-resume-job-process-limit'
PROBE_OBJECT_BINDING_GAP = 'windows-static-probe-original-object-binding'
PUBLICATION_SOURCES = ('tools/appended_engine_windows_publication.py',
    'tests/diagnostics/windows_engine_publication.py', 'tools/process_tree.py',
    'tools/appended_engine_windows_contract.py')
LIMIT_BOUNDS = {'configure_seconds': (1, 3600), 'build_seconds': (1, 28800),
    'install_seconds': (1, 3600), 'probe_seconds': (1, 3600),
    'cleanup_seconds': (1, 60), 'maximum_jobs': (1, 4),
    'maximum_processes': (1, 1024), 'maximum_output_bytes': (1024, 1024**4),
    'maximum_log_bytes': (1024, 128 * 1024**2)}


def _hash(raw):
    return hashlib.sha256(raw).hexdigest()


def _equal(actual, expected, label):
    if proof.encoded(actual) != proof.encoded(expected):
        raise ValueError('Different ' + label)


def _fields(value, fields, label):
    return contract.fields(value, fields, label)


def _integer(value, label, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ValueError('Bounded exact integer required: ' + label)
    return value


def _reference(value, label, paths=None):
    _fields(value, ('path', 'sha256'), label)
    proof.windows_path(value['path'], label)
    contract.pin(value['sha256'], label)
    if paths is not None:
        paths.add(value['path'], 'file', value['sha256'])
    return copy.deepcopy(value)


def _host_read(path, pin, maximum=MAX_METADATA):
    """Bounded ordinary metadata read, with descriptor and pathname identity joins."""
    contract.pin(pin, 'metadata')
    path = Path(path)
    if not path.is_absolute() or '..' in path.parts:
        raise ValueError('Explicit absolute metadata path required')
    def identity(state):
        return (state.st_dev, state.st_ino, state.st_mode, state.st_nlink,
                state.st_size, state.st_mtime_ns, state.st_ctime_ns)
    def ordinary():
        for current in reversed((path, *path.parents)):
            state = current.lstat()
            directory = current != path
            attrs = getattr(state, 'st_file_attributes', 0)
            if (stat.S_ISLNK(state.st_mode) or attrs & 0x400 or
                    not (stat.S_ISDIR(state.st_mode) if directory else stat.S_ISREG(state.st_mode)) or
                    not directory and state.st_nlink != 1):
                raise ValueError('Metadata must be ordinary and unaliased')
        return identity(path.lstat())
    before = ordinary()
    if before[4] > maximum:
        raise ValueError('Metadata byte bound exceeded')
    with os.fdopen(os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0)), 'rb') as stream:
        opened = identity(os.fstat(stream.fileno()))
        raw = stream.read(maximum + 1)
        after = identity(os.fstat(stream.fileno()))
    if before != opened or before != after or before != ordinary() or len(raw) > maximum:
        raise ValueError('Metadata changed during bounded read')
    if _hash(raw) != pin:
        raise ValueError('Metadata differs from independent SHA256')
    return raw


def _local_metadata(relative, pin):
    """Read repository metadata only; it carries no retained-byte admission."""
    path = ROOT / relative
    raw = _host_read(path, pin)
    return raw, {'path': str(path), 'sha256': pin}


def validate_limits(value):
    _fields(value, LIMIT_BOUNDS, 'dependency execution limits')
    return {key: _integer(value[key], key, *bound) for key, bound in LIMIT_BOUNDS.items()}


def _relative(value):
    if (type(value) is not str or not value or len(value) > 1024 or
            PurePosixPath(value).as_posix() != value or value.startswith('/') or
            any(part in ('', '.', '..') for part in value.split('/'))):
        raise ValueError('Canonical relative source member required')
    proof.windows_path('C:/source/' + value)
    return value


def _recipe_metadata():
    """Check the exact pending schema; status words cannot create review authority."""
    profile_raw, profile_ref = _local_metadata(PROFILE, PROFILE_PIN)
    review_raw, review_ref = _local_metadata(SOURCE_REVIEW, SOURCE_REVIEW_PIN)
    # The historical Linux document is used exclusively for these six identities.
    linux_raw = _host_read(ROOT / SOURCE_METADATA, SOURCE_METADATA_PIN)
    linux = contract.parse_document(linux_raw)
    profile = contract.parse_document(profile_raw)
    review = contract.parse_document(review_raw)
    _fields(profile, ('schema_version', 'kind', 'target', 'implementation_status',
        'executable_plan', 'build', 'production_eligible', 'engine_execution',
        'kernel_rebuild', 'woff2', 'maximum_jobs', 'source_policy', 'components',
        'libraries', 'recipe_files', 'source_review'), 'Windows dependency recipe')
    expected = {'schema_version': 1,
        'kind': 'foundation-native-engine-windows-dependency-recipe-v1',
        'target': proof.TARGET, 'implementation_status': 'supplier-entrypoint-review-required',
        'executable_plan': False, 'build': False, 'production_eligible': False,
        'engine_execution': False, 'kernel_rebuild': False, 'woff2': 'OFF',
        'maximum_jobs': 4, 'source_policy': 'exact-retained-archives-no-fetch-no-fallback',
        'recipe_files': list(RECIPE_FILES), 'source_review': 'source-review.json'}
    for key, wanted in expected.items():
        _equal(profile[key], wanted, 'recipe ' + key)
    _fields(profile['components'], proof.SOURCES, 'thirteen Windows supplier identities')
    for supplier in proof.SOURCES:
        _fields(profile['components'][supplier], IDENTITY_FIELDS, supplier + ' identity')
        wanted = {key: linux['components'][supplier][key] for key in IDENTITY_FIELDS}
        _equal(profile['components'][supplier], wanted, supplier + ' pinned source metadata')
    _fields(profile['libraries'], proof.LIBRARY_SUPPLIERS, 'Windows20 supplier map')
    for target, supplier in proof.LIBRARY_SUPPLIERS.items():
        wanted = {'supplier': supplier}
        if target == 'WebP::libwebp':
            wanted['required_links'] = ['WebP::sharpyuv']
        elif target == 'WebP::demux':
            wanted['required_links'] = ['WebP::libwebp']
        _equal(profile['libraries'][target], wanted, 'library supplier/required links')
    _fields(review, ('schema_version', 'kind', 'target', 'scope', 'missing_reason', 'sources'),
            'supplier source review')
    for key, wanted in {'schema_version': 1,
            'kind': 'foundation-native-engine-windows-dependency-source-review-v1',
            'target': proof.TARGET,
            'scope': 'metadata-identities-only-entrypoint-review-unperformed'}.items():
        _equal(review[key], wanted, 'source review ' + key)
    contract.text(review['missing_reason'], 'missing supplier review reason')
    _fields(review['sources'], proof.SOURCES, 'supplier reviews')
    for supplier in proof.SOURCES:
        item = review['sources'][supplier]
        _fields(item, IDENTITY_FIELDS + ('status', 'entrypoints', 'commands', 'artifact_map',
            'required_build_tools', 'patches'), supplier + ' source review')
        _equal(item, {**profile['components'][supplier], 'status': 'unreviewed',
            'entrypoints': [], 'commands': [], 'artifact_map': None,
            'required_build_tools': [], 'patches': []}, supplier + ' unperformed source review')
    return profile, review, {'recipe': profile_ref, 'source_review': review_ref}


class MissingInputs(contract.MissingInputs):
    def as_dict(self):
        return {'schema_version': 1,
            'kind': 'foundation-native-engine-windows-dependency-missing-inputs-v1',
            'scope': SCOPE, 'missing': copy.deepcopy(list(self.missing)),
            **{key: False for key in FALSE_FACTS}}


def _review_gaps(review):
    return [{'role': 'windows-dependency-source-declaration-join', 'path': RECIPE,
             'reason': 'literal Windows commands and installed artifact map require original supplier entrypoint review'},
            *({'role': 'windows-dependency-supplier-review:' + supplier,
               'path': RECIPE + '/source-review.json#sources/' + supplier,
               'reason': review['missing_reason']} for supplier in proof.SOURCES)]


def _activation_gaps(review):
    return [*_review_gaps(review),
        {'role': JOB_PROCESS_LIMIT_GAP, 'path': 'tools/process_tree.py#launch',
         'reason': 'maximum_processes is a sampled monitoring threshold; the canonical owner has no selected enforced Job active-process limit configured before resume'},
        {'role': PROBE_OBJECT_BINDING_GAP, 'path': RECIPE + '/static-closure-probe.cpp',
         'reason': 'pinned probe object bytes do not establish their original source, compiler command or owned compilation; that reviewed binding is not implemented'}]


def _require_reviewed_recipe():
    profile, review, references = _recipe_metadata()
    # There is intentionally no "reviewed":true escape hatch in v1. Admitting a
    # future finite recipe requires review and a separately implemented schema.
    raise MissingInputs(_activation_gaps(review))


def validate_selection(value):
    _fields(value, ('schema_version', 'kind', 'target', 'toolchain_identity',
        'inventories', 'sources', 'output', 'publication', 'limits'), 'dependency selection')
    _equal(value['schema_version'], 1, 'selection schema')
    _equal(value['kind'], SELECTION_KIND, 'selection kind')
    _equal(value['target'], proof.TARGET, 'selection target')
    paths = proof._Paths()
    _reference(value['toolchain_identity'], 'original H', paths)
    _fields(value['inventories'], proof.INVENTORIES, 'toolchain inventory selections')
    for role in proof.INVENTORIES:
        _reference(value['inventories'][role], role, paths)
    _fields(value['sources'], proof.SOURCES, 'thirteen source selections')
    unique = set()
    for supplier in proof.SOURCES:
        item = _fields(value['sources'][supplier], ('archive', 'replay'), supplier)
        for name in ('archive', 'replay'):
            ref = _reference(item[name], supplier + ' ' + name, paths)
            if ref['path'].casefold() in unique:
                raise ValueError('Supplier archive/replay references must be distinct')
            unique.add(ref['path'].casefold())
    output = paths.add(value['output'], 'directory')
    publication = _fields(value['publication'], ('qualification', 'source_identity',
                                                'runtime_identity'), 'publication selection')
    _reference(publication['qualification'], 'publication qualification', paths)
    _fields(publication['source_identity'], PUBLICATION_SOURCES, 'publication source identities')
    for name, digest in publication['source_identity'].items():
        contract.pin(digest, name)
    runtime = _fields(publication['runtime_identity'], ('python_path', 'python_sha256',
        'python_version', 'system', 'machine', 'pointer_bits', 'windows_version',
        'system_root'), 'publication runtime identity')
    proof.windows_path(runtime['python_path'])
    proof.windows_path(runtime['system_root'])
    contract.pin(runtime['python_sha256'], 'publication Python')
    proof._version(runtime['python_version'], 'publication Python')
    for name, wanted in {'system': 'Windows', 'machine': 'x86_64', 'pointer_bits': 64}.items():
        _equal(runtime[name], wanted, 'publication runtime ' + name)
    versions = runtime['windows_version']
    if type(versions) is not list or len(versions) != 3:
        raise ValueError('Explicit Windows version triple required')
    for item in versions:
        _integer(item, 'Windows version component', 0, 2**32 - 1)
    validate_limits(value['limits'])
    # Protect the whole input root even when its exact file is elsewhere.
    for spelling, kind, pin in paths.entries.values():
        if kind == 'file' and (spelling.casefold().startswith(output.casefold() + '/') or
                              output.casefold().startswith(spelling.casefold() + '/')):
            raise ValueError('Dependency output overlaps selected input')
    return copy.deepcopy(value)


@dataclass(frozen=True)
class DependencyInputs:
    selection_ref: dict
    selection: dict
    recipe: dict
    source_review: dict
    producer_refs: dict
    missing: tuple


def inspect_selection(selection_ref):
    """Inspect selected JSON and fixed source metadata only; no referenced bodies."""
    _fields(selection_ref, ('path', 'sha256'), 'selection metadata reference')
    raw = _host_read(selection_ref['path'], selection_ref['sha256'])
    selection = validate_selection(proof.parse_document(raw))
    profile, review, refs = _recipe_metadata()
    for supplier in proof.SOURCES:
        archive = selection['sources'][supplier]['archive']
        if (archive['sha256'] != profile['components'][supplier]['sha256'] or
                PureWindowsPath(archive['path']).name != profile['components'][supplier]['archive']):
            raise ValueError('Selected supplier archive pin differs: ' + supplier)
    return DependencyInputs(copy.deepcopy(selection_ref), selection, profile, review,
                            refs, tuple(_activation_gaps(review)))


def plan(selection_ref):
    """Produce no executable plan while original Windows supplier reviews are absent."""
    inputs = inspect_selection(selection_ref)
    if inputs.missing:
        raise MissingInputs(inputs.missing)
    raise ValueError('No admitted Windows dependency recipe implementation')


def require_native_host():
    if os.name != 'nt' or platform.machine().upper() not in ('AMD64', 'X86_64') or struct.calcsize('P') != 8:
        raise ValueError('Native Windows x64 host required for dependency execution/admission')


def build(plan_ref):
    """Explicit native operation; no arbitrary Workspace or qualification injection."""
    require_native_host()
    _require_reviewed_recipe()  # before plan/body reads and any output mutation
    raise ValueError('No admitted Windows dependency executable plan')


def validate_source_declarations(identity_raw, identity_pin, receipt_raw, receipt_pin, native_inputs):
    """Pure H/D declaration checking; expected commands never come from D itself."""
    identity = proof.validate_toolchain_identity(identity_raw, identity_pin)
    contract.pin(receipt_pin, 'original dependency D')
    if type(receipt_raw) is not bytes or _hash(receipt_raw) != receipt_pin:
        raise ValueError('Original dependency receipt SHA256 mismatch')
    receipt = proof.parse_document(receipt_raw)
    inputs = contract.validate_inputs(native_inputs)
    if inputs['woff2'] != 'OFF':
        raise ValueError('Windows dependency recipe v1 requires WOFF2 OFF')
    _source_receipt_envelope(receipt, identity_pin, identity, inputs)
    # Shape validation alone is not original command authority. In particular do
    # not construct expected={k:receipt[k]} and certify a self-authored command.
    _require_reviewed_recipe()
    raise ValueError('No independent reviewed Windows source declaration join')


def _source_receipt_envelope(receipt, identity_pin, identity, inputs):
    """Closed source-only H/D/prefix joins, without certifying literal commands."""
    _fields(receipt, ('schema_version', 'kind', 'target', 'scope', 'bindings',
        'commands', 'prefix', 'libraries', 'postflight', 'probe', 'facts'), 'dependency D')
    for name, wanted in {'schema_version': 1, 'kind': proof.RECEIPT_KIND,
            'target': proof.TARGET, 'scope': proof.SCOPE}.items():
        _equal(receipt[name], wanted, 'dependency D ' + name)
    paths = proof._Paths()
    proof._bindings(receipt['bindings'], paths)
    profile, _review, _refs = _recipe_metadata()
    for supplier, selected in receipt['bindings']['sources'].items():
        component = profile['components'][supplier]
        _equal(selected['version'], component['version'], supplier + ' original source version')
        _equal({key: selected['archive'][key] for key in ('sha256', 'bytes', 'format', 'strip_prefix')},
               {key: component[key] for key in ('sha256', 'bytes', 'format', 'strip_prefix')},
               supplier + ' exact retained source archive')
        _equal(PureWindowsPath(selected['archive']['path']).name, component['archive'],
               supplier + ' archive identity name')
    _equal(receipt['bindings']['toolchain_identity_sha256'], identity_pin, 'D/H pin')
    controller = receipt['bindings']['controller']
    _equal(controller['program'], identity['programs']['python'], 'D/H controller Python')
    _equal(controller['runtime_subject_sha256'], identity['inventories']['host_generators']['subject_sha256'],
           'D/H complete controller runtime')
    proof._prefix(receipt['prefix'], paths)
    _equal(receipt['prefix']['root'], inputs['dependency_prefix'], 'D/native prefix')
    proof._libraries(receipt['libraries'], receipt['bindings'], receipt['prefix'], paths, True)
    native_map = {target: {key: item[key] for key in ('path', 'sha256', 'includes', 'definitions', 'links')}
                  for target, item in receipt['libraries'].items()}
    _equal(native_map, inputs['libraries'], 'D/native Windows20 map')
    for name in ('compiler', 'linker', 'builtins'):
        selected = identity['builtins'] if name == 'builtins' else {
            key: identity['programs'][name][key] for key in ('path', 'sha256')}
        _equal(selected, inputs['toolchain'][name], 'H/native ' + name)
    _equal(identity['inventories']['llvm']['version'], inputs['toolchain']['compiler_version'], 'H/native LLVM release')
    for role in ('msvc_stl', 'windows_sdk'):
        _equal(identity['inventories'][role]['root'], inputs['toolchain'][role]['root'], 'H/native ' + role + ' root')
    _fields(receipt['facts'], proof.FALSE_FACTS, 'unqualified D facts')
    for name in proof.FALSE_FACTS:
        _equal(receipt['facts'][name], False, 'D ' + name)
    # Strict finite command envelope, without treating its self-declarations as
    # reviewed authority. Original expected command derivation is still missing.
    proof._array(receipt['commands'], 'D commands', proof.MAX_COMMANDS, 1)
    declarations = []
    for command in receipt['commands']:
        _fields(command, proof.COMMAND_FIELDS + ('logs', 'output_subject_sha256', 'job'), 'D command')
        declaration = {key: command[key] for key in proof.COMMAND_FIELDS}
        proof._command(declaration, paths)
        _command_toolchain_join(declaration, identity)
        proof._job(command['job'], declaration)
        _fields(command['logs'], ('combined',), 'D log')
        _reference(command['logs']['combined'], 'D original closed log', paths)
        contract.pin(command['output_subject_sha256'], 'D command outputs')
        declarations.append(declaration)
    proof._probe(receipt['probe'], declarations, receipt['libraries'], paths)
    _fields(receipt['postflight'], ('toolchain_identity_sha256', 'sources'), 'D postflight')
    _equal(receipt['postflight']['toolchain_identity_sha256'], identity_pin, 'D postflight H')
    _equal(receipt['postflight']['sources'], {
        supplier: item['source_subject_sha256'] for supplier, item in receipt['bindings']['sources'].items()},
        'D postflight source projections')


def _command_toolchain_join(command, identity):
    """Join source declarations to H; this does not observe native tool versions.

    The current finite PATH policy admits only exact parents of H's selected
    programs. A different runtime directory needs a future reviewed H/recipe
    capability; merely being below some retained root supplies no authority.
    """
    matches = [role for role, selected in identity['programs'].items()
               if proof.encoded(command['program']) == proof.encoded(selected)]
    if len(matches) != 1:
        raise ValueError('Command program path/hash/version does not join one exact H role')
    environment = {name.casefold(): value for name, value in command['environment'].items()}
    _equal(environment['systemroot'], identity['system_root'], 'command/H SystemRoot')
    directories = environment['path'].split(';')
    allowed = {PureWindowsPath(selected['path']).parent.as_posix()
               for selected in identity['programs'].values()}
    if (not directories or len(directories) > len(allowed) or
            len({path.casefold() for path in directories}) != len(directories) or
            any(path not in allowed for path in directories)):
        raise ValueError('Command PATH must use unique exact H program parent directories')
    return matches[0]


def admit_dependency_producer(receipt_ref, native_inputs, inventories, identity):
    """Native receipt admission requires genuine recipe authority before body IO."""
    require_native_host()
    _require_reviewed_recipe()
    raise ValueError('No admitted Windows dependency producer recipe')


def _inventory_encoded(value):
    """Canonical bytes for already shape/count/size-bounded inventory metadata.

    Complete inventories have a 32 MiB domain. H and D retain the proof module's
    separate 4 MiB and node bounds; those caps must not reject a valid SDK/source
    inventory before its fixed-size subject is formed.
    """
    raw = contract.encoded(value)
    if len(raw) > 32 * 1024**2:
        raise ValueError('Complete inventory metadata exceeds byte bound')
    return raw


def _inventory_equal(actual, expected, label):
    if _inventory_encoded(actual) != _inventory_encoded(expected):
        raise ValueError('Different ' + label)


def _subject(value):
    raw = _inventory_encoded({k: v for k, v in value.items() if k != 'provenance'})
    return _hash(raw)


def _source_projection(value, supplier, expected_identity):
    """Validate this producer's thirteen-source metadata projection, before D/H joins.

    This validator performs no archive extraction and claims no body admission.
    Each regular member has one canonical path/hash/size; notices are actual
    selected source members. No engine 157-file replay or handoff is involved.
    """
    _fields(value, ('schema_version', 'kind', 'target', 'supplier', 'identity',
        'source_root', 'files', 'directories', 'notices', 'transformations'), 'supplier replay')
    _equal(value['schema_version'], 1, 'supplier replay schema')
    _equal(value['kind'], 'foundation-native-engine-windows-dependency-source-replay-v1', 'supplier replay kind')
    _equal(value['target'], proof.TARGET, 'supplier replay target')
    _equal(value['supplier'], supplier, 'supplier replay owner')
    _equal(value['identity'], expected_identity, 'supplier original archive')
    proof.windows_path(value['source_root'])
    if type(value['files']) is not dict or not 1 <= len(value['files']) <= MAX_SOURCE_FILES:
        raise ValueError('Bounded complete supplier source file map required')
    paths, total = proof._Paths(), 0
    directories = value['directories']
    if type(directories) is not list or directories != sorted(set(directories)) or len(directories) > MAX_SOURCE_FILES:
        raise ValueError('Sorted bounded source directories required')
    for name in directories:
        paths.add(value['source_root'] + '/' + _relative(name), 'directory')
    for name, record in value['files'].items():
        _fields(record, ('sha256', 'bytes'), 'source member')
        contract.pin(record['sha256'], 'source member')
        total += _integer(record['bytes'], 'source bytes', 0, MAX_SOURCE_BYTES)
        paths.add(value['source_root'] + '/' + _relative(name), 'file', record['sha256'])
        if any(str(parent) != '.' and str(parent) not in directories
               for parent in PurePosixPath(name).parents):
            raise ValueError('Source projection omits a parent directory')
    if total > MAX_SOURCE_BYTES:
        raise ValueError('Supplier source total byte bound exceeded')
    notices = value['notices']
    if type(notices) is not list or not 1 <= len(notices) <= 256 or notices != sorted(set(notices)):
        raise ValueError('Bounded selected source notices required')
    if any(_relative(name) not in value['files'] for name in notices):
        raise ValueError('Source notice is not a projected original source member')
    # Reviewed transformations need explicit before/after/member identities in a
    # future schema. A caller cannot supply a patch or normalized source here.
    _equal(value['transformations'], [], 'unreviewed source transformations')
    source_subject = {'root': value['source_root'], 'files': value['files'], 'directories': directories}
    return {'source_subject_sha256': _hash(_inventory_encoded(source_subject)),
            'notice_subject_sha256': _hash(_inventory_encoded({name: value['files'][name] for name in notices}))}


def _archive_projection(raw, component):
    """Use the bounded structural iterator; no engine replay or source authority.

    ARCHIVE_HELPER_SOURCES names the complete repository import closure. Eventual
    producer identities must bind that closure, including document/editor pure
    contracts reached through the native-actions module. Only the four generic
    stream helpers are used; no handoff or engine-proof operation is invoked.
    """
    if (type(raw) is not bytes or len(raw) > MAX_SOURCE_ARCHIVE_BYTES or
            len(raw) != component['bytes'] or _hash(raw) != component['sha256']):
        raise ValueError('Original supplier archive bytes differ')
    if component['format'] not in ('zip', 'tar-gzip', 'tar-xz'):
        raise ValueError('Unsupported original supplier archive format')
    from appended_engine_windows_source_replay import (
        _Budget, _BoundedStream, _archive_entries, _read_member)
    budget = _Budget({'seconds': 60, 'maximum_archive_bytes': MAX_SOURCE_ARCHIVE_BYTES,
        'maximum_expanded_bytes': MAX_SOURCE_BYTES, 'maximum_members': MAX_SOURCE_FILES * 2,
        'maximum_member_bytes': MAX_SOURCE_MEMBER_BYTES, 'maximum_patch_bytes': 1024**2})
    source = _BoundedStream(io.BytesIO(raw), len(raw), budget)
    paths, files, directories = proof._Paths(), {}, set()
    seen = set()
    prefix = component['strip_prefix']
    for name, kind, _mode, size, _link, stream in _archive_entries(source, component['format'], budget):
        budget.member(size)
        if kind not in ('file', 'directory'):
            raise ValueError('Nonordinary/link supplier archive member')
        directory = kind == 'directory'
        if name in (prefix, prefix + '/') and directory:
            continue
        if directory and name.endswith('/'):
            name = name[:-1]
        if not name.startswith(prefix + '/'):
            raise ValueError('Supplier member outside exact strip prefix')
        relative = _relative(name[len(prefix) + 1:])
        path = 'C:/source/' + relative
        if path.casefold() in seen:
            raise ValueError('Duplicate or case-aliased supplier archive member')
        seen.add(path.casefold())
        paths.add(path, 'directory' if directory else 'file')
        for parent in PurePosixPath(relative).parents:
            if str(parent) != '.': directories.add(str(parent))
        if directory:
            directories.add(relative)
            continue
        member_pin, _body = _read_member(stream, size, False, budget)
        files[relative] = {'sha256': member_pin, 'bytes': size}
    if not files:
        raise ValueError('Empty supplier source projection')
    return {'files': files, 'directories': sorted(directories)}


def _native_sources(selection, profile):
    """Admit original13 archives and exact unmodified retained source projections.

    Called only by a future admitted recipe activation. Replays have this
    controller's supplier schema; the engine handoff/replay is unrelated.
    """
    require_native_host()
    from appended_engine_windows_prototype import _read, _ordinary, _document
    result, protected_paths, roots = {}, [], []
    for supplier in proof.SOURCES:
        selected = selection['sources'][supplier]
        component = profile['components'][supplier]
        replay = _document(selected['replay']['path'], selected['replay']['sha256'])
        facts = _source_projection(replay, supplier, component)
        source_root = replay['source_root']
        for other in roots + [selection['output']]:
            if (source_root.casefold() == other.casefold() or
                    source_root.casefold().startswith(other.casefold() + '/') or
                    other.casefold().startswith(source_root.casefold() + '/')):
                raise ValueError('Supplier source roots and output must be disjoint')
        roots.append(source_root)
        protected_paths += [source_root, selected['archive']['path'], selected['replay']['path']]
        original = _archive_projection(_read(selected['archive']['path'], component['sha256'],
                                            maximum=512 * 1024**2), component)
        _inventory_equal(original, {key: replay[key] for key in ('files', 'directories')},
               supplier + ' original archive/source projection')
        root = _ordinary(replay['source_root'], directory=True)
        observed_files, observed_directories, pending = {}, [], [root]
        while pending:
            current = pending.pop()
            with os.scandir(current) as children:
                for child in children:
                    name = Path(child.path).relative_to(root).as_posix()
                    if name in replay['directories']:
                        _ordinary(child.path, directory=True)
                        observed_directories.append(name); pending.append(Path(child.path))
                    elif name in replay['files']:
                        record = replay['files'][name]
                        body = _read(child.path, record['sha256'], maximum=512 * 1024**2)
                        observed_files[name] = {'sha256': _hash(body), 'bytes': len(body)}
                    else:
                        raise ValueError('Unlisted retained supplier source entry')
        _inventory_equal({'files': observed_files, 'directories': sorted(observed_directories)}, original,
               supplier + ' complete retained source tree')
        result[supplier] = {'version': component['version'], 'archive': {
            'path': selected['archive']['path'], **{key: component[key]
                for key in ('sha256', 'bytes', 'format', 'strip_prefix')}},
            'replay': copy.deepcopy(selected['replay']), **facts}
    return {'bindings': result, 'protected_paths': protected_paths}


def _native_toolchain(identity, inventory_refs):
    """Check native bodies; missing original version authority prevents H admission."""
    require_native_host()
    from appended_engine_windows_prototype import (
        inspect_inventory, inspect_static_archive, inspect_tool_image, _document, _read, _selected_file)
    identity = proof.toolchain_identity(identity)
    _fields(inventory_refs, proof.INVENTORIES, 'native toolchain references')
    inventories = {role: inspect_inventory(inventory_refs[role], role) for role in proof.INVENTORIES}
    actual_subjects = {}
    for role, inventory in inventories.items():
        metadata = _document(inventory_refs[role]['path'], inventory_refs[role]['sha256'])
        actual_subjects[role] = {'root': inventory['root'], 'version': inventory['version'],
                                  'subject_sha256': _subject(metadata)}
    for role, item in identity['programs'].items():
        reference = {k: item[k] for k in ('path', 'sha256')}
        owner = 'llvm' if role in proof.LLVM_PROGRAMS else 'host_generators'
        path = _selected_file(reference, inventories, (owner,), role)
        image = inspect_tool_image(_read(path, item['sha256']))
        if image['dll']:
            raise ValueError('Selected program is a DLL: ' + role)
    allowed = set(proof.CRT_LIBRARIES) | set(proof.SYSTEM_LINKS) | {'clang_rt.builtins-x86_64'}
    for role, item in [('builtins', identity['builtins']), *identity['crt_libraries'].items()]:
        owners = ('llvm',) if role == 'builtins' else ('windows_sdk',) if role == 'libucrt' else ('msvc_stl',)
        path = _selected_file(item, inventories, owners, role)
        inspect_static_archive(_read(path, item['sha256']), allowed_default_libraries=allowed)
    for category in ('include_directories', 'library_directories'):
        for directory in identity[category]:
            matches = [inv for inv in inventories.values() if directory.startswith(inv['root'] + '/') and
                directory[len(inv['root']) + 1:] in inv['directories']]
            if len(matches) != 1:
                raise ValueError('Tool search path not in exactly one inventory')
    _equal(actual_subjects, identity['inventories'], 'native complete inventory subjects')
    actual_root = os.environ.get('SystemRoot', '').replace('\\', '/')
    _equal(actual_root, identity['system_root'], 'actual OS SystemRoot')
    selected_python = identity['programs']['python']
    _equal(str(Path(sys.executable)).replace('\\', '/'), selected_python['path'], 'actual controller Python')
    _equal(platform.python_version(), selected_python['version'], 'actual Python version')
    # Entire interpreter tree was admitted above; verify the running image again.
    _read(sys.executable, selected_python['sha256'])
    # PE machine/import checking does not observe the selected program version.
    # The future finite recipe must admit original version commands/resources.
    raise MissingInputs([{'role': 'windows-dependency-original-tool-version-observations',
        'path': '<reviewed finite Windows tool version observations>',
        'reason': 'complete native bytes and controller runtime checks do not establish original version observation authority'}])


def _open_workspace(inputs, identity, protected_paths):
    """Obtain the actual qualified A Workspace; never accept a supplied instance."""
    require_native_host()
    from appended_engine_windows_publication import Workspace, admit_qualification, _Native
    selection = validate_selection(inputs.selection)
    identity = proof.toolchain_identity(identity)
    publication = selection['publication']
    source = {name: _hash(_host_read(ROOT / name, publication['source_identity'][name]))
              for name in PUBLICATION_SOURCES}
    # Native obtains SystemRoot from the OS, not the retained SDK or ambient PATH.
    runtime = _Native().runtime_identity()
    _equal(runtime, publication['runtime_identity'], 'actual publication runtime')
    _equal(runtime['python_path'], identity['programs']['python']['path'], 'H/actual controller path')
    _equal(runtime['python_sha256'], identity['programs']['python']['sha256'], 'H/actual controller bytes')
    _equal(runtime['python_version'], identity['programs']['python']['version'], 'H/actual controller version')
    _equal(runtime['system_root'], identity['system_root'], 'H/actual OS root')
    qualification = admit_qualification(publication['qualification'],
        source_identity=source, runtime_identity=runtime)
    return Workspace.create_new(selection['output'], protected_paths=protected_paths,
        limits=selection['limits'], qualification=qualification)


def _validate_prefix_metadata(metadata):
    _fields(metadata, ('schema_version', 'kind', 'role', 'target', 'root', 'version',
        'files', 'directories', 'provenance'), 'dependency prefix inventory')
    for name, wanted in {'schema_version': 1, 'kind': 'foundation-windows-retained-inventory-v1',
            'role': 'native_dependencies', 'target': proof.TARGET}.items():
        _equal(metadata[name], wanted, 'prefix ' + name)
    proof.windows_path(metadata['root']); contract.text(metadata['version'], 'prefix version')
    if type(metadata['files']) is not dict or not 1 <= len(metadata['files']) <= MAX_SOURCE_FILES:
        raise ValueError('Bounded complete prefix file map required')
    directories = metadata['directories']
    if type(directories) is not list or directories != sorted(set(directories)) or len(directories) > MAX_SOURCE_FILES:
        raise ValueError('Bounded sorted prefix directories required')
    paths, total = proof._Paths(), 0
    for name in directories:
        paths.add(metadata['root'] + '/' + _relative(name), 'directory')
    for name, record in metadata['files'].items():
        _fields(record, ('sha256', 'bytes'), 'prefix file')
        contract.pin(record['sha256'], 'prefix file')
        total += _integer(record['bytes'], 'prefix file bytes', 0, 512 * 1024**2)
        paths.add(metadata['root'] + '/' + _relative(name), 'file', record['sha256'])
        if any(str(parent) != '.' and str(parent) not in directories for parent in PurePosixPath(name).parents):
            raise ValueError('Prefix omits a parent directory')
    if total > 32 * 1024**3:
        raise ValueError('Prefix total byte bound exceeded')
    _reference(metadata['provenance'], 'later prefix provenance', paths)


def _inspect_prefix(metadata, libraries, read_body, inspect_archive):
    """Join the complete retained prefix inventory and inspect each archive."""
    _validate_prefix_metadata(metadata)
    _fields(libraries, proof.LIBRARY_SUPPLIERS, 'prefix Windows20 map')
    defaults = set(proof.CRT_LIBRARIES) | set(proof.SYSTEM_LINKS) | {'clang_rt.builtins-x86_64'}
    defaults |= {PureWindowsPath(library['path']).stem.casefold() for library in libraries.values()}
    inspected = {}
    for target, library in libraries.items():
        path = library['path']
        if not path.startswith(metadata['root'] + '/'):
            raise ValueError('Dependency library escapes prefix')
        relative = path[len(metadata['root']) + 1:]
        record = metadata['files'].get(relative)
        if type(record) is not dict or record.get('sha256') != library['sha256']:
            raise ValueError('Library absent from complete prefix snapshot')
        raw = read_body(path, library['sha256'])
        if len(raw) != record.get('bytes') or _hash(raw) != library['sha256']:
            raise ValueError('Prefix archive bytes changed')
        result = inspect_archive(raw, allowed_default_libraries=defaults)
        if result.get('format') != 'coff-archive' or result.get('machine') != 'x86_64':
            raise ValueError('Prefix needs native static AMD64 COFF archives')
        inspected[target] = {'archive_sha256': library['sha256'], 'format': 'coff-static',
            'machine': 'AMD64', 'member_count': len(result['members']),
            **{name: 0 for name in proof.INSPECTION_FIELDS[4:]}}
    return _subject(metadata), inspected


def _absolute_row(workspace, row):
    _fields(row, ('path', 'sha256', 'bytes'), 'owned publication row')
    _relative(row['path'])
    contract.pin(row['sha256'], 'owned publication row')
    return {'path': workspace.output + '/' + row['path'], 'sha256': row['sha256']}


def _probe_link_inputs(libraries, identity, system_libraries):
    """Exact closure: Windows20, five CRT archives, builtins, reviewed SDK system libs."""
    identity = proof.toolchain_identity(identity)
    _fields(libraries, proof.LIBRARY_SUPPLIERS, 'probe Windows20')
    if type(system_libraries) is not list or len(system_libraries) > len(proof.SYSTEM_LINKS):
        raise ValueError('Bounded reviewed SDK system libraries required')
    result = [{key: libraries[target][key] for key in ('path', 'sha256')}
              for target in sorted(proof.LIBRARY_SUPPLIERS)]
    result += [copy.deepcopy(identity['crt_libraries'][role]) for role in proof.CRT_LIBRARIES]
    result.append(copy.deepcopy(identity['builtins']))
    for item in system_libraries:
        _reference(item, 'reviewed SDK system link')
        if (not item['path'].startswith(identity['inventories']['windows_sdk']['root'] + '/') or
                PureWindowsPath(item['path']).stem not in proof.SYSTEM_LINKS or
                not any(item['path'].startswith(directory + '/') for directory in identity['library_directories'])):
            raise ValueError('Probe system link escapes selected SDK/static system map')
        result.append(copy.deepcopy(item))
    paths = proof._Paths()
    seen = set()
    for item in result:
        _reference(item, 'probe static closure', paths)
        if item['path'].casefold() in seen:
            raise ValueError('Aliased probe static input')
        seen.add(item['path'].casefold())
    return result


def _verify_probe(command, libraries, identity, system_libraries, output, read_body, inspect_image,
                  *, reviewed_objects=()):
    """Check finite whole-archive link declarations and inspect the resulting PE.

    Object refs and bytes are a private structural input. Original object source
    and compilation authority remain the named public activation gap; no source
    graph, object command or D object-provenance schema is invented here.
    """
    proof._command(command, proof._Paths())
    _equal(command['stage'], 'probe', 'closure probe stage')
    identity = proof.toolchain_identity(identity)
    _command_toolchain_join(command, identity)
    _equal(command['program'], identity['programs']['linker'], 'selected direct lld-link probe')
    references = _probe_link_inputs(libraries, identity, system_libraries)
    # This finite direct-argument route accepts no opaque response-file escape.
    # A future reviewed response-file recipe must bind its literal content too.
    if command['response_files']:
        raise ValueError('Reviewed direct-argument static probe required')
    if type(reviewed_objects) not in (list, tuple) or not 1 <= len(reviewed_objects) <= 64:
        raise ValueError('Bounded nonempty reviewed probe object references required')
    _reference(output, 'closure probe linked output')
    if not output['path'].endswith('.exe'):
        raise ValueError('Native closure probe output requires its exact .exe path')
    paths, objects = proof._Paths(), []
    for reference in references:
        _reference(reference, 'probe static closure', paths)
    for reference in reviewed_objects:
        selected = _reference(reference, 'reviewed probe object', paths)
        if not selected['path'].endswith('.obj') or any(
                selected['path'].casefold() == other['path'].casefold() for other in objects):
            raise ValueError('Canonical unique reviewed .obj references required')
        objects.append(selected)
    _reference(output, 'closure probe linked output', paths)
    # Retaining every archive member, with explicit default libraries and no
    # reference/ICF discards, discriminates the whole static closure from a
    # successful tag-only probe that extracted no dependency archive members.
    required = ['/NODEFAULTLIB', '/MACHINE:X64', '/OPT:NOREF', '/OPT:NOICF',
                '/OUT:' + output['path']]
    required += ['/WHOLEARCHIVE:' + reference['path'] for reference in references[:20]]
    required += [reference['path'] for reference in references[20:] + objects]
    optional = {'/NOLOGO', '/WX', '/INCREMENTAL:NO', '/SUBSYSTEM:CONSOLE', '/Brepro'}
    arguments = command['argv'][1:]
    if (any(arguments.count(argument) != 1 for argument in required) or
            any(argument not in required and argument not in optional for argument in arguments) or
            any(arguments.count(argument) > 1 for argument in optional)):
        raise ValueError('Probe requires exact retained whole-archive inputs and finite direct lld-link flags')
    for reference in references:
        read_body(reference['path'], reference['sha256'])
    for reference in objects:
        body = read_body(reference['path'], reference['sha256'])
        if type(body) is not bytes or _hash(body) != reference['sha256']:
            raise ValueError('Reviewed probe object bytes differ from original pin')
    raw = read_body(output['path'], output['sha256'])
    if _hash(raw) != output['sha256']:
        raise ValueError('Closure probe output changed')
    image = inspect_image(raw)
    if image.get('format') != 'pe32plus' or image.get('machine') != 'x86_64' or image.get('dll') is not False:
        raise ValueError('Closure probe must be a native AMD64 executable')
    allowed = {'kernel32.dll', 'kernelbase.dll', 'ntdll.dll',
               *[name + '.dll' for name in proof.SYSTEM_LINKS]}
    if any(name not in allowed for name in image['needed']):
        raise ValueError('Static closure probe imports an unadmitted runtime')
    return {'command_id': command['id'], 'library_targets': sorted(proof.LIBRARY_SUPPLIERS),
            'link_inputs': references, 'output': copy.deepcopy(output)}


@dataclass(frozen=True)
class _CandidateReceipt:
    raw: bytes
    _seal: object


def _assemble_receipt(bindings, declarations, commands, prefix, libraries, inspections, probe):
    """Assemble observations; independently derived declarations remain explicit."""
    proof._bindings(bindings, proof._Paths())
    helper_paths = [item['path'] for item in bindings['producer']['helpers']]
    missing_helpers = [name for name in ARCHIVE_HELPER_SOURCES
                       if not any(path.endswith('/' + name) for path in helper_paths)]
    if missing_helpers:
        raise ValueError('Controller archive helper source closure missing: ' + ', '.join(missing_helpers))
    expected = {'bindings': copy.deepcopy(bindings),
        'commands': copy.deepcopy(declarations),
        'prefix': copy.deepcopy(prefix), 'libraries': copy.deepcopy(libraries),
        'probe': copy.deepcopy(probe)}
    receipt = {'schema_version': 1, 'kind': proof.RECEIPT_KIND, 'target': copy.deepcopy(proof.TARGET),
        'scope': proof.SCOPE, 'bindings': copy.deepcopy(bindings), 'commands': copy.deepcopy(commands),
        'prefix': copy.deepcopy(prefix), 'libraries': {
            target: {**copy.deepcopy(library), 'inspection': copy.deepcopy(inspections[target])}
            for target, library in libraries.items()}, 'probe': copy.deepcopy(probe),
        'postflight': {'toolchain_identity_sha256': bindings['toolchain_identity_sha256'],
            'sources': {supplier: item['source_subject_sha256'] for supplier, item in bindings['sources'].items()}},
        'facts': {name: False for name in proof.FALSE_FACTS}}
    # Here the declaration source is the controller's finite reviewed plan plus
    # admitted output pins; this assembly helper is not source-only authority.
    checked = proof.validate_receipt(receipt, expected)
    return _CandidateReceipt(proof.encoded(checked), _CANDIDATE_TOKEN)


def _publish_candidate(workspace, candidate, prefix_inventory, native_inputs, notice_refs):
    """Publish D, then provenance/inventory/native inputs, without a hash cycle.

    The caller has joined every writer, frozen/rechecked inputs, and assembled D
    from reviewed declarations. No arbitrary original report is accepted here.
    Failure stops dependent publication and retains the owned Workspace.
    """
    if type(candidate) is not _CandidateReceipt or candidate._seal is not _CANDIDATE_TOKEN:
        raise ValueError('Controller-assembled original dependency receipt required')
    receipt = proof.parse_document(candidate.raw)
    _validate_prefix_metadata(prefix_inventory)
    _equal(prefix_inventory['root'], receipt['prefix']['root'], 'published prefix root')
    _equal(_subject(prefix_inventory), receipt['prefix']['inventory_subject_sha256'], 'published prefix subject')
    if prefix_inventory.get('role') != 'native_dependencies' or prefix_inventory.get('kind') != 'foundation-windows-retained-inventory-v1':
        raise ValueError('Complete retained native dependency inventory required')
    proof._array(notice_refs, 'prefix original notices', 256, 1)
    for reference in notice_refs:
        _reference(reference, 'prefix notice')
    before = workspace.inspect_outputs()
    prefix_root = prefix_inventory['root']
    if not prefix_root.startswith(workspace.output + '/'):
        raise ValueError('Published prefix escapes owned Workspace')
    relative_prefix = prefix_root[len(workspace.output) + 1:] + '/'
    actual_files = {name[len(relative_prefix):]: {key: row[key] for key in ('sha256', 'bytes')}
        for name, row in before['files'].items() if name.startswith(relative_prefix)}
    actual_directories = [name[len(relative_prefix):] for name in before['directories']
                          if name.startswith(relative_prefix)]
    _inventory_equal(actual_files, prefix_inventory['files'], 'complete actual prefix files')
    _inventory_equal(actual_directories, prefix_inventory['directories'], 'complete actual prefix directories')
    for target, library in receipt['libraries'].items():
        name = library['path'][len(prefix_root) + 1:]
        if actual_files.get(name, {}).get('sha256') != library['sha256']:
            raise ValueError('Published Windows20 archive not in actual prefix: ' + target)
        if any(directory[len(prefix_root) + 1:] not in actual_directories for directory in library['includes']):
            raise ValueError('Published library include directory absent from actual prefix')
    for reference in notice_refs:
        if (not reference['path'].startswith(prefix_root + '/') or
                actual_files.get(reference['path'][len(prefix_root) + 1:], {}).get('sha256') != reference['sha256']):
            raise ValueError('Published notice not in actual complete prefix')
    notice_names = {reference['path'][len(prefix_root) + 1:] for reference in notice_refs}
    library_names = {library['path'][len(prefix_root) + 1:] for library in receipt['libraries'].values()}
    _equal(receipt['prefix']['notice_subject_sha256'], _hash(_inventory_encoded({
        name: actual_files[name] for name in sorted(notice_names)})), 'actual prefix notice subject')
    _equal(receipt['prefix']['header_data_subject_sha256'], _hash(_inventory_encoded({
        'root': prefix_root, 'files': {name: row for name, row in actual_files.items()
            if name not in notice_names | library_names}, 'directories': actual_directories})),
        'actual prefix header/data subject')
    native = contract.validate_inputs(native_inputs)
    _equal(native['dependency_prefix'], prefix_root, 'published native prefix')
    _equal(native['libraries'], {target: {key: library[key] for key in
        ('path', 'sha256', 'includes', 'definitions', 'links')}
        for target, library in receipt['libraries'].items()}, 'published native Windows20 map')
    workspace.check_anchors()
    workspace.mkdir_new('metadata')
    receipt_ref = _absolute_row(workspace, workspace.commit_receipt_new(
        'metadata/dependency-receipt.json', candidate.raw))
    provenance = {'schema_version': 1, 'kind': 'foundation-windows-retained-provenance-v1',
        'role': 'native_dependencies', 'target': copy.deepcopy(proof.TARGET),
        'inventory_subject_sha256': receipt['prefix']['inventory_subject_sha256'],
        'sources': [{key: item['archive'][key] for key in ('path', 'sha256')}
                    for item in receipt['bindings']['sources'].values()],
        'notices': copy.deepcopy(notice_refs), 'original_reports': [receipt_ref]}
    provenance_ref = _absolute_row(workspace, workspace.publish_bytes_new(
        'metadata/dependency-provenance.json', proof.encoded(provenance)))
    inventory = {**copy.deepcopy(prefix_inventory), 'provenance': provenance_ref}
    inventory_ref = _absolute_row(workspace, workspace.publish_bytes_new(
        'metadata/dependency-inventory.json', _inventory_encoded(inventory)))
    native['dependency_inventory'] = inventory_ref
    native = contract.validate_inputs(native)
    manifest_ref = _absolute_row(workspace, workspace.publish_bytes_new(
        'metadata/native-inputs.json', proof.encoded(native)))
    after = workspace.inspect_outputs()
    # Existing output bytes must remain frozen across all publication steps.
    if (any(after['files'].get(name) != row for name, row in before['files'].items()) or
            {name for name in after['files'] if name.startswith(relative_prefix)} !=
            {name for name in before['files'] if name.startswith(relative_prefix)} or
            [name for name in after['directories'] if name.startswith(relative_prefix)] !=
            [name for name in before['directories'] if name.startswith(relative_prefix)]):
        workspace.retain_uncertain(None, None, 'output changed during candidate publication')
        raise ValueError('Frozen output changed during publication')
    workspace.close_joined()
    return {'receipt': receipt_ref, 'inventory': inventory_ref, 'native_inputs': manifest_ref,
            **{name: False for name in proof.FALSE_FACTS}}


def _run_stage(workspace, declaration, limits, *, monotonic=time.monotonic,
               pause=time.sleep):
    """Private owned-stage primitive; Workspace owns launch and log association.

    Workspace, rather than a serialized flag, joins and closes the actual owner.
    Public build never accepts these adapters or a prequalified Workspace.
    """
    proof._command(declaration, proof._Paths())
    limits = validate_limits(limits)
    log = workspace.open_log_new('logs/' + declaration['id'] + '.log')
    workspace.mark_running(log)  # launch intent precedes every possible writer
    started, owner, joined, sealed = monotonic(), None, None, False
    join_attempted, seal_attempted = False, False
    peak_count, peak_output = 1, 0
    budget = limits[declaration['stage'] + '_seconds']
    def sample():
        nonlocal peak_count, peak_output
        workspace.check_anchors()
        usage = workspace.usage(log=log)
        size = usage['bytes']
        peak_output = max(peak_output, size)
        if size > limits['maximum_output_bytes'] or usage['log_bytes'] > limits['maximum_log_bytes']:
            raise ValueError('Dependency output/log bound exceeded')
        if owner is not None:
            count = owner.job.active()
            peak_count = max(peak_count, count)
            if count > limits['maximum_processes']:
                raise ValueError('Dependency Job process-count bound exceeded')
        if monotonic() - started >= budget:
            raise ValueError('Dependency command wall deadline exceeded')
    try:
        sample()
        owner = workspace.launch(log, declaration['argv'], declaration['cwd'],
                                 env=declaration['environment'])
        if owner.job is None:
            raise ValueError('Native command did not return a Windows Job owner')
        while owner.poll() is None:
            sample()
            pause(0.05)
        sample()
        # This call itself performs owner.finish()+close(); never call them here.
        join_attempted = True
        joined = workspace.mark_joined(log, {'phase': declaration['stage'],
            'argv': list(declaration['argv']), 'cwd': declaration['cwd']})
        observation = joined.as_dict()
        seal_attempted = True
        pinned = workspace.seal_log(log)
        pinned = _absolute_row(workspace, pinned)
        sealed = True
        if observation.get('returncode') != 0 or observation.get('process_tree_closed') is not True or observation.get('closure') != 'actual-bound-job-finish-and-close':
            raise ValueError('Dependency command did not complete successfully under its bound owner')
        usage = workspace.inspect_outputs()
        final_bytes = _integer(usage['bytes'], 'joined output bytes', 0, 2**63 - 1)
        peak_output = max(peak_output, final_bytes)
        if peak_output > limits['maximum_output_bytes']:
            raise ValueError('Dependency output byte bound exceeded after join')
        elapsed = int((monotonic() - started) * 1000)
        if elapsed >= budget * 1000:
            raise ValueError('Dependency command deadline exceeded at join')
        return joined, {**copy.deepcopy(declaration), 'logs': {'combined': pinned},
            'output_subject_sha256': _hash(_inventory_encoded(usage)), 'job': {
                'owner': 'windows-job-v1', 'launch_intent_sha256': _hash(proof.encoded(declaration)),
                'image': {k: declaration['program'][k] for k in ('path', 'sha256')},
                'launch_suspended': True, 'assigned_before_resume': True,
                'breakaway_allowed': False, 'kill_on_close': True, 'exit_code': observation['returncode'],
                'elapsed_milliseconds': elapsed, 'wall_limit_milliseconds': budget * 1000,
                # These fields are sampled monitoring observations. The missing
                # canonical pre-resume enforced Job limit blocks activation.
                'process_count': peak_count, 'process_limit': limits['maximum_processes'],
                'peak_output_bytes': peak_output, 'output_limit_bytes': limits['maximum_output_bytes'],
                'active_processes_at_join': 0, 'streams_closed': True,
                'join_completed': True, 'owner_closed': True}}
    except BaseException as error:
        if (join_attempted and joined is None) or (seal_attempted and not sealed):
            workspace.retain_uncertain(owner, log, str(error))
            raise
        try:
            if joined is None and owner is not None:
                owner.terminate(timeout=limits['cleanup_seconds'])
                join_attempted = True
                joined = workspace.mark_joined(log, {'phase': declaration['stage'],
                    'argv': list(declaration['argv']), 'cwd': declaration['cwd']})
            if joined is not None:
                workspace.mark_failed_joined(joined, str(error))
                if not sealed:
                    seal_attempted = True
                    workspace.seal_log(log)
            else:
                # launch() can conceal writers before returning an owner.
                workspace.retain_uncertain(owner, log, str(error))
        except BaseException as cleanup:
            workspace.retain_uncertain(owner, log, str(error) + '; cleanup/join: ' + str(cleanup))
        raise


def _execute_commands(workspace, declarations, limits):
    """Execute one finite reviewed supplier graph, without a shell or fallback.

    Process fixtures replace the entire private Workspace; this controller has
    no injectable launch callback. Public build accepts no Workspace, reviewed
    graph or successful qualification from a caller.
    """
    proof._array(declarations, 'reviewed graph', proof.MAX_COMMANDS, 1)
    stages = {supplier: [] for supplier in proof.SOURCES}
    ids = set()
    for command in declarations:
        proof._command(command, proof._Paths())
        if command['id'] in ids:
            raise ValueError('Duplicate reviewed command id')
        ids.add(command['id'])
        if command['supplier'] in stages:
            stages[command['supplier']].append(command['stage'])
    if any(value != ['configure', 'build', 'install'] for value in stages.values()):
        raise ValueError('Incomplete reviewed supplier graph')
    if sum(item['stage'] == 'probe' for item in declarations) != 1 or declarations[-1]['stage'] != 'probe':
        raise ValueError('Exactly one final reviewed closure probe required')
    workspace.mkdir_new('logs')
    observations = []
    for declaration in declarations:
        _joined, observation = _run_stage(workspace, declaration, limits)
        observations.append(observation)
    return observations


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    for action, name in (('plan', 'selection'), ('build', 'plan')):
        child = sub.add_parser(action)
        child.add_argument('--' + name, required=True)
        child.add_argument('--' + name + '-sha256', required=True)
    args = parser.parse_args(argv)
    name = 'selection' if args.action == 'plan' else 'plan'
    reference = {'path': getattr(args, name), 'sha256': getattr(args, name + '_sha256')}
    result = plan(reference) if args.action == 'plan' else build(reference)
    sys.stdout.write(proof.encoded(result).decode('ascii'))
    return 0


def cli(argv=None):
    try:
        return main(argv)
    except MissingInputs as error:
        sys.stdout.write(proof.encoded(error.as_dict()).decode('ascii'))
        return 2
    except (OSError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(cli())
