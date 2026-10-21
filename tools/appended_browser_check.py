#!/usr/bin/env python3
"""Actual direct-file checks of frozen binary and rich BOTH browser carriers.

The composition dispatcher supplies verified byte helpers and complete execution
bindings. The outer qualifier validates the frozen policy/plan; this adapter
checks its selected subject again and never builds, rewrites or serves the app.
Linux Firefox and Chromium have explicit physical adapters. Other hosts fail
closed. ChromeDriver is qualification instrumentation, never an app dependency.
"""
import base64
import http.client
import http.server
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import sys
import secrets
import threading
import time
import urllib.request
import urllib.error

import appended_container as container
import appended_release as release
from process_tree import ProcessTreeError

ROOT = Path(__file__).resolve().parents[1]
CHECKER_SOURCES = ('tools/appended_browser_check.py', 'gui/tests/browser_test.py', 'tools/process_tree.py')
# Additional interpreting code for schema-2 rich scenarios. The immutable
# qualification schema-v1 source catalogue remains unchanged. These fixed paths
# have a separate exact pin map inside the independently frozen scenario.
RICH_INSPECTION_SOURCES = (
    'tools/appended_container.py',
    'tools/appended_engine_consumer.py',
    'tools/appended_engine_document_consumer.py',
    'tools/appended_engine_document_contract.py',
    'tools/appended_engine_editor_consumer.py',
    'tools/appended_engine_editor_contract.py',
    'tools/appended_engine_manifest.py',
    'tools/appended_engine_sdk.py',
    'tools/appended_policy.py',
    'tools/appended_project.py',
    'tools/appended_wasm.py',
    'tools/browser_bundle.py',
    'tools/browser_editor_bundle.py',
    'tools/browser_surface_bundle.py',
    'tools/dependency_archive.py',
    'tools/package_appended_engine_document_wasm.py',
    'tools/package_appended_engine_wasm.py',
    'tools/package_notices.py',
    'tools/package_wasm.py',
    'tools/sdk_manifest.py',
    'tools/source_identity.py',
)
RICH_PENDING = {
    'cold_app_startup': 'requires a correlated presented frame, ready frontend and accepted real input',
    'warm_app_startup': 'ordinary reloads with the same visible/interactive witness have not been measured',
    'input_feedback': 'requires input-correlated native publication ACK applied to a presented frame',
    'provider_computation': 'requires the native reply/ACK plus the corresponding presented result',
}
SURFACE_PROTOCOL = 'foundation-rich-surface-observer-v1'
SURFACE_SOURCES = ('tools/appended_rich_surface_actions.py',)
MAX_SCENARIO = 512 * 1024
MAX_VALUE = 64 * 1024
NAME = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z')
DECIMAL = re.compile(r'[1-9][0-9]{0,19}\Z')
ASSERTIONS = ('actual-browser', 'application-scenario', 'retained-runtime')
MAX_CHROMIUM_IMAGE = 512 * 1024 * 1024
CHROMIUM_ONLINE = {'offline': False, 'latency': 0, 'download_throughput': 1048576, 'upload_throughput': 1048576}
CHROMIUM_OFFLINE = {'offline': True, 'latency': 0, 'download_throughput': 0, 'upload_throughput': 0}
CANARY_ROLES = ('root', 'frame', 'worker')


def _validate_offline(engine, value):
    """Validate native offline selection plus an independently witnessed control."""
    if engine == 'firefox':
        expected = {'enabled': True, 'positive_control': 'NS_ERROR_OFFLINE'}
    elif engine == 'chromium':
        online = {role: {'response': True, 'requests': 1} for role in CANARY_ROLES}
        offline = {role: {'response': False, 'requests': 0} for role in CANARY_ROLES}
        expected = {'enabled': True, 'positive_control': 'owned-loopback-root-frame-worker',
            'before': {'online': online, 'offline': offline, 'online_conditions': CHROMIUM_ONLINE,
                       'conditions': CHROMIUM_OFFLINE, 'listener_control': True},
            'after': {'offline': offline, 'conditions': CHROMIUM_OFFLINE, 'listener_control': True},
            'listener_joined': True}
    else:
        return False
    try:
        return container.canonical_json(value) == container.canonical_json(expected)
    except (TypeError, ValueError):
        return False


def _text(value, limit=MAX_VALUE):
    return type(value) is str and '\0' not in value and len(value.encode('utf-8')) <= limit


def _execution(value):
    keys = ('plan', 'check', 'composition_check_id', 'run_id', 'attempt', 'qualification_policy_sha256', 'profile')
    release._keys(value, keys, label='browser execution context')
    for key in ('plan', 'qualification_policy_sha256'):
        release._sha(value[key])
    if (any(type(value[key]) is not str or not NAME.fullmatch(value[key]) for key in ('check', 'composition_check_id', 'run_id', 'profile'))
            or value['check'] != value['composition_check_id'] or type(value['attempt']) is not int or value['attempt'] < 1):
        raise ValueError('complete frozen browser execution context is required')


def _scenario(path, pin, subject, artifact, target, backend):
    saved = container._snapshot(path, MAX_SCENARIO)
    if container.digest(saved.content) != release._sha(pin):
        raise ValueError('browser scenario differs from its independent SHA-256 pin')
    value = release._json(saved.content)
    rich = artifact.get('profile') == 'both'
    surface = rich and value.get('schema_version') == 3
    keys = ('schema_version', 'kind', 'candidate_sha256', 'artifact_id', 'target', 'backend',
            'browser', 'viewport', 'title', 'steps') + (('rich_identities', 'rich_inspection_sources') if rich else ()) + (('observer_protocol', 'rich_surface_sources') if surface else ())
    release._keys(value, keys, ('inputs',), label='browser scenario')
    expected_kind = 'foundation-rich-surface-browser-scenario' if surface else 'foundation-rich-both-browser-scenario' if rich else 'foundation-appended-browser-scenario'
    expected_schema = 3 if surface else 2 if rich else 1
    if (type(value['schema_version']) is not int or value['schema_version'] != expected_schema or value['kind'] != expected_kind
            or value['candidate_sha256'] != subject['candidate_sha256']
            or (value['artifact_id'], value['target'], value['backend']) != (artifact['id'], target, backend)):
        raise ValueError('browser scenario names another frozen artifact or target')
    if rich:
        pins = value['rich_inspection_sources']
        release._keys(pins, RICH_INSPECTION_SOURCES, label='rich inspection source cohort')
        for pin in pins.values():
            release._sha(pin)
        # Scenario pins are checked against identities extracted from the public
        # descriptor, payload and rich-prefix contracts in _rich_both_identity.
        identity = value['rich_identities']
        release._keys(identity, ('profile', 'source_tree_sha256', 'source_observed_at_package_sha256',
            'kernel_inputs_sha256', 'kernel_descriptor_sha256', 'kernel_prefix_sha256', 'kernel_prefix_length',
            'kernel_receipt_sha256', 'engine_recipe_sha256', 'engine_manifest_sha256', 'engine_proof_sha256',
            'engine_runtime_sha256', 'payload_transport_sha256', 'payload_package_sha256', 'payload_id'),
            label='rich BOTH scenario identities')
        hashes = tuple(key for key in identity if key not in ('profile', 'kernel_prefix_length', 'payload_id'))
        if (identity['profile'] != 'both' or type(identity['kernel_prefix_length']) is not int
                or identity['kernel_prefix_length'] <= 0):
            raise ValueError('rich BOTH scenario requires a positive exact base prefix identity')
        for key in hashes:
            release._sha(identity[key])
        if not _text(identity['payload_id'], 256) or not identity['payload_id']:
            raise ValueError('rich BOTH scenario requires the exact public payload identifier')
    browser = value['browser']
    release._keys(browser, ('engine', 'executable', 'sha256'), ('driver',), label='selected browser')
    if browser['engine'] not in ('firefox', 'chromium') or not _text(browser['executable'], 4096) or not Path(browser['executable']).is_absolute():
        raise ValueError('an explicit absolute browser executable is required')
    release._sha(browser['sha256'])
    if browser['engine'] == 'chromium':
        driver = browser.get('driver')
        release._keys(driver, ('executable', 'sha256'), label='selected Chromium driver')
        if not _text(driver['executable'], 4096) or not Path(driver['executable']).is_absolute():
            raise ValueError('Chromium requires an independently pinned absolute native driver')
        release._sha(driver['sha256'])
        if driver['executable'] == browser['executable']:
            raise ValueError('browser and driver must be distinct native images')
    elif 'driver' in browser:
        raise ValueError('Firefox does not consume a Chromium driver')
    viewport = value['viewport']
    release._keys(viewport, ('width', 'height'), label='browser viewport')
    if any(type(viewport[key]) is not int or not 320 <= viewport[key] <= 4096 for key in viewport) or not _text(value['title'], 4096):
        raise ValueError('invalid browser viewport or title')
    if type(value['steps']) is not list or not 2 <= len(value['steps']) <= 64:
        raise ValueError('browser scenario requires bounded nonempty interactions and results')
    surface_sources = []
    if surface:
        if value['observer_protocol'] != SURFACE_PROTOCOL:
            raise ValueError('unsupported rich surface observer protocol')
        actions, source = _surface_actions(value['rich_surface_sources'])
        surface_sources.append(source)
        _validate_surface_steps(value['steps'], actions)
    seen, edited, interacted, later_assertion = set(), set(), False, False
    for step in (() if surface else value['steps']):
        if type(step) is not dict or step.get('action') not in ('edit', 'activate', 'assert-text', 'assert-value'):
            raise ValueError('unsupported data-only browser action')
        fields = ('id', 'action', 'widget') + (() if step['action'] == 'activate' else ('value',))
        release._keys(step, fields, label='browser step')
        widget = step['widget']
        release._keys(widget, ('id', 'generation'), label='browser widget identity')
        if (type(step['id']) is not str or not NAME.fullmatch(step['id']) or step['id'] in seen
                or not _text(widget['id'], 256) or not widget['id']
                or type(widget['generation']) is not str or not DECIMAL.fullmatch(widget['generation'])
                or int(widget['generation']) > (1 << 64) - 1
                or 'value' in step and not _text(step['value'])):
            raise ValueError('invalid, duplicate or excessive browser step')
        seen.add(step['id'])
        if step['action'] == 'edit':
            key = (widget['id'], widget['generation'])
            if key in edited:
                raise ValueError('scenario v1 cannot repeat an unacknowledged edit')
            edited.add(key)
        if step['action'] in ('edit', 'activate'):
            interacted = True
        elif interacted:
            later_assertion = True
    if not surface and not later_assertion:
        raise ValueError('browser scenario needs an application assertion after interaction')
    inputs = value.get('inputs', {})
    if type(inputs) is not dict or len(inputs) > 64:
        raise ValueError('invalid browser scenario input inventory')
    snapshots, total, input_names = list(surface_sources), 0, set()
    for name, expected in inputs.items():
        container.resource_path(name);release._sha(expected)
        if name.casefold() in input_names:
            raise ValueError('browser scenario input paths alias')
        input_names.add(name.casefold())
        item = container._snapshot(Path(path).parent / name, 64 * 1024 * 1024)
        total += len(item.content)
        if total > 256 * 1024 * 1024 or container.digest(item.content) != expected:
            raise ValueError('browser scenario input differs or exceeds bounds')
        snapshots.append(item)
    return saved, value, snapshots


