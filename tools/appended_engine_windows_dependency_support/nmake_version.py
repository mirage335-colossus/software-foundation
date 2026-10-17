"""Pure finite PE VERSIONINFO reader for the private NMake resource method.

This derives descriptive numeric fields, never native/issuer authority. The
caller separately admits the exact native program/runtime and source closure.
No input reads, platform probes, commands or imports of selected code occur.
"""
import bisect
import copy
import json
import re
import struct
from pathlib import PureWindowsPath
import unicodedata


METHOD = 'nmake-pe-version-resource-v1'
OUTPUT_KIND = 'foundation-windows-nmake-version-resource-v1'
MAX_IMAGE_BYTES = 64 * 1024 * 1024
MAX_RESOURCE_BYTES = 8 * 1024 * 1024
MAX_OUTPUT_BYTES = 4096
FIXED_FIELDS = ('dwSignature', 'dwStrucVersion', 'dwFileVersionMS', 'dwFileVersionLS',
    'dwProductVersionMS', 'dwProductVersionLS', 'dwFileFlagsMask', 'dwFileFlags',
    'dwFileOS', 'dwFileType', 'dwFileSubtype', 'dwFileDateMS', 'dwFileDateLS')
FACT_FIELDS = ('version4', 'product_version4', 'resource_name', 'languages', 'fixed_file_info')
_RESOURCE_TYPES = frozenset((1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 14, 16, 17, 19, 20, 21, 22, 23, 24))
_STRING_KEYS = frozenset(('Comments', 'CompanyName', 'FileDescription', 'FileVersion',
    'InternalName', 'LegalCopyright', 'LegalTrademarks', 'OriginalFilename',
    'ProductName', 'ProductVersion'))


class InvalidVersionInfo(ValueError):
    code = 'DATA'


class UnsupportedVersionInfo(ValueError):
    code = 'SOURCE'


def _fail(message):
    raise InvalidVersionInfo('nmake-version-resource: ' + message)


def _unsupported(message):
    raise UnsupportedVersionInfo('nmake-version-resource-format: ' + message)


def _span(raw, offset, size):
    if (type(offset) is not int or type(size) is not int or offset < 0 or size < 0 or
            offset > len(raw) or size > len(raw) - offset):
        _fail('truncated or overflowing range')
    return raw[offset:offset + size]


def _u16(raw, offset):
    return struct.unpack('<H', _span(raw, offset, 2))[0]


def _u32(raw, offset):
    return struct.unpack('<I', _span(raw, offset, 4))[0]


def _disjoint(intervals, start, size, label):
    end = start + size
    index = bisect.bisect_left(intervals, (start, end))
    if ((index and intervals[index - 1][1] > start) or
            (index < len(intervals) and intervals[index][0] < end)):
        _fail('overlapping/aliased ' + label)
    intervals.insert(index, (start, end))


