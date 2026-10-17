#!/usr/bin/env python3
"""Finalize an explicit binary-only browser kernel from already compiled assets.

This separate producer does not change package_wasm's legacy/source-identity
schemas, build a runtime, acquire an SDK, compose a payload or certify a release.
Use appended_container to replace/remove the suffix of its retained exact prefix.
"""
import argparse
import base64
from html import escape
import json
from pathlib import Path
import re
import sys

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
import appended_container as container
import browser_bundle
import package_wasm

HTML_NAME = 'foundation-appended-browser.html'
DESCRIPTOR_NAME = 'kernel.json'
KIND = 'foundation-binary-browser-kernel-v1'
CSP = package_wasm.CSP
POLICY = {'abi': {'major': 1, 'minor': 0}, 'services': ['foundation.kernel', 'foundation.view'],
          'capabilities': ['foundation.view.v1']}
PROVIDERS_POLICY = {'abi': {'major': 1, 'minor': 0},
                    'services': ['foundation.kernel', 'foundation.providers', 'foundation.view'],
                    'capabilities': ['foundation.providers.v1', 'foundation.view.v1']}
PROVIDERS_EXPORT = 'gui_web_providers_v1'
IMPORTS = {
    'appended_browser_bootstrap.mjs': ('browser_embedding.mjs', 'wasm_transport.mjs'),
    'browser_embedding.mjs': package_wasm.IMPORTS['browser_embedding.mjs'],
    'browser_client.mjs': package_wasm.IMPORTS['browser_client.mjs'],
    'browser_services.mjs': ('file_services.mjs',),
    **browser_bundle.CHILD_GRAPH,
}
ASSETS = tuple(sorted(set(IMPORTS) | {dependency for values in IMPORTS.values() for dependency in values} |
                      {'browser_lifecycle.mjs', 'wasm_transport.mjs', 'wasm_worker.mjs',
                       'appended_wasm_worker.mjs', 'style.css', 'gui_appended_web_wasm.js',
                       'gui_appended_web_wasm.wasm'}))
OUTER_STYLE = ('html,body{margin:0;width:100%;height:100%}#application{width:100%;height:calc(100% - 3rem)}'
               '#application>iframe{display:block;width:100%;height:100%;border:0}'
               '#status{margin:.5rem;font:14px sans-serif}details{font:12px sans-serif}pre{white-space:pre-wrap}')
OPEN = ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta http-equiv="Content-Security-Policy" content="' + escape(CSP, quote=True) + '">'
        '<title>Binary application kernel</title><style>')
MIDDLE = ('</style></head><body><main id="application"></main>'
          '<p id="status" role="status">Starting binary application…</p>'
          '<script type="application/octet-stream" id="foundation-appended-kernel">')
BOOT_OPEN = '</script><script type="module" id="foundation-appended-bootstrap">'
BOOT_CLOSE = '</script>' + container.HTML_MARKER.decode('ascii')


def _js(value):
    # A JavaScript string literal inside an HTML script must not expose an HTML
    # terminator, even when the literal is only data to JavaScript's parser.
    return json.dumps(value, ensure_ascii=True, separators=(',', ':')).replace('<', r'\u003c')


def bootstrap_source():
    return '''
const raw=document.querySelector('#foundation-appended-kernel').textContent;
const own=document.querySelector('#foundation-appended-bootstrap').textContent;
const prefix=new TextEncoder().encode(@@OPEN@@+document.querySelector('style').textContent+@@MIDDLE@@+raw+@@BOOT_OPEN@@+own+@@BOOT_CLOSE@@);
const unbase64=encoded=>{const raw=atob(encoded),bytes=new Uint8Array(raw.length);for(let n=0;n<raw.length;n++)bytes[n]=raw.charCodeAt(n);return bytes;};
const kernel=JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(unbase64(raw)));
const text=name=>new TextDecoder('utf-8',{fatal:true}).decode(unbase64(kernel.assets[name]));
const urls=[],modules=new Map(),dependencies=GRAPH;
const local=source=>{const url=URL.createObjectURL(new Blob([source],{type:'text/javascript'}));urls.push(url);return url;};
const moduleURL=name=>{
  if(modules.has(name))return modules.get(name);
  let source=text(name);
  for(const dependency of dependencies[name]||[]){const target=JSON.stringify(moduleURL(dependency));source=source.replace("'./"+dependency+"'",target).replace('"./'+dependency+'"',target);}
  const url=local(source);modules.set(name,url);return url;
};
try{
  const {startAppendedBrowser}=await import(moduleURL('appended_browser_bootstrap.mjs'));
  await startAppendedBrowser({prefix,kernel,workerSource:new TextDecoder().decode(unbase64(CLASSIC_WORKER))});
}catch(error){document.querySelector('#status').textContent='Could not start binary application: '+String(error.message||error).slice(0,4096);}
finally{for(const url of urls)URL.revokeObjectURL(url);}
'''.replace('@@OPEN@@', _js(OPEN)).replace('@@MIDDLE@@', _js(MIDDLE)).replace(
        '@@BOOT_OPEN@@', _js(BOOT_OPEN)).replace('@@BOOT_CLOSE@@', _js(BOOT_CLOSE)).replace('GRAPH', _js(IMPORTS))


