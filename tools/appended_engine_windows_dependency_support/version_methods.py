"""Fixed source-owned Windows version methods for thirteen selected roles.

Numeric results describe observed programs. They cannot authenticate an original
CI acquisition, current input ownership, command closure or an issued capability.
NMake/MSBuild have separate fixed host-method plans; only the three declared LLVM
resource roles use an admitted Python runner for their independently held image.
"""

from __future__ import annotations

import copy
import hashlib
import os
from pathlib import Path
import stat
import types

HERE = Path(__file__).resolve().parent
ROLE_ORDER = ('compiler', 'linker', 'archiver', 'resource_compiler',
    'manifest_tool', 'cmake', 'ninja', 'python', 'perl', 'ruby', 'gperf',
    'nmake', 'msbuild')
LLVM_ROLES = ('compiler', 'linker', 'archiver', 'resource_compiler', 'manifest_tool')
RESOURCE_ROLES = ('archiver', 'resource_compiler', 'manifest_tool')
_RELEASES = {'base': ('methods.py', 9983, 'ab6fad7a14c7d08e5980c8c4a61eda3a3e76a2e85d5ff7006a36fd296e54eefc'), 'llvm': ('llvm_methods.py', 9764, '62a0c91a43764dfd577f75ffccb75a56e0e181452a51ca37777e893736fca9a4'), 'console': ('console_methods.py', 4997, 'dbdfdc7eae58f761788a511e043a107a62f63254e35387148786e73080048c8a'), 'supported': ('supported_builtins.py', 4173, '085b5cb185df615824b5596d56cb0ba1c99e7c17a3553642ec7666f395f6a04a')}
_MODULES = {}


class MissingMethod(ValueError):
    pass


def _module(name):
    if name not in _MODULES:
        relative, size, expected = _RELEASES[name]
        source = HERE / relative
        before = source.lstat()
        if (not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size != size):
            raise ValueError('Fixed version method source type or bound differs')
        with source.open('rb') as stream:
            opened = os.fstat(stream.fileno()); raw = stream.read(size + 1)
            after = os.fstat(stream.fileno())
        identity = lambda row: (row.st_dev, row.st_ino, row.st_mode, row.st_nlink,
            row.st_size, row.st_mtime_ns, row.st_ctime_ns)
        if (identity(before) != identity(opened) or identity(before) != identity(after) or
                identity(before) != identity(source.lstat()) or len(raw) != size or
                hashlib.sha256(raw).hexdigest() != expected):
            raise ValueError('Fixed version method source identity/SHA256 differs')
        value = types.ModuleType('_foundation_windows_fixed_version_' + name)
        value.__file__ = str(source)
        exec(compile(raw, str(source), 'exec'), vars(value))
        _MODULES[name] = value
    return _MODULES[name]


def _selected(role):
    if type(role) is not str or role not in ROLE_ORDER:
        raise MissingMethod('windows-tool-version-method:' + str(role))
    return _module('llvm' if role in LLVM_ROLES else
        'console' if role in ('ninja', 'gperf') else
        'supported' if role in ('perl', 'ruby') else 'base')


def method_for(role):
    selected = _selected(role)
    try:
        return selected.method_for(role)
    except selected.MissingMethod as error:
        raise MissingMethod(str(error)) from error


def argv(role, program_path, emitter_path=None):
    selected = _selected(role)
    try:
        if role in ('perl', 'ruby'):
            return selected.version_argv(role, method_for(role), program_path, emitter_path)
        return selected.argv(role, program_path, emitter_path)
    except selected.MissingMethod as error:
        raise MissingMethod(str(error)) from error


def extract(role, method, raw_log, *, final=True):
    if type(final) is not bool:
        raise ValueError('Exact supported-method selector required')
    selected = _selected(role)
    try:
        if role in ('perl', 'ruby'):
            return selected.parse_supported_builtin_version(role, method, raw_log)
        return selected.extract(role, method, raw_log, final=final)
    except selected.MissingMethod as error:
        raise MissingMethod(str(error)) from error


def source_refs(role):
    selected = _selected(role)
    try:
        return copy.deepcopy(selected.source_refs(role))
    except selected.MissingMethod as error:
        raise MissingMethod(str(error)) from error


def resource_refs(role):
    if role not in RESOURCE_ROLES:
        raise MissingMethod('windows-tool-version-resource-method:' + str(role))
    return copy.deepcopy(_module('llvm').resource_refs(role))


def resource_argv(role, runner_path, emitter_path, program_ref3):
    if role not in RESOURCE_ROLES:
        raise MissingMethod('windows-tool-version-resource-method:' + str(role))
    return _module('llvm').resource_argv(role, runner_path, emitter_path, program_ref3)


def parse_resource_version(role, method, raw_log, program_ref3):
    if role not in RESOURCE_ROLES:
        raise MissingMethod('windows-tool-version-resource-method:' + str(role))
    selected = _module('llvm')
    try:
        return selected.parse_resource_version(role, method, raw_log, program_ref3)
    except selected.MissingMethod as error:
        raise MissingMethod(str(error)) from error


def final_method_gaps():
    # Loading each selected pure source verifies that the advertised method is
    # actually present. The two host roles are implemented by fixed issuer plans.
    gaps = []
    for role in ROLE_ORDER:
        try:
            method_for(role)
        except MissingMethod as error:
            gaps.append(str(error))
    return tuple(gaps)
