#!/usr/bin/env python3
"""Pure initial rich-browser carrier producer over independently pinned inputs.

This separate format never builds, downloads, loads an engine or upgrades the
binary browser producer. Parser fixtures are inspectable, never publishable.
"""
import argparse
import base64
import binascii
from html import escape
import json
from pathlib import Path
import re
import sys

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
import appended_container as container
import appended_engine_manifest as manifest
import browser_bundle
import package_wasm

KIND = 'foundation-rich-browser-kernel-v1'
PHYSICAL_KIND = 'foundation-rich-browser-physical-kernel-v1'
PHYSICAL_KERNEL_KIND = 'foundation-copied-engine-physical-browser'
PHYSICAL_RECEIPT_KIND = 'foundation-rich-browser-physical-kernel-proof-v1'
COMPOSITION_RECEIPT_KIND = 'foundation-rich-browser-composition-kernel-proof-v1'
PHYSICAL_COMPOSITION_RECEIPT_KIND = 'foundation-rich-browser-physical-composition-kernel-proof-v1'
COMPOSITION_RECEIPT_KINDS = {
    'foundation-rich-browser-kernel-proof-v1': COMPOSITION_RECEIPT_KIND,
    PHYSICAL_RECEIPT_KIND: PHYSICAL_COMPOSITION_RECEIPT_KIND,
    'foundation-rich-browser-document-kernel-proof-v1': 'foundation-rich-browser-document-composition-kernel-proof-v1',
    'foundation-rich-browser-editor-kernel-proof-v1': 'foundation-rich-browser-editor-composition-kernel-proof-v1',
}
COMPOSITION_EXPORT = 'gui_web_application_composition_v1'
COMPOSITION_CHECK = 'application_composition_query'
HTML_NAME = 'foundation-appended-engine-browser.html'
DESCRIPTOR_NAME = 'kernel.json'
QUALIFICATION = 'unqualified-development'
CSP = package_wasm.CSP
MAX_MODULE = 4 * 1024 * 1024
MAX_MODULES = 32 * 1024 * 1024
MAX_FACTORY = 16 * 1024 * 1024
MAX_KERNEL_WASM = 64 * 1024 * 1024
MAX_NOTICES = 16 * 1024 * 1024
MAX_NOTICE = 4 * 1024 * 1024
MAX_EVIDENCE = 64 * 1024 * 1024
MAX_COMMAND_CATALOG = 64 * 1024
FACTORY_NAME = 'gui_appended_engine_wasm.js'
WASM_NAME = 'gui_appended_engine_wasm.wasm'
POLICIES = {
    'web': {'abi': {'major': 1, 'minor': 0}, 'services': ['foundation.kernel'],
            'capabilities': ['foundation.startup.v1']},
    'both': {'abi': {'major': 1, 'minor': 0},
             'services': ['foundation.kernel', 'foundation.providers'],
             'capabilities': ['foundation.providers.v1', 'foundation.startup.v1']},
}
# These are retained parent/Worker imports. Renderer source modules below are
# additional inert inputs used to verify the two generated pure-data bundles.
IMPORTS = {
    'appended_engine_browser_bootstrap.mjs': (
        'browser_embedding.mjs', 'wasm_transport.mjs', 'renderer_channel.mjs',
        'browser_surface_protocol.mjs', 'renderer_surface_child_bundle.mjs',
        'appended_browser_bootstrap.mjs', 'engine_kernel_bridge.mjs'),
    'appended_browser_bootstrap.mjs': ('browser_embedding.mjs', 'wasm_transport.mjs'),
    'browser_embedding.mjs': ('browser_client.mjs', 'browser_services.mjs',
        'browser_lifecycle.mjs', 'renderer_channel.mjs', 'browser_limits.mjs',
        'renderer_child_bundle.mjs'),
    'browser_client.mjs': ('browser_limits.mjs', 'browser_limits.mjs'),
    'browser_services.mjs': ('file_services.mjs',),
    'appended_engine_wasm_worker.mjs': ('engine_kernel_bridge.mjs',),
    'browser_lifecycle.mjs': (), 'wasm_transport.mjs': (),
    'file_services.mjs': (), 'engine_kernel_bridge.mjs': (),
    'browser_limits.mjs': (), 'browser_presenter.mjs': (),
    'renderer_channel.mjs': ('browser_limits.mjs',),
    'browser_surface_protocol.mjs': (),
    'renderer_child_bundle.mjs': (), 'renderer_surface_child_bundle.mjs': (),
}
OUTER_STYLE = ('html,body{margin:0;width:100%;height:100%}'
               '#application{width:100%;height:calc(100% - 3rem)}'
               '#application>iframe{display:block;width:100%;height:100%;border:0}'
               '#status{margin:.5rem;font:14px sans-serif}'
               'details{font:12px sans-serif}pre{white-space:pre-wrap}')
OPEN = ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta http-equiv="Content-Security-Policy" content="' + escape(CSP, quote=True) + '">'
        '<title>Rich application kernel</title><style>')
MIDDLE = ('</style></head><body><main id="application"></main>'
          '<p id="status" role="status">Starting application…</p>'
          '<script type="application/octet-stream" id="foundation-rich-kernel">')
BOOT_OPEN = '</script><script type="module" id="foundation-rich-bootstrap">'
BOOT_CLOSE = '</script>' + container.HTML_MARKER.decode('ascii')


def _consumer():
    import appended_engine_consumer
    return appended_engine_consumer


def _surface():
    import browser_surface_bundle
    return browser_surface_bundle


def _keys(value, names, label):
    if type(value) is not dict or set(value) != set(names):
        raise ValueError('invalid ' + label + ' fields')


def _sha(value, label):
    return manifest.sha256(value, label)


def _plain(value):
    """Copy recursively frozen JSON metadata without retaining caller objects."""
    from collections.abc import Mapping
    if isinstance(value, Mapping):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain(item) for item in value]
    return value


