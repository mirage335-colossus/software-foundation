"""Read-only reconstruction of original H2/D2-or-D3/W2/G2 dependency evidence.

Only the actual shared Origin and version issuer can establish original member
authority.  This factory creates no Workspace and launches no process.  All
current files and complete inventory trees stay held until the final readback;
the durable token is issued only after known input owners have closed.
"""
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time
import types

REQUEST_KIND = 'private-windows-retained-dependency-with-generated-inputs-v2'
RESULT_KIND = 'foundation-windows-dependency-with-probe-and-generated-inputs-v2'
MAX_DOCUMENT = 4 * 1024**2
MAX_INVENTORY = 32 * 1024**2
MAX_BODY = 256 * 1024**2
MAX_LEDGER = 4096
_PRODUCTION = {}
_UNCERTAIN = []


class AdmittedDependencyWithProbe:
    __slots__ = ()

    def __new__(cls, *args, **kwargs):
        raise ValueError('Only the actual complete retained reader issues admission')


def _owner():
    owner = globals().get('_support_source_owner')
    if type(owner) is not types.ModuleType:
        raise ValueError('Verified controller source owner required')
    return owner._require_source_child(__name__, sys.modules.get(__name__))


def _inputs():
    return _owner()._support_module('current_inputs')


def _issuer():
    """Earliest sanctioned source-provider ingress; no canonical tool preload."""
    return _inputs()._issuer()


def _source(role):
    return _owner()._support_module(role)


def _ref(value):
    return _owner()._reference(value)


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _equal(left, right, label):
    _owner()._equal(left, right, label)


def _document(raw, reference, maximum=MAX_DOCUMENT):
    return _inputs()._document(raw, reference, maximum)


def _request(value):
    w = _owner()._pure()
    w._fields(value, ('schema_version', 'kind', 'target', 'selection', 'result',
        'tool_observations', 'originals'), 'retained dependency request')
    _equal(value['schema_version'], 2, 'retained request schema')
    _equal(value['kind'], REQUEST_KIND, 'retained request kind')
    _equal(value['target'], w.TARGET, 'retained request target')
    paths = set()
    for name in ('selection', 'result', 'tool_observations', 'originals'):
        reference = _ref(value[name])
        if reference['path'].casefold() in paths:
            raise ValueError('Retained request reference aliases')
        paths.add(reference['path'].casefold())
    return copy.deepcopy(value)


def _body(value, label, *, empty=False):
    w = _owner()._pure()
    w._fields(value, ('path', 'sha256', 'bytes'), label)
    _ref({key: value[key] for key in ('path', 'sha256')})
    w._int(value['bytes'], label + ' bytes', 0 if empty else 1, MAX_BODY)
    return copy.deepcopy(value)


def _result(raw, reference):
    value = _document(raw, reference)
    w = _owner()._pure()
    w._fields(value, ('schema_version', 'kind', 'dependency_receipt',
        'probe_object_witness', 'generated_input_witness', 'references',
        'toolchain_identity', 'toolchain_identity_sha256', *w.FALSE_FACTS), 'completed dependency result')
    _equal(value['schema_version'], 2, 'completed result schema')
    _equal(value['kind'], RESULT_KIND, 'completed result kind')
    for name in ('dependency_receipt', 'probe_object_witness', 'generated_input_witness'):
        _body(value[name], name)
    w._fields(value['references'], ('inventory', 'native_inputs'), 'completed references')
    for name, row in value['references'].items():
        _body(row, name)
    _ref(value['toolchain_identity'])
    _equal(value['toolchain_identity']['sha256'], value['toolchain_identity_sha256'], 'original H2 pin')
    for name in w.FALSE_FACTS:
        if value[name] is not False:
            raise ValueError('Unqualified dependency cannot claim ' + name)
    refs = [value[name] for name in ('dependency_receipt', 'probe_object_witness',
        'generated_input_witness')] + list(value['references'].values()) + [value['toolchain_identity']]
    if len({row['path'].casefold() for row in refs}) != len(refs):
        raise ValueError('Completed dependency evidence paths alias')
    return copy.deepcopy(value)


