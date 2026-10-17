#!/usr/bin/env python3
"""Explicit, offline Linux dependency preparation for a native engine candidate.

Planning is passive. Building is a separate costly maintenance operation: it
never follows from a missing engine prefix or an appended application edit.
Only the fixed local-source CMake recipe may configure, compile and install.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import shutil
import stat
import struct
import sys
import tarfile
import time
import types
import zipfile

import appended_engine_manifest as manifest
import appended_engine_native_inputs as native_inputs
from dependency_archive import PathInventory
import process_tree

ROOT = Path(__file__).resolve().parents[1]
RECIPE = 'recipes/webkitwasm-native-deps-linux-x86_64-v1'
TARGET = {'system': 'Linux', 'processor': 'x86_64',
          'triple': 'x86_64-buildroot-linux-gnu', 'pointer_bits': 64}
SELECTION_KIND = 'foundation-native-engine-dependencies-selection-v1'
SOURCES_KIND = 'foundation-native-engine-dependency-sources-v1'
PLAN_KIND = 'foundation-native-engine-dependencies-plan-v1'
BUILD_KIND = 'foundation-native-engine-dependencies-build-v1'
MAX_DOCUMENT = 32 * 1024 * 1024
MAX_ARCHIVE_FILES = 1000000
MAX_MEMBER_BYTES = 256 * 1024 * 1024
MAX_EXPANDED_BYTES = 32 * 1024 * 1024 * 1024
MAX_OUTPUT_ENTRIES = 1000000
RECIPE_FILES = ('profile.json', 'source-review.json', 'CMakeLists.txt', 'cmake/components.cmake',
                'cmake/install-common.cmake',
                'cmake/install-selected.cmake', 'cmake/install-assets.cmake',
                'sqlite/CMakeLists.txt', 'pic/CMakeLists.txt', 'pic/probe.cpp',
                'pic/capture-commands.cmake', 'README.md', 'NOTICES.md')
PRODUCER_HELPERS = ('appended_engine_native_dependencies.py', 'appended_engine_native_inputs.py',
                    'appended_engine_native_actions_contract.py', 'appended_engine_document_contract.py',
                    'appended_engine_editor_contract.py', 'appended_engine_manifest.py',
                    'dependency_archive.py', 'process_tree.py')
PRODUCER_CONTROL_SOURCES = ('tools/appended_engine_native_sdk.py',
    'recipes/webkitwasm-native-rich4083-v1/producer/native-sdk-toolchain.cmake.in')
PRODUCER_SOURCES = tuple(RECIPE + '/' + name for name in RECIPE_FILES) + tuple(
    'tools/' + name for name in PRODUCER_HELPERS) + PRODUCER_CONTROL_SOURCES
PRIVATE_SHARED_SOURCES = (
    'recipes/webkitwasm-native-rich4083-v1/producer/private-cpp-runtime-policy-v1.json',
    'recipes/webkitwasm-native-rich4083-v1/producer/native-private-runtime.cmake',
    'recipes/webkitwasm-native-rich4083-v1/producer/verify-provider.cmake',
    'tools/appended_engine_native_original_proof.py',
    'tools/appended_engine_native_prototype.py')
# Keep fixed runtime indices and final checker path; join only new passive sources.
PRIVATE_SHARED_SOURCES = PRIVATE_SHARED_SOURCES[:-2] + native_inputs.ROLE7_PRODUCERS + PRIVATE_SHARED_SOURCES[-2:]
PRIVATE_KIND = 'foundation-native-engine-prototype-private-sdk-toolchain-v1'
PRIVATE_POLICY = 'private-static-gcc-sdk-v1'
PRIVATE_POLICY_SHA256 = '4983920c892241475f839f6bc6e7a293b348322e390307d4a1769b97ceab9bcc'
PRIVATE_EXPORT = 'foundation_native_dependency_pic_probe'
PRIVATE_EXPORT_RAW = b'{\n  global: foundation_native_dependency_pic_probe;\n  local: *;\n};\n'
PRIVATE_ROLE_NAMES = ('LIBSTDCXX', 'LIBGCC', 'LIBGCC_EH', 'CRTBEGINS', 'CRTENDS')
PRIVATE_CMAKE_INPUTS = ('NATIVE_PRIVATE_RUNTIME_HELPER', 'NATIVE_PRIVATE_RUNTIME_HELPER_SHA256',
    'BIB_NATIVE_RUNTIME_COMPILER_TRIPLE', 'BIB_NATIVE_RUNTIME_POLICY_SHA256',
    'BIB_NATIVE_RUNTIME_SELECTION_PATH', 'BIB_NATIVE_RUNTIME_SELECTION_SHA256') + tuple(
    'BIB_NATIVE_RUNTIME_' + role + '_' + suffix for role in PRIVATE_ROLE_NAMES for suffix in ('PATH', 'SHA256')) + (
    'BIB_NATIVE_RUNTIME_LINK_MAP',)
LIMIT_KEYS = ('prepare_seconds', 'configure_seconds', 'build_seconds',
              'cleanup_seconds', 'maximum_jobs', 'maximum_output_bytes',
              'minimum_free_bytes', 'maximum_process_tree_bytes')
_UNCERTAIN_OWNERS = []


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True,
                       allow_nan=False) + '\n').encode('ascii')


def fields(value, expected, label):
    if type(value) is not dict or set(value) != set(expected):
        raise ValueError(label + ' has missing or unknown fields')


def sha(value):
    if type(value) is not str or not re.fullmatch('[0-9a-f]{64}', value) or value == '0' * 64:
        raise ValueError('A nonzero independent lowercase SHA256 is required')
    return value


def shell_word(value, role):
    # Upstream generated Makefiles expand compiler and include/library paths
    # into shell commands. CMake quoting alone does not quote those later
    # expansions. Admit one conservative literal path vocabulary throughout.
    if type(value) is not str or not re.fullmatch(r'/[A-Za-z0-9_./+\-]+', value):
        raise ValueError('Native dependency ' + role + ' must be a literal shell path word')
    return value


def ordinary(path, *, directory=False):
    raw, path = os.fspath(path), Path(path)
    if not path.is_absolute() or str(path) != raw or '..' in path.parts:
        raise ValueError('Native dependency paths must be normalized absolute paths')
    for part in reversed((path, *path.parents)):
        state = part.lstat()
        want_directory = directory if part == path else True
        if (not (stat.S_ISDIR(state.st_mode) if want_directory else stat.S_ISREG(state.st_mode))
                or stat.S_ISLNK(state.st_mode) or not want_directory and state.st_nlink != 1):
            raise ValueError('Native dependencies refuse linked or special input: ' + str(part))
    return path


def read(path, pin=None, *, maximum=MAX_DOCUMENT):
    path = ordinary(path)
    before = path.stat()
    if before.st_size > maximum:
        raise ValueError('Native dependency input exceeds its byte limit')
    identity = lambda s: (s.st_dev, s.st_ino, s.st_mode, s.st_nlink, s.st_size,
                          s.st_mtime_ns, s.st_ctime_ns)
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as stream:
        opened = os.fstat(stream.fileno())
        raw = stream.read(maximum + 1)
        after = os.fstat(stream.fileno())
    if (identity(before) != identity(opened) or identity(before) != identity(after)
            or identity(before) != identity(path.stat()) or len(raw) > maximum):
        raise ValueError('Native dependency input changed while reading')
    if pin is not None and hashlib.sha256(raw).hexdigest() != sha(pin):
        raise ValueError('Native dependency input differs from its independent pin')
    return raw


def document(path, pin=None):
    def pairs(items):
        result = {}
        for name, value in items:
            if name in result:
                raise ValueError('Duplicate native dependency JSON field: ' + name)
            result[name] = value
        return result
    def invalid(value):
        raise ValueError('Nonfinite native dependency JSON: ' + value)
    try:
        result = json.loads(read(path, pin).decode('utf-8'), object_pairs_hook=pairs,
                            parse_constant=invalid)
        encoded(result)
        return result
    except (UnicodeError, RecursionError, OverflowError) as error:
        raise ValueError('Invalid native dependency JSON encoding/nesting') from error


def _ref(value, base):
    fields(value, ('path', 'sha256'), 'Native dependency reference')
    return Path(base) / manifest.path_name(value['path']), sha(value['sha256'])


def _limits(value):
    fields(value, LIMIT_KEYS, 'Native dependency phase limits')
    for name, item in value.items():
        if type(item) is not int or item <= 0 or item > 2**48:
            raise ValueError('Native dependency limit must be a bounded positive integer: ' + name)
    if value['maximum_jobs'] != 4:
        raise ValueError('Native dependency recipe requires a global four-job compilation cap')
    if any(value[name] > 24 * 60 * 60 for name in
           ('prepare_seconds', 'configure_seconds', 'build_seconds')) or value['cleanup_seconds'] > 60:
        raise ValueError('Native dependency wall/cleanup deadline exceeds its supported bound')
    return dict(value)


def load_profile(repository_root=ROOT):
    profile = document(Path(repository_root) / RECIPE / 'profile.json')
    fields(profile, ('schema_version', 'kind', 'target', 'maximum_jobs', 'source_policy',
                     'cmake_inputs', 'components', 'libraries', 'pkg_config', 'assets',
                     'notices', 'limitations', 'pic_check', 'private_runtime'), 'Native dependency recipe profile')
    manifest.target_contract(profile['target'])
    if (type(profile['schema_version']) is not int or profile['schema_version'] != 1
            or profile['kind'] != 'foundation-native-dependency-recipe-v1' or profile['target'] != TARGET
            or type(profile['maximum_jobs']) is not int or profile['maximum_jobs'] != 4
            or profile['source_policy'] != 'exact-retained-archives-no-fetch-no-patches'
            or len(profile['components']) != 15):
        raise ValueError('Unsupported native dependency recipe profile')
    names = {'icu', 'zlib', 'brotli', 'png', 'jpeg', 'webp', 'freetype', 'harfbuzz',
             'xml2', 'sqlite', 'openssl', 'nghttp2', 'psl', 'curl', 'fontconfig'}
    if set(profile['components']) != names or set(profile['libraries']) != native_inputs.LIBRARIES:
        raise ValueError('Native dependency recipe changes the supported source/library closure')
    pic = profile['pic_check']
    fields(pic, ('ordered_libraries', 'output', 'system_links', 'link_options'), 'Native dependency PIC check')
    if (type(pic['ordered_libraries']) is not list or len(pic['ordered_libraries']) != 22
            or set(pic['ordered_libraries']) != native_inputs.LIBRARIES
            or pic['output'] != 'pic/libfoundation-native-dependencies-pic-check.so'
            or pic['system_links'] != ['Threads::Threads', 'm', 'dl', 'rt', 'atomic']
            or pic['link_options'] != ['-Wl,-z,defs', '-Wl,-z,text']):
        raise ValueError('Native dependency PIC check must bind the complete static closure')
    if profile['private_runtime'] != {'policy': PRIVATE_POLICY, 'policy_sha256': PRIVATE_POLICY_SHA256,
            'toolchain_kind': PRIVATE_KIND, 'cmake_inputs': list(PRIVATE_CMAKE_INPUTS),
            'export': PRIVATE_EXPORT, 'export_map_sha256': hashlib.sha256(PRIVATE_EXPORT_RAW).hexdigest()}:
        raise ValueError('Native dependency private-runtime policy differs from the fixed contract')
    if 'NATIVE_PIC_RUNTIME_MODE' not in profile['cmake_inputs']:
        raise ValueError('Native dependency recipe lacks its explicit PIC runtime mode')
    return profile


def _sources(value, base, inputs, profile):
    fields(value, ('schema_version', 'kind', 'archives', 'notices'), 'Native dependency sources')
    if type(value['schema_version']) is not int or value['schema_version'] != 1 or value['kind'] != SOURCES_KIND:
        raise ValueError('Unsupported native dependency source format')
    components = profile['components']
    if type(value['archives']) is not dict or set(value['archives']) != set(components):
        raise ValueError('Native dependency sources must name exactly the fifteen fixed archives')
    result = {}
    for name, component in components.items():
        entry = value['archives'][name]
        fields(entry, ('path', 'sha256', 'bytes', 'format', 'strip_prefix', 'normalizations'),
               'Native dependency archive ' + name)
        for key in ('sha256', 'bytes', 'format', 'strip_prefix'):
            if entry[key] != component[key]:
                raise ValueError('Native dependency archive differs from fixed recipe: ' + name + '/' + key)
        if type(entry['bytes']) is not int or entry['bytes'] <= 0:
            raise ValueError('Native dependency archive byte count is invalid')
        path = Path(base) / manifest.path_name(entry['path'])
        inputs.file(path, entry['sha256'], 'dependency archive ' + name, maximum=entry['bytes'])
        if path.stat().st_size != entry['bytes']:
            raise ValueError('Native dependency archive byte count differs: ' + name)
        normalizations = entry['normalizations']
        if type(normalizations) is not dict:
            raise ValueError('Native dependency normalization map is invalid')
        for member, target in normalizations.items():
            manifest.path_name(member)
            manifest.path_name(target)
            if member == target or target in normalizations:
                raise ValueError('Native dependency normalizations cannot be self-links or chains')
        result[name] = dict(entry, path=str(path))
    if type(value['notices']) is not list or not value['notices']:
        raise ValueError('Native dependency original notices must be explicitly retained')
    notices = []
    for entry in value['notices']:
        path, pin = _ref(entry, base)
        inputs.file(path, pin, 'dependency original notice')
        notices.append({'path': str(path), 'sha256': pin})
    return result, notices


class Inspection:
    def __init__(self, selection, selection_path, selection_sha256, inputs, profile,
                 archives, notices, toolchain, host_tools, assets, limits, repository_root):
        self.selection, self.selection_path = selection, Path(selection_path)
        self.selection_sha256, self.inputs, self.profile = selection_sha256, inputs, profile
        self.archives, self.notices = archives, notices
        self.toolchain, self.host_tools, self.assets = toolchain, host_tools, assets
        self.phase_limits, self.repository_root = limits, Path(repository_root)

    def recheck(self):
        self.inputs.recheck()

    @property
    def protected_paths(self):
        return self.inputs.protected_paths

    def as_dict(self):
        return {'selection': {'path': str(self.selection_path), 'sha256': self.selection_sha256},
                'archives': self.archives, 'notices': self.notices,
                'toolchain': self.toolchain, 'host_tools': self.host_tools,
                'assets': self.assets, 'phase_limits': self.phase_limits,
                'profile': self.profile, 'inputs': list(self.inputs.records),
                'production_eligible': False, 'engine_execution': False, 'kernel_rebuild': False}


def _producer_inputs(inputs, repository_root):
    # SDK admission is a pure transitive input parser. Its implementation and
    # toolchain template remain part of this fixed producer source closure even
    # when a selection uses the original explicit-toolchain input format.
    for name in PRODUCER_SOURCES:
        source = Path(repository_root) / name
        inputs.repository_file(source, hashlib.sha256(read(source)).hexdigest(),
            'native dependency producer source ' + name,
            repository_root=repository_root, source_paths=PRODUCER_SOURCES)
    # Do not recapture these shared leaves under the dependency23 authority.
    # parse_toolchain captures the policy using this exact native20 authority.
    for name in PRIVATE_SHARED_SOURCES:
        source = Path(repository_root) / name
        inputs.repository_file(source, hashlib.sha256(read(source)).hexdigest(),
            'native dependency shared runtime source ' + name,
            repository_root=repository_root, source_paths=native_inputs.PRODUCERS)


def inspect_selection(path, pin, *, repository_root=ROOT):
    """Validate explicit retained inputs; never execute a program or search an SDK."""
    path, pin = ordinary(path), sha(pin)
    inputs = native_inputs.InputSet()
    selection = inputs.document({'path': path.name, 'sha256': pin}, path.parent,
                                'native dependency selection')
    fields(selection, ('schema_version', 'kind', 'target', 'archives', 'toolchain',
                       'host_tools', 'assets', 'phase_limits'), 'Native dependency selection')
    manifest.target_contract(selection['target'])
    if (type(selection['schema_version']) is not int or selection['schema_version'] != 1 or selection['kind'] != SELECTION_KIND
            or selection['target'] != TARGET):
        raise ValueError('Only the explicit Linux x86_64 native dependency recipe is supported')
    limits = _limits(selection['phase_limits'])
    inputs.deadline = time.monotonic() + limits['prepare_seconds']
    profile = load_profile(repository_root)
    _producer_inputs(inputs, repository_root)
    source_doc = inputs.document(selection['archives'], path.parent, 'native dependency source manifest')
    source_path, _ = _ref(selection['archives'], path.parent)
    archives, notices = _sources(source_doc, source_path.parent, inputs, profile)
    toolchain_doc = inputs.document(selection['toolchain'], path.parent, 'native dependency toolchain')
    toolchain_path, _ = _ref(selection['toolchain'], path.parent)
    toolchain = native_inputs.parse_toolchain(toolchain_doc, toolchain_path.parent, inputs, TARGET,
                                            repository_root=repository_root)
    host_doc = inputs.document(selection['host_tools'], path.parent, 'native dependency host tools')
    host_path, _ = _ref(selection['host_tools'], path.parent)
    host = native_inputs.parse_host_tools(host_doc, host_path.parent, inputs, toolchain,
                                         repository_root=repository_root)
    native_inputs.render_environment(toolchain, host)
    if 'make' not in host['programs']:
        raise ValueError('Native dependency recipe requires an explicitly admitted make program')
    asset_doc = inputs.document(selection['assets'], path.parent, 'native dependency assets')
    asset_path, _ = _ref(selection['assets'], path.parent)
    assets = native_inputs.parse_assets(asset_doc, asset_path.parent, inputs, TARGET)
    result = Inspection(selection, path, pin, inputs, profile, archives, notices,
                        toolchain, host, assets, limits, repository_root)
    values = cache_values(result, Path('/native-dependency-plan-output'))
    render_cache(values, cache_names(result))
    result.recheck()
    inputs.check_deadline()
    return result


def fresh_output(path, protected=()):
    raw, path = os.fspath(path), Path(path)
    shell_word(raw, 'output')
    if not path.is_absolute() or str(path) != raw or '..' in path.parts:
        raise ValueError('Native dependency output must be a normalized absolute path')
    ordinary(path.parent, directory=True)
    for other in protected:
        other = Path(other)
        if path == other or path in other.parents or other in path.parents:
            raise ValueError('Native dependency output overlaps retained input: ' + str(other))
    if path.exists() or path.is_symlink():
        raise ValueError('Native dependency output must be fresh; preserve previous evidence')
    path.mkdir(mode=0o700)
    return path


def save(path, value):
    path = Path(path)
    ordinary(path.parent, directory=True)
    raw = value if type(value) is bytes else encoded(value)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
    with os.fdopen(descriptor, 'wb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def make_plan(selection, pin, output, *, repository_root=ROOT):
    inspected = inspect_selection(selection, pin, repository_root=repository_root)
    value = {'schema_version': 1, 'kind': PLAN_KIND,
             'scope': 'explicit-native-dependency-candidate',
             'selection': {'path': str(inspected.selection_path), 'sha256': pin},
             'inspection': inspected.as_dict(), 'production_eligible': False,
             'engine_execution': False, 'kernel_rebuild': False}
    output = fresh_output(output, inspected.protected_paths)
    inspected.recheck()
    save(output / 'plan.json', value)
    return value


def verify_plan(path, pin, *, repository_root=ROOT):
    value = document(path, pin)
    fields(value, ('schema_version', 'kind', 'scope', 'selection', 'inspection',
                   'production_eligible', 'engine_execution', 'kernel_rebuild'), 'Native dependency plan')
    if (type(value['schema_version']) is not int or value['schema_version'] != 1 or value['kind'] != PLAN_KIND
            or value['scope'] != 'explicit-native-dependency-candidate'
            or any(value[key] is not False for key in
                   ('production_eligible', 'engine_execution', 'kernel_rebuild'))):
        raise ValueError('Unsupported native dependency candidate plan')
    fields(value['selection'], ('path', 'sha256'), 'Native dependency plan selection')
    inspected = inspect_selection(value['selection']['path'], value['selection']['sha256'],
                                  repository_root=repository_root)
    if value['inspection'] != inspected.as_dict():
        raise ValueError('Native dependency plan no longer matches exact retained inputs/recipe')
    return inspected, value


def _member_name(raw, strip_prefix):
    raw = raw.rstrip('/')
    manifest.path_name(raw)
    if raw == strip_prefix:
        return None
    prefix = strip_prefix + '/'
    if not raw.startswith(prefix):
        raise ValueError('Native dependency archive contains an entry outside its exact root')
    return manifest.path_name(raw[len(prefix):])


def extract_archive(entry, output, *, deadline=None, maximum_bytes=MAX_EXPANDED_BYTES,
                    minimum_free_bytes=0):
    """Materialize only exact direct-to-regular link normalizations, never follow links."""
    output = fresh_output(output)
    registry, records, regular, links, total, count = PathInventory(), [], {}, {}, 0, 0
    archive_path = ordinary(entry['path'])
    if hashlib.sha256(read(archive_path, entry['sha256'], maximum=entry['bytes'])).hexdigest() != entry['sha256']:
        raise ValueError('Native dependency archive changed')
    normalizations = entry['normalizations']
    def check_clock():
        if deadline is not None and time.monotonic() >= deadline:
            raise ValueError('Native dependency preparation wall deadline exceeded')
        if shutil.disk_usage(output).free < minimum_free_bytes:
            raise ValueError('Native dependency preparation free disk reserve exhausted')
    def inspect(member, kind, size, mode, opener, link=None):
        nonlocal total, count
        check_clock()
        count += 1
        if count > MAX_ARCHIVE_FILES:
            raise ValueError('Native dependency expanded file count exceeds its bound')
        name = _member_name(member, entry['strip_prefix'])
        if name is None:
            if kind != 'directory':
                raise ValueError('Native dependency archive root is not a directory')
            return
        registry.add(name, kind == 'directory')
        if kind == 'directory':
            (output / name).mkdir(parents=True, exist_ok=True, mode=0o755)
            return
        if kind == 'link':
            if name not in normalizations:
                raise ValueError('Native dependency link requires an exact normalization: ' + name)
            links[name] = link
            return
        if kind != 'file' or type(size) is not int or size < 0 or size > MAX_MEMBER_BYTES:
            raise ValueError('Native dependency archive has an unsupported or oversized entry')
        total += size
        if total > min(MAX_EXPANDED_BYTES, maximum_bytes):
            raise ValueError('Native dependency expanded byte count exceeds its bound')
        destination = output / name
        destination.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
        digest, written = hashlib.sha256(), 0
        with opener() as source, destination.open('xb') as stream:
            while True:
                check_clock()
                block = source.read(min(1024 * 1024, size - written + 1))
                if not block:
                    break
                written += len(block)
                if written > size:
                    raise ValueError('Native dependency archive member exceeds its declared size')
                digest.update(block)
                stream.write(block)
        if written != size:
            raise ValueError('Native dependency archive member is truncated')
        mode = 0o755 if mode & 0o111 else 0o644
        destination.chmod(mode)
        regular[name] = destination
        records.append({'path': name, 'sha256': digest.hexdigest(), 'bytes': written, 'mode': mode})
    if entry['format'] in ('tar-gzip', 'tar-xz'):
        with tarfile.open(archive_path, 'r:gz' if entry['format'] == 'tar-gzip' else 'r:xz') as archive:
            for member in archive:
                kind = ('directory' if member.isdir() else 'file' if member.isfile() else
                        'link' if member.issym() or member.islnk() else 'special')
                inspect(member.name, kind, member.size, member.mode,
                        lambda m=member: archive.extractfile(m),
                        {'target': member.linkname, 'hard': member.islnk()})
    elif entry['format'] == 'zip':
        with zipfile.ZipFile(archive_path) as archive:
            for member in archive.infolist():
                mode = member.external_attr >> 16
                kind = ('directory' if member.is_dir() else
                        'file' if not stat.S_IFMT(mode) or stat.S_ISREG(mode) else 'special')
                inspect(member.filename, kind, member.file_size, mode,
                        lambda m=member: archive.open(m))
    else:
        raise ValueError('Unsupported native dependency archive format')
    if set(links) != set(normalizations):
        raise ValueError('Native dependency archive normalization map omits or invents links')
    for name, link in sorted(links.items()):
        check_clock()
        target = normalizations[name]
        actual = link['target'] if link['hard'] else str(PurePosixPath(name).parent / link['target'])
        if link['hard']:
            actual = _member_name(actual, entry['strip_prefix'])
        # A normalization may remove '..' from an upstream relative link, but
        # its final member and the exact declared target must remain contained.
        parts = []
        for part in PurePosixPath(actual).parts:
            if part == '..':
                if not parts:
                    raise ValueError('Native dependency archive link escapes its root')
                parts.pop()
            elif part not in ('', '.'):
                parts.append(part)
        actual = '/'.join(parts)
        if actual != target or target not in regular or PurePosixPath(link['target']).is_absolute():
            raise ValueError('Native dependency link normalization is not exact direct-to-regular')
        destination = output / name
        destination.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
        size = regular[target].stat().st_size
        total += size
        if total > min(MAX_EXPANDED_BYTES, maximum_bytes):
            raise ValueError('Native dependency normalized bytes exceed their bound')
        digest, written = hashlib.sha256(), 0
        with regular[target].open('rb') as source, destination.open('xb') as stream:
            for block in iter(lambda: source.read(1024 * 1024), b''):
                check_clock()
                written += len(block)
                if written > size:
                    raise ValueError('Native dependency normalized source changed size')
                digest.update(block)
                stream.write(block)
        check_clock()
        if written != size:
            raise ValueError('Native dependency normalized source was truncated')
        mode = stat.S_IMODE(regular[target].stat().st_mode)
        destination.chmod(mode)
        records.append({'path': name, 'sha256': digest.hexdigest(),
                        'bytes': written, 'mode': mode, 'normalized_from': target})
    if not regular:
        raise ValueError('Native dependency archive contains no ordinary source files')
    return sorted(records, key=lambda item: item['path'])


def cmake_literal(value):
    """Quote a literal CMake value without permitting command/list injection."""
    if type(value) is not str or not value or len(value) > 16384 or any(
            ord(char) < 32 or ord(char) >= 127 or char in ';$|' for char in value):
        raise ValueError('Native dependency cache scalar is not a bounded literal')
    for width in range(1, 9):
        equals = '=' * width
        if ']' + equals + ']' not in value:
            return '[' + equals + '[' + value + ']' + equals + ']'
    raise ValueError('Native dependency cache scalar has no safe bracket delimiter')


def private_runtime(inspected):
    runtime = inspected.toolchain.get('private_runtime')
    if inspected.toolchain.get('kind') == PRIVATE_KIND:
        if type(runtime) is not dict:
            raise ValueError('Private SDK toolchain lacks its validated runtime selection; no generic fallback')
        return runtime
    if runtime is not None:
        raise ValueError('Generic dependency toolchain cannot acquire private runtime semantics')
    return None


def cache_names(inspected):
    return inspected.profile['cmake_inputs'] + (list(PRIVATE_CMAKE_INPUTS) if private_runtime(inspected) else [])


def private_cache_values(inspected, output):
    runtime = private_runtime(inspected)
    if runtime is None:
        return {}
    values = dict(runtime['cmake'])
    expected = set(PRIVATE_CMAKE_INPUTS) - {'NATIVE_PRIVATE_RUNTIME_HELPER',
        'NATIVE_PRIVATE_RUNTIME_HELPER_SHA256', 'BIB_NATIVE_RUNTIME_LINK_MAP'}
    if (set(values) != expected or values['BIB_NATIVE_RUNTIME_POLICY_SHA256'] != PRIVATE_POLICY_SHA256
            or values['BIB_NATIVE_RUNTIME_COMPILER_TRIPLE'] != TARGET['triple']
            or values['BIB_NATIVE_RUNTIME_SELECTION_SHA256'] != sha(runtime['record']['sha256'])):
        raise ValueError('Private dependency CMake values differ from the exact validated SDK contract')
    helper = Path(inspected.repository_root) / PRIVATE_SHARED_SOURCES[1]
    captured = {record['path']: record for record in inspected.inputs.records}
    if str(helper) not in captured:
        raise ValueError('Private runtime helper was not captured under its shared source authority')
    values.update({'NATIVE_PRIVATE_RUNTIME_HELPER': str(Path(output) / 'private-runtime/native-private-runtime.cmake'),
        'NATIVE_PRIVATE_RUNTIME_HELPER_SHA256': captured[str(helper)]['sha256'],
        'BIB_NATIVE_RUNTIME_SELECTION_PATH': str(Path(output) / 'private-runtime/selection.json'),
        'BIB_NATIVE_RUNTIME_LINK_MAP': str(Path(output) / 'components/pic/evidence/dependency-runtime-link.map')})
    return values


def cache_values(inspected, output):
    output = Path(output)
    toolchain, host = inspected.toolchain, inspected.host_tools
    sysroot = toolchain['inventories'][toolchain['runtime']['sysroot_inventory']]['root']
    shell_word(str(output), 'output')
    shell_word(sysroot, 'sysroot')
    flags = '-fPIC -march=x86-64 -mtune=generic --sysroot=' + sysroot
    values = {'NATIVE_PREFIX': str(output / 'prefix'), 'NATIVE_WORK': str(output / 'components'),
              'NATIVE_TOOLCHAIN': toolchain['toolchain_file'],
              'NATIVE_SYSROOT': sysroot,
              'NATIVE_C_FLAGS': flags, 'NATIVE_CXX_FLAGS': flags,
              'NATIVE_LINK_FLAGS': '',
              'NATIVE_PIC_RUNTIME_MODE': PRIVATE_POLICY if private_runtime(inspected) else 'generic-pic-v1'}
    for name in inspected.archives:
        values['SOURCE_' + name] = str(output / 'sources' / name)
    programs = dict(toolchain['tools'])
    programs.update(host['programs'])
    for name, program in programs.items():
        shell_word(program['path'], 'admitted program ' + name)
    for name in ('cmake', 'ninja', 'make', 'sh', 'perl', 'python', 'gperf',
                 'pkg_config', 'c', 'cxx', 'archiver', 'ranlib'):
        if name not in programs:
            raise ValueError('Native dependency recipe requires admitted program: ' + name)
        values['PROGRAM_' + name] = programs[name]['path']
    assets = inspected.assets
    for name, role in (('NATIVE_ASSETS_FONT_CONFIG', 'font_config'),
                       ('NATIVE_ASSETS_ICU_DATA', 'icu_data'),
                       ('NATIVE_ASSETS_CA_BUNDLE', 'ca_bundle')):
        values[name] = assets[role]['path']
    values['NATIVE_ASSETS_FONTS'] = [entry['path'] for entry in assets['fonts']]
    values['NATIVE_NOTICE_FILES'] = sorted(set(entry['path'] for entry in
                                              inspected.notices + assets['notices']))
    values.update(private_cache_values(inspected, output))
    return values


def render_cache(values, expected):
    if type(expected) is not list or set(values) != set(expected):
        raise ValueError('Native dependency cache names differ from the fixed recipe contract')
    lines = ['# Generated literal inputs for the explicit native dependency recipe.']
    for key, value in sorted(values.items()):
        if not re.fullmatch('[A-Za-z_][A-Za-z_0-9]*', key):
            raise ValueError('Invalid native dependency cache key')
        if type(value) is list:
            if not value:
                raise ValueError('Native dependency cache list must not be empty')
            quoted = ' '.join(cmake_literal(item) for item in value)
            lines.append('set(' + key + ' ' + quoted + ' CACHE INTERNAL "" FORCE)')
        else:
            quoted = '""' if value == '' else cmake_literal(value)
            lines.append('set(' + key + ' ' + quoted + ' CACHE INTERNAL "" FORCE)')
    return ('\n'.join(lines) + '\n').encode('ascii')


def _resources(root, pid=None):
    total, count, pending = 0, 0, [Path(root)]
    while pending:
        with os.scandir(pending.pop()) as entries:
            for entry in entries:
                count += 1
                if count > MAX_OUTPUT_ENTRIES:
                    raise ValueError('Native dependency output entry bound exceeded')
                state = entry.stat(follow_symlinks=False)
                if stat.S_ISDIR(state.st_mode):
                    pending.append(Path(entry.path))
                elif stat.S_ISREG(state.st_mode) or stat.S_ISLNK(state.st_mode):
                    total += state.st_size
                else:
                    raise ValueError('Native dependency build output contains a special file')
    memory, pending, seen = 0, [pid] if pid else [], set()
    while pending:
        current = pending.pop()
        if current in seen:
            continue
        seen.add(current)
        if len(seen) > 1024:
            raise ValueError('Native dependency process-tree bound exceeded')
        base = Path('/proc') / str(current)
        try:
            first = (base / 'stat').read_text().rsplit(')', 1)[1].split()[19]
            status = (base / 'status').read_text()
            children = (base / 'task' / str(current) / 'children').read_text().split()
            last = (base / 'stat').read_text().rsplit(')', 1)[1].split()[19]
        except FileNotFoundError:
            continue
        if first != last:
            raise ValueError('Native dependency process identity changed during memory sample')
        match = re.search(r'^VmRSS:\s+([0-9]+)\s+kB$', status, re.M)
        if match:
            memory += int(match.group(1)) * 1024
        for child in children:
            if not child.isdecimal() or int(child) <= 0:
                raise ValueError('Invalid native dependency descendant observation')
            pending.append(int(child))
    return {'output_bytes': total, 'free_bytes': shutil.disk_usage(root).free,
            'process_tree_bytes': memory}


def _check_resources(sample, limits):
    if sample['output_bytes'] > limits['maximum_output_bytes']:
        raise ValueError('Native dependency private output byte limit exceeded')
    if sample['free_bytes'] < limits['minimum_free_bytes']:
        raise ValueError('Native dependency free disk reserve exhausted')
    if sample['process_tree_bytes'] > limits['maximum_process_tree_bytes']:
        raise ValueError('Native dependency sampled process-tree memory limit exceeded')


def bounded_inventory(root, limits, deadline=None):
    """Hash the complete installed prefix with streaming deadline/size checks."""
    root, files, directories, modes = ordinary(root, directory=True), {}, [], {}
    registry, count, total = PathInventory(), 0, 0
    def checkpoint():
        if deadline is not None and time.monotonic() >= deadline:
            raise ValueError('Native dependency final inventory wall deadline exceeded')
        if shutil.disk_usage(root).free < limits['minimum_free_bytes']:
            raise ValueError('Native dependency final inventory free reserve exhausted')
    def walk(directory):
        nonlocal count, total
        checkpoint()
        for path in sorted(directory.iterdir()):
            checkpoint()
            count += 1
            if count > MAX_OUTPUT_ENTRIES:
                raise ValueError('Native dependency prefix inventory entry bound exceeded')
            before = path.lstat()
            name = manifest.path_name(path.relative_to(root).as_posix())
            is_directory = stat.S_ISDIR(before.st_mode)
            registry.add(name, is_directory)
            mode = stat.S_IMODE(before.st_mode)
            if is_directory:
                if mode != 0o755:
                    raise ValueError('Native dependency prefix directory mode is not 0755')
                directories.append(name)
                modes[name] = mode
                walk(path)
            else:
                ordinary(path)
                if mode not in (0o644, 0o755):
                    raise ValueError('Native dependency prefix file mode is not normalized')
                total += before.st_size
                if total > limits['maximum_output_bytes']:
                    raise ValueError('Native dependency prefix inventory byte limit exceeded')
                digest = hashlib.sha256()
                with path.open('rb') as stream:
                    for block in iter(lambda: stream.read(1024 * 1024), b''):
                        checkpoint()
                        digest.update(block)
                after = path.lstat()
                if (before.st_dev, before.st_ino, before.st_size, before.st_mode,
                        before.st_mtime_ns, before.st_ctime_ns) != (
                        after.st_dev, after.st_ino, after.st_size, after.st_mode,
                        after.st_mtime_ns, after.st_ctime_ns):
                    raise ValueError('Native dependency installed file changed during inventory')
                files[name], modes[name] = digest.hexdigest(), mode
    walk(root)
    checkpoint()
    return {'files': files, 'directories': sorted(directories), 'modes': modes}


def run_owned(argv, cwd, log, environment, limits, *, phase, output, absolute_deadline=None):
    """Own one process tree through closed logs and descendant teardown."""
    if phase not in ('configure', 'build', 'inspection'):
        raise ValueError('Unknown native dependency process phase')
    if type(argv) is not list or not argv or any(type(item) is not str or not item for item in argv):
        raise ValueError('Invalid native dependency command')
    deadline = limits['configure_seconds' if phase == 'inspection' else phase + '_seconds']
    started, owner, peak, next_sample = time.monotonic(), None, 0, 0
    launched, closed, cleanup_uncertain, failure, code = False, True, False, None, None
    _check_resources(_resources(output), limits)
    if absolute_deadline is not None and started >= absolute_deadline:
        raise ValueError('Native dependency aggregate build/inspection wall deadline exceeded')
    try:
        with Path(log).open('xb') as stream:
            owner = process_tree.launch(argv, Path(cwd), stream, env=environment)
            launched, closed = True, False
            save(Path(log).with_suffix('.launch.json'), {'phase': phase, 'argv': argv,
                 'cwd': str(cwd), 'supervisor_pid': owner.process.pid})
            while owner.poll() is None:
                now = time.monotonic()
                if now - started >= deadline:
                    raise ValueError('Native dependency ' + phase + ' wall deadline exceeded')
                if absolute_deadline is not None and now >= absolute_deadline:
                    raise ValueError('Native dependency aggregate build/inspection wall deadline exceeded')
                if now >= next_sample:
                    sample = _resources(output, owner.process.pid)
                    peak = max(peak, sample['process_tree_bytes'])
                    _check_resources(sample, limits)
                    next_sample = now + 2
                time.sleep(0.1)
            code = owner.finish()
            if code != 0:
                raise ValueError('Native dependency ' + phase + ' exited ' + str(code))
    except BaseException as error:
        failure = error
        if owner is not None:
            try:
                owner.terminate(timeout=limits['cleanup_seconds'])
            except BaseException as cleanup:
                cleanup_uncertain = True
                _UNCERTAIN_OWNERS.append(owner)
                failure = process_tree.ProcessTreeError(
                    'Native dependency cleanup uncertain; preserve ownership: ' + str(cleanup))
                raise failure from error
        raise
    finally:
        final_error = None
        if owner is not None and not cleanup_uncertain:
            try:
                owner.close()
                closed = True
            except BaseException as error:
                closed, final_error = False, error
                _UNCERTAIN_OWNERS.append(owner)
                if failure is None:
                    failure = error
                else:
                    original = failure
                    failure = process_tree.ProcessTreeError('Original native dependency failure: '
                        + str(original) + '; owner closure also failed: ' + str(error))
                    failure.__cause__ = original
        elif isinstance(failure, process_tree.ProcessTreeError):
            closed = False
        if failure is None:
            try:
                _check_resources(_resources(output), limits)
                if time.monotonic() - started >= deadline:
                    raise ValueError('Native dependency ' + phase + ' wall deadline exceeded')
                if absolute_deadline is not None and time.monotonic() >= absolute_deadline:
                    raise ValueError('Native dependency aggregate build/inspection wall deadline exceeded')
            except BaseException as error:
                failure, final_error = error, error
        stage = {'phase': phase, 'argv': argv, 'cwd': str(cwd), 'exit_code': code,
                 'status': 'passed' if failure is None else 'incomplete',
                 'launched': launched, 'wall_seconds': time.monotonic() - started,
                 'process_tree_closed': closed, 'sampled_peak_process_tree_bytes': peak,
                 'memory_observation': 'sampled-aggregate-rss-not-a-kernel-hard-limit'}
        if failure is not None:
            stage['error'] = str(failure)[:4096]
            setattr(failure, 'native_stage_receipt', stage)
        try:
            save(Path(log).with_suffix('.stage.json'), stage)
        except BaseException as publication:
            if failure is None:
                setattr(publication, 'native_stage_receipt', stage)
                raise
            combined = ValueError('Original native dependency failure: ' + str(failure)
                + '; stage evidence publication also failed: ' + str(publication))
            setattr(combined, 'native_stage_receipt', stage)
            raise combined from failure
        if final_error is not None:
            raise failure
    return stage


def _copy_asset_input(inspected, output):
    """Retain original relative asset references unchanged for the next consumer."""
    reference = inspected.selection['assets']
    source_path, pin = _ref(reference, inspected.selection_path.parent)
    original = document(source_path, pin)
    root = Path(output) / 'retained' / 'assets'
    root.mkdir(parents=True, mode=0o755)
    registry = PathInventory()
    copies = {}
    for entry in original['fonts'] + [original[name] for name in ('font_config', 'icu_data', 'ca_bundle')]:
        copies[manifest.path_name(entry['path'])] = entry['sha256']
    for entry in original['notices']:
        name = manifest.path_name(entry['path'])
        if name in copies and copies[name] != entry['sha256']:
            raise ValueError('Native asset/notice alias has inconsistent pins')
        copies[name] = entry['sha256']
    if source_path.name in copies and copies[source_path.name] != pin:
        raise ValueError('Native asset path aliases its original manifest with different bytes')
    copies[source_path.name] = pin
    for name, expected in sorted(copies.items()):
        registry.add(name, False)
        destination = root / name
        destination.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
        save(destination, read(source_path.parent / name, expected,
                               maximum=native_inputs.MAX_FILE if name != source_path.name else MAX_DOCUMENT))
    return {'path': 'retained/assets/' + source_path.name, 'sha256': pin}


def file_digest(path, maximum, deadline=None):
    path = ordinary(path)
    before = path.lstat()
    if before.st_size > maximum:
        raise ValueError('Native dependency evidence file exceeds its byte limit')
    digest, size = hashlib.sha256(), 0
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            if deadline is not None and time.monotonic() >= deadline:
                raise ValueError('Native dependency evidence hashing deadline exceeded')
            size += len(block)
            if size > maximum:
                raise ValueError('Native dependency evidence file grew beyond its limit')
            digest.update(block)
    after = path.lstat()
    if (before.st_dev, before.st_ino, before.st_size, before.st_mode, before.st_mtime_ns,
            before.st_ctime_ns) != (after.st_dev, after.st_ino, after.st_size, after.st_mode,
                                    after.st_mtime_ns, after.st_ctime_ns) or size != before.st_size:
        raise ValueError('Native dependency evidence file changed while hashing')
    return digest.hexdigest()


def verify_pic_output(raw, needed_libraries):
    """Interpret only successful admitted readelf header/dynamic/relocation output."""
    try:
        text = raw.decode('utf-8')
    except UnicodeError as error:
        raise ValueError('Native PIC inspection log is not UTF-8') from error
    if not re.search(r'^\s*Type:\s+DYN\b', text, re.M):
        raise ValueError('Native PIC inspection does not identify the actual shared library')
    if re.search(r'\(TEXTREL\)|\(FLAGS\)[^\n]*\bTEXTREL\b', text):
        raise ValueError('Native dependency shared-link check contains dynamic text relocations')
    needed = re.findall(r'\(NEEDED\)[^\n]*\[([^\]\n]+)\]', text)
    if not needed or set(needed) - set(needed_libraries):
        raise ValueError('Native PIC shared link has missing or unadmitted runtime dependencies')
    return sorted(set(needed))


def verify_pic_commands(raw, cxx, archive_paths, shared, options):
    """Bind the retained native link command to every whole-archive input."""
    try:
        lines = raw.decode('utf-8').splitlines()
    except UnicodeError as error:
        raise ValueError('Native PIC command log is not UTF-8') from error
    candidates = []
    for line in lines:
        try:
            tokens = shlex.split(line)
        except ValueError as error:
            raise ValueError('Native PIC command log has invalid shell quoting') from error
        if cxx not in tokens or '-Wl,--whole-archive' not in tokens:
            continue
        if tokens.count(cxx) != 1:
            raise ValueError('Native PIC command has an ambiguous compiler')
        start = tokens.index(cxx)
        end = next((index for index in range(start + 1, len(tokens))
                    if tokens[index] in ('&&', ';', '|', '||')), len(tokens))
        candidates.append(tokens[start:end])
    if len(candidates) != 1:
        raise ValueError('Native PIC check has no unambiguous retained whole-archive link command')
    argv = candidates[0]
    if ('-shared' not in argv or any(option not in argv for option in options)
            or argv.count('-o') != 1 or argv.index('-o') + 1 >= len(argv)):
        raise ValueError('Native PIC command omits its required shared-link policy/output')
    if argv[argv.index('-o') + 1] not in (str(shared), shared.name):
        raise ValueError('Native PIC command writes a different shared-library output')
    if argv.count('-Wl,--whole-archive') != 1 or argv.count('-Wl,--no-whole-archive') != 1:
        raise ValueError('Native PIC command has an ambiguous whole-archive interval')
    first, last = argv.index('-Wl,--whole-archive'), argv.index('-Wl,--no-whole-archive')
    if first >= last or argv[first + 1:last] != archive_paths:
        raise ValueError('Native PIC link command omits or reorders the whole-archive closure')
    outside = argv[:first] + argv[last + 1:]
    if any(path in outside for path in archive_paths) or any(
            token not in outside for token in ('-lm', '-ldl', '-lrt', '-latomic')):
        raise ValueError('Native PIC command has a different closed system-link policy')
    return argv


def verify_private_pic_command(argv, values, export_map):
    required = ('-static-libstdc++', '-static-libgcc', '-Wl,--exclude-libs,ALL',
                '-Wl,--trace', '-Wl,-Map,' + values['BIB_NATIVE_RUNTIME_LINK_MAP'],
                '-Wl,--version-script,' + str(export_map))
    if any(argv.count(option) != 1 for option in required):
        raise ValueError('Private dependency PIC command differs from its exact runtime/map/export policy')
    if any(token.startswith(('-Wl,-Map,', '-Wl,--version-script,')) and token not in required
           for token in argv):
        raise ValueError('Private dependency PIC command includes a foreign map/export policy')


def _pic_receipt(inspected, output, environment, commands, deadline):
    """Require the CMake-owned all-member shared link; never load its DSO."""
    policy = inspected.profile['pic_check']
    actual, ordered = {}, []
    for target in policy['ordered_libraries']:
        declaration = inspected.profile['libraries'][target]
        archive = output / 'prefix' / manifest.path_name(declaration['archive'])
        actual[target] = native_inputs.inspect_static_archive(archive, deadline=deadline)
        ordered.append({'target': target, 'archive': declaration['archive'],
                        'sha256': actual[target]['sha256']})
    shared = output / 'components' / manifest.path_name(policy['output'])
    shared_hash = file_digest(shared, inspected.phase_limits['maximum_output_bytes'], deadline)
    with shared.open('rb') as stream:
        header = stream.read(64)
    if (len(header) != 64 or header[:7] != b'\x7fELF\x02\x01\x01'
            or struct.unpack_from('<HH', header, 16) != (3, 62)):
        raise ValueError('Native PIC check output is not an ELF64 x86_64 DSO')
    original_commands = output / 'components/pic/pic-commands.log'
    command_hash = file_digest(original_commands, MAX_DOCUMENT, deadline)
    ordered_paths = [str(output / 'prefix' / item['archive']) for item in ordered]
    ordered_file = output / 'components/pic/ordered-archives.txt'
    if read(ordered_file).decode('utf-8').splitlines() != ordered_paths:
        raise ValueError('Native PIC CMake archive receipt differs from the exact ordered closure')
    link_argv = verify_pic_commands(read(original_commands, command_hash),
        inspected.toolchain['tools']['cxx']['path'], ordered_paths, shared, policy['link_options'])
    private = private_runtime(inspected) is not None
    if private:
        verify_private_pic_command(link_argv, private_cache_values(inspected, output),
                                   output / 'components/pic/dependencies-pic.exports.map')
    directory = output / 'pic-check'
    directory.mkdir(mode=0o755)
    inspector = inspected.toolchain['tools']['inspect']
    argv = [inspector['path'], '-h', '-d', '-r', str(shared)]
    log = directory / 'inspection.log'
    command = run_owned(argv, output, log, environment, inspected.phase_limits,
                        phase='inspection', output=output, absolute_deadline=deadline)
    commands.append(command)
    raw = read(log)
    needed = verify_pic_output(raw, inspected.toolchain['runtime']['needed_libraries'])
    if file_digest(shared, inspected.phase_limits['maximum_output_bytes'], deadline) != shared_hash:
        raise ValueError('Native PIC DSO changed during actual inspection')
    result = {'schema_version': 1, 'kind': 'foundation-native-dependencies-pic-shared-link-v1',
              'target': TARGET, 'toolchain_identity_sha256': inspected.toolchain['identity']['identity_sha256'],
              'ordered_archives': ordered, 'link_options': policy['link_options'],
              'system_links': policy['system_links'], 'needed_libraries': needed,
              'shared_library': {'path': 'components/' + policy['output'], 'sha256': shared_hash},
              'compiler_link_commands': {'path': 'components/pic/pic-commands.log', 'sha256': command_hash},
              'link_argv': link_argv,
              'cmake_ordered_archives': {'path': 'components/pic/ordered-archives.txt',
                  'sha256': hashlib.sha256(read(ordered_file)).hexdigest()},
              'inspection': {'argv': argv, 'tool_sha256': inspector['sha256'], 'exit_code': 0,
                             'log': {'path': 'pic-check/inspection.log',
                                     'sha256': hashlib.sha256(raw).hexdigest()}},
              'dso_loaded_or_executed': False, 'production_eligible': False}
    if private:
        result['kind'] = 'foundation-native-dependencies-private-pic-shared-link-v1'
        result['private_runtime'] = private_pic_evidence(inspected, output, shared, shared_hash,
                                                       environment, commands, deadline, expected_needed=needed)
    save(directory / 'receipt.json', result)
    return result, actual, raw, argv


def admit_controller(inspected):
    """Require the actual build controller and its admitted runtime before work."""
    if not sys.dont_write_bytecode:
        raise ValueError('Native dependency build requires PYTHONDONTWRITEBYTECODE=1 before invocation')
    program = inspected.host_tools['programs']['python']
    actual = str(Path(sys.executable).resolve())
    if actual != program['path']:
        raise ValueError('Native dependency build controller differs from admitted host Python; '
                         'invoke PYTHONDONTWRITEBYTECODE=1 PYTHON=' + program['path']
                         + ' ./build.sh native-engine-dependencies build ...')
    result = {'kind': 'admitted-native-dependency-build-controller-v1', 'path': actual,
            'sha256': program['sha256'], 'declared_version': program['version'],
            'bytecode_disabled': True}
    if inspected.host_tools.get('kind') == 'foundation-native-engine-prototype-sdk-host-tools-v1':
        result.update(runtime=inspected.host_tools['interpreter_runtimes']['python'],
                      interpreter_binding=inspected.host_tools['interpreter_bindings']['python'])
    else:
        runtime = inspected.host_tools['module_inventories']['python']
        result.update(runtime=runtime['runtime'],
                      module_inventory={'root': runtime['root'], 'inventory': runtime['inventory']})
    return result


def stage_private_sources(inspected, output):
    if private_runtime(inspected) is None:
        return
    directory = Path(output) / 'private-runtime'
    directory.mkdir(mode=0o755)
    for name in PRIVATE_SHARED_SOURCES:
        save(directory / Path(name).name, inspected.inputs.bytes(Path(inspected.repository_root) / name))
    runtime = private_runtime(inspected)
    save(directory / 'selection.json', inspected.inputs.bytes(Path(runtime['record']['path'])))


def private_link_verifier(inspected):
    """Load only the captured authoritative pure checker, without a source walk."""
    path = Path(inspected.repository_root) / PRIVATE_SHARED_SOURCES[-1]
    raw = inspected.inputs.bytes(path)
    module = types.ModuleType('_foundation_dependency_private_link_verifier')
    module.__file__ = str(path)
    exec(compile(raw, str(path), 'exec'), module.__dict__)
    if inspected.inputs.bytes(path) != raw:
        raise ValueError('Private runtime verifier source changed while loading')
    return module.verify_private_runtime_link


def private_pic_evidence(inspected, output, shared, shared_hash, environment, commands, deadline, *, expected_needed):
    """Reuse the provider's pure input join and closed CMake ELF inspection."""
    if deadline is not None and deadline - time.monotonic() < 60:
        raise ValueError('Private runtime input inspection requires its remaining 60-second budget')
    values = private_cache_values(inspected, output)
    trace, link_map = output / 'logs/build.log', Path(values['BIB_NATIVE_RUNTIME_LINK_MAP'])
    joined = private_link_verifier(inspected)(values, trace, link_map)
    if (joined['kind'] != 'foundation-native-private-runtime-link-inputs-v1'
            or joined['scope'] != 'actual-selected-static-runtime-inputs-only-no-runtime-execution'
            or joined['policy_sha256'] != PRIVATE_POLICY_SHA256
            or joined['selection_sha256'] != values['BIB_NATIVE_RUNTIME_SELECTION_SHA256']
            or joined['selected_paths'] != sorted(values['BIB_NATIVE_RUNTIME_' + role + '_PATH']
                                                for role in PRIVATE_ROLE_NAMES)
            or any(joined[name] is not False for name in ('production_eligible', 'engine_execution', 'kernel_rebuild'))):
        raise ValueError('Shared private runtime checker returned a different bound input proof')
    directory = output / 'pic-check/private-runtime'
    directory.mkdir(mode=0o755)
    inspector = inspected.toolchain['tools']['inspect']
    verifier = output / 'private-runtime/verify-provider.cmake'
    original = Path(inspected.repository_root) / PRIVATE_SHARED_SOURCES[2]
    verifier_raw = inspected.inputs.bytes(original)
    if read(verifier, hashlib.sha256(verifier_raw).hexdigest()) != verifier_raw:
        raise ValueError('Staged private ELF verifier differs from captured source')
    arguments = {'ARTIFACT': str(shared), 'BUILD_ROOT': str(output), 'EVIDENCE': str(directory),
        'INSPECT_TOOL': inspector['path'], 'INSPECT_SHA256': inspector['sha256'],
        'ALLOWED_NEEDED_JSON': json.dumps(inspected.toolchain['runtime']['needed_libraries'], separators=(',', ':')),
        'MAXIMUM_ARTIFACT_BYTES': str(inspected.phase_limits['maximum_output_bytes']),
        'PRIVATE_RUNTIME_POLICY_SHA256': PRIVATE_POLICY_SHA256, 'INSPECTION_KIND': 'dependencies-pic-v1'}
    argv = [inspected.toolchain['tools']['cmake']['path']] + [
        '-DBIB_NATIVE_PROTOTYPE_' + name + '=' + value for name, value in sorted(arguments.items())] + ['-P', str(verifier)]
    commands.append(run_owned(argv, output, directory / 'command.log', environment, inspected.phase_limits,
        phase='inspection', output=output, absolute_deadline=deadline))
    receipt = directory / 'provider-inspection.json'
    evidence = document(receipt)
    fields(evidence, ('schema_version', 'kind', 'scope', 'artifact_sha256', 'artifact_bytes',
        'architecture', 'exports', 'needed', 'symbols_sha256', 'dynamic_sha256', 'version_info_sha256',
        'inspect_tool_sha256', 'private_runtime_policy_sha256', 'production_eligible',
        'engine_execution', 'kernel_rebuild'), 'Private dependency ELF receipt')
    if (type(evidence.get('schema_version')) is not int or evidence['schema_version'] != 1
            or evidence.get('kind') != 'foundation-native-dependencies-private-pic-inspection-v1'
            or evidence.get('scope') != 'actual-linked-native-dependencies-private-pic-byte-inspection'
            or evidence.get('artifact_sha256') != shared_hash or evidence.get('architecture') != 'elf64-x86_64'
            or type(evidence.get('artifact_bytes')) is not int or evidence['artifact_bytes'] != shared.stat().st_size
            or type(evidence.get('needed')) is not list or not evidence['needed']
            or any(type(item) is not str for item in evidence['needed'])
            or set(evidence['needed']) - set(inspected.toolchain['runtime']['needed_libraries'])
            or sorted(set(evidence['needed'])) != expected_needed
            or evidence.get('exports') != [PRIVATE_EXPORT] or evidence.get('inspect_tool_sha256') != inspector['sha256']
            or evidence.get('private_runtime_policy_sha256') != PRIVATE_POLICY_SHA256
            or any(evidence.get(name) is not False for name in ('production_eligible', 'engine_execution', 'kernel_rebuild'))):
        raise ValueError('Private dependency ELF receipt differs from the exact diagnostic contract')
    for field, name in (('symbols_sha256', 'provider-dynamic-symbols.txt'),
                        ('dynamic_sha256', 'provider-dynamic-section.txt'),
                        ('version_info_sha256', 'provider-version-info.txt')):
        if file_digest(directory / name, 4 * 1024 * 1024, deadline) != sha(evidence.get(field)):
            raise ValueError('Private dependency ELF log differs from its receipt')
    export_map = output / 'components/pic/dependencies-pic.exports.map'
    if read(export_map) != PRIVATE_EXPORT_RAW:
        raise ValueError('Private dependency diagnostic export policy differs from its fixed bytes')
    inspected.inputs.bytes(original)
    if file_digest(shared, inspected.phase_limits['maximum_output_bytes'], deadline) != shared_hash:
        raise ValueError('Private dependency DSO changed during shared verification')
    return {'policy_sha256': PRIVATE_POLICY_SHA256,
        'selection_sha256': values['BIB_NATIVE_RUNTIME_SELECTION_SHA256'], 'link_inputs': joined,
        'inspection': {'path': receipt.relative_to(output).as_posix(),
                       'sha256': file_digest(receipt, MAX_DOCUMENT, deadline)},
        'export_map': {'path': export_map.relative_to(output).as_posix(),
                       'sha256': hashlib.sha256(PRIVATE_EXPORT_RAW).hexdigest(), 'bytes': len(PRIVATE_EXPORT_RAW)},
        'verifier_source_sha256': hashlib.sha256(verifier_raw).hexdigest()}


