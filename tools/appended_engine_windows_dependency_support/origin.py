"""Read existing retained original authority; never execute or manufacture it.

The shared provider getter loads only fixed source definitions. Native input
admission occurs in the actual factory; pure checks and inert fixtures cannot
issue a private production original token.
"""
from __future__ import annotations

import copy
import gzip
import hashlib
import json
import math
import os
from pathlib import Path, PureWindowsPath
import platform
import re
import struct
import stat
import time
import threading
import unicodedata
import zlib

A_SOURCE_SHA256 = '02f675a2480bbb94eafed0cac101b8afca1d2c3fe4a17dddd4cfb9693998edc0'
_CHECKOUT = Path(__file__).resolve().parents[2]
_CURRENT_SOURCE_FACTS = {'tests/diagnostics/windows_engine_publication.py': {'bytes': 10515,
                                                     'sha256': '2ad31fa883729c7b157f21744cfcc5272b0eaad5591bcc3fc568ff8321fe2f8e'},
 'tests/diagnostics/windows_engine_source_reader.py': {'bytes': 26675,
                                                       'sha256': 'ea0743e266178395b792ea58d996a42b8c063d06d1c729745ea83d5ea34400a6'},
 'tools/appended_engine_native_inputs.py': {'bytes': 236376,
                                            'sha256': '973fdddefa5a4cccc0190fdc4c4f6f1ba6afd693b17d70d928e428c4060eb706'},
 'tools/appended_engine_native_sdk.py': {'bytes': 67094,
                                         'sha256': 'ae915886d9a5a6cefe230c10445c977f9841ed98e1e5ff14cd9883a73688828a'},
 'tools/appended_engine_windows_contract.py': {'bytes': 18541,
                                               'sha256': 'ef065be8c502211ea748dbfc1732b6ca02b9210ee78ed74901f2b6ca6869d5d8'},
 'tools/appended_engine_windows_publication.py': {'bytes': 98362,
                                                  'sha256': '02f675a2480bbb94eafed0cac101b8afca1d2c3fe4a17dddd4cfb9693998edc0'},
 'tools/process_tree.py': {'bytes': 70487,
                           'sha256': '521fa923a4396afeda67b05efabb0c21f1161895fbe72f172d4d7dfc69c1496f'}}
_CURRENT_SOURCE_CATALOGUE = {name: dict(facts, path=(_CHECKOUT / name).as_posix())
    for name, facts in _CURRENT_SOURCE_FACTS.items()}


def current_source_catalogue():
    """Return fixed current facts at actual maintained filenames; no authority."""
    return copy.deepcopy(_CURRENT_SOURCE_CATALOGUE)


def provider_source_catalogue():
    """Return fixed provider facts; no caller root or loader graph is accepted."""
    return copy.deepcopy(_PROVIDER_SOURCES)

REQUEST_KIND = 'foundation-windows-retained-originals-request-v1'
SUMMARY_KIND = 'foundation-windows-issued-retained-originals-v1'
_SHA = re.compile(r'[0-9a-f]{64}')
_OID = re.compile(r'[0-9a-f]{40}')
_NAME = re.compile(r'[a-z0-9][a-z0-9_-]{0,79}')
_ISSUED = {}
_UNCERTAIN = []
_SOURCE_FILES = ('tools/appended_engine_windows_publication.py',
    'tests/diagnostics/windows_engine_source_reader.py', 'tools/process_tree.py',
    'tools/appended_engine_windows_contract.py')
_SOURCE_IMPORTS = frozenset(('__future__', 'argparse', 'base64', 'binascii', 'contextlib', 'copy', 'ctypes',
    'dataclasses', 'hashlib', 'io', 'json', 'math', 'os', 'pathlib', 'platform', 're',
    'secrets', 'signal', 'stat', 'struct', 'subprocess', 'sys', 'threading', 'time',
    'traceback', 'types', 'uuid', 'select', 'errno', 'weakref', 'collections',
    'fcntl', 'socket', 'tempfile', 'typing', 'resource', 'selectors', 'atexit',
    'gzip', 'importlib', 'lzma', 'zipfile', 'tarfile', 'shutil', 'datetime', 'posixpath', 'shlex', 'zlib'))
_PROVIDER_ORDER = ('dependency_archive', 'appended_engine_manifest',
    'appended_engine_document_contract', 'appended_engine_editor_contract',
    'appended_engine_native_actions_contract', 'appended_engine_native_inputs', 'appended_engine_native_sdk',
    'appended_engine_windows_contract', 'appended_engine_windows_handoff',
    'process_tree', 'appended_engine_windows_source_replay')
_PROVIDER_SOURCE_FACTS = {'appended_engine_document_contract': {'bytes': 20492,
                                       'sha256': '2a1bb13756d605c0d2edbdcc62744110d68e88d4b2517753e0ef9a1c7a8c01fd'},
 'appended_engine_editor_contract': {'bytes': 15584,
                                     'sha256': '198ca94d231f58fdd027cd8bd1142d6d3fcbdc1e1975d127930eb400e77238c3'},
 'appended_engine_manifest': {'bytes': 21624,
                              'sha256': '6807d4471349f0bb8972ea7dbc257c6b8c8b79530ee32f9dcbca84750680952a'},
 'appended_engine_native_actions_contract': {'bytes': 16206,
                                             'sha256': 'd2808ae5a424f98984478e1bf287ce628e13aa2a06dd9d73cf45660e6dc3a48e'},
 'appended_engine_native_inputs': {'bytes': 236376,
                                   'sha256': '973fdddefa5a4cccc0190fdc4c4f6f1ba6afd693b17d70d928e428c4060eb706'},
 'appended_engine_native_sdk': {'bytes': 67094,
                                'sha256': 'ae915886d9a5a6cefe230c10445c977f9841ed98e1e5ff14cd9883a73688828a'},
 'appended_engine_windows_contract': {'bytes': 18541,
                                      'sha256': 'ef065be8c502211ea748dbfc1732b6ca02b9210ee78ed74901f2b6ca6869d5d8'},
 'appended_engine_windows_handoff': {'bytes': 41354,
                                     'sha256': '6bbf1209d1cb673b18f7f6ba5e6d8977d57df68c13287c1f592f0c4f64ac556b'},
 'appended_engine_windows_source_replay': {'bytes': 127602,
                                           'sha256': '2b0539c7769bb7fd906d9984faea536bccfbe51e85fc3dbc137f4a4c64c66788'},
 'dependency_archive': {'bytes': 14550,
                        'sha256': '28a2433591726aadcd35fc57e01d6e5c7307a2ed67b64846735b49f693b38d8a'},
 'process_tree': {'bytes': 70487,
                  'sha256': '521fa923a4396afeda67b05efabb0c21f1161895fbe72f172d4d7dfc69c1496f'}}