def _deadline(value):
    if (type(value) not in (int, float) or not math.isfinite(value)
            or not 0 < value - time.monotonic() <= 86400):
        raise ValueError('Original live overall deadline required')
    return value


class _Originals:
    """One genuine Origin membership scope plus independently held current bytes."""
    def __init__(self, origin, token, lease, *, version_origin=None):
        self.origin, self.token, self.lease = origin, token, lease
        self.rows, self.bytes = {}, 0
        self.maximum = min(lease['selection']['limits']['maximum_output_bytes'], 32 * 1024**3)
        self.members = origin.require_retained_originals(token)['members']
        self.version_origin = version_origin
        self.version_members = (origin.require_retained_originals(version_origin)['members']
            if version_origin is not None else None)

    def read(self, reference, maximum=MAX_BODY, *, document=False):
        return self._read(self.token, self.members, reference, maximum, document=document)

    def read_version(self, reference, maximum=MAX_BODY, *, document=False):
        """Use V's genuine scope, without requiring a duplicated D membership."""
        if self.version_origin is None:
            raise ValueError('Genuine original V membership scope required')
        return self._read(self.version_origin, self.version_members,
            reference, maximum, document=document)

    def _read(self, token, members, reference, maximum, *, document):
        if type(maximum) is not int or not 1 <= maximum <= MAX_BODY:
            raise ValueError('Finite original body bound required')
        if (type(reference) is not dict or set(reference) not in (
                {'path', 'sha256'}, {'path', 'sha256', 'bytes'},
                {'path', 'sha256', 'bytes', 'mode'})):
            raise ValueError('Closed original body reference required')
        if 'mode' in reference and reference['mode'] != 0o644:
            raise ValueError('Original logical body mode must be 0644')
        ref = _ref({key: reference[key] for key in ('path', 'sha256')})
        self.origin.require_original_membership(token, [ref])
        member = members.get(ref['path'])
        if type(member) is not dict:
            raise ValueError('Exact original member spelling is absent')
        original = _body(member['reference'], 'original member', empty=True)
        _equal({key: original[key] for key in ('path', 'sha256')}, ref, 'original member identity')
        size = original['bytes']
        if size > maximum or document and not size:
            raise ValueError('Original member exceeds selected format bound or is empty')
        if 'bytes' in reference and (type(reference['bytes']) is not int or reference['bytes'] != size):
            raise ValueError('Declared original EOF differs from genuine member')
        old = self.rows.get(ref['path'].casefold())
        if old is None:
            if len(self.rows) >= MAX_LEDGER or size > self.maximum - self.bytes:
                raise ValueError('Original ledger count/aggregate byte budget exhausted before read')
        else:
            _equal(old, original, 'original body spelling/pin/EOF')
        # Supply the genuine original EOF before acquiring/cache-allocating the
        # body. A zero-byte member uses one byte of bounded EOF lookahead only.
        raw = self.lease['held'].read_ref(original, max(1, size))
        if type(raw) is not bytes or len(raw) > maximum or _sha(raw) != ref['sha256']:
            raise ValueError('Current original body differs')
        if 'bytes' in reference and reference['bytes'] != len(raw):
            raise ValueError('Original EOF differs from retained member')
        if document and not raw:
            raise ValueError('Original metadata document is empty')
        row = dict(ref, bytes=len(raw))
        if old is None:
            self.bytes += len(raw)
            self.rows[ref['path'].casefold()] = row
        self.origin.require_original_membership(token, [row])
        return raw

    def read_maintained_source(self, reference):
        """The fixed maintained Source is bound by code, not a D data scope."""
        _equal(reference, self.lease['request']['maintained_source'], 'original maintained Source ref')
        _equal(reference['sha256'], _owner()._pure().SOURCE_SHA256, 'fixed maintained probe Source')
        ref = _ref(reference)
        old = self.rows.get(ref['path'].casefold())
        if old is None and (len(self.rows) >= MAX_LEDGER or self.maximum - self.bytes < 65536):
            raise ValueError('Original ledger budget exhausted before fixed Source read')
        raw = self.lease['held'].read_ref(ref, 65536)
        if type(raw) is not bytes or not raw or _sha(raw) != ref['sha256']:
            raise ValueError('Actual fixed maintained Source differs')
        row = dict(ref, bytes=len(raw))
        if old is None:
            self.bytes += len(raw)
            self.rows[ref['path'].casefold()] = row
        else:
            _equal(old, row, 'same original fixed Source bytes')
        return raw

    def ledger(self):
        return copy.deepcopy(sorted(self.rows.values(), key=lambda row: row['path'].casefold()))


