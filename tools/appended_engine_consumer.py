#!/usr/bin/env python3
"""Inspect pinned neutral-engine inputs without building, loading or qualifying them.

Stage A remains a complete retained-byte integrity format. This additive reader
checks a prospective copied-provider contract and preserves original runtime
evidence identities. It never executes that evidence or an engine factory.
"""
import argparse
from dataclasses import dataclass, fields as dataclass_fields
import hashlib
import json
from pathlib import Path
import re
import tarfile
from types import MappingProxyType

import appended_engine_manifest as manifest
import appended_engine_sdk as sdk
from dependency_archive import encoded

ROOT = Path(__file__).resolve().parents[1]
SCOPE = 'retained-consumer-byte-and-static-contract-only'
EMBEDDED_SCOPE = 'embedded-retained-consumer-byte-and-static-contract-only'
PROOF_KIND = 'foundation-neutral-engine-provider-proof-v1'
BUILD_KIND = 'foundation-neutral-engine-provider-build-v1'
RUNTIME_KIND = 'foundation-neutral-engine-runtime-evidence-v1'
BINDING = 'copied-owner-bridge/direct-worker-v1'
PHYSICAL_BINDING = 'copied-owner-bridge/direct-worker-physical-v1'
PHYSICAL_PROOF_KIND = 'foundation-neutral-engine-provider-physical-proof-v1'
PHYSICAL_BUILD_KIND = 'foundation-neutral-engine-provider-physical-build-v1'
PHYSICAL_RUNTIME_KIND = 'foundation-neutral-engine-physical-runtime-evidence-v1'
BRIDGE_ABI = 0x00010000
CAPABILITIES = '259'
PHYSICAL_CAPABILITIES = '467'
COMMAND_CATALOG_SHA256 = 'd244e6a17561b49b937ad25058f2d662f4f86063633b716bdb87d0250796a47b'
MAX_COMMAND_CATALOG_BYTES = 64 * 1024
PHYSICAL_PROFILE_FACTS = MappingProxyType({
    'command_catalog_sha256': COMMAND_CATALOG_SHA256,
    'surface_protocol_version': 1, 'surface_capabilities': '8225',
    'mouse_input_version': 1, 'key_mapping_version': 1,
    'viewport_width': 800, 'viewport_height': 600, 'display_scale': 1,
})
RUNTIME_CHECKS = ('factory-inert', 'copied-describe', 'offline-entry-resource-load',
                  'native-service-result-and-ack', 'outside-engine-owner-pump',
                  'opaque-raster-frame', 'worker-failure-close', 'separate-heaps-copied-bridge')
PHYSICAL_INPUT_CHECKS = ('raw-key-location-altgraph', 'mouse-five-buttons-context-cancel',
                         'input-context-navigation-retirement', 'native-effect-input-admission')
PHYSICAL_RUNTIME_CHECKS = RUNTIME_CHECKS + PHYSICAL_INPUT_CHECKS
_PROFILE_FIELDS = ('schema_version', 'kind', 'target', 'binding', 'pointer_bits', 'pthread',
                   'shared_memory', 'bridge_abi', 'capabilities', 'contract_sha256',
                   'build_sha256', 'source_recipe_sha256')
_EVIDENCE_FIELDS = ('binary_manifest', 'source_manifest', 'recipe', 'proof', 'provider_build', 'runtime', 'reports')


class ConsumerError(ValueError):
    """The selected retained input cannot satisfy this consumer contract."""


def _fail(message):
    raise ConsumerError(message)


def _hash(data):
    return hashlib.sha256(data).hexdigest()


def _freeze(value):
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value


def _thaw(value):
    if hasattr(value, 'items'):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value


@dataclass(frozen=True)
class ConsumerLimits:
    max_factory_bytes: int = 16 * 1024 * 1024
    max_wasm_bytes: int = 256 * 1024 * 1024
    max_data_member_bytes: int = 64 * 1024 * 1024
    max_data_total_bytes: int = 128 * 1024 * 1024
    max_notice_bytes: int = 4 * 1024 * 1024
    max_notices_total_bytes: int = 16 * 1024 * 1024
    max_data_files: int = 128
    max_notices: int = 128
    max_reports_total_bytes: int = 32 * 1024 * 1024

    def __post_init__(self):
        for field in dataclass_fields(self):
            value = getattr(self, field.name)
            if type(value) is not int or value < 0:
                _fail('Invalid consumer limit: ' + field.name)
        if not self.max_factory_bytes or not self.max_wasm_bytes or not self.max_notice_bytes:
            _fail('Factory, Wasm and notice member limits must be positive')


@dataclass(frozen=True)
class ConsumerInspection:
    metadata: object
    assets: object
    notices: object
    evidence: object

    def as_dict(self):
        return _thaw(self.metadata)


