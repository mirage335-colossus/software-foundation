#!/usr/bin/env python3
"""Finite Windows engine lifecycle and raw candidate runtime maintenance.

The closed retained-input engine graph and separate raw document/runtime harness
share the same actual admitted Workspace/stage runner. Original source, tool,
input and publication admissions precede output. Results remain unqualified;
this tool neither emits an eligible SDK nor falls back to another engine build.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import platform
import re
import stat
import struct
import sys
import time
import threading
import types

"""Fixed dependency-entry bootstrap, included in the maintained prototype.

This header owns no dependency token or second source cache. It selects the
actual facade and its existing controller owner before any native imports.
"""
import ast as _entry_ast
import hashlib as _entry_hashlib
import os as _entry_os
from pathlib import Path as _EntryPath
import stat as _entry_stat
import sys as _entry_sys
import threading as _entry_threading
import types as _entry_types

_DEPENDENCY_FACADE_SHA256 = '64e724a1f677108d514f605ab199c206fea03f64b21e0be7857472c3cd18c780'  # Bound to the final maintained facade bytes.
_DEPENDENCY_FACADE_BYTES = 10406
_DEPENDENCY_FACADE_NAME = 'appended_engine_windows_dependencies'
_DEPENDENCY_CORE_NAME = '_foundation_windows_h2d3_controller_core_v1'
_DEPENDENCY_ENTRY_LOCK = _entry_threading.RLock()
_DEPENDENCY_FAILED_RESERVATIONS = []


def _entry_identity(state):
    return (state.st_dev, state.st_ino, state.st_mode, state.st_nlink,
        state.st_size, state.st_mtime_ns, state.st_ctime_ns)


def _entry_source(path, pin, size):
    if (type(pin) is not str or len(pin) != 64 or
            any(letter not in '0123456789abcdef' for letter in pin) or
            type(size) is not int or not 1 <= size <= 1024 * 1024):
        raise ValueError('The maintained dependency facade source binding is unfinished')
    for current in (path, *path.parents):
        state = current.lstat()
        if (_entry_stat.S_ISLNK(state.st_mode) or
                getattr(state, 'st_file_attributes', 0) & 0x400 or
                not (_entry_stat.S_ISREG(state.st_mode) if current == path else
                    _entry_stat.S_ISDIR(state.st_mode))):
            raise ValueError('Dependency bootstrap requires ordinary source paths')
    before = path.lstat()
    if before.st_nlink != 1 or before.st_size != size:
        raise ValueError('Dependency bootstrap source size or link count changed')
    with path.open('rb') as stream:
        opened = _entry_os.fstat(stream.fileno())
        raw = stream.read(size + 1)
        after = _entry_os.fstat(stream.fileno())
    if (len(raw) != size or _entry_identity(before) != _entry_identity(opened) or
            _entry_identity(before) != _entry_identity(after) or
            _entry_identity(before) != _entry_identity(path.lstat()) or
            _entry_hashlib.sha256(raw).hexdigest() != pin):
        raise ValueError('Dependency bootstrap source bytes or identity changed')
    return raw


def _entry_controller_binding(raw, filename):
    values = {}
    wanted = {'_CONTROLLER_SHA256', '_CONTROLLER_BYTES'}
    for node in _entry_ast.parse(raw, filename=filename).body:
        if isinstance(node, _entry_ast.Assign):
            names = [target.id for target in node.targets
                if isinstance(target, _entry_ast.Name) and target.id in wanted]
            for name in names:
                if name in values or len(node.targets) != 1:
                    raise ValueError('The facade controller source binding is ambiguous')
                values[name] = _entry_ast.literal_eval(node.value)
    if set(values) != wanted:
        raise ValueError('The facade has no complete controller source binding')
    return values['_CONTROLLER_SHA256'], values['_CONTROLLER_BYTES']


def _entry_function(module, raw, path, name):
    """Reject a module-shaped substitute before calling its owner accessors."""
    function = vars(module).get(name)
    top = compile(raw, str(path), 'exec', dont_inherit=True)
    matches = [item for item in top.co_consts
        if isinstance(item, _entry_types.CodeType) and item.co_name == name]
    if (type(function) is not _entry_types.FunctionType or
            function.__globals__ is not vars(module) or
            function.__code__.co_filename != str(path) or len(matches) != 1 or
            function.__code__ != matches[0]):
        raise ValueError('Dependency entry accessor is not its maintained source function')
    return function


def _dependency_entry():
    """Return the actual C entry owner, preserving dependency-first issuance."""
    with _DEPENDENCY_ENTRY_LOCK:
        facade_path = _EntryPath(__file__).resolve().with_name(
            'appended_engine_windows_dependencies.py')
        facade_raw = _entry_source(facade_path, _DEPENDENCY_FACADE_SHA256,
            _DEPENDENCY_FACADE_BYTES)
        core_pin, core_size = _entry_controller_binding(facade_raw, str(facade_path))
        core_path = facade_path.with_name('appended_engine_windows_dependency_support') / 'controller.py'
        core_raw = _entry_source(core_path, core_pin, core_size)
        facade_present = _DEPENDENCY_FACADE_NAME in _entry_sys.modules
        core_present = _DEPENDENCY_CORE_NAME in _entry_sys.modules
        if facade_present != core_present:
            raise ValueError('A partial dependency entry registration cannot be adopted')
        if not facade_present:
            facade = _entry_types.ModuleType(_DEPENDENCY_FACADE_NAME)
            facade.__file__ = str(facade_path)
            facade.__package__ = ''
            if _entry_sys.modules.setdefault(_DEPENDENCY_FACADE_NAME, facade) is not facade:
                raise ValueError('The dependency entry lost its module reservation')
            try:
                exec(compile(facade_raw, str(facade_path), 'exec', dont_inherit=True), vars(facade))
                if (_entry_sys.modules.get(_DEPENDENCY_FACADE_NAME) is not facade or
                        vars(facade).get('__file__') != str(facade_path)):
                    raise ValueError('Dependency entry registration changed during loading')
                _entry_function(facade, facade_raw, facade_path, '_module')('controller')
            except BaseException:
                _DEPENDENCY_FAILED_RESERVATIONS.append(facade)
                # Keep the actual failed reservation and any Core owner alive.
                # Never remove or restore a foreign module after uncertainty.
                raise
        facade = _entry_sys.modules.get(_DEPENDENCY_FACADE_NAME)
        core = _entry_sys.modules.get(_DEPENDENCY_CORE_NAME)
        if (type(facade) is not _entry_types.ModuleType or
                type(core) is not _entry_types.ModuleType or
                vars(facade).get('__file__') != str(facade_path) or
                vars(core).get('__file__') != str(core_path)):
            raise ValueError('The dependency facade and controller are not their actual source modules')
        facade_resolver = _entry_function(facade, facade_raw, facade_path, '_module')
        owner_getter = _entry_function(core, core_raw, core_path, '_dependency_entry')
        core_resolver = _entry_function(core, core_raw, core_path, '_support_module')
        cache = vars(facade).get('_SOURCE_CACHE')
        row = cache.get(_DEPENDENCY_CORE_NAME) if type(cache) is dict else None
        if (type(row) is not dict or set(row) != {'path', 'pin', 'module'} or
                row['path'] != str(core_path) or row['pin'] != core_pin or
                row['module'] is not core or owner_getter() is not facade or
                core_resolver('controller') is not core or
                facade_resolver('controller') is not core):
            raise ValueError('Dependency entry and controller ownership do not join')
        if (_entry_sys.modules.get(_DEPENDENCY_FACADE_NAME) is not facade or
                _entry_sys.modules.get(_DEPENDENCY_CORE_NAME) is not core):
            raise ValueError('Dependency entry registration changed during owner validation')
        return facade


# Only these two pure consistency tools are outside the Origin-owned B closure.
_PROTOTYPE_TOOL_SOURCES = {
    'appended_engine_sdk': ('appended_engine_sdk.py', 'c04d7de7bcf5387eec890533af314cca3e999a55f1b6dc66d49a3a52581a842e', 18034),
    'appended_engine_native_consumer': ('appended_engine_native_consumer.py', 'f5d95283a879c6b56ff6875ed6cc476bcad03bb1d6595a3aa8d6eedbb929c902', 94074),
}
_PROTOTYPE_TOOL_CACHE = {}
_PROTOTYPE_TOOL_FAILURES = []
_PROTOTYPE_TOOL_LOCK = threading.RLock()


def _prototype_tool_module(name):
    # The source owner is obtained from the sole fixed entry, never a caller.
    dependencies = _dependency_entry()
    with _PROTOTYPE_TOOL_LOCK:
        filename, pin, size = _PROTOTYPE_TOOL_SOURCES[name]
        path = Path(__file__).resolve().with_name(filename)
        identity = lambda value: (value.st_dev, value.st_ino, value.st_mode, value.st_nlink,
            value.st_size, value.st_mtime_ns, value.st_ctime_ns)
        before = identity(path.lstat())
        raw = dependencies._source_bytes(path, pin, size)
        if identity(path.lstat()) != before:
            raise ValueError('Prototype consistency source changed before execution')
        previous = _PROTOTYPE_TOOL_CACHE.get(name)
        if previous is not None:
            module, original_path, original_pin, original_identity = previous
            if (original_path != path or original_pin != pin or original_identity != before or
                    sys.modules.get(name) is not module or
                    getattr(module, '__file__', None) != str(path)):
                raise ValueError('Owned prototype consistency tool registration changed')
            return module
        if name in sys.modules:
            raise ValueError('Unknown preloaded prototype consistency tool')
        module = types.ModuleType(name)
        module.__file__ = str(path)
        module.__package__ = ''
        if sys.modules.setdefault(name, module) is not module:
            raise ValueError('Prototype consistency tool reservation lost its slot')
        published = None
        try:
            exec(compile(raw, str(path), 'exec', dont_inherit=True), vars(module))
            if (sys.modules.get(name) is not module or getattr(module, '__file__', None) != str(path) or
                    name in _PROTOTYPE_TOOL_CACHE):
                raise ValueError('Prototype consistency tool changed during source execution')
            dependencies._source_bytes(path, pin, size)
            if identity(path.lstat()) != before:
                raise ValueError('Prototype consistency source changed during execution')
            published = (module, path, pin, before)
            _PROTOTYPE_TOOL_CACHE[name] = published
            if sys.modules.get(name) is not module:
                raise ValueError('Prototype consistency tool lost its final module slot')
            return module
        except BaseException:
            if published is not None and _PROTOTYPE_TOOL_CACHE.get(name) is published:
                del _PROTOTYPE_TOOL_CACHE[name]
            _PROTOTYPE_TOOL_FAILURES.append(module)
            # Keep failed own blockers and foreign winners exactly as observed.
            raise


def _prototype_owned_tools():
    dependencies = _dependency_entry()
    # The sanctioned shared Origin is the first owner of B and its dependencies.
    source = dependencies._module('retained_dependency')._issuer().originals_module()._capture_source_provider()
    if sys.modules.get('appended_engine_windows_source_replay') is not source:
        raise ValueError('Actual prototype source provider registration differs')
    _prototype_tool_module('appended_engine_sdk')
    _prototype_tool_module('appended_engine_native_consumer')


_prototype_owned_tools()

import appended_engine_native_consumer as consumer
import appended_engine_windows_contract as contract
import process_tree

ROOT = Path(__file__).resolve().parents[1]
RECIPE = contract.RECIPE + '/windows'
SCOPE = 'native-windows-engine-candidate-source-and-static-inspection-only'
PLAN_KIND = 'foundation-native-engine-windows-prototype-plan-v1'
SELECTION_KIND = 'foundation-native-engine-windows-prototype-selection-v1'
MAX_DOCUMENT = 32 * 1024 * 1024
MAX_BINARY = 512 * 1024 * 1024
MAX_INVENTORY_FILES = 65536
MAX_INVENTORY_BYTES = 32 * 1024 * 1024 * 1024
MAX_OUTPUT_ENTRIES = 524288
GETTER = 'bib_engine_get_provider_v1'
FALSE_FACTS = ('production_eligible', 'native_runtime_qualified', 'engine_execution', 'kernel_rebuild')
INVENTORY_ROLES = frozenset(('llvm', 'msvc_stl', 'windows_sdk', 'host_generators',
                             'native_dependencies', 'product_assets'))
PROGRAM_NAMES = {
    'compiler': ('clang-cl.exe',), 'linker': ('lld-link.exe',),
    'archiver': ('llvm-lib.exe',), 'resource_compiler': ('llvm-rc.exe',),
    'manifest_tool': ('llvm-mt.exe',), 'cmake': ('cmake.exe',), 'ninja': ('ninja.exe',),
    'python': ('python.exe',), 'perl': ('perl.exe',), 'ruby': ('ruby.exe',),
    'gperf': ('gperf.exe',),
}
SYSTEM_IMPORTS = frozenset(('advapi32.dll', 'bcrypt.dll', 'combase.dll', 'crypt32.dll',
    'd2d1.dll', 'dwrite.dll', 'gdi32.dll', 'iphlpapi.dll', 'kernel32.dll', 'kernelbase.dll',
    'normaliz.dll', 'ntdll.dll', 'ole32.dll', 'oleaut32.dll', 'secur32.dll', 'shell32.dll',
    'shlwapi.dll', 'user32.dll', 'version.dll', 'windowscodecs.dll', 'winmm.dll', 'ws2_32.dll'))
DYNAMIC_CRT = re.compile(r'^(?:msvcr[^/]*|msvcp[^/]*|msvcprt[^/]*|vcruntime[^/]*|'
                         r'ucrtbase[^/]*|api-ms-win-crt-[^/]*|concrt[^/]*|vccorlib[^/]*)\.dll$', re.I)
_UNCERTAIN_OWNERS = []


def encoded(value):
    return contract.encoded(value)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def _missing(role, path, reason):
    return {'role': role, 'path': str(path), 'reason': reason}


def _identity(state):
    return (state.st_dev, state.st_ino, state.st_mode, state.st_nlink,
            state.st_size, state.st_mtime_ns, state.st_ctime_ns)


def _ordinary(path, directory=False):
    path = Path(path)
    if not path.is_absolute() or '..' in path.parts:
        raise ValueError('An explicit normalized absolute host path is required')
    for current in reversed((path, *path.parents)):
        state = current.lstat()
        attributes = getattr(state, 'st_file_attributes', None)
        wanted = directory if current == path else True
        if (stat.S_ISLNK(state.st_mode) or attributes is not None and attributes & 0x400
                or os.name == 'nt' and type(attributes) is not int
                or not (stat.S_ISDIR(state.st_mode) if wanted else stat.S_ISREG(state.st_mode))
                or not wanted and state.st_nlink != 1):
            raise ValueError('Windows candidate input must be ordinary, unaliased and singly linked')
    return path


def _read(path, pin=None, *, maximum=MAX_DOCUMENT):
    """Bounded consistent read; this never grants publication authority."""
    try:
        path = _ordinary(path)
    except FileNotFoundError as error:
        raise contract.MissingInputs([_missing('retained-input', path, 'selected ordinary input is absent')]) from error
    before = _identity(path.lstat())
    if before[4] > maximum:
        raise ValueError('Windows candidate input exceeds its byte bound')
    with os.fdopen(os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0)), 'rb') as stream:
        opened = _identity(os.fstat(stream.fileno()))
        raw = stream.read(maximum + 1)
        after = _identity(os.fstat(stream.fileno()))
    _ordinary(path)
    if before != opened or before != after or before != _identity(path.lstat()) or len(raw) > maximum:
        raise ValueError('Windows candidate input changed during bounded read')
    if pin is not None and digest(raw) != contract.pin(pin, 'Windows candidate input'):
        raise ValueError('Windows candidate input differs from its independent SHA256')
    return raw


def _document(path, pin):
    raw = _read(path, pin)
    # Reuse the strict duplicate/nonfinite/Unicode parser with its explicit bound.
    # Inventory metadata has a separate larger bound than the passive contract.
    import json
    def pairs(items):
        result = {}
        for key, item in items:
            if key in result:
                raise ValueError('Duplicate Windows candidate JSON field: ' + key)
            result[key] = item
        return result
    def invalid(value):
        raise ValueError('Nonfinite Windows candidate JSON: ' + value)
    try:
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=pairs, parse_constant=invalid)
        encoded(value)  # rejects nonfinite overflows; UTF-8 below rejects lone surrogates
        def strings(item):
            if type(item) is str:
                item.encode('utf-8')
            elif type(item) is dict:
                for key, child in item.items(): strings(key); strings(child)
            elif type(item) is list:
                for child in item: strings(child)
        strings(value)
        return value
    except (UnicodeError, RecursionError, OverflowError) as error:
        raise ValueError('Invalid Windows candidate JSON encoding or nesting') from error


def _reference(value, label):
    contract.fields(value, ('path', 'sha256'), label)
    return contract.windows_path(value['path'], label), contract.pin(value['sha256'], label)


def _relative(value):
    if (type(value) is not str or not value or len(value) > 1024 or
            PurePosixPath(value).as_posix() != value or value.startswith('/') or
            any(part in ('', '.', '..') for part in value.split('/'))):
        raise ValueError('Canonical relative Windows inventory path required')
    # Reuse the complete Windows alias/device/ADS policy for every component.
    contract.windows_path('C:/inventory/' + value, 'inventory member')
    return value


def _integer(value, label, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ValueError('Bounded integer required: ' + label)
    return value


def validate_limits(value):
    bounds = {'configure_seconds': (1, 3600), 'build_seconds': (1, 28800),
        'cleanup_seconds': (1, 60), 'maximum_jobs': (1, 64),
        'maximum_processes': (1, 1024), 'maximum_output_bytes': (1024, 1024 ** 4),
        'maximum_log_bytes': (1024, 128 * 1024 * 1024)}
    contract.fields(value, bounds, 'Windows phase limits')
    return {name: _integer(value[name], name, *bound) for name, bound in bounds.items()}


def validate_selection(value):
    contract.fields(value, ('schema_version', 'kind', 'handoff', 'admission', 'output_root',
                            'phase_limits'), 'Windows prototype selection')
    if type(value['schema_version']) is not int or value['schema_version'] != 1 or value['kind'] != SELECTION_KIND:
        raise ValueError('Unsupported Windows prototype selection schema')
    contract.fields(value['handoff'], ('root', 'sha256'), 'Windows handoff selection')
    contract.windows_path(value['handoff']['root'], 'immutable Windows handoff root')
    contract.pin(value['handoff']['sha256'], 'immutable Windows handoff')
    _reference(value['admission'], 'complete Windows native admission')
    contract.windows_path(value['output_root'], 'fresh Windows output root')
    validate_limits(value['phase_limits'])
    left, right = PureWindowsPath(value['output_root']), PureWindowsPath(value['handoff']['root'])
    if left == right or left in right.parents or right in left.parents:
        raise ValueError('Windows output overlaps the immutable handoff')
    return copy.deepcopy(value)


def inspect_provider(raw):
    """Verify static PE facts only; do not load a DLL or call its getter."""
    result = consumer.scan_native_binary(raw, maximum_bytes=MAX_BINARY)
    if result['format'] != 'pe32plus' or result['exports'] != [GETTER]:
        raise ValueError('Windows provider must be an x64 DLL with its sole getter export')
    for name in result['needed']:
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\.dll', name, re.I):
            raise ValueError('Windows provider import must be an ASCII DLL basename')
        if DYNAMIC_CRT.fullmatch(name):
            raise ValueError('Windows provider imports a forbidden dynamic CRT: ' + name)
        if name.casefold() not in SYSTEM_IMPORTS:
            raise ValueError('Windows provider import escapes the system DLL allowlist: ' + name)
    return {'schema_version': 1, 'kind': 'foundation-windows-provider-static-inspection-v1',
        'scope': 'static-pe-machine-dll-exports-imports-only', 'sha256': digest(raw),
        'bytes': len(raw), 'binary': result, **{name: False for name in FALSE_FACTS}}


def inspect_tool_image(raw):
    """Read native tool machine/sections/imports without executing its entrypoint.

    Tool interpreters may use a retained dynamic CRT. That does not relax the
    provider's separate /MT policy. Imported non-system DLLs still need exact
    single-inventory resolution before a tool path joins a candidate plan.
    """
    if type(raw) is not bytes or not 64 <= len(raw) <= MAX_BINARY or raw[:2] != b'MZ':
        raise ValueError('Native Windows tool needs bounded actual PE bytes')
    nt = struct.unpack_from('<I', raw, 60)[0]
    _span(raw, nt, 24, 'tool PE header')
    if nt < 64 or raw[nt:nt + 4] != b'PE\0\0':
        raise ValueError('Invalid native tool PE signature')
    machine, count, _timestamp, _symbols, _symbol_count, optional_size, flags = struct.unpack_from('<HHIIIHH', raw, nt + 4)
    if machine != 0x8664 or not flags & 2 or not 1 <= count <= 96 or not 224 <= optional_size <= 4096:
        raise ValueError('Native Windows tool must be a bounded x64 PE image')
    optional = nt + 24; _span(raw, optional, optional_size, 'tool optional header')
    if struct.unpack_from('<H', raw, optional)[0] != 0x20b:
        raise ValueError('Native Windows tools require PE32+')
    directories = struct.unpack_from('<I', raw, optional + 108)[0]
    if not 14 <= directories <= 16 or 112 + 8 * directories > optional_size:
        raise ValueError('Native tool PE data-directory shape is incomplete')
    headers = struct.unpack_from('<I', raw, optional + 60)[0]
    image_size = struct.unpack_from('<I', raw, optional + 56)[0]
    section_alignment, file_alignment = struct.unpack_from('<II', raw, optional + 32)
    if (not 4096 <= section_alignment <= 1 << 20 or section_alignment & (section_alignment - 1)
            or not 512 <= file_alignment <= 65536 or file_alignment & (file_alignment - 1)
            or file_alignment > section_alignment or headers % file_alignment
            or image_size <= headers or image_size % section_alignment):
        raise ValueError('Invalid native tool PE image size or alignment')
    table = optional + optional_size; _span(raw, table, count * 40, 'tool sections')
    if not table + 40 * count <= headers <= len(raw):
        raise ValueError('Native tool PE headers are truncated')
    sections = []
    for index in range(count):
        virtual, address, size, offset = struct.unpack_from('<IIII', raw, table + index * 40 + 8)
        extent = max(virtual, size)
        if (not extent or address < headers or address + extent > image_size
                or address % section_alignment or size and (offset < headers or
                    offset % file_alignment or size % file_alignment)):
            raise ValueError('Invalid native tool PE section')
        _span(raw, offset, size, 'tool section data')
        for prior_address, prior_extent, prior_offset, prior_size in sections:
            if address < prior_address + prior_extent and prior_address < address + extent or size and prior_size and offset < prior_offset + prior_size and prior_offset < offset + size:
                raise ValueError('Overlapping native tool PE sections')
        sections.append((address, extent, offset, size))
    def rva(address, size):
        matches = [(offset + address - base, extent - (address - base))
            for base, _virtual, offset, extent in sections
            if base <= address and address - base <= extent and size <= extent - (address - base)]
        if len(matches) != 1:
            raise ValueError('Native tool PE RVA is unbacked or ambiguous')
        return matches[0]
    def directory(index):
        if index >= directories:
            return 0, 0
        address, size = struct.unpack_from('<II', raw, optional + 112 + index * 8)
        if bool(address) != bool(size):
            raise ValueError('Incomplete native tool PE directory')
        if address: rva(address, size)
        return address, size
    # A tool's delayed/bound/CLR dependencies would escape the finite import
    # resolution below. They need a separately reviewed successor policy.
    if any(directory(index) != (0, 0) for index in (11, 13, 14)):
        raise ValueError('Native tool has unsupported bound/delayed/CLR dependencies')
    export_address, export_size = directory(0)
    if export_address:
        export_at, _available = rva(export_address, 40)
        function_count = struct.unpack_from('<I', raw, export_at + 20)[0]
        functions_address = struct.unpack_from('<I', raw, export_at + 28)[0]
        if export_size < 40 or not 1 <= function_count <= 65536 or not functions_address:
            raise ValueError('Invalid native tool export table')
        functions_at, _available = rva(functions_address, function_count * 4)
        for index in range(function_count):
            address = struct.unpack_from('<I', raw, functions_at + index * 4)[0]
            if export_address <= address < export_address + export_size:
                raise ValueError('Native tool/runtime forwarded exports need a separate closed policy')
    needed, import_count = [], 0
    address, size = directory(1)
    if address:
        at, _available = rva(address, size)
        if size < 20:
            raise ValueError('Truncated native tool import descriptors')
        for cursor in range(0, size - 19, 20):
            original, timestamp, chain, name, first = struct.unpack_from('<IIIII', raw, at + cursor)
            if not any((original, timestamp, chain, name, first)): break
            if timestamp or chain or not name or not first or len(needed) >= 4096:
                raise ValueError('Unsupported native tool import descriptor')
            location, available = rva(name, 1)
            end = raw.find(b'\0', location, location + min(available, 129))
            if end < 0:
                raise ValueError('Unterminated native tool import basename')
            try: library = raw[location:end].decode('ascii')
            except UnicodeError as error: raise ValueError('Non-ASCII native tool import') from error
            if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\.dll', library, re.I) or library.casefold() in needed:
                raise ValueError('Aliased or repeated native tool import')
            needed.append(library.casefold())
            # Both lookup and IAT arrays must be backed through their complete
            # terminators. A nonzero FirstThunk alone is not import evidence.
            lookup = original or first
            for index in range(65536):
                lookup_at, _available = rva(lookup + index * 8, 8)
                rva(first + index * 8, 8)
                value = struct.unpack_from('<Q', raw, lookup_at)[0]
                if not value:
                    break
                import_count += 1
                if import_count > 65536:
                    raise ValueError('Native tool PE import-symbol bound exceeded')
                if value & (1 << 63):
                    if value & ~((1 << 63) | 0xffff) or not value & 0xffff:
                        raise ValueError('Invalid native tool ordinal import')
                else:
                    if value > 0xffffffff:
                        raise ValueError('Invalid native tool imported-name RVA width')
                    rva(value, 2)
                    symbol_at, available = rva(value + 2, 1)
                    end = raw.find(b'\0', symbol_at, symbol_at + min(available, 65536))
                    if end <= symbol_at:
                        raise ValueError('Native tool imported symbol is empty or unterminated')
                    try: raw[symbol_at:end].decode('ascii')
                    except UnicodeError as error: raise ValueError('Non-ASCII native tool imported symbol') from error
            else:
                raise ValueError('Native tool import lookup lacks its bounded terminator')
        else:
            raise ValueError('Native tool imports lack their complete terminator')
    return {'machine': 'x86_64', 'format': 'pe32plus', 'dll': bool(flags & 0x2000), 'needed': needed}


def _span(raw, offset, size, label):
    if offset < 0 or size < 0 or offset > len(raw) or size > len(raw) - offset:
        raise ValueError('Truncated COFF ' + label)
    return raw[offset:offset + size]


def _directives(raw, allowed_default_libraries=None):
    try:
        text = raw.rstrip(b'\0').decode('ascii')
    except UnicodeError as error:
        raise ValueError('COFF linker directives must be bounded ASCII') from error
    # Directive arguments can be quoted; whitespace inside a quoted argument is
    # retained so it cannot hide a second /DEFAULTLIB or mismatched CRT request.
    tokens, cursor = [], 0
    while cursor < len(text):
        if text[cursor].isspace(): cursor += 1; continue
        token, quoted = '', False
        while cursor < len(text) and (quoted or not text[cursor].isspace()):
            char = text[cursor]; cursor += 1
            if char == '"': quoted = not quoted
            else: token += char
        if quoted:
            raise ValueError('Unterminated COFF linker directive quote')
        tokens.append(token)
    for token in tokens:
        lowered = token.casefold()
        if not lowered.startswith(('/defaultlib:', '-defaultlib:', '/failifmismatch:',
                '-failifmismatch:', '/include:', '-include:', '/alternatename:',
                '-alternatename:', '/merge:', '-merge:', '/section:', '-section:')):
            raise ValueError('COFF archive has an unsupported linker directive; no ambient path/output escape is allowed')
        if lowered.startswith(('/defaultlib:', '-defaultlib:')):
            library = lowered.split(':', 1)[1]
            if library.endswith('.lib'): library = library[:-4]
            if (not re.fullmatch('[a-z0-9_.-]+', library) or library.startswith(
                    ('msvcrt', 'msvcprt', 'ucrt', 'vcruntime', 'concrt', 'vccorlib')) or
                    library in ('libcmtd', 'libcpmtd', 'libvcruntimed', 'libucrtd')):
                raise ValueError('COFF archive requests a dynamic CRT or aliased default library')
            if allowed_default_libraries is not None and library not in allowed_default_libraries:
                raise ValueError('COFF default library escapes the exact static dependency/system library set: ' + library)
        if lowered.startswith(('/failifmismatch:', '-failifmismatch:')) and 'runtimelibrary=' in lowered:
            if lowered.split('runtimelibrary=', 1)[1] != 'mt_staticrelease':
                raise ValueError('COFF archive has a non-/MT Release runtime mismatch')
    return tokens


def inspect_coff_object(raw, *, allowed_default_libraries=None):
    """Strict ordinary COFF/BigObj reader; import objects never count as static."""
    if type(raw) is not bytes or len(raw) < 20 or len(raw) > MAX_BINARY:
        raise ValueError('Bounded COFF object bytes required')
    symbol_size = 18
    if raw[:4] == b'\0\0\xff\xff':
        # ANON_OBJECT_HEADER_BIGOBJ has this exact class id and version >=2.
        if len(raw) < 56 or struct.unpack_from('<H', raw, 4)[0] != 2 or raw[12:28] != bytes.fromhex('c7a1bad1eebaa94baf20faf66aa4dcb8'):
            raise ValueError('COFF short import/anonymous object is not a static object')
        machine = struct.unpack_from('<H', raw, 6)[0]
        sections, symbols, count = struct.unpack_from('<III', raw, 44)
        header, symbol_size = 56, 20
    else:
        machine, sections, _timestamp, symbols, count, optional, flags = struct.unpack_from('<HHIIIHH', raw)
        if optional or flags & 0x2002:
            raise ValueError('COFF archive contains an image or optional header')
        header = 20
    if machine != 0x8664 or not 1 <= sections <= 65536 or count > 16 * 1024 * 1024:
        raise ValueError('Static Windows archive requires bounded x86_64 COFF objects')
    table_end = header + sections * 40
    _span(raw, header, sections * 40, 'section table')
    strings = b''
    if symbols:
        _span(raw, symbols, count * symbol_size + 4, 'symbol table')
        string_at = symbols + count * symbol_size
        string_size = struct.unpack_from('<I', raw, string_at)[0]
        if string_size < 4:
            raise ValueError('Invalid COFF string table size')
        strings = _span(raw, string_at, string_size, 'string table')
        if symbols < table_end:
            raise ValueError('COFF symbol table overlaps headers')
    elif count:
        raise ValueError('COFF symbols lack their table')
    primary_symbols, symbol_index = set(), 0
    while symbol_index < count:
        symbol_at = symbols + symbol_index * symbol_size
        symbol = _span(raw, symbol_at, symbol_size, 'primary symbol')
        auxiliary_count = symbol[-1]
        if auxiliary_count > count - symbol_index - 1:
            raise ValueError('COFF auxiliary symbol records exceed the declared symbol table')
        section = struct.unpack_from('<i' if symbol_size == 20 else '<h', symbol, 12)[0]
        if not -2 <= section <= sections:
            raise ValueError('COFF primary symbol has an invalid section number')
        if symbol[:4] == bytes(4):
            string_offset = struct.unpack_from('<I', symbol, 4)[0]
            if not 4 <= string_offset < len(strings) or strings.find(b'\0', string_offset) < 0:
                raise ValueError('COFF primary symbol has an invalid long name')
        elif not symbol[:8].split(b'\0', 1)[0]:
            raise ValueError('COFF primary symbol has an empty name')
        primary_symbols.add(symbol_index)
        symbol_index += 1 + auxiliary_count
    directives = []
    spans = [(0, table_end)]
    if symbols:
        spans.append((symbols, count * symbol_size + len(strings)))
    for index in range(sections):
        at = header + index * 40
        name_raw = raw[at:at + 8].rstrip(b'\0')
        if name_raw.startswith(b'/'):
            if not name_raw[1:].isdigit() or not strings:
                raise ValueError('Invalid COFF long section name')
            position = int(name_raw[1:]); _span(strings, position, 1, 'long section name')
            end = strings.find(b'\0', position)
            if position < 4 or end < 0 or end - position > 128:
                raise ValueError('Unterminated COFF long section name')
            name_raw = strings[position:end]
        try: name = name_raw.decode('ascii')
        except UnicodeError as error: raise ValueError('Invalid COFF section name') from error
        size, offset, relocations, line_numbers, reloc_count, line_count = struct.unpack_from('<IIIIHH', raw, at + 16)
        if struct.unpack_from('<I', raw, at + 36)[0] & 0x01000000:
            raise ValueError('COFF relocation-overflow sections need a separate bounded reader')
        if name.startswith('.idata'):
            raise ValueError('COFF archive contains an old-format import-library object')
        for start, length, label in ((offset, size, 'section data'),
                (relocations, reloc_count * 10, 'relocations'), (line_numbers, line_count * 6, 'line numbers')):
            if length:
                if start < table_end:
                    raise ValueError('COFF data overlaps its headers')
                _span(raw, start, length, label)
                for previous, extent in spans:
                    if start < previous + extent and previous < start + length:
                        raise ValueError('Overlapping COFF data ranges')
                spans.append((start, length))
        for relocation_index in range(reloc_count):
            _address, symbol_index, relocation_type = struct.unpack_from('<IIH', raw, relocations + relocation_index * 10)
            if symbol_index not in primary_symbols:
                raise ValueError('COFF relocation must reference an existing primary symbol, not an absent or auxiliary record')
            if relocation_type > 0x10:
                raise ValueError('COFF relocation has an unsupported x64 type')
        if name == '.drectve':
            directives.extend(_directives(_span(raw, offset, size, 'directives'), allowed_default_libraries))
    return {'machine': 'x86_64', 'sections': sections, 'directives': directives,
            'format': 'coff-bigobj' if symbol_size == 20 else 'coff'}


def inspect_static_archive(raw, *, allowed_default_libraries=None):
    """Read Microsoft regular archives, including its two '/' linker members."""
    if type(raw) is not bytes or not 8 <= len(raw) <= MAX_BINARY or raw[:8] != b'!<arch>\n':
        raise ValueError('Windows dependencies require a bounded regular COFF archive')
    cursor, tables, longnames, members, names, indexes, member_offsets = 8, 0, None, [], set(), [], set()
    while cursor < len(raw):
        if len(members) + tables >= 65536:
            raise ValueError('Windows COFF archive member bound exceeded')
        header_offset = cursor
        header = _span(raw, cursor, 60, 'archive member header'); cursor += 60
        if header[58:] != b'`\n' or not re.fullmatch(rb' *[0-9]+ *', header[48:58]):
            raise ValueError('Malformed Windows COFF archive member header')
        size = int(header[48:58]); body = _span(raw, cursor, size, 'archive member'); cursor += size
        if cursor & 1:
            if _span(raw, cursor, 1, 'archive padding') != b'\n':
                raise ValueError('Invalid Windows COFF archive padding')
            cursor += 1
        try: name = header[:16].decode('ascii').rstrip(' ')
        except UnicodeError as error: raise ValueError('Non-ASCII COFF member name') from error
        if name == '/':
            tables += 1
            if tables > 2 or members or longnames is not None:
                raise ValueError('Misplaced or extra COFF linker table')
            indexes.append(body)
            continue
        if name == '//':
            if longnames is not None or members:
                raise ValueError('Misplaced or repeated COFF long-name table')
            longnames = body
            continue
        if name.startswith('/'):
            if not name[1:].isdigit() or longnames is None:
                raise ValueError('Invalid COFF long-member reference')
            position = int(name[1:]); _span(longnames, position, 1, 'member name')
            # Microsoft uses NUL; LLVM's GNU-compatible writer may use /\n.
            ends = [end for end in (longnames.find(b'\0', position), longnames.find(b'/\n', position)) if end >= 0]
            if not ends:
                raise ValueError('Unterminated COFF archive member name')
            try: name = longnames[position:min(ends)].decode('ascii')
            except UnicodeError as error: raise ValueError('Invalid long COFF member name') from error
        else:
            name = name.removesuffix('/')
        if not re.fullmatch(r'[A-Za-z0-9_.$+()-]{1,240}', name) or name.casefold() in names:
            raise ValueError('Unsafe or repeated COFF archive object name')
        names.add(name.casefold())
        member_offsets.add(header_offset)
        members.append({'name': name, 'sha256': digest(body),
            **inspect_coff_object(body, allowed_default_libraries=allowed_default_libraries)})
    if not members:
        raise ValueError('Windows static archive contains no actual COFF object')
    for index, body in enumerate(indexes):
        _span(body, 0, 4, 'linker index count')
        count = struct.unpack_from('>I' if index == 0 else '<I', body)[0]
        if count > 1048576:
            raise ValueError('COFF linker index exceeds its symbol/member bound')
        _span(body, 4, count * 4, 'linker index offsets')
        offsets = struct.unpack_from(('>' if index == 0 else '<') + str(count) + 'I', body, 4)
        if any(offset not in member_offsets for offset in offsets):
            raise ValueError('COFF linker index points outside actual object members')
        cursor = 4 + count * 4
        symbols = count
        if index == 1:
            _span(body, cursor, 4, 'second linker symbol count')
            symbols = struct.unpack_from('<I', body, cursor)[0]; cursor += 4
            if symbols > 1048576:
                raise ValueError('COFF second linker symbol bound exceeded')
            _span(body, cursor, symbols * 2, 'second linker member indices')
            indices = struct.unpack_from('<' + str(symbols) + 'H', body, cursor)
            if any(not 1 <= value <= count for value in indices):
                raise ValueError('COFF second linker index has an invalid member number')
            cursor += symbols * 2
        names_raw = body[cursor:]
        if (symbols and (not names_raw.endswith(b'\0') or len(names_raw.split(b'\0')) != symbols + 1)
                or not symbols and names_raw or any(not name for name in names_raw.split(b'\0')[:-1])):
            raise ValueError('COFF linker index has an incomplete symbol string table')
    return {'format': 'coff-archive', 'machine': 'x86_64', 'sha256': digest(raw),
            'bytes': len(raw), 'members': members}


def _inventory_subject(value):
    return digest(encoded({key: item for key, item in value.items() if key != 'provenance'}))


def inspect_inventory(reference, role):
    """Join every retained file to a finite inventory and original provenance.

    This is a consistency admission. Producer/runtime qualification remains a
    separate original-evidence contract; a `passed` string cannot create it.
    """
    path, pin = _reference(reference, role + ' complete inventory')
    value = _document(path, pin)
    contract.fields(value, ('schema_version', 'kind', 'role', 'target', 'root', 'version',
                            'files', 'directories', 'provenance'), role + ' inventory')
    if (type(value['schema_version']) is not int or value['schema_version'] != 1 or
            value['kind'] != 'foundation-windows-retained-inventory-v1' or
            value['role'] != role or value['target'] != contract.TARGET):
        raise ValueError('Windows retained inventory schema/role/target differs')
    root = contract.windows_path(value['root'], role + ' root')
    contract.text(value['version'], role + ' version')
    files, directories = value['files'], value['directories']
    if type(files) is not dict or not 1 <= len(files) <= MAX_INVENTORY_FILES or type(directories) is not list:
        raise ValueError('Windows retained inventory needs a bounded complete file map')
    if directories != sorted(set(directories)) or len(directories) > MAX_INVENTORY_FILES:
        raise ValueError('Windows retained directories must be bounded, unique and sorted')
    kinds, total = {}, 0
    for name in directories:
        _relative(name); kinds[name.casefold()] = (name, 'directory')
    if len(kinds) != len(directories):
        raise ValueError('Windows retained inventory has case aliases')
    for name, record in files.items():
        _relative(name); contract.fields(record, ('sha256', 'bytes'), role + ' file')
        contract.pin(record['sha256'], role + '/' + name)
        total += _integer(record['bytes'], role + ' file bytes', 0, MAX_BINARY)
        if name.casefold() in kinds or total > MAX_INVENTORY_BYTES:
            raise ValueError('Windows retained inventory aliases or exceeds its total bound')
        kinds[name.casefold()] = (name, 'file')
        for parent in PurePosixPath(name).parents:
            if str(parent) != '.' and kinds.get(str(parent).casefold()) != (str(parent), 'directory'):
                raise ValueError('Windows retained inventory omits or aliases a parent directory')
    root_path = _ordinary(root, directory=True)
    actual, pending = {}, [root_path]
    while pending:
        current = pending.pop()
        with os.scandir(current) as children:
            for child in children:
                name = Path(child.path).relative_to(root_path).as_posix()
                if len(actual) >= 2 * MAX_INVENTORY_FILES or name.casefold() not in kinds:
                    raise ValueError('Windows retained tree contains an unlisted entry')
                original, kind = kinds[name.casefold()]
                if name != original:
                    raise ValueError('Windows retained tree spelling differs from its inventory')
                _ordinary(child.path, directory=kind == 'directory')
                actual[name] = kind
                if kind == 'directory': pending.append(Path(child.path))
                else:
                    raw = _read(child.path, files[name]['sha256'], maximum=MAX_BINARY)
                    if len(raw) != files[name]['bytes']:
                        raise ValueError('Windows retained file size differs from its inventory')
    if actual != {name: kind for name, kind in kinds.values()}:
        raise ValueError('Windows retained tree is incomplete')
    provenance_path, provenance_pin = _reference(value['provenance'], role + ' original provenance')
    provenance = _document(provenance_path, provenance_pin)
    contract.fields(provenance, ('schema_version', 'kind', 'role', 'target', 'inventory_subject_sha256',
        'sources', 'notices', 'original_reports'), role + ' original provenance')
    if (type(provenance['schema_version']) is not int or provenance['schema_version'] != 1 or
            provenance['kind'] != 'foundation-windows-retained-provenance-v1' or provenance['role'] != role or
            provenance['target'] != contract.TARGET or provenance['inventory_subject_sha256'] != _inventory_subject(value)):
        raise ValueError('Windows inventory and original provenance do not join')
    protected_paths = [root, path, provenance_path]
    for category in ('sources', 'notices', 'original_reports'):
        references = provenance[category]
        if type(references) is not list or not 1 <= len(references) <= 256:
            raise ValueError('Windows provenance needs finite original ' + category)
        seen = set()
        for item in references:
            selected, selected_pin = _reference(item, role + ' original ' + category)
            if selected.casefold() in seen:
                raise ValueError('Repeated Windows provenance reference')
            seen.add(selected.casefold())
            _read(selected, selected_pin, maximum=MAX_BINARY)
            protected_paths.append(selected)
    return {'reference': copy.deepcopy(reference), 'root': root, 'version': value['version'],
            'files': copy.deepcopy(files), 'directories': list(directories),
            'provenance': copy.deepcopy(value['provenance']),
            'protected_paths': list(dict.fromkeys(protected_paths))}


def _selected_file(reference, inventories, roles, label):
    path, pin = _reference(reference, label)
    candidates = []
    for role in roles:
        inventory = inventories[role]
        if contract.inside(path, inventory['root']):
            name = PureWindowsPath(path).relative_to(PureWindowsPath(inventory['root'])).as_posix()
            if inventory['files'].get(name, {}).get('sha256') == pin:
                candidates.append((role, name))
    if len(candidates) != 1:
        raise ValueError('Selected Windows file lacks one exact complete inventory identity: ' + label)
    return path


def _admission(value, handoff):
    value, original_admission_sha256 = _engine_admission_view(value, handoff)
    contract.fields(value, ('schema_version', 'kind', 'target', 'handoff_sha256',
        'recipe_sha256', 'sources_sha256', 'provider_build_sha256', 'metadata_header_sha256',
        'toolchain_identity_sha256', 'inventories', 'programs', 'builtins', 'crt_libraries',
        'program_versions', 'include_directories', 'library_directories', 'system_root'), 'Windows native admission')
    if (type(value['schema_version']) is not int or
            (value['schema_version'], value['kind']) not in (
                (1, 'foundation-native-engine-windows-admission-v1'),
                (2, 'foundation-native-engine-windows-admission-v2')) or value['target'] != contract.TARGET):
        raise ValueError('Unsupported native Windows admission schema/target')
    for name in ('handoff_sha256', 'recipe_sha256', 'sources_sha256', 'provider_build_sha256',
                 'metadata_header_sha256', 'toolchain_identity_sha256'):
        if contract.pin(value[name], name) != handoff[name]:
            raise ValueError('Windows admission differs from immutable handoff: ' + name)
    contract.fields(value['inventories'], INVENTORY_ROLES, 'Windows complete inventories')
    inventories = {role: inspect_inventory(value['inventories'][role], role) for role in sorted(INVENTORY_ROLES)}
    roots = [PureWindowsPath(item['root']) for item in inventories.values()]
    for index, left in enumerate(roots):
        if any(left == right or left in right.parents or right in left.parents for right in roots[index + 1:]):
            raise ValueError('Windows complete inventory roots overlap')
    contract.fields(value['programs'], PROGRAM_NAMES, 'Windows admitted programs')
    contract.fields(value['program_versions'], PROGRAM_NAMES, 'Windows admitted program versions')
    for role, version in value['program_versions'].items():
        if type(version) is not str or not re.fullmatch(r'[1-9][0-9]*\.[0-9]+(?:\.[0-9]+){0,2}', version):
            raise ValueError('An exact dotted native tool version is required: ' + role)
        numbers = tuple(int(part) for part in version.split('.'))
        minimum = {'cmake': (3, 24), 'ninja': (1, 10), 'python': (3, 9),
                   'perl': (5, 10), 'ruby': (2, 5), 'gperf': (3, 0)}.get(role, (19, 1, 7))
        if numbers < minimum:
            raise ValueError('Native Windows tool is below its declared producer baseline: ' + role)
    programs = {}
    for role, names in PROGRAM_NAMES.items():
        path = _selected_file(value['programs'][role], inventories,
            ('llvm',) if role in ('compiler', 'linker', 'archiver', 'resource_compiler', 'manifest_tool') else ('host_generators',), role)
        if PureWindowsPath(path).name not in names:
            raise ValueError('Windows program has the wrong finite role: ' + role)
        if inspect_tool_image(_read(path, value['programs'][role]['sha256'], maximum=MAX_BINARY))['dll']:
            raise ValueError('Native Windows program must be an executable image: ' + role)
        programs[role] = path
    inputs = contract.validate_inputs(handoff['native_inputs'])
    chain = inputs['toolchain']
    if programs['compiler'] != chain['compiler']['path'] or programs['linker'] != chain['linker']['path']:
        raise ValueError('Windows CMake programs and native input manifest disagree')
    for role in ('compiler', 'linker'):
        if value['programs'][role] != chain[role] or value['program_versions'][role] != chain['compiler_version']:
            raise ValueError('Windows compiler/linker independent pins or exact LLVM versions disagree')
    for role in ('archiver', 'resource_compiler', 'manifest_tool'):
        if value['program_versions'][role] != chain['compiler_version']:
            raise ValueError('Native LLVM tools must share the selected exact release')
    for role in ('msvc_stl', 'windows_sdk'):
        if chain[role] != {'root': inventories[role]['root'], 'inventory': value['inventories'][role]}:
            raise ValueError('Windows SDK/STL inventory differs from native input manifest')
    if (inputs['dependency_prefix'] != inventories['native_dependencies']['root'] or
            inputs['dependency_inventory'] != value['inventories']['native_dependencies'] or
            chain['compiler_version'] != inventories['llvm']['version']):
        raise ValueError('Windows dependency/toolchain identity differs from native input manifest')
    if not re.fullmatch(r'14\.[0-9]+\.[0-9]+', inventories['msvc_stl']['version']) or not re.fullmatch(r'10\.0\.[0-9]+\.[0-9]+', inventories['windows_sdk']['version']):
        raise ValueError('Explicit Microsoft STL/toolset and Windows 10 SDK versions are required')
    # Resolve all declared tool imports, including those of retained runtime
    # DLLs, inside the complete tool inventories or the explicit system set.
    runtime_images, runtime_paths = {}, {}
    for role in ('llvm', 'host_generators'):
        inventory = inventories[role]
        for name, record in inventory['files'].items():
            if PurePosixPath(name).suffix.casefold() not in ('.exe', '.dll', '.pyd'):
                continue
            basename = PurePosixPath(name).name.casefold()
            if basename in runtime_images:
                raise ValueError('Windows tool runtime DLL basename has ambiguous inventory resolution')
            path = _join(inventory['root'], name)
            runtime_images[basename] = inspect_tool_image(_read(path, record['sha256'], maximum=MAX_BINARY))
            runtime_paths[basename] = path
    tool_system = SYSTEM_IMPORTS | {'msvcrt.dll', 'ucrtbase.dll'}
    loader_directories = {PureWindowsPath(path).parent for path in programs.values()}
    for name, image in runtime_images.items():
        for needed in image['needed']:
            if needed in tool_system or re.fullmatch(r'api-ms-win-(?:core|security|crt)-[a-z0-9-]+\.dll', needed):
                continue
            if (needed not in runtime_images or not runtime_images[needed]['dll'] or
                    PureWindowsPath(runtime_paths[needed]).parent not in loader_directories):
                raise contract.MissingInputs([_missing('host-tool-runtime', needed,
                    'native tool import has no unique pinned DLL in the explicit loader search locations: ' + name)])
    builtins = _selected_file(value['builtins'], inventories, ('llvm',), 'clang static builtins')
    if value['builtins'] != chain['builtins']:
        raise ValueError('Windows clang builtins differ from native input manifest')
    expected_crt = {'libcmt', 'libcpmt', 'libvcruntime', 'libucrt', 'oldnames'}
    allowed_defaults = expected_crt | set(contract.SYSTEM_LINKS) | {'dwrite', 'd2d1', 'windowscodecs', 'uuid'} | {
        PureWindowsPath(item['path']).stem.casefold() for item in inputs['libraries'].values()}
    allowed_defaults.add(PureWindowsPath(builtins).stem.casefold())
    inspect_static_archive(_read(builtins, value['builtins']['sha256'], maximum=MAX_BINARY),
                           allowed_default_libraries=allowed_defaults)
    contract.fields(value['crt_libraries'], expected_crt, 'Windows static Release CRT library set')
    for role, reference in value['crt_libraries'].items():
        path = _selected_file(reference, inventories, ('msvc_stl', 'windows_sdk'), role)
        if PureWindowsPath(path).name.casefold() != role + '.lib':
            raise ValueError('Windows static CRT library basename differs: ' + role)
        inspect_static_archive(_read(path, reference['sha256'], maximum=MAX_BINARY),
                               allowed_default_libraries=allowed_defaults)
    for name, item in inputs['libraries'].items():
        path = _selected_file({key: item[key] for key in ('path', 'sha256')}, inventories,
                              ('native_dependencies',), name)
        inspect_static_archive(_read(path, item['sha256'], maximum=MAX_BINARY),
                               allowed_default_libraries=allowed_defaults)
    for category in ('include_directories', 'library_directories'):
        values = value[category]
        if type(values) is not list or not 1 <= len(values) <= 32 or len(set(values)) != len(values):
            raise ValueError('Windows explicit search directories must be bounded and unique')
        for path in values:
            contract.windows_path(path, category)
            matches = [item for item in inventories.values() if contract.inside(path, item['root']) and
                PureWindowsPath(path).relative_to(PureWindowsPath(item['root'])).as_posix() in item['directories']]
            if len(matches) != 1:
                raise ValueError('Windows search directory lacks an exact complete inventory')
    system_root = contract.windows_path(value['system_root'], 'Windows system root')
    protected_paths = list(dict.fromkeys(path for inventory in inventories.values()
        for path in inventory['protected_paths']))
    return {'inventories': inventories, 'programs': programs, 'native_inputs': inputs,
        'include_directories': list(value['include_directories']), 'library_directories': list(value['library_directories']),
        'system_root': system_root, 'admission_sha256': (original_admission_sha256
            if original_admission_sha256 is not None else digest(encoded(value))),
        'protected_paths': protected_paths}


def _join(root, name):
    return (PureWindowsPath(root) / PurePosixPath(_relative(name))).as_posix()


def render_cache(template, values):
    if type(template) is not bytes or type(values) is not dict:
        raise ValueError('Windows CMake template and values have invalid types')
    text = template.decode('ascii')
    tokens = set(re.findall(r'@([A-Za-z_][A-Za-z_0-9]*)@', text))
    if not tokens or set(values) != tokens:
        raise ValueError('Windows CMake values must exactly match finite template tokens')
    for name, value in values.items():
        if (type(value) is not str or not value or len(value) > 4096 or
                any(ord(char) < 32 or ord(char) >= 127 or char in ';"\\$@' for char in value)):
            raise ValueError('Windows CMake token is not a bounded literal: ' + name)
        text = text.replace('@' + name + '@', value)
    if '@' in text:
        raise ValueError('Unresolved Windows CMake token')
    return text.encode('ascii')


def native_environment(admission, output):
    """Construct from admitted paths only; never copy os.environ."""
    contract.windows_path(output, 'Windows output root')
    programs = admission['programs']
    search = []
    for role in sorted(programs):
        directory = PureWindowsPath(programs[role]).parent.as_posix()
        if directory not in search: search.append(directory)
    system = admission['system_root']
    return {'SystemRoot': system, 'WINDIR': system, 'PATH': ';'.join(search + [system + '/System32']),
        'INCLUDE': ';'.join(admission['include_directories']), 'LIB': ';'.join(admission['library_directories']),
        'TEMP': output + '/tmp', 'TMP': output + '/tmp', 'PYTHONNOUSERSITE': '1',
        'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONUTF8': '1', 'LC_ALL': 'C', 'LANG': 'C',
        'TZ': 'UTC', 'SOURCE_DATE_EPOCH': '0'}


def _candidate_plan(selection, handoff, admission, *, repository_root=ROOT):
    output, source = selection['output_root'], selection['handoff']['root']
    build = output + '/cmake'
    paths = handoff['paths']; programs = admission['programs']
    retained = _join(source, paths['retained'])
    assembled = _join(source, paths['assembled'])
    # Metadata generation is intentionally absent: consume the exact POSIX output.
    metadata = _join(source, paths['metadata_header'])
    input_path = _join(source, paths['native_inputs'])
    values = {'CMAKE_TOOLCHAIN_FILE': output + '/windows-toolchain.cmake',
        'CMAKE_C_COMPILER': programs['compiler'], 'CMAKE_CXX_COMPILER': programs['compiler'],
        'CMAKE_LINKER': programs['linker'], 'CMAKE_AR': programs['archiver'],
        'CMAKE_RC_COMPILER': programs['resource_compiler'], 'CMAKE_MT': programs['manifest_tool'],
        'CMAKE_MAKE_PROGRAM': programs['ninja'], 'Python_EXECUTABLE': programs['python'],
        'PERL_EXECUTABLE': programs['perl'], 'Ruby_EXECUTABLE': programs['ruby'],
        'GPERF_EXECUTABLE': programs['gperf'], 'FOUNDATION_NATIVE_DEPENDENCY_PREFIX': admission['native_inputs']['dependency_prefix'],
        'FOUNDATION_NATIVE_WINDOWS_INPUTS': input_path,
        'FOUNDATION_NATIVE_WINDOWS_INPUTS_SHA256': handoff['files'][paths['native_inputs']],
        'BIB_NATIVE_PROVIDER_SOURCE_ROOT': assembled,
        'BIB_NATIVE_PROVIDER_BINDING_SOURCE': assembled + '/source/document-provider/runtime/BibNativeDocumentActionsBinding.cpp',
        'BIB_NATIVE_PROVIDER_BINDING_HEADER': assembled + '/source/native/BibNativeProviderBootstrap.hpp',
        'BIB_NATIVE_PROVIDER_METADATA_HEADER': metadata,
        'BIB_NATIVE_PROVIDER_METADATA_HEADER_SHA256': handoff['metadata_header_sha256'],
        'BIB_NATIVE_EMBEDDER_CMAKE': retained + '/cmake/native-provider.cmake'}
    # The immutable source catalogue, not an inferred filesystem spelling, owns
    # binding paths and pins. Refuse missing authority rather than guessing.
    for variable in ('BIB_NATIVE_PROVIDER_BINDING_SOURCE', 'BIB_NATIVE_PROVIDER_BINDING_HEADER'):
        relative = PureWindowsPath(values[variable]).relative_to(PureWindowsPath(source)).as_posix()
        if relative not in handoff['files']:
            raise contract.MissingInputs([_missing('native-provider-binding', values[variable],
                'exact retained binding path is not present in the handoff inventory')])
        values[variable + '_SHA256'] = handoff['files'][relative]
    rendered = {}
    for template, destination in (('windows-toolchain.cmake.in', 'windows-toolchain.cmake'),
                                  ('windows-initial-cache.cmake.in', 'windows-initial-cache.cmake')):
        raw = _read(Path(repository_root) / RECIPE / template)
        tokens = set(re.findall(rb'@([A-Za-z_][A-Za-z_0-9]*)@', raw))
        rendered[destination] = render_cache(raw, {token.decode(): values[token.decode()] for token in tokens}).decode('ascii')
    missing = [
        _missing('windows-publication-adapter', output,
            'complete original native Windows handle-relative publication qualification is required for build'),
        _missing('native-source-replay', source,
            'passive plan requires the original held supplier extraction and reviewed overlay replay admission at build'),
        _missing('native-dependency-producer-proof', admission['native_inputs']['dependency_prefix'],
            'complete retained original D/O/H/W dependency admission is required; byte consistency alone is insufficient'),
    ]
    return {'schema_version': 1, 'kind': PLAN_KIND, 'scope': SCOPE, 'target': dict(contract.TARGET),
        'selection': copy.deepcopy(selection), 'handoff_sha256': handoff['handoff_sha256'],
        'source_catalogue': copy.deepcopy(contract.CATALOGUE),
        'metadata': {name: handoff[name] for name in ('recipe_sha256', 'sources_sha256',
            'provider_build_sha256', 'metadata_header_sha256', 'toolchain_identity_sha256')},
        'admission_sha256': admission['admission_sha256'], 'rendered': rendered,
        'environment': native_environment(admission, output),
        'commands': [{'phase': 'configure', 'argv': [programs['cmake'], '-S', assembled + '/source/engine',
            '-B', build, '-G', 'Ninja', '-C', output + '/windows-initial-cache.cmake'], 'cwd': output},
            {'phase': 'build', 'argv': [programs['cmake'], '--build', build, '--config', 'Release',
            '--target', 'BibNativeProvider', '--parallel', str(selection['phase_limits']['maximum_jobs'])], 'cwd': output}],
        'executable_plan': False, 'build': False, 'missing_admission': missing,
        **{name: False for name in FALSE_FACTS}}


def create_plan(selection_path, pin, *, repository_root=ROOT):
    selection = validate_selection(_document(selection_path, pin))
    import appended_engine_windows_handoff as handoff_tool
    handoff = handoff_tool.verify_handoff(selection['handoff']['root'], selection['handoff']['sha256'])
    if handoff['target'] != contract.TARGET or handoff['source_catalogue'] != contract.CATALOGUE:
        raise ValueError('Windows handoff source catalogue or target differs from this producer')
    reference, admission_pin = _reference(selection['admission'], 'complete Windows native admission')
    admitted = _admission(_document(reference, admission_pin), handoff)
    admitted['admission_sha256'] = admission_pin  # preserve the original independently pinned bytes
    output = PureWindowsPath(selection['output_root'])
    selected_metadata = contract.windows_path(PureWindowsPath(os.fspath(selection_path)).as_posix(),
                                               'Windows selection metadata')
    protected = list(dict.fromkeys(contract.windows_path(PureWindowsPath(os.fspath(value)).as_posix(),
        'protected Windows authority input') for value in [selected_metadata, selection['admission']['path'],
        *handoff['protected_paths'], *admitted['protected_paths']]))
    for value in protected:
        other = PureWindowsPath(value)
        if output == other or output in other.parents or other in output.parents:
            raise ValueError('Windows output overlaps a retained admission input')
    plan = _candidate_plan(selection, handoff, admitted, repository_root=repository_root)
    plan['protected_paths'] = list(protected)
    return plan


def require_native_host():
    if os.name != 'nt' or platform.system() != 'Windows' or platform.machine().casefold() not in ('amd64', 'x86_64') or struct.calcsize('P') != 8:
        raise ValueError('Windows engine build requires a native Windows x64 Python host; no cross-host fallback')


def _output_usage(root):
    total, entries, pending = 0, 0, [_ordinary(root, directory=True)]
    while pending:
        current = pending.pop()
        with os.scandir(current) as children:
            for child in children:
                entries += 1
                if entries > MAX_OUTPUT_ENTRIES:
                    raise ValueError('Windows candidate output entry bound exceeded')
                state = child.stat(follow_symlinks=False)
                directory = stat.S_ISDIR(state.st_mode)
                _ordinary(child.path, directory=directory)
                if directory: pending.append(Path(child.path))
                else: total += state.st_size
    return total


def run_owned(argv, cwd, stream, environment, limits, *, phase, resource_root):
    """Run only within a caller-owned private tree and retain uncertain owners.

    The caller must already own the stream/tree through qualified publication.
    This helper does not create, save, remove, relaunch or publish any path.
    Windows Job Objects own descendants before the first instruction executes.
    """
    require_native_host()
    limits = validate_limits(limits)
    if phase not in ('configure', 'build') or type(argv) is not list or not argv:
        raise ValueError('Unknown or empty finite Windows command')
    if any(type(item) is not str or not item or '\0' in item for item in argv):
        raise ValueError('Windows command arguments must be bounded literal strings')
    contract.windows_path(argv[0], 'native command executable')
    contract.windows_path(str(cwd), 'native command working directory')
    if type(environment) is not dict or any(type(key) is not str or type(value) is not str or '\0' in key + value for key, value in environment.items()):
        raise ValueError('Invalid explicit Windows command environment')
    if not hasattr(stream, 'fileno'):
        raise ValueError('Windows command needs an already owned binary log stream')
    started, owner, uncertain = time.monotonic(), None, False
    budget = limits[phase + '_seconds']
    def sample():
        if time.monotonic() - started >= budget:
            raise ValueError('Windows ' + phase + ' wall deadline exceeded')
        if _output_usage(resource_root) > limits['maximum_output_bytes']:
            raise ValueError('Windows candidate output byte bound exceeded')
        if os.fstat(stream.fileno()).st_size > limits['maximum_log_bytes']:
            raise ValueError('Windows candidate log byte bound exceeded')
        if owner is not None and not owner.closed and owner.job.active() > limits['maximum_processes']:
            raise ValueError('Windows Job process-count bound exceeded')
        if time.monotonic() - started >= budget:
            raise ValueError('Windows ' + phase + ' wall deadline exceeded during resource sampling')
    try:
        sample()
        owner = process_tree.launch(argv, cwd, stream, env=environment)
        if owner.job is None:
            raise process_tree.ProcessTreeError('Native Windows launch returned no Job Object owner')
        while owner.poll() is None:
            sample()
            time.sleep(0.05)
        code = owner.finish()  # A successful parent alone never grants completion.
        if code != 0:
            raise ValueError('Windows ' + phase + ' exited ' + str(code))
        sample()
    except BaseException as error:
        if owner is not None:
            try:
                owner.terminate(timeout=limits['cleanup_seconds'])
            except BaseException as cleanup:
                uncertain = True; _UNCERTAIN_OWNERS.append((owner, stream, resource_root))
                raise process_tree.ProcessTreeError('Windows cleanup is uncertain; retain log/output ownership: ' + str(cleanup)) from error
        elif isinstance(error, process_tree.ProcessTreeError):
            # launch() can fail after a resume with uncertain cleanup, before
            # returning an owner. Keep the caller's output lifetime explicit.
            uncertain = True; _UNCERTAIN_OWNERS.append((None, stream, resource_root))
        raise
    finally:
        if owner is not None and not uncertain:
            try:
                owner.close()
            except BaseException as error:
                _UNCERTAIN_OWNERS.append((owner, stream, resource_root))
                raise process_tree.ProcessTreeError('Windows close is uncertain; retain log/output ownership: ' + str(error)) from error
    sample()
    elapsed = time.monotonic() - started
    if elapsed >= budget:
        raise ValueError('Windows ' + phase + ' wall deadline exceeded after owned completion')
    return {'phase': phase, 'argv': list(argv), 'cwd': str(cwd), 'returncode': code,
        'process_tree_closed': True, 'wall_seconds': elapsed,
        'resource_policy': 'bounded-wall-output-log-and-job-process-count; no-memory-limit-claim'}


def _source_publication_adapter(inspection, root, handoff_sha256, replay_reference):
    """Return the actual B-loaded A issuer for this live native source subject.

    The module is code identity, not a publication qualification. Callers still
    admit original publication evidence through this exact returned issuer.
    """
    require_native_host()
    source_tool = _runtime_source_provider()
    source_tool._require_source_inspection(inspection, root, handoff_sha256, replay_reference)
    api = source_tool._native_input_reader()
    inspection.check()
    return api


def _capture_source_adapter(selection, replay_reference, *, input_qualification, deadline):
    """Acquire the actual source owner before any output or command exists.

    The caller retains this inspection outermost through all Workspace/Job/log
    joins. Neither the returned passive facts nor a plan can replace it.
    """
    require_native_host()
    source_tool = _runtime_source_provider()
    subject = selection['handoff']
    inspection = source_tool.inspect_for_handoff(subject['root'], subject['sha256'], replay_reference,
        input_qualification=input_qualification, deadline=deadline)
    try:
        api = _source_publication_adapter(inspection, subject['root'], subject['sha256'], replay_reference)
        return inspection, api, inspection.as_dict()
    except BaseException:
        try:
            inspection.close()
        except BaseException as cleanup:
            inspection.revoke()
            _UNCERTAIN_OWNERS.append((inspection, None, None))
            raise process_tree.ProcessTreeError(
                'Source bootstrap close uncertain; retain the actual inspection owner') from cleanup
        raise




"""Private source fragment for the maintained Windows prototype postimage.

