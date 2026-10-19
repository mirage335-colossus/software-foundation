"""Closed retained52 direct-TU successors; initially the editor form Guard only.

The accepted InputMethod candidate supplies fifty original compiler closures.
Only the reviewed Guard and generated-metadata Shim compile. No predecessor
plan is replayed against live producer code and no ancestor path is discovered.
"""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path

HELPER = 'tools/appended_engine_retained_successor.py'
PLAN_KIND = 'foundation-document-v2-maintenance-retained-successor-plan-v1'
BUILD_KIND = 'foundation-document-v2-maintenance-retained-successor-build-v1'
DONOR_KIND = 'foundation-document-v2-retained-successor-donor-v1'
PROVENANCE_KIND = 'foundation-document-v2-retained-successor-object-provenance-v1'
TRANSITION = 'editor-form-guard-preentry-v1'
GUARD = 'ProviderGuard.cpp'
SHIM = 'BibEngineDocumentWasmShim.cpp'
MAIN = 'main.cpp'
THEME = 'RenderThemeEmscripten.cpp'
OWNER = 'UnifiedSource-950a39b6-13.cpp'
FRESH = (SHIM, GUARD)
SOURCE = 'source/foundation/third_party/appended-engine/src/ProviderGuard.cpp'
BEFORE_SHA256 = '6ec6546880d6736311ab8def5563da79a870dd1f68b56fdcbe947835acf817a8'
# Root source acceptance; binding source bytes does not authorize a producer run.
AFTER_SHA256 = 'b77001d050dfc2451b46cc116ea8e7c3c5271d4b4f08a7dcfdba59c58ffed6c5'
AFTER_BYTES = 69260
SOURCE_ACCEPTANCE_SHA256 = 'aae075f824859c9133a24bdea86ad1e7cb86d9b58165a907e13b665d4fd36757'
PROOF_SOURCE = 'provenance/retained-successor-reuse-proof.json'
HEADER_IDENTITY_SOURCE = 'provenance/retained-successor-header-identity.json'
RAW_PREDECESSOR_SHA256 = 'b3e3083f097afc700c5e4fe1cf57cf1c16ed268108145664ac5cc1d015afe384'
PREDECESSOR_PRELINK = dict(root='sources', path='prelink-plan.json',
    sha256='1ccf762ffb24fad349515a51039712e9375465649f67c108f0bc16d218edb2a7')
HEADER_IDENTITY = dict(root='sources', path='provenance/input-method-header-identity.json',
    sha256='bbbec496a5304111f9a19d3099b6fa7b489ab7ff0ba06eb0320d8a634506a01b')
PINS = {
    'root_acceptance': 'a328a82ea65e0f58248f86ebc6bbf6e04d04238b7bb3d42c1e3572be0bb6b68e',
    'closed_result': '61009c050d7184ce0bd2def8637773208c31755f69651af6a66702dd08f93dd8',
    'plan': '62b781943494d766688679a148b0a4bc27c63e1693e6bbf2a261eb624698df0a',
    'maintenance_build': '5f47f49788fcb627763695258095cae50210f6b315f84209c105d36012187000',
    'commands': 'bcec4a07ac145f71872b79498b49f4a6324c4d42203e4a28c85c5ff9f8d4bb0f',
    'input_freeze': 'ae5843aa221077680f89b06d7252c30fb05ad36dc809da5595cfbe535fdcbef6',
    'input_method_donor': '3fea67d55415ae9b270a7aa1c525fd7956e19160ff38b4c8c146ccd768291749',
}


def require(condition, message):
    if not condition:
        raise ValueError('Retained successor ' + message)


def layout(transition=TRANSITION, *, bound=True):
    """One registered layout, never caller-selected fresh IDs or ancestors."""
    require(type(transition) is str and transition == TRANSITION, 'unknown transition')
    require(type(bound) is bool, 'layout bound selector must be boolean')
    value = dict(transition=TRANSITION, fresh=list(FRESH), source=SOURCE,
        before_sha256=BEFORE_SHA256, after_sha256=AFTER_SHA256,
        after_bytes=AFTER_BYTES, source_acceptance_sha256=SOURCE_ACCEPTANCE_SHA256)
    if bound:
        for key in ('after_sha256', 'source_acceptance_sha256'):
            pin = value[key]
            require(type(pin) is str and len(pin) == 64 and set(pin) <= set('0123456789abcdef')
                and pin != '0' * 64, 'reviewed source binding remains unarmed')
        require(type(AFTER_BYTES) is int and 0 < AFTER_BYTES <= 1048576
            and AFTER_SHA256 != BEFORE_SHA256, 'reviewed source binding remains unarmed')
    return value


