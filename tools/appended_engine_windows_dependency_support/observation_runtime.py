"""Additive pure runtime-profile joins around the frozen original-O checker.

The returned facts are consistency facts only.  They cannot establish original
origin, held input/Job ownership, runtime execution or an issuer capability.
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
CORE_SHA256 = '1015d81599bf7823ea5c9df7c5477b12fd325e4b878e5189975b90dca13881c8'
CORE_BYTES = 10155
RUNTIME_ROLES = ('nmake', 'msbuild')
MAX_PROFILE_BYTES = 2 * 1024 * 1024
MAX_OBSERVATION_BYTES = 1024 * 1024
_CORE = None


def _encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True,
                       allow_nan=False) + '\n').encode('ascii')


def _core():
    global _CORE
    if _CORE is None:
        source = HERE / 'observations.py'
        before = source.lstat()
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size != CORE_BYTES:
            raise ValueError('Fixed original-O checker type/size differs')
        with source.open('rb') as stream:
            opened = os.fstat(stream.fileno())
            raw = stream.read(CORE_BYTES + 1)
            after = os.fstat(stream.fileno())
        identity = lambda row: (row.st_dev, row.st_ino, row.st_mode, row.st_nlink,
                                row.st_size, row.st_mtime_ns, row.st_ctime_ns)
        if (identity(before) != identity(opened) or identity(before) != identity(after) or
                identity(before) != identity(source.lstat()) or len(raw) != CORE_BYTES or
                hashlib.sha256(raw).hexdigest() != CORE_SHA256):
            raise ValueError('Fixed original-O checker source release differs')
        module = types.ModuleType('_private_observation_runtime_core')
        module.__file__ = str(source)
        exec(compile(raw, str(source), 'exec'), vars(module))
        _CORE = module
    return _CORE


def runtime_bindings(value):
    """Validate and copy the exact two-role declaration, without authority."""
    proof = _core()._module('proof')
    proof._fields(value, RUNTIME_ROLES, 'two original runtime profiles')
    aliases = set()
    for role in RUNTIME_ROLES:
        item = value[role]
        proof._fields(item, ('reference', 'subject_sha256'), role + ' runtime binding')
        reference = item['reference']
        proof._fields(reference, ('path', 'sha256', 'bytes', 'mode'), role + ' original runtime profile')
        proof.windows_path(reference['path'], role + ' original runtime profile')
        proof._pin(reference['sha256'], role + ' original runtime profile')
        proof._integer(reference['bytes'], role + ' original runtime profile bytes', 1, MAX_PROFILE_BYTES)
        if type(reference['mode']) is not int or reference['mode'] != 0o644:
            raise ValueError('Runtime profile logical mode0644 required')
        if reference['path'].casefold() in aliases:
            raise ValueError('Original runtime profile paths repeat or alias')
        aliases.add(reference['path'].casefold())
        proof._pin(item['subject_sha256'], role + ' derived runtime subject')
    return copy.deepcopy(value)


def _document(raw, expected):
    if (type(raw) is not bytes or not 1 <= len(raw) <= MAX_OBSERVATION_BYTES or
            type(expected) is not str or hashlib.sha256(raw).hexdigest() != expected):
        raise ValueError('Whole original runtime O bytes/pin differ')
    def pairs(items):
        result = {}
        for key, item in items:
            if key in result:
                raise ValueError('Duplicate original O field')
            result[key] = item
        return result
    value = json.loads(raw.decode('ascii'), object_pairs_hook=pairs,
                       parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Invalid O number')))
    pending, count = [(value, 0)], 0
    while pending:
        item, depth = pending.pop()
        count += 1
        if count > 32768 or depth > 32:
            raise ValueError('Original O structure exceeds its bound')
        if type(item) is dict:
            pending.extend((nested, depth + 1) for nested in item.values())
        elif type(item) is list:
            pending.extend((nested, depth + 1) for nested in item)
    return value


def observation(raw, pin, *, role, program, inventory_subject_sha256,
                collector, command, log_raw, log_reference, runtime_profiles=None):
    core = _core()
    original = _document(raw, pin)
    expected = dict(role=role, program=program,
                    inventory_subject_sha256=inventory_subject_sha256,
                    collector=collector, command=command,
                    log_raw=log_raw, log_reference=log_reference)
    if (type(original) is dict and type(original.get('schema_version')) is int and
            original['schema_version'] == 1 and original.get('kind') == core.O1_KIND):
        if runtime_profiles is not None:
            raise ValueError('Original O1 has no runtime-profile extension')
        return core.observation(raw, pin, **expected)
    if (type(original) is not dict or type(original.get('schema_version')) is not int or
            original['schema_version'] != 2 or original.get('kind') != core.O2_KIND or
            set(original) != set(core.O_FIELDS) | {'runtime_profiles'}):
        raise ValueError('Exact successor O2 runtime-profile fields required')
    if _encoded(original) != raw:
        raise ValueError('Original O2 must use the frozen canonical JSON encoding')
    actual = runtime_bindings(original['runtime_profiles'])
    independent = runtime_bindings(runtime_profiles)
    if _encoded(actual) != _encoded(independent):
        raise ValueError('Original runtime profiles differ from independent held facts')
    core_value = copy.deepcopy(original)
    del core_value['runtime_profiles']
    core_raw = _encoded(core_value)
    result = core.observation(core_raw, hashlib.sha256(core_raw).hexdigest(), **expected)
    result['observation'] = copy.deepcopy(original)
    return result
