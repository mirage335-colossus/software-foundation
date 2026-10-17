"""Private source proposal: bounded version bytes, never native admission.

Only CMake's documented 3.31 capabilities format is implemented. The record
validator establishes declaration/byte consistency. In particular serialized
Job flags, qualification refs and caller-supplied expected data cannot establish
an original execution. A future native constructor must bind actual private
Workspace/JoinedStage/log/runtime authority before this data can become facts.
There are no filesystem reads, subprocesses, C2 imports or publication imports.
"""
from __future__ import annotations

import hashlib
import json

import appended_engine_windows_dependency_proof as proof

METHOD = 'cmake-capabilities-3.31-final-v1'
KIND = 'foundation-native-engine-windows-tool-version-observation-v1'
MAX_BYTES = 65536
MAX_DEPTH = 16
MAX_NODES = 4096


class MissingMethod(ValueError):
    """A format is unfinished source, not an observed incompatible version."""


def _hash(raw):
    return hashlib.sha256(raw).hexdigest()


def _fields(value, names, label):
    if type(value) is not dict or set(value) != set(names):
        raise ValueError('Closed ' + label + ' fields required')


def _int(value, label, minimum=0, maximum=2**31 - 1):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError('Bounded exact integer required: ' + label)


def _pin(value):
    if (type(value) is not str or len(value) != 64 or value == '0' * 64 or
            any(c not in '0123456789abcdef' for c in value)):
        raise ValueError('Independent nonzero SHA256 required')


def _ref(value):
    _fields(value, ('path', 'sha256'), 'reference')
    proof.windows_path(value['path'])
    _pin(value['sha256'])


def _environment(value):
    required, optional = {'SystemRoot', 'PATH'}, {'TEMP', 'TMP'}
    if (type(value) is not dict or not required <= set(value) <= required | optional or
            bool(set(value) & optional) != (optional <= set(value))):
        raise ValueError('Closed original version-query environment required')
    for name in set(value) - {'PATH'}:
        proof.windows_path(value[name])
    if type(value['PATH']) is not str:
        raise ValueError('Explicit finite PATH required')
    directories = value['PATH'].split(';')
    if not 1 <= len(directories) <= 64 or len({x.casefold() for x in directories}) != len(directories):
        raise ValueError('Unique bounded original PATH required')
    for directory in directories:
        proof.windows_path(directory)


def _json(raw):
    if type(raw) is not bytes or not 1 <= len(raw) <= MAX_BYTES or raw.startswith(b'\xef\xbb\xbf'):
        raise ValueError('Bounded original UTF-8 JSON bytes required')
    # Check nesting before json allocates a recursive container graph.
    depth, quoted, escaped = 0, False, False
    lexemes, scalar = 0, False
    for byte in raw:
        if quoted:
            if escaped:
                escaped = False
            elif byte == 92:
                escaped = True
            elif byte == 34:
                quoted = False
        elif byte == 34:
            quoted = True
            lexemes += 1  # Count object keys too: a conservative allocation cap.
            scalar = False
        elif byte in (91, 123):
            depth += 1
            lexemes += 1
            scalar = False
            if depth > MAX_DEPTH:
                raise ValueError('Original JSON nesting exceeds bound')
        elif byte in (93, 125):
            depth -= 1
            scalar = False
            if depth < 0:
                raise ValueError('Unbalanced original JSON')
        elif byte in (9, 10, 13, 32, 44, 58):
            scalar = False
        elif not scalar:
            lexemes += 1
            scalar = True
        if lexemes > MAX_NODES:
            raise ValueError('Original JSON token count exceeds allocation bound')
    if depth or quoted:
        raise ValueError('Incomplete original JSON')

    def integer(text):
        if len(text.lstrip('-')) > 10:
            raise ValueError('Original JSON integer exceeds bound')
        result = int(text)
        if not -(2**31) <= result <= 2**31 - 1:
            raise ValueError('Original JSON integer exceeds bound')
        return result

    def forbidden(text):
        raise ValueError('Noninteger/nonfinite original JSON number')

    def pairs(items):
        result = {}
        for name, item in items:
            if name in result:
                raise ValueError('Duplicate original JSON key')
            result[name] = item
        return result

    value = json.loads(raw.decode('utf-8'), object_pairs_hook=pairs,
                       parse_int=integer, parse_float=forbidden, parse_constant=forbidden)
    count, pending = 0, [value]
    while pending:
        item = pending.pop()
        count += 1
        if count > MAX_NODES:
            raise ValueError('Original JSON node count exceeds bound')
        if type(item) is dict:
            pending.extend(item.values())
        elif type(item) is list:
            pending.extend(item)
    return value


