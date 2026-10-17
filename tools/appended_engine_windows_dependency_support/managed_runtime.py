"""Finite held-byte MSBuild metadata/XML consistency; never native admission.

No selected input is opened or executed. Physical CLI layouts are provisional
source assumptions pending independent format evidence; see API-PLAN.md. This is
not an IL verifier or proof of reflection/dynamic-loader execution closure.
"""

import copy
import hashlib
import json
import re
import struct
import xml.etree.ElementTree as ET


MAX_FILE = 64 * 1024 * 1024
MAX_TOTAL = 256 * 1024 * 1024
MAX_FILES = 4096
MAX_METADATA = 16 * 1024 * 1024
MAX_ROWS = 65536
MAX_DERIVED = 8 * 1024 * 1024
MAX_XML = 1024 * 1024
MAX_XML_NODES = 16384
MAX_XML_DEPTH = 64
PROFILE_KIND = 'foundation-windows-msbuild-managed-runtime-profile-v1'
SCOPE = 'held-byte-metadata-literal-msbuild-consistency-only'


class MissingInputs(ValueError):
    """Concrete unsupported SOURCE semantics or missing selected DATA."""


def _missing(category, field, detail):
    raise MissingInputs(category + ':' + field + ': ' + detail)


def _keys(value, fields, label):
    if type(value) is not dict or set(value) != set(fields):
        raise ValueError('Exact ' + label + ' fields required')
    return value


def _integer(value, minimum, maximum, label):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError('Invalid bounded ' + label)
    return value


def _text(value, label, maximum=4096):
    if (type(value) is not str or not 1 <= len(value) <= maximum or
            any(ord(c) < 32 or ord(c) == 127 for c in value)):
        raise ValueError('Invalid bounded ' + label)
    return value


def _pin(value):
    if (type(value) is not str or not re.fullmatch('[0-9a-f]{64}', value) or
            value == '0' * 64):
        raise ValueError('Nonzero lowercase SHA256 required')
    return value


def _relative(value):
    _text(value, 'portable relative path')
    if (not value.isascii() or value.startswith('/') or
            any(c in value for c in '\\:;"$@%~<>|?*') or
            any(not part or part in ('.', '..') or part.endswith((' ', '.')) or
                re.fullmatch(r'(?i:con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?', part)
                for part in value.split('/'))):
        raise ValueError('Canonical portable relative path required')
    return value


def _path(value):
    _text(value, 'Windows path')
    if not re.match(r'^[A-Z]:/', value):
        raise ValueError('Canonical absolute Windows path required')
    _relative(value[3:])
    return value


def _within(path, root):
    return path.startswith(root + '/')


def _ref(value, label='file reference'):
    _keys(value, ('path', 'sha256', 'bytes'), label)
    _path(value['path']); _pin(value['sha256'])
    _integer(value['bytes'], 1, MAX_FILE, label + ' bytes')
    return value


def _metadata_ref(value):
    _keys(value, ('path', 'sha256'), 'metadata reference')
    _path(value['path']); _pin(value['sha256'])
    return value


def _canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'),
                       ensure_ascii=False) + '\n').encode('utf-8')


def _json(raw, maximum):
    if type(raw) is not bytes or not 1 <= len(raw) <= maximum:
        raise ValueError('Bounded original JSON bytes required')
    def pairs(rows):
        result = {}
        for key, value in rows:
            if key in result:
                raise ValueError('Duplicate JSON field')
            result[key] = value
        return result
    try:
        return json.loads(raw.decode('utf-8'), object_pairs_hook=pairs,
                          parse_constant=lambda value: (_ for _ in ()).throw(
                              ValueError('Non-finite JSON number')))
    except (UnicodeError, RecursionError) as error:
        raise ValueError('Invalid bounded JSON document') from error


def _span(raw, offset, size, label):
    if (type(offset) is not int or type(size) is not int or offset < 0 or
            size < 0 or offset > len(raw) or size > len(raw) - offset):
        raise ValueError('Truncated or overflowing ' + label)
    return raw[offset:offset + size]


class _PE:
    def __init__(self, raw):
        if type(raw) is not bytes or not 64 <= len(raw) <= MAX_FILE or raw[:2] != b'MZ':
            raise ValueError('Bounded actual PE bytes required')
        self.raw = raw
        self._strings, self._string_bytes = {}, 0
        nt = struct.unpack_from('<I', raw, 60)[0]
        _span(raw, nt, 24, 'PE header')
        if nt < 64 or raw[nt:nt + 4] != b'PE\0\0':
            raise ValueError('Invalid PE signature')
        machine, count, _time, _symbols, _nsyms, optional_size, flags = struct.unpack_from('<HHIIIHH', raw, nt + 4)
        if machine not in (0x14c, 0x8664) or not flags & 2 or not 1 <= count <= 96:
            _missing('SOURCE', 'image.machine', 'only executable i386/AMD64 PE profiles implemented')
        self.machine = 'x86_64' if machine == 0x8664 else 'i386'
        self.dll = bool(flags & 0x2000)
        optional = nt + 24
        if optional_size < 2:
            raise ValueError('Truncated PE optional header')
        _span(raw, optional, optional_size, 'optional header')
        magic = struct.unpack_from('<H', raw, optional)[0]
        if (magic, machine) not in ((0x10b, 0x14c), (0x20b, 0x8664)):
            raise ValueError('PE magic/machine mismatch')
        self.width = 8 if magic == 0x20b else 4
        base = 112 if self.width == 8 else 96
        if not base + 15 * 8 <= optional_size <= 4096:
            raise ValueError('Incomplete PE optional header')
        count_dirs = struct.unpack_from('<I', raw, optional + base - 4)[0]
        if not 15 <= count_dirs <= 16 or base + count_dirs * 8 > optional_size:
            raise ValueError('Incomplete PE data-directory shape')
        headers = struct.unpack_from('<I', raw, optional + 60)[0]
        image = struct.unpack_from('<I', raw, optional + 56)[0]
        section_align, file_align = struct.unpack_from('<II', raw, optional + 32)
        if (not 4096 <= section_align <= 1 << 20 or section_align & (section_align - 1) or
                not 512 <= file_align <= 65536 or file_align & (file_align - 1) or
                file_align > section_align or headers % file_align or
                image <= headers or image % section_align):
            raise ValueError('Invalid PE image alignment/size')
        table = optional + optional_size
        if not table + count * 40 <= headers <= len(raw):
            raise ValueError('Invalid PE headers size')
        self.sections = []
        for i in range(count):
            virtual, address, size, offset = struct.unpack_from('<IIII', raw, table + i * 40 + 8)
            extent = max(virtual, size)
            if (not extent or address < headers or address % section_align or
                    address + extent > image or size and
                    (offset < headers or offset % file_align or size % file_align)):
                raise ValueError('Invalid PE section')
            _span(raw, offset, size, 'PE section bytes')
            for prior, extent0, offset0, size0 in self.sections:
                if (address < prior + extent0 and prior < address + extent or
                        size and size0 and offset < offset0 + size0 and offset0 < offset + size):
                    raise ValueError('Overlapping PE sections')
            self.sections.append((address, extent, offset, size))
        self.directories = [struct.unpack_from('<II', raw, optional + base + i * 8)
                            for i in range(count_dirs)]
        for i, (address, size) in enumerate(self.directories):
            if bool(address) != bool(size):
                raise ValueError('Incomplete PE directory')
            if address:
                if i == 4:  # Authenticode is a file offset, never an RVA.
                    if address % 8:
                        raise ValueError('Unaligned PE certificate table')
                    _span(raw, address, size, 'PE certificate table')
                else:
                    self.rva(address, size)
        if any(self.directory(i) != (0, 0) for i in (7, 8, 11, 13, 15)):
            _missing('SOURCE', 'image.directories', 'architecture/global/bound/delay/reserved directory policy')

    def directory(self, index):
        return self.directories[index] if index < len(self.directories) else (0, 0)

    def rva(self, address, size):
        matches = [(offset + address - base, raw_size - (address - base))
                   for base, _extent, offset, raw_size in self.sections
                   if base <= address and address - base <= raw_size and
                   size <= raw_size - (address - base)]
        if len(matches) != 1:
            raise ValueError('Unbacked or ambiguous PE RVA')
        return matches[0]

    def string(self, address, maximum=1024):
        key = (address, maximum)
        if key in self._strings:
            return self._strings[key]
        at, available = self.rva(address, 1)
        end = self.raw.find(b'\0', at, at + min(available, maximum + 1))
        if end <= at:
            raise ValueError('Empty/unterminated PE string')
        self._string_bytes += end - at
        if len(self._strings) >= MAX_ROWS or self._string_bytes > MAX_DERIVED:
            _missing('DATA', 'image.strings.work_bound', 'unique PE strings exceed finite 8-MiB domain')
        try:
            result = self.raw[at:end].decode('ascii')
        except UnicodeError as error:
            raise ValueError('Non-ASCII PE string') from error
        self._strings[key] = result
        return result

    def imports(self):
        result = []
        address, size = self.directory(1)
        if not address:
            return result
        at, _ = self.rva(address, size)
        if size < 20:
            raise ValueError('Truncated PE imports')
        terminated = False
        symbols = 0
        derived_bytes = 0
        for offset in range(0, size - 19, 20):
            lookup, stamp, chain, name, first = struct.unpack_from('<IIIII', self.raw, at + offset)
            if not any((lookup, stamp, chain, name, first)):
                if any(self.raw[at + offset + 20:at + size]):
                    raise ValueError('Data after PE import terminator')
                terminated = True; break
            if stamp or chain or not name or not first or len(result) >= 4096:
                raise ValueError('Unsupported/incomplete PE import descriptor')
            library = self.string(name, 128)
            if (not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,123}\.dll', library, re.I) or
                    library.casefold() in [row['name'] for row in result]):
                raise ValueError('Invalid/aliased PE imported DLL')
            imported = []
            for i in range(65536):
                entry, _ = self.rva((lookup or first) + i * self.width, self.width)
                self.rva(first + i * self.width, self.width)
                value = int.from_bytes(self.raw[entry:entry + self.width], 'little')
                if not value:
                    break
                symbols += 1
                if symbols > 65536:
                    raise ValueError('PE import symbol bound exceeded')
                high = 1 << (8 * self.width - 1)
                if value & high:
                    if value & ~(high | 0xffff) or not value & 0xffff:
                        raise ValueError('Invalid imported ordinal')
                    imported.append({'ordinal': value & 0xffff})
                    derived_bytes += 32
                else:
                    if value > 0xffffffff:
                        raise ValueError('Invalid import-name RVA')
                    self.rva(value, 2)
                    name = self.string(value + 2, 4096)
                    derived_bytes += len(name) + 32
                    imported.append({'name': name})
                if derived_bytes > MAX_DERIVED:
                    _missing('DATA', 'image.imports.work_bound', 'derived import symbols exceed finite 8-MiB domain')
            else:
                raise ValueError('Unterminated PE import thunk')
            result.append({'name': library.casefold(), 'symbols': imported})
        if not terminated:
            raise ValueError('Unterminated PE import descriptor array')
        return result


