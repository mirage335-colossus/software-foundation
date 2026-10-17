"""Finite supported host runtimes, from independently held original bytes.

These are pure consistency facts. The actual issuer owns the complete inventory,
current native OS identity, qualified readers, original Job and whole log. No
profile or returned dictionary establishes any of those authorities.
"""

import copy
import hashlib
import json
import os
from pathlib import Path
import stat
import types


HERE = Path(__file__).resolve().parent
NMAKE_KIND = 'foundation-windows-nmake-shell-runtime-profile-v1'
SUBJECT_KIND = 'foundation-native-engine-windows-supported-host-runtime-subject-v1'
OS_POLICY = 'qualified-native-system-root-v1'
MAX_PROFILE_BYTES = 2 * 1024**2
SOURCES = {
    'base': ('runtime_base.py', 6249,
             '911cd28fc1d23ae891b9730a4405c25cee661fca2fefd6d4d3db85f294b48194'),
    'native': ('native_inspection.py', 1914,
               '9b91a9a47598e37650c1d6f54ab64402b028452baf58ddfe9a321cad88c071e6'),
    'msbuild': ('host_methods.py', 4780,
                '017230b1026703e027d007f17a82ac00eb6df2729f0169f989343a224d092e3d'),
}
_MODULES = {}


def _encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'),
                       ensure_ascii=True, allow_nan=False) + '\n').encode('ascii')


def _module(name):
    if name not in _MODULES:
        relative, size, pin = SOURCES[name]
        source = HERE / relative
        before = source.lstat()
        identity = lambda value: (value.st_dev, value.st_ino, value.st_mode,
            value.st_nlink, value.st_size, value.st_mtime_ns, value.st_ctime_ns)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size != size:
            raise ValueError('Fixed supported-host runtime source type/size differs')
        with source.open('rb') as stream:
            opened = os.fstat(stream.fileno())
            raw = stream.read(size + 1)
            after = os.fstat(stream.fileno())
        if (identity(before) != identity(opened) or identity(before) != identity(after) or
                identity(before) != identity(source.lstat()) or len(raw) != size or
                hashlib.sha256(raw).hexdigest() != pin):
            raise ValueError('Fixed supported-host runtime source identity/pin differs')
        module = types.ModuleType('_private_supported_host_runtime_' + name)
        module.__file__ = str(source)
        exec(compile(raw, str(source), 'exec'), vars(module))
        _MODULES[name] = module
    return _MODULES[name]


def _managed():
    return _module('base')._managed()


def _document(role, reference, raw):
    if role not in ('nmake', 'msbuild') or type(role) is not str:
        raise ValueError('Exact supported host runtime role required')
    managed = _managed()
    managed._keys(reference, ('path', 'sha256', 'bytes', 'mode'), 'host runtime profile')
    managed._path(reference['path']); managed._pin(reference['sha256'])
    managed._integer(reference['bytes'], 1, MAX_PROFILE_BYTES, 'host runtime profile bytes')
    if type(reference['mode']) is not int or reference['mode'] != 0o644:
        raise ValueError('Host runtime profile logical mode0644 required')
    if (type(raw) is not bytes or len(raw) != reference['bytes'] or
            hashlib.sha256(raw).hexdigest() != reference['sha256']):
        raise ValueError('Whole original host runtime profile differs')
    if role == 'msbuild':
        return managed.parse_runtime_profile(raw, reference['sha256'])
    value = managed._json(raw, MAX_PROFILE_BYTES)
    managed._keys(value, ('schema_version', 'kind', 'program', 'host_bundle',
                         'native_images', 'system'), 'NMake shell runtime profile')
    if type(value['schema_version']) is not int or value['schema_version'] != 1 or value['kind'] != NMAKE_KIND:
        raise ValueError('Exact NMake shell runtime profile schema/kind required')
    managed._ref(value['program'])
    if value['program']['path'].rsplit('/', 1)[-1] != 'nmake.exe':
        raise ValueError('Exact NMake subject required')
    host = managed._keys(value['host_bundle'], ('root', 'inventory', 'subject_sha256'), 'host bundle')
    managed._path(host['root']); managed._metadata_ref(host['inventory']); managed._pin(host['subject_sha256'])
    if (reference['path'].casefold() == host['root'].casefold() or
            reference['path'].casefold().startswith(host['root'].rstrip('/').casefold() + '/')):
        raise ValueError('Runtime profile must be outside its complete host inventory')
    images = value['native_images']
    if type(images) is not list or not 1 <= len(images) <= 256:
        raise ValueError('Finite exact NMake native image closure required')
    names = set()
    for row in images:
        managed._ref(row)
        if not row['path'].startswith(host['root'].rstrip('/') + '/') or row['path'].casefold() in names:
            raise ValueError('NMake native closure escapes or aliases its complete host inventory')
        names.add(row['path'].casefold())
    if value['program'] not in images:
        raise ValueError('NMake subject absent from original native closure')
    system = managed._keys(value['system'], ('policy', 'root', 'windows_version',
        'command_processor'), 'qualified operating-system shell')
    if system['policy'] != OS_POLICY:
        raise ValueError('Exact existing qualified native OS-origin policy required')
    managed._path(system['root']); managed._ref(system['command_processor'])
    if system['command_processor']['path'] != system['root'].rstrip('/') + '/System32/cmd.exe':
        raise ValueError('Only the derived native System32 command processor is supported')
    version = system['windows_version']
    if type(version) is not list or len(version) != 3:
        raise ValueError('Exact current Windows major/minor/build required')
    for component in version:
        managed._integer(component, 0, 2**31 - 1, 'current Windows version component')
    return copy.deepcopy(value)