def _resource_region(raw):
    if type(raw) is not bytes or not 512 <= len(raw) <= MAX_IMAGE_BYTES:
        _fail('image must be 512 bytes through 64 MiB')
    if _span(raw, 0, 2) != b'MZ': _fail('missing DOS signature')
    pe = _u32(raw, 0x3c)
    if pe < 64 or pe % 4 or _span(raw, pe, 4) != b'PE\0\0':
        _fail('invalid aligned PE header')
    machine, count = _u16(raw, pe + 4), _u16(raw, pe + 6)
    if machine != 0x8664: _unsupported('only AMD64 is supported')
    if not 1 <= count <= 96: _fail('finite nonempty section table required')
    if _u32(raw, pe + 12) or _u32(raw, pe + 16):
        _unsupported('COFF symbol table is outside this image profile')
    optional_size, characteristics = _u16(raw, pe + 20), _u16(raw, pe + 22)
    if characteristics not in (0x22, 0x23):
        _unsupported('exact native executable/large-address-aware COFF flags required')
    optional = pe + 24
    if optional_size != 240 or _u16(raw, optional) != 0x20b:
        _unsupported('only the 16-directory PE32+ optional header is supported')
    _span(raw, optional, optional_size)
    if _u16(raw, optional + 68) != 3: _unsupported('console application subsystem required')
    dll_flags = _u16(raw, optional + 70)
    if dll_flags & ~0xcfe0: _unsupported('unknown/unsupported DLL characteristic bits')
    section_alignment, file_alignment = _u32(raw, optional + 32), _u32(raw, optional + 36)
    if (file_alignment < 512 or file_alignment > 65536 or file_alignment & (file_alignment - 1) or
            section_alignment < file_alignment or section_alignment & (section_alignment - 1)):
        _unsupported('ordinary power-of-two file/section alignment required')
    image_size, header_size = _u32(raw, optional + 56), _u32(raw, optional + 60)
    section_table = optional + optional_size
    if (header_size % file_alignment or header_size < section_table + count * 40 or
            header_size > len(raw) or image_size % section_alignment or not image_size):
        _fail('invalid image/header extent')
    if _u32(raw, optional + 108) != 16: _unsupported('exactly 16 data directories required')
    if _u32(raw, optional + 112 + 14 * 8) or _u32(raw, optional + 116 + 14 * 8):
        _unsupported('CLR managed images remain rejected')
    if _u32(raw, optional + 112 + 15 * 8) or _u32(raw, optional + 116 + 15 * 8):
        _unsupported('reserved data directory must be empty')
    resource_rva, resource_size = _u32(raw, optional + 128), _u32(raw, optional + 132)
    if not 16 <= resource_size <= MAX_RESOURCE_BYTES or not resource_rva:
        _unsupported('bounded nonempty resource directory required')
    raw_ranges, virtual_ranges, sections, names = [], [], [], set()
    for index in range(count):
        offset = section_table + index * 40
        name = _span(raw, offset, 8).rstrip(b'\0')
        if not name or b'\0' in name or name in names: _fail('aliased/empty section name')
        names.add(name)
        virtual_size, rva, size, pointer = (_u32(raw, offset + delta) for delta in (8, 12, 16, 20))
        flags = _u32(raw, offset + 36)
        if (_u32(raw, offset + 24) or _u32(raw, offset + 28) or
                _u16(raw, offset + 32) or _u16(raw, offset + 34)):
            _unsupported('image COFF relocations/line tables are unsupported')
        if not virtual_size or rva % section_alignment or rva < header_size:
            _fail('invalid section virtual extent')
        extent = max(virtual_size, size)
        if rva > image_size or extent > image_size - rva: _fail('section escapes image extent')
        _disjoint(virtual_ranges, rva, extent, 'section virtual ranges')
        if size:
            if pointer < header_size or pointer % file_alignment or size % file_alignment:
                _fail('unaligned/overlapping section file extent')
            _span(raw, pointer, size)
            _disjoint(raw_ranges, pointer, size, 'section file ranges')
        elif pointer:
            _unsupported('zero-byte section must have no file pointer')
        sections.append((rva, virtual_size, pointer, size, flags))
    def mapped(rva, size):
        matches = []
        for base, virtual_size, pointer, file_size, flags in sections:
            if rva >= base and rva - base <= min(virtual_size, file_size) and size <= min(virtual_size, file_size) - (rva - base):
                matches.append((pointer + rva - base, flags))
        if len(matches) != 1: _fail('RVA has no unique complete file-backed mapping')
        return matches[0]
    resource_offset, flags = mapped(resource_rva, resource_size)
    if flags != 0x40000040: _unsupported('read-only initialized resource section required')
    entry = _u32(raw, optional + 16)
    if not entry or not mapped(entry, 1)[1] & 0x20000000:
        _fail('native entry point must be file-backed executable code')
    return _span(raw, resource_offset, resource_size), resource_rva