_PROVIDER_SOURCES = {name: dict(facts, path=(_CHECKOUT / "tools" / (name + ".py")).as_posix())
    for name, facts in _PROVIDER_SOURCE_FACTS.items()}
_PROVIDER_CACHE = None
_PROVIDER_LOCK = threading.RLock()
_LIMIT_BOUNDS = {'seconds': 86400, 'maximum_archive_bytes': 8 * 1024 ** 3,
    'maximum_expanded_bytes': 32 * 1024 ** 3, 'maximum_members': 1000000,
    'maximum_member_bytes': 256 * 1024 ** 2, 'maximum_patch_bytes': 32 * 1024 ** 2}


class OriginalDataError(ValueError):
    code = 'DATA'


class OriginalSourceError(ValueError):
    code = 'SOURCE'


class OriginalOwnershipUncertain(ValueError):
    code = 'OWNERSHIP_UNCERTAIN'


def _fields(value, keys, label):
    if type(value) is not dict or set(value) != set(keys):
        raise OriginalSourceError('Unsupported ' + label + ' fields')
    return value


def _pin(value):
    if type(value) is not str or not _SHA.fullmatch(value):
        raise OriginalDataError('An exact SHA256 is required')
    return value


def _positive(value):
    return type(value) is int and value > 0


def _relative(value):
    if (type(value) is not str or not value or len(value.encode('utf-8')) > 4096 or
            unicodedata.normalize('NFC', value) != value or '\\' in value or ':' in value or
            value.startswith('/') or any(part in ('', '.', '..') for part in value.split('/'))):
        raise OriginalSourceError('Unsupported retained relative path')
    for part in value.split('/'):
        if (part.endswith(('.', ' ')) or any(ord(c) < 32 or ord(c) == 127 or c in '<>"|?*' for c in part) or
                re.fullmatch(r'(?i:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?', part)):
            raise OriginalSourceError('Unsupported retained path component')
    return value


def _absolute(value):
    if type(value) is not str or len(value) > 4096:
        raise OriginalSourceError('An absolute normalized Windows path is required')
    path = PureWindowsPath(value)
    if (not re.fullmatch('[A-Za-z]:', path.drive) or not path.is_absolute() or
            path.as_posix() != value or '..' in path.parts):
        raise OriginalSourceError('An absolute normalized Windows path is required')
    for part in path.parts[1:]:
        _relative(part)
    return value


def _join(root, relative):
    return (PureWindowsPath(root) / _relative(relative)).as_posix()


def _ref(value, *, absolute=False, size=True):
    _fields(value, ('path', 'sha256', 'bytes') if size else ('path', 'sha256'), 'retained reference')
    (_absolute if absolute else _relative)(value['path']); _pin(value['sha256'])
    if size and (type(value['bytes']) is not int or not 0 <= value['bytes'] < 2 ** 63):
        raise OriginalDataError('An exact retained byte count is required')
    return copy.deepcopy(value)


def _encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False) + '\n').encode('utf-8')


def _parse(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result: raise OriginalDataError('Duplicate original JSON field')
            result[key] = value
        return result
    def bad(_): raise OriginalDataError('Nonfinite original JSON')
    try:
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=pairs, parse_constant=bad)
        _encoded(value)
        return value
    except (UnicodeError, RecursionError, OverflowError, json.JSONDecodeError, ValueError) as error:
        if isinstance(error, OriginalDataError): raise
        raise OriginalDataError('Invalid original JSON') from error


def _file_map(files, *, transport):
    if type(files) is not dict or not files or len(files) > (16000 if transport else 1000000):
        raise OriginalDataError('A finite complete original file inventory is required')
    aliases, result, total = {}, {}, 0
    for path, row in files.items():
        _relative(path)
        if transport:
            _fields(row, ('size', 'mode', 'sha256'), 'original transport file')
            if (type(row['size']) is not int or row['size'] < 0 or
                    type(row['mode']) is not int or row['mode'] not in (0o644, 0o755)):
                raise OriginalDataError('Invalid original transport file size/mode')
            _pin(row['sha256']); total += row['size']; result[path] = copy.deepcopy(row)
        else:
            result[path] = _pin(row)
        parts = path.split('/')
        for count in range(1, len(parts) + 1):
            current = '/'.join(parts[:count]); kind = 'file' if count == len(parts) else 'directory'
            prior = aliases.setdefault(current.casefold(), (current, kind))
            if prior != (current, kind): raise OriginalDataError('Original inventory path alias/kind conflict')
    if total > 64 * 1024 ** 3: raise OriginalDataError('Original transport bytes exceed policy')
    return result


def _context(value):
    keys = ('repository', 'run_id', 'attempt', 'source_commit', 'workflow', 'name')
    context = {key: value[key] for key in keys}
    if (type(context['repository']) is not str or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9][A-Za-z0-9_.-]*', context['repository']) or
            not _positive(context['run_id']) or not _positive(context['attempt']) or
            type(context['source_commit']) is not str or not _OID.fullmatch(context['source_commit']) or
            type(context['workflow']) is not str or not re.fullmatch(r'[a-zA-Z0-9_-]+\.yml', context['workflow']) or
            type(context['name']) is not str or not _NAME.fullmatch(context['name'])):
        raise OriginalDataError('Original CI context is incomplete')
    return context


def _asset(value):
    _fields(value, ('id', 'name', 'size', 'sha256'), 'original asset')
    if (not _positive(value['id']) or type(value['name']) is not str or
            type(value['size']) is not int or not 0 < value['size'] < 2 * 1024 ** 3):
        raise OriginalDataError('Original asset identity is incomplete')
    _pin(value['sha256']); return value