def profile_references(role, reference, raw):
    profile = _document(role, reference, raw)
    if role == 'msbuild':
        return _module('base').profile_references(role, reference, raw)
    selected = {row['path']: row for row in profile['native_images']}
    shell = profile['system']['command_processor']
    if shell['path'].casefold() in {name.casefold() for name in selected}:
        raise ValueError('Native operating-system shell aliases a bundled runtime image')
    selected[shell['path']] = shell
    return [copy.deepcopy(selected[name]) for name in sorted(selected)]


def system_references(role, reference, raw):
    profile = _document(role, reference, raw)
    return [] if role == 'msbuild' else [copy.deepcopy(profile['system']['command_processor'])]


def _held(ref, held):
    raw = held.get(ref['path'])
    if (type(raw) is not bytes or len(raw) != ref['bytes'] or
            hashlib.sha256(raw).hexdigest() != ref['sha256']):
        raise ValueError('Original host runtime selected bytes differ: ' + ref['path'])
    return raw


def runtime_profile(role, reference, raw, *, held_inventory, held_bytes,
                    system_identity=None, selected_program=None):
    profile = _document(role, reference, raw)
    if selected_program is not None and profile['program'] != selected_program:
        raise ValueError('Runtime program differs from independently selected original program')
    if role == 'msbuild':
        # A finite original CLR/configuration/import closure plus the source-owned
        # task-free project is the supported observation path. The static reader's
        # false authority flags remain descriptive, never an added execution gate.
        result = _module('base').runtime_profile(role, reference, raw,
            held_inventory=held_inventory, held_bytes=held_bytes)
        project = profile['msbuild']['entry_project']
        if profile['msbuild']['projects'] != [project] or profile['msbuild']['tasks']:
            raise ValueError('Version observation supports only one task-free original project')
        _module('msbuild').verify_project(_held(project, held_bytes))
        result['method_inputs'] = {'runtime_profile': copy.deepcopy(result['binding']),
            'project': {**copy.deepcopy(project), 'mode': 0o644},
            'project_raw': _held(project, held_bytes)}
        return result
    managed = _managed()
    inventory = managed._inventory(held_inventory)
    host = profile['host_bundle']
    if (host['root'] != inventory['root'] or host['inventory'] != held_inventory['reference'] or
            host['subject_sha256'] != inventory['subject_sha256']):
        raise ValueError('NMake runtime does not join the actual original complete host inventory')
    expected_refs = profile_references(role, reference, raw)
    if type(held_bytes) is not dict or set(held_bytes) != {row['path'] for row in expected_refs}:
        raise ValueError('Exact selected host and system runtime held-byte set required')
    if any(type(value) is not bytes for value in held_bytes.values()):
        raise ValueError('Original runtime files must be byte strings')
    if sum(len(value) for value in held_bytes.values()) > 256 * 1024**2:
        raise ValueError('Selected host runtime aggregate exceeds its finite bound')
    managed._keys(system_identity, ('root', 'windows_version'), 'actual current native OS identity')
    if system_identity != {key: profile['system'][key] for key in ('root', 'windows_version')}:
        raise ValueError('Original shell profile differs from current qualified native OS identity')
    inspector = _module('native')
    images, dependencies = {}, {}
    for item in profile['native_images']:
        relative = item['path'][len(host['root'].rstrip('/')) + 1:]
        if inventory['files'].get(relative) != {key: item[key] for key in ('sha256', 'bytes')}:
            raise ValueError('NMake runtime image not in complete held original inventory')
        if item['bytes'] > 64 * 1024**2:
            raise ValueError('NMake runtime image exceeds supported byte bound')
        facts = inspector.inspect_tool_image(_held(item, held_bytes))
        if bool(facts['dll']) != (item['path'] != profile['program']['path']):
            raise ValueError('NMake runtime image executable/DLL role differs')
        images[item['path']] = facts
    for name, facts in images.items():
        directory = name.rsplit('/', 1)[0]
        reached = []
        for imported in facts['needed']:
            if imported in inspector.SYSTEM_IMPORTS:
                continue
            choices = [path for path in images if path.rsplit('/', 1)[0] == directory and
                       path.rsplit('/', 1)[-1].casefold() == imported]
            if len(choices) != 1:
                raise ValueError('NMake native dependency has no exact same-directory bundled resolution')
            reached.append(choices[0])
        dependencies[name] = reached
    reached, pending = set(), [profile['program']['path']]
    while pending:
        name = pending.pop()
        if name not in reached:
            reached.add(name); pending.extend(dependencies[name])
    if reached != set(images):
        raise ValueError('NMake runtime contains unreached native image declarations')
    shell = profile['system']['command_processor']
    shell_facts = inspector.inspect_tool_image(_held(shell, held_bytes))
    if shell_facts['dll']:
        raise ValueError('Supported original OS shell must be a native executable')
    facts = {'program': copy.deepcopy(profile['program']), 'inventory_subject_sha256': inventory['subject_sha256'],
        'native_images': copy.deepcopy(profile['native_images']), 'native_dependencies': dependencies,
        'system': copy.deepcopy(profile['system']), 'system_imports': shell_facts['needed'],
        'selected_files': expected_refs,
        'execution_authority': False}
    subject = {'schema_version': 1, 'kind': SUBJECT_KIND, 'role': role,
        'profile': copy.deepcopy(reference), 'semantic_sources': copy.deepcopy(SOURCES), 'facts': facts}
    return {'binding': {'reference': copy.deepcopy(reference),
            'subject_sha256': hashlib.sha256(_encoded(subject)).hexdigest()},
        'selected_files': expected_refs, 'consistency': facts,
        'execution_environment': {'COMSPEC': shell['path']}}


