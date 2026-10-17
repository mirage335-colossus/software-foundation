#!/usr/bin/env python3
"""Assemble the separate reviewed surface-renderer graph as inert parent data.

The ordinary binary renderer graph remains owned by browser_bundle. This module
uses its lexical assembler with a fixed, additive surface graph; no application
script, engine factory or transport belongs in the renderer document.
"""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import stat

import browser_bundle

CHILD_PROTOCOL = browser_bundle.CHILD_PROTOCOL
CHILD_SANDBOX = browser_bundle.CHILD_SANDBOX
BUNDLE_NAME = 'renderer_surface_child_bundle.mjs'
CHILD_MODULES = (
    'browser_limits.mjs', 'browser_presenter.mjs', 'browser_surface_protocol.mjs',
    'browser_surface.mjs', 'renderer_channel.mjs', 'renderer_surface_dom.mjs',
    'renderer_surface_frame.mjs',
)
CHILD_GRAPH = {
    'browser_limits.mjs': (),
    'browser_presenter.mjs': (),
    'browser_surface_protocol.mjs': (),
    'browser_surface.mjs': ('browser_surface_protocol.mjs',),
    'renderer_channel.mjs': ('browser_limits.mjs',),
    'renderer_surface_dom.mjs': ('browser_limits.mjs', 'browser_surface.mjs'),
    'renderer_surface_frame.mjs': (
        'renderer_surface_dom.mjs', 'browser_surface_protocol.mjs',
        'browser_presenter.mjs', 'renderer_channel.mjs', 'browser_limits.mjs'),
}
CHILD_EXPORTS = {
    'browser_limits.mjs': browser_bundle.CHILD_EXPORTS['browser_limits.mjs'],
    'browser_presenter.mjs': ('createBrowserPresenter',),
    'browser_surface_protocol.mjs': ('validateSurfaceState', 'validateSurfaceOperation'),
    'browser_surface.mjs': ('BASIC_SURFACE_FEATURES', 'captureSurfaceKey',
                            'surfaceScalarMap', 'createBrowserSurface'),
    'renderer_channel.mjs': browser_bundle.CHILD_EXPORTS['renderer_channel.mjs'],
    'renderer_surface_dom.mjs': ('identity', 'byteOffset', 'utf16Offset', 'Renderer'),
    'renderer_surface_frame.mjs': ('startRendererFrame',),
}
CHILD_FIELDS = ('CHILD_SCRIPT', 'CHILD_SCRIPT_SHA256', 'CHILD_CSP',
                'CHILD_SANDBOX', 'CHILD_PROTOCOL', 'CHILD_STYLE')
SOURCE_NAMES = CHILD_MODULES + ('style.css',)
MAX_INPUT_BYTES = 64 * 1024 * 1024
MAX_BUNDLE_BYTES = 64 * 1024 * 1024
DATA_HEADER = '// Generated renderer data; never evaluate this script in the parent.'


def _blobs(blobs, names):
    if type(blobs) is not dict or set(blobs) != set(names):
        raise ValueError('Surface child bundle inventory differs')
    if any(type(data) is not bytes or len(data) > (MAX_BUNDLE_BYTES if name == BUNDLE_NAME else MAX_INPUT_BYTES)
           for name, data in blobs.items()):
        raise ValueError('Surface child inputs must be bounded byte strings')


def _metadata(metadata):
    if (type(metadata) is not dict or set(metadata) != set(CHILD_FIELDS)
            or any(type(metadata[name]) is not str for name in CHILD_FIELDS)):
        raise ValueError('Surface child data fields differ')
    script, style = metadata['CHILD_SCRIPT'], metadata['CHILD_STYLE']
    if (any(value in script.lower() for value in ('</script', '<!--', '-->')) or '\x00' in script or '\r' in script
            or '</style' in style.lower() or '</script' in style.lower() or '\x00' in style):
        raise ValueError('Unsafe surface child data terminator')
    expected_hash = base64.b64encode(hashlib.sha256(script.encode('utf-8')).digest()).decode('ascii')
    if (metadata['CHILD_SCRIPT_SHA256'] != expected_hash
            or metadata['CHILD_CSP'] != browser_bundle.child_csp(script)
            or metadata['CHILD_SANDBOX'] != CHILD_SANDBOX
            or metadata['CHILD_PROTOCOL'] != CHILD_PROTOCOL):
        raise ValueError('Surface child script policy mismatch')
    return {name: metadata[name] for name in CHILD_FIELDS}