def reference(value, api, pin=None):
    api.fields(value, ('path', 'sha256'), 'retained successor reference')
    api.sha(value['sha256'], 'retained successor reference')
    require(pin is None or value['sha256'] == pin, 'closed authority pin differs')
    return api._completed_reference(value)


def freeze_reference(value, api):
    api.fields(value, ('path', 'sha256'), 'retained successor frozen reference')
    require(value['sha256'] == PINS['input_freeze'], 'closed freeze pin differs')
    path = api.ordinary(value['path'])
    require(path.stat().st_size <= 192 * 1024 * 1024, 'closed freeze exceeds 192 MiB')
    return api.document_contract.strict_json(api.checked_read(path, value['sha256']),
        'retained successor closed physical freeze', maximum=192 * 1024 * 1024)


def artifact_names(selected, archives):
    require(len(selected) == len(set(selected)) == 52 and set(FRESH) <= set(selected)
        and {MAIN, OWNER, THEME} <= set(selected) and len(archives) == len(set(archives)) == 5
        and set(archives) == {'JavaScriptCore', 'PAL', 'Skia', 'WTF', 'WebCore'},
        'requires exact52 objects and five archives')
    names = {'artifacts/foundation-retained-engine.mjs', 'artifacts/foundation-retained-engine.wasm',
        'document-generated/BibCopiedDocumentMetadata.generated.h',
        'document-generated/provider-build.json', 'evidence/engine-link.map'}
    for name in selected:
        names.add('objects/' + name + '.o')
        names.update(('objects/' + name + '.o.d',) if name in FRESH else
            ('evidence/import-' + name + '.json', 'evidence/import-' + name + '.original.d'))
    for name in archives:
        names.update(('archives/lib' + name + '.a', 'evidence/archive-' + name + '.json',
            'evidence/import-archive-' + name + '.json'))
    require(len(names) == 174, 'requires174 artifact records')
    return names


