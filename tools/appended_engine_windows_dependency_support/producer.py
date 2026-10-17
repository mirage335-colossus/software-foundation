"""Source-owned fresh V -> D3/W2/G2 composition, without caller factories.

Planning reads bounded request/selection metadata only. Native production keeps
one original deadline, one genuine A instance and the Core-owned registries.
Unknown supplier/interface methods stop before collection or output creation.
"""
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import sys
import time
import types


PLAN_KIND = 'foundation-windows-dependency-probe-production-plan-v2'
RESULT_KIND = 'foundation-windows-dependency-with-probe-and-generated-inputs-v2'
RECIPE = 'recipes/webkitwasm-native-deps-windows-x86_64-v1'
PROFILE_SHA256 = '14b73b412dab26015fdec17027e29526cfc35f1b9f377a675333257b75860ada'
TEMPLATE_SHA256 = '5461a349b2f16b1cb4fadb87b8714d86eca790206ae8b44d93ef9403f50256a7'
MAX_DOCUMENT = 4 * 1024**2
MAX_SOURCE = 256 * 1024
SDK_INSPECTION_GAP = 'windows-dependency-sdk-system-import-inspection-source'
# Reviewed pure-family postimages and their non-family pure dependencies.
# Runtime never reads the development manifest that recorded these identities.
PURE_SOURCES = {
    'admission.py': 'b4ed8350ad0efb2cac897973a784f9a98b93b47e533ded96e2d80edb162c23e3',
    'builtins/builtins_protocol.py': 'c334b013d3fcc024784182a461f3ee5837b006629da598788df4fe05fb251cc6',
    'builtins/perl/emitter.pl': 'bd80d964e46d45891b644f9a1018f7bdc7569105021b186407aca093bfe4e137',
    'builtins/perl/parser.py': '05a3c978918b050b5695116675e9dd7d1dbf3748876892d14876aabd2f65ad75',
    'builtins/protocol_contract.py': '478dfa28a66fd3023dbf24803e3b8ef48ec35c12baaf8f3f6947a1c2d0a49d31',
    'builtins/python/emitter.py': '90067e97239cacb1c5cc0d45a53d00df4060207cfc6e17e2a626f95c530573ab',
    'builtins/python/parser.py': '014b378ed23c525dc42ac3719ef0e05db98ef22086b83f3bf375d7b0faaa8ba2',
    'builtins/ruby/emitter.rb': 'e8b4a1fea4b6de2fe2853d75706c1ff34aa3f0a384db4dff5e2c5230778c82ff',
    'builtins/ruby/parser.py': '45b43a5afcb97c177b0804c920f7c05fd5ade1447e3d75c799587af42d06ac1a',
    'cmake_version.py': '871c7fe6a8cda6d511aa52377ec024b7ccce5972a8fef3fe2247d9c672fd4d10',
    'current_publication.py': '1a4c46fb2fa5d7f82eec3d396c68ae2b20554e154c28584bcf273df1c377f522',
    'historical_publication.py': '966061803c511ffd6380621829e79f2108f89a6425530ef802f9112f8bec7cf1',
    'host_methods.py': '017230b1026703e027d007f17a82ac00eb6df2729f0169f989343a224d092e3d',
    'identity.py': 'b2a66fe02ab1a2890fe53bfc82872421ed00ff53037389d7da9e0d26fb46f919',
    'inventory.py': 'b4480452a0a25821203f6ef9448eb9612d969bfd9d5540b92b26463e1a286d07',
    'inventory_contract.py': '83ff23d4356e454e899446e16bfea9aaf8d778f1d91972ace45220d2a9bf2bfb',
    'managed_runtime.py': 'a4c7a366c927e655ccd4f331174c9310d1e0d0357a29bae0452a9e56a9ae99c2',
    'methods.py': 'ab6fad7a14c7d08e5980c8c4a61eda3a3e76a2e85d5ff7006a36fd296e54eefc',
    'nmake_version.py': '20645406f9402db9f70d24679508078cfa7e648d77f652e30e4355bc1df90fdc',
    'nmake_version_emitter.py': '82ae5d7e673450505435af68bd1c1aa04718dac86fe454bde267b6547d35adb0',
    'observation_host.py': '4609b6a50e0ecb73c17a8563f8b346a35a0c5ca32f471076bd7528c75558eaf0',
    'observation_runtime.py': '061a0535dda535c31ecf340d645af773bdc52ccc9b8aa88fc9a190eddfc6e756',
    'observations.py': '1015d81599bf7823ea5c9df7c5477b12fd325e4b878e5189975b90dca13881c8',
    'probe_core.py': 'ba66eaa2d88912ab4ae5277cc56f0616384a9c38241f8c1ad374b38a40f0747f',
    'probe_d3.py': '647186156cfb0289da9e95fa13d9f99cc70264ac7a05e62410585b20c7246717',
    'probe_w2.py': 'e11c3734ea8ba7a1e9bc52fdf4c19822ecf06f2c46579d456b3ad568476d06b3',
    'proof_d3.py': 'a032b4f632e3770bd6b1daeef28a95759717483aabe8a549f27b8710ea21d55a',
    'proof_h2.py': 'b4fe04854dd90833bdbc82e829e286086c7bd5e7878de72224c2b8d9da0ba7a9',
    'runtime.py': '557801ca12c660cc81f78d79e77bfcfbfa41d84fae5284815636c8e45427c5ec',
    'runtime_base.py': '911cd28fc1d23ae891b9730a4405c25cee661fca2fefd6d4d3db85f294b48194',
    'native_inspection.py': '9b91a9a47598e37650c1d6f54ab64402b028452baf58ddfe9a321cad88c071e6',
    'native_inspection_core.py': '75e816fdca8cc9ccf4d384d4e4f01e7be76f53879a6e5cfd7c6bdf9dc4e892f8',
    '../appended_engine_windows_dependency_proof.py': '6d30769578be43268cf9a6226054db79d0e16956e52085fb0f1c4618505b5747',
    '../appended_engine_windows_contract.py': 'ef065be8c502211ea748dbfc1732b6ca02b9210ee78ed74901f2b6ca6869d5d8',
}