def classic_worker(blobs):
    core = package_wasm.classic_worker_source(blobs['wasm_worker.mjs'])
    core_install = "if(typeof WorkerGlobalScope!=='undefined'&&globalThis instanceof WorkerGlobalScope)installWasmWorker(globalThis);"
    if core.count(core_install) != 1:
        raise ValueError('Reviewed generic Worker installation changed')
    source = blobs['appended_wasm_worker.mjs'].decode('utf-8')
    imported = "import {installWasmWorker} from './wasm_worker.mjs';"
    declaration = 'export function installAppendedWasmWorker(scope,loadModule)'
    if source.count(imported) != 1 or not source.startswith(imported) or source.count(declaration) != 1:
        raise ValueError('Reviewed appended Worker entry changed')
    # Accept only the one static edge, one function export and one dynamic
    # factory import. This is not a general source-to-source module bundler.
    expected = [(source.index('import '), 'import'), (source.index('export '), 'export'),
                (source.index('import(url)'), 'import')]
    if browser_bundle._keywords(source) != expected:
        raise ValueError('Unexpected appended Worker module syntax')
    return core.replace(core_install, '') + '\n' + source.replace(imported, '', 1).replace('export ', '', 1)


def _provider_export(data):
    """Find the private function export in the bounded compiled kernel.

    Inspect the actual export section rather than searching arbitrary/custom
    bytes for its name. This is capability sanity only, not module validation,
    a guest-profile change, execution, or source-to-binary reconstruction proof.
    """
    if data[:8] != b'\0asm\1\0\0\0':
        raise ValueError('Invalid compiled browser kernel Wasm header')
    position = 8
    def take(size, end):
        nonlocal position
        if size > end - position:
            raise ValueError('Truncated compiled browser kernel section')
        result = data[position:position + size]
        position += size
        return result
    def u32(end):
        value = 0
        for shift in range(0, 35, 7):
            part = take(1, end)[0]
            if shift == 28 and part > 15:
                raise ValueError('Invalid compiled browser kernel u32 LEB')
            value |= (part & 127) << shift
            if not part & 128:
                return value
        raise ValueError('Unterminated compiled browser kernel u32 LEB')
    found, seen_exports = False, False
    while position < len(data):
        section, size = take(1, len(data))[0], u32(len(data))
        if size > len(data) - position:
            raise ValueError('Truncated compiled browser kernel section')
        end = position + size
        if section != 7:
            position = end
            continue
        if seen_exports:
            raise ValueError('Duplicate compiled browser kernel export section')
        seen_exports = True
        count = u32(end)
        if count > 65536:
            raise ValueError('Compiled browser kernel export count exceeds limit')
        names = set()
        for _ in range(count):
            raw = take(u32(end), end)
            try:
                name = raw.decode('utf-8')
            except UnicodeError as error:
                raise ValueError('Invalid compiled browser kernel export name') from error
            kind = take(1, end)[0]
            u32(end)  # Export index; the actual compiler/runtime owns typing.
            if name in names or kind > 4:
                raise ValueError('Duplicate name or unknown compiled browser kernel export kind')
            names.add(name)
            if name == PROVIDERS_EXPORT:
                if kind != 0:
                    raise ValueError('Provider marker must be a function export')
                found = True
        if position != end:
            raise ValueError('Unexpected compiled browser kernel export bytes')
    return found


