#!/usr/bin/env python3
"""Passive consumption of one fixed original authentication/member producer.

The caller supplies independently reviewed authority and an existing InputSet.
This module never opens files itself, starts programs, imports a submitted
producer, parses package/signature/archive contents or publishes readiness.
"""
import hashlib
import json
from pathlib import Path, PurePosixPath
import re


MIB = 1024 * 1024
PROOF_KIND = 'foundation-native-fixed-trixie-original-proof-v1'
LAUNCH_KIND = 'foundation-native-fixed-trixie-original-launch-v1'
ROLES = ('gperf', 'ruby3.3', 'libruby3.3')
KNOWN_SOURCES = {
    'collector': {'sha256': 'ec769e909194cdc26cd283f3160ff9836dfc25105100341cca28b8b1731d5c62', 'bytes': 102702},
    'runner': {'sha256': 'ee3d31ccb80cf45b5d85dd3c09aa659c09dfd126fe40c2d1cce038fbb65586aa', 'bytes': 20268},
    'process_tree': {'sha256': 'cb68d2449ce3c1aa18a24169466e6f5d425b710fac1c356d5e22deeac14b687d', 'bytes': 33939},
}
FIXED_INPUTS = {
    'InRelease': ('0584fba32e13e0ab8285fb16c27adea1ec03a73669c18702821094fd6ca86675', 140421),
    'Release': ('ed56aac47e7911e65ee63aae8d67e29f20e023f840e49f8ed037043a33de138a', 138612),
    'Packages': ('4f2c68d67001d595fbd343f6dbad44468953a51c4d9dec3a4803249f6e295940', 56620099),
}
PACKAGES = {
    'gperf': {'name': 'gperf', 'source_package': 'gperf', 'version': '3.2.1-1', 'architecture': 'amd64',
        'filename': 'pool/main/g/gperf/gperf_3.2.1-1_amd64.deb',
        'sha256': '8a09d9ead1899a8ade3ed6205c06f1ce0b50792da8f92f6672a7060410fc226e', 'bytes': 153464},
    'ruby3.3': {'name': 'ruby3.3', 'source_package': 'ruby3.3', 'version': '3.3.8-2', 'architecture': 'amd64',
        'filename': 'pool/main/r/ruby3.3/ruby3.3_3.3.8-2_amd64.deb',
        'sha256': '10798ffe8edc86d7f9491655a115049a7a77dfbef5dc909dc13803cbb6c47f9b', 'bytes': 834088},
    'libruby3.3': {'name': 'libruby3.3', 'source_package': 'ruby3.3', 'version': '3.3.8-2', 'architecture': 'amd64',
        'filename': 'pool/main/r/ruby3.3/libruby3.3_3.3.8-2_amd64.deb',
        'sha256': '033d7f7359da6353d29e5cb87ef411357d3841c02fd7d1089897653fec665289', 'bytes': 6300780},
}
SIGNERS = sorted(('4CB50190207B4758A3F73A796ED0E7B82643E131',
    'B8E5F13176D2A7A75220028078DBA3BC47EF2265', '41587F7DB8C774BCCF131416762F67A0B2C39DE4'))
LIMITS = {
    'inrelease_bytes': MIB, 'release_bytes': MIB, 'keyring_bytes': MIB,
    'packages_bytes': 64 * MIB, 'deb_bytes': 64 * MIB, 'tar_bytes': 256 * MIB,
    'tar_metadata_entries': 10000, 'member_bytes': 16 * MIB,
    'selected_member_bytes': 64 * MIB, 'stanza_bytes': 65536,
    'child_stderr_bytes': MIB, 'worker_log_bytes': 65536,
    'proof_bytes': MIB, 'metadata_document_bytes': MIB,
    'collector_pointer_bytes': 4096, 'unique_opaque_body_bytes': 1024 * MIB,
    'attempt_seconds': 300, 'gpgv_seconds': 30, 'dpkg_seconds': 60,
    'cleanup_seconds': 5, 'worker_roles_concurrent': 1, 'child_creations': 17,
}
MAX_ENTRIES = 65536
EMPTY_SHA256 = hashlib.sha256(b'').hexdigest()
# InputSet.inventory assigns these metadata roles to its document, not leaves.
# They are exact fixed-v4 categories; an arbitrary body *-inventory is not exempt.
_GENERATED_INVENTORY_ROLES = frozenset(
    ['diagnostic-body-packages-inventory']
    + ['diagnostic-body-runtime-' + role + '-inventory' for role in ('controller', 'gpgv', 'dpkg_deb')]
    + ['diagnostic-body-' + kind + '-' + role + '-inventory'
       for kind in ('deb', 'member-tar') for role in ROLES])


