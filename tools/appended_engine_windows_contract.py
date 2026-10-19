#!/usr/bin/env python3
"""Passive Windows rich-engine input contract; no executable producer is emitted.

Only explicitly selected JSON metadata is read. A reference and its digest do not
admit the referenced compiler, SDK, archive, runtime or provenance. Check validates
the source-input shape; plan names the still-unadmitted prerequisites and exits 2.
Neither action scans an SDK, starts programs, fetches inputs or rebuilds a kernel.
"""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path, PureWindowsPath
import re
import stat
import sys

ROOT = Path(__file__).resolve().parents[1]
RECIPE = 'recipes/webkitwasm-native-rich4083-v1'
PROFILE_PATH = RECIPE + '/windows-producer-profile.json'
MAX_DOCUMENT = 1024 * 1024
SCOPE = 'windows-native-source-input-contract-only'
TARGET = {'system': 'Windows', 'processor': 'x86_64',
          'triple': 'x86_64-pc-windows-msvc', 'pointer_bits': 64}
CATALOGUE = {
    'source_map': {'path': RECIPE + '/source-imports.json',
                   'sha256': 'fa60aaba2408eb3d20f0b12f6412d0a012d3932581d30f98ae74ed145d131eea'},
    'provenance': {'path': RECIPE + '/provenance.json',
                   'sha256': '760b92449bb10fa7501c33408c840e68e78a00ed996633505574f0d4027f8839'},
    'graph': {'path': RECIPE + '/cmake/native-provider.cmake',
              'sha256': 'a19c8e7ddd7f1c4f15b143ca33a4826bec806ad0bd95137ac5a6059811d6dab1'},
}
COMPOSITION_PROFILE_KIND = 'foundation-native-engine-windows-producer-composition-undo-profile-v1'
COMPOSITION_CATALOGUE = {'source_map': {'path': 'recipes/webkitwasm-native-rich4083-v1/source-imports.json', 'sha256': '03c4f8a0c21165961d84da521ac0afaf8bf0d97ff2d09b1c2819390c31544b8b'}, 'provenance': {'path': 'recipes/webkitwasm-native-rich4083-v1/provenance.json', 'sha256': 'f5e4a29c6e5bdd0d396c634e8f51a2cc64c43f75d8f25e251184f65c55eb86ee'}, 'graph': {'path': 'recipes/webkitwasm-native-rich4083-v1/cmake/native-provider.cmake', 'sha256': 'a19c8e7ddd7f1c4f15b143ca33a4826bec806ad0bd95137ac5a6059811d6dab1'}}  # Bound only after final metadata/helper freeze.


NATIVE_POPUP_PROFILE_KIND = 'foundation-native-engine-windows-producer-native-popup-capability-profile-v1'
NATIVE_POPUP_CATALOGUE = {'source_map': {'path': 'recipes/webkitwasm-native-rich4083-v1/source-imports.json', 'sha256': '677fba2311553bafcbfb10317ad1a871b59bbe10223935cd6681a80af8d9e663'}, 'provenance': {'path': 'recipes/webkitwasm-native-rich4083-v1/provenance.json', 'sha256': 'f5e4a29c6e5bdd0d396c634e8f51a2cc64c43f75d8f25e251184f65c55eb86ee'}, 'graph': {'path': 'recipes/webkitwasm-native-rich4083-v1/cmake/native-provider.cmake', 'sha256': 'a19c8e7ddd7f1c4f15b143ca33a4826bec806ad0bd95137ac5a6059811d6dab1'}}


NATIVE_CONTROL_KEYPRESS_PROFILE_KIND = 'foundation-native-engine-windows-producer-native-control-keypress-profile-v1'
NATIVE_CONTROL_KEYPRESS_CATALOGUE = {'source_map': {'path': 'recipes/webkitwasm-native-rich4083-v1/source-imports.json', 'sha256': '11208c13bce5e005526199a1922deed8b17259d93d0d892e35fdc6a8969bd9d0'}, 'provenance': {'path': 'recipes/webkitwasm-native-rich4083-v1/provenance.json', 'sha256': 'f5e4a29c6e5bdd0d396c634e8f51a2cc64c43f75d8f25e251184f65c55eb86ee'}, 'graph': {'path': 'recipes/webkitwasm-native-rich4083-v1/cmake/native-provider.cmake', 'sha256': 'a19c8e7ddd7f1c4f15b143ca33a4826bec806ad0bd95137ac5a6059811d6dab1'}}


