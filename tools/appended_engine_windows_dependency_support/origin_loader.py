"""One fixed retained-original module instance for the private H2 consumers.

This loads maintained source, never selected retained input bytes.  Consumers
must share this module instance; a second independently imported loader fails
closed rather than creating another production capability registry.
"""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import os
import stat
import sys
import threading


HERE = Path(__file__).resolve().parent
SOURCE = HERE / 'origin.py'
SOURCE_SHA256 = '79c64fa668fa75e14979b167027636c405d6564996fa6cc703e947dc15f0d65c'
SOURCE_MAXIMUM_BYTES = 256 * 1024
MODULE_NAME = '_foundation_retained_originals_79c64fa668fa75e1'
SHARED_LOADER_NAME = '_foundation_windows_h2_origin_loader_v1'
_MODULE = None
_SOURCE_IDENTITY = None
_LOCK = threading.RLock()
_FAILED_RESERVATIONS = []


class SourceReleaseError(ValueError):
    pass


def _identity(value):
    return (value.st_dev, value.st_ino, value.st_mode, value.st_nlink,
            value.st_size, value.st_mtime_ns, value.st_ctime_ns,
            getattr(value, 'st_file_attributes', 0))


def _source_bytes():
    for current in reversed((SOURCE, *SOURCE.parents)):
        value = current.lstat()
        if (getattr(value, 'st_file_attributes', 0) & 0x400 or
                not (stat.S_ISREG(value.st_mode) if current == SOURCE else
                     stat.S_ISDIR(value.st_mode)) or
                current == SOURCE and value.st_nlink != 1):
            raise SourceReleaseError('Fixed original-reader source must be ordinary')
    before = SOURCE.lstat()
    if not 1 <= before.st_size <= SOURCE_MAXIMUM_BYTES:
        raise SourceReleaseError('Fixed original-reader source exceeds its bound')
    with SOURCE.open('rb') as stream:
        if _identity(os.fstat(stream.fileno())) != _identity(before):
            raise SourceReleaseError('Original-reader source changed before capture')
        raw = stream.read(SOURCE_MAXIMUM_BYTES + 1)
        after = os.fstat(stream.fileno())
    if (_identity(before) != _identity(after) or
            _identity(before) != _identity(SOURCE.lstat()) or
            len(raw) != before.st_size or
            hashlib.sha256(raw).hexdigest() != SOURCE_SHA256):
        raise SourceReleaseError('Fixed original-reader source release does not join')
    return raw, _identity(before)


def originals_module():
    """Return the single source-checked production Origin registry module.

    No module/path/loader or caller authority is accepted.  Existing foreign
    cache entries are rejected, including a separately executed copy with the
    same filename.  Pure fixtures cannot install a production module here.
    """
    global _MODULE, _SOURCE_IDENTITY
    with _LOCK:
        raw, identity = _source_bytes()
        if _MODULE is not None:
            if (_SOURCE_IDENTITY != identity or
                    sys.modules.get(MODULE_NAME) is not _MODULE):
                raise SourceReleaseError('Original-reader module/source identity changed')
            return _MODULE
        if MODULE_NAME in sys.modules:
            raise SourceReleaseError('A foreign original-reader cache entry exists')
        specification = importlib.util.spec_from_file_location(MODULE_NAME, SOURCE)
        module = importlib.util.module_from_spec(specification)
        # A second independently imported loader has another lock. Reserve the
        # shared name atomically; it must never overwrite a winning registry.
        if sys.modules.setdefault(MODULE_NAME, module) is not module:
            raise SourceReleaseError('A foreign original-reader cache reservation exists')
        try:
            # Execute the captured and pinned bytes, never a second path read.
            exec(compile(raw, str(SOURCE), 'exec'), module.__dict__)
            _, after = _source_bytes()
            if after != identity or sys.modules.get(MODULE_NAME) is not module:
                raise SourceReleaseError('Original-reader source/cache changed during load')
        except BaseException:
            # A foreign replacement may race any check followed by deletion.
            # Keep the failed own reservation as a blocker; never erase a slot
            # which might now belong to another loader.
            _FAILED_RESERVATIONS.append(module)
            raise
        _SOURCE_IDENTITY, _MODULE = identity, module
        return module