def _core():
    owner = globals().get('_support_source_owner')
    if type(owner) is not types.ModuleType:
        raise ValueError('Verified producer source owner required')
    return owner._require_source_child(__name__, sys.modules.get(__name__))


def _module(role):
    return _core()._support_module(role)


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _time(deadline):
    if (type(deadline) not in (int, float) or not math.isfinite(deadline)
            or time.monotonic() >= deadline):
        raise ValueError('Original dependency operation deadline exhausted')


def _source_gaps():
    gaps = list(_module('supplier_registry').source_gaps())
    gaps.extend(_module('library_interfaces').source_interface_gaps())
    # The fixed library child owns its separate SDK import reader. Never route
    # SDK imports through the stricter supplier-output archive inspector.
    if 'select_sdk_libraries' not in vars(_module('library_interfaces')):
        gaps.append(SDK_INSPECTION_GAP)
    return sorted(set(gaps))


def _require_source():
    gaps = _source_gaps()
    if gaps:
        raise _core().MissingSource(gaps)


def _plan_value(request_ref, request, selected):
    c = _core()
    value = {'schema_version': 2, 'kind': PLAN_KIND,
        'target': copy.deepcopy(c._pure().TARGET),
        'request': c._reference(request_ref),
        'dependency_selection': copy.deepcopy(request['dependency_selection']),
        'toolchain_identity': copy.deepcopy(selected['toolchain_identity']),
        'sources': copy.deepcopy(selected['sources']), 'output': selected['output'],
        'version_output': selected['output'] + '.tool-versions',
        'limits': copy.deepcopy(selected['limits']), 'source_gaps': _source_gaps(),
        **{name: False for name in c._pure().FALSE_FACTS}}
    c._pure().encoded(value)
    return value


def _bootstrap_plan(request_ref):
    inputs, selection = _module('current_inputs'), _module('selection')
    request_raw, request = inputs._bootstrap(_core()._reference(request_ref))
    request = _core()._request(inputs._request(request))
    selection_raw, selected = inputs._bootstrap(request['dependency_selection'])
    selected = selection.validate_selection(selected)
    return request, selected, request_raw, selection_raw


def plan(request_ref):
    """Return finite declarations; do not create owners, saves or processes."""
    request, selected, unused_request, unused_selection = _bootstrap_plan(request_ref)
    return _plan_value(request_ref, request, selected)


def _ref(path, pin):
    return _core()._reference({'path': Path(path).as_posix(), 'sha256': pin})