def _ci_metadata(selection, receipt):
    """Pure original-format checks; this function cannot issue a capability."""
    _fields(receipt, ('pointer', 'manifest', 'producer'), 'original CI fetch result')
    context_keys = ('repository', 'run_id', 'attempt', 'source_commit', 'workflow', 'name')
    _fields(selection, (*context_keys, 'schema_version', 'job_id', 'release_id', 'tag', 'manifest'), 'original CI pointer')
    context = _context(selection)
    if (type(selection['schema_version']) is not int or selection['schema_version'] != 1 or
            not _positive(selection['job_id']) or not _positive(selection['release_id']) or
            selection['tag'] != 'ci-' + str(context['run_id']) + '-attempt-' + str(context['attempt']) or
            receipt['pointer'] != selection):
        raise OriginalDataError('Original CI selection/pointer differs')
    asset = _asset(selection['manifest'])
    if asset['name'] != 'bundle-' + context['name'] + '.json':
        raise OriginalDataError('Original manifest asset name differs')
    manifest = receipt['manifest']
    _fields(manifest, (*context_keys, 'schema_version', 'repository_id', 'release_id', 'producer', 'metadata', 'files', 'archive'), 'original CI manifest')
    if (type(manifest['schema_version']) is not int or manifest['schema_version'] != 1 or
            any(type(manifest[k]) is not type(v) or manifest[k] != v for k, v in context.items()) or
            not _positive(manifest['repository_id']) or type(manifest['release_id']) is not int or manifest['release_id'] != selection['release_id'] or
            type(manifest['metadata']) is not dict or len(_encoded(manifest['metadata'])) > 65536):
        raise OriginalDataError('Original CI manifest context differs')
    producer = manifest['producer']
    _fields(producer, ('id', 'name', 'runner_id', 'runner_name'), 'original manifest producer')
    if (producer['id'] != selection['job_id'] or not _positive(producer['id']) or
            not _positive(producer['runner_id']) or any(type(producer[k]) is not str or not producer[k] for k in ('name', 'runner_name'))):
        raise OriginalDataError('Original CI producer identity is incomplete')
    job = receipt['producer']
    if (type(job) is not dict or any(type(job.get(k)) is not type(v) or job[k] != v for k, v in producer.items()) or
            job.get('run_id') != context['run_id'] or type(job.get('run_id')) is not int or
            job.get('run_attempt') != context['attempt'] or type(job.get('run_attempt')) is not int or
            job.get('head_sha') != context['source_commit'] or job.get('status') != 'completed' or job.get('conclusion') != 'success'):
        raise OriginalDataError('Original historical job is not the selected completed successful producer')
    files = _file_map(manifest['files'], transport=True)
    archive = manifest['archive']; _fields(archive, ('size', 'sha256', 'parts'), 'original transport archive')
    _pin(archive['sha256'])
    if (type(archive['size']) is not int or not 0 < archive['size'] <= 64 * 1024 ** 3 + 32 * 1024 ** 2 or
            type(archive['parts']) is not list or not 1 <= len(archive['parts']) <= 256):
        raise OriginalDataError('Original archive identity is incomplete')
    prefix = 'blob-' + hashlib.sha256(context['name'].encode()).hexdigest() + '-'
    ids, total = set(), 0
    for index, part in enumerate(archive['parts']):
        _asset(part)
        if (part['id'] in ids or part['size'] > 512 * 1024 ** 2 or
                part['name'] != prefix + str(index).zfill(4) + '-' + part['sha256']):
            raise OriginalDataError('Original archive chunk identity/order differs')
        ids.add(part['id']); total += part['size']
    if total != archive['size']: raise OriginalDataError('Original archive chunks are incomplete')
    raw = _encoded(manifest)
    if len(raw) > 8 * 1024 ** 2 or len(raw) != asset['size'] or hashlib.sha256(raw).hexdigest() != asset['sha256']:
        raise OriginalSourceError('Original CI manifest is not the known canonical retained transport format')
    return {'context': context, 'repository_id': manifest['repository_id'], 'release_id': manifest['release_id'],
        'manifest': copy.deepcopy(asset), 'producer': dict(producer, run_id=job['run_id'], run_attempt=job['run_attempt'],
        head_sha=job['head_sha'], status=job['status'], conclusion=job['conclusion']), 'files': files}


def _base_metadata(selection, receipt):
    _fields(receipt, ('fetched', 'recipe', 'files', 'payload'), 'original base acquisition')
    if (receipt['fetched'] is not True or receipt['payload'] != 'complete'):
        raise OriginalDataError('A complete original base acquisition is required')
    _pin(receipt['recipe']); recipe = receipt['recipe']
    stem = 'sdk-' + recipe
    names = (stem + '-binary.tar.gz', stem + '-sources.tar.gz', stem + '-SHA256SUMS')
    if type(receipt['files']) is not dict or set(receipt['files']) != set(names):
        raise OriginalDataError('Original base acquisition lacks the complete group')
    for value in receipt['files'].values(): _pin(value)
    if type(selection) is not dict or type(selection.get('reused')) is not bool:
        raise OriginalSourceError('Unsupported original base publication result')
    keys = ('operation', 'repository', 'execute', 'recipe', 'source_commit', 'files', 'lifecycle', 'plan_sha256', 'reused')
    _fields(selection, keys if selection['reused'] else (*keys, 'release_id', 'removed_assets'), 'original base publication')
    if (selection['operation'] != 'publish-base' or selection['execute'] is not True or
            selection['recipe'] != recipe or selection['files'] != receipt['files'] or
            type(selection['source_commit']) is not str or not _OID.fullmatch(selection['source_commit']) or
            type(selection['repository']) is not str or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9][A-Za-z0-9_.-]*', selection['repository']) or
            selection['lifecycle'] != 'prerelease; never Latest; immutable complete group; retire superseded matching SDK slots'):
        raise OriginalDataError('Original base publication/acquisition differs')
    _pin(selection['plan_sha256'])
    if not selection['reused'] and (not _positive(selection['release_id']) or type(selection['removed_assets']) is not dict):
        raise OriginalDataError('Original base publication identity is incomplete')
    return {'repository': selection['repository'], 'recipe': recipe, 'source_commit': selection['source_commit'],
        'files': copy.deepcopy(receipt['files']), 'payload': 'complete', 'release_id': selection.get('release_id'), 'names': names}