class MissingInputs(ValueError):
    """Named missing compatible evidence, never permission for another builder."""
    def __init__(self, missing):
        self.missing = tuple(dict(item) for item in missing)
        self.roles = tuple(item['role'] for item in self.missing)
        super().__init__('Missing original producer inputs: ' + '; '.join(
            item['role'] + ': ' + item['reason'] for item in self.missing))

    def as_dict(self):
        return {'missing': [dict(item) for item in self.missing]}


def _missing(role, path, reason):
    raise MissingInputs([{'role': role, 'path': str(path), 'reason': reason}])


def _fields(value, names, label):
    if type(value) is not dict or set(value) != set(names):
        raise ValueError(label + ' has unknown or missing fields')
    return value


def _integer(value, label, minimum=0, maximum=1024 * MIB):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(label + ' requires a bounded actual integer')
    return value


def _pin(value):
    if type(value) is not str or re.fullmatch('[0-9a-f]{64}', value) is None or value == '0' * 64:
        raise ValueError('A nonzero lowercase SHA256 is required')
    return value


def _text(value):
    if (type(value) is not str or not value or any(ord(c) < 32 or ord(c) == 127
            or 0xD800 <= ord(c) <= 0xDFFF for c in value)):
        raise ValueError('Canonical nonempty text is required')
    return value


def _relative(value):
    _text(value)
    if (value.startswith('/') or '\\' in value or ':' in value or ';' in value
            or any(part in ('', '.', '..') or part.endswith(('.', ' '))
                   for part in value.split('/'))):
        raise ValueError('A confined portable relative path is required')
    return value


def _absolute(value):
    if isinstance(value, Path):
        value = str(value)
    _text(value)
    if (not value.startswith('/') or value.startswith('//') or '\\' in value
            or ':' in value or ';' in value or any(part in ('', '.', '..')
                for part in value.split('/')[1:])):
        raise ValueError('A normalized explicit absolute path is required')
    return Path(value)


def _ref(value, base):
    _fields(value, ('path', 'sha256'), 'original file reference')
    return _absolute(base) / _relative(value['path']), _pin(value['sha256'])


def _json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate original metadata JSON key')
            result[key] = value
        return result
    def number(_value):
        raise ValueError('Original metadata requires actual integers, never float/nonfinite values')
    try:
        return json.loads(raw.decode('utf-8'), object_pairs_hook=pairs,
                          parse_float=number, parse_constant=number)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as error:
        raise ValueError('Bounded strict UTF8 JSON is required') from error


def _encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()


def _schema(value, names, kind, scope=None):
    _fields(value, names, kind)
    if type(value['schema_version']) is not int or value['schema_version'] != 1 or value['kind'] != kind:
        raise ValueError('Unsupported original metadata schema/kind')
    if scope is not None and value['scope'] != scope:
        raise ValueError('Original metadata scope differs')
    return value


def _ownership(value):
    _fields(value, ('closed', 'descendants_closed', 'logs_closed'), 'original ownership')
    if any(flag is not True for flag in value.values()):
        raise ValueError('Original process/descendant/log ownership is not closed')


def _completion(value):
    _fields(value, ('finish_returncode', 'fault', 'terminated', 'outliving'), 'original completion')
    if (type(value['finish_returncode']) is not int or value['finish_returncode'] != 0
            or value['fault'] is not None or value['terminated'] is not False or value['outliving'] is not False):
        raise ValueError('Original qualified completion is unsuccessful or open')


def _ineligible(value):
    if any(value[key] is not False for key in ('production_eligible', 'native_engine_execution', 'kernel_rebuild')):
        raise ValueError('Original proof scope flags must be actual false')


def _producer(value, base, source_pin, policy_pin):
    _fields(value, ('source_closure', 'launch_policy'), 'original producer')
    first, second = _ref(value['source_closure'], base), _ref(value['launch_policy'], base)
    for role, actual, expected in (('diagnostic-original-source-authority', first, source_pin),
                                   ('diagnostic-original-launch-authority', second, policy_pin)):
        if actual[1] != expected:
            _missing(role, actual[0], 'record does not select the independently approved authority')
    if first[0] == second[0]:
        raise ValueError('Original source and launch policy documents must be distinct')
    return first, second