def _rich_sources(pins):
    """Bind every additional public-prefix interpreter before importing it."""
    release._keys(pins, RICH_INSPECTION_SOURCES, label='rich inspection source cohort')
    snapshots = []
    for name in RICH_INSPECTION_SOURCES:
        saved = container._snapshot(ROOT / name, 2 * 1024 * 1024)
        if container.digest(saved.content) != release._sha(pins[name]):
            raise ValueError('rich inspection source differs from frozen scenario: ' + name)
        snapshots.append(saved)
    return snapshots


def _surface_actions(pins):
    """Interpret only the independently pinned new action helper bytes."""
    release._keys(pins, SURFACE_SOURCES, label='rich surface source cohort')
    name = SURFACE_SOURCES[0]
    saved = container._snapshot(ROOT / name, 2 * 1024 * 1024)
    if container.digest(saved.content) != release._sha(pins[name]):
        raise ValueError('rich surface action source differs from frozen scenario')
    spec = importlib.util.spec_from_file_location('foundation_pinned_surface_actions', saved.path)
    module = importlib.util.module_from_spec(spec)
    exec(compile(saved.content, str(saved.path), 'exec'), module.__dict__)
    return module, saved


def _validate_surface_steps(steps, actions):
    seen, physical, asserted = set(), set(), False
    for step in steps:
        if type(step) is not dict or not isinstance(step.get('id'), str) or not NAME.fullmatch(step['id']) or step['id'] in seen:
            raise ValueError('invalid or duplicate rich surface step identity')
        kind = step.get('action')
        if isinstance(kind, str) and kind.startswith('surface-'):
            actions.validate_surface_action(step)
            physical.add(step['id'])
        elif kind in ('assert-document', 'capture'):
            release._keys(step, ('id', 'action', 'after') + (('predicate', 'expected') if kind == 'assert-document' else ()), label='rich observation step')
            if type(step['after']) is not str or step['after'] not in physical:
                raise ValueError('rich observation must follow a prior physical action')
            if kind == 'assert-document':
                predicate = step['predicate']
                if type(predicate) is not dict:
                    raise ValueError('rich document predicate must be typed data')
                predicate_kind = predicate.get('kind')
                if type(predicate_kind) is not str:
                    raise ValueError('rich document predicate kind must be text')
                fields = {'text-present': (), 'text-absent': (), 'form-value': ('label',),
                    'descendant-text': ('name',), 'selection-text': (), 'tagged-text': ('tag',)}.get(predicate_kind)
                if fields is None:
                    raise ValueError('unsupported rich document predicate')
                release._keys(predicate, ('kind', *fields), label='rich document predicate')
                if not _text(step['expected'], 4096) or not step['expected']:
                    raise ValueError('rich document expectation must be bounded nonempty text')
                if any(not _text(predicate[key], 256) or not predicate[key] for key in fields):
                    raise ValueError('rich document target must be bounded nonempty text')
                if predicate_kind == 'tagged-text' and predicate['tag'] not in ('b', 'strong', 'em', 'i'):
                    raise ValueError('rich tagged-text predicate requires a known semantic tag')
                asserted = True
        else:
            raise ValueError('unsupported rich surface step')
        seen.add(step['id'])
    if not physical or not asserted:
        raise ValueError('rich surface scenario needs physical input and a native document assertion')


SURFACE_READ = "return globalThis.foundationRichSurfaceObserver?.read() ?? null;"
SURFACE_OBSERVE = '''const done=arguments[arguments.length-1];
const observer=globalThis.foundationRichSurfaceObserver;
if(!observer){done({ok:false,error:'Rich surface observer unavailable',admission:null});}
else observer.observeDocument().then(value=>done({ok:true,value}),
 error=>done({ok:false,error:String(error.message||error),admission:error.admission??null}));'''


def _native_surface_document(observed):
    if (type(observed) is not dict or observed.get('protocol') != SURFACE_PROTOCOL or observed.get('closed') is not False
            or not re.fullmatch(r'[0-9a-f]{64}', str(observed.get('frontendGeneration', '')))):
        raise ValueError('native observation has no live public frontend identity')
    presentation, state = observed.get('presentation'), observed.get('document')
    if (type(presentation) is not dict or presentation.get('available') is not True or type(state) is not dict
            or state.get('available') is not True or not DECIMAL.fullmatch(str(state.get('observation', '')))):
        raise ValueError('native observation or actual rendered surface is unavailable')
    revision = state.get('publicationRevision')
    if not DECIMAL.fullmatch(str(revision)) or int(revision) > int(presentation['snapshotRevision']):
        raise ValueError('native document has no accepted GUI publication')
    document = state.get('document')
    if type(document) is not dict or document.get('protocol') != 2:
        raise ValueError('native observation has no paired document-v2 values')
    body, forms = document.get('body'), document.get('forms')
    if type(body) is not dict or type(forms) is not dict or forms.get('protocol') != 2:
        raise ValueError('native document/form pair is incomplete')
    snapshot = body.get('snapshot')
    if (body.get('errorCode') != '' or type(snapshot) is not dict or snapshot.get('truncated') is not False
            or snapshot.get('version') != forms.get('version') or forms.get('version') != document.get('publication')
            or type(snapshot.get('nodes')) is not list or len(snapshot['nodes']) > 2048):
        raise ValueError('native body is erroneous, truncated or not paired with forms')
    return body, forms


def _document_predicate(observed, predicate, expected):
    body, forms = _native_surface_document(observed)
    nodes = body['snapshot']['nodes']
    visible = [node for node in nodes if not node.get('masked') and not node.get('omitted')]
    text = ''.join(node.get('text', '') for node in visible if node.get('kind') == 'text')
    kind = predicate['kind']
    if kind == 'text-present':
        return expected in text
    if kind == 'text-absent':
        return expected not in text
    if kind == 'form-value':
        controls = [control for control in forms['controls'] if control.get('label') == predicate['label'] and not control.get('omitted')]
        if len(controls) != 1 or not controls[0].get('complete') or controls[0].get('kind') == 'secure_readonly':
            return False
        state = controls[0].get('state')
        return bool(state and state.get('kind') == 'text' and state['value']['value'] == expected)
    by_id = {node['id']: node for node in visible}
    def descendant_text(parent):
        ids = {parent['id']}
        for node in visible:
            if node.get('parent') in ids:
                ids.add(node['id'])
        return ''.join(node.get('text', '') for node in visible if node['id'] in ids and node.get('kind') == 'text')
    if kind in ('descendant-text', 'tagged-text'):
        matches = [node for node in visible if node.get('kind') == 'element' and
            (node.get('name') == predicate['name'] if kind == 'descendant-text' else node.get('tag') == predicate['tag'])]
        if kind == 'descendant-text':
            return len(matches) == 1 and descendant_text(matches[0]) == expected
        return sum(descendant_text(node) == expected for node in matches) == 1
    selection = body.get('originalSelection')
    if not selection or any(body['degraded'].values()):
        return False
    anchor, focus = (selection['endpoints'][key] for key in ('anchor', 'focus'))
    if anchor['kind'] != 'text_utf16' or focus['kind'] != 'text_utf16' or anchor['node'] != focus['node']:
        return False
    node = by_id.get(anchor['node'])
    if not node or node.get('kind') != 'text':
        return False
    low, high = sorted((anchor['offset'], focus['offset']))
    encoded = node['text'].encode('utf-16-le')
    if high * 2 > len(encoded):
        return False
    try:
        return encoded[low * 2:high * 2].decode('utf-16-le') == expected
    except UnicodeDecodeError:
        return False


def _surface_capture(browser, evidence, name):
    raw = base64.b64decode(browser.command('WebDriver:TakeScreenshot', {})['value'], validate=True)
    if not raw.startswith(b'\x89PNG\r\n\x1a\n') or len(raw) > 16 * 1024 * 1024:
        raise ValueError('rich surface screenshot is invalid or oversized')
    with (evidence / name).open('xb') as stream:
        stream.write(raw)
    return {'path': name, 'sha256': container.digest(raw)}