class _Capture:
    def __init__(self, owner, root, deadline, limits):
        self.owner, self.root, self.deadline, self.limits = owner, root, deadline, limits
        self.files, self.streams, self.members, self.expanded = {}, [], 0, 0

    def time(self):
        if time.monotonic() >= self.deadline: raise OriginalDataError('Retained original read deadline expired')

    def charge(self, size):
        self.time(); self.members += 1; self.expanded += size
        if self.members > self.limits['maximum_members'] or self.expanded > self.limits['maximum_expanded_bytes']:
            raise OriginalDataError('Retained original aggregate bound exceeded')

    def stream(self, reference):
        self.time(); reference = _ref(reference)
        stream = self.owner.open_archive(reference['path'], expected={**{k: reference[k] for k in ('sha256', 'bytes')}, 'mode': 0o644})
        self.streams.append(stream)
        return stream

    def capture(self, reference, *, metadata=False):
        reference = _ref(reference); path = reference['path']
        maximum = min(self.limits['maximum_member_bytes'], 16 * 1024 ** 2) if metadata else self.limits['maximum_member_bytes']
        if reference['bytes'] > maximum: raise OriginalDataError('Retained original member exceeds its bounded read size')
        if path in self.files:
            prior, raw = self.files[path]
            if prior != reference: raise OriginalDataError('Retained original path has conflicting independent references')
            if not metadata or raw is not None: return raw
        else: self.charge(reference['bytes'])
        stream = self.stream(reference); digest = hashlib.sha256(); total, chunks = 0, []
        try:
            while True:
                self.time(); block = stream.read(min(1024 * 1024, reference['bytes'] - total + 1))
                if not block: break
                total += len(block)
                if total > reference['bytes']: raise OriginalDataError('Retained original exceeds declared EOF')
                digest.update(block)
                if metadata: chunks.append(block)
            if total != reference['bytes'] or digest.hexdigest() != reference['sha256']:
                raise OriginalDataError('Retained original bytes differ from the selected original')
        finally: stream.close()
        raw = b''.join(chunks) if metadata else None
        self.files[path] = (reference, raw)
        return raw

    def document(self, reference): return _parse(self.capture(reference, metadata=True))

    def complete_tree(self, prefix, paths):
        """Enumerate only already anchored directories using the reviewed A API."""
        expected = {prefix: set()}
        for path in paths:
            parts = _relative(path).split('/'); directory = prefix
            for index, part in enumerate(parts):
                expected.setdefault(directory, set()).add(part)
                if index + 1 < len(parts):
                    directory += '/' + part; expected.setdefault(directory, set())
        for relative, names in expected.items():
            self.time()
            record = self.owner._directories.get(relative)
            if record is None: raise OriginalSourceError('Complete retained directory was not anchored')
            try: actual = self.owner._native.names(record['handle'])
            except BaseException as error:
                # names() is an explicit direct A operation. Pending NT work
                # must enter A's uncertain-owner state before any cleanup.
                self.owner._failure(error)
                if isinstance(error, AttributeError): raise OriginalSourceError('Unsupported actual input enumeration interface') from error
                raise
            if actual != sorted(names): raise OriginalDataError('Retained origin contains missing/undeclared directory entries')
        self.owner.check()


def _header_text(raw):
    head, _, tail = raw.partition(b'\0')
    if tail.strip(b'\0'): raise OriginalSourceError('Unsupported embedded tar header bytes')
    try: return head.decode('utf-8')
    except UnicodeError as error: raise OriginalSourceError('Unsupported tar path encoding') from error


def _octal(raw):
    raw = raw.strip(b'\0 ')
    if not raw or any(c not in b'01234567' for c in raw):
        raise OriginalSourceError('Unsupported tar numeric format')
    return int(raw, 8)


def _read_exact(stream, size, capture):
    chunks, total = [], 0
    while total < size:
        capture.time(); block = stream.read(min(1024 * 1024, size - total))
        if not block: raise OriginalDataError('Truncated retained archive')
        total += len(block); chunks.append(block)
    return b''.join(chunks)


