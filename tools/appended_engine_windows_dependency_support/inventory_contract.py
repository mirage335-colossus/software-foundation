"""Pure schema-v1 inventory/provenance declarations; no native admission.

Only supplied JSON bytes are inspected. Original source, notice and report
references are declarations, never opened, executed or treated as authority.
The physical inventory remains a separate generic native-reader operation.
"""

import copy
import hashlib
import json
from pathlib import PurePosixPath, PureWindowsPath
import re


ROLES = frozenset(('llvm', 'msvc_stl', 'windows_sdk', 'host_generators'))
TARGET = {'system': 'Windows', 'processor': 'x86_64',
          'triple': 'x86_64-pc-windows-msvc', 'pointer_bits': 64}
MAX_DOCUMENT = 32 * 1024 * 1024
MAX_BINARY = 512 * 1024 * 1024
MAX_INVENTORY_FILES = 65536
MAX_INVENTORY_BYTES = 32 * 1024 * 1024 * 1024
MAX_ORIGINAL_REFS = 256


def encoded(value):
    """The frozen generic inventory's existing subject encoding."""
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True,
                       allow_nan=False) + '\n').encode('ascii')


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
    # Frozen de8d contract policy, independent of a moving canonical module.
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


def _relative(value):
    if (type(value) is not str or not value or len(value) > 1024 or
            PurePosixPath(value).as_posix() != value or value.startswith('/') or
            any(part in ('', '.', '..') for part in value.split('/'))):
        raise ValueError('Canonical relative Windows inventory path required')
    _windows_path('C:/inventory/' + value, 'inventory member')
    return value


def _reference(value, label):
    _fields(value, ('path', 'sha256'), label)
    _windows_path(value['path'], label)
    _pin(value['sha256'], label)
    return copy.deepcopy(value)


def _document(raw, expected_pin, label):
    _pin(expected_pin, label)
    if type(raw) is not bytes or not 1 <= len(raw) <= MAX_DOCUMENT:
        raise ValueError('Original inventory JSON byte type/bound differs')
    if hashlib.sha256(raw).hexdigest() != expected_pin:
        raise ValueError('Original inventory JSON differs from its independent SHA256')

    def pairs(items):
        result = {}
        for key, item in items:
            if key in result:
                raise ValueError('Duplicate inventory JSON field: ' + key)
            result[key] = item
        return result

    def invalid(value):
        raise ValueError('Nonfinite inventory JSON: ' + value)

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
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=pairs, parse_constant=invalid)
        encoded(value)  # Also rejects finite-spelling numeric overflow to infinity.
        strings(value)
        return value
    except (UnicodeError, RecursionError, OverflowError) as error:
        raise ValueError('Invalid inventory JSON encoding or nesting') from error


def inventory_declaration(raw, pin, role, *, provenance_raw, provenance_pin):
    """Return owned generic declarations joined to explicit original JSON bytes.

    `version` remains an inventory label. Neither it, a passed status, matching
    pins nor this function authenticates a producer or observes a tool version.
    """
    if type(role) is not str or role not in ROLES:
        raise ValueError('One of the four toolchain inventory roles is required')
    value = _document(raw, pin, role + ' inventory')
    _fields(value, ('schema_version', 'kind', 'role', 'target', 'root', 'version',
                    'files', 'directories', 'provenance'), role + ' inventory')
    if (type(value['schema_version']) is not int or value['schema_version'] != 1 or
            value['kind'] != 'foundation-windows-retained-inventory-v1' or
            value['role'] != role or encoded(value['target']) != encoded(TARGET)):
        raise ValueError('Windows retained inventory schema/role/target differs')
    root = _windows_path(value['root'], role + ' root')
    _text(value['version'], role + ' version')
    files, directories = value['files'], value['directories']
    if (type(files) is not dict or not 1 <= len(files) <= MAX_INVENTORY_FILES or
            type(directories) is not list or len(directories) > MAX_INVENTORY_FILES or
            any(type(name) is not str for name in directories)):
        raise ValueError('Windows retained inventory needs bounded complete file/directory maps')
    if directories != sorted(set(directories)):
        raise ValueError('Windows retained directories must be unique and sorted')
    kinds = {}
    for name in directories:
        _relative(name)
        if name.casefold() in kinds:
            raise ValueError('Windows retained inventory has case aliases')
        kinds[name.casefold()] = (name, 'directory')

    def parents(name):
        for parent in PurePosixPath(name).parents:
            if str(parent) != '.' and kinds.get(str(parent).casefold()) != (str(parent), 'directory'):
                raise ValueError('Windows retained inventory omits or aliases a parent directory')

    # The generic native scan also requires ancestors of declared empty dirs.
    # Check those now without touching a physical tree.
    for name in directories:
        parents(name)
    total = 0
    for name, record in files.items():
        _relative(name)
        _fields(record, ('sha256', 'bytes'), role + ' file')
        _pin(record['sha256'], role + '/' + name)
        if type(record['bytes']) is not int or not 0 <= record['bytes'] <= MAX_BINARY:
            raise ValueError('Bounded exact inventory file byte count required')
        total += record['bytes']
        if name.casefold() in kinds or total > MAX_INVENTORY_BYTES:
            raise ValueError('Windows retained inventory aliases or exceeds its total bound')
        kinds[name.casefold()] = (name, 'file')
        parents(name)
    provenance_ref = _reference(value['provenance'], role + ' original provenance')
    if provenance_ref['sha256'] != _pin(provenance_pin, 'original provenance'):
        raise ValueError('Supplied provenance pin differs from the inventory declaration')
    provenance = _document(provenance_raw, provenance_pin, role + ' provenance')
    _fields(provenance, ('schema_version', 'kind', 'role', 'target', 'inventory_subject_sha256',
                         'sources', 'notices', 'original_reports'), role + ' original provenance')
    subject = hashlib.sha256(encoded({key: item for key, item in value.items() if key != 'provenance'})).hexdigest()
    if (type(provenance['schema_version']) is not int or provenance['schema_version'] != 1 or
            provenance['kind'] != 'foundation-windows-retained-provenance-v1' or
            provenance['role'] != role or encoded(provenance['target']) != encoded(TARGET) or
            provenance['inventory_subject_sha256'] != subject):
        raise ValueError('Windows inventory and original provenance do not join')
    originals, selected = [copy.deepcopy(provenance_ref)], {provenance_ref['path'].casefold(): provenance_ref}
    for category in ('sources', 'notices', 'original_reports'):
        references = provenance[category]
        if type(references) is not list or not 1 <= len(references) <= MAX_ORIGINAL_REFS:
            raise ValueError('Windows provenance needs finite original ' + category)
        seen = set()
        for item in references:
            item = _reference(item, role + ' original ' + category)
            alias = item['path'].casefold()
            if alias in seen:
                raise ValueError('Repeated Windows provenance reference')
            seen.add(alias)
            previous = selected.get(alias)
            if previous is not None and previous != item:
                raise ValueError('Conflicting Windows provenance spelling or pin')
            if previous is None:
                selected[alias] = item
                originals.append(item)
    return {'root': root, 'version': value['version'], 'files': copy.deepcopy(files),
            'directories': list(directories), 'subject_sha256': subject,
            'provenance': copy.deepcopy(provenance_ref), 'original_refs': copy.deepcopy(originals)}
