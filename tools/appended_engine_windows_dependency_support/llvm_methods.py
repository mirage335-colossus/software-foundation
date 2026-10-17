"""Fixed LLVM5 numeric methods and typed PE-resource subjects; no native trust.

Console option/printer shapes are grounded in llvmorg-19.1.7 source. Resource
methods use a separate finite LLVM fixed-field policy and an unchanged NMake
structural codec. Only fixed pinned helper source is read lazily. No selected
program, runtime, SDK, archive or product body is read or executed here.
Inventory labels and H versions are never accepted as parser input. Descriptive
numeric observations do not authenticate a supplier release, VCS, or vendor.
"""

import hashlib
import os
from pathlib import Path, PureWindowsPath
import re
import stat
import types


METHODS = {'compiler': 'clang-cl-dumpversion-numeric-v1',
           'linker': 'lld-link-version-numeric-v1',
           'archiver': 'llvm3-pe-version-resource-v1',
           'resource_compiler': 'llvm3-pe-version-resource-v1',
           'manifest_tool': 'llvm3-pe-version-resource-v1'}
PROGRAM_NAMES = {'compiler': 'clang-cl.exe', 'linker': 'lld-link.exe',
                 'archiver': 'llvm-lib.exe', 'resource_compiler': 'llvm-rc.exe',
                 'manifest_tool': 'llvm-mt.exe'}
RESOURCE_ROLES = ('archiver', 'resource_compiler', 'manifest_tool')
MINIMUM = (19, 1, 7)
MAX_LOG_BYTES = 4096
_NUMBER = r'(?:0|[1-9][0-9]{0,4})'
_VERSION = _NUMBER + r'\.' + _NUMBER + r'\.' + _NUMBER
_RESERVED = {'CON', 'PRN', 'AUX', 'NUL', 'CONIN$', 'CONOUT$',
             *('COM' + str(index) for index in range(1, 10)),
             *('LPT' + str(index) for index in range(1, 10))}
_HERE = Path(__file__).resolve().parent
_SOURCE_ROWS = {
    'parser': ('resource/llvm_version.py', 9374,
               '3f9600b3309c6ec5848d2de6e97d79c0fea9b02c80e801ccf133d42fa7673d4f'),
    'codec': ('nmake_version.py', 22934,
              '20645406f9402db9f70d24679508078cfa7e648d77f652e30e4355bc1df90fdc'),
    'emitter': ('resource/llvm_version_emitter.py', 6714,
                'a2d069a2682090c2b44094530ca4e0f1563426711046f9298ddaa3a14e72c511'),
}


class MissingMethod(ValueError):
    """The role or method is outside the fixed five-role source interface."""


class UnsupportedFormat(ValueError):
    """Original numeric output does not satisfy the admitted finite policy."""


def method_for(role):
    if type(role) is not str or not 1 <= len(role) <= 128:
        raise ValueError('Bounded exact LLVM version role required')
    if role not in METHODS:
        raise MissingMethod('windows-tool-version-method:' + role)
    return METHODS[role]


def _path(value, *, basename):
    if (type(value) is not str or not 4 <= len(value) <= 4096 or
            not value.isascii() or re.match(r'^[A-Z]:/', value) is None or
            PureWindowsPath(value).as_posix() != value or
            any(ord(char) < 32 or ord(char) == 127 or char in '\\;"$@~<>|?*'
                for char in value) or
            any(not part or part in ('.', '..') or part.endswith((' ', '.')) or
                ':' in part or part.split('.')[0].upper() in _RESERVED
                for part in value[3:].split('/')) or
            value.rsplit('/', 1)[-1] != basename):
        raise ValueError('Exact canonical selected LLVM method path required')
    return value


def argv(role, program_path, emitter_path=None):
    """Literal console argv; resources require the separate typed runner API."""
    method_for(role)
    if role in RESOURCE_ROLES:
        raise ValueError('LLVM resource argv needs independent subject ref3 and Python runner')
    program = _path(program_path, basename=PROGRAM_NAMES[role])
    if emitter_path is not None:
        raise ValueError('Direct LLVM console methods take no emitter')
    if role == 'compiler':
        return [program, '--no-default-config', '/clang:-dumpversion']
    return [program, '--version']


def _resource_role(role):
    method_for(role)
    if role not in RESOURCE_ROLES:
        raise ValueError('One of the three fixed LLVM PE-subject roles required')


def resource_refs(role):
    """Owned finite ref4 rows, relative to this adapter's source directory."""
    _resource_role(role)
    return {name: {'path': relative, 'sha256': pin, 'bytes': count, 'mode': 0o644}
            for name, (relative, count, pin) in _SOURCE_ROWS.items()}


def source_refs(role):
    """Fixed source ref2 closure; this adapter is pinned separately by its user."""
    method_for(role)
    if role not in RESOURCE_ROLES:
        return []
    rows = resource_refs(role)
    return [{key: rows[name][key] for key in ('path', 'sha256')}
            for name in ('parser', 'codec', 'emitter')]


