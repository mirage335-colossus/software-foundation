#!/usr/bin/env python3
"""Pure explicit document/editor browser carrier over retained observations.

This producer never builds, fetches, loads or executes a provider, SDK or kernel.
Legacy259/467 formats are separate. Inert fixtures can be inspected, not published.
"""
import argparse
import base64
import binascii
import json
from pathlib import Path
import re
import sys
from types import MappingProxyType

import appended_container as container
import appended_engine_document_consumer as consumer
import appended_engine_document_contract as contract
import appended_engine_editor_consumer as editor_consumer
import appended_engine_editor_contract as editor_contract
import appended_engine_manifest as manifest
import appended_engine_sdk as sdk
import browser_bundle
import package_appended_engine_wasm as rendering

KIND = 'foundation-rich-browser-document-kernel-v1'
KERNEL_KIND = 'foundation-copied-engine-document-browser'
RECEIPT_KIND = 'foundation-rich-browser-document-kernel-proof-v1'
EDITOR_KIND = 'foundation-rich-browser-editor-kernel-v1'
EDITOR_KERNEL_KIND = 'foundation-copied-engine-editor-browser'
EDITOR_RECEIPT_KIND = 'foundation-rich-browser-editor-kernel-proof-v1'
COMPOSITION_RECEIPT_KIND = 'foundation-rich-browser-document-composition-kernel-proof-v1'
EDITOR_COMPOSITION_RECEIPT_KIND = 'foundation-rich-browser-editor-composition-kernel-proof-v1'
HTML_NAME = rendering.HTML_NAME
DESCRIPTOR_NAME = 'kernel.json'
FACTORY_NAME = rendering.FACTORY_NAME
WASM_NAME = rendering.WASM_NAME
QUALIFICATION = 'unqualified-development'
CSP = rendering.CSP
OPEN, OUTER_STYLE, MIDDLE = rendering.OPEN, rendering.OUTER_STYLE, rendering.MIDDLE
BOOT_OPEN, BOOT_CLOSE = rendering.BOOT_OPEN, rendering.BOOT_CLOSE
IMPORTS = MappingProxyType({name: tuple(deps) for name, deps in rendering.IMPORTS.items()})
EDITOR_IMPORTS = MappingProxyType({**IMPORTS, 'renderer_editor_child_bundle.mjs': (),
    'browser_document_endpoint.mjs': (),
    'browser_editor_endpoint.mjs': ('browser_surface_editor_controller.mjs',
        'browser_surface_editor_text.mjs', 'browser_surface_protocol.mjs'),
    'browser_surface_editor_controller.mjs': ('browser_surface.mjs', 'browser_surface_editor_text.mjs'),
    'browser_surface_editor_text.mjs': ('browser_surface.mjs',),
    'browser_surface.mjs': ('browser_surface_protocol.mjs',)})
POLICIES = contract.json_copy(rendering.POLICIES)
MAX_MODULE = 4 * 1024 * 1024
MAX_MODULES = 32 * 1024 * 1024
MAX_FACTORY = 16 * 1024 * 1024
MAX_KERNEL_WASM = 64 * 1024 * 1024
MAX_ENGINE_WASM = 256 * 1024 * 1024
MAX_NOTICES = 16 * 1024 * 1024
MAX_NOTICE = 4 * 1024 * 1024
MAX_EVIDENCE = 64 * 1024 * 1024
MAX_REPORTS = 1024
MAX_INTERFACE_BYTES = contract.MAX_INTERFACE_BYTES
MAX_INTERFACES_BYTES = contract.MAX_INTERFACES_BYTES
EDITOR_MAX_INTERFACES_BYTES = editor_contract.MAX_INTERFACES_BYTES
ORDER_CHECKS = ('kernel_document_facts_before_engine_factory',
                'engine_describe_before_kernel_configure', 'kernel_configure_before_start')
BASE_CHECKS = ('inert_factory', 'compiled_profile_query', 'engine_describe_match')
DOCUMENT_CHECKS = ('document_profile_query', 'engine_document_bootstrap', 'host_assets_match',
    'document_owner_app_native_effect_publication', 'document_work_and_action_ack',
    'document_terminal_unknown_no_replay')
PHYSICAL_CHECKS = ('raw-key-location-altgraph', 'mouse-five-buttons-context-cancel',
    'input-context-navigation-retirement', 'native-effect-input-admission',
    'document_current_physical_provider')
EDITOR_CHECKS = ('editor_profile_query', 'editor_query4_owned_projection',
    'editor_command8_native_readback', 'editor_command9_native_revocation',
    'editor_full_worker_target_key', 'editor_pending_form_service_barriers',
    'editor_composition_focus_retirement', 'editor_unknown_terminal_no_replay',
    'engine_editor_bootstrap')
RECEIPT_FIELDS = ('schema_version', 'kind', 'scope', 'status', 'profile', 'source',
    'toolchain', 'artifacts', 'wasm_facts', 'compiled_profile', 'engine_profile', 'checks',
    'build_origin', 'document_profile', 'compiled_document_profile', 'engine_bootstrap', 'host_assets')
ENVELOPE_FIELDS = ('schema_version', 'kind', 'kernel', 'modules', 'evidence',
                   'identities', 'group_files', 'document_profile')
KERNEL_FIELDS = ('schema_version', 'kind', 'kernel_profile', 'kernel_wasm_lookup',
    'engine_wasm_lookup', 'kernel_factory', 'kernel_wasm', 'engine_factory', 'engine_wasm',
    'engine_profile', 'engine_assets', 'notices')


def _document_selector(value):
    if type(value) is str and value == 'editor':
        return editor_contract.editor_selector(value)
    return contract.document_selector(value)


def _engine_contract(selected):
    return editor_contract if selected == 'editor' else contract


def _engine_consumer(selected):
    return editor_consumer if selected == 'editor' else consumer


def _engine_selection(selected):
    return {'editor_profile': selected} if selected == 'editor' else {'document_profile': selected}