def accepted_authority(ref, api):
    """Read only the exact closed InputMethod bundle, with bounded named roles."""
    value = reference(ref, api)
    api.fields(value, ('schema_version', 'kind', 'document_profile', 'transition', *PINS,
        'input_method_private', 'input_method_ninja_log', 'main_compiled'), 'retained successor donor')
    layout(value['transition'], bound=False)
    require(type(value['schema_version']) is int and value['schema_version'] == 1
        and value['kind'] == DONOR_KIND and value['document_profile'] == 'editor', 'donor kind/profile differs')
    docs = {key: (freeze_reference(value[key], api) if key == 'input_freeze'
        else reference(value[key], api, pin)) for key, pin in PINS.items()}
    root, closed, old, build, commands, freeze, predecessor = (docs[k] for k in PINS)
    parent = api._input_method_module()
    require(root.get('kind') == 'root-closed-successful-donor-input-method-repair-candidate-accepted-v1'
        and type(root.get('actual_session')) is int and root['actual_session'] == 8260
        and type(root.get('caller_observed_exit')) is int and root['caller_observed_exit'] == 0
        and root.get('status') == 'passed' and root.get('production_eligible') is False
        and root.get('verified_artifact_records') == 174
        and all(root.get(k) is True for k in ('closed', 'writers_joined', 'inputs_unchanged',
            'all_artifact_physical_identities_root_rechecked', 'runtime_not_run'))
        and api._supervision_report(root.get('qualified_report'), 0), 'requires accepted natural InputMethod Root8260')
    for key, name in (('closed', 'closed_result'), ('plan', 'plan'), ('commands', 'commands'),
            ('maintenance_build', 'maintenance_build'), ('donor_descriptor', 'input_method_donor')):
        fact = api._successful_module()._p5_flat_fact(root['records'][key], api)
        require({k: fact[k] for k in ('path', 'sha256')} == value[name], 'Root closed role join differs')
    require(old.get('kind') == parent.PLAN_KIND and old.get('production_eligible') is False
        and old['successful_donor']['reference'] == value['input_method_donor']
        and old['profile_sha256'] == api.digest(api.ROOT / api.profile_path('editor')), 'closed parent plan differs')
    selected = [o['id'] for o in old['reuse']['objects']]
    archives = [a['name'] for a in old['reuse']['archives']]
    parent.artifact_names(selected, archives)
    fresh = [name for name in selected if name in parent.FRESH]
    imported = [name for name in selected if name not in parent.FRESH]
    accounting = dict(selected=52, compiled=2, imported=50, archive_imported=5, archive_repacked=0,
        compiled_ids=fresh, imported_ids=imported, imported_archive_names=archives)
    require(build.get('kind') == parent.BUILD_KIND and build.get('status') == 'passed'
        and build.get('production_eligible') is False and build.get('accounting') == accounting
        and build.get('plan_sha256') == value['plan']['sha256']
        and build.get('successful_donor') == value['input_method_donor']
        and build.get('commands') == dict(path='evidence/commands.json', sha256=value['commands']['sha256'])
        and set(commands['objects']) == set(parent.FRESH) and set(commands['imports']) == set(imported)
        and set(commands['archive_imports']) == set(archives), 'closed parent compiler/copy accounting differs')
    require(all(closed.get(k) is True for k in ('closed', 'verified', 'writers_joined', 'runtime_not_run'))
        and closed.get('status') == 'passed' and type(closed.get('returncode')) is int and closed['returncode'] == 0
        and closed.get('production_eligible') is False and closed.get('supervisor_report') == root['qualified_report']
        and closed.get('maintenance_build_sha256') == value['maintenance_build']['sha256']
        and closed.get('successful_donor', {}).get('accounting') == accounting
        and closed.get('static_byte_readback') == 'passed'
        and closed.get('input_identity_namespace_postflight') == 'passed'
        and closed.get('actual_objects') == 52 and closed.get('actual_archive_reports') == 5
        and closed.get('opaque_unchanged_members') == 2060, 'closed parent readback differs')
    records = closed['artifact_records']
    require(set(records) == parent.artifact_names(selected, archives)
        and hashlib.sha256((json.dumps(records, sort_keys=True, separators=(',', ':')) + '\n').encode()).hexdigest()
            == root['artifact_records_sha256'],
        'closed parent complete174 authority differs')
    bindings = api._completed_binding(dict(sources=old['selection']['sources'], sdk=old['selection']['sdk'],
        reuse=old['selection']['reuse_root'], build=str(Path(value['maintenance_build']['path']).parent)))
    require(value['commands']['path'] == str(bindings['build'] / 'evidence/commands.json')
        and type(freeze.get('files')) is dict
        and all(str(base) in freeze['roots'].values() for key, base in bindings.items() if key != 'build'),
        'closed parent roots/freeze differ')
    actual_vfs = api._completed_private_context(value['input_method_private'], bindings, old, freeze)
    require(value['input_method_private']['configuration']['sha256'] == build['private_configuration']['config_sha256']
        and value['input_method_private']['launcher']['sha256'] == build['private_configuration']['launcher_sha256'],
        'closed parent actual private compiler context differs')
    return dict(reference=dict(ref), descriptor=value, root=root, closed=closed, plan=old, build=build,
        commands=commands, freeze=freeze, predecessor=predecessor, records=records,
        bindings=bindings, actual_vfs=actual_vfs)


def _old_inspection(authority, current, api):
    # The InputMethod helper's frozen-metadata reader is independent of its old
    # donor admission. It does not replay the parent plan or follow ancestors.
    return api._input_method_module()._old_inspection(authority, current, api)