# ECMA-335 physical table layout is a provisional source assumption here. Every
# present table is laid out; unsupported schemas never silently shift later rows.
_CODED = {
    'TypeDefOrRef': (2, {0: 2, 1: 1, 2: 27}),
    'HasConstant': (2, {0: 4, 1: 8, 2: 23}),
    'HasCustomAttribute': (5, dict(enumerate((6, 4, 1, 2, 8, 9, 10, 0, 14, 23, 20, 17, 26, 27, 32, 35, 38, 39, 40, 42, 44, 43)))),
    'HasFieldMarshal': (1, {0: 4, 1: 8}),
    'HasDeclSecurity': (2, {0: 2, 1: 6, 2: 32}),
    'MemberRefParent': (3, {0: 2, 1: 1, 2: 26, 3: 6, 4: 27}),
    'HasSemantics': (1, {0: 20, 1: 23}),
    'MethodDefOrRef': (1, {0: 6, 1: 10}),
    'MemberForwarded': (1, {0: 4, 1: 6}),
    'Implementation': (2, {0: 38, 1: 35, 2: 39}),
    'CustomAttributeType': (3, {2: 6, 3: 10}),
    'ResolutionScope': (2, {0: 0, 1: 26, 2: 35, 3: 1}),
    'TypeOrMethodDef': (1, {0: 2, 1: 6}),
}
_TABLES = {
    0: ('u2', 'str', 'guid', 'guid', 'guid'),
    1: ('ResolutionScope', 'str', 'str'),
    2: ('u4', 'str', 'str', 'TypeDefOrRef', 'l4', 'l6'),
    3: ('t4',), 4: ('u2', 'str', 'blob'), 5: ('t6',),
    6: ('u4', 'u2', 'u2', 'str', 'blob', 'l8'),
    7: ('t8',), 8: ('u2', 'u2', 'str'), 9: ('t2', 'TypeDefOrRef'),
    10: ('MemberRefParent', 'str', 'blob'),
    11: ('u2', 'HasConstant', 'blob'),
    12: ('HasCustomAttribute', 'CustomAttributeType', 'blob'),
    13: ('HasFieldMarshal', 'blob'), 14: ('u2', 'HasDeclSecurity', 'blob'),
    15: ('u2', 'u4', 't2'), 16: ('u4', 't4'), 17: ('blob',),
    18: ('t2', 'l20'), 19: ('t20',), 20: ('u2', 'str', 'TypeDefOrRef'),
    21: ('t2', 'l23'), 22: ('t23',), 23: ('u2', 'str', 'blob'),
    24: ('u2', 't6', 'HasSemantics'),
    25: ('t2', 'MethodDefOrRef', 'MethodDefOrRef'), 26: ('str',),
    27: ('blob',), 28: ('u2', 'MemberForwarded', 'str', 't26'),
    29: ('u4', 't4'), 30: ('u4', 'u4'), 31: ('u4',),
    32: ('u4', 'u2', 'u2', 'u2', 'u2', 'u4', 'blob', 'str', 'str'),
    33: ('u4',), 34: ('u4', 'u4', 'u4'),
    35: ('u2', 'u2', 'u2', 'u2', 'u4', 'blob', 'str', 'str', 'blob'),
    36: ('u4', 't35'), 37: ('u4', 'u4', 'u4', 't35'),
    38: ('u4', 'str', 'blob'),
    39: ('u4', 'u4', 'str', 'str', 'Implementation'),
    40: ('u4', 'u4', 'str', 'Implementation'), 41: ('t2', 't2'),
    42: ('u2', 'u2', 'TypeOrMethodDef', 'str'),
    43: ('MethodDefOrRef', 'blob'), 44: ('t42', 'TypeDefOrRef'),
}

# Columns with mandatory non-null table/coded/heap references. List starts are
# separately checked against count+1. Optional namespace/culture/key fields and
# embedded-resource Implementation remain nullable.
_REQUIRED = {
    0: (1, 2), 1: (0, 1), 2: (1,), 4: (1, 2), 6: (3, 4),
    9: (0, 1), 10: (0, 1, 2), 11: (1, 2), 12: (0, 1, 2),
    13: (0, 1), 14: (1, 2), 15: (2,), 16: (1,), 17: (0,),
    18: (0,), 20: (1, 2), 21: (0,), 23: (1, 2), 24: (1, 2),
    25: (0, 1, 2), 26: (0,), 27: (0,), 28: (1, 2, 3), 29: (1,),
    32: (7,), 35: (6,), 36: (1,), 37: (3,), 38: (1, 2),
    39: (2, 4), 40: (2,), 41: (0, 1), 42: (2,), 43: (0, 1),
    44: (0, 1),
}


