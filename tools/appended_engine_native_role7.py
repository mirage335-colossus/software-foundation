"""Finite passive ROLE7-v2 joins. No collector, live capture or program call."""
from pathlib import Path

from role7 import common, capture, observer, os_origins

KIND = 'foundation-retained-diagnostic-host-original-proof-provenance-v2'
SOURCE_PINS = {
    'common.py': '3d7e89aa7afde5e2f2ecd047dac1dddd71e0521350979b0536e3e1a6bd2ddb43',
    'observer.py': 'c2fcd66af150d82b42953097110deafe90f68365b0d5bdece33c84f00ae4b770',
    'capture.py': '1c8eb9c2f173097fd0ef3d8268d1fdfe55e64470c1122e828adef64c3cf8e29b',
    'os_origins.py': 'c17058ab87a7f325610f44fd1df5acac1581495fbd153103a84de973c2e36819',
    '__init__.py': 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
}
capture._COMMON = observer._COMMON = common
capture._OBSERVER = observer


def _missing(data, role, reason, path=''):
    raise data.MissingInputs([dict(role=role, path=str(path), reason=reason)])


def source_files(data, inputs, repository_root):
    """Join the actual imported fixed modules before any submitted v2 bodies."""
    root = data._diagnostic_absolute(repository_root)
    modules = {'common.py': common, 'observer.py': observer,
               'capture.py': capture, 'os_origins.py': os_origins}
    for name, digest in SOURCE_PINS.items():
        path = root / 'tools/role7' / name
        if name in modules and str(path) != modules[name].__file__:
            raise ValueError('ROLE7 fixed import differs from exact retained source path')
        raw = data._producer_bytes(inputs, path, 'diagnostic-provenance-role7-producer-' + name, root)
        if data.sha256(raw) != digest:
            raise ValueError('ROLE7 fixed passive source bytes changed: ' + name)


def _original_source(data, inputs, path, digest, size, repository_root):
    # These are source identities from an independently pinned finite closure,
    # not SDK/program/runtime bodies or a submitted import instruction.
    path = data._diagnostic_absolute(path)
    if path == common.ROOT / 'tools/process_tree.py':
        # The same source may already be captured by native admission. Reuse
        # its maintained producer authority; the original closure pin below
        # still fixes the exact historical supervisor body and extent.
        raw = data._producer_bytes(inputs, path,
            'diagnostic-provenance-role7-original-supervisor', common.ROOT)
    else:
        record = data._diagnostic_capture(inputs, path, digest, 'diagnostic-provenance-role7-source', maximum=131072)
        raw = inputs.bytes(path, maximum=131072)
        if record['mode'] != 0o644:
            raise ValueError('Retained original ROLE7 source must be ordinary0644')
    if len(raw) != size or data.sha256(raw) != digest:
        raise ValueError('Retained original ROLE7 source closure bytes differ')


