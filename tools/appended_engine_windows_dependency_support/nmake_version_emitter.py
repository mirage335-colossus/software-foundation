"""Standalone future-Job NMake resource observer; never execute the subject.

The independently admitted collector Python runs this exact source with -I -S.
Source import is inert. Selected I/O occurs only in main on actual Windows x64.
"""
import hashlib
import os
from pathlib import Path
import platform
import re
import stat
import struct
import sys
import types


PARSER_BASENAME = 'nmake_version.py'
PARSER_SHA256 = '20645406f9402db9f70d24679508078cfa7e648d77f652e30e4355bc1df90fdc'
PARSER_BYTES = 22934
MAX_IMAGE_BYTES = 64 * 1024 * 1024


def parse_arguments(argv):
    """Pure exact argv grammar; the fixed parser validates the full body ref."""
    if (type(argv) is not list or len(argv) != 6 or any(type(x) is not str for x in argv) or
            argv[0] != '--program' or argv[2] != '--sha256' or argv[4] != '--bytes'):
        raise ValueError('Exact --program/--sha256/--bytes arguments required')
    if re.fullmatch('[0-9a-f]{64}', argv[3]) is None or argv[3] == '0' * 64:
        raise ValueError('Exact independent nonzero program hash required')
    if re.fullmatch('[1-9][0-9]{0,8}', argv[5]) is None:
        raise ValueError('Canonical bounded decimal program byte count required')
    size = int(argv[5])
    if not 512 <= size <= MAX_IMAGE_BYTES:
        raise ValueError('Program body must be 512 bytes through 64 MiB')
    if not argv[1] or len(argv[1]) > 1024:
        raise ValueError('Bounded selected program path required')
    return {'path': argv[1], 'sha256': argv[3], 'bytes': size}


def _native_guard():
    if (os.name != 'nt' or platform.system() != 'Windows' or
            platform.machine().casefold() not in ('amd64', 'x86_64') or struct.calcsize('P') != 8):
        raise ValueError('Actual native Windows x64 collector is required')


def _identity(state):
    return (state.st_dev, state.st_ino, state.st_mode, state.st_size,
            state.st_mtime_ns, state.st_ctime_ns, state.st_nlink,
            getattr(state, 'st_file_attributes', 0))


def _path_states(path):
    states = []
    for component in reversed((path, *path.parents)):
        state = component.lstat()
        if (stat.S_ISLNK(state.st_mode) or getattr(state, 'st_file_attributes', 0) & 0x400 or
                not (stat.S_ISREG(state.st_mode) if component == path else stat.S_ISDIR(state.st_mode)) or
                component == path and state.st_nlink != 1):
            raise ValueError('Ordinary unaliased non-reparse source/program path required')
        states.append((component, _identity(state)))
    return states


def _read_pinned(path, *, size, sha256):
    """Finite stable ordinary-file capture; descriptive bytes, no native token."""
    if type(size) is not int or not 1 <= size <= MAX_IMAGE_BYTES:
        raise ValueError('Finite pinned source/program size required')
    path = Path(path).absolute()
    before = _path_states(path)
    if before[-1][1][3] != size:
        raise ValueError('Selected source/program size differs')
    chunks, count, digest = [], 0, hashlib.sha256()
    with path.open('rb') as stream:
        if _identity(os.fstat(stream.fileno())) != before[-1][1]:
            raise ValueError('Opened source/program identity differs')
        while True:
            block = stream.read(min(1024 * 1024, size - count + 1))
            if not block: break
            count += len(block)
            if count > size: raise ValueError('Source/program exceeds pinned EOF')
            digest.update(block); chunks.append(block)
        if _identity(os.fstat(stream.fileno())) != before[-1][1]:
            raise ValueError('Source/program changed during held read')
    if _path_states(path) != before or count != size or digest.hexdigest() != sha256:
        raise ValueError('Source/program identity/hash/EOF differs')
    return b''.join(chunks)


def _load_parser():
    # Inspect the original path components before deriving the exact sibling;
    # do not resolve symlinks into an apparently ordinary alternate parent.
    emitter = Path(__file__).absolute()
    _path_states(emitter)
    source = emitter.parent / PARSER_BASENAME
    raw = _read_pinned(source, size=PARSER_BYTES, sha256=PARSER_SHA256)
    module = types.ModuleType('_private_nmake_version_resource_parser')
    module.__file__ = str(source)
    exec(compile(raw, str(source), 'exec'), vars(module))
    return module


def main(argv=None):
    try:
        _native_guard()
        program = parse_arguments(sys.argv[1:] if argv is None else argv)
        parser = _load_parser()
        # This fixed private pure ref checker runs before selected program I/O.
        program = parser._program(program)
        raw = _read_pinned(Path(program['path']), size=program['bytes'], sha256=program['sha256'])
        facts = parser.inspect_version_info(raw)
        output = parser.render_output(program, facts)
        sys.stdout.buffer.write(output)
        sys.stdout.buffer.flush()
        return 0
    except (ValueError, OSError, EOFError, UnicodeError):
        # Do not leak partial observations, selected data or exception text into
        # a protocol line. A failed Job is rejected by the separate O checker.
        sys.stderr.write('nmake-version-resource observation failed\n')
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
