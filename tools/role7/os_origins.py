"""Passive joins to independently reviewed original host-OS member facts.

All I/O belongs to the caller's capture owner.  This module does not authenticate
packages, follow live aliases, walk roots, load submitted code or run programs.
The two approved pins must come from a separately reviewed authority; no input
document can install that authority.  There is no default approved pin.
"""
import hashlib
import json
from pathlib import Path
import re


MANIFEST_KIND = 'foundation-native-diagnostic-os-origin-manifest-v1'
RECORD_KIND = 'foundation-native-diagnostic-original-os-record-v1'
SCOPE = 'original-host-os-selected-members-only'
MAX_DOCUMENT = 1024 * 1024
MAX_RECORD = 4 * MAX_DOCUMENT
MAX_ENTRIES = 4096
MAX_MEMBER = 256 * MAX_DOCUMENT
MAX_ALIAS_STEPS = 16
EMPTY_SHA256 = hashlib.sha256(b'').hexdigest()


class MissingInputs(ValueError):
    def __init__(self, missing):
        self.missing = tuple(dict(item) for item in missing)
        self.roles = tuple(item['role'] for item in self.missing)
        super().__init__('Missing original OS evidence: ' + '; '.join(self.roles))

    def as_dict(self):
        return {'missing': [dict(item) for item in self.missing]}


def _missing(role, path, reason):
    raise MissingInputs([{'role': role, 'path': str(path), 'reason': reason}])


def _fields(value, names, label):
    if type(value) is not dict or set(value) != set(names):
        raise ValueError(label + ' has unknown or missing fields')


def _text(value):
    if (type(value) is not str or not value or len(value) > 4096
            or any(ord(c) < 32 or 127 <= ord(c) <= 159 or 0xd800 <= ord(c) <= 0xdfff for c in value)):
        raise ValueError('Canonical bounded nonempty text required')
    return value


def _pin(value):
    if type(value) is not str or re.fullmatch('[0-9a-f]{64}', value) is None or value == '0' * 64:
        raise ValueError('Nonzero lowercase SHA256 required')
    return value


def _integer(value, minimum, maximum):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError('Bounded actual integer required')
    return value


def _relative(value):
    _text(value)
    if (value.startswith('/') or '\\' in value or ':' in value or ';' in value
            or any(part in ('', '.', '..') or part.endswith(('.', ' ')) for part in value.split('/'))):
        raise ValueError('Canonical confined relative path required')
    return value


def _absolute(value):
    if isinstance(value, Path):
        value = str(value)
    _text(value)
    if (not value.startswith('/') or value.startswith('//') or '\\' in value or ':' in value or ';' in value
            or any(part in ('', '.', '..') for part in value.split('/')[1:])):
        raise ValueError('Canonical explicit absolute path required')
    return value


def _id(value):
    if type(value) is not str or re.fullmatch('[a-z][a-z0-9_-]{0,127}', value) is None:
        raise ValueError('Canonical original evidence identifier required')
    return value


def _map(value, label):
    if type(value) is not dict or not value or len(value) > MAX_ENTRIES:
        raise ValueError(label + ' requires a nonempty bounded map')
    return value


def _json(raw):
    def pairs(items):
        value = {}
        for key, item in items:
            if key in value:
                raise ValueError('Duplicate original OS metadata key')
            value[key] = item
        return value
    def number(_value):
        raise ValueError('Original OS metadata requires integers')
    try:
        return json.loads(raw.decode('utf-8'), object_pairs_hook=pairs,
                          parse_float=number, parse_constant=number)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as error:
        raise ValueError('Bounded strict original OS JSON required') from error


def _schema(value, names, kind):
    _fields(value, names, kind)
    if type(value['schema_version']) is not int or value['schema_version'] != 1:
        raise ValueError('Unsupported original OS schema')
    if value['kind'] != kind or value['scope'] != SCOPE:
        raise ValueError('Original OS kind/scope differs')


def _reference(ref, base):
    _fields(ref, ('path', 'sha256'), 'original OS reference')
    return Path(_absolute(base)) / _relative(ref['path']), _pin(ref['sha256'])