def records(data, wrapper, base, inputs, authority, *, repository_root):
    """Consume original pinned DATA only; never construct a BridgeCapture."""
    data._schema(wrapper, ('schema_version', 'kind', 'scope', 'original_proof', 'derived_files',
        'operating_system_providers', 'os_original', 'role7_launch'), KIND)
    if wrapper['scope'] != data.DIAGNOSTIC_HOST_SCOPE:
        raise ValueError('ROLE7 provenance scope differs')
    if common.FIXED_INPUT_SHA256 is None or common.FIXED_POLICY_SHA256 is None:
        _missing(data, 'diagnostic-role7-fixed-input-authority', 'Independent source-installed ROLE7 input/policy pins absent')
    data.pin(common.FIXED_INPUT_SHA256); data.pin(common.FIXED_POLICY_SHA256)
    if authority.launch_policy_sha256 != common.FIXED_POLICY_SHA256:
        raise ValueError('ROLE7 original launch policy differs from source-installed approval')
    data._diagnostic_authored_source('observer', SOURCE_PINS['observer.py'], Path(repository_root) / 'tools/role7/observer.py')
    source_files(data, inputs, repository_root)
    launch_ref, launch = data._diagnostic_document(wrapper['role7_launch'], base, inputs, 'diagnostic-provenance-role7-launch')
    data._schema(launch, ('schema_version', 'kind', 'scope', 'source_closure_sha256', 'launch_policy_sha256',
        'fixed_input', 'commands', 'readiness', 'ownership', 'production_eligible', 'native_engine_execution', 'kernel_rebuild'),
        'foundation-native-diagnostic-role7-launch-v1')
    if (launch['scope'] != 'original-eight-command-role7-observation-only'
            or launch['source_closure_sha256'] != authority.source_closure_sha256
            or launch['launch_policy_sha256'] != authority.launch_policy_sha256
            or any(launch[name] is not False for name in ('production_eligible', 'native_engine_execution', 'kernel_rebuild'))):
        raise ValueError('Original ROLE7 launch/source/policy/ineligible facts differ')
    data._diagnostic_ownership(launch['ownership'])
    data._fields(launch['fixed_input'], ('path', 'sha256'), 'Original ROLE7 fixed input')
    input_path = data._diagnostic_absolute(launch['fixed_input']['path'])
    if input_path.name != 'role7-input.json' or launch['fixed_input']['sha256'] != common.FIXED_INPUT_SHA256:
        raise ValueError('Original ROLE7 fixed input differs from independent source pin')
    def original_doc(path, digest, role):
        raw = data._diagnostic_capture(inputs, path, digest, role, maximum=65536)
        if raw['mode'] != 0o644:
            raise ValueError('Original ROLE7 metadata must be ordinary0644')
        return data.strict_json(inputs.bytes(path, maximum=65536))
    fixed = common.validate_fixed_input(original_doc(input_path, common.FIXED_INPUT_SHA256, 'diagnostic-provenance-role7-fixed-input'))
    policy = original_doc(input_path.parent / 'role7-launch-policy.json', authority.launch_policy_sha256, 'diagnostic-provenance-role7-policy')
    common.validate_policy(policy, fixed, observer.schedules())
    if str(Path(launch_ref['path']).parent) != policy['workspace_root']:
        raise ValueError('Original ROLE7 launch root differs from original policy')
    closure = original_doc(input_path.parent / 'role7-source-closure.json', authority.source_closure_sha256, 'diagnostic-provenance-role7-source-closure')
    data._schema(closure, ('schema_version', 'kind', 'files'), 'foundation-native-role7-source-closure-v1')
    data._fields(closure['files'], ('common.py', 'observer.py', 'capture.py', 'process_tree.py'), 'Original four ROLE7 sources')
    for name, item in closure['files'].items():
        data._fields(item, ('path', 'sha256', 'bytes'), 'Original ROLE7 source identity')
        expected = common.ROOT / 'tools/process_tree.py' if name == 'process_tree.py' else input_path.parent / name
        digest = common.TREE_SHA256 if name == 'process_tree.py' else SOURCE_PINS[name]
        data.manifest.integer(item['bytes'], 'Original ROLE7 source bytes', 1, 131072)
        if item['path'] != str(expected) or item['sha256'] != digest:
            raise ValueError('Original ROLE7 source closure differs from exact approved source/path')
        _original_source(data, inputs, expected, digest, item['bytes'], repository_root)
    try:
        os_data = os_origins.consume_original_os_manifest(wrapper['os_original'], base, inputs,
            approved_manifest_sha256=authority.os_manifest_sha256,
            approved_original_record_sha256=authority.os_original_record_sha256)
        capture.require_os_origins(os_data, policy, fixed)
    except (os_origins.MissingInputs, common.MissingInputs) as error:
        raise data.MissingInputs(error.missing) from error
    except common.UnsupportedReadiness as error:
        _missing(data, 'diagnostic-role7-readiness', str(error))
    commands = {}; readiness = {}; root = Path(policy['workspace_root'])
    for group in ('commands', 'readiness'):
        data._fields(launch[group], ('host', 'subjects'), 'Original ROLE7 ' + group)
        data._fields(launch[group]['subjects'], common.ROLES, 'Original seven ROLE7 ' + group)
        for role in ('host', *common.ROLES):
            ref = launch[group]['host'] if role == 'host' else launch[group]['subjects'][role]
            _, value = data._diagnostic_document(ref, root, inputs, 'diagnostic-provenance-role7-' + group + '-' + role)
            (commands if group == 'commands' else readiness)[role] = value
    inputs.check_deadline()
    return dict(launch_ref=launch_ref, launch=launch, fixed=fixed, policy=policy,
                os=os_data, root=str(root), commands=commands, readiness=readiness)