def _engine_profile(value, selected):
    return _engine_contract(selected).validate_engine_profile(value, **_engine_selection(selected))


def _interface_budget(selected):
    return EDITOR_MAX_INTERFACES_BYTES if selected == 'editor' else MAX_INTERFACES_BYTES


def _kind(selected, document, editor):
    return editor if selected == 'editor' else document


def _order_checks(selected):
    return ('kernel_editor_facts_before_engine_factory', *ORDER_CHECKS[1:]) if selected == 'editor' else ORDER_CHECKS


def _plain(value):
    if hasattr(value, 'items'):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain(item) for item in value]
    return value


def _same(left, right):
    return contract.canonical_json(left) == contract.canonical_json(right)


def _keys(value, names, label):
    contract.require_fields(value, names, label)


def _sha(value, label):
    return contract.validate_sha256(value, label)


def _profile(value):
    if type(value) is not str or value not in POLICIES:
        raise ValueError('Document kernel profile must be explicitly web or both')
    return value


def _encoded(raw):
    return base64.b64encode(raw).decode('ascii')


def _decoded(value, maximum, label):
    if type(value) is not str or len(value) > ((maximum + 2) // 3) * 4:
        raise ValueError('Invalid/oversized base64 ' + label)
    try:
        raw = base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error) as error:
        raise ValueError('Invalid base64 ' + label) from error
    if len(raw) > maximum or _encoded(raw) != value:
        raise ValueError('Noncanonical/oversized base64 ' + label)
    return raw


def _asset(raw):
    return {'data': _encoded(raw), 'sha256': container.digest(raw)}


def _read_asset(value, maximum, label):
    _keys(value, ('data', 'sha256'), label)
    raw = _decoded(value['data'], maximum, label)
    if container.digest(raw) != _sha(value['sha256'], label):
        raise ValueError(label + ' digest differs')
    return raw


def asset_names(*, document_profile='pixel'):
    selected = _document_selector(document_profile)
    if selected != 'editor':
        return rendering.asset_names()
    import browser_editor_bundle as editor
    return tuple(sorted(set(rendering.asset_names()) | set(EDITOR_IMPORTS)
                        | set(editor.SOURCE_NAMES) | {editor.BUNDLE_NAME}))


def validate_assets(blobs, *, document_profile='pixel'):
    selected = _document_selector(document_profile)
    if selected != 'editor':
        return rendering.validate_assets(blobs)
    if type(blobs) is not dict or set(blobs) != set(asset_names(document_profile=selected)):
        raise ValueError('Editor browser host asset inventory differs')
    if (any(type(raw) is not bytes or len(raw) > MAX_MODULE for raw in blobs.values())
            or sum(map(len, blobs.values())) > MAX_MODULES):
        raise ValueError('Editor browser host assets exceed limits')
    for raw in blobs.values():
        raw.decode('utf-8')
    original = rendering.validate_assets({name: blobs[name] for name in rendering.asset_names()})
    document_name = 'browser_document_endpoint.mjs'
    # This parent-only leaf has no import edges. Reuse the reviewed source
    # lexer to reject imports/reexports and bind all four public exports;
    # discard its rewritten text without evaluating any JavaScript.
    browser_bundle._module(document_name, blobs[document_name].decode('utf-8'),
        {document_name: EDITOR_IMPORTS[document_name]},
        {document_name: ('validateDocumentState', 'validateDocumentOperation',
                         'validateDocumentReply', 'createBrowserDocumentEndpoint')})
    import browser_editor_bundle as editor
    selected_bundle = editor.verify_assets({name: blobs[name] for name in (*editor.SOURCE_NAMES, editor.BUNDLE_NAME)})
    return {**original, 'editor': {'protocol': selected_bundle['CHILD_PROTOCOL'],
        'sandbox': selected_bundle['CHILD_SANDBOX'], 'csp': selected_bundle['CHILD_CSP'],
        'script_sha256': container.digest(selected_bundle['CHILD_SCRIPT'].encode())}}


def bootstrap_source(*, document_profile):
    selected = _document_selector(document_profile)
    # This bool selects only the owned renderer projection, never a259/467
    # provider binding. Keep the exact shell expected by this pure bootstrap.
    source = rendering.bootstrap_source(selected in ('physical', 'editor'))
    if selected != 'editor':
        return source
    old_graph = json.dumps(_plain(IMPORTS), ensure_ascii=True, separators=(',', ':')).replace('<', r'\u003c')
    new_graph = json.dumps(_plain(EDITOR_IMPORTS), ensure_ascii=True, separators=(',', ':')).replace('<', r'\u003c')
    old_import = "const physical=await import(moduleURL('renderer_surface_child_bundle.mjs'));"
    if (source.count('graph=' + old_graph + ';') != 1 or source.count(old_import) != 1
            or source.count('physicalRendererBundle});') != 1):
        raise ValueError('Editor bootstrap source differs from the reviewed base shell')
    return (source.replace('graph=' + old_graph + ';', 'graph=' + new_graph + ';')
            .replace(old_import, "const editor=await import(moduleURL('renderer_editor_child_bundle.mjs'));\n"
                "const {validateEditorPublication,validateEditorOperation,validateEditorReply}=await import(moduleURL('browser_editor_endpoint.mjs'));\n"
                "const editorProtocol=Object.freeze({validateEditorPublication,validateEditorOperation,validateEditorReply});\n"
                "const {validateDocumentState,validateDocumentOperation,validateDocumentReply}=await import(moduleURL('browser_document_endpoint.mjs'));\n"
                "const documentProtocol=Object.freeze({validateDocumentState,validateDocumentOperation,validateDocumentReply});")
            .replace('physical.CHILD_', 'editor.CHILD_')
            .replace('physicalRendererBundle', 'editorRendererBundle')
            .replace('editorRendererBundle});', 'editorRendererBundle,editorProtocol,documentProtocol});'))


def _asset_hashes(blobs):
    return {name: container.digest(raw) for name, raw in sorted(blobs.items())}