def _source_images(lease):
    """Hold fixed loaded Source bytes, never selected status declarations."""
    c = _core()
    entry = c._dependency_entry()
    original = vars(entry)['_SOURCE_CACHE'][c._CORE_NAME]
    controller = _ref(original['path'], original['pin'])
    references = {controller['path']: controller}
    expected_sizes = {}
    for filename, pin, size, name in c._SUPPORT_SOURCES.values():
        ref = _ref(Path(c.__file__).resolve().with_name(filename), pin)
        references[ref['path']] = ref
        expected_sizes[ref['path']] = size
    for relative, pin in PURE_SOURCES.items():
        ref = _ref((Path(c.__file__).resolve().parent / relative).resolve(), pin)
        previous = references.setdefault(ref['path'], ref)
        c._equal(previous, ref, 'fixed transitive pure Source identity')
    for row in c._SOURCE_MODULES.values():
        if row.get('state') == 'loaded':
            ref = _ref(row['path'], row['pin'])
            old = references.setdefault(ref['path'], ref)
            c._equal(old, ref, 'one actual Source image pin')
    root = Path(c.__file__).resolve().parents[2]
    profile = _ref(root / RECIPE / 'profile.json', PROFILE_SHA256)
    template = _ref(root / RECIPE / 'initial-cache.cmake.in', TEMPLATE_SHA256)
    maintained = copy.deepcopy(lease['request']['maintained_source'])
    for ref in (profile, template, maintained):
        references[ref['path']] = ref
    resources = []
    for row in _module('supplier_registry').binding_info()['suppliers'].values():
        for resource in row.get('resources', []):
            if not 1 <= resource['bytes'] <= 65536:
                raise ValueError('Bounded fixed supplier Source resource required')
            ref = _ref(resource['path'], resource['sha256'])
            references[ref['path']] = ref
            expected_sizes[ref['path']] = resource['bytes']
            resources.append(ref)
    images = {}
    for ref in sorted(references.values(), key=lambda item: item['path']):
        raw = lease['held'].read_ref(ref, MAX_SOURCE)
        if _sha(raw) != ref['sha256']:
            raise ValueError('Original maintained Source image differs')
        if ref['path'] in expected_sizes and len(raw) != expected_sizes[ref['path']]:
            raise ValueError('Original maintained Source image size differs')
        images[ref['path']] = {'reference': copy.deepcopy(ref), 'raw': raw}
    registry = next((row['reference'] for row in images.values()
        if row['reference']['path'] == Path(c.__file__).resolve().with_name(
            'supplier_registry.py').as_posix()), None)
    if registry is None:
        raise ValueError('Original maintained supplier registry image absent')
    helpers = [row['reference'] for row in images.values()
        if row['reference'] not in (controller, profile, template, maintained)]
    if not 1 <= len(helpers) <= 64:
        raise ValueError('Finite complete Source helper closure required')
    return images, {'controller': controller, 'recipe': profile,
        'source_review': copy.deepcopy(registry), 'helpers': copy.deepcopy(helpers),
        'templates': [template, maintained, *sorted(resources, key=lambda row: row['path'])]}


def _policy_seal(policy):
    b = _module('supplier_factory_contract_base')
    keys = ('request_ref', 'request', 'selection', 'plan', 'plan_ref', 'identity',
        'identity_reference', 'identity_pin', 'commands', 'registration',
        'generated_inputs', 'supplier_returns', 'rendered_files', 'bindings',
        'library_declarations', 'build_instances', 'prefix_notices', 'notice_refs',
        'sdk_tail', 'link_tail', 'source_mode', 'produced_runtime_policies')
    return {**{name: _sha(b._source_encoded(policy[name])) for name in keys},
        'identity_raw': _sha(policy['identity_raw']),
        'source_images': {path: {'reference': copy.deepcopy(row['reference']), 'sha256': _sha(row['raw'])}
            for path, row in policy['source_images'].items()}}