def _capture(ref, base, inputs, role, maximum):
    path, digest = _reference(ref, base)
    inputs.check_deadline()
    try:
        record = inputs.file(path, digest, role, maximum=maximum)
    except FileNotFoundError:
        _missing(role, path, 'independently selected original metadata absent')
    if (type(record) is not dict or record.get('path') != str(path) or record.get('sha256') != digest
            or type(record.get('bytes')) is not int or not 1 <= record['bytes'] <= maximum
            or type(record.get('mode')) is not int or record['mode'] != 0o644):
        raise ValueError('Capture must supply the exact ordinary0644 metadata facts')
    if any(old.startswith('diagnostic-body-') for old in record.get('roles', ())):
        raise ValueError('Original OS metadata cannot alias an opaque body capture')
    raw = inputs.bytes(path, maximum=maximum)
    inputs.check_deadline()
    if type(raw) is not bytes or len(raw) != record['bytes'] or hashlib.sha256(raw).hexdigest() != digest:
        raise ValueError('Captured original OS metadata bytes changed')
    value = _json(raw)
    if type(value) is not dict:
        raise ValueError('Original OS metadata must be a JSON object')
    return {'path': str(path), 'sha256': digest, 'bytes': len(raw), 'kind': value.get('kind')}, value


def _record(value):
    _schema(value, ('schema_version', 'kind', 'scope', 'sources', 'members', 'placements', 'aliases'), RECORD_KIND)
    sources, members, placements = (_map(value[key], key) for key in ('sources', 'members', 'placements'))
    aliases = value['aliases']
    if type(aliases) is not dict or len(aliases) > MAX_ENTRIES:
        raise ValueError('Original aliases require a bounded explicit map')
    if len(sources) + len(members) + len(placements) + len(aliases) > MAX_ENTRIES:
        raise ValueError('Original OS metadata aggregate entries exceed bound')
    for name, fact in sources.items():
        _id(name)
        _fields(fact, ('kind', 'identity', 'original_evidence_sha256'), 'original source descriptor')
        if fact['kind'] not in ('authenticated-package', 'source-build-output'):
            raise ValueError('Unknown original source descriptor kind')
        _text(fact['identity'])
        _pin(fact['original_evidence_sha256'])
    for name, fact in members.items():
        _relative(name)
        _fields(fact, ('source', 'sha256', 'bytes', 'mode'), 'original regular member')
        if _id(fact['source']) not in sources:
            raise ValueError('Original regular member names an absent source descriptor')
        _pin(fact['sha256'])
        _integer(fact['bytes'], 0, MAX_MEMBER)
        if fact['bytes'] == 0 and fact['sha256'] != EMPTY_SHA256:
            raise ValueError('Empty original regular member has a nonempty-content digest')
        if type(fact['mode']) is not int or fact['mode'] not in (0o644, 0o755):
            raise ValueError('Original regular member must be ordinary0644 or0755')
    for path, member in placements.items():
        _absolute(path)
        if _relative(member) not in members:
            raise ValueError('Original regular placement names an absent member')
    if set(placements) & set(aliases):
        raise ValueError('An original path cannot be both regular and an alias')
    for path, alias in aliases.items():
        _absolute(path)
        _fields(alias, ('type', 'target'), 'original literal alias')
        target = _text(alias['target'])
        if alias['type'] not in ('symlink', 'hardlink') or any(c in target for c in ('\\', ':', ';')):
            raise ValueError('Original literal alias type/target differs')
        if alias['type'] == 'hardlink':
            _absolute(target)
            if target not in placements:
                raise ValueError('Original hardlink must name a direct regular placement')
        elif target.startswith('//') or any(part == '' for part in target.split('/')[1:]):
            raise ValueError('Original symlink literal target is ambiguous')
    return value