def _receipt_header(value, profile, selected):
    original_kind = _kind(selected, RECEIPT_KIND, EDITOR_RECEIPT_KIND)
    composition = rendering.composition_receipt_variant(value, original_kind)
    fields = tuple('compiled_editor_profile' if name == 'compiled_document_profile' else name
                   for name in RECEIPT_FIELDS) if selected == 'editor' else RECEIPT_FIELDS
    _keys(value, fields + (('compiled_composition',) if composition else ()), 'document Foundation receipt')
    if (type(value['schema_version']) is not int or value['schema_version'] != 1
            or value['kind'] != (_kind(selected, COMPOSITION_RECEIPT_KIND, EDITOR_COMPOSITION_RECEIPT_KIND)
                                if composition else original_kind) or value['profile'] != profile
            or value['document_profile'] != selected
            or value['scope'] not in ('foundation-rich-kernel-runtime', 'parser-fixture-only')
            or value['status'] not in ('passed', 'unfinished', 'failed')):
        raise ValueError('Unsupported document Foundation receipt')
    _keys(value['toolchain'], ('sdk_sha256', 'target'), 'Foundation toolchain')
    _sha(value['toolchain']['sdk_sha256'], 'Foundation paired SDK')
    target = manifest.target_contract(value['toolchain']['target'])
    if target['system'] != 'Emscripten' or target['processor'] != 'wasm32':
        raise ValueError('Document Foundation kernel requires Emscripten wasm32')
    return composition


def _compiled_document_observation(value, profile, selected):
    _keys(value, ('export', 'signature', 'observed_result', 'observed_output',
                  'observed_bytes', 'before_engine_factory', 'before_configure'), 'compiled document facts')
    getter = _kind(selected, 'gui_web_engine_document_describe_v1', 'gui_web_engine_editor_describe_v1')
    if (value['export'] != getter
            or not _same(value['signature'], {'params': ['i32', 'i32'], 'results': ['i32']})
            or value['before_engine_factory'] is not True or value['before_configure'] is not True):
        raise ValueError('Missing actual compiled document facts/order observation')
    raw = _decoded(value['observed_output'], 4095, 'compiled document facts')
    if (not raw or b'\0' in raw or type(value['observed_bytes']) is not int
            or value['observed_bytes'] != len(raw)):
        raise ValueError('Compiled document facts measured count/NUL differs')
    observed = contract.strict_json(raw, 'actual compiled document facts', maximum=4095)
    _engine_profile(observed, selected)
    if not _same(observed, value['observed_result']) or not _same(observed, profile):
        raise ValueError('Actual compiled document facts differ from selected engine')


def inspect_kernel_receipt(raw, pin, factory, wasm, profile, engine_profile, *, document_profile,
                           expected_kernel_inputs=None, host_assets=None):
    """Read pinned original observations; never execute or newly certify them."""
    selected = _document_selector(document_profile)
    profile = _profile(profile)
    engine_profile = _engine_profile(engine_profile, selected)
    if type(raw) is not bytes or len(raw) > manifest.MAX_MANIFEST or container.digest(raw) != _sha(pin, 'Foundation receipt'):
        raise ValueError('Document Foundation receipt differs from independent pin')
    value = contract.strict_json(raw, 'document Foundation receipt')
    composition = _receipt_header(value, profile, selected)
    _keys(value['source'], ('tree_sha256', 'kernel_inputs_sha256'), 'Foundation source')
    for key, digest in value['source'].items():
        _sha(digest, 'Foundation source ' + key)
    if expected_kernel_inputs is not None and value['source']['kernel_inputs_sha256'] != expected_kernel_inputs:
        raise ValueError('Compiled Foundation kernel inputs differ from observed projection')
    _keys(value['artifacts'], ('factory', 'wasm'), 'Foundation artifacts')
    for role, data, maximum in (('factory', factory, MAX_FACTORY), ('wasm', wasm, MAX_KERNEL_WASM)):
        item = value['artifacts'][role]
        _keys(item, ('sha256', 'bytes', 'lookup_name') if role == 'wasm' else ('sha256', 'bytes'), 'Foundation artifact')
        manifest.integer(item['bytes'], 'Foundation artifact bytes', 1, maximum)
        if role == 'wasm' and item['lookup_name'] != WASM_NAME:
            raise ValueError('Foundation Wasm lookup differs from its compiled filename')
        if type(data) is not bytes or len(data) != item['bytes'] or container.digest(data) != _sha(item['sha256'], role):
            raise ValueError('Actual Foundation ' + role + ' differs from receipt')
    consumer.scan_factory(factory)
    facts = consumer.scan_wasm(wasm)
    if not _same(value['wasm_facts'], facts):
        raise ValueError('Foundation Wasm facts differ from actual section scan')
    required = {'gui_web_engine_bridge_v1': ([], ['i32']), 'gui_web_engine_profile_v1': ([], ['i32']),
        'gui_web_engine_dispatch_v1': (['i32'] * 5, ['i32']), 'gui_web_create': (['i32'], ['i32']),
        'gui_web_receive': (['i32'], ['i32']), 'gui_web_destroy': ([], []),
        'malloc': (['i32'], ['i32']), 'free': (['i32'], []),
        _kind(selected, 'gui_web_engine_document_describe_v1', 'gui_web_engine_editor_describe_v1'):
            (['i32', 'i32'], ['i32'])}
    if composition:
        required[rendering.COMPOSITION_EXPORT] = ([], ['i32'])
    exports = {item['name']: item for item in facts['exports']}
    for name, (parameters, results) in required.items():
        item = exports.get(name)
        if item is None or item['kind'] != 'function' or item['details'] != {'parameters': parameters, 'results': results}:
            raise ValueError('Missing actual typed document Foundation export ' + name)
    memories = facts['memories']
    if (facts['start'] is not None or len(memories) != 1 or memories[0]['shared']
            or memories[0]['memory64'] or memories[0]['imported'] or memories[0]['maximum'] is None
            or memories[0]['maximum'] > 65536):
        raise ValueError('Foundation kernel requires one private finite defined wasm32 memory/no start')
    if any(name in exports for name in ('main', '_main', '_start', 'bib_eval', 'bib_pump')):
        raise ValueError('Diagnostic/auto-main Foundation exports are ineligible')
    marker = value['compiled_profile']
    _keys(marker, ('export', 'signature', 'observed_result', 'before_configure'), 'compiled web/both marker')
    if (marker['export'] != 'gui_web_engine_profile_v1' or not _same(marker['signature'], {'params': [], 'results': ['i32']})
            or type(marker['observed_result']) is not int or marker['observed_result'] != (1 if profile == 'web' else 2)
            or marker['before_configure'] is not True):
        raise ValueError('Actual compiled web/both marker differs')
    if not _same(value['engine_profile'], engine_profile):
        raise ValueError('Actual engine DESCRIBE differs from selected document engine')
    if composition:
        rendering.validate_compiled_composition(value['compiled_composition'], profile)
    observation = 'compiled_editor_profile' if selected == 'editor' else 'compiled_document_profile'
    _compiled_document_observation(value[observation], engine_profile, selected)
    bootstrap = value['engine_bootstrap']
    _keys(bootstrap, ('engine', 'order'), 'combined engine bootstrap')
    _engine_contract(selected).validate_bootstrap(bootstrap['engine'], engine_profile=engine_profile,
                                                 **_engine_selection(selected))
    _keys(bootstrap['order'], _order_checks(selected), 'combined engine bootstrap order')
    if any(status not in ('passed', 'failed', 'not-run') for status in bootstrap['order'].values()):
        raise ValueError('Invalid combined engine bootstrap order status')
    if (type(host_assets) is not dict or set(host_assets) != set(asset_names(document_profile=selected))
            or type(value['host_assets']) is not dict or not _same(value['host_assets'], host_assets)):
        raise ValueError('Actual document host asset inventory differs from selected same-directory graph')
    for name, digest in value['host_assets'].items():
        _sha(digest, 'document host asset ' + name)
    checks = (BASE_CHECKS + DOCUMENT_CHECKS + (PHYSICAL_CHECKS if selected in ('physical', 'editor') else ())
              + (EDITOR_CHECKS if selected == 'editor' else ())
              + ((rendering.COMPOSITION_CHECK,) if composition else ()))
    _keys(value['checks'], checks, 'Foundation document runtime checks')
    if any(status not in ('passed', 'unfinished', 'failed') for status in value['checks'].values()):
        raise ValueError('Invalid original Foundation runtime check status')
    manifest.text(value['build_origin'], 'Foundation build origin')
    eligible = (value['scope'] == 'foundation-rich-kernel-runtime' and value['status'] == 'passed'
        and all(status == 'passed' for status in value['checks'].values())
        and all(status == 'passed' for status in bootstrap['order'].values())
        and all(bootstrap['engine']['checks'][name] == 'passed' for name in contract.BOOTSTRAP_CHECKS))
    return value, eligible