class _Metadata:
    def __init__(self, raw):
        if not 32 <= len(raw) <= MAX_METADATA:
            raise ValueError('Bounded CLR metadata required')
        self.raw = raw
        signature, major, minor, reserved, version_size = struct.unpack_from('<IHHII', raw, 0)
        if signature != 0x424a5342 or reserved or (major, minor) != (1, 1):
            _missing('SOURCE', 'metadata.root', 'only BSJB metadata root version 1.1 implemented')
        if not 4 <= version_size <= 256 or version_size % 4:
            raise ValueError('Invalid metadata version size')
        version = _span(raw, 16, version_size, 'metadata version')
        end = version.find(b'\0')
        if end <= 0 or any(version[end:]):
            raise ValueError('Invalid metadata version padding')
        try:
            self.version = version[:end].decode('ascii')
        except UnicodeError as error:
            raise ValueError('Invalid metadata version') from error
        at = 16 + version_size
        _span(raw, at, 4, 'metadata stream count')
        flags, count = struct.unpack_from('<HH', raw, at); at += 4
        if flags or not 4 <= count <= 8:
            raise ValueError('Invalid metadata stream flags/count')
        streams = {}
        for _ in range(count):
            _span(raw, at, 9, 'metadata stream header')
            offset, size = struct.unpack_from('<II', raw, at); at += 8
            end = raw.find(b'\0', at, min(len(raw), at + 33))
            if end <= at:
                raise ValueError('Unterminated metadata stream name')
            try:
                name = raw[at:end].decode('ascii')
            except UnicodeError as error:
                raise ValueError('Invalid metadata stream name') from error
            next_at = (end + 4) & ~3
            if any(_span(raw, end, next_at - end, 'stream name padding')):
                raise ValueError('Nonzero metadata stream name padding')
            at = next_at
            if name not in ('#~', '#Strings', '#Blob', '#GUID', '#US'):
                _missing('SOURCE', 'metadata.stream.' + name, 'only compressed #~ and standard heaps implemented')
            if name in streams or offset % 4:
                raise ValueError('Duplicate/unaligned metadata stream')
            _span(raw, offset, size, 'metadata stream body')
            streams[name] = (offset, size)
        if not {'#~', '#Strings', '#Blob', '#GUID'} <= set(streams):
            raise ValueError('Missing required CLR metadata streams')
        for name, (offset, size) in streams.items():
            if offset < at:
                raise ValueError('Metadata stream overlaps its headers')
            for other, (offset0, size0) in streams.items():
                if name != other and size and size0 and offset < offset0 + size0 and offset0 < offset + size:
                    raise ValueError('Overlapping metadata streams')
        self.heaps = {name: raw[offset:offset + size] for name, (offset, size) in streams.items()}
        self._strings, self._blob_ranges, self._blobs, self._key_tokens = {}, {}, {}, {}
        self._decoded_size = self._copied_blob_size = 0
        if (not self.heaps['#Strings'] or self.heaps['#Strings'][0] or
                not self.heaps['#Blob'] or self.heaps['#Blob'][0] or
                len(self.heaps['#GUID']) % 16):
            raise ValueError('Invalid CLR heap boundary')
        tables = self.heaps['#~']
        _span(tables, 0, 24, 'metadata tables header')
        reserved, major, minor, heap_flags, reserved1, valid, sorted_mask = struct.unpack_from('<IBBBBQQ', tables, 0)
        if reserved or (major, minor, reserved1) != (2, 0, 1) or heap_flags & ~7:
            _missing('SOURCE', 'metadata.tables.header', 'only compressed table version 2.0 and three heap-width bits implemented')
        if valid >> 45 or sorted_mask >> 45:
            raise ValueError('Unknown CLR metadata table bits')
        self.counts = {}
        at = 24
        for table in range(45):
            if valid & (1 << table):
                _span(tables, at, 4, 'metadata row count')
                rows = struct.unpack_from('<I', tables, at)[0]; at += 4
                _integer(rows, 0, MAX_ROWS, 'metadata rows')
                self.counts[table] = rows
        if sum(self.counts.values()) > MAX_ROWS:
            raise ValueError('Metadata aggregate row bound exceeded')
        if any(self.counts.get(table, 0) for table in (3, 5, 7, 19, 22, 30, 31)):
            _missing('SOURCE', 'metadata.tables.pointer-or-enc', 'pointer/edit-and-continue table semantics')
        for i, name in enumerate(('#Strings', '#GUID', '#Blob')):
            if len(self.heaps[name]) >= 65536 and not heap_flags & (1 << i):
                raise ValueError('CLR heap too large for declared index width')
        def width(column):
            if column in ('u2', 'u4'):
                return int(column[1])
            if column in ('str', 'guid', 'blob'):
                return 4 if heap_flags & (1 << ('str', 'guid', 'blob').index(column)) else 2
            if column[0] in ('t', 'l') and column[1:].isdigit():
                return 4 if self.counts.get(int(column[1:]), 0) >= 65536 else 2
            bits, tags = _CODED[column]
            return 4 if max((self.counts.get(t, 0) for t in tags.values()), default=0) >= (1 << (16 - bits)) else 2
        self.rows = {}
        for table in range(45):
            columns = _TABLES[table]
            widths = [width(column) for column in columns]
            row_size = sum(widths)
            _span(tables, at, row_size * self.counts.get(table, 0), 'metadata table rows')
            values = []
            for _ in range(self.counts.get(table, 0)):
                row = []
                for column, size in zip(columns, widths):
                    value = int.from_bytes(tables[at:at + size], 'little'); at += size
                    self.validate_index(column, value)
                    row.append(value)
                if any(not row[index] for index in _REQUIRED.get(table, ())):
                    raise ValueError('Null mandatory CLR metadata reference')
                values.append(row)
            self.rows[table] = values
        if any(tables[at:]):
            raise ValueError('Nonzero bytes after complete metadata tables')
        for owner, column, target in ((2, 4, 4), (2, 5, 6), (6, 5, 8),
                                      (18, 1, 20), (21, 1, 23)):
            starts = [row[column] for row in self.rows[owner]]
            if (not starts and self.counts.get(target, 0) or
                    starts and (starts[0] != 1 or starts != sorted(starts))):
                raise ValueError('Invalid complete CLR list ownership partition')
        for table, column in ((18, 0), (21, 0), (29, 1)):
            owners = [row[column] for row in self.rows[table]]
            if len(owners) != len(set(owners)):
                raise ValueError('Repeated CLR metadata owner')

    def validate_index(self, column, value):
        if column == 'str': self.string(value)
        elif column == 'blob': self.blob_range(value)
        elif column == 'guid':
            if value and value * 16 > len(self.heaps['#GUID']):
                raise ValueError('Invalid metadata GUID index')
        elif column[0] in ('t', 'l') and column[1:].isdigit():
            maximum = self.counts.get(int(column[1:]), 0) + (column[0] == 'l')
            if value > maximum or column[0] == 'l' and not value:
                raise ValueError('Invalid metadata table/list index')
        elif column in _CODED and value:
            bits, tags = _CODED[column]
            tag, index = value & ((1 << bits) - 1), value >> bits
            if tag not in tags or not 1 <= index <= self.counts.get(tags[tag], 0):
                raise ValueError('Invalid metadata coded index')

    def string(self, index):
        if index in self._strings:
            return self._strings[index]
        heap = self.heaps['#Strings']
        if index >= len(heap):
            raise ValueError('Out-of-range metadata string index')
        end = heap.find(b'\0', index, min(len(heap), index + 65537))
        if end < 0:
            raise ValueError('Unterminated/big metadata string')
        self._decoded_size += end - index
        if len(self._strings) >= MAX_ROWS or self._decoded_size > MAX_DERIVED:
            _missing('DATA', 'metadata.strings.work_bound', 'unique decoded string span exceeds finite 8-MiB domain')
        try:
            value = heap[index:end].decode('utf-8')
        except UnicodeError as error:
            raise ValueError('Invalid metadata UTF-8 string') from error
        self._strings[index] = value
        return value

    def blob_range(self, index):
        if not index:
            return 0, 0
        if index in self._blob_ranges:
            return self._blob_ranges[index]
        if len(self._blob_ranges) >= MAX_ROWS:
            _missing('DATA', 'metadata.blobs.work_bound', 'too many unique blob references')
        heap = self.heaps['#Blob']
        _span(heap, index, 1, 'metadata blob prefix')
        first = heap[index]
        if first < 0x80:
            size, prefix = first, 1
        elif first < 0xc0:
            _span(heap, index, 2, 'metadata blob prefix')
            size, prefix = ((first & 0x3f) << 8) | heap[index + 1], 2
            if size < 0x80: raise ValueError('Noncanonical metadata blob size')
        elif first < 0xe0:
            _span(heap, index, 4, 'metadata blob prefix')
            size, prefix = ((first & 0x1f) << 24) | int.from_bytes(heap[index + 1:index + 4], 'big'), 4
            if size < 0x4000: raise ValueError('Noncanonical metadata blob size')
        else:
            raise ValueError('Reserved metadata blob size encoding')
        if size > len(heap) - index - prefix:
            raise ValueError('Truncated metadata blob body')
        result = (index + prefix, size)
        self._blob_ranges[index] = result
        return result

    def blob(self, index):
        if index not in self._blobs:
            offset, size = self.blob_range(index)
            self._copied_blob_size += size
            if size > MAX_XML or self._copied_blob_size > MAX_DERIVED:
                _missing('DATA', 'metadata.blob.work_bound', 'needed blob exceeds 1-MiB or aggregate 8-MiB domain')
            self._blobs[index] = self.heaps['#Blob'][offset:offset + size]
        return self._blobs[index]

    def identity(self, row, reference):
        if reference:
            version, flags, key, name, culture = row[:4], row[4], row[5], row[6], row[7]
        else:
            version, flags, key, name, culture = row[1:5], row[5], row[6], row[7], row[8]
        if flags & ~1:
            _missing('SOURCE', 'metadata.assembly.flags', 'retargetable/content-type/processor assembly identities')
        key_index = key
        key = self.blob(key_index)
        if flags & 1:
            if not key:
                raise ValueError('Assembly public-key flag has no key')
            if key_index not in self._key_tokens:
                self._key_tokens[key_index] = hashlib.sha1(key).digest()[-8:][::-1].hex()
            token = self._key_tokens[key_index]
        else:
            if len(key) not in (0, 8) or not reference and key:
                raise ValueError('Invalid public-key token/full-key declaration')
            token = key.hex()
        name, culture = self.string(name), self.string(culture)
        if not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.-]{0,255}', name):
            raise ValueError('Invalid bounded assembly name')
        if culture and not re.fullmatch(r'[A-Za-z0-9-]{1,64}', culture):
            raise ValueError('Invalid assembly culture')
        return {'name': name, 'version': list(version), 'culture': culture,
                'public_key_token': token}