def _exercise_surface(browser, engine, scenario, evidence, deadline):
    actions, _ = _surface_actions(scenario['rich_surface_sources'])
    browser.until("return globalThis.foundationRichSurfaceObserver?.read().presentation?.available === true;")
    frontend_generation, last_observation = None, 0
    def observe():
        nonlocal frontend_generation, last_observation
        result = browser.evaluate(SURFACE_OBSERVE, asynchronous=True)
        if type(result) is not dict or result.get('ok') is not True:
            raise ValueError('actual native document observation failed: ' + str(result))
        # Native Take can finish before the next RAF blit. Wait only for
        # presentation; never replay the preceding physical action.
        browser.until("return globalThis.foundationRichSurfaceObserver?.read().presentation?.available === true;")
        observed = browser.evaluate(SURFACE_READ)
        if observed['document']['observation'] != result['value']['document']['observation']:
            raise ValueError('native observation changed before presentation readback')
        _native_surface_document(observed)
        if frontend_generation is not None and observed['frontendGeneration'] != frontend_generation:
            raise ValueError('rich frontend was replaced during the application scenario')
        native_observation = int(observed['document']['observation'])
        if native_observation <= last_observation:
            raise ValueError('rich document observation did not refresh')
        frontend_generation, last_observation = observed['frontendGeneration'], native_observation
        return observed
    baseline = observe()
    observations, changed, first_input, last_observed = [], False, None, None
    for step in scenario['steps']:
        kind = step['action']
        record = {'id': step['id'], 'action': kind, 'passed': True}
        if kind.startswith('surface-'):
            browser.until("return globalThis.foundationRichSurfaceObserver?.read().presentation?.available === true;")
            dispatched = actions.dispatch_surface_action(browser, engine, step)
            if first_input is None:
                first_input = dispatched
            record['physical_dispatch_ns'] = dispatched
        elif kind == 'assert-document':
            observed = observe()
            while not _document_predicate(observed, step['predicate'], step['expected']):
                if time.monotonic() >= deadline:
                    raise TimeoutError('native rich document assertion failed: ' + step['id'])
                time.sleep(.02)
                observed = observe()
            if step['predicate']['kind'] not in ('form-value', 'selection-text'):
                changed |= not _document_predicate(baseline, step['predicate'], step['expected'])
            last_observed = time.monotonic_ns()
            record['native_observation'] = observed
            record['native_observed_ns'] = last_observed
            record['after'] = step['after']
            record['capture'] = _surface_capture(browser, evidence, 'step-' + step['id'] + '.png')
        else:
            record['after'] = step['after']
            record['capture'] = _surface_capture(browser, evidence, 'step-' + step['id'] + '.png')
        observations.append(record)
    if not changed or first_input is None or last_observed is None:
        raise ValueError('rich surface scenario did not prove a changed native application result')
    return observations, first_input, last_observed, baseline


def _check_surface_records(result, scenario, evidence):
    records = result.get('observations')
    if type(records) is not list or len(records) != len(scenario['steps']):
        raise ValueError('rich surface scenario observations are incomplete')
    baseline = result.get('rich_surface_baseline')
    _native_surface_document(baseline)
    changed, captures = False, []
    last_observation = int(baseline['document']['observation'])
    last_dispatch = last_event = 0
    first_dispatch = last_native_observed = None
    dispatches = {}
    for step, record in zip(scenario['steps'], records):
        if (type(record) is not dict or record.get('id') != step['id'] or record.get('action') != step['action']
                or record.get('passed') is not True):
            raise ValueError('rich surface observation identity differs')
        if step['action'].startswith('surface-'):
            release._keys(record, ('id', 'action', 'passed', 'physical_dispatch_ns'), label='physical dispatch observation')
            if type(record['physical_dispatch_ns']) is not int or record['physical_dispatch_ns'] <= 0:
                raise ValueError('rich physical dispatch clock is absent')
            dispatched = record['physical_dispatch_ns']
            if dispatched <= last_dispatch or dispatched < last_event:
                raise ValueError('rich physical dispatch order regressed')
            dispatches[step['id']] = dispatched
            if first_dispatch is None:
                first_dispatch = dispatched
            last_dispatch = last_event = dispatched
            continue
        release._keys(record, ('id', 'action', 'passed', 'after', 'capture') +
            (('native_observation', 'native_observed_ns') if step['action'] == 'assert-document' else ()), label='rich native observation')
        if record['after'] != step['after']:
            raise ValueError('rich observation names another prior action')
        if step['action'] == 'assert-document':
            if record['native_observation'].get('frontendGeneration') != baseline['frontendGeneration']:
                raise ValueError('saved native rich observation belongs to another frontend')
            if not _document_predicate(record['native_observation'], step['predicate'], step['expected']):
                raise ValueError('saved native rich assertion does not match its scenario')
            observation = int(record['native_observation']['document']['observation'])
            observed_ns = record['native_observed_ns']
            if observation <= last_observation:
                raise ValueError('saved native rich observation did not refresh')
            if (type(observed_ns) is not int or observed_ns <= 0 or observed_ns < last_event
                    or step['after'] not in dispatches or observed_ns < dispatches[step['after']]):
                raise ValueError('saved native rich observation precedes its physical input')
            last_observation, last_native_observed, last_event = observation, observed_ns, observed_ns
            if step['predicate']['kind'] not in ('form-value', 'selection-text'):
                changed |= not _document_predicate(baseline, step['predicate'], step['expected'])
        capture = record['capture']
        release._keys(capture, ('path', 'sha256'), label='rich step capture')
        if capture['path'] != 'step-' + step['id'] + '.png':
            raise ValueError('rich step capture path differs')
        saved = container._snapshot(evidence / capture['path'], 16 * 1024 * 1024)
        if not saved.content.startswith(b'\x89PNG\r\n\x1a\n') or container.digest(saved.content) != release._sha(capture['sha256']):
            raise ValueError('rich step screenshot is missing or differs')
        captures.append(saved)
    if not changed:
        raise ValueError('rich scenario lacks a changed native result beyond provisional form editing')
    clocks = result.get('clocks')
    if (not _valid_surface_clocks(clocks) or clocks['first_trusted_dispatch_ns'] != first_dispatch
            or clocks['native_result_observed_ns'] != last_native_observed):
        raise ValueError('rich surface timing envelope differs from its ordered observations')
    return captures


def _inspect_rich_prefix(prefix, kind):
    """Select the public role parser; never reinterpret editor bytes as rendering."""
    if kind in ('foundation-rich-browser-document-kernel-v1', 'foundation-rich-browser-editor-kernel-v1'):
        from package_appended_engine_document_wasm import inspect_prefix
    elif kind in ('foundation-rich-browser-kernel-v1', 'foundation-rich-browser-physical-kernel-v1'):
        from package_appended_engine_wasm import inspect_prefix
    else:
        raise ValueError('unsupported public rich retained-prefix role')
    envelope, facts = inspect_prefix(prefix)
    if envelope.get('kind') != kind:
        raise ValueError('rich descriptor and inspected prefix roles differ')
    # Imported modules must be the same fixed source-root files that the
    # scenario pins. A cached module from another checkout is not this cohort.
    for name in RICH_INSPECTION_SOURCES:
        loaded = sys.modules.get(Path(name).stem)
        if loaded is not None and Path(loaded.__file__).resolve() != (ROOT / name).resolve():
            raise ValueError('rich interpreter loaded from another source root: ' + name)
    return envelope, facts


def _rich_both_identity(directory, subject, artifact):
    """Derive rich BOTH pins from the verified public candidate metadata."""
    selection = subject['selection']
    composition = subject['composition']
    if (artifact.get('carrier') != 'html' or artifact.get('profile') != 'both'
            or composition['payload'].get('mode') != 'both'):
        raise ValueError('rich browser requires an HTML BOTH kernel and BOTH payload')
    selected = [item for item in selection['kernels'] if item['id'] == artifact['id']]
    if len(selected) != 1:
        raise ValueError('rich browser selection lacks one exact retained base')
    selected = selected[0]
    descriptor_path = directory / selected['descriptor']['path']
    descriptor_saved = container._snapshot(descriptor_path, 16 * 1024 * 1024)
    if container.digest(descriptor_saved.content) != selected['descriptor']['sha256']:
        raise ValueError('rich browser retained descriptor differs from its content address')
    descriptor = container.parse_json(descriptor_saved.content, 'retained rich kernel descriptor')
    container.validate_descriptor(descriptor)
    described, members, _ = release._members(directory / artifact['archive'])
    runtime_name = artifact['runtime_member']
    if runtime_name not in members:
        raise ValueError('rich browser runtime is absent from the selected artifact')
    runtime = members[runtime_name][0]
    parsed = container.parse_artifact(runtime, descriptor, expected_mode='both')
    if parsed.package is None or parsed.package.mode != 'both':
        raise ValueError('rich browser payload is not the selected BOTH package')
    envelope, facts = _inspect_rich_prefix(parsed.prefix, descriptor.get('provenance', {}).get('kind'))
    if facts.get('production_eligible') is not True:
        raise ValueError('rich browser engine and Foundation receipt are not production eligible')
    provenance = descriptor.get('provenance', {})
    identities = envelope.get('identities', {})
    if provenance.get('identities') != identities:
        raise ValueError('rich base descriptor and embedded public identities differ')
    # These are the exact joins in the package producer's public metadata:
    # source/tree and payload from selection/composition; engine, kernel and
    # receipt identities from the inspected retained prefix; base from descriptor.
    return {
        'profile': 'both',
        'source_tree_sha256': selection['source']['tree_sha256'],
        'source_observed_at_package_sha256': identities['source_observed_at_package_sha256'],
        'kernel_inputs_sha256': identities['kernel_inputs_sha256'],
        'kernel_descriptor_sha256': artifact['kernel_descriptor_sha256'],
        'kernel_prefix_sha256': artifact['kernel_prefix_sha256'],
        'kernel_prefix_length': artifact['kernel_prefix_length'],
        'kernel_receipt_sha256': identities['kernel_receipt_sha256'],
        'engine_recipe_sha256': identities['engine_recipe_sha256'],
        'engine_manifest_sha256': identities['engine_manifest_sha256'],
        'engine_proof_sha256': identities['engine_proof_sha256'],
        'engine_runtime_sha256': identities['engine_runtime_sha256'],
        'payload_transport_sha256': composition['payload']['transport_sha256'],
        'payload_package_sha256': composition['payload']['package_sha256'],
        'payload_id': composition['payload']['payload_id'],
    }