def extract_observed_version(role, method, raw_log):
    """Derive a version from whole captured bytes; no expected version is input."""
    if role != 'cmake' or method != METHOD:
        raise MissingMethod('windows-tool-version-method:' + str(role))
    value = _json(raw_log)
    allowed = {'version', 'generators', 'fileApi', 'serverMode', 'tls', 'debugger'}
    required = allowed - {'fileApi'}
    if type(value) is not dict or not required <= set(value) <= allowed:
        raise ValueError('Documented CMake 3.31 capabilities root required')
    if type(value['generators']) is not list or not value['generators'] or any(
            type(item) is not dict for item in value['generators']):
        raise ValueError('CMake generator capability list required')
    if 'fileApi' in value and type(value['fileApi']) is not dict:
        raise ValueError('CMake fileApi object required')
    for name in ('serverMode', 'tls', 'debugger'):
        if type(value[name]) is not bool:
            raise ValueError('CMake capability boolean required')
    if value['serverMode'] is not False:
        raise ValueError('CMake 3.31 server mode must be false')
    version = value['version']
    _fields(version, ('string', 'major', 'minor', 'patch', 'suffix', 'isDirty'), 'CMake version')
    for name in ('major', 'minor', 'patch'):
        _int(version[name], 'CMake ' + name)
    if (version['major'] != 3 or version['minor'] != 31 or version['suffix'] != '' or
            type(version['isDirty']) is not bool or version['isDirty']):
        raise ValueError('Reviewed CMake 3.31 clean final release required')
    release = '.'.join(str(version[name]) for name in ('major', 'minor', 'patch'))
    if version['string'] != release:
        raise ValueError('CMake numeric and string release disagree')
    return release


def parse_observation_record(raw_receipt, receipt_sha256, raw_log, expected):
    """Pure closed-record join, NOT original producer or native Job authority.

    expected comes independently from selected/admitted bytes and source policy,
    never the record. It deliberately contains no expected/observed version.
    """
    _fields(expected, ('role', 'method', 'program', 'inventory_subject_sha256',
        'collector', 'cwd', 'environment', 'limits', 'output_subject_sha256'), 'independent selection')
    _pin(receipt_sha256)
    if type(raw_receipt) is not bytes or not 1 <= len(raw_receipt) <= MAX_BYTES:
        raise ValueError('Bounded original observation receipt required before hashing')
    if _hash(raw_receipt) != receipt_sha256:
        raise ValueError('Original observation receipt pin differs')
    value = _json(raw_receipt)
    _fields(value, ('schema_version', 'kind', 'target', 'role', 'method', 'program',
        'inventory_subject_sha256', 'collector', 'command', 'log', 'job',
        'output_subject_sha256'), 'observation')
    for name, wanted in (('schema_version', 1), ('kind', KIND), ('target', proof.TARGET)):
        if type(value[name]) is not type(wanted) or value[name] != wanted:
            raise ValueError('Wrong observation ' + name)
    for name in ('role', 'method', 'program', 'inventory_subject_sha256', 'collector', 'output_subject_sha256'):
        if proof.encoded(value[name]) != proof.encoded(expected[name]):
            raise ValueError('Observation differs from independent ' + name)
    _ref(value['program'])
    _pin(value['inventory_subject_sha256'])
    _pin(value['output_subject_sha256'])
    if value['role'] != 'cmake' or value['method'] != METHOD:
        raise MissingMethod('windows-tool-version-method:' + str(value['role']))
    if value['program']['path'].rsplit('/', 1)[-1] != 'cmake.exe':
        raise ValueError('Selected CMake program role required')
    collector = value['collector']
    _fields(collector, ('program', 'runtime_subject_sha256', 'sources', 'qualification'), 'collector')
    _ref(collector['program']); _pin(collector['runtime_subject_sha256']); _ref(collector['qualification'])
    if type(collector['sources']) is not list or not 1 <= len(collector['sources']) <= 64:
        raise ValueError('Finite original collector source closure required')
    seen = set()
    for source in collector['sources']:
        _ref(source)
        if source['path'].casefold() in seen:
            raise ValueError('Unique collector source paths required')
        seen.add(source['path'].casefold())
    command = value['command']
    _fields(command, ('program', 'argv', 'cwd', 'environment'), 'command')
    wanted_command = {'program': expected['program'],
        'argv': [expected['program']['path'], '-E', 'capabilities'],
        'cwd': expected['cwd'], 'environment': expected['environment']}
    if proof.encoded(command) != proof.encoded(wanted_command):
        raise ValueError('Fixed source-owned version command differs')
    proof.windows_path(command['cwd'])
    _environment(command['environment'])
    log = value['log']
    _fields(log, ('path', 'sha256', 'bytes', 'mode'), 'original closed log')
    _ref({name: log[name] for name in ('path', 'sha256')})
    _int(log['bytes'], 'closed log bytes', 1, MAX_BYTES)
    if (type(log['mode']) is not int or log['mode'] != 0o644 or type(raw_log) is not bytes or
            log['bytes'] != len(raw_log) or log['sha256'] != _hash(raw_log)):
        raise ValueError('Complete original log bytes/hash/mode differ')
    _fields(expected['limits'], ('wall_milliseconds', 'maximum_processes',
        'maximum_output_bytes', 'maximum_log_bytes'), 'original finite limits')
    for name in expected['limits']:
        _int(expected['limits'][name], name, 1)
    if len(raw_log) > expected['limits']['maximum_log_bytes']:
        raise ValueError('Original log exceeds selected limit')
    proof._job(value['job'], command)  # Pure consistency only, exactly as D's verifier.
    if value['job']['peak_output_bytes'] < len(raw_log):
        raise ValueError('Original output observation is smaller than its closed log')
    for name, selected in (('wall_limit_milliseconds', 'wall_milliseconds'),
            ('process_limit', 'maximum_processes'), ('output_limit_bytes', 'maximum_output_bytes')):
        if value['job'][name] != expected['limits'][selected]:
            raise ValueError('Original Job differs from selected limit')
    release = extract_observed_version(value['role'], value['method'], raw_log)
    return {'role': value['role'], 'version': release,
            'receipt_sha256': receipt_sha256, 'log_sha256': log['sha256'],
            'native_admitted': False}
