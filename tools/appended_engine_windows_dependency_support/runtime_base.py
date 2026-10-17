"""Source-owned runtime subject construction from independently held bytes.

This pure consistency reader cannot admit a native runtime or issue versions.
Actual factories own all captures; unsupported semantic readers stay SOURCE.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import stat
import types


HERE = Path(__file__).resolve().parent
MANAGED_SOURCE = ('managed_runtime.py', 64755,
    'a4c7a366c927e655ccd4f331174c9310d1e0d0357a29bae0452a9e56a9ae99c2')
SEMANTIC_SOURCES = {
    'managed_runtime.py': MANAGED_SOURCE[2],
    'inventory_contract.py': '83ff23d4356e454e899446e16bfea9aaf8d778f1d91972ace45220d2a9bf2bfb'}
SUBJECT_KIND = 'foundation-native-engine-windows-tool-runtime-subject-v1'
MAX_PROFILE_BYTES = 2 * 1024 * 1024
_MANAGED = None


class MissingInputs(ValueError):
    def __init__(self, gaps):
        self.gaps = tuple(gaps)
        super().__init__('; '.join(self.gaps))


def _encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'),
                       ensure_ascii=True, allow_nan=False) + '\n').encode('ascii')


def _managed():
    global _MANAGED
    if _MANAGED is None:
        relative, size, expected = MANAGED_SOURCE
        source = HERE / relative
        before = source.lstat()
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size != size:
            raise ValueError('Fixed managed checker type/size differs')
        with source.open('rb') as stream:
            opened = os.fstat(stream.fileno())
            raw = stream.read(size + 1)
            after = os.fstat(stream.fileno())
        identity = lambda row: (row.st_dev, row.st_ino, row.st_mode, row.st_nlink,
                                row.st_size, row.st_mtime_ns, row.st_ctime_ns)
        if (identity(before) != identity(opened) or identity(before) != identity(after) or
                identity(before) != identity(source.lstat()) or len(raw) != size or
                hashlib.sha256(raw).hexdigest() != expected):
            raise ValueError('Fixed managed checker source release differs')
        module = types.ModuleType('_private_h2_managed_runtime')
        module.__file__ = str(source)
        exec(compile(raw, str(source), 'exec'), vars(module))
        _MANAGED = module
    return _MANAGED


def _profile(role, reference, raw):
    if role not in ('nmake', 'msbuild') or type(role) is not str:
        raise ValueError('Exact nmake/msbuild runtime role required')
    managed = _managed()
    managed._keys(reference, ('path', 'sha256', 'bytes', 'mode'), 'original runtime profile')
    managed._path(reference['path']); managed._pin(reference['sha256'])
    managed._integer(reference['bytes'], 1, MAX_PROFILE_BYTES, 'original runtime profile bytes')
    if type(reference['mode']) is not int or reference['mode'] != 0o644:
        raise ValueError('Original runtime profile logical mode0644 required')
    if (type(raw) is not bytes or len(raw) != reference['bytes'] or
            hashlib.sha256(raw).hexdigest() != reference['sha256']):
        raise ValueError('Whole original runtime profile bytes/pin differ')
    if role == 'nmake':
        raise MissingInputs(['SOURCE:windows-nmake-original-shell-runtime-profile-reader'])
    profile = managed.parse_runtime_profile(raw, reference['sha256'])
    host_root = profile['host_bundle']['root']
    if (reference['path'].casefold() == host_root.casefold() or
            reference['path'].casefold().startswith(host_root.rstrip('/').casefold() + '/')):
        raise ValueError('Original profile must be outside its complete host inventory')
    return managed, profile


def profile_references(role, reference, raw):
    """Select exact finite declared file refs before an actual caller captures.

    This parses only the source-owned profile declaration; it never claims those
    files exist, are held, are complete or can safely execute.
    """
    _, profile = _profile(role, reference, raw)
    selected, aliases, pending, total = {}, {}, [profile], 0
    while pending:
        value = pending.pop()
        if type(value) is dict:
            if set(value) == {'path', 'sha256', 'bytes'}:
                name = value['path']
                if name.casefold() in aliases and aliases[name.casefold()] != name:
                    raise ValueError('Runtime profile file references alias by case')
                if name in selected and selected[name] != value:
                    raise ValueError('Runtime profile file references have different pins')
                aliases[name.casefold()] = name
                if name not in selected:
                    total += value['bytes']
                selected[name] = copy.deepcopy(value)
                if len(selected) > 4096 or total > 256 * 1024**2:
                    raise ValueError('Runtime profile selected byte/count bound exceeded')
            else:
                pending.extend(value.values())
        elif type(value) is list:
            pending.extend(value)
    return [selected[name] for name in sorted(selected)]


def runtime_profile(role, reference, raw, *, held_inventory, held_bytes):
    """Return a bound subject and reached references; no execution authority.

    ``held_inventory`` and ``held_bytes`` have the frozen managed-reader shapes.
    Callers independently retain the complete inventory trees and original
    profile/configuration/runtime bytes through their own successful closure.
    """
    managed, profile = _profile(role, reference, raw)
    profile_references(role, reference, raw)
    facts = managed.verify_profile(profile, held_inventory, held_bytes)
    # These are structural facts. False native/execution flags remain false.
    subject = {'schema_version': 1, 'kind': SUBJECT_KIND, 'role': role,
               'profile': copy.deepcopy(reference),
               'semantic_sources': copy.deepcopy(SEMANTIC_SOURCES),
               'facts': facts}
    return {'binding': {'reference': copy.deepcopy(reference),
                        'subject_sha256': hashlib.sha256(_encoded(subject)).hexdigest()},
            'selected_files': copy.deepcopy(facts['selected_files']),
            'consistency': copy.deepcopy(facts)}