WIDGET = '''const key=JSON.stringify([arguments[0],arguments[1]]);
const matches=Array.from(document.querySelectorAll('.widget')).filter(e=>e.dataset.key===key);
if(matches.length!==1)throw Error('Expected exactly one widget');
const widget=matches[0];
const bounds=widget.getBoundingClientRect(),style=getComputedStyle(widget);
if(widget.hidden||style.visibility==='hidden'||style.display==='none'||bounds.width<=0||bounds.height<=0)
 throw Error('Widget is not visibly presented');
const editor=widget.matches('input,textarea')?widget:widget.querySelector('input,textarea');
'''
READ = WIDGET + "return arguments[2]==='assert-value'?(editor?editor.value:null):widget.textContent;"
ACTION = WIDGET + '''if(arguments[2]==='edit'){
 if(!editor||editor.disabled||editor.readOnly)throw Error('Widget is not editable');
 editor.focus();editor.value=arguments[3];
 editor.dispatchEvent(new InputEvent('input',{bubbles:true,inputType:'insertReplacementText',data:arguments[3]}));
}else{const button=widget.matches('button')?widget:widget.querySelector('button');
 if(!button||button.disabled)throw Error('Widget is not an enabled button');button.click();}
return true;'''
TRUSTED_TARGET = '''const key=JSON.stringify([arguments[0],arguments[1]]);
const matches=Array.from(document.querySelectorAll('.widget')).filter(e=>e.dataset.key===key);
if(matches.length!==1)throw Error('Expected exactly one widget');
const widget=matches[0],button=widget.matches('button')?widget:widget.querySelector('button');
const editor=widget.matches('input,textarea')?widget:widget.querySelector('input,textarea');
const target=arguments[2]==='edit'?editor:button;
if(!target||target.disabled||arguments[2]==='edit'&&target.readOnly)throw Error('Trusted input target is unavailable');
const style=getComputedStyle(target),r=target.getBoundingClientRect();
if(widget.hidden||style.visibility==='hidden'||style.display==='none'||r.width<=0||r.height<=0)
 throw Error('Trusted input target is not visibly presented');
return {x:r.left+r.width/2,y:r.top+r.height/2};'''


def _trusted_action(browser, engine, step):
    """Use WebDriver pointer/keyboard actions; script execution only locates controls."""
    widget = step['widget']
    point = browser.evaluate(TRUSTED_TARGET, (widget['id'], widget['generation'], step['action']))
    if (type(point) is not dict or any(type(point.get(key)) not in (int, float) or not math.isfinite(point[key])
                                      for key in ('x', 'y'))):
        raise ValueError('browser did not return finite visible input coordinates')
    x, y = round(point['x']), round(point['y'])
    pointer = {'type': 'pointer', 'id': 'foundation-pointer', 'parameters': {'pointerType': 'mouse'},
               'actions': [{'type': 'pointerMove', 'duration': 0, 'x': x, 'y': y},
                           {'type': 'pointerDown', 'button': 0}, {'type': 'pointerUp', 'button': 0}]}
    def dispatch(actions):
        request = {'actions': actions}
        if engine == 'chromium':
            browser.request('POST', browser.path('/actions'), request)
        else:
            browser.command('WebDriver:PerformActions', request)
    # WebDriver sources share ticks. Complete the focus click before sending
    # Ctrl+A/text; combining pointer and keyboard sources races initial focus.
    dispatched_ns = time.monotonic_ns()
    dispatch([pointer])
    if step['action'] == 'edit':
        keys = [{'type': 'keyDown', 'value': '\ue009'}, {'type': 'keyDown', 'value': 'a'},
                {'type': 'keyUp', 'value': 'a'}, {'type': 'keyUp', 'value': '\ue009'}]
        value = step.get('value', '')
        for char in value or '\ue003':
            keys.extend(({'type': 'keyDown', 'value': char}, {'type': 'keyUp', 'value': char}))
        dispatch([{'type': 'key', 'id': 'foundation-keyboard', 'actions': keys}])
    return dispatched_ns


def _rich_clocks(start, dispatch, observed):
    """Protocol/DOM spans only: public bootstrap exports no presentation ACK."""
    return {'kind': 'ordinary-rich-browser-dom-observation-v1',
        'adapter_start_ns': start, 'first_trusted_dispatch_ns': dispatch,
        'changed_dom_observed_ns': observed,
        'adapter_to_changed_dom_ns': observed - start,
        'first_dispatch_to_changed_dom_ns': observed - dispatch,
        'pending_measurements': dict(RICH_PENDING)}


def _valid_rich_clocks(value):
    if type(value) is not dict:
        return False
    try:
        release._keys(value, ('kind', 'adapter_start_ns', 'first_trusted_dispatch_ns',
            'changed_dom_observed_ns', 'adapter_to_changed_dom_ns',
            'first_dispatch_to_changed_dom_ns', 'pending_measurements'), label='rich browser DOM spans')
        start, dispatch, observed = (value[key] for key in
            ('adapter_start_ns', 'first_trusted_dispatch_ns', 'changed_dom_observed_ns'))
        if not all(type(item) is int and item > 0 for item in (start, dispatch, observed)):
            return False
        return (start <= dispatch <= observed
            and all(type(value[key]) is int and value[key] >= 0 for key in
                ('adapter_to_changed_dom_ns', 'first_dispatch_to_changed_dom_ns'))
            and release._same_json(value, _rich_clocks(start, dispatch, observed)))
    except (ValueError, TypeError):
        return False


def _surface_clocks(start, dispatch, observed):
    return {'kind': 'ordinary-rich-browser-native-observation-v1',
        'adapter_start_ns': start, 'first_trusted_dispatch_ns': dispatch,
        'native_result_observed_ns': observed,
        'adapter_to_native_observation_ns': observed - start,
        'first_dispatch_to_native_observation_ns': observed - dispatch,
        'pending_measurements': dict(RICH_PENDING)}


def _valid_surface_clocks(value):
    if type(value) is not dict:
        return False
    try:
        start, dispatch, observed = (value[key] for key in
            ('adapter_start_ns', 'first_trusted_dispatch_ns', 'native_result_observed_ns'))
        return (all(type(item) is int and item > 0 for item in (start, dispatch, observed))
            and start <= dispatch <= observed and release._same_json(value, _surface_clocks(start, dispatch, observed)))
    except (KeyError, ValueError, TypeError):
        return False

OFFLINE = '''const done=arguments[arguments.length-1];
const io=Components.classes['@mozilla.org/network/io-service;1'].getService(Components.interfaces.nsIIOService);
const prefs=Components.classes['@mozilla.org/preferences-service;1'].getService(Components.interfaces.nsIPrefBranch);
prefs.setBoolPref('network.manage-offline-status',false);io.offline=true;
const {NetUtil}=ChromeUtils.importESModule('resource://gre/modules/NetUtil.sys.mjs');
const finish=status=>done({enabled:io.offline,positive_control:status===Components.results.NS_ERROR_OFFLINE?'NS_ERROR_OFFLINE':String(status)});
try{const channel=NetUtil.newChannel({uri:'https://foundation-offline.invalid/qualification',loadUsingSystemPrincipal:true});
channel.asyncOpen({onStartRequest(){},onDataAvailable(request){request.cancel(Components.results.NS_ERROR_ABORT);},
onStopRequest(request,status){finish(status);}});}catch(error){finish(error.result);}'''
OFFLINE_STATE = "return Components.classes['@mozilla.org/network/io-service;1'].getService(Components.interfaces.nsIIOService).offline;"


def _load_browser_helper():
    path = ROOT / 'gui/tests/browser_test.py'
    spec = importlib.util.spec_from_file_location('appended_actual_browser_helper', path)
    module = importlib.util.module_from_spec(spec)
    previous = sys.dont_write_bytecode
    try:
        sys.dont_write_bytecode = True
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


def _process_image(browser):
    pid = browser.capabilities.get('moz:processID')
    if type(pid) is not int or pid <= 0:
        raise ValueError('Firefox did not identify its actual process')
    current, ancestors = pid, []
    for _ in range(64):
        ancestors.append(current)
        if current == browser.process.pid:
            break
        status = Path('/proc', str(current), 'status').read_text()
        match = re.search(r'^PPid:\s+(\d+)$', status, re.MULTILINE)
        if not match or int(match[1]) <= 1:
            raise ValueError('browser process is outside the owned supervisor')
        current = int(match[1])
    else:
        raise ValueError('browser process ancestry exceeds bound')
    path = Path(os.readlink(Path('/proc', str(pid), 'exe')))
    if path.name not in ('firefox', 'firefox-esr', 'firefox-bin'):
        raise ValueError('actual process is not the selected Firefox image')
    saved = container._snapshot(path, 128 * 1024 * 1024)
    return saved, {'pid': pid, 'path': str(path), 'sha256': container.digest(saved.content), 'owned_ancestry': ancestors}


def _proc_identity(pid):
    if type(pid) is not int or pid <= 0:
        raise ValueError('invalid owned browser process identifier')
    raw = Path('/proc', str(pid), 'stat').read_text()
    # comm may contain spaces and parentheses; fields after its last ')' start
    # with field 3. starttime is field 22, not a timestamp guessed from a PID.
    fields = raw[raw.rfind(')') + 2:].split()
    if len(fields) < 20 or not fields[19].isdecimal():
        raise ValueError('browser process identity is unavailable')
    return fields[19], int(fields[1])