def inspect_managed_image(raw, expected_ref):
    """Derive bounded structural managed facts; no native/IL/loader authority."""
    expected_ref = _ref(expected_ref)
    if (type(raw) is not bytes or len(raw) != expected_ref['bytes'] or
            hashlib.sha256(raw).hexdigest() != expected_ref['sha256']):
        raise ValueError('Managed program/image reference differs from held bytes')
    pe = _PE(raw)
    address, size = pe.directory(14)
    if not address or size != 72:
        _missing('SOURCE', 'image.clr_header', 'exact 72-byte CLI header required')
    at, _ = pe.rva(address, size)
    cb, major, minor, metadata_address, metadata_size, flags, entry = struct.unpack_from('<IHHIIII', raw, at)
    if cb != 72 or (major, minor) != (2, 5):
        _missing('SOURCE', 'image.clr_header.version', 'CLI header/runtime profile 72/2.5 required')
    if not flags & 1 or flags & ~9:
        _missing('SOURCE', 'image.clr_flags', 'only ILONLY with optional strong-name bit; no required/preferred32 or native entry')
    if pe.directory(0) != (0, 0) or pe.directory(9) != (0, 0):
        _missing('SOURCE', 'image.native_exports_or_tls', 'managed exports/TLS runtime selection')
    for offset, label in ((40, 'code_manager'), (48, 'vtable_fixups'),
                          (56, 'export_jumps'), (64, 'managed_native_header')):
        if struct.unpack_from('<II', raw, at + offset) != (0, 0):
            _missing('SOURCE', 'image.clr_header.' + label, 'mixed/native/ReadyToRun support')
    for offset, label in ((24, 'resources'), (32, 'strong_name')):
        rva, count = struct.unpack_from('<II', raw, at + offset)
        if bool(rva) != bool(count): raise ValueError('Incomplete CLI ' + label)
        if rva: pe.rva(rva, count)
        if label == 'strong_name' and bool(flags & 8) != bool(rva):
            raise ValueError('Strong-name directory/flag mismatch')
    location, _ = pe.rva(metadata_address, metadata_size)
    metadata = _Metadata(_span(raw, location, metadata_size, 'CLR metadata'))
    if metadata.version != 'v4.0.30319':
        _missing('SOURCE', 'metadata.version', 'explicit .NET Framework v4 metadata profile required')
    if len(metadata.rows[0]) != 1 or len(metadata.rows[32]) != 1:
        _missing('SOURCE', 'metadata.module_or_assembly', 'exactly one Module and Assembly required')
    if any(metadata.rows[t] for t in (33, 34, 36, 37, 38, 39)):
        _missing('SOURCE', 'metadata.multifile_or_platform', 'File/ExportedType/assembly platform tables')
    if metadata.rows[41]:
        _missing('SOURCE', 'metadata.nested_types', 'nested task/type identity requires an explicit successor')
    if any(row[0] & 7 >= 2 for row in metadata.rows[2]):
        _missing('SOURCE', 'metadata.nested_visibility', 'nested TypeDef visibility is outside top-level identity domain')
    module = metadata.rows[0][0]
    if module[0] or not module[1] or not module[2] or module[3] or module[4]:
        raise ValueError('Invalid single-module generation/MVID')
    if (not metadata.rows[2] or metadata.string(metadata.rows[2][0][1]) != '<Module>' or
            metadata.rows[2][0][2] or metadata.rows[2][0][3]):
        raise ValueError('Required first <Module> TypeDef absent or malformed')
    if any(row[0] & 0x2000 for row in metadata.rows[4]):
        _missing('SOURCE', 'metadata.field.pinvoke', 'field P/Invoke is outside MethodDef-only domain')
    for row in metadata.rows[40]:
        if row[3]:
            _missing('SOURCE', 'metadata.resource.implementation', 'external manifest resource')
        resources_address, resources_size = struct.unpack_from('<II', raw, at + 24)
        if not resources_address or row[0] > resources_size - 4:
            raise ValueError('Unbacked embedded managed resource')
        resource_at, _ = pe.rva(resources_address + row[0], 4)
        payload = struct.unpack_from('<I', raw, resource_at)[0]
        if payload > resources_size - row[0] - 4:
            raise ValueError('Embedded managed resource exceeds CLI resources')
    for row in metadata.rows[1]:
        if row[0] and row[0] & 3 == 1:
            _missing('SOURCE', 'metadata.typeref.module_scope', 'external managed module TypeRef')
    if any(row[0] and row[0] & 7 == 2 for row in metadata.rows[10]):
        _missing('SOURCE', 'metadata.memberref.module_scope', 'external managed module MemberRef')
    if entry:
        if entry >> 24 != 6 or not 1 <= entry & 0xffffff <= len(metadata.rows[6]) or pe.dll:
            raise ValueError('Invalid managed entrypoint token')
        entry_row = metadata.rows[6][(entry & 0xffffff) - 1]
        if not entry_row[0] or not entry_row[2] & 0x10 or entry_row[2] & (0x400 | 0x2000):
            raise ValueError('Managed entrypoint must have a static IL body')
    elif not pe.dll:
        raise ValueError('Managed executable lacks entrypoint')
    pinvoke_methods = set()
    pinvokes = []
    for row in metadata.rows[28]:
        mapping, member, import_name, scope = row
        if (mapping & ~0x3777 or mapping & 0x700 not in (0x100, 0x200, 0x300, 0x400, 0x500) or
                mapping & 0x30 == 0x30 or mapping & 0x3000 == 0x3000 or not mapping & 1 or
                not member or member & 1 != 1 or not scope):
            _missing('SOURCE', 'metadata.implmap.flags_or_member', 'only explicit NoMangle named MethodDef P/Invoke with finite charset/calling convention implemented')
        name = metadata.string(import_name)
        if not re.fullmatch(r'[A-Za-z_?][A-Za-z0-9_?@$.-]{0,1023}', name):
            _missing('SOURCE', 'metadata.implmap.name', 'ordinal/decorated unsupported import name')
        module_name = metadata.string(metadata.rows[26][scope - 1][0])
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,123}\.dll', module_name, re.I):
            _missing('SOURCE', 'metadata.moduleref.name', 'explicit DLL basename required')
        method = member >> 1
        if method in pinvoke_methods: raise ValueError('Duplicate P/Invoke method mapping')
        pinvoke_methods.add(method)
        pinvokes.append({'module': module_name.casefold(), 'name': name,
                         'mapping_flags': mapping, 'method_row': method})
    if len({row['module'] for row in pinvokes}) != len(metadata.rows[26]):
        _missing('SOURCE', 'metadata.moduleref.unresolved', 'unused/repeated/external module references')
    for index, row in enumerate(metadata.rows[6], 1):
        rva, impl, method_flags, _name, signature, _param = row
        if method_flags & 8:
            _missing('SOURCE', 'metadata.method.unmanaged_export', 'unmanaged export methods unsupported')
        if impl & ~0x108 or impl & 0x1000:
            _missing('SOURCE', 'metadata.method.implflags', 'native/runtime/internal-call/unmanaged method implementation')
        if not metadata.blob(signature): raise ValueError('Method signature missing')
        if bool(method_flags & 0x2000) != (index in pinvoke_methods):
            raise ValueError('P/Invoke method flag/map mismatch')
        if rva:
            pe.rva(rva, 1)
            if method_flags & (0x400 | 0x2000): raise ValueError('Abstract/PInvoke method has IL RVA')
        elif not method_flags & (0x400 | 0x2000):
            raise ValueError('Managed method body absent')
    identities = [metadata.identity(row, True) for row in metadata.rows[35]]
    if len({_canonical(identity) for identity in identities}) != len(identities):
        raise ValueError('Repeated exact assembly reference')
    types, type_bytes = [], 0
    for row in metadata.rows[2]:
        namespace, name = metadata.string(row[2]), metadata.string(row[1])
        type_bytes += len(namespace.encode('utf-8')) + len(name.encode('utf-8')) + 1
        if type_bytes > MAX_DERIVED:
            _missing('DATA', 'metadata.types.work_bound', 'derived type identities exceed 8-MiB domain')
        types.append(namespace + ('.' if namespace else '') + name)
    if len(types) != len(set(types)):
        raise ValueError('Duplicate complete top-level TypeDef identity')
    facts = {'scope': SCOPE, 'image': copy.deepcopy(expected_ref),
            'machine': pe.machine, 'format': 'pe32plus' if pe.width == 8 else 'pe32',
            'dll': pe.dll, 'clr_version': [major, minor], 'clr_flags': flags,
            'metadata_version': metadata.version, 'module': metadata.string(module[1]),
            'assembly': metadata.identity(metadata.rows[32][0], False),
            'assembly_references': identities, 'pinvokes': pinvokes,
            'native_imports': pe.imports(), 'types': types,
            'table_counts': {str(t): n for t, n in metadata.counts.items()},
            'metadata_sha256': hashlib.sha256(metadata.raw).hexdigest(),
            'native_admission': False, 'il_verified': False,
            'execution_closure_proven': False}
    if len(_canonical(facts)) > MAX_DERIVED:
        _missing('DATA', 'metadata.facts.work_bound', 'derived image facts exceed 8-MiB domain')
    return facts