def preflight(data, value, base, inputs, toolchain, authority, provenance_ref, wrapper, *, repository_root):
    # Same existing original proof mechanism, exactly once. Retained v2 data does
    # not become actual live capture or a reason to execute the collector.
    data._diagnostic_role7_authority()
    records(data, wrapper, Path(provenance_ref['path']).parent, inputs,
            data._diagnostic_role7_authority(), repository_root=repository_root)
    roots = [item['root'] for item in toolchain['inventories'].values()]
    original = data._diagnostic_original(wrapper['original_proof'], Path(provenance_ref['path']).parent,
        data._DiagnosticProofCapture(inputs, roots), authority, repository_root=repository_root)
    external = data._diagnostic_original_result(original, wrapper, Path(provenance_ref['path']).parent)
    for item in data._diagnostic_map(value['module_inventories'], 'ROLE7 host extensions').values():
        data._fields(item, ('root', 'inventory'), 'ROLE7 host extension')
        root = data._diagnostic_absolute(item['root']); ref = data._diagnostic_reference(item['inventory'], base)
        for old in external:
            prior = Path(old['root'])
            if root == prior or root in prior.parents or prior in root.parents:
                if root != prior or ref['sha256'] != old['inventory']['sha256']:
                    raise ValueError('ROLE7 host extension contradicts original complete root')
    payload = data.encoded(dict(provenance_ref=provenance_ref, wrapper=wrapper, original=original))
    if len(payload) > data.MAX_DOCUMENT:
        raise ValueError('ROLE7 immutable preflight metadata exceeds document bound')
    return data._DiagnosticHostPreflight(inputs, str(base), str(repository_root), data.sha256(data.encoded(value)),
        data._diagnostic_toolchain_identity(toolchain), authority, payload)


def origins(data, wrapper, base, inputs, combined, sdk, packages, role7_records):
    # Exact OS-original extension of the already reviewed bridge. Every other
    # SDK/package/derived branch remains the maintained canonical implementation.
    os_files = role7_records['os']['files']
    class Origins(data._DiagnosticOrigins):
        def origin(self, value):
            if type(value) is dict and value.get('kind') == 'os-original':
                data._fields(value, ('kind', 'id'), 'Original OS origin')
                name = data._diagnostic_name(value['id'], 'Original OS ID')
                if name not in os_files:
                    _missing(data, 'diagnostic-original-os-member', 'Exact approved OS member absent', name)
                original = os_files[name]
                actual = data._diagnostic_capture(inputs, Path(original['resolved_path']), original['sha256'], 'diagnostic-body-os-origin')
                data._diagnostic_same_file(actual, original)
                return dict(original, path=original['resolved_path'], terminal='os-original', os_id=name)
            return super().origin(value)
        def match(self, retained, origin, role, observed=None):
            actual = self.origin(origin)
            if actual['terminal'] != 'os-original':
                return super().match(retained, origin, role, observed)
            data._diagnostic_same_file(retained, actual)
            if observed != (actual['logical_path'], actual['resolved_path']):
                raise ValueError('Observed OS logical/resolved paths differ from approved original alias facts')
            return actual
    return Origins(wrapper, base, inputs, combined, sdk, packages)