def _chromium_images(browser, scenario):
    pid = browser.capabilities.get('goog:processID')
    first = _proc_identity(pid)
    ancestors, identities, current = [], {}, pid
    for _ in range(64):
        ancestors.append(current)
        identities[current] = _proc_identity(current)
        if current == browser.process.pid:
            break
        current = identities[current][1]
        if current <= 1:
            raise ValueError('Chromium process is outside the owned driver supervisor')
    else:
        raise ValueError('Chromium process ancestry exceeds bound')
    if len(ancestors) < 3:
        raise ValueError('Chromium has no owned native driver ancestor')
    driver_pid = ancestors[-2]
    records, snapshots = [], []
    for actual_pid, selected, limit in ((pid, scenario['browser'], MAX_CHROMIUM_IMAGE),
                                       (driver_pid, scenario['browser']['driver'], 128 * 1024 * 1024)):
        image_path = Path(os.readlink(Path('/proc', str(actual_pid), 'exe')))
        image = container._snapshot(image_path, limit)
        expected = container._snapshot(selected['executable'], limit)
        if (image.path != expected.path or image.identity[:2] != expected.identity[:2]
                or container.digest(image.content) != selected['sha256'] or not image.content.startswith(b'\x7fELF')):
            raise ValueError('actual Chromium browser/driver differs from its pinned native image')
        records.append({'pid': actual_pid, 'start_time': identities[actual_pid][0], 'path': str(image.path),
            'sha256': container.digest(image.content), 'owned_ancestry': ancestors[ancestors.index(actual_pid):]})
        snapshots.extend((image, expected))
    if first != identities[pid] or any(_proc_identity(item) != identity for item, identity in identities.items()):
        raise ValueError('browser process identity changed during ancestry inspection')
    return snapshots, records[0], records[1]


def _chromium_identity(capabilities, image, driver, scenario):
    """Validate the observed native identity without inferring it from a name."""
    if type(capabilities) is not dict or capabilities.get('browserName') not in ('chrome', 'chromium'):
        return False
    version = capabilities.get('browserVersion')
    native = capabilities.get('chrome', {})
    driver_version = native.get('chromedriverVersion') if type(native) is dict else None
    if (type(version) is not str or not re.fullmatch(r'[0-9]+(?:\.[0-9]+){3}', version)
            or not _text(driver_version, 256)
            or not re.fullmatch(r'[0-9]+(?:\.[0-9]+){3}(?: \([^\r\n]*\))?', driver_version)
            or version.split('.')[0] != driver_version.split('.')[0]):
        return False
    for observed, selected, expected_pid in ((image, scenario['browser'], capabilities.get('goog:processID')),
                                           (driver, scenario['browser']['driver'], None)):
        if (type(observed) is not dict or type(observed.get('pid')) is not int or observed['pid'] <= 0
                or expected_pid is not None and observed['pid'] != expected_pid
                or type(observed.get('start_time')) is not str or not DECIMAL.fullmatch(observed['start_time'])
                or observed.get('path') != selected['executable'] or observed.get('sha256') != selected['sha256']
                or type(observed.get('owned_ancestry')) is not list or not 2 <= len(observed['owned_ancestry']) <= 64
                or observed['owned_ancestry'][0] != observed['pid']
                or any(type(item) is not int or item <= 0 for item in observed['owned_ancestry'])
                or len(set(observed['owned_ancestry'])) != len(observed['owned_ancestry'])):
            return False
    return (type(capabilities.get('goog:processID')) is int
            and image['owned_ancestry'][-2:] == driver['owned_ancestry']
            and driver['pid'] != image['pid'])


class _CanaryResources:
    """An owned bounded resource witness, never an application HTTP server."""
    def __init__(self, deadline):
        self.deadline, self.lock = deadline, threading.Lock()
        self.closed, self.cleanup_error = False, None
        token = secrets.token_hex(24)
        self.bodies = {'/' + token + '/' + phase + '/' + role: token + ':' + phase + ':' + role
            for phase, roles in (('online', CANARY_ROLES), ('before', (*CANARY_ROLES, 'host')),
                                 ('after', (*CANARY_ROLES, 'host'))) for role in roles}
        self.counts = dict.fromkeys(self.bodies, 0)
        owner = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def setup(self):
                self.request.settimeout(max(.01, min(5, owner.deadline - time.monotonic())))
                super().setup()

            def do_GET(self):
                with owner.lock:
                    if self.path not in owner.bodies or owner.counts[self.path] >= 2:
                        self.send_error(404);return
                    owner.counts[self.path] += 1
                    content = owner.bodies[self.path].encode('ascii')
                self.send_response(200)
                self.send_header('Content-Type', 'text/plain')
                self.send_header('Content-Length', str(len(content)))
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Cache-Control', 'no-store')
                self.end_headers();self.wfile.write(content)

            def log_message(self, *args):
                pass

        self.server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.server.daemon_threads = False
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={'poll_interval': .02},
                                       name='appended-chromium-resource-witness')
        try:
            self.thread.start()
        except BaseException:
            self.server.server_close()
            raise

    def resource(self, phase, role):
        suffix = '/' + phase + '/' + role
        path = next(name for name in self.bodies if name.endswith(suffix))
        return path, 'http://127.0.0.1:' + str(self.server.server_port) + path, self.bodies[path]

    def count(self, path):
        with self.lock:
            return self.counts[path]

    def control(self, phase):
        path, _, expected = self.resource(phase, 'host')
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port,
            timeout=max(.01, min(5, self.deadline - time.monotonic())))
        try:
            connection.request('GET', path)
            response = connection.getresponse()
            if response.status != 200 or response.read(4096) != expected.encode('ascii') or self.count(path) != 1:
                raise ValueError('owned browser resource witness failed its independent liveness control')
        finally:
            connection.close()
        return True

    def close(self):
        # Handler requests have bounded reads, and server_close joins all handler
        # threads. No final browser evidence precedes listener/writer closure.
        if self.cleanup_error is not None:
            raise self.cleanup_error
        if self.closed:
            return
        try:
            self.server.shutdown();self.thread.join(timeout=6)
            self.server.server_close()
            if self.thread.is_alive():
                raise RuntimeError('listener remains live')
        except BaseException as error:
            self.cleanup_error = ProcessTreeError('browser canary cleanup uncertain; retain output ownership: ' + str(error))
            raise self.cleanup_error from error
        self.closed = True

    def complete(self):
        with self.lock:
            for path, count in self.counts.items():
                expected = 1 if '/online/' in path or path.endswith('/host') else 0
                if count != expected:
                    raise ValueError('browser resource witness recorded a late, missing or duplicate request')


CANARY_FETCH = '''const done=arguments[arguments.length-1],url=arguments[0],body=arguments[1];
fetch(url,{mode:'cors',cache:'no-store'}).then(async response=>done({response:response.ok&&await response.text()===body}),
()=>done({response:false}));'''
CANARY_WORKER = '''const done=arguments[arguments.length-1];
const source="onmessage=async e=>{try{const r=await fetch(e.data.url,{mode:'cors',cache:'no-store'});postMessage({response:r.ok&&await r.text()===e.data.body});}catch(e){postMessage({response:false});}}";
const object=URL.createObjectURL(new Blob([source],{type:'text/javascript'})),worker=new Worker(object);
URL.revokeObjectURL(object);let finished=false;
const finish=value=>{if(finished)return;finished=true;clearTimeout(timer);worker.terminate();done(value);};
const timer=setTimeout(()=>finish({error:'worker-timeout'}),arguments[2]);
worker.onmessage=e=>finish(e.data);worker.onerror=()=>finish({error:'worker-error'});
worker.postMessage({url:arguments[0],body:arguments[1]});'''


def _canary_phase(browser, resources, phase, online):
    result = {}
    for role in CANARY_ROLES:
        browser.root()
        if role == 'frame':
            browser.frame(0)
        path, url, body = resources.resource(phase, role)
        observed = browser.evaluate(CANARY_WORKER if role == 'worker' else CANARY_FETCH,
            (url, body, 8000) if role == 'worker' else (url, body), asynchronous=True)
        count = resources.count(path)
        expected = {'response': online}
        if observed != expected or count != int(online):
            raise ValueError('Chromium ' + role + ' did not prove the selected online/offline resource behavior')
        result[role] = dict(expected, requests=count)
    browser.root()
    return result


def _owned_children(pid):
    """Read cooperative descendants without guessing or signaling foreign PIDs."""
    result, pending, task_count = set(), [pid], 0
    while pending:
        current = pending.pop()
        try:
            tasks = list(Path('/proc', str(current), 'task').iterdir())
        except FileNotFoundError:
            continue
        task_count += len(tasks)
        if task_count > 4096:
            raise ProcessTreeError('browser task inventory exceeds bound')
        children = set()
        for task in tasks:
            try:
                children.update(int(raw) for raw in (task / 'children').read_text().split())
            except FileNotFoundError:
                continue
        for child in children:
            if child <= 0 or child == pid or len(result) >= 4096:
                raise ProcessTreeError('browser descendant inventory is cyclic or exceeds bound')
            if child not in result:
                result.add(child);pending.append(child)
    return result


def _chromium_quit(browser, image, driver, deadline):
    if browser.cdp('Browser.close', {}) != {}:
        raise ValueError('Chromium did not acknowledge normal browser close')
    while time.monotonic() < deadline:
        children = _owned_children(browser.process.pid)
        if children == {driver['pid']}:
            try:
                browser_gone = _proc_identity(image['pid'])[0] != image['start_time']
            except FileNotFoundError:
                browser_gone = True
            if browser_gone:
                break
        if browser.owner.poll() is not None:
            raise ValueError('Chromium driver exited before its browser descendants joined')
        time.sleep(.02)
    else:
        raise TimeoutError('Chromium browser/helper descendants did not exit normally')
    try:
        if _proc_identity(image['pid'])[0] == image['start_time']:
            raise ValueError('Chromium browser remained live after its close acknowledgement')
    except FileNotFoundError:
        pass
    if _proc_identity(driver['pid'])[0] != driver['start_time']:
        raise ValueError('Chromium driver process identity changed before shutdown')
    if browser.request('GET', '/shutdown') is not None:
        raise ValueError('Chromium driver did not acknowledge normal shutdown')
    if browser.owner.wait(timeout=max(.01, min(10, deadline - time.monotonic()))) != 0:
        raise ValueError('Chromium driver did not exit normally')
    browser.owner.finish();browser.owner.close();browser.log.close();browser.closed = True
    return {'acknowledged': True, 'normal_exit': True}