class _Capture:
    """Route-local accounting; all physical capture is delegated to InputSet."""
    def __init__(self, inputs):
        self.inputs = inputs
        self.files = {}
        self.total = 0
        self.inventories = {}
        self.classes = {}

    def file(self, path, sha, role, maximum):
        self.inputs.check_deadline()
        path = _absolute(path)
        key = str(path)
        kind = 'opaque' if role.startswith('diagnostic-body-') else 'metadata'
        if key in self.classes and self.classes[key] != kind:
            raise ValueError('An opaque original input cannot acquire a metadata alias')
        remaining = LIMITS['unique_opaque_body_bytes'] - self.total
        bound = maximum if key in self.files else min(maximum, remaining)
        try:
            record = self.inputs.file(path, _pin(sha), role, maximum=bound)
        except FileNotFoundError as error:
            _missing(role, path, 'ordinary original retained input absent')
        if (type(record) is not dict or record.get('path') != key or record.get('sha256') != sha
                or type(record.get('bytes')) is not int or not 0 <= record['bytes'] <= bound
                or type(record.get('mode')) is not int or record['mode'] not in (0o644, 0o755)):
            raise ValueError('Capture did not supply the required ordinary original file facts')
        if kind == 'opaque' and any(any(marker in old for marker in ('provenance', 'inventory', 'inspection'))
                or old in ('font', 'font_config', 'icu_data', 'ca_bundle', 'host-runtime-facts')
                for old in record.get('roles', ())):
            raise ValueError('An opaque original body already has a metadata capture role')
        if kind == 'metadata' and any(old.startswith('diagnostic-body-') and old not in _GENERATED_INVENTORY_ROLES
                                      for old in record.get('roles', ())):
            raise ValueError('An original metadata leaf already has an opaque capture role')
        if key in self.files:
            if any(self.files[key][name] != record[name] for name in ('sha256', 'bytes', 'mode')):
                raise ValueError('An original file identity changed through an alias')
        else:
            self.total += record['bytes']
            self.files[key] = dict(record)
        self.classes[key] = kind
        return record

    def raw(self, ref, base, role, maximum, expected_name=None):
        path, sha = _ref(ref, base)
        if expected_name is not None and path != _absolute(base) / expected_name:
            raise ValueError('Original metadata reference differs from the fixed layout')
        record = self.file(path, sha, role, maximum)
        if record['mode'] != 0o644:
            raise ValueError('Published original metadata must be ordinary0644')
        raw = self.inputs.bytes(path, maximum=maximum)
        if type(raw) is not bytes or len(raw) != record['bytes'] or hashlib.sha256(raw).hexdigest() != sha:
            raise ValueError('Captured original metadata changed during bounded read')
        return path, raw

    def document(self, ref, base, role, maximum=None, expected_name=None):
        path, raw = self.raw(ref, base, role, LIMITS['metadata_document_bytes'] if maximum is None else maximum,
                             expected_name)
        return path, _json(raw), raw

    def inventory(self, record, base, role):
        _fields(record, ('root', 'inventory'), 'complete original inventory record')
        root = _absolute(record['root'])
        path, value, _ = self.document(record['inventory'], base, 'diagnostic-provenance-body-inventory')
        if root == path or root in path.parents:
            raise ValueError('Original inventory metadata must be outside its root')
        _fields(value, ('files', 'directories', 'modes'), 'complete original inventory')
        files, dirs, modes = (value[name] for name in ('files', 'directories', 'modes'))
        if (type(files) is not dict or not files or type(dirs) is not list
                or any(type(name) is not str for name in dirs) or dirs != sorted(set(dirs))
                or type(modes) is not dict or set(modes) != set(files) | set(dirs)
                or set(files) & set(dirs) or len(files) + len(dirs) > MAX_ENTRIES):
            raise ValueError('Original inventory requires finite complete files/directories/modes')
        registry = {}
        for name in (*dirs, *files):
            _relative(name)
            folded = name.casefold()
            if folded in registry:
                raise ValueError('Original inventory contains a portable case collision')
            registry[folded] = name
            parents = PurePosixPath(name).parents
            if any(str(parent) not in dirs for parent in parents if str(parent) != '.'):
                raise ValueError('Original inventory omits a parent directory')
            if type(modes[name]) is not int or modes[name] not in ((0o755,) if name in dirs else (0o644, 0o755)):
                raise ValueError('Original inventory requires ordinary file/directory modes')
        key = (str(root), str(path), record['inventory']['sha256'])
        if key in self.inventories:
            previous = self.inventories[key]
            if previous['role'].startswith('diagnostic-body-') != role.startswith('diagnostic-body-'):
                raise ValueError('Original inventory cannot cross metadata/opaque classes')
            return previous
        captured = {}
        for name, sha in sorted(files.items()):
            self.inputs.check_deadline()
            item = self.file(root / name, sha, role, LIMITS['unique_opaque_body_bytes'])
            if item['mode'] != modes[name]:
                raise ValueError('Original inventory leaf mode differs from actual retained mode')
            captured[name] = item
        # Unknown actual entries fail in the existing walker before body reads.
        actual = self.inputs.inventory(record, base, role)
        if any(actual.get(name) != expected for name, expected in
               (('root', str(root)), ('files', files), ('directories', dirs), ('modes', modes))):
            raise ValueError('Complete original inventory differs from captured declared inputs')
        result = {'root': root, 'path': path, 'sha256': record['inventory']['sha256'],
                  'files': captured, 'directories': dirs, 'role': role}
        self.inventories[key] = result
        return result

    def blob(self, value, base, role, maximum):
        _fields(value, ('root', 'inventory', 'member', 'sha256', 'bytes'), 'original BLOB')
        name = _relative(value['member'])
        _integer(value['bytes'], 'original BLOB bytes', maximum=maximum)
        inv = self.inventory({'root': value['root'], 'inventory': value['inventory']}, base, role)
        if name not in inv['files']:
            raise ValueError('Original BLOB is not an admitted complete-inventory leaf')
        item = self.file(inv['root'] / name, value['sha256'], role, maximum)
        if item['bytes'] != value['bytes']:
            raise ValueError('Original BLOB size differs from actual captured bytes')
        return inv['root'] / name, inv

    def finish(self):
        self.inputs.check_deadline()
        self.inputs.recheck()
        self.inputs.check_deadline()
        return [{'root': key[0], 'inventory': {'path': key[1], 'sha256': key[2]}}
                for key in sorted(self.inventories)]


