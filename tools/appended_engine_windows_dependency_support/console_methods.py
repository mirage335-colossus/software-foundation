"""Pure fixed Ninja/gperf console methods derived from pinned upstream Source.

This module reads and runs nothing. Its numeric results do not authenticate a
program, native process, output log, or final admission. The actual issuer owns
those subjects and applies the existing project numeric baseline afterward.
See API.md for the finite upstream printer compatibility and source provenance.
"""

import re


MAX_LOG_BYTES = 4096
_NUMERIC = re.compile(r'[1-9][0-9]*\.[0-9]+(?:\.[0-9]+){0,2}', re.ASCII)
_METHODS = (
    ('ninja', 'ninja-version-release-line-v1'),
    ('gperf', 'gperf-3.1-version-release-banner-v1'),
)
_GPERF_TAIL = (
    'Copyright (C) 1989-2017 Free Software Foundation, Inc.\n'
    'License GPLv3+: GNU GPL version 3 or later <http://gnu.org/licenses/gpl.html>\n'
    'This is free software: you are free to change and redistribute it.\n'
    'There is NO WARRANTY, to the extent permitted by law.\n'
    'Written by Douglas C. Schmidt and Bruno Haible.\n'
)


class MissingMethod(ValueError):
    """The requested role/method has no reviewed Source semantics here."""


def method_for(role):
    """Select one fixed method without accepting a version or vendor label."""
    if type(role) is not str or not 1 <= len(role) <= 128:
        raise ValueError('Bounded exact version role required')
    for candidate, method in _METHODS:
        if role == candidate:
            return method
    raise MissingMethod('windows-tool-version-method:' + role)


def source_refs(role):
    """No runtime helper/emitter closure; issuer separately pins this module."""
    method_for(role)
    return []


def _path(value):
    # Consistent with the existing fixed methods' canonical Windows argv domain.
    # This is a declaration check; physical selected-file admission is external.
    if (type(value) is not str or not 4 <= len(value) <= 4096 or not value.isascii() or
            not 'A' <= value[0] <= 'Z' or value[1:3] != ':/' or
            any(ord(c) < 32 or ord(c) == 127 or c in '\\;"$@~<>|?*' for c in value) or
            any(not part or part in ('.', '..') or part.endswith((' ', '.')) or ':' in part
                for part in value[3:].split('/'))):
        raise ValueError('Explicit canonical Windows program path required')
    return value


def argv(role, program_path, emitter_path=None):
    """Return the reviewed literal argv; never resolve, read, or launch it."""
    method_for(role)
    program_path = _path(program_path)
    if program_path.rsplit('/', 1)[-1] != role + '.exe':
        raise ValueError('Selected version program basename/role differs')
    if emitter_path is not None:
        raise ValueError('Console version methods take no emitter')
    return [program_path, '--version']


def _log(raw):
    if type(raw) is not bytes or not 1 <= len(raw) <= MAX_LOG_BYTES:
        raise ValueError('Bounded exact raw version log bytes required')
    try:
        text = raw.decode('ascii')
    except UnicodeDecodeError as error:
        raise ValueError('Version log must be ASCII') from error
    # Accept the source's LF or uniform Windows text-mode CRLF. This finite
    # transport normalization neither strips whitespace nor drops any lines.
    if '\r' in text:
        normalized = text.replace('\r\n', '\n')
        if '\r' in normalized or '\n' in text.replace('\r\n', ''):
            raise ValueError('Version log has mixed or bare-CR line endings')
        text = normalized
    return text


def _numeric(value):
    # The existing project domain has two through four numeric components.
    # A suffix cannot be relabelled as a final release. No minimum is invented.
    if not 1 <= len(value) <= 64 or _NUMERIC.fullmatch(value) is None:
        raise ValueError('Version log does not declare a numeric final release')
    return value


def extract(role, method, raw_log, *, final=True):
    """Derive the numeric release from the complete fixed output grammar.

    No H, inventory version, expected version, regex, or banner is accepted.
    Both exact boolean final selections use the same suffix-free grammar.
    Native process success and held original-log identity remain caller duties.
    """
    selected_method = method_for(role)
    if type(method) is not str or method != selected_method:
        raise MissingMethod('windows-tool-version-method:' + role)
    if type(final) is not bool:
        raise ValueError('Exact final-method selector required')
    text = _log(raw_log)
    if role == 'ninja':
        if not text.endswith('\n'):
            raise ValueError('Ninja version log has no terminal newline')
        return _numeric(text[:-1])
    prefix = 'GNU gperf '
    if not text.startswith(prefix) or not text.endswith(_GPERF_TAIL):
        raise ValueError('gperf version log differs from the reviewed whole banner')
    header = text[:-len(_GPERF_TAIL)]
    if not header.endswith('\n'):
        raise ValueError('gperf version header has no terminal newline')
    return _numeric(header[len(prefix):-1])