def _phase_evidence(receipt, originals, limits):
    """Join original logs and source-owned resource ceilings, without executing."""
    c = _owner()
    for command in receipt['commands']:
        if command['stage'] not in c.PHASES:
            raise ValueError('Unregistered retained stage')
        _, key = c.PHASES[command['stage']]
        job = command['job']
        if (job['wall_limit_milliseconds'] > limits[key] * 1000
                or job['process_limit'] != limits['maximum_processes']
                or job['output_limit_bytes'] != limits['maximum_output_bytes']):
            raise ValueError('Original Job exceeds independently selected stage policy')
        originals.read(command['logs']['combined'], min(MAX_BODY, limits['maximum_log_bytes']))


def _runtime_member(originals, reference, maximum):
    """Describe a D member and its exact EOF before any runtime body read."""
    ref = _ref(reference)
    originals.origin.require_original_membership(originals.token, [ref])
    member = originals.members.get(ref['path'])
    if type(member) is not dict:
        raise ValueError('Exact produced-runtime D member is absent')
    row = _body(member['reference'], 'original produced-runtime member')
    _equal({key: row[key] for key in ('path', 'sha256')}, ref, 'original runtime D member identity')
    _owner()._pure()._int(row['bytes'], 'original produced-runtime image bytes', 64, maximum)
    old = originals.rows.get(ref['path'].casefold())
    if old is not None:
        _equal(old, row, 'same original produced-runtime member')
    return row


def _runtime_read_budget(originals, rows):
    """Reserve no authority; reject an impossible selected read batch early."""
    unique = {}
    for row in rows:
        key = row['path'].casefold()
        previous = unique.setdefault(key, row)
        _equal(previous, row, 'produced-runtime batch path spelling/pin/EOF')
    new = [row for key, row in unique.items() if key not in originals.rows]
    if (len(new) > MAX_LEDGER - len(originals.rows)
            or sum(row['bytes'] for row in new) > originals.maximum - originals.bytes):
        raise ValueError('Original runtime ledger count/aggregate budget exhausted before body reads')


def _runtime_parent_tree(snapshot, workspace, program_parent):
    """Project the complete historical executable directory, including data."""
    _owner()._pure()._path(program_parent)
    if not program_parent.startswith(workspace + '/'):
        raise ValueError('Original produced-runtime parent must be inside its Workspace')
    member = program_parent[len(workspace) + 1:]
    if member not in snapshot['directories']:
        raise ValueError('Original producer snapshot lacks its executable directory')
    prefix = member + '/'
    return {'root': program_parent,
        'files': {name[len(prefix):]: {key: row[key] for key in ('sha256', 'bytes')}
            for name, row in snapshot['files'].items() if name.startswith(prefix)},
        'directories': [name[len(prefix):] for name in snapshot['directories'] if name.startswith(prefix)]}


def _hold_runtime_parent(lease, tree):
    """Hold exact current membership; additions since the snapshot reject."""
    old = lease['held'].trees.get(tree['root'].casefold())
    if old is None:
        lease['held'].hold_tree(tree)
    else:
        previous = {key: old['inventory'][key] for key in ('root', 'files', 'directories')}
        encode = _source('supplier_factory_contract_base')._source_encoded
        if encode(previous) != encode(tree):
            raise ValueError('Original produced-runtime directory differs from another complete held snapshot')
        old['owner'].check()


