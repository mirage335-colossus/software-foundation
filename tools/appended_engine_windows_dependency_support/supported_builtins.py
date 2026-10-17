"""Fixed Perl/Ruby numeric observations under the existing supported policy.

This additive source candidate returns descriptive numeric strings only. It
does not establish vendor final-release status, original observation authority,
selected-runtime identity, native execution or a qualified issuer capability.
Frozen predecessor parsers, emitters and method registry remain unchanged.
"""

import hashlib
import os
from pathlib import Path
import stat
import types


HERE = Path(__file__).resolve().parent
ROLE_ORDER = ('perl', 'ruby')
_METHODS = {
    'perl': 'perl-builtin-supported-version-v2',
    'ruby': 'ruby-direct-supported-version-v2',
}
_ORIGINAL_BYTES = 9983
_ORIGINAL_SHA256 = 'ab6fad7a14c7d08e5980c8c4a61eda3a3e76a2e85d5ff7006a36fd296e54eefc'
_ORIGINAL = None


class MissingMethod(ValueError):
    """An unknown fixed source method, never an observed runtime fact."""


def method_for(role):
    if type(role) is not str or not 1 <= len(role) <= 128:
        raise ValueError('Bounded exact supported builtin role required')
    if role not in _METHODS:
        raise MissingMethod('windows-runtime-supported-version-method:' + role)
    return _METHODS[role]


def _method(role, method):
    expected = method_for(role)
    if type(method) is not str or method != expected:
        raise MissingMethod('windows-runtime-supported-version-method:' + role)


def _original():
    global _ORIGINAL
    if _ORIGINAL is None:
        source = HERE / 'methods.py'
        before = source.lstat()
        if (not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or
                before.st_size != _ORIGINAL_BYTES):
            raise ValueError('Fixed predecessor method source type/size differs')
        with source.open('rb') as stream:
            opened = os.fstat(stream.fileno())
            raw = stream.read(_ORIGINAL_BYTES + 1)
            after = os.fstat(stream.fileno())
        identity = lambda item: (item.st_dev, item.st_ino, item.st_mode,
            item.st_nlink, item.st_size, item.st_mtime_ns, item.st_ctime_ns)
        if (identity(before) != identity(opened) or
                identity(before) != identity(after) or
                identity(before) != identity(source.lstat()) or
                len(raw) != _ORIGINAL_BYTES or
                hashlib.sha256(raw).hexdigest() != _ORIGINAL_SHA256):
            raise ValueError('Fixed predecessor method source identity/SHA256 differs')
        module = types.ModuleType('_private_supported_builtin_predecessor')
        module.__file__ = str(source)
        exec(compile(raw, str(source), 'exec'), vars(module))
        _ORIGINAL = module
    return _ORIGINAL


def source_refs(role):
    """Describe the finite frozen helper/emitter closure; never select tools."""
    method_for(role)
    original = _original()
    return [{'path': 'methods.py', 'sha256': _ORIGINAL_SHA256}] + [
        {'path': item['path'], 'sha256': item['sha256']}
        for item in original.source_refs(role)]


def parse_supported_builtin_version(role, method, raw_log):
    """Derive an actual numeric observation, with no caller-expected version.

    Perl retains the predecessor's canonical triple, major5 and enforced taint1
    policy. Ruby retains its engine/equal-version policy and excludes the
    documented patchlevel -1 development case. No new minimum, stable-series
    predicate or independent vendor final-release authority is introduced.
    """
    _method(role, method)
    original = _original()
    protocol = original._load(role)
    try:
        parser = protocol._method(role, original.method_for(role))
        value = protocol.decode_raw(raw_log)
        version = parser.observed_numeric(value)
    except protocol.MissingMethod as error:
        raise MissingMethod(str(error)) from error
    if role == 'ruby' and value['ruby_patchlevel'] == -1:
        raise ValueError('Ruby development build is outside the supported policy')
    return version


def version_argv(role, method, program_path, emitter_path):
    """Return the exact predecessor argv and canonical declaration checks."""
    _method(role, method)
    return _original().argv(role, program_path, emitter_path)