def _fixed_policy(current_input_token, source_token, *, request_ref):
    """Issue the Core factory only from genuine independent current/source caps.

    Retained admission uses this same Source derivation and original output
    layout. No receipt, Workspace, graph or callback is an input to the method.
    """
    _require_source()
    c, inputs = _core(), _module('current_inputs')
    sources, helper = _module('source_inputs'), _module('supplier_factory_contract')
    registry, library = _module('supplier_registry'), _module('library_interfaces')
    lease = inputs._lease_for_controller(current_input_token)
    source_state, source_lease = sources._state(source_token)
    if source_state['inputs'] is not current_input_token or source_lease is not lease:
        raise ValueError('Same original current/source owners required')
    if source_state['mode'] not in ('fresh-owned', 'retained-read-only'):
        raise ValueError('Exact original Source capability mode required')
    request_ref = c._reference(request_ref)
    held_request = inputs._document(lease['held'].read_ref(request_ref, MAX_DOCUMENT), request_ref)
    c._equal(held_request, lease['request'], 'original producer request')
    selected, identity = lease['selection'], lease['identity']
    root, prefix = selected['output'], selected['output'] + '/prefix'
    plan_value = _plan_value(request_ref, lease['request'], selected)
    plan_ref = {'path': root + '/metadata/plan.json', 'sha256': _sha(c._pure().encoded(plan_value))}
    returns, renders, commands, generated = {}, {}, [], []
    runtime_policies = {}
    registration = {'stages': [], 'produced_tools': {}}
    # Resolve the finite transitive Source closure, then acquire its actual
    # lifetime holds before any factory reads a template or renders a graph.
    generated_module = _module('generated_inputs')
    c._witness_module()
    c._proof_module()
    images, producer = _source_images(lease)
    for supplier in registry.SUPPLIERS:
        projection = source_state['projections'][supplier]
        layout = {'root': root + '/sources/' + supplier,
            'files': copy.deepcopy(projection['files']), 'directories': copy.deepcopy(projection['directories'])}
        recipe = {'source': copy.deepcopy(projection['identity']), 'recipes': {}}
        context = helper.factory_context(supplier, identity=identity, source_layout=layout,
            build_root=root, prefix_root=prefix, source_recipe_bindings=recipe)
        common = helper.render_cmake_inputs(context)
        recipe['recipes'].update(common['references'])
        result = registry.reviewed_supplier_commands(supplier, identity=identity,
            source_layout=layout, build_root=root, prefix_root=prefix,
            source_recipe_bindings=recipe)
        returns[supplier] = result
        for rendered in [*common['rendered_files'], *result['rendered_files']]:
            old = renders.setdefault(rendered['output'], rendered['content'])
            if old != rendered['content']:
                raise ValueError('Conflicting fixed Source rendered bytes')
        commands.extend(copy.deepcopy(result['commands']))
        registration['stages'].extend(copy.deepcopy(result['registration']['stages']))
        for role, row in result['registration']['produced_tools'].items():
            if role in registration['produced_tools']:
                raise ValueError('Duplicate fixed produced-program role')
            registration['produced_tools'][role] = copy.deepcopy(row)
        runtime_rows = registry.reviewed_produced_runtime_facts(
            supplier, result['registration']['produced_tools'])
        if set(runtime_policies).intersection(runtime_rows):
            raise ValueError('Duplicate fixed produced-runtime policy role')
        runtime_policies.update(copy.deepcopy(runtime_rows))
        generated.extend(copy.deepcopy(result['generated_inputs']))
    declarations = library.declarations(identity, prefix, returns)
    h = inputs._proof().legacy()
    bindings = {'selection': copy.deepcopy(lease['request']['dependency_selection']),
        'plan': plan_ref, 'producer': producer,
        'toolchain_identity_sha256': selected['toolchain_identity']['sha256'],
        'sources': copy.deepcopy(source_state['bindings']),
        'controller': {'program': copy.deepcopy(identity['programs']['python']),
            'runtime_subject_sha256': lease['original_program_evidence']['python']['runtime_subject_sha256'],
            'machine': 'AMD64', 'pointer_bits': 64}}
    h._bindings(bindings, h._Paths())
    instances, notices = {}, {}
    for supplier in registry.SUPPLIERS:
        instances[supplier] = 'supplier-' + supplier + '-' + _sha(c._pure().encoded({
            'workspace': root, 'supplier': supplier,
            'source_subject_sha256': bindings['sources'][supplier]['source_subject_sha256']}))[:16]
        projection = source_state['projections'][supplier]
        for name in projection['notices']:
            notices['share/licenses/' + supplier + '/' + name] = copy.deepcopy(projection['files'][name])
    notice_refs = [{'path': prefix + '/' + name, 'sha256': row['sha256']}
        for name, row in sorted(notices.items())]
    if not 1 <= len(notice_refs) <= 256:
        raise ValueError('Finite complete prefix notice set required')
    factory = object.__new__(c._Factory)
    # A deriving factory has genuine owners and fixed Source interfaces but no
    # execution authority. The library child may only select original SDK data.
    policy = {'state': 'deriving', 'context': None, 'input_token': current_input_token, 'source_token': source_token,
        'expected': {'bindings': copy.deepcopy(bindings)}, 'library_declarations': declarations,
        'build_instances': instances, 'prefix_notices': notices, 'revoked': False,
        'source_mode': source_state['mode']}
    c._NATIVE_FACTORIES[factory] = policy
    try:
        sdk_tail = library.select_sdk_libraries(current_input_token, factory)
        link_tail = library.probe_link_tail(identity, declarations, sdk_tail)
        probe = library.probe_declaration(identity, declarations, workspace_root=root,
            object_path=root + '/probe/static-closure-probe.obj', link_inputs=sdk_tail,
            maximum_jobs=selected['limits']['maximum_jobs'])
        commands.append(probe)
        registration['stages'].append({key: probe[key] for key in ('id', 'supplier', 'stage')})
        if not 1 <= len(commands) <= h.MAX_COMMANDS or len({row['id'] for row in commands}) != len(commands):
            raise ValueError('Finite unique independently fixed command graph required')
        generated = generated_module.declarations(generated, commands, root)
    except BaseException:
        policy['revoked'] = True
        raise
    policy.update({
        'request_ref': request_ref, 'request': copy.deepcopy(lease['request']),
        'selection': copy.deepcopy(selected), 'identity': copy.deepcopy(identity),
        'identity_raw': lease['identity_raw'], 'identity_reference': copy.deepcopy(selected['toolchain_identity']),
        'identity_pin': selected['toolchain_identity']['sha256'], 'plan': plan_value, 'plan_ref': plan_ref,
        'commands': commands, 'registration': registration, 'generated_inputs': generated,
        'supplier_returns': returns, 'rendered_files': renders, 'source_images': images,
        'bindings': bindings, 'library_declarations': declarations, 'build_instances': instances,
        'prefix_notices': notices, 'notice_refs': notice_refs, 'sdk_tail': sdk_tail, 'link_tail': link_tail,
        'expected': {'bindings': copy.deepcopy(bindings), 'commands': copy.deepcopy(commands),
            'prefix': None, 'libraries': None, 'probe': None, 'registration': copy.deepcopy(registration),
            'original_program_evidence': copy.deepcopy(lease['original_program_evidence']),
            'nmake_runtime': copy.deepcopy(lease['nmake_runtime'])},
        'prefix_inventory': None, 'library_inspections': None, 'source_mode': source_state['mode'],
        'produced_runtime_policies': runtime_policies})
    policy['seal'] = _policy_seal(policy)
    policy['state'] = 'ready'
    return factory