def _identity(value):
    _keys(value, ('name', 'version', 'culture', 'public_key_token'), 'assembly identity')
    if not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.-]{0,255}', _text(value['name'], 'assembly name', 256)):
        raise ValueError('Invalid assembly name')
    if type(value['version']) is not list or len(value['version']) != 4:
        raise ValueError('Four exact assembly version numbers required')
    for number in value['version']: _integer(number, 0, 65535, 'assembly version')
    if type(value['culture']) is not str or value['culture'] and not re.fullmatch('[A-Za-z0-9-]{1,64}', value['culture']):
        raise ValueError('Invalid assembly culture')
    if type(value['public_key_token']) is not str or not re.fullmatch('(?:[0-9a-f]{16})?', value['public_key_token']):
        raise ValueError('Invalid assembly public-key token')
    return value


def _list(value, label, maximum=MAX_FILES):
    if type(value) is not list or len(value) > maximum:
        raise ValueError('Bounded exact ' + label + ' list required')
    return value


def _profile(value):
    _keys(value, ('schema_version', 'kind', 'format_profile', 'program', 'host_bundle',
                  'managed_runtime', 'native_runtime_roots', 'assemblies',
                  'native_images', 'msbuild'), 'managed runtime profile')
    if (type(value['schema_version']) is not int or value['schema_version'] != 1 or
            value['kind'] != PROFILE_KIND or
            value['format_profile'] != 'provisional-cli-ecma335-layout-v1'):
        _missing('SOURCE', 'profile.kind_or_format', 'exact private schema-1 provisional CLI profile required')
    _ref(value['program'], 'MSBuild program')
    if value['program']['path'].rsplit('/', 1)[-1] != 'MSBuild.exe':
        raise ValueError('Exact selected MSBuild.exe image required')
    host = _keys(value['host_bundle'], ('root', 'inventory', 'subject_sha256'), 'host bundle')
    _path(host['root']); _metadata_ref(host['inventory']); _pin(host['subject_sha256'])
    runtime = _keys(value['managed_runtime'], ('family', 'root', 'configuration',
                    'machine_configuration', 'clr_image', 'clr_version',
                    'framework_sku', 'metadata_version'), 'managed runtime')
    if (runtime['family'] != 'net-framework-v4' or runtime['clr_version'] != 'v4.0' or
            runtime['metadata_version'] != 'v4.0.30319'):
        _missing('SOURCE', 'profile.managed_runtime.family', 'only explicit .NET Framework v4 profile implemented')
    _path(runtime['root'])
    if not re.fullmatch(r'\.NETFramework,Version=v4\.[0-9]+(?:\.[0-9]+)?', _text(runtime['framework_sku'], 'framework SKU', 128)):
        raise ValueError('Explicit .NET Framework 4 SKU required; CLR v4.0 is not a release')
    for key in ('configuration', 'machine_configuration', 'clr_image'): _ref(runtime[key])
    if runtime['configuration']['path'] != value['program']['path'] + '.config':
        raise ValueError('Original executable configuration path differs')
    if (not runtime['machine_configuration']['path'].endswith('/machine.config') or
            not _within(runtime['machine_configuration']['path'], runtime['root']) or
            runtime['clr_image']['path'] != runtime['root'] + '/clr.dll'):
        raise ValueError('Exact selected runtime CLR/machine configuration relationship required')
    roots = _list(value['native_runtime_roots'], 'native roots', 64)
    for root in [runtime['root']] + roots:
        _path(root)
        if not (root == host['root'] or _within(root, host['root'])):
            _missing('DATA', 'profile.runtime_root', 'outside single host_generators bundle; Root/native-parent typed-root proposal required: ' + root)
    if not roots or roots != sorted(set(roots)):
        raise ValueError('Unique sorted explicit native roots required')
    for row in _list(value['assemblies'], 'managed assemblies'):
        _keys(row, ('image', 'identity', 'role', 'bindings'), 'managed assembly')
        _ref(row['image']); _identity(row['identity'])
        if row['role'] not in ('program', 'task', 'support', 'runtime'):
            raise ValueError('Exact selected managed assembly role required')
        for binding in _list(row['bindings'], 'assembly bindings'):
            _keys(binding, ('reference', 'image'), 'assembly binding')
            _identity(binding['reference']); _ref(binding['image'])
    for row in _list(value['native_images'], 'native images'):
        _keys(row, ('image', 'imports'), 'native image')
        _ref(row['image'])
        for binding in _list(row['imports'], 'native import bindings'):
            _keys(binding, ('name', 'image'), 'native import binding')
            _ref(binding['image'])
            if (type(binding['name']) is not str or
                    not re.fullmatch(r'[a-z0-9][a-z0-9_.-]{0,123}\.dll', binding['name'])):
                raise ValueError('Exact casefolded native DLL basename required')
    msbuild = _keys(value['msbuild'], ('entry_project', 'projects', 'tasks'), 'MSBuild closure')
    _ref(msbuild['entry_project'])
    for ref in _list(msbuild['projects'], 'MSBuild projects'): _ref(ref)
    for row in _list(msbuild['tasks'], 'MSBuild tasks'):
        _keys(row, ('name', 'assembly', 'source'), 'MSBuild task')
        if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_.]{0,255}', _text(row['name'], 'task name', 256)):
            raise ValueError('Literal full task name required')
        _ref(row['assembly']); _ref(row['source'])
    return value


