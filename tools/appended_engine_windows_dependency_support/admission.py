"""Pure admission-v2 declaration consistency; never native admission authority.

The complete v2 declaration stays intact. Its two separately owned eleven-role
views are for engine composition only after genuine full-H2 native validation.
No input body, tool, inventory, token or original provenance is opened here.
"""

import copy
from pathlib import PureWindowsPath
import re


TARGET = {'system': 'Windows', 'processor': 'x86_64',
          'triple': 'x86_64-pc-windows-msvc', 'pointer_bits': 64}
KIND = 'foundation-native-engine-windows-admission-v2'
ENGINE_PROGRAM_NAMES = {
    'compiler': ('clang-cl.exe',), 'linker': ('lld-link.exe',),
    'archiver': ('llvm-lib.exe',), 'resource_compiler': ('llvm-rc.exe',),
    'manifest_tool': ('llvm-mt.exe',), 'cmake': ('cmake.exe',),
    'ninja': ('ninja.exe',), 'python': ('python.exe',), 'perl': ('perl.exe',),
    'ruby': ('ruby.exe',), 'gperf': ('gperf.exe',),
}
PROGRAM_NAMES = dict(ENGINE_PROGRAM_NAMES, nmake=('nmake.exe',), msbuild=('MSBuild.exe',))
LLVM_ROLES = ('compiler', 'linker', 'archiver', 'resource_compiler', 'manifest_tool')
INVENTORY_ROLES = frozenset(('llvm', 'msvc_stl', 'windows_sdk',
    'host_generators', 'native_dependencies', 'product_assets'))
CRT_ROLES = frozenset(('libcmt', 'libcpmt', 'libvcruntime', 'libucrt', 'oldnames'))
JOIN_FIELDS = ('handoff_sha256', 'recipe_sha256', 'sources_sha256',
    'provider_build_sha256', 'metadata_header_sha256', 'toolchain_identity_sha256')
ADMISSION_FIELDS = ('schema_version', 'kind', 'target', *JOIN_FIELDS,
    'inventories', 'programs', 'builtins', 'crt_libraries', 'program_versions',
    'include_directories', 'library_directories', 'system_root')


def _fields(value, names, label):
    if type(value) is not dict or set(value) != set(names):
        raise ValueError('Unsupported ' + label + ' fields')


def _pin(value, label):
    if (type(value) is not str or re.fullmatch('[0-9a-f]{64}', value) is None or
            value == '0' * 64):
        raise ValueError('Independent nonzero SHA256 required: ' + label)
    return value


def _text(value, label):
    if (type(value) is not str or not value or len(value) > 4096 or
            any(ord(char) < 32 or 127 <= ord(char) <= 159 for char in value)):
        raise ValueError('Invalid ' + label)
    try:
        value.encode('utf-8')
    except UnicodeError as error:
        raise ValueError('Invalid UTF-8 ' + label) from error
    return value


def _windows_path(value, label):
    """The released 83ff/de8d canonical local Windows declaration policy."""
    _text(value, label)
    selected = PureWindowsPath(value)
    if (not re.match('^[A-Z]:/', value) or not selected.is_absolute() or
            selected.as_posix() != value or len(value) <= 3 or '\\' in value or
            any(char in value for char in (';', '"', '$', '@'))):
        raise ValueError('Explicit canonical local Windows path required: ' + label)
    reserved = {'CON', 'PRN', 'AUX', 'NUL', 'CONIN$', 'CONOUT$',
                *('COM' + str(index) for index in range(1, 10)),
                *('LPT' + str(index) for index in range(1, 10)),
                *('COM' + digit for digit in '¹²³'),
                *('LPT' + digit for digit in '¹²³')}
    for part in selected.parts[1:]:
        if (part in ('.', '..') or part.endswith((' ', '.')) or
                any(char in part for char in ':<>|?*') or
                part.split('.')[0].upper() in reserved):
            raise ValueError('Aliased or nonportable Windows path: ' + label)
    return value


class _Paths:
    """Reject conflicting spelling, kind or pins among declared path components."""

    def __init__(self):
        self.entries = {}

    def add(self, path, label, digest=None):
        _windows_path(path, label)
        parts = PureWindowsPath(path).parts
        for count in range(1, len(parts) + 1):
            component = PureWindowsPath(*parts[:count]).as_posix()
            directory = count < len(parts) or digest is None
            entry = (component, directory, None if directory else digest)
            previous = self.entries.get(component.casefold())
            if previous is not None and previous != entry:
                raise ValueError('Conflicting Windows declared path spelling, kind or pin: ' + label)
            self.entries[component.casefold()] = entry

    def reference(self, value, label):
        _fields(value, ('path', 'sha256'), label)
        self.add(value['path'], label, _pin(value['sha256'], label))
        return value['path']