def _factory(factory):
    c = _core()
    if type(factory) is not c._Factory or factory not in c._NATIVE_FACTORIES:
        raise ValueError('Original Source-owned Core factory required')
    policy = c._NATIVE_FACTORIES[factory]
    if policy['revoked'] or policy['state'] != 'ready':
        raise ValueError('Complete unrevoked Source factory required')
    lease = _module('current_inputs')._lease_for_controller(policy['input_token'])
    state, same = _module('source_inputs')._state(policy['source_token'])
    if same is not lease or state['inputs'] is not policy['input_token']:
        raise ValueError('Original Source factory owners changed')
    if state['mode'] != policy['source_mode']:
        raise ValueError('Original sealed Source capability mode changed')
    c._equal(_policy_seal(policy), policy['seal'], 'independently sealed Source policy')
    for key, wanted in (('bindings', policy['bindings']), ('commands', policy['commands']),
            ('registration', policy['registration']),
            ('original_program_evidence', lease['original_program_evidence']),
            ('nmake_runtime', lease['nmake_runtime'])):
        c._equal(policy['expected'][key], wanted, 'independent Source expected ' + key)
    return policy, lease


def require_fixed_policy(factory):
    """Owned independent declarations for the fixed retained reader only."""
    policy, unused = _factory(factory)
    keys = ('request_ref', 'request', 'selection', 'plan', 'plan_ref', 'identity',
        'identity_reference', 'identity_pin', 'commands', 'registration', 'generated_inputs',
        'supplier_returns', 'rendered_files', 'bindings', 'library_declarations',
        'build_instances', 'prefix_notices', 'notice_refs', 'sdk_tail', 'link_tail', 'source_mode',
        'produced_runtime_policies')
    return {name: copy.deepcopy(policy[name]) for name in keys}


def sdk_libraries(factory):
    policy, unused = _factory(factory)
    return copy.deepcopy(policy['sdk_tail'])


def _mkdir(context, relative):
    parts = relative.split('/')
    for count in range(1, len(parts) + 1):
        name = '/'.join(parts[:count])
        if name not in context.workspace.directories:
            context.workspace.mkdir_new(name)


def _publish(context, relative, raw):
    if '/' in relative:
        _mkdir(context, relative.rsplit('/', 1)[0])
    row = context.workspace.publish_bytes_new(relative, raw)
    if row['sha256'] != _sha(raw) or row['bytes'] != len(raw):
        raise ValueError('Original owned Source publication differs')
    context._capture({'path': context.workspace.output + '/' + relative,
        'sha256': row['sha256']}, len(raw), minimum=0)
    return row


def _publish_inputs(context, policy):
    # compile_probe has already checked that this Workspace began empty.
    _publish(context, 'metadata/plan.json', _core()._pure().encoded(policy['plan']))
    for directory in ('build', 'recipes', 'prefix'):
        _mkdir(context, directory)
    for supplier in _module('supplier_registry').SUPPLIERS:
        _mkdir(context, 'build/' + supplier)
        _mkdir(context, 'recipes/' + supplier)
    for relative, text in sorted(policy['rendered_files'].items()):
        _publish(context, relative, text.encode('ascii'))


def _copy_notices(context, policy):
    source = _module('source_inputs').require_sources(policy['source_token'])
    for supplier, projection in source['projections'].items():
        for name in projection['notices']:
            row = projection['files'][name]
            raw = context.held.read_ref({'path': projection['source_root'] + '/' + name,
                'sha256': row['sha256']}, 256 * 1024**2)
            if len(raw) != row['bytes']:
                raise ValueError('Actual original notice size differs')
            _publish(context, 'prefix/share/licenses/' + supplier + '/' + name, raw)