def catalogue_for_profile(value):
    if type(value) is dict and value.get('kind') == NATIVE_CONTROL_KEYPRESS_PROFILE_KIND:
        if type(NATIVE_CONTROL_KEYPRESS_CATALOGUE) is not dict or set(NATIVE_CONTROL_KEYPRESS_CATALOGUE) != set(CATALOGUE):
            raise ValueError('Native control keypress source catalogue remains unbound')
        return NATIVE_CONTROL_KEYPRESS_CATALOGUE
    if type(value) is dict and value.get('kind') == NATIVE_POPUP_PROFILE_KIND:
        if type(NATIVE_POPUP_CATALOGUE) is not dict or set(NATIVE_POPUP_CATALOGUE) != set(CATALOGUE):
            raise ValueError('Native popup source catalogue remains unbound')
        return NATIVE_POPUP_CATALOGUE
    if type(value) is dict and value.get('kind') == COMPOSITION_PROFILE_KIND:
        if type(COMPOSITION_CATALOGUE) is not dict or set(COMPOSITION_CATALOGUE) != set(CATALOGUE):
            raise ValueError('Composition source catalogue remains unbound')
        return COMPOSITION_CATALOGUE
    return CATALOGUE


def catalogue_for_map_digest(value):
    if type(NATIVE_CONTROL_KEYPRESS_CATALOGUE) is dict and value == NATIVE_CONTROL_KEYPRESS_CATALOGUE['source_map']['sha256']:
        return NATIVE_CONTROL_KEYPRESS_CATALOGUE
    if type(NATIVE_POPUP_CATALOGUE) is dict and value == NATIVE_POPUP_CATALOGUE['source_map']['sha256']:
        return NATIVE_POPUP_CATALOGUE
    if type(COMPOSITION_CATALOGUE) is dict and value == COMPOSITION_CATALOGUE['source_map']['sha256']:
        return COMPOSITION_CATALOGUE
    return CATALOGUE


def catalogue_for_recipe_inputs(inputs):
    if (type(NATIVE_CONTROL_KEYPRESS_CATALOGUE) is dict and type(inputs) is dict and
            any(type(row) is dict and row.get('sha256') == NATIVE_CONTROL_KEYPRESS_CATALOGUE['source_map']['sha256'] for row in inputs.values())):
        return NATIVE_CONTROL_KEYPRESS_CATALOGUE
    if (type(NATIVE_POPUP_CATALOGUE) is dict and type(inputs) is dict and
            any(type(row) is dict and row.get('sha256') == NATIVE_POPUP_CATALOGUE['source_map']['sha256'] for row in inputs.values())):
        return NATIVE_POPUP_CATALOGUE
    if (type(COMPOSITION_CATALOGUE) is dict and type(inputs) is dict and
            any(type(v) is dict and v.get('sha256') == COMPOSITION_CATALOGUE['source_map']['sha256'] for v in inputs.values())):
        return COMPOSITION_CATALOGUE
    return CATALOGUE


def catalogue_for_reference(value):
    """Accept only one complete independently pinned catalogue version."""
    if type(value) is dict and value == CATALOGUE:
        return CATALOGUE
    if type(COMPOSITION_CATALOGUE) is dict and type(value) is dict and value == COMPOSITION_CATALOGUE:
        return COMPOSITION_CATALOGUE
    if type(NATIVE_POPUP_CATALOGUE) is dict and type(value) is dict and value == NATIVE_POPUP_CATALOGUE:
        return NATIVE_POPUP_CATALOGUE
    if type(NATIVE_CONTROL_KEYPRESS_CATALOGUE) is dict and type(value) is dict and value == NATIVE_CONTROL_KEYPRESS_CATALOGUE:
        return NATIVE_CONTROL_KEYPRESS_CATALOGUE
    raise ValueError('Unsupported exact native source catalogue reference')