def _resolve(logical, record, check_deadline):
    pending, current, seen, steps = logical.split('/')[1:], [], set(), []
    while pending:
        check_deadline()
        if len('/'.join(current + pending)) > 4096:
            raise ValueError('Original alias pending path exceeds bound')
        part, pending = pending[0], pending[1:]
        if part in ('', '.'):
            continue
        if part == '..':
            if current:
                current.pop()
            continue
        current.append(part)
        path = '/' + '/'.join(current)
        if path in record['placements'] and pending:
            raise ValueError('Original regular leaf cannot supply a directory prefix')
        if path not in record['aliases']:
            continue
        if len(steps) == MAX_ALIAS_STEPS:
            raise ValueError('Original alias derivation exceeds step bound')
        # Only alias expansions can cycle. At most16 bounded states survive;
        # ordinary path components must not grow a quadratic history table.
        state = (path, tuple(pending))
        if state in seen:
            raise ValueError('Original alias derivation contains a cycle')
        seen.add(state)
        alias = record['aliases'][path]
        if alias['type'] == 'hardlink' and pending:
            raise ValueError('Original hardlink cannot supply a directory prefix')
        target = alias['target']
        current.pop()
        if target.startswith('/'):
            current = []
        pending = target.split('/') + pending
        next_path = '/' + '/'.join(current + [part for part in pending if part])
        steps.append({'path': path, 'type': alias['type'], 'literal_target': target, 'next_path': next_path})
    final = '/' + '/'.join(current)
    if final not in record['placements']:
        _missing('diagnostic-original-os-member', final, 'original ordinary placement absent')
    return final, steps or None


def consume_original_os_manifest(ref, base, inputs, *, approved_manifest_sha256=None,
                                 approved_original_record_sha256=None):
    """Join two approved metadata documents, never original/retained body files.

    The approved record digest means a separate original-evidence review has
    approved that exact table.  Descriptor strings/pins inside JSON do not prove
    authentication and cannot supply either approved argument.
    """
    missing = []
    for value, role in ((approved_manifest_sha256, 'diagnostic-original-os-authority'),
                        (approved_original_record_sha256, 'diagnostic-original-os-record-authority')):
        if value is None:
            missing.append({'role': role, 'path': str(base), 'reason': 'independently approved exact original metadata pin absent'})
        else:
            _pin(value)
    if missing:
        raise MissingInputs(missing)
    path, digest = _reference(ref, base)
    if digest != approved_manifest_sha256:
        _missing('diagnostic-original-os-authority', path, 'submitted manifest does not select the independently approved pin')
    manifest_ref, manifest = _capture(ref, base, inputs, 'diagnostic-provenance-os-manifest', MAX_DOCUMENT)
    _schema(manifest, ('schema_version', 'kind', 'scope', 'original_record', 'files'), MANIFEST_KIND)
    original_path, original_pin = _reference(manifest['original_record'], path.parent)
    if original_pin != approved_original_record_sha256:
        _missing('diagnostic-original-os-record-authority', original_path, 'manifest does not select the independently approved original record pin')
    if original_path == path:
        raise ValueError('OS manifest and original record must be distinct metadata leaves')
    record_ref, original = _capture(manifest['original_record'], path.parent, inputs,
                                    'diagnostic-provenance-os-original', MAX_RECORD)
    original = _record(original)
    files, resolved = _map(manifest['files'], 'original selected OS files'), set()
    result = {}
    for name, fact in files.items():
        inputs.check_deadline()
        _id(name)
        _fields(fact, ('logical_path', 'resolved_path', 'sha256', 'bytes', 'mode', 'original_member'), 'selected original OS file')
        logical, final = _absolute(fact['logical_path']), _absolute(fact['resolved_path'])
        actual, alias = _resolve(logical, original, inputs.check_deadline)
        if actual != final or final in resolved:
            raise ValueError('Selected original OS resolution differs or duplicates a regular target')
        resolved.add(final)
        member = _relative(fact['original_member'])
        if original['placements'][final] != member:
            raise ValueError('Selected OS original member differs from its regular placement')
        expected = original['members'][member]
        _pin(fact['sha256'])
        _integer(fact['bytes'], 0, MAX_MEMBER)
        if type(fact['mode']) is not int or any(fact[key] != expected[key] for key in ('sha256', 'bytes', 'mode')):
            raise ValueError('Selected OS file differs from its approved original regular member')
        result[name] = dict(fact, alias=alias)
    inputs.check_deadline()
    return {'manifest': manifest_ref, 'original_record': record_ref, 'files': result}