def _execute_chromium(runtime, scenario, evidence, work, timeout, environment):
    helper, deadline = _load_browser_helper(), time.monotonic() + timeout
    adapter_start_ns = time.monotonic_ns() if 'rich_identities' in scenario else None

    class Chromium(helper.ChromiumBrowser):
        def _launch(self, argv, directory, log_name, *, env=None):
            self.owner = None;self.closed = False;self.cleanup_error = None
            self.log = (directory / log_name).open('x')
            try:
                self.owner = helper.process_tree.launch(argv, work, self.log, env=dict(environment))
                self.process = self.owner.process
            except BaseException:
                self._close(lambda: None);raise

        def request(self, method, path, data=None):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                # The reused startup loop retries OSError (including Python's
                # TimeoutError). A terminal budget exhaustion must not be retried.
                raise ValueError('Chromium scenario exceeded its total deadline')
            if method == 'POST' and path == '/session':
                data['capabilities']['alwaysMatch']['goog:loggingPrefs'] = {'browser': 'ALL'}
            request = urllib.request.Request(self.base + path,
                data=None if data is None else json.dumps(data).encode(),
                headers={'Content-Type': 'application/json'}, method=method)
            try:
                with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request, timeout=min(15, remaining)) as response:
                    raw = response.read(32 * 1024 * 1024 + 1)
                    if len(raw) > 32 * 1024 * 1024:
                        raise ValueError('Chromium driver response exceeds bound')
                    value = json.loads(raw)
            except urllib.error.HTTPError as error:
                raise ValueError('Chromium driver rejected fixed instrumentation: ' + error.read(4096).decode(errors='replace')) from error
            if type(value) is not dict or 'value' not in value or type(value['value']) is dict and 'error' in value['value']:
                raise ValueError('Chromium driver returned malformed or unsupported instrumentation')
            return value['value']

        def evaluate(self, source, arguments=(), *, asynchronous=False):
            return self.request('POST', self.path('/execute/async' if asynchronous else '/execute/sync'),
                {'script': source, 'args': list(arguments)})

        def until(self, source, arguments=(), expected=True):
            while time.monotonic() < deadline:
                if self.evaluate(source, arguments) == expected:
                    return
                time.sleep(.02)
            raise TimeoutError('Chromium application assertion did not become true')

        def cdp(self, method, params):
            return self.request('POST', self.path('/goog/cdp/execute'), {'cmd': method, 'params': params})

        def conditions(self, value=None):
            if value is not None:
                self.request('POST', self.path('/chromium/network_conditions'), {'network_conditions': value})
            result = self.request('GET', self.path('/chromium/network_conditions'))
            if value is not None and container.canonical_json(result) != container.canonical_json(value):
                raise ValueError('Chromium native network-condition readback differs')
            return result

    browser, resources, result = None, None, None
    try:
        with helper.browser_workspace(evidence) as workspace:
            try:
                browser = Chromium(scenario['browser']['executable'], scenario['browser']['driver']['executable'], workspace,
                    ['--disable-background-networking', '--disable-component-update', '--disable-extensions',
                     '--disable-sync', '--no-default-browser-check', '--no-proxy-server'])
                images, image, driver = _chromium_images(browser, scenario)
                if not _chromium_identity(browser.capabilities, image, driver, scenario):
                    raise ValueError('actual Chromium browser/driver identity or version join is absent')
                browser.request('POST', browser.path('/timeouts'), {'script': min(10000, int(timeout * 1000))})
                browser.request('POST', browser.path('/window/rect'), scenario['viewport'])
                control = work / 'owned browser network control.html'
                with control.open('x') as stream:
                    stream.write('<!doctype html><meta charset="utf-8"><iframe sandbox="allow-scripts" srcdoc="<!doctype html><meta charset=&quot;utf-8&quot;>"></iframe>')
                resources = _CanaryResources(deadline)
                browser.command('WebDriver:Navigate', {'url': control.resolve().as_uri()})
                browser.until('return document.readyState === "complete";')
                online_conditions = browser.conditions(CHROMIUM_ONLINE)
                online = _canary_phase(browser, resources, 'online', True)
                conditions = browser.conditions(CHROMIUM_OFFLINE)
                before = {'online': online, 'offline': _canary_phase(browser, resources, 'before', False),
                    'online_conditions': online_conditions, 'conditions': conditions, 'listener_control': resources.control('before')}
                browser.command('WebDriver:Navigate', {'url': runtime.resolve().as_uri()})
                browser.until('return document.readyState === "complete";')
                browser.until('return document.querySelector("#status")?.textContent;', expected=scenario['title'])
                policy = browser.evaluate("return Array.from(document.querySelectorAll('iframe')).map(e=>({sandbox:e.getAttribute('sandbox'),srcdoc:e.hasAttribute('srcdoc')}));")
                if policy != [{'sandbox': 'allow-scripts', 'srcdoc': True}]:
                    raise ValueError('binary GUI requires exactly one isolated output frame')
                browser.frame(0)
                if scenario['schema_version'] == 3:
                    observations, first_input_dispatch_ns, changed_dom_observed_ns, surface_baseline = _exercise_surface(browser, 'chromium', scenario, evidence, deadline)
                    changed = True
                else:
                    initial = {}
                    for step in scenario['steps']:
                        if step['action'].startswith('assert-'):
                            key = (step['widget']['id'], step['widget']['generation'], step['action'])
                            initial[key] = browser.evaluate(READ, key)
                    observations, changed, edits = [], False, set()
                    first_input_dispatch_ns = changed_dom_observed_ns = None
                    for step in scenario['steps']:
                        key = (step['widget']['id'], step['widget']['generation'])
                        args = (*key, step['action'], step.get('value'))
                        if step['action'] in ('edit', 'activate'):
                            if step['action'] == 'edit':
                                if key in edits:
                                    raise ValueError('scenario cannot repeat an unacknowledged edit')
                                edits.add(key)
                            if 'rich_identities' in scenario:
                                dispatched_ns = _trusted_action(browser, 'chromium', step)
                                if first_input_dispatch_ns is None:
                                    first_input_dispatch_ns = dispatched_ns
                            else:
                                browser.evaluate(ACTION, args)
                        else:
                            browser.until(READ, args[:3], step['value'])
                            changed |= key not in edits and initial[(*key, step['action'])] != step['value']
                            if changed and first_input_dispatch_ns is not None and changed_dom_observed_ns is None:
                                changed_dom_observed_ns = time.monotonic_ns()
                        observations.append({'id': step['id'], 'action': step['action'], 'widget': step['widget'], 'passed': True})
                if not changed:
                    raise ValueError('scenario did not prove a changed application result beyond provisional edits')
                capture = base64.b64decode(browser.command('WebDriver:TakeScreenshot', {})['value'], validate=True)
                if len(capture) > 16 * 1024 * 1024:
                    raise ValueError('browser capture exceeds bound')
                with (evidence / 'capture.png').open('xb') as stream:
                    stream.write(capture)
                browser.root();browser.command('WebDriver:Navigate', {'url': control.resolve().as_uri()})
                browser.until('return document.readyState === "complete";')
                after = {'offline': _canary_phase(browser, resources, 'after', False),
                    'conditions': browser.conditions(), 'listener_control': resources.control('after')}
                resources.close();resources.complete();resources = None
                offline = {'enabled': True, 'positive_control': 'owned-loopback-root-frame-worker',
                           'before': before, 'after': after, 'listener_joined': True}
                if not _validate_offline('chromium', offline):
                    raise ValueError('Chromium complete offline resource witness differs')
                for saved in images:
                    container._recheck(saved)
                quit_result = _chromium_quit(browser, image, driver, deadline)
                for saved in images:
                    container._recheck(saved)
                result = {'engine': 'chromium', 'capabilities': browser.capabilities, 'actual_image': image,
                    'actual_driver': driver, 'offline': offline, 'quit': quit_result, 'process_tree_joined': True,
                    'direct_file_uri': runtime.resolve().as_uri(), 'runtime_sha256': container.digest(runtime.read_bytes()),
                    'executed_tests': [step['id'] for step in scenario['steps']], 'observations': observations,
                    'application_result_changed': True, 'capture_sha256': container.digest(capture), 'frame_policy': policy}
                if scenario['schema_version'] == 3:
                    result['rich_surface_baseline'] = surface_baseline
                if adapter_start_ns is not None:
                    if first_input_dispatch_ns is None or changed_dom_observed_ns is None:
                        raise ValueError('rich BOTH DOM span lacks a trusted input and changed result')
                    result['clocks'] = (_surface_clocks if scenario['schema_version'] == 3 else _rich_clocks)(adapter_start_ns, first_input_dispatch_ns, changed_dom_observed_ns)
            finally:
                try:
                    if resources is not None:
                        resources.close()
                finally:
                    if browser is not None:
                        browser.close()
    except helper.BrowserCleanupError as error:
        raise ProcessTreeError('Chromium cleanup uncertain; retain output ownership: ' + str(error)) from error
    return result