def parse_runtime_profile(raw, pin):
    """Parse a pinned closed declaration, retaining no caller-owned structures."""
    _pin(pin)
    if type(raw) is not bytes or hashlib.sha256(raw).hexdigest() != pin:
        raise ValueError('Original managed runtime profile pin differs')
    value = _json(raw, 2 * 1024 * 1024)
    def bounded(item, depth=0):
        if depth > 64: raise ValueError('Managed profile nesting bound exceeded')
        if type(item) is dict:
            if len(item) > MAX_FILES: raise ValueError('Profile field bound exceeded')
            for key, nested in item.items():
                if type(key) is not str: raise ValueError('String JSON keys required')
                bounded(nested, depth + 1)
        elif type(item) is list:
            if len(item) > MAX_FILES: raise ValueError('Profile list bound exceeded')
            for nested in item: bounded(nested, depth + 1)
        elif type(item) is str:
            if len(item) > 4096: raise ValueError('Profile string bound exceeded')
        elif type(item) not in (int, bool, type(None)):
            raise ValueError('Profile floats/unknown values unsupported')
    bounded(value)
    return copy.deepcopy(_profile(value))


def _xml(raw, label):
    if type(raw) is not bytes or not 1 <= len(raw) <= MAX_XML:
        _missing('DATA', label, 'selected XML exceeds finite 1-MiB domain')
    # Only UTF-8 XML; forbid all DTD/entity declarations before parser expansion.
    try:
        text = raw.decode('utf-8')
    except UnicodeError as error:
        raise ValueError('Only original UTF-8 XML is implemented') from error
    if '<!DOCTYPE' in text.upper() or '<!ENTITY' in text.upper() or '\0' in text:
        raise ValueError('XML DTD/entity/NUL prohibited')
    if re.match(r'\s*<\?xml[^?]*encoding\s*=\s*[\'"](?!utf-8[\'"])', text, re.I):
        raise ValueError('Unsupported XML encoding declaration')
    # Pull events bound depth/node count during construction rather than after.
    parser = ET.XMLPullParser(('start', 'end'))
    depth = count = 0
    root = None
    try:
        for offset in range(0, len(text), 4096):
            parser.feed(text[offset:offset + 4096])
            for event, element in parser.read_events():
                if event == 'start':
                    depth += 1; count += 1
                    if root is None: root = element
                    if depth > MAX_XML_DEPTH or count > MAX_XML_NODES or len(element.attrib) > 64:
                        raise ValueError('XML finite depth/node/attribute bound exceeded')
                    for key, val in element.attrib.items():
                        if len(key) > 256 or len(val) > 4096:
                            raise ValueError('XML attribute bound exceeded')
                else: depth -= 1
        parser.close()
    except ET.ParseError as error:
        raise ValueError('Malformed original XML') from error
    if root is None or depth:
        raise ValueError('Incomplete XML document')
    for element in root.iter():
        if element.tail and element.tail.strip() or element.text and element.text.strip():
            _missing('SOURCE', label + '.text', 'only structural literal XML without text content implemented')
    return root


def _attrs(element, allowed, required, field):
    if not set(required) <= set(element.attrib) <= set(allowed):
        _missing('SOURCE', field, 'unsupported XML attributes: ' + ','.join(sorted(set(element.attrib) ^ set(required))))


def _literal(value, field):
    _text(value, field)
    if any(c in value for c in '$@%*?') or '$(' in value or '@(' in value or '%(' in value:
        _missing('SOURCE', field, 'property/item/metadata expansion, wildcard or MSBuild escaping')
    return value


def _resolve_literal(source, value, root, field):
    value = _literal(value, field)
    try:
        if re.match(r'^[A-Z]:/', value):
            result = _path(value)
        else:
            _relative(value)
            result = _path(source.rsplit('/', 1)[0] + '/' + value)
    except ValueError as error:
        _missing('SOURCE', field, 'noncanonical/aliased literal path: ' + str(error))
    if not _within(result, root):
        _missing('DATA', field, 'outside held host bundle; typed-root proposal required: ' + result)
    return result


def _runtime_configuration(profile, held):
    runtime = profile['managed_runtime']
    root = _xml(held[runtime['configuration']['path']], 'runtime.configuration')
    if root.tag != 'configuration' or root.attrib:
        _missing('SOURCE', 'runtime.configuration.root', 'literal configuration with no configSource/namespace')
    if len(root) != 1 or root[0].tag != 'startup' or root[0].attrib:
        _missing('SOURCE', 'runtime.configuration.startup', 'one explicit startup; binding/probing/publisher/legacy policy unsupported')
    startup = root[0]
    if len(startup) != 1 or startup[0].tag != 'supportedRuntime' or len(startup[0]):
        _missing('SOURCE', 'runtime.configuration.supportedRuntime', 'one exact CLR runtime, no fallback/requiredRuntime')
    _attrs(startup[0], ('version', 'sku'), ('version', 'sku'), 'runtime.configuration.supportedRuntime')
    if startup[0].attrib != {'version': runtime['clr_version'], 'sku': runtime['framework_sku']}:
        raise ValueError('Original runtime selection differs from declared version/SKU')
    machine = _xml(held[runtime['machine_configuration']['path']], 'runtime.machine_configuration')
    if machine.tag != 'configuration' or machine.attrib or len(machine):
        _missing('SOURCE', 'runtime.machine_configuration.policy', 'only explicit empty machine policy implemented; supplied policy needs exact source extension')