def validate(data, observed, observed_base, wrapper, provenance_base, inputs, host, toolchain, origins, role7_records):
    """Join rebased candidate data to the pinned originals, without live reads."""
    r = role7_records; fixed = r['fixed']; root = Path(r['root'])
    if fixed['programs'] != host['programs'] or r['launch']['ownership'] != observed['ownership']:
        raise ValueError('Retained ROLE7 programs/ownership differ from admitted original observations')
    for role in common.INTERPRETERS:
        if fixed['interpreter_paths'][role] != host['interpreter_runtimes'][role]['search_paths']:
            raise ValueError('Retained ROLE7 interpreter paths differ from complete host facts')
    env = data._diagnostic_environment(toolchain, host)
    if env != r['policy']['environment']:
        raise ValueError('Retained ROLE7 environment differs from original policy and admitted tools')
    observer_record = origins.resolve('observer')
    original_observer = Path(r['launch']['fixed_input']['path']).parent / 'observer.py'
    if observer_record['path'] != str(original_observer) or observer_record['sha256'] != SOURCE_PINS['observer.py']:
        raise ValueError('Retained ROLE7 collector path/body differs from original source closure')
    values = observed['runtime']; providers = values['providers']; modules = values['modules']
    for role in ('host', *common.ROLES):
        candidate = observed['commands']['host'] if role == 'host' else observed['commands']['subjects'][role]
        original = r['commands'][role]
        for key in ('argv', 'environment', 'cwd', 'returncode', 'started_utc', 'finished_utc', 'ownership'):
            if data.encoded(candidate[key]) != data.encoded(original[key]):
                raise ValueError('Rebased ROLE7 COMMAND changed original ' + key)
        for stream in ('stdout', 'stderr'):
            if data._diagnostic_reference(candidate[stream], observed_base) != data._diagnostic_reference(original[stream], root):
                raise ValueError('Rebased ROLE7 raw stream differs from original target/hash')
        argv = [host['programs']['python']['path'], '-I', '-B', str(original_observer)]
        argv += ['--observe-host'] if role == 'host' else ['--observe-subject', role, '--program', host['programs'][role]['path']]
        raw, _, _ = data._diagnostic_command(original, argv, env, root, inputs, 'retained-role7-' + role)
        ready = capture.validate_readiness(role, r['readiness'][role], fixed, observer.schedules())
        if original['cwd'] != str(root / role):
            raise ValueError('Retained ROLE7 command cwd differs from fixed subject directory')
        capture.validate_raw(role, raw, fixed)
        if role == 'host':
            paths = sorted({*fixed['os_provider_paths'].values(), fixed['programs']['python']['path']})
            if not set(paths) <= set(ready['loaded_provider_paths']):
                raise ValueError('Original host readiness omits exact libc/loader/controller footprint')
            continue
        for key in ('search_paths', 'loaded_module_paths', 'loaded_provider_paths'):
            if ready[key] != raw[key]:
                raise ValueError('Original ROLE7 stdout and held readiness footprints differ')
        loaded = values['loaded_by_subject'][role]
        selected = [providers[name] for name in loaded['providers']]
        selected += [modules[role][name] for name in loaded['modules']] if role in modules else []
        for index, item in enumerate(selected):
            physical = ready['loaded_file_identities'][item['resolved_path']]['file_identity']
            retained = data._diagnostic_retained_file(item['retained'], origins.combined, inputs,
                'diagnostic-body-provider' if index < len(loaded['providers']) else 'diagnostic-body-module')
            if retained['bytes'] != physical[4] or retained['mode'] != physical[2] & 0o777:
                raise ValueError('Original held physical size/mode differs from captured retained bytes')
    if data._diagnostic_reference(observed['host']['os_release'], observed_base) != dict(
            path=str(root / 'host/os-release.raw'), sha256=fixed['os_release']['sha256']):
        raise ValueError('Retained ROLE7 os-release differs from original fixed input pin')
    inputs.check_deadline()