def _member_id(value):
    _text(value)
    if value.startswith('/') or '\\' in value or any(part in ('', '.', '..') for part in value.split('/')):
        raise ValueError('Original source member ID is not canonical case-sensitive POSIX data')
    return value


def _selection(value):
    _fields(value, ROLES, 'fixed package selections')
    for item in value.values():
        _fields(item, ('members', 'link_origins'), 'fixed member selection')
        for kind in ('members', 'link_origins'):
            names = item[kind]
            if type(names) is not list or len(names) > LIMITS['tar_metadata_entries']:
                raise ValueError('Fixed member selection requires a bounded list')
            for name in names:
                _member_id(name)
            if len(names) != len(set(names)):
                raise ValueError('Original selection has duplicate member IDs')
        if not item['members'] or set(item['members']) & set(item['link_origins']):
            raise ValueError('Original regular/link selections must be nonempty and disjoint')


def _partitions(metadata, opaque):
    if any(a == b or a in b.parents or b in a.parents for a in metadata for b in opaque):
        raise ValueError('Original metadata/source/keyring and opaque roots overlap')


def _authority(capture, producer, base, source_pin, policy_pin):
    source_ref, policy_ref = _producer(producer, base, source_pin, policy_pin)
    source_path, source, _ = capture.document(producer['source_closure'], base, 'diagnostic-provenance-source-closure')
    policy_path, policy, _ = capture.document(producer['launch_policy'], base, 'diagnostic-provenance-launch-policy')
    for value, kind, role, path in (
            (source, 'foundation-native-fixed-trixie-original-source-closure-v1',
             'diagnostic-original-source-authority', source_path),
            (policy, 'foundation-native-fixed-trixie-original-launch-policy-v1',
             'diagnostic-original-launch-authority', policy_path)):
        if type(value) is not dict or value.get('kind') != kind:
            _missing(role, path, 'compatible original authority kind is absent')
    _schema(source, ('schema_version', 'kind', 'scope', 'inventory', 'files'),
            'foundation-native-fixed-trixie-original-source-closure-v1', 'fixed-original-producer-source-only')
    _fields(source['files'], KNOWN_SOURCES, 'original source roles')
    inv = capture.inventory(source['inventory'], source_path.parent, 'diagnostic-provenance-source-collector')
    sources = {}
    for name, expected in KNOWN_SOURCES.items():
        item = _fields(source['files'][name], ('path', 'sha256', 'bytes', 'mode'), 'original source file')
        _pin(item['sha256'])
        _integer(item['bytes'], 'original source length', 1)
        _integer(item['mode'], 'original source mode', maximum=0o777)
        if item['mode'] not in (0o644, 0o755):
            raise ValueError('Original source mode must be ordinary0644 or0755')
        if any(item[key] != expected[key] for key in ('sha256', 'bytes')):
            _missing('diagnostic-original-source-authority', source_path, 'original producer source is not the reviewed fixed implementation')
        leaf = _relative(item['path'])
        if leaf not in inv['files'] or any(inv['files'][leaf][key] != item[key] for key in ('sha256', 'bytes', 'mode')):
            raise ValueError('Original source facts differ from complete actual source inventory')
        sources[name] = inv['root'] / leaf
        capture.file(sources[name], item['sha256'], 'diagnostic-provenance-source-' + name.replace('_', '-'), item['bytes'])
    if set(inv['files']) != {item['path'] for item in source['files'].values()}:
        raise ValueError('Original source inventory contains an extra import/cache leaf')
    _schema(policy, ('schema_version', 'kind', 'scope', 'source_closure_sha256', 'programs',
        'keyring', 'runtime_inventories', 'selection', 'environment', 'limits'),
        'foundation-native-fixed-trixie-original-launch-policy-v1', 'fixed-original-producer-launch-authority-only')
    if policy['source_closure_sha256'] != source_ref[1]:
        raise ValueError('Original launch policy does not bind its independent source closure')
    _fields(policy['limits'], LIMITS, 'original limits')
    if any(type(policy['limits'][key]) is not int or policy['limits'][key] != value for key, value in LIMITS.items()):
        raise ValueError('Original fixed limits differ from reviewed v4 policy')
    _fields(policy['programs'], ('controller', 'gpgv', 'dpkg_deb'), 'original program roles')
    _fields(policy['runtime_inventories'], policy['programs'], 'original runtime aliases')
    _selection(policy['selection'])
    runtime_roots = [_absolute(item['root']) for item in policy['runtime_inventories'].values()
                     if type(item) is dict and 'root' in item]
    keyring = _fields(policy['keyring'], ('root', 'inventory', 'member', 'sha256', 'bytes'), 'original keyring')
    _partitions((inv['root'], _absolute(keyring['root']), _absolute(base)), runtime_roots)
    programs = {}
    for role, item in policy['programs'].items():
        _fields(item, ('path', 'sha256', 'version'), 'original program')
        path = _absolute(item['path'])
        _text(item['version'])
        runtime = capture.inventory(policy['runtime_inventories'][role], policy_path.parent, 'diagnostic-body-runtime-' + role)
        if runtime['root'] not in path.parents:
            raise ValueError('Original program is outside its named complete runtime')
        name = path.relative_to(runtime['root']).as_posix()
        leaf = capture.file(path, item['sha256'], 'diagnostic-body-program-' + role, LIMITS['unique_opaque_body_bytes'])
        if name not in runtime['files'] or leaf['mode'] != 0o755 or leaf['bytes'] <= 0:
            raise ValueError('Original program must be an actual nonempty executable runtime leaf')
        programs[role] = str(path)
    environment = _fields(policy['environment'], ('PATH', 'LANG', 'LC_ALL', 'TZ', 'SOURCE_DATE_EPOCH'), 'original ENV5')
    epoch = environment['SOURCE_DATE_EPOCH']
    if type(epoch) is not str or re.fullmatch('0|[1-9][0-9]*', epoch) is None:
        raise ValueError('Original epoch is not canonical ASCII decimal')
    expected_env = {'PATH': ':'.join(sorted({str(Path(path).parent) for path in programs.values()})),
        'LANG': 'C.UTF-8', 'LC_ALL': 'C.UTF-8', 'TZ': 'UTC', 'SOURCE_DATE_EPOCH': epoch}
    if environment != expected_env:
        raise ValueError('Original environment differs from the exact three-program ENV5')
    keyring_path, keyring_inv = capture.blob(keyring, policy_path.parent, 'diagnostic-provenance-keyring', LIMITS['keyring_bytes'])
    return {'sources': sources, 'policy': policy, 'programs': programs, 'environment': expected_env,
            'keyring': keyring_path, 'source_root': inv['root'], 'keyring_root': keyring_inv['root'],
            'runtime_roots': runtime_roots}


