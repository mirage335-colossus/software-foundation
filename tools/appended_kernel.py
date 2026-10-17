#!/usr/bin/env python3
"""Explicit initial native-kernel finalization; never compiles or reseals a kernel.

Run after installation and stripping, before hashing or appending. This producer
adds ELF load-page padding and writes the reserved boundary once. The retained
composer is a separate operation and never calls this producer implicitly.
"""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import stat
import struct
import sys

from appended_container import (ContainerError, MAX_INDEX, MAX_KERNEL, STAMP_MAGIC,
                                _native, _ordinary_path, _recheck, _snapshot, _write_new,
                                canonical_json, parse_artifact, validate_descriptor)


DIAGNOSTICS_SERVICE = 'foundation.diagnostics'
DIAGNOSTICS_SCHEMA = 'aed2a35d3cb1625b2ab40032c853bd98a13ac3cb5705427b4a3c8209e0c05810'


class KernelError(ValueError):
    """The explicit initial producer cannot establish the declared kernel."""


def _range(offset, size, length, label):
    if offset > length or size > length - offset:
        raise KernelError('invalid ' + label + ' bounds')


def _elf_layout(data):
    if (len(data) < 52 or data[:4] != b'\x7fELF' or data[4] not in (1, 2) or
            data[5] not in (1, 2) or data[6] != 1):
        raise KernelError('input is not a supported ELF executable')
    endian = '<' if data[5] == 1 else '>'
    is64 = data[4] == 2
    header_format = endian + ('HHIQQQIHHHHHH' if is64 else 'HHIIIIIHHHHHH')
    if len(data) < 16 + struct.calcsize(header_format):
        raise KernelError('truncated ELF header')
    header = struct.unpack_from(header_format, data, 16)
    phoff, phsize, phcount = header[4], header[8], header[9]
    phformat = endian + ('IIQQQQQQ' if is64 else 'IIIIIIII')
    if header[0] not in (2, 3) or not 1 <= phcount <= 4096 or phsize != struct.calcsize(phformat):
        raise KernelError('invalid ELF executable program headers')
    _range(phoff, phcount * phsize, len(data), 'ELF program-header table')
    required = len(data)
    readonly = []
    loads = 0
    for i in range(phcount):
        ph = struct.unpack_from(phformat, data, phoff + i * phsize)
        if ph[0] != 1:
            continue
        loads += 1
        offset, size, memory, flags, align = ((ph[2], ph[5], ph[6], ph[1], ph[7]) if is64
                                            else (ph[1], ph[4], ph[5], ph[6], ph[7]))
        _range(offset, size, len(data), 'ELF load extent')
        if size > memory or align > 1 << 30 or align and align & (align - 1):
            raise KernelError('invalid ELF load alignment or memory size')
        rounding = max(4096, align)
        required = max(required, ((offset + size + rounding - 1) // rounding) * rounding)
        if flags & 4 and not flags & 2:
            readonly.append((offset, size))
    if not loads:
        raise KernelError('ELF executable has no loadable segments')
    return required, readonly


def _pe_layout(data):
    if len(data) < 64 or data[:2] != b'MZ':
        raise KernelError('input is not a supported PE executable')
    offset = struct.unpack_from('<I', data, 60)[0]
    _range(offset, 24, len(data), 'PE header')
    if data[offset:offset + 4] != b'PE\0\0':
        raise KernelError('invalid PE signature')
    _, count, _, _, _, optional_size, flags = struct.unpack_from('<HHIIIHH', data, offset + 4)
    if not flags & 2 or flags & 0x2000 or not 1 <= count <= 96:
        raise KernelError('input must be a PE executable, not a DLL')
    optional = offset + 24
    _range(optional, optional_size, len(data), 'PE optional header')
    if optional_size < 2:
        raise KernelError('truncated PE optional header')
    magic = struct.unpack_from('<H', data, optional)[0]
    directories_offset = 96 if magic == 0x10b else 112 if magic == 0x20b else 0
    if not directories_offset or optional_size < directories_offset:
        raise KernelError('unsupported PE optional header')
    directories = struct.unpack_from('<I', data, optional + directories_offset - 4)[0]
    if directories > 16 or directories * 8 > optional_size - directories_offset:
        raise KernelError('invalid PE directory bounds')
    if directories > 4 and any(struct.unpack_from('<II', data, optional + directories_offset + 32)):
        raise KernelError('signed PE input is unsupported; finalize an unsigned kernel')
    sections = optional + optional_size
    _range(sections, count * 40, len(data), 'PE section table')
    readonly = []
    for i in range(count):
        section = sections + 40 * i
        size, position = struct.unpack_from('<II', data, section + 16)
        characteristics = struct.unpack_from('<I', data, section + 36)[0]
        _range(position, size, len(data), 'PE section')
        if characteristics & 0x40000000 and not characteristics & 0x80000000:
            readonly.append((position, size))
    return len(data), readonly


def seal_bytes(data, carrier=None):
    """Return (sealed bytes, carrier, stamp offset) from one unsealed executable.

    No executable prefix or presumed legacy base is reconstructed. The complete
    input is retained, apart from its designated initially zero boundary field.
    """
    if type(data) is not bytes or not 1 <= len(data) <= MAX_KERNEL:
        raise KernelError('kernel input must be bounded immutable bytes')
    detected = 'elf' if data.startswith(b'\x7fELF') else 'pe' if data.startswith(b'MZ') else None
    if detected is None or carrier is not None and carrier != detected:
        raise KernelError('kernel carrier is unsupported or disagrees with the input')
    if data.count(STAMP_MAGIC) != 1:
        raise KernelError('kernel needs exactly one reserved initial boundary stamp; legacy inputs are not sealable')
    stamp = data.index(STAMP_MAGIC)
    _range(stamp, 16, len(data), 'boundary stamp')
    if data[stamp + 8:stamp + 16] != bytes(8):
        raise KernelError('kernel is already sealed; retain its descriptor instead of resealing or rebuilding')
    required, readonly = (_elf_layout(data) if detected == 'elf' else _pe_layout(data))
    if required > MAX_KERNEL:
        raise KernelError('finalized ELF load-page padding exceeds the kernel limit')
    if not any(start <= stamp and stamp - start + 16 <= size for start, size in readonly):
        raise KernelError('boundary stamp must be wholly inside readable immutable native data')
    result = bytearray(data)
    result.extend(bytes(required - len(data)))
    struct.pack_into('<Q', result, stamp + 8, len(result))
    finalized = bytes(result)
    _native(finalized, detected, stamp)
    return finalized, detected, stamp


def _json_object(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise KernelError('duplicate provenance JSON key')
            result[key] = value
        return result
    path = Path(path)
    if path.stat().st_size > 16 * 1024 * 1024:
        raise KernelError('producer provenance exceeds the 16 MiB input limit')
    value = json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=unique)
    if type(value) is not dict:
        raise KernelError('producer provenance must be a JSON object')
    return value


def _new_destination(path):
    path = Path(path).absolute()
    if os.path.lexists(path):
        raise KernelError('kernel output destination must be new: ' + str(path))
    return path


def _bind_output_parents(path):
    """Create only ordinary output directories and retain their physical IDs.

    Directory timestamps change when staging files, so retain device, inode and
    mode. As with the shared composer publisher, concurrent bypassing writers
    require filesystem exclusion under the repository coordination policy.
    """
    result = []
    for parent in reversed(tuple(path.parents)):
        try:
            state = parent.lstat()
        except FileNotFoundError:
            parent.mkdir()
            state = parent.lstat()
        if not stat.S_ISDIR(state.st_mode):
            raise KernelError('kernel output parents must be ordinary nonlinked directories: ' + str(parent))
        result.append((parent, (state.st_dev, state.st_ino, state.st_mode)))
    return tuple(result)


def _recheck_output_parents(bindings):
    for parent, expected in bindings:
        state = parent.lstat()
        if not stat.S_ISDIR(state.st_mode) or (state.st_dev, state.st_ino, state.st_mode) != expected:
            raise KernelError('kernel output parent changed before publication: ' + str(parent))
    _ordinary_path(bindings[-1][0], directory=True)


def seal(input_path, output, descriptor_path, source_root, provenance, carrier=None, *,
         services=None, capabilities=()):
    """Finalize an explicit producer input into fresh kernel/descriptor outputs.

    Caller-supplied build evidence is retained verbatim. Source observed during
    sealing is recorded separately and does not pretend to authenticate the
    compiler, prove a source-to-binary relationship or grant release certification.
    """
    from appended_policy import kernel_source_tree
    from source_identity import ignored_source_path, source_tree

    output, descriptor_path = _new_destination(output), _new_destination(descriptor_path)
    if output.resolve(strict=False) == descriptor_path.resolve(strict=False):
        raise KernelError('kernel and descriptor destinations must differ')
    source_root = Path(source_root).resolve(strict=True)
    for destination in (output, descriptor_path):
        resolved = destination.resolve(strict=False)
        if source_root in resolved.parents:
            name = resolved.relative_to(source_root).as_posix()
            if not ignored_source_path(name):
                raise KernelError('kernel outputs must be outside source inputs or under ignored build/ or .agent-work/')
    output_parents = _bind_output_parents(output)
    descriptor_parents = _bind_output_parents(descriptor_path)
    original_input = _snapshot(input_path, MAX_KERNEL)
    if type(provenance) is not dict or 'sealing' in provenance:
        raise KernelError('producer provenance must be an object without a reserved sealing field')
    if (services is not None and not isinstance(services, (tuple, list)) or
            not isinstance(capabilities, (tuple, list)) or
            any(not isinstance(name, str) for name in (services or ())) or
            any(not isinstance(name, str) for name in capabilities)):
        raise KernelError('compiled service and capability declarations must be lists of names')
    declared_services = sorted(set(services if services is not None else (DIAGNOSTICS_SERVICE,)) |
                               {'foundation.kernel'})
    declared_capabilities = sorted(set(capabilities))
    before = original_input.content
    finalized, detected, stamp = seal_bytes(before, carrier)
    full_source = source_tree(source_root)
    kernel_inputs = kernel_source_tree(source_root)
    original_provenance = copy.deepcopy(provenance)
    evidence = copy.deepcopy(provenance)
    evidence['sealing'] = {
        'operation': 'explicit-initial-native-boundary-v1',
        'qualification': 'unqualified-development',
        'input_sha256': hashlib.sha256(before).hexdigest(),
        'source_observed_at_seal_sha256': full_source['tree_sha256'],
        'source_binding': 'caller-declared-build-inputs; sealing is not source-to-binary certification',
    }
    descriptor = {
        'schema_version': 1, 'kind': 'foundation-kernel', 'carrier': detected,
        'profile': 'binary', 'append_format': 1, 'abi': {'major': 1, 'minor': 0},
        'capabilities': declared_capabilities, 'services': declared_services,
        'executable': {'length': len(finalized), 'sha256': hashlib.sha256(finalized).hexdigest()},
        'boundary_offset': stamp, 'provenance': evidence, 'kernel_inputs': kernel_inputs,
    }
    validate_descriptor(descriptor)
    parse_artifact(finalized, descriptor)
    encoded = canonical_json(descriptor)
    if len(encoded) > MAX_INDEX:
        raise KernelError('kernel descriptor exceeds the consumer 4 MiB limit')
    _recheck(original_input)
    if (source_tree(source_root) != full_source or kernel_source_tree(source_root) != kernel_inputs or
            provenance != original_provenance):
        raise KernelError('kernel, source or provenance inputs changed during sealing')
    _recheck_output_parents(output_parents)
    _recheck_output_parents(descriptor_parents)

    def verify_kernel(data):
        _recheck_output_parents(output_parents)
        _recheck_output_parents(descriptor_parents)
        parse_artifact(data, descriptor)

    # All validation precedes either publication. A racing destination still
    # fails exclusively, preserving the other writer's complete bytes.
    _write_new(output, finalized, [original_input], original_input.mode, verify_kernel)
    _write_new(descriptor_path, encoded, [original_input], 0o644,
               lambda _: _recheck_output_parents(descriptor_parents))
    return descriptor


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('seal',))
    parser.add_argument('--input', type=Path, required=True, help='newly compiled/installed unsealed kernel')
    parser.add_argument('--output', type=Path, required=True, help='fresh finalized immutable kernel path')
    parser.add_argument('--descriptor', type=Path, required=True, help='fresh kernel.json path')
    parser.add_argument('--source-root', type=Path, required=True, help='producer-declared kernel build source')
    parser.add_argument('--carrier', choices=('elf', 'pe'))
    parser.add_argument('--service', action='append', help='compiled service inventory; overrides console diagnostics default (bootstrap is always included)')
    parser.add_argument('--capability', action='append', default=[], help='compiled generic capability inventory; repeat as needed')
    evidence = parser.add_mutually_exclusive_group(required=True)
    evidence.add_argument('--provenance', type=Path, help='retained original build provenance JSON object')
    evidence.add_argument('--developer-unqualified', action='store_true', help='explicit local-development evidence without certification')
    args = parser.parse_args(argv)
    try:
        provenance = (_json_object(args.provenance) if args.provenance else
                      {'build_origin': 'local-development', 'qualification': 'unqualified',
                       'build_evidence': 'caller-declared; no release certificate'})
        descriptor = seal(args.input, args.output, args.descriptor, args.source_root, provenance, args.carrier,
                          services=args.service, capabilities=args.capability)
        print(json.dumps({'kernel': str(args.output), 'descriptor': str(args.descriptor),
                          'kernel_sha256': descriptor['executable']['sha256'],
                          'descriptor_sha256': hashlib.sha256(canonical_json(descriptor)).hexdigest()}, sort_keys=True))
        return 0
    except (KernelError, ContainerError, ValueError, OSError) as error:
        print('kernel-seal: ' + str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