def build(blobs):
    """Return six consumer fields for exactly the reviewed source graph and CSS."""
    _blobs(blobs, SOURCE_NAMES)
    metadata = browser_bundle.assemble(blobs, graph=CHILD_GRAPH, exports=CHILD_EXPORTS)
    result = _metadata({name: metadata[name] for name in CHILD_FIELDS})
    module_bytes(result)
    return result


def module_bytes(metadata):
    """Encode six canonical JSON string exports without executing their contents."""
    data = browser_bundle.module_bytes(_metadata(metadata))
    if len(data) > MAX_BUNDLE_BYTES:
        raise ValueError('Generated surface child bundle exceeds its asset bound')
    return data


def parse_module(data):
    """Check canonical pure data and its policy; source binding uses verify_assets."""
    if type(data) is not bytes or len(data) > MAX_BUNDLE_BYTES:
        raise ValueError('Surface child module must be bounded bytes')
    lines = data.decode('utf-8').splitlines()
    if len(lines) != len(CHILD_FIELDS) + 1 or lines[0] != DATA_HEADER:
        raise ValueError('Invalid generated surface child data module')
    metadata = {}
    for name, line in zip(CHILD_FIELDS, lines[1:]):
        prefix = 'export const ' + name + '='
        if not line.startswith(prefix) or not line.endswith(';'):
            raise ValueError('Invalid generated surface child data export')
        metadata[name] = json.loads(line[len(prefix):-1])
    checked = _metadata(metadata)
    if module_bytes(checked) != data:
        raise ValueError('Noncanonical generated surface child data module')
    return checked


def verify_assets(blobs):
    """Reconstruct and compare the generated module against its exact sources."""
    _blobs(blobs, SOURCE_NAMES + (BUNDLE_NAME,))
    metadata = build({name: blobs[name] for name in SOURCE_NAMES})
    if blobs[BUNDLE_NAME] != module_bytes(metadata):
        raise ValueError('Generated surface child bundle differs from source graph')
    return metadata


def _ordinary_info(path):
    info = path.lstat()
    attributes = getattr(info, 'st_file_attributes', None)
    if (stat.S_ISLNK(info.st_mode) or (attributes is not None and attributes & 0x400)
            or (os.name == 'nt' and attributes is None)):
        raise ValueError('Surface child paths reject links and reparse points')
    return info


def _ordinary_parents(path):
    for parent in reversed(path.absolute().parents):
        try:
            info = _ordinary_info(parent)
        except FileNotFoundError:
            continue
        if not stat.S_ISDIR(info.st_mode):
            raise ValueError('Surface child paths require ordinary directory ancestors')


def _bounded_read(path, limit):
    with path.open('rb') as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError('Surface child file exceeds its asset bound: ' + str(path))
    return data


def generate(assets, output=None):
    """Generate maintained build output, preserving an identical output's mtime."""
    root = Path(assets)
    _ordinary_parents(root)
    if not root.exists() or not stat.S_ISDIR(_ordinary_info(root).st_mode):
        raise ValueError('Surface child assets must be an ordinary directory')
    blobs = {}
    input_identities = set()
    for name in SOURCE_NAMES:
        path = root / name
        if not path.exists():
            raise ValueError('Expected ordinary bounded surface child input: ' + str(path))
        info = _ordinary_info(path)
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_INPUT_BYTES:
            raise ValueError('Expected ordinary bounded surface child input: ' + str(path))
        blobs[name] = _bounded_read(path, MAX_INPUT_BYTES)
        input_identities.add((info.st_dev, info.st_ino))
    data = module_bytes(build(blobs))
    output = root / BUNDLE_NAME if output is None else Path(output)
    _ordinary_parents(output)
    try:
        output_info = _ordinary_info(output)
    except FileNotFoundError:
        output_info = None
    if output_info is not None and (not stat.S_ISREG(output_info.st_mode)
                                    or output_info.st_size > MAX_BUNDLE_BYTES):
        raise ValueError('Surface child bundle output must be ordinary')
    if output.resolve() in {(root / name).resolve() for name in SOURCE_NAMES}:
        raise ValueError('Surface child output must not replace an input')
    if output_info is not None:
        if (output_info.st_dev, output_info.st_ino) in input_identities:
            raise ValueError('Surface child output must not alias an input')
    previous = None if output_info is None else _bounded_read(output, MAX_BUNDLE_BYTES)
    output.parent.mkdir(parents=True, exist_ok=True)
    if previous != data:
        output.write_bytes(data)
    return data


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--assets', required=True, type=Path)
    parser.add_argument('--output', type=Path)
    arguments = parser.parse_args(argv)
    generate(arguments.assets, arguments.output)


if __name__ == '__main__':
    main()
