"""Fixed maintained pure byte-inspector source; no engine prototype import."""

import hashlib
import os
from pathlib import Path
import stat
import types


SOURCE = Path(__file__).resolve().parent / 'native_inspection_core.py'
SOURCE_BYTES = 21266
SOURCE_SHA256 = '75e816fdca8cc9ccf4d384d4e4f01e7be76f53879a6e5cfd7c6bdf9dc4e892f8'
_MODULE = None


def _load():
    global _MODULE
    if _MODULE is None:
        before = SOURCE.lstat()
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size != SOURCE_BYTES:
            raise ValueError('Maintained pure native byte-inspector source type/size differs')
        with SOURCE.open('rb') as stream:
            opened = os.fstat(stream.fileno())
            raw = stream.read(SOURCE_BYTES + 1)
            after = os.fstat(stream.fileno())
        identity = lambda value: (value.st_dev, value.st_ino, value.st_mode,
            value.st_nlink, value.st_size, value.st_mtime_ns, value.st_ctime_ns)
        if (identity(before) != identity(opened) or identity(before) != identity(after) or
                identity(before) != identity(SOURCE.lstat()) or len(raw) != SOURCE_BYTES or
                hashlib.sha256(raw).hexdigest() != SOURCE_SHA256):
            raise ValueError('Maintained pure native byte-inspector source identity/pin differs')
        module = types.ModuleType('_fixed_windows_native_byte_inspection')
        module.__file__ = str(SOURCE)
        exec(compile(raw, str(SOURCE), 'exec'), vars(module))
        _MODULE = module
    return _MODULE


def inspect_tool_image(raw):
    return _load().inspect_tool_image(raw)


def inspect_static_archive(raw, *, allowed_default_libraries=None):
    return _load().inspect_static_archive(raw, allowed_default_libraries=allowed_default_libraries)


def __getattr__(name):
    if name == 'SYSTEM_IMPORTS':
        return _load().SYSTEM_IMPORTS
    raise AttributeError(name)