def final_method_gaps():
    """Every local role has a source-grounded numeric baseline method."""
    return ()


def _read_source(name):
    relative, count, expected_pin = _SOURCE_ROWS[name]
    path = _HERE / relative
    with path.open('rb') as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size != count or count > 131072:
            raise ValueError('Fixed LLVM method source type/size differs: ' + relative)
        raw = stream.read(count + 1)
        after = os.fstat(stream.fileno())
    identity = lambda row: (row.st_dev, row.st_ino, row.st_mode, row.st_size,
                            row.st_mtime_ns, row.st_ctime_ns)
    if (identity(before) != identity(after) or len(raw) != count or
            hashlib.sha256(raw).hexdigest() != expected_pin):
        raise ValueError('Fixed LLVM method source identity/pin differs: ' + relative)
    return raw


def _resource_parser():
    sources = {name: _read_source(name) for name in ('parser', 'codec', 'emitter')}
    emitter = types.ModuleType('_fixed_llvm_resource_emitter')
    emitter.__file__ = str(_HERE / _SOURCE_ROWS['emitter'][0])
    exec(compile(sources['emitter'], emitter.__file__, 'exec', dont_inherit=True), vars(emitter))
    return emitter._compile_parser(sources['codec'], sources['parser'])


def resource_argv(role, runner_path, emitter_path, program_ref3):
    """Use an independently admitted Python runner for one actual PE subject.

    The native O2 controller must hold and join that runner, selected subject,
    complete runtime, fixed source closure, Workspace and original Job/log.
    This pure command declaration performs none of those admissions.
    """
    _resource_role(role)
    _path(runner_path, basename='python.exe')
    return _resource_parser().collector_argv(role, runner_path, emitter_path, program_ref3)


def _line(raw):
    if type(raw) is not bytes or not 1 <= len(raw) <= MAX_LOG_BYTES:
        raise UnsupportedFormat('Bounded complete LLVM version log bytes required')
    if raw.endswith(b'\r\n'):
        body = raw[:-2]
    elif raw.endswith(b'\n'):
        body = raw[:-1]
    else:
        raise UnsupportedFormat('Complete LLVM version line terminator required')
    if not body or any(byte < 32 or byte > 126 for byte in body):
        raise UnsupportedFormat('One whole printable ASCII LLVM version line required')
    return body.decode('ascii')


def _version(text):
    if re.fullmatch(_VERSION, text) is None:
        raise UnsupportedFormat('Exact LLVM numeric major.minor.patch required')
    numbers = tuple(int(component) for component in text.split('.'))
    if any(component > 65535 for component in numbers):
        raise UnsupportedFormat('LLVM numeric component exceeds fixed-file range')
    if numbers < MINIMUM:
        raise UnsupportedFormat('Observed LLVM is below numeric baseline19.1.7')
    return '.'.join(map(str, numbers))


def parse_resource_version(role, method, raw_log, program_ref3):
    """Return a numeric triple after joining the independent selected ref3."""
    _resource_role(role)
    if type(method) is not str or method != method_for(role):
        raise MissingMethod('windows-tool-version-method:' + role)
    parser = _resource_parser()
    selected = parser._program(role, program_ref3)
    facts = parser.parse_output(raw_log, role=role, program=selected)
    return _version('.'.join(map(str, facts['version4'][:3])))


def extract(role, method, raw_log, *, final=True):
    """Derive numeric components without any H/inventory expected-version input.

    Resource extraction here is self-consistency only. Original O2 observations
    use parse_resource_version with their independently held selected ref3.
    ``final`` preserves the shared Boolean signature and adds no supplier-release
    or VCS attestation. Unsupported suffixes are data-format failures.
    """
    selected = method_for(role)
    if type(method) is not str or method != selected:
        raise MissingMethod('windows-tool-version-method:' + role)
    if type(final) is not bool:
        raise ValueError('Exact Boolean numeric-method selector required')
    if role in RESOURCE_ROLES:
        return _version(_resource_parser().parse_numeric(role, raw_log))
    line = _line(raw_log)
    if role == 'compiler':
        return _version(line)
    matches = list(re.finditer(r'(?<!\S)LLD (' + _VERSION + r')(?=[ )]|$)', line))
    if len(matches) != 1:
        raise UnsupportedFormat('One unambiguous LLD numeric version required')
    match = matches[0]
    vendor, suffix = line[:match.start()], line[match.end():]
    if vendor and (not vendor.endswith(' ') or not vendor[:-1].strip() or
                   vendor[0] == ' ' or len(vendor) > 256):
        raise UnsupportedFormat('Bounded optional LLD vendor prefix required')
    if suffix and (len(suffix) > 2048 or not suffix.startswith(' (') or
                   not suffix.endswith(')') or len(suffix) < 5 or
                   '(' in suffix[2:-1] or ')' in suffix[2:-1] or
                   not suffix[2:-1].strip()):
        raise UnsupportedFormat('Bounded optional LLD repository metadata required')
    return _version(match.group(1))