def validate_assets(blobs, *, providers=False):
    if set(blobs) != set(ASSETS) or sum(map(len, blobs.values())) > package_wasm.MAX_TOTAL:
        raise ValueError('Invalid appended browser asset inventory or size')
    if not blobs['gui_appended_web_wasm.wasm'].startswith(b'\0asm\1\0\0\0'):
        raise ValueError('Invalid compiled browser kernel Wasm header')
    if len(blobs['gui_appended_web_wasm.js']) > 16 * 1024 * 1024:
        raise ValueError('Compiled browser factory exceeds Worker limit')
    if providers and not _provider_export(blobs['gui_appended_web_wasm.wasm']):
        raise ValueError('Provider policy requires compiled kernel function export ' + PROVIDERS_EXPORT)
    for name, data in blobs.items():
        if len(data) > package_wasm.MAX_ASSET:
            raise ValueError('Appended browser asset exceeds limit')
        if name != 'gui_appended_web_wasm.wasm':
            data.decode('utf-8')
    metadata = package_wasm.child_metadata(blobs)
    for name, dependencies in IMPORTS.items():
        discovered = re.findall(r"['\"]\./([A-Za-z0-9_.-]+\.mjs)['\"]", blobs[name].decode('utf-8'))
        if sorted(discovered) != sorted(dependencies):
            raise ValueError('Reviewed appended module dependency changed: ' + name)
    classic_worker(blobs)
    return metadata


def make_prefix(blobs, notices, source_sha256, kernel_inputs_sha256, sdk_identity=None, *, providers=False):
    child = validate_assets(blobs, providers=providers)
    policy = PROVIDERS_POLICY if providers else POLICY
    if not notices or sum(map(len, notices.values())) > 4 * 1024 * 1024:
        raise ValueError('Bounded applicable notices are required')
    for name, data in notices.items():
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', name):
            raise ValueError('Invalid notice label')
        data.decode('utf-8')
    for value in (source_sha256, kernel_inputs_sha256):
        if not isinstance(value, str) or not re.fullmatch(r'[0-9a-f]{64}', value):
            raise ValueError('Complete source identities are required')
    metadata = {'schema_version': 1, 'kind': KIND, 'policy': policy,
                'source_observed_at_package_sha256': source_sha256,
                'kernel_inputs_sha256': kernel_inputs_sha256,
                'assets': {name: base64.b64encode(data).decode('ascii') for name, data in sorted(blobs.items())},
                'inputs': {name: container.digest(data) for name, data in sorted(blobs.items())},
                'notices': {name: base64.b64encode(data).decode('ascii') for name, data in sorted(notices.items())},
                'sdk': sdk_identity}
    encoded = base64.b64encode(container.canonical_json(metadata)).decode('ascii')
    worker = base64.b64encode(classic_worker(blobs).encode('utf-8')).decode('ascii')
    bootstrap = bootstrap_source().replace('CLASSIC_WORKER', _js(worker))
    prefix = (OPEN + OUTER_STYLE + MIDDLE + encoded + BOOT_OPEN + bootstrap + BOOT_CLOSE).encode('utf-8')
    container._html_shell(prefix)
    return prefix, metadata, child