def _scan_archive_members(stream, capture, manifest_name):
    """Bounded regular/PAX-path tar reader for the existing archive_tree emitter."""
    files, aliases, metadata, explicit, pending_path = {}, {}, {}, set(), None
    expanded = 0
    with gzip.GzipFile(fileobj=stream, mode='rb') as incoming:
        while True:
            capture.charge(512); header = _read_exact(incoming, 512, capture); expanded += 512
            if header == bytes(512):
                capture.charge(512); expanded += 512
                if pending_path is not None or _read_exact(incoming, 512, capture) != bytes(512):
                    raise OriginalDataError('Incomplete retained tar terminator')
                while True:
                    capture.time(); remaining = capture.limits['maximum_expanded_bytes'] - capture.expanded
                    tail = incoming.read(min(1024 * 1024, max(0, remaining) + 1))
                    if not tail: break
                    expanded += len(tail); capture.expanded += len(tail)
                    if tail.strip(b'\0') or expanded > capture.limits['maximum_expanded_bytes'] or capture.expanded > capture.limits['maximum_expanded_bytes']:
                        raise OriginalDataError('Unexpected/oversized retained tar trailer')
                break
            checksum = sum(header[:148]) + 8 * 32 + sum(header[156:])
            if checksum != _octal(header[148:156]): raise OriginalDataError('Retained tar header checksum differs')
            if header[257:265] != b'ustar\x0000': raise OriginalSourceError('Unsupported retained tar header format')
            kind, size, mode = header[156:157], _octal(header[124:136]), _octal(header[100:108])
            if size > capture.limits['maximum_member_bytes'] or expanded + size > capture.limits['maximum_expanded_bytes']:
                raise OriginalDataError('Retained tar member/expanded bound exceeded')
            name = _header_text(header[:100]); prefix = _header_text(header[345:500])
            if prefix: name = prefix + '/' + name
            if kind == b'x':
                if pending_path is not None or size > min(1024 * 1024, capture.limits['maximum_patch_bytes']):
                    raise OriginalSourceError('Unsupported retained PAX extension bound')
                capture.expanded += size
                if capture.expanded > capture.limits['maximum_expanded_bytes']: raise OriginalDataError('Retained PAX aggregate bound exceeded')
                raw = _read_exact(incoming, size, capture); cursor = 0
                while cursor < len(raw):
                    space = raw.find(b' ', cursor)
                    if space < 0 or space - cursor > 12 or not raw[cursor:space].isdigit(): raise OriginalDataError('Invalid retained PAX record')
                    length = int(raw[cursor:space]); end = cursor + length
                    if length <= space - cursor + 1 or end > len(raw) or raw[end - 1:end] != b'\n': raise OriginalDataError('Invalid retained PAX length')
                    key, sep, value = raw[space + 1:end - 1].partition(b'=')
                    if key != b'path' or not sep or pending_path is not None: raise OriginalSourceError('Unsupported retained PAX authority field')
                    try: pending_path = value.decode('utf-8')
                    except UnicodeError as error: raise OriginalDataError('Invalid retained PAX path') from error
                    cursor = end
            elif kind in (b'0', b'\0', b'5'):
                name = pending_path if pending_path is not None else name; pending_path = None
                directory = kind == b'5'
                if directory: name = name.rstrip('/')
                _relative(name)
                if name in explicit: raise OriginalDataError('Repeated retained tar member')
                explicit.add(name)
                for count in range(1, len(name.split('/')) + 1):
                    spelling = '/'.join(name.split('/')[:count]); item_kind = 'directory' if directory or count < len(name.split('/')) else 'file'
                    prior = aliases.setdefault(spelling.casefold(), (spelling, item_kind))
                    if prior != (spelling, item_kind): raise OriginalDataError('Retained tar path aliases/kinds conflict')
                if directory:
                    if size: raise OriginalDataError('Retained tar directory has data')
                else:
                    if name in files or mode not in (0o644, 0o755): raise OriginalDataError('Duplicate/unsupported retained tar file')
                    capture.charge(size); digest = hashlib.sha256(); remaining = size; chunks = []
                    if name == manifest_name and size > 16 * 1024 ** 2: raise OriginalDataError('Retained group manifest exceeds its bound')
                    while remaining:
                        block = _read_exact(incoming, min(1024 * 1024, remaining), capture)
                        remaining -= len(block); digest.update(block)
                        if name == manifest_name: chunks.append(block)
                    files[name] = {'sha256': digest.hexdigest(), 'bytes': size, 'mode': mode}
                    if name == manifest_name: metadata[name] = b''.join(chunks)
            else: raise OriginalSourceError('Unsupported linked/special retained tar member')
            padding = (-size) % 512
            capture.expanded += padding
            if capture.expanded > capture.limits['maximum_expanded_bytes']: raise OriginalDataError('Retained tar aggregate byte bound exceeded')
            if padding and _read_exact(incoming, padding, capture) != bytes(padding): raise OriginalDataError('Nonzero retained tar padding')
            expanded += size + padding
    if manifest_name not in metadata: raise OriginalDataError('Missing retained group manifest')
    manifest = _parse(metadata[manifest_name])
    if type(manifest) is not dict or type(manifest.get('schema_version')) is not int or manifest['schema_version'] != 1:
        raise OriginalSourceError('Unsupported retained group manifest schema')
    expected = _file_map(manifest.get('files'), transport=False)
    if expected != {name: row['sha256'] for name, row in files.items() if name != manifest_name}:
        raise OriginalDataError('Retained group manifest does not cover exact actual member bytes')
    return manifest, hashlib.sha256(metadata[manifest_name]).hexdigest(), files


def _archive_members(stream, capture, manifest_name):
    try: return _scan_archive_members(stream, capture, manifest_name)
    except (OriginalDataError, OriginalSourceError, OriginalOwnershipUncertain): raise
    except (zlib.error, OSError, EOFError, ValueError, OverflowError) as error:
        raise OriginalDataError('Malformed retained gzip/tar original') from error


def _record_member(members, root, reference, origin, member):
    absolute = _join(root, reference['path']); selected = dict(reference, path=absolute)
    fact = {'name': origin['name'], 'kind': origin['kind'], 'member': member}
    if absolute in members:
        if members[absolute]['reference'] != selected: raise OriginalDataError('Original membership reference conflicts')
        if fact not in members[absolute]['origins']: members[absolute]['origins'].append(fact)
    else: members[absolute] = {'reference': selected, 'origins': [fact]}