class _Reader:
    def __init__(self, data):
        self.data = memoryview(data)
        self.position = 0

    def take(self, count):
        if count < 0 or count > len(self.data) - self.position:
            _fail('Truncated Wasm section')
        start = self.position
        self.position += count
        return self.data[start:self.position]

    def byte(self):
        return self.take(1)[0]

    def unsigned(self, bits=32):
        value = 0
        count = (bits + 6) // 7
        for index in range(count):
            part = self.byte()
            if index == count - 1 and part >= 1 << (bits - index * 7):
                _fail('Invalid Wasm unsigned LEB')
            value |= (part & 127) << (index * 7)
            if not part & 128:
                if index and part == 0:
                    _fail('Noncanonical Wasm unsigned LEB')
                return value
        _fail('Unterminated Wasm unsigned LEB')

    def signed(self, bits):
        # Initializer payload is inspected only for supported constant syntax.
        for index in range((bits + 6) // 7):
            part = self.byte()
            if not part & 128:
                return
        _fail('Unterminated Wasm signed initializer LEB')

    def name(self):
        size = self.unsigned()
        if size > 65536:
            _fail('Wasm name exceeds inspection limit')
        try:
            return bytes(self.take(size)).decode('utf-8')
        except UnicodeError as error:
            raise ConsumerError('Invalid Wasm UTF-8 name') from error

    def count(self):
        count = self.unsigned()
        if count > len(self.data) - self.position:
            _fail('Wasm vector count exceeds remaining section bytes')
        return count

    def end(self):
        if self.position != len(self.data):
            _fail('Unexpected trailing Wasm section bytes')


_VALUES = {0x7f: 'i32', 0x7e: 'i64', 0x7d: 'f32', 0x7c: 'f64',
           0x7b: 'v128', 0x70: 'funcref', 0x6f: 'externref'}


def _value(reader):
    value = reader.byte()
    if value not in _VALUES:
        _fail('Unsupported Wasm value type inspection; reviewed inspector maintenance required')
    return _VALUES[value]


def _limits(reader, memory=False):
    flags = reader.unsigned()
    if flags & ~(7 if memory else 1):
        _fail('Unsupported Wasm limits flags')
    memory64 = bool(flags & 4)
    minimum = reader.unsigned(64 if memory64 else 32)
    maximum = reader.unsigned(64 if memory64 else 32) if flags & 1 else None
    if maximum is not None and minimum > maximum:
        _fail('Invalid Wasm memory/table bounds')
    result = {'minimum': minimum, 'maximum': maximum}
    if memory:
        result.update(shared=bool(flags & 2), memory64=memory64)
        if result['shared'] and maximum is None:
            _fail('Shared Wasm memory requires a maximum')
    return result


def _table(reader):
    element = _value(reader)
    if element not in ('funcref', 'externref'):
        _fail('Invalid Wasm table element type')
    return {'element': element, **_limits(reader)}


def _global(reader):
    value, mutable = _value(reader), reader.byte()
    if mutable not in (0, 1):
        _fail('Invalid Wasm global mutability')
    return {'value': value, 'mutable': bool(mutable)}


def _initializer(reader):
    while True:
        operation = reader.byte()
        if operation == 0x0b:
            return
        if operation in (0x41, 0x42):
            reader.signed(32 if operation == 0x41 else 64)
        elif operation in (0x43, 0x44):
            reader.take(4 if operation == 0x43 else 8)
        elif operation in (0x23, 0xd2):
            reader.unsigned()
        elif operation == 0xd0:
            if _value(reader) not in ('funcref', 'externref'):
                _fail('Unsupported Wasm reference initializer')
        else:
            _fail('Unsupported Wasm initializer inspection; reviewed inspector maintenance required')


def scan_wasm(data):
    """Read actual imports/exports/types/memory; never validate/execute bodies."""
    if type(data) is not bytes or data[:8] != b'\0asm\1\0\0\0':
        _fail('Invalid engine Wasm header')
    outer = _Reader(data)
    outer.take(8)
    sections, previous = {}, 0
    order = {value: index + 1 for index, value in enumerate((1, 2, 3, 4, 5, 13, 6, 7, 8, 9, 12, 10, 11))}
    while outer.position < len(outer.data):
        section = outer.byte()
        content = outer.take(outer.unsigned())
        if section == 0:
            continue
        if section not in order or section in sections or order[section] <= previous:
            _fail('Duplicate, unknown or out-of-order Wasm section')
        previous = order[section]
        sections[section] = content
    types, functions, tables, memories, globals_, tags, imports = [], [], [], [], [], [], []
    def reader(section):
        return _Reader(sections.get(section, b'\0'))
    r = reader(1)
    for _ in range(r.count()):
        if r.byte() != 0x60:
            _fail('Unsupported Wasm type definition inspection')
        types.append({'parameters': [_value(r) for _ in range(r.count())],
                      'results': [_value(r) for _ in range(r.count())]})
    r.end()
    def signature(index):
        if index >= len(types):
            _fail('Wasm function type index out of range')
        return types[index]
    def tag(r):
        if r.byte() != 0:
            _fail('Unsupported Wasm tag attribute')
        return signature(r.unsigned())
    r = reader(2)
    for _ in range(r.count()):
        module, name, kind = r.name(), r.name(), r.byte()
        if kind == 0:
            details = signature(r.unsigned()); functions.append(details); label = 'function'
        elif kind == 1:
            details = _table(r); tables.append(details); label = 'table'
        elif kind == 2:
            details = _limits(r, True); label = 'memory'
            memories.append({'imported': True, 'module': module, 'name': name, **details})
        elif kind == 3:
            details = _global(r); globals_.append(details); label = 'global'
        elif kind == 4:
            details = tag(r); tags.append(details); label = 'tag'
        else:
            _fail('Unsupported Wasm import kind')
        imports.append({'module': module, 'name': name, 'kind': label, 'details': details})
    r.end()
    r = reader(3)
    defined = r.count()
    for _ in range(defined):
        functions.append(signature(r.unsigned()))
    r.end()
    r = reader(4)
    for _ in range(r.count()):
        tables.append(_table(r))
    r.end()
    r = reader(5)
    for _ in range(r.count()):
        memories.append({'imported': False, 'module': None, 'name': None, **_limits(r, True)})
    r.end()
    r = reader(13)
    for _ in range(r.count()):
        tags.append(tag(r))
    r.end()
    r = reader(6)
    for _ in range(r.count()):
        globals_.append(_global(r)); _initializer(r)
    r.end()
    exports, names = [], set()
    r = reader(7)
    collections = (functions, tables, memories, globals_, tags)
    labels = ('function', 'table', 'memory', 'global', 'tag')
    for _ in range(r.count()):
        name, kind, index = r.name(), r.byte(), r.unsigned()
        if name in names or kind >= len(collections) or index >= len(collections[kind]):
            _fail('Duplicate Wasm export name or invalid export index/kind')
        names.add(name)
        details = collections[kind][index]
        if kind == 2:
            details = {key: details[key] for key in ('minimum', 'maximum', 'shared', 'memory64')}
        exports.append({'name': name, 'kind': labels[kind], 'index': index, 'details': details})
    r.end()
    start = None
    if 8 in sections:
        r = _Reader(sections[8]); start = r.unsigned(); r.end()
        if start >= len(functions):
            _fail('Wasm start function index out of range')
    r = reader(10)
    if r.count() != defined:
        _fail('Wasm function/code count differs')
    for _ in range(defined):
        r.take(r.unsigned())
    r.end()
    return {'imports': imports, 'exports': sorted(exports, key=lambda item: item['name']),
            'memories': memories, 'start': start}


def scan_factory(data):
    """Inspect dependency/export syntax, without claiming JS inertness proof."""
    if type(data) is not bytes:
        _fail('Factory must be owned bytes')
    try:
        source = data.decode('utf-8')
    except UnicodeError as error:
        raise ConsumerError('Invalid factory UTF-8') from error
    if '\0' in source:
        _fail('Invalid factory NUL')
    import browser_bundle
    marker = '$fe_meta$'
    if marker in source:
        _fail('Unsupported factory inspection marker collision')
    # Preserve code positions and let the existing lexical scanner distinguish
    # occurrences in comments/strings from actual nested import.meta.url syntax.
    masked = re.sub(r'(?<![\w$.])import\s*\.\s*meta\s*\.\s*url\b',
                    lambda match: marker + ' ' * (len(match[0]) - len(marker)), source)
    try:
        tokens = [word for _, word in browser_bundle._keywords(masked, all_tokens=True)]
    except ValueError as error:
        raise ConsumerError('Unsupported factory module syntax: ' + str(error)) from error
    if 'import' in tokens:
        _fail('Factory module dependencies/import.meta syntax are unsupported')
    exports = [index for index, word in enumerate(tokens) if word == 'export']
    if len(exports) != 1 or tokens[exports[0] + 1:exports[0] + 2] != ['default']:
        _fail('Factory requires exactly one ESM default export; CJS/reexports are ineligible')
    for index, word in enumerate(tokens):
        tail = tokens[index + 1:index + 4]
        if word == 'require' and tail[:1] == ['('] or word == 'module' and tail[:2] == ['.', 'exports']:
            _fail('CommonJS factory is ineligible')
        if word in ('callMain', 'doRun', '_main', 'main', 'bib_eval', '_bib_eval', 'bib_pump', '_bib_pump') and tail[:1] == ['(']:
            _fail('Diagnostic/auto-main factory entry is ineligible')
    if 'engine-pre.js' in source:
        _fail('Supplier diagnostic bootstrap is ineligible')
    return {'module_dependencies': [], 'default_export': True, 'import_meta_url': marker in tokens}


def _document(raw, label):
    if type(raw) is not bytes or len(raw) > manifest.MAX_MANIFEST:
        _fail('Invalid/oversized owned ' + label + ' document bytes')
    try:
        value = manifest.json_bytes(raw)
        # Stage A does not walk arbitrary strings; strict new documents do.
        encoded(value).decode('utf-8').encode('utf-8')
        def unicode_values(item):
            if isinstance(item, str):
                item.encode('utf-8')
            elif isinstance(item, list):
                for child in item: unicode_values(child)
            elif isinstance(item, dict):
                for key, child in item.items(): unicode_values(key); unicode_values(child)
        unicode_values(value)
        return value
    except (ValueError, UnicodeError, RecursionError) as error:
        raise ConsumerError('Invalid ' + label + ': ' + str(error)) from error


def _fields(value, names, label):
    try:
        return manifest.fields(value, names, label)
    except ValueError as error:
        raise ConsumerError(str(error)) from error


def _version(value, kind, label):
    if type(value['schema_version']) is not int or value['schema_version'] != 1 or value['kind'] != kind:
        _fail('Unsupported ' + label + ' kind/version')


def _target(target, paired_sdk):
    manifest.target_contract(target)
    manifest.sha256(paired_sdk, 'paired SDK')
    if target['system'] != 'Emscripten' or target['processor'] != 'wasm32':
        _fail('Only the retained browser wasm32 copied-owner consumer is implemented')


def _pins(pins):
    _fields(pins, ('recipe', 'manifest', 'proof', 'runtime'), 'independent consumer pins')
    for key, value in pins.items():
        manifest.sha256(value, key + ' independent pin')


def _member_bytes(mapping, path, files, maximum, label):
    manifest.path_name(path)
    if path not in mapping or path not in files:
        _fail('Missing inventoried ' + label + ': ' + path)
    raw = mapping[path]
    if type(raw) is not bytes or len(raw) > maximum:
        _fail('Oversized/unowned ' + label + ': ' + path)
    if _hash(raw) != files[path]:
        _fail(label + ' differs from pinned binary inventory: ' + path)
    return raw


def _reference(value, label):
    _fields(value, ('path', 'sha256'), label)
    manifest.path_name(value['path']); manifest.sha256(value['sha256'], label)
    return value['path']


def _production_eligible(runtime):
    return (runtime['scope'] == 'retained-neutral-provider-runtime' and runtime['status'] == 'passed'
            and all(item['status'] == 'passed' and bool(item['evidence']) for item in runtime['checks'].values()))


def _physical_mode(required_binding):
    if type(required_binding) is not str or required_binding not in (BINDING, PHYSICAL_BINDING):
        _fail('Unsupported required copied-owner binding')
    return required_binding == PHYSICAL_BINDING


def validate_engine_profile(profile, *, required_binding=BINDING):
    """Validate the explicit consumer's exact static profile; retain an owned copy.

    Build/recipe hashes have no execution meaning here. Full inspection also
    binds them to the independently pinned original documents.
    """
    physical = _physical_mode(required_binding)
    profile = _document(encoded(profile), 'engine copied profile')
    _fields(profile, _PROFILE_FIELDS + (tuple(PHYSICAL_PROFILE_FACTS) if physical else ()), 'engine copied profile')
    for name in ('contract_sha256', 'build_sha256', 'source_recipe_sha256'):
        manifest.sha256(profile[name], 'engine profile ' + name)
    expected = {'schema_version': 1, 'kind': 'foundation-copied-engine-physical-v1' if physical else 'foundation-copied-engine-v1',
                'target': 'browser-wasm32', 'binding': required_binding, 'pointer_bits': 32,
                'pthread': False, 'shared_memory': False, 'bridge_abi': BRIDGE_ABI,
                'capabilities': PHYSICAL_CAPABILITIES if physical else CAPABILITIES,
                'contract_sha256': _hash((ROOT / 'include/foundation/appended/engine_provider.h').read_bytes()),
                'build_sha256': profile['build_sha256'], 'source_recipe_sha256': profile['source_recipe_sha256']}
    if physical:
        expected.update(PHYSICAL_PROFILE_FACTS)
    if encoded(profile) != encoded(expected):
        _fail('Engine copied profile differs from exact selected consumer contract')
    return _freeze(profile)


def _command_catalog(proof, raw, binary, source, recipe):
    reference = proof['command_catalog']
    path = _reference(reference, 'physical command-catalog reference')
    if reference['sha256'] != COMMAND_CATALOG_SHA256:
        _fail('Physical command catalog differs from the approved byte identity')
    raw = _member_bytes({path: raw}, path, binary['files'], MAX_COMMAND_CATALOG_BYTES, 'physical command catalog')
    item = recipe['inputs'].get(path)
    if (_hash(raw) != COMMAND_CATALOG_SHA256 or source['files'].get(path) != COMMAND_CATALOG_SHA256
            or type(item) is not dict or item.get('sha256') != COMMAND_CATALOG_SHA256):
        _fail('Physical command catalog differs from original source/recipe inventory')
    if type(_document(raw, 'physical command catalog')) is not dict:
        _fail('Physical command catalog must be a JSON object')
    return path


def _inspect(evidence, assets, notices, pins, kernel_target, paired_sdk, required_binding, limits,
             group_files=None):
    # Freeze caller-owned mappings before checking or retaining any bytes. In
    # particular, never validate one report lookup and return a later lookup.
    if not all(hasattr(value, 'items') for value in (evidence, assets, notices, pins)):
        _fail('Expected owned consumer document/asset/notice/pin mappings')
    evidence, assets, notices, pins = (dict(value.items()) for value in (evidence, assets, notices, pins))
    if not hasattr(evidence.get('reports'), 'items'):
        _fail('Expected owned original runtime evidence files')
    evidence['reports'] = dict(evidence['reports'].items())
    kernel_target = _document(encoded(kernel_target), 'consumer target')
    _target(kernel_target, paired_sdk); _pins(pins)
    physical = _physical_mode(required_binding)
    limits = ConsumerLimits() if limits is None else limits
    if not isinstance(limits, ConsumerLimits):
        _fail('Expected explicit ConsumerLimits')
    evidence_fields = _EVIDENCE_FIELDS + (('command_catalog',) if physical else ())
    if not hasattr(evidence, 'items') or set(evidence) != set(evidence_fields):
        _fail('Invalid embedded consumer evidence fields')
    if not hasattr(assets, 'items') or not hasattr(notices, 'items'):
        _fail('Expected owned engine asset and notice mappings')
    for label in _EVIDENCE_FIELDS[:-1]:
        if type(evidence[label]) is not bytes or len(evidence[label]) > manifest.MAX_MANIFEST:
            _fail('Invalid/oversized owned ' + label + ' document bytes')
    if physical and (type(evidence['command_catalog']) is not bytes or len(evidence['command_catalog']) > MAX_COMMAND_CATALOG_BYTES):
        _fail('Invalid/oversized owned physical command catalog bytes')
    for label, pin in (('recipe', 'recipe'), ('binary_manifest', 'manifest'), ('proof', 'proof'), ('runtime', 'runtime')):
        if type(evidence[label]) is not bytes or _hash(evidence[label]) != pins[pin]:
            _fail('Independent ' + pin + ' pin mismatch')
    binary = _document(evidence['binary_manifest'], 'binary manifest')
    source = _document(evidence['source_manifest'], 'source manifest')
    recipe = _document(evidence['recipe'], 'recipe')
    manifest.binary_contract(binary)
    manifest.source_contract(source, recipe, pins['recipe'])
    source_hash = _hash(evidence['source_manifest'])
    manifest.verify_binding(binary, source, source_hash, recipe)
    if binary['recipe_id'] != pins['recipe'] or binary['target'] != kernel_target:
        _fail('Engine recipe/target differs from consumer selection')
    provider = binary['provider']
    canonical_header = _hash((ROOT / 'include/foundation/appended/engine_provider.h').read_bytes())
    if (provider['format'] != 'browser-module' or provider['binding'] != 'copied-owner-bridge'
            or type(provider['abi_major']) is not int or provider['abi_major'] != 1
            or type(provider['abi_minor']) is not int or provider['abi_minor'] != 0
            or provider['header_sha256'] != canonical_header):
        _fail('Engine requires actual canonical header, provider ABI1.0 and copied-owner binding')
    if binary['toolchain']['paired_sdk_sha256'] != paired_sdk:
        _fail('Engine paired SDK differs from consumer selection')
    proof = _document(evidence['proof'], 'provider proof')
    proof_fields = ('schema_version', 'kind', 'recipe_id', 'sources_sha256', 'provider_build',
                    'engine_profile', 'assets', 'wasm_facts', 'factory_policy', 'runtime_evidence')
    _fields(proof, proof_fields + (('command_catalog',) if physical else ()), 'provider proof')
    _version(proof, PHYSICAL_PROOF_KIND if physical else PROOF_KIND, 'provider proof')
    files = binary['files']
    proof_path = binary['build']['link_receipt']
    build_path = _reference(proof['provider_build'], 'provider-build reference')
    runtime_path = _reference(proof['runtime_evidence'], 'runtime-evidence reference')
    metadata_paths = (proof_path, build_path, runtime_path, provider['header'])
    if physical:
        metadata_paths += (_command_catalog(proof, evidence['command_catalog'], binary, source, recipe),)
    if len(set(metadata_paths)) != len(metadata_paths):
        _fail('Conflicting provider metadata/header roles')
    for path, raw, expected in ((proof_path, evidence['proof'], pins['proof']),
                               (build_path, evidence['provider_build'], proof['provider_build']['sha256']),
                               (runtime_path, evidence['runtime'], pins['runtime'])):
        if files.get(path) != expected or _hash(raw) != expected:
            _fail('Provider proof/build/runtime identity differs from inventoried bytes')
    if proof['runtime_evidence']['sha256'] != pins['runtime']:
        _fail('Independent runtime evidence pin mismatch')
    if proof['recipe_id'] != pins['recipe'] or proof['sources_sha256'] != source_hash:
        _fail('Provider proof source binding mismatch')
    build = _document(evidence['provider_build'], 'provider build')
    build_fields = ('schema_version', 'kind', 'target', 'toolchain', 'options', 'source_recipe_sha256',
                    'source_inputs_sha256', 'contract_header_sha256', 'binding', 'configuration',
                    'capabilities', 'bridge_abi')
    _fields(build, build_fields + (tuple(PHYSICAL_PROFILE_FACTS) if physical else ()), 'provider build')
    _version(build, PHYSICAL_BUILD_KIND if physical else BUILD_KIND, 'provider build')
    expected_config = {'profile': 'browser-wasm32-cpu-direct-owner-physical-v1' if physical else 'browser-wasm32-cpu-direct-owner-v1', 'modularized': True,
                       'esm': True, 'auto_main': False, 'pthread': False, 'shared_memory': False,
                       'fixed_viewport_width': 800, 'fixed_viewport_height': 600}
    if (encoded(build['target']) != encoded(binary['target']) or encoded(build['toolchain']) != encoded(binary['toolchain'])
            or encoded(build['options']) != encoded(binary['options']) or build['source_recipe_sha256'] != pins['recipe']
            or build['source_inputs_sha256'] != _hash(encoded(recipe['inputs']))
            or build['contract_header_sha256'] != canonical_header or build['binding'] != required_binding
            or encoded(build['configuration']) != encoded(expected_config)
            or build['capabilities'] != (PHYSICAL_CAPABILITIES if physical else CAPABILITIES) or type(build['bridge_abi']) is not int
            or build['bridge_abi'] != BRIDGE_ABI):
        _fail('Provider build configuration/identity differs from the neutral copied contract')
    if physical and any(encoded(build[name]) != encoded(value) for name, value in PHYSICAL_PROFILE_FACTS.items()):
        _fail('Provider build physical facts differ from the exact maintained generator contract')
    profile = proof['engine_profile']
    validate_engine_profile(profile, required_binding=required_binding)
    if profile['build_sha256'] != _hash(evidence['provider_build']) or profile['source_recipe_sha256'] != pins['recipe']:
        _fail('Engine copied profile differs from exact current raster/service contract')
    asset_records = proof['assets']
    if type(asset_records) is not dict or set(asset_records) != set(provider['assets']) or set(assets) != set(asset_records):
        _fail('Engine asset closure differs from complete provider assets')
    if set(notices) != set(binary['licenses']) or len(notices) > limits.max_notices:
        _fail('Engine notices differ from complete retained license closure')
    role_paths, lookup_names, owned_assets = {}, set(), {}
    data_total = 0
    for path, item in asset_records.items():
        _fields(item, ('role', 'sha256', 'bytes', 'mode', 'lookup_name'), 'runtime asset')
        role = item['role']
        if role not in ('factory', 'wasm', 'data'):
            _fail('Unsupported engine asset role')
        maximum = {'factory': limits.max_factory_bytes, 'wasm': limits.max_wasm_bytes, 'data': limits.max_data_member_bytes}[role]
        if type(item['bytes']) is not int or item['bytes'] < (0 if role == 'data' else 1):
            _fail('Invalid declared engine asset byte length')
        raw = _member_bytes(assets, path, files, maximum, 'engine asset')
        if (len(raw) != item['bytes'] or item['sha256'] != files[path]
                or type(item['mode']) is not int or item['mode'] != binary['modes'][path]):
            _fail('Engine asset length/hash/mode differs from pinned member')
        if role in ('wasm', 'data'):
            name = item['lookup_name']
            if (not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}', name)
                    or '..' in name or name.casefold() in lookup_names):
                _fail('Unsafe or aliased factory Wasm/data lookup name')
            lookup_names.add(name.casefold())
            if role == 'data':
                data_total += len(raw)
        elif item['lookup_name'] is not None:
            _fail('Factory does not have a factory lookup name')
        role_paths.setdefault(role, []).append(path); owned_assets[path] = raw
    if (len(role_paths.get('factory', ())) != 1 or len(role_paths.get('wasm', ())) != 1
            or role_paths['factory'][0] != provider['entry'] or len(role_paths.get('data', ())) > limits.max_data_files
            or data_total > limits.max_data_total_bytes):
        _fail('Engine factory/Wasm/data role closure or bound mismatch')
    reserved = set(metadata_paths) | set(assets) | set(notices)
    if len(reserved) != len(metadata_paths) + len(assets) + len(notices):
        _fail('Conflicting engine asset/metadata/notice roles')
    owned_notices, notice_records, notice_total = {}, {}, 0
    for path in notices:
        raw = _member_bytes(notices, path, files, limits.max_notice_bytes, 'engine notice')
        if source['files'].get(path) != _hash(raw):
            _fail('Engine notice differs from original source notice')
        owned_notices[path] = raw; notice_total += len(raw)
        notice_records[path] = {'sha256': _hash(raw), 'bytes': len(raw), 'mode': binary['modes'][path]}
    if notice_total > limits.max_notices_total_bytes:
        _fail('Engine notices exceed total bound')
    facts = scan_wasm(owned_assets[role_paths['wasm'][0]])
    if encoded(proof['wasm_facts']) != encoded(facts):
        _fail('Engine Wasm facts differ from actual section scan')
    memories = facts['memories']
    if (facts['start'] is not None or len(memories) != 1 or memories[0]['shared']
            or memories[0]['memory64'] or memories[0]['maximum'] is None
            or memories[0]['maximum'] > 65536):
        _fail('Engine requires one finite private unshared wasm32 memory and no start section')
    required = {'bib_engine_wasm_bridge_v1': ([], ['i32']),
                'bib_engine_wasm_dispatch_v1': (['i32'] * 5, ['i32']),
                'malloc': (['i32'], ['i32']), 'free': (['i32'], [])}
    exports = {item['name']: item for item in facts['exports']}
    for name, (parameters, results) in required.items():
        item = exports.get(name)
        if item is None or item['kind'] != 'function' or item['details'] != {'parameters': parameters, 'results': results}:
            _fail('Missing or mistyped actual copied Wasm export: ' + name)
    for item in facts['imports'] + facts['exports']:
        name = item['name'].lstrip('_').lower()
        if name in ('main', 'start', 'bib_eval', 'bib_pump') or name.startswith(('pthread', 'emscripten_thread')):
            _fail('Diagnostic/pthread Wasm import/export is ineligible: ' + item['name'])
    policy = proof['factory_policy']
    _fields(policy, ('kind', 'imports', 'data_loading', 'incoming_module_api', 'syntax'), 'factory policy')
    incoming = policy['incoming_module_api']
    if (policy['kind'] != 'inert-esm-copied-owner-v1' or policy['imports'] != []
            or type(incoming) is not list or any(not isinstance(name, str) for name in incoming)
            or incoming != sorted(set(incoming))
            or not {'wasmBinary', 'noInitialRun', 'print', 'printErr', 'foundationEngineHost', 'locateFile'} <= set(incoming)
            or policy['data_loading'] not in ('embedded', 'getPreloadedPackage')
            or policy['data_loading'] == 'embedded' and bool(role_paths.get('data'))
            or role_paths.get('data') and 'getPreloadedPackage' not in incoming):
        _fail('Factory inert/data-loading/incoming API policy is incompatible')
    syntax = scan_factory(owned_assets[role_paths['factory'][0]])
    if encoded(policy['syntax']) != encoded(syntax):
        _fail('Factory syntax facts differ from actual retained source')
    runtime = _document(evidence['runtime'], 'runtime evidence')
    _fields(runtime, ('schema_version', 'kind', 'scope', 'status', 'recipe_id', 'provider_build_sha256',
                      'assets_sha256', 'target', 'paired_sdk_sha256', 'engine_profile', 'browser', 'checks'), 'runtime evidence')
    _version(runtime, PHYSICAL_RUNTIME_KIND if physical else RUNTIME_KIND, 'runtime evidence')
    if (runtime['scope'] not in ('parser-fixture-only', 'retained-neutral-provider-runtime')
            or runtime['status'] not in ('passed', 'failed', 'incomplete')
            or runtime['recipe_id'] != pins['recipe'] or runtime['provider_build_sha256'] != profile['build_sha256']
            or runtime['assets_sha256'] != _hash(encoded(asset_records)) or encoded(runtime['target']) != encoded(kernel_target)
            or runtime['paired_sdk_sha256'] != paired_sdk or encoded(runtime['engine_profile']) != encoded(profile)):
        _fail('Original runtime evidence scope/subject differs from selected engine closure')
    _fields(runtime['browser'], ('name', 'version'), 'observed browser')
    for value in runtime['browser'].values(): manifest.text(value, 'original observed browser identity')
    _fields(runtime['checks'], PHYSICAL_RUNTIME_CHECKS if physical else RUNTIME_CHECKS, 'original runtime checks')
    reports = evidence['reports']
    if not hasattr(reports, 'items'):
        _fail('Expected owned original runtime evidence files')
    referenced = set()
    for name, check in runtime['checks'].items():
        _fields(check, ('status', 'evidence'), 'original runtime check ' + name)
        if check['status'] not in ('passed', 'failed', 'not-run') or type(check['evidence']) is not list:
            _fail('Invalid original runtime check status/evidence')
        paths = []
        for reference in check['evidence']:
            path = _reference(reference, 'original runtime case reference')
            if path in reserved or path in paths:
                _fail('Conflicting/duplicate original case-evidence role')
            raw = _member_bytes(reports, path, files, limits.max_reports_total_bytes, 'original runtime report')
            if _hash(raw) != reference['sha256']:
                _fail('Original runtime case evidence pin mismatch')
            paths.append(path); referenced.add(path)
        if check['status'] == 'passed' and not paths:
            _fail('Passed original runtime case requires retained evidence')
    if set(reports) != referenced or sum(len(reports[path]) for path in reports) > limits.max_reports_total_bytes:
        _fail('Original runtime report closure differs or exceeds bound')
    metadata = {'scope': SCOPE if group_files is not None else EMBEDDED_SCOPE,
                'whole_group_verified': group_files is not None,
                'production_eligible': _production_eligible(runtime), 'recipe_id': pins['recipe'],
                'binary_manifest_sha256': pins['manifest'], 'source_manifest_sha256': source_hash,
                'proof_sha256': pins['proof'], 'runtime_sha256': pins['runtime'], 'group_files': group_files,
                'engine_profile': profile, 'provider_build_sha256': profile['build_sha256'],
                'assets': asset_records, 'notices': notice_records, 'wasm_facts': facts,
                'factory_policy': policy, 'runtime_evidence': runtime}
    if physical:
        metadata['command_catalog'] = proof['command_catalog']
    return ConsumerInspection(_freeze(metadata), _freeze(owned_assets), _freeze(owned_notices),
                              _freeze({key: dict(value) if key == 'reports' else value for key, value in evidence.items()}))


