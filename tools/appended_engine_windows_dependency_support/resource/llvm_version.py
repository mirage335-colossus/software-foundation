"""Pure finite LLVM3 VERSIONINFO-subject method; no expected version input.

The source-exact NMake codec supplies only structural PE/resource helpers.
Its strict NMake semantic, program-name and output policies are never called.
This method derives descriptive facts, never native execution or issuer trust.
The supported loader supplies the exact frozen codec, not an ambient import.
"""
import copy
import json
from pathlib import PureWindowsPath
import re
import unicodedata

import nmake_structure_codec as _codec


METHOD = 'llvm3-pe-version-resource-v1'
OUTPUT_KIND = 'foundation-windows-llvm3-version-resource-v1'
ROLES = {'archiver': 'llvm-lib.exe', 'resource_compiler': 'llvm-rc.exe',
         'manifest_tool': 'llvm-mt.exe'}
MAX_IMAGE_BYTES = 64 * 1024 * 1024
MAX_OUTPUT_BYTES = 4096
FIXED_FIELDS = _codec.FIXED_FIELDS
FACT_FIELDS = _codec.FACT_FIELDS
DEFAULT_ZERO_FIELDS = ('dwProductVersionMS', 'dwProductVersionLS',
    'dwFileFlagsMask', 'dwFileFlags', 'dwFileOS', 'dwFileType',
    'dwFileSubtype', 'dwFileDateMS', 'dwFileDateLS')
InvalidVersionInfo = _codec.InvalidVersionInfo
UnsupportedVersionInfo = _codec.UnsupportedVersionInfo


def _fail(message):
    raise InvalidVersionInfo('llvm3-version-resource: ' + message)


def method_for(role):
    if type(role) is not str or role not in ROLES:
        _fail('exact LLVM3 subject role required')
    return METHOD


def _path(value, *, basename=None):
    if (type(value) is not str or not 4 <= len(value) <= 1024 or
            re.match('^[A-Z]:/', value) is None or
            PureWindowsPath(value).as_posix() != value or
            not PureWindowsPath(value).is_absolute() or
            unicodedata.normalize('NFC', value) != value or
            basename is not None and PureWindowsPath(value).name != basename):
        _fail('canonical absolute selected Windows path required')
    try:
        value.encode('utf-8')
    except UnicodeError as error:
        raise InvalidVersionInfo('llvm3-version-resource: malformed path Unicode') from error
    for part in PureWindowsPath(value).parts[1:]:
        if (part in ('.', '..') or part.endswith((' ', '.')) or
                any(ord(char) < 32 or 127 <= ord(char) <= 159 or
                    char in ':<>|?*;"$@' for char in part) or
                re.fullmatch(r'(?i:CON|PRN|AUX|NUL|COM[1-9¹²³]|LPT[1-9¹²³])(?:\..*)?', part)):
            _fail('aliased/unsupported selected Windows path')
    return value


def _program(role, value):
    method_for(role)
    if type(value) is not dict or set(value) != {'path', 'sha256', 'bytes'}:
        _fail('exact independent program ref3 required')
    _path(value['path'], basename=ROLES[role])
    pin = value['sha256']
    if (type(pin) is not str or re.fullmatch('[0-9a-f]{64}', pin) is None or
            pin == '0' * 64):
        _fail('exact nonzero program hash required')
    if type(value['bytes']) is not int or not 512 <= value['bytes'] <= MAX_IMAGE_BYTES:
        _fail('program bytes must be 512 through 64 MiB')
    return copy.deepcopy(value)


def collector_argv(role, runner_path, emitter_path, program_ref3):
    """Literal typed-subject command, using the independently selected runner."""
    selected = _program(role, program_ref3)
    _path(runner_path)
    _path(emitter_path, basename='llvm_version_emitter.py')
    return [runner_path, '-I', '-S', emitter_path, '--role', role,
            '--program', selected['path'], '--sha256', selected['sha256'],
            '--bytes', str(selected['bytes'])]


def version_argv(role, program_path, emitter_path, *, runner_path=None,
                 program_sha256=None, program_bytes=None):
    """Fail closed when the generic interface lacks independent runner/ref3."""
    return collector_argv(role, runner_path, emitter_path,
        {'path': program_path, 'sha256': program_sha256, 'bytes': program_bytes})