def _origin(capture, origin, members):
    if type(origin) is not dict or type(origin.get('name')) is not str or not _NAME.fullmatch(origin['name']):
        raise OriginalSourceError('Unsupported retained origin selection')
    kind = origin.get('kind')
    keys = ('name', 'kind', 'selection', 'receipt', 'payload_root') if kind == 'ci' else ('name', 'kind', 'selection', 'receipt', 'group_root', 'members')
    if kind not in ('ci', 'base'): raise OriginalSourceError('Unsupported original transport kind')
    _fields(origin, keys, 'retained origin')
    selection = capture.document(origin['selection']); receipt = capture.document(origin['receipt'])
    common = {'name': origin['name'], 'kind': kind,
        'selection': dict(_ref(origin['selection']), path=_join(capture.root, origin['selection']['path'])),
        'receipt': dict(_ref(origin['receipt']), path=_join(capture.root, origin['receipt']['path']))}
    if kind == 'ci':
        facts = _ci_metadata(selection, receipt); prefix = _relative(origin['payload_root']); files = facts.pop('files')
        for name, row in files.items():
            reference = {'path': prefix + '/' + name, 'sha256': row['sha256'], 'bytes': row['size']}
            capture.capture(reference); _record_member(members, capture.root, reference, origin, name)
        capture.complete_tree(prefix, files)
        return dict(common, **facts, payload_root=_join(capture.root, prefix))
    facts = _base_metadata(selection, receipt); prefix = _relative(origin['group_root'])
    # Exact archive EOF is required by A. Existing original group file hashes
    # alone do not carry sizes, so select the original reference records as
    # retained members with the reserved group/NAME namespace.
    if type(origin['members']) is not list or not origin['members'] or len(origin['members']) > 16000:
        raise OriginalDataError('Finite original base member/reference records are required')
    refs, selected = {}, []
    for item in origin['members']:
        _fields(item, ('member', 'reference'), 'base original membership'); _relative(item['member'])
        reference = _ref(item['reference'])
        if item['member'] in refs: raise OriginalDataError('Repeated original base member')
        refs[item['member']] = reference
        if item['member'].startswith('group/'):
            name = item['member'][6:]
            if name not in facts['names'] or reference['path'] != prefix + '/' + name or reference['sha256'] != facts['files'][name]:
                raise OriginalDataError('Original group reference differs from complete acquisition')
        else: selected.append((item['member'], reference))
    if {key for key in refs if key.startswith('group/')} != {'group/' + name for name in facts['names']}:
        raise OriginalDataError('Original group needs all three independently sized references')
    binary, source, checksum = facts.pop('names')
    sums_raw = capture.capture(refs['group/' + checksum], metadata=True)
    try: lines = sums_raw.decode('utf-8').splitlines()
    except UnicodeError as error: raise OriginalDataError('Invalid retained group checksum text') from error
    sums = {}
    for line in lines:
        parts = line.split('  ')
        if len(parts) != 2 or parts[1] in sums: raise OriginalDataError('Invalid/duplicate retained group checksum')
        sums[_relative(parts[1])] = _pin(parts[0])
    if sums != {name: facts['files'][name] for name in (binary, source)}:
        raise OriginalDataError('Original group pair checksum differs')
    archive_facts = {}
    for role, name, manifest_name in (('binary', binary, 'sdk.json'), ('sources', source, 'sources.json')):
        reference = refs['group/' + name]
        # Hash in finite chunks first; the same native deny-writer handle stays
        # held for the subsequent bounded tar traversal and final check/close.
        if reference['bytes'] > capture.limits['maximum_archive_bytes']: raise OriginalDataError('Original group archive exceeds bound')
        stream = capture.stream(reference); digest = hashlib.sha256(); total = 0
        try:
            while True:
                capture.time(); block = stream.read(min(1024 * 1024, reference['bytes'] - total + 1))
                if not block: break
                total += len(block); digest.update(block)
                if total > reference['bytes']: raise OriginalDataError('Original archive exceeds selected EOF')
            if total != reference['bytes'] or digest.hexdigest() != reference['sha256']: raise OriginalDataError('Original group archive differs')
            stream.seek(0); archive_facts[role] = _archive_members(stream, capture, manifest_name)
        finally: stream.close()
        _record_member(members, capture.root, reference, origin, 'group/' + name)
    sdk, _, binary_files = archive_facts['binary']; sources, source_pin, source_files = archive_facts['sources']
    if (sdk.get('recipe_id') != facts['recipe'] or sources.get('recipe_id') != facts['recipe'] or sdk.get('sources_sha256') != source_pin):
        raise OriginalDataError('Original complete binary/source/recipe inventories do not join')
    for member, reference in selected:
        role, _, name = member.partition('/')
        if role not in ('binary', 'sources') or not name: raise OriginalSourceError('Unsupported original base member namespace')
        actual = (binary_files if role == 'binary' else source_files).get(name)
        if actual is None or actual['sha256'] != reference['sha256'] or actual['bytes'] != reference['bytes']:
            raise OriginalDataError('Selected original document is not an actual complete-group member')
        capture.capture(reference); _record_member(members, capture.root, reference, origin, member)
    _record_member(members, capture.root, refs['group/' + checksum], origin, 'group/' + checksum)
    capture.complete_tree(prefix, (binary, source, checksum))
    return dict(common, **facts, group_root=_join(capture.root, prefix), source_manifest_sha256=source_pin)


class IssuedRetainedOriginals:
    __slots__ = ()
    def __new__(cls, *args, **kwargs):
        raise OriginalSourceError('Use the actual native retained-original factory')


def require_retained_originals(token):
    if type(token) is not IssuedRetainedOriginals or token not in _ISSUED:
        raise OriginalSourceError('Unissued retained-original capability')
    return _parse(_ISSUED[token])


def require_original_membership(token, refs):
    summary = require_retained_originals(token)
    if type(refs) is not list or not 1 <= len(refs) <= 16000: raise OriginalDataError('Finite required-original references are required')
    result = []
    for reference in refs:
        if type(reference) is not dict or set(reference) not in ({'path', 'sha256'}, {'path', 'sha256', 'bytes'}):
            raise OriginalSourceError('Unsupported required-original reference fields')
        _absolute(reference['path']); _pin(reference['sha256'])
        fact = summary['members'].get(reference['path'])
        if fact is None or any(fact['reference'][name] != value or type(fact['reference'][name]) is not type(value) for name, value in reference.items()):
            raise OriginalDataError('Required document was not captured as an original member')
        result.append(copy.deepcopy(fact))
    return result


def _read_consistent(reference, maximum):
    """Bound bootstrap/source bytes; only later anchored reads grant facts."""
    reference = _ref(reference, absolute=True, size=False); path = Path(reference['path'])
    for current in reversed((path, *path.parents)):
        state = current.lstat()
        if (stat.S_ISLNK(state.st_mode) or getattr(state, 'st_file_attributes', 0) & 0x400 or
                not (stat.S_ISREG(state.st_mode) if current == path else stat.S_ISDIR(state.st_mode)) or
                current == path and state.st_nlink != 1):
            raise OriginalDataError('Bootstrap/source reference must be ordinary and unaliased')
    before = path.lstat()
    if before.st_size > maximum: raise OriginalDataError('Bootstrap/source byte bound exceeded')
    identity = lambda state: (state.st_dev, state.st_ino, state.st_size, state.st_mtime_ns, state.st_ctime_ns,
        state.st_nlink, getattr(state, 'st_file_attributes', 0))
    with path.open('rb') as stream:
        opened = os.fstat(stream.fileno()); raw = stream.read(maximum + 1); after = os.fstat(stream.fileno())
    if (identity(before) != identity(opened) or identity(before) != identity(after) or identity(before) != identity(path.lstat()) or
            len(raw) > maximum or hashlib.sha256(raw).hexdigest() != reference['sha256']):
        raise OriginalDataError('Bootstrap/source identity or independent hash changed')
    return raw


def _read_source(reference):
    """Read one fixed ordinary source file; this grants no native authority."""
    path = Path(reference['path'])
    if not path.is_absolute() or reference['bytes'] > 1024 * 1024:
        raise OriginalSourceError('Unsupported fixed provider source path/size')
    for current in reversed((path, *path.parents)):
        state = current.lstat()
        if (stat.S_ISLNK(state.st_mode) or getattr(state, 'st_file_attributes', 0) & 0x400 or
                not (stat.S_ISREG(state.st_mode) if current == path else stat.S_ISDIR(state.st_mode)) or
                current == path and state.st_nlink != 1):
            raise OriginalSourceError('Fixed provider source must be ordinary and unaliased')
    identity = lambda state: (state.st_dev, state.st_ino, state.st_size, state.st_mtime_ns,
        state.st_ctime_ns, state.st_nlink, getattr(state, 'st_file_attributes', 0))
    before = path.lstat()
    if before.st_size != reference['bytes']:
        raise OriginalSourceError('Fixed provider source byte count differs')
    with path.open('rb') as stream:
        opened = os.fstat(stream.fileno()); raw = stream.read(reference['bytes'] + 1)
        after = os.fstat(stream.fileno())
    if (identity(before) != identity(opened) or identity(before) != identity(after) or
            identity(before) != identity(path.lstat()) or len(raw) != reference['bytes'] or
            hashlib.sha256(raw).hexdigest() != reference['sha256']):
        raise OriginalSourceError('Fixed provider source bytes or physical identity changed')
    return raw


