"""Fixed LLVM3 resource collector: selected PE bytes are data, never executed.

Only main performs selected source/subject reads on actual Windows x64.
Imports and _compile_parser are inert with respect to selected programs.
"""
import builtins
import hashlib
import os
from pathlib import Path
import platform
import re
import stat
import struct
import sys
import types


PARSER_BASENAME = 'llvm_version.py'
PARSER_SHA256 = '3f9600b3309c6ec5848d2de6e97d79c0fea9b02c80e801ccf133d42fa7673d4f'
PARSER_BYTES = 9374
CODEC_RELATIVE_PATH = '../nmake_version.py'
CODEC_SHA256 = '20645406f9402db9f70d24679508078cfa7e648d77f652e30e4355bc1df90fdc'
CODEC_BYTES = 22934
MAX_IMAGE_BYTES = 64 * 1024 * 1024
ROLES = ('archiver', 'resource_compiler', 'manifest_tool')


def parse_arguments(argv):
    """Pure exact argv grammar; parser validates the full typed subject ref3."""
    if (type(argv) is not list or len(argv) != 8 or
            any(type(item) is not str for item in argv) or
            argv[0] != '--role' or argv[2] != '--program' or
            argv[4] != '--sha256' or argv[6] != '--bytes' or argv[1] not in ROLES):
        raise ValueError('Exact LLVM3 role/program/sha256/bytes arguments required')
    if re.fullmatch('[0-9a-f]{64}', argv[5]) is None or argv[5] == '0' * 64:
        raise ValueError('Independent nonzero program hash required')
    if re.fullmatch('[1-9][0-9]{0,8}', argv[7]) is None:
        raise ValueError('Canonical bounded program byte count required')
    size = int(argv[7])
    if not 512 <= size <= MAX_IMAGE_BYTES:
        raise ValueError('Program body must be 512 bytes through 64 MiB')
    if not argv[3] or len(argv[3]) > 1024:
        raise ValueError('Bounded selected program path required')
    return {'role': argv[1], 'program':
        {'path': argv[3], 'sha256': argv[5], 'bytes': size}}


def _native_guard():
    if (os.name != 'nt' or platform.system() != 'Windows' or
            platform.machine().casefold() not in ('amd64', 'x86_64') or
            struct.calcsize('P') != 8):
        raise ValueError('Actual native Windows x64 collector required')


def _identity(state):
    return (state.st_dev, state.st_ino, state.st_mode, state.st_size,
        state.st_mtime_ns, state.st_ctime_ns, state.st_nlink,
        getattr(state, 'st_file_attributes', 0))


def _path_states(path):
    states = []
    for component in reversed((path, *path.parents)):
        state = component.lstat()
        if (stat.S_ISLNK(state.st_mode) or
                getattr(state, 'st_file_attributes', 0) & 0x400 or
                not (stat.S_ISREG(state.st_mode) if component == path else
                     stat.S_ISDIR(state.st_mode)) or
                component == path and state.st_nlink != 1):
            raise ValueError('Ordinary unaliased non-reparse source/subject path required')
        states.append((component, _identity(state)))
    return states


def _read_pinned(path, *, size, sha256):
    """Finite held ordinary-file capture; no native/issuer trust is returned."""
    if type(size) is not int or not 1 <= size <= MAX_IMAGE_BYTES:
        raise ValueError('Finite pinned source/subject size required')
    path = Path(path).absolute()
    before = _path_states(path)
    if before[-1][1][3] != size:
        raise ValueError('Selected source/subject size differs')
    chunks, count, digest = [], 0, hashlib.sha256()
    with path.open('rb') as stream:
        if _identity(os.fstat(stream.fileno())) != before[-1][1]:
            raise ValueError('Opened source/subject identity differs')
        while True:
            block = stream.read(min(1024 * 1024, size - count + 1))
            if not block:
                break
            count += len(block)
            if count > size:
                raise ValueError('Source/subject exceeds pinned EOF')
            digest.update(block)
            chunks.append(block)
        if _identity(os.fstat(stream.fileno())) != before[-1][1]:
            raise ValueError('Source/subject changed during held read')
    if (_path_states(path) != before or count != size or
            digest.hexdigest() != sha256):
        raise ValueError('Source/subject identity/hash/EOF differs')
    return b''.join(chunks)


def _compile_parser(codec_raw, parser_raw):
    """Compile the fixed inert source closure; perform no filesystem reads."""
    for raw, size, pin in ((codec_raw, CODEC_BYTES, CODEC_SHA256),
                           (parser_raw, PARSER_BYTES, PARSER_SHA256)):
        if type(raw) is not bytes or len(raw) != size or hashlib.sha256(raw).hexdigest() != pin:
            raise ValueError('Fixed LLVM3 resource source bytes/SHA256 differ')
    codec = types.ModuleType('nmake_structure_codec')
    codec.__file__ = CODEC_RELATIVE_PATH
    exec(compile(codec_raw, CODEC_RELATIVE_PATH, 'exec'), vars(codec))
    ordinary_import = builtins.__import__
    def fixed_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == 'nmake_structure_codec' and level == 0:
            return codec
        return ordinary_import(name, globals, locals, fromlist, level)
    parser = types.ModuleType('_private_llvm3_version_resource_parser')
    parser.__file__ = PARSER_BASENAME
    parser.__dict__['__builtins__'] = dict(vars(builtins), __import__=fixed_import)
    exec(compile(parser_raw, PARSER_BASENAME, 'exec'), vars(parser))
    return parser


def _load_parser():
    emitter = Path(__file__).absolute()
    if emitter.name != 'llvm_version_emitter.py':
        raise ValueError('Exact fixed emitter basename required')
    _path_states(emitter)
    codec_raw = _read_pinned(emitter.parent / CODEC_RELATIVE_PATH,
        size=CODEC_BYTES, sha256=CODEC_SHA256)
    parser_raw = _read_pinned(emitter.parent / PARSER_BASENAME,
        size=PARSER_BYTES, sha256=PARSER_SHA256)
    return _compile_parser(codec_raw, parser_raw)


def main(argv=None):
    try:
        _native_guard()
        arguments = parse_arguments(sys.argv[1:] if argv is None else argv)
        parser = _load_parser()
        role = arguments['role']
        # Exact typed basename and canonical ref3 are checked before subject I/O.
        program = parser._program(role, arguments['program'])
        raw = _read_pinned(Path(program['path']),
            size=program['bytes'], sha256=program['sha256'])
        facts = parser.inspect_version_info(raw)
        output = parser.render_output(role, program, facts)
        sys.stdout.buffer.write(output)
        sys.stdout.buffer.flush()
        return 0
    except (ValueError, OSError, EOFError, UnicodeError):
        sys.stderr.write('llvm3-version-resource observation failed\n')
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
