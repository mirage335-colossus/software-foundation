#!/usr/bin/env python3
"""Explicit first-native Linux engine candidate; never a payload/kernel fallback.

Plan is passive. Build consumes an immutable complete plan and starts only its
admitted metadata generator and real supplier CMake graph. Missing native inputs
cannot select dependency production, a downloader, another engine or a kernel.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import stat
import sys
import time

import appended_engine_native_inputs as native_inputs
import process_tree

ROOT = Path(__file__).resolve().parents[1]
RECIPE = 'recipes/webkitwasm-native-rich4083-v1'
SCOPE = 'first-native-engine-baseline-candidate'
PLAN_KIND = 'foundation-native-engine-prototype-plan-v1'
BUILD_KIND = 'foundation-native-engine-prototype-build-v1'
MAX_DOCUMENT = 32 * 1024 * 1024
MAX_OUTPUT_ENTRIES = 524288
MAX_PROCESSES = 1024
PRIVATE_RUNTIME_POLICY_SHA256 = '4983920c892241475f839f6bc6e7a293b348322e390307d4a1769b97ceab9bcc'
RUNTIME_ROLES = ('LIBSTDCXX', 'LIBGCC', 'LIBGCC_EH', 'CRTBEGINS', 'CRTENDS')
MAX_LINK_EVIDENCE = 128 * 1024 * 1024
# Uncertain owners must not get an automatic second/default-budget cleanup.
# The failed command retains ownership for explicit recovery; no success or
# release may be inferred from the controller subsequently exiting.
_UNCERTAIN_OWNERS = []
PLAN_FIELDS = frozenset(('schema_version', 'kind', 'scope', 'selection', 'inspection',
    'phase_limits', 'production_eligible', 'engine_execution', 'kernel_rebuild'))


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True,
                       allow_nan=False) + '\n').encode('ascii')


def _sha(value):
    if type(value) is not str or not re.fullmatch('[0-9a-f]{64}', value) or value == '0' * 64:
        raise ValueError('A nonzero independent lowercase SHA256 is required')
    return value


def _ordinary(path, *, directory=False):
    raw = os.fspath(path)
    path = Path(raw)
    if not path.is_absolute() or str(path) != raw or '..' in path.parts:
        raise ValueError('Native prototype paths must be normalized absolute paths')
    for part in reversed((path, *path.parents)):
        current = part.lstat()
        want_directory = directory if part == path else True
        if (not (stat.S_ISDIR(current.st_mode) if want_directory else stat.S_ISREG(current.st_mode))
                or stat.S_ISLNK(current.st_mode) or not want_directory and current.st_nlink != 1):
            raise ValueError('Native prototype refuses linked, aliased or special input: ' + str(part))
    return path


def _read(path, pin=None):
    path = _ordinary(path)
    before = path.stat()
    if before.st_size > MAX_DOCUMENT:
        raise ValueError('Native prototype document exceeds 32 MiB')
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as stream:
        opened = os.fstat(stream.fileno())
        raw = stream.read(MAX_DOCUMENT + 1)
        after = os.fstat(stream.fileno())
    identity = lambda s: (s.st_dev, s.st_ino, s.st_mode, s.st_nlink, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
    if (identity(before) != identity(opened) or identity(before) != identity(after)
            or identity(before) != identity(path.stat()) or len(raw) > MAX_DOCUMENT):
        raise ValueError('Native prototype document changed while reading')
    if pin is not None and hashlib.sha256(raw).hexdigest() != _sha(pin):
        raise ValueError('Native prototype document differs from its independent pin')
    return raw


def read_document(path, pin=None):
    def pairs(items):
        value = {}
        for key, item in items:
            if key in value:
                raise ValueError('Duplicate native prototype JSON field: ' + key)
            value[key] = item
        return value
    def invalid(value):
        raise ValueError('Nonfinite native prototype JSON: ' + value)
    def strings(value):
        if type(value) is str:
            value.encode('utf-8')
        elif type(value) is dict:
            for key, item in value.items():
                strings(key)
                strings(item)
        elif type(value) is list:
            for item in value:
                strings(item)
    try:
        value = json.loads(_read(path, pin).decode('utf-8'), object_pairs_hook=pairs,
                           parse_constant=invalid)
        strings(value)
        encoded(value)
        return value
    except (UnicodeError, RecursionError, OverflowError) as error:
        raise ValueError('Invalid native prototype JSON encoding/nesting') from error


def render_cache(template, values):
    """Render only exact reviewed scalar cache tokens; no CMake code injection."""
    if type(template) is not bytes or type(values) is not dict:
        raise ValueError('Cache template/values have the wrong type')
    try:
        text = template.decode('ascii')
    except UnicodeError as error:
        raise ValueError('Cache template must be ASCII') from error
    tokens = set(re.findall(r'@([A-Za-z_][A-Za-z_0-9]*)@', text))
    if not tokens or set(values) != tokens:
        raise ValueError('Cache values must exactly match its named template tokens')
    for name, value in values.items():
        if (type(value) is not str or not value or len(value) > 4096
                or any(ord(char) < 32 or ord(char) >= 127 or char in ';"\\$@' for char in value)):
            raise ValueError('Cache value is not a bounded literal scalar: ' + name)
        text = text.replace('@' + name + '@', value)
    if '@' in text:
        raise ValueError('Unresolved native prototype cache template token')
    return text.encode('ascii')


def _fresh_output(path, protected=()):
    raw = os.fspath(path)
    path = Path(raw)
    if not path.is_absolute() or str(path) != raw or '..' in path.parts:
        raise ValueError('Native prototype output must be a normalized absolute path')
    _ordinary(path.parent, directory=True)
    for other in protected:
        other = Path(other)
        if path == other or path in other.parents or other in path.parents:
            raise ValueError('Native prototype output overlaps a retained input: ' + str(other))
    if path.exists() or path.is_symlink():
        raise ValueError('Native prototype output must be fresh; preserve existing evidence')
    path.mkdir(mode=0o700)
    return path


def _save(path, value):
    """Publish one owned new file; no replacement or uncertain retry."""
    path = Path(path)
    _ordinary(path.parent, directory=True)
    raw = value if type(value) is bytes else encoded(value)
    directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    temporary = '.' + path.name + '.tmp-' + secrets.token_hex(8)
    physical, created = None, False
    try:
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                             0o600, dir_fd=directory)
        created = True
        with os.fdopen(descriptor, 'wb') as stream:
            current = os.fstat(stream.fileno())
            physical = (current.st_dev, current.st_ino)
            stream.write(raw)
            os.fchmod(stream.fileno(), 0o644)
            stream.flush()
            os.fsync(stream.fileno())
        current = os.stat(temporary, dir_fd=directory, follow_symlinks=False)
        if ((current.st_dev, current.st_ino) != physical or current.st_nlink != 1
                or not stat.S_ISREG(current.st_mode) or current.st_size != len(raw)):
            raise ValueError('Native prototype private publication identity changed')
        os.link(temporary, path.name, src_dir_fd=directory, dst_dir_fd=directory,
                follow_symlinks=False)
        os.unlink(temporary, dir_fd=directory)
        created = False
        os.fsync(directory)
    finally:
        try:
            if created:
                current = os.stat(temporary, dir_fd=directory, follow_symlinks=False)
                if (current.st_dev, current.st_ino) != physical:
                    raise ValueError('Native publication cleanup is uncertain; preserve private output')
                os.unlink(temporary, dir_fd=directory)
        finally:
            os.close(directory)


def _output_usage(root):
    total, entries, pending = 0, 0, [Path(root)]
    while pending:
        parent = pending.pop()
        with os.scandir(parent) as children:
            for child in children:
                entries += 1
                if entries > MAX_OUTPUT_ENTRIES:
                    raise ValueError('Native prototype output exceeds its bounded entry count')
                state = child.stat(follow_symlinks=False)
                if stat.S_ISDIR(state.st_mode):
                    pending.append(Path(child.path))
                elif stat.S_ISREG(state.st_mode):
                    total += state.st_size
                elif stat.S_ISLNK(state.st_mode):
                    # CMake/supplier outputs may contain local library symlinks;
                    # never follow them while accounting private output bytes.
                    total += state.st_size
                else:
                    raise ValueError('Unexpected special file in native prototype output')
    return total


def _process_memory(pid):
    """Sample only the owned Linux supervisor's actual descendant tree."""
    total, pending, seen = 0, [int(pid)], set()
    while pending:
        current = pending.pop()
        if current in seen:
            continue
        seen.add(current)
        if len(seen) > MAX_PROCESSES:
            raise ValueError('Native prototype process tree exceeds 1024 members')
        base = Path('/proc') / str(current)
        try:
            first = (base / 'stat').read_text().rsplit(')', 1)[1].split()[19]
            status = (base / 'status').read_text()
            children = (base / 'task' / str(current) / 'children').read_text().split()
            last = (base / 'stat').read_text().rsplit(')', 1)[1].split()[19]
        except FileNotFoundError:
            continue
        if first != last:
            raise ValueError('Owned native process identity changed during sampling')
        match = re.search(r'^VmRSS:\s+([0-9]+)\s+kB$', status, re.M)
        if match:
            total += int(match.group(1)) * 1024
        for child in children:
            if not child.isdecimal() or int(child) <= 0:
                raise ValueError('Invalid owned native descendant observation')
            pending.append(int(child))
    return total