def _execute_browser(runtime, scenario, evidence, work, timeout, environment):
    """Only physical browser boundary. No supplied script or application glue."""
    if scenario['browser']['engine'] == 'chromium':
        return _execute_chromium(runtime, scenario, evidence, work, timeout, environment)
    helper = _load_browser_helper()
    deadline = time.monotonic() + timeout
    adapter_start_ns = time.monotonic_ns() if 'rich_identities' in scenario else None
    helper.FIREFOX_STARTUP_TIMEOUT_SECONDS = min(timeout, 60)

    class Firefox(helper.Browser):
        def _launch(self, argv, directory, log_name, *, env=None):
            preferences = {'network.manage-offline-status': False, 'browser.offline': True,
                # Firefox's optional idle forkserver may outlive a normal Quit.
                # Disable that launcher optimization in this fresh test profile
                # so strict whole-tree natural completion remains required.
                'dom.ipc.forkserver.enable': False,
                'app.update.enabled': False, 'app.update.auto': False, 'extensions.update.enabled': False,
                'network.captive-portal-service.enabled': False, 'network.connectivity-service.enabled': False,
                'datareporting.healthreport.uploadEnabled': False, 'toolkit.telemetry.enabled': False,
                'media.peerconnection.enabled': False, 'browser.startup.homepage': 'about:blank'}
            with (self.profile / 'user.js').open('a') as stream:
                import json
                stream.write(''.join('user_pref(' + json.dumps(key) + ',' + json.dumps(value) + ');\n' for key, value in preferences.items()))
            argv.insert(1, '--remote-allow-system-access')
            self.owner = None;self.closed = False;self.cleanup_error = None
            self.log = (directory / log_name).open('x')
            try:
                self.owner = helper.process_tree.launch(argv, work, self.log, env=dict(environment, MOZ_HEADLESS='1'))
                self.process = self.owner.process
            except BaseException:
                self._close(lambda: None)
                raise

        def command(self, name, args):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError('browser scenario exceeded its total deadline')
            self.socket.settimeout(min(15, remaining))
            return super().command(name, args)

        def evaluate(self, source, arguments=(), *, asynchronous=False):
            return self.command('WebDriver:ExecuteAsyncScript' if asynchronous else 'WebDriver:ExecuteScript',
                {'script': source, 'args': list(arguments), 'newSandbox': True, 'sandbox': None})['value']

        def until(self, source, arguments=(), expected=True):
            while time.monotonic() < deadline:
                if self.evaluate(source, arguments) == expected:
                    return
                time.sleep(.02)
            raise TimeoutError('browser application assertion did not become true')

    result, browser = None, None
    try:
        with helper.browser_workspace(evidence) as workspace:
            try:
                browser = Firefox(scenario['browser']['executable'], workspace)
                capabilities = browser.capabilities
                if (capabilities.get('browserName') != 'firefox' or not _text(capabilities.get('browserVersion'), 128)
                        or type(capabilities.get('moz:buildID')) is not str or not re.fullmatch(r'[0-9]{14}', capabilities['moz:buildID'])):
                    raise ValueError('actual Firefox identity is absent')
                image, image_record = _process_image(browser)
                browser.command('WebDriver:SetTimeouts', {'script': min(10000, int(timeout * 1000))})
                browser.command('Marionette:SetContext', {'value': 'chrome'})
                offline = browser.evaluate(OFFLINE, asynchronous=True)
                if offline != {'enabled': True, 'positive_control': 'NS_ERROR_OFFLINE'}:
                    raise ValueError('browser resource blocking was not proved offline')
                browser.command('Marionette:SetContext', {'value': 'content'})
                browser.command('WebDriver:SetWindowRect', scenario['viewport'])
                browser.command('WebDriver:Navigate', {'url': runtime.resolve().as_uri()})
                browser.until('return document.readyState === "complete";')
                browser.until('return document.querySelector("#status")?.textContent;', expected=scenario['title'])
                policy = browser.evaluate("return Array.from(document.querySelectorAll('iframe')).map(e=>({sandbox:e.getAttribute('sandbox'),srcdoc:e.hasAttribute('srcdoc')}));")
                if policy != [{'sandbox': 'allow-scripts', 'srcdoc': True}]:
                    raise ValueError('binary GUI requires exactly one isolated output frame')
                browser.frame(0)
                if scenario['schema_version'] == 3:
                    observations, first_input_dispatch_ns, changed_dom_observed_ns, surface_baseline = _exercise_surface(browser, 'firefox', scenario, evidence, deadline)
                    changed = True
                else:
                    initial = {}
                    for step in scenario['steps']:
                        if step['action'].startswith('assert-'):
                            key = (step['widget']['id'], step['widget']['generation'], step['action'])
                            initial[key] = browser.evaluate(READ, key)
                    observations, changed, edits = [], False, set()
                    first_input_dispatch_ns = changed_dom_observed_ns = None
                    for step in scenario['steps']:
                        key = (step['widget']['id'], step['widget']['generation'])
                        args = (*key, step['action'], step.get('value'))
                        if step['action'] in ('edit', 'activate'):
                            if step['action'] == 'edit':
                                if key in edits:
                                    raise ValueError('scenario v1 cannot repeat an edit without an application acknowledgement')
                                edits.add(key)
                            if 'rich_identities' in scenario:
                                dispatched_ns = _trusted_action(browser, 'firefox', step)
                                if first_input_dispatch_ns is None:
                                    first_input_dispatch_ns = dispatched_ns
                            else:
                                browser.evaluate(ACTION, args)
                        else:
                            browser.until(READ, args[:3], step['value'])
                            changed |= key not in edits and initial[(*key, step['action'])] != step['value']
                            if changed and first_input_dispatch_ns is not None and changed_dom_observed_ns is None:
                                changed_dom_observed_ns = time.monotonic_ns()
                        observations.append({'id': step['id'], 'action': step['action'], 'widget': step['widget'], 'passed': True})
                if not changed:
                    raise ValueError('scenario did not prove a changed application result beyond provisional edits')
                raw = browser.command('WebDriver:TakeScreenshot', {})['value']
                capture = base64.b64decode(raw, validate=True)
                if len(capture) > 16 * 1024 * 1024:
                    raise ValueError('browser capture exceeds bound')
                with (evidence / 'capture.png').open('xb') as stream:
                    stream.write(capture)
                browser.root();browser.command('Marionette:SetContext', {'value': 'chrome'})
                if browser.evaluate(OFFLINE_STATE) is not True:
                    raise ValueError('browser left offline mode during application execution')
                container._recheck(image)
                quit_result = browser.command('Marionette:Quit', {'flags': ['eAttemptQuit']})
                if (type(quit_result) is not dict or quit_result.get('cause') != 'shutdown'
                        or quit_result.get('forced') is not False or quit_result.get('in_app') is not True):
                    raise ValueError('browser did not acknowledge a normal application quit')
                if browser.owner.wait(timeout=10) != 0:
                    raise ValueError('browser did not exit normally after quit')
                browser.owner.finish();browser.owner.close()
                browser.socket.close();browser.log.close();browser.closed = True
                container._recheck(image)
                result = {'engine': 'firefox', 'capabilities': capabilities, 'actual_image': image_record,
                    'offline': offline, 'quit': {'acknowledged': True, 'normal_exit': True},
                    'process_tree_joined': True, 'direct_file_uri': runtime.resolve().as_uri(),
                    'runtime_sha256': container.digest(runtime.read_bytes()), 'executed_tests': [step['id'] for step in scenario['steps']],
                    'observations': observations, 'application_result_changed': True,
                    'capture_sha256': container.digest(capture), 'frame_policy': policy}
                if scenario['schema_version'] == 3:
                    result['rich_surface_baseline'] = surface_baseline
                if adapter_start_ns is not None:
                    if first_input_dispatch_ns is None or changed_dom_observed_ns is None:
                        raise ValueError('rich BOTH DOM span lacks a trusted input and changed result')
                    result['clocks'] = (_surface_clocks if scenario['schema_version'] == 3 else _rich_clocks)(adapter_start_ns, first_input_dispatch_ns, changed_dom_observed_ns)
            finally:
                if browser is not None:
                    browser.close()
    except helper.BrowserCleanupError as error:
        raise ProcessTreeError('browser cleanup uncertain; retain output ownership: ' + str(error)) from error
    # Neither a successful test nor a parent process exit precedes cleanup proof.
    return result


def _installed(context, helpers):
    """Validate an install helper's owned prefix without relocating its runtime."""
    prefix = container._ordinary_path(context['installed_prefix'], directory=True)
    inventory = context['installed_inventory']
    if type(inventory) is not dict or helpers['tree'](prefix) != inventory:
        raise ValueError('installed browser prefix differs from its complete trusted inventory')
    release._keys(inventory, ('files', 'directories'), label='installed browser inventory')
    entry = context['artifact']
    expected = {name: dict(value, mode=entry['modes'][name]) for name, value in entry['files'].items()}
    if any(inventory['files'].get(name) != value for name, value in expected.items()):
        raise ValueError('installed browser artifact bytes or modes differ from frozen product')
    _, _, directories = release._members(context['directory'] / entry['archive'])
    if any(inventory['directories'].get(name) != mode for name, mode in directories.items()):
        raise ValueError('installed browser artifact directory modes differ from frozen product')
    return prefix, inventory