def inspect_embedded_consumer(*, evidence, assets, notices, pins, kernel_target, paired_sdk,
                              required_binding=BINDING, limits=None):
    return _inspect(evidence, assets, notices, pins, kernel_target, paired_sdk, required_binding, limits)


def _read_members(archive_path, wanted, *, aggregate_limit=None):
    """Read only named, bounded ordinary members after complete Stage A checks."""
    result, total = {}, 0
    with tarfile.open(archive_path, 'r:*') as archive:
        for member in archive:
            if member.name not in wanted:
                continue
            selected = wanted[member.name]
            maximum, expected = selected if isinstance(selected, tuple) else (selected, None)
            total += member.size
            if (member.name in result or not member.isfile() or member.size < 0 or member.size > maximum
                    or expected is not None and member.size != expected
                    or aggregate_limit is not None and total > aggregate_limit):
                _fail('Duplicate/oversized/nonordinary consumer archive member')
            with archive.extractfile(member) as stream:
                raw = stream.read(member.size + 1)
            if len(raw) != member.size:
                _fail('Consumer archive member changed/truncated')
            result[member.name] = raw
    if set(result) != set(wanted):
        _fail('Missing retained consumer archive members')
    return result


def inspect_kernel_consumer(group, *, expected_recipe, expected_manifest, expected_proof, expected_runtime,
                            kernel_target, paired_sdk, required_binding=BINDING, limits=None):
    physical = _physical_mode(required_binding)
    kernel_target = _document(encoded(kernel_target), 'consumer target')
    _target(kernel_target, paired_sdk)
    pins = {'recipe': expected_recipe, 'manifest': expected_manifest, 'proof': expected_proof, 'runtime': expected_runtime}
    _pins(pins)
    limits = ConsumerLimits() if limits is None else limits
    if not isinstance(limits, ConsumerLimits):
        _fail('Expected explicit ConsumerLimits')
    verified = sdk.verify_group(group, expected_recipe)
    if verified['binary_manifest_sha256'] != expected_manifest:
        _fail('Independent manifest pin mismatch')
    root = manifest.ordinary_root(group)
    binary_name, source_name, _ = sdk.group_names(expected_recipe)
    binary_path, source_path = root / binary_name, root / source_name
    raw_binary = _read_members(binary_path, {'engine-sdk.json': manifest.MAX_MANIFEST})['engine-sdk.json']
    binary = _document(raw_binary, 'binary manifest')
    raw_proof = _read_members(binary_path, {binary['build']['link_receipt']: manifest.MAX_MANIFEST})[binary['build']['link_receipt']]
    if _hash(raw_proof) != expected_proof:
        _fail('Independent proof pin mismatch')
    proof = _document(raw_proof, 'provider proof')
    _fields(proof, ('schema_version', 'kind', 'recipe_id', 'sources_sha256', 'provider_build',
                    'engine_profile', 'assets', 'wasm_facts', 'factory_policy', 'runtime_evidence') +
                    (('command_catalog',) if physical else ()), 'provider proof')
    _version(proof, PHYSICAL_PROOF_KIND if physical else PROOF_KIND, 'provider proof')
    build_path = _reference(proof['provider_build'], 'provider-build reference')
    runtime_path = _reference(proof['runtime_evidence'], 'runtime-evidence reference')
    wanted_documents = {build_path: manifest.MAX_MANIFEST, runtime_path: manifest.MAX_MANIFEST}
    if physical:
        catalog_path = _reference(proof['command_catalog'], 'physical command-catalog reference')
        if proof['command_catalog']['sha256'] != COMMAND_CATALOG_SHA256:
            _fail('Physical command catalog differs from the approved byte identity')
        if type(proof['assets']) is not dict:
            _fail('Invalid provider asset records')
        if catalog_path in ((binary['build']['link_receipt'], build_path, runtime_path, binary['provider']['header']) +
                            tuple(proof['assets']) + tuple(binary['licenses'])):
            _fail('Conflicting physical command-catalog metadata role')
        wanted_documents[catalog_path] = MAX_COMMAND_CATALOG_BYTES
    documents = _read_members(binary_path, wanted_documents)
    if (_hash(documents[runtime_path]) != expected_runtime
            or proof['runtime_evidence']['sha256'] != expected_runtime):
        _fail('Independent runtime evidence pin mismatch')
    if _hash(documents[build_path]) != proof['provider_build']['sha256']:
        _fail('Provider-build identity differs from retained bytes')
    runtime = _document(documents[runtime_path], 'runtime evidence')
    sources = _read_members(source_path, {'recipe.json': manifest.MAX_MANIFEST, 'sources.json': manifest.MAX_MANIFEST})
    if physical:
        _command_catalog(proof, documents[catalog_path], binary,
                         _document(sources['sources.json'], 'source manifest'), _document(sources['recipe.json'], 'recipe'))
    wanted_reports = {}
    if type(runtime.get('checks')) is not dict:
        _fail('Invalid original runtime checks')
    for check in runtime['checks'].values():
        if type(check) is not dict or type(check.get('evidence')) is not list:
            _fail('Invalid original runtime check evidence')
        for reference in check['evidence']:
            wanted_reports[_reference(reference, 'original runtime case reference')] = limits.max_reports_total_bytes
    if physical and catalog_path in wanted_reports:
        _fail('Conflicting physical command-catalog asset/notice/report role')
    asset_limits = {}
    if type(proof['assets']) is not dict:
        _fail('Invalid provider asset records')
    if len(proof['assets']) > limits.max_data_files + 2:
        _fail('Engine asset count exceeds retained consumer bound')
    counts = {'factory': 0, 'wasm': 0, 'data': 0}
    declared_data_bytes = 0
    for path, item in proof['assets'].items():
        if type(item) is not dict or item.get('role') not in ('factory', 'wasm', 'data'):
            _fail('Invalid runtime asset role')
        role = item['role']; counts[role] += 1
        maximum = {'factory': limits.max_factory_bytes, 'wasm': limits.max_wasm_bytes, 'data': limits.max_data_member_bytes}[role]
        size = item.get('bytes')
        if type(size) is not int or size < 0 or size > maximum:
            _fail('Declared engine asset size exceeds retained consumer bound')
        if role == 'data':
            declared_data_bytes += size
        asset_limits[path] = maximum, size
    if (counts['factory'] != 1 or counts['wasm'] != 1 or counts['data'] > limits.max_data_files
            or declared_data_bytes > limits.max_data_total_bytes):
        _fail('Engine asset role count exceeds retained consumer contract')
    if len(binary['licenses']) > limits.max_notices:
        _fail('Engine notice count exceeds retained consumer bound')
    assets = _read_members(binary_path, asset_limits,
                          aggregate_limit=limits.max_factory_bytes + limits.max_wasm_bytes + limits.max_data_total_bytes)
    notices = _read_members(binary_path, {path: limits.max_notice_bytes for path in binary['licenses']},
                           aggregate_limit=limits.max_notices_total_bytes)
    reports = _read_members(binary_path, wanted_reports, aggregate_limit=limits.max_reports_total_bytes)
    evidence = {'binary_manifest': raw_binary, 'source_manifest': sources['sources.json'], 'recipe': sources['recipe.json'],
                'proof': raw_proof, 'provider_build': documents[build_path], 'runtime': documents[runtime_path], 'reports': reports}
    if physical:
        evidence['command_catalog'] = documents[catalog_path]
    result = _inspect(evidence, assets, notices, pins, kernel_target, paired_sdk, required_binding, limits, verified['files'])
    if sdk.group_snapshot(root, expected_recipe) != verified['files']:
        _fail('Retained engine group changed during consumer inspection')
    return result