def _same_json(left, right):
    # Python equality aliases true/1 and false/0. Contract observations retain
    # their JSON types even inside nested Wasm facts and profile records.
    return container.canonical_json(left) == container.canonical_json(right)


def _encoded(data):
    return base64.b64encode(data).decode('ascii')


def _decoded(value, limit, label):
    if type(value) is not str or len(value) > ((limit + 2) // 3) * 4:
        raise ValueError('oversized or invalid base64 ' + label)
    try:
        result = base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error) as error:
        raise ValueError('invalid base64 ' + label) from error
    if len(result) > limit or _encoded(result) != value:
        raise ValueError('noncanonical or oversized base64 ' + label)
    return result


def _asset(data):
    return {'data': _encoded(data), 'sha256': container.digest(data)}


def _read_asset(value, limit, label):
    _keys(value, ('data', 'sha256'), label)
    data = _decoded(value['data'], limit, label)
    if container.digest(data) != _sha(value['sha256'], label):
        raise ValueError(label + ' digest differs')
    return data


def _profile(value):
    if type(value) is not str or value not in POLICIES:
        raise ValueError('rich kernel profile must be web or both')
    return value


def _physical(value):
    if type(value) is not bool:
        raise ValueError('physical input selection must be an explicit boolean')
    return value


def _binding(physical_input):
    consumer = _consumer()
    return consumer.PHYSICAL_BINDING if _physical(physical_input) else consumer.BINDING


def _asset_hashes(blobs):
    return {name: container.digest(data) for name, data in sorted(blobs.items())}


def asset_names():
    surface = _surface()
    return tuple(sorted(set(IMPORTS) | set(browser_bundle.CHILD_MODULES) |
                        set(surface.CHILD_MODULES) | {'style.css'}))


def validate_assets(blobs):
    if type(blobs) is not dict or set(blobs) != set(asset_names()):
        raise ValueError('rich browser host asset inventory differs')
    if any(type(value) is not bytes or len(value) > MAX_MODULE for value in blobs.values()) or sum(map(len, blobs.values())) > MAX_MODULES:
        raise ValueError('rich browser host assets exceed limits')
    for name, data in blobs.items():
        data.decode('utf-8')
    for name, dependencies in IMPORTS.items():
        found = re.findall(r"['\"]\./([A-Za-z0-9_.-]+\.mjs)['\"]", blobs[name].decode('utf-8'))
        if sorted(found) != sorted(dependencies):
            raise ValueError('reviewed rich parent dependency changed: ' + name)
    ordinary = browser_bundle.assemble({name: blobs[name] for name in browser_bundle.CHILD_MODULES + ('style.css',)})
    if blobs[browser_bundle.BUNDLE_NAME] != browser_bundle.module_bytes(ordinary):
        raise ValueError('ordinary inert child bundle differs')
    surface = _surface()
    selected = surface.verify_assets({name: blobs[name] for name in surface.CHILD_MODULES + ('style.css', surface.BUNDLE_NAME)})
    return {'ordinary': {'protocol': ordinary['CHILD_PROTOCOL'], 'sandbox': ordinary['CHILD_SANDBOX'],
                         'csp': ordinary['CHILD_CSP'], 'script_sha256': container.digest(ordinary['CHILD_SCRIPT'].encode())},
            'surface': {'protocol': selected['CHILD_PROTOCOL'], 'sandbox': selected['CHILD_SANDBOX'],
                        'csp': selected['CHILD_CSP'], 'script_sha256': container.digest(selected['CHILD_SCRIPT'].encode())}}


def composition_receipt_variant(value, original_kind):
    """Select an explicit additive receipt kind without relaxing any old schema."""
    if original_kind not in COMPOSITION_RECEIPT_KINDS:
        raise ValueError('unknown original Foundation receipt family')
    return type(value) is dict and value.get('kind') == COMPOSITION_RECEIPT_KINDS[original_kind]


def validate_compiled_composition(observation, profile):
    """Validate a retained actual query observation; never execute the getter."""
    profile = _profile(profile)
    _keys(observation, ('export', 'signature', 'observed_result', 'before_engine_factory', 'before_configure'),
          'compiled application composition')
    if (observation['export'] != COMPOSITION_EXPORT or
            not _same_json(observation['signature'], {'params': [], 'results': ['i32']}) or
            type(observation['observed_result']) is not int or
            observation['observed_result'] != (5 if profile == 'web' else 7) or
            observation['before_engine_factory'] is not True or observation['before_configure'] is not True):
        raise ValueError('compiled application composition query observation is missing or incompatible')
    return observation


def composition_descriptor_policy(profile, checked_receipt, *, eligible):
    """Extend copied policy only after admission of actual composition receipts.

    Callers supply the receipt returned by inspect_kernel_receipt and the
    existing carrier eligibility result. Parser fixtures remain inspectable
    observations and cannot acquire the additional capabilities here.
    """
    profile = _profile(profile)
    policy = _plain(POLICIES[profile])
    if (type(checked_receipt) is not dict or
            checked_receipt.get('kind') not in COMPOSITION_RECEIPT_KINDS.values()):
        return policy
    validate_compiled_composition(checked_receipt.get('compiled_composition'), profile)
    if (eligible is not True or checked_receipt.get('scope') != 'foundation-rich-kernel-runtime' or
            checked_receipt.get('status') != 'passed' or type(checked_receipt.get('checks')) is not dict or
            checked_receipt['checks'].get(COMPOSITION_CHECK) != 'passed'):
        return policy
    policy['capabilities'] = sorted(policy['capabilities'] + ['foundation.gui-composition.v1'])
    if profile == 'both':
        policy['services'] = sorted(policy['services'] + ['foundation.view'])
        policy['capabilities'] = sorted(policy['capabilities'] + ['foundation.view.v1'])
    return policy