def _msbuild_closure(profile, held, managed):
    selected = profile['msbuild']
    projects = {row['path']: row for row in selected['projects']}
    if len(projects) != len(selected['projects']) or selected['entry_project'] != projects.get(selected['entry_project']['path']):
        raise ValueError('MSBuild entry/project references duplicate or differ')
    seen, active, tasks, targets, invocations = [], set(), [], set(), []
    task_names = set()
    root = profile['host_bundle']['root']
    def visit(path):
        if len(active) >= MAX_XML_DEPTH:
            _missing('DATA', 'msbuild.import.depth', 'literal import graph exceeds finite 64-level domain')
        if path in active:
            _missing('SOURCE', 'msbuild.import.cycle', 'literal import cycle at ' + path)
        if path in seen:
            _missing('SOURCE', 'msbuild.import.repeated', 'duplicate import evaluation/override semantics at ' + path)
        if path not in projects or path not in held:
            _missing('DATA', 'msbuild.import', 'missing exact selected project bytes: ' + path)
        if len(seen) >= MAX_FILES:
            raise ValueError('MSBuild project bound exceeded')
        active.add(path); seen.append(path)
        element = _xml(held[path], 'msbuild.project')
        ns = '{http://schemas.microsoft.com/developer/msbuild/2003}' if element.tag.startswith('{') else ''
        if element.tag != ns + 'Project':
            _missing('SOURCE', 'msbuild.project.namespace', 'exact MSBuild 2003 namespace or unqualified Project required')
        _attrs(element, (), (), 'msbuild.project.attributes')
        for child in element:
            if child.tag == ns + 'Import':
                _attrs(child, ('Project',), ('Project',), 'msbuild.import.attributes')
                if len(child): raise ValueError('Import may not have child nodes')
                visit(_resolve_literal(path, child.attrib['Project'], root, 'msbuild.import.Project'))
            elif child.tag == ns + 'UsingTask':
                _attrs(child, ('TaskName', 'AssemblyFile'), ('TaskName', 'AssemblyFile'), 'msbuild.task.attributes')
                if len(child): _missing('SOURCE', 'msbuild.task.factory', 'inline task/task factory')
                name = _literal(child.attrib['TaskName'], 'msbuild.task.TaskName')
                if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_.]{0,255}', name):
                    raise ValueError('Exact literal full task name required')
                if name.casefold() in task_names:
                    _missing('SOURCE', 'msbuild.task.duplicate', 'UsingTask precedence/override semantics')
                target = _resolve_literal(path, child.attrib['AssemblyFile'], root, 'msbuild.task.AssemblyFile')
                if target not in managed or name not in managed[target]['types']:
                    _missing('DATA', 'msbuild.task.assembly', 'selected managed image/type absent: ' + target + ':' + name)
                task_names.add(name.casefold())
                tasks.append({'name': name, 'assembly': managed[target]['image'], 'source': projects[path]})
            elif child.tag == ns + 'Target':
                _attrs(child, ('Name',), ('Name',), 'msbuild.target.attributes')
                name = _literal(child.attrib['Name'], 'msbuild.target.Name')
                if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_.-]{0,255}', name) or name.casefold() in targets:
                    _missing('SOURCE', 'msbuild.target.duplicate_or_name', 'exact unique target required; no override/order guessing')
                targets.add(name.casefold())
                for task in child:
                    if not task.tag.startswith(ns) or '{' in task.tag[len(ns):] or len(task):
                        _missing('SOURCE', 'msbuild.target.task', 'literal task invocation without Output/children required')
                    taskname = task.tag[len(ns):]
                    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_.]{0,255}', taskname):
                        raise ValueError('Literal task invocation name required')
                    for key, val in task.attrib.items():
                        if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,127}', key):
                            _missing('SOURCE', 'msbuild.target.task.parameter_name', 'unqualified bounded parameter required')
                        if key.casefold() in ('condition', 'continueonerror', 'msbuildruntime', 'msbuildarchitecture'):
                            _missing('SOURCE', 'msbuild.target.task.' + key, 'runtime/condition/control task semantics')
                        _literal(val, 'msbuild.target.task.parameter')
                    invocations.append(taskname)
            else:
                _missing('SOURCE', 'msbuild.project.element', 'unsupported evaluation element: ' + child.tag)
        active.remove(path)
    visit(selected['entry_project']['path'])
    if seen != [ref['path'] for ref in selected['projects']]:
        raise ValueError('Exact ordered reached MSBuild project set differs')
    if tasks != selected['tasks']:
        raise ValueError('Exact ordered UsingTask declarations differ from profile')
    for name in invocations:
        if name not in {task['name'] for task in tasks}:
            _missing('DATA', 'msbuild.task.invocation', 'explicit full UsingTask registration absent: ' + name)
    return {'projects': seen, 'tasks': tasks, 'targets': sorted(targets),
            'invocations': invocations}


def _inventory(held_inventory):
    """Read only our fixed frozen source helper, never selected input paths."""
    _keys(held_inventory, ('reference', 'raw', 'provenance_reference', 'provenance_raw'), 'held original inventory')
    _metadata_ref(held_inventory['reference']); _metadata_ref(held_inventory['provenance_reference'])
    import builtins
    import os
    from pathlib import Path
    import stat
    source_path = Path(__file__).resolve().parent / 'inventory_contract.py'
    with source_path.open('rb') as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size != 10077:
            raise ValueError('Frozen inventory helper size/type differs')
        raw = stream.read(10078)
        after = os.fstat(stream.fileno())
    ident = lambda value: (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns)
    if (ident(before) != ident(after) or len(raw) != 10077 or
            hashlib.sha256(raw).hexdigest() != '83ff23d4356e454e899446e16bfea9aaf8d778f1d91972ace45220d2a9bf2bfb'):
        raise ValueError('Frozen inventory helper source identity differs')
    allowed = frozenset(('copy', 'hashlib', 'json', 'pathlib', 're'))
    original_import = builtins.__import__
    def source_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name not in allowed or level:
            raise ImportError('Unreviewed inventory-helper source import')
        return original_import(name, globals, locals, fromlist, level)
    namespace = {'__name__': '_frozen_managed_inventory',
                 '__builtins__': {**vars(builtins), '__import__': source_import}}
    exec(compile(raw, str(source_path), 'exec'), namespace)
    result = namespace['inventory_declaration'](
        held_inventory['raw'], held_inventory['reference']['sha256'], 'host_generators',
        provenance_raw=held_inventory['provenance_raw'],
        provenance_pin=held_inventory['provenance_reference']['sha256'])
    if result['provenance'] != held_inventory['provenance_reference']:
        raise ValueError('Original inventory provenance reference differs')
    return result


