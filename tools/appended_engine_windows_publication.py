#!/usr/bin/env python3
"""Owned native Windows candidate output; complete atomic visibility, no power-loss promise.

Native bindings are lazy. Public Workspace creation requires original, source-
bound Windows qualification evidence. Private fake bindings serve inert tests;
the opt-in diagnostic uses the real binding without making a production claim.
No provider, compiler, source assembler or SDK producer is selected here.
"""
from __future__ import annotations

import copy
import ctypes as ct
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path, PureWindowsPath
import platform
import re
import secrets
import stat
import struct
import sys
import time

import appended_engine_windows_contract as contract
import process_tree

CONTRACT_SHA256 = 'ef065be8c502211ea748dbfc1732b6ca02b9210ee78ed74901f2b6ca6869d5d8'
POLICY = 'native-windows-local-ntfs-atomic-no-replace-v1'
SCOPE = 'actual-native-windows-publication'
MAX_METADATA = 1024 * 1024
MAX_FILE = 512 * 1024 * 1024
SOURCE_FILES = ('tools/appended_engine_windows_publication.py',
    'tests/diagnostics/windows_engine_publication.py', 'tools/process_tree.py',
    'tools/appended_engine_windows_contract.py')
CASE_NAMES = ('test_complete_atomic_no_replace', 'test_existing_directory_and_case_collision',
    'test_ancestor_handles_prevent_rename', 'test_reparse_and_hardlink_rejected',
    'test_complete_output_inventory', 'test_owned_pending_cleanup',
    'test_parent_exit_with_writer_rejected', 'test_joined_owner_seals_log',
    'test_flush_failure_stops_publication', 'test_uncertain_rename_retains_evidence')
_TOKEN = object()
_RETAINED = []

# Windows ABI, including on LP64 fixture hosts. Never use host c_long/wchar here.
U8, U16, U32, I32, I64 = ct.c_uint8, ct.c_uint16, ct.c_uint32, ct.c_int32, ct.c_int64
HANDLE, PVOID, UPTR = ct.c_void_p, ct.c_void_p, ct.c_size_t


class UNICODE_STRING(ct.Structure):
    _fields_ = [('Length', U16), ('MaximumLength', U16), ('Buffer', PVOID)]


class OBJECT_ATTRIBUTES(ct.Structure):
    _fields_ = [('Length', U32), ('RootDirectory', HANDLE), ('ObjectName', ct.POINTER(UNICODE_STRING)),
        ('Attributes', U32), ('SecurityDescriptor', PVOID), ('SecurityQualityOfService', PVOID)]


class _STATUS_UNION(ct.Union):
    _fields_ = [('Status', I32), ('Pointer', PVOID)]


class IO_STATUS_BLOCK(ct.Structure):
    _anonymous_ = ('result',)
    _fields_ = [('result', _STATUS_UNION), ('Information', UPTR)]


class FILE_BASIC_INFO(ct.Structure):
    _fields_ = [('CreationTime', I64), ('LastAccessTime', I64), ('LastWriteTime', I64),
        ('ChangeTime', I64), ('FileAttributes', U32)]


class FILE_STANDARD_INFO(ct.Structure):
    _fields_ = [('AllocationSize', I64), ('EndOfFile', I64), ('NumberOfLinks', U32),
        ('DeletePending', U8), ('Directory', U8)]


class FILE_ID_INFO(ct.Structure):
    _fields_ = [('VolumeSerialNumber', ct.c_uint64), ('FileId', U8 * 16)]


class FILE_ATTRIBUTE_TAG_INFO(ct.Structure):
    _fields_ = [('FileAttributes', U32), ('ReparseTag', U32)]


class FILE_RENAME_INFORMATION(ct.Structure):
    _fields_ = [('Flags', U32), ('RootDirectory', HANDLE), ('FileNameLength', U32), ('FileName', U16 * 1)]


def abi_layout():
    if ct.sizeof(HANDLE) != 8:
        raise ValueError('Windows publication requires the x64 ABI')
    expected = {UNICODE_STRING: 16, OBJECT_ATTRIBUTES: 48, IO_STATUS_BLOCK: 16,
        FILE_BASIC_INFO: 40, FILE_STANDARD_INFO: 24, FILE_ID_INFO: 24,
        FILE_ATTRIBUTE_TAG_INFO: 8, FILE_RENAME_INFORMATION: 24}
    if any(ct.sizeof(kind) != size for kind, size in expected.items()) or FILE_RENAME_INFORMATION.FileName.offset != 20:
        raise ValueError('Windows publication ABI layout differs')
    return {kind.__name__: size for kind, size in expected.items()}


class PublicationError(ValueError):
    pass


class OwnershipUncertain(PublicationError):
    pass


def encoded(value):
    return contract.encoded(value)


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _component(value):
    if type(value) is not str or '/' in value or '\\' in value:
        raise PublicationError('One literal Windows child component is required')
    contract.windows_path('C:/anchor/' + value, 'publication child')
    if len(value.encode('utf-16-le')) > 510:
        raise PublicationError('Windows publication component exceeds 255 UTF16 units')
    return value


def _relative(value):
    if type(value) is not str or not value or value.startswith('/') or '\\' in value:
        raise PublicationError('A canonical relative output path is required')
    for part in value.split('/'): _component(part)
    if len(value.split('/')) > 64 or len(value) > 4096:
        raise PublicationError('Windows output path exceeds its depth/length bound')
    return value


def _native_host():
    if os.name != 'nt' or platform.system() != 'Windows' or platform.machine().casefold() not in ('amd64', 'x86_64') or struct.calcsize('P') != 8:
        raise PublicationError('Native Windows x64 is required; no POSIX publication fallback')
    abi_layout()