def _evidence_shape(evidence, selected):
    evidence = _plain(evidence)
    _keys(evidence, contract.EVIDENCE_FIELDS, 'original document engine evidence')
    if type(evidence['reports']) is not dict or len(evidence['reports']) > MAX_REPORTS:
        raise ValueError('Original document report inventory exceeds count bound')
    count = 10 if selected == 'editor' else 6 if selected == 'physical' else 5
    if type(evidence['interfaces']) is not dict or len(evidence['interfaces']) != count:
        raise ValueError('Original document interface inventory differs')
    for name in (*evidence['reports'], *evidence['interfaces']):
        manifest.path_name(name)
    return evidence


def _encode_evidence(evidence, *, document_profile):
    selected = _document_selector(document_profile)
    evidence = _evidence_shape(evidence, selected)
    documents = [raw for name, raw in evidence.items() if name not in ('reports', 'interfaces')]
    documents += list(evidence['reports'].values())
    interfaces = list(evidence['interfaces'].values())
    if (any(type(raw) is not bytes or len(raw) > manifest.MAX_MANIFEST for raw in documents)
            or any(type(raw) is not bytes or len(raw) > MAX_INTERFACE_BYTES for raw in interfaces)
            or sum(map(len, interfaces)) > _interface_budget(selected)
            or sum(map(len, documents + interfaces)) > MAX_EVIDENCE):
        raise ValueError('Original document evidence exceeds retained byte budget')
    proof = contract.strict_json(evidence['proof'], 'original document proof')
    _keys(proof, contract.PROOF_FIELDS, 'original document proof')
    _engine_contract(selected).validate_interface_bytes(proof['interfaces'], evidence['interfaces'],
                                                        **_engine_selection(selected))
    result = {name: _encoded(raw) for name, raw in evidence.items() if name not in ('reports', 'interfaces')}
    for name in ('reports', 'interfaces'):
        result[name] = {path: _encoded(raw) for path, raw in evidence[name].items()}
    return result