def _compile_provider_sources(bundle):
    """Private inert seam; never issues Q, native readers or original tokens.

    Only the no-argument fixed loader supplies production bytes here. Initial
    namespace occupancy rejects, even for a same-path or apparently genuine
    preload. The B-owned A loader is the sole actual-A compiler.
    """
    import builtins
    import sys
    import types
    _fields(bundle, _PROVIDER_ORDER, 'fixed provider source bundle')
    reserved = (*_PROVIDER_ORDER, 'appended_engine_windows_publication')
    if any(name in sys.modules for name in reserved):
        raise OriginalSourceError('Unknown preloaded provider dependency or native reader')
    modules = {}
    original_import = builtins.__import__
    def fixed_import(name, globals=None, locals=None, fromlist=(), level=0):
        if level: raise OriginalSourceError('Unsupported relative provider source import')
        if name in _PROVIDER_ORDER:
            if name not in modules or sys.modules.get(name) is not modules[name]:
                raise OriginalSourceError('Unowned or forward provider dependency')
            return modules[name]
        if name.split('.')[0] not in _SOURCE_IMPORTS:
            raise OriginalSourceError('Unsupported provider source import dependency: ' + name)
        return original_import(name, globals, locals, fromlist, level)
    try:
        for name in _PROVIDER_ORDER:
            path, raw = bundle[name]
            if type(path) is not str or type(raw) is not bytes: raise OriginalSourceError('Verified source bytes/path required')
            if name in sys.modules: raise OriginalSourceError('Provider module namespace changed during bootstrap')
            module = types.ModuleType(name); module.__file__ = path; module.__package__ = ''
            module.__dict__['__builtins__'] = dict(vars(builtins), __import__=fixed_import)
            if sys.modules.setdefault(name, module) is not module:
                raise OriginalSourceError('Provider module namespace changed before reservation')
            exec(compile(raw, path, 'exec', dont_inherit=True), module.__dict__)
            if sys.modules.get(name) is not module:
                raise OriginalSourceError('Provider module registration changed during bootstrap')
            modules[name] = module
        if any(sys.modules.get(name) is not module or getattr(module, '__file__', None) != bundle[name][0]
                for name, module in modules.items()):
            raise OriginalSourceError('Provider dependency registration or source filename changed during bootstrap')
        return modules
    except BaseException:
        # A failed reservation remains a blocker. Never overwrite, restore or
        # delete a foreign slot after uncertain bootstrap ownership.
        raise


def _capture_source_provider():
    """Return the one fixed B provider; never observe or qualify native inputs."""
    import sys
    global _PROVIDER_CACHE
    with _PROVIDER_LOCK:
        try:
            bundle = {name: (reference['path'], _read_source(reference))
                for name, reference in _PROVIDER_SOURCES.items()}
            if _PROVIDER_CACHE is None:
                _PROVIDER_CACHE = _compile_provider_sources(bundle)
            else:
                _fields(_PROVIDER_CACHE, _PROVIDER_ORDER, 'owned provider cache')
                for name, module in _PROVIDER_CACHE.items():
                    if (sys.modules.get(name) is not module or
                            getattr(module, '__file__', None) != _PROVIDER_SOURCES[name]['path']):
                        raise OriginalSourceError('Owned provider module registration or source path changed')
            return _PROVIDER_CACHE['appended_engine_windows_source_replay']
        except (OSError, ImportError, SyntaxError, ValueError) as error:
            if isinstance(error, OriginalSourceError): raise
            raise OriginalSourceError('The fixed source-backed B provider is unavailable') from error


def _current_input_identity(source_identity):
    _fields(source_identity, _SOURCE_FILES, 'complete actual input source identity')
    for pin in source_identity.values(): _pin(pin)
    expected = {name: _CURRENT_SOURCE_CATALOGUE[name]['sha256'] for name in _SOURCE_FILES}
    if source_identity != expected:
        raise OriginalSourceError('Input source identity differs from the complete current fixed source map')
    return expected


def _require_current_adapter(native):
    import sys
    path = str(Path(_CURRENT_SOURCE_CATALOGUE['tools/appended_engine_windows_publication.py']['path']))
    if (sys.modules.get('appended_engine_windows_publication') is not native or
            getattr(native, '__file__', None) != path or
            getattr(native, 'INPUT_SOURCE_FILES', None) != _SOURCE_FILES or
            getattr(native, 'INPUT_CONTRACT_SHA256', None) != _CURRENT_SOURCE_CATALOGUE['tools/appended_engine_windows_contract.py']['sha256'] or
            getattr(native, 'CONTRACT_SHA256', None) != _CURRENT_SOURCE_CATALOGUE['tools/appended_engine_windows_contract.py']['sha256']):
        raise OriginalSourceError('B returned a different actual reader filename or current source contract')
    for name in ('inspect_input_subject', 'admit_input_qualification'):
        function = getattr(native, name, None)
        if (getattr(function, '__module__', None) != 'appended_engine_windows_publication' or
                getattr(getattr(function, '__code__', None), 'co_filename', None) != path):
            raise OriginalSourceError('Actual input reader code filename differs from its current source')
    if getattr(native, 'process_tree', None) is not _PROVIDER_CACHE['process_tree']:
        raise OriginalSourceError('Actual input reader uses a different process authority instance')
    return native


def _native_adapter(source_identity):
    """Reuse B's actual A instance for Q, input readers and later publication."""
    _current_input_identity(source_identity)
    try:
        for name in _SOURCE_FILES:
            _read_source(_CURRENT_SOURCE_CATALOGUE[name])
        provider = _capture_source_provider()
        return _require_current_adapter(provider._native_input_reader())
    except (OSError, ImportError, AttributeError, ValueError) as error:
        if isinstance(error, OriginalSourceError): raise
        raise OriginalSourceError('The B-owned actual native retained-input adapter is unavailable') from error