def predecessor_proof(proof):
    """Pure exact raw51 inverse; callers independently bind the current bytes.

    This inverse admits no header change or historical proof restamping. The
    restored canonical document must be the already accepted InputMethod raw51.
    """
    spec = layout()
    header = proof.get('header_identity') if type(proof) is dict else None
    require(type(proof) is dict and proof.get('kind') == 'foundation-document-v2-baseline-reuse-v1'
        and type(header) is dict and set(header) == {'root', 'path', 'sha256'}
        and header.get('root') == 'sources' and header.get('path') == HEADER_IDENTITY_SOURCE
        and type(header.get('sha256')) is str and len(header['sha256']) == 64
        and set(header['sha256']) <= set('0123456789abcdef'), 'raw proof/header283 identity differs')
    rows = proof.get('objects')
    require(type(rows) is list and len(rows) == 51 and all(type(row) is dict for row in rows)
        and len({row.get('id') for row in rows}) == 51
        and {GUARD, SHIM, MAIN, OWNER} <= {row.get('id') for row in rows}
        and THEME not in {row.get('id') for row in rows}, 'raw proof must remain exact51 without Theme')
    metadata = proof.get('metadata')
    require(type(metadata) is dict and type(metadata.get('prelink_plan')) is dict
        and {k: metadata['prelink_plan'].get(k) for k in ('root', 'path')} ==
            {k: PREDECESSOR_PRELINK[k] for k in ('root', 'path')}
        and type(metadata['prelink_plan'].get('sha256')) is str
        and len(metadata['prelink_plan']['sha256']) == 64
        and set(metadata['prelink_plan']['sha256']) <= set('0123456789abcdef')
        and set(metadata['prelink_plan']) == set(PREDECESSOR_PRELINK),
        'raw proof requires an exact prelink reference at its original coordinate')
    generated = [metadata[k] for k in sorted(metadata)]
    require(all(row.get('compile_context', {}).get('generated_metadata') == generated for row in rows),
        'raw proof generated metadata differs from exact sorted current roles')
    restored = deepcopy(proof)
    restored['header_identity'] = deepcopy(HEADER_IDENTITY)
    restored['metadata']['prelink_plan'] = deepcopy(PREDECESSOR_PRELINK)
    before = dict(root='sources', path=SOURCE, sha256=BEFORE_SHA256)
    after = dict(before, sha256=spec['after_sha256'])
    guard = next(row for row in restored['objects'] if row['id'] == GUARD)
    require(guard.get('source') == after and guard.get('compile_context', {}).get('source') == after
        and guard.get('provenance', {}).get('source_replacement', {}).get('after') == after,
        'raw proof Guard source/derived-command joins differ')
    guard['source'] = deepcopy(before)
    guard['compile_context']['source'] = deepcopy(before)
    guard['provenance']['source_replacement']['after'] = deepcopy(before)
    guard['dependencies'] = [deepcopy(before) if ref == after else ref for ref in guard['dependencies']]
    for row in restored['objects']:
        row['compile_context']['generated_metadata'] = [restored['metadata'][k] for k in sorted(restored['metadata'])]
    raw = (json.dumps(restored, sort_keys=True, indent=2) + '\n').encode()
    require(hashlib.sha256(raw).hexdigest() == RAW_PREDECESSOR_SHA256,
        'raw proof changes beyond the reviewed Guard/prelink transition')
    return restored