def _decode_evidence(value, *, document_profile):
    selected = _document_selector(document_profile)
    value = _evidence_shape(value, selected)
    scalars = [item for name, item in value.items() if name not in ('reports', 'interfaces')]
    encoded = scalars + list(value['reports'].values()) + list(value['interfaces'].values())
    if (any(type(item) is not str for item in encoded)
            or sum(map(len, encoded)) > ((MAX_EVIDENCE + 2) // 3) * 4 + 4 * len(encoded)):
        raise ValueError('Encoded document evidence exceeds retained byte budget')
    # Bound interface allocations together, before decoding any of them.
    interface_values = list(value['interfaces'].values())
    if sum(map(len, interface_values)) > ((_interface_budget(selected) + 2) // 3) * 4 + 4 * len(interface_values):
        raise ValueError('Encoded document interfaces exceed aggregate budget')
    result = {name: _decoded(raw, manifest.MAX_MANIFEST, name) for name, raw in value.items()
              if name not in ('reports', 'interfaces')}
    result['reports'] = {name: _decoded(raw, manifest.MAX_MANIFEST, 'original runtime report') for name, raw in value['reports'].items()}
    result['interfaces'] = {name: _decoded(raw, MAX_INTERFACE_BYTES, 'original document interface') for name, raw in value['interfaces'].items()}
    raw_documents = [raw for name, raw in result.items() if name not in ('reports', 'interfaces')] + list(result['reports'].values())
    if (sum(map(len, result['interfaces'].values())) > _interface_budget(selected)
            or sum(map(len, raw_documents)) + sum(map(len, result['interfaces'].values())) > MAX_EVIDENCE):
        raise ValueError('Decoded document evidence exceeds retained byte budget')
    proof = contract.strict_json(result['proof'], 'original document proof')
    _keys(proof, contract.PROOF_FIELDS, 'original document proof')
    _engine_contract(selected).validate_interface_bytes(proof['interfaces'], result['interfaces'],
                                                        **_engine_selection(selected))
    return result


def make_prefix(blobs, factory, wasm, engine, kernel_receipt, kernel_receipt_pin, notices,
                source_sha256, kernel_inputs_sha256, profile, *, document_profile, group_files=None):
    """Pure fixture-capable assembly; publication requires real original proofs."""
    selected = _document_selector(document_profile)
    profile = _profile(profile)
    if type(blobs) is not dict:
        raise ValueError('Expected owned document host asset mapping')
    blobs = dict(blobs.items())
    child = validate_assets(blobs, document_profile=selected)
    metadata = contract.json_copy(engine.as_dict(), 'document consumer inspection')
    selected_contract = _engine_contract(selected)
    if type(metadata) is not dict or metadata.get('scope') not in (selected_contract.SCOPE, selected_contract.EMBEDDED_SCOPE):
        raise ValueError('Document carrier requires the separate document consumer')
    engine_profile = _engine_profile(metadata['engine_profile'], selected)
    receipt, kernel_eligible = inspect_kernel_receipt(kernel_receipt, kernel_receipt_pin, factory, wasm,
        profile, engine_profile, document_profile=selected, expected_kernel_inputs=kernel_inputs_sha256,
        host_assets=_asset_hashes(blobs))
    evidence = _plain(engine.evidence)
    binary = contract.strict_json(evidence['binary_manifest'], 'original engine binary manifest')
    if (not _same(receipt['toolchain']['target'], binary['target'])
            or receipt['toolchain']['sdk_sha256'] != binary['toolchain']['paired_sdk_sha256']):
        raise ValueError('Foundation and engine paired target/SDK observations differ')
    if metadata['factory_policy']['data_loading'] != 'embedded' or any(item['role'] == 'data' for item in metadata['assets'].values()):
        raise ValueError('External engine data requires a reviewed CSP-compatible retained-byte preloader; no fallback is attempted')
    for value in (source_sha256, kernel_inputs_sha256):
        _sha(value, 'observed packaging source')
    if type(notices) is not dict or not notices or len(notices) > 128:
        raise ValueError('Explicit bounded Foundation notices are required')
    all_notices = {}
    for label, raw in notices.items():
        if type(label) is not str or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}', label) or type(raw) is not bytes:
            raise ValueError('Invalid Foundation notice')
        all_notices[label] = raw
    for name, raw in engine.notices.items():
        label = 'engine/' + name
        if len(label) > 256 or label in all_notices:
            raise ValueError('Engine notice label exceeds retained browser closure')
        all_notices[label] = bytes(raw)
    if (len(all_notices) > 128 or any(len(raw) > MAX_NOTICE for raw in all_notices.values())
            or sum(map(len, all_notices.values())) > MAX_NOTICES):
        raise ValueError('Document carrier notices exceed retained bounds')
    for raw in all_notices.values():
        raw.decode('utf-8')
    roles = {item['role']: name for name, item in metadata['assets'].items() if item['role'] in ('factory', 'wasm')}
    if set(roles) != {'factory', 'wasm'}:
        raise ValueError('Missing complete document engine factory/Wasm roles')
    pins = {name: metadata[key] for name, key in (('recipe', 'recipe_id'), ('manifest', 'binary_manifest_sha256'),
             ('proof', 'proof_sha256'), ('runtime', 'runtime_sha256'))}
    groups = _plain(group_files if group_files is not None else metadata['group_files'])
    if type(groups) is not dict or set(groups) != set(sdk.group_names(pins['recipe'])):
        raise ValueError('Complete original engine group identities are required')
    for name, digest in groups.items():
        _sha(digest, 'original engine group ' + name)
    kernel = {'schema_version': 1, 'kind': _kind(selected, KERNEL_KIND, EDITOR_KERNEL_KIND), 'kernel_profile': profile,
        'kernel_wasm_lookup': WASM_NAME, 'engine_wasm_lookup': metadata['assets'][roles['wasm']]['lookup_name'],
        'kernel_factory': _asset(factory), 'kernel_wasm': _asset(wasm),
        'engine_factory': _asset(bytes(engine.assets[roles['factory']])),
        'engine_wasm': _asset(bytes(engine.assets[roles['wasm']])), 'engine_profile': engine_profile,
        'engine_assets': {}, 'notices': {name: _asset(raw) for name, raw in sorted(all_notices.items())}}
    envelope = {'schema_version': 1, 'kind': _kind(selected, KIND, EDITOR_KIND), 'document_profile': selected, 'kernel': kernel,
        'modules': {name: _encoded(raw) for name, raw in sorted(blobs.items())},
        'evidence': {'engine': _encode_evidence(evidence, document_profile=selected), 'kernel_receipt': _encoded(kernel_receipt)},
        'identities': {'source_observed_at_package_sha256': source_sha256,
            'kernel_inputs_sha256': kernel_inputs_sha256, 'kernel_receipt_sha256': kernel_receipt_pin,
            'engine_recipe_sha256': pins['recipe'], 'engine_manifest_sha256': pins['manifest'],
            'engine_proof_sha256': pins['proof'], 'engine_runtime_sha256': pins['runtime']},
        'group_files': groups}
    encoded = _encoded(container.canonical_json(envelope))
    prefix = (OPEN + OUTER_STYLE + MIDDLE + encoded + BOOT_OPEN
              + bootstrap_source(document_profile=selected) + BOOT_CLOSE).encode('utf-8')
    if len(prefix) > container.MAX_KERNEL:
        raise ValueError('Measured encoded document prefix exceeds carrier limit; reviewed kernel/container maintenance is required')
    container._html_shell(prefix)
    facts = {'production_eligible': metadata.get('production_eligible') is True and kernel_eligible,
             'engine': metadata, 'kernel_receipt': receipt, 'child': child}
    return prefix, envelope, facts


def inspect_prefix(prefix):
    """Check the retained owned closure without claiming whole-archive checks."""
    if type(prefix) is not bytes or not 1 <= len(prefix) <= container.MAX_KERNEL:
        raise ValueError('Invalid document rich browser prefix length')
    container._html_shell(prefix)
    blocks = re.findall(rb'<script type="application/octet-stream" id="foundation-rich-kernel">([A-Za-z0-9+/=]+)</script>', prefix)
    if len(blocks) != 1:
        raise ValueError('Missing canonical document browser asset block')
    envelope = contract.strict_json(_decoded(blocks[0].decode('ascii'), container.MAX_KERNEL, 'document envelope'),
                                    'document browser envelope', maximum=container.MAX_KERNEL)
    _keys(envelope, ENVELOPE_FIELDS, 'document browser envelope')
    selected = _document_selector(envelope['document_profile'])
    if (type(envelope['schema_version']) is not int or envelope['schema_version'] != 1
            or envelope['kind'] != _kind(selected, KIND, EDITOR_KIND)):
        raise ValueError('Unsupported document browser envelope')
    kernel = envelope['kernel']
    _keys(kernel, KERNEL_FIELDS, 'document browser kernel')
    if (type(kernel['schema_version']) is not int or kernel['schema_version'] != 1
            or kernel['kind'] != _kind(selected, KERNEL_KIND, EDITOR_KERNEL_KIND)):
        raise ValueError('Unsupported document retained kernel')
    profile = _profile(kernel['kernel_profile'])
    _engine_profile(kernel['engine_profile'], selected)
    modules = envelope['modules']
    if (type(modules) is not dict or set(modules) != set(asset_names(document_profile=selected))
            or any(type(raw) is not str for raw in modules.values())
            or sum(map(len, modules.values())) > ((MAX_MODULES + 2) // 3) * 4 + 4 * len(modules)):
        raise ValueError('Document host module inventory/aggregate budget differs')
    blobs = {name: _decoded(raw, MAX_MODULE, 'document host module') for name, raw in modules.items()}
    factory = _read_asset(kernel['kernel_factory'], MAX_FACTORY, 'Foundation factory')
    wasm = _read_asset(kernel['kernel_wasm'], MAX_KERNEL_WASM, 'Foundation Wasm')
    _keys(envelope['identities'], ('source_observed_at_package_sha256', 'kernel_inputs_sha256', 'kernel_receipt_sha256',
        'engine_recipe_sha256', 'engine_manifest_sha256', 'engine_proof_sha256', 'engine_runtime_sha256'), 'retained document identities')
    ids = envelope['identities']
    for name, digest in ids.items():
        _sha(digest, name)
    _keys(envelope['evidence'], ('engine', 'kernel_receipt'), 'retained document evidence')
    evidence = _decode_evidence(envelope['evidence']['engine'], document_profile=selected)
    receipt = _decoded(envelope['evidence']['kernel_receipt'], manifest.MAX_MANIFEST, 'Foundation receipt')
    proof = contract.strict_json(evidence['proof'], 'original document proof')
    if type(proof) is not dict or type(proof.get('assets')) is not dict:
        raise ValueError('Missing document engine asset declarations')
    roles = {item.get('role'): name for name, item in proof['assets'].items()
             if type(item) is dict and item.get('role') in ('factory', 'wasm')}
    if set(roles) != {'factory', 'wasm'} or kernel['engine_assets'] != {}:
        raise ValueError('Unsupported document engine data closure; embedded data is required')
    if (kernel['kernel_wasm_lookup'] != WASM_NAME
            or kernel['engine_wasm_lookup'] != proof['assets'][roles['wasm']].get('lookup_name')):
        raise ValueError('Document retained Wasm lookups differ from actual declarations')
    assets = {roles['factory']: _read_asset(kernel['engine_factory'], MAX_FACTORY, 'engine factory'),
              roles['wasm']: _read_asset(kernel['engine_wasm'], MAX_ENGINE_WASM, 'engine Wasm')}
    if type(kernel['notices']) is not dict or len(kernel['notices']) > 128:
        raise ValueError('Invalid document retained notices')
    # Preflight encoded aggregate before materializing a whole notice closure.
    if any(type(item) is not dict or type(item.get('data')) is not str for item in kernel['notices'].values()):
        raise ValueError('Invalid document notice asset shape')
    if sum(len(item['data']) for item in kernel['notices'].values()) > ((MAX_NOTICES + 2) // 3) * 4 + 4 * len(kernel['notices']):
        raise ValueError('Encoded document notices exceed aggregate budget')
    notices = {name: _read_asset(item, MAX_NOTICE, 'notice') for name, item in kernel['notices'].items()}
    own_notices = {name: raw for name, raw in notices.items() if not name.startswith('engine/')}
    engine_notices = {name[len('engine/'):]: raw for name, raw in notices.items() if name.startswith('engine/')}
    parsed = contract.strict_json(receipt, 'document Foundation receipt')
    _receipt_header(parsed, profile, selected)
    pins = {name: ids['engine_' + key + '_sha256'] for name, key in
            (('recipe', 'recipe'), ('manifest', 'manifest'), ('proof', 'proof'), ('runtime', 'runtime'))}
    engine = _engine_consumer(selected).inspect_embedded_consumer(evidence=evidence, assets=assets,
        notices=engine_notices, pins=pins, kernel_target=parsed['toolchain']['target'],
        paired_sdk=parsed['toolchain']['sdk_sha256'], **_engine_selection(selected))
    rebuilt, metadata, facts = make_prefix(blobs, factory, wasm, engine, receipt, ids['kernel_receipt_sha256'], own_notices,
        ids['source_observed_at_package_sha256'], ids['kernel_inputs_sha256'], profile,
        document_profile=selected, group_files=envelope['group_files'])
    if not _same(metadata, envelope) or rebuilt != prefix:
        raise ValueError('Document browser prefix differs from canonical retained inputs')
    return envelope, facts


def _descriptor(prefix, envelope, facts, kernel_inputs):
    profile = envelope['kernel']['kernel_profile']
    selected = _document_selector(envelope['document_profile'])
    return {'schema_version': 1, 'kind': 'foundation-kernel', 'carrier': 'html', 'profile': profile,
        'append_format': 1, **rendering.composition_descriptor_policy(profile, facts['kernel_receipt'],
            eligible=facts['production_eligible']), 'boundary_offset': None,
        'executable': {'length': len(prefix), 'sha256': container.digest(prefix)}, 'kernel_inputs': kernel_inputs,
        'provenance': {'kind': _kind(selected, KIND, EDITOR_KIND), 'qualification': QUALIFICATION,
            'runtime': 'one-direct-worker/two-private-wasm-instances', 'renderer_modes': ['isolated-surface'],
            'csp': CSP, 'identities': envelope['identities'], 'group_files': envelope['group_files'],
            'inputs': {name: container.digest(_decoded(raw, MAX_MODULE, name)) for name, raw in envelope['modules'].items()},
            'child': facts['child'], 'build_origin': facts['kernel_receipt']['build_origin'],
            'source_binding': 'observed packaging inputs and pinned original runtime observations; not release certification'}}


def package(assets, output, notice_paths, *, profile, document_profile, source_root, engine_group,
            engine_recipe_sha256, engine_manifest_sha256, engine_proof_sha256, engine_runtime_sha256,
            kernel_receipt, kernel_receipt_sha256, developer_unqualified=False, kernel_module_dir=None):
    if developer_unqualified is not True:
        raise ValueError('Initial document carrier requires explicit --developer-unqualified; runtime facts remain mandatory')
    selected, profile = _document_selector(document_profile), _profile(profile)
    from appended_policy import kernel_source_tree
    from source_identity import ignored_source_path, source_tree
    source_root = Path(source_root).resolve(strict=True)
    output = Path(output).absolute()
    destination = output.resolve(strict=False)
    if source_root in destination.parents and not ignored_source_path(destination.relative_to(source_root).as_posix() + '/'):
        raise ValueError('Document carrier output must be outside source inputs or in ignored build/.agent-work')
    if output.exists() or output.is_symlink():
        raise ValueError('Document carrier output destination must be new')
    container._ordinary_path(output.parent, directory=True)
    source_before, inputs_before = source_tree(source_root), kernel_source_tree(source_root)
    snapshots = []
    receipt = container._snapshot(kernel_receipt, manifest.MAX_MANIFEST)
    snapshots.append(receipt)
    if container.digest(receipt.content) != _sha(kernel_receipt_sha256, 'Foundation receipt'):
        raise ValueError('Document Foundation receipt differs from independent pin')
    preliminary = contract.strict_json(receipt.content, 'document Foundation receipt')
    _receipt_header(preliminary, profile, selected)
    selection = dict(expected_recipe=engine_recipe_sha256, expected_manifest=engine_manifest_sha256,
        expected_proof=engine_proof_sha256, expected_runtime=engine_runtime_sha256,
        kernel_target=preliminary['toolchain']['target'], paired_sdk=preliminary['toolchain']['sdk_sha256'],
        **_engine_selection(selected))
    selected_consumer = _engine_consumer(selected)
    engine = selected_consumer.verify_kernel_consumer(engine_group, **selection)
    blobs = {}
    for name in asset_names(document_profile=selected):
        saved = container._snapshot(Path(assets) / name, MAX_MODULE)
        snapshots.append(saved); blobs[name] = saved.content
    module_dir = Path(kernel_module_dir) if kernel_module_dir is not None else Path(assets)
    factory = container._snapshot(module_dir / FACTORY_NAME, MAX_FACTORY)
    wasm = container._snapshot(module_dir / WASM_NAME, MAX_KERNEL_WASM)
    snapshots.extend((factory, wasm))
    notice_inputs = {}
    for item in notice_paths:
        label, raw = str(item).split('=', 1) if '=' in str(item) else (Path(item).name, str(item))
        if label in notice_inputs:
            raise ValueError('Duplicate Foundation notice label')
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}', label):
            raise ValueError('Invalid Foundation notice label')
        notice_inputs[label] = raw
        if len(notice_inputs) + len(engine.notices) > 128:
            raise ValueError('Document carrier notices exceed retained count bound')
    notice_bytes = sum(len(raw) for raw in engine.notices.values())
    if notice_bytes > MAX_NOTICES:
        raise ValueError('Original engine notices exceed retained aggregate budget')
    notices = {}
    for label, path in notice_inputs.items():
        saved = container._snapshot(path, min(MAX_NOTICE, MAX_NOTICES - notice_bytes))
        notice_bytes += len(saved.content)
        snapshots.append(saved); notices[label] = saved.content
    prefix, envelope, facts = make_prefix(blobs, factory.content, wasm.content, engine, receipt.content,
        kernel_receipt_sha256, notices, source_before['tree_sha256'], inputs_before['tree_sha256'], profile, document_profile=selected)
    if not facts['production_eligible']:
        raise ValueError('Real complete engine and Foundation document runtime observations are required; fixtures cannot publish')
    checked_envelope, checked_facts = inspect_prefix(prefix)
    if not _same(checked_envelope, envelope) or not checked_facts['production_eligible']:
        raise ValueError('Document prefix failed complete prepublication closure verification')
    descriptor = _descriptor(prefix, envelope, facts, inputs_before)
    container.validate_descriptor(descriptor)
    container.parse_artifact(prefix, descriptor, expected_mode='neither')
    checked = selected_consumer.verify_kernel_consumer(engine_group, **selection)
    if not _same(checked.as_dict(), engine.as_dict()):
        raise ValueError('Retained document engine changed before publication')
    if source_tree(source_root) != source_before or kernel_source_tree(source_root) != inputs_before:
        raise ValueError('Source inputs changed during document carrier packaging')
    for saved in snapshots:
        container._recheck(saved)
    output.mkdir(exist_ok=False)
    contents = {HTML_NAME: prefix, DESCRIPTOR_NAME: container.canonical_json(descriptor)}
    for name, raw in contents.items():
        container._write_new(output / name, raw, snapshots)
    checksums = ''.join(container.digest(contents[name]) + '  ' + name + '\n' for name in sorted(contents)).encode('ascii')
    container._write_new(output / 'manifest.sha256', checksums, snapshots)
    verify(output)
    return descriptor


def inspect_output(output, descriptor_sha256=None):
    """Inspect complete carrier integrity; fixtures remain explicitly ineligible."""
    output = container._ordinary_path(output, directory=True)
    if {path.name for path in output.iterdir()} != {HTML_NAME, DESCRIPTOR_NAME, 'manifest.sha256'}:
        raise ValueError('Incomplete or unexpected document browser inventory')
    raw = container._snapshot(output / DESCRIPTOR_NAME, container.MAX_INDEX).content
    if descriptor_sha256 is not None and container.digest(raw) != _sha(descriptor_sha256, 'retained descriptor'):
        raise ValueError('Document browser descriptor differs from independent pin')
    descriptor = container.validate_descriptor(contract.strict_json(raw, 'document browser descriptor', maximum=container.MAX_INDEX))
    from appended_policy import validate_kernel_inputs
    validate_kernel_inputs(descriptor.get('kernel_inputs'))
    prefix = container._snapshot(output / HTML_NAME, container.MAX_KERNEL).content
    container.parse_artifact(prefix, descriptor, expected_mode='neither')
    envelope, facts = inspect_prefix(prefix)
    rebuilt = _descriptor(prefix, envelope, facts, descriptor['kernel_inputs'])
    if not _same(descriptor, rebuilt) or descriptor['kernel_inputs']['tree_sha256'] != envelope['identities']['kernel_inputs_sha256']:
        raise ValueError('Document descriptor differs from canonical policy/inputs')
    expected = ''.join(container.digest(data) + '  ' + name + '\n' for name, data in sorted(
        ((HTML_NAME, prefix), (DESCRIPTOR_NAME, raw)))).encode('ascii')
    if container._snapshot(output / 'manifest.sha256', 1024).content != expected:
        raise ValueError('Document carrier checksum inventory differs')
    facts['independently_pinned_descriptor'] = descriptor_sha256 is not None
    return descriptor, facts


def verify(output, descriptor_sha256=None):
    descriptor, facts = inspect_output(output, descriptor_sha256)
    if not facts['production_eligible']:
        raise ValueError('Retained document carrier has no complete real runtime observations')
    return descriptor


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify', action='store_true')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--descriptor-sha256')
    parser.add_argument('--document-profile', choices=('pixel', 'physical', 'editor'))
    parser.add_argument('--assets', type=Path)
    parser.add_argument('--kernel-module-dir', type=Path)
    parser.add_argument('--source-root', type=Path)
    parser.add_argument('--profile', choices=tuple(POLICIES))
    parser.add_argument('--notice', action='append', default=[])
    parser.add_argument('--engine-group', type=Path)
    for name in ('engine-recipe', 'engine-manifest', 'engine-proof', 'engine-runtime', 'kernel-receipt'):
        parser.add_argument('--' + name + '-sha256')
    parser.add_argument('--kernel-receipt', type=Path)
    parser.add_argument('--developer-unqualified', action='store_true')
    args = parser.parse_args(argv)
    try:
        if args.verify:
            production = (args.document_profile, args.assets, args.kernel_module_dir, args.source_root, args.profile, args.notice,
                args.engine_group, args.engine_recipe_sha256, args.engine_manifest_sha256, args.engine_proof_sha256,
                args.engine_runtime_sha256, args.kernel_receipt, args.kernel_receipt_sha256, args.developer_unqualified)
            if any(production):
                raise ValueError('Verification reads retained policy; production flags cannot upgrade a carrier')
            result = verify(args.output, args.descriptor_sha256)
        else:
            if args.descriptor_sha256:
                raise ValueError('--descriptor-sha256 applies only to verification')
            required = ('document_profile', 'assets', 'source_root', 'profile', 'engine_group', 'engine_recipe_sha256',
                'engine_manifest_sha256', 'engine_proof_sha256', 'engine_runtime_sha256', 'kernel_receipt', 'kernel_receipt_sha256')
            if any(getattr(args, name) is None for name in required):
                raise ValueError('Document production requires explicit selection/assets/profile/source/group and every independent input pin')
            result = package(args.assets, args.output, args.notice, profile=args.profile, document_profile=args.document_profile,
                source_root=args.source_root, engine_group=args.engine_group, engine_recipe_sha256=args.engine_recipe_sha256,
                engine_manifest_sha256=args.engine_manifest_sha256, engine_proof_sha256=args.engine_proof_sha256,
                engine_runtime_sha256=args.engine_runtime_sha256, kernel_receipt=args.kernel_receipt,
                kernel_receipt_sha256=args.kernel_receipt_sha256, developer_unqualified=args.developer_unqualified,
                kernel_module_dir=args.kernel_module_dir)
        print(container.canonical_json({'kind': result['provenance']['kind'], 'profile': result['profile'],
            'qualification': result['provenance']['qualification'], 'independently_pinned_descriptor': args.descriptor_sha256 is not None}).decode())
        return 0
    except (ValueError, OSError, UnicodeError, KeyError, TypeError) as error:
        print('document rich browser kernel: ' + str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