def _command(value, argv, environment, cwd):
    _fields(value, ('argv', 'environment', 'cwd', 'returncode', 'stdout', 'stderr', 'ownership'), 'original command')
    if (value['argv'] != argv or value['environment'] != environment or value['cwd'] != str(cwd)
            or type(value['returncode']) is not int or value['returncode'] != 0):
        raise ValueError('Original command differs from the fixed observed argv/environment/cwd/result')
    _ownership(value['ownership'])


def _facts(value, selection, totals):
    if type(value['members']) is not dict or type(value['link_origins']) is not dict:
        raise ValueError('Original selected members/link origins must be maps')
    if any(set(value[name]) != set(selection[name]) for name in ('members', 'link_origins')):
        raise ValueError('Original selected regular/link set differs from independent policy')
    for name, fact in value['members'].items():
        _member_id(name)
        _fields(fact, ('sha256', 'size', 'mode'), 'original regular member fact')
        _pin(fact['sha256'])
        _integer(fact['size'], 'original member size', maximum=LIMITS['member_bytes'])
        _integer(fact['mode'], 'original member mode', maximum=0o777)
        if fact['size'] == 0 and fact['sha256'] != EMPTY_SHA256:
            raise ValueError('Empty original member must have the actual empty-content hash')
        totals[0] += fact['size']
    for name, fact in value['link_origins'].items():
        _member_id(name)
        _fields(fact, ('type', 'target'), 'original link origin')
        if (fact['type'] not in ('symlink', 'hardlink') or type(fact['target']) is not str
                or not fact['target'] or '\0' in fact['target']
                or any(0xD800 <= ord(c) <= 0xDFFF for c in fact['target'])):
            raise ValueError('Original link origin requires its literal nonfollowed target')
    totals[1] += len(value['members']) + len(value['link_origins'])
    if totals[0] > LIMITS['selected_member_bytes'] or totals[1] > LIMITS['tar_metadata_entries']:
        raise ValueError('Original global selected member size/count bound exceeded')