def inspect_kernel_receipt(raw, pin, factory, wasm, profile, engine_profile, *, expected_kernel_inputs=None,
                           physical_input=False, host_assets=None):
    """Validate pinned observations; never execute or newly certify them."""
    profile = _profile(profile)
    physical_input = _physical(physical_input)
    if type(raw) is not bytes or len(raw) > manifest.MAX_MANIFEST or container.digest(raw) != _sha(pin, 'kernel receipt'):
        raise ValueError('kernel receipt differs from independent pin')
    value = manifest.json_bytes(raw)
    original_kind = PHYSICAL_RECEIPT_KIND if physical_input else 'foundation-rich-browser-kernel-proof-v1'
    composition = composition_receipt_variant(value, original_kind)
    fields = ('schema_version', 'kind', 'scope', 'status', 'profile', 'source', 'toolchain',
              'artifacts', 'wasm_facts', 'compiled_profile', 'engine_profile', 'checks', 'build_origin')
    _keys(value, fields + (('compiled_input_profile', 'host_assets') if physical_input else ()) +
          (('compiled_composition',) if composition else ()), 'kernel receipt')
    if (type(value['schema_version']) is not int or value['schema_version'] != 1 or
            value['kind'] != (COMPOSITION_RECEIPT_KINDS[original_kind] if composition else original_kind) or value['profile'] != profile or
            value['scope'] not in ('foundation-rich-kernel-runtime', 'parser-fixture-only') or
            value['status'] not in ('passed', 'unfinished', 'failed')):
        raise ValueError('unsupported rich kernel receipt')
    _keys(value['source'], ('tree_sha256', 'kernel_inputs_sha256'), 'kernel source')
    for key, item in value['source'].items():
        _sha(item, 'kernel source ' + key)
    if expected_kernel_inputs is not None and value['source']['kernel_inputs_sha256'] != expected_kernel_inputs:
        raise ValueError('compiled kernel inputs differ from observed kernel source projection')
    _keys(value['toolchain'], ('sdk_sha256', 'target'), 'kernel toolchain')
    _sha(value['toolchain']['sdk_sha256'], 'Foundation paired SDK')
    target = manifest.target_contract(value['toolchain']['target'])
    if target['system'] != 'Emscripten' or target['processor'] != 'wasm32':
        raise ValueError('rich Foundation kernel requires Emscripten wasm32')
    _keys(value['artifacts'], ('factory', 'wasm'), 'kernel artifacts')
    for role, data, limit in (('factory', factory, MAX_FACTORY), ('wasm', wasm, MAX_KERNEL_WASM)):
        item = value['artifacts'][role]
        _keys(item, ('sha256', 'bytes', 'lookup_name') if role == 'wasm' else ('sha256', 'bytes'), 'kernel artifact')
        if role == 'wasm' and item['lookup_name'] != WASM_NAME:
            raise ValueError('Foundation Wasm lookup must match its exact compiled output name')
        manifest.integer(item['bytes'], 'kernel artifact bytes', 1, limit)
        if type(data) is not bytes or len(data) != item['bytes'] or container.digest(data) != _sha(item['sha256'], role):
            raise ValueError('compiled kernel ' + role + ' differs from receipt')
    consumer = _consumer()
    consumer.scan_factory(factory)
    facts = consumer.scan_wasm(wasm)
    if not _same_json(value['wasm_facts'], facts):
        raise ValueError('compiled Foundation Wasm facts differ from receipt')
    required = {'gui_web_engine_bridge_v1': ([], ['i32']), 'gui_web_engine_profile_v1': ([], ['i32']),
                'gui_web_engine_dispatch_v1': (['i32'] * 5, ['i32']),
                'gui_web_create': (['i32'], ['i32']), 'gui_web_receive': (['i32'], ['i32']),
                'gui_web_destroy': ([], []), 'malloc': (['i32'], ['i32']), 'free': (['i32'], [])}
    if physical_input:
        required['gui_web_engine_input_describe_v1'] = (['i32', 'i32'], ['i32'])
    if composition:
        required[COMPOSITION_EXPORT] = ([], ['i32'])
    exports = {item['name']: item for item in facts['exports']}
    for name, (parameters, results) in required.items():
        item = exports.get(name)
        if item is None or item['kind'] != 'function' or item['details'] != {'parameters': parameters, 'results': results}:
            raise ValueError('compiled Foundation kernel lacks required typed export ' + name)
    memories = facts['memories']
    if (facts['start'] is not None or len(memories) != 1 or memories[0]['shared'] or
            memories[0]['memory64'] or memories[0]['imported'] or memories[0]['maximum'] is None):
        raise ValueError('Foundation kernel requires one private finite wasm32 memory and no start section')
    if any(name in exports for name in ('main', '_main', '_start', 'bib_eval', 'bib_pump')):
        raise ValueError('diagnostic or automatic-main Foundation exports are ineligible')
    _keys(value['compiled_profile'], ('export', 'signature', 'observed_result', 'before_configure'), 'compiled profile')
    observed = value['compiled_profile']
    if (observed['export'] != 'gui_web_engine_profile_v1' or
            observed['signature'] != {'params': [], 'results': ['i32']} or
            type(observed['observed_result']) is not int or observed['observed_result'] != (1 if profile == 'web' else 2) or
            observed['before_configure'] is not True):
        raise ValueError('compiled rich profile query observation is missing or incompatible')
    if not _same_json(value['engine_profile'], engine_profile):
        raise ValueError('observed engine DESCRIBE identity differs from selected engine')
    checks = ('inert_factory', 'compiled_profile_query', 'engine_describe_match')
    if composition:
        validate_compiled_composition(value['compiled_composition'], profile)
        checks += (COMPOSITION_CHECK,)
    if physical_input:
        consumer = _consumer()
        if (type(engine_profile) is not dict or engine_profile.get('binding') != consumer.PHYSICAL_BINDING
                or engine_profile.get('kind') != 'foundation-copied-engine-physical-v1'):
            raise ValueError('physical input requires the explicit physical engine contract')
        observation = value['compiled_input_profile']
        _keys(observation, ('export', 'signature', 'observed_result', 'observed_output', 'observed_bytes',
                            'before_engine_factory', 'before_configure'), 'compiled input profile')
        output = _decoded(observation['observed_output'], 4095, 'compiled input profile output')
        if (observation['export'] != 'gui_web_engine_input_describe_v1'
                or not _same_json(observation['signature'], {'params': ['i32', 'i32'], 'results': ['i32']})
                or type(observation['observed_bytes']) is not int
                or observation['observed_bytes'] != len(output) or not output or b'\0' in output
                or observation['before_engine_factory'] is not True or observation['before_configure'] is not True):
            raise ValueError('compiled physical input query observation is missing or incompatible')
        # Retain the actual bounded query output, not a reconstructed byte-count
        # claim. The selected consumer separately validates its exact20 facts.
        consumer.validate_engine_profile(engine_profile, required_binding=consumer.PHYSICAL_BINDING)
        # The observation preserves the real emission, including harmless JSON
        # whitespace/order. Decode as a string so a BOM is not silently removed.
        observed_output = manifest.json_bytes(output.decode('utf-8'))
        if (not _same_json(observed_output, observation['observed_result'])
                or not _same_json(observed_output, engine_profile)):
            raise ValueError('compiled physical input query differs from engine DESCRIBE')
        if (type(host_assets) is not dict or type(value['host_assets']) is not dict
                or set(host_assets) != set(asset_names()) or not _same_json(value['host_assets'], host_assets)):
            raise ValueError('physical runtime host asset inventory differs from selected same-directory graph')
        for name, digest in value['host_assets'].items():
            _sha(digest, 'physical host asset ' + name)
        checks += ('input_profile_query', 'host_assets_match') + consumer.PHYSICAL_INPUT_CHECKS
    _keys(value['checks'], checks, 'kernel runtime checks')
    if any(item not in ('passed', 'unfinished', 'failed') for item in value['checks'].values()):
        raise ValueError('invalid original kernel runtime check status')
    manifest.text(value['build_origin'], 'kernel build origin')
    eligible = (value['scope'] == 'foundation-rich-kernel-runtime' and value['status'] == 'passed' and
                all(item == 'passed' for item in value['checks'].values()))
    return value, eligible