def verify_kernel_consumer(group, **kwargs):
    result = inspect_kernel_consumer(group, **kwargs)
    if not result.metadata['production_eligible']:
        _fail('Retained engine is production-ineligible: actual neutral-provider runtime evidence remains required; fixtures never qualify')
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('inspect', 'verify'))
    parser.add_argument('--group', type=Path, required=True)
    for name in ('recipe', 'manifest', 'proof', 'runtime'):
        parser.add_argument('--' + name + '-sha256', required=True)
    parser.add_argument('--kernel-target-json', type=Path, required=True)
    parser.add_argument('--paired-sdk-sha256', required=True)
    parser.add_argument('--physical-input', action='store_true', help='Require the separate physical467/mouse-v1 retained contract')
    args = parser.parse_args(argv)
    operation = inspect_kernel_consumer if args.action == 'inspect' else verify_kernel_consumer
    result = operation(args.group, expected_recipe=args.recipe_sha256, expected_manifest=args.manifest_sha256,
                       expected_proof=args.proof_sha256, expected_runtime=args.runtime_sha256,
                       kernel_target=_document(args.kernel_target_json.read_bytes(), 'kernel target'),
                       paired_sdk=args.paired_sdk_sha256,
                       required_binding=PHYSICAL_BINDING if args.physical_input else BINDING)
    print(json.dumps(result.as_dict(), sort_keys=True))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, OSError, tarfile.TarError) as error:
        raise SystemExit('appended engine consumer: ' + str(error))