def _resources(root, pid=None):
    return {'output_bytes': _output_usage(root),
            'free_bytes': shutil.disk_usage(root).free,
            'process_tree_bytes': _process_memory(pid) if pid is not None else 0}


def _check_resources(sample, limits):
    if sample['output_bytes'] > limits['maximum_output_bytes']:
        raise ValueError('Native prototype private output byte limit exceeded')
    if sample['free_bytes'] < limits['minimum_free_bytes']:
        raise ValueError('Native prototype free disk reserve exhausted')
    if sample['process_tree_bytes'] > limits['maximum_process_tree_bytes']:
        raise ValueError('Native prototype sampled process-tree memory limit exceeded')


def run_owned(argv, cwd, log_path, environment, limits, *, phase, resource_root):
    """Supervise one admitted stage and close descendants before its receipt."""
    if phase not in ('metadata', 'configure', 'build'):
        raise ValueError('Unknown native prototype process phase')
    if (type(argv) is not list or not argv or any(type(x) is not str or not x for x in argv)
            or type(environment) is not dict):
        raise ValueError('Invalid native prototype command/environment')
    deadline_seconds = limits['prepare_seconds' if phase == 'metadata' else phase + '_seconds']
    started, owner, receipt, failure = time.monotonic(), None, None, None
    closed, launched, cleanup_uncertain = True, False, False
    sampled_peak = 0
    _check_resources(_resources(resource_root), limits)
    try:
        with Path(log_path).open('xb') as stream:
            owner = process_tree.launch(argv, Path(cwd), stream, env=environment)
            launched, closed = True, False
            _save(Path(log_path).with_suffix('.launch.json'), {'phase': phase, 'argv': argv,
                'cwd': str(cwd), 'supervisor_pid': owner.process.pid})
            while owner.poll() is None:
                if time.monotonic() - started >= deadline_seconds:
                    raise ValueError('Native prototype ' + phase + ' wall deadline exceeded')
                sample = _resources(resource_root, owner.process.pid)
                sampled_peak = max(sampled_peak, sample['process_tree_bytes'])
                _check_resources(sample, limits)
                time.sleep(0.25)
            code = owner.finish()
            receipt = {'phase': phase, 'argv': argv, 'cwd': str(cwd), 'returncode': code}
            if code != 0:
                raise ValueError('Native prototype ' + phase + ' exited ' + str(code))
            # A zero first observed after the deadline is still late. The loop
            # condition and finish() can both advance time without an iteration.
            if time.monotonic() - started >= deadline_seconds:
                raise ValueError('Native prototype ' + phase + ' wall deadline exceeded')
    except BaseException as error:
        failure = error
        if owner is not None:
            try:
                owner.terminate(timeout=limits['cleanup_seconds'])
            except BaseException as cleanup:
                cleanup_uncertain = True
                _UNCERTAIN_OWNERS.append(owner)
                failure = process_tree.ProcessTreeError(
                    'Native prototype cleanup is uncertain; retain output ownership: ' + str(cleanup))
                raise failure from error
        raise
    finally:
        final_error = None
        final_elapsed = None
        if owner is not None and not cleanup_uncertain:
            try:
                owner.close()
                closed = True
            except BaseException as error:
                failure = error
                closed = False
                final_error = error
                _UNCERTAIN_OWNERS.append(owner)
        elif isinstance(failure, process_tree.ProcessTreeError):
            # Launch may have failed after child execution and uncertain cleanup.
            closed = False
        if failure is None:
            try:
                if time.monotonic() - started >= deadline_seconds:
                    raise ValueError('Native prototype ' + phase + ' wall deadline exceeded')
                _check_resources(_resources(resource_root), limits)
                # Closing streams/descendants and the final resource sample
                # belong to the same work budget as the actual command.
                final_elapsed = time.monotonic() - started
                if final_elapsed >= deadline_seconds:
                    raise ValueError('Native prototype ' + phase + ' wall deadline exceeded')
            except BaseException as error:
                failure = error
                final_error = error
        if final_elapsed is None:
            final_elapsed = time.monotonic() - started
        stage = dict(receipt or {'phase': phase, 'argv': argv, 'cwd': str(cwd), 'returncode': None})
        stage.update({'status': 'passed' if failure is None else 'incomplete',
            'launched': launched, 'wall_seconds': final_elapsed,
            'process_tree_closed': closed, 'sampled_peak_process_tree_bytes': sampled_peak,
            'memory_observation': 'sampled-aggregate-rss-not-a-kernel-hard-limit'})
        if failure is not None:
            stage['error'] = str(failure)[:4096]
            setattr(failure, 'native_stage_receipt', stage)
        try:
            _save(Path(log_path).with_suffix('.stage.json'), stage)
        except BaseException as publication:
            if failure is None:
                setattr(publication, 'native_stage_receipt', stage)
                raise
            combined = ValueError('Original native stage failure: ' + str(failure)
                + '; stage evidence publication also failed: ' + str(publication))
            setattr(combined, 'native_stage_receipt', stage)
            raise combined from failure
        if final_error is not None:
            raise final_error
    return stage