def _native_context(factory, *, deadline):
    c = _core()
    policy, lease = _factory(factory)
    source_state, source_lease = _module('source_inputs')._state(policy['source_token'])
    if (source_lease is not lease or source_state['mode'] != 'fresh-owned'
            or policy['source_mode'] != 'fresh-owned' or source_state['materialized']):
        raise ValueError('Native production requires genuine unmaterialized fresh-owned sources')
    if policy['context'] is not None:
        raise ValueError('One actual native Workspace per Source factory required')
    issuer, a, subject = lease['issuer'], lease['a'], lease['subject']
    witness = c._witness_module()  # Resolve Source before creating any output.
    publication = lease['selection']['publication']
    catalogue = issuer._current_source_catalogue()['publication_source_identity']
    c._pure()._fields(catalogue, _module('selection').PUBLICATION_SOURCES, 'actual publication Source closure')
    c._equal(publication['source_identity'], catalogue, 'selected/current actual publication Source')
    c._equal(publication['runtime_identity'], subject['runtime_identity'], 'same actual publication/input runtime')
    _time(deadline)
    q = a.admit_qualification(publication['qualification'], source_identity=catalogue,
        runtime_identity=subject['runtime_identity'])
    lease['held'].check()
    # Use original spellings, never the casefolded registry lookup keys.
    protected = [row['reference']['path'] for row in lease['held'].selected.values()]
    protected += [row['inventory']['root'] for row in lease['held'].trees.values()]
    protected += [policy['selection']['output'] + '.tool-versions']
    limits = policy['selection']['limits']
    context = object.__new__(c._NativeContext)
    context.workspace, context.held = None, lease['held']
    context.identity = copy.deepcopy(policy['identity'])
    context.commands, context.registration = copy.deepcopy(policy['commands']), copy.deepcopy(policy['registration'])
    context.original_evidence = copy.deepcopy(lease['original_program_evidence'])
    context.nmake_runtime = copy.deepcopy(lease['nmake_runtime'])
    context.limits, context.deadline = copy.deepcopy(limits), deadline
    context.clock, context.pause = time.monotonic, time.sleep
    context.captures, context.observations, context.products = [], [], {}
    context.next_index, context.revoked, context.closed, context.probe = 0, False, False, None
    policy['context'] = context
    c._NATIVE_CONTEXTS[context] = {'factory': factory, 'workspace': None, 'held': context.held,
        'input_token': policy['input_token'], 'source_token': policy['source_token'],
        'witness': witness, 'identity_raw': policy['identity_raw'], 'identity_pin': policy['identity_pin'],
        'nmake_runtime': copy.deepcopy(lease['nmake_runtime'])}
    # Preserve the opening context before the fallible new-owner operation.
    workspace = a.Workspace.create_new(policy['selection']['output'], protected_paths=protected,
        limits={'maximum_output_bytes': limits['maximum_output_bytes'],
            'maximum_log_bytes': limits['maximum_log_bytes'], 'maximum_entries': 1000000,
            'maximum_file_bytes': 256 * 1024**2,
            'io_seconds': min(60, max(1, math.ceil(deadline - time.monotonic())))}, qualification=q)
    context.workspace = workspace
    c._NATIVE_CONTEXTS[context]['workspace'] = workspace
    if type(workspace) is not a.Workspace or workspace.diagnostic:
        raise ValueError('Actual same-A qualified production Workspace required')
    context._check()
    return context


def _inspect_installed(context, factory):
    c, library = _core(), _module('library_interfaces')
    policy, unused = _factory(factory)
    checked = library.inspect_prefix(context, policy['library_declarations'])
    policy['expected']['prefix'] = copy.deepcopy(checked['prefix'])
    policy['expected']['libraries'] = {target: {key: copy.deepcopy(value) for key, value in row.items()
        if key != 'inspection'} for target, row in checked['libraries'].items()}
    policy['library_inspections'] = {target: copy.deepcopy(row['inspection'])
        for target, row in checked['libraries'].items()}
    policy['prefix_inventory'] = library.require_prefix_inventory(factory)
    link_inputs = [{key: checked['libraries'][target][key] for key in ('path', 'sha256')}
        for target in sorted(checked['libraries'])] + copy.deepcopy(policy['link_tail'])
    probe = library.probe_command(context.identity, checked['prefix'], checked['libraries'],
        workspace_root=context.workspace.output, object_path=context.workspace.output + '/probe/static-closure-probe.obj',
        link_inputs=link_inputs, maximum_jobs=context.limits['maximum_jobs'])
    c._equal(probe, context.commands[-1], 'unchanged independently fixed final probe declaration')
    return link_inputs