def _identities(root):
    """Bind the complete prefix, including trusted foreign files, to its objects."""
    result = {}
    for path in (root, *sorted(root.rglob('*'))):
        if path.is_symlink():
            raise ValueError('browser runtime prefix contains a link')
        stat = path.lstat()
        result[path.relative_to(root).as_posix()] = (stat.st_dev, stat.st_ino, stat.st_mode,
            stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
    return result


def run(context):
    _execution(context['execution_context'])
    if type(context['timeout']) not in (int, float) or not 0 < context['timeout'] <= 300:
        raise ValueError('browser timeout must be positive and bounded')
    directory, subject, artifact = context['directory'], context['subject'], context['artifact']
    if (context['target'], context['backend']) != ('web-wasm32', 'web'):
        raise ValueError('browser adapter requires the exact web-wasm32/web product')
    observed = release.verify_composition_subject(directory, subject['candidate_sha256'])
    if observed != subject or artifact not in observed['composition']['artifacts']:
        raise ValueError('browser selection differs from verified complete candidate')
    rich = artifact.get('profile') == 'both'
    if rich:
        if artifact['carrier'] != 'html' or subject['composition']['payload']['mode'] != 'both':
            raise ValueError('rich browser adapter requires an HTML BOTH application')
    elif artifact['carrier'] != 'html' or artifact['profile'] != 'binary' or subject['composition']['payload']['mode'] != 'binary':
        raise ValueError('browser adapter requires a binary-defined GUI application in an HTML carrier')
    saved, scenario, inputs = _scenario(context['scenario'], context['scenario_sha256'], subject, artifact, context['target'], context['backend'])
    rich_sources = _rich_sources(scenario['rich_inspection_sources']) if rich else []
    if rich:
        expected = _rich_both_identity(directory, subject, artifact)
        if scenario['rich_identities'] != expected:
            raise ValueError('rich BOTH scenario identities differ from verified engine/kernel/base/payload metadata')
    if not sys.platform.startswith('linux'):
        raise ValueError('actual browser adapters currently require Linux')
    chromium = scenario['browser']['engine'] == 'chromium'
    executable = container._snapshot(scenario['browser']['executable'], MAX_CHROMIUM_IMAGE if chromium else 128 * 1024 * 1024)
    if container.digest(executable.content) != scenario['browser']['sha256'] or not executable.path.stat().st_mode & 0o111:
        raise ValueError('selected browser executable differs from independent pin or is not executable')
    driver_input = None
    if chromium:
        driver_input = container._snapshot(scenario['browser']['driver']['executable'], 128 * 1024 * 1024)
        if (container.digest(driver_input.content) != scenario['browser']['driver']['sha256'] or not driver_input.mode & 0o111
                or executable.identity[:2] == driver_input.identity[:2]
                or any(not item.content.startswith(b'\x7fELF') for item in (executable, driver_input))):
            raise ValueError('Chromium requires distinct pinned executable native browser and driver images')
    sources = [container._snapshot(ROOT / name, 2 * 1024 * 1024) for name in CHECKER_SOURCES]
    checker_sources = dict(context.get('checker_sources', {}))
    for name, item in zip(CHECKER_SOURCES, sources):
        actual = container.digest(item.content)
        if name in checker_sources and checker_sources[name] != actual:
            raise ValueError('browser checker source differs from frozen execution')
        checker_sources[name] = actual
    helpers, evidence, work = context['helpers'], context['evidence'] / 'browser', context['work']
    installed = ('installed_prefix' in context, 'installed_inventory' in context)
    if installed[0] != installed[1]:
        raise ValueError('installed browser execution requires both trusted prefix and full inventory')
    evidence.mkdir()
    helpers['new_json'](evidence / 'scenario.json', scenario)
    if rich:
        source_directory = evidence / 'rich-inspection-sources';source_directory.mkdir()
        for name, item in zip(RICH_INSPECTION_SOURCES, rich_sources):
            with (source_directory / Path(name).name).open('xb') as stream:
                stream.write(item.content)
        if scenario['schema_version'] == 3:
            surface_directory = evidence / 'rich-surface-sources';surface_directory.mkdir()
            _, surface_source = _surface_actions(scenario['rich_surface_sources'])
            with (surface_directory / surface_source.path.name).open('xb') as stream:
                stream.write(surface_source.content)
    if installed[0]:
        relocated, before = _installed(context, helpers)
    else:
        relocated = work / 'relocated browser archive with spaces'
        before = helpers['extract'](directory, artifact, relocated)
    identities = _identities(relocated)
    runtime = relocated / artifact['runtime_member']
    if container.digest(runtime.read_bytes()) != artifact['runtime_sha256']:
        raise ValueError('extracted final browser runtime differs')
    helpers['new_json'](evidence / 'before.json', before)
    names = [step['id'] for step in scenario['steps']]
    environment_work = work / 'browser environment';environment_work.mkdir()
    try:
        result = _execute_browser(runtime, scenario, evidence, work, context['timeout'], helpers['environment'](environment_work))
        if type(result) is not dict or result.get('process_tree_joined') is not True:
            raise ProcessTreeError('browser process tree completion is unproved; retain output ownership')
        if (result.get('engine') != scenario['browser']['engine']
                or not _validate_offline(result.get('engine'), result.get('offline'))
                or result.get('quit') != {'acknowledged': True, 'normal_exit': True}
                or result.get('direct_file_uri') != runtime.resolve().as_uri()
                or result.get('runtime_sha256') != artifact['runtime_sha256']):
            raise ValueError('actual browser identity, offline and quit/join evidence are incomplete')
        if rich and not (_valid_surface_clocks if scenario['schema_version'] == 3 else _valid_rich_clocks)(result.get('clocks')):
            raise ValueError('rich BOTH browser result lacks honest DOM spans and pending presentation metrics')
        capabilities, image = result.get('capabilities', {}), result.get('actual_image', {})
        if chromium:
            if not _chromium_identity(capabilities, image, result.get('actual_driver'), scenario):
                raise ValueError('actual Chromium process/image/driver/build identity is incomplete')
            actual_driver = container._snapshot(result['actual_driver']['path'], 128 * 1024 * 1024)
            if container.digest(actual_driver.content) != scenario['browser']['driver']['sha256']:
                raise ValueError('actual Chromium driver changed after execution')
        elif (type(capabilities) is not dict or capabilities.get('browserName') != 'firefox'
                or not _text(capabilities.get('browserVersion'), 128)
                or type(capabilities.get('moz:buildID')) is not str or not re.fullmatch(r'[0-9]{14}', capabilities['moz:buildID'])
                or type(capabilities.get('moz:processID')) is not int or capabilities['moz:processID'] <= 0
                or type(image) is not dict or image.get('pid') != capabilities['moz:processID']
                or not _text(image.get('path'), 4096) or not Path(image['path']).is_absolute()
                or type(image.get('owned_ancestry')) is not list or not 2 <= len(image['owned_ancestry']) <= 64
                or image['owned_ancestry'][0] != image['pid']
                or any(type(pid) is not int or pid <= 0 for pid in image['owned_ancestry'])):
            raise ValueError('actual browser process/image/build identity is incomplete')
        image_after = container._snapshot(image['path'], MAX_CHROMIUM_IMAGE if chromium else 128 * 1024 * 1024)
        if container.digest(image_after.content) != release._sha(image.get('sha256')):
            raise ValueError('actual browser image changed after execution')
        capture = container._snapshot(evidence / 'capture.png', 16 * 1024 * 1024)
        if not capture.content.startswith(b'\x89PNG\r\n\x1a\n') or container.digest(capture.content) != result.get('capture_sha256'):
            raise ValueError('browser capture is missing or differs')
        context['passed'].append('actual-browser')
        surface_captures = []
        if scenario['schema_version'] == 3:
            if result.get('executed_tests') != names or result.get('application_result_changed') is not True or result.get('frame_policy') != [{'sandbox': 'allow-scripts', 'srcdoc': True}]:
                raise ValueError('browser did not execute its complete rich surface scenario')
            surface_captures = _check_surface_records(result, scenario, evidence)
        else:
            observations = result.get('observations')
            if (result.get('executed_tests') != names or result.get('application_result_changed') is not True
                    or type(observations) is not list or len(observations) != len(names)
                    or any(observed != {'id': step['id'], 'action': step['action'], 'widget': step['widget'], 'passed': True}
                           for observed, step in zip(observations, scenario['steps']))
                    or result.get('frame_policy') != [{'sandbox': 'allow-scripts', 'srcdoc': True}]):
                raise ValueError('browser did not execute its complete application scenario')
        context['passed'].append('application-scenario')
        after = helpers['tree'](relocated)
        helpers['new_json'](evidence / 'after.json', after)
        if (after != before or _identities(relocated) != identities
                or container.digest(runtime.read_bytes()) != artifact['runtime_sha256']):
            raise ValueError('browser runtime or extracted byte inventory changed')
        for item in (saved, executable, image_after, capture, *inputs, *sources, *rich_sources, *surface_captures):
            container._recheck(item)
        if chromium:
            container._recheck(driver_input);container._recheck(actual_driver)
        if release.verify_composition_subject(directory, subject['candidate_sha256']) != subject:
            raise ValueError('browser candidate changed during execution')
        context['passed'].append('retained-runtime')
    except BaseException as error:
        if not helpers['uncertain'](error):
            helpers['junit'](evidence / 'scenario.junit.xml', names, failed=(names[0], str(error)), skipped=names[1:])
        raise
    helpers['junit'](evidence / 'scenario.junit.xml', names)
    result.update(executable={'path': str(executable.path), 'sha256': scenario['browser']['sha256']},
                  scenario_sha256=context['scenario_sha256'], browser_version=capabilities['browserVersion'], status='passed')
    if rich:
        result['rich_inspection_sources'] = dict(scenario['rich_inspection_sources'])
        result['scenario_scope'] = ('physical retained-engine surface input, native document readback and captured pixels; native ACK/causal latency unmeasured' if scenario['schema_version'] == 3 else 'trusted compiled-view controls in an eligible BOTH carrier; rich engine-frame interactions unmeasured')
        if scenario['schema_version'] == 3:
            result['rich_surface_sources'] = dict(scenario['rich_surface_sources'])
    if chromium:
        result['driver'] = {'path': str(driver_input.path), 'sha256': scenario['browser']['driver']['sha256']}
    helpers['new_json'](evidence / 'observation.json', result)
    return {'scenario_sha256': context['scenario_sha256'], 'executed_tests': names,
            'junit': 'browser/scenario.junit.xml', 'browser': result, 'checker_sources': checker_sources}