def _versions(versions):
    _fields(versions, PROGRAM_NAMES, 'Windows declared program versions')
    minima = {'cmake': (3, 24), 'ninja': (1, 10), 'python': (3, 9),
              'perl': (5, 10), 'ruby': (2, 5), 'gperf': (3, 0)}
    for role, version in versions.items():
        _text(version, role + ' declared release version')
        if re.fullmatch(r'[1-9][0-9]*\.[0-9]+(?:\.[0-9]+){0,2}', version) is None:
            raise ValueError('An exact dotted native tool release version is required: ' + role)
        numbers = tuple(int(part) for part in version.split('.'))
        minimum = (19, 1, 7) if role in LLVM_ROLES else minima.get(role)
        if minimum is not None and numbers < minimum:
            raise ValueError('Native Windows tool is below its declared producer baseline: ' + role)
    if any(versions[role] != versions['compiler'] for role in LLVM_ROLES):
        raise ValueError('Native LLVM tools must declare the same exact release')


def engine_admission_declaration(value, handoff):
    """Return an owned v2 declaration and separate engine-eleven declarations.

    This checks only caller-supplied values. The caller must retain the original
    v2 bytes/pin and obtain genuine full-H2 authority before using either view.
    It cannot replace complete inventory, file-byte or native-identity checking.
    """
    _fields(value, ADMISSION_FIELDS, 'Windows admission-v2 declaration')
    if (type(value['schema_version']) is not int or value['schema_version'] != 2 or
            type(value['kind']) is not str or value['kind'] != KIND):
        raise ValueError('Exact schema-2 admission-v2 tag required; v1 and mixed tags reject')
    _fields(value['target'], TARGET, 'Windows target declaration')
    if any(type(value['target'][key]) is not type(expected) or
            value['target'][key] != expected for key, expected in TARGET.items()):
        raise ValueError('Windows admission target declaration differs')
    if type(handoff) is not dict or not set(JOIN_FIELDS).issubset(handoff):
        raise ValueError('Independently supplied handoff needs all six digest joins')
    for name in JOIN_FIELDS:
        if _pin(value[name], name) != _pin(handoff[name], 'handoff ' + name):
            raise ValueError('Windows admission differs from supplied handoff: ' + name)
    paths = _Paths()
    _fields(value['inventories'], INVENTORY_ROLES, 'Windows inventory references')
    for role, reference in value['inventories'].items():
        paths.reference(reference, role + ' inventory')
    _fields(value['programs'], PROGRAM_NAMES, 'Windows declared programs')
    _versions(value['program_versions'])
    for role, names in PROGRAM_NAMES.items():
        path = paths.reference(value['programs'][role], role + ' program')
        if PureWindowsPath(path).name not in names:
            raise ValueError('Windows program has the wrong finite role basename: ' + role)
    builtins = paths.reference(value['builtins'], 'clang static builtins')
    if not builtins.endswith('.lib'):
        raise ValueError('Windows clang static builtins need an explicit .lib reference')
    _fields(value['crt_libraries'], CRT_ROLES, 'Windows static Release CRT references')
    for role, reference in value['crt_libraries'].items():
        path = paths.reference(reference, role + ' static CRT')
        if PureWindowsPath(path).name.casefold() != role + '.lib':
            raise ValueError('Windows static CRT library basename differs: ' + role)
    for category in ('include_directories', 'library_directories'):
        declared = value[category]
        if (type(declared) is not list or not 1 <= len(declared) <= 32 or
                any(type(path) is not str for path in declared) or
                len(set(declared)) != len(declared)):
            raise ValueError('Windows explicit search directories must be bounded and unique')
        for path in declared:
            paths.add(path, category)
    paths.add(value['system_root'], 'Windows system root')
    return {'original': copy.deepcopy(value),
            'engine_programs': {role: copy.deepcopy(value['programs'][role])
                                for role in ENGINE_PROGRAM_NAMES},
            'engine_program_versions': {role: value['program_versions'][role]
                                        for role in ENGINE_PROGRAM_NAMES}}