def _version_leaves(region, base_rva):
    ranges, visited, leaves = [], set(), []
    entry_count = 0
    def directory(offset, route):
        nonlocal entry_count
        if offset % 4 or offset in visited: _fail('aliased/cyclic/unaligned resource directory')
        visited.add(offset)
        if len(visited) > 4096: _fail('resource directory count exceeds 4096')
        _span(region, offset, 16)
        if _u32(region, offset) or _u16(region, offset + 8) or _u16(region, offset + 10):
            _unsupported('resource directory reserved/user-version fields must be zero')
        named, count = _u16(region, offset + 12), _u16(region, offset + 14)
        if named: _unsupported('named resource routes are unsupported')
        if not count: _fail('empty resource directory')
        entry_count += count
        if entry_count > 16384: _fail('resource entry count exceeds 16384')
        _span(region, offset, 16 + count * 8)
        _disjoint(ranges, offset, 16 + count * 8, 'resource metadata/payload ranges')
        previous = -1
        for index in range(count):
            row = offset + 16 + index * 8
            identifier, target = _u32(region, row), _u32(region, row + 4)
            if identifier > 65535 or identifier <= previous: _fail('resource IDs must be unique sorted uint16 values')
            previous = identifier
            if not route and identifier not in _RESOURCE_TYPES: _unsupported('unknown predefined resource type')
            if len(route) == 1 and not identifier: _fail('resource name ID must be nonzero')
            selected = route + (identifier,)
            child = target & 0x7fffffff
            if len(route) < 2:
                if not target & 0x80000000: _unsupported('resource route ends before language level')
                directory(child, selected)
                continue
            if target & 0x80000000: _unsupported('resource route exceeds three levels')
            if child % 4: _fail('unaligned resource data entry')
            _span(region, child, 16)
            _disjoint(ranges, child, 16, 'resource metadata/payload ranges')
            rva, size, codepage, reserved = (_u32(region, child + delta) for delta in (0, 4, 8, 12))
            if codepage or reserved: _unsupported('resource data codepage/reserved fields must be zero')
            payload = rva - base_rva
            if payload < 0 or payload % 4 or not size: _fail('invalid resource payload RVA/size')
            _span(region, payload, size)
            _disjoint(ranges, payload, size, 'resource metadata/payload ranges')
            if selected[0] == 16:
                if selected[1] != 1: _unsupported('VERSIONINFO resource name must be 1')
                if len(leaves) >= 64: _fail('VERSIONINFO language count exceeds 64')
                leaves.append((selected[2], _span(region, payload, size)))
    directory(0, ())
    if not leaves: _unsupported('RT_VERSION/1 resource is absent')
    return leaves


def _align(value):
    return (value + 3) & ~3


def _padding(raw, start, end):
    if any(_span(raw, start, end - start)): _fail('version alignment padding must be zero')


def _block(raw, offset, limit):
    if offset % 4 or offset + 6 > limit: _fail('unaligned/truncated version block')
    length, value_length, kind = _u16(raw, offset), _u16(raw, offset + 2), _u16(raw, offset + 4)
    end = offset + length
    if length < 8 or length % 2 or end > limit: _fail('version block escapes its parent or WORD alignment')
    if kind not in (0, 1): _unsupported('unknown version block type')
    cursor, key_words = offset + 6, []
    while cursor + 2 <= end:
        word = _u16(raw, cursor); cursor += 2
        if not word: break
        key_words.append(word)
        if len(key_words) > 128: _fail('version key exceeds 128 code units')
    else: _fail('version key lacks a bounded terminator')
    try: key = struct.pack('<' + 'H' * len(key_words), *key_words).decode('utf-16le')
    except UnicodeError as error: raise InvalidVersionInfo('nmake-version-resource: invalid Unicode key') from error
    if not key or any(ord(char) < 32 or ord(char) > 126 for char in key):
        _unsupported('only nonempty ASCII version keys are supported')
    value_start = _align(cursor)
    if value_start > end: _fail('version alignment escapes its block')
    _padding(raw, cursor, value_start)
    value_bytes = value_length * (2 if kind else 1)
    value_end = value_start + value_bytes
    if value_end > end: _fail('version value escapes its block')
    return {'key': key, 'type': kind, 'value_length': value_length,
            'value_start': value_start, 'value_end': value_end, 'end': end}


def _children(raw, parent):
    cursor = _align(parent['value_end'])
    if cursor > parent['end']:
        if parent['value_end'] != parent['end']: _fail('child alignment escapes parent')
        return []
    _padding(raw, parent['value_end'], cursor)
    result = []
    while cursor < parent['end']:
        if parent['end'] - cursor <= 3:
            _padding(raw, cursor, parent['end']); break
        child = _block(raw, cursor, parent['end'])
        result.append(child)
        if len(result) > 256: _fail('version child count exceeds 256')
        following = _align(child['end'])
        if following > parent['end']:
            if child['end'] != parent['end']: _fail('child trailing alignment escapes parent')
            cursor = parent['end']
        else:
            _padding(raw, child['end'], following); cursor = following
    return result


def _container(block, key):
    if block['key'] != key or block['type'] != 1 or block['value_length']:
        _unsupported('unsupported ' + key + ' container')


