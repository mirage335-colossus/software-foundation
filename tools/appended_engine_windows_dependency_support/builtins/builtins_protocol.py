"""Bounded pure raw-log parser candidate. It grants no original/native authority.

The caller supplies only the source-selected role/method and complete original
stdout/stderr log bytes. It cannot supply an expected or observed version. No
emitter is imported, evaluated or invoked; no project module is imported.
"""

import json

from protocol_contract import MissingMethod, explicit_path
from python import parser as python_parser
from perl import parser as perl_parser
from ruby import parser as ruby_parser


MAX_BYTES = 4096
MAX_DEPTH = 8
MAX_TOKENS = 128
_METHODS = {'python': python_parser, 'perl': perl_parser, 'ruby': ruby_parser}


def _lexical_bound(text):
    """Conservative token/depth ceiling before json allocates an object graph."""
    depth = 0
    tokens = 0
    quoted = escaped = scalar = False
    for character in text:
        if quoted:
            if escaped:
                escaped = False
            elif character == '\\':
                escaped = True
            elif character == '"':
                quoted = False
            continue
        if character == '"':
            quoted = True
            scalar = False
            tokens += 1
        elif character in '{[':
            depth += 1
            tokens += 1
            scalar = False
            if depth > MAX_DEPTH:
                raise ValueError('builtin observation nesting exceeds bound')
        elif character in '}]':
            depth -= 1
            scalar = False
            if depth < 0:
                raise ValueError('builtin observation has unmatched closing token')
        elif character in ' \t\r\n,:':
            scalar = False
        elif not scalar:
            scalar = True
            tokens += 1
        if tokens > MAX_TOKENS:
            raise ValueError('builtin observation lexical tokens exceed bound')
    if quoted or depth:
        raise ValueError('builtin observation is incomplete')


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('builtin observation contains a duplicate key')
        result[key] = value
    return result


def _parse_int(value):
    digits = value[1:] if value.startswith('-') else value
    if len(digits) > 10:
        raise ValueError('builtin observation integer spelling exceeds bound')
    number = int(value)
    if not -2147483648 <= number <= 2147483647:
        raise ValueError('builtin observation integer exceeds bound')
    return number


def _not_number(value):
    raise ValueError('builtin observation accepts exact integers only')


def decode_raw(raw_log):
    if type(raw_log) is not bytes or not 1 <= len(raw_log) <= MAX_BYTES:
        raise ValueError('complete builtin raw log bytes exceed bound')
    try:
        text = raw_log.decode('utf-8', errors='strict')
    except UnicodeDecodeError as error:
        raise ValueError('builtin observation is not strict UTF-8') from error
    _lexical_bound(text)
    try:
        value = json.loads(text, object_pairs_hook=_pairs, parse_int=_parse_int,
                           parse_float=_not_number, parse_constant=_not_number)
    except json.JSONDecodeError as error:
        raise ValueError('builtin observation must be one whole JSON document') from error
    if type(value) is not dict:
        raise ValueError('builtin observation must be an object')
    return value


def _method(role, method):
    if type(role) is not str or type(method) is not str:
        raise ValueError('builtin role/method must be strings')
    parser = _METHODS.get(role)
    if parser is None or method != parser.METHOD:
        raise MissingMethod('windows-runtime-version-method:' + role)
    return parser


def parse_numeric_observation(role, method, raw_log):
    """Independent numeric fact, never sufficient for final H admission."""
    return _method(role, method).observed_numeric(decode_raw(raw_log))


def parse_final_builtin_version(role, method, raw_log):
    """Independent final version where the documented method establishes it."""
    return _method(role, method).validate(decode_raw(raw_log))


def version_argv(role, method, program_path, emitter_path):
    program_path = explicit_path(program_path, 'version program')
    emitter_path = explicit_path(emitter_path, 'version emitter')
    return _method(role, method).argv(program_path, emitter_path)


def closed_environment(system_root, path_directories, temporary_directory):
    """Pure declaration builder; no ambient env and no native path admission."""
    system_root = explicit_path(system_root, 'SystemRoot')
    temporary_directory = explicit_path(temporary_directory, 'temporary directory')
    if type(path_directories) not in (list, tuple) or not 1 <= len(path_directories) <= 64:
        raise ValueError('PATH requires a finite explicit directory list')
    paths = [explicit_path(value, 'PATH directory') for value in path_directories]
    if any(';' in value for value in paths) or len(set(value.casefold() for value in paths)) != len(paths):
        raise ValueError('PATH directories require unique unambiguous declarations')
    result = {'SystemRoot': system_root, 'PATH': ';'.join(paths),
              'TEMP': temporary_directory, 'TMP': temporary_directory}
    if sum(len(key) + len(value) + 2 for key, value in result.items()) + 1 > 16384:
        raise ValueError('closed environment exceeds conservative source bound')
    return result