LIBRARIES = frozenset(('ICU::data', 'ICU::i18n', 'ICU::uc', 'HarfBuzz::HarfBuzz',
    'HarfBuzz::ICU', 'JPEG::JPEG', 'LibXml2::LibXml2', 'PNG::PNG', 'SQLite3::SQLite3',
    'WebP::libwebp', 'WebP::demux', 'WebP::sharpyuv', 'ZLIB::ZLIB', 'CURL::libcurl', 'OpenSSL::SSL',
    'OpenSSL::Crypto', 'LibPSL::LibPSL', 'FoundationNative::nghttp2', 'Brotli::dec',
    'Brotli::common'))
SYSTEM_LINKS = frozenset(('advapi32', 'bcrypt', 'crypt32', 'iphlpapi', 'normaliz',
    'ole32', 'secur32', 'shell32', 'shlwapi', 'user32', 'version', 'winmm', 'ws2_32'))
FALSE_FACTS = ('executable_plan', 'build', 'production_eligible', 'engine_execution',
               'kernel_rebuild')


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True,
                       allow_nan=False) + '\n').encode('ascii')


def fields(value, names, label):
    if type(value) is not dict or set(value) != set(names):
        raise ValueError('Unsupported ' + label + ' fields')
    return value


def text(value, label):
    if (type(value) is not str or not value or len(value) > 4096 or any(
            ord(char) < 32 or 127 <= ord(char) <= 159 for char in value)):
        raise ValueError('Invalid ' + label)
    try:
        value.encode('utf-8')
    except UnicodeError as error:
        raise ValueError('Invalid UTF-8 ' + label) from error
    return value


def pin(value, label):
    if type(value) is not str or not re.fullmatch('[0-9a-f]{64}', value) or value == '0' * 64:
        raise ValueError('Independent nonzero SHA256 required: ' + label)
    return value


def parse_document(raw):
    if type(raw) is not bytes or len(raw) > MAX_DOCUMENT:
        raise ValueError('Windows input JSON exceeds its 1 MiB byte bound')
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate Windows input JSON field: ' + key)
            result[key] = value
        return result
    def invalid(value):
        raise ValueError('Nonfinite Windows input JSON: ' + value)
    def unicode_values(value):
        if type(value) is str:
            value.encode('utf-8')
        elif type(value) is dict:
            for key, item in value.items():
                unicode_values(key)
                unicode_values(item)
        elif type(value) is list:
            for item in value:
                unicode_values(item)
    try:
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=pairs,
                           parse_constant=invalid)
        unicode_values(value)
        encoded(value)
        return value
    except (UnicodeError, RecursionError, OverflowError) as error:
        raise ValueError('Invalid Windows input JSON encoding or nesting') from error


def windows_path(value, label):
    """Canonical drive-absolute, slash-separated CMake paths; no UNC/ADS aliases."""
    text(value, label)
    path = PureWindowsPath(value)
    if (not re.match('^[A-Z]:/', value) or not path.is_absolute() or
            path.as_posix() != value or len(value) <= 3 or '\\' in value or
            any(char in value for char in (';', '"', '$', '@'))):
        raise ValueError('Explicit canonical local Windows path required: ' + label)
    reserved = {'CON', 'PRN', 'AUX', 'NUL', 'CONIN$', 'CONOUT$',
                *('COM' + str(index) for index in range(1, 10)),
                *('LPT' + str(index) for index in range(1, 10)),
                *('COM' + digit for digit in '¹²³'),
                *('LPT' + digit for digit in '¹²³')}
    for part in path.parts[1:]:
        if (part in ('.', '..') or part.endswith((' ', '.')) or
                any(char in part for char in ':<>|?*') or
                part.split('.')[0].upper() in reserved):
            raise ValueError('Aliased or nonportable Windows path: ' + label)
    return value


def inside(path, root):
    child, parent = PureWindowsPath(path), PureWindowsPath(root)
    return child != parent and parent in child.parents