def _prefix_manifest(inspected, output, commands, plan_pin, preparation, *, controller,
                     build_deadline=None):
    prefix, libraries, archives = output / 'prefix', {}, {}
    inspection_root = output / 'inspections'
    inspection_root.mkdir(mode=0o755)
    environment = native_inputs.render_environment(inspected.toolchain, inspected.host_tools)
    environment.update({'HOME': str(output / 'home'), 'TMPDIR': str(output / 'tmp'),
                        'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONNOUSERSITE': '1'})
    inspector = inspected.toolchain['tools']['inspect']
    pic, pic_archives, pic_log, pic_argv = _pic_receipt(inspected, output, environment, commands, build_deadline)
    for number, (target, declaration) in enumerate(sorted(inspected.profile['libraries'].items())):
        archive = prefix / manifest.path_name(declaration['archive'])
        actual = native_inputs.inspect_static_archive(archive, deadline=build_deadline)
        if actual != pic_archives[target]:
            raise ValueError('Native dependency archive changed after the all-member PIC link')
        directory = inspection_root / ('%02d' % number)
        directory.mkdir(mode=0o755)
        save(directory / 'members.json', actual)
        save(directory / 'pic-check.log', pic_log)
        archives[target] = {'path': directory.relative_to(output).as_posix() + '/members.json',
                            'sha256': hashlib.sha256(encoded(actual)).hexdigest()}
        log = directory / 'archive.log'
        argv = [inspector['path'], '-h', str(archive)]
        command = run_owned(argv, output, log, environment, inspected.phase_limits,
                            phase='inspection', output=output, absolute_deadline=build_deadline)
        commands.append(command)
        evidence = {'schema_version': 1, 'kind': 'foundation-native-dependency-archive-inspection-v1',
                    'target': TARGET, 'toolchain_identity_sha256': inspected.toolchain['identity']['identity_sha256'],
                    'archive_sha256': actual['sha256'], 'format': actual['format'], 'pic': True,
                    'runtime': inspected.toolchain['runtime'],
                    'commands': [{'tool_sha256': inspector['sha256'], 'argv': argv,
                                  'exit_code': 0, 'log': {'path': 'archive.log',
                                  'sha256': hashlib.sha256(read(log)).hexdigest()}},
                                 {'tool_sha256': inspector['sha256'], 'argv': pic_argv, 'exit_code': 0,
                                  'log': {'path': 'pic-check.log',
                                          'sha256': hashlib.sha256(pic_log).hexdigest()}}]}
        save(directory / 'inspection.json', evidence)
        declaration = dict(declaration, **{name: sorted(set(declaration[name]))
                                          for name in ('includes', 'definitions', 'links')})
        libraries[target] = dict(declaration, sha256=actual['sha256'], inspection={
            'path': directory.relative_to(output).as_posix() + '/inspection.json',
            'sha256': hashlib.sha256(encoded(evidence)).hexdigest()})
    # Preserve the exact build facts before a prefix can become a usable input.
    assets = _copy_asset_input(inspected, output)
    inspected.inputs.deadline = build_deadline
    inspected.recheck()
    inventory = bounded_inventory(prefix, inspected.phase_limits, build_deadline)
    manifest.inventory_contract(inventory, '__outside-inventory__.json')
    save(output / 'prefix-inventory.json', inventory)
    original_notices = []
    notice_root = output / 'retained' / 'notices'
    notice_root.mkdir(mode=0o755)
    for number, original in enumerate(inspected.notices + inspected.assets['notices']):
        name = '%03d-' % number + Path(original['path']).name
        save(notice_root / name, read(original['path'], original['sha256']))
        original_notices.append({'path': 'retained/notices/' + name, 'sha256': original['sha256']})
    receipt = {'schema_version': 1, 'kind': BUILD_KIND, 'target': TARGET,
               'plan_sha256': plan_pin, 'inspection': inspected.as_dict(),
               'build_controller': controller,
               'preparation': preparation, 'commands': commands,
               'archive_members': archives,
               'initial_cache_sha256': hashlib.sha256(read(output / 'inputs.cmake')).hexdigest(),
               'prefix_inventory_sha256': hashlib.sha256(encoded(inventory)).hexdigest(),
               'process_tree_closed': True, 'maximum_compilation_jobs': 4,
               'production_eligible': False, 'engine_execution': False, 'kernel_rebuild': False,
               'pic_shared_link': pic,
               'limits': ['The all-member PIC shared link is checked; the real engine shared link/runtime remains required.',
                          'This candidate prefix is not an eligible engine SDK or a release qualification.']}
    save(output / 'build-receipt.json', receipt)
    pc_directories = sorted(set(str(PurePosixPath(name).parent)
                                for name in inspected.profile['pkg_config']))
    pc_files = {}
    for name in inspected.profile['pkg_config']:
        name = manifest.path_name(name)
        if name not in inventory['files']:
            raise ValueError('Native dependency prefix omits required pkg-config file: ' + name)
        pc_files[name] = inventory['files'][name]
    result = {'schema_version': 1, 'kind': 'foundation-native-engine-prototype-dependencies-v1',
              'target': TARGET, 'toolchain_identity_sha256': inspected.toolchain['identity']['identity_sha256'],
              'prefix': str(prefix), 'inventory': {'path': 'prefix-inventory.json',
              'sha256': hashlib.sha256(encoded(inventory)).hexdigest()},
              'build_provenance': [{'path': 'build-receipt.json',
                                    'sha256': hashlib.sha256(encoded(receipt)).hexdigest()},
                                   {'path': 'pic-check/receipt.json',
                                    'sha256': hashlib.sha256(encoded(pic)).hexdigest()}],
              'libraries': libraries, 'pkg_config': {'directories': pc_directories, 'files': pc_files},
              'assets': assets, 'notices': original_notices, 'windows_inputs': None}
    _check_resources(_resources(output), inspected.phase_limits)
    if build_deadline is not None and time.monotonic() >= build_deadline:
        raise ValueError('Native dependency final publication wall deadline exceeded')
    save(output / 'dependencies.json', result)
    return result