def create_plan(selection, pin, output, *, repository_root=ROOT):
    inspection = native_inputs.inspect_selection(selection, _sha(pin), repository_root=repository_root)
    facts = inspection.as_dict()
    plan = {'schema_version': 1, 'kind': PLAN_KIND, 'scope': SCOPE,
        'selection': {'path': str(selection), 'sha256': pin}, 'inspection': facts,
        'phase_limits': inspection.phase_limits, 'production_eligible': False,
        'engine_execution': False, 'kernel_rebuild': False}
    inspection.recheck()
    destination = _fresh_output(output, inspection.protected_paths)
    _save(destination / 'plan.json', plan)
    return plan


def verify_plan(path, pin, *, repository_root=ROOT):
    raw = _read(path, _sha(pin))
    plan = read_document(path, pin)
    if (type(plan) is not dict or set(plan) != PLAN_FIELDS or plan['schema_version'] != 1
            or type(plan['schema_version']) is not int or plan['kind'] != PLAN_KIND
            or plan['scope'] != SCOPE or raw != encoded(plan)
            or any(plan[name] is not False for name in ('production_eligible', 'engine_execution', 'kernel_rebuild'))):
        raise ValueError('Plan is not an original canonical first-native candidate plan')
    reference = plan['selection']
    if type(reference) is not dict or set(reference) != {'path', 'sha256'}:
        raise ValueError('Invalid native prototype plan selection')
    inspection = native_inputs.inspect_selection(Path(reference['path']), _sha(reference['sha256']),
                                                repository_root=repository_root)
    if inspection.as_dict() != plan['inspection'] or inspection.phase_limits != plan['phase_limits']:
        raise ValueError('Native prototype original plan inputs changed; retain the earlier plan')
    inspection.recheck()
    return plan, inspection