def validate_profile(value):
    native_control_keypress = type(value) is dict and value.get('kind') == NATIVE_CONTROL_KEYPRESS_PROFILE_KIND
    native_popup = type(value) is dict and value.get('kind') == NATIVE_POPUP_PROFILE_KIND
    composition = type(value) is dict and value.get('kind') == COMPOSITION_PROFILE_KIND
    catalogue = catalogue_for_profile(value)
    expected = {
        'schema_version': 1, 'kind': NATIVE_CONTROL_KEYPRESS_PROFILE_KIND if native_control_keypress else NATIVE_POPUP_PROFILE_KIND if native_popup else COMPOSITION_PROFILE_KIND if composition else 'foundation-native-engine-windows-producer-profile-v1',
        'scope': SCOPE, 'profile': 'document-actions-v1', 'target': TARGET,
        'recipe_directory': RECIPE, **catalogue,
        'source_files': 158 if native_control_keypress or native_popup or composition else 157, 'engine_files': 48, 'direct_translation_units': 32,
        'toolchain_policy': 'native-windows-x64-clang-cl-cxx23-release-static-mt',
        'publication_policy': 'unimplemented-native-adapter-or-two-host-metadata-join',
        'dependency_policy': 'complete-pinned-static-native-inventory-and-provenance',
        'implementation_status': 'passive-input-contract-only',
        **{name: False for name in FALSE_FACTS},
    }
    if type(value) is not dict or encoded(value) != encoded(expected):
        raise ValueError('Windows producer profile differs from its exact source-only contract')
    return copy.deepcopy(value)


def validate_inputs(value):
    """Validate the existing CMake importer's shape, without reading its references."""
    fields(value, ('schema_version', 'kind', 'target', 'build_type', 'crt',
        'cpu_baseline', 'os_floor_declaration', 'engine_cxx_standard',
        'dependency_prefix', 'toolchain', 'dependency_inventory', 'woff2',
        'libraries'), 'Windows native input')
    expected = {'schema_version': 1, 'kind': 'foundation-native-engine-windows-inputs',
        'target': 'windows-x86_64', 'build_type': 'Release', 'crt': 'static-mt',
        'cpu_baseline': 'x86_64-sse2', 'os_floor_declaration': 'windows-10-1809-unqualified',
        'engine_cxx_standard': 23}
    if any(type(value[name]) is not type(wanted) or value[name] != wanted
           for name, wanted in expected.items()):
        raise ValueError('Windows target/C++23/Release/static-CRT/CPU/floor declaration differs')
    prefix = windows_path(value['dependency_prefix'], 'native dependency prefix')
    aliases = {}
    def register(path, digest=None):
        parts = PureWindowsPath(path).parts
        for count in range(1, len(parts) + 1):
            component = PureWindowsPath(*parts[:count]).as_posix()
            directory = count < len(parts) or digest is None
            component_digest = None if directory else digest
            previous = aliases.get(component.casefold())
            if previous is not None and (previous[0] != component or
                    previous[2] != directory or previous[1] != component_digest):
                raise ValueError('Conflicting Windows path spelling, kind or independent pin')
            aliases[component.casefold()] = (component, component_digest, directory)
    def reference(item, label):
        fields(item, ('path', 'sha256'), label)
        path = windows_path(item['path'], label)
        register(path, pin(item['sha256'], label))
        return path
    register(prefix)
    chain = fields(value['toolchain'], ('compiler', 'linker', 'builtins',
        'compiler_version', 'msvc_stl', 'windows_sdk'), 'Windows toolchain')
    for role in ('compiler', 'linker', 'builtins'):
        path = reference(chain[role], role)
        basename = PureWindowsPath(path).name
        allowed = {'compiler': ('clang-cl.exe',), 'linker': ('link.exe', 'lld-link.exe')}
        if role in allowed and basename not in allowed[role] or role == 'builtins' and not path.endswith('.lib'):
            raise ValueError('Windows tool role needs its explicit clang-cl/linker/builtins file: ' + role)
    if (type(chain['compiler_version']) is not str or
            not re.fullmatch(r'[1-9][0-9]*\.[0-9]+\.[0-9]+', chain['compiler_version'])):
        raise ValueError('Exact dotted clang-cl compiler version required')
    for role in ('msvc_stl', 'windows_sdk'):
        item = fields(chain[role], ('root', 'inventory'), role)
        root = windows_path(item['root'], role + ' root')
        register(root)
        reference(item['inventory'], role + ' complete inventory')
    reference(value['dependency_inventory'], 'native dependency complete inventory')
    if value['woff2'] not in ('ON', 'OFF') or type(value['woff2']) is not str:
        raise ValueError('Windows WOFF2 policy must be explicitly ON or OFF')
    required = LIBRARIES | (frozenset(('WOFF2::dec', 'WOFF2::common'))
                            if value['woff2'] == 'ON' else frozenset())
    fields(value['libraries'], required, 'closed Windows native library map')
    for target, item in value['libraries'].items():
        fields(item, ('path', 'sha256', 'includes', 'definitions', 'links'), target)
        path = reference({name: item[name] for name in ('path', 'sha256')}, target)
        if not inside(path, prefix) or not path.endswith('.lib'):
            raise ValueError('Windows static dependency archive must be inside its prefix: ' + target)
        for property_name in ('includes', 'definitions', 'links'):
            values = item[property_name]
            if (type(values) is not list or len(values) > 128 or
                    any(type(child) is not str for child in values) or len(set(values)) != len(values)):
                raise ValueError('Bounded unique Windows library property required: ' + property_name)
            for child in values:
                text(child, target + '/' + property_name)
                if property_name == 'includes':
                    windows_path(child, 'native dependency include')
                    register(child)
                    if not inside(child, prefix):
                        raise ValueError('Windows include escapes its native dependency prefix')
                elif property_name == 'definitions':
                    if not re.fullmatch(r'[A-Z][A-Z0-9_]*(=[A-Za-z0-9_]+)?', child):
                        raise ValueError('Windows dependency definition must be a scalar macro')
                elif child not in required and child not in SYSTEM_LINKS:
                    raise ValueError('Windows dependency link escapes its closed native/system target set')
        if target == 'WebP::libwebp' and 'WebP::sharpyuv' not in item['links']:
            raise ValueError('Static Windows WebP requires its explicit same-source sharpyuv target/link closure')
    # Own the accepted data. Caller mutation must never rewrite a checked plan.
    return copy.deepcopy(value)