def _admit_input_subject(profile):
    """Shared fixed actual-A admission; never accept a supplied reader/context."""
    if (os.name != 'nt' or platform.system() != 'Windows' or platform.machine().casefold() not in ('amd64', 'x86_64') or struct.calcsize('P') != 8):
        raise OriginalSourceError('Actual native Windows x64 retained-input semantics are required')
    _fields(profile, ('qualification', 'source_identity', 'runtime_identity'), 'actual retained-input admission')
    _ref(profile['qualification'], absolute=True, size=False)
    native = _native_adapter(profile['source_identity'])
    try:
        actual = native.inspect_input_subject()
        if actual['source_identity'].get('tools/appended_engine_windows_publication.py') != A_SOURCE_SHA256:
            raise OriginalSourceError('A source differs from the reviewed coherent input-reader source binding')
        if profile['source_identity'] != actual['source_identity'] or profile['runtime_identity'] != actual['runtime_identity']:
            raise OriginalDataError('Declared input subject differs from actual native source/runtime observations')
        qualification = native.admit_input_qualification(profile['qualification'], **actual)
        return native, qualification, copy.deepcopy(actual)
    except native.OwnershipUncertain as error:
        _UNCERTAIN.append((native, None))
        raise OriginalOwnershipUncertain('Native input qualification ownership is uncertain') from error
    except (native.PublicationError, OSError) as error:
        raise OriginalDataError('Original input qualification/subject could not be admitted') from error


def admit_retained_originals(request_ref, *, deadline, limits):
    """Own actual A/Q/runtime/source reads, close them, then issue one token."""
    if (os.name != 'nt' or platform.system() != 'Windows' or platform.machine().casefold() not in ('amd64', 'x86_64') or struct.calcsize('P') != 8):
        raise OriginalSourceError('Actual native Windows x64 retained-input semantics are required')
    _ref(request_ref, absolute=True, size=False)
    if type(deadline) not in (int, float) or not math.isfinite(deadline) or time.monotonic() >= deadline:
        raise OriginalDataError('An unexpired finite absolute read deadline is required')
    _fields(limits, _LIMIT_BOUNDS, 'retained-original input limits')
    if any(type(limits[key]) is not int or not 1 <= limits[key] <= maximum for key, maximum in _LIMIT_BOUNDS.items()):
        raise OriginalDataError('Retained-original input limit exceeds its finite bound')
    # Deliberately lazy: importing this module or exercising pure checks never
    # imports A, executes a helper, queries a tool, or touches native inputs.
    native = None
    owner = None
    try:
        raw = _read_consistent(request_ref, min(limits['maximum_member_bytes'], 16 * 1024 ** 2))
        request = _parse(raw)
        _fields(request, ('schema_version', 'kind', 'root', 'input', 'origins'), 'retained-original request')
        if type(request['schema_version']) is not int or request['schema_version'] != 1 or request['kind'] != REQUEST_KIND:
            raise OriginalSourceError('Unsupported retained-original request schema')
        root = _absolute(request['root'])
        native, qualification, actual = _admit_input_subject(request['input'])
        if any(not hasattr(native, name) for name in ('inspect_input_subject', 'admit_input_qualification', 'AnchoredInputs', 'OwnershipUncertain', 'PublicationError')):
            raise OriginalSourceError('Unsupported retained-input adapter interface')
        owner = native.AnchoredInputs.open_existing(root, qualification=qualification, limits=limits, deadline=deadline)
        if type(owner) is not native.AnchoredInputs: raise OriginalSourceError('Actual anchored-input owner required')
        capture = _Capture(owner, root, deadline, limits)
        try: relative_request = PureWindowsPath(request_ref['path']).relative_to(PureWindowsPath(root)).as_posix()
        except ValueError as error: raise OriginalDataError('The selected request is outside its owned root') from error
        captured = capture.capture({'path': relative_request, 'sha256': request_ref['sha256'], 'bytes': len(raw)}, metadata=True)
        if captured != raw: raise OriginalDataError('The request changed before native anchored capture')
        if type(request['origins']) is not list or not 1 <= len(request['origins']) <= 128:
            raise OriginalDataError('A finite nonempty original-origin selection is required')
        names, origins, members = set(), [], {}
        for origin in request['origins']:
            facts = _origin(capture, origin, members)
            if facts['name'] in names: raise OriginalDataError('Repeated original origin name')
            names.add(facts['name']); origins.append(facts)
        owner.check()
        summary = {'schema_version': 1, 'kind': SUMMARY_KIND, 'request': copy.deepcopy(request_ref),
            'root': root, 'input': {'qualification': copy.deepcopy(request['input']['qualification']),
                **actual, 'filesystem': owner.filesystem}, 'origins': origins, 'members': members, 'readers_closed': True}
        encoded = _encoded(summary)
        owner.close()
        if not owner.closed or owner.uncertain: raise OriginalOwnershipUncertain('Original input reader closure is unconfirmed')
        if time.monotonic() >= deadline: raise OriginalDataError('Retained original deadline expired before issuance')
        token = object.__new__(IssuedRetainedOriginals)
        _ISSUED[token] = encoded
        return token
    except BaseException as error:
        if owner is not None and owner.uncertain:
            _UNCERTAIN.append((native, owner))
            raise OriginalOwnershipUncertain('Retain uncertain original input ownership; no capability issued') from error
        if owner is not None and not owner.closed:
            try: owner.close()
            except BaseException as cleanup:
                _UNCERTAIN.append((native, owner))
                raise OriginalOwnershipUncertain('Retain uncertain original input ownership; no capability issued') from cleanup
        if native is not None and isinstance(error, native.OwnershipUncertain):
            _UNCERTAIN.append((native, owner)); raise OriginalOwnershipUncertain('Native original input ownership is uncertain') from error
        if isinstance(error, FileNotFoundError): raise OriginalDataError('Selected actual original input is absent') from error
        if isinstance(error, (OSError, EOFError, zlib.error)) or native is not None and isinstance(error, native.PublicationError):
            raise OriginalDataError('Actual original input/qualification could not be admitted') from error
        raise