def build(plan, pin, output, *, repository_root=ROOT):
    """Execute only the explicit fixed CMake graph; never infer cost authorization."""
    if not sys.platform.startswith('linux'):
        raise ValueError('Native dependency production currently requires a qualified Linux host')
    started = time.monotonic()
    inspected, value = verify_plan(plan, pin, repository_root=repository_root)
    controller = admit_controller(inspected)
    output = fresh_output(output, (*inspected.protected_paths, Path(plan)))
    commands, prepared = [], {}
    try:
        deadline = started + inspected.phase_limits['prepare_seconds']
        for name in ('sources', 'components', 'logs', 'home', 'tmp', 'recipe'):
            (output / name).mkdir(mode=0o755)
        for name in RECIPE_FILES:
            destination = output / 'recipe' / name
            destination.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
            save(destination, read(inspected.repository_root / RECIPE / name))
        stage_private_sources(inspected, output)
        for name, entry in inspected.archives.items():
            available = inspected.phase_limits['maximum_output_bytes'] - _resources(output)['output_bytes']
            prepared[name] = extract_archive(entry, output / 'sources' / name, deadline=deadline,
                maximum_bytes=available, minimum_free_bytes=inspected.phase_limits['minimum_free_bytes'])
            _check_resources(_resources(output), inspected.phase_limits)
        save(output / 'source-projection.json', prepared)
        cache = render_cache(cache_values(inspected, output), cache_names(inspected))
        save(output / 'inputs.cmake', cache)
        inspected.recheck()
        if time.monotonic() >= deadline:
            raise ValueError('Native dependency preparation wall deadline exceeded')
        environment = native_inputs.render_environment(inspected.toolchain, inspected.host_tools)
        environment.update({'HOME': str(output / 'home'), 'TMPDIR': str(output / 'tmp'),
                            'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONNOUSERSITE': '1',
                            'PKG_CONFIG_PATH': '', 'PKG_CONFIG_LIBDIR': str(output / 'prefix/lib/pkgconfig'),
                            'PKG_CONFIG_SYSROOT_DIR': '', 'CMAKE_BUILD_PARALLEL_LEVEL': '4'})
        cmake = inspected.toolchain['tools']['cmake']['path']
        configure = [cmake, '-S', str(output / 'recipe'), '-B', str(output / 'graph'), '-G', 'Ninja',
                     '-C', str(output / 'inputs.cmake'),
                     '-DCMAKE_MAKE_PROGRAM=' + inspected.toolchain['tools']['ninja']['path']]
        commands.append(run_owned(configure, output, output / 'logs/configure.log', environment,
                                  inspected.phase_limits, phase='configure', output=output))
        # The superbuild is serial. Its one active component may use four jobs;
        # another four-job component cannot run until its predecessor installs.
        build_deadline = time.monotonic() + inspected.phase_limits['build_seconds']
        commands.append(run_owned([cmake, '--build', str(output / 'graph'), '--parallel', '1',
                                   '--target', 'native-dependencies'], output,
                                  output / 'logs/build.log', environment, inspected.phase_limits,
                                  phase='build', output=output, absolute_deadline=build_deadline))
        return _prefix_manifest(inspected, output, commands, pin, prepared,
                                controller=controller, build_deadline=build_deadline)
    except BaseException as error:
        failure = {'schema_version': 1, 'kind': BUILD_KIND, 'failed': True,
                   'reason': str(error), 'completed_commands': commands,
                   'production_eligible': False, 'engine_execution': False, 'kernel_rebuild': False}
        if hasattr(error, 'native_stage_receipt'):
            failure['incomplete_stage'] = error.native_stage_receipt
        try:
            save(output / 'failure.json', failure)
        except BaseException as publication:
            combined = ValueError('Original native dependency failure: ' + str(error)
                + '; failure evidence publication also failed: ' + str(publication))
            if hasattr(error, 'native_stage_receipt'):
                setattr(combined, 'native_stage_receipt', error.native_stage_receipt)
            raise combined from error
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest='action', required=True)
    plan_parser = actions.add_parser('plan')
    plan_parser.add_argument('--selection', required=True)
    plan_parser.add_argument('--selection-sha256', required=True)
    plan_parser.add_argument('--output', required=True)
    build_parser = actions.add_parser('build')
    build_parser.add_argument('--plan', required=True)
    build_parser.add_argument('--plan-sha256', required=True)
    build_parser.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    if args.action == 'plan':
        result = make_plan(args.selection, args.selection_sha256, args.output)
    else:
        result = build(args.plan, args.plan_sha256, args.output)
    print(encoded(result).decode('ascii'), end='')
    return 0


def cli(argv=None):
    try:
        return main(argv)
    except native_inputs.MissingInputs as error:
        print(encoded(error.as_dict()).decode('ascii'), end='', file=sys.stderr)
        return 2
    except (OSError, ValueError, KeyError, TypeError, process_tree.ProcessTreeError) as error:
        print('native-engine-dependencies: ' + str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(cli())