def _produced_runtime_evidence(receipt, originals, factory):
    """Reconstruct original runtime bytes; no document or dictionary is a cap.

    The supported layout keeps the executable directory's entire membership
    unchanged since its producer snapshot. Later additions there reject, even
    when they are another executable. Other original directory files are held
    from that snapshot; selected PE/document/snapshot bodies also require D
    membership and enter the original ledger. An empty graph reads nothing.
    """
    c = _owner()
    policy, lease = _source('producer')._factory(factory)
    if (lease is not originals.lease or policy['context'] is not None
            or policy['source_mode'] != 'retained-read-only'):
        raise ValueError('Same genuine read-only runtime reconstruction owners required')
    registered, runtime_policies = policy['registration']['produced_tools'], policy['produced_runtime_policies']
    if type(runtime_policies) is not dict or set(runtime_policies) != set(registered):
        raise ValueError('Exact independent produced-runtime Source roles required')
    if not registered:
        return
    if len(registered) > 128:
        raise ValueError('Finite original produced-runtime role count required')
    commands = {row['id']: row for row in receipt['commands']}
    workspace = lease['selection']['output']
    historical = lease['version_selection']['publication']['runtime_identity']
    system = {'root': historical['system_root'], 'windows_version': copy.deepcopy(historical['windows_version'])}
    snapshots = {}
    for role, recipe in registered.items():
        command = commands[recipe['producing_command_id']]
        produced = command['produced_outputs'][recipe['output']]
        c._pure()._fields(produced, ('role', 'program', 'inspection_subject_sha256',
            'runtime_subject_sha256'), 'original produced-runtime observation')
        _equal(produced['role'], role, 'independent original produced-runtime role')
        program = _ref(produced['program'])
        _equal(program['path'], recipe['root'] + '/' + recipe['output'], 'Source-fixed original produced program path')
        source_policy = runtime_policies[role]
        layout = c._runtime_layout(program, source_policy, producer_root=recipe['root'])
        snapshot_ref = {'path': workspace + '/metadata/stage-output/' + command['id'] + '.json',
            'sha256': command['output_subject_sha256']}
        previous = snapshots.get(snapshot_ref['path'])
        if previous is None:
            raw = originals.read(snapshot_ref, MAX_INVENTORY, document=True)
            snapshot = _source('generated_inputs')._snapshot_document(raw, snapshot_ref['sha256'], workspace)
            snapshots[snapshot_ref['path']] = {'reference': snapshot_ref, 'value': snapshot}
        else:
            _equal(previous['reference'], snapshot_ref, 'same original runtime producer snapshot')
            snapshot = previous['value']
        maximum_output = lease['selection']['limits']['maximum_output_bytes']
        if snapshot['bytes'] > maximum_output:
            raise ValueError('Original runtime producer snapshot exceeds its independently selected Job output limit')
        program_member = snapshot['files'].get(program['path'][len(workspace) + 1:])
        if (type(program_member) is not dict or program_member.get('kind') != 'file'
                or program_member['sha256'] != program['sha256']):
            raise ValueError('Actual produced program is absent from its original producer snapshot')
        program_body = _runtime_member(originals, program, c.MAX_RUNTIME_BYTES)
        _equal(program_body['bytes'], program_member['bytes'], 'original producer program EOF')
        selected, total = {}, program_body['bytes']
        for name, path in layout.items():
            member = snapshot['files'].get(path[len(workspace) + 1:])
            if type(member) is not dict or member.get('kind') != 'file':
                raise ValueError('Original produced-runtime DLL is absent from its producer snapshot')
            ref = _ref({'path': path, 'sha256': member['sha256']})
            row = _runtime_member(originals, ref, c.MAX_RUNTIME_DLL_BYTES)
            _equal(row['bytes'], member['bytes'], 'original producer DLL EOF')
            total += row['bytes']
            if total > c.MAX_RUNTIME_BYTES:
                raise ValueError('Original produced-runtime aggregate image byte bound exceeded')
            selected[name] = row
        _runtime_read_budget(originals, [program_body, *selected.values()])
        parent = program['path'].rsplit('/', 1)[0]
        tree = _runtime_parent_tree(snapshot, workspace, parent)
        if sum(row['bytes'] for row in tree['files'].values()) > maximum_output:
            raise ValueError('Original runtime directory exceeds its independently selected Job output limit')
        actual_dlls = {name for name in tree['files'] if '/' not in name and name.casefold().endswith('.dll')}
        expected_dlls = {path[len(parent) + 1:] for path in layout.values()}
        if (actual_dlls != expected_dlls
                or any(name.casefold() in c._native_inspection().SYSTEM_IMPORTS for name in actual_dlls)):
            raise ValueError('Original sibling DLL membership differs or shadows an OS import')
        _hold_runtime_parent(lease, tree)
        program_raw = originals.read(program_body, c.MAX_RUNTIME_BYTES)
        libraries = {name: {'reference': {key: row[key] for key in ('path', 'sha256')},
            'raw': originals.read(row, c.MAX_RUNTIME_DLL_BYTES)} for name, row in selected.items()}
        value = c._runtime_document(program, source_policy, program_raw, libraries,
            system, producer_root=recipe['root'])
        _equal(value['inspection_subjects']['program'], produced['inspection_subject_sha256'],
            'original actual produced executable inspection')
        runtime_raw = c._pure().encoded(value)
        _equal(_sha(runtime_raw), produced['runtime_subject_sha256'], 'original actual produced runtime subject')
        document = {'path': workspace + '/metadata/produced-runtime/' + role + '.json',
            'sha256': produced['runtime_subject_sha256']}
        if originals.read(document, MAX_DOCUMENT, document=True) != runtime_raw:
            raise ValueError('Original produced runtime document differs from independently reconstructed bytes')
        lease['held'].check()