This fragment is inert until explicitly integrated into that postimage. It uses
the prototype's already imported contract, PureWindowsPath, hashlib and re.
Rendering never reads files, configures CMake, or grants runtime qualification.
"""


def _render_windows_lifecycle_graph(original_graph_path, output_root):
    """Wrap the same provider graph with one private component install rule.

    The caller creates cmake/evidence through its qualified output owner before
    configure. This fresh, one-pass graph rejects an existing metadata file,
    including on automatic CMake regeneration; preserve that failed operation
    and start a fresh one rather than accept or replace existing evidence.
    CMake's actual TARGET_FILE expressions supply the target identity; this
    source does not infer a build-tree DLL spelling or install other targets.
    """
    original = contract.windows_path(original_graph_path, 'original Windows provider graph')
    output = contract.windows_path(output_root, 'private Windows lifecycle output')
    if not original.endswith('/cmake/native-provider.cmake'):
        raise ValueError('Windows lifecycle requires the exact retained native-provider.cmake graph')
    if (PureWindowsPath(original) == PureWindowsPath(output) or
            PureWindowsPath(output) in PureWindowsPath(original).parents or
            PureWindowsPath(original) in PureWindowsPath(output).parents):
        raise ValueError('Windows lifecycle output overlaps its original provider graph')
    # contract.windows_path rejects CMake expansion/list/quote syntax. A bracket
    # terminator is not part of that path policy; reject it for this literal form.
    if any(']]' in value for value in (original, output)):
        raise ValueError('Windows lifecycle path cannot terminate a CMake literal')
    generated = output + '/cmake/evidence/provider-target.json'
    return ('''# Private Windows prototype lifecycle; the retained graph remains the owner.
cmake_minimum_required(VERSION 3.24)
if(NOT CMAKE_HOST_SYSTEM_NAME STREQUAL "Windows" OR
        NOT CMAKE_SYSTEM_NAME STREQUAL "Windows" OR NOT WIN32 OR EMSCRIPTEN OR
        NOT MSVC OR NOT COMPILER_IS_CLANG_CL OR
        NOT CMAKE_CXX_COMPILER_FRONTEND_VARIANT STREQUAL "MSVC" OR
        NOT WTF_CPU_X86_64 OR WTF_CPU_ARM64 OR NOT CMAKE_SIZEOF_VOID_P EQUAL 8)
    message(FATAL_ERROR "Private Windows lifecycle requires the same native Windows x64 clang-cl engine graph")
endif()
if(NOT PORT STREQUAL "Foundation" OR NOT CMAKE_GENERATOR STREQUAL "Ninja" OR
        NOT CMAKE_BUILD_TYPE STREQUAL "Release" OR
        NOT CMAKE_MSVC_RUNTIME_LIBRARY STREQUAL "MultiThreaded")
    message(FATAL_ERROR "Private Windows lifecycle requires PORT=Foundation Release and explicit static /MT")
endif()
include([[@ORIGINAL_GRAPH@]])
if(NOT TARGET BibNativeProvider)
    message(FATAL_ERROR "The retained common graph did not create BibNativeProvider")
endif()
get_target_property(_bib_lifecycle_type BibNativeProvider TYPE)
get_target_property(_bib_lifecycle_imported BibNativeProvider IMPORTED)
get_target_property(_bib_lifecycle_alias BibNativeProvider ALIASED_TARGET)
get_target_property(_bib_lifecycle_crt BibNativeProvider MSVC_RUNTIME_LIBRARY)
if(_bib_lifecycle_imported OR _bib_lifecycle_alias OR
        NOT _bib_lifecycle_type STREQUAL "SHARED_LIBRARY" OR
        NOT _bib_lifecycle_crt STREQUAL "MultiThreaded")
    message(FATAL_ERROR "Private lifecycle requires the actual shared provider target with static /MT")
endif()
file(REAL_PATH "${CMAKE_BINARY_DIR}" _bib_lifecycle_actual_build)
file(REAL_PATH [[@EXPECTED_BUILD@]] _bib_lifecycle_expected_build)
if(NOT _bib_lifecycle_actual_build STREQUAL _bib_lifecycle_expected_build OR
        NOT IS_DIRECTORY [[@EVIDENCE_PARENT@]])
    message(FATAL_ERROR "Private lifecycle metadata requires the explicit owned engine build/evidence directory")
endif()
if(EXISTS [[@TARGET_METADATA@]] OR IS_SYMLINK [[@TARGET_METADATA@]])
    message(FATAL_ERROR "Private lifecycle refuses an existing provider target metadata destination")
endif()
file(GENERATE OUTPUT [[@TARGET_METADATA@]] CONTENT [=[{
  "schema_version": 1,
  "kind": "foundation-windows-provider-target-v1",
  "scope": "actual-cmake-provider-target-identity-only",
  "target": "BibNativeProvider",
  "configuration": "$<CONFIG>",
  "file": "$<TARGET_FILE:BibNativeProvider>",
  "filename": "$<TARGET_FILE_NAME:BibNativeProvider>",
  "production_eligible": false,
  "native_runtime_qualified": false,
  "engine_execution": false,
  "kernel_rebuild": false
}
]=])
# Only this private provider DLL joins the selected component. Supplier default
# install rules and SDK/package publication are outside this component.
install(TARGETS BibNativeProvider
    RUNTIME DESTINATION bin COMPONENT FoundationNativePrototype)
'''.replace('@ORIGINAL_GRAPH@', original)
        .replace('@EXPECTED_BUILD@', output + '/cmake')
        .replace('@EVIDENCE_PARENT@', output + '/cmake/evidence')
        .replace('@TARGET_METADATA@', generated)).encode('ascii')


"""Pure Windows compile-policy readback fragment; no instruction-floor proof."""


def _inspect_windows_compile_policy(raw_compile_commands, raw_cache, *, compiler,
                                    build_root, assembled_root):
    """Check bounded CMake evidence, never execute a command or read its inputs.

    Requires the caller's anchored, post-configure complete byte captures. The
    receipt binds those bytes; it does not prove the compiler ran or establish
    an instruction floor, correct optimized dispatch, or runtime qualification.
    """
    import json

    def path(value, label):
        if type(value) is not str or len(value) > 4096:
            raise ValueError('Bounded Windows compile evidence path required: ' + label)
        return contract.windows_path(PureWindowsPath(value).as_posix(), label)

    selected_compiler = path(compiler, 'admitted compile-policy compiler')
    build = path(build_root, 'owned compile-policy build root')
    assembled = path(assembled_root, 'assembled compile-policy source root')
    if (PureWindowsPath(build) == PureWindowsPath(assembled) or
            PureWindowsPath(build) in PureWindowsPath(assembled).parents or
            PureWindowsPath(assembled) in PureWindowsPath(build).parents):
        raise ValueError('Compile-policy source and output roots must be disjoint')

    def bounded_text(raw, maximum, label):
        if type(raw) is not bytes or not raw or len(raw) > maximum:
            raise ValueError('Bounded actual Windows ' + label + ' bytes required')
        try:
            value = raw.decode('utf-8')
            value.encode('utf-8')
        except UnicodeError as error:
            raise ValueError('Invalid UTF-8 Windows ' + label) from error
        if '\x00' in value:
            raise ValueError('NUL in Windows ' + label)
        return value

    def argument(value):
        if (type(value) is not str or not value or len(value) > 32768 or
                any(ord(char) < 32 or ord(char) == 127 for char in value)):
            raise ValueError('Invalid bounded Windows compile argument')
        value.encode('utf-8')
        return value

    def windows_argv(command):
        # The Windows CRT quoting rules, including backslashes before a quote.
        # This is value parsing only; no shell, CommandLineToArgvW or launch.
        argument(command)
        if len(command) > 1024 * 1024:
            raise ValueError('Windows compile command exceeds its byte bound')
        result, offset, length = [], 0, len(command)
        while offset < length:
            while offset < length and command[offset] in ' \t': offset += 1
            if offset == length: break
            token, quoted = [], False
            while offset < length:
                if not quoted and command[offset] in ' \t': break
                slashes = 0
                while offset < length and command[offset] == '\\':
                    slashes += 1; offset += 1
                if offset < length and command[offset] == '"':
                    token.append('\\' * (slashes // 2))
                    if slashes % 2:
                        token.append('"'); offset += 1
                    elif quoted and offset + 1 < length and command[offset + 1] == '"':
                        token.append('"'); offset += 2
                    else:
                        quoted = not quoted; offset += 1
                else:
                    token.append('\\' * slashes)
                    if offset == length or not quoted and command[offset] in ' \t': break
                    token.append(command[offset]); offset += 1
            if quoted:
                raise ValueError('Unterminated quoted Windows compile argument')
            result.append(argument(''.join(token)))
            if len(result) > 32768:
                raise ValueError('Windows compile argument-count bound exceeded')
        if not result:
            raise ValueError('Empty Windows compile command')
        return result

    def forwarded(value):
        return value[7:] if value.lower().startswith('/clang:') else value

    def cpu_flags(arguments):
        # This is intentionally narrower than all compiler options. New opaque
        # forwarding/response mechanisms need explicit readback support first.
        result = []
        for index, original in enumerate(arguments):
            token = forwarded(original)
            lower = token.lower()
            if (token.startswith('@') or lower in ('-xclang', '/xclang', '-mllvm', '/fallback', '/link') or
                    lower.startswith(('-target-cpu', '-target-feature', '/clang:',
                                      '-xclang=', '/xclang=', '-mllvm=',
                                      '--config', '-xarch', '--dependent-lib='))):
                raise ValueError('Opaque Windows compiler CPU/response forwarding is unsupported')
            if token in ('&', '&&', '|', '||', '<', '>'):
                raise ValueError('Shell syntax is unsupported in direct Windows compile evidence')
            if re.fullmatch(r'[/-]m[td]d?', token, re.I):
                if token not in ('/MT', '-MT'):
                    raise ValueError('Windows compile evidence selects dynamic or debug CRT')
                continue
            if lower.startswith('-fms-runtime-lib=') and lower != '-fms-runtime-lib=static':
                raise ValueError('Windows compile evidence overrides its static Release CRT')
            if re.fullmatch(r'[/-]D(?:_DLL|_DEBUG|_MT)(?:=.*)?', token):
                raise ValueError('Windows compile evidence overrides static Release CRT macros')
            if (token in ('/D', '-D') and index + 1 < len(arguments) and
                    re.fullmatch(r'(?:_DLL|_DEBUG|_MT)(?:=.*)?', forwarded(arguments[index + 1]))):
                raise ValueError('Windows compile evidence overrides split static Release CRT macros')
            if (re.fullmatch(r'[/-]U_MT', token) or
                    token in ('/U', '-U') and index + 1 < len(arguments) and
                    forwarded(arguments[index + 1]) == '_MT'):
                raise ValueError('Windows compile evidence undefines its static CRT macro')
            if lower in ('-mno-sse', '-mno-sse2'):
                raise ValueError('Windows compile evidence disables its explicit SSE2 baseline')
            if lower.startswith('/arch:'):
                if lower != '/arch:sse2': result.append(lower)
            elif lower.startswith(('-march=', '-mcpu=', '-mtune=', '-target-cpu', '-target-feature')):
                result.append(lower)
            elif lower.startswith('-m') and lower not in ('-msse2', '-m64') and not lower.startswith('-mno-'):
                result.append(lower)
        return result

    def pairs(items):
        value = {}
        for key, child in items:
            if key in value: raise ValueError('Duplicate Windows compile JSON field: ' + key)
            value[key] = child
        return value

    def nonfinite(value):
        raise ValueError('Nonfinite Windows compile JSON value: ' + value)

    cache_text = bounded_text(raw_cache, 16 * 1024 * 1024, 'CMakeCache')
    cache = {}
    for line in cache_text.splitlines():
        if not line or line.startswith(('#', '//')): continue
        match = re.fullmatch(r'([^:=\r\n]+):([^=\r\n]+)=(.*)', line)
        if match is None or len(match[1]) > 1024 or match[1] in cache:
            raise ValueError('Malformed or duplicate Windows CMakeCache field')
        cache[match[1]] = match[3]
    required = {'CMAKE_BUILD_TYPE': 'Release', 'CMAKE_MSVC_RUNTIME_LIBRARY': 'MultiThreaded',
        'CMAKE_CXX_STANDARD': '23', 'CMAKE_GENERATOR': 'Ninja',
        'CMAKE_EXPORT_COMPILE_COMMANDS': 'ON'}
    for name, wanted in required.items():
        if cache.get(name) != wanted:
            raise ValueError('Windows compile-policy cache differs: ' + name)
    for name in ('CMAKE_C_COMPILER', 'CMAKE_CXX_COMPILER'):
        if PureWindowsPath(path(cache.get(name), name)) != PureWindowsPath(selected_compiler):
            raise ValueError('Windows compile-policy cache compiler differs')
    for name, wanted in (('CMAKE_CACHEFILE_DIR', build),
                         ('CMAKE_HOME_DIRECTORY', assembled + '/source/engine')):
        if PureWindowsPath(path(cache.get(name), name)) != PureWindowsPath(wanted):
            raise ValueError('Windows compile-policy cache root differs: ' + name)
    for name, value in cache.items():
        if re.fullmatch(r'CMAKE_(C|CXX)_FLAGS(?:_(?:RELEASE|DEBUG|RELWITHDEBINFO|MINSIZEREL))?', name):
            if value and cpu_flags(windows_argv(value)):
                raise ValueError('Windows CMakeCache raises the global CPU baseline: ' + name)

    commands_text = bounded_text(raw_compile_commands, 64 * 1024 * 1024, 'compile_commands')
    try:
        commands = json.loads(commands_text, object_pairs_hook=pairs, parse_constant=nonfinite)
    except (UnicodeError, RecursionError, OverflowError) as error:
        raise ValueError('Invalid Windows compile JSON encoding or nesting') from error
    if type(commands) is not list or not 1 <= len(commands) <= 65536:
        raise ValueError('Windows compile evidence requires a bounded nonempty command array')
    dispatch_prefix = assembled + '/source/engine/Source/ThirdParty/skia/'
    dispatch = {
        'src/opts/SkOpts_hsw.cpp': {'-march=haswell'},
        'src/opts/SkOpts_skx.cpp': {'-march=skylake-avx512'},
        'modules/skcms/src/skcms_TransformHsw.cc': {'-mf16c', '-mavx2'},
        'modules/skcms/src/skcms_TransformSkx.cc': {
            '-mavx512f', '-mavx512dq', '-mavx512cd', '-mavx512bw', '-mavx512vl'},
    }
    dispatched, ordinary = [], 0
    for entry in commands:
        if (type(entry) is not dict or not {'directory', 'file'} <= set(entry) or
                set(entry) - {'directory', 'file', 'command', 'arguments', 'output'} or
                ('command' in entry) == ('arguments' in entry)):
            raise ValueError('Unsupported Windows compile-command entry fields')
        directory, source = path(entry['directory'], 'compile directory'), path(entry['file'], 'compile source')
        if (PureWindowsPath(directory) != PureWindowsPath(build) and
                PureWindowsPath(build) not in PureWindowsPath(directory).parents):
            raise ValueError('Windows compile command escapes its owned build tree')
        if not any(PureWindowsPath(root) in PureWindowsPath(source).parents for root in (assembled, build)):
            raise ValueError('Windows compile source escapes assembled/generated roots')
        if 'output' in entry:
            argument(entry['output'])
        if 'arguments' in entry:
            if type(entry['arguments']) is not list or not 1 <= len(entry['arguments']) <= 32768:
                raise ValueError('Bounded Windows compile arguments array required')
            argv = [argument(token) for token in entry['arguments']]
        else:
            argv = windows_argv(entry['command'])
        if PureWindowsPath(path(argv[0], 'actual compile executable')) != PureWindowsPath(selected_compiler):
            raise ValueError('Windows compile command does not use its admitted clang-cl directly')
        options = [forwarded(token) for token in argv[1:]]
        if not any(token in ('/MT', '-MT') for token in options):
            raise ValueError('Actual Windows compile command lacks explicit static Release CRT')
        if '-msse2' not in options:
            raise ValueError('Actual Windows compile command lacks its explicit SSE2 baseline')
        targets = []
        for index, token in enumerate(options):
            if token.startswith('--target='): targets.append(token.split('=', 1)[1])
            elif token in ('-target', '--target'):
                if index + 1 == len(options): raise ValueError('Incomplete Windows compiler target option')
                targets.append(options[index + 1])
        if not targets or any(target != 'x86_64-pc-windows-msvc' for target in targets):
            raise ValueError('Actual Windows compile command lacks its exact native x64 target')
        advanced = cpu_flags(argv[1:])
        if advanced:
            relative = next((name for name in dispatch if PureWindowsPath(source) ==
                             PureWindowsPath(dispatch_prefix + name)), None)
            if relative is None or not set(advanced) <= dispatch[relative]:
                raise ValueError('Windows compile command raises an unadmitted source CPU baseline')
            dispatched.append({'file': source, 'cpu_flags': advanced})
        else:
            ordinary += 1
    return {'schema_version': 1, 'kind': 'foundation-windows-compile-policy-readback-v1',
        'scope': 'actual-configured-command-policy-readback-only',
        'compile_commands_sha256': hashlib.sha256(raw_compile_commands).hexdigest(),
        'cmake_cache_sha256': hashlib.sha256(raw_cache).hexdigest(),
        'compiler': selected_compiler, 'build_root': build, 'assembled_root': assembled,
        'commands': len(commands), 'ordinary_commands': ordinary,
        'explicit_dispatched_commands': dispatched,
        'static_release_crt_command_policy': True, 'x64_target_command_policy': True,
        'sse2_baseline_command_policy': True, 'instruction_floor_verified': False,
        'missing_data': [{'role': 'windows-cpu-floor-original-evidence', 'path': build,
            'reason': 'command-policy readback does not establish emitted instruction floor or correct optimized-leaf dispatch; original CPU-floor evidence is required'}],
        'production_eligible': False, 'native_runtime_qualified': False,
        'engine_execution': False, 'kernel_rebuild': False}


# Private integration fragment; globals are supplied by the maintained prototype.
# It contains no independent launcher, generated engine, or public authority seam.
LIFECYCLE_KIND = 'foundation-native-engine-windows-prototype-build-v1'
LIFECYCLE_PHASES = ('configure', 'build', 'install', 'probe')


def _lifecycle_deadline(limits, started, deadline=None):
    import math
    limits = validate_limits(limits)
    # Install/probe, if a maintained graph is supplied later, each receive no
    # more than the selected configure budget. No per-phase reset extends this.
    allowance = (limits['build_seconds'] + 3 * limits['configure_seconds'] +
                 4 * limits['cleanup_seconds'] + 120)
    ceiling = started + min(86400, allowance)
    if deadline is None:
        return ceiling
    if (type(deadline) not in (int, float) or not math.isfinite(deadline) or
            not started < deadline <= ceiling):
        raise ValueError('Finite initial Windows operation deadline within selected budgets required')
    return deadline


def _lifecycle_time(deadline):
    import math
    if (type(deadline) not in (int, float) or not math.isfinite(deadline) or
            time.monotonic() >= deadline):
        raise ValueError('Initial Windows operation deadline expired')


def _lifecycle_declaration(command, environment):
    contract.fields(command, ('phase', 'argv', 'cwd'), 'Windows prototype phase command')
    if command['phase'] not in LIFECYCLE_PHASES:
        raise ValueError('Unknown finite Windows prototype phase')
    argv = command['argv']
    if (type(argv) is not list or not 1 <= len(argv) <= 128 or
            any(type(item) is not str or not item or len(item) > 4096 or
                any(ord(char) < 32 for char in item) and item != _STATIC_PROBE_BOOTSTRAP
                for item in argv)):
        raise ValueError('Bounded literal Windows prototype arguments required')
    contract.windows_path(argv[0], 'Windows prototype executable')
    contract.windows_path(command['cwd'], 'Windows prototype working directory')
    if (type(environment) is not dict or not environment or len(environment) > 64 or
            any(type(key) is not str or not key or type(value) is not str or
                len(key) + len(value) > 32768 or '\0' in key + value
                for key, value in environment.items())):
        raise ValueError('Explicit bounded Windows prototype environment required')
    return copy.deepcopy(command)


def _run_workspace_stage(workspace, command, environment, limits, inspection, *, deadline):
    """Use the exact Workspace-owned log and its sole actual Job launcher.

    This private routine receives only the graph assembled by build. Workspace
    itself issues the joined object and performs finish/close; no serialized
    receipt, external callback or caller-supplied owner establishes completion.
    """
    command = _lifecycle_declaration(command, environment)
    limits = validate_limits(limits)
    phase = command['phase']
    budget = limits['build_seconds' if phase == 'build' else 'configure_seconds']
    started = time.monotonic()
    phase_deadline = min(deadline, started + budget)
    owner = joined = log = None
    join_attempted = seal_attempted = sealed = False
    peak_processes = peak_bytes = 0
    pinned_log = None

    def sample():
        nonlocal peak_processes, peak_bytes
        _lifecycle_time(phase_deadline)
        inspection.check()
        workspace.check_anchors()
        usage = workspace.usage(log=log) if log is not None else workspace.usage()
        if (type(usage) is not dict or type(usage.get('bytes')) is not int or
                usage['bytes'] < 0 or usage['bytes'] > limits['maximum_output_bytes'] or
                log is not None and (type(usage.get('log_bytes')) is not int or
                    not 0 <= usage['log_bytes'] <= limits['maximum_log_bytes'])):
            raise ValueError('Windows prototype output/log bound exceeded')
        peak_bytes = max(peak_bytes, usage['bytes'])
        if owner is not None:
            count = owner.job.active()
            if type(count) is not int or not 0 <= count <= limits['maximum_processes']:
                raise ValueError('Windows prototype observed Job process bound exceeded')
            peak_processes = max(peak_processes, count)
        _lifecycle_time(phase_deadline)

    try:
        sample()
        # This immutable launch intent is visible before the first child writer.
        workspace.publish_bytes_new('evidence/' + phase + '-intent.json', encoded({
            'command': command, 'environment': copy.deepcopy(environment),
            'initial_deadline': deadline, 'phase_deadline': phase_deadline}))
        log = workspace.open_log_new('logs/' + phase + '.log')
        workspace.mark_running(log)
        owner = workspace.launch(log, command['argv'], command['cwd'], env=environment,
            maximum_active_processes=limits['maximum_processes'])
        if owner.job is None:
            raise process_tree.ProcessTreeError('Windows prototype launch has no actual Job owner')
        while owner.poll() is None:
            sample()
            time.sleep(min(0.05, max(0.0, phase_deadline - time.monotonic())))
        sample()
        join_attempted = True
        joined = workspace.mark_joined(log, command)
        observed = joined.as_dict()
        seal_attempted = True
        pinned_log = workspace.seal_log(log)
        sealed = True
        if (observed.get('returncode') != 0 or observed.get('process_tree_closed') is not True or
                observed.get('closure') != 'actual-bound-job-finish-and-close'):
            raise ValueError('Windows prototype phase did not complete under its actual bound Job')
        inspection.check()
        inventory = workspace.inspect_outputs()
        peak_bytes = max(peak_bytes, inventory['bytes'])
        if peak_bytes > limits['maximum_output_bytes']:
            raise ValueError('Windows prototype output bound exceeded after Job closure')
        _lifecycle_time(phase_deadline)
        receipt = dict(command, returncode=observed['returncode'], process_tree_closed=True,
            closure=observed['closure'], log=copy.deepcopy(pinned_log),
            log_identity=copy.deepcopy(log.identity),
            wall_seconds=time.monotonic() - started,
            initial_deadline=deadline, phase_deadline=phase_deadline,
            maximum_observed_processes=peak_processes,
            process_limit_enforced=True, peak_output_bytes=peak_bytes,
            output_subject_sha256=digest(encoded(inventory)))
        workspace.publish_bytes_new('evidence/' + phase + '-result.json', encoded(receipt))
        return joined, receipt
    except BaseException as error:
        # Once join/seal outcome is uncertain, do not repeat it or issue a save.
        if (join_attempted and joined is None) or (seal_attempted and not sealed):
            workspace.retain_uncertain(owner, log, str(error))
            raise
        try:
            if owner is not None and joined is None:
                owner.terminate(timeout=min(limits['cleanup_seconds'],
                    max(0.001, deadline - time.monotonic())))
                join_attempted = True
                joined = workspace.mark_joined(log, command)
            if joined is not None:
                failed = workspace.mark_failed_joined(joined, str(error))
                if not sealed:
                    seal_attempted = True
                    pinned_log = workspace.seal_log(log)
                    sealed = True
                error.native_stage_receipt = dict(failed, log=copy.deepcopy(pinned_log),
                    initial_deadline=deadline, phase_deadline=phase_deadline)
            elif log is not None:
                # A launch can fail after child creation without returning owner.
                workspace.retain_uncertain(owner, log, str(error))
        except BaseException as cleanup:
            workspace.retain_uncertain(owner, log, str(error) + '; cleanup: ' + str(cleanup))
        raise


def _publication_source_root(api, repository_root=None):
    """Use the actual source filename after the B-owned adapter handoff.

    This derives a path from an already authenticated A; it does not admit an
    unknown module. A uses the same resolved filename root for its input subject
    and Workspace source recheck. Recipe and static-inspector roots stay separate.
    """
    filename = getattr(api, '__file__', None)
    if type(filename) is not str:
        raise ValueError('Actual Windows publication source filename is absent')
    source = _ordinary(Path(filename))
    if source.name != 'appended_engine_windows_publication.py' or source.parent.name != 'tools':
        raise ValueError('Actual Windows publication source has a different logical filename')
    root = source.resolve().parents[1]
    if repository_root is not None and Path(repository_root).resolve() != root:
        raise ValueError('Explicit publication source root differs from the actual B-issued A filename')
    return root


def _hold_lifecycle_sources(api, held, repository_root):
    """Keep project helper and actual native subject observations distinct."""
    project = {}
    native = {}
    native_root = _publication_source_root(api)
    for root, names, result in (
            (Path(repository_root), _prototype_helper_closure(Path(repository_root)), project),
            (native_root, sorted(set(api.SOURCE_FILES) | set(api.INPUT_SOURCE_FILES)), native)):
        for name in names:
            raw = _read(root / name)
            reference = {'path': PureWindowsPath(os.fspath(root / name)).as_posix(),
                         'sha256': digest(raw)}
            if held.reference(reference) != raw:
                raise ValueError('Held Windows lifecycle helper/subject source changed')
            result[name] = reference['sha256']
    return project, {'root': PureWindowsPath(os.fspath(native_root)).as_posix(), 'sources': native}


def _publication_qualification(api, reference, *, repository_root=None):
    if reference is None:
        raise contract.MissingInputs([_missing('windows-publication-qualification',
            'original native Windows publication evidence',
            'complete original publication cases and actual source/runtime subject are required')])
    _reference(reference, 'native Windows publication qualification')
    # Source reader and publication qualifications have DIFFERENT diagnostic
    # subjects. Observe the publication set directly; do not copy report claims.
    source_root = _publication_source_root(api, repository_root)
    sources = {name: digest(_read(source_root / name)) for name in api.SOURCE_FILES}
    if sources.get('tools/appended_engine_windows_contract.py') != api.CONTRACT_SHA256:
        raise contract.MissingInputs([_missing('windows-publication-source-baseline',
            'tools/appended_engine_windows_publication.py',
            'publication and current Windows contract sources require a coherent source join before original qualification')])
    actual = api.inspect_input_subject()
    if any(actual['source_identity'].get(name) != sources[name]
           for name in set(api.SOURCE_FILES) & set(api.INPUT_SOURCE_FILES)):
        raise ValueError('Actual publication/input source subjects differ on their shared files')
    return api.admit_qualification(reference, source_identity=sources,
                                  runtime_identity=actual['runtime_identity'])


def _retain_lifecycle_graph(inspection, workspace, resources, error):
    if inspection is not None:
        inspection.revoke()
    if workspace is not None and not workspace.closed:
        workspace.retain_uncertain(None, None, str(error))
    _UNCERTAIN_OWNERS.append((inspection, workspace, tuple(resources), str(error)))


def _close_lifecycle_graph(inspection, workspace, resources):
    """Source inspection is always outermost; uncertainty retains every owner."""
    try:
        if workspace is not None and not workspace.closed:
            workspace.close_joined()
        for resource in reversed(resources):
            resource.close()
        if inspection is not None:
            inspection.close()
    except BaseException as error:
        _retain_lifecycle_graph(inspection, workspace, resources, error)
        raise process_tree.ProcessTreeError(
            'Windows lifecycle close is uncertain; retain actual source, Job, log and output graph: ' + str(error)) from error


def _lifecycle_json(raw):
    import json
    if type(raw) is not bytes or len(raw) > MAX_DOCUMENT:
        raise ValueError('Bounded Windows lifecycle metadata bytes required')
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate Windows lifecycle metadata field: ' + key)
            result[key] = value
        return result
    def invalid(value):
        raise ValueError('Nonfinite Windows lifecycle metadata: ' + value)
    value = json.loads(raw.decode('utf-8'), object_pairs_hook=pairs, parse_constant=invalid)
    encoded(value)
    return value


def _lifecycle_input_limits(deadline):
    import math
    _lifecycle_time(deadline)
    return {'seconds': min(86400, max(1, int(math.ceil(deadline - time.monotonic())))),
        'maximum_archive_bytes': 8 * 1024 ** 3, 'maximum_expanded_bytes': 32 * 1024 ** 3,
        'maximum_members': 1000000, 'maximum_member_bytes': 256 * 1024 ** 2,
        'maximum_patch_bytes': 32 * 1024 ** 2}


class _HeldLifecycleInputs:
    """Keep actual admitted metadata and complete tool/product trees read-only."""
    def __init__(self, api, qualification, deadline):
        self.api, self.qualification, self.deadline = api, qualification, deadline
        self.owners, self.roots, self.trees = [], {}, []
        self.closed, self.uncertain = False, False

    def _root(self, root):
        if type(root) is str and re.fullmatch(r'[A-Z]:/', root):
            raise contract.MissingInputs([_missing('windows-native-metadata-containing-directory',
                root, 'retained authority metadata must have an explicit ordinary containing directory below the local drive root; the qualified reader does not capture drive-root containers')])
        root = contract.windows_path(root, 'Windows lifecycle input root')
        if root not in self.roots:
            try:
                owner = self.api.AnchoredInputs.open_existing(root,
                    qualification=self.qualification, limits=_lifecycle_input_limits(self.deadline),
                    deadline=self.deadline)
            except BaseException:
                # The native opener retains any concealed handle itself. With
                # no returned owner, preserve the enclosing graph as well.
                self.uncertain = True
                raise
            self.owners.append(owner)
            self.roots[root] = owner
        return self.roots[root]

    def reference(self, reference, *, maximum=MAX_DOCUMENT):
        path, pin = _reference(reference, 'held Windows lifecycle reference')
        selected = PureWindowsPath(path)
        owner = self._root(selected.parent.as_posix())
        return owner.read(selected.name, expected={'sha256': pin, 'mode': 0o644},
                          maximum=maximum)

    def inventory(self, reference, role):
        raw = self.reference(reference)
        value = _lifecycle_json(raw)
        if type(value) is not dict or 'provenance' not in value:
            raise ValueError('Original complete inventory provenance reference required')
        provenance_ref = value['provenance']
        _reference(provenance_ref, 'held complete inventory provenance')
        provenance_raw = self.reference(provenance_ref)
        declare = _shared_dependency_api('inventory_declaration')
        declaration = declare(raw, reference['sha256'], role,
            provenance_raw=provenance_raw, provenance_pin=provenance_ref['sha256'])
        contract.fields(declaration, ('root', 'version', 'files', 'directories',
            'subject_sha256', 'provenance', 'original_refs'), 'shared inventory declaration')
        # The common parser owns supported metadata versions, provenance and
        # finite declarations. A independently captures complete physical trees.
        declared = {name: dict(row, mode=0o644)
                    for name, row in declaration['files'].items()}
        owner = self._root(declaration['root'])
        tree = owner.capture_tree('', files=declared,
                                  directories=declaration['directories'])
        self.trees.append(tree)
        for name, row in sorted(declared.items()):
            stream, hashed, count = tree.open_file(name), hashlib.sha256(), 0
            try:
                while count < row['bytes']:
                    _lifecycle_time(self.deadline)
                    block = stream.read(min(1024 * 1024, row['bytes'] - count))
                    if type(block) is not bytes or not block:
                        raise ValueError('Held Windows inventory leaf ended before declared EOF')
                    count += len(block); hashed.update(block)
                if stream.read(1) or count != row['bytes'] or hashed.hexdigest() != row['sha256']:
                    raise ValueError('Held Windows inventory leaf differs from original pin/EOF')
            finally:
                stream.close()  # borrowed view; actual read-only handle stays held
        for original in declaration['original_refs']:
            self.reference(original, maximum=MAX_BINARY)
        self.check()
        return value

    def check(self):
        if self.closed:
            raise ValueError('Held Windows lifecycle inputs are closed')
        _lifecycle_time(self.deadline)
        for owner in self.owners:
            owner.check()
        _lifecycle_time(self.deadline)

    def close(self):
        if self.closed:
            raise ValueError('Held Windows lifecycle inputs already closed')
        for owner in reversed(self.owners):
            owner.close()
        self.closed = True


def _held_output_bytes(api, qualification, workspace, relative, row, resources, *, deadline,
                       maximum=MAX_DOCUMENT):
    _relative(relative)
    contract.fields(row, ('path', 'kind', 'bytes', 'sha256'), 'actual Windows output row')
    if row['path'] != relative or row['kind'] != 'file' or not 0 <= row['bytes'] <= maximum:
        raise ValueError('Actual Windows output row differs from selected ordinary file')
    held = _HeldLifecycleInputs(api, qualification, deadline)
    resources.append(held)  # own before a fallible native open/capture
    raw = held.reference({'path': workspace.output + '/' + relative, 'sha256': row['sha256']},
                         maximum=maximum)
    if len(raw) != row['bytes']:
        raise ValueError('Held Windows output EOF differs from actual Workspace inspection')
    held.check()
    workspace.check_anchors()
    return raw


def _require_dependency_admission(value, admitted, handoff, held, admission_value=None, *, retained=False):
    if value is None:
        raise contract.MissingInputs([_missing('windows-original-dependency-admission',
            admitted['native_inputs']['dependency_prefix'],
            'an actual same-process issued dependency D/W/H admission is required; raw pinned refs or status metadata cannot issue it')])
    dependencies = _dependency_entry()
    require = getattr(dependencies, 'require_retained_dependency_with_probe' if retained
        else 'require_dependency_with_probe', None)
    if not callable(require):
        raise contract.MissingInputs([_missing('windows-original-dependency-admission-issuer',
            'tools/appended_engine_windows_dependencies.py',
            'the genuine original D/W/native-H issuer must be integrated before this actual token can be checked')])
    observed = require(value)
    if type(observed) is not dict or type(observed.get('references')) is not dict:
        raise ValueError('Actual original dependency issuer result required')
    inventory_ref = observed['references'].get('inventory')
    native_ref = observed['references'].get('native_inputs')
    for row in (inventory_ref, native_ref):
        contract.fields(row, ('path', 'sha256', 'bytes'), 'original dependency published reference')
        _integer(row['bytes'], 'original dependency published bytes', 0, MAX_DOCUMENT)
        _reference({name: row[name] for name in ('path', 'sha256')}, 'original dependency published reference')
    if ({name: inventory_ref[name] for name in ('path', 'sha256')} !=
            admitted['native_inputs']['dependency_inventory']):
        raise ValueError('Original dependency admission does not join current held dependency inventory')
    # The issuer's additional exact H/native-input joins are required below; this
    # does not reconstruct H by copying independent version declarations.
    if observed.get('toolchain_identity_sha256') != handoff['toolchain_identity_sha256']:
        raise ValueError('Original dependency admission H differs from immutable source handoff')
    native_raw = held.reference({name: native_ref[name] for name in ('path', 'sha256')})
    if len(native_raw) != native_ref['bytes']:
        raise ValueError('Original dependency native-input EOF differs')
    original_native = _lifecycle_json(native_raw)
    if original_native != admitted['native_inputs']:
        raise ValueError('Original dependency admission differs from exact selected native inputs')
    original_identity = observed.get('toolchain_identity')
    _reference(original_identity, 'original issued dependency H')
    if original_identity['sha256'] != observed['toolchain_identity_sha256']:
        raise ValueError('Original dependency H reference differs from executed D binding')
    identity_raw = held.reference(original_identity)
    validate_identity = _shared_dependency_api('validate_toolchain_identity')
    identity = validate_identity(identity_raw, observed['toolchain_identity_sha256'])
    if admission_value is None:
        raise ValueError('Complete held native admission is required for original H join')
    # Join the complete original H1/H2 role map before creating any engine-use
    # view. H2 nmake/msbuild declarations must match the same actual original H
    # even though this consumer's engine commands do not invoke those tools.
    contract.fields(admission_value.get('programs'), identity['programs'],
                    'complete current programs against original H1/H2')
    contract.fields(admission_value.get('program_versions'), identity['programs'],
                    'complete current program versions against original H1/H2')
    for role in identity['programs']:
        expected_program = dict(admission_value['programs'][role],
            version=admission_value['program_versions'][role])
        if identity['programs'][role] != expected_program:
            raise ValueError('Current held program/version differs from actual original H: ' + role)
    for category in ('builtins', 'crt_libraries', 'include_directories',
                     'library_directories', 'system_root'):
        if identity[category] != admission_value[category]:
            raise ValueError('Current held admission differs from actual original H: ' + category)
    for role, subject in identity['inventories'].items():
        inventory = _lifecycle_json(held.reference(admission_value['inventories'][role]))
        expected = {'root': inventory['root'], 'version': inventory['version'],
                    'subject_sha256': _inventory_subject(inventory)}
        if subject != expected:
            raise ValueError('Current complete inventory differs from original H: ' + role)
    current_kind = 'foundation-windows-dependency-with-probe-and-generated-inputs-v2'
    current = observed.get('schema_version') == 2 or observed.get('kind') == current_kind
    if current and (type(observed.get('schema_version')) is not int or
            observed['schema_version'] != 2 or observed.get('kind') != current_kind):
        raise ValueError('Current original dependency result requires its exact schema2/kind2 pair')
    if not current and ('generated_input_witness' in observed or 'original_references' in observed):
        raise ValueError('Generated original dependency fields require the current closed result kind')
    names = ('dependency_receipt', 'probe_object_witness', 'result')
    if current:
        names += ('generated_input_witness',)
    for name in names:
        row = observed.get(name)
        contract.fields(row, ('path', 'sha256', 'bytes'), 'original dependency evidence row')
        _integer(row['bytes'], 'original dependency evidence bytes', 1 if current else 0, MAX_DOCUMENT)
        raw = held.reference({key: row[key] for key in ('path', 'sha256')})
        if len(raw) != row['bytes']:
            raise ValueError('Original dependency evidence EOF differs: ' + name)
    if current:
        ledger = observed.get('original_references')
        if type(ledger) is not list or not 1 <= len(ledger) <= 4096:
            raise ValueError('Current dependency admission requires its complete finite original-reference ledger')
        paths = set()
        total = 0
        for row in ledger:
            contract.fields(row, ('path', 'sha256', 'bytes'), 'original dependency ledger body')
            path, _pin = _reference({key: row[key] for key in ('path', 'sha256')},
                                     'original dependency ledger body')
            _integer(row['bytes'], 'original dependency ledger body bytes', 0, 256 * 1024 * 1024)
            if path.casefold() in paths:
                raise ValueError('Original dependency ledger contains repeated or aliased paths')
            paths.add(path.casefold())
            total += row['bytes']
            if total > MAX_INVENTORY_BYTES:
                raise ValueError('Original dependency ledger exceeds the existing aggregate input budget')
        for row in ledger:
            raw = held.reference({key: row[key] for key in ('path', 'sha256')}, maximum=max(1, row['bytes']))
            if len(raw) != row['bytes']:
                raise ValueError('Original dependency ledger body EOF differs')
    # Preserve the complete original H1/H2 facts and pin in this consumer's
    # provenance. The engine-use11 comparison does not erase extra H2 roles.
    return dict(observed, admitted_toolchain_identity=copy.deepcopy(identity))


def _lifecycle_rendered(plan, handoff):
    output, source = plan['selection']['output_root'], plan['selection']['handoff']['root']
    old_header = _join(source, handoff['paths']['metadata_header'])
    new_header = output + '/cmake/generated/BibNativeProviderActionsMetadata.generated.h'
    old_graph = _join(source, handoff['paths']['retained']) + '/cmake/native-provider.cmake'
    new_graph = output + '/windows-native-lifecycle.cmake'
    rendered = dict(plan['rendered'])
    cache = rendered['windows-initial-cache.cmake']
    for original, replacement in ((old_header, new_header), (old_graph, new_graph)):
        if cache.count(original) != 1:
            raise ValueError('Finite Windows initial cache source token differs')
        cache = cache.replace(original, replacement)
    rendered['windows-initial-cache.cmake'] = cache
    rendered['windows-native-lifecycle.cmake'] = _render_windows_lifecycle_graph(old_graph, output).decode('ascii')
    return rendered, {'source': old_header, 'destination': new_header,
        'relative': 'cmake/generated/BibNativeProviderActionsMetadata.generated.h',
        'sha256': handoff['metadata_header_sha256']}


def _target_metadata(value, workspace):
    contract.fields(value, ('schema_version', 'kind', 'scope', 'target', 'configuration',
        'file', 'filename', *FALSE_FACTS), 'actual CMake provider target metadata')
    if (type(value['schema_version']) is not int or value['schema_version'] != 1 or
            value['kind'] != 'foundation-windows-provider-target-v1' or
            value['scope'] != 'actual-cmake-provider-target-identity-only' or
            value['target'] != 'BibNativeProvider' or value['configuration'] != 'Release' or
            value['filename'] != 'foundation-webcore-native-provider.dll' or
            any(value[name] is not False for name in FALSE_FACTS)):
        raise ValueError('Actual Windows target metadata subject differs')
    path = contract.windows_path(value['file'], 'actual CMake provider target file')
    if (not contract.inside(path, workspace.output + '/cmake') or
            PureWindowsPath(path).name != value['filename']):
        raise ValueError('Actual Windows provider target escapes its owned build tree')
    return PureWindowsPath(path).relative_to(PureWindowsPath(workspace.output)).as_posix()


def _held_probe_log(api, qualification, workspace, receipts, resources, *, deadline):
    inventory = workspace.inspect_outputs()
    selected = {name[len('logs/'):]: dict(sha256=row['sha256'],
        bytes=row['bytes'], mode=0o644) for name, row in inventory['files'].items()
        if name.startswith('logs/')}
    if set(selected) != {phase + '.log' for phase in LIFECYCLE_PHASES}:
        raise ValueError('Complete final Windows phase log inventory differs')
    held = _HeldLifecycleInputs(api, qualification, deadline)
    resources.append(held)
    root = held._root(workspace.output + '/logs')
    tree = root.capture_tree('', files=selected, directories=[])
    held.trees.append(tree)
    observed = tree.as_dict()['observed']['files']
    for receipt in receipts:
        name = receipt['phase'] + '.log'
        if observed[name]['identity'] != receipt['log_identity']:
            raise ValueError('Final original phase log physical identity changed after actual sealing')
    stream = tree.open_file('probe.log')
    try:
        if selected['probe.log']['bytes'] > MAX_DOCUMENT:
            raise ValueError('Static Windows probe output exceeds bounded JSON size')
        raw = stream.read()
    finally:
        stream.close()
    if digest(raw) != selected['probe.log']['sha256'] or len(raw) != selected['probe.log']['bytes']:
        raise ValueError('Actual sealed static Windows probe log differs from final held bytes')
    held.check()
    return raw


def _controller_lifecycle_python(admitted):
    selected = contract.windows_path(PureWindowsPath(os.fspath(sys.executable)).as_posix(),
        'actual native lifecycle controller Python')
    expected = admitted['programs']['python']
    if selected != expected or sys.version_info < (3, 9) or not sys.dont_write_bytecode:
        raise ValueError('Windows lifecycle requires its exact admitted Python3.9+ controller with bytecode disabled at startup')
    return selected


def _build_native_lifecycle(selection_path, pin, *, repository_root=ROOT, source_replay=None,
                            input_qualification=None, publication=None,
                            dependency_admission=None, dependency_reference=None, deadline=None):
    """Produce an installed static-inspected candidate; never execute its DLL."""
    require_native_host()
    entered = time.monotonic()
    selection = validate_selection(_document(selection_path, pin))
    limits = validate_limits(selection['phase_limits'])
    deadline = _lifecycle_deadline(limits, entered, deadline)
    missing = []
    for role, value in (('native-source-replay', source_replay),
                        ('windows-native-input-qualification', input_qualification),
                        ('windows-publication-qualification', publication),
                        ('windows-original-dependency-admission',
                         dependency_admission if dependency_admission is not None else dependency_reference)):
        if value is None:
            missing.append(_missing(role, selection['output_root'],
                'original complete input is required before creating any output'))
    if missing:
        raise contract.MissingInputs(missing)
    inspection = workspace = held = None
    resources, receipts, phase = [], [], 'admit'
    try:
        # Retained reconstruction owns the one fixed shared Origin/B/A loader.
        # Initialize it before the existing B import; unknown preloads still fail.
        retained_dependency = dependency_admission is None
        if retained_dependency:
            dependency_admission = _admit_retained_lifecycle_dependencies(dependency_reference,
                deadline=deadline)
        if type(input_qualification) is dict:
            source_replay_tool = _runtime_source_provider()
            input_qualification = source_replay_tool.admit_native_input_qualification(input_qualification)
        inspection, api, source_facts = _capture_source_adapter(selection, source_replay,
            input_qualification=input_qualification, deadline=deadline)
        held = _HeldLifecycleInputs(api, input_qualification, deadline)
        resources.append(held)
        actual_selection = _lifecycle_json(held.reference({'path': PureWindowsPath(
            os.fspath(selection_path)).as_posix(), 'sha256': contract.pin(pin, 'Windows selection')}))
        if actual_selection != selection:
            raise ValueError('Actual held Windows selection differs from initial selected bytes')
        admission_value = _lifecycle_json(held.reference(selection['admission']))
        contract.fields(admission_value.get('inventories'), INVENTORY_ROLES,
                        'held complete Windows inventories')
        for role in sorted(INVENTORY_ROLES):
            held.inventory(admission_value['inventories'][role], role)
        # Existing complete verifier now reads paths whose exact physical files
        # and complete memberships are held by the native input adapter.
        import appended_engine_windows_handoff as handoff_tool
        handoff = handoff_tool.verify_handoff(selection['handoff']['root'],
                                              selection['handoff']['sha256'])
        original_dependencies = _require_dependency_admission(dependency_admission,
            {'native_inputs': handoff['native_inputs']}, handoff, held,
            admission_value, retained=retained_dependency)
        # Actual full H1/H2 origin and all current complete subjects precede
        # consumption of the engine-use view. This verifier is consistency only.
        admitted = _admission(admission_value, handoff)
        admitted['admission_sha256'] = selection['admission']['sha256']
        controller = _controller_lifecycle_python(admitted)
        plan = create_plan(selection_path, pin, repository_root=repository_root)
        rendered, metadata = _lifecycle_rendered(plan, handoff)
        # Pin every source body reachable by the static-probe script. Source
        # coordination controls writers; actual read-only handles preserve its
        # exact admitted implementation throughout this operation.
        source_pins, native_subject_sources = _hold_lifecycle_sources(api, held, repository_root)
        qualification = _publication_qualification(api, publication)
        cap_sources = _lifecycle_cap_admission(api, qualification)
        protected = list(dict.fromkeys([*plan['protected_paths'],
            *(row['path'] for row in (publication, source_replay)),
            *[owner.root for owner in held.owners]]))
        inspection.check(); held.check(); _lifecycle_time(deadline)
        workspace = api.Workspace.create_new(selection['output_root'], protected_paths=protected,
            limits=limits, qualification=qualification)
        phase = 'prepare'
        for name in ('cmake', 'cmake/generated', 'cmake/evidence', 'evidence', 'logs',
                     'tmp', 'tmp/pycache', 'install', 'install/bin'):
            workspace.mkdir_new(name)
        header = _read(metadata['source'], metadata['sha256'])
        inspection.check()
        workspace.publish_bytes_new(metadata['relative'], header)
        for name, text in rendered.items():
            workspace.publish_bytes_new(name, text.encode('ascii'))
        workspace.publish_bytes_new('evidence/original-plan.json', encoded(plan))
        workspace.publish_bytes_new('evidence/lifecycle-admission.json', encoded({
            'controller_python': controller, 'source': source_facts,
            'helper_sources': source_pins, 'native_subject_sources': native_subject_sources,
            'dependencies': original_dependencies,
            'native_admission_original': copy.deepcopy(admission_value),
            'native_admission_sha256': selection['admission']['sha256'],
            'pre_resume_process_limit_sources': cap_sources,
            'metadata_transfer': metadata, 'initial_deadline': deadline,
            **{name: False for name in FALSE_FACTS}}))
        commands = copy.deepcopy(plan['commands'])
        commands.append({'phase': 'install', 'argv': [admitted['programs']['cmake'], '--install',
            workspace.output + '/cmake', '--config', 'Release', '--component',
            'FoundationNativePrototype', '--prefix', workspace.output + '/install'],
            'cwd': workspace.output})
        for command in commands:
            phase = command['phase']
            inspection.check(); held.check(); _lifecycle_time(deadline)
            _joined, receipt = _run_workspace_stage(workspace, command, plan['environment'],
                limits, inspection, deadline=deadline)
            receipts.append(receipt)
            held.check()
        inventory = workspace.inspect_outputs()
        target_raw = _held_output_bytes(api, input_qualification, workspace,
            'cmake/evidence/provider-target.json',
            inventory['files']['cmake/evidence/provider-target.json'], resources, deadline=deadline)
        target_relative = _target_metadata(_lifecycle_json(target_raw), workspace)
        installed_relative = 'install/bin/foundation-webcore-native-provider.dll'
        build_row, installed_row = inventory['files'][target_relative], inventory['files'][installed_relative]
        if any(build_row[name] != installed_row[name] for name in ('sha256', 'bytes')):
            raise ValueError('Installed Windows provider differs from actual built CMake target')
        provider_raw = _held_output_bytes(api, input_qualification, workspace,
            installed_relative, installed_row, resources, deadline=deadline, maximum=MAX_BINARY)
        provider = inspect_provider(provider_raw)
        compile_raw = _held_output_bytes(api, input_qualification, workspace,
            'cmake/compile_commands.json', inventory['files']['cmake/compile_commands.json'],
            resources, deadline=deadline)
        cache_raw = _held_output_bytes(api, input_qualification, workspace,
            'cmake/CMakeCache.txt', inventory['files']['cmake/CMakeCache.txt'], resources,
            deadline=deadline)
        cpu_policy = _inspect_windows_compile_policy(compile_raw, cache_raw,
            compiler=admitted['programs']['compiler'], build_root=workspace.output + '/cmake',
            assembled_root=_join(selection['handoff']['root'], handoff['paths']['assembled']))
        phase = 'probe'
        command = _static_probe_command(controller, admitted, repository_root,
            workspace.output, installed_row['sha256'])
        _joined, receipt = _run_workspace_stage(workspace, command, plan['environment'],
            limits, inspection, deadline=deadline)
        receipts.append(receipt)
        raw_probe = _held_probe_log(api, input_qualification, workspace, receipts,
                                   resources, deadline=deadline)
        if _lifecycle_json(raw_probe) != provider:
            raise ValueError('Actual static probe output differs from independently inspected held provider bytes')
        for resource in resources:
            resource.check()
        inspection.check(); workspace.check_anchors(); _lifecycle_time(deadline)
        final_inventory = workspace.inspect_outputs()
        result = {'schema_version': 1, 'kind': LIFECYCLE_KIND, 'scope': SCOPE,
            'status': 'installed-static-inspected-candidate', 'target': dict(contract.TARGET),
            'selection_sha256': pin, 'handoff_sha256': selection['handoff']['sha256'],
            'admission_sha256': selection['admission']['sha256'], 'metadata_transfer': metadata,
            'provider': provider, 'provider_path': workspace.output + '/' + installed_relative,
            'compile_policy': cpu_policy, 'stages': receipts,
            'output_subject_sha256': digest(encoded(final_inventory)),
            'publication_state': 'jobs-and-logs-closed-filesystem-owner-still-held',
            'next_gate': 'original native runtime, CPU-floor/dispatch evidence and complete retained SDK admission',
            **{name: False for name in FALSE_FACTS}}
        # The saved receipt describes the observed pre-close state. Only after
        # actual closure does the returned result report filesystem_owner_closed.
        row = workspace.commit_receipt_new('native-prototype-build.json', encoded(result))
        _close_lifecycle_graph(inspection, workspace, resources)
        return dict(result, publication=copy.deepcopy(row), filesystem_owner_closed=True,
                    source_input_owners_closed=True)
    except BaseException as error:
        uncertain = (isinstance(error, process_tree.ProcessTreeError) or
            workspace is not None and workspace.uncertain or
            any(resource.uncertain or any(owner.uncertain for owner in resource.owners)
                for resource in resources))
        if uncertain:
            _retain_lifecycle_graph(inspection, workspace, resources, error)
            raise
        if workspace is not None:
            failure = {'schema_version': 1, 'kind': LIFECYCLE_KIND, 'scope': SCOPE,
                'status': 'incomplete', 'phase': phase, 'selection_sha256': pin,
                'error': str(error)[:4096], 'completed_stages': receipts,
                'failed_stage': getattr(error, 'native_stage_receipt', None),
                **{name: False for name in FALSE_FACTS}}
            try:
                workspace.publish_bytes_new('native-prototype-failure.json', encoded(failure))
            except BaseException as publication_error:
                _retain_lifecycle_graph(inspection, workspace, resources, publication_error)
                raise process_tree.ProcessTreeError('Windows failure publication is uncertain: ' +
                    str(publication_error)) from error
        _close_lifecycle_graph(inspection, workspace, resources)
        raise


def _prototype_helper_closure(repository_root):
    """Finite literal local imports only, starting at the maintained CLI script."""
    import ast
    pending, names = ['tools/appended_engine_windows_prototype.py',
        'tools/appended_engine_windows_dependencies.py'], set()
    while pending:
        name = pending.pop()
        if name in names:
            continue
        if len(names) >= 64:
            raise ValueError('Windows static-probe helper source closure exceeds 64 files')
        raw = _read(Path(repository_root) / name)
        tree = ast.parse(raw, filename=name)
        names.add(name)
        for node in ast.walk(tree):
            modules = ([alias.name for alias in node.names] if isinstance(node, ast.Import)
                else [node.module] if isinstance(node, ast.ImportFrom) and node.level == 0
                else [])
            for module in modules:
                if module is None:
                    continue
                path = Path(repository_root) / 'tools' / (module.split('.')[0] + '.py')
                if path.is_file():
                    pending.append(path.relative_to(repository_root).as_posix())
    return sorted(names)


_STATIC_PROBE_BOOTSTRAP = r'''import sys
args = sys.argv[1:]
if len(args) < 11:
    raise RuntimeError("Incomplete fixed Windows static-inspector bootstrap")
exe, version, tools, cache, count = args[:5]
prefixes = args[5:9]
if not count.isdecimal() or not 1 <= int(count) <= 16:
    raise RuntimeError("Invalid fixed Windows runtime path count")
count = int(count)
expected, tail = args[9:9 + count], args[9 + count:]
normal = lambda value: value.replace(chr(92), "/")
if (normal(sys.executable) != exe or
        ".".join(str(value) for value in sys.version_info[:3]) != version or
        not sys.flags.isolated or not sys.flags.no_site or
        not sys.flags.ignore_environment or not sys.flags.no_user_site or
        sys.dont_write_bytecode is not True or
        normal(sys.pycache_prefix or "") != cache or
        [normal(value) for value in sys.path] != expected or
        [normal(value) for value in (sys.prefix, sys.base_prefix, sys.exec_prefix, sys.base_exec_prefix)] != prefixes or
        not tail or not tail[0].startswith(tools + "/") or
        "/" in tail[0][len(tools) + 1:]):
    raise RuntimeError("Actual isolated Windows interpreter/runtime/helper scope differs")
# Import the runner from the already checked runtime search paths before adding
# the exact captured helper root. No ambient site, cwd or PYTHONPATH is admitted.
import runpy
sys.path.insert(0, tools)
sys.argv = tail
runpy.run_path(tail[0], run_name="__main__")
'''


def _isolated_probe_paths(admitted):
    inventory = admitted['inventories']['host_generators']
    root = inventory['root']
    paths = []
    zip_name = 'python' + str(sys.version_info[0]) + str(sys.version_info[1]) + '.zip'
    for original in sys.path:
        if type(original) is not str or not original:
            continue
        path = PureWindowsPath(original).as_posix()
        if not path.startswith(root + '/') and path != root:
            continue  # controller-only helper paths are never passed to -I
        contract.windows_path(path, 'actual isolated Python runtime path')
        relative = (PureWindowsPath(path).relative_to(PureWindowsPath(root)).as_posix()
                    if path != root else '')
        parent = PurePosixPath(relative).parent.as_posix()
        parent = '' if parent == '.' else parent
        present_directory = relative == '' or relative in inventory['directories']
        present_zip = relative in inventory['files'] and PurePosixPath(relative).suffix.casefold() == '.zip'
        absent_standard_zip = (PurePosixPath(relative).name.casefold() == zip_name and
            relative not in inventory['files'] and relative not in inventory['directories'] and
            (parent == '' or parent in inventory['directories']))
        if not (present_directory or present_zip or absent_standard_zip):
            raise ValueError('Actual isolated Python runtime path lacks a complete held inventory disposition')
        if path in paths:
            raise ValueError('Actual isolated Python runtime paths are repeated')
        paths.append(path)
    for original in (sys.prefix, sys.base_prefix, sys.exec_prefix, sys.base_exec_prefix):
        path = PureWindowsPath(original).as_posix()
        if path == root:
            continue
        if (not path.startswith(root + '/') or
                PureWindowsPath(path).relative_to(PureWindowsPath(root)).as_posix() not in inventory['directories']):
            raise ValueError('Actual controller Python prefix lacks a complete held runtime inventory')
    if not 1 <= len(paths) <= 16:
        raise ValueError('A finite observed and inventoried isolated Python runtime path list is required')
    return paths


def _static_probe_command(controller, admitted, repository_root, output, provider_pin):
    script = PureWindowsPath(os.fspath(Path(repository_root) /
        'tools/appended_engine_windows_prototype.py')).as_posix()
    tools = PureWindowsPath(script).parent.as_posix()
    cache = output + '/tmp/pycache'
    paths = _isolated_probe_paths(admitted)
    version = '.'.join(str(value) for value in sys.version_info[:3])
    return {'phase': 'probe', 'argv': [controller, '-I', '-S', '-B', '-X',
        'pycache_prefix=' + cache, '-c', _STATIC_PROBE_BOOTSTRAP, controller,
        version, tools, cache, str(len(paths)),
        *[PureWindowsPath(value).as_posix() for value in
          (sys.prefix, sys.base_prefix, sys.exec_prefix, sys.base_exec_prefix)],
        *paths, script, 'inspect-provider',
        '--provider', output + '/install/bin/foundation-webcore-native-provider.dll',
        '--provider-sha256', provider_pin], 'cwd': output}


def _admit_retained_lifecycle_dependencies(reference, *, deadline):
    _reference(reference, 'original retained Windows dependency admission request')
    dependencies = _dependency_entry()
    admit = getattr(dependencies, 'admit_retained_dependency_with_probe', None)
    if not callable(admit):
        raise contract.MissingInputs([_missing('windows-retained-dependency-admission-source-join',
            'tools/appended_engine_windows_dependencies.py',
            'the reviewed original D/O/H/W reconstruction issuer must be composed into the native dependency controller')])
    return admit(reference, overall_deadline=deadline)


# Root must bind BOTH rows after the coherent A/process landing. Neither a
# sampled population nor a signature's existence can substitute for this join.
WINDOWS_LIFECYCLE_CAP_SOURCES = {
    'tools/appended_engine_windows_publication.py': '02f675a2480bbb94eafed0cac101b8afca1d2c3fe4a17dddd4cfb9693998edc0',
    'tools/process_tree.py': '521fa923a4396afeda67b05efabb0c21f1161895fbe72f172d4d7dfc69c1496f',
}


def _lifecycle_cap_admission(api, qualification, *, repository_root=None):
    expected = WINDOWS_LIFECYCLE_CAP_SOURCES
    missing = [_missing('windows-prototype-pre-resume-process-cap-source', name,
        'the coherent cap-enabled A/process source pin must be bound by the source owner before native output creation')
        for name, pin in expected.items() if pin is None]
    if missing:
        raise contract.MissingInputs(missing)
    source_root = _publication_source_root(api, repository_root)
    original = qualification.as_dict()['source_identity']
    for name, pin in expected.items():
        contract.pin(pin, 'reviewed Windows pre-resume process-cap source')
        if original.get(name) != pin:
            raise contract.MissingInputs([_missing('windows-prototype-original-process-cap-source',
                name, 'original native publication qualification does not cover the exact reviewed cap-enabled source')])
        _read(source_root / name, pin)
    return copy.deepcopy(expected)


def _shared_dependency_api(name):
    dependencies = _dependency_entry()
    method = getattr(dependencies, name, None)
    if not callable(method):
        raise contract.MissingInputs([_missing('windows-shared-dependency-parser-source-join',
            'tools/appended_engine_windows_dependencies.py::' + name,
            'the reviewed shared inventory and H1/H2 dispatcher must be composed into the dependency facade')])
    return method


def _engine_admission_view(value, handoff):
    """Consume the shared full-v2 declaration, retaining its tag and identity."""
    if (type(value) is not dict or type(value.get('schema_version')) is not int or
            value.get('schema_version') != 2 or
            value.get('kind') != 'foundation-native-engine-windows-admission-v2'):
        return value, None
    declare = _shared_dependency_api('engine_admission_declaration')
    declaration = declare(value, handoff)
    contract.fields(declaration, ('original', 'engine_programs', 'engine_program_versions'),
                    'shared full native admission declaration')
    if declaration['original'] != value:
        raise ValueError('Shared native declaration changed the original full v2 admission')
    original = copy.deepcopy(declaration['original'])
    contract.fields(declaration['engine_programs'], PROGRAM_NAMES, 'engine-use eleven program view')
    contract.fields(declaration['engine_program_versions'], PROGRAM_NAMES,
                    'engine-use eleven version view')
    if (declaration['engine_programs'] != {role: original['programs'][role] for role in PROGRAM_NAMES} or
            declaration['engine_program_versions'] != {
                role: original['program_versions'][role] for role in PROGRAM_NAMES}):
        raise ValueError('Engine-use program view differs from original full v2 admission')
    view = copy.deepcopy(original)
    view['programs'] = copy.deepcopy(declaration['engine_programs'])
    view['program_versions'] = copy.deepcopy(declaration['engine_program_versions'])
    # This transient view keeps schema2/kind2. It is never serialized as H1,
    # compared as a complete H2 identity, or used before genuine H2 admission.
    return view, digest(encoded(original))



def build(selection_path, pin, *, repository_root=ROOT, source_replay=None,
          input_qualification=None, publication=None, dependency_admission=None,
          dependency_reference=None, deadline=None):
    return _build_native_lifecycle(selection_path, pin, repository_root=repository_root,
        source_replay=source_replay, input_qualification=input_qualification,
        publication=publication, dependency_admission=dependency_admission,
        dependency_reference=dependency_reference, deadline=deadline)


_RAW_RUNTIME_SOURCES = ('CMakeLists.txt', 'runtime-target.cmake', 'windows-runtime-main.cpp',
    'common/raw_candidate_probe.hpp', 'common/raw_candidate_probe.cpp',
    'fixture/index.html')
# Fixed approved compiler/fixture source bytes. The observer algorithm itself
# is protected by the enclosing prototype/A source qualification; it is not its
# own compile input and therefore adds no circular self-hash.
_RAW_RUNTIME_SOURCE_PINS = {
    'CMakeLists.txt': '9d4461fc59b65ac45f1048178a889a22c10beaa1b4fea114dbd094956cfa1e42',
    'runtime-target.cmake': '0f2e989af311b97eef558704a384cb2ad9e10efda0e3daeb7e45dd05c2fcf2fc',
    'windows-runtime-main.cpp': '9e4d3bd0fd5135df21391f5062e838edad5670c2ce323daf0d0eec2ceb3959a8',
    'common/raw_candidate_probe.hpp': '839aea960a0a9f6e841b00b17e578f86415017508b088de7ac9abdb30c293838',
    'common/raw_candidate_probe.cpp': '57ef037681baaaf12e969b7e6f3f86e8b83c219b34d18865a9cb9b6b4c446876',
    'fixture/index.html': '944b2ec5efa3a08d51429a1df36062b926478153103bd480a716f83780f48951',
}
_RAW_GENERIC_ROLES = ('foundation_appended_abi', 'foundation_appended_container',
    'foundation_appended_resource_url', 'foundation_appended_web_services',
    'foundation_appended_document_forms', 'foundation_appended_editor_codec',
    'foundation_appended_engine_owner', 'foundation_appended_native_engine_driver',
    'foundation_appended_native_engine_loader', 'foundation_gui_appended_demo_services',
    'foundation_gui_appended_document', 'foundation_gui_appended_document_codec',
    'foundation_gui_appended_document_controller', 'foundation_gui_appended_document_forms',
    'foundation_gui_appended_document_v2_codec', 'foundation_gui_document_action_v1_codec',
    'foundation_gui_engine_document_broker', 'foundation_gui_appended_engine_document_application',
    'foundation_gui_native_engine_document_composition')
_RAW_BUILDS, _RAW_OBSERVATIONS = {}, {}
_RAW_RUNTIME_WINDOWS_TOOLCHAIN_SHA256 = 'd2070d1b4b01b1754212a44ff8b2be7ceb13494c802258be80b3de5606d61643'
_RAW_RUNTIME_CRT = ('libcmt', 'libcpmt', 'libvcruntime', 'libucrt', 'oldnames')
# A finite desktop system-link set, including CMake's usual console defaults.
# Each path below is selected from the ORIGINAL held SDK inventory, never LIB.
_RAW_RUNTIME_SYSTEM_LIBRARIES = ('kernel32', 'user32', 'advapi32', 'gdi32', 'winspool',
    'comdlg32', 'shell32', 'ole32', 'oleaut32', 'uuid', 'ws2_32', 'bcrypt', 'crypt32',
    'secur32', 'version', 'winmm', 'dwrite', 'd2d1', 'windowscodecs', 'combase',
    'ntdll', 'shlwapi', 'normaliz', 'iphlpapi')
_RAW_RUNTIME_PROGRAM_CACHE = {'CMAKE_C_COMPILER': 'compiler', 'CMAKE_CXX_COMPILER': 'compiler',
    'CMAKE_LINKER': 'linker', 'CMAKE_AR': 'archiver', 'CMAKE_RC_COMPILER': 'resource_compiler',
    'CMAKE_MT': 'manifest_tool', 'CMAKE_MAKE_PROGRAM': 'ninja'}


class _OriginalWindowsRuntimeHarnessBuild:
    def __new__(cls):
        raise TypeError('Original runtime harness builds are issued only after controlled compilation and graph closure')


class _OriginalWindowsRuntimeObservation:
    def __new__(cls):
        raise TypeError('Original runtime observations are issued only after the controlled runtime and complete graph closure')


def _raw_runtime_json(raw):
    value = _lifecycle_json(raw)
    # The shared strict parser handles duplicates/Unicode/nonfinite constants;
    # this walk also catches JSON numeric overflow before any field is ignored.
    def visit(item, depth=0):
        if depth > 32:
            raise ValueError('Raw runtime JSON nesting bound exceeded')
        if type(item) is float:
            raise ValueError('Raw runtime evidence has no floating point fields')
        if type(item) is dict:
            if len(item) > 256: raise ValueError('Raw runtime JSON object bound exceeded')
            for key, child in item.items():
                key.encode('utf-8'); visit(child, depth + 1)
        elif type(item) is list:
            if len(item) > 256: raise ValueError('Raw runtime JSON array bound exceeded')
            for child in item: visit(child, depth + 1)
        elif type(item) is str:
            if len(item) > 4096: raise ValueError('Raw runtime JSON string bound exceeded')
            item.encode('utf-8')
    visit(value)
    return value


def _raw_runtime_record(raw, *, pid, nonce, recipe_sha256, provider_build_sha256, package_sha256):
    """Pure validation only. A fixture/raw record can NEVER mint an observation."""
    value = _raw_runtime_json(raw)
    contract.fields(value, ('schema_version', 'kind', 'platform', 'process_id', 'nonce',
        'recipe_sha256', 'provider_build_sha256', 'package_sha256', 'loader', 'observations'), 'raw runtime observation')
    if (type(value['schema_version']) is not int or value['schema_version'] != 1 or
            value['kind'] != 'foundation-raw-native-candidate-runtime-observations-v1' or
            value['platform'] != 'windows-x86_64' or type(value['process_id']) is not int or
            value['process_id'] != pid or type(pid) is not int or pid <= 0 or
            value['nonce'] != contract.pin(nonce, 'original runtime challenge') or
            value['recipe_sha256'] != contract.pin(recipe_sha256, 'original runtime R') or
            value['provider_build_sha256'] != contract.pin(provider_build_sha256, 'original runtime B') or
            value['package_sha256'] != contract.pin(package_sha256, 'original runtime package') or
            value['loader'] != 'LoadLibraryExW-DLL_LOAD_DIR-SYSTEM32-process-lifetime'):
        raise ValueError('Original raw runtime process/challenge/subject differs')
    names = ('getter_calls', 'starts', 'rejected_second_starts', 'provider_entries', 'maximum_provider_depth',
        'enter_calls', 'leave_calls', 'outside_owner_samples', 'query3_calls', 'query3_reply_bytes', 'semantic_revision',
        'echo_calls', 'echo_request_bytes', 'echo_reply_bytes', 'service_ack_through', 'deliveries',
        'damage_callbacks', 'frame_revision', 'opaque_pixels', 'differing_pixels', 'application_instance',
        'document_sequence', 'service_generation', 'snapshot_revision', 'marker_observations', 'final_state')
    observed = value['observations']
    contract.fields(observed, (*names, 'frame_sha256', 'query3_sha256'), 'raw shared runtime counters')
    for name in names:
        if type(observed[name]) is not int or not 0 <= observed[name] <= (1 << 64) - 1:
            raise ValueError('Raw runtime counters must be actual bounded integers: ' + name)
    for name in ('frame_sha256', 'query3_sha256'): contract.pin(observed[name], name)
    if (any(observed[name] != 1 for name in ('getter_calls', 'starts', 'rejected_second_starts',
                                           'maximum_provider_depth', 'echo_calls')) or
            observed['enter_calls'] <= 0 or observed['enter_calls'] != observed['leave_calls'] or
            any(observed[name] <= 0 for name in ('provider_entries', 'outside_owner_samples', 'query3_calls',
                'semantic_revision', 'deliveries', 'damage_callbacks', 'frame_revision', 'application_instance',
                'document_sequence', 'service_generation', 'snapshot_revision', 'marker_observations')) or
            not 1 <= observed['query3_reply_bytes'] <= 1048576 or
            observed['echo_request_bytes'] != 32 or observed['echo_reply_bytes'] != 32 or
            observed['service_ack_through'] < 2 or observed['opaque_pixels'] != 480000 or
            not 1 <= observed['differing_pixels'] <= 480000 or observed['final_state'] != 4):
        raise ValueError('Original shared document/render/service/owner-close predicates failed')
    return value


def _raw_native_graph(api, inspection, workspace, subject, environment, input_qualification,
                      dependency_admission, publication, resources, *, deadline):
    """Bind actual issued source/A graph and original cap-qualified helper bytes."""
    require_native_host(); _lifecycle_time(deadline); inspection.check()
    contract.fields(subject, ('handoff', 'source_replay', 'admission', 'recipe_sha256', 'provider_build_sha256',
        'toolchain_identity_sha256'), 'original runtime source subject')
    contract.fields(subject['handoff'], ('root', 'sha256'), 'runtime handoff')
    _reference(subject['source_replay'], 'original runtime source replay')
    _reference(subject['admission'], 'complete original native runtime admission')
    for name in ('recipe_sha256', 'provider_build_sha256', 'toolchain_identity_sha256'):
        contract.pin(subject[name], name)
    actual = _source_publication_adapter(inspection, subject['handoff']['root'],
        subject['handoff']['sha256'], subject['source_replay'])
    if actual is not api or type(workspace) is not api.Workspace or type(workspace.native) is not api._Native:
        raise ValueError('The same actual source-held native A Workspace is required')
    if workspace.diagnostic or workspace.closed or workspace.failed or workspace.uncertain or workspace.joined or workspace.logs:
        raise ValueError('Raw runtime requires one fresh non-diagnostic qualified Workspace')
    # Re-admit the ORIGINAL publication qualification and exact source-owned cap
    # baseline. Keyword shape or a passed boolean supplies neither authority.
    qualification = _publication_qualification(api, publication)
    _lifecycle_cap_admission(api, qualification)
    facts = qualification.as_dict()
    if (workspace.filesystem != facts['filesystem'] or
            workspace.native.runtime_identity() != facts['runtime_identity'] or
            api.process_tree is not process_tree):
        raise ValueError('Original runtime Workspace source/filesystem/runtime differs from qualified A')
    if environment.get('TEMP') != workspace.output + '/tmp' or environment.get('TMP') != workspace.output + '/tmp':
        raise ValueError('Raw runtime temporary paths must belong to its fresh Workspace')
    held = _HeldLifecycleInputs(api, input_qualification, deadline); resources.append(held)
    # Keep the raw manifest pinned, but obtain enriched R/B/H/native-input facts
    # through the SAME maintained verifier over the actual source-held capsule.
    held.reference({'path': subject['handoff']['root'] + '/handoff.json',
        'sha256': subject['handoff']['sha256']})
    import appended_engine_windows_handoff as handoff_tool
    handoff = handoff_tool.verify_handoff(subject['handoff']['root'], subject['handoff']['sha256'])
    if any(handoff.get(name) != subject[name] for name in ('recipe_sha256', 'provider_build_sha256', 'toolchain_identity_sha256')):
        raise ValueError('Runtime R/B/H declarations differ from actual source-held handoff bytes')
    admission = _raw_runtime_json(held.reference(subject['admission']))
    contract.fields(admission.get('inventories'), INVENTORY_ROLES, 'complete original runtime native inventories')
    for role in sorted(INVENTORY_ROLES): held.inventory(admission['inventories'][role], role)
    # The v6 helper joins ALL original H1/H2 roles before the engine's narrower
    # admission view (including additional nmake/msbuild roles when selected).
    _require_dependency_admission(dependency_admission, {'native_inputs': handoff['native_inputs']},
        handoff, held, admission, retained=True)
    admitted = _admission(admission, handoff)
    admitted['raw_runtime_original_builtins'] = copy.deepcopy(admission['builtins'])
    admitted['raw_runtime_original_crt'] = copy.deepcopy(admission['crt_libraries'])
    _controller_lifecycle_python(admitted)
    if environment != native_environment(admitted, workspace.output):
        raise ValueError('Runtime environment differs from the exact original admitted tool/runtime closure')
    workspace.check_anchors()
    return held, admitted


def _raw_hold_sources(held, source_root, pins):
    contract.windows_path(source_root, 'exact raw harness source root')
    contract.fields(pins, _RAW_RUNTIME_SOURCES, 'complete fixed raw harness source pins')
    if pins != _RAW_RUNTIME_SOURCE_PINS:
        raise ValueError('Raw runtime compiler/fixture sources differ from the approved source catalogue')
    raw = {name: held.reference({'path': source_root + '/' + name,
        'sha256': contract.pin(pins[name], name)}) for name in _RAW_RUNTIME_SOURCES}
    held.check(); return raw


def _raw_harness_image(raw):
    value = inspect_tool_image(raw)
    if value['dll'] or any(DYNAMIC_CRT.fullmatch(name) or name.casefold() not in SYSTEM_IMPORTS
                           for name in value['needed']):
        raise ValueError('Raw runtime harness must be an actual static-CRT x64 executable with only fixed system imports')
    return value


def _raw_runtime_archive_roles(archives, original_membership):
    """A current role label cannot rename an original kernel/provider aggregate."""
    contract.fields(archives, _RAW_GENERIC_ROLES, 'closed original generic archive roles')
    for role in _RAW_GENERIC_ROLES:
        reference = archives[role]
        if PureWindowsPath(reference['path']).name != role + '.lib':
            raise ValueError('Retained generic archive basename differs from its maintained static-target role: ' + role)
        matches = [fact for fact in original_membership if
            all(fact['reference'].get(key) == reference[key] for key in ('path', 'sha256'))]
        if len(matches) != 1 or not any(PurePosixPath(origin['member']).name == role + '.lib'
                for origin in matches[0]['origins']):
            raise ValueError('Actual C original member basename differs from the generic static-target role: ' + role)


def _raw_generic_inputs(held, reference, generic_originals, admitted):
    if generic_originals is None:
        raise contract.MissingInputs([_missing('windows-original-retained-generic-runtime-members', reference['path'],
            'genuine C original-origin membership for static archives and complete header/provenance bytes is required')])
    original_membership = _shared_dependency_api('require_original_membership')
    value = _raw_runtime_json(held.reference(reference))
    original_refs = [] # This new held/pinned manifest is a current declaration, not historical producer evidence.
    contract.fields(value, ('schema_version', 'kind', 'target', 'crt', 'archives', 'include_directories', 'header_inventories'),
        'retained raw runtime generic link inputs')
    if (type(value['schema_version']) is not int or value['schema_version'] != 1 or
            value['kind'] != 'foundation-raw-runtime-generic-link-inputs-v1' or
            value['target'] != 'windows-x86_64' or value['crt'] != 'static-mt'):
        raise ValueError('Raw runtime generic-link input subject differs')
    contract.fields(value['archives'], _RAW_GENERIC_ROLES, 'closed generic static archive roles')
    allowed_defaults = set(_RAW_RUNTIME_CRT) | set(_RAW_RUNTIME_SYSTEM_LIBRARIES)
    builtins = admitted.get('raw_runtime_original_builtins')
    if type(builtins) is dict:
        path, _pin = _reference(builtins, 'original admitted clang builtins')
        allowed_defaults.add(PureWindowsPath(path).stem.casefold())
    for name in _RAW_GENERIC_ROLES:
        row = value['archives'][name]; _reference(row, 'retained generic static archive')
        if PureWindowsPath(row['path']).name != name + '.lib':
            raise ValueError('Generic archive selection cannot relabel an original kernel/provider aggregate: ' + name)
        raw = held.reference(row, maximum=MAX_BINARY)
        inspect_static_archive(raw, allowed_default_libraries=allowed_defaults)
        original_refs.append(dict(row, bytes=len(raw)))
    roots = value['include_directories']
    if type(roots) is not list or not 1 <= len(roots) <= 32 or len(set(roots)) != len(roots):
        raise ValueError('Finite exact retained generic header roots required')
    references = value['header_inventories']
    if type(references) is not list or not 1 <= len(references) <= 32:
        raise ValueError('Complete retained generic header inventory/provenance references required')
    admitted_directories = set()
    for reference in references:
        _reference(reference, 'complete generic header inventory')
        inventory_raw = held.reference(reference)
        inventory = held.inventory(reference, 'product_assets')
        original_refs.append(dict(reference, bytes=len(inventory_raw)))
        provenance = inventory['provenance']; _reference(provenance, 'original generic inventory provenance')
        provenance_raw = held.reference(provenance)
        original_refs.append(dict(provenance, bytes=len(provenance_raw)))
        declaration = _shared_dependency_api('inventory_declaration')(inventory_raw, reference['sha256'],
            'product_assets', provenance_raw=provenance_raw, provenance_pin=provenance['sha256'])
        for original in declaration['original_refs']:
            raw = held.reference(original, maximum=MAX_BINARY)
            original_refs.append(dict(original, bytes=len(raw)))
        # held.inventory has captured/hash-checked every exact leaf and all
        # complete directory memberships before these facts join original C.
        for name, row in inventory['files'].items():
            original_refs.append({'path': inventory['root'] + '/' + name,
                'sha256': row['sha256'], 'bytes': row['bytes']})
        admitted_directories.add(inventory['root'])
        admitted_directories.update(inventory['root'] + '/' + name for name in inventory['directories'])
    # The actual A capture and shared original-provenance parser above own all
    # header bytes; naming an arbitrary directory never supplies this authority.
    for root in roots:
        contract.windows_path(root, 'retained generic header root')
        if root not in admitted_directories:
            raise contract.MissingInputs([_missing('windows-runtime-retained-generic-headers', root,
                'complete original held generic-header inventory must be admitted before harness configuration')])
    # C's actual opaque original-origin issuer is mandatory. A declared hash,
    # provenance status, fixture token or summary cannot supply membership.
    unique = {}
    for row in original_refs:
        previous = unique.get(row['path'])
        if previous is not None and any(previous.get(key) != item for key, item in row.items() if key in previous):
            raise ValueError('Conflicting original generic runtime member identities')
        unique[row['path']] = row if previous is None or len(row) > len(previous) else previous
    rows = list(unique.values())
    membership = []
    for offset in range(0, len(rows), 16000):
        membership.extend(original_membership(generic_originals, rows[offset:offset + 16000]))
    _raw_runtime_archive_roles(value['archives'], membership)
    held.check(); return {'manifest': value, 'original_membership': membership}


def _raw_runtime_link_inputs(held, admitted):
    """Absolute original-H link inputs; suppressed DEFAULTLIB never searches LIB.

    The full original H token has already joined all these complete inventories
    in _raw_native_graph. SDK import libraries are held original SDK bytes, not
    falsely passed through the static-only COFF archive inspector.
    """
    crt = admitted['raw_runtime_original_crt']
    contract.fields(crt, _RAW_RUNTIME_CRT, 'original runtime static CRT closure')
    references = [dict(crt[name]) for name in _RAW_RUNTIME_CRT]
    references.append(dict(admitted['raw_runtime_original_builtins']))
    sdk = admitted['inventories']['windows_sdk']
    directories = {PureWindowsPath(path) for path in admitted['library_directories']}
    for name in _RAW_RUNTIME_SYSTEM_LIBRARIES:
        matches = [{'path': sdk['root'] + '/' + leaf, 'sha256': row['sha256']}
            for leaf, row in sdk['files'].items()
            if PureWindowsPath(leaf).name.casefold() == name + '.lib' and
               PureWindowsPath(sdk['root'] + '/' + leaf).parent in directories]
        if len(matches) != 1:
            raise contract.MissingInputs([_missing('windows-runtime-original-sdk-link-library', name + '.lib',
                'exactly one original Windows SDK leaf in the full-H selected library directories is required')])
        references.extend(matches)
    result, seen = [], set()
    for reference in references:
        path, _pin = _reference(reference, 'absolute original runtime link input')
        if path.casefold() in seen or PureWindowsPath(path).suffix.casefold() != '.lib':
            raise ValueError('Original runtime link inputs have aliases or non-library paths')
        seen.add(path.casefold())
        matches = [row for inventory in admitted['inventories'].values()
            for leaf, row in inventory['files'].items()
            if (inventory['root'] + '/' + leaf) == path and row['sha256'] == reference['sha256']]
        if len(matches) != 1:
            raise ValueError('Absolute runtime link input differs from the actual original H inventory')
        raw = held.reference(reference, maximum=MAX_BINARY)
        if len(raw) != matches[0]['bytes']:
            raise ValueError('Absolute original runtime link input EOF differs')
        result.append(dict(reference, bytes=len(raw)))
    held.check()
    return {'authority': 'same-actual-original-full-H1-H2-complete-inventories', 'references': result}


def _raw_runtime_link_cache(link_inputs):
    """Render only qualified absolute paths into a fresh owned initial cache."""
    paths = []
    for reference in link_inputs['references']:
        path = contract.windows_path(reference['path'], 'original runtime absolute link path')
        paths.append('"' + path + '"')
    standard = ' '.join(paths)
    values = {'CMAKE_EXE_LINKER_FLAGS': '/NODEFAULTLIB',
        'CMAKE_EXE_LINKER_FLAGS_RELEASE': '/INCREMENTAL:NO /MACHINE:X64',
        'CMAKE_CXX_STANDARD_LIBRARIES': standard}
    source = '# Exact original H paths; every implicit DEFAULTLIB request is suppressed.\n'
    for name, value in values.items():
        source += 'set(' + name + ' "' + value.replace('"', '\\"') + '" CACHE STRING "" FORCE)\n'
    return source.encode('ascii'), values


def _raw_runtime_link_readback(raw_cache, raw_ninja, inputs, link_inputs, expected_cache):
    """Pure actual configure readback; no fixture/status can issue authority."""
    cache, cache_types = {}, {}
    for line in raw_cache.decode('utf-8').splitlines():
        if not line or line.startswith(('#', '//')): continue
        match = re.fullmatch(r'([^:=]+):([^=]+)=(.*)', line)
        if match:
            if match[1] in cache: raise ValueError('Repeated actual runtime CMake cache key')
            cache[match[1]], cache_types[match[1]] = match[3], match[2]
    if any(cache.get(name) != value or cache_types.get(name) != (
            'FILEPATH' if name in _RAW_RUNTIME_PROGRAM_CACHE else 'STRING')
            for name, value in expected_cache.items()):
        raise ValueError('Actual runtime configure changed the closed absolute link cache')
    text = raw_ninja.decode('utf-8')
    # Only Ninja's three literal escapes and physical-line continuation are
    # accepted here. Variable expansion in the selected link lists is rejected.
    text = text.replace('$\r\n', '').replace('$\n', '')
    lines, blocks = text.splitlines(), []
    for number, line in enumerate(lines):
        if not line.startswith('build foundation_raw_windows_candidate_runtime.exe:'): continue
        block = {}
        for following in lines[number + 1:]:
            if following and not following.startswith((' ', '#')): break
            match = re.fullmatch(r'  ([A-Z_]+) = (.*)', following)
            if match:
                if match[1] in block: raise ValueError('Repeated actual runtime Ninja link variable')
                block[match[1]] = match[2]
        blocks.append(block)
    if len(blocks) != 1: raise ValueError('One actual harness-only executable Ninja edge is required')
    block = blocks[0]
    def literal(value):
        result, cursor = '', 0
        while cursor < len(value):
            char = value[cursor]; cursor += 1
            if char == '$':
                if cursor == len(value) or value[cursor] not in '$ :':
                    raise ValueError('Runtime link metadata has an unqualified Ninja variable')
                char = value[cursor]; cursor += 1
            result += char
        return result
    def words(value):
        # Fixed absolute .lib paths cannot contain quotes or end in backslashes;
        # their generated command spelling needs only ordinary paired quotes.
        tokens, current, quoted = [], '', False
        for char in literal(value):
            if char == '"': quoted = not quoted
            elif char.isspace() and not quoted:
                if current: tokens.append(current); current = ''
            else: current += char
        if quoted: raise ValueError('Unterminated actual runtime library quote')
        if current: tokens.append(current)
        return tokens
    wanted = [inputs['manifest']['archives'][name]['path'] for name in _RAW_GENERIC_ROLES]
    wanted += [row['path'] for row in link_inputs['references']]
    actual = words(block.get('LINK_LIBRARIES', ''))
    if [PureWindowsPath(path) for path in actual] != [PureWindowsPath(path) for path in wanted]:
        raise ValueError('Actual runtime linker library argv escapes the closed original absolute inputs')
    flags = [word.casefold() for word in words(block.get('LINK_FLAGS', ''))]
    required = {'/nodefaultlib', '/incremental:no', '/machine:x64'}
    allowed = required | {'/subsystem:console', '/version:0.0', '/manifest', '/manifest:embed'}
    if not required.issubset(flags) or len(set(flags)) != len(flags) or any(flag not in allowed for flag in flags):
        raise ValueError('Actual runtime link flags differ from the finite original closure')
    if literal(block.get('LINK_PATH', '')).strip():
        raise ValueError('Actual runtime linker must have no directory-based library search inputs')
    return {'scope': 'actual-configured-ninja-library-and-link-flag-readback',
        'cache_sha256': digest(raw_cache), 'ninja_sha256': digest(raw_ninja),
        'absolute_libraries': wanted, 'link_flags': flags,
        'program_cache': {name: cache[name] for name in _RAW_RUNTIME_PROGRAM_CACHE}}


def _build_windows_runtime_harness(*, api, input_qualification, inspection, workspace,
        source_root, source_pins, generic_manifest, toolchain_reference, cmake,
        dependency_admission, generic_originals, publication, subject, environment, limits, resources, deadline):
    """Own a separate original harness-only build, close it, then issue its token.

    This source operation is an explicitly selected maintenance step. It never
    selects a supplier/provider/kernel build and has no generic-target fallback.
    Actual compilation remains UNRUN until separately authorized and supplied
    complete retained generic archives, headers, toolchain and original proofs.
    """
    try:
        held, admitted = _raw_native_graph(api, inspection, workspace, subject, environment,
            input_qualification, dependency_admission, publication, resources, deadline=deadline)
        contract.windows_path(cmake, 'original admitted runtime-harness CMake')
        if cmake != admitted['programs']['cmake']:
            raise ValueError('Harness build CMake differs from the original admitted H executable')
        _reference(generic_manifest, 'held current generic-link selection manifest')
        if toolchain_reference is not None:
            _reference(toolchain_reference, 'original admitted Windows toolchain source')
        for name in ('tmp', 'logs', 'evidence', 'cmake', 'harness-source',
                     'harness-source/common', 'harness-source/fixture'): workspace.mkdir_new(name)
        source_bytes = _raw_hold_sources(held, source_root, source_pins)
        transfer = {name: workspace.publish_bytes_new('harness-source/' + name, source_bytes[name])
            for name in _RAW_RUNTIME_SOURCES}
        inputs = _raw_generic_inputs(held, generic_manifest, generic_originals, admitted)
        link_inputs = _raw_runtime_link_inputs(held, admitted)
        link_cache, expected_link_cache = _raw_runtime_link_cache(link_inputs)
        link_cache_row = workspace.publish_bytes_new('runtime-link-closure.cmake', link_cache)
        template_path = PureWindowsPath(Path(ROOT) / RECIPE / 'windows-toolchain.cmake.in').as_posix()
        template = held.reference({'path': template_path, 'sha256': _RAW_RUNTIME_WINDOWS_TOOLCHAIN_SHA256})
        programs = admitted['programs']
        expected_link_cache.update({name: programs[role] for name, role in _RAW_RUNTIME_PROGRAM_CACHE.items()})
        expected_link_cache.update({'CMAKE_BUILD_TYPE': 'Release', 'CMAKE_MSVC_RUNTIME_LIBRARY': 'MultiThreaded'})
        expected_toolchain = render_cache(template, {'CMAKE_C_COMPILER': programs['compiler'],
            'CMAKE_CXX_COMPILER': programs['compiler'], 'CMAKE_LINKER': programs['linker'],
            'CMAKE_AR': programs['archiver'], 'CMAKE_RC_COMPILER': programs['resource_compiler'],
            'CMAKE_MT': programs['manifest_tool']})
        if toolchain_reference is not None and held.reference(toolchain_reference) != expected_toolchain:
            raise ValueError('Harness toolchain differs from the exact maintained native Windows template and admitted tools')
        toolchain_row = workspace.publish_bytes_new('runtime-toolchain.cmake', expected_toolchain)
        commands = [
            {'phase': 'configure', 'cwd': workspace.output, 'argv': [cmake, '-S', workspace.output + '/harness-source',
                '-B', workspace.output + '/cmake', '-G', 'Ninja',
                '-C', workspace.output + '/runtime-link-closure.cmake',
                '-DCMAKE_TOOLCHAIN_FILE=' + workspace.output + '/runtime-toolchain.cmake', '-DCMAKE_BUILD_TYPE=Release',
                '-DCMAKE_MAKE_PROGRAM:FILEPATH=' + programs['ninja'],
                '-DCMAKE_MSVC_RUNTIME_LIBRARY=MultiThreaded',
                '-DBIB_RAW_RUNTIME_GENERIC_MANIFEST=' + generic_manifest['path'],
                '-DBIB_RAW_RUNTIME_GENERIC_MANIFEST_SHA256=' + generic_manifest['sha256']]},
            {'phase': 'build', 'cwd': workspace.output, 'argv': [cmake, '--build', workspace.output + '/cmake',
                '--config', 'Release', '--target', 'foundation_raw_windows_candidate_runtime',
                '--parallel', str(validate_limits(limits)['maximum_jobs'])]}]
        receipts, link_readback = [], None
        for command in commands:
            held.check(); inspection.check()
            joined, receipt = _run_workspace_stage(workspace, command, environment, limits, inspection, deadline=deadline)
            if type(joined) is not api.JoinedStage or not any(joined is item for item in workspace.joined):
                raise ValueError('Original harness build needs its actual Workspace-issued joined stages')
            receipts.append(receipt)
            if command['phase'] == 'configure':
                configured, raw_metadata = workspace.inspect_outputs(), {}
                for name in ('CMakeCache.txt', 'build.ninja'):
                    relative = 'cmake/' + name
                    row = configured['files'].get(relative)
                    if row is None: raise ValueError('Actual runtime configure metadata is absent: ' + name)
                    raw_metadata[name] = _held_output_bytes(api, input_qualification, workspace, relative,
                        row, resources, deadline=deadline)
                link_readback = _raw_runtime_link_readback(raw_metadata['CMakeCache.txt'],
                    raw_metadata['build.ninja'], inputs, link_inputs, expected_link_cache)
        inventory = workspace.inspect_outputs()
        metadata_row = inventory['files'].get('cmake/runtime-target.json')
        if metadata_row is None: raise ValueError('Original CMake harness target metadata is absent')
        metadata_raw = _held_output_bytes(api, input_qualification, workspace, 'cmake/runtime-target.json',
            metadata_row, resources, deadline=deadline)
        metadata = _raw_runtime_json(metadata_raw)
        contract.fields(metadata, ('schema_version', 'kind', 'file', 'filename'), 'actual raw harness CMake target')
        if (type(metadata['schema_version']) is not int or metadata['schema_version'] != 1 or
                metadata['kind'] != 'foundation-raw-windows-runtime-target-v1' or
                metadata['filename'] != 'foundation_raw_windows_candidate_runtime.exe'):
            raise ValueError('Actual original harness CMake target subject differs')
        path = contract.windows_path(metadata['file'], 'actual original harness executable')
        if not contract.inside(path, workspace.output + '/cmake') or PureWindowsPath(path).name != metadata['filename']:
            raise ValueError('Original harness CMake target escapes its owned tree')
        relative = PureWindowsPath(path).relative_to(PureWindowsPath(workspace.output)).as_posix()
        row = inventory['files'].get(relative)
        if row is None: raise ValueError('Actual compiled harness bytes are absent')
        raw = _held_output_bytes(api, input_qualification, workspace, relative, row, resources,
            deadline=deadline, maximum=MAX_BINARY)
        _raw_harness_image(raw)
        # Final complete immutable log captures retain physical identities; no
        # serialized configure/build result can replace their original objects.
        rows = {name[len('logs/'):]: dict(sha256=item['sha256'], bytes=item['bytes'], mode=0o644)
            for name, item in inventory['files'].items() if name.startswith('logs/')}
        if set(rows) != {'configure.log', 'build.log'}: raise ValueError('Complete original harness-build logs differ')
        logs = held._root(workspace.output + '/logs').capture_tree('', files=rows, directories=[]); held.trees.append(logs)
        held.check()
        for receipt in receipts:
            if logs.as_dict()['observed']['files'][receipt['phase'] + '.log']['identity'] != receipt['log_identity']:
                raise ValueError('Original harness-build log physical identity changed')
        value = {'schema_version': 1, 'kind': 'foundation-original-windows-runtime-harness-build-v1',
            'scope': 'actual-two-tu-harness-and-retained-generic-archives-only',
            'subject': copy.deepcopy(subject), 'source_root': source_root, 'source_pins': copy.deepcopy(source_pins),
            'source_transfer': transfer,
            'generic_manifest': copy.deepcopy(generic_manifest), 'generic_inputs': inputs,
            'absolute_link_inputs': link_inputs, 'link_readback': link_readback,
            'link_cache': {'path': workspace.output + '/runtime-link-closure.cmake',
                'sha256': link_cache_row['sha256']},
            'toolchain': {'path': workspace.output + '/runtime-toolchain.cmake',
                'sha256': toolchain_row['sha256']},
            'toolchain_template': {'path': template_path, 'sha256': _RAW_RUNTIME_WINDOWS_TOOLCHAIN_SHA256},
            'stages': receipts,
            'harness': {'path': path, 'sha256': row['sha256']}, 'harness_bytes': row['bytes'],
            'engine_execution': False, 'kernel_rebuild': False, 'production_eligible': False}
        for owner in resources: owner.check()
        inspection.check()
        output = workspace.commit_receipt_new('runtime-harness-build.json', encoded(value))
        _close_lifecycle_graph(inspection, workspace, resources)
        token = object.__new__(_OriginalWindowsRuntimeHarnessBuild)
        _RAW_BUILDS[token] = dict(value, reference={'path': workspace.output + '/runtime-harness-build.json',
            'sha256': output['sha256'], 'bytes': output['bytes']},
            closure='all-original-workspace-input-and-source-owners-closed')
        return token
    except BaseException as error:
        _retain_lifecycle_graph(inspection, workspace, resources, error)
        raise


def _raw_final_log(api, qualification, workspace, joined, receipt, resources, *, deadline):
    if (type(joined) is not api.JoinedStage or not any(joined is item for item in workspace.joined) or
            receipt['phase'] != 'probe'):
        raise ValueError('Original runtime must have its exact actual Workspace-issued JoinedStage')
    matches = [item for item in workspace.logs if item.path == 'logs/probe.log']
    if len(matches) != 1 or len(workspace.logs) != 1 or matches[0]._state != 'sealed':
        raise ValueError('Original runtime needs its one exact sealed OwnedLog')
    log = matches[0]
    launches = [item for item in workspace._launches if item[0] is log and item[1] is log._owner and item[2] is log.stream]
    if (len(launches) != 1 or type(log._owner) is not process_tree.ProcessTree or not log._owner.closed or
            log._owner.process.returncode != 0 or receipt['log_identity'] != log.identity):
        raise ValueError('Original runtime launch/log/process association differs')
    actual = joined.as_dict()
    if (any(actual[name] != receipt[name] for name in ('phase', 'argv', 'cwd')) or
            actual['returncode'] != 0 or actual['closure'] != 'actual-bound-job-finish-and-close'):
        raise ValueError('Original runtime JoinedStage command or closure differs')
    inventory = workspace.inspect_outputs()
    rows = {name[len('logs/'):]: dict(sha256=row['sha256'], bytes=row['bytes'], mode=0o644)
        for name, row in inventory['files'].items() if name.startswith('logs/')}
    if set(rows) != {'probe.log'}: raise ValueError('Complete final original runtime log tree differs')
    capture = _HeldLifecycleInputs(api, qualification, deadline); resources.append(capture)
    root = capture._root(workspace.output + '/logs')
    tree = root.capture_tree('', files=rows, directories=[]); capture.trees.append(tree)
    capture.check()
    if tree.as_dict()['observed']['files']['probe.log']['identity'] != log.identity:
        raise ValueError('Original sealed runtime log physical identity changed')
    stream = tree.open_file('probe.log')
    try:
        if rows['probe.log']['bytes'] > MAX_DOCUMENT: raise ValueError('Original runtime observation JSON is too large')
        raw = stream.read()
    finally: stream.close()
    if len(raw) != rows['probe.log']['bytes'] or digest(raw) != rows['probe.log']['sha256']:
        raise ValueError('Original runtime sealed log bytes/EOF differ')
    capture.check(); workspace.check_anchors()
    return raw, log._owner.process.pid, rows['probe.log']


def _require_original_windows_runtime(value):
    """Immutable original snapshot only; consumers must re-hold its subjects."""
    if type(value) is not _OriginalWindowsRuntimeObservation or value not in _RAW_OBSERVATIONS:
        raise ValueError('An actual post-closure original Windows runtime observation is required')
    return copy.deepcopy(_RAW_OBSERVATIONS[value])


def _observe_windows_candidate_runtime(*, api, input_qualification, inspection, workspace,
        harness_build, provider_reference, package_reference, package_index_offset, package_index_length,
        dependency_admission, generic_originals, publication, subject, environment, limits, resources, deadline):
    """Take ownership of this entire fresh graph, close it, THEN issue evidence.

    The passed inspection, Workspace and resources must never be used/closed by
    the caller afterward. Any failure retains the whole actual owner graph.
    """
    import secrets
    try:
        held, admitted = _raw_native_graph(api, inspection, workspace, subject, environment,
            input_qualification, dependency_admission, publication, resources, deadline=deadline)
        if type(harness_build) is not _OriginalWindowsRuntimeHarnessBuild or harness_build not in _RAW_BUILDS:
            raise contract.MissingInputs([_missing('windows-original-runtime-harness-build', 'raw candidate harness',
                'an original controlled harness-only build with the exact retained generic inputs is required')])
        build = copy.deepcopy(_RAW_BUILDS[harness_build])
        if build['subject'] != subject:
            raise ValueError('Original runtime harness build belongs to another R/B/H/source subject')
        for name in ('tmp', 'logs', 'evidence'): workspace.mkdir_new(name)
        original_build = _lifecycle_json(held.reference({name: build['reference'][name] for name in ('path', 'sha256')}))
        if original_build != {name: value for name, value in build.items() if name not in ('reference', 'closure')}:
            raise ValueError('Immutable original harness build report differs from its actual issued snapshot')
        _raw_hold_sources(held, build['source_root'], build['source_pins'])
        if _raw_generic_inputs(held, build['generic_manifest'], generic_originals, admitted) != build['generic_inputs']:
            raise ValueError('Current held generic runtime input closure differs from the original harness build')
        if _raw_runtime_link_inputs(held, admitted) != build['absolute_link_inputs']:
            raise ValueError('Current held original-H runtime link closure differs from the original harness build')
        harness_raw = held.reference(build['harness'], maximum=MAX_BINARY)
        if len(harness_raw) != build['harness_bytes']:
            raise ValueError('Original compiled harness byte count/EOF differs')
        _raw_harness_image(harness_raw) # Static executable inspection; no load here.
        provider_raw = held.reference(provider_reference, maximum=MAX_BINARY); inspect_provider(provider_raw)
        package_raw = held.reference(package_reference, maximum=4 * 1024 * 1024)
        for number in (package_index_offset, package_index_length):
            if type(number) is not int or number <= 0: raise ValueError('Original package index requires positive actual integers')
        if package_index_offset + package_index_length != len(package_raw):
            raise ValueError('Original runtime package index is not its exact suffix')
        nonce = secrets.token_hex(32)
        command = {'phase': 'probe', 'cwd': workspace.output, 'argv': [build['harness']['path'],
            provider_reference['path'], package_reference['path'], str(package_index_offset), str(package_index_length),
            package_reference['sha256'], subject['recipe_sha256'], subject['provider_build_sha256'], nonce]}
        held.check(); inspection.check()
        joined, stage = _run_workspace_stage(workspace, command, environment, limits, inspection, deadline=deadline)
        raw, pid, log = _raw_final_log(api, input_qualification, workspace, joined, stage, resources, deadline=deadline)
        observed = _raw_runtime_record(raw, pid=pid, nonce=nonce, recipe_sha256=subject['recipe_sha256'],
            provider_build_sha256=subject['provider_build_sha256'], package_sha256=package_reference['sha256'])
        inspection.check()
        for owner in resources: owner.check()
        if workspace.failed or workspace.uncertain: raise ValueError('Original runtime graph is failed/uncertain')
        value = {'schema_version': 1, 'kind': 'foundation-original-raw-windows-runtime-evidence-v1',
            'scope': 'original-raw-candidate-document-render-service-observations-only',
            'subject': copy.deepcopy(subject), 'harness_build': build,
            'provider': copy.deepcopy(provider_reference), 'package': copy.deepcopy(package_reference),
            'package_index_offset': package_index_offset, 'package_index_length': package_index_length,
            'observations': observed, 'stage': stage, 'original_log': log,
            'initial_deadline': deadline, 'engine_execution': True,
            'production_eligible': False, 'native_runtime_qualified': False,
            'instruction_floor_verified': False, 'sdk_eligible': False, 'kernel_rebuild': False,
            'unrun': ['full-native-runtime-contract', 'cpu-floor-and-dispatch', 'private-loader-conflict-matrix',
                'retained-native-sdk-admission', 'release-platform-qualification']}
        row = workspace.commit_receipt_new('runtime-evidence.json', encoded(value))
        _close_lifecycle_graph(inspection, workspace, resources)
        token = object.__new__(_OriginalWindowsRuntimeObservation)
        _RAW_OBSERVATIONS[token] = dict(value, reference=dict(path=workspace.output + '/runtime-evidence.json',
            sha256=row['sha256'], bytes=row['bytes']), closure='all-original-workspace-input-and-source-owners-closed')
        return token
    except BaseException as error:
        _retain_lifecycle_graph(inspection, workspace, resources, error)
        raise


RUNTIME_REQUEST_KIND = 'foundation-raw-windows-runtime-maintenance-request-v1'


def _runtime_request(value):
    contract.fields(value, ('schema_version', 'kind', 'selection', 'source_replay',
        'input_qualification', 'publication', 'retained_dependency', 'retained_originals',
        'generic_manifest', 'provider', 'package', 'package_index_offset',
        'package_index_length', 'harness_build_output_root', 'runtime_output_root'),
        'raw Windows runtime maintenance request')
    if (type(value['schema_version']) is not int or value['schema_version'] != 1 or
            value['kind'] != RUNTIME_REQUEST_KIND):
        raise ValueError('Unsupported raw Windows runtime maintenance request')
    for name in ('selection', 'source_replay', 'input_qualification', 'publication',
                 'retained_dependency', 'retained_originals', 'generic_manifest', 'provider', 'package'):
        if value[name] is None:
            raise contract.MissingInputs([_missing('windows-runtime-original-' + name,
                'explicit retained original input', 'a genuine independently pinned original is required')])
        _reference(value[name], 'raw runtime ' + name)
    for name in ('package_index_offset', 'package_index_length'):
        _integer(value[name], name, 1, 4 * 1024 * 1024)
    outputs = [contract.windows_path(value[name], name)
               for name in ('harness_build_output_root', 'runtime_output_root')]
    paths = [PureWindowsPath(path) for path in outputs]
    if paths[0] == paths[1] or paths[0] in paths[1].parents or paths[1] in paths[0].parents:
        raise ValueError('Harness-build and runtime output roots must be disjoint')
    return copy.deepcopy(value)


def _runtime_open_graph(request, request_reference, selection, input_qualification,
                        dependency_admission, output, *, deadline):
    """Acquire current exact inputs before one fresh actual Workspace.

    The returned graph transfers to exactly one runtime kernel. Until transfer,
    this function and its caller close known owners or retain the entire graph.
    """
    _lifecycle_time(deadline)
    inspection = workspace = None
    resources = []
    creating = False
    try:
        inspection, api, _source_facts = _capture_source_adapter(selection,
            request['source_replay'], input_qualification=input_qualification, deadline=deadline)
        held = _HeldLifecycleInputs(api, input_qualification, deadline)
        resources.append(held)
        if _runtime_request(_lifecycle_json(held.reference(request_reference))) != request:
            raise ValueError('Held original runtime request changed after initial selection')
        if validate_selection(_lifecycle_json(held.reference(request['selection']))) != selection:
            raise ValueError('Held original runtime selection changed after initial selection')
        admission = _lifecycle_json(held.reference(selection['admission']))
        contract.fields(admission.get('inventories'), INVENTORY_ROLES,
                        'complete current runtime admission inventories')
        for role in sorted(INVENTORY_ROLES):
            held.inventory(admission['inventories'][role], role)
        import appended_engine_windows_handoff as handoff_tool
        handoff = handoff_tool.verify_handoff(selection['handoff']['root'],
                                               selection['handoff']['sha256'])
        _require_dependency_admission(dependency_admission,
            {'native_inputs': handoff['native_inputs']}, handoff, held, admission, retained=True)
        admitted = _admission(admission, handoff)
        _controller_lifecycle_python(admitted)
        runtime_paths = _isolated_probe_paths(admitted)
        if (any(type(path) is not str or not path for path in sys.path) or
                [PureWindowsPath(path).as_posix() for path in sys.path] != runtime_paths):
            raise ValueError('Actual isolated maintenance runtime has an unheld or foreign import path')
        qualification = _publication_qualification(api, request['publication'])
        _lifecycle_cap_admission(api, qualification)
        subject = {'handoff': copy.deepcopy(selection['handoff']),
            'source_replay': copy.deepcopy(request['source_replay']),
            'admission': copy.deepcopy(selection['admission']),
            **{name: handoff[name] for name in
               ('recipe_sha256', 'provider_build_sha256', 'toolchain_identity_sha256')}}
        protected = [request_reference['path'], *[request[name]['path'] for name in
            ('selection', 'source_replay', 'input_qualification', 'publication',
             'retained_dependency', 'retained_originals', 'generic_manifest', 'provider', 'package')],
            selection['handoff']['root'], selection['admission']['path'],
            *[owner.root for owner in held.owners]]
        # Source-owned bootstrap rows are actual verified raw-code observations;
        # keep those exact files held until every resulting command has joined.
        for reference in _runtime_bootstrap_source_references():
            held.reference(reference)
            protected.append(reference['path'])
        other = request['runtime_output_root'] if output == request['harness_build_output_root'] else request['harness_build_output_root']
        protected.append(other)
        environment = native_environment(admitted, output)
        inspection.check(); held.check(); _lifecycle_time(deadline)
        creating = True
        workspace = api.Workspace.create_new(output,
            protected_paths=list(dict.fromkeys(protected)), limits=selection['phase_limits'],
            qualification=qualification)
        creating = False
        return {'api': api, 'inspection': inspection, 'workspace': workspace,
            'resources': resources, 'subject': subject,
            'environment': environment, 'admitted': admitted}
    except BaseException as error:
        if (creating or isinstance(error, process_tree.ProcessTreeError) or
                getattr(workspace, 'uncertain', False) or
                any(getattr(owner, 'uncertain', False) for owner in resources)):
            _retain_lifecycle_graph(inspection, workspace, resources, error)
        else:
            _close_lifecycle_graph(inspection, workspace, resources)
        raise


def _runtime_maintenance(request_path, pin):
    """Reachable fixed-input source path; no user-supplied API or callback."""
    require_native_host()
    entered = time.monotonic()
    if not (sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode):
        raise ValueError('Raw Windows runtime maintenance requires Python -I -S -B')
    request_reference = {'path': contract.windows_path(os.fspath(request_path),
        'original runtime request'), 'sha256': contract.pin(pin, 'original runtime request')}
    request = _runtime_request(_document(request_reference['path'], request_reference['sha256']))
    selection = validate_selection(_document(request['selection']['path'], request['selection']['sha256']))
    limits = validate_limits(selection['phase_limits'])
    # The one absolute deadline starts at entry and covers both separate Jobs,
    # all original reconstructions, every reader and every final close.
    deadline = _lifecycle_deadline(limits, entered)
    _lifecycle_time(deadline)
    replay = _runtime_source_provider()
    input_qualification = replay.admit_native_input_qualification(request['input_qualification'])
    dependency_admission = _shared_dependency_api('admit_retained_dependency_with_probe')(
        request['retained_dependency'], overall_deadline=deadline)
    generic_originals = _shared_dependency_api('admit_retained_originals')(
        request['retained_originals'], deadline=deadline, limits=_lifecycle_input_limits(deadline))
    _lifecycle_time(deadline)
    source_root = _runtime_maintained_source_root()
    source_pins = copy.deepcopy(_RAW_RUNTIME_SOURCE_PINS)
    build_graph = _runtime_open_graph(request, request_reference, selection,
        input_qualification, dependency_admission, request['harness_build_output_root'], deadline=deadline)
    # Kernel takes the entire actual graph. It closes all owners before issuance;
    # any unknown outcome retains it and this caller never retries/closes again.
    harness = _build_windows_runtime_harness(api=build_graph['api'], input_qualification=input_qualification,
        inspection=build_graph['inspection'], workspace=build_graph['workspace'],
        source_root=source_root, source_pins=source_pins,
        generic_manifest=request['generic_manifest'], toolchain_reference=None,
        cmake=build_graph['admitted']['programs']['cmake'], dependency_admission=dependency_admission,
        generic_originals=generic_originals, publication=request['publication'],
        subject=build_graph['subject'], environment=build_graph['environment'],
        limits=limits, resources=build_graph['resources'], deadline=deadline)
    _lifecycle_time(deadline)
    runtime_graph = _runtime_open_graph(request, request_reference, selection,
        input_qualification, dependency_admission, request['runtime_output_root'], deadline=deadline)
    token = _observe_windows_candidate_runtime(api=runtime_graph['api'], input_qualification=input_qualification,
        inspection=runtime_graph['inspection'], workspace=runtime_graph['workspace'], harness_build=harness,
        provider_reference=request['provider'], package_reference=request['package'],
        package_index_offset=request['package_index_offset'], package_index_length=request['package_index_length'],
        dependency_admission=dependency_admission, generic_originals=generic_originals,
        publication=request['publication'], subject=runtime_graph['subject'],
        environment=runtime_graph['environment'], limits=limits,
        resources=runtime_graph['resources'], deadline=deadline)
    return _require_original_windows_runtime(token)


def _runtime_source_provider():
    dependencies = _dependency_entry()
    return dependencies._module('retained_dependency')._issuer().originals_module()._capture_source_provider()


def _runtime_maintained_source_root():
    return (ROOT / 'tools/appended_engine_windows_dependency_support/raw_runtime').as_posix()


def _runtime_bootstrap_source_references():
    # The actual maintained controller contains its lifecycle/runtime code.
    # Literal project helper sources remain physically held through all joins.
    return [{'path': (ROOT / name).as_posix(), 'sha256': digest(_read(ROOT / name))}
            for name in _prototype_helper_closure(ROOT)]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('plan', 'build', 'inspect-provider', 'runtime'))
    parser.add_argument('--request', type=Path)
    parser.add_argument('--request-sha256')
    parser.add_argument('--selection', type=Path)
    parser.add_argument('--selection-sha256')
    parser.add_argument('--provider', type=Path)
    parser.add_argument('--provider-sha256')
    for option in ('source-replay', 'input-qualification', 'publication', 'dependency-admission'):
        parser.add_argument('--' + option, type=Path)
        parser.add_argument('--' + option + '-sha256')
    args = parser.parse_args(argv)
    if args.action == 'runtime':
        if (args.request is None or args.request_sha256 is None or
                any(getattr(args, name) is not None for name in
                    ('selection', 'selection_sha256', 'provider', 'provider_sha256',
                     'source_replay', 'source_replay_sha256', 'input_qualification',
                     'input_qualification_sha256', 'publication', 'publication_sha256',
                     'dependency_admission', 'dependency_admission_sha256'))):
            parser.error('runtime requires only --request and --request-sha256')
        result = _runtime_maintenance(args.request, args.request_sha256)
        print(encoded(result).decode('ascii'), end='')
        return 0
    if args.request is not None or args.request_sha256 is not None:
        parser.error('--request and --request-sha256 select only runtime')
    references = {}
    for option in ('source_replay', 'input_qualification', 'publication', 'dependency_admission'):
        path, selected_pin = getattr(args, option), getattr(args, option + '_sha256')
        if (path is None) != (selected_pin is None):
            parser.error('--' + option.replace('_', '-') + ' and its SHA256 must be selected together')
        references[option] = (None if path is None else {
            'path': PureWindowsPath(os.fspath(path)).as_posix(), 'sha256': selected_pin})
    if args.action == 'inspect-provider':
        if args.provider is None or args.provider_sha256 is None or args.selection is not None or args.selection_sha256 is not None or any(references.values()):
            parser.error('inspect-provider requires only --provider and --provider-sha256')
        result = inspect_provider(_read(args.provider, args.provider_sha256, maximum=MAX_BINARY))
    else:
        if args.selection is None or args.selection_sha256 is None or args.provider is not None or args.provider_sha256 is not None:
            parser.error('plan/build require only --selection and --selection-sha256')
        if args.action == 'plan':
            if any(references.values()):
                parser.error('plan consumes only selection metadata; original admission references select build')
            result = create_plan(args.selection, args.selection_sha256)
        else:
            result = build(args.selection, args.selection_sha256,
                source_replay=references['source_replay'],
                input_qualification=references['input_qualification'],
                publication=references['publication'],
                dependency_reference=references['dependency_admission'])
    print(encoded(result).decode('ascii'), end='')
    return 0


def cli(argv=None):
    try:
        return main(argv)
    except contract.MissingInputs as error:
        result = error.as_dict(); result['scope'] = SCOPE
        result.update({name: False for name in FALSE_FACTS})
        print(encoded(result).decode('ascii'), file=sys.stderr, end='')
        return 2
    except (ValueError, OSError, process_tree.ProcessTreeError) as error:
        print('Windows engine candidate: ' + str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(cli())
