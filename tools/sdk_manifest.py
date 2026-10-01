#!/usr/bin/env python3
"""Validate prepared SDK bytes and separate host, target and source contracts."""
from pathlib import Path
import re
from dependency_archive import digest, read_json, relative, verify_inventory


def contained(root, name):
    path = root.joinpath(*relative(name).parts)
    if path.is_symlink() or not path.exists() or (root != path.resolve() and root not in path.resolve().parents):
        raise ValueError('missing or escaping SDK path')
    return path


def verify_sdk(root, release=False):
    root = Path(root).resolve(strict=True)
    data = read_json(root / 'sdk.json')
    if data.get('schema_version') != 1 or not re.fullmatch(r'[0-9a-f]{64}', data.get('recipe_id', '')):
        raise ValueError('invalid SDK schema or full recipe identity')
    if data.get('installed_root') and data['installed_root'] != str(root):
        raise ValueError('installed SDK moved; reinstall the retained archive at its new root')
    target = data['target']
    if target['system'] not in ('Linux', 'Windows', 'Emscripten'):
        raise ValueError('unsupported target system')
    for field in ('processor', 'triple'):
        if not isinstance(target[field], str) or not target[field]: raise ValueError('missing target metadata')
    fields = ('sysroot',) if data.get('kind') == 'windows-dependencies' else ('cxx_compiler', 'sysroot')
    for field in fields:
        contained(root, target[field])
    verify_inventory(root, data['files'], exclude=('sdk.json',))
    for name in data.get('host_tools', {}).values():
        if not contained(root, name).is_file() or name not in data['files']:
            raise ValueError('host tool omitted from SDK inventory')
    for name in data.get('licenses', []):
        contained(root, name)
    if data.get('kind') != 'windows-dependencies' and target['cxx_compiler'] not in data['files']:
        raise ValueError('compiler omitted from SDK inventory')
    if release:
        if data.get('kind') not in ('source-build', 'retained-upstream', 'windows-dependencies'):
            raise ValueError('SDK preparation kind is not qualified for release')
        if not data.get('licenses') or not data.get('sources_sha256'):
            raise ValueError('SDK lacks retained source/license identity')
        if target['system'] == 'Linux' and data.get('baseline') != {'distribution': 'debian-12', 'glibc': '2.36'}:
            raise ValueError('Linux release SDK must declare the Bookworm runtime baseline')
        for scope in (() if data.get('kind') == 'windows-dependencies' else ('host', 'target')):
            report = data.get('audits', {}).get(scope, {})
            if report.get('status') != 'passed': raise ValueError('SDK compatibility audit missing: ' + scope)
    return digest(root / 'sdk.json')