def _literal(value):
    if (type(value) is not str or not value or len(value) > 1024 * 1024
            or ']===]' in value or '\x00' in value or '\r' in value or '\n' in value):
        raise ValueError('Invalid bounded CMake literal')
    return '[===[' + value + ']===]'


def _cache_values(template, values):
    names = set(re.findall(rb'@([A-Za-z_][A-Za-z_0-9]*)@', template))
    expected = {name.decode('ascii') for name in names}
    if not expected <= set(values):
        raise ValueError('Prepared native input misses cache variables: ' + ','.join(sorted(expected - set(values))))
    return {name: values[name] for name in expected}


def _runtime_values(values, retained, evidence):
    """Bind the already admitted private selection to one target-local hook."""
    required = ('COMPILER_TRIPLE', 'SELECTION_PATH', 'SELECTION_SHA256', 'POLICY_SHA256')
    required += tuple(role + suffix for role in RUNTIME_ROLES for suffix in ('_PATH', '_SHA256'))
    missing = [name for name in required if not values.get('BIB_NATIVE_RUNTIME_' + name)]
    if missing:
        raise ValueError('Missing admitted private C++ runtime selection: ' + ','.join(missing))
    if (values['BIB_NATIVE_RUNTIME_COMPILER_TRIPLE'] != 'x86_64-buildroot-linux-gnu'
            or values['BIB_NATIVE_RUNTIME_POLICY_SHA256'] != PRIVATE_RUNTIME_POLICY_SHA256):
        raise ValueError('Private C++ runtime differs from the explicit first-native policy')
    _read(retained / RECIPE / 'producer/private-cpp-runtime-policy-v1.json',
          PRIVATE_RUNTIME_POLICY_SHA256)
    _read(Path(values['BIB_NATIVE_RUNTIME_SELECTION_PATH']),
          _sha(values['BIB_NATIVE_RUNTIME_SELECTION_SHA256']))
    for role in RUNTIME_ROLES:
        _ordinary(Path(values['BIB_NATIVE_RUNTIME_' + role + '_PATH']))
        _sha(values['BIB_NATIVE_RUNTIME_' + role + '_SHA256'])
    values['BIB_NATIVE_RUNTIME_LINK_MAP'] = str(evidence / 'provider-link.map')
    return {name: values[name] for name in sorted(values) if name.startswith('BIB_NATIVE_RUNTIME_')}


def _link_lines(path, deadline):
    """Stream a bounded original linker output without loading its entire map."""
    path = _ordinary(path)
    before = path.stat()
    if before.st_size > MAX_LINK_EVIDENCE:
        raise ValueError('Private runtime link evidence exceeds its 128 MiB per-file bound')
    fingerprint = lambda item: (item.st_dev, item.st_ino, item.st_mode, item.st_nlink,
        item.st_size, item.st_mtime_ns, item.st_ctime_ns)
    consumed, digest = 0, hashlib.sha256()
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as stream:
        if fingerprint(os.fstat(stream.fileno())) != fingerprint(before):
            raise ValueError('Private runtime link evidence changed before reading')
        while True:
            if time.monotonic() >= deadline:
                raise ValueError('Private runtime link evidence wall deadline exceeded')
            line = stream.readline(1024 * 1024 + 1)
            if not line:
                break
            consumed += len(line)
            if consumed > MAX_LINK_EVIDENCE or len(line) > 1024 * 1024:
                raise ValueError('Private runtime link evidence has an oversized line/file')
            digest.update(line)
            yield line.decode('utf-8')
        if fingerprint(os.fstat(stream.fileno())) != fingerprint(before):
            raise ValueError('Private runtime link evidence changed while reading')
    if fingerprint(path.stat()) != fingerprint(before):
        raise ValueError('Private runtime link evidence changed after reading')
    if time.monotonic() >= deadline:
        raise ValueError('Private runtime link evidence wall deadline exceeded')
    return {'path': str(path), 'sha256': digest.hexdigest(), 'bytes': consumed}


