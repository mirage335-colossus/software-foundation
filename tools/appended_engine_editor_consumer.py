#!/usr/bin/env python3
"""Inspect explicit editor-v1 retained inputs without executing or qualifying them.

Legacy copied259/467 and document1795/2003 admission is unchanged. This separate
reader preserves original editor-provider runtime evidence and complete retained
byte closure; static inspection never executes a factory, report or SDK program.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import tarfile
from types import MappingProxyType

import appended_engine_editor_contract as contract
import appended_engine_manifest as manifest
import appended_engine_sdk as sdk
from appended_engine_consumer import (ConsumerError, ConsumerInspection, ConsumerLimits,
                                      scan_factory, scan_wasm)
from dependency_archive import encoded

SCOPE = contract.SCOPE
EMBEDDED_SCOPE = contract.EMBEDDED_SCOPE
BINDING = contract.BINDING
PROOF_KIND = contract.PROOF_KIND
BUILD_KIND = contract.BUILD_KIND
RUNTIME_KIND = contract.RUNTIME_KIND
validate_engine_profile = contract.validate_engine_profile


def _fail(message):
    raise ConsumerError(message)


def _hash(raw):
    return hashlib.sha256(raw).hexdigest()


def _freeze(value):
    if type(value) is dict:
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if type(value) is list:
        return tuple(_freeze(item) for item in value)
    return value


def _same(left, right):
    return contract.canonical_json(left) == contract.canonical_json(right)


def _editor(raw, label):
    if type(raw) is not bytes:
        _fail('Expected owned ' + label + ' editor bytes')
    return contract.strict_json(raw, label, maximum=manifest.MAX_MANIFEST)


def _mapping(value, label):
    if not hasattr(value, 'items'):
        _fail('Expected owned ' + label + ' mapping')
    return dict(value.items())


def _evidence(value):
    value = _mapping(value, 'editor evidence')
    contract.require_fields(value, contract.EVIDENCE_FIELDS, 'editor evidence')
    value['reports'] = _mapping(value['reports'], 'original runtime report')
    value['interfaces'] = _mapping(value['interfaces'], 'editor interface')
    for label in contract.EVIDENCE_FIELDS:
        if label not in ('reports', 'interfaces') and (
                type(value[label]) is not bytes or len(value[label]) > manifest.MAX_MANIFEST):
            _fail('Invalid/oversized owned ' + label + ' editor bytes')
    return value


def _reference(value, label):
    contract.require_fields(value, ('path', 'sha256'), label)
    manifest.path_name(value['path'])
    contract.validate_sha256(value['sha256'], label)
    return value['path']


def _version(value, kind, label):
    if type(value['schema_version']) is not int or value['schema_version'] != 1 or value['kind'] != kind:
        _fail('Unsupported ' + label + ' kind/version')


def _selection(kernel_target, paired_sdk, editor_profile, limits):
    selected = contract.editor_selector(editor_profile)
    target = contract.json_copy(kernel_target, 'editor consumer target')
    manifest.target_contract(target)
    contract.validate_sha256(paired_sdk, 'paired SDK')
    if target['system'] != 'Emscripten' or target['processor'] != 'wasm32':
        _fail('Only the browser wasm32 editor consumer is implemented')
    limits = ConsumerLimits() if limits is None else limits
    if not isinstance(limits, ConsumerLimits):
        _fail('Expected explicit ConsumerLimits')
    return selected, target, limits


def _pins(value):
    value = _mapping(value, 'independent editor consumer pin')
    contract.require_fields(value, ('recipe', 'manifest', 'proof', 'runtime'), 'independent editor consumer pins')
    for name, pin in value.items():
        contract.validate_sha256(pin, name + ' independent pin')
    return value


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


def _metadata_paths(binary, proof, selected):
    references = contract.validate_interface_references(proof['interfaces'], editor_profile=selected)
    for reference in references.values():
        _reference(reference, 'editor interface reference')
    build_path = _reference(proof['provider_build'], 'editor provider-build reference')
    runtime_path = _reference(proof['runtime_evidence'], 'editor runtime reference')
    proof_path = binary['build']['link_receipt']
    metadata = {proof_path, build_path, runtime_path}
    interface_paths = {reference['path'] for reference in references.values()}
    if len(metadata) != 3 or metadata & interface_paths:
        _fail('Conflicting editor proof/build/runtime/interface roles')
    # This is the only intentional alias: Stage-A's provider header is the
    # canonical base interface. Do not count it as a second metadata member.
    if binary['provider']['header'] != references['base_header']['path']:
        _fail('Editor provider header must name the canonical base interface')
    reserved = metadata | interface_paths
    if reserved & (set(binary['provider']['assets']) | set(binary['licenses'])):
        _fail('Conflicting editor metadata/asset/notice roles')
    return references, build_path, runtime_path, reserved


def _editors(evidence, pins, target, paired_sdk, selected):
    for label, pin in (('recipe', 'recipe'), ('binary_manifest', 'manifest'), ('proof', 'proof'), ('runtime', 'runtime')):
        if _hash(evidence[label]) != pins[pin]:
            _fail('Independent ' + pin + ' pin mismatch')
    binary = _editor(evidence['binary_manifest'], 'binary manifest')
    source = _editor(evidence['source_manifest'], 'source manifest')
    recipe = _editor(evidence['recipe'], 'recipe')
    manifest.binary_contract(binary)
    manifest.source_contract(source, recipe, pins['recipe'])
    source_hash = _hash(evidence['source_manifest'])
    manifest.verify_binding(binary, source, source_hash, recipe)
    if binary['recipe_id'] != pins['recipe'] or not _same(binary['target'], target):
        _fail('Editor recipe/target differs from consumer selection')
    provider = binary['provider']
    if (provider['format'] != 'browser-module' or provider['binding'] != 'copied-owner-bridge'
            or type(provider['abi_major']) is not int or provider['abi_major'] != 1
            or type(provider['abi_minor']) is not int or provider['abi_minor'] != 1
            or provider['header_sha256'] != contract.BASE_HEADER_SHA256):
        _fail('Editor provider requires canonical base bytes and explicit provider ABI1.1')
    if binary['toolchain']['paired_sdk_sha256'] != paired_sdk:
        _fail('Editor paired SDK differs from consumer selection')
    proof = _editor(evidence['proof'], 'editor provider proof')
    contract.require_fields(proof, contract.PROOF_FIELDS, 'editor provider proof')
    _version(proof, PROOF_KIND, 'editor provider proof')
    references, build_path, runtime_path, reserved = _metadata_paths(binary, proof, selected)
    interfaces = contract.validate_interface_bytes(references, evidence['interfaces'], editor_profile=selected)
    for path, raw in interfaces.items():
        _member_bytes(interfaces, path, binary['files'], contract.MAX_INTERFACE_BYTES, 'editor interface')
        item = recipe['inputs'].get(path)
        if (source['files'].get(path) != _hash(raw) or type(item) is not dict
                or item.get('sha256') != _hash(raw) or item.get('role') != 'interface'):
            _fail('Editor interface differs from original source/recipe interface inventory')
    for path, raw, expected in ((binary['build']['link_receipt'], evidence['proof'], pins['proof']),
                               (build_path, evidence['provider_build'], proof['provider_build']['sha256']),
                               (runtime_path, evidence['runtime'], pins['runtime'])):
        if binary['files'].get(path) != expected or _hash(raw) != expected:
            _fail('Editor proof/build/runtime identity differs from inventoried bytes')
    if proof['runtime_evidence']['sha256'] != pins['runtime']:
        _fail('Independent editor runtime evidence pin mismatch')
    if proof['recipe_id'] != pins['recipe'] or proof['sources_sha256'] != source_hash:
        _fail('Editor proof source binding mismatch')
    build = _editor(evidence['provider_build'], 'editor provider build')
    contract.require_fields(build, contract.BUILD_FIELDS, 'editor provider build')
    _version(build, BUILD_KIND, 'editor provider build')
    provider_contract = contract.validate_provider_contract(build['provider_contract'], editor_profile=selected)
    if (not _same(build['target'], binary['target']) or not _same(build['toolchain'], binary['toolchain'])
            or not _same(build['options'], binary['options']) or build['source_recipe_sha256'] != pins['recipe']
            or build['source_inputs_sha256'] != _hash(encoded(recipe['inputs']))
            or build['contract_header_sha256'] != contract.CONTRACT_SHA256 or build['binding'] != BINDING
            or not _same(build['configuration'], contract.expected_configuration(editor_profile=selected))
            or build['capabilities'] != contract.CAPABILITIES[selected]
            or type(build['bridge_abi']) is not int or build['bridge_abi'] != 65536):
        _fail('Editor provider build configuration/identity differs from selected contract')
    profile = validate_engine_profile(proof['engine_profile'], editor_profile=selected)
    if profile['build_sha256'] != _hash(evidence['provider_build']) or profile['source_recipe_sha256'] != pins['recipe']:
        _fail('Editor profile differs from exact provider-build/recipe bytes')
    runtime = _editor(evidence['runtime'], 'editor runtime evidence')
    contract.require_fields(runtime, contract.RUNTIME_FIELDS, 'editor runtime evidence')
    _version(runtime, RUNTIME_KIND, 'editor runtime evidence')
    if (runtime['scope'] not in ('parser-fixture-only', 'retained-neutral-provider-runtime')
            or runtime['status'] not in ('passed', 'failed', 'incomplete')
            or runtime['recipe_id'] != pins['recipe'] or runtime['provider_build_sha256'] != profile['build_sha256']
            or runtime['assets_sha256'] != _hash(encoded(proof['assets'])) or not _same(runtime['target'], target)
            or runtime['paired_sdk_sha256'] != paired_sdk or not _same(runtime['engine_profile'], profile)):
        _fail('Original editor runtime scope/subject differs from selected closure')
    contract.require_fields(runtime['browser'], ('name', 'version'), 'original observed browser')
    for value in runtime['browser'].values():
        manifest.text(value, 'original observed browser identity')
    contract.validate_provider_observation(runtime['provider_observation'], editor_profile=selected)
    if not _same(runtime['provider_observation']['contract'], provider_contract):
        _fail('Observed provider contract differs from original build')
    contract.validate_bootstrap(runtime['bootstrap'], editor_profile=selected, engine_profile=profile)
    contract.require_fields(runtime['checks'], contract.runtime_checks(editor_profile=selected), 'original editor runtime checks')
    return binary, source, recipe, proof, build, profile, runtime, references, reserved


def _report_references(runtime, reserved):
    references = {}
    for name, check in runtime['checks'].items():
        contract.require_fields(check, ('status', 'evidence'), 'original runtime check ' + name)
        if check['status'] not in ('passed', 'failed', 'not-run') or type(check['evidence']) is not list:
            _fail('Invalid original runtime check status/evidence')
        seen = set()
        for reference in check['evidence']:
            path = _reference(reference, 'original runtime case reference')
            if path in reserved or path in seen:
                _fail('Conflicting/duplicate original runtime case-evidence role')
            if path in references and references[path] != reference['sha256']:
                _fail('Conflicting original runtime report pins')
            seen.add(path)
            references[path] = reference['sha256']
        if check['status'] == 'passed' and not seen:
            _fail('Passed original runtime case requires retained evidence')
    return references


def _asset_limits(proof, provider, notices, limits):
    records = proof['assets']
    if type(records) is not dict or set(records) != set(provider['assets']):
        _fail('Editor engine asset closure differs from complete provider assets')
    if len(notices) > limits.max_notices:
        _fail('Editor engine notice count exceeds retained bound')
    counts, lookup, selected, total = {'factory': 0, 'wasm': 0, 'data': 0}, set(), {}, 0
    for path, item in records.items():
        manifest.path_name(path)
        contract.require_fields(item, ('role', 'sha256', 'bytes', 'mode', 'lookup_name'), 'runtime asset')
        role = item['role']
        if type(role) is not str or role not in counts:
            _fail('Unsupported editor engine asset role')
        counts[role] += 1
        maximum = {'factory': limits.max_factory_bytes, 'wasm': limits.max_wasm_bytes, 'data': limits.max_data_member_bytes}[role]
        size = item['bytes']
        if type(size) is not int or not (0 if role == 'data' else 1) <= size <= maximum:
            _fail('Declared editor engine asset size exceeds retained bound')
        if role in ('wasm', 'data'):
            name = item['lookup_name']
            if (type(name) is not str or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}', name)
                    or '..' in name or name.casefold() in lookup):
                _fail('Unsafe or aliased factory Wasm/data lookup name')
            lookup.add(name.casefold())
        elif item['lookup_name'] is not None or path != provider['entry']:
            _fail('Editor factory role/lookup differs from provider entry')
        if role == 'data':
            total += size
        selected[path] = maximum, size
    if counts['factory'] != 1 or counts['wasm'] != 1 or counts['data'] > limits.max_data_files or total > limits.max_data_total_bytes:
        _fail('Editor engine asset role/count/aggregate bound mismatch')
    return selected


def _static_contract(proof, assets):
    factory = next(path for path, item in proof['assets'].items() if item['role'] == 'factory')
    wasm = next(path for path, item in proof['assets'].items() if item['role'] == 'wasm')
    facts = scan_wasm(assets[wasm])
    if not _same(proof['wasm_facts'], facts):
        _fail('Editor Wasm facts differ from actual section scan')
    memories = facts['memories']
    # A factory may create and import a private Memory. Shape does not prove
    # heap ownership; the original separate-heaps runtime check is mandatory.
    if (facts['start'] is not None or len(memories) != 1 or memories[0]['shared'] or memories[0]['memory64']
            or memories[0]['maximum'] is None or memories[0]['maximum'] > 65536):
        _fail('Editor engine requires one finite private wasm32 memory and no start section')
    required = {'bib_engine_wasm_bridge_v1': ([], ['i32']),
                'bib_engine_wasm_dispatch_v1': (['i32'] * 5, ['i32']),
                'bib_engine_wasm_editor_facts_v1': (['i32', 'i32'], ['i32']),
                'bib_engine_wasm_editor_configure_v1': (['i32', 'i32'], ['i32']),
                'malloc': (['i32'], ['i32']), 'free': (['i32'], [])}
    exports = {item['name']: item for item in facts['exports']}
    for name, (parameters, results) in required.items():
        item = exports.get(name)
        if item is None or item['kind'] != 'function' or item['details'] != {'parameters': parameters, 'results': results}:
            _fail('Missing or mistyped actual editor Wasm export: ' + name)
    for item in facts['imports'] + facts['exports']:
        name = item['name'].lstrip('_').lower()
        if name in ('main', 'start', 'bib_eval', 'bib_pump') or name.startswith(('pthread', 'emscripten_thread')):
            _fail('Diagnostic/pthread Wasm import/export is ineligible: ' + item['name'])
    policy = proof['factory_policy']
    contract.require_fields(policy, ('kind', 'imports', 'data_loading', 'incoming_module_api', 'syntax'), 'factory policy')
    incoming = policy['incoming_module_api']
    has_data = any(item['role'] == 'data' for item in proof['assets'].values())
    if (policy['kind'] != 'inert-esm-copied-owner-v1' or policy['imports'] != []
            or type(incoming) is not list or any(type(name) is not str for name in incoming)
            or incoming != sorted(set(incoming))
            or not {'wasmBinary', 'noInitialRun', 'print', 'printErr', 'foundationEngineHost', 'locateFile'} <= set(incoming)
            or policy['data_loading'] not in ('embedded', 'getPreloadedPackage')
            or policy['data_loading'] == 'embedded' and has_data
            or has_data and 'getPreloadedPackage' not in incoming):
        _fail('Editor factory inert/data-loading/incoming API policy differs')
    if not _same(policy['syntax'], scan_factory(assets[factory])):
        _fail('Editor factory syntax facts differ from retained source')
    return facts, policy


def _production_eligible(runtime):
    return (runtime['scope'] == 'retained-neutral-provider-runtime' and runtime['status'] == 'passed'
            and all(check['status'] == 'passed' and bool(check['evidence']) for check in runtime['checks'].values())
            and all(runtime['bootstrap']['checks'][name] == 'passed' for name in contract.BOOTSTRAP_CHECKS))


def _inspect(evidence, assets, notices, pins, kernel_target, paired_sdk, editor_profile, limits, group_files=None):
    selected, target, limits = _selection(kernel_target, paired_sdk, editor_profile, limits)
    evidence, pins = _evidence(evidence), _pins(pins)
    assets, notices = _mapping(assets, 'engine asset'), _mapping(notices, 'engine notice')
    binary, source, recipe, proof, build, profile, runtime, references, reserved = _editors(evidence, pins, target, paired_sdk, selected)
    asset_limits = _asset_limits(proof, binary['provider'], binary['licenses'], limits)
    if set(assets) != set(asset_limits) or set(notices) != set(binary['licenses']):
        _fail('Editor engine assets/notices differ from complete retained closure')
    reserved |= set(assets) | set(notices)
    report_references = _report_references(runtime, reserved)
    owned_assets = {}
    for path, item in proof['assets'].items():
        raw = _member_bytes(assets, path, binary['files'], asset_limits[path][0], 'editor engine asset')
        if (len(raw) != item['bytes'] or item['sha256'] != binary['files'][path]
                or type(item['mode']) is not int or item['mode'] != binary['modes'][path]):
            _fail('Editor asset length/hash/mode differs from pinned member')
        owned_assets[path] = raw
    owned_notices, notice_records, total = {}, {}, 0
    for path in notices:
        raw = _member_bytes(notices, path, binary['files'], limits.max_notice_bytes, 'editor engine notice')
        if source['files'].get(path) != _hash(raw):
            _fail('Editor notice differs from original source notice')
        owned_notices[path] = raw
        total += len(raw)
        notice_records[path] = {'sha256': _hash(raw), 'bytes': len(raw), 'mode': binary['modes'][path]}
    if total > limits.max_notices_total_bytes:
        _fail('Editor notices exceed aggregate bound')
    reports = evidence['reports']
    if set(reports) != set(report_references):
        _fail('Original editor report closure differs')
    for path, expected in report_references.items():
        raw = _member_bytes(reports, path, binary['files'], limits.max_reports_total_bytes, 'original editor runtime report')
        if _hash(raw) != expected:
            _fail('Original editor runtime report pin mismatch')
    if sum(map(len, reports.values())) > limits.max_reports_total_bytes:
        _fail('Original editor reports exceed aggregate bound')
    facts, policy = _static_contract(proof, owned_assets)
    metadata = {'scope': SCOPE if group_files is not None else EMBEDDED_SCOPE,
                'whole_group_verified': group_files is not None, 'production_eligible': _production_eligible(runtime),
                'recipe_id': pins['recipe'], 'binary_manifest_sha256': pins['manifest'],
                'source_manifest_sha256': _hash(evidence['source_manifest']), 'proof_sha256': pins['proof'],
                'runtime_sha256': pins['runtime'], 'group_files': group_files, 'engine_profile': profile,
                'provider_build_sha256': profile['build_sha256'], 'provider_contract': build['provider_contract'],
                'interfaces': references, 'assets': proof['assets'], 'notices': notice_records,
                'wasm_facts': facts, 'factory_policy': policy, 'runtime_evidence': runtime}
    return ConsumerInspection(_freeze(metadata), _freeze(owned_assets), _freeze(owned_notices), _freeze(evidence))


def inspect_embedded_consumer(*, evidence, assets, notices, pins, kernel_target, paired_sdk, editor_profile, limits=None):
    return _inspect(evidence, assets, notices, pins, kernel_target, paired_sdk, editor_profile, limits)


def _read_members(archive_path, wanted, *, aggregate_limit=None):
    """Read named bounded ordinary members after complete Stage-A verification."""
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
                _fail('Duplicate/oversized/nonordinary editor consumer archive member')
            with archive.extractfile(member) as stream:
                raw = stream.read(member.size + 1)
            if len(raw) != member.size:
                _fail('Editor consumer archive member changed/truncated')
            result[member.name] = raw
    if set(result) != set(wanted):
        _fail('Missing retained editor consumer archive members')
    return result


def inspect_kernel_consumer(group, *, expected_recipe, expected_manifest, expected_proof, expected_runtime,
                            kernel_target, paired_sdk, editor_profile, limits=None):
    selected, target, limits = _selection(kernel_target, paired_sdk, editor_profile, limits)
    pins = _pins({'recipe': expected_recipe, 'manifest': expected_manifest, 'proof': expected_proof, 'runtime': expected_runtime})
    verified = sdk.verify_group(group, expected_recipe)
    if verified['binary_manifest_sha256'] != expected_manifest:
        _fail('Independent editor manifest pin mismatch')
    root = manifest.ordinary_root(group)
    binary_name, source_name, _ = sdk.group_names(expected_recipe)
    binary_path, source_path = root / binary_name, root / source_name
    raw_binary = _read_members(binary_path, {'engine-sdk.json': manifest.MAX_MANIFEST})['engine-sdk.json']
    if _hash(raw_binary) != expected_manifest:
        _fail('Independent editor manifest bytes mismatch')
    binary = _editor(raw_binary, 'binary manifest')
    manifest.binary_contract(binary)
    proof_path = binary['build']['link_receipt']
    raw_proof = _read_members(binary_path, {proof_path: manifest.MAX_MANIFEST})[proof_path]
    if _hash(raw_proof) != expected_proof:
        _fail('Independent editor proof pin mismatch')
    proof = _editor(raw_proof, 'editor provider proof')
    contract.require_fields(proof, contract.PROOF_FIELDS, 'editor provider proof')
    _version(proof, PROOF_KIND, 'editor provider proof')
    references, build_path, runtime_path, _ = _metadata_paths(binary, proof, selected)
    interfaces = _read_members(binary_path, {item['path']: contract.MAX_INTERFACE_BYTES for item in references.values()},
                               aggregate_limit=contract.MAX_INTERFACES_BYTES)
    editors = _read_members(binary_path, {build_path: manifest.MAX_MANIFEST, runtime_path: manifest.MAX_MANIFEST})
    sources = _read_members(source_path, {'recipe.json': manifest.MAX_MANIFEST, 'sources.json': manifest.MAX_MANIFEST})
    evidence = {'binary_manifest': raw_binary, 'source_manifest': sources['sources.json'], 'recipe': sources['recipe.json'],
                'proof': raw_proof, 'provider_build': editors[build_path], 'runtime': editors[runtime_path],
                'interfaces': interfaces, 'reports': {}}
    # Finish interface/schema/subject checks before materializing runtime assets.
    _, _, _, _, _, _, runtime, _, reserved = _editors(evidence, pins, target, paired_sdk, selected)
    asset_limits = _asset_limits(proof, binary['provider'], binary['licenses'], limits)
    report_references = _report_references(runtime, reserved | set(proof['assets']) | set(binary['licenses']))
    assets = _read_members(binary_path, asset_limits,
                          aggregate_limit=limits.max_factory_bytes + limits.max_wasm_bytes + limits.max_data_total_bytes)
    notices = _read_members(binary_path, {path: limits.max_notice_bytes for path in binary['licenses']},
                           aggregate_limit=limits.max_notices_total_bytes)
    evidence['reports'] = _read_members(binary_path, {path: limits.max_reports_total_bytes for path in report_references},
                                       aggregate_limit=limits.max_reports_total_bytes)
    result = _inspect(evidence, assets, notices, pins, target, paired_sdk, selected, limits, verified['files'])
    if sdk.group_snapshot(root, expected_recipe) != verified['files']:
        _fail('Retained editor engine group changed during consumer inspection')
    return result


def verify_kernel_consumer(group, **kwargs):
    result = inspect_kernel_consumer(group, **kwargs)
    if not result.metadata['production_eligible']:
        _fail('Retained editor engine is production-ineligible: original actual runtime evidence remains required; fixtures never qualify')
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('inspect', 'verify'))
    parser.add_argument('--editor-profile', choices=('editor',), required=True)
    parser.add_argument('--group', type=Path, required=True)
    for name in ('recipe', 'manifest', 'proof', 'runtime'):
        parser.add_argument('--' + name + '-sha256', required=True)
    parser.add_argument('--kernel-target-json', type=Path, required=True)
    parser.add_argument('--paired-sdk-sha256', required=True)
    args = parser.parse_args(argv)
    operation = inspect_kernel_consumer if args.action == 'inspect' else verify_kernel_consumer
    result = operation(args.group, expected_recipe=args.recipe_sha256, expected_manifest=args.manifest_sha256,
                       expected_proof=args.proof_sha256, expected_runtime=args.runtime_sha256,
                       kernel_target=_editor(args.kernel_target_json.read_bytes(), 'kernel target'),
                       paired_sdk=args.paired_sdk_sha256, editor_profile=args.editor_profile)
    print(json.dumps(result.as_dict(), sort_keys=True))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, OSError, tarfile.TarError) as error:
        raise SystemExit('appended editor engine consumer: ' + str(error))