def nmake_environment(profile_raw, reference, base_environment, *, system_identity):
    """A new private runtime policy; frozen D2/helper977 are never widened."""
    profile = _document('nmake', reference, profile_raw)
    required = {'SystemRoot', 'PATH', 'TEMP', 'TMP'}
    if (type(base_environment) is not dict or not required <= set(base_environment) or
            not set(base_environment) <= required | {'INCLUDE', 'LIB'}):
        raise ValueError('Exact preexisting closed H2 build environment required')
    managed = _managed()
    for name in ('SystemRoot', 'TEMP', 'TMP'):
        managed._path(base_environment[name])
    if base_environment['TEMP'] != base_environment['TMP']:
        raise ValueError('Original build TEMP/TMP differ')
    for name in ('PATH', 'INCLUDE', 'LIB'):
        if name not in base_environment:
            continue
        value = base_environment[name]
        if type(value) is not str or not 1 <= len(value) <= 65536:
            raise ValueError('Finite original build directory declaration required')
        directories = value.split(';')
        if not 1 <= len(directories) <= 64 or len({row.casefold() for row in directories}) != len(directories):
            raise ValueError('Unique finite original build directories required')
        for row in directories:
            managed._path(row)
    if (base_environment['SystemRoot'] != system_identity['root'] or
            system_identity != {key: profile['system'][key] for key in ('root', 'windows_version')}):
        raise ValueError('Derived command processor OS subject differs')
    return {**copy.deepcopy(base_environment), 'COMSPEC': profile['system']['command_processor']['path']}