def verify_profile(profile, held_inventory, held_bytes):
    """Join exact declared static closure to original inventory/held byte facts.

    Returned dictionaries never authenticate their caller, its native capture,
    runtime search policy, publisher, source origin, version or execution closure.
    """
    profile = copy.deepcopy(_profile(profile))
    inventory = _inventory(held_inventory)
    host = profile['host_bundle']
    if (host['root'] != inventory['root'] or
            host['inventory'] != held_inventory['reference'] or
            host['subject_sha256'] != inventory['subject_sha256']):
        raise ValueError('Profile does not join original complete host inventory subject')
    if type(held_bytes) is not dict or not 1 <= len(held_bytes) <= MAX_FILES:
        _missing('DATA', 'held_bytes.count', 'finite selected runtime profile must have 1..4096 files')
    total = 0
    for path, raw in held_bytes.items():
        _path(path)
        if not _within(path, host['root']):
            _missing('DATA', 'held_bytes.root', 'outside host bundle; Root/native-parent typed-root proposal required: ' + path)
        if type(raw) is not bytes or len(raw) > MAX_FILE:
            _missing('DATA', 'held_bytes.file', 'selected file exceeds 64-MiB domain: ' + path)
        total += len(raw)
        if total > MAX_TOTAL:
            _missing('DATA', 'held_bytes.aggregate', 'selected closure exceeds 256-MiB domain')
        relative = path[len(host['root']) + 1:]
        expected = inventory['files'].get(relative)
        if expected != {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}:
            raise ValueError('Held runtime bytes do not join exact complete inventory file: ' + path)
    selected_refs = {}
    def select(ref):
        _ref(ref)
        previous = selected_refs.get(ref['path'])
        if previous is not None and previous != ref: raise ValueError('Conflicting selected runtime file reference')
        selected_refs[ref['path']] = copy.deepcopy(ref)
        raw = held_bytes.get(ref['path'])
        if raw is None:
            _missing('DATA', 'profile.file', 'exact selected held bytes absent: ' + ref['path'])
        if len(raw) != ref['bytes'] or hashlib.sha256(raw).hexdigest() != ref['sha256']:
            raise ValueError('Profile file reference differs from held bytes: ' + ref['path'])
        return raw
    select(profile['program'])
    runtime = profile['managed_runtime']
    for key in ('configuration', 'machine_configuration', 'clr_image'): select(runtime[key])
    managed = {}
    derived_size = 0
    definitions = {}
    for row in profile['assemblies']:
        path = row['image']['path']
        if path in managed: raise ValueError('Repeated managed assembly image')
        facts = inspect_managed_image(select(row['image']), row['image'])
        derived_size += len(_canonical(facts))
        if derived_size > 32 * 1024 * 1024:
            _missing('DATA', 'profile.facts.work_bound', 'managed derived facts exceed finite 32-MiB aggregate domain')
        if facts['assembly'] != row['identity']:
            raise ValueError('Selected assembly identity differs from metadata')
        key = (row['identity']['name'].casefold(), tuple(row['identity']['version']),
               row['identity']['culture'].casefold(), row['identity']['public_key_token'])
        if key in definitions: raise ValueError('Aliased/repeated assembly identity')
        definitions[key] = path
        if row['role'] == 'runtime' and not _within(path, runtime['root']):
            raise ValueError('Runtime assembly lies outside explicit managed runtime root')
        managed[path] = facts
    program = profile['program']['path']
    if (program not in managed or managed[program]['image'] != profile['program'] or
            managed[program]['dll'] or sum(row['role'] == 'program' for row in profile['assemblies']) != 1 or
            not any(row['role'] == 'program' and row['image'] == profile['program'] for row in profile['assemblies'])):
        raise ValueError('Exact executable program assembly/role missing')
    native = {}
    for row in profile['native_images']:
        path = row['image']['path']
        if path in native or path in managed: raise ValueError('Repeated/ambiguous native image')
        raw = select(row['image']); pe = _PE(raw)
        if pe.machine != 'x86_64' or pe.directory(14) != (0, 0):
            _missing('SOURCE', 'native_image.format', 'strict native x64 runtime image required; CLR remains rejected')
        if pe.directory(0) != (0, 0):
            address, size = pe.directory(0)
            at, _ = pe.rva(address, 40)
            count = struct.unpack_from('<I', raw, at + 20)[0]
            functions = struct.unpack_from('<I', raw, at + 28)[0]
            if size < 40 or not 1 <= count <= 65536: raise ValueError('Invalid native export directory')
            location, _ = pe.rva(functions, count * 4)
            for i in range(count):
                target = struct.unpack_from('<I', raw, location + i * 4)[0]
                if address <= target < address + size:
                    _missing('SOURCE', 'native_image.forwarded_export', 'explicit forwarded native exports unsupported')
                if target: pe.rva(target, 1)
        if not any(path == root or _within(path, root) for root in profile['native_runtime_roots']):
            raise ValueError('Native image outside selected native runtime roots')
        native_facts = {'image': copy.deepcopy(row['image']), 'imports': pe.imports()}
        native_size = len(_canonical(native_facts))
        derived_size += native_size
        if native_size > MAX_DERIVED or derived_size > 32 * 1024 * 1024:
            _missing('DATA', 'profile.facts.work_bound', 'native derived facts exceed finite 8-MiB/image or 32-MiB aggregate domain')
        native[path] = native_facts
    if runtime['clr_image']['path'] not in native or native[runtime['clr_image']['path']]['image'] != runtime['clr_image']:
        raise ValueError('Selected CLR image lacks native held image declaration')
    native_bindings = {}
    for row in profile['native_images']:
        facts = native[row['image']['path']]
        names = [item['name'] for item in row['imports']]
        if len(names) != len(set(names)) or set(names) != {item['name'] for item in facts['imports']}:
            raise ValueError('Complete native import resolution set differs')
        for item in row['imports']:
            target = item['image']['path']
            if target not in native or native[target]['image'] != item['image'] or target.rsplit('/', 1)[-1].casefold() != item['name']:
                _missing('DATA', 'native_image.import', 'exact selected native import resolution absent: ' + item['name'])
        native_bindings[row['image']['path']] = {item['name']: item['image']['path'] for item in row['imports']}
    native_by_name = {}
    for path in native:
        name = path.rsplit('/', 1)[-1].casefold()
        if name in native_by_name:
            _missing('SOURCE', 'native_image.basename', 'ambiguous search-root origin; exact source/runtime selection extension required')
        native_by_name[name] = path
    managed_edges = {}
    for row in profile['assemblies']:
        facts = managed[row['image']['path']]
        refs = [binding['reference'] for binding in row['bindings']]
        if refs != facts['assembly_references']:
            raise ValueError('Exact ordered managed AssemblyRef binding set differs')
        edges = []
        for binding in row['bindings']:
            target = binding['image']['path']
            if (target not in managed or managed[target]['image'] != binding['image'] or
                    managed[target]['assembly'] != binding['reference']):
                _missing('DATA', 'managed_image.assembly_reference', 'exact identity-selected target image absent: ' + binding['reference']['name'])
            edges.append(target)
        required_native = {item['name'] for item in facts['native_imports']} | {item['module'] for item in facts['pinvokes']}
        for name in required_native:
            if name not in native_by_name:
                _missing('DATA', 'managed_image.native_reference', 'exact selected native DLL image absent: ' + name)
        managed_edges[row['image']['path']] = edges + [native_by_name[name] for name in sorted(required_native)]
    for ref in profile['msbuild']['projects']: select(ref)
    for task in profile['msbuild']['tasks']:
        select(task['source']); select(task['assembly'])
    _runtime_configuration(profile, held_bytes)
    msbuild = _msbuild_closure(profile, held_bytes, managed)
    reached = set()
    pending = [program, runtime['clr_image']['path']] + [task['assembly']['path'] for task in msbuild['tasks']]
    while pending:
        path = pending.pop()
        if path in reached: continue
        reached.add(path)
        if len(reached) > MAX_FILES: raise ValueError('Dependency graph bound exceeded')
        pending.extend(managed_edges.get(path, ()))
        pending.extend(native_bindings.get(path, {}).values())
    if reached != set(managed) | set(native):
        raise ValueError('Unreached extra managed/native image declarations')
    if set(selected_refs) != set(held_bytes):
        raise ValueError('Held byte set has extras or absent selected closure files')
    return {'scope': SCOPE, 'program': copy.deepcopy(profile['program']),
            'inventory_reference': copy.deepcopy(host['inventory']),
            'inventory_subject_sha256': inventory['subject_sha256'],
            'managed_images': copy.deepcopy(managed), 'native_images': copy.deepcopy(native),
            'msbuild': msbuild, 'selected_files': [selected_refs[path] for path in sorted(selected_refs)],
            'native_admission': False, 'execution_closure_proven': False,
            'format_qualified': False}