def _check_children(raw, root):
    seen, tables, translations = set(), set(), None
    for child in _children(raw, root):
        if child['key'] in seen: _fail('duplicate version child container')
        seen.add(child['key'])
        if child['key'] == 'StringFileInfo':
            _container(child, 'StringFileInfo')
            rows = _children(raw, child)
            if not 1 <= len(rows) <= 64: _unsupported('one through 64 string tables required')
            for table in rows:
                if table['type'] != 1 or table['value_length'] or re.fullmatch('[0-9A-Fa-f]{8}', table['key']) is None:
                    _unsupported('unsupported string-table header')
                pair = (int(table['key'][:4], 16), int(table['key'][4:], 16))
                if pair in tables: _fail('aliased/duplicate language-codepage string table')
                tables.add(pair)
                strings, keys = _children(raw, table), set()
                if not strings: _fail('empty string table')
                for string in strings:
                    if string['key'] in ('PrivateBuild', 'SpecialBuild'):
                        _fail('non-final string is inconsistent with clear release flags')
                    if string['key'] not in _STRING_KEYS or string['type'] != 1 or not string['value_length']:
                        _unsupported('unsupported version string field')
                    if string['key'].casefold() in keys: _fail('duplicate/aliased version string key')
                    keys.add(string['key'].casefold())
                    value = _span(raw, string['value_start'], string['value_end'] - string['value_start'])
                    try: text = value.decode('utf-16le')
                    except UnicodeError as error: raise InvalidVersionInfo('nmake-version-resource: invalid Unicode string') from error
                    if not text.endswith('\0') or '\0' in text[:-1]: _fail('version string must have one final terminator')
                    if string['value_end'] != string['end']: _fail('version string has unknown trailing data')
        elif child['key'] == 'VarFileInfo':
            _container(child, 'VarFileInfo')
            rows = _children(raw, child)
            if len(rows) != 1: _unsupported('one Translation variable required')
            variable = rows[0]
            size = variable['value_length']
            if (variable['key'] != 'Translation' or variable['type'] != 0 or
                    not 4 <= size <= 256 or size % 4 or variable['value_end'] != variable['end']):
                _unsupported('unsupported Translation variable')
            translations = set()
            for offset in range(variable['value_start'], variable['value_end'], 4):
                pair = (_u16(raw, offset), _u16(raw, offset + 2))
                if pair in translations: _fail('duplicate Translation pair')
                translations.add(pair)
        else:
            _unsupported('unknown VS_VERSION_INFO child type')
    if tables and translations is not None and tables != translations:
        _fail('string-table and Translation language/codepage sets differ')


def _fixed_values(raw):
    if not 92 <= len(raw) <= 65535: _fail('VERSIONINFO leaf must be 92 through 65535 bytes')
    root = _block(raw, 0, len(raw))
    if root['key'] != 'VS_VERSION_INFO' or root['type'] != 0 or root['value_length'] != 52 or root['value_start'] != 40:
        _unsupported('exact VS_VERSION_INFO binary fixed-value root required')
    if len(raw) - root['end'] > 3: _fail('unknown data after VERSIONINFO root')
    _padding(raw, root['end'], len(raw))
    _check_children(raw, root)
    return dict(zip(FIXED_FIELDS, struct.unpack('<13I', _span(raw, root['value_start'], 52))))


def _components(ms, ls):
    return [ms >> 16, ms & 65535, ls >> 16, ls & 65535]


def _fixed(fixed):
    if type(fixed) is not dict or set(fixed) != set(FIXED_FIELDS): _fail('exact 13-DWORD fixed information required')
    if any(type(value) is not int or not 0 <= value <= 0xffffffff for value in fixed.values()):
        _fail('fixed information fields must be uint32 integers')
    if fixed['dwSignature'] != 0xfeef04bd: _fail('fixed information signature differs')
    if fixed['dwStrucVersion'] != 0x10000: _unsupported('unsupported fixed-information structure version')
    if fixed['dwFileFlagsMask'] != 0x3f: _unsupported('complete known six-flag mask is required')
    if fixed['dwFileFlags'] != 0: _fail('debug/prerelease/patched/private/inferred/special flags must all be clear')
    if fixed['dwFileOS'] != 0x40004 or fixed['dwFileType'] != 1 or fixed['dwFileSubtype'] != 0:
        _unsupported('NT Windows application with zero subtype required')
    version = _components(fixed['dwFileVersionMS'], fixed['dwFileVersionLS'])
    product = _components(fixed['dwProductVersionMS'], fixed['dwProductVersionLS'])
    if version != product: _unsupported('finite NMake profile requires equal numeric file/product versions')
    return version, product