def _complete_expected(factory, prefix_facts, probe_output):
    """Complete D3 declarations from actual Source-owned inspections, never D.

    Native and retained paths share the sealed Source policy. The library
    owner's private record, not the offered dictionary, supplies prefix facts.
    The exact selected probe output is reopened through the genuine live owner.
    """
    c, library = _core(), _module('library_interfaces')
    policy, lease = _factory(factory)
    checked = library.require_prefix_facts(factory)
    c._equal(prefix_facts, checked, 'actual independently inspected prefix facts')
    probe_output = c._reference(probe_output)
    c._equal(probe_output['path'], policy['selection']['output'] + '/probe/static-closure-probe.exe',
        'fixed original final probe output path')
    raw = lease['held'].read_ref(probe_output, 256 * 1024**2)
    inspected = c._inspect_native_image(raw)
    if inspected.get('machine') != 'x86_64' or inspected.get('dll') is not False:
        raise ValueError('Actual original closure probe must be an x64 executable')
    libraries = {target: {key: copy.deepcopy(value) for key, value in row.items()
        if key != 'inspection'} for target, row in checked['libraries'].items()}
    links = [{key: libraries[target][key] for key in ('path', 'sha256')}
        for target in sorted(libraries)] + copy.deepcopy(policy['link_tail'])
    probe = library.probe_command(policy['identity'], checked['prefix'], checked['libraries'],
        workspace_root=policy['selection']['output'],
        object_path=policy['selection']['output'] + '/probe/static-closure-probe.obj',
        link_inputs=links, maximum_jobs=policy['selection']['limits']['maximum_jobs'])
    c._equal(probe, policy['commands'][-1], 'same independently fixed final probe command')
    expected = {'bindings': copy.deepcopy(policy['bindings']), 'commands': copy.deepcopy(policy['commands']),
        'prefix': copy.deepcopy(checked['prefix']), 'libraries': libraries,
        'probe': {'command_id': probe['id'], 'library_targets': sorted(libraries),
            'link_inputs': links, 'output': probe_output},
        'registration': copy.deepcopy(policy['registration']),
        'original_program_evidence': copy.deepcopy(lease['original_program_evidence']),
        'nmake_runtime': copy.deepcopy(lease['nmake_runtime'])}
    c._pure()._fields(expected, c._proof_module().EXPECTED_FIELDS, 'independent D3 expectation fields')
    policy['expected'] = copy.deepcopy(expected)
    policy['library_inspections'] = {target: copy.deepcopy(row['inspection'])
        for target, row in checked['libraries'].items()}
    policy['prefix_inventory'] = library.require_prefix_inventory(factory)
    return expected


def _finish(context, factory, lifecycle, link_inputs):
    c, publication = _core(), _module('dependency_publication')
    policy, unused = _factory(factory)
    if context.next_index != len(context.commands):
        raise ValueError('Complete original fixed generated lifecycle required')
    path = context.workspace.output + '/probe/static-closure-probe.exe'
    relative = path[len(context.workspace.output) + 1:]
    snapshot = context.workspace.inspect_outputs()
    row = snapshot['files'].get(relative)
    if type(row) is not dict or row.get('kind') != 'file':
        raise ValueError('Actual final closure-probe output absent')
    capture = context._capture({'path': path, 'sha256': row['sha256']}, row['bytes'])
    inspection = c._inspect_native_image(capture['raw'])
    if inspection.get('machine') != 'x86_64' or inspection.get('dll') is not False:
        raise ValueError('Actual final closure probe must be an x64 executable')
    checked = _module('library_interfaces').require_prefix_facts(factory)
    expected = _complete_expected(factory, checked, {'path': path, 'sha256': row['sha256']})
    c._equal(expected['probe']['link_inputs'], link_inputs, 'same original fixed full link inputs')
    # Expected contains the exact eight D3 fields; current checked outputs fill
    # its three observational subjects, never fields read from an offered D.
    c._proof_module()._d2().legacy()._fields(policy['expected'],
        c._proof_module().EXPECTED_FIELDS, 'independent final D3 expectations')
    complete = publication.publish_completed(context, lifecycle)
    final = publication.recheck_completed(context)
    c._equal(final, complete['snapshot'], 'original final publication snapshot')
    context._check()
    c._equal(context.workspace.inspect_outputs(), final, 'complete actual outputs before input closure')
    _module('current_inputs').close_current_inputs(policy['input_token'])
    c._equal(context.workspace.inspect_outputs(), final, 'complete actual outputs after input closure')
    context.workspace.close_joined()
    if (not context.workspace.closed or context.workspace.uncertain
            or any(not owner.closed or owner.uncertain for owner in context.held.owners)):
        raise ValueError('All original native owners must close knowingly before issuance')
    _time(context.deadline)
    context.closed = True
    value = copy.deepcopy(complete['value'])
    if value.get('schema_version') != 2 or value.get('kind') != RESULT_KIND:
        raise ValueError('Exact completed D3/W2/G2 result required')
    value['result'] = copy.deepcopy(complete['reference'])
    value['original_references'] = copy.deepcopy(complete['original_references'])
    raw = c._pure().encoded(value)
    token = object.__new__(c.IssuedDependencyV2)
    c._NATIVE_RESULTS[token] = raw
    return token


