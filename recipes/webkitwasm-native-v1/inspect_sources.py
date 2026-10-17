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

RECIPE = 'recipes/webkitwasm-native-v1'
FIELDS = {'schema_version', 'kind', 'scope', 'profile', 'suppliers', 'provenance',
          'requirements', 'limits', 'inputs'}
INPUT_FIELDS = {'tracked_path', 'sha256', 'bytes', 'mode', 'role', 'origin'}
REQUIREMENTS = ['closed-retained-native-source-recipe-and-provider-build',
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
            or value['kind'] != 'foundation-native-engine-source-inputs' \
            or value['scope'] != 'native-source-candidate-only' or value['profile'] != 'pixel':
        raise ValueError('Unsupported native source map contract')
    if value['limits'] != LIMITS or value['requirements'] != REQUIREMENTS:
        raise ValueError('Native source requirements/budgets cannot be widened')
    if type(value['suppliers']) is not dict or set(value['suppliers']) != {'wrapper', 'engine'}:
        raise ValueError('Both pinned source suppliers are required')
    expected = {'wrapper': '68c618544e1f8af18ebce346281a6a49766aa194',
                'engine': 'aec9d2ad958e716ab4bca4bf03007e6edac7323f'}
    if value['suppliers'] != expected or type(value['provenance']) is not dict:
        raise ValueError('Native source supplier/provenance contract changed')
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
    return {'scope': 'native-source-input-integrity-only', 'profile': 'pixel',
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