def _js(value):
    return json.dumps(value, ensure_ascii=True, separators=(',', ':')).replace('<', r'\u003c')


def bootstrap_source(physical_input=False):
    # The graph is fixed and verified before publication. Workers receive their
    # own rewritten module source; no renderer script executes in this realm.
    physical_input = _physical(physical_input)
    source = '''
const raw=document.querySelector('#foundation-rich-kernel').textContent;
const own=document.querySelector('#foundation-rich-bootstrap').textContent;
const prefix=new TextEncoder().encode(@@OPEN@@+document.querySelector('style').textContent+@@MIDDLE@@+raw+@@BOOT_OPEN@@+own+@@BOOT_CLOSE@@);
const decodeBase64=s=>{const raw=atob(s);const bytes=new Uint8Array(raw.length);for(let i=0;i<raw.length;i++)bytes[i]=raw.charCodeAt(i);return bytes;};
const retained=JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(decodeBase64(raw)));
const text=name=>new TextDecoder('utf-8',{fatal:true}).decode(decodeBase64(retained.modules[name]));
const urls=[],cache=new Map(),active=new Set(),graph=@@GRAPH@@;
const local=source=>{const url=URL.createObjectURL(new Blob([source],{type:'text/javascript'}));urls.push(url);return url;};
const rewritten=name=>{let source=text(name);for(const dep of graph[name]||[]){const target=JSON.stringify(moduleURL(dep));source=source.replace("'./"+dep+"'",target).replace('"./'+dep+'"',target);}return source;};
const moduleURL=name=>{if(cache.has(name))return cache.get(name);if(active.has(name))throw Error('Cyclic retained module graph');active.add(name);const url=local(rewritten(name));active.delete(name);cache.set(name,url);return url;};
try{const {startAppendedEngineBrowser}=await import(moduleURL('appended_engine_browser_bootstrap.mjs'));
await startAppendedEngineBrowser({prefix,kernel:retained.kernel,workerSource:rewritten('appended_engine_wasm_worker.mjs')});}
catch(error){document.querySelector('#status').textContent='Could not start application: '+String(error.message||error).slice(0,4096);}
finally{for(const url of urls)URL.revokeObjectURL(url);}
'''
    if physical_input:
        source = source.replace("await startAppendedEngineBrowser({prefix,kernel:retained.kernel,workerSource:rewritten('appended_engine_wasm_worker.mjs')});",
            "const physical=await import(moduleURL('renderer_surface_child_bundle.mjs'));\n"
            "const physicalRendererBundle=Object.freeze({CHILD_SCRIPT:physical.CHILD_SCRIPT,CHILD_SCRIPT_SHA256:physical.CHILD_SCRIPT_SHA256,"
            "CHILD_STYLE:physical.CHILD_STYLE,CHILD_CSP:physical.CHILD_CSP,CHILD_SANDBOX:physical.CHILD_SANDBOX,CHILD_PROTOCOL:physical.CHILD_PROTOCOL});\n"
            "await startAppendedEngineBrowser({prefix,kernel:retained.kernel,workerSource:rewritten('appended_engine_wasm_worker.mjs'),physicalRendererBundle});")
    return source.replace('@@OPEN@@', _js(OPEN)).replace('@@MIDDLE@@', _js(MIDDLE)).replace('@@BOOT_OPEN@@', _js(BOOT_OPEN)).replace('@@BOOT_CLOSE@@', _js(BOOT_CLOSE)).replace('@@GRAPH@@', _js(IMPORTS))