def _abort(input_token, context, error):
    c = _core()
    if context is not None:
        context._revoke(error)
        state = c._NATIVE_CONTEXTS.get(context)
        if state is not None:
            c._NATIVE_FACTORIES[state['factory']]['revoked'] = True
        # Unknown launch/join/publication state remains retained, never retried.
        if context.workspace is not None and (context.workspace.uncertain
                or any(log._state != 'sealed' for log in context.workspace.logs)):
            return
    try:
        if input_token is not None:
            _module('current_inputs').close_current_inputs(input_token)
        if context is not None and context.workspace is not None and not context.workspace.closed:
            context.workspace.close_joined()
            context.closed = True
    except BaseException as cleanup:
        c._RETAINED_UNCERTAIN.append((context, str(error) + '; cleanup: ' + str(cleanup)))
        if context is not None and context.workspace is not None:
            context.workspace.retain_uncertain(None, None, str(cleanup))


def build(request_ref, *, overall_deadline=None):
    """Produce only through original fresh collection and known owner closure."""
    started = time.monotonic()  # Before Source gates, parsing or any bootstrap.
    ceiling = started + 86400
    if overall_deadline is not None:
        if (type(overall_deadline) not in (int, float) or not math.isfinite(overall_deadline)
                or overall_deadline <= started):
            raise ValueError('Finite live caller overall deadline required')
        ceiling = min(ceiling, overall_deadline)
    request_ref = _core()._reference(request_ref)
    request, selected, unused_request, unused_selection = _bootstrap_plan(request_ref)
    deadline = _module('selection').operation_deadline(started, ceiling, selected['limits'])
    _time(deadline)
    _require_source()
    inputs, issuer = _module('current_inputs'), _module('current_inputs')._issuer()
    unused_raw, version_selection = inputs._bootstrap(request['version_selection'])
    version_selection = issuer._selection(version_selection)
    _time(deadline)
    limits = copy.deepcopy(issuer.DEFAULT_LIMITS)
    limits['wall_milliseconds'] = min(60000, int((deadline - time.monotonic()) * 1000))
    if limits['wall_milliseconds'] < 1:
        raise ValueError('Original deadline exhausted before fresh version collection')
    versions = issuer._observe_tool_versions(version_selection,
        output=selected['output'] + '.tool-versions', limits=limits)
    _time(deadline)
    input_token = context = factory = None
    try:
        input_token = inputs.admit_current_inputs(request_ref, versions, deadline=deadline)
        source_token = _module('source_inputs').admit_sources(input_token)
        factory = _fixed_policy(input_token, source_token, request_ref=request_ref)
        context = _native_context(factory, deadline=deadline)
        policy, unused = _factory(factory)
        unused_phase, compile_limits = _core()._phase_limits(context.limits, 'probe', deadline, time.monotonic())
        witness = _core()._NATIVE_CONTEXTS[context]['witness']
        compile_limits['maximum_output_bytes'] = min(compile_limits['maximum_output_bytes'],
            witness.MAX_SOURCE_BYTES + witness.MAX_OBJECT_BYTES + witness.MAX_LOG_BYTES)
        compile_limits['maximum_log_bytes'] = min(compile_limits['maximum_log_bytes'], witness.MAX_LOG_BYTES)
        context.compile_probe(witness,
            identity_raw=policy['identity_raw'], identity_pin=policy['identity_pin'],
            maintained_source_path=request['maintained_source']['path'], limits=compile_limits)
        _module('source_inputs').materialize_sources(source_token, context)
        _publish_inputs(context, policy)
        generated = _module('generated_inputs')
        lifecycle = generated._for_native(context)
        while context.next_index < len(context.commands) - 1:
            generated.step(lifecycle)
        _copy_notices(context, policy)
        link_inputs = _inspect_installed(context, factory)
        generated.step(lifecycle)
        return _finish(context, factory, lifecycle, link_inputs)
    except BaseException as error:
        if context is None and factory is not None:
            context = _core()._NATIVE_FACTORIES[factory]['context']
        _abort(input_token, context, error)
        raise


def require_dependency_with_probe(token):
    return _core().require_dependency_v2(token)


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError(message)


def cli(argv=None):
    parser = _Parser(description='Private finite Windows dependency Source producer')
    parser.add_argument('operation', choices=('plan', 'build'))
    parser.add_argument('--request', required=True)
    parser.add_argument('--request-sha256', required=True)
    try:
        args = parser.parse_args(argv)
        reference = {'path': args.request, 'sha256': args.request_sha256}
        result = plan(reference) if args.operation == 'plan' else require_dependency_with_probe(build(reference))
        sys.stdout.write(_core()._pure().encoded(result).decode('ascii'))
        return 0
    except SystemExit as error:
        return 0 if error.code == 0 else 1
    except Exception as error:
        missing = getattr(error, 'gaps', getattr(error, 'missing', None))
        if missing is not None:
            value, code = {'missing_inputs': sorted(set(missing))}, 2
        else:
            value, code = {'error': str(error)}, 1
        sys.stdout.write(json.dumps(value, sort_keys=True, ensure_ascii=True) + '\n')
        return code