def verify_private_runtime_link(values, trace_path, map_path):
    """Join actual GNU trace/map inputs; a DT_NEEDED allowlist is insufficient."""
    selected = {os.path.normpath(values['BIB_NATIVE_RUNTIME_' + role + '_PATH'])
        for role in RUNTIME_ROLES}
    if len(selected) != len(RUNTIME_ROLES):
        raise ValueError('Private runtime selection must contain five distinct role paths')
    runtime_family = r'(?:stdc\+\+[^/\s()]*|supc\+\+[^/\s()]*|gcc[^/\s()]*|c\+\+[^/\s()]*|unwind[^/\s()]*)'
    runtime_path = re.compile(r'(/[A-Za-z0-9_./+-]+/(?:lib' + runtime_family
        + r'[.]a|crt(?:begin|end)[^/\s()]*[.]o))(?=[\s()]|$)')
    shared_path = re.compile(r'/[A-Za-z0-9_./+-]+/lib' + runtime_family
        + r'[.]so(?:[.][0-9]+)*(?=[\s()]|$)')
    evidence, deadline = {}, time.monotonic() + 60
    for role, path in (('linker_input_trace', trace_path), ('linker_map', map_path)):
        seen, iterator = set(), _link_lines(path, deadline)
        try:
            while True:
                try:
                    line = next(iterator)
                except StopIteration as complete:
                    record = complete.value
                    break
                if shared_path.search(line):
                    raise ValueError('Private runtime link selected a shared C++/unwind library')
                for found in runtime_path.findall(line):
                    actual = os.path.normpath(found)
                    if actual not in selected:
                        raise ValueError('Private runtime link selected an undeclared runtime input: ' + found)
                    seen.add(actual)
        finally:
            iterator.close()
        if seen != selected:
            raise ValueError('Actual private runtime ' + role + ' lacks selected role inputs: '
                             + ','.join(sorted(selected - seen)))
        evidence[role] = record
    return {'kind': 'foundation-native-private-runtime-link-inputs-v1',
        'policy_sha256': PRIVATE_RUNTIME_POLICY_SHA256,
        'selection_sha256': values['BIB_NATIVE_RUNTIME_SELECTION_SHA256'],
        'selected_paths': sorted(selected), 'evidence': evidence,
        'scope': 'actual-selected-static-runtime-inputs-only-no-runtime-execution',
        'production_eligible': False, 'engine_execution': False, 'kernel_rebuild': False}