def _encode_evidence(evidence, physical_input=False):
    fields = ('binary_manifest', 'source_manifest', 'recipe', 'proof', 'provider_build', 'runtime', 'reports')
    _keys(evidence, fields + (('command_catalog',) if _physical(physical_input) else ()), 'embedded engine evidence')
    if type(evidence['reports']) is not dict or len(evidence['reports']) > 1024:
        raise ValueError('invalid original engine evidence inventory')
    raw_values = [value for name, value in evidence.items() if name != 'reports'] + list(evidence['reports'].values())
    if (any(type(value) is not bytes or len(value) > manifest.MAX_MANIFEST for value in raw_values) or
            sum(map(len, raw_values)) > MAX_EVIDENCE):
        raise ValueError('original engine evidence exceeds retained budget')
    if physical_input and len(evidence['command_catalog']) > MAX_COMMAND_CATALOG:
        raise ValueError('physical command catalog exceeds retained budget')
    result = {name: _encoded(value) for name, value in evidence.items() if name != 'reports'}
    result['reports'] = {manifest.path_name(name): _encoded(value) for name, value in evidence['reports'].items()}
    return result


def _decode_evidence(value, physical_input=False):
    fields = ('binary_manifest', 'source_manifest', 'recipe', 'proof', 'provider_build', 'runtime', 'reports')
    _keys(value, fields + (('command_catalog',) if _physical(physical_input) else ()), 'embedded engine evidence')
    if type(value['reports']) is not dict or len(value['reports']) > 1024:
        raise ValueError('invalid original engine evidence inventory')
    encoded_values = [item for name, item in value.items() if name != 'reports'] + list(value['reports'].values())
    if any(type(item) is not str for item in encoded_values) or sum(map(len, encoded_values)) > ((MAX_EVIDENCE + 2) // 3) * 4 + 4 * len(encoded_values):
        raise ValueError('original engine evidence exceeds retained budget')
    result = {name: _decoded(item, MAX_COMMAND_CATALOG if name == 'command_catalog' else manifest.MAX_MANIFEST, name)
              for name, item in value.items() if name != 'reports'}
    result['reports'] = {manifest.path_name(name): _decoded(item, manifest.MAX_MANIFEST, 'original runtime evidence')
                         for name, item in value['reports'].items()}
    if sum(map(len, (value for key, value in result.items() if key != 'reports'))) + sum(map(len, result['reports'].values())) > MAX_EVIDENCE:
        raise ValueError('original engine evidence exceeds retained budget')
    return result


def make_prefix(blobs, factory, wasm, engine, kernel_receipt, kernel_receipt_pin, notices,
                source_sha256, kernel_inputs_sha256, profile, *, group_files=None, physical_input=False):
    """Pure fixture-capable assembly; publication separately requires real proofs."""
    profile = _profile(profile)
    physical_input = _physical(physical_input)
    child = validate_assets(blobs)
    metadata = engine.as_dict()
    engine_profile = metadata['engine_profile']
    if (engine_profile.get('binding') != _binding(physical_input) or engine_profile.get('kind') !=
            ('foundation-copied-engine-physical-v1' if physical_input else 'foundation-copied-engine-v1')):
        raise ValueError('selected engine contract differs from explicit physical input mode')
    checked_receipt, kernel_eligible = inspect_kernel_receipt(kernel_receipt, kernel_receipt_pin, factory, wasm,
        profile, engine_profile, expected_kernel_inputs=kernel_inputs_sha256,
        physical_input=physical_input, host_assets=_asset_hashes(blobs) if physical_input else None)
    binary = manifest.json_bytes(bytes(engine.evidence['binary_manifest']))
    if (checked_receipt['toolchain']['target'] != binary['target'] or
            checked_receipt['toolchain']['sdk_sha256'] != binary['toolchain']['paired_sdk_sha256']):
        raise ValueError('Foundation and engine target/paired SDK observations differ')
    if metadata['factory_policy']['data_loading'] != 'embedded' or any(item['role'] == 'data' for item in metadata['assets'].values()):
        raise ValueError('external engine data requires a reviewed CSP-compatible retained-byte preloader; no fallback is attempted')
    for value in (source_sha256, kernel_inputs_sha256):
        _sha(value, 'observed source')
    if type(notices) is not dict or not notices or len(notices) > 128:
        raise ValueError('explicit bounded Foundation notices are required')
    all_notices = {}
    for label, data in notices.items():
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}', label) or type(data) is not bytes:
            raise ValueError('invalid Foundation notice')
        all_notices[label] = data
    for name, data in engine.notices.items():
        label = 'engine/' + name
        if len(label) > 256 or label in all_notices:
            raise ValueError('engine notice label exceeds browser closure')
        all_notices[label] = bytes(data)
    if (len(all_notices) > 128 or any(len(data) > MAX_NOTICE for data in all_notices.values()) or
            sum(map(len, all_notices.values())) > MAX_NOTICES):
        raise ValueError('retained browser notices exceed limits')
    for data in all_notices.values():
        data.decode('utf-8')
    roles = {item['role']: name for name, item in metadata['assets'].items() if item['role'] in ('factory', 'wasm')}
    pins = {name: metadata[key] for name, key in (('recipe', 'recipe_id'), ('manifest', 'binary_manifest_sha256'),
             ('proof', 'proof_sha256'), ('runtime', 'runtime_sha256'))}
    groups = _plain(group_files if group_files is not None else metadata['group_files'])
    if type(groups) is not dict or set(groups) != set(__import__('appended_engine_sdk').group_names(pins['recipe'])):
        raise ValueError('complete original engine group identities are required')
    for name, value in groups.items():
        _sha(value, 'original engine group ' + name)
    kernel = {'schema_version': 1, 'kind': PHYSICAL_KERNEL_KIND if physical_input else 'foundation-copied-engine-browser', 'kernel_profile': profile,
              'kernel_wasm_lookup': WASM_NAME, 'engine_wasm_lookup': metadata['assets'][roles['wasm']]['lookup_name'],
              'kernel_factory': _asset(factory), 'kernel_wasm': _asset(wasm),
              'engine_factory': _asset(bytes(engine.assets[roles['factory']])),
              'engine_wasm': _asset(bytes(engine.assets[roles['wasm']])),
              'engine_profile': engine_profile, 'engine_assets': {},
              'notices': {name: _asset(data) for name, data in sorted(all_notices.items())}}
    envelope = {'schema_version': 1, 'kind': PHYSICAL_KIND if physical_input else KIND, 'kernel': kernel,
                'modules': {name: _encoded(data) for name, data in sorted(blobs.items())},
                'evidence': {'engine': _encode_evidence(_plain(engine.evidence), physical_input), 'kernel_receipt': _encoded(kernel_receipt)},
                'identities': {'source_observed_at_package_sha256': source_sha256,
                    'kernel_inputs_sha256': kernel_inputs_sha256, 'kernel_receipt_sha256': kernel_receipt_pin,
                    'engine_recipe_sha256': pins['recipe'], 'engine_manifest_sha256': pins['manifest'],
                    'engine_proof_sha256': pins['proof'], 'engine_runtime_sha256': pins['runtime']},
                'group_files': groups}
    encoded = _encoded(container.canonical_json(envelope))
    prefix = (OPEN + OUTER_STYLE + MIDDLE + encoded + BOOT_OPEN + bootstrap_source(physical_input) + BOOT_CLOSE).encode('utf-8')
    if len(prefix) > container.MAX_KERNEL:
        raise ValueError('measured encoded rich prefix exceeds carrier limit; reviewed kernel profile/container maintenance is required')
    container._html_shell(prefix)
    facts = {'production_eligible': bool(metadata['production_eligible'] and kernel_eligible),
             'engine': metadata, 'kernel_receipt': checked_receipt, 'child': child}
    return prefix, envelope, facts