def _probe_limits(witness, limits):
    job = witness['command']['job']
    wall = job.get('wall_limit_milliseconds')
    _owner()._pure()._int(wall, 'original compile wall limit', 1,
        limits['probe_seconds'] * 1000)
    return {'wall_milliseconds': wall, 'maximum_processes': limits['maximum_processes'],
        'maximum_output_bytes': min(65536 + 4 * 1024**2 + 1024**2, limits['maximum_output_bytes']),
        'maximum_log_bytes': min(1024**2, limits['maximum_log_bytes'])}


def _expected_for_kind(factory, prefix_facts, output, tag):
    expected = _source('producer')._complete_expected(factory, prefix_facts, output)
    if tag == (3, 'foundation-native-engine-windows-dependencies-build-v3'):
        return expected
    if tag == (2, 'foundation-native-engine-windows-dependencies-build-v2'):
        # The old strict parser receives its original seven-field expectation.
        # No original D bytes, command or environment is rewritten.
        return {key: value for key, value in expected.items() if key != 'nmake_runtime'}
    raise ValueError('Original D2 or D3 kind is required')


def require_retained_dependency_with_probe(value):
    if type(value) is not AdmittedDependencyWithProbe or value not in _PRODUCTION:
        raise ValueError('Actual completed opaque retained dependency admission required')
    return json.loads(_PRODUCTION[value])