def effective_inspection(base, authority, api):
    spec = layout()
    predecessor_proof(base.proof)
    old = authority['plan']['reuse']
    proof, config = deepcopy(base.proof), deepcopy(base.profile)
    require(base.selection['document_profile'] == 'editor'
        and base.selection['sdk_manifest_sha256'] == authority['plan']['selection']['sdk_manifest_sha256']
        and base.roots['sdk'] == authority['bindings']['sdk'], 'paired editor SDK differs')
    theme = deepcopy(next(o for o in old['objects'] if o['id'] == THEME))
    theme['compile_context']['generated_metadata'] = [proof['metadata'][k] for k in sorted(proof['metadata'])]
    proof['objects'].insert(35, theme)
    config['direct_objects'].append(THEME)
    config['source_bindings'][THEME] = api._theme_module().SOURCE
    config['derived_commands'][THEME] = dict(donor_source=THEME, remove=[], append=[])
    require([o['id'] for o in proof['objects']] == [o['id'] for o in old['objects']]
        == config['direct_objects'] + config['engine_objects'], 'ordered52 graph differs')
    narrowed = deepcopy(proof)
    for obj, before in zip(narrowed['objects'], old['objects']):
        obj['compile_context']['generated_metadata'] = deepcopy(before['compile_context']['generated_metadata'])
        if obj['id'] == GUARD:
            source = before['source']
            require(source == dict(root='sources', path=SOURCE, sha256=BEFORE_SHA256)
                and obj['source'] == dict(source, sha256=spec['after_sha256']), 'approved Guard source delta differs')
            replacement = obj['source']
            obj['source'] = deepcopy(source)
            require(obj['compile_context']['source'] == replacement, 'Guard cached source differs')
            obj['compile_context']['source'] = deepcopy(source)
            obj['dependencies'] = [source if ref == replacement else ref for ref in obj['dependencies']]
            if 'provenance' in before:
                require(obj['provenance'].get('source_replacement', {}).get('after') == replacement,
                    'Guard derived-command source join differs')
                obj['provenance']['source_replacement']['after'] = deepcopy(source)
    header_path = api.ref_path(proof['header_identity'], base.roots, base.inventories)
    current_header = api.checked_document(header_path, proof['header_identity']['sha256'])
    old_ref = old['header_identity']
    require(old_ref == HEADER_IDENTITY, 'accepted InputMethod header identity differs')
    old_fact = authority['freeze']['files'].get(str(authority['bindings']['sources'] / old_ref['path']))
    require(type(old_fact) is dict and old_fact.get('sha256') == old_ref['sha256'],
        'accepted header identity lacks frozen authority')
    old_header = api.document(api._completed_fact(old_fact))
    header_identity_transition(old_header, current_header, authority['plan']['selection']['projection_sha256'],
        base.selection['projection_sha256'])
    narrowed['header_identity'] = deepcopy(old_ref)
    require(set(proof['metadata']) == set(old['metadata']), 'metadata role set differs')
    for name in proof['metadata']:
        if name == 'prelink_plan':
            require({k: proof['metadata'][name][k] for k in ('root', 'path')} ==
                {k: old['metadata'][name][k] for k in ('root', 'path')}, 'prelink coordinate differs')
            narrowed['metadata'][name] = deepcopy(old['metadata'][name])
    require(narrowed == old, 'proof changes beyond approved Guard/generated metadata')
    require(base.inventories['sources'].get(SOURCE) == spec['after_sha256']
        and len(api.checked_read(base.roots['sources'] / SOURCE, spec['after_sha256'])) == spec['after_bytes'],
        'approved Guard source bytes differ')
    result = api.Inspection(base.selection, base.recipe, base.projection, proof, base.roots, base.inventories, config)
    for obj in proof['objects']:
        api._current_context(obj, result)
    return result


def header_identity_transition(previous, current, previous_projection, current_projection):
    require(type(previous) is dict and type(current) is dict
        and previous.get('projection_sha256') == previous_projection
        and current.get('projection_sha256') == current_projection,
        'header identity must join its exact source projection')
    restored = dict(current, projection_sha256=previous_projection)
    require(restored == previous, 'physical header identity changed beyond its derived projection pin')


def context_transition(previous, current, api):
    spec = layout()
    api._completed_context_matches(previous, current)
    key = '{sources}/' + SOURCE
    require(previous['namespace'].get(key) == BEFORE_SHA256
        and current['namespace'].get(key) == spec['after_sha256'], 'Guard include namespace source join differs')
    narrowed = deepcopy(current)
    narrowed['namespace'][key] = BEFORE_SHA256
    require(narrowed == previous, 'include namespace changes beyond the approved Guard TU')


def compiler_bindings(row, api):
    provenance = row['donor_provenance']
    require(provenance['kind'] == api._input_method_module().PROVENANCE_KIND
        and provenance['compile_origin'] in ('select-event-compiled', 'select-event-imported'),
        'inherited object lost accepted InputMethod compiler provenance')
    return api._completed_binding(provenance['compile_bindings'])