class MissingInputs(ValueError):
    def __init__(self, missing):
        self.missing = tuple(copy.deepcopy(missing))
        super().__init__('Missing retained Windows engine inputs: ' + '; '.join(
            item['role'] + ': ' + item['path'] + ' (' + item['reason'] + ')' for item in self.missing))

    def as_dict(self):
        return {'schema_version': 1, 'kind': 'foundation-native-engine-windows-missing-inputs-v1',
                'scope': SCOPE, 'missing': copy.deepcopy(list(self.missing)),
                **{name: False for name in FALSE_FACTS}}


def required_admission(value):
    value = validate_inputs(value)
    chain = value['toolchain']
    rows = [
        ('clang-cl-toolchain', chain['compiler']['path'], 'complete compiler/tool runtime inventory and original provenance are not admitted'),
        ('native-linker', chain['linker']['path'], 'exact linker identity/version, CRT compatibility and owned completion are not admitted'),
        ('clang-builtins', chain['builtins']['path'], 'native COFF architecture, static CRT and library provenance are not admitted'),
        ('msvc-stl', chain['msvc_stl']['root'], 'complete separately retained MSVC STL/toolset bytes and provenance are not admitted'),
        ('windows-sdk', chain['windows_sdk']['root'], 'complete separately retained Windows SDK bytes and version are not admitted'),
        ('native-dependencies', value['dependency_prefix'], 'complete library/include inventories, COFF/CRT/link closure and producer provenance are not admitted'),
        ('host-generators', '<explicit retained Windows build-only generators>', 'Python/Perl/Ruby/gperf/CMake/Ninja and complete interpreter runtimes are not selected or admitted'),
        ('product-assets', '<explicit retained fonts/data/notices>', 'complete product fonts/data/license closure is not selected or admitted'),
        ('metadata-publication-join', '<explicit native adapter or two-host handoff>', 'native source publication and exact POSIX-generated R/S/B/header transfer join are not implemented'),
        ('native-build-adapter', '<explicit Windows clang-cl producer>', 'the selected common graph requires a native Windows host; no executable producer or cross-host policy is implemented'),
        ('provider-inspection', '<explicit PE sole-export/import/CRT verifier>', 'linked provider byte inspection and exact input link evidence are not implemented'),
    ]
    return [{'role': role, 'path': path, 'reason': reason} for role, path, reason in rows]