def inspect_prefix(prefix):
    """Check retained runtime closure without claiming original archive verification."""
    if type(prefix) is not bytes or not 1 <= len(prefix) <= container.MAX_KERNEL:
        raise ValueError('invalid rich browser prefix length')
    container._html_shell(prefix)
    blocks = re.findall(rb'<script type="application/octet-stream" id="foundation-rich-kernel">([A-Za-z0-9+/=]+)</script>', prefix)
    if len(blocks) != 1:
        raise ValueError('missing canonical rich browser asset block')
    envelope = container.parse_json(_decoded(blocks[0].decode('ascii'), container.MAX_KERNEL, 'rich envelope'), 'rich browser envelope')
    _keys(envelope, ('schema_version', 'kind', 'kernel', 'modules', 'evidence', 'identities', 'group_files'), 'rich envelope')
    if type(envelope['schema_version']) is not int or envelope['schema_version'] != 1 or envelope['kind'] not in (KIND, PHYSICAL_KIND):
        raise ValueError('unsupported rich browser envelope')
    physical_input = envelope['kind'] == PHYSICAL_KIND
    kernel = envelope['kernel']
    _keys(kernel, ('schema_version', 'kind', 'kernel_profile', 'kernel_wasm_lookup', 'engine_wasm_lookup', 'kernel_factory', 'kernel_wasm', 'engine_factory',
                   'engine_wasm', 'engine_profile', 'engine_assets', 'notices'), 'rich browser kernel')
    if type(kernel['schema_version']) is not int or kernel['schema_version'] != 1 or kernel['kind'] != (PHYSICAL_KERNEL_KIND if physical_input else 'foundation-copied-engine-browser'):
        raise ValueError('unsupported retained rich kernel')
    profile = _profile(kernel['kernel_profile'])
    if type(envelope['modules']) is not dict:
        raise ValueError('invalid retained host modules')
    if (set(envelope['modules']) != set(asset_names()) or
            any(type(value) is not str for value in envelope['modules'].values()) or
            sum(map(len, envelope['modules'].values())) > ((MAX_MODULES + 2) // 3) * 4 + 4 * len(envelope['modules'])):
        raise ValueError('retained host module inventory or aggregate size differs')
    blobs = {name: _decoded(value, MAX_MODULE, 'host module') for name, value in envelope['modules'].items()}
    factory = _read_asset(kernel['kernel_factory'], MAX_FACTORY, 'Foundation factory')
    wasm = _read_asset(kernel['kernel_wasm'], MAX_KERNEL_WASM, 'Foundation Wasm')
    _keys(envelope['identities'], ('source_observed_at_package_sha256', 'kernel_inputs_sha256', 'kernel_receipt_sha256',
        'engine_recipe_sha256', 'engine_manifest_sha256', 'engine_proof_sha256', 'engine_runtime_sha256'), 'retained identities')
    ids = envelope['identities']
    for name, value in ids.items():
        _sha(value, name)
    _keys(envelope['evidence'], ('engine', 'kernel_receipt'), 'retained evidence')
    evidence = _decode_evidence(envelope['evidence']['engine'], physical_input)
    receipt = _decoded(envelope['evidence']['kernel_receipt'], manifest.MAX_MANIFEST, 'Foundation receipt')
    proof = manifest.json_bytes(evidence['proof'])
    if type(proof) is not dict or type(proof.get('assets')) is not dict:
        raise ValueError('missing engine runtime asset declarations')
    roles = {item.get('role'): name for name, item in proof['assets'].items() if type(item) is dict and item.get('role') in ('factory', 'wasm')}
    if set(roles) != {'factory', 'wasm'} or kernel['engine_assets'] != {}:
        raise ValueError('unsupported engine data closure; embedded data is required')
    if (kernel['kernel_wasm_lookup'] != WASM_NAME or
            kernel['engine_wasm_lookup'] != proof['assets'][roles['wasm']].get('lookup_name')):
        raise ValueError('retained Wasm lookup names differ from compiled and provider-proof declarations')
    assets = {roles['factory']: _read_asset(kernel['engine_factory'], MAX_FACTORY, 'engine factory'),
              roles['wasm']: _read_asset(kernel['engine_wasm'], 256 * 1024 * 1024, 'engine Wasm')}
    if type(kernel['notices']) is not dict or len(kernel['notices']) > 128:
        raise ValueError('invalid retained notices')
    all_notices = {name: _read_asset(value, MAX_NOTICE, 'notice') for name, value in kernel['notices'].items()}
    own_notices = {name: data for name, data in all_notices.items() if not name.startswith('engine/')}
    engine_notices = {name[len('engine/'):]: data for name, data in all_notices.items() if name.startswith('engine/')}
    parsed_receipt = manifest.json_bytes(receipt)
    if type(parsed_receipt) is not dict or type(parsed_receipt.get('toolchain')) is not dict:
        raise ValueError('missing Foundation toolchain observation')
    pins = {name: ids['engine_' + key + '_sha256'] for name, key in
            (('recipe', 'recipe'), ('manifest', 'manifest'), ('proof', 'proof'), ('runtime', 'runtime'))}
    engine = _consumer().inspect_embedded_consumer(evidence=evidence, assets=assets, notices=engine_notices,
        pins=pins, kernel_target=parsed_receipt['toolchain'].get('target'), paired_sdk=parsed_receipt['toolchain'].get('sdk_sha256'),
        required_binding=_binding(physical_input))
    rebuilt, metadata, facts = make_prefix(blobs, factory, wasm, engine, receipt, ids['kernel_receipt_sha256'], own_notices,
        ids['source_observed_at_package_sha256'], ids['kernel_inputs_sha256'], profile, group_files=envelope['group_files'],
        physical_input=physical_input)
    if metadata != envelope or rebuilt != prefix:
        raise ValueError('rich browser prefix differs from canonical retained inputs')
    return envelope, facts


def _descriptor(prefix, envelope, facts, kernel_inputs):
    profile = envelope['kernel']['kernel_profile']
    return {'schema_version': 1, 'kind': 'foundation-kernel', 'carrier': 'html', 'profile': profile,
            'append_format': 1, **composition_descriptor_policy(profile, facts['kernel_receipt'],
                eligible=facts['production_eligible']), 'boundary_offset': None,
            'executable': {'length': len(prefix), 'sha256': container.digest(prefix)}, 'kernel_inputs': kernel_inputs,
            'provenance': {'kind': envelope['kind'], 'qualification': QUALIFICATION,
                'runtime': 'one-direct-worker/two-private-wasm-instances', 'renderer_modes': ['isolated-surface'],
                'csp': CSP, 'identities': envelope['identities'], 'group_files': envelope['group_files'],
                'inputs': {name: container.digest(_decoded(value, MAX_MODULE, name)) for name, value in envelope['modules'].items()},
                'child': facts['child'], 'build_origin': facts['kernel_receipt']['build_origin'],
                'source_binding': 'observed packaging inputs and pinned original runtime observations; not release certification'}}


def package(assets, output, notice_paths, *, profile, source_root, engine_group,
            engine_recipe_sha256, engine_manifest_sha256, engine_proof_sha256, engine_runtime_sha256,
            kernel_receipt, kernel_receipt_sha256, developer_unqualified=False, kernel_module_dir=None,
            physical_input=False):
    if developer_unqualified is not True:
        raise ValueError('initial rich production requires explicit --developer-unqualified; it cannot skip runtime facts')
    _profile(profile)
    physical_input = _physical(physical_input)
    from appended_policy import kernel_source_tree
    from source_identity import ignored_source_path, source_tree
    source_root = Path(source_root).resolve(strict=True)
    output = Path(output).absolute()
    destination = output.resolve(strict=False)
    if source_root in destination.parents and not ignored_source_path(destination.relative_to(source_root).as_posix() + '/'):
        raise ValueError('rich carrier output must be outside source inputs or in ignored build/.agent-work')
    # Output admission precedes any expensive read, and every publication is new.
    if output.exists() or output.is_symlink():
        raise ValueError('rich carrier output destination must be new')
    container._ordinary_path(output.parent, directory=True)
    source_before, inputs_before = source_tree(source_root), kernel_source_tree(source_root)
    snapshots = []
    receipt = container._snapshot(kernel_receipt, manifest.MAX_MANIFEST)
    snapshots.append(receipt)
    if container.digest(receipt.content) != _sha(kernel_receipt_sha256, 'kernel receipt'):
        raise ValueError('kernel receipt differs from independent pin')
    preliminary = manifest.json_bytes(receipt.content)
    if type(preliminary) is not dict or type(preliminary.get('toolchain')) is not dict:
        raise ValueError('missing pinned Foundation toolchain receipt')
    engine = _consumer().verify_kernel_consumer(engine_group, expected_recipe=engine_recipe_sha256,
        expected_manifest=engine_manifest_sha256, expected_proof=engine_proof_sha256,
        expected_runtime=engine_runtime_sha256, kernel_target=preliminary['toolchain'].get('target'),
        paired_sdk=preliminary['toolchain'].get('sdk_sha256'), required_binding=_binding(physical_input))
    blobs = {}
    for name in asset_names():
        saved = container._snapshot(Path(assets) / name, MAX_MODULE)
        snapshots.append(saved); blobs[name] = saved.content
    selected = Path(kernel_module_dir) if kernel_module_dir is not None else Path(assets)
    factory = container._snapshot(selected / FACTORY_NAME, MAX_FACTORY)
    wasm = container._snapshot(selected / WASM_NAME, MAX_KERNEL_WASM)
    snapshots.extend((factory, wasm))
    notices = {}
    for item in notice_paths:
        label, raw = str(item).split('=', 1) if '=' in str(item) else (Path(item).name, str(item))
        if label in notices:
            raise ValueError('duplicate Foundation notice label')
        saved = container._snapshot(raw, MAX_NOTICE)
        snapshots.append(saved); notices[label] = saved.content
    prefix, envelope, facts = make_prefix(blobs, factory.content, wasm.content, engine, receipt.content,
        kernel_receipt_sha256, notices, source_before['tree_sha256'], inputs_before['tree_sha256'], profile,
        physical_input=physical_input)
    if not facts['production_eligible']:
        raise ValueError('real complete engine and compiled Foundation runtime observations are required; fixtures cannot publish a rich kernel')
    checked_envelope, checked_facts = inspect_prefix(prefix)
    if checked_envelope != envelope or not checked_facts['production_eligible']:
        raise ValueError('rich prefix failed complete prepublication runtime-closure verification')
    descriptor = _descriptor(prefix, envelope, facts, inputs_before)
    container.validate_descriptor(descriptor)
    container.parse_artifact(prefix, descriptor, expected_mode='neither')
    if source_tree(source_root) != source_before or kernel_source_tree(source_root) != inputs_before:
        raise ValueError('source inputs changed during rich kernel packaging')
    for saved in snapshots:
        container._recheck(saved)
    # Recheck the external complete retained group before reserving publication.
    checked = _consumer().verify_kernel_consumer(engine_group, expected_recipe=engine_recipe_sha256,
        expected_manifest=engine_manifest_sha256, expected_proof=engine_proof_sha256,
        expected_runtime=engine_runtime_sha256, kernel_target=preliminary['toolchain'].get('target'),
        paired_sdk=preliminary['toolchain'].get('sdk_sha256'), required_binding=_binding(physical_input))
    if checked.as_dict() != engine.as_dict():
        raise ValueError('retained engine changed before publication')
    output.mkdir(exist_ok=False)
    contents = {HTML_NAME: prefix, DESCRIPTOR_NAME: container.canonical_json(descriptor)}
    for name, data in contents.items():
        container._write_new(output / name, data, snapshots)
    checksums = ''.join(container.digest(contents[name]) + '  ' + name + '\n' for name in sorted(contents)).encode('ascii')
    container._write_new(output / 'manifest.sha256', checksums, snapshots)
    verify(output)
    return descriptor


def inspect_output(output, descriptor_sha256=None):
    """Inspect complete carrier integrity; fixture reports remain ineligible."""
    output = container._ordinary_path(output, directory=True)
    if {path.name for path in output.iterdir()} != {HTML_NAME, DESCRIPTOR_NAME, 'manifest.sha256'}:
        raise ValueError('incomplete or unexpected rich browser inventory')
    descriptor_raw = container._snapshot(output / DESCRIPTOR_NAME, container.MAX_INDEX).content
    if descriptor_sha256 is not None and container.digest(descriptor_raw) != _sha(descriptor_sha256, 'retained descriptor'):
        raise ValueError('rich browser descriptor differs from independent pin')
    descriptor = container.validate_descriptor(container.parse_json(descriptor_raw, 'rich browser descriptor'))
    from appended_policy import validate_kernel_inputs
    validate_kernel_inputs(descriptor.get('kernel_inputs'))
    prefix = container._snapshot(output / HTML_NAME, container.MAX_KERNEL).content
    container.parse_artifact(prefix, descriptor, expected_mode='neither')
    envelope, facts = inspect_prefix(prefix)
    rebuilt = _descriptor(prefix, envelope, facts, descriptor['kernel_inputs'])
    if descriptor != rebuilt or descriptor['kernel_inputs']['tree_sha256'] != envelope['identities']['kernel_inputs_sha256']:
        raise ValueError('rich browser descriptor differs from canonical policy/inputs')
    expected = ''.join(container.digest(data) + '  ' + name + '\n' for name, data in sorted(
        ((HTML_NAME, prefix), (DESCRIPTOR_NAME, descriptor_raw)))).encode('ascii')
    if container._snapshot(output / 'manifest.sha256', 1024).content != expected:
        raise ValueError('rich browser checksum inventory differs')
    facts['independently_pinned_descriptor'] = descriptor_sha256 is not None
    return descriptor, facts


def verify(output, descriptor_sha256=None):
    descriptor, facts = inspect_output(output, descriptor_sha256)
    if not facts['production_eligible']:
        raise ValueError('retained rich carrier has no complete real runtime observations')
    return descriptor


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify', action='store_true')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--descriptor-sha256')
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
    parser.add_argument('--physical-input', action='store_true')
    args = parser.parse_args(argv)
    try:
        if args.verify:
            production = (args.assets, args.kernel_module_dir, args.source_root, args.profile, args.notice,
                args.engine_group, args.engine_recipe_sha256, args.engine_manifest_sha256,
                args.engine_proof_sha256, args.engine_runtime_sha256, args.kernel_receipt,
                args.kernel_receipt_sha256, args.developer_unqualified, args.physical_input)
            if any(production):
                raise ValueError('verification reads retained policy; production flags cannot upgrade a carrier')
            result = verify(args.output, args.descriptor_sha256)
        else:
            if args.descriptor_sha256:
                raise ValueError('--descriptor-sha256 applies only to verification')
            required = ('assets', 'source_root', 'profile', 'engine_group', 'engine_recipe_sha256',
                        'engine_manifest_sha256', 'engine_proof_sha256', 'engine_runtime_sha256',
                        'kernel_receipt', 'kernel_receipt_sha256')
            if any(getattr(args, name) is None for name in required):
                raise ValueError('rich production requires explicit assets, profile, source, group and every independent input pin')
            result = package(args.assets, args.output, args.notice, profile=args.profile, source_root=args.source_root,
                engine_group=args.engine_group, engine_recipe_sha256=args.engine_recipe_sha256,
                engine_manifest_sha256=args.engine_manifest_sha256, engine_proof_sha256=args.engine_proof_sha256,
                engine_runtime_sha256=args.engine_runtime_sha256, kernel_receipt=args.kernel_receipt,
                kernel_receipt_sha256=args.kernel_receipt_sha256, developer_unqualified=args.developer_unqualified,
                kernel_module_dir=args.kernel_module_dir, physical_input=args.physical_input)
        print(container.canonical_json({'kind': result['provenance']['kind'], 'profile': result['profile'],
              'qualification': result['provenance']['qualification'],
              'independently_pinned_descriptor': args.descriptor_sha256 is not None}).decode())
        return 0
    except (ValueError, OSError, UnicodeError, KeyError, TypeError) as error:
        print('rich browser kernel: ' + str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