def _write_graph(inspection, prepared, build_root, evidence, output):
    """Join only declared native dependency links and the original provider graph."""
    values = dict(prepared.cmake)
    retained = Path(prepared.as_dict()['retained_root'])
    original = values['BIB_NATIVE_EMBEDDER_CMAKE']
    verifier = retained / RECIPE / 'producer/verify-provider.cmake'
    _ordinary(Path(original))
    _ordinary(verifier)
    runtime = _runtime_values(values, retained, evidence)
    runtime_helper = retained / RECIPE / 'producer/native-private-runtime.cmake'
    _ordinary(runtime_helper)
    libraries = inspection.as_dict()['dependencies']['libraries']
    for variable, name in (('NGHTTP2_LIBRARY', 'FoundationNative::nghttp2'),
                           ('BROTLIDEC_LIBRARY', 'Brotli::dec'), ('BROTLICOMMON_LIBRARY', 'Brotli::common')):
        values[variable] = libraries[name]['archive']
    # Find modules own ordinary imported targets. Only these two reviewed
    # supplier seams need a newly declared private dependency target.
    creatable = {'WebP::sharpyuv', 'FoundationNative::nghttp2', 'Brotli::dec', 'Brotli::common'}
    lines = ['# Derived from the pinned original provider graph and admitted native prefix.\n',
             'include(' + _literal(str(original)) + ')\n']
    names = sorted(libraries)
    lines.append('set(_bib_proto_dependency_names ' + ' '.join(_literal(name) for name in names) + ')\n')
    lines.append('set(_bib_proto_dependency_archives ' + ' '.join(_literal(libraries[name]['archive']) for name in names) + ')\n')
    lines.append('''function(_bib_proto_normalize_link out value)
  if("${value}" MATCHES "^\\\\$<LINK_ONLY:([^<>]+)>$")
    set(value "${CMAKE_MATCH_1}")
  endif()
  if(IS_ABSOLUTE "${value}")
    file(REAL_PATH "${value}" _path)
    list(FIND _bib_proto_dependency_archives "${_path}" _index)
    if(_index EQUAL -1)
      message(FATAL_ERROR "Imported static link escapes admitted native archives: ${value}")
    endif()
    list(GET _bib_proto_dependency_names ${_index} _name)
  elseif(TARGET "${value}")
    get_target_property(_value_actual "${value}" ALIASED_TARGET)
    if(NOT _value_actual)
      set(_value_actual "${value}")
    endif()
    set(_name "")
    foreach(_candidate IN LISTS _bib_proto_dependency_names)
      get_target_property(_candidate_actual "${_candidate}" ALIASED_TARGET)
      if(NOT _candidate_actual)
        set(_candidate_actual "${_candidate}")
      endif()
      if(_candidate_actual STREQUAL _value_actual)
        set(_name "${_candidate}")
      endif()
    endforeach()
    if(value STREQUAL "Threads::Threads")
      set(_name "Threads::Threads")
    endif()
    if(NOT _name)
      message(FATAL_ERROR "Imported static link names an undeclared native target: ${value}")
    endif()
  elseif(value MATCHES "^(m|dl|rt|atomic)$")
    set(_name "${value}")
  else()
    message(FATAL_ERROR "Imported native link has no reviewed literal normalization: ${value}")
  endif()
  set(${out} "${_name}" PARENT_SCOPE)
endfunction()
''')
    for variable, name in (('NGHTTP2_LIBRARY', 'FoundationNative::nghttp2'),
                           ('BROTLIDEC_LIBRARY', 'Brotli::dec'), ('BROTLICOMMON_LIBRARY', 'Brotli::common')):
        lines.extend(['if(NOT DEFINED ' + variable + ' OR NOT IS_ABSOLUTE "${' + variable + '}")\n',
                      '  message(FATAL_ERROR "Missing actual native raw dependency selection: ' + variable + '")\nendif()\n',
                      'file(REAL_PATH "${' + variable + '}" _raw_archive)\n',
                      'if(NOT _raw_archive STREQUAL ' + _literal(libraries[name]['archive']) + ')\n',
                      '  message(FATAL_ERROR "Raw native dependency differs from its independent archive pin: ' + variable + '")\nendif()\n'])
    for name, item in sorted(libraries.items()):
        archive = item['archive']
        if name in creatable:
            lines.extend(['if(NOT TARGET ' + name + ')\n',
                          '  add_library(' + name + ' STATIC IMPORTED GLOBAL)\n',
                          '  set_target_properties(' + name + ' PROPERTIES IMPORTED_LOCATION '
                          + _literal(archive) + ')\n', 'endif()\n'])
        lines.extend(['if(NOT TARGET ' + name + ')\n',
                      '  message(FATAL_ERROR "Required admitted native dependency target is missing: ' + name + '")\n',
                      'endif()\n',
                      'get_target_property(_actual ' + name + ' ALIASED_TARGET)\n',
                      'if(NOT _actual)\n  set(_actual ' + name + ')\nendif()\n',
                      'get_target_property(_imported "${_actual}" IMPORTED)\n',
                      'get_target_property(_location "${_actual}" IMPORTED_LOCATION)\n',
                      'if(NOT _location)\n  get_target_property(_location "${_actual}" IMPORTED_LOCATION_RELEASE)\nendif()\n',
                      'if(NOT _imported OR NOT _location)\n',
                      '  message(FATAL_ERROR "Dependency is not the declared native prefix import: ' + name + '")\nendif()\n',
                      'file(REAL_PATH "${_location}" _location)\n',
                      'if(NOT _location STREQUAL ' + _literal(archive) + ')\n',
                      '  message(FATAL_ERROR "Native dependency archive differs from the independent manifest: ' + name + '")\nendif()\n'])
    for name, item in sorted(libraries.items()):
        lines.extend(['get_target_property(_actual ' + name + ' ALIASED_TARGET)\n',
                      'if(NOT _actual)\n  set(_actual ' + name + ')\nendif()\n'])
        lines.append('set(_expected_includes ' + ' '.join(_literal(path) for path in item['includes']) + ')\n')
        lines.append('set(_expected_definitions ' + ' '.join(_literal(value) for value in item['definitions']) + ')\n')
        lines.append('set(_expected_links ' + ' '.join(_literal(link) for link in item['links']) + ')\n')
        lines.append('''foreach(_property IN ITEMS INTERFACE_INCLUDE_DIRECTORIES INTERFACE_SYSTEM_INCLUDE_DIRECTORIES)
  get_target_property(_values "${_actual}" ${_property})
  if(_values)
    foreach(_value IN LISTS _values)
      if(NOT IS_ABSOLUTE "${_value}" OR "${_value}" MATCHES "\\\\$<")
        message(FATAL_ERROR "Native imported include is not an admitted absolute directory: ${_value}")
      endif()
      file(REAL_PATH "${_value}" _value)
      if(NOT _value IN_LIST _expected_includes)
        message(FATAL_ERROR "Native imported header path escapes its declared interface: ${_value}")
      endif()
    endforeach()
  endif()
endforeach()
get_target_property(_definitions "${_actual}" INTERFACE_COMPILE_DEFINITIONS)
if(_definitions)
  foreach(_definition IN LISTS _definitions)
    if(NOT _definition IN_LIST _expected_definitions)
      message(FATAL_ERROR "Native imported macro differs from its declared interface: ${_definition}")
    endif()
  endforeach()
endif()
get_target_property(_links "${_actual}" INTERFACE_LINK_LIBRARIES)
if(_links)
  foreach(_link IN LISTS _links)
    _bib_proto_normalize_link(_normalized "${_link}")
    if(NOT _normalized IN_LIST _expected_links)
      message(FATAL_ERROR "Native imported static link differs from its declared interface: ${_link}")
    endif()
  endforeach()
endif()
foreach(_property IN ITEMS INTERFACE_COMPILE_OPTIONS INTERFACE_LINK_OPTIONS)
  get_target_property(_values "${_actual}" ${_property})
  if(_values)
    message(FATAL_ERROR "Native imported options require an explicit reviewed policy: ${_actual}/${_property}=${_values}")
  endif()
endforeach()
set_property(TARGET "${_actual}" PROPERTY INTERFACE_INCLUDE_DIRECTORIES "${_expected_includes}")
set_property(TARGET "${_actual}" PROPERTY INTERFACE_SYSTEM_INCLUDE_DIRECTORIES "")
set_property(TARGET "${_actual}" PROPERTY INTERFACE_COMPILE_DEFINITIONS "${_expected_definitions}")
set_property(TARGET "${_actual}" PROPERTY INTERFACE_LINK_LIBRARIES "${_expected_links}")
''')
    lines.append('include(' + _literal(str(runtime_helper)) + ')\n')
    for name, value in runtime.items():
        lines.append('set(' + name + ' ' + _literal(value) + ')\n')
    lines.append('bib_apply_private_cpp_runtime(BibNativeProvider)\n')
    inspect = inspection.programs['inspect']
    arguments = {
        'ARTIFACT': '$<TARGET_FILE:BibNativeProvider>', 'BUILD_ROOT': str(build_root),
        'EVIDENCE': str(evidence), 'INSPECT_TOOL': inspect['path'], 'INSPECT_SHA256': inspect['sha256'],
        'ALLOWED_NEEDED_JSON': json.dumps(inspection.needed_libraries, separators=(',', ':')),
        'PRIVATE_RUNTIME_POLICY_SHA256': PRIVATE_RUNTIME_POLICY_SHA256,
        'MAXIMUM_ARTIFACT_BYTES': str(min(2 * 1024 * 1024 * 1024, inspection.phase_limits['maximum_output_bytes']))}
    lines.extend(['add_custom_command(TARGET BibNativeProvider POST_BUILD\n',
                  '  COMMAND ' + _literal(inspection.programs['cmake']['path']) + '\n'])
    for key, value in arguments.items():
        lines.append('    ' + _literal('-DBIB_NATIVE_PROTOTYPE_' + key + '=' + value) + '\n')
    lines.extend(['    -P ' + _literal(str(verifier)) + '\n',
                  '  BYPRODUCTS ' + _literal(str(evidence / 'provider-inspection.json')) + '\n',
                  '  VERBATIM)\n'])
    _save(output, ''.join(lines).encode('ascii'))
    values['BIB_NATIVE_EMBEDDER_CMAKE'] = str(output)
    return values