def assess(profile, value):
    validate_profile(profile)
    value = validate_inputs(value)
    return {'schema_version': 1, 'kind': 'foundation-native-engine-windows-contract-check-v1',
            'scope': SCOPE, 'target': dict(TARGET), 'manifest_contract_valid': True,
            'source_catalogue': copy.deepcopy(catalogue_for_profile(profile)),
            'missing_admission': required_admission(value),
            **{name: False for name in FALSE_FACTS}}


def read_metadata(path, expected_pin, role):
    """Read only a caller-pinned metadata document; never follow its references."""
    path = Path(path)
    if not path.is_absolute() or '..' in path.parts:
        raise ValueError('Explicit absolute metadata path required')
    pin(expected_pin, role)
    identity = lambda state: (state.st_dev, state.st_ino, state.st_mode, state.st_nlink,
                              state.st_size, state.st_mtime_ns, state.st_ctime_ns)
    def ordinary_state(current, directory):
        state = current.lstat()
        attributes = getattr(state, 'st_file_attributes', None)
        if (stat.S_ISLNK(state.st_mode) or attributes is not None and attributes & 0x400 or
                os.name == 'nt' and type(attributes) is not int or
                not (stat.S_ISDIR(state.st_mode) if directory else stat.S_ISREG(state.st_mode)) or
                not directory and state.st_nlink != 1):
            raise ValueError('Metadata must be an ordinary singly linked file')
        return state
    try:
        ancestors = {}
        for current in reversed((path, *path.parents)):
            directory = current != path
            state = ordinary_state(current, directory)
            # Reading metadata does not need stable parent directory contents;
            # its selected physical path and ordinary kind must remain exact.
            ancestors[current] = (state.st_dev, state.st_ino, state.st_mode)
        before = path.lstat()
    except FileNotFoundError as error:
        raise MissingInputs([{'role': role, 'path': str(path),
                              'reason': 'explicit independently pinned metadata file absent'}]) from error
    if before.st_size > MAX_DOCUMENT:
        raise ValueError('Windows input JSON exceeds its 1 MiB byte bound')
    with os.fdopen(os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0)), 'rb') as stream:
        opened = os.fstat(stream.fileno())
        raw = stream.read(MAX_DOCUMENT + 1)
        after = os.fstat(stream.fileno())
    if (identity(before) != identity(opened) or identity(before) != identity(after) or
            identity(before) != identity(path.lstat()) or len(raw) > MAX_DOCUMENT):
        raise ValueError('Windows metadata changed during bounded read')
    for current, selected in ancestors.items():
        state = ordinary_state(current, current != path)
        if (state.st_dev, state.st_ino, state.st_mode) != selected:
            raise ValueError('Windows metadata path identity changed during bounded read')
    if hashlib.sha256(raw).hexdigest() != expected_pin:
        raise ValueError('Windows metadata differs from its independent SHA256')
    return parse_document(raw)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('check', 'plan'))
    parser.add_argument('--profile', required=True, type=Path)
    parser.add_argument('--profile-sha256', required=True)
    parser.add_argument('--inputs', required=True, type=Path)
    parser.add_argument('--inputs-sha256', required=True)
    args = parser.parse_args(argv)
    profile = read_metadata(args.profile, args.profile_sha256, 'windows-source-profile')
    value = read_metadata(args.inputs, args.inputs_sha256, 'windows-native-input-manifest')
    result = assess(profile, value)
    if args.action == 'plan':
        raise MissingInputs(result['missing_admission'])
    print(encoded(result).decode('ascii'), end='')
    return 0


def cli(argv=None):
    try:
        return main(argv)
    except MissingInputs as error:
        print(encoded(error.as_dict()).decode('ascii'), file=sys.stderr, end='')
        return 2
    except (ValueError, OSError) as error:
        print('Windows engine input contract: ' + str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(cli())