def _fixed(value):
    if type(value) is not dict or set(value) != set(FIXED_FIELDS):
        _fail('exact 13-DWORD fixed information required')
    if any(type(item) is not int or not 0 <= item <= 0xffffffff
           for item in value.values()):
        _fail('fixed information fields must be uint32 integers')
    if value['dwSignature'] != 0xfeef04bd:
        _fail('fixed information signature differs')
    if value['dwStrucVersion'] != 0x10000:
        raise UnsupportedVersionInfo('llvm3-version-resource: unsupported fixed structure')
    if any(value[key] != 0 for key in DEFAULT_ZERO_FIELDS):
        raise UnsupportedVersionInfo('llvm3-version-resource: finite zero/default profile differs')
    version = _codec._components(value['dwFileVersionMS'], value['dwFileVersionLS'])
    product = _codec._components(value['dwProductVersionMS'], value['dwProductVersionLS'])
    if version[3] != 0:
        raise UnsupportedVersionInfo('llvm3-version-resource: fourth file component must be zero')
    # The retained template declares FILEVERSION only. This admitted finite
    # profile additionally restricts its omitted fields to zero/default values;
    # it is no executed RC-writer proof or supplier-release attestation.
    return version, product


def _facts(value):
    if type(value) is not dict or set(value) != set(FACT_FIELDS):
        _fail('exact version fact fields required')
    version, product = _fixed(value['fixed_file_info'])
    for name, expected in (('version4', version), ('product_version4', product)):
        row = value[name]
        if (type(row) is not list or len(row) != 4 or
                any(type(item) is not int or not 0 <= item <= 65535 for item in row) or
                row != expected):
            _fail('numeric components differ from observed fixed DWORDs')
    if type(value['resource_name']) is not int or value['resource_name'] != 1:
        _fail('version resource name must be integer1')
    languages = value['languages']
    if (type(languages) is not list or not 1 <= len(languages) <= 64 or
            any(type(item) is not int or not 0 <= item <= 65535 for item in languages) or
            languages != sorted(set(languages))):
        _fail('version languages must be sorted unique uint16 integers')
    return copy.deepcopy(value)


def inspect_version_info(raw):
    """Observe fixed file version from supplied bytes; no selected-file I/O."""
    region, base = _codec._resource_region(raw)
    leaves = _codec._version_leaves(region, base)
    fixed = None
    for language, payload in leaves:
        selected = _codec._fixed_values(payload)
        _fixed(selected)
        if fixed is not None and selected != fixed:
            _fail('selected language fixed values disagree')
        fixed = selected
    version, product = _fixed(fixed)
    return _facts({'version4': version, 'product_version4': product,
        'resource_name': 1, 'languages': sorted(language for language, _ in leaves),
        'fixed_file_info': fixed})


def _encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'),
        ensure_ascii=True, allow_nan=False) + '\n').encode('ascii')


def render_output(role, program, facts):
    """Canonical descriptive envelope; successful rendering issues no token."""
    document = {'schema_version': 1, 'kind': OUTPUT_KIND, 'role': role,
        'program': _program(role, program), **_facts(facts)}
    raw = _encoded(document)
    if len(raw) > MAX_OUTPUT_BYTES:
        _fail('whole output exceeds 4096 bytes')
    return raw


def parse_output(raw, *, role, program=None):
    """Validate the complete log; O callers supply independent selected ref3.

    Omitting program checks self-consistency only and grants no subject binding.
    """
    method_for(role)
    selected = None if program is None else _program(role, program)
    if type(raw) is not bytes or not 1 <= len(raw) <= MAX_OUTPUT_BYTES:
        _fail('bounded whole output bytes required')
    def pairs(rows):
        value = {}
        for name, item in rows:
            if name in value:
                _fail('duplicate output JSON field')
            value[name] = item
        return value
    def bad(_):
        _fail('nonfinite output JSON')
    try:
        value = json.loads(raw.decode('ascii'), object_pairs_hook=pairs, parse_constant=bad)
        if type(value) is not dict or set(value) != {'schema_version', 'kind', 'role', 'program', *FACT_FIELDS}:
            _fail('exact output envelope required')
        if (type(value['schema_version']) is not int or value['schema_version'] != 1 or
                value['kind'] != OUTPUT_KIND or value['role'] != role):
            _fail('output schema/kind/role differs')
        actual = _program(role, value['program'])
        if selected is not None and actual != selected:
            _fail('output program differs from independently selected ref3')
        facts = _facts({key: value[key] for key in FACT_FIELDS})
        if _encoded(value) != raw:
            _fail('output must be one canonical complete ASCII JSON line')
        return facts
    except (UnicodeError, json.JSONDecodeError, RecursionError, OverflowError) as error:
        raise InvalidVersionInfo('llvm3-version-resource: invalid output encoding/nesting') from error


def parse_numeric(role, raw_log):
    """Self-consistent descriptive version; independent O joins remain required."""
    facts = parse_output(raw_log, role=role)
    return '.'.join(map(str, facts['version4'][:3]))