def _main_row(authority, old_inspection, api):
    row = deepcopy(authority['descriptor']['main_compiled'])
    api.fields(row, ('id', 'ninja_record', 'ninja_command', 'command_script'), 'retained main compiler declaration')
    require(row['id'] == MAIN, 'only actual InputMethod main compiler may become imported')
    records, bindings, commands = (authority[k] for k in ('records', 'bindings', 'commands'))
    argv, cwd = commands['objects'][MAIN], str(bindings['build'] / 'cmake/build')
    product, depfile = records['objects/' + MAIN + '.o'], records['objects/' + MAIN + '.o.d']
    row.update(object=product, depfile=depfile, original_argv=argv, original_cwd=cwd,
        command_sha256=hashlib.sha256(api.encoded(dict(argv=argv, cwd=cwd))).hexdigest())
    fact = authority['descriptor']['input_method_ninja_log']
    api._successful_module()._fact_shape(fact, bindings['build'] / 'cmake/build/.ninja_log', api)
    require(fact['bytes'] <= 16 * 1024 * 1024, 'Ninja ledger exceeds16MiB')
    ninja = api._completed_fact(fact).decode('utf-8')
    require(ninja.startswith('# ninja log v6\n'), 'Ninja ledger version differs')
    target = str(bindings['build'] / ('objects/' + MAIN + '.o'))
    matching = [line.split('\t') for line in ninja.splitlines()[1:]
        if len(line.split('\t')) == 5 and line.split('\t')[3] == target]
    require(len(matching) == 1 and row['ninja_record'] == matching[0]
        and all(v.isdecimal() for v in row['ninja_record'][:3])
        and int(row['ninja_record'][1]) >= int(row['ninja_record'][0])
        and int(row['ninja_record'][2]) == product['identity'][5]
        and row['ninja_record'][4] == api._completed_ninja_command(row, argv, bindings, old_inspection.proof['host_tools']),
        'main lacks exact successful InputMethod compiler/Ninja authority')
    return row


def admit_donor(ref, base, api):
    authority = accepted_authority(ref, api)
    effective = effective_inspection(base, authority, api)
    old_inspection = _old_inspection(authority, base, api)
    require(authority['actual_vfs'] == api._completed_normalize_vfs(
        api._header_identity(old_inspection)['overlay'], old_inspection.roots), 'actual InputMethod compiler VFS differs')
    old, records, bindings = (authority[k] for k in ('plan', 'records', 'bindings'))
    dependency_refs = api._input_method_module().dependency_refs
    main = _main_row(authority, old_inspection, api)
    raw = api._completed_fact(main['depfile'])
    refs = dependency_refs(raw, main, bindings, authority['freeze'], old_inspection, api)
    main['dependency_keys'] = sorted({os.path.normpath(str(Path(p) if Path(p).is_absolute()
        else Path(main['original_cwd']) / p)) for p in api._depfile_inputs(raw, target=main['object']['path'])})
    rows, closures = {MAIN: main}, {MAIN: refs}
    all_refs = list(refs)
    for inherited in old['successful_donor']['objects']:
        name = inherited['id']
        receipt = api.document(api._completed_fact(records['evidence/import-' + name + '.json']))
        require(receipt.get('object') == inherited['object'] and receipt.get('original_depfile') == inherited['depfile']
            and receipt.get('donor_provenance') == inherited['donor_provenance']
            and receipt.get('compiler_invoked') is False and receipt.get('hardlinked') is False
            and receipt.get('destination') == records['objects/' + name + '.o']['path']
            and receipt.get('sha256') == records['objects/' + name + '.o']['sha256'] == inherited['object']['sha256']
            and receipt.get('bytes') == records['objects/' + name + '.o']['bytes'] == inherited['object']['bytes'],
            'inherited InputMethod independent-copy receipt differs')
        raw = api._completed_fact(records['evidence/import-' + name + '.original.d'])
        require(raw == api._completed_fact(inherited['depfile']), 'inherited original depfile bytes differ')
        deps = dependency_refs(raw, inherited, compiler_bindings(inherited, api), authority['freeze'], old_inspection, api)
        all_refs.extend(deps)
        rows[name], closures[name] = deepcopy(inherited), deps
        rows[name]['object'] = records['objects/' + name + '.o']
    shim = dict(id=SHIM, original_argv=authority['commands']['objects'][SHIM],
        original_cwd=str(bindings['build'] / 'cmake/build'))
    closures[SHIM] = dependency_refs(api._completed_fact(records['objects/' + SHIM + '.o.d']),
        shim, bindings, authority['freeze'], old_inspection, api, generated=True)
    all_refs.extend(closures[SHIM])
    api._input_method_module().validate_dependency_owners(closures)
    previous = api._completed_header_context(old_inspection, all_refs, old_inspection.proof['objects'])
    current = api._completed_header_context(effective, all_refs, effective.proof['objects'])
    context_transition(previous, current, api)
    imported = []
    for obj in effective.proof['objects']:
        name = obj['id']
        if name in FRESH:
            continue
        row = rows[name]
        for dep in closures[name]:
            api.ref_path(dep, effective.roots, effective.inventories)
        api._completed_fact(row['object'])
        row['donor_provenance'] = dict(kind=PROVENANCE_KIND,
            parent_root_acceptance=authority['descriptor']['root_acceptance'],
            parent_object=records['objects/' + name + '.o'], predecessor=row.get('donor_provenance'),
            compile_bindings={k: str(v) for k, v in
                (bindings if name == MAIN else compiler_bindings(row, api)).items()},
            compile_origin='input-method-compiled' if name == MAIN else 'input-method-imported')
        imported.append(row)
    require(len(imported) == 50 and {MAIN, OWNER} <= {r['id'] for r in imported}
        and not set(FRESH) & {r['id'] for r in imported}, 'requires50 imports including main and Unified13')
    archives = []
    for row in old['successful_donor']['archives']:
        name = row['name']
        fact, report = records['archives/lib' + name + '.a'], records['evidence/archive-' + name + '.json']
        require(fact['sha256'] == row['archive']['sha256'] and fact['bytes'] == row['archive']['bytes']
            and api._completed_fact(report) == api._completed_fact(row['report']), 'unchanged accepted archive differs')
        api._completed_fact(fact)
        archives.append(dict(name=name, archive=fact, report=report))
    inherited = old['successful_donor']
    metadata = set(inherited['metadata_directories'])
    metadata.update(str(Path(v['path']).parent) for v in authority['descriptor'].values()
        if type(v) is dict and 'path' in v)
    return dict(reference=dict(ref), objects=imported, archives=archives,
        original_bindings=inherited['original_bindings'], dependency_sidecar=inherited['dependency_sidecar'],
        additional_input_directories=sorted(set(inherited.get('additional_input_directories', []))
            | {str(v) for v in bindings.values()}), metadata_directories=sorted(metadata)), effective