def package(assets, output, notice_paths, module_dir=None, sdk=None, source_root=None, *, providers=False):
    from appended_policy import kernel_source_tree
    from source_identity import ignored_source_path, source_tree
    if source_root is None:
        raise ValueError('Explicit source root is required for a retained browser kernel')
    assets, output, source_root = Path(assets), Path(output), Path(source_root).resolve(strict=True)
    destination = output.resolve(strict=False)
    if source_root in destination.parents and not ignored_source_path(destination.relative_to(source_root).as_posix() + '/'):
        raise ValueError('Browser kernel outputs must be outside source inputs or under ignored build/ or .agent-work/')
    source_before, inputs_before = source_tree(source_root), kernel_source_tree(source_root)
    notice_paths, notices, sdk_identity, snapshots = list(notice_paths), {}, None, []
    if sdk is not None:
        snapshots.append(container._snapshot(Path(sdk) / 'sdk.json', container.MAX_INDEX))
        extra, sdk_identity = package_wasm.sdk_notices(sdk)
        notice_paths.extend(extra)
    for item in notice_paths:
        label, raw = str(item).split('=', 1) if '=' in str(item) else (Path(item).name, str(item))
        if label in notices:
            raise ValueError('Duplicate notice label')
        saved = container._snapshot(Path(raw), 4 * 1024 * 1024)
        snapshots.append(saved)
        notices[label] = saved.content
    blobs = {}
    for name in ASSETS:
        saved = container._snapshot((Path(module_dir) if module_dir and name.startswith('gui_appended_web_wasm.') else assets) / name, package_wasm.MAX_ASSET)
        snapshots.append(saved)
        blobs[name] = saved.content
    prefix, metadata, child = make_prefix(blobs, notices, source_before['tree_sha256'], inputs_before['tree_sha256'], sdk_identity, providers=providers)
    policy = metadata['policy']
    descriptor = {'schema_version': 1, 'kind': 'foundation-kernel', 'carrier': 'html', 'profile': 'binary',
                  'append_format': 1, **policy, 'boundary_offset': None,
                  'executable': {'length': len(prefix), 'sha256': container.digest(prefix)},
                  'kernel_inputs': inputs_before,
                  'provenance': {'kind': KIND, 'qualification': 'unqualified-development',
                                 'runtime': 'dedicated-worker', 'renderer_modes': ['isolated'], 'child': child,
                                 'csp': CSP, 'inputs': metadata['inputs'],
                                 'source_observed_at_package_sha256': source_before['tree_sha256'], 'sdk': sdk_identity,
                                 'source_binding': 'observed packaging inputs; not source-to-binary certification'}}
    container.validate_descriptor(descriptor)
    container.parse_artifact(prefix, descriptor, expected_mode='neither')
    if source_tree(source_root) != source_before or kernel_source_tree(source_root) != inputs_before:
        raise ValueError('Source inputs changed during browser kernel packaging')
    for saved in snapshots:
        container._recheck(saved)
    # A kernel producer must not overwrite a previously retained prefix. This
    # directory reservation and each file publication fail if another writer
    # arrived first. An interrupted producer leaves evidence for inspection.
    output.parent.mkdir(parents=True, exist_ok=True)
    container._ordinary_path(output.parent, directory=True)
    output.mkdir(exist_ok=False)
    contents = {HTML_NAME: prefix, DESCRIPTOR_NAME: container.canonical_json(descriptor)}
    for name, content in contents.items():
        container._write_new(output / name, content, snapshots=snapshots)
    container._write_new(output / 'manifest.sha256', ''.join(container.digest(contents[name]) + '  ' + name + '\n' for name in sorted(contents)).encode('ascii'), snapshots=snapshots)
    verify(output)
    return descriptor


def _verify_retained_inputs(inputs):
    """Check historical inventory integrity without granting reuse eligibility.

    The general retained-source selector deliberately rejects projection v1.
    Immutable old browser prefixes can still be verified against their original
    complete inventory and descriptor pin; this read-only exception does not
    produce v1 descriptors or reinterpret the old projection as current policy.
    """
    from appended_policy import CONFIGURATION, repository_path, validate_kernel_inputs
    if not isinstance(inputs, dict) or inputs.get('projection') != 'foundation-appended-kernel-v1':
        validate_kernel_inputs(inputs)
        return False
    if (set(inputs) != {'schema_version', 'projection', 'tree_sha256', 'files', 'executables'} or
            type(inputs['schema_version']) is not int or inputs['schema_version'] != 1):
        raise ValueError('Invalid historical browser kernel input inventory')
    files, executables = inputs['files'], inputs['executables']
    if (not isinstance(files, dict) or not files or CONFIGURATION not in files or
            any(not repository_path(name) or not isinstance(value, str) or not re.fullmatch(r'[0-9a-f]{64}', value)
                for name, value in files.items()) or
            not isinstance(executables, list) or any(not isinstance(name, str) for name in executables) or
            executables != sorted(set(executables)) or not set(executables) <= set(files)):
        raise ValueError('Invalid historical browser kernel input inventory')
    from dependency_archive import encoded
    if container.digest(encoded({'files': files, 'executables': executables})) != inputs['tree_sha256']:
        raise ValueError('Historical browser kernel input identity mismatch')
    return True