def _facts(value):
    if type(value) is not dict or set(value) != set(FACT_FIELDS): _fail('exact version facts fields required')
    version, product = _fixed(value['fixed_file_info'])
    for field, expected in (('version4', version), ('product_version4', product)):
        row = value[field]
        if type(row) is not list or len(row) != 4 or any(type(x) is not int or not 0 <= x <= 65535 for x in row) or row != expected:
            _fail('declared numeric version components differ from fixed DWORDs')
    if type(value['resource_name']) is not int or value['resource_name'] != 1: _fail('version resource name must be integer1')
    languages = value['languages']
    if (type(languages) is not list or not 1 <= len(languages) <= 64 or
            any(type(x) is not int or not 0 <= x <= 65535 for x in languages) or
            languages != sorted(set(languages))):
        _fail('version languages must be sorted unique uint16 integers')
    return copy.deepcopy(value)


def inspect_version_info(raw):
    """Derive independent fixed numeric release facts; no expected version input."""
    region, base = _resource_region(raw)
    leaves = _version_leaves(region, base)
    fixed = None
    for language, payload in leaves:
        selected = _fixed_values(payload)
        _fixed(selected)
        if fixed is not None and selected != fixed: _fail('selected language fixed values disagree')
        fixed = selected
    version, product = _fixed(fixed)
    return _facts({'version4': version, 'product_version4': product, 'resource_name': 1,
        'languages': sorted(language for language, _ in leaves), 'fixed_file_info': fixed})


def _program(value):
    if type(value) is not dict or set(value) != {'path', 'sha256', 'bytes'}: _fail('exact program ref3 required')
    path = value['path']
    if (type(path) is not str or not 4 <= len(path) <= 1024 or re.match('^[A-Z]:/', path) is None or
            PureWindowsPath(path).as_posix() != path or not PureWindowsPath(path).is_absolute() or
            unicodedata.normalize('NFC', path) != path or PureWindowsPath(path).name != 'nmake.exe'):
        _fail('canonical absolute selected nmake.exe path required')
    try: path.encode('utf-8')
    except UnicodeError as error: raise InvalidVersionInfo('nmake-version-resource: malformed program path Unicode') from error
    for part in PureWindowsPath(path).parts[1:]:
        if (part in ('.', '..') or part.endswith((' ', '.')) or
                any(ord(c) < 32 or 127 <= ord(c) <= 159 or c in ':<>|?*;"$@' for c in part) or
                re.fullmatch(r'(?i:CON|PRN|AUX|NUL|COM[1-9¹²³]|LPT[1-9¹²³])(?:\..*)?', part)):
            _fail('aliased/unsupported selected program path')
    pin = value['sha256']
    if type(pin) is not str or re.fullmatch('[0-9a-f]{64}', pin) is None or pin == '0' * 64:
        _fail('exact nonzero selected program hash required')
    if type(value['bytes']) is not int or not 512 <= value['bytes'] <= MAX_IMAGE_BYTES:
        _fail('selected program bytes must be 512 through 64 MiB')
    return copy.deepcopy(value)


def _encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False) + '\n').encode('ascii')


def render_output(program, facts):
    """Serialize checked descriptive facts; successful rendering issues no token."""
    document = {'schema_version': 1, 'kind': OUTPUT_KIND, 'program': _program(program), **_facts(facts)}
    raw = _encoded(document)
    if len(raw) > MAX_OUTPUT_BYTES: _fail('whole output exceeds 4096 bytes')
    return raw


def parse_output(raw, *, program):
    """Revalidate one canonical whole output against independently selected ref3."""
    selected = _program(program)
    if type(raw) is not bytes or not 1 <= len(raw) <= MAX_OUTPUT_BYTES: _fail('bounded whole output bytes required')
    def pairs(rows):
        value = {}
        for key, item in rows:
            if key in value: _fail('duplicate output JSON field')
            value[key] = item
        return value
    def bad(_): _fail('nonfinite output JSON')
    try:
        value = json.loads(raw.decode('ascii'), object_pairs_hook=pairs, parse_constant=bad)
        if type(value) is not dict or set(value) != {'schema_version', 'kind', 'program', *FACT_FIELDS}:
            _fail('exact output envelope required')
        if type(value['schema_version']) is not int or value['schema_version'] != 1 or value['kind'] != OUTPUT_KIND:
            _fail('output schema/kind differs')
        if _program(value['program']) != selected: _fail('output program differs from independently selected body')
        facts = _facts({key: value[key] for key in FACT_FIELDS})
        if _encoded(value) != raw: _fail('output must be one canonical complete ASCII JSON line')
        return facts
    except (UnicodeError, json.JSONDecodeError, RecursionError, OverflowError) as error:
        raise InvalidVersionInfo('nmake-version-resource: invalid output encoding/nesting') from error