def producer_inputs(api):
    return {name: api.digest(api.ROOT / name) for name in
        (*api._input_method_module().producer_inputs(api), HELPER)}


def _helper_admitted(base, api):
    for name, pin in producer_inputs(api).items():
        require(base.inventories['sources'].get(name) == pin, 'retain exact producer helper: ' + name)


def make_plan(selection, output, donor_ref, transition, api):
    spec = layout(transition)
    base = api.inspect_inputs(selection, _retained_transition=transition)
    _helper_admitted(base, api)
    donor, inspected = admit_donor(donor_ref, base, api)
    destination = api.engine_sdk.new_destination(output, (*base.roots.values(), *api._completed_input_directories(donor)))
    plan = dict(schema_version=1, kind=PLAN_KIND, scope=api.SCOPE, selection=inspected.selection,
        profile_sha256=api.digest(api.ROOT / api.profile_path('editor')), producer_inputs=producer_inputs(api),
        retained_transition=spec, reuse=inspected.proof, projection=base.projection,
        production_eligible=False, successful_donor=donor)
    with api.engine_sdk._OwnedTree(destination.parent, '.engine-retained-successor-plan-') as staged:
        (staged.path / 'plan.json').write_bytes(api.encoded(plan))
        staged.publish(destination)
    return dict(scope=api.SCOPE, plan=str(destination / 'plan.json'),
        plan_sha256=api.digest(destination / 'plan.json'), production_eligible=False)


def verify_plan(plan, api):
    api.fields(plan, ('schema_version', 'kind', 'scope', 'selection', 'profile_sha256', 'producer_inputs',
        'retained_transition', 'reuse', 'projection', 'production_eligible', 'successful_donor'), 'retained successor plan')
    require(type(plan['retained_transition']) is dict, 'plan layout must be an exact object')
    spec = layout(plan['retained_transition'].get('transition'))
    require(type(plan['schema_version']) is int and plan['schema_version'] == 1 and plan['kind'] == PLAN_KIND
        and plan['scope'] == api.SCOPE and plan['production_eligible'] is False
        and plan['retained_transition'] == spec
        and plan['profile_sha256'] == api.digest(api.ROOT / api.profile_path('editor'))
        and plan['producer_inputs'] == producer_inputs(api), 'plan layout/producer/profile identity changed')
    base = api.inspect_inputs(plan['selection'], _retained_transition=spec['transition'])
    _helper_admitted(base, api)
    donor, effective = admit_donor(plan['successful_donor']['reference'], base, api)
    require(plan['reuse'] == effective.proof and plan['projection'] == base.projection
        and plan['successful_donor'] == donor, 'effective graph or donor changed')
    return plan, effective