def verify(output, descriptor_sha256=None):
    output = Path(output)
    if output.is_symlink() or {path.name for path in output.iterdir()} != {HTML_NAME, DESCRIPTOR_NAME, 'manifest.sha256'}:
        raise ValueError('Incomplete or unexpected browser kernel inventory')
    raw = package_wasm.read_file(output / DESCRIPTOR_NAME, container.MAX_INDEX)
    if descriptor_sha256 is not None and container.digest(raw) != descriptor_sha256:
        raise ValueError('Browser kernel descriptor differs from independent pin')
    descriptor = container.validate_descriptor(container.parse_json(raw, 'browser kernel descriptor'))
    historical = _verify_retained_inputs(descriptor.get('kernel_inputs'))
    prefix = package_wasm.read_file(output / HTML_NAME, container.MAX_KERNEL)
    artifact = container.parse_artifact(prefix, descriptor, expected_mode='neither')
    if descriptor['carrier'] != 'html' or descriptor['profile'] != 'binary' or descriptor['provenance'].get('kind') != KIND:
        raise ValueError('Incorrect binary browser kernel descriptor')
    payloads = re.findall(rb'<script type="application/octet-stream" id="foundation-appended-kernel">([A-Za-z0-9+/=]+)</script>', artifact.prefix)
    if len(payloads) != 1:
        raise ValueError('Missing canonical browser kernel asset block')
    encoded = base64.b64decode(payloads[0], validate=True)
    if base64.b64encode(encoded) != payloads[0]:
        raise ValueError('Noncanonical browser kernel asset base64')
    metadata = container.parse_json(encoded, 'browser kernel assets')
    expected_keys = {'schema_version', 'kind', 'policy', 'source_observed_at_package_sha256', 'kernel_inputs_sha256', 'assets', 'inputs', 'notices', 'sdk'}
    if (set(metadata) != expected_keys or metadata['schema_version'] != 1 or metadata['kind'] != KIND or
            metadata['policy'] not in (POLICY, PROVIDERS_POLICY)):
        raise ValueError('Unexpected browser kernel asset metadata')
    policy = metadata['policy']
    if historical and policy != POLICY:
        raise ValueError('Historical browser inventory cannot advertise the new provider policy')
    blobs = {name: base64.b64decode(value, validate=True) for name, value in metadata['assets'].items()}
    notices = {name: base64.b64decode(value, validate=True) for name, value in metadata['notices'].items()}
    provenance = descriptor['provenance']
    if (set(provenance) != {'kind', 'qualification', 'runtime', 'renderer_modes', 'child', 'csp', 'inputs',
                            'source_observed_at_package_sha256', 'sdk', 'source_binding'} or
            provenance.get('qualification') != 'unqualified-development' or provenance.get('runtime') != 'dedicated-worker' or
            provenance.get('source_binding') != 'observed packaging inputs; not source-to-binary certification'):
        raise ValueError('Unexpected browser kernel producer provenance')
    rebuilt, checked, child = make_prefix(blobs, notices, metadata['source_observed_at_package_sha256'], metadata['kernel_inputs_sha256'], metadata['sdk'], providers=policy == PROVIDERS_POLICY)
    if (rebuilt != prefix or checked != metadata or descriptor['abi'] != policy['abi'] or descriptor['services'] != policy['services'] or
            descriptor['capabilities'] != policy['capabilities'] or provenance.get('child') != child or provenance.get('csp') != CSP or
            provenance.get('renderer_modes') != ['isolated'] or provenance.get('inputs') != metadata['inputs'] or
            provenance.get('source_observed_at_package_sha256') != metadata['source_observed_at_package_sha256'] or
            descriptor.get('kernel_inputs', {}).get('tree_sha256') != metadata['kernel_inputs_sha256'] or provenance.get('sdk') != metadata['sdk']):
        raise ValueError('Browser kernel differs from canonical retained inputs')
    expected = ''.join(container.digest(package_wasm.read_file(output / name, container.MAX_KERNEL)) + '  ' + name + '\n' for name in sorted((HTML_NAME, DESCRIPTOR_NAME)))
    if package_wasm.read_file(output / 'manifest.sha256').decode('ascii') != expected:
        raise ValueError('Browser kernel checksum mismatch')
    return descriptor


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--assets', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--module-dir', type=Path)
    parser.add_argument('--source-root', type=Path)
    parser.add_argument('--notice', action='append', default=[])
    parser.add_argument('--sdk', type=Path)
    parser.add_argument('--providers', action='store_true', help='Advertise module providers; requires the compiled private provider marker')
    parser.add_argument('--verify', action='store_true')
    parser.add_argument('--descriptor-sha256')
    args = parser.parse_args(argv)
    if args.verify:
        if args.providers:
            parser.error('--providers selects initial production; verification reads the retained policy')
        verify(args.output, args.descriptor_sha256)
    elif args.assets:
        package(args.assets, args.output, args.notice, args.module_dir, args.sdk, args.source_root, providers=args.providers)
    else:
        parser.error('--assets is required for browser kernel production')


if __name__ == '__main__':
    main()