def _child_environment(inspection, output):
    # Start with the exact admitted environment, never the caller's shell.
    environment = dict(inspection.environment)
    home, temporary = output / 'private-home', output / 'private-tmp'
    home.mkdir(mode=0o700)
    temporary.mkdir(mode=0o700)
    environment.update({'HOME': str(home), 'TMPDIR': str(temporary),
                        'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONNOUSERSITE': '1'})
    return environment


def _controller_python(inspection):
    """Bind process_tree's supervisor interpreter to the admitted host runtime."""
    program = inspection.programs['python']
    actual = Path(sys.executable).resolve(strict=True)
    expected = Path(program['path']).resolve(strict=True)
    if actual != expected:
        raise ValueError('Native prototype build must run under its admitted host Python; '
                         'select that executable with PYTHON before invoking build.sh')
    if not sys.dont_write_bytecode:
        raise ValueError('Native prototype build requires PYTHONDONTWRITEBYTECODE=1 '
                         'before starting its admitted Python')
    # inspect_selection/recheck binds this exact file and complete interpreter
    # runtime inventory. No second unadmitted controller executable is selected.
    return {'path': str(actual), 'sha256': _sha(program['sha256']),
            'bytecode_disabled': True, 'runtime': 'admitted-host-python-inventory'}


