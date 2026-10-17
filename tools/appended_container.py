#!/usr/bin/env python3
"""Bounded canonical appended-package reference composer; never invokes build tools.

The external verifier authenticates bytes only when supplied independently pinned
kernel-descriptor bytes. This module is a format/reference implementation, not
proof that a declared kernel profile has passed runtime/release qualification.
"""
import argparse
import base64
import binascii
from dataclasses import dataclass
import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import stat
import struct
import sys
import tempfile
import unicodedata

FORMAT_VERSION = 1
MAGIC = b'SFAPND01'
STAMP_MAGIC = b'SFKERN01'
TRAILER = struct.Struct('<8sIIQQQQQ32s32s32s40s')
TRAILER_SIZE = 192
CARRIERS = {'package': 0, 'elf': 1, 'pe': 2, 'html': 3}
HTML_MARKER = b'<!--SFAPPEND01-->'
HTML_OPEN = b'\n<script type="application/octet-stream" id="foundation-appended-v1">'
HTML_CLOSE = b'</script>\n</body>\n</html>\n'
MAX_PACKAGE = 256 * 1024 * 1024
MAX_INDEX = 4 * 1024 * 1024
MAX_FILE = 64 * 1024 * 1024
MAX_KERNEL = 512 * 1024 * 1024
MAX_FILES = 4096
MAX_PATH = 240
MAX_DEPTH = 16
MAX_ARTIFACT = MAX_KERNEL + ((MAX_PACKAGE + TRAILER_SIZE + 2) // 3) * 4 + 4096
UINT64_MAX = (1 << 64) - 1
BINARY_PROFILE = 'foundation-guest-v1'
STARTUP_PATH = 'web/.foundation/startup-v1.json'
STARTUP_CAPABILITY = 'foundation.startup.v1'
COMPOSITION_STARTUP_PATH = 'web/.foundation/startup-v2.json'
GUI_COMPOSITION_CAPABILITY = 'foundation.gui-composition.v1'
MAX_STARTUP = 4096
_STARTUP_BYTES = b'{"kind":"foundation-appended-startup","primary":"web","schema_version":1}'
PROFILES = {'minimal': set(), 'web': {'web'}, 'binary': {'binary'}, 'both': {'web', 'binary'}}
_HEX = re.compile(r'[0-9a-f]{64}\Z')
_NAME = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z')
_WINDOWS_RESERVED = re.compile(r'(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?\Z', re.I)


class ContainerError(ValueError):
    """An input does not meet the explicitly versioned reference contract."""


def digest(data):
    return hashlib.sha256(data).hexdigest()


def _fail(message):
    raise ContainerError(message)


def _integer(value, label, maximum=UINT64_MAX, minimum=0):
    if type(value) is not int or not minimum <= value <= maximum:
        _fail('Invalid integer for ' + label)
    return value


def _keys(value, required, optional=(), label='object'):
    if type(value) is not dict or not set(required) <= set(value) or set(value) - set(required) - set(optional):
        _fail('Invalid ' + label + ' fields')


def _json_value(value, depth=0, budget=None):
    if budget is None:
        budget = [100000]
    budget[0] -= 1
    if depth > 16 or budget[0] < 0:
        _fail('JSON nesting/value limit exceeded')
    if value is None or type(value) is bool:
        return
    if type(value) is int:
        _integer(value, 'JSON value')
    elif type(value) is str:
        try:
            value.encode('utf-8')
        except UnicodeError as error:
            raise ContainerError('Invalid Unicode scalar in JSON') from error
    elif type(value) is list:
        for item in value:
            _json_value(item, depth + 1, budget)
    elif type(value) is dict:
        for key, item in value.items():
            if type(key) is not str:
                _fail('JSON object key must be text')
            try:
                key.encode('utf-8')
            except UnicodeError as error:
                raise ContainerError('Invalid Unicode scalar in JSON key') from error
            _json_value(item, depth + 1, budget)
    else:
        _fail('Only integer-valued canonical JSON is supported')


def canonical_json(value):
    _json_value(value)
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            _fail('Duplicate JSON field: ' + key)
        result[key] = value
    return result


def parse_json(data, label='JSON'):
    try:
        value = json.loads(data.decode('utf-8'), object_pairs_hook=_pairs,
                           parse_float=lambda _: _fail('JSON floating point is unsupported'),
                           parse_constant=lambda _: _fail('Invalid JSON constant'))
        if canonical_json(value) != data:
            _fail('Noncanonical ' + label)
        return value
    except (UnicodeError, json.JSONDecodeError, RecursionError) as error:
        raise ContainerError('Malformed ' + label) from error


def resource_path(value):
    if type(value) is not str:
        _fail('Resource path must be text')
    try:
        encoded = value.encode('utf-8')
    except UnicodeError as error:
        raise ContainerError('Invalid resource path encoding') from error
    if (not encoded or len(encoded) > MAX_PATH or not value.isascii() or unicodedata.normalize('NFC', value) != value
            or any(unicodedata.category(c).startswith('C') for c in value)
            or any(c in value for c in '\\:%?#<>"|*') or value.startswith('/')):
        _fail('Unsafe resource path: ' + repr(value))
    segments = value.split('/')
    if len(segments) > MAX_DEPTH or any(not s or s in ('.', '..') or s[-1:] in ('.', ' ')
                                        or _WINDOWS_RESERVED.fullmatch(s) for s in segments):
        _fail('Unsafe resource path: ' + repr(value))
    return value


def _sha(value, label):
    if type(value) is not str or not _HEX.fullmatch(value):
        _fail('Invalid SHA-256 for ' + label)
    return value


def _strings(value, label):
    if (type(value) is not list or len(value) > 4096 or any(type(v) is not str or not _NAME.fullmatch(v) for v in value)
            or value != sorted(set(value))):
        _fail('Invalid sorted ' + label)


def _application(value):
    _keys(value, ('id', 'name', 'version'), label='application')
    for key, item in value.items():
        if type(item) is not str or not item or len(item.encode('utf-8')) > 256 or any(ord(c) < 32 or 127 <= ord(c) <= 159 for c in item):
            _fail('Invalid application ' + key)
    if not re.fullmatch(r'[a-z][a-z0-9]*(?:[.-][a-z0-9]+)+', value['id']):
        _fail('Invalid namespaced application identity')
    if (len(value['version']) > 128 or not re.fullmatch(
            r'[0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z]+(?:[.-][0-9A-Za-z]+)*)?'
            r'(?:\+[0-9A-Za-z]+(?:[.-][0-9A-Za-z]+)*)?', value['version'])):
        _fail('Invalid application version')


def _requirements(value):
    _keys(value, ('abi', 'services', 'capabilities'), label='requirements')
    _keys(value['abi'], ('major', 'minor'), label='ABI')
    _integer(value['abi']['major'], 'ABI major', 65535, 1)
    _integer(value['abi']['minor'], 'ABI minor', 65535)
    _strings(value['services'], 'services')
    _strings(value['capabilities'], 'capabilities')


def _audit_module(data, profile):
    if profile != BINARY_PROFILE:
        _fail('Unsupported portable binary profile: ' + str(profile))
    tools = str(Path(__file__).resolve().parent)
    if tools not in sys.path:
        sys.path.insert(0, tools)
    try:
        from appended_wasm import validate_module
    except ImportError as error:
        raise ContainerError('Portable module validator unavailable; binary packing cannot proceed') from error
    validate_module(data)


@dataclass(frozen=True)
class Package:
    data: bytes
    index: dict
    index_offset: int
    index_length: int

    @property
    def payload_id(self):
        return digest(self.data[self.index_offset:])

    @property
    def package_sha256(self):
        return digest(self.data)

    @property
    def mode(self):
        web, binary = (self.index['components'][name]['present'] for name in ('web', 'binary'))
        return 'both' if web and binary else 'web' if web else 'binary' if binary else 'neither'

    def file_bytes(self, path):
        for entry in self.index['files']:
            if entry['path'] == path:
                return self.data[entry['offset']:entry['offset'] + entry['length']]
        raise KeyError(path)


@dataclass(frozen=True)
class Artifact:
    prefix: bytes
    package: object
    carrier: str
    trusted: bool

    @property
    def mode(self):
        return self.package.mode if self.package is not None else 'neither'

    def report(self):
        return {'schema_version': 1, 'carrier': self.carrier, 'mode': self.mode,
                'kernel_length': len(self.prefix), 'kernel_sha256': digest(self.prefix),
                'independently_pinned_kernel': self.trusted,
                'package_sha256': self.package.package_sha256 if self.package else None,
                'payload_id': self.package.payload_id if self.package else None,
                'index': self.package.index if self.package else None}


def parse_package(data, index_offset, index_length):
    if type(data) is not bytes or len(data) > MAX_PACKAGE:
        _fail('Package exceeds limit or is not immutable bytes')
    _integer(index_offset, 'index offset', MAX_PACKAGE)
    _integer(index_length, 'index length', MAX_INDEX, 1)
    if index_offset > len(data) or index_length != len(data) - index_offset:
        _fail('Index must end exactly at package boundary')
    index = parse_json(data[index_offset:], 'payload index')
    _keys(index, ('schema_version', 'kind', 'application', 'components', 'requires', 'identities', 'files'), label='payload index')
    if type(index['schema_version']) is not int or index['schema_version'] != 1 or index['kind'] != 'foundation-appended-package':
        _fail('Unsupported payload index schema')
    _application(index['application'])
    _requirements(index['requires'])
    if type(index['identities']) is not dict or len(index['identities']) > 128:
        _fail('Invalid input identities')
    for name, value in index['identities'].items():
        if not _NAME.fullmatch(name):
            _fail('Invalid input identity name')
        _sha(value, 'input identity')
    components = index['components']
    _keys(components, ('web', 'binary'), label='components')
    _keys(components['web'], ('present', 'entry'), label='web component')
    _keys(components['binary'], ('present', 'entry', 'profile'), label='binary component')
    for name in ('web', 'binary'):
        component = components[name]
        if type(component['present']) is not bool:
            _fail('Component presence must be boolean')
        if component['present']:
            resource_path(component['entry'])
        elif component['entry'] is not None:
            _fail('Absent component retains an entry point')
    if not components['binary']['present'] and components['binary']['profile'] is not None:
        _fail('Absent binary component retains a profile')
    files = index['files']
    if type(files) is not list or not 1 <= len(files) <= MAX_FILES:
        _fail('Invalid payload file count')
    offset, paths, aliases, found = 0, [], set(), {'web': [], 'binary': []}
    for entry in files:
        _keys(entry, ('path', 'component', 'offset', 'length', 'media_type', 'sha256'), label='file entry')
        path = resource_path(entry['path'])
        component = entry['component']
        if type(component) is not str or component not in found or not path.startswith(component + '/'):
            _fail('File component namespace mismatch')
        if not components[component]['present']:
            _fail('Absent component retains files')
        alias = path.casefold()
        if alias in aliases:
            _fail('Duplicate or case-aliased resource path')
        aliases.add(alias)
        paths.append(path)
        _integer(entry['offset'], 'file offset', MAX_PACKAGE)
        size = _integer(entry['length'], 'file length', MAX_FILE)
        if entry['offset'] != offset or size > index_offset - offset:
            _fail('File data must have contiguous nonoverlapping coverage')
        offset += size
        if type(entry['media_type']) is not str or not re.fullmatch(r'[a-z0-9.+-]+/[a-z0-9.+-]+', entry['media_type']):
            _fail('Invalid media type')
        if digest(data[entry['offset']:offset]) != _sha(entry['sha256'], path):
            _fail('File SHA-256 mismatch: ' + path)
        found[component].append(entry)
    if paths != sorted(paths, key=lambda p: p.encode('utf-8')) or offset != index_offset:
        _fail('Unsorted paths or unexplained package data')
    for path in paths:
        parts = path.casefold().split('/')
        if any('/'.join(parts[:i]) in aliases for i in range(1, len(parts))):
            _fail('Resource file/directory alias')
    for name in ('web', 'binary'):
        component = components[name]
        if component['present'] and component['entry'] not in {entry['path'] for entry in found[name]}:
            _fail('Missing component entry point: ' + name)
    if components['web']['present']:
        entry = next(e for e in found['web'] if e['path'] == components['web']['entry'])
        if entry['media_type'] != 'text/html':
            _fail('Web entry point must be text/html')
        try:
            data[entry['offset']:entry['offset'] + entry['length']].decode('utf-8')
        except UnicodeError as error:
            raise ContainerError('Web entry point is not UTF-8') from error
    if components['binary']['present']:
        if len(found['binary']) != 1 or components['binary']['entry'] != 'binary/application.wasm':
            _fail('Binary v1 requires exactly binary/application.wasm')
        entry = found['binary'][0]
        if entry['media_type'] != 'application/wasm':
            _fail('Binary entry point must be application/wasm')
        _audit_module(data[entry['offset']:entry['offset'] + entry['length']], components['binary']['profile'])
    return Package(data, index, index_offset, index_length)


def build_package(files, application, *, web_entry=None, binary_entry=None, binary_profile=None,
                  requires=None, identities=None):
    """Create logical data+index bytes from explicit virtual-path byte resources."""
    if web_entry is None and binary_entry is None:
        _fail('Neither mode uses the pristine kernel, not an empty package')
    if type(files) is not dict or not 1 <= len(files) <= MAX_FILES:
        _fail('A package requires a bounded nonempty file inventory')
    content, entries = bytearray(), []
    for path in sorted(files, key=lambda p: resource_path(p).encode('utf-8')):
        value = files[path]
        if type(value) is not bytes or len(value) > MAX_FILE:
            _fail('Invalid immutable file bytes: ' + path)
        component = path.split('/')[0]
        media_type = {'html': 'text/html', 'htm': 'text/html', 'mjs': 'text/javascript',
                      'js': 'text/javascript', 'css': 'text/css', 'wasm': 'application/wasm',
                      'json': 'application/json', 'svg': 'image/svg+xml', 'png': 'image/png',
                      'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'txt': 'text/plain',
                      'woff': 'font/woff', 'woff2': 'font/woff2'}.get(path.rsplit('.', 1)[-1].lower(), 'application/octet-stream')
        entries.append({'path': path, 'component': component, 'offset': len(content),
                        'length': len(value), 'media_type': media_type, 'sha256': digest(value)})
        if len(value) > MAX_PACKAGE - len(content):
            _fail('Package data exceeds limit')
        content.extend(value)
    index = {'schema_version': 1, 'kind': 'foundation-appended-package', 'application': application,
             'components': {'web': {'present': web_entry is not None, 'entry': web_entry},
                            'binary': {'present': binary_entry is not None, 'entry': binary_entry,
                                       'profile': binary_profile}},
             'requires': requires if requires is not None else {'abi': {'major': 1, 'minor': 0}, 'services': [], 'capabilities': []},
             'identities': identities if identities is not None else {}, 'files': entries}
    encoded = canonical_json(index)
    return parse_package(bytes(content) + encoded, len(content), len(encoded))


def _startup_namespace(path):
    folded = path.casefold()
    return folded == 'web/.foundation' or folded.startswith('web/.foundation/')


def _composition_startup(primary, requires):
    value = requires if requires is not None else {
        'abi': {'major': 1, 'minor': 0}, 'services': [], 'capabilities': []}
    _requirements(value)
    return primary != 'web' or GUI_COMPOSITION_CAPABILITY in value['capabilities']


def _rich_requirements(requires, primary='web'):
    value = requires if requires is not None else {
        'abi': {'major': 1, 'minor': 0}, 'services': [], 'capabilities': []}
    _requirements(value)
    if primary not in ('web', 'compiled', 'binary'):
        _fail('Unsupported rich startup primary')
    if primary != 'binary' and {'foundation.view', 'foundation.view.v1'} & set(value['services'] + value['capabilities']):
        _fail('Rich ' + primary + '-primary startup cannot satisfy required foundation.view or foundation.view.v1; secondary views are unsupported')
    result = {'abi': dict(value['abi']), 'services': list(value['services']),
              'capabilities': sorted(set(value['capabilities']) | {STARTUP_CAPABILITY})}
    if _composition_startup(primary, value):
        result['capabilities'] = sorted(set(result['capabilities']) | {GUI_COMPOSITION_CAPABILITY})
    if primary == 'binary':
        if 'foundation.view.v1' in result['services'] or 'foundation.view' in result['capabilities']:
            _fail('Binary primary needs service foundation.view and capability foundation.view.v1')
        result['services'] = sorted(set(result['services']) | {'foundation.view'})
        result['capabilities'] = sorted(set(result['capabilities']) | {'foundation.view.v1'})
    _requirements(result)
    return result


def validate_rich_startup(package, *, _expected_primary=None):
    """Validate actual versioned startup bytes before creating a Module or Page.

    Version one remains exact web-only admission. Version two selects the
    additive GUI composition capability; this parser never certifies a kernel.
    """
    if type(package) is not Package:
        _fail('Rich startup requires an actual verified Package')
    verified = parse_package(package.data, package.index_offset, package.index_length)
    if canonical_json(package.index) != canonical_json(verified.index):
        _fail('Package index differs from its actual canonical bytes')
    if verified.mode not in ('web', 'both'):
        _fail('Rich startup requires a present web component')
    required = verified.index['requires']
    if STARTUP_CAPABILITY not in required['capabilities']:
        _fail('Rich startup is missing required capability ' + STARTUP_CAPABILITY)
    reserved = [entry for entry in verified.index['files'] if _startup_namespace(entry['path'])]
    if len(reserved) != 1 or reserved[0]['path'] not in (STARTUP_PATH, COMPOSITION_STARTUP_PATH):
        _fail('Rich startup requires exactly one recognized versioned startup resource in the reserved namespace')
    entry = reserved[0]
    if entry['component'] != 'web' or entry['media_type'] != 'application/json':
        _fail('Rich startup metadata must be a web application/json resource')
    if not 1 <= entry['length'] <= MAX_STARTUP:
        _fail('Rich startup metadata exceeds its 4 KiB limit or is empty')
    startup = parse_json(verified.file_bytes(entry['path']), 'startup metadata')
    _keys(startup, ('kind', 'primary', 'schema_version'), label='startup metadata')
    version = 1 if entry['path'] == STARTUP_PATH else 2
    if (type(startup['schema_version']) is not int or startup['schema_version'] != version
            or startup['kind'] != 'foundation-appended-startup'):
        _fail('Unsupported rich startup metadata schema/path combination')
    primary = startup['primary']
    if primary not in ('web', 'compiled', 'binary') or (_expected_primary is not None and primary != _expected_primary):
        _fail('Rich startup does not match the selected primary contract')
    if version == 1 and (primary != 'web' or GUI_COMPOSITION_CAPABILITY in required['capabilities']):
        _fail('Version-one rich startup supports web primary only; GUI composition requires startup-v2 and explicit kernel maintenance')
    if version == 2 and GUI_COMPOSITION_CAPABILITY not in required['capabilities']:
        _fail('Version-two rich startup requires foundation.gui-composition.v1; select a compatible retained kernel or explicit kernel maintenance')
    _rich_requirements(required, primary)
    if primary == 'binary' and (verified.mode != 'both' or 'foundation.view' not in required['services']
                                or 'foundation.view.v1' not in required['capabilities']):
        _fail('Binary rich primary requires its binary component and shared view binding requirements')
    return startup


def trailer_bytes(prefix, package, carrier):
    if carrier not in CARRIERS:
        _fail('Unsupported carrier')
    return TRAILER.pack(MAGIC, FORMAT_VERSION, TRAILER_SIZE, len(prefix), len(package.data),
                        package.index_offset, package.index_length, CARRIERS[carrier],
                        bytes.fromhex(digest(prefix)), bytes.fromhex(package.package_sha256),
                        bytes.fromhex(package.payload_id), bytes(40))


def encode_package(package):
    """Standalone transport: logical package followed by carrier-zero trailer."""
    return package.data + trailer_bytes(b'', package, 'package')


def _decode_trailer(blob, prefix_length=None, carrier=None):
    if len(blob) < TRAILER_SIZE:
        _fail('Missing or truncated appended trailer')
    fields = TRAILER.unpack(blob[-TRAILER_SIZE:])
    magic, version, size, kernel_length, package_length, index_offset, index_length, carrier_id, kernel_hash, package_hash, index_hash, reserved = fields
    if magic != MAGIC or version != FORMAT_VERSION or size != TRAILER_SIZE or reserved != bytes(40):
        _fail('Unrecognized, unsupported or corrupt appended trailer')
    if carrier_id not in CARRIERS.values() or carrier is not None and carrier_id != CARRIERS[carrier]:
        _fail('Appended carrier mismatch')
    if prefix_length is not None and kernel_length != prefix_length:
        _fail('Trailer disagrees with independently pinned kernel length')
    if kernel_length > MAX_KERNEL or package_length > MAX_PACKAGE or index_length > MAX_INDEX:
        _fail('Appended length exceeds limit')
    if package_length + TRAILER_SIZE > len(blob):
        _fail('Truncated appended package')
    start = len(blob) - TRAILER_SIZE - package_length
    package_data = blob[start:-TRAILER_SIZE]
    if digest(package_data) != package_hash.hex():
        _fail('Package SHA-256 mismatch')
    package = parse_package(package_data, index_offset, index_length)
    if package.payload_id != index_hash.hex():
        _fail('Index SHA-256 mismatch')
    return kernel_length, kernel_hash.hex(), package, carrier_id, start


def _native(prefix, carrier, boundary_offset=None):
    immutable = []
    load_mappings = []
    if carrier == 'elf':
        if len(prefix) < 52 or prefix[:4] != b'\x7fELF' or prefix[4] not in (1, 2) or prefix[5] not in (1, 2) or prefix[6] != 1:
            _fail('Invalid ELF kernel header')
        endian = '<' if prefix[5] == 1 else '>'
        if prefix[4] == 2:
            if len(prefix) < 64:
                _fail('Truncated ELF64 header')
            header = struct.unpack_from(endian + 'HHIQQQIHHHHHH', prefix, 16)
            phoff, phsize, phcount = header[4], header[8], header[9]
            phformat = endian + 'IIQQQQQQ'
        else:
            header = struct.unpack_from(endian + 'HHIIIIIHHHHHH', prefix, 16)
            phoff, phsize, phcount = header[4], header[8], header[9]
            phformat = endian + 'IIIIIIII'
        if header[0] not in (2, 3) or not phcount or phcount > 4096 or phsize != struct.calcsize(phformat) or phoff > len(prefix) or phcount * phsize > len(prefix) - phoff:
            _fail('Invalid ELF program-header table')
        loads = 0
        for i in range(phcount):
            ph = struct.unpack_from(phformat, prefix, phoff + i * phsize)
            if ph[0] != 1:
                continue
            loads += 1
            offset, size, memory, flags, align = ((ph[2], ph[5], ph[6], ph[1], ph[7]) if prefix[4] == 2
                                                   else (ph[1], ph[4], ph[5], ph[6], ph[7]))
            virtual = ph[3] if prefix[4] == 2 else ph[2]
            address_end = 1 << (64 if prefix[4] == 2 else 32)
            if memory > address_end - virtual:
                _fail('ELF load virtual range overflows its address width')
            if flags & 4 and not flags & 2:
                immutable.append((offset, size))
            if size > memory or offset > len(prefix) or size > len(prefix) - offset or align > (1 << 30) or align and align & (align - 1):
                _fail('Invalid ELF load extent')
            rounding = max(4096, align)
            load_mappings.append((offset, size, virtual, memory, flags, rounding))
            if ((offset + size + rounding - 1) // rounding) * rounding > len(prefix):
                _fail('ELF kernel requires finalized padding beyond page-rounded PT_LOAD extents')
        if not loads:
            _fail('ELF kernel has no loadable segments')
    elif carrier == 'pe':
        if len(prefix) < 64 or prefix[:2] != b'MZ':
            _fail('Invalid PE DOS header')
        offset = struct.unpack_from('<I', prefix, 60)[0]
        if offset > len(prefix) - 24 or prefix[offset:offset + 4] != b'PE\0\0':
            _fail('Invalid PE header')
        _, count, _, _, _, optional_size, flags = struct.unpack_from('<HHIIIHH', prefix, offset + 4)
        optional = offset + 24
        if not flags & 2 or flags & 0x2000 or not 1 <= count <= 96 or optional_size > len(prefix) - optional or optional_size < 2:
            _fail('Invalid PE optional-header bounds')
        magic = struct.unpack_from('<H', prefix, optional)[0]
        directory_offset = 96 if magic == 0x10b else 112 if magic == 0x20b else 0
        if not directory_offset or optional_size < directory_offset:
            _fail('Invalid PE optional header')
        directories = struct.unpack_from('<I', prefix, optional + directory_offset - 4)[0]
        if directories > 16 or directories * 8 > optional_size - directory_offset:
            _fail('Invalid PE data-directory bounds')
        if directories > 4 and any(struct.unpack_from('<II', prefix, optional + directory_offset + 32)):
            _fail('Signed PE kernels are unsupported; certificate directory must be absent')
        section_offset = optional + optional_size
        if count * 40 > len(prefix) - section_offset:
            _fail('Truncated PE section table')
        for index in range(count):
            raw_size, raw_offset = struct.unpack_from('<II', prefix, section_offset + index * 40 + 16)
            if raw_offset > len(prefix) or raw_size > len(prefix) - raw_offset:
                _fail('Invalid PE section extent')
            flags = struct.unpack_from('<I', prefix, section_offset + index * 40 + 36)[0]
            if flags & 0x40000000 and not flags & 0x80000000:
                immutable.append((raw_offset, raw_size))
    else:
        _fail('Unsupported native carrier')
    if boundary_offset is not None:
        if not any(start <= boundary_offset and boundary_offset - start + 16 <= size
                   for start, size in immutable):
            _fail('Kernel boundary metadata must occupy readable immutable native data')
        # Permissions apply to virtual pages, not merely file extents. A later
        # writable load can replace the same page containing the supposedly
        # read-only constant. Distinct-address private COW file aliases are fine.
        for offset, size, virtual, memory, flags, rounding in load_mappings:
            if not (flags & 4 and not flags & 2 and offset <= boundary_offset
                    and boundary_offset - offset + 16 <= size):
                continue
            stamp_virtual = virtual + boundary_offset - offset
            protected_start = stamp_virtual // rounding * rounding
            protected_end = (stamp_virtual + 16 + rounding - 1) // rounding * rounding
            for _, _, write_virtual, write_memory, write_flags, write_rounding in load_mappings:
                if not write_flags & 2 or not write_memory:
                    continue
                write_start = write_virtual // write_rounding * write_rounding
                write_end = (write_virtual + write_memory + write_rounding - 1) // write_rounding * write_rounding
                if write_start < protected_end and protected_start < write_end:
                    _fail('Writable ELF load overlaps the immutable boundary metadata page')


def validate_descriptor(descriptor):
    _keys(descriptor, ('schema_version', 'kind', 'carrier', 'profile', 'append_format', 'abi', 'capabilities',
                       'services', 'executable', 'boundary_offset', 'provenance'), ('kernel_inputs',), 'kernel descriptor')
    if type(descriptor['schema_version']) is not int or descriptor['schema_version'] != 1 or descriptor['kind'] != 'foundation-kernel':
        _fail('Unsupported kernel descriptor schema')
    if (type(descriptor['carrier']) is not str or type(descriptor['profile']) is not str
            or descriptor['carrier'] not in ('elf', 'pe', 'html') or descriptor['profile'] not in PROFILES):
        _fail('Unsupported kernel carrier or capability profile')
    if type(descriptor['append_format']) is not int or descriptor['append_format'] != FORMAT_VERSION:
        _fail('Kernel lacks the required appended format; explicit kernel maintenance required')
    _requirements({'abi': descriptor['abi'], 'services': descriptor['services'], 'capabilities': descriptor['capabilities']})
    _keys(descriptor['executable'], ('length', 'sha256'), label='kernel executable')
    _integer(descriptor['executable']['length'], 'kernel length', MAX_KERNEL, 1)
    _sha(descriptor['executable']['sha256'], 'kernel executable')
    if descriptor['carrier'] == 'html':
        if descriptor['boundary_offset'] is not None:
            _fail('HTML boundary offset must be null')
    else:
        position = _integer(descriptor['boundary_offset'], 'kernel boundary offset', MAX_KERNEL)
        if position > descriptor['executable']['length'] - 16:
            _fail('Kernel boundary metadata exceeds prefix')
    if type(descriptor['provenance']) is not dict or 'kernel_inputs' in descriptor and type(descriptor['kernel_inputs']) is not dict:
        _fail('Invalid kernel provenance or input inventory')
    _json_value(descriptor)
    return descriptor


class _ShellValidator(HTMLParser):
    # A deliberately constrained, balanced shell grammar avoids HTML error
    # recovery and parser-state-dependent interpretation of the suffix block.
    VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link',
            'meta', 'param', 'source', 'track', 'wbr'}
    FORBIDDEN = {'plaintext', 'xmp', 'noembed', 'noframes', 'noscript', 'iframe',
                 'template', 'svg', 'math'}

    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.stack = []
        self.counts = {'html': 0, 'head': 0, 'body': 0}
        self.marker = 0
        self.doctype = 0

    def handle_decl(self, decl):
        if decl.lower() != 'doctype html' or self.doctype or self.stack:
            _fail('HTML shell requires one initial HTML doctype')
        self.doctype += 1

    def unknown_decl(self, data):
        _fail('Unsupported HTML shell declaration')

    def handle_pi(self, data):
        _fail('Unsupported HTML shell processing instruction')

    def handle_starttag(self, tag, attrs):
        if tag in self.FORBIDDEN or self.marker:
            _fail('Unsupported HTML shell element or content after boundary')
        names = [name for name, _ in attrs]
        if len(names) != len(set(names)):
            _fail('Duplicate HTML shell attribute')
        if any(name == 'id' and value is not None and value.casefold() == 'foundation-appended-v1'
               for name, value in attrs):
            _fail('Pristine HTML shell already contains the owned payload block')
        if tag in self.counts:
            self.counts[tag] += 1
            if self.counts[tag] != 1:
                _fail('Duplicate HTML shell structural element')
            if tag == 'html' and self.stack or tag in ('head', 'body') and self.stack != ['html']:
                _fail('Invalid HTML shell structural nesting')
            if tag == 'body' and self.counts['head'] != 1:
                _fail('HTML shell requires a closed head before body')
        elif not self.stack or self.stack[-1] == 'html':
            _fail('HTML shell element lies outside head/body')
        if tag not in self.VOID:
            self.stack.append(tag)

    def handle_startendtag(self, tag, attrs):
        if tag not in self.VOID:
            _fail('Only void HTML shell elements may self-close')
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        if tag in ('html', 'body') or not self.stack or self.stack[-1] != tag or self.marker:
            _fail('HTML shell must use balanced inner tags and omit outer closing tags')
        self.stack.pop()

    def handle_comment(self, data):
        if data == 'SFAPPEND01':
            if self.stack != ['html', 'body'] or self.marker:
                _fail('HTML shell boundary is not in body parsing state')
            self.marker += 1
        elif self.marker:
            _fail('HTML shell content follows boundary')

    def handle_data(self, data):
        if self.marker or (not self.stack or self.stack == ['html']) and data.strip():
            _fail('HTML shell has unexpected text outside its document')

    def finish(self):
        if self.doctype != 1 or self.counts != {'html': 1, 'head': 1, 'body': 1} or self.stack != ['html', 'body'] or self.marker != 1:
            _fail('HTML shell lacks its balanced pristine parsing boundary')


def _html_shell(prefix):
    if not prefix.startswith(b'<!doctype html>') or not prefix.endswith(HTML_MARKER):
        _fail('HTML kernel lacks its canonical pristine-shell boundary')
    try:
        source = prefix.decode('utf-8')
        parser = _ShellValidator()
        parser.feed(source)
        parser.close()
        parser.finish()
    except (UnicodeError, RecursionError) as error:
        raise ContainerError('Malformed UTF-8 HTML shell') from error


def _verify_prefix(prefix, descriptor):
    if len(prefix) != descriptor['executable']['length'] or digest(prefix) != descriptor['executable']['sha256']:
        _fail('Kernel prefix differs from independently pinned descriptor')
    carrier = descriptor['carrier']
    if carrier == 'html':
        _html_shell(prefix)
    else:
        position = descriptor['boundary_offset']
        if prefix[position:position + 16] != STAMP_MAGIC + struct.pack('<Q', len(prefix)):
            _fail('Kernel lacks finalized pristine-length metadata; explicit kernel maintenance required')
        _native(prefix, carrier, position)


def _compatible(package, descriptor):
    components = {name for name in ('web', 'binary') if package.index['components'][name]['present']}
    if not components <= PROFILES[descriptor['profile']]:
        _fail('Kernel profile lacks payload capability; select a compatible retained kernel or explicit kernel maintenance')
    required = package.index['requires']
    if (required['abi']['major'] != descriptor['abi']['major'] or required['abi']['minor'] > descriptor['abi']['minor']):
        _fail('Kernel ABI is incompatible; explicit kernel maintenance required')
    for key in ('services', 'capabilities'):
        missing = sorted(set(required[key]) - set(descriptor[key]))
        if missing:
            _fail('Kernel missing required ' + key + ': ' + ', '.join(missing))


def _expected(artifact, mode):
    if mode is not None and (mode not in ('neither', 'web', 'binary', 'both') or artifact.mode != mode):
        _fail('Payload presence disagrees with independently required mode: ' + str(mode))
    return artifact


def parse_artifact(data, descriptor=None, *, expected_mode=None):
    """Verify raw bytes. With no descriptor only internal consistency is proven."""
    if type(data) is not bytes or len(data) > MAX_ARTIFACT:
        _fail('Artifact exceeds size limit or is not immutable bytes')
    if descriptor is not None:
        validate_descriptor(descriptor)
        length, carrier = descriptor['executable']['length'], descriptor['carrier']
        if len(data) < length:
            _fail('Artifact is shorter than pinned pristine kernel')
        prefix = data[:length]
        _verify_prefix(prefix, descriptor)
        if len(data) == length:
            return _expected(Artifact(prefix, None, carrier, True), expected_mode)
        if carrier == 'html':
            suffix = data[length:]
            maximum = ((MAX_PACKAGE + TRAILER_SIZE + 2) // 3) * 4
            if not suffix.startswith(HTML_OPEN) or not suffix.endswith(HTML_CLOSE):
                _fail('Malformed canonical HTML appended suffix')
            encoded = suffix[len(HTML_OPEN):-len(HTML_CLOSE)]
            if len(encoded) > maximum:
                _fail('HTML encoded package exceeds limit')
            try:
                blob = base64.b64decode(encoded, validate=True)
            except (binascii.Error, ValueError) as error:
                raise ContainerError('Invalid HTML package base64') from error
            if base64.b64encode(blob) != encoded:
                _fail('Noncanonical HTML package base64')
            kernel_length, kernel_hash, package, _, start = _decode_trailer(blob, length, carrier)
            if start != 0:
                _fail('HTML block has unexplained decoded bytes')
        else:
            kernel_length, kernel_hash, package, _, start = _decode_trailer(data, length, carrier)
            if start != length:
                _fail('Native file size differs from kernel+package+trailer')
        if kernel_hash != digest(prefix):
            _fail('Trailer kernel SHA-256 mismatch')
        _compatible(package, descriptor)
        return _expected(Artifact(prefix, package, carrier, True), expected_mode)
    # The transport carrier is deliberately separate from the logical package.
    if data[-TRAILER_SIZE:-TRAILER_SIZE + 8] != MAGIC and HTML_OPEN in data:
        if data.count(HTML_OPEN) != 1 or not data.endswith(HTML_CLOSE):
            _fail('Duplicate or malformed HTML appended blocks')
        prefix, encoded = data.split(HTML_OPEN)
        _html_shell(prefix)
        encoded = encoded[:-len(HTML_CLOSE)]
        if len(encoded) > ((MAX_PACKAGE + TRAILER_SIZE + 2) // 3) * 4:
            _fail('HTML encoded package exceeds limit')
        try:
            blob = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError) as error:
            raise ContainerError('Invalid HTML package base64') from error
        if base64.b64encode(blob) != encoded:
            _fail('Noncanonical HTML package base64')
        kernel_length, kernel_hash, package, carrier_id, start = _decode_trailer(blob, len(prefix), 'html')
        if start:
            _fail('HTML block has unexplained decoded bytes')
    else:
        kernel_length, kernel_hash, package, carrier_id, start = _decode_trailer(data)
        if start != kernel_length:
            _fail('Native/transport file size differs from kernel+package+trailer')
        prefix = data[:start]
        if carrier_id == 0 and prefix:
            _fail('Standalone package transport cannot contain a kernel')
        if carrier_id == CARRIERS['html']:
            _fail('HTML carrier requires canonical ASCII framing')
    if digest(prefix) != kernel_hash:
        _fail('Trailer kernel SHA-256 mismatch')
    detected_carrier = next(k for k, v in CARRIERS.items() if v == carrier_id)
    if detected_carrier in ('elf', 'pe'):
        _native(prefix, detected_carrier)
    return _expected(Artifact(prefix, package, detected_carrier, False), expected_mode)


def compose_bytes(source, descriptor, package=None, *, expected_mode=None):
    """Replace the entire suffix, preserving an independently pinned exact prefix."""
    existing = parse_artifact(source, descriptor)
    if package is not None:
        # Revalidate callers' objects; do not trust a hand-constructed Package.
        package = parse_package(package.data, package.index_offset, package.index_length)
        _compatible(package, descriptor)
        trailer = trailer_bytes(existing.prefix, package, existing.carrier)
        suffix = (HTML_OPEN + base64.b64encode(package.data + trailer) + HTML_CLOSE
                  if existing.carrier == 'html' else package.data + trailer)
        result = existing.prefix + suffix
    else:
        result = existing.prefix
    parse_artifact(result, descriptor, expected_mode=expected_mode)
    return result


@dataclass(frozen=True)
class _Snapshot:
    path: Path
    content: bytes
    identity: tuple
    mode: int


def _ordinary_path(path, *, directory=False):
    path = Path(os.path.abspath(os.fspath(path)))
    for item in reversed((path,) + tuple(path.parents)):
        try:
            state = item.lstat()
        except OSError as error:
            raise ContainerError('Missing input/parent: ' + str(item)) from error
        if stat.S_ISLNK(state.st_mode):
            _fail('Linked input or parent is unsupported: ' + str(item))
    if directory and not path.is_dir():
        _fail('Expected ordinary directory: ' + str(path))
    return path


def _identity(state):
    return (state.st_dev, state.st_ino, state.st_size, state.st_mtime_ns, state.st_ctime_ns, state.st_mode)


def _snapshot(path, limit=MAX_ARTIFACT):
    path = _ordinary_path(path)
    flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_BINARY', 0)
    fd = os.open(path, flags)
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_size > limit:
            _fail('Expected bounded ordinary input file: ' + str(path))
        chunks, remaining = [], limit + 1
        while remaining:
            chunk = os.read(fd, min(1024 * 1024, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        data = b''.join(chunks)
        if len(data) > limit or len(data) != before.st_size or _identity(before) != _identity(os.fstat(fd)):
            _fail('Input changed during read: ' + str(path))
    finally:
        os.close(fd)
    if _identity(path.lstat()) != _identity(before):
        _fail('Input identity changed during read: ' + str(path))
    return _Snapshot(path, data, _identity(before), stat.S_IMODE(before.st_mode))


def _recheck(snapshot):
    if isinstance(snapshot, _TreeSnapshot):
        if (_identity(_ordinary_path(snapshot.path, directory=True).lstat()) != snapshot.identity
                or _tree_inventory(snapshot.path) != snapshot.inventory
                or _identity(snapshot.path.lstat()) != snapshot.identity):
            _fail('Web source inventory changed before output publication')
        return
    current = _snapshot(snapshot.path, max(len(snapshot.content), 1))
    if current.identity != snapshot.identity or current.content != snapshot.content:
        _fail('Input changed before output publication: ' + str(snapshot.path))


def _write_new(output, content, snapshots=(), mode=0o644, verifier=None):
    """Publish through exclusive same-directory staging and a no-replace hardlink."""
    output = Path(os.path.abspath(os.fspath(output)))
    parent = _ordinary_path(output.parent, directory=True)
    if output.exists() or output.is_symlink():
        _fail('Output destination must be new: ' + str(output))
    fd, name = tempfile.mkstemp(prefix='.sfappend-', dir=parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(content)
            stream.flush()
            if hasattr(os, 'fchmod'):
                os.fchmod(stream.fileno(), mode & 0o777)
            else:
                os.chmod(temporary, mode & 0o777)
            os.fsync(stream.fileno())
        written = _snapshot(temporary, len(content)).content
        if written != content:
            _fail('Temporary output verification failed')
        if verifier is not None:
            verifier(written)
        for source in snapshots:
            _recheck(source)
        # This operation atomically fails if *anything* appeared at output.
        os.link(temporary, output, follow_symlinks=False)
    finally:
        temporary.unlink(missing_ok=True)
    return output


def load_kernel_descriptor(path, descriptor_sha256):
    _sha(descriptor_sha256, 'independently pinned kernel descriptor')
    saved = _snapshot(path, MAX_INDEX)
    if digest(saved.content) != descriptor_sha256:
        _fail('Kernel descriptor differs from independently pinned SHA-256')
    return validate_descriptor(parse_json(saved.content, 'kernel descriptor'))


def _load_descriptor(path, pin):
    _sha(pin, 'independently pinned kernel descriptor')
    saved = _snapshot(path, MAX_INDEX)
    if digest(saved.content) != pin:
        _fail('Kernel descriptor differs from independently pinned SHA-256')
    return validate_descriptor(parse_json(saved.content, 'kernel descriptor')), saved


def compose(source, descriptor, descriptor_sha256, package, output, *, expected_mode=None):
    """Compose from pristine/composed input plus a pinned canonical descriptor."""
    kernel, descriptor_input = _load_descriptor(descriptor, descriptor_sha256)
    source_input = _snapshot(source)
    inputs = [source_input, descriptor_input]
    payload = None
    if package is not None:
        package_input = _snapshot(package, MAX_PACKAGE + TRAILER_SIZE)
        parsed = parse_artifact(package_input.content)
        if parsed.carrier != 'package':
            _fail('Compose requires a standalone package transport')
        payload = parsed.package
        inputs.append(package_input)
    result = compose_bytes(source_input.content, kernel, payload, expected_mode=expected_mode)
    _write_new(output, result, inputs, source_input.mode,
               lambda data: parse_artifact(data, kernel, expected_mode=expected_mode))
    report = parse_artifact(result, kernel, expected_mode=expected_mode).report()
    report['artifact_sha256'] = digest(result)
    report['kernel_descriptor_sha256'] = descriptor_sha256
    return report


def strip(source, descriptor, descriptor_sha256, output, *, expected_mode=None):
    # expected_mode applies to the same input snapshot that is stripped.
    kernel, descriptor_input = _load_descriptor(descriptor, descriptor_sha256)
    source_input = _snapshot(source)
    existing = parse_artifact(source_input.content, kernel, expected_mode=expected_mode)
    result = compose_bytes(source_input.content, kernel)
    _write_new(output, result, [source_input, descriptor_input], source_input.mode,
               lambda data: parse_artifact(data, kernel, expected_mode='neither'))
    report = Artifact(existing.prefix, None, existing.carrier, True).report()
    report['artifact_sha256'] = digest(result)
    report['kernel_descriptor_sha256'] = descriptor_sha256
    return report


def verify(path, descriptor=None, descriptor_sha256=None, *, expected_mode=None, expected_sha256=None):
    source = _snapshot(path)
    if expected_sha256 is not None and digest(source.content) != _sha(expected_sha256, 'expected artifact'):
        _fail('Artifact differs from independently pinned SHA-256')
    if (descriptor is None) != (descriptor_sha256 is None):
        _fail('Kernel descriptor and independently pinned SHA-256 must be supplied together')
    kernel = load_kernel_descriptor(descriptor, descriptor_sha256) if descriptor is not None else None
    result = parse_artifact(source.content, kernel, expected_mode=expected_mode).report()
    result['artifact_sha256'] = digest(source.content)
    result['independently_pinned_artifact'] = expected_sha256 is not None
    return result


@dataclass(frozen=True)
class _TreeSnapshot:
    path: Path
    inventory: tuple
    identity: tuple


def _walk_error(error):
    raise ContainerError('Web source traversal failed: ' + str(error)) from error


def _tree_inventory(root):
    entries = []
    for directory, directories, names in os.walk(root, followlinks=False, onerror=_walk_error):
        for name in sorted(directories + names):
            path = Path(directory) / name
            state = path.lstat()
            if not stat.S_ISREG(state.st_mode) and not stat.S_ISDIR(state.st_mode):
                _fail('Web source contains unsupported linked/special input')
            entries.append((path.relative_to(root).as_posix(), _identity(state)))
            if len(entries) > MAX_FILES * 2:
                _fail('Web source inventory exceeds limit')
    return tuple(sorted(entries))


def _pack(web_root, binary_module, output, *, application, web_entry='index.html', binary_profile=BINARY_PROFILE,
          requires=None, identities=None, _inputs=(), startup=False, _startup_primary="web"):
    if _startup_primary not in ('web', 'compiled', 'binary'):
        _fail('Unsupported private startup primary')
    composition = startup and _composition_startup(_startup_primary, requires)
    startup_path = COMPOSITION_STARTUP_PATH if composition else STARTUP_PATH
    startup_bytes = (canonical_json({'kind': 'foundation-appended-startup',
                                    'primary': _startup_primary, 'schema_version': 2})
                     if composition else _STARTUP_BYTES)
    files, snapshots = {}, list(_inputs)
    collected = len(startup_bytes) if startup else 0
    if startup:
        if web_root is None:
            _fail('Rich startup requires a present web component')
        requires = _rich_requirements(requires, _startup_primary)
        if _startup_primary == "binary" and binary_module is None:
            _fail("Binary rich primary requires its precompiled binary module")
    if web_root is not None:
        root = _ordinary_path(web_root, directory=True)
        resource_path(web_entry)
        root_identity = _identity(root.lstat())
        inventory = _tree_inventory(root)
        if _identity(root.lstat()) != root_identity:
            _fail('Web source root changed during inventory')
        if startup and any(_startup_namespace('web/' + name) for name, _ in inventory):
            _fail('Rich startup reserves the web/.foundation namespace; source files and directories cannot supply it')
        snapshots.append(_TreeSnapshot(root, inventory, root_identity))
        visited = 0
        for directory, directories, names in os.walk(root, followlinks=False, onerror=_walk_error):
            visited += 1
            if visited > MAX_FILES:
                _fail('Web directory count exceeds limit')
            for name in directories:
                _ordinary_path(Path(directory) / name, directory=True)
            for name in names:
                path = Path(directory) / name
                virtual = 'web/' + path.relative_to(root).as_posix()
                resource_path(virtual)
                saved = _snapshot(path, min(MAX_FILE, MAX_PACKAGE - collected))
                collected += len(saved.content)
                snapshots.append(saved)
                files[virtual] = saved.content
                if len(files) > MAX_FILES:
                    _fail('Web file count exceeds limit')
    if binary_module is not None:
        saved = _snapshot(binary_module, min(MAX_FILE, MAX_PACKAGE - collected))
        snapshots.append(saved)
        files['binary/application.wasm'] = saved.content
    if startup:
        files[startup_path] = startup_bytes
    payload = build_package(files, application, web_entry='web/' + web_entry if web_root is not None else None,
                            binary_entry='binary/application.wasm' if binary_module is not None else None,
                            binary_profile=binary_profile if binary_module is not None else None,
                            requires=requires, identities=identities)
    if startup:
        validate_rich_startup(payload, _expected_primary=_startup_primary)
    encoded = encode_package(payload)
    def verify_written(data):
        parsed = parse_artifact(data)
        if startup:
            validate_rich_startup(parsed.package, _expected_primary=_startup_primary)
    _write_new(output, encoded, snapshots, verifier=verify_written)
    result = parse_artifact(encoded).report()
    result['artifact_sha256'] = digest(encoded)
    return result


def pack(web_root, binary_module, output, *, application, web_entry='index.html', binary_profile=BINARY_PROFILE,
         requires=None, identities=None, _inputs=()):
    """Pack explicit resources unchanged, without generating startup metadata."""
    return _pack(web_root, binary_module, output, application=application, web_entry=web_entry,
                 binary_profile=binary_profile, requires=requires, identities=identities, _inputs=_inputs)


def pack_project(project_root, binary_module, output, *, rich_startup=False, binary_profile=BINARY_PROFILE,
                 requires=None):
    """Pack a validated project; only explicit rich startup generates metadata.

    The explicit configured primary selects its canonical startup metadata.
    The retained kernel must independently support that primary; this function
    never compiles the supplied binary module or a retained kernel.
    """
    if type(rich_startup) is not bool:
        _fail('Rich startup selection must be boolean')
    if rich_startup:
        # Validate requirements before source/configuration traversal.
        _requirements(requires if requires is not None else {'abi': {'major': 1, 'minor': 0}, 'services': [], 'capabilities': []})
    tools = str(Path(__file__).resolve().parent)
    if tools not in sys.path:
        sys.path.insert(0, tools)
    from appended_project import load_project
    project = load_project(project_root)
    startup_primary = 'web'
    if rich_startup:
        if not project.configured:
            _fail('Rich startup requires an explicit configured primary')
        startup_primary = project.startup_primary
        if startup_primary not in ('web', 'compiled', 'binary'):
            _fail('Unsupported configured rich primary')
        requires = _rich_requirements(requires, startup_primary)
        if project.mode not in ('web', 'both'):
            _fail('Rich startup requires an enabled web component')
    config_inputs, identities = [], {}
    if project.configured:
        saved = _snapshot(project.root / 'foundation-project.json', MAX_INDEX)
        if saved.content != project._source_bytes:
            _fail('Project configuration changed during selection')
        config_inputs.append(saved)
        identities['project-config'] = digest(saved.content)
    if (binary_module is not None) != project.binary.enabled:
        _fail('Binary presence requires an explicit precompiled --binary-module matching project configuration; no build is attempted')
    return _pack(project.root / project.web.source if project.web.enabled else None,
                 binary_module, output, application=project.data['application'],
                 web_entry=project.web.entry or 'index.html', binary_profile=binary_profile,
                 requires=requires, identities=identities, _inputs=config_inputs, startup=rich_startup, _startup_primary=startup_primary)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest='action', required=True)
    for action in ('inspect', 'verify', 'compose', 'strip'):
        child = actions.add_parser(action)
        child.add_argument('--input', type=Path, required=True)
        child.add_argument('--kernel-descriptor', type=Path, required=action in ('compose', 'strip'))
        child.add_argument('--kernel-descriptor-sha256', required=action in ('compose', 'strip'))
        child.add_argument('--expected-mode', choices=('neither', 'web', 'binary', 'both'))
        if action in ('compose', 'strip'):
            child.add_argument('--output', type=Path, required=True)
        if action == 'compose':
            payload = child.add_mutually_exclusive_group(required=True)
            payload.add_argument('--package', type=Path)
            payload.add_argument('--no-payload', action='store_true')
        elif action in ('inspect', 'verify'):
            child.add_argument('--expected-sha256')
    child = actions.add_parser('pack')
    child.add_argument('--project-root', type=Path, default=Path.cwd())
    child.add_argument('--binary-module', type=Path)
    child.add_argument('--binary-profile', default=BINARY_PROFILE)
    child.add_argument('--rich-startup', action='store_true',
                       help='generate rich startup metadata from the explicit configured primary for a compatible retained kernel')
    child.add_argument('--require-service', metavar='NAME', action='append', default=[],
                       help='required service name; repeat for distinct names')
    child.add_argument('--require-capability', metavar='NAME', action='append', default=[],
                       help='required kernel capability; repeat for distinct names')
    child.add_argument('--require-abi-minor', type=int, default=0, metavar='MINOR',
                       help='minimum compatible ABI minor version (0..65535; major remains 1)')
    child.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.action == 'pack':
            for names, label in ((args.require_service, 'service'), (args.require_capability, 'capability')):
                if len(names) != len(set(names)):
                    _fail('Duplicate required ' + label + ' name')
            requires = {'abi': {'major': 1, 'minor': args.require_abi_minor},
                        'services': sorted(args.require_service),
                        'capabilities': sorted(args.require_capability)}
            _requirements(requires)
            result = pack_project(args.project_root, args.binary_module, args.output,
                                  rich_startup=args.rich_startup, binary_profile=args.binary_profile,
                                  requires=requires)
        elif args.action == 'compose':
            result = compose(args.input, args.kernel_descriptor, args.kernel_descriptor_sha256,
                             args.package, args.output, expected_mode=args.expected_mode)
        elif args.action == 'strip':
            result = strip(args.input, args.kernel_descriptor, args.kernel_descriptor_sha256,
                           args.output, expected_mode=args.expected_mode)
        else:
            result = verify(args.input, args.kernel_descriptor, args.kernel_descriptor_sha256,
                            expected_mode=args.expected_mode, expected_sha256=args.expected_sha256)
        print(canonical_json(result).decode('utf-8'))
        return 0
    except (ValueError, OSError) as error:
        print('appended container: ' + str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