def admit_retained_dependency_with_probe(request_ref, *, overall_deadline):
    """Reconstruct originals/current native inputs; never build as a fallback."""
    deadline = _deadline(overall_deadline)
    _ref(request_ref)
    if os.name != 'nt':
        raise _inputs().MissingInputs(('windows-dependency-native-windows-host',))
    request_raw, request = _inputs()._bootstrap(request_ref)
    request = _request(request)
    result_raw, _ = _inputs()._bootstrap(request['result'])
    result = _result(result_raw, request['result'])
    # Known incomplete source routes stop before any native factory or data tree.
    gaps = _source('producer').source_gaps()
    if gaps:
        raise _owner().MissingSource(gaps)
    issuer = _issuer()
    limits = _source('selection').input_limits(deadline, time.monotonic())
    versions = issuer.admit_retained_observed_versions(request['tool_observations'],
        deadline=deadline, limits=limits)
    _, observation_request = _inputs()._bootstrap(request['tool_observations'])
    origin_module = issuer.originals_module()
    if observation_request['originals'] == request['originals']:
        origin = issuer.require_observed_origin(versions, request['originals'])
    else:
        origin = origin_module.admit_retained_originals(request['originals'],
            deadline=deadline, limits=limits)
    native = None
    try:
        native = _inputs().admit_current_inputs(request['selection'], versions,
            deadline=deadline, originals=origin,
            version_origin_ref=observation_request['originals'])
        lease = _inputs()._lease_for_controller(native)
        version_origin = issuer.require_observed_origin(versions, observation_request['originals'])
        originals = _Originals(origin_module, origin, lease, version_origin=version_origin)
        originals.read(request['selection'], MAX_DOCUMENT, document=True)
        originals.read(lease['request']['dependency_selection'], MAX_DOCUMENT, document=True)
        # V retains its own historical authority; D independently keeps all
        # original V bodies held through its final success and close.
        for reference in lease['original_references']:
            originals.read_version(reference)
        originals.read_version(lease['request']['version_selection'], MAX_DOCUMENT, document=True)
        # The new top-level request_ref selector need not be historical. Its
        # selection field names the original executed producer request, whose
        # membership and every selected original are required independently.
        if originals.read(request['result'], MAX_DOCUMENT, document=True) != result_raw:
            raise ValueError('Completed result changed before anchored readback')
        origin_module.require_original_membership(origin, [request['selection']])
        sources = _source('source_inputs').admit_source_declarations(native)
        factory = _source('producer')._fixed_policy(native, sources,
            request_ref=request['selection'])
        policy = _owner()._NATIVE_FACTORIES[factory]
        _equal(result['toolchain_identity'], lease['selection']['toolchain_identity'], 'original H2 reference')
        _equal(result['toolchain_identity_sha256'], _sha(lease['identity_raw']), 'actual original H2')
        originals.read_version(result['toolchain_identity'], MAX_DOCUMENT, document=True)
        plan = policy['expected']['bindings']['plan']
        if originals.read(plan, MAX_DOCUMENT, document=True) != _owner()._pure().encoded(policy['plan']):
            raise ValueError('Original fixed plan differs from independently derived plan')
        inventory_ref = result['references']['inventory']
        inventory_raw = originals.read(inventory_ref, MAX_INVENTORY, document=True)
        inventory_doc = _document(inventory_raw, inventory_ref, MAX_INVENTORY)
        provenance_ref = inventory_doc['provenance']
        provenance_raw = originals.read(provenance_ref, MAX_INVENTORY, document=True)
        inventory = _inputs().inventory_declaration(inventory_raw, inventory_ref['sha256'],
            'native_dependencies', provenance_raw=provenance_raw,
            provenance_pin=provenance_ref['sha256'])
        provenance = _document(provenance_raw, provenance_ref, MAX_INVENTORY)
        _equal(provenance['original_reports'], [{key: result[name][key]
            for key in ('path', 'sha256')} for name in ('dependency_receipt',
                'probe_object_witness', 'generated_input_witness')], 'same completed D/W/G provenance bundle')
        _equal(provenance['sources'], [{key: row['archive'][key] for key in ('path', 'sha256')}
            for supplier, row in sorted(policy['expected']['bindings']['sources'].items())],
            'same independently admitted source archives')
        _equal(provenance['notices'], policy['notice_refs'], 'same source-owned installed notices')
        policy['prefix_inventory'] = {key: copy.deepcopy(inventory_doc[key])
            for key in inventory_doc if key != 'provenance'}
        prefix_facts = _source('library_interfaces').inspect_retained_prefix(native, factory, inventory)
        d_ref = result['dependency_receipt']
        d_raw = originals.read(d_ref, MAX_DOCUMENT, document=True)
        declaration = _document(d_raw, d_ref)
        output = declaration['probe']['output']
        fixed_output = lease['selection']['output'] + '/probe/static-closure-probe.exe'
        _equal(output['path'], fixed_output, 'fixed original probe executable path')
        probe_raw = originals.read(output, MAX_BODY)
        image = _owner()._native_inspection().inspect_tool_image(probe_raw)
        if image.get('format') != 'pe32plus' or image.get('machine') != 'x86_64' or image.get('dll') is not False:
            raise ValueError('Original linked probe is not an AMD64 executable')
        expected = _expected_for_kind(factory, prefix_facts,
            {'path': fixed_output, 'sha256': _sha(probe_raw)},
            (declaration.get('schema_version'), declaration.get('kind')))
        if declaration['schema_version'] == 3:
            receipt = _owner()._proof_module().validate_dependency_receipt(
                d_raw, d_ref['sha256'], expected, lease['identity'])
        else:
            receipt = _inputs()._proof().validate_dependency_receipt(
                d_raw, d_ref['sha256'], expected, lease['identity'])
        _phase_evidence(receipt, originals, lease['selection']['limits'])
        _produced_runtime_evidence(receipt, originals, factory)
        w_ref = result['probe_object_witness']
        w_raw = originals.read(w_ref, MAX_DOCUMENT, document=True)
        witness = _document(w_raw, w_ref)
        source = witness['source']
        maintained = lease['request']['maintained_source']
        maintained_raw = originals.read_maintained_source(maintained)
        compiled_raw = originals.read(source['compiled'], 65536)
        object_raw = originals.read(witness['object'], 4 * 1024**2)
        log_raw = originals.read(witness['command']['logs']['combined'], 1024**2)
        _owner()._witness_module().validate_witness(w_raw, w_ref['sha256'],
            identity_raw=lease['identity_raw'], identity_pin=result['toolchain_identity_sha256'],
            dependency_raw=d_raw, dependency_pin=d_ref['sha256'], dependency_path=d_ref['path'],
            expected=expected, maintained_source_raw=maintained_raw, compiled_source_raw=compiled_raw,
            object_raw=object_raw, log_raw=log_raw, maintained_source_path=maintained['path'],
            workspace_root=lease['selection']['output'],
            limits=_probe_limits(witness, lease['selection']['limits']))
        g_ref = result['generated_input_witness']
        g_raw = originals.read(g_ref, MAX_DOCUMENT, document=True)
        generated = _document(g_raw, g_ref)
        snapshots, outputs = {}, {}
        for binding in generated['bindings']:
            for key, destination in (('producer_snapshot', snapshots), ('output', outputs)):
                ref = binding[key]
                destination[ref['path']] = originals.read(ref, MAX_INVENTORY)
        _source('generated_inputs').validate_witness(g_raw, g_ref['sha256'],
            identity_raw=lease['identity_raw'], identity_pin=result['toolchain_identity_sha256'],
            dependency_raw=d_raw, dependency_pin=d_ref['sha256'], dependency_path=d_ref['path'],
            expected=expected, generated_inputs=policy['generated_inputs'],
            workspace_root=lease['selection']['output'], snapshots=snapshots, outputs=outputs)
        native_ref = result['references']['native_inputs']
        native_raw = originals.read(native_ref, MAX_DOCUMENT, document=True)
        actual_native = _source('selection')._contract().validate_inputs(_document(native_raw, native_ref))
        expected_native = _source('selection').native_input_declaration(lease['identity'],
            lease['selection']['inventories'], prefix_facts['prefix']['root'],
            {key: inventory_ref[key] for key in ('path', 'sha256')}, prefix_facts['libraries'])
        _equal(actual_native, expected_native, 'original exact native-input publication')
        _inputs().require_current_inputs(native)
        _source('source_inputs').require_sources(sources)
        ledger = originals.ledger()
        summary = copy.deepcopy(result)
        summary['result'] = {'path': request['result']['path'],
            'sha256': request['result']['sha256'], 'bytes': len(result_raw)}
        summary['original_references'] = ledger
        lease['held'].check()
        _inputs().close_current_inputs(native)
        if not lease['held'].closed or any(not owner.closed or owner.uncertain for owner in lease['held'].owners):
            raise ValueError('All original retained readers must close before admission')
        _deadline(deadline)
        token = object.__new__(AdmittedDependencyWithProbe)
        _PRODUCTION[token] = _owner()._pure().encoded(summary)
        return token
    except BaseException as error:
        if native is not None:
            try:
                state = _inputs()._ISSUED[native]
                if not state['closed']:
                    _inputs().close_current_inputs(native)
            except BaseException as cleanup:
                _UNCERTAIN.append((native, type(error).__name__, str(error), cleanup))
        raise