def build(plan_path, pin, output, *, repository_root=ROOT):
    if os.name != 'posix' or not sys.platform.startswith('linux'):
        raise ValueError('First-native prototype build supports Linux only; Windows needs its explicit native inputs and qualified two-host metadata/publication path')
    plan, inspection = verify_plan(plan_path, _sha(pin), repository_root=repository_root)
    controller = _controller_python(inspection)
    destination = _fresh_output(output, (*inspection.protected_paths, Path(plan_path)))
    receipts, phase, closed = [], 'prepare', True
    try:
        evidence, logs = destination / 'evidence', destination / 'logs'
        evidence.mkdir(mode=0o700)
        logs.mkdir(mode=0o700)
        _save(evidence / 'original-plan.json', plan)
        _save(evidence / 'controller-python.json', controller)
        _check_resources(_resources(destination), inspection.phase_limits)
        start = time.monotonic()
        prepared_root = destination / 'prepared'
        prepared = native_inputs.assemble(inspection, prepared_root)
        preparation_seconds = time.monotonic() - start
        if preparation_seconds >= inspection.phase_limits['prepare_seconds']:
            raise ValueError('Native prototype source preparation wall limit exceeded')
        facts = prepared.as_dict()
        _save(evidence / 'prepared-inputs.json', facts)
        inspection.recheck()
        _check_resources(_resources(destination), inspection.phase_limits)
        build_root = destination / 'cmake'
        build_root.mkdir(mode=0o700)
        generated = build_root / 'generated'
        generated.mkdir(mode=0o700)
        inspection_directory = build_root / 'evidence'
        inspection_directory.mkdir(mode=0o700)
        environment = _child_environment(inspection, destination)
        retained = Path(facts['retained_root'])
        generator = retained / 'source/native/runtime/generate_native_actions_metadata.py'
        _ordinary(generator)
        phase = 'metadata'
        metadata_argv = [inspection.programs['python']['path'], str(generator),
            '--source-root', str(retained), '--recipe-sha256', facts['recipe_sha256'],
            '--source-manifest-sha256', facts['sources_sha256'], '--provider-build', facts['provider_build_path'],
            '--provider-build-sha256', facts['provider_build_sha256'], '--output-root', str(generated)]
        _save(evidence / 'metadata-intent.json', {'argv': metadata_argv, 'cwd': str(destination)})
        metadata_limits = dict(inspection.phase_limits)
        metadata_limits['prepare_seconds'] -= preparation_seconds
        receipts.append(run_owned(metadata_argv, destination, logs / 'metadata.log', environment,
            metadata_limits, phase='metadata', resource_root=destination))
        metadata = generated / 'BibNativeProviderActionsMetadata.generated.h'
        raw_header = _read(metadata)
        if b'@' in raw_header or b'DESIGN TEMPLATE' in raw_header:
            raise ValueError('Generated native metadata contains unresolved/design tokens')
        values = _write_graph(inspection, prepared, build_root, inspection_directory,
                              destination / 'native-provider-prototype.cmake')
        values['BIB_NATIVE_PROVIDER_METADATA_HEADER'] = str(metadata)
        values['BIB_NATIVE_PROVIDER_METADATA_HEADER_SHA256'] = hashlib.sha256(raw_header).hexdigest()
        template = _read(retained / RECIPE / 'producer/native-initial-cache.cmake')
        cache = destination / 'native-initial-cache.cmake'
        _save(cache, render_cache(template, _cache_values(template, values)))
        source_root = Path(facts['assembled_root']) / 'source/engine'
        _ordinary(source_root / 'CMakeLists.txt')
        cmake = inspection.programs['cmake']['path']
        commands = [('configure', [cmake, '-S', str(source_root), '-B', str(build_root),
            '-G', 'Ninja', '-C', str(cache)]),
            ('build', [cmake, '--build', str(build_root), '--target', 'BibNativeProvider',
                       '--parallel', str(inspection.phase_limits['maximum_jobs'])])]
        for phase, argv in commands:
            verify_plan(plan_path, pin, repository_root=repository_root)
            _save(evidence / (phase + '-intent.json'), {'argv': argv, 'cwd': str(destination)})
            receipts.append(run_owned(argv, destination, logs / (phase + '.log'), environment,
                inspection.phase_limits, phase=phase, resource_root=destination))
            _save(evidence / (phase + '-result.json'), receipts[-1])
        verify_plan(plan_path, pin, repository_root=repository_root)
        artifact_inspection = read_document(inspection_directory / 'provider-inspection.json')
        if (artifact_inspection.get('kind') != 'foundation-native-engine-prototype-inspection-v1'
                or artifact_inspection.get('private_runtime_policy_sha256') != PRIVATE_RUNTIME_POLICY_SHA256
                or any(artifact_inspection.get(name) is not False for name in
                       ('production_eligible', 'engine_execution', 'kernel_rebuild'))):
            raise ValueError('Missing original native candidate byte inspection')
        runtime_link = verify_private_runtime_link(values, logs / 'build.log',
                                                   inspection_directory / 'provider-link.map')
        _save(evidence / 'private-runtime-link-inputs.json', runtime_link)
        result = {'schema_version': 1, 'kind': BUILD_KIND, 'scope': SCOPE,
            'status': 'linked-candidate', 'plan_sha256': pin, 'prepared': facts,
            'inspection': artifact_inspection, 'private_runtime_link': runtime_link, 'stages': receipts,
            'production_eligible': False, 'engine_execution': False, 'kernel_rebuild': False,
            'next_gate': 'original native provider runtime and full retained-group admission; no eligible SDK was emitted'}
        _save(destination / 'native-prototype-build.json', result)
        return result
    except BaseException as error:
        failed_stage = getattr(error, 'native_stage_receipt', None)
        if failed_stage is not None:
            closed = failed_stage['process_tree_closed']
        elif isinstance(error, process_tree.ProcessTreeError):
            closed = False
        failure_receipt = {'schema_version': 1,
            'kind': BUILD_KIND, 'scope': SCOPE, 'status': 'incomplete', 'phase': phase,
            'plan_sha256': pin, 'error': str(error)[:4096], 'completed_stages': receipts,
            'failed_stage': failed_stage,
            'process_ownership_confirmed': closed, 'production_eligible': False,
            'engine_execution': False, 'kernel_rebuild': False}
        try:
            _save(destination / 'native-prototype-failure.json', failure_receipt)
        except BaseException as publication:
            combined = ValueError('Original native prototype failure: ' + str(error)
                + '; failure evidence publication also failed: ' + str(publication))
            setattr(combined, 'native_failure_receipt', failure_receipt)
            raise combined from error
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    plan = sub.add_parser('plan', help='Passively validate explicit complete native inputs')
    plan.add_argument('--selection', required=True, type=Path)
    plan.add_argument('--selection-sha256', required=True)
    plan.add_argument('--output', required=True, type=Path)
    selected = sub.add_parser('build', help='Explicit costly first-native candidate; never selected by payload tools')
    selected.add_argument('--plan', required=True, type=Path)
    selected.add_argument('--plan-sha256', required=True)
    selected.add_argument('--output', required=True, type=Path)
    args = parser.parse_args(argv)
    result = (create_plan(args.selection, args.selection_sha256, args.output) if args.action == 'plan'
              else build(args.plan, args.plan_sha256, args.output))
    print(encoded(result).decode('ascii'), end='')
    return 0


def cli(argv=None):
    """Identical direct and supported-dispatch diagnostics and exit status."""
    try:
        return main(argv)
    except native_inputs.MissingInputs as error:
        print(encoded(error.as_dict()).decode('ascii'), file=sys.stderr, end='')
        return 2
    except (ValueError, OSError, process_tree.ProcessTreeError) as error:
        print('native engine prototype: ' + str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(cli())
