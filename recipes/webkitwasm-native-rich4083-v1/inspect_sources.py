#!/usr/bin/env python3
"""Inspect the finite native source candidate; never build or certify an engine."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat

RECIPE = 'recipes/webkitwasm-native-rich4083-v1'
FIELDS = {'schema_version', 'kind', 'scope', 'profile', 'suppliers', 'provenance',
          'requirements', 'limits', 'inputs'}
INPUT_FIELDS = {'tracked_path', 'sha256', 'bytes', 'mode', 'role', 'origin'}
REQUIREMENTS = ['closed-retained-native-actions-source-recipe-and-provider-build',
                'target-qualified-native-dependency-baseline',
                'native-compile-link-runtime']
LIMITS = {'maximum_entries': 256, 'maximum_file_bytes': 8388608,
          'maximum_total_bytes': 33554432}


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON key: ' + key)
        result[key] = value
    return result


def _path(value):
    if type(value) is not str or not value or len(value) > 4096:
        raise ValueError('Invalid native source path')
    if any(ord(char) < 32 or ord(char) > 126 or char in '\\:< >"|?*' for char in value):
        raise ValueError('Nonportable native source path')
    for part in value.split('/'):
        if not part or part in ('.', '..') or part.endswith(('.', ' ')):
            raise ValueError('Invalid native source path component')
        stem = part.split('.', 1)[0].lower()
        if stem in {'con', 'prn', 'aux', 'nul', 'conin$', 'conout$',
                    *('com' + str(i) for i in range(1, 10)),
                    *('lpt' + str(i) for i in range(1, 10))}:
            raise ValueError('Reserved native source path component')
    return value


def _digest(value):
    if type(value) is not str or not re.fullmatch('[0-9a-f]{64}', value):
        raise ValueError('Invalid native source SHA256')
    return value


def _read(root, relative, maximum):
    """Reject links at each named ancestor and detect changes during a read."""
    relative = _path(relative)
    current = root
    for index, part in enumerate(relative.split('/')):
        current = current / part
        entry = current.lstat()
        if index + 1 < len(relative.split('/')):
            if not stat.S_ISDIR(entry.st_mode):
                raise ValueError('Native source ancestor is not a directory: ' + relative)
        elif not stat.S_ISREG(entry.st_mode):
            raise ValueError('Native source is not a regular file: ' + relative)
    before = current.lstat()
    if before.st_size > maximum:
        raise ValueError('Native source exceeds its read budget: ' + relative)
    descriptor = os.open(current, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
    with os.fdopen(descriptor, 'rb') as stream:
        opened = os.fstat(stream.fileno())
        if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
            raise ValueError('Native source identity changed before read: ' + relative)
        raw = stream.read(maximum + 1)
    after = current.lstat()
    identity = lambda item: (item.st_dev, item.st_ino, item.st_size,
                             item.st_mtime_ns, stat.S_IMODE(item.st_mode))
    if len(raw) > maximum or identity(before) != identity(after):
        raise ValueError('Native source changed during read: ' + relative)
    return raw, stat.S_IMODE(before.st_mode)


# Explicit source-only successor; final native source facts stay unbound until release.
COMPOSITION_SOURCE_KIND = 'foundation-native-engine-actions-composition-undo-source-inputs-v1'
COMPOSITION_PROFILE_KIND = 'foundation-native-engine-prototype-composition-undo-profile-v1'
COMPOSITION_BRIDGE = 'source/wrapper/src/embedder/BibEngineProviderCompositionUndo.h'
COMPOSITION_SOURCE_FACTS = {'source/document-provider/editor/BibNativeEditorBackend.cpp': {'sha256': 'd14dab28100d3689d9a04aa4a81290b50cf24cd3e00a34b2f8402d9eeca9da60', 'bytes': 61375, 'mode': 420}, 'source/wrapper/src/embedder/main.cpp': {'sha256': '3c2c7beb2b582ab91fb8174aa7d5f6022ce1a4b29ec66918674f9f13fadd88ac', 'bytes': 48346, 'mode': 420}, 'source/wrapper/src/embedder/BibPageClients.h': {'sha256': '6e77e9b1b47cc5e4e3d2a5dcd7600ea959c4b22eb95c763165c4ccc3c5d28a43', 'bytes': 29858, 'mode': 420}, 'source/wrapper/src/embedder/BibUndoHistory.h': {'sha256': 'f6ca9055367085abe855a19b0d047034279dff1beb7dc44c8c2ab78001d602bb', 'bytes': 9317, 'mode': 420}, 'source/wrapper/src/embedder/BibEngineProviderCompositionUndo.h': {'sha256': '1572b86481c93b9568c781ababc9f6645f505a038704f91236192e31a4208118', 'bytes': 592, 'mode': 420}}
COMPOSITION_NAMESPACE_SHA256 = '786fd3a2c417370bc0dae92bae552c5c7a80ba0adf6dfa67ef88ad5ffcf15812'
COMPOSITION_RETAINED_SHA256 = '436136c1f85dfa38608f6852bce7192cb8d89e8e03d84e85e00d6a95322d8af8'
COMPOSITION_PREDECESSORS = {'source/document-provider/editor/BibNativeEditorBackend.cpp': {'current_sha256': '5fe5f78c031cb50b83b40aed998a02a765045fdd111dba1ea7f76950f8ab1815', 'record_sha256': '936d83294fe9561a8822c1d49c7ea35768125aa5b20dc4d069c662059327181d'}, 'source/wrapper/src/embedder/BibPageClients.h': {'current_sha256': 'cd5775db97976fc01d8f457474d41cbafd3ae2895efbd0a3dff49bbfe2e8f3d2', 'record_sha256': '9b8de546a2822ac27dc540bb14eb7e931af06fde1048b1793a96611ce5c01ffe'}, 'source/wrapper/src/embedder/BibUndoHistory.h': {'current_sha256': 'eda850a3b35353dc47be20f85fe16bff55058aaf83610ee0c96a7ffda5c369f2', 'record_sha256': '72ff0df8f1a13f52d18c06483492eb305f4884750eea14af7dd26c3428e4ee2d'}, 'source/wrapper/src/embedder/main.cpp': {'current_sha256': '4cb8131b86f6bf1ede303053b7aa1752fab16dd66fe8b0271f97d256e0cd137b', 'record_sha256': '590cea1e6c33f40e7e00d2e6d8a7a7727da0436130b2537fa6fa3484a104fd74'}}


def composition_catalogue_counts(value):
    """Admit only the exact released one-header successor, never a count range."""
    if type(COMPOSITION_SOURCE_FACTS) is not dict:
        raise ValueError('Composition source successor facts remain unbound')
    fields = {'schema_version', 'kind', 'scope', 'profile', 'suppliers', 'provenance', 'requirements', 'limits', 'inputs'}
    if (type(value) is not dict or set(value) != fields or type(value['schema_version']) is not int
            or value['schema_version'] != 1 or value['kind'] != COMPOSITION_SOURCE_KIND
            or value['scope'] != 'native-actions-source-candidate-only' or value['profile'] != 'actions'):
        raise ValueError('Exact composition source successor version required')
    entries = value['inputs']
    known = set(COMPOSITION_PREDECESSORS) | {COMPOSITION_BRIDGE}
    if type(entries) is not dict or len(entries) != 198 or set(COMPOSITION_SOURCE_FACTS) != known:
        raise ValueError('Composition successor requires exact198 entries/five source pins')
    canonical = lambda data: json.dumps(data, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode('ascii')
    hashed = lambda data: hashlib.sha256(canonical(data)).hexdigest()
    if hashed(sorted(entries)) != COMPOSITION_NAMESPACE_SHA256:
        raise ValueError('Composition source successor namespace differs')
    retained = {k: v for k, v in entries.items() if k.startswith('source/') and k not in known}
    if len(retained) != 153 or hashed(retained) != COMPOSITION_RETAINED_SHA256:
        raise ValueError('Unchanged153 native source rows differ')
    for logical in known:
        item = entries[logical]
        expected = COMPOSITION_SOURCE_FACTS[logical]
        if (type(expected) is not dict or set(expected) != {'sha256', 'bytes', 'mode'}
                or type(expected['sha256']) is not str or not re.fullmatch('[0-9a-f]{64}', expected['sha256'])
                or type(expected['bytes']) is not int or not 0 < expected['bytes'] <= 8388608
                or type(expected['mode']) is not int or expected['mode'] != 420):
            raise ValueError('Final composition source pins required')
        if (type(item) is not dict or set(item) != {'tracked_path', 'sha256', 'bytes', 'mode', 'role', 'origin'}
                or item['tracked_path'] != RECIPE + '/' + logical or item['role'] != 'source'
                or any(type(item[k]) is not type(expected[k]) or item[k] != expected[k] for k in expected)):
            raise ValueError('Released composition source fact differs')
        origin = item['origin']
        if type(origin) is not dict or set(origin) != {'kind', 'record'} or type(origin['record']) is not dict:
            raise ValueError('Explicit native source successor record required')
        record = origin['record']
        if type(record.get('after_bytes')) is not int or type(record.get('bytes')) is not int:
            raise ValueError('Native source record byte counts require strict integers')
        if logical == COMPOSITION_BRIDGE:
            wanted = {'action': 'new-private-source-header', 'selection': 'source-only-addition',
                'origin': 'reviewed-source-only-composition-undo-private-bridge', 'origin_path': item['tracked_path'],
                'source': logical, 'preimage_sha256': None, 'sha256': expected['sha256'], 'bytes': expected['bytes'],
                'after_sha256': expected['sha256'], 'after_bytes': expected['bytes'], 'mode': expected['mode']}
            if origin['kind'] != 'reviewed-source-only-composition-undo-private-bridge' or record != wanted:
                raise ValueError('Bridge cannot claim historical compiled/capsule origin')
        else:
            if origin['kind'] != 'mapped-native-actions-runtime':
                raise ValueError('Native adapted predecessor origin differs')
            successor = record.get('successor')
            if type(successor) is not dict or set(successor) != {'kind', 'correction', 'sha256', 'source_path', 'source_only', 'supersedes'}:
                raise ValueError('Exact composition successor lineage required')
            prior = successor['supersedes']
            expected_prior = COMPOSITION_PREDECESSORS[logical]
            if (type(prior) is not dict or set(prior) != {'origin', 'sha256', 'tracked_path'}
                    or prior['sha256'] != expected_prior['current_sha256'] or prior['tracked_path'] != item['tracked_path']
                    or hashed(prior['origin']) != expected_prior['record_sha256']):
                raise ValueError('Native original/adapted predecessor was restamped')
            old = prior['origin']
            allowed = {'action', 'selection', 'after_sha256', 'after_bytes', 'successor'}
            if (set(record) != set(old) | allowed
                    or any(record.get(k) != v for k, v in old.items() if k not in allowed)
                    or record['after_sha256'] != expected['sha256'] or record['after_bytes'] != expected['bytes']
                    or successor['kind'] != 'reviewed-native-composition-cancel-inverse-repair'
                    or successor['correction'] != 'transaction-owned-native-composition-inverse-and-original-selection'
                    or successor['sha256'] != expected['sha256'] or successor['source_path'] != item['tracked_path']
                    or successor['source_only'] is not True):
                raise ValueError('Native current source must preserve its full historical origin')
    return {'source_files': 158, 'engine_files': 48, 'direct_translation_units': 32}


def inspect(repository_root, source_map_sha256):
    if os.name != 'posix':
        raise ValueError('Native source inspection currently requires POSIX file-mode/identity semantics')
    root = Path(repository_root)
    if not root.is_absolute() or not stat.S_ISDIR(root.lstat().st_mode):
        raise ValueError('Provide an absolute ordinary repository directory')
    pinned = _digest(source_map_sha256)
    raw, _ = _read(root, RECIPE + '/source-imports.json', 1048576)
    if hashlib.sha256(raw).hexdigest() != pinned:
        raise ValueError('Native source map differs from its independent pin')
    value = json.loads(raw, object_pairs_hook=_object,
                       parse_constant=lambda item: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))
    if type(value) is not dict or set(value) != FIELDS:
        raise ValueError('Invalid native source map fields')
    if type(value['schema_version']) is not int or value['schema_version'] != 1 \
            or value['kind'] not in ('foundation-native-engine-actions-source-inputs', COMPOSITION_SOURCE_KIND) \
            or value['scope'] != 'native-actions-source-candidate-only' or value['profile'] != 'actions':
        raise ValueError('Unsupported native source map contract')
    if value['limits'] != LIMITS or value['requirements'] != REQUIREMENTS:
        raise ValueError('Native source requirements/budgets cannot be widened')
    if type(value['suppliers']) is not dict or set(value['suppliers']) != {'wrapper', 'engine'}:
        raise ValueError('Both pinned source suppliers are required')
    expected = {'wrapper': '68c618544e1f8af18ebce346281a6a49766aa194',
                'engine': 'aec9d2ad958e716ab4bca4bf03007e6edac7323f'}
    if value['suppliers'] != expected or type(value['provenance']) is not dict:
        raise ValueError('Native source supplier/provenance contract changed')
    if value['kind'] == COMPOSITION_SOURCE_KIND:
        composition_catalogue_counts(value)
    elif type(value['inputs']) is dict and COMPOSITION_BRIDGE in value['inputs']:
        raise ValueError('Composition bridge requires its explicit successor version')
    entries = value['inputs']
    if type(entries) is not dict or not 1 <= len(entries) <= LIMITS['maximum_entries']:
        raise ValueError('Invalid native source input inventory')
    total, tracked, aliases = 0, set(), set()
    for logical, item in sorted(entries.items()):
        _path(logical)
        if type(item) is not dict or set(item) != INPUT_FIELDS:
            raise ValueError('Invalid native source input fields: ' + logical)
        name = _path(item['tracked_path'])
        if not name.startswith(RECIPE + '/') or name in tracked or name.lower() in aliases:
            raise ValueError('Native inputs must have distinct recipe-local paths')
        tracked.add(name)
        aliases.add(name.lower())
        if type(item['bytes']) is not int or not 0 <= item['bytes'] <= LIMITS['maximum_file_bytes'] \
                or type(item['mode']) is not int or item['mode'] != 0o644 \
                or item['role'] not in {'source', 'interface', 'patch', 'license', 'config', 'helper', 'provenance'} \
                or type(item['origin']) is not dict or type(item['origin'].get('kind')) is not str:
            raise ValueError('Invalid native source input facts: ' + logical)
        _digest(item['sha256'])
        body, mode = _read(root, name, LIMITS['maximum_file_bytes'])
        if len(body) != item['bytes'] or mode != item['mode'] \
                or hashlib.sha256(body).hexdigest() != item['sha256']:
            raise ValueError('Native source input differs from its inventory: ' + logical)
        total += len(body)
        if total > LIMITS['maximum_total_bytes']:
            raise ValueError('Native source inventory exceeds its total budget')
    # Walk only this small, declared source-delta namespace, never the supplier
    # tree, SDK, cache, or repository. Unknown source leaves must be reviewed.
    source = root / RECIPE / 'source'
    found = set()
    stack = [source]
    namespace_entries = 0
    while stack:
        directory = stack.pop()
        if not stat.S_ISDIR(directory.lstat().st_mode):
            raise ValueError('Native source namespace contains a non-directory')
        for child in directory.iterdir():
            namespace_entries += 1
            if namespace_entries > LIMITS['maximum_entries']:
                raise ValueError('Native source namespace exceeds its budget')
            kind = child.lstat().st_mode
            if stat.S_ISDIR(kind):
                stack.append(child)
            elif stat.S_ISREG(kind):
                found.add(child.relative_to(root).as_posix())
            else:
                raise ValueError('Native source namespace contains a link/special file')
    expected_sources = {name for name in tracked if name.startswith(RECIPE + '/source/')}
    if found != expected_sources:
        raise ValueError('Native source namespace differs from complete input inventory')
    return {'scope': 'native-actions-source-input-integrity-only', 'profile': 'actions',
            'source_map_sha256': pinned, 'files': len(entries), 'bytes': total,
            'requirements': REQUIREMENTS, 'native_build_performed': False,
            'native_runtime_checks_passed': False, 'kernel_rebuild_performed': False,
            'production_eligible': False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository-root', required=True)
    parser.add_argument('--source-map-sha256', required=True)
    args = parser.parse_args(argv)
    try:
        result = inspect(args.repository_root, args.source_map_sha256)
    except (OSError, ValueError, TypeError) as error:
        parser.exit(1, 'Native source inspection failed: ' + str(error) + '\n')
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