def validate_fresh_members(name, refs):
    if name == GUARD:
        require(dict(root='sources', path=SOURCE, sha256=layout()['after_sha256']) in refs,
            'fresh Guard depfile omits its reviewed source')


def build_receipt(result, plan, inspected, output, commands, api):
    require(plan.get('kind') == PLAN_KIND and plan.get('retained_transition') == layout(), 'receipt layout differs')
    api._theme_module()._record_import_receipts(result, plan, output, commands, api)
    counts = result['accounting']
    names = [row['id'] for row in inspected.proof['objects']]
    archives = [row['name'] for row in inspected.proof['archives']]
    require(counts['compiled'] == 2 and counts['imported'] == 50 and set(counts['compiled_ids']) == set(FRESH)
        and [r['id'] for r in plan['successful_donor']['objects']] == counts['imported_ids']
        and set(commands['archive_imports']) == set(archives), 'receipt2/50/5 partition differs')
    for row in plan['successful_donor']['objects']:
        receipt = api.checked_document(Path(output) / ('evidence/import-' + row['id'] + '.json'))
        require(receipt.get('donor_provenance') == row['donor_provenance']
            and row['donor_provenance']['kind'] == PROVENANCE_KIND, 'import lost original compiler history')
    reports = []
    for row in plan['successful_donor']['archives']:
        file = Path(output) / ('evidence/import-archive-' + row['name'] + '.json')
        receipt = api.checked_document(file)
        target = api.ordinary(Path(output) / ('archives/lib' + row['name'] + '.a'))
        require(receipt.get('kind') == 'foundation-document-v2-archive-import-v1'
            and receipt.get('archive') == row['archive'] and receipt.get('original_report') == row['report']
            and receipt.get('name') == row['name'] and receipt.get('origin') == 'imported'
            and receipt.get('destination') == str(target) and receipt.get('hardlinked') is False
            and receipt.get('archive_program_invoked') is False and receipt.get('production_eligible') is False
            and receipt.get('sha256') == api.digest(target) == row['archive']['sha256']
            and receipt.get('bytes') == target.stat().st_size == row['archive']['bytes']
            and target.stat().st_nlink == 1 and api._identity7(target.stat())[:2] != row['archive']['identity'][:2],
            'archive independent copy/readback differs')
        reports.append(dict(name=row['name'], receipt=str(file.relative_to(output)), sha256=api.digest(file)))
    for name in artifact_names(names, archives):
        api.ordinary(Path(output) / name)
    bindings = api._completed_binding(dict(sources=str(inspected.roots['sources']), sdk=str(inspected.roots['sdk']),
        reuse=str(inspected.roots['reuse']), build=str(output)))
    for name in FRESH:
        row = dict(id=name, original_argv=commands['objects'][name], original_cwd=str(Path(output) / 'cmake/build'))
        refs = api._input_method_module().dependency_refs(api.checked_read(Path(output) / ('objects/' + name + '.o.d')),
            row, bindings, None, inspected, api, generated=name == SHIM)
        validate_fresh_members(name, refs)
    final_map(api.checked_read(Path(output) / 'evidence/engine-link.map'), output, api)
    result.update(kind=BUILD_KIND, retained_transition=layout(), expected_artifact_records=174, archive_imports=reports)
    result['accounting'].update(archive_imported=5, archive_repacked=0, imported_archive_names=archives)


def final_map(raw, output, api):
    return api._select_event_module().final_map(raw, output, api)


def validate_proof_location(selection, path, sources, source_files):
    require(selection['document_profile'] == 'editor' and path == sources / PROOF_SOURCE
        and source_files.get(PROOF_SOURCE) == selection['reuse_proof_sha256'],
        'proof must be the pinned inventoried successor metadata')


def validate_metadata_overlay(proof):
    require(proof['header_identity']['root'] == 'sources'
        and proof['header_identity']['path'] == HEADER_IDENTITY_SOURCE,
        'must preserve accepted InputMethod header283 identity')
    def visit(value):
        if type(value) is dict:
            require(not (value.get('root') == 'sources'
                and value.get('path') in (PROOF_SOURCE, 'sources.json', 'recipe.json')), 'metadata hash cycle')
            for item in value.values():
                visit(item)
        elif type(value) is list:
            for item in value:
                visit(item)
    visit(proof)