def _utf16(value):
    raw = value.encode('utf-16-le')
    if '\0' in value or len(raw) > 65532:
        raise PublicationError('Invalid bounded Windows UTF16 string')
    storage = (U16 * (len(raw) // 2 + 1)).from_buffer_copy(raw + b'\0\0')
    return storage, UNICODE_STRING(len(raw), len(raw) + 2, ct.cast(storage, PVOID))


def _decode_utf16(pointer, units):
    return ct.string_at(pointer, units * 2).decode('utf-16-le')


def _rename_buffer(parent, name):
    _component(name); raw = name.encode('utf-16-le')
    size = ct.sizeof(FILE_RENAME_INFORMATION) + len(raw)
    buffer = ct.create_string_buffer(size)
    header = FILE_RENAME_INFORMATION.from_buffer(buffer)
    header.Flags, header.RootDirectory, header.FileNameLength = 0, parent, len(raw)
    ct.memmove(ct.addressof(buffer) + FILE_RENAME_INFORMATION.FileName.offset, raw, len(raw))
    return buffer


def _directory_names(raw):
    """Parse FILE_NAMES_INFORMATION class12 with complete bounded chaining."""
    names, cursor = [], 0
    if type(raw) is not bytes or not raw or len(raw) > 65536:
        raise PublicationError('Invalid native directory enumeration buffer')
    while True:
        if len(raw) - cursor < 12:
            raise PublicationError('Truncated native directory entry')
        next_offset, _index, size = struct.unpack_from('<III', raw, cursor)
        if size & 1 or size > 510 or size > len(raw) - cursor - 12:
            raise PublicationError('Invalid native directory name byte bound')
        try: name = raw[cursor + 12:cursor + 12 + size].decode('utf-16-le')
        except UnicodeError as error: raise PublicationError('Invalid directory UTF16') from error
        if name not in ('.', '..'): names.append(_component(name))
        if not next_offset: break
        if next_offset < 12 + size or next_offset & 3 or next_offset >= len(raw) - cursor:
            raise PublicationError('Invalid native directory chain offset')
        cursor += next_offset
    if len({name.casefold() for name in names}) != len(names):
        raise PublicationError('Native enumeration contains aliased names')
    return names


def _read_reference(reference, *, maximum=MAX_METADATA, document=True):
    contract.fields(reference, ('path', 'sha256'), 'publication evidence reference')
    if type(reference['path']) is not str: raise PublicationError('Explicit absolute evidence path required')
    path = Path(reference['path']); pin = contract.pin(reference['sha256'], 'publication evidence')
    if not path.is_absolute() or '..' in path.parts:
        raise PublicationError('Explicit absolute evidence path required')
    if document:
        return contract.read_metadata(path, pin, 'original Windows publication evidence')
    # Original console data is bounded and pinned, never interpreted as code.
    raw = _ordinary_bytes(path, maximum)
    if _sha(raw) != pin: raise PublicationError('Original console differs from its pin')
    return raw


def _ordinary_bytes(path, maximum):
    """Bound an ordinary input read and join its opened and named identities."""
    path = Path(path)
    for current in reversed((path, *path.parents)):
        info = current.lstat(); attrs = getattr(info, 'st_file_attributes', 0)
        if attrs & 0x400 or not (stat.S_ISREG(info.st_mode) if current == path else stat.S_ISDIR(info.st_mode)) or current == path and info.st_nlink != 1:
            raise PublicationError('Original input must be ordinary and singly linked')
    before = path.lstat()
    identity = lambda state: (state.st_dev, state.st_ino, state.st_size, state.st_mtime_ns,
        state.st_ctime_ns, state.st_nlink, state.st_mode, getattr(state, 'st_file_attributes', 0))
    if before.st_size > maximum: raise PublicationError('Original input exceeds its bound')
    with path.open('rb') as stream:
        if identity(os.fstat(stream.fileno())) != identity(before): raise PublicationError('Evidence changed before read')
        raw = stream.read(maximum + 1)
        after = os.fstat(stream.fileno())
    if identity(before) != identity(after) or identity(before) != identity(path.lstat()) or len(raw) > maximum:
        raise PublicationError('Original input changed during read')
    return raw


@dataclass(frozen=True)
class Qualification:
    _data: bytes
    _seal: object

    def as_dict(self):
        if self._seal is not _TOKEN: raise PublicationError('Unadmitted publication qualification')
        return json.loads(self._data)


def admit_qualification(reference, pin=None, *, source_identity, runtime_identity):
    """Cross-check complete original native cases; a status label is insufficient."""
    if pin is not None: reference = {'path': os.fspath(reference), 'sha256': pin}
    report = _read_reference(reference)
    contract.fields(report, ('schema_version', 'kind', 'scope', 'policy', 'source_identity',
        'runtime_identity', 'filesystem', 'run_report', 'observations', 'console'), 'native publication qualification')
    if type(report['schema_version']) is not int or report['schema_version'] != 1 or report['kind'] != 'foundation-windows-publication-qualification-v1' or report['scope'] != SCOPE or report['policy'] != POLICY:
        raise PublicationError('Unsupported native publication qualification subject')
    if report['source_identity'] != source_identity or report['runtime_identity'] != runtime_identity:
        raise PublicationError('Native publication source/runtime identity does not join')
    if type(source_identity) is not dict or set(source_identity) != set(SOURCE_FILES):
        raise PublicationError('Complete publication/diagnostic/process/contract source identity required')
    for name, digest in source_identity.items(): contract.pin(digest, name)
    if source_identity['tools/appended_engine_windows_contract.py'] != CONTRACT_SHA256:
        raise PublicationError('Publication uses a different Windows contract source')
    _validate_runtime(runtime_identity)
    filesystem = report['filesystem']
    contract.fields(filesystem, ('name', 'volume_serial'), 'qualified local filesystem')
    if filesystem['name'] != 'NTFS' or type(filesystem['volume_serial']) is not int or not 0 < filesystem['volume_serial'] < 2 ** 64:
        raise PublicationError('Qualified local NTFS volume identity required')
    run = _read_reference(report['run_report'])
    contract.fields(run, ('schema_version', 'system', 'status', 'inventory', 'excluded', 'results'), 'complete native case inventory')
    if run['schema_version'] != 1 or type(run['schema_version']) is not int or run['system'] != 'Windows' or run['status'] != 'passed' or run['excluded'] != {}:
        raise PublicationError('Native qualification has failed/incomplete/excluded cases')
    inventory = run['inventory']
    if (type(inventory) is not list or len(inventory) != len(CASE_NAMES) or
            any(type(name) is not str for name in inventory) or len(set(inventory)) != len(inventory)):
        raise PublicationError('Native qualification case inventory is incomplete')
    names = {name.rsplit('.', 1)[-1]: name for name in inventory if type(name) is str and '.NativePublication.' in name}
    if type(run['results']) is not dict or set(names) != set(CASE_NAMES) or set(run['results']) != set(inventory) or any(run['results'][name] != {'status': 'passed'} for name in inventory):
        raise PublicationError('Native qualification cases are missing, repeated or not passed')
    observations = _read_reference(report['observations'])
    contract.fields(observations, ('schema_version', 'kind', 'scope', 'policy', 'source_identity',
        'runtime_identity', 'filesystem', 'cases'), 'original native publication observations')
    if (observations['schema_version'] != 1 or type(observations['schema_version']) is not int or
            observations['kind'] != 'foundation-windows-publication-observations-v1' or
            any(observations[name] != report[name] for name in ('scope', 'policy', 'source_identity', 'runtime_identity', 'filesystem')) or
            type(observations['cases']) is not dict or set(observations['cases']) != set(CASE_NAMES)):
        raise PublicationError('Original native observations do not join the qualification')
    for name, item in observations['cases'].items():
        contract.fields(item, ('operation', 'observed'), 'native case observation')
        if item['operation'] != name or type(item['observed']) is not dict or not item['observed']:
            raise PublicationError('Native case lacks original operation/readback observations')
    console = _read_reference(report['console'], maximum=64 * 1024 * 1024, document=False)
    marker = b'WINDOWS_PUBLICATION_OBSERVATIONS_SHA256=' + report['observations']['sha256'].encode('ascii')
    if marker not in console:
        raise PublicationError('Original console does not bind the complete native observations')
    facts = {'kind': report['kind'], 'policy': POLICY, 'reference': copy.deepcopy(reference),
        'source_identity': copy.deepcopy(source_identity), 'runtime_identity': copy.deepcopy(runtime_identity),
        'filesystem': copy.deepcopy(filesystem), 'originals': {name: copy.deepcopy(report[name]) for name in ('run_report', 'observations', 'console')},
        'production_eligible': False, 'native_runtime_qualified': False, 'power_loss_guarantee': False}
    return Qualification(encoded(facts), _TOKEN)


def _validate_runtime(value):
    contract.fields(value, ('python_path', 'python_sha256', 'python_version', 'system', 'machine',
        'pointer_bits', 'windows_version', 'system_root'), 'publication runtime identity')
    contract.windows_path(value['python_path'], 'actual controller Python')
    contract.pin(value['python_sha256'], 'actual controller Python')
    contract.windows_path(value['system_root'], 'actual Windows directory')
    if value['system'] != 'Windows' or value['machine'] != 'x86_64' or type(value['pointer_bits']) is not int or value['pointer_bits'] != 64 or type(value['python_version']) is not str or not re.fullmatch(r'3\.[0-9]+\.[0-9]+', value['python_version']):
        raise PublicationError('Native Windows x64 Python runtime required')
    if tuple(map(int, value['python_version'].split('.'))) < (3, 9, 0):
        raise PublicationError('The developer helper baseline requires Python 3.9 or newer')
    versions = value['windows_version']
    if type(versions) is not list or len(versions) != 3 or any(type(item) is not int or not 0 <= item < 2 ** 32 for item in versions):
        raise PublicationError('Actual bounded Windows version required')


class _Native:
    """Finite x64 Win32/NT binding. Constructing it is a real native operation."""
    def __init__(self):
        _native_host()
        self.k = ct.WinDLL('kernel32', use_last_error=True)
        self.a = ct.WinDLL('advapi32', use_last_error=True)
        self.n = ct.WinDLL('ntdll', use_last_error=True)
        self.events = []
        self._signatures()
        self.sid = self._current_sid()

    def _signatures(self):
        signatures = {
            'CreateFileW': ([PVOID, U32, U32, PVOID, U32, U32, HANDLE], HANDLE),
            'CloseHandle': ([HANDLE], I32), 'GetFileType': ([HANDLE], U32),
            'GetFileInformationByHandleEx': ([HANDLE, U32, PVOID, U32], I32),
            'GetFinalPathNameByHandleW': ([HANDLE, PVOID, U32, U32], U32),
            'GetDriveTypeW': ([PVOID], U32), 'GetWindowsDirectoryW': ([PVOID, U32], U32),
            'GetVolumeInformationByHandleW': ([HANDLE, PVOID, U32, ct.POINTER(U32), ct.POINTER(U32), ct.POINTER(U32), PVOID, U32], I32),
            'ReadFile': ([HANDLE, PVOID, U32, ct.POINTER(U32), PVOID], I32),
            'WriteFile': ([HANDLE, PVOID, U32, ct.POINTER(U32), PVOID], I32),
            'SetFilePointerEx': ([HANDLE, I64, ct.POINTER(I64), U32], I32),
            'FlushFileBuffers': ([HANDLE], I32), 'GetCurrentProcess': ([], HANDLE),
            'DuplicateHandle': ([HANDLE, HANDLE, HANDLE, ct.POINTER(HANDLE), U32, I32, U32], I32),
            'LocalFree': ([PVOID], PVOID),
        }
        for name, (args, result) in signatures.items():
            function = getattr(self.k, name); function.argtypes, function.restype = args, result
        signatures = {
            'OpenProcessToken': ([HANDLE, U32, ct.POINTER(HANDLE)], I32),
            'GetTokenInformation': ([HANDLE, U32, PVOID, U32, ct.POINTER(U32)], I32),
            'ConvertSidToStringSidW': ([PVOID, ct.POINTER(PVOID)], I32),
            'ConvertStringSecurityDescriptorToSecurityDescriptorW': ([PVOID, U32, ct.POINTER(PVOID), ct.POINTER(U32)], I32),
            'GetSecurityInfo': ([HANDLE, U32, U32, ct.POINTER(PVOID), PVOID, ct.POINTER(PVOID), PVOID, ct.POINTER(PVOID)], U32),
            'GetSecurityDescriptorControl': ([PVOID, ct.POINTER(U16), ct.POINTER(U32)], I32),
        }
        for name, (args, result) in signatures.items():
            function = getattr(self.a, name); function.argtypes, function.restype = args, result
        self.n.NtCreateFile.argtypes = [ct.POINTER(HANDLE), U32, ct.POINTER(OBJECT_ATTRIBUTES), ct.POINTER(IO_STATUS_BLOCK), PVOID, U32, U32, U32, U32, PVOID, U32]
        self.n.NtCreateFile.restype = I32
        self.n.NtSetInformationFile.argtypes = [HANDLE, ct.POINTER(IO_STATUS_BLOCK), PVOID, U32, U32]
        self.n.NtSetInformationFile.restype = I32
        self.n.NtQueryDirectoryFile.argtypes = [HANDLE, HANDLE, PVOID, PVOID, ct.POINTER(IO_STATUS_BLOCK), PVOID, U32, U32, U8, PVOID, U8]
        self.n.NtQueryDirectoryFile.restype = I32
        self.n.RtlNtStatusToDosError.argtypes, self.n.RtlNtStatusToDosError.restype = [I32], U32

    def _win(self, ok, operation):
        if not ok: raise OSError(ct.get_last_error(), operation)

    def _nt(self, status, operation):
        # All handles are synchronous. Pending/alternate success must not be
        # mistaken for completed creation/publication.
        if status != 0:
            error = int(self.n.RtlNtStatusToDosError(I32(status)))
            if status & 0xffffffff in (0xc0000035, 0xc000003a, 0xc0000034):
                kind = FileExistsError if status & 0xffffffff == 0xc0000035 else FileNotFoundError
                raise kind(error, operation)
            raise OSError(error, operation + ' NTSTATUS=0x%08x' % (status & 0xffffffff))

    def _completed_nt(self, status, operation, handle, *storage):
        if status & 0xffffffff == 0x103:
            # Synchronous handles exclude this supported-path result. Keep all
            # ctypes storage alive if that native contract is violated anyway.
            record = {'operation': operation, 'handle': handle, 'storage': storage}
            self._unknown_operations = getattr(self, '_unknown_operations', []) + [record]
            raise OwnershipUncertain('Unexpected pending native operation; retain its storage and handles')
        self._nt(status, operation)

    def close(self, handle):
        self._win(self.k.CloseHandle(handle), 'CloseHandle'); self.events.append('close')

    def _sid_text(self, pointer):
        output = PVOID(); self._win(self.a.ConvertSidToStringSidW(pointer, ct.byref(output)), 'ConvertSidToStringSidW')
        try:
            chunks = []
            for index in range(184):
                unit = ct.string_at(output.value + index * 2, 2)
                if unit == b'\0\0': return b''.join(chunks).decode('utf-16-le')
                chunks.append(unit)
            raise PublicationError('SID string exceeds its bound')
        finally:
            if self.k.LocalFree(output): raise PublicationError('LocalFree SID failed')

    def _current_sid(self):
        token = HANDLE(); self._win(self.a.OpenProcessToken(self.k.GetCurrentProcess(), 8, ct.byref(token)), 'OpenProcessToken')
        try:
            size = U32(); self.a.GetTokenInformation(token, 1, None, 0, ct.byref(size))
            if not 16 <= size.value <= 65536: raise PublicationError('Invalid TOKEN_USER bound')
            buffer = ct.create_string_buffer(size.value)
            self._win(self.a.GetTokenInformation(token, 1, buffer, size, ct.byref(size)), 'GetTokenInformation')
            return self._sid_text(HANDLE.from_buffer(buffer).value)
        finally: self.close(token)

    def _private_sd(self):
        text, _us = _utf16('O:' + self.sid + 'D:P(A;OICI;FA;;;' + self.sid + ')(A;OICI;FA;;;SY)')
        descriptor = PVOID(); size = U32()
        self._win(self.a.ConvertStringSecurityDescriptorToSecurityDescriptorW(text, 1, ct.byref(descriptor), ct.byref(size)), 'ConvertStringSecurityDescriptor')
        return descriptor

    def verify_private(self, handle):
        owner, dacl, descriptor = PVOID(), PVOID(), PVOID()
        error = self.a.GetSecurityInfo(handle, 1, 5, ct.byref(owner), None, ct.byref(dacl), None, ct.byref(descriptor))
        if error: raise OSError(error, 'GetSecurityInfo')
        try:
            control, revision = U16(), U32()
            self._win(self.a.GetSecurityDescriptorControl(descriptor, ct.byref(control), ct.byref(revision)), 'GetSecurityDescriptorControl')
            if self._sid_text(owner) != self.sid or not dacl or not control.value & 0x1000:
                raise PublicationError('New Windows output lacks caller-owned protected DACL')
            header = ct.string_at(dacl, 8); size, count = struct.unpack_from('<HH', header, 2)
            if not 8 <= size <= 65535 or count != 2: raise PublicationError('Private DACL has unknown entries')
            raw, cursor, seen = ct.string_at(dacl, size), 8, set()
            for _index in range(count):
                if len(raw) - cursor < 8: raise PublicationError('Truncated private ACE')
                kind, flags, length, mask = struct.unpack_from('<BBHI', raw, cursor)
                if kind != 0 or flags & ~3 or cursor & 3 or length & 3 or length < 16 or length > len(raw) - cursor or mask != 0x1f01ff:
                    raise PublicationError('Unsupported private ACE')
                seen.add(self._sid_text(dacl.value + cursor + 8)); cursor += length
            if cursor != len(raw) or seen != {self.sid, 'S-1-5-18'}: raise PublicationError('Private output DACL grants unexpected principal')
        finally:
            if descriptor and self.k.LocalFree(descriptor): raise PublicationError('LocalFree security failed')

    def final_path(self, handle):
        buffer = (U16 * 32768)(); count = self.k.GetFinalPathNameByHandleW(handle, buffer, len(buffer), 0)
        if not count or count >= len(buffer): self._win(False, 'GetFinalPathNameByHandleW')
        value = _decode_utf16(buffer, count)
        if not value.startswith('\\\\?\\'): raise PublicationError('Unexpected final Windows namespace')
        return value[4:].replace('\\', '/')

    def state(self, handle, *, _raw=False):
        if self.k.GetFileType(handle) != 1: raise PublicationError('Windows publication requires a disk file handle')
        basic, standard, tag, identity = FILE_BASIC_INFO(), FILE_STANDARD_INFO(), FILE_ATTRIBUTE_TAG_INFO(), FILE_ID_INFO()
        for number, value in ((0, basic), (1, standard), (9, tag), (18, identity)):
            self._win(self.k.GetFileInformationByHandleEx(handle, number, ct.byref(value), ct.sizeof(value)), 'GetFileInformationByHandleEx')
        invalid = (tag.FileAttributes != basic.FileAttributes or not identity.VolumeSerialNumber or not any(identity.FileId) or
                tag.FileAttributes & (0x400 | 0x40 | 0x1000 | 0x40000 | 0x400000) or tag.ReparseTag or
                bool(tag.FileAttributes & 16) != bool(standard.Directory) or standard.DeletePending or
                not standard.Directory and standard.NumberOfLinks != 1 or standard.EndOfFile < 0)
        if invalid and not _raw:
            raise PublicationError('Windows output is reparse/device/offline/linked/delete-pending')
        self.events.append('state')
        result = {'identity': [int(identity.VolumeSerialNumber), bytes(identity.FileId).hex()],
            'directory': bool(standard.Directory), 'links': int(standard.NumberOfLinks),
            'bytes': int(standard.EndOfFile), 'attributes': int(tag.FileAttributes),
            'version': [int(basic.CreationTime), int(basic.LastWriteTime), int(basic.ChangeTime)],
            'path': self.final_path(handle)}
        if _raw:
            # Actual queried observations allow identity-confirmed closure of a
            # rejected input. They are not ordinary-file or qualification proof.
            result.update(_basic_attributes=int(basic.FileAttributes),
                _reparse_tag=int(tag.ReparseTag), _delete_pending=bool(standard.DeletePending))
        return result

    def open_root(self, root):
        if not re.fullmatch('[A-Z]:/', root): raise PublicationError('Local drive root required')
        text, _us = _utf16(root.replace('/', '\\'))
        if self.k.GetDriveTypeW(text) != 3: raise PublicationError('Only local fixed drives are admitted')
        handle = self.k.CreateFileW(text, 0x1200a1, 3, None, 3, 0x02200000, None)
        if handle == ct.c_void_p(-1).value: self._win(False, 'CreateFileW drive root')
        return handle

    def open_child(self, parent, name, *, create=False, directory=False, writable=False, metadata_only=False, input_file=False):
        if type(input_file) is not bool or input_file and (create or directory or writable or metadata_only):
            raise PublicationError('Input role requires an existing ordinary read-only file')
        _component(name); text, us = _utf16(name)
        sd = self._private_sd() if create else None
        attributes = OBJECT_ATTRIBUTES(ct.sizeof(OBJECT_ATTRIBUTES), parent, ct.pointer(us), 0x1040, sd, None)
        handle, status = HANDLE(), IO_STATUS_BLOCK()
        access = (0x1200a1 if directory else 0x120080 | (0 if metadata_only else 1))
        if create and not directory: access = 0xc0030000 | 0x100000  # generic read/write, DELETE, READ_CONTROL, SYNCHRONIZE
        elif writable: access |= 0x10000
        options = 0x20 | (1 if create and directory else 0x200000)
        if create and not directory: options |= 0x40
        if input_file:
            access = 0x80100000  # GENERIC_READ | SYNCHRONIZE: documented seeking access
            options |= 0x40     # NON_DIRECTORY_FILE; raw observations still need ordinary admission
        sharing = 1 if input_file else (3 if directory or create else 7)
        failure, pending = None, False
        try:
            code = int(self.n.NtCreateFile(ct.byref(handle), access, ct.byref(attributes), ct.byref(status), None,
                0x80, sharing, 2 if create else 1, options, None, 0))
            pending = code & 0xffffffff == 0x103
            self._completed_nt(code, 'NtCreateFile ' + name, handle, status, attributes, us, text, sd)
            if not handle.value or status.Information != (2 if create else 1):
                raise OwnershipUncertain('Native create/open disposition differs; preserve unknown outcome')
        except BaseException as error: failure = error
        cleanup_error = None
        if sd and not pending:
            try:
                if self.k.LocalFree(sd): cleanup_error = PublicationError('LocalFree creation security failed')
            except BaseException as error: cleanup_error = error
        if cleanup_error is not None:
            self._unknown_security_descriptors = getattr(self, '_unknown_security_descriptors', []) + [sd]
            if handle.value:
                self._unknown_handles = getattr(self, '_unknown_handles', []) + [handle.value]
            raise OwnershipUncertain('Creation security cleanup failed; retain the native open outcome') from cleanup_error
        if failure is not None:
            if handle.value:
                if create or isinstance(failure, OwnershipUncertain):
                    self._unknown_handles = getattr(self, '_unknown_handles', []) + [handle.value]
                else:
                    try: self.close(handle)
                    except BaseException:
                        self._unknown_handles = getattr(self, '_unknown_handles', []) + [handle.value]
                        raise
            raise failure
        self.events.append('create' if create else 'open')
        return handle.value

    def filesystem(self, handle):
        name = (U16 * 64)(); serial, maximum, flags = U32(), U32(), U32()
        self._win(self.k.GetVolumeInformationByHandleW(handle, None, 0, ct.byref(serial), ct.byref(maximum), ct.byref(flags), name, len(name)), 'GetVolumeInformationByHandleW')
        fs = bytes(name).decode('utf-16-le').split('\0', 1)[0]
        if fs != 'NTFS' or not flags.value & 8 or flags.value & 0x80000:
            raise PublicationError('Writable local NTFS with persistent ACLs required')
        return {'name': fs, 'volume_serial': self.state(handle)['identity'][0]}

    def runtime_identity(self):
        executable = Path(sys.executable)
        # The runner separately admits its complete current Python runtime.
        raw = _ordinary_bytes(executable, MAX_FILE)
        path = PureWindowsPath(str(executable)).as_posix(); contract.windows_path(path, 'controller')
        root = (U16 * 32768)(); count = self.k.GetWindowsDirectoryW(root, len(root))
        if not count or count >= len(root): self._win(False, 'GetWindowsDirectoryW')
        version = sys.getwindowsversion()
        return {'python_path': path, 'python_sha256': _sha(raw), 'python_version': '.'.join(map(str, sys.version_info[:3])),
            'system': 'Windows', 'machine': 'x86_64', 'pointer_bits': 64,
            'windows_version': [version.major, version.minor, version.build],
            'system_root': _decode_utf16(root, count).replace('\\', '/')}

    def names(self, handle, *, deadline=None, maximum_entries=None):
        # Input callers supply their already fixed lifetime and member bound.
        # Existing output callers retain their original limits and behavior.
        import math
        if deadline is not None and (type(deadline) not in (int, float) or not math.isfinite(deadline)):
            raise PublicationError('Finite native enumeration deadline required')
        if maximum_entries is not None and (type(maximum_entries) is not int or not 1 <= maximum_entries <= 1000000):
            raise PublicationError('Finite native enumeration entry bound required')
        bound = 524288 if maximum_entries is None else maximum_entries
        output, restart = [], True
        for _page in range(8192):
            if deadline is not None and time.monotonic() >= deadline:
                raise PublicationError('Native directory enumeration deadline expired')
            buffer, status = ct.create_string_buffer(65536), IO_STATUS_BLOCK()
            result = int(self.n.NtQueryDirectoryFile(handle, None, None, None, ct.byref(status), buffer,
                len(buffer), 12, 0, None, int(restart)))
            if result & 0xffffffff == 0x80000006: break
            self._completed_nt(result, 'NtQueryDirectoryFile', handle, buffer, status)
            if not 0 < status.Information <= len(buffer): raise PublicationError('Incomplete directory enumeration')
            output.extend(_directory_names(buffer.raw[:status.Information])); restart = False
            if len(output) > bound: raise PublicationError('Native directory entry bound exceeded')
        else: raise PublicationError('Output enumeration page bound exceeded')
        if deadline is not None and time.monotonic() >= deadline:
            raise PublicationError('Native directory enumeration deadline expired')
        if len(output) != len({name.casefold() for name in output}): raise PublicationError('Aliased native directory entries')
        return sorted(output)

    def write(self, handle, raw):
        buffer = ct.create_string_buffer(raw); done = U32()
        self._win(self.k.WriteFile(handle, buffer, len(raw), ct.byref(done), None), 'WriteFile')
        return done.value

    def flush(self, handle):
        self._win(self.k.FlushFileBuffers(handle), 'FlushFileBuffers'); self.events.append('flush')

    def read(self, handle, maximum):
        self._win(self.k.SetFilePointerEx(handle, 0, None, 0), 'SetFilePointerEx')
        chunks, count = [], 0
        while True:
            size = min(1024 * 1024, maximum - count + 1); buffer, done = ct.create_string_buffer(size), U32()
            self._win(self.k.ReadFile(handle, buffer, size, ct.byref(done), None), 'ReadFile')
            if not done.value: break
            count += done.value
            if count > maximum: raise PublicationError('Native file exceeds bounded read')
            chunks.append(buffer.raw[:done.value])
        self.events.append('read'); return b''.join(chunks)

    def read_at(self, handle, offset, count):
        """One synchronous bounded chunk; input owner locks the complete sequence."""
        if type(offset) is not int or not 0 <= offset < 2 ** 63 or type(count) is not int or not 0 <= count <= 1024 * 1024:
            raise PublicationError('Bounded native input offset/count required')
        if not count: return b''
        position = I64()
        self._win(self.k.SetFilePointerEx(handle, offset, ct.byref(position), 0), 'SetFilePointerEx input')
        if position.value != offset:
            raise OwnershipUncertain('Native input seek position differs')
        buffer, done = ct.create_string_buffer(count), U32()
        if not self.k.ReadFile(handle, buffer, count, ct.byref(done), None):
            error = ct.get_last_error()
            if error == 997:  # ERROR_IO_PENDING is outside the synchronous admitted path
                record = {'operation': 'ReadFile input', 'handle': handle, 'storage': (buffer, done)}
                self._unknown_operations = getattr(self, '_unknown_operations', []) + [record]
                raise OwnershipUncertain('Unexpected pending input read; retain buffers and handle')
            raise OSError(error, 'ReadFile input')
        if done.value > count:
            raise OwnershipUncertain('Native input read count exceeds its request')
        return buffer.raw[:done.value]

    def stream(self, handle):
        import msvcrt
        duplicate = HANDLE(); process = self.k.GetCurrentProcess()
        descriptor = None
        try:
            self._win(self.k.DuplicateHandle(process, handle, process, ct.byref(duplicate), 0, 0, 2), 'DuplicateHandle')
            descriptor = msvcrt.open_osfhandle(duplicate.value, os.O_APPEND)
            msvcrt.setmode(descriptor, os.O_BINARY)
            return os.fdopen(descriptor, 'wb', buffering=0)
        except BaseException:
            # Ownership transfers to the CRT only after open_osfhandle returns.
            # Do not guess whether a partially failed stream wrapper closed it.
            if descriptor is not None:
                self._unknown_stream_descriptors = getattr(self, '_unknown_stream_descriptors', []) + [descriptor]
            elif duplicate.value:
                self._unknown_handles = getattr(self, '_unknown_handles', []) + [duplicate.value]
            raise

    def stream_state(self, stream):
        import msvcrt
        if stream.closed: raise OwnershipUncertain('Owned native stream was closed before sealing')
        descriptor = stream.fileno()
        handle = msvcrt.get_osfhandle(descriptor)
        if type(descriptor) is not int or descriptor < 0 or type(handle) is not int or handle in (-2, -1, 0):
            raise OwnershipUncertain('Owned CRT descriptor has no ordinary native file handle')
        state = self.state(handle)
        if state['directory']: raise OwnershipUncertain('Owned stream targets a directory')
        return {'descriptor': descriptor, 'handle': handle, 'identity': state['identity'], 'path': state['path']}

    def rename_new(self, handle, parent, name):
        buffer, status = _rename_buffer(parent, name), IO_STATUS_BLOCK()
        code = int(self.n.NtSetInformationFile(handle, ct.byref(status), buffer, len(buffer), 10))
        self._completed_nt(code, 'NtSetInformationFile no-replace rename', handle, buffer, status)
        self.events.append('rename')

    def remove(self, handle):
        value, status = U8(1), IO_STATUS_BLOCK()
        code = int(self.n.NtSetInformationFile(handle, ct.byref(status), ct.byref(value), 1, 13))
        self._completed_nt(code, 'NtSetInformationFile owned delete', handle, value, status)
        # The handle may only be closed after successful disposition.
        self.close(handle); self.events.append('remove')


def _limits(value):
    names = ('maximum_output_bytes', 'maximum_log_bytes', 'maximum_entries', 'maximum_file_bytes', 'io_seconds')
    defaults = {'maximum_output_bytes': 64 * 1024 ** 3, 'maximum_log_bytes': 64 * 1024 ** 2,
        'maximum_entries': 524288, 'maximum_file_bytes': MAX_FILE, 'io_seconds': 120}
    if type(value) is not dict: raise PublicationError('Explicit publication limits required')
    # Runner phase-limit records may include its separate command budgets.
    for name in names:
        if name in value: defaults[name] = value[name]
    bounds = {'maximum_output_bytes': 1024 ** 4, 'maximum_log_bytes': 128 * 1024 ** 2,
        'maximum_entries': 524288, 'maximum_file_bytes': MAX_FILE, 'io_seconds': 3600}
    for name, maximum in bounds.items():
        if type(defaults[name]) is not int or not 1 <= defaults[name] <= maximum:
            raise PublicationError('Invalid publication limit: ' + name)
    return defaults


@dataclass
class OwnedLog:
    path: str
    pending_path: str
    _stream: object
    identity: list
    _handle: object
    _workspace: object
    _stream_facts: bytes
    _state: str = 'open'
    _owner: object = None

    @property
    def stream(self):
        return self._stream


@dataclass(frozen=True)
class JoinedStage:
    _data: bytes
    _seal: object

    def as_dict(self):
        if self._seal is not _TOKEN: raise PublicationError('Unowned joined stage')
        return json.loads(self._data)


class Workspace:
    """Retain native filesystem and Job writers through final publication."""
    def __init__(self, *args, **kwargs):
        raise PublicationError('Use Workspace.create_new with admitted native evidence')

    @classmethod
    def create_new(cls, output, *, protected_paths, limits, qualification):
        _native_host()
        if type(qualification) is not Qualification or qualification._seal is not _TOKEN:
            raise PublicationError('Original native publication qualification is required')
        facts = qualification.as_dict(); native = _Native()
        if native.runtime_identity() != facts['runtime_identity']:
            raise PublicationError('Actual native runtime differs from publication qualification')
        root = Path(__file__).resolve().parents[1]
        if any(_sha(_ordinary_bytes(root / name, MAX_METADATA)) != pin for name, pin in facts['source_identity'].items()):
            raise PublicationError('Publication/diagnostic/process/contract source changed after qualification')
        authority = [facts['reference']['path'], *(row['path'] for row in facts['originals'].values()),
            facts['runtime_identity']['python_path'], facts['runtime_identity']['system_root'],
            *(PureWindowsPath(root / name).as_posix() for name in SOURCE_FILES)]
        return cls._create(native, output, (*protected_paths, *authority), limits, facts['filesystem'], diagnostic=False)

    @classmethod
    def _create(cls, native, output, protected_paths, limits, filesystem=None, *, diagnostic=True):
        output = contract.windows_path(os.fspath(output), 'fresh native Workspace')
        selected = PureWindowsPath(output)
        if not selected.name: raise PublicationError('Fresh Workspace must be below a local drive root')
        protected = tuple(contract.windows_path(os.fspath(item), 'protected native input') for item in protected_paths)
        if any(selected == PureWindowsPath(item) or selected in PureWindowsPath(item).parents or PureWindowsPath(item) in selected.parents for item in protected):
            raise PublicationError('Workspace overlaps a protected retained input')
        self = object.__new__(cls)
        self.native, self.output, self.limits, self.protected_paths = native, output, _limits(limits), protected
        self.directories, self.identities, self.logs, self.files, self.joined = {}, {}, [], {}, []
        self._launches = []
        self.closed, self.uncertain, self.failed, self.committed = False, False, False, False
        self.diagnostic = diagnostic
        self.ancestors = []
        try:
            parent_path = selected.parent
            current = selected.drive + '/'; handle = native.open_root(current)
            self.ancestors.append((current, handle, native.state(handle)['identity']))
            self._check_handle(handle, current, True)
            for part in parent_path.parts[1:]:
                handle = native.open_child(handle, part, directory=True)
                current += ('' if current.endswith('/') else '/') + part
                state = self._check_handle(handle, current, True)
                self.ancestors.append((current, handle, state['identity']))
            actual = native.filesystem(handle)
            if filesystem is not None and actual != filesystem:
                raise PublicationError('Selected filesystem/volume differs from native qualification')
            self.filesystem = copy.deepcopy(actual)
            root_handle = native.open_child(handle, selected.name, create=True, directory=True)
            # Once mutation starts, any incomplete failure preserves its root.
            self.root = root_handle
            state = self._check_handle(root_handle, output, True); native.verify_private(root_handle)
            self.directories[''] = root_handle; self.identities[''] = state['identity']
            self.check_anchors()
            return self
        except BaseException as error:
            if hasattr(self, 'root') or isinstance(error, OwnershipUncertain) or getattr(native, '_unknown_handles', []):
                self.uncertain = True; _RETAINED.append(self)
            else:
                for _path, handle, _identity in reversed(self.ancestors):
                    try: native.close(handle)
                    except BaseException: self.uncertain = True; _RETAINED.append(self)
            raise

    def _check_handle(self, handle, path, directory):
        state = self.native.state(handle)
        if state['directory'] is not directory or state['path'] != path:
            raise PublicationError('Native output kind or normalized path identity differs')
        if not directory and state['links'] != 1: raise PublicationError('Native file must be singly linked')
        return state

    def _open_child(self, *args, **kwargs):
        try: return self.native.open_child(*args, **kwargs)
        except BaseException as error:
            if isinstance(error, OwnershipUncertain) or getattr(self.native, '_unknown_handles', []) or getattr(self.native, '_unknown_operations', []):
                self.retain_uncertain(None, None, 'native open/create outcome is uncertain')
            raise

    def _ready(self):
        if self.closed or self.uncertain: raise OwnershipUncertain('Workspace is closed or uncertain; stop dependent work')
        if any(log._state == 'running' for log in self.logs):
            raise PublicationError('Command writers remain active; publication/inspection is forbidden')

    def _parent(self, path):
        _relative(path); parent = path.rsplit('/', 1)[0] if '/' in path else ''
        if parent not in self.directories: raise PublicationError('Output parent must be explicitly owned first')
        return self.directories[parent], path.rsplit('/', 1)[-1]

    def check_anchors(self):
        if self.closed or self.uncertain: raise OwnershipUncertain('Workspace cannot revalidate uncertain/closed anchors')
        try:
            for path, handle, identity in self.ancestors:
                if self._check_handle(handle, path, True)['identity'] != identity:
                    raise OwnershipUncertain('Workspace ancestor identity changed')
            for path, handle in self.directories.items():
                absolute = self.output + ('/' + path if path else '')
                if self._check_handle(handle, absolute, True)['identity'] != self.identities[path]:
                    raise OwnershipUncertain('Workspace directory identity changed')
        except BaseException:
            self.retain_uncertain(None, None, 'anchor identity/kind/path verification failed')
            raise

    def mkdir_new(self, path):
        self._ready(); parent, name = self._parent(path); self.check_anchors()
        if path in self.directories: raise FileExistsError('Output directory already owned; no reuse')
        handle = self._open_child(parent, name, create=True, directory=True)
        try:
            state = self._check_handle(handle, self.output + '/' + path, True); self.native.verify_private(handle)
            self.directories[path], self.identities[path] = handle, state['identity']
            self.check_anchors()
        except BaseException:
            self._retained_directories = getattr(self, '_retained_directories', []) + [handle]
            self.retain_uncertain(None, None, 'new directory could not be verified'); raise
        return path

    def _pending(self, path):
        parent, name = self._parent(path); self.check_anchors()
        pending_name = '.' + name + '.pending-' + secrets.token_hex(16)
        handle = self._open_child(parent, pending_name, create=True)
        pending = (path.rsplit('/', 1)[0] + '/' if '/' in path else '') + pending_name
        try:
            state = self._check_handle(handle, self.output + '/' + pending, False); self.native.verify_private(handle)
        except BaseException:
            self._retained_pending = getattr(self, '_retained_pending', []) + [(pending, handle, None)]
            self.retain_uncertain(None, None, 'new pending file could not be verified'); raise
        return parent, name, pending, handle, state['identity']

    def _publish(self, path, pending, handle, identity):
        parent, name = self._parent(path); self.check_anchors()
        before = self._check_handle(handle, self.output + '/' + pending, False)
        if before['identity'] != identity:
            self.retain_uncertain(None, None, 'pending publication identity changed')
            raise OwnershipUncertain('Pending publication identity changed')
        raw = self.native.read(handle, self.limits['maximum_file_bytes'])
        self.native.flush(handle)
        try:
            self.native.rename_new(handle, parent, name)
            after = self._check_handle(handle, self.output + '/' + path, False)
            if after['identity'] != identity or after['bytes'] != len(raw) or self.native.read(handle, len(raw)) != raw:
                raise OwnershipUncertain('Published file identity/bytes differ')
            self.check_anchors()
            self.native.close(handle)
        except FileExistsError:
            # Known collision did not rename; owned pending bytes stay intact.
            self.failed = True
            raise
        except BaseException:
            self.retain_uncertain(None, None, 'publication result or close is uncertain'); raise
        row = {'path': path, 'sha256': _sha(raw), 'bytes': len(raw)}
        self.files[path] = copy.deepcopy(row)
        return row

    def publish_bytes_new(self, path, raw):
        self._ready()
        if type(raw) is not bytes or len(raw) > self.limits['maximum_file_bytes']:
            raise PublicationError('Bounded immutable publication bytes required')
        if path in self.files: raise FileExistsError('Output file already published')
        parent, _name, pending, handle, identity = self._pending(path)
        deadline, offset = time.monotonic() + self.limits['io_seconds'], 0
        try:
            while offset < len(raw):
                if time.monotonic() >= deadline: raise PublicationError('Publication write deadline exceeded')
                count = self.native.write(handle, raw[offset:offset + 1024 * 1024])
                if type(count) is not int or not 0 < count <= min(1024 * 1024, len(raw) - offset):
                    raise PublicationError('Incomplete native publication write')
                offset += count
            return self._publish(path, pending, handle, identity)
        except BaseException:
            self.failed = True
            # Pending files are retained, never erased by an automatic finally.
            self._retained_pending = getattr(self, '_retained_pending', []) + [(pending, handle, identity)]
            raise

    def open_log_new(self, path):
        self._ready(); _relative(path)
        if any(log.path.casefold() == path.casefold() for log in self.logs): raise FileExistsError('Log already selected')
        _parent, _name, pending, handle, identity = self._pending(path)
        retained = (pending, handle, identity)
        self._retained_pending = getattr(self, '_retained_pending', []) + [retained]
        stream = None
        try:
            stream = self.native.stream(handle)
            facts = self.native.stream_state(stream)
            if facts['identity'] != identity or facts['path'] != self.output + '/' + pending:
                raise OwnershipUncertain('New native stream does not target its created pending file')
            log = OwnedLog(path, pending, stream, identity, handle, self, encoded(facts))
            self.logs.append(log)
            self._check_stream(log)
        except BaseException:
            if stream is not None: self._retained_streams = getattr(self, '_retained_streams', []) + [stream]
            self.retain_uncertain(None, None, 'log stream creation uncertain'); raise
        self._retained_pending.remove(retained)
        return log

    def mark_running(self, log):
        self._ready(); self._log(log, 'open'); log._state = 'running'

    def _log(self, log, *states):
        if type(log) is not OwnedLog or log._workspace is not self or log not in self.logs or log._state not in states:
            raise PublicationError('Log ownership/state differs')

    def _check_stream(self, log):
        try:
            facts = self.native.stream_state(log.stream)
            primary = self._check_handle(log._handle, self.output + '/' + log.pending_path, False)
            if encoded(facts) != log._stream_facts or primary['identity'] != log.identity or facts['identity'] != log.identity:
                raise OwnershipUncertain('Owned stream descriptor/native file identity changed')
        except BaseException as error:
            self.retain_uncertain(log._owner, log, 'owned native stream identity cannot be confirmed')
            raise OwnershipUncertain('Owned stream descriptor/native file identity changed or closed') from error

    def bind_owner(self, log, owner):
        self._log(log, 'running')
        if isinstance(self.native, _Native) and not any(item[0] is log and item[1] is owner and item[2] is log.stream for item in self._launches):
            self.retain_uncertain(owner, log, 'supplied owner was not launched for this exact stream')
            raise PublicationError('Use Workspace.launch to associate this exact stream with its actual Job owner')
        if log._owner is not None or not isinstance(owner, process_tree.ProcessTree) or owner.job is None or owner.closed:
            raise PublicationError('Bind one actual open Windows Job owner to the running log')
        if isinstance(self.native, _Native) and (type(owner) is not process_tree.ProcessTree or
                type(owner.job) is not process_tree._WindowsJob or owner.job.handle is None):
            raise PublicationError('The native stream requires the actual returned Windows Job owner')
        self._check_stream(log)
        log._owner = owner

    def launch(self, log, argv, cwd, *, env, maximum_active_processes=None):
        """Launch with this exact owned stream; never accept a launch callback."""
        self._log(log, 'running')
        if self.closed or self.uncertain or log._owner is not None:
            raise OwnershipUncertain('Workspace cannot launch an already bound or uncertain log')
        self.check_anchors()
        self._check_stream(log)
        owner = None
        try:
            if maximum_active_processes is None:
                owner = process_tree.launch(argv, cwd, log.stream, env=env)
            else:
                owner = process_tree.launch(argv, cwd, log.stream, env=env,
                    maximum_active_processes=maximum_active_processes)
            self._launches.append((log, owner, log.stream))
            self.bind_owner(log, owner)
            return owner
        except BaseException:
            self.retain_uncertain(owner, log, 'launch or exact stream association is unconfirmed')
            raise

    def mark_joined(self, log, stage):
        self._log(log, 'running')
        owner = log._owner
        if owner is None:
            self.retain_uncertain(None, log, 'running log has no returned Job owner')
            raise OwnershipUncertain('Running log has no returned Job owner; retain workspace')
        if isinstance(self.native, _Native) and not any(item[0] is log and item[1] is owner and item[2] is log.stream for item in self._launches):
            self.retain_uncertain(owner, log, 'launched stream association changed')
            raise OwnershipUncertain('The actual launched stream/owner association changed')
        self._check_stream(log)
        if type(stage) is not dict or stage.get('phase') not in ('configure', 'build', 'install', 'probe'):
            raise PublicationError('Phase subject required before joining')
        try:
            code = owner.finish()
            owner.close()
            if not owner.closed or owner.process.poll() is None or code != owner.process.returncode:
                raise OwnershipUncertain('Job owner did not complete and close')
        except BaseException:
            self.retain_uncertain(owner, log, 'Job finish/close unconfirmed'); raise
        log._state = 'joined'; self.failed |= code != 0
        facts = copy.deepcopy(stage)
        if 'returncode' in facts and facts['returncode'] != code:
            self.failed = True; raise PublicationError('Phase claimed a different returncode')
        facts.update({'returncode': code, 'process_tree_closed': True, 'closure': 'actual-bound-job-finish-and-close'})
        joined = JoinedStage(encoded(facts), _TOKEN); self.joined.append(joined)
        return joined

    def mark_failed_joined(self, joined, reason):
        self._ready()
        if type(joined) is not JoinedStage or joined._seal is not _TOKEN or not any(joined is item for item in self.joined) or type(reason) is not str or not reason:
            raise PublicationError('An actual joined phase and explicit failure reason are required')
        self.failed = True
        return dict(joined.as_dict(), status='failed', error=reason)

    def seal_log(self, log):
        self._ready(); self._log(log, 'joined')
        if isinstance(self.native, _Native) and not any(item[0] is log and item[1] is log._owner and item[2] is log.stream for item in self._launches):
            self.retain_uncertain(log._owner, log, 'joined stream association changed')
            raise OwnershipUncertain('The joined stream/owner association changed before sealing')
        self._check_stream(log)
        try:
            log.stream.flush()
            self.native.flush(log._handle)
            log.stream.close()
            state = self.native.state(log._handle)
            if state['bytes'] > self.limits['maximum_log_bytes']: raise PublicationError('Log byte bound exceeded')
            row = self._publish(log.path, log.pending_path, log._handle, log.identity)
            log._state = 'sealed'; return row
        except BaseException:
            self.retain_uncertain(log._owner, log, 'log sealing failed'); raise

    def _close_reader(self, handle):
        if self.uncertain:
            self._retained_readers = getattr(self, '_retained_readers', []) + [handle]
            return
        try: self.native.close(handle)
        except BaseException:
            self._retained_readers = getattr(self, '_retained_readers', []) + [handle]
            self.retain_uncertain(None, None, 'inspection handle close is uncertain')
            raise

    def _names(self, handle):
        try: return self.native.names(handle)
        except OwnershipUncertain:
            self.retain_uncertain(None, None, 'native enumeration completion is uncertain')
            raise

    def _scan_outputs(self, *, read_bytes):
        # Depth-first traversal keeps at most two handles per bounded level.
        # Every returned reader is closed even when a later entry is malformed.
        rows, seen, total = {}, set(), 0

        def visit(path, handle):
            nonlocal total
            names = self._names(handle)
            for name in names:
                child_path = _relative(path + '/' + name if path else name)
                if len(rows) >= self.limits['maximum_entries']: raise PublicationError('Output entry bound exceeded')
                child = self._open_child(handle, name, metadata_only=not read_bytes)
                try:
                    state = self.native.state(child)
                    if state['path'] != self.output + '/' + child_path: raise PublicationError('Output path alias detected')
                    identity = tuple(state['identity'])
                    if identity in seen: raise PublicationError('Physical output alias detected')
                    seen.add(identity)
                    if state['directory']:
                        directory = self._open_child(handle, name, directory=True)
                        try:
                            reopened = self.native.state(directory)
                            if not reopened['directory'] or reopened['identity'] != state['identity'] or reopened['path'] != state['path']:
                                raise PublicationError('Directory identity changed before enumeration')
                            rows[child_path] = {'path': child_path, 'kind': 'directory'}
                            visit(child_path, directory)
                        finally: self._close_reader(directory)
                    else:
                        row = {'path': child_path, 'kind': 'file', 'bytes': state['bytes']}
                        if read_bytes:
                            raw = self.native.read(child, self.limits['maximum_file_bytes'])
                            if len(raw) != state['bytes'] or self.native.state(child) != state:
                                raise PublicationError('Output changed during inspection')
                            row['sha256'] = _sha(raw)
                        total += state['bytes']
                        if total > self.limits['maximum_output_bytes']: raise PublicationError('Output byte bound exceeded')
                        rows[child_path] = row
                finally: self._close_reader(child)
            if read_bytes and self._names(handle) != names:
                raise PublicationError('Output directory changed during inspection')

        visit('', self.directories[''])
        return rows, total

    def inspect_outputs(self, expected=None):
        self._ready(); self.check_anchors()
        rows, total = self._scan_outputs(read_bytes=True)
        if expected is not None:
            if type(expected) is not dict or set(expected) != set(rows): raise PublicationError('Complete output inventory differs')
            for name, row in expected.items():
                if row != rows[name]: raise PublicationError('Output byte identity differs: ' + name)
        self.check_anchors()
        return {'files': {name: item for name, item in rows.items() if item['kind'] == 'file'},
            'directories': sorted(name for name, item in rows.items() if item['kind'] == 'directory'), 'bytes': total}

    def usage(self, log=None):
        """Metadata-only sample while owned commands write; no frozen-byte claim."""
        if self.closed or self.uncertain: raise OwnershipUncertain('Workspace usage owner is uncertain')
        self.check_anchors()
        rows, total = self._scan_outputs(read_bytes=False)
        result = {'bytes': total, 'entries': len(rows)}
        if log is not None:
            self._log(log, 'running')
            state = self._check_handle(log._handle, self.output + '/' + log.pending_path, False)
            if state['identity'] != log.identity:
                self.retain_uncertain(log._owner, log, 'running log identity changed')
                raise OwnershipUncertain('Running log identity changed')
            result['log_bytes'] = state['bytes']
            if state['bytes'] > self.limits['maximum_log_bytes']: raise PublicationError('Log byte bound exceeded')
        return result

    def commit_receipt_new(self, path, raw):
        self._ready()
        if self.failed or self.committed or any(log._state != 'sealed' for log in self.logs):
            raise PublicationError('Failed/unsealed/already committed Workspace cannot publish success')
        self.inspect_outputs()
        row = self.publish_bytes_new(path, raw); self.committed = True
        return row

    def remove_owned_pending(self, path):
        self._ready()
        matches = [item for item in getattr(self, '_retained_pending', []) if item[0] == path]
        if len(matches) != 1: raise PublicationError('Cleanup requires one exact owned pending identity')
        pending, handle, identity = matches[0]
        try:
            if self._check_handle(handle, self.output + '/' + pending, False)['identity'] != identity:
                raise OwnershipUncertain('Pending cleanup identity changed')
            self.native.remove(handle)
        except BaseException:
            self.retain_uncertain(None, None, 'pending cleanup identity or disposition is uncertain')
            raise
        self._retained_pending.remove(matches[0])

    def retain_uncertain(self, owner, log, reason):
        self.uncertain = True
        self.retained_reason = str(reason)
        _RETAINED.append((self, owner, log))

    def close_joined(self):
        self._ready()
        if any(log._state != 'sealed' for log in self.logs) or getattr(self, '_retained_pending', []):
            raise PublicationError('Open/unsealed/pending outputs require explicit disposition before close')
        try:
            for handle in reversed(list(self.directories.values())): self.native.close(handle)
            for _path, handle, _identity in reversed(self.ancestors): self.native.close(handle)
        except BaseException:
            self.retain_uncertain(None, None, 'filesystem owner close failed'); raise
        self.closed = True


def _diagnostic_workspace(output, *, limits=None):
    """Private native-fixture bootstrap; never grants public qualification."""
    return Workspace._create(_Native(), output, (), limits or {}, diagnostic=True)


# Retained input authority is distinct from output publication authority.
INPUT_SCOPE = 'actual-native-windows-source-reader'
INPUT_POLICY = 'native-windows-local-ntfs-retained-readonly-input-v1'
INPUT_CONTRACT_SHA256 = 'ef065be8c502211ea748dbfc1732b6ca02b9210ee78ed74901f2b6ca6869d5d8'
INPUT_SOURCE_FILES = ('tools/appended_engine_windows_publication.py',
    'tests/diagnostics/windows_engine_source_reader.py', 'tools/process_tree.py',
    'tools/appended_engine_windows_contract.py')
INPUT_CASE_NAMES = ('test_pinned_metadata_read', 'test_anchor_rename_delete_conflict',
    'test_write_handle_conflicts', 'test_writable_mapping_conflict',
    'test_leaf_rename_delete_conflict', 'test_reparse_hardlink_alias_rejected',
    'test_seekable_zip_tar_capture', 'test_bounds_deadline_and_state_changes',
    'test_reader_close_releases_handles')
_INPUT_ISSUED = {}


class InputQualification:
    """Opaque capability issued only after the input-specific original join."""
    __slots__ = ()

    def __new__(cls, *args, **kwargs):
        raise PublicationError('Use admit_input_qualification with complete original input evidence')

    def as_dict(self):
        if type(self) is not InputQualification or self not in _INPUT_ISSUED:
            raise PublicationError('Unissued native input qualification')
        return json.loads(_INPUT_ISSUED[self])


def admit_input_qualification(reference, pin=None, *, source_identity, runtime_identity):
    """Join the whole independent input diagnostic; publication proof cannot substitute."""
    if pin is not None: reference = {'path': os.fspath(reference), 'sha256': pin}
    report = _read_reference(reference)
    contract.fields(report, ('schema_version', 'kind', 'scope', 'policy', 'source_identity',
        'runtime_identity', 'filesystem', 'run_report', 'observations', 'console'), 'native input qualification')
    if (type(report['schema_version']) is not int or report['schema_version'] != 1 or
            report['kind'] != 'foundation-windows-source-reader-qualification-v1' or
            report['scope'] != INPUT_SCOPE or report['policy'] != INPUT_POLICY):
        raise PublicationError('Unsupported native input qualification subject')
    if report['source_identity'] != source_identity or report['runtime_identity'] != runtime_identity:
        raise PublicationError('Native input source/runtime identity does not join')
    if type(source_identity) is not dict or set(source_identity) != set(INPUT_SOURCE_FILES):
        raise PublicationError('Complete input helper/diagnostic/process/contract source identity required')
    for name, digest in source_identity.items(): contract.pin(digest, name)
    if source_identity['tools/appended_engine_windows_contract.py'] != INPUT_CONTRACT_SHA256:
        raise PublicationError('Input reader uses a different Windows contract source')
    _validate_runtime(runtime_identity)
    filesystem = report['filesystem']
    contract.fields(filesystem, ('name', 'volume_serial'), 'qualified input filesystem')
    if filesystem['name'] != 'NTFS' or type(filesystem['volume_serial']) is not int or not 0 < filesystem['volume_serial'] < 2 ** 64:
        raise PublicationError('Qualified local NTFS volume identity required')
    run = _read_reference(report['run_report'])
    contract.fields(run, ('schema_version', 'system', 'status', 'inventory', 'excluded', 'results'), 'whole native input case inventory')
    inventory = run['inventory']
    prefix = 'diagnostic_windows_engine_source_reader.NativeSourceReader.'
    if (type(run['schema_version']) is not int or run['schema_version'] != 1 or run['system'] != 'Windows' or
            run['status'] != 'passed' or run['excluded'] != {} or type(inventory) is not list or
            len(inventory) != len(INPUT_CASE_NAMES) or any(type(name) is not str for name in inventory) or
            len(set(inventory)) != len(inventory) or set(inventory) != {prefix + name for name in INPUT_CASE_NAMES} or
            type(run['results']) is not dict or set(run['results']) != set(inventory) or
            any(run['results'][name] != {'status': 'passed'} for name in inventory)):
        raise PublicationError('Native input qualification has missing/failed/excluded cases')
    observations = _read_reference(report['observations'])
    contract.fields(observations, ('schema_version', 'kind', 'scope', 'policy', 'source_identity',
        'runtime_identity', 'filesystem', 'cases'), 'original native input observations')
    if (type(observations['schema_version']) is not int or observations['schema_version'] != 1 or
            observations['kind'] != 'foundation-windows-source-reader-observations-v1' or
            any(observations[name] != report[name] for name in ('scope', 'policy', 'source_identity', 'runtime_identity', 'filesystem')) or
            type(observations['cases']) is not dict or set(observations['cases']) != set(INPUT_CASE_NAMES)):
        raise PublicationError('Original native input observations do not join')
    for name, row in observations['cases'].items():
        contract.fields(row, ('operation', 'observed'), 'input case observation')
        if row['operation'] != name or type(row['observed']) is not dict or not row['observed']:
            raise PublicationError('Native input case lacks original operation/readback facts')
    console = _read_reference(report['console'], maximum=64 * 1024 * 1024, document=False)
    marker = b'WINDOWS_SOURCE_READER_OBSERVATIONS_SHA256=' + report['observations']['sha256'].encode('ascii')
    if marker not in console:
        raise PublicationError('Original console does not bind complete native input observations')
    facts = {'scope': INPUT_SCOPE, 'policy': INPUT_POLICY, 'reference': copy.deepcopy(reference),
        'source_identity': copy.deepcopy(source_identity), 'runtime_identity': copy.deepcopy(runtime_identity),
        'filesystem': copy.deepcopy(filesystem),
        'originals': {name: copy.deepcopy(report[name]) for name in ('run_report', 'observations', 'console')}}
    result = object.__new__(InputQualification)
    _INPUT_ISSUED[result] = encoded(facts)
    return result


def _input_limits(value):
    bounds = {'seconds': 86400, 'maximum_archive_bytes': 8 * 1024 ** 3,
        'maximum_expanded_bytes': 32 * 1024 ** 3, 'maximum_members': 1000000,
        'maximum_member_bytes': 256 * 1024 ** 2, 'maximum_patch_bytes': 32 * 1024 ** 2}
    if type(value) is not dict or set(value) != set(bounds):
        raise PublicationError('Exact six retained-source capture limits required')
    if any(type(value[name]) is not int or not 1 <= value[name] <= bound for name, bound in bounds.items()):
        raise PublicationError('Retained-source capture limit is outside its finite bound')
    return copy.deepcopy(value)


def _input_expected(value, *, metadata=False, tree=False):
    fields = ('sha256', 'mode') if (metadata or tree) and type(value) is dict and 'bytes' not in value else ('sha256', 'bytes', 'mode')
    contract.fields(value, fields, 'independently pinned retained input')
    contract.pin(value['sha256'], 'retained input')
    if (type(value['mode']) is not int or value['mode'] not in ((0o644, 0o755) if tree else (0o644,)) or
            'bytes' in value and (type(value['bytes']) is not int or not 0 <= value['bytes'] < 2 ** 63)):
        raise PublicationError('Exact retained input size declaration and supported logical manifest mode required')
    return copy.deepcopy(value)


def _input_subject(native):
    checkout = Path(__file__).resolve().parents[1]
    return {'source_identity': {name: _sha(_ordinary_bytes(checkout / name, MAX_METADATA)) for name in INPUT_SOURCE_FILES},
        'runtime_identity': native.runtime_identity()}


def inspect_input_subject():
    """Observe actual subjects; this is not full Python/SDK admission or qualification."""
    _native_host()
    return _input_subject(_Native())


class _SeekableInput:
    """Borrowed read-only view; closing it never releases the owner's file lock."""
    __slots__ = ('_owner', '_record', '_cursor', '_closed')

    def __init__(self, owner, record):
        self._owner, self._record, self._cursor, self._closed = owner, record, 0, False

    @property
    def closed(self): return self._closed or self._owner.closed

    def readable(self):
        self._owner._view_ready(self)
        return True

    def seekable(self):
        self._owner._view_ready(self)
        return True

    def tell(self):
        with self._owner._lock:
            self._owner._view_ready(self)
            return self._cursor

    def seek(self, offset, whence=0):
        with self._owner._lock:
            self._owner._view_ready(self)
            if type(offset) is not int or type(whence) is not int or whence not in (0, 1, 2):
                raise PublicationError('Integral SET/CUR/END input seek required')
            end = self._record['bytes']
            target = (0 if whence == 0 else self._cursor if whence == 1 else end) + offset
            if not 0 <= target <= end:
                # Ordinary binary-file range failures are OSError. ZipFile
                # deliberately catches this during optional ZIP64 tail probes.
                raise OSError(22, 'Input seek exceeds independently pinned EOF')
            self._cursor = target
            return target

    def read(self, size=-1):
        return self._owner._read_view(self, size)

    def close(self):
        with self._owner._lock:
            self._closed = True


class HeldInputTree:
    """Borrowed structural capture; declared hashes are never observed hashes."""
    __slots__ = ('_owner', '_root', '_files', '_directories', '_file_records', '_directory_records', '_complete')

    def __init__(self, *args, **kwargs):
        raise PublicationError('Use AnchoredInputs.capture_tree')

    def as_dict(self):
        # Passive observations remain readable after revocation/close. They do
        # not revalidate the source or renew either caller deadline.
        with self._owner._lock:
            return {'root': self._root, 'files': copy.deepcopy(self._files),
                'directories': list(self._directories), 'observed': {
                    'files': {name: copy.deepcopy(record['state']) for name, record in self._file_records.items()},
                    'directories': {name: copy.deepcopy(record['state']) for name, record in self._directory_records.items()}}}

    def open_file(self, relative):
        with self._owner._lock:
            try:
                self._owner._ready()
                if self not in self._owner._trees or not self._complete:
                    raise PublicationError('Input tree capture is incomplete or foreign')
                relative = _relative(relative)
                if relative not in self._file_records:
                    raise PublicationError('Input tree view must select a declared ordinary leaf')
                record = self._file_records[relative]
                self._owner._check_record(record)
                view = _SeekableInput(self._owner, record)
                self._owner._views.append(view)
                return view
            except BaseException as error:
                self._owner._failure(error); raise


class AnchoredInputs:
    """Retain selected source handles; it grants no output or source-proof authority."""
    def __init__(self, *args, **kwargs):
        raise PublicationError('Use AnchoredInputs.open_existing with original input qualification')

    @property
    def root(self): return self._root

    @property
    def closed(self): return self._closed

    @property
    def uncertain(self): return self._uncertain

    @property
    def filesystem(self): return copy.deepcopy(self._filesystem)

    @classmethod
    def open_existing(cls, root, *, qualification, limits, deadline=None):
        _native_host()
        if type(qualification) is not InputQualification or qualification not in _INPUT_ISSUED:
            raise PublicationError('Original native input qualification is required')
        facts = qualification.as_dict()
        native = _Native()
        subject = _input_subject(native)
        if subject['runtime_identity'] != facts['runtime_identity']:
            raise PublicationError('Actual native runtime differs from input qualification')
        if subject['source_identity'] != facts['source_identity']:
            raise PublicationError('Input helper/diagnostic/process/contract source changed after qualification')
        return cls._open(native, root, limits=limits, deadline=deadline, filesystem=facts['filesystem'])

    @classmethod
    def _open(cls, native, root, *, limits, deadline=None, filesystem=None):
        # Private inert/native-diagnostic seam. It never issues qualification.
        import math
        import threading
        self = object.__new__(cls)
        self._root = contract.windows_path(os.fspath(root), 'existing retained input root')
        self._native, self._limits, self._lock = native, _input_limits(limits), threading.RLock()
        entered = time.monotonic()
        if deadline is not None and (type(deadline) not in (int, float) or not math.isfinite(deadline)):
            raise PublicationError('Finite absolute enclosing input deadline required')
        self._deadline = min(entered + self._limits['seconds'], deadline) if deadline is not None else entered + self._limits['seconds']
        self._closed, self._uncertain, self._failed = False, False, False
        self._records, self._files, self._directories, self._views = [], {}, {}, []
        self._trees, self._tree_entries = [], set()
        self._aliases, self._physical, self._charged = {}, {}, {}
        self._captured_bytes, self._filesystem = 0, None
        try:
            self._time()
            selected = PureWindowsPath(self._root)
            current = selected.drive + '/'
            record = self._acquire(None, current, True)
            for part in selected.parts[1:]:
                self._time()
                current += ('' if current.endswith('/') else '/') + part
                record = self._acquire(record, current, True)
            self._directories[''] = record
            actual = native.filesystem(record['handle'])
            if filesystem is not None and actual != filesystem:
                raise PublicationError('Selected input volume differs from native qualification')
            self._filesystem = copy.deepcopy(actual)
            self.check()
            return self
        except BaseException as error:
            self._failure(error)
            if not self._uncertain:
                try: self.close()
                except BaseException: pass  # close retains its own precise uncertain owner
            raise

    def _time(self):
        if time.monotonic() >= self._deadline:
            raise PublicationError('Retained input capture deadline expired')

    def _ready(self):
        if self._closed: raise PublicationError('Retained input owner is closed')
        if self._uncertain: raise OwnershipUncertain('Retained input ownership is uncertain')
        if self._failed: raise PublicationError('Retained input capture failed; stop dependent proof')
        self._time()

    def _failure(self, error):
        self._failed = True
        if (isinstance(error, OwnershipUncertain) or getattr(self._native, '_unknown_handles', []) or
                getattr(self._native, '_unknown_operations', [])):
            self._uncertain = True
            self._reason = str(error)
            if not any(item is self for item in _RETAINED): _RETAINED.append(self)

    def _observe(self, record):
        try:
            state = self._native.state(record['handle'], _raw=True)
            identity = state['identity']
            if (type(identity) is not list or len(identity) != 2 or type(identity[0]) is not int or not 0 < identity[0] < 2 ** 64 or
                    type(identity[1]) is not str or not re.fullmatch('[0-9a-f]{32}', identity[1]) or identity[1] == '0' * 32):
                raise OwnershipUncertain('Input handle lacks complete physical identity')
            return state
        except BaseException as error:
            self._failure(OwnershipUncertain('Cannot observe the retained native input handle'))
            raise OwnershipUncertain('Cannot observe the retained native input handle') from error

    def _ordinary(self, state, record):
        if (state['directory'] is not record['directory'] or state['path'] != record['path'] or
                record.get('identity') is not None and state['identity'] != record['identity'] or
                self._records and state['identity'][0] != self._records[0]['identity'][0]):
            raise OwnershipUncertain('Retained input kind/path/physical identity changed')
        attributes = state['attributes']
        if (state['_basic_attributes'] != attributes or state['_reparse_tag'] or state['_delete_pending'] or
                attributes & (0x400 | 0x40 | 0x1000 | 0x40000 | 0x400000) or
                bool(attributes & 16) != state['directory'] or state['bytes'] < 0 or
                not record['directory'] and state['links'] != 1):
            raise PublicationError('Retained input is reparse/device/offline/linked/delete-pending')

    def _acquire(self, parent, path, directory):
        # Allocate/register the slot before the native open can acquire anything.
        record = {'handle': None, 'path': path, 'directory': directory,
            'identity': None, 'state': None, 'closed': False}
        self._records.append(record)
        try:
            record['handle'] = (self._native.open_root(path) if parent is None else
                self._native.open_child(parent['handle'], PureWindowsPath(path).name,
                    directory=directory, input_file=not directory))
            state = self._observe(record)
            record['identity'] = copy.deepcopy(state['identity'])
            record['state'] = copy.deepcopy(state)
            if state['path'] != path or state['directory'] is not directory:
                # A fresh returned object is known, but its spelling/kind is
                # inadmissible. Retain its actual opened baseline for safe close.
                raise PublicationError('Selected input path spelling or kind differs from the opened object')
            self._ordinary(state, record)
            return record
        except BaseException as error:
            self._failure(error)
            if record['handle'] is None:
                record['closed'] = True  # no successful handle was returned
            elif not self._uncertain:
                self._close_record(record)
            raise

    def _check_record(self, record, *, content=True):
        state = self._observe(record)
        self._ordinary(state, record)
        if content and not record['directory'] and state != record['state']:
            raise PublicationError('Retained input bytes/attributes/version changed')
        return state

    def _close_record(self, record):
        if record['closed']: return
        try:
            # A rejected data pin/version can close a known physical handle. Do
            # not close a numerically reused handle or a changed path/kind.
            state = self._observe(record)
            if (record['identity'] is None or state['identity'] != record['identity'] or
                    record['state'] is None or state['path'] != record['state']['path'] or
                    state['directory'] is not record['state']['directory']):
                raise OwnershipUncertain('Cannot close a changed retained input identity')
            self._native.close(record['handle'])
            record['closed'] = True
        except BaseException as error:
            self._failure(OwnershipUncertain('Retained input close outcome is uncertain'))
            raise OwnershipUncertain('Retained input close outcome is uncertain') from error

    def _directory(self, relative):
        parent, prefix = self._directories[''], ''
        for part in relative.split('/') if relative else ():
            self._time(); prefix += ('/' if prefix else '') + part
            if prefix.casefold() in self._aliases and self._aliases[prefix.casefold()] != prefix:
                raise PublicationError('Retained input directory aliases by case')
            self._aliases[prefix.casefold()] = prefix
            if prefix in self._files:
                raise PublicationError('Retained input file is also selected as a directory')
            if prefix not in self._directories:
                self._directories[prefix] = self._acquire(parent, self._root.rstrip('/') + '/' + prefix, True)
            parent = self._directories[prefix]
            self._check_record(parent)
        return parent

    @staticmethod
    def _compatible(left, right, observed=None):
        return (left['sha256'] == right['sha256'] and left['mode'] == right['mode'] and
            not ('bytes' in left and 'bytes' in right and left['bytes'] != right['bytes']) and
            (observed is None or all('bytes' not in row or row['bytes'] == observed for row in (left, right))))

    def _capture(self, relative, expected, role, *, maximum=None):
        self._ready(); relative = _relative(relative)
        expected = _input_expected(expected, metadata=role == 'metadata', tree=role == 'tree')
        alias = relative.casefold()
        if alias in self._aliases and self._aliases[alias] != relative:
            raise PublicationError('Active retained input paths alias by case')
        if relative in self._charged:
            prior, prior_role = self._charged[relative]
            if role == 'tree' or prior_role == 'tree':
                if not self._compatible(prior, expected, self._files[relative]['bytes'] if relative in self._files else None):
                    raise PublicationError('Tree and selected input declarations differ')
                if prior_role == 'tree' and role != 'tree':
                    self._charged[relative] = (copy.deepcopy(expected), role)
            elif (prior, prior_role) != (expected, role):
                raise PublicationError('Retained input path was selected with different pins/role')
        else:
            declared = expected.get('bytes', 0)
            if (len(set(self._charged) | self._tree_entries | {relative}) > self._limits['maximum_members'] or
                    self._captured_bytes + declared > self._limits['maximum_expanded_bytes']):
                raise PublicationError('Retained input aggregate bytes/count bound exceeded')
            self._charged[relative] = (copy.deepcopy(expected), role)
            self._captured_bytes += declared
            self._aliases[alias] = relative
        if relative in self._files:
            record = self._files[relative]; self._check_record(record)
            if role != 'tree' and record['role'] == 'tree':
                record['expected'], record['role'] = copy.deepcopy(expected), role
            if maximum is not None and record['bytes'] > maximum:
                raise PublicationError('Retained metadata observed EOF exceeds caller byte bound')
            return record
        if relative in self._directories:
            raise PublicationError('Retained input directory is also selected as a file')
        parent = self._directory(relative.rpartition('/')[0])
        record = self._acquire(parent, self._root.rstrip('/') + '/' + relative, False)
        record['expected'], record['role'] = copy.deepcopy(expected), role
        record['bytes'] = record['state']['bytes']
        self._files[relative] = record
        physical = tuple(record['identity'])
        if physical in self._physical and self._physical[physical] != relative:
            raise PublicationError('Different retained paths identify the same physical file')
        self._physical[physical] = relative
        if 'bytes' in expected and record['bytes'] != expected['bytes']:
            raise PublicationError('Retained input EOF differs from its independent pin')
        if 'bytes' not in expected:
            # SHA-only metadata has an observed frozen EOF, not an independent
            # size declaration. Charge it before any data read/allocation.
            if self._captured_bytes + record['bytes'] > self._limits['maximum_expanded_bytes']:
                raise PublicationError('Retained metadata observed EOF exceeds aggregate byte bound')
            self._captured_bytes += record['bytes']
        if maximum is not None and record['bytes'] > maximum:
            raise PublicationError('Retained metadata observed EOF exceeds caller byte bound')
        return record

    def capture_tree(self, relative, *, files, directories):
        with self._lock:
            try:
                self._ready()
                relative = '' if type(relative) is str and relative == '' else _relative(relative)
                if type(files) is not dict or type(directories) is not list:
                    raise PublicationError('Exact input tree file map and directory list required')
                if len(files) + len(directories) > self._limits['maximum_members']:
                    raise PublicationError('Input tree member bound exceeded')
                declared = {_relative(name): _input_expected(row, tree=True) for name, row in files.items()}
                names = [_relative(name) for name in directories]
                all_names, directory_set = list(declared) + names, set(names)
                if (len(names) != len(set(names)) or len(all_names) != len({name.casefold() for name in all_names}) or
                        any('/'.join(name.split('/')[:index]) not in directory_set for name in all_names
                            for index in range(1, len(name.split('/'))))):
                    raise PublicationError('Input tree parents, kinds or path aliases differ')
                full = lambda name: relative + ('/' if relative and name else '') + name
                entries = {_relative(full(name)) for name in all_names}
                if relative: entries.add(relative)
                if len(set(self._charged) | self._tree_entries | entries) > self._limits['maximum_members']:
                    raise PublicationError('Input tree aggregate member bound exceeded')
                for prior in self._trees:
                    if prior._root == relative:
                        if not prior._complete or prior._files != declared or prior._directories != sorted(names):
                            raise PublicationError('Retained tree root was selected with a different manifest')
                        self._check_tree(prior)
                        return prior
                if len(self._trees) >= self._limits['maximum_members']:
                    raise PublicationError('Retained tree capture count bound exceeded')
                self._tree_entries.update(entries)
                tree = object.__new__(HeldInputTree)
                tree._owner, tree._root = self, relative
                tree._files, tree._directories = declared, sorted(names)
                tree._file_records, tree._directory_records, tree._complete = {}, {}, False
                self._trees.append(tree)  # Own the incomplete capture before fallible opens.
                tree._directory_records[''] = self._directory(relative)
                for name in sorted(names, key=lambda item: (item.count('/'), item)):
                    tree._directory_records[name] = self._directory(full(name))
                # Reject unknown names before acquiring their alleged file kind.
                self._check_tree(tree, complete=False)
                for name, row in sorted(declared.items()):
                    self._time()
                    record = self._capture(full(name), row, 'tree')
                    # Structural EOF is charged to the physical aggregate.
                    # Decoder-member limits do not bound compressed archives;
                    # the archive/core callers enforce their own role limits.
                    tree._file_records[name] = record
                self._check_tree(tree)
                tree._complete = True
                return tree
            except BaseException as error:
                self._failure(error); raise

    def _check_tree(self, tree, *, complete=True):
        expected = {name: [] for name in tree._directory_records}
        for name in list(tree._files) + tree._directories:
            parent, _, leaf = name.rpartition('/')
            expected[parent].append(leaf)
        for name, record in tree._directory_records.items():
            self._time(); self._check_record(record)
            actual = self._native.names(record['handle'], deadline=self._deadline,
                maximum_entries=self._limits['maximum_members'])
            if (type(actual) is not list or any(type(item) is not str for item in actual) or
                    len(actual) != len(set(actual)) or len(actual) != len({item.casefold() for item in actual}) or
                    actual != sorted(expected[name])):
                raise PublicationError('Complete retained input tree membership differs')
            self._time(); self._check_record(record)
        if complete:
            if set(tree._file_records) != set(tree._files):
                raise PublicationError('Retained input tree leaf capture is incomplete')
            for record in tree._file_records.values():
                self._time(); self._check_record(record)

    def read(self, relative, *, expected, maximum):
        with self._lock:
            try:
                self._ready()
                if type(maximum) is not int or not 1 <= maximum <= self._limits['maximum_expanded_bytes']:
                    raise PublicationError('Finite positive retained metadata byte bound required')
                expected = _input_expected(expected, metadata=True)
                if 'bytes' in expected and expected['bytes'] > maximum: raise PublicationError('Retained metadata exceeds caller byte bound')
                record = self._capture(relative, expected, 'metadata', maximum=maximum)
                if 'metadata' not in record:
                    stream = _SeekableInput(self, record); self._views.append(stream)
                    try: raw = self._read_view(stream, -1)
                    finally: stream.close()
                    if _sha(raw) != expected['sha256']:
                        raise PublicationError('Retained metadata differs from its independent SHA256 pin')
                    record['metadata'] = raw
                self._check_record(record)
                return record['metadata']
            except BaseException as error:
                self._failure(error); raise

    def open_archive(self, relative, *, expected):
        with self._lock:
            try:
                self._ready(); expected = _input_expected(expected)
                if expected['bytes'] > self._limits['maximum_archive_bytes']:
                    raise PublicationError('Retained archive EOF exceeds its byte bound')
                record = self._capture(relative, expected, 'archive')
                stream = _SeekableInput(self, record); self._views.append(stream)
                return stream
            except BaseException as error:
                self._failure(error); raise

    def _view_ready(self, view):
        self._ready()
        if type(view) is not _SeekableInput or view._owner is not self or view not in self._views or view._closed:
            raise PublicationError('Retained input view is closed or foreign')

    def _read_view(self, view, size):
        with self._lock:
            try:
                self._view_ready(view)
                if type(size) is not int or size < -1:
                    raise PublicationError('Integral bounded input read size required')
                record = view._record
                self._check_record(record)
                remaining = record['bytes'] - view._cursor
                wanted = remaining if size == -1 else min(size, remaining)
                chunks, completed = [], 0
                while completed < wanted:
                    self._time()
                    count = min(1024 * 1024, wanted - completed)
                    raw = self._native.read_at(record['handle'], view._cursor + completed, count)
                    if type(raw) is not bytes or not 0 < len(raw) <= count:
                        raise PublicationError('Retained input read ended before pinned EOF or exceeded request')
                    chunks.append(raw); completed += len(raw)
                    self._check_record(record)
                self._time(); self._check_record(record)
                view._cursor += completed
                return b''.join(chunks)
            except BaseException as error:
                self._failure(error); raise

    def check(self):
        with self._lock:
            try:
                self._ready()
                for record in self._records:
                    self._time()
                    if not record['closed']: self._check_record(record)
                for tree in self._trees:
                    if not tree._complete:
                        raise PublicationError('Retained input tree capture is incomplete')
                    self._check_tree(tree)
            except BaseException as error:
                self._failure(error); raise

    def close(self):
        with self._lock:
            if self._closed: raise PublicationError('Retained input owner already closed')
            if self._uncertain: raise OwnershipUncertain('Retain uncertain input owner; no guessed cleanup')
            # Cooperative capture deadline expiry does not abandon known handles.
            for view in self._views: view._closed = True
            for record in reversed(self._records): self._close_record(record)
            self._closed = True


def _diagnostic_inputs(root, *, limits, deadline=None):
    """Private native-fixture bootstrap; never issues InputQualification."""
    return AnchoredInputs._open(_Native(), root, limits=limits, deadline=deadline)