def _diagnostic_original_proof(launch_ref, base, inputs, *,
        approved_source_closure_sha256, approved_launch_policy_sha256):
    """Validate metadata from the one fixed producer; return only original facts.

    Authority arguments MUST come from a reviewed versioned caller, never the
    submitted host/receipt JSON. No compatible authority is installed by default.
    """
    absent = []
    for role, value in (('diagnostic-original-source-authority', approved_source_closure_sha256),
                        ('diagnostic-original-launch-authority', approved_launch_policy_sha256)):
        try:
            _pin(value)
        except ValueError:
            absent.append({'role': role, 'path': '', 'reason': 'independently approved original authority is absent'})
    if absent:
        raise MissingInputs(absent)
    capture = _Capture(inputs)
    launch_path, launch, _ = capture.document(launch_ref, base, 'diagnostic-provenance-launch')
    metadata = launch_path.parent
    if type(launch) is not dict or launch.get('kind') != LAUNCH_KIND:
        _missing('diagnostic-original-proof', launch_path, 'compatible original launch receipt absent')
    _schema(launch, ('schema_version', 'kind', 'scope', 'producer', 'invocation', 'command', 'completion',
        'proof', 'production_eligible', 'native_engine_execution', 'kernel_rebuild'),
        LAUNCH_KIND, 'original-post-closure-producer-launch-only')
    _ineligible(launch)
    _completion(launch['completion'])
    authority = _authority(capture, launch['producer'], metadata,
                           approved_source_closure_sha256, approved_launch_policy_sha256)
    _, invocation, _ = capture.document(launch['invocation'], metadata, 'diagnostic-provenance-invocation', expected_name='invocation.json')
    _schema(invocation, ('schema_version', 'kind', 'producer', 'input_root', 'metadata_output', 'opaque_output', 'workspace'),
            'foundation-native-fixed-trixie-original-invocation-v1')
    if invocation['producer'] != launch['producer']:
        raise ValueError('Original invocation does not bind the same independent producer')
    input_root, observed_metadata, opaque, workspace = (_absolute(invocation[name])
        for name in ('input_root', 'metadata_output', 'opaque_output', 'workspace'))
    roots = (input_root, observed_metadata, opaque, workspace)
    if any(a == b or a in b.parents or b in a.parents for i, a in enumerate(roots) for b in roots[i + 1:]):
        raise ValueError('Original input/output/workspace paths overlap')
    _partitions((metadata, authority['source_root'], authority['keyring_root']),
                (*authority['runtime_roots'], input_root / 'body', opaque))
    protected = (authority['source_root'], authority['keyring_root'], *authority['runtime_roots'])
    if any(a == b or a in b.parents or b in a.parents for a in roots[1:] for b in protected):
        raise ValueError('Original output/workspace overlaps protected source/runtime/keyring')
    programs, sources, env = (authority[name] for name in ('programs', 'sources', 'environment'))
    argv = [programs['controller'], '-I', '-B', str(sources['collector']), '--collect-fixed',
            '--invocation', str(input_root / 'metadata/invocation.json')]
    _command(launch['command'], argv, env, workspace)
    _, pointer_raw = capture.raw(launch['command']['stdout'], metadata, 'diagnostic-provenance-collector-stdout',
                                 LIMITS['collector_pointer_bytes'], 'collector.stdout')
    _, error_raw = capture.raw(launch['command']['stderr'], metadata, 'diagnostic-provenance-collector-stderr',
                               LIMITS['child_stderr_bytes'], 'collector.stderr')
    if error_raw:
        raise ValueError('Successful original collector stderr must be empty')
    pointer = _fields(_json(pointer_raw), ('proof_sha256', 'bytes', 'kind'), 'canonical original proof pointer')
    if pointer['kind'] != PROOF_KIND or _encoded(pointer) != pointer_raw:
        raise ValueError('Original collector stdout is not its exact canonical pointer')
    _integer(pointer['bytes'], 'original proof pointer bytes', 1, LIMITS['proof_bytes'])
    _pin(pointer['proof_sha256'])
    proof_ref = _fields(launch['proof'], ('path', 'sha256', 'bytes', 'kind'), 'original proof reference')
    _integer(proof_ref['bytes'], 'original proof bytes', 1, LIMITS['proof_bytes'])
    if (proof_ref['kind'] != PROOF_KIND or proof_ref['sha256'] != pointer['proof_sha256']
            or proof_ref['bytes'] != pointer['bytes']):
        raise ValueError('Original proof reference differs from its closed pointer')
    proof_path, proof, proof_raw = capture.document({'path': proof_ref['path'], 'sha256': proof_ref['sha256']},
        metadata, 'diagnostic-provenance-proof', LIMITS['proof_bytes'], 'proof.json')
    if len(proof_raw) != proof_ref['bytes']:
        raise ValueError('Original proof length differs from its actual captured bytes')
    _schema(proof, ('schema_version', 'kind', 'scope', 'producer', 'inputs', 'authentication', 'packages',
        'production_eligible', 'native_engine_execution', 'kernel_rebuild'), PROOF_KIND,
        'fixed-three-package-original-regular-members-only')
    _ineligible(proof)
    if proof['producer'] != launch['producer']:
        raise ValueError('Original proof producer differs from its independent launch')
    _fields(proof['inputs'], ('inrelease', 'retained_release', 'keyring', 'index'), 'original proof inputs')
    for key, name, cap in (('inrelease', 'InRelease', 'inrelease_bytes'), ('retained_release', 'Release', 'release_bytes')):
        _, raw = capture.raw(proof['inputs'][key], metadata, 'diagnostic-provenance-' + key.replace('_', '-'), LIMITS[cap], name)
        if (hashlib.sha256(raw).hexdigest(), len(raw)) != FIXED_INPUTS[name]:
            raise ValueError('Fixed original signed metadata identity differs')
    _, keyring_raw = capture.raw(proof['inputs']['keyring'], metadata, 'diagnostic-provenance-keyring', LIMITS['keyring_bytes'], 'keyring.gpg')
    if (hashlib.sha256(keyring_raw).hexdigest(), len(keyring_raw)) != (
            authority['policy']['keyring']['sha256'], authority['policy']['keyring']['bytes']):
        raise ValueError('Original copied keyring differs from independent policy')

    def body(blob, root, member, inventory, cap, role):
        if (type(blob) is not dict or blob.get('root') != str(root) or blob.get('member') != member
                or type(blob.get('inventory')) is not dict or blob['inventory'].get('path') != inventory):
            raise ValueError('Original BLOB differs from its fixed root/member/inventory layout')
        return capture.blob(blob, metadata, role, cap)

    index = proof['inputs']['index']
    _, input_inv = body(index, input_root / 'body', 'Packages', 'body-inventory.json', LIMITS['packages_bytes'], 'diagnostic-body-packages')
    if (index['sha256'], index['bytes']) != FIXED_INPUTS['Packages']:
        raise ValueError('Fixed original Packages identity differs')
    expected_inputs = {'Packages', *(Path(item['filename']).name for item in PACKAGES.values())}
    if set(input_inv['files']) != expected_inputs:
        raise ValueError('Original inputbody complete root does not contain exactly the fixed four leaves')
    authentication = _fields(proof['authentication'], ('gpgv', 'decoded_release', 'signing_fingerprints', 'index_entry'), 'original authentication')
    entry = _fields(authentication['index_entry'], ('path', 'sha256', 'bytes'), 'original signed index entry')
    _integer(entry['bytes'], 'original signed index bytes', maximum=LIMITS['packages_bytes'])
    if entry != {'path': 'main/binary-amd64/Packages', 'sha256': index['sha256'], 'bytes': index['bytes']}:
        raise ValueError('Original signed index entry differs from fixed current body')
    if type(authentication['signing_fingerprints']) is not list or authentication['signing_fingerprints'] != SIGNERS:
        raise ValueError('Original proof does not record the exact three sorted signing fingerprints')

    def child(value, role):
        _fields(value, ('argv', 'environment', 'cwd', 'returncode', 'stdout', 'stderr', 'ownership', 'worker'), 'original child')
        _ownership(value['ownership'])
        expected_argv = ([programs['gpgv'], '--homedir', str(workspace / 'gnupg'), '--keyring', str(authority['keyring']),
            '--status-fd=2', '--output', '-', str(input_root / 'metadata/InRelease')] if role == 'gpgv' else
            [programs['dpkg_deb'], '--fsys-tarfile', str(input_root / 'body' / Path(PACKAGES[role]['filename']).name)])
        if (value['argv'] != expected_argv or value['environment'] != env or value['cwd'] != str(workspace)
                or type(value['returncode']) is not int or value['returncode'] != 0):
            raise ValueError('Original child command differs from fixed independent policy/layout')
        worker = _fields(value['worker'], ('packet', 'argv', 'log', 'completion', 'ownership'), 'original worker')
        _ownership(worker['ownership'])
        _completion(worker['completion'])
        packet_name = 'worker-' + role + '.json'
        expected_worker = [programs['controller'], '-I', '-B', str(sources['collector']), '--fixed-worker', role,
                           '--packet', str(observed_metadata / packet_name)]
        if worker['argv'] != expected_worker:
            raise ValueError('Original worker differs from fixed isolated source/packet argv')
        _, packet, _ = capture.document(worker['packet'], metadata, 'diagnostic-provenance-worker-packet', expected_name=packet_name)
        _schema(packet, ('schema_version', 'kind', 'role', 'producer', 'argv', 'environment', 'cwd',
            'stdout_path', 'stderr_path', 'deadline_seconds'), 'foundation-native-fixed-trixie-worker-packet-v1')
        stderr_name = 'raw/' + role + '.stderr'
        stdout_name = 'raw/gpgv.stdout' if role == 'gpgv' else role + '.tar'
        expected_packet = {'schema_version': 1, 'kind': 'foundation-native-fixed-trixie-worker-packet-v1',
            'role': role, 'producer': launch['producer'], 'argv': expected_argv, 'environment': env,
            'cwd': str(workspace), 'stdout_path': str((observed_metadata if role == 'gpgv' else opaque) / stdout_name),
            'stderr_path': str(observed_metadata / stderr_name),
            'deadline_seconds': LIMITS['gpgv_seconds' if role == 'gpgv' else 'dpkg_seconds']}
        _integer(packet['deadline_seconds'], 'original worker deadline', 1, 300)
        if packet != expected_packet:
            raise ValueError('Original worker packet differs from fixed child/raw paths/environment/deadline')
        capture.raw(worker['log'], metadata, 'diagnostic-provenance-worker-log-' + role,
                    LIMITS['worker_log_bytes'], 'raw/worker-' + role + '.log')
        _, errors = capture.raw(value['stderr'], metadata, 'diagnostic-provenance-gpgv-status-stderr' if role == 'gpgv'
            else 'diagnostic-provenance-dpkg-stderr-' + role, LIMITS['child_stderr_bytes'], stderr_name)
        if role != 'gpgv' and errors:
            raise ValueError('Successful fixed original dpkg stderr must be empty')
        if role == 'gpgv':
            capture.raw(value['stdout'], metadata, 'diagnostic-provenance-decoded-release', LIMITS['release_bytes'], stdout_name)
        else:
            _, inv = body(value['stdout'], opaque, stdout_name, 'opaque-inventory.json', LIMITS['tar_bytes'], 'diagnostic-body-member-tar-' + role)
            if set(inv['files']) != {name + '.tar' for name in ROLES}:
                raise ValueError('Original opaque complete root must contain exactly three TAR leaves')

    child(authentication['gpgv'], 'gpgv')
    if authentication['decoded_release'] != authentication['gpgv']['stdout']:
        raise ValueError('Original decoded Release alias differs from original gpgv stdout')
    _fields(proof['packages'], ROLES, 'fixed original packages')
    totals = [0, 0]
    result_packages = {}
    for role, expected in PACKAGES.items():
        item = _fields(proof['packages'][role], ('name', 'source_package', 'version', 'architecture',
            'archive', 'stanza', 'reader', 'members', 'link_origins'), 'fixed original package')
        if any(item[key] != expected[key] for key in ('name', 'source_package', 'version', 'architecture')):
            raise ValueError('Original fixed package scalar identity differs')
        blob = item['archive']
        body(blob, input_root / 'body', Path(expected['filename']).name, 'body-inventory.json', LIMITS['deb_bytes'], 'diagnostic-body-deb-' + role)
        if (blob['sha256'], blob['bytes']) != (expected['sha256'], expected['bytes']):
            raise ValueError('Original fixed package archive identity differs')
        capture.raw(item['stanza'], metadata, 'diagnostic-provenance-stanza-' + role,
                    LIMITS['stanza_bytes'], 'stanzas/' + role + '.paragraph')
        child(item['reader'], role)
        _facts(item, authority['policy']['selection'][role], totals)
        result_packages[role] = {name: item[name] for name in
            ('name', 'source_package', 'version', 'architecture', 'members', 'link_origins')}
    inventories = capture.finish()
    return {'launch': {'path': str(launch_path), 'sha256': launch_ref['sha256']},
            'proof': {'path': str(proof_path), 'sha256': proof_ref['sha256'], 'bytes': len(proof_raw), 'kind': PROOF_KIND},
            'packages': result_packages, 'external_inventories': inventories}
